"""Build a self-contained Windows x64 ZIP with a pinned Python runtime.

The result does not require Python to be installed on the target machine. It is
still a portable ZIP, not a publicly trusted installer: Authenticode/MSIX
signing is intentionally outside the selected local OSS delivery model.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import stat
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ci import build_release  # noqa: E402
from ci import offline_help  # noqa: E402


PYTHON_VERSION = "3.12.10"
PYTHON_ARCHIVE = f"python-{PYTHON_VERSION}-embed-amd64.zip"
PYTHON_URL = f"https://www.python.org/ftp/python/{PYTHON_VERSION}/{PYTHON_ARCHIVE}"
PYTHON_SHA256 = "4acbed6dd1c744b0376e3b1cf57ce906f9dc9e95e68824584c8099a63025a3c3"
PORTABLE_REQUIREMENTS = ROOT / "requirements-portable.txt"
MANIFEST_NAME = "_integrity/portable-manifest.json"
SIGNATURE_NAME = "_integrity/portable-manifest.sig"
README_NAME = "PORTABLE_README.txt"
LAUNCHER_NAME = "Blatero.exe"
PORTABLE_APP_EXCLUDES = {
    "DEVLOG.md",
    "debug_two_channels.py",
    "devices_check.py",
    "README.md",
    "README.en.md",
    "PRIVACY.md",
    "TRANSCRIPT_FORMAT.md",
    "DIARIZATION_MODELS.md",
    "install_blatero.py",
    "test_roundtrip.py",
    "ci/generate_release_key.py",
    "ci/release_step.py",
}
PORTABLE_APP_EXCLUDE_PREFIXES = (
    "ci/portable_launcher/",
)
MAX_RUNTIME_ARCHIVE_BYTES = 32 * 1024**2
MAX_RUNTIME_FILES = 100
MAX_RUNTIME_FILE_BYTES = 20 * 1024**2
MAX_PACKAGE_BYTES = 2 * 1024**3
MAX_PAYLOAD_BYTES = 4 * 1024**3
MAX_PAYLOAD_FILES = 50_000
MAX_METADATA_BYTES = 16 * 1024**2
DOCOPT_SOURCE = (
    "https://files.pythonhosted.org/packages/a2/55/"
    "8f8cab2afd404cf578136ef2cc5dfb50baa1761b68c9da1fb1e4eed343c9/"
    "docopt-0.6.2.tar.gz#sha256="
    "49b3a825280bd66b3aa83585ef59c4a8c82f2c8a522dbe754a8bc8d08c85c491")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _download_runtime(cache: Path) -> Path:
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / PYTHON_ARCHIVE
    if target.is_file() and _sha256(target) == PYTHON_SHA256:
        return target
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.unlink(missing_ok=True)
    # URL is a compile-time python.org HTTPS constant; bytes are verified by
    # PYTHON_SHA256 before extraction.
    with urllib.request.urlopen(  # nosec B310
            PYTHON_URL, timeout=60) as response, temporary.open("wb") as output:
        if response.status != 200:
            raise RuntimeError(f"Python runtime download failed: HTTP {response.status}")
        shutil.copyfileobj(response, output, length=1024 * 1024)
    if temporary.stat().st_size > MAX_RUNTIME_ARCHIVE_BYTES:
        temporary.unlink(missing_ok=True)
        raise ValueError("Python runtime archive is unexpectedly large")
    if _sha256(temporary) != PYTHON_SHA256:
        temporary.unlink(missing_ok=True)
        raise ValueError("Python runtime SHA-256 mismatch")
    os.replace(temporary, target)
    return target


def _safe_extract_runtime(archive: Path, destination: Path) -> None:
    if archive.stat().st_size > MAX_RUNTIME_ARCHIVE_BYTES:
        raise ValueError("Python runtime archive is too large")
    with zipfile.ZipFile(archive) as source:
        entries = source.infolist()
        if not entries or len(entries) > MAX_RUNTIME_FILES:
            raise ValueError("unexpected Python runtime archive layout")
        for entry in entries:
            path = PurePosixPath(entry.filename)
            if (path.is_absolute() or not path.parts or ".." in path.parts
                    or entry.is_dir() or entry.file_size > MAX_RUNTIME_FILE_BYTES):
                raise ValueError(f"unsafe Python runtime member: {entry.filename}")
            target = destination.joinpath(*path.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name(target.name + ".tmp")
            with source.open(entry) as incoming, temporary.open("wb") as output:
                shutil.copyfileobj(incoming, output, length=1024 * 1024)
            os.replace(temporary, target)


def _configure_runtime(runtime: Path) -> None:
    pth = runtime / "python312._pth"
    if not pth.is_file():
        raise ValueError("python312._pth is missing")
    pth.write_text(
        "python312.zip\n.\n../app\n..\nLib/site-packages\nimport site\n",
        encoding="utf-8",
        newline="\n",
    )
    license_file = runtime / "LICENSE.txt"
    if not license_file.is_file():
        raise ValueError("Python LICENSE.txt is missing")
    license_file.replace(runtime / "PYTHON-LICENSE.txt")


def _write_launcher_icon(path: Path) -> None:
    # The same multi-resolution asset as the desktop shortcut and favicon.
    # CI and end users do not need CairoSVG/Pillow to rebuild the launcher.
    shutil.copyfile(ROOT / "assets" / "blatero.ico", path)


def _build_launcher(bundle: Path) -> None:
    csc = Path(os.environ.get(
        "WINDIR", r"C:\Windows")) / "Microsoft.NET" / "Framework64" / "v4.0.30319" / "csc.exe"
    if not csc.is_file():
        csc = Path(os.environ.get(
            "WINDIR", r"C:\Windows")) / "Microsoft.NET" / "Framework" / "v4.0.30319" / "csc.exe"
    if not csc.is_file():
        raise RuntimeError("C# compiler for portable launcher was not found")
    icon = bundle / ".blatero-launcher.ico"
    _write_launcher_icon(icon)
    source = ROOT / "ci" / "portable_launcher" / "BlateroLauncher.cs"
    subprocess.run([
        str(csc), "/nologo", "/target:winexe", "/optimize+",
        "/reference:System.dll", "/reference:System.Drawing.dll",
        "/reference:System.Windows.Forms.dll",
        f"/win32icon:{icon}", f"/out:{bundle / LAUNCHER_NAME}", str(source),
    ], cwd=ROOT, check=True)
    icon.unlink(missing_ok=True)


def _copy_application(bundle: Path) -> int:
    count = 0
    for name in build_release.validate_runtime_inventory(build_release._tracked_files(), root=ROOT):
        if name in PORTABLE_APP_EXCLUDES or any(
                name.startswith(prefix) for prefix in PORTABLE_APP_EXCLUDE_PREFIXES):
            continue
        if name in {"start_blatero.cmd", "install_blatero.cmd"}:
            continue
        source = ROOT / Path(*PurePosixPath(name).parts)
        relative = Path(*PurePosixPath(name).parts)
        if name.startswith(("docs/wiki/", "docs/legal/")):
            target = bundle / relative
        else:
            target = bundle / "app" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        count += 1
    shutil.copy2(ROOT / "start_blatero.cmd", bundle / "app" / "start_blatero.cmd")
    offline_help.build(bundle / "docs")
    help_errors = offline_help.validate(bundle / "docs")
    if help_errors:
        raise ValueError("invalid offline help: " + "; ".join(help_errors))
    (bundle / "app" / ".portable-runtime").write_text(
        f"python={PYTHON_VERSION}\narchitecture=win_amd64\n", encoding="ascii")
    (bundle / "app" / ".blatero-data-dir").write_text(
        "%USERPROFILE%\\Documents\\Blatero\n", encoding="utf-8")
    _build_launcher(bundle)
    (bundle / README_NAME).write_text(
        "Blatero — переносимая сборка для Windows x64\n"
        "\n"
        "1. Распакуйте весь ZIP в отдельную папку.\n"
        "2. Запустите Blatero.exe двойным щелчком.\n"
        "3. Если это первый запуск на машине, нажмите «Проверить установку».\n"
        "4. Нажмите «Запустить Blatero» и дождитесь открытия браузера.\n"
        "5. Документация открывается из Blatero.exe или из docs\\wiki\\Home.html.\n"
        "6. Перед рабочими записями прочитайте docs\\legal\\RECORDING_POLICY.md.\n"
        "\n"
        "Рабочие данные хранятся в %USERPROFILE%\\Documents\\Blatero и не\n"
        "удаляются вместе с папкой программы. Интернет нужен только для явно\n"
        "выбранных облачных провайдеров, календарей, обновлений и установки\n"
        "дополнительных моделей.\n"
        "\n"
        "Лицензия кода Blatero — MIT: app\\LICENSE. Условия использования:\n"
        "docs\\legal\\EVALUATION_LICENSE.md.\n"
        "\n"
        "Это подписанный внутренним ключом portable-пакет, а не Authenticode-\n"
        "подписанный установщик Windows. Проверка целостности:\n"
        "  runtime\\python.exe app\\ci\\build_windows_portable.py --verify <архив.zip>\n",
        encoding="utf-8",
        newline="\n",
    )
    with (bundle / README_NAME).open("a", encoding="utf-8", newline="\n") as guide:
        guide.write(
            "\nENGLISH\n"
            "1. Extract the entire ZIP into a dedicated folder. Run Blatero.exe.\n"
            "2. Check installation, then Start Blatero; configure your own audio and keys.\n"
            "3. Offline help: docs\\wiki\\en\\Home.html (Russian: docs\\wiki\\Home.html).\n"
            "4. Data is kept in your Windows Documents\\Blatero folder, separately from code.\n"
            "5. Blatero code is MIT-licensed: app\\LICENSE. Terms of use:\n"
            "   docs\\legal\\EVALUATION_LICENSE.md; read RECORDING_POLICY.md before use.\n"
            "6. Test in the test data environment before a real meeting.\n"
            "The package has Ed25519 integrity signing, not public Windows publisher trust.\n"
            "Verify ZIP: runtime\\python.exe app\\ci\\build_windows_portable.py --verify <archive.zip>\n")
    return count


def _prepare_wheels(wheelhouse: Path) -> list[dict]:
    if sys.version_info[:2] != (3, 12) or sys.platform != "win32":
        raise RuntimeError("portable dependencies must be resolved by Windows Python 3.12")
    wheelhouse.mkdir(parents=True, exist_ok=True)
    # docopt publishes only an sdist. Build this exact hashed pure-Python source
    # on the release machine, never on the recipient's computer. All other
    # dependencies must still have binary wheels; do not enable a broad fallback.
    subprocess.run([
        sys.executable, "-m", "pip", "wheel", "--disable-pip-version-check",
        "--no-deps", "--no-build-isolation", "--wheel-dir", str(wheelhouse),
        DOCOPT_SOURCE,
    ], cwd=ROOT, check=True)
    subprocess.run([
        sys.executable, "-m", "pip", "download", "--disable-pip-version-check",
        "--only-binary=:all:", "--find-links", str(wheelhouse), "--dest", str(wheelhouse),
        "-r", str(PORTABLE_REQUIREMENTS),
    ], cwd=ROOT, check=True)
    wheels = sorted(wheelhouse.glob("*.whl"), key=lambda path: path.name.casefold())
    if not wheels:
        raise RuntimeError("portable wheelhouse is empty")
    return [{"name": path.name, "sha256": _sha256(path), "size": path.stat().st_size}
            for path in wheels]


def _install_dependencies(runtime: Path, wheelhouse: Path) -> None:
    target = runtime / "Lib" / "site-packages"
    target.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        sys.executable, "-m", "pip", "install", "--disable-pip-version-check",
        "--no-index", "--no-compile", "--upgrade", "--target", str(target),
        "--find-links", str(wheelhouse), "-r", str(PORTABLE_REQUIREMENTS),
    ], cwd=ROOT, check=True)
    _finalize_runtime_packages(runtime, target)
    digest = hashlib.sha256((ROOT / "requirements.lock").read_bytes()).hexdigest()
    (runtime / ".blatero-lock-sha256").write_text(digest + "\n", encoding="ascii")
    _prune_runtime_junk(target)


def _finalize_runtime_packages(runtime: Path, site_packages: Path) -> None:
    # The locked urllib3-future wheel installs a startup hook that replaces
    # urllib3's files when both distributions are present. Run it in our owned
    # staging runtime before signing, then drop the now redundant write hook.
    hook = site_packages / "urllib3_future.pth"
    if not hook.is_file():
        return
    subprocess.run([
        str(runtime / "python.exe"), "-B", "-c",
        "import urllib3, urllib3_future; "
        "assert urllib3.__version__ == urllib3_future.__version__",
    ], cwd=runtime, check=True)
    if (site_packages / "urllib3/_base_connection.py").exists():
        raise RuntimeError("urllib3 replacement did not finish in the staging runtime")
    hook.unlink()


def _prune_runtime_junk(site_packages: Path) -> int:
    removed = 0
    for path in sorted(site_packages.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        if path.is_dir() and path.name.casefold() in {"test", "tests"}:
            shutil.rmtree(path, ignore_errors=True)
            removed += 1
        elif path.is_dir() and path.name == "__pycache__":
            shutil.rmtree(path, ignore_errors=True)
            removed += 1
        elif path.is_file() and path.suffix in {".pyc", ".pyo"}:
            path.unlink(missing_ok=True)
            removed += 1
    return removed


def _file_manifest(bundle: Path) -> dict[str, dict]:
    result = {}
    for path in sorted(bundle.rglob("*"), key=lambda item: item.as_posix().casefold()):
        if not path.is_file() or path.name in {MANIFEST_NAME, SIGNATURE_NAME}:
            continue
        name = path.relative_to(bundle).as_posix()
        result[name] = {"sha256": _sha256(path), "size": path.stat().st_size}
    return result


def _write_manifest(bundle: Path, version: str, wheels: list[dict],
                    private_key_path: Path | None) -> dict:
    manifest = {
        "schema_version": 1,
        "product": "blatero-portable",
        "version": version,
        "platform": "windows-x86_64",
        "python": {"version": PYTHON_VERSION, "archive": PYTHON_ARCHIVE,
                   "sha256": PYTHON_SHA256, "url": PYTHON_URL},
        "requirements_sha256": _sha256(ROOT / "requirements-portable.txt"),
        "source_commit": subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, text=True,
            stdout=subprocess.PIPE).stdout.strip(),
        "created_at": build_release._created_at(),
        "wheels": wheels,
        "files": _file_manifest(bundle),
    }
    encoded = json.dumps(
        manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    (bundle / MANIFEST_NAME).parent.mkdir(parents=True, exist_ok=True)
    (bundle / MANIFEST_NAME).write_bytes(encoded)
    if private_key_path is not None:
        private = serialization.load_pem_private_key(
            private_key_path.read_bytes(), password=None)
        if not isinstance(private, Ed25519PrivateKey):
            raise ValueError("portable signing key must be Ed25519")
        (bundle / SIGNATURE_NAME).write_bytes(base64.b64encode(private.sign(encoded)))
    return manifest


def _zip_bundle(bundle: Path, output: Path) -> dict:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=9, allowZip64=True) as archive:
        for path in sorted(bundle.rglob("*"), key=lambda item: item.as_posix().casefold()):
            if not path.is_file():
                continue
            name = path.relative_to(bundle).as_posix()
            with path.open("rb") as source, archive.open(
                    build_release._zip_info(name), "w") as target:
                shutil.copyfileobj(source, target, length=1024 * 1024)
    os.replace(temporary, output)
    digest = _sha256(output)
    output.with_suffix(output.suffix + ".sha256").write_text(
        f"{digest}  {output.name}\n", encoding="ascii")
    return {"output": str(output), "sha256": digest, "size": output.stat().st_size}


def verify(package: Path, public_key_path: Path) -> dict:
    package = package.resolve(strict=True)
    if package.stat().st_size > MAX_PACKAGE_BYTES:
        raise ValueError("portable package is too large")
    public = serialization.load_pem_public_key(public_key_path.read_bytes())
    with zipfile.ZipFile(package) as archive:
        entries = archive.infolist()
        names = [entry.filename for entry in entries]
        folded_names = [name.casefold() for name in names]
        if (len(entries) > MAX_PAYLOAD_FILES + 2
                or len(names) != len(set(names))
                or len(folded_names) != len(set(folded_names))):
            raise ValueError("portable package has duplicate or excessive entries")
        by_name = {entry.filename: entry for entry in entries}
        if MANIFEST_NAME not in by_name or SIGNATURE_NAME not in by_name:
            raise ValueError("portable package signature is missing")
        if (by_name[MANIFEST_NAME].file_size > MAX_METADATA_BYTES
                or by_name[SIGNATURE_NAME].file_size > MAX_METADATA_BYTES):
            raise ValueError("portable package metadata is too large")
        manifest_bytes = archive.read(by_name[MANIFEST_NAME])
        signature = base64.b64decode(archive.read(by_name[SIGNATURE_NAME]), validate=True)
        public.verify(signature, manifest_bytes)
        manifest = json.loads(manifest_bytes)
        files = manifest.get("files")
        if (manifest.get("schema_version") != 1
                or manifest.get("product") != "blatero-portable"
                or not isinstance(files, dict) or len(files) > MAX_PAYLOAD_FILES):
            raise ValueError("invalid portable manifest")
        expected = set(files) | {MANIFEST_NAME, SIGNATURE_NAME}
        if set(names) != expected:
            raise ValueError("portable package content differs from manifest")
        total = 0
        for name, metadata in files.items():
            if not isinstance(name, str) or not isinstance(metadata, dict):
                raise ValueError("invalid portable file metadata")
            path = PurePosixPath(name)
            entry = by_name.get(name)
            mode = (entry.external_attr >> 16) if entry else 0
            if (entry is None or not name or "\\" in name or "\x00" in name
                    or path.is_absolute() or any(part in {"", ".", ".."}
                                                for part in path.parts)
                    or path.parts[0].endswith(":") or entry.is_dir()
                    or stat.S_ISLNK(mode)):
                raise ValueError(f"unsafe portable member: {name}")
            size = int(metadata.get("size", -1))
            if size != entry.file_size or size < 0:
                raise ValueError(f"portable size mismatch: {name}")
            total += size
            if total > MAX_PAYLOAD_BYTES:
                raise ValueError("portable payload is too large")
            digest = hashlib.sha256()
            with archive.open(entry) as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(block)
            if digest.hexdigest() != metadata.get("sha256"):
                raise ValueError(f"portable SHA-256 mismatch: {name}")
    return {"version": str(manifest.get("version", "")), "files": len(files),
            "package": str(package), "sha256": _sha256(package), "size": package.stat().st_size}


def build(output: Path, *, cache: Path, wheelhouse: Path,
          private_key_path: Path | None = None, version: str | None = None) -> dict:
    if version is None:
        import tomllib
        version = str(tomllib.loads(
            (ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"])
    runtime_archive = _download_runtime(cache)
    # Do not mix old dependency versions into the signed wheel inventory.
    lock_identity = build_release.generate_sbom.build(PORTABLE_REQUIREMENTS)["serialNumber"]
    wheelhouse = wheelhouse / hashlib.sha256(lock_identity.encode("ascii")).hexdigest()[:20]
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary_root = Path(tempfile.mkdtemp(prefix="blatero-portable-", dir=output.parent))
    bundle = temporary_root / f"Blatero-{version}"
    try:
        runtime = bundle / "runtime"
        runtime.mkdir(parents=True)
        _safe_extract_runtime(runtime_archive, runtime)
        _configure_runtime(runtime)
        app_files = _copy_application(bundle)
        integrity = bundle / "_integrity"
        integrity.mkdir(parents=True, exist_ok=True)
        (integrity / "SBOM.cdx.json").write_bytes(
            build_release.generate_sbom.encoded(
                PORTABLE_REQUIREMENTS, version=version))
        wheels = _prepare_wheels(wheelhouse)
        _install_dependencies(runtime, wheelhouse)
        manifest = _write_manifest(bundle, version, wheels, private_key_path)
        package = _zip_bundle(bundle, output)
        return {"version": version, "app_files": app_files,
                "payload_files": len(manifest["files"]), "wheels": len(wheels),
                "signed": private_key_path is not None, **package}
    finally:
        shutil.rmtree(temporary_root, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify")
    parser.add_argument("--public-key", default=str(ROOT / "release_public_key.pem"))
    parser.add_argument("--output")
    parser.add_argument("--cache", default=str(ROOT / ".tmp" / "portable-cache"))
    parser.add_argument("--wheelhouse", default=str(ROOT / ".tmp" / "portable-wheels"))
    parser.add_argument("--signing-key")
    parser.add_argument("--version")
    args = parser.parse_args()
    if args.verify:
        print(json.dumps(verify(Path(args.verify), Path(args.public_key)),
                         ensure_ascii=False, indent=2))
        return 0
    version = args.version
    if version is None:
        import tomllib
        version = str(tomllib.loads(
            (ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"])
    output = Path(args.output) if args.output else (
        ROOT / "dist" / f"blatero-portable-{version}-win-x64.zip")
    result = build(
        output.resolve(), cache=Path(args.cache).resolve(),
        wheelhouse=Path(args.wheelhouse).resolve(),
        private_key_path=Path(args.signing_key).resolve() if args.signing_key else None,
        version=args.version)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
