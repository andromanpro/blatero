"""Signed release verification, deferred updates and one-step rollback.

Updates are staged while the panel is running and applied by the launcher on
the next start. Mutable data is outside ``APP_ROOT`` and never appears in a
release manifest. Every payload file is covered by an Ed25519 signature.
"""
from __future__ import annotations

import argparse
import base64
from contextlib import contextmanager
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import stat
import sys
import tempfile
import uuid
import zipfile
from pathlib import Path, PurePosixPath

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

import app_paths

APP_ROOT = app_paths.APP_ROOT
DATA_ROOT = app_paths.DATA_ROOT
UPDATE_ROOT = app_paths.UPDATE_ROOT
PUBLIC_KEY_FILE = APP_ROOT / "release_public_key.pem"
PENDING_FILE = UPDATE_ROOT / "pending-update.json"
PENDING_ROLLBACK_FILE = UPDATE_ROOT / "pending-rollback.json"
INSTALLED_STATE_FILE = UPDATE_ROOT / "installed-release.json"
LAST_BACKUP_FILE = UPDATE_ROOT / "last-backup.json"
HISTORY_FILE = UPDATE_ROOT / "history.jsonl"
TRANSACTION_FILE = UPDATE_ROOT / "release-transaction.json"
DEPENDENCY_MARKER = Path(sys.prefix) / ".blatero-lock-sha256"
MANIFEST_NAME = "release-manifest.json"
SIGNATURE_NAME = "release-manifest.sig"
SCHEMA_VERSION = 1
MAX_PACKAGE_BYTES = 512 * 1024 * 1024
MAX_UNPACKED_BYTES = 1024 * 1024 * 1024
MAX_MEMBERS = 2500
VERSION_RE = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?")


class ReleaseError(ValueError):
    """A release is unsafe, damaged or incompatible."""


class PortableUpdateError(ReleaseError):
    """A source package cannot update the portable runtime/help layout."""


def _require_source_layout(app_root: Path) -> None:
    if (app_root / ".portable-runtime").is_file():
        raise PortableUpdateError(
            "portable обновляется полным пакетом в новой папке; "
            "сохраните прежний путь данных (BLATERO_DATA_DIR для нестандартного пути)")


def _now() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as output:
        output.write(json.dumps(payload, ensure_ascii=False, indent=2))
        output.flush()
        os.fsync(output.fileno())
    os.replace(temporary, path)


def _atomic_remove(path: Path) -> None:
    """Remove a state marker without failing an idempotent recovery pass."""
    path.unlink(missing_ok=True)


def _read_json(path: Path, default: dict | None = None) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, ValueError):
        return dict(default or {})
    return value if isinstance(value, dict) else dict(default or {})


def _safe_member(name: str) -> str:
    if not name or "\\" in name or "\x00" in name:
        raise ReleaseError("в архиве найдено недопустимое имя файла")
    path = PurePosixPath(name)
    if path.is_absolute() or any(part in ("", ".", "..") for part in path.parts):
        raise ReleaseError(f"путь файла выходит за каталог установки: {name}")
    if path.parts[0].endswith(":"):
        raise ReleaseError(f"абсолютный Windows-путь запрещён: {name}")
    return path.as_posix()


def _archive_members(archive: zipfile.ZipFile) -> dict[str, zipfile.ZipInfo]:
    members: dict[str, zipfile.ZipInfo] = {}
    total = 0
    if len(archive.infolist()) > MAX_MEMBERS:
        raise ReleaseError("в релизе слишком много файлов")
    for info in archive.infolist():
        if info.is_dir():
            continue
        name = _safe_member(info.filename)
        folded = name.casefold()
        if any(existing.casefold() == folded for existing in members):
            raise ReleaseError(f"дублирующееся имя файла в релизе: {name}")
        mode = (info.external_attr >> 16) & 0o170000
        if mode == stat.S_IFLNK:
            raise ReleaseError(f"символические ссылки в релизе запрещены: {name}")
        total += int(info.file_size)
        if total > MAX_UNPACKED_BYTES:
            raise ReleaseError("распакованный релиз превышает допустимый размер")
        members[name] = info
    return members


def _load_public_key(path: Path) -> Ed25519PublicKey:
    try:
        key = serialization.load_pem_public_key(path.read_bytes())
    except (OSError, ValueError, TypeError) as exc:
        raise ReleaseError("доверенный ключ релизов не настроен") from exc
    if not isinstance(key, Ed25519PublicKey):
        raise ReleaseError("ключ релизов должен быть Ed25519")
    return key


def verify_package(package: str | Path,
                   public_key: str | Path | None = None) -> dict:
    package = Path(package).resolve()
    if not package.is_file():
        raise ReleaseError("файл релиза не найден")
    if package.stat().st_size > MAX_PACKAGE_BYTES:
        raise ReleaseError("архив релиза слишком большой")
    key = _load_public_key(Path(public_key or PUBLIC_KEY_FILE))
    try:
        with zipfile.ZipFile(package) as archive:
            members = _archive_members(archive)
            if MANIFEST_NAME not in members or SIGNATURE_NAME not in members:
                raise ReleaseError("в архиве нет подписанного манифеста")
            manifest_bytes = archive.read(members[MANIFEST_NAME])
            try:
                signature = base64.b64decode(
                    archive.read(members[SIGNATURE_NAME]), validate=True)
                key.verify(signature, manifest_bytes)
            except (ValueError, InvalidSignature) as exc:
                raise ReleaseError("подпись релиза недействительна") from exc
            try:
                manifest = json.loads(manifest_bytes.decode("utf-8"))
            except (UnicodeDecodeError, ValueError) as exc:
                raise ReleaseError("манифест релиза повреждён") from exc
            if not isinstance(manifest, dict):
                raise ReleaseError("манифест релиза должен быть объектом")
            if manifest.get("schema_version") != SCHEMA_VERSION:
                raise ReleaseError("версия формата релиза не поддерживается")
            if manifest.get("product") != "blatero":
                raise ReleaseError("архив предназначен не для Blatero")
            version = str(manifest.get("version", ""))
            if not VERSION_RE.fullmatch(version):
                raise ReleaseError("в манифесте указана неверная версия")
            files = manifest.get("files")
            if not isinstance(files, dict) or not files:
                raise ReleaseError("манифест не содержит файлов приложения")
            expected = set()
            for raw_name, metadata in files.items():
                name = _safe_member(str(raw_name))
                if name in (MANIFEST_NAME, SIGNATURE_NAME):
                    raise ReleaseError("служебный файл не может входить в payload")
                if not isinstance(metadata, dict):
                    raise ReleaseError(f"нет контрольной суммы файла: {name}")
                expected.add(name)
            payload_names = set(members) - {MANIFEST_NAME, SIGNATURE_NAME}
            if payload_names != expected:
                raise ReleaseError("состав архива не совпадает с манифестом")
            for name in sorted(expected):
                metadata = files[name]
                data = archive.read(members[name])
                digest = hashlib.sha256(data).hexdigest()
                if digest != str(metadata.get("sha256", "")):
                    raise ReleaseError(f"контрольная сумма не совпала: {name}")
                if len(data) != int(metadata.get("size", -1)):
                    raise ReleaseError(f"размер файла не совпал: {name}")
    except zipfile.BadZipFile as exc:
        raise ReleaseError("файл релиза не является корректным ZIP-архивом") from exc
    return {
        "version": version,
        "created_at": str(manifest.get("created_at", "")),
        "files": files,
        "package": str(package),
        "package_sha256": _sha256(package),
        "package_size": package.stat().st_size,
        "manifest": manifest,
    }


def extract_verified(package: str | Path, destination: str | Path,
                     public_key: str | Path | None = None) -> dict:
    info = verify_package(package, public_key)
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(info["package"]) as archive:
        members = _archive_members(archive)
        for name in sorted(info["files"]):
            target = destination.joinpath(*PurePosixPath(name).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name(target.name + ".tmp")
            with archive.open(members[name]) as source, temporary.open("wb") as output:
                shutil.copyfileobj(source, output)
            os.replace(temporary, target)
    return info


def _managed_install(app_root: Path | None = None) -> bool:
    app_root = Path(app_root or APP_ROOT)
    return (app_root / ".blatero-data-dir").is_file() and not (app_root / ".git").exists()


def stage_update(package: str | Path) -> dict:
    if not _managed_install():
        raise ReleaseError("рабочую Git-копию нельзя обновлять релизным пакетом")
    _require_source_layout(APP_ROOT)
    info = verify_package(package)
    UPDATE_ROOT.mkdir(parents=True, exist_ok=True)
    staged_dir = UPDATE_ROOT / "staged"
    staged_dir.mkdir(parents=True, exist_ok=True)
    staged = staged_dir / f"blatero-{info['version']}-{info['package_sha256'][:12]}.zip"
    temporary = staged.with_suffix(".zip.tmp")
    shutil.copy2(info["package"], temporary)
    if _sha256(temporary) != info["package_sha256"]:
        temporary.unlink(missing_ok=True)
        raise ReleaseError("архив изменился во время копирования")
    os.replace(temporary, staged)
    payload = {
        "schema_version": 1,
        "version": info["version"],
        "package": str(staged),
        "package_sha256": info["package_sha256"],
        "staged_at": _now(),
    }
    _atomic_json(PENDING_FILE, payload)
    PENDING_ROLLBACK_FILE.unlink(missing_ok=True)
    return payload


def cancel_pending() -> bool:
    pending = _read_json(PENDING_FILE)
    rollback = _read_json(PENDING_ROLLBACK_FILE)
    PENDING_FILE.unlink(missing_ok=True)
    PENDING_ROLLBACK_FILE.unlink(missing_ok=True)
    package = Path(str(pending.get("package", "")))
    try:
        if package.is_file() and package.parent == (UPDATE_ROOT / "staged").resolve():
            package.unlink()
    except OSError:
        pass
    return bool(pending or rollback)


@contextmanager
def _rollback_note_guard():
    from knowledge_hub import runtime_root
    from operation_lock import OperationLock, OperationLockError

    root = runtime_root()
    if not root.is_dir():
        yield
        return
    try:
        with OperationLock(root / "notes.lock"):
            journal = root / "note-publication.json"
            if journal.is_symlink() or journal.exists():
                raise ReleaseError(
                    "Откат не начат: есть незавершённое сохранение в Библиотеке. "
                    "Откройте Библиотеку в текущей версии и завершите восстановление.")
            yield
    except OperationLockError as exc:
        raise ReleaseError("Откат не начат: Библиотека сохраняет изменения. Повторите позже.") from exc


def schedule_rollback() -> dict:
    backup = _read_json(LAST_BACKUP_FILE)
    raw_backup_dir = str(backup.get("backup_dir", "")).strip()
    if not raw_backup_dir:
        raise ReleaseError("доступного отката нет")
    backup_dir = Path(raw_backup_dir)
    metadata = _read_json(backup_dir / "backup.json") if backup_dir.is_dir() else {}
    if not metadata or metadata.get("rolled_back"):
        raise ReleaseError("доступного отката нет")
    payload = {
        "schema_version": 1,
        "backup_dir": str(backup_dir),
        "from_version": metadata.get("to_version", ""),
        "to_version": metadata.get("from_version", ""),
        "scheduled_at": _now(),
    }
    with _rollback_note_guard():
        _atomic_json(PENDING_ROLLBACK_FILE, payload)
        PENDING_FILE.unlink(missing_ok=True)
    return payload


def _restore_backup(app_root: Path, metadata: dict, backup_dir: Path) -> None:
    for name in metadata.get("created", []):
        target = app_root.joinpath(*PurePosixPath(_safe_member(name)).parts)
        if target.is_file():
            target.unlink()
    for name in metadata.get("backed_up", []):
        safe_name = _safe_member(name)
        source = backup_dir / "files" / Path(*PurePosixPath(safe_name).parts)
        target = app_root / Path(*PurePosixPath(safe_name).parts)
        if not source.is_file():
            raise ReleaseError(f"резервная копия повреждена: {safe_name}")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def _append_history(payload: dict) -> None:
    UPDATE_ROOT.mkdir(parents=True, exist_ok=True)
    with HISTORY_FILE.open("a", encoding="utf-8") as output:
        output.write(json.dumps(payload, ensure_ascii=False) + "\n")
        output.flush()
        os.fsync(output.fileno())


def _history_has(operation_id: str) -> bool:
    if not operation_id:
        return False
    try:
        with HISTORY_FILE.open("r", encoding="utf-8") as source:
            for line in source:
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                if event.get("operation_id") == operation_id:
                    return True
    except OSError:
        return False
    return False


def _write_transaction(transaction: dict, phase: str) -> dict:
    value = dict(transaction)
    value["phase"] = phase
    value["updated_at"] = _now()
    _atomic_json(TRANSACTION_FILE, value)
    return value


def _restore_json_state(path: Path, value: dict) -> None:
    if value:
        _atomic_json(path, value)
    else:
        _atomic_remove(path)


def _release_files_match(app_root: Path, files: dict,
                         removed: list[str] | None = None) -> bool:
    for name, metadata in files.items():
        target = app_root / Path(*PurePosixPath(_safe_member(name)).parts)
        if (not target.is_file()
                or target.stat().st_size != int(metadata.get("size", -1))
                or _sha256(target) != metadata.get("sha256")):
            return False
    for name in removed or []:
        target = app_root / Path(*PurePosixPath(_safe_member(name)).parts)
        if target.exists():
            return False
    return True


def _apply_update(pending: dict, app_root: Path) -> dict:
    _require_source_layout(app_root)
    package = Path(str(pending.get("package", ""))).resolve()
    info = verify_package(package, app_root / "release_public_key.pem")
    if info["package_sha256"] != pending.get("package_sha256"):
        raise ReleaseError("подготовленный архив был изменён")
    previous = _read_json(INSTALLED_STATE_FILE)
    previous_last_backup = _read_json(LAST_BACKUP_FILE)
    previous_files = set(previous.get("files", {}))
    new_files = set(info["files"])
    backup_dir = UPDATE_ROOT / "backups" / (
        dt.datetime.now().strftime("%Y%m%d-%H%M%S") + f"-to-{info['version']}")
    backup_files = backup_dir / "files"
    UPDATE_ROOT.mkdir(parents=True, exist_ok=True)
    stage_dir = Path(tempfile.mkdtemp(prefix="apply-", dir=UPDATE_ROOT))
    extract_verified(package, stage_dir, app_root / "release_public_key.pem")
    impacted = sorted(new_files | (previous_files - new_files))
    backed_up: list[str] = []
    created: list[str] = []
    for name in impacted:
        target = app_root / Path(*PurePosixPath(name).parts)
        if target.is_file():
            backup = backup_files / Path(*PurePosixPath(name).parts)
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, backup)
            backed_up.append(name)
        elif name in new_files:
            created.append(name)
    metadata = {
        "schema_version": 1,
        "from_version": previous.get("version", "неизвестно"),
        "to_version": info["version"],
        "created_at": _now(),
        "backed_up": backed_up,
        "created": created,
        "previous_installed": previous,
        "rolled_back": False,
    }
    _atomic_json(backup_dir / "backup.json", metadata)
    installed = {
        "schema_version": 1,
        "version": info["version"],
        "installed_at": _now(),
        "files": info["files"],
        "package_sha256": info["package_sha256"],
    }
    transaction = _write_transaction({
        "schema_version": 1,
        "operation_id": uuid.uuid4().hex,
        "kind": "update",
        "app_root": str(app_root),
        "backup_dir": str(backup_dir),
        "package": str(package),
        "previous_installed": previous,
        "previous_last_backup": previous_last_backup,
        "installed": installed,
        "removed": sorted(previous_files - new_files),
    }, "prepared")
    try:
        transaction = _write_transaction(transaction, "applying")
        for name in sorted(previous_files - new_files):
            target = app_root / Path(*PurePosixPath(name).parts)
            target.unlink(missing_ok=True)
        for name in sorted(new_files):
            source = stage_dir / Path(*PurePosixPath(name).parts)
            target = app_root / Path(*PurePosixPath(name).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name(target.name + ".blatero-update")
            shutil.copy2(source, temporary)
            os.replace(temporary, target)
        _atomic_json(INSTALLED_STATE_FILE, installed)
        if not _release_files_match(
                app_root, info["files"], transaction["removed"]):
            raise ReleaseError("проверка файлов после обновления не пройдена")
        transaction = _write_transaction(transaction, "applied")
        result = _commit_update_transaction(transaction, app_root)
    except Exception:
        _rollback_update_transaction(transaction, app_root)
        raise
    finally:
        shutil.rmtree(stage_dir, ignore_errors=True)
    return result


def _rollback_update_transaction(transaction: dict, app_root: Path) -> dict:
    transaction = _write_transaction(transaction, "rolling_back")
    backup_dir = Path(str(transaction.get("backup_dir", ""))).resolve()
    metadata = _read_json(backup_dir / "backup.json")
    if not metadata:
        raise ReleaseError("журнал обновления ссылается на повреждённую копию")
    _restore_backup(app_root, metadata, backup_dir)
    _restore_json_state(
        INSTALLED_STATE_FILE,
        transaction.get("previous_installed")
        if isinstance(transaction.get("previous_installed"), dict) else {})
    _restore_json_state(
        LAST_BACKUP_FILE,
        transaction.get("previous_last_backup")
        if isinstance(transaction.get("previous_last_backup"), dict) else {})
    _write_transaction(transaction, "rolled_back")
    _atomic_remove(TRANSACTION_FILE)
    return {"action": "update-recovered", "version": metadata.get("from_version", "")}


def _commit_update_transaction(transaction: dict, app_root: Path) -> dict:
    installed = transaction.get("installed")
    if not isinstance(installed, dict) or not installed:
        raise ReleaseError("журнал обновления не содержит новое состояние")
    files = installed.get("files")
    if not isinstance(files, dict) or not _release_files_match(
            app_root, files, transaction.get("removed", [])):
        return _rollback_update_transaction(transaction, app_root)
    _atomic_json(INSTALLED_STATE_FILE, installed)
    backup_dir = Path(str(transaction.get("backup_dir", ""))).resolve()
    _atomic_json(LAST_BACKUP_FILE, {"backup_dir": str(backup_dir)})
    operation_id = str(transaction.get("operation_id", ""))
    if not _history_has(operation_id):
        _append_history({"action": "update", "operation_id": operation_id,
                         **installed})
    _write_transaction(transaction, "committed")
    _atomic_remove(PENDING_FILE)
    package = Path(str(transaction.get("package", "")))
    try:
        if package.is_file() and package.parent == (UPDATE_ROOT / "staged").resolve():
            package.unlink()
    except OSError:
        pass
    _atomic_remove(TRANSACTION_FILE)
    return {"action": "updated", "version": installed.get("version", ""),
            "backup_dir": str(backup_dir)}


def _apply_rollback(pending: dict, app_root: Path) -> dict:
    backup_dir = Path(str(pending.get("backup_dir", ""))).resolve()
    if backup_dir.parent != (UPDATE_ROOT / "backups").resolve():
        raise ReleaseError("каталог отката выходит за хранилище обновлений")
    metadata = _read_json(backup_dir / "backup.json")
    if not metadata:
        raise ReleaseError("резервная копия недоступна или уже использована")
    if metadata.get("rolled_back"):
        _atomic_remove(PENDING_ROLLBACK_FILE)
        _atomic_remove(LAST_BACKUP_FILE)
        return {"action": "rolled_back", "version": metadata.get("from_version", "")}
    transaction = _write_transaction({
        "schema_version": 1,
        "operation_id": uuid.uuid4().hex,
        "kind": "rollback",
        "app_root": str(app_root),
        "backup_dir": str(backup_dir),
    }, "prepared")
    return _complete_rollback_transaction(transaction, app_root)


def _complete_rollback_transaction(transaction: dict, app_root: Path) -> dict:
    with _rollback_note_guard():
        return _restore_rollback_transaction(transaction, app_root)


def _restore_rollback_transaction(transaction: dict, app_root: Path) -> dict:
    transaction = _write_transaction(transaction, "rolling_back")
    backup_dir = Path(str(transaction.get("backup_dir", ""))).resolve()
    metadata = _read_json(backup_dir / "backup.json")
    if not metadata:
        raise ReleaseError("журнал отката ссылается на повреждённую копию")
    _restore_backup(app_root, metadata, backup_dir)
    previous = metadata.get("previous_installed")
    if isinstance(previous, dict) and previous:
        _atomic_json(INSTALLED_STATE_FILE, previous)
    else:
        INSTALLED_STATE_FILE.unlink(missing_ok=True)
    metadata["rolled_back"] = True
    metadata["rolled_back_at"] = _now()
    _atomic_json(backup_dir / "backup.json", metadata)
    _write_transaction(transaction, "committed")
    _atomic_remove(PENDING_ROLLBACK_FILE)
    _atomic_remove(LAST_BACKUP_FILE)
    result = {"action": "rolled_back", "version": metadata.get("from_version", "")}
    operation_id = str(transaction.get("operation_id", ""))
    if not _history_has(operation_id):
        _append_history({**result, "operation_id": operation_id, "at": _now()})
    _atomic_remove(TRANSACTION_FILE)
    return result


def _reconcile_transaction(app_root: Path) -> dict | None:
    transaction = _read_json(TRANSACTION_FILE)
    if not transaction:
        return None
    recorded_root = Path(str(transaction.get("app_root", ""))).resolve()
    if recorded_root != app_root:
        raise ReleaseError("незавершённое обновление относится к другой установке")
    kind = transaction.get("kind")
    phase = transaction.get("phase")
    if kind == "rollback":
        return _complete_rollback_transaction(transaction, app_root)
    if kind != "update":
        raise ReleaseError("неизвестный тип незавершённого обновления")
    if phase in {"applied", "committed"}:
        installed = transaction.get("installed")
        files = installed.get("files", {}) if isinstance(installed, dict) else {}
        if files and _release_files_match(
                app_root, files, transaction.get("removed", [])):
            return _commit_update_transaction(transaction, app_root)
    return _rollback_update_transaction(transaction, app_root)


def apply_pending(app_root: str | Path = APP_ROOT) -> dict:
    app_root = Path(app_root).resolve()
    reconciled = _reconcile_transaction(app_root)
    if reconciled is not None:
        return reconciled
    rollback = _read_json(PENDING_ROLLBACK_FILE)
    if rollback:
        if not _managed_install(app_root):
            raise ReleaseError("рабочую Git-копию нельзя откатывать релизным пакетом")
        return _apply_rollback(rollback, app_root)
    pending = _read_json(PENDING_FILE)
    if pending:
        if not _managed_install(app_root):
            raise ReleaseError("рабочую Git-копию нельзя обновлять релизным пакетом")
        if (app_root / ".portable-runtime").is_file():
            # Old versions could stage a source package in a portable bundle.
            # Reject it without blocking every subsequent launcher start or
            # mixing new code with old root-level help/runtime. Keep the ZIP.
            operation_id = "portable-rejected-" + hashlib.sha256(
                json.dumps(pending, sort_keys=True).encode("utf-8")).hexdigest()
            result = {"action": "update_rejected", "code": "portable_full_required",
                      "version": pending.get("version", "")}
            if not _history_has(operation_id):
                _append_history({**result, "operation_id": operation_id, "at": _now()})
            _atomic_remove(PENDING_FILE)
            return result
        return _apply_update(pending, app_root)
    return {"action": "none"}


def status() -> dict:
    installed = _read_json(INSTALLED_STATE_FILE)
    pending = _read_json(PENDING_FILE)
    rollback = _read_json(PENDING_ROLLBACK_FILE)
    last = _read_json(LAST_BACKUP_FILE)
    raw_backup_dir = str(last.get("backup_dir", "")).strip()
    backup_dir = Path(raw_backup_dir) if raw_backup_dir else None
    backup = (_read_json(backup_dir / "backup.json")
              if backup_dir is not None and backup_dir.is_dir() else {})
    return {
        "type": "update_manager",
        "state": "ready",
        "managed_install": _managed_install(),
        "source_updates_supported": not (APP_ROOT / ".portable-runtime").is_file(),
        "version": installed.get("version", _source_version()),
        "installed_at": installed.get("installed_at", ""),
        "app_root": str(APP_ROOT),
        "data_root": str(DATA_ROOT),
        "trusted_key": PUBLIC_KEY_FILE.is_file(),
        "pending": pending,
        "pending_rollback": rollback,
        "rollback_available": bool(backup and not backup.get("rolled_back")),
        "rollback_version": backup.get("from_version", ""),
    }


def _source_version() -> str:
    try:
        import tomllib
        value = tomllib.loads((APP_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        return str(value.get("project", {}).get("version", "dev"))
    except (OSError, ValueError):
        return "dev"


def sync_dependencies() -> dict:
    lock = APP_ROOT / "requirements.lock"
    if not lock.is_file():
        raise ReleaseError("requirements.lock не найден")
    digest = _sha256(lock)
    try:
        current = DEPENDENCY_MARKER.read_text(encoding="ascii").strip()
    except OSError:
        current = ""
    if current == digest:
        return {"action": "dependencies-current", "sha256": digest}
    # Нельзя безопасно менять активную venv по месту: частичный pip install
    # переживёт файловый rollback приложения. Релизы с новым lock ставятся
    # полным portable/installer-пакетом, где окружение собирается отдельно.
    raise ReleaseError(
        "обновление меняет зависимости; установите полный portable/installer "
        "пакет — активное окружение оставлено без изменений")


def main() -> int:
    parser = argparse.ArgumentParser(description="Безопасные обновления Blatero")
    commands = parser.add_subparsers(dest="command", required=True)
    verify = commands.add_parser("verify")
    verify.add_argument("package")
    stage = commands.add_parser("stage")
    stage.add_argument("package")
    commands.add_parser("status")
    commands.add_parser("cancel")
    commands.add_parser("schedule-rollback")
    commands.add_parser("sync-dependencies")
    apply = commands.add_parser("apply-pending")
    apply.add_argument("--app-root", default=str(APP_ROOT))
    args = parser.parse_args()
    try:
        if args.command == "verify":
            result = verify_package(args.package)
        elif args.command == "stage":
            result = stage_update(args.package)
        elif args.command == "cancel":
            result = {"cancelled": cancel_pending()}
        elif args.command == "schedule-rollback":
            result = schedule_rollback()
        elif args.command == "apply-pending":
            result = apply_pending(args.app_root)
        elif args.command == "sync-dependencies":
            result = sync_dependencies()
        else:
            result = status()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ReleaseError, ValueError) as exc:
        print(f"Blatero update: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
