"""Local Windows installer for a signed Blatero release package."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

import release_manager


def _empty_or_missing(path: Path) -> bool:
    return not path.exists() or (path.is_dir() and not any(path.iterdir()))


def _write_installed_state(data_dir: Path, info: dict) -> None:
    state = {
        "schema_version": 1,
        "version": info["version"],
        "installed_at": release_manager._now(),
        "files": info["files"],
        "package_sha256": info["package_sha256"],
    }
    target = data_dir / ".updates" / "installed-release.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".tmp")
    temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, target)


def _installed_payload_matches(install_dir: Path, data_dir: Path,
                               info: dict, *, dependencies: bool) -> bool:
    """Recognize a fully published install whose final state write was interrupted."""
    pointer = install_dir / ".blatero-data-dir"
    try:
        if Path(pointer.read_text(encoding="utf-8").strip()).resolve() != data_dir:
            return False
    except (OSError, ValueError):
        return False
    files = info.get("files")
    if not isinstance(files, dict) or not files:
        return False
    for raw_name, metadata in files.items():
        if not isinstance(metadata, dict):
            return False
        target = install_dir.joinpath(*Path(str(raw_name)).parts)
        try:
            if (not target.is_file()
                    or target.stat().st_size != int(metadata.get("size", -1))
                    or release_manager._sha256(target) != metadata.get("sha256")):
                return False
        except (OSError, TypeError, ValueError):
            return False
    if dependencies and not (
            install_dir / ".venv" / "Scripts" / "python.exe").is_file():
        return False
    return True


def _shortcut_result(install_dir: Path, requested: bool) -> tuple[Path | None, list[str]]:
    if not requested:
        return None, []
    try:
        return _create_desktop_shortcut(install_dir), []
    except Exception as exc:
        return None, [
            "программа установлена, но ярлык не создан: "
            f"{type(exc).__name__}: {exc}"]


def _result(info: dict, install_dir: Path, data_dir: Path,
            shortcut: Path | None, warnings: list[str], *, repaired: bool = False) -> dict:
    return {
        "version": info["version"],
        "install_dir": str(install_dir),
        "data_dir": str(data_dir),
        "shortcut": str(shortcut) if shortcut else "",
        "warnings": warnings,
        "repaired": repaired,
    }


def _known_folder(name: str, fallback: Path) -> Path:
    """Resolve redirected Windows folders instead of concatenating USERPROFILE."""
    if os.name != "nt":
        return fallback
    script = (
        "[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false);"
        f"[Environment]::GetFolderPath('{name}')")
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8")
        value = result.stdout.strip()
        return Path(value) if value else fallback
    except (OSError, subprocess.SubprocessError, UnicodeError):
        return fallback


def _create_desktop_shortcut(install_dir: Path) -> Path:
    home = Path(os.environ.get("USERPROFILE", str(Path.home())))
    desktop = _known_folder("Desktop", home / "Desktop")
    desktop.mkdir(parents=True, exist_ok=True)
    shortcut = desktop / "Blatero.lnk"
    environment = os.environ.copy()
    environment["BLATERO_SHORTCUT"] = str(shortcut)
    environment["BLATERO_TARGET"] = str(install_dir / "start_blatero.cmd")
    environment["BLATERO_WORKDIR"] = str(install_dir)
    environment["BLATERO_ICON"] = str(install_dir / "assets" / "blatero.ico")
    script = (
        "$w=New-Object -ComObject WScript.Shell;"
        "$s=$w.CreateShortcut($env:BLATERO_SHORTCUT);"
        "$s.TargetPath=$env:BLATERO_TARGET;"
        "$s.WorkingDirectory=$env:BLATERO_WORKDIR;"
        "$s.IconLocation=$env:BLATERO_ICON+',0';"
        "$s.Description='Blatero — локальный ассистент встреч';"
        "$s.Save()"
    )
    subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
        env=environment, check=True, stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE, text=True)
    return shortcut


def install(package: str | Path, install_dir: str | Path, data_dir: str | Path,
            *, create_shortcut: bool = True,
            install_dependencies: bool = True) -> dict:
    package = Path(package).resolve()
    install_dir = Path(install_dir).resolve()
    data_dir = Path(data_dir).resolve()
    if install_dir == data_dir or install_dir in data_dir.parents or data_dir in install_dir.parents:
        raise ValueError("каталоги программы и данных должны быть раздельными")
    info = release_manager.verify_package(package)
    if not _empty_or_missing(install_dir):
        if not _installed_payload_matches(
                install_dir, data_dir, info, dependencies=install_dependencies):
            raise ValueError(
                "каталог программы не пуст и не совпадает с этим релизом")
        # A crash after publishing the app but before this state write is safe to
        # repair by repeating the same signed installation.
        _write_installed_state(data_dir, info)
        shortcut, warnings = _shortcut_result(install_dir, create_shortcut)
        return _result(
            info, install_dir, data_dir, shortcut, warnings, repaired=True)
    install_dir.parent.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix="blatero-install-", dir=install_dir.parent))
    try:
        release_manager.extract_verified(package, temporary)
        (temporary / ".blatero-data-dir").write_text(
            str(data_dir) + "\n", encoding="utf-8")
        if install_dependencies:
            subprocess.run(
                [sys.executable, "-m", "venv", str(temporary / ".venv")],
                check=True)
            python = temporary / ".venv" / "Scripts" / "python.exe"
            subprocess.run([
                str(python), "-m", "pip", "install", "--disable-pip-version-check",
                "-r", str(temporary / "requirements.lock")], check=True)
            lock_digest = release_manager._sha256(temporary / "requirements.lock")
            (temporary / ".venv" / ".blatero-lock-sha256").write_text(
                lock_digest + "\n", encoding="ascii")
        if install_dir.exists():
            install_dir.rmdir()
        os.replace(temporary, install_dir)
        _write_installed_state(data_dir, info)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    shortcut, warnings = _shortcut_result(install_dir, create_shortcut)
    return _result(info, install_dir, data_dir, shortcut, warnings)


def _default_paths() -> tuple[Path, Path]:
    local = Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
    home = Path(os.environ.get("USERPROFILE", str(Path.home())))
    documents = _known_folder("MyDocuments", home / "Documents")
    return local / "Programs" / "Blatero", documents / "Blatero"


def gui() -> int:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    install_default, data_default = _default_paths()
    root = tk.Tk()
    root.title("Установка Blatero")
    root.geometry("760x430")
    root.minsize(680, 400)
    package = tk.StringVar()
    install_path = tk.StringVar(value=str(install_default))
    data_path = tk.StringVar(value=str(data_default))
    shortcut = tk.BooleanVar(value=True)
    status = tk.StringVar(value="Выберите подписанный ZIP-релиз Blatero.")

    frame = ttk.Frame(root, padding=22)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="Blatero", font=("Segoe UI", 20, "bold")).pack(anchor="w")
    ttk.Label(frame, text=(
        "Код программы и ваши данные хранятся отдельно. Обновление меняет только "
        "код; записи, модели, токены и голосовой профиль остаются в каталоге данных."),
        wraplength=700).pack(anchor="w", pady=(5, 18))

    def row(label: str, variable: tk.StringVar, browse) -> None:
        box = ttk.Frame(frame)
        box.pack(fill="x", pady=5)
        ttk.Label(box, text=label, width=19).pack(side="left")
        ttk.Entry(box, textvariable=variable).pack(side="left", fill="x", expand=True)
        ttk.Button(box, text="Обзор…", command=browse).pack(side="left", padx=(8, 0))

    row("Подписанный релиз", package, lambda: package.set(
        filedialog.askopenfilename(filetypes=[("Blatero release", "*.zip")]) or package.get()))
    row("Каталог программы", install_path, lambda: install_path.set(
        filedialog.askdirectory() or install_path.get()))
    row("Каталог данных", data_path, lambda: data_path.set(
        filedialog.askdirectory() or data_path.get()))
    ttk.Checkbutton(frame, text="Создать ярлык Blatero на рабочем столе",
                    variable=shortcut).pack(anchor="w", pady=(12, 5))
    ttk.Label(frame, textvariable=status, wraplength=700).pack(anchor="w", pady=8)
    actions = ttk.Frame(frame)
    actions.pack(fill="x", side="bottom")
    install_button = ttk.Button(actions, text="Установить")
    install_button.pack(side="right")

    def worker(package_value: str, install_value: str, data_value: str,
               shortcut_value: bool) -> None:
        try:
            result = install(package_value, install_value, data_value,
                             create_shortcut=shortcut_value)
        except Exception as exc:
            error = str(exc)
            root.after(0, lambda: (
                status.set(f"Установка не завершена: {error}"),
                install_button.configure(state="normal"),
                messagebox.showerror("Blatero", error)))
            return
        def finish() -> None:
            warnings = list(result.get("warnings") or [])
            status.set(f"Blatero {result['version']} установлен.")
            if warnings:
                messagebox.showwarning(
                    "Blatero", "Установка завершена.\n\n" + "\n".join(warnings))
            else:
                messagebox.showinfo(
                    "Blatero", "Установка завершена. Запустите Blatero ярлыком.")
            root.destroy()
        root.after(0, finish)

    def start() -> None:
        if not package.get().strip():
            messagebox.showwarning("Blatero", "Сначала выберите ZIP-релиз.")
            return
        install_button.configure(state="disabled")
        status.set("Проверяю подпись и устанавливаю зависимости…")
        threading.Thread(
            target=worker,
            args=(package.get(), install_path.get(), data_path.get(), shortcut.get()),
            daemon=True,
        ).start()

    install_button.configure(command=start)
    root.mainloop()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Установка Blatero")
    parser.add_argument("--gui", action="store_true")
    parser.add_argument("--package")
    parser.add_argument("--install-dir")
    parser.add_argument("--data-dir")
    parser.add_argument("--no-shortcut", action="store_true")
    args = parser.parse_args()
    if args.gui or not args.package:
        return gui()
    if not args.install_dir or not args.data_dir:
        parser.error("--install-dir и --data-dir обязательны")
    result = install(args.package, args.install_dir, args.data_dir,
                     create_shortcut=not args.no_shortcut)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
