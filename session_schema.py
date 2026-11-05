"""Versioned, restart-safe migrations for a Blatero session directory."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import shutil
import threading
from pathlib import Path

from session_utils import direct_child, transcript_segments


PRODUCT = "blatero"
CURRENT_VERSION = 1
MANIFEST_FILE = ".session-schema.json"
JOURNAL_FILE = ".session-migration.json"
META_FILE = "meta.json"
MIN_FREE_BYTES = 1024 * 1024
_LOCK = threading.RLock()
_BACKUP_NAME_RE = re.compile(r"meta\.before-schema-v\d+(?:-\d+)?\.json\Z")
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")


class SessionSchemaError(RuntimeError):
    """A session cannot be safely opened or migrated."""


def _now() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="milliseconds")


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_json(path: Path) -> tuple[dict, str]:
    if not path.is_file():
        return {}, "missing"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        return {}, f"{type(exc).__name__}: файл не читается"
    if not isinstance(value, dict):
        return {}, "ожидался JSON-объект"
    return value, ""


def _atomic_json(path: Path, value: dict) -> None:
    temporary = path.with_name(path.name + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as output:
            json.dump(value, output, ensure_ascii=False, indent=2)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _atomic_backup(source: Path, target: Path, expected_sha256: str) -> None:
    if source.is_symlink() or target.is_symlink():
        raise SessionSchemaError("символические ссылки в миграции запрещены")
    if target.is_file():
        if _digest(target.read_bytes()) != expected_sha256:
            raise SessionSchemaError(
                f"резервная копия миграции повреждена: {target.name}")
        return
    temporary = target.with_name(target.name + ".tmp")
    try:
        temporary.unlink(missing_ok=True)
        shutil.copy2(source, temporary)
        copied = temporary.read_bytes()
        if _digest(copied) != expected_sha256:
            raise SessionSchemaError(
                f"не удалось проверить резервную копию {source.name}")
        with temporary.open("r+b") as output:
            os.fsync(output.fileno())
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def _integer_version(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def inspect(session: Path) -> dict:
    session = Path(session).resolve()
    manifest_path = session / MANIFEST_FILE
    manifest, manifest_error = _read_json(manifest_path)
    journal, journal_error = _read_json(session / JOURNAL_FILE)
    base = {
        "session": session.name,
        "current_version": CURRENT_VERSION,
        "manifest_file": MANIFEST_FILE,
        "journal_file": JOURNAL_FILE,
        "attention": False,
    }
    if manifest_error == "missing":
        if journal_error not in ("", "missing"):
            return {
                **base, "state": "corrupt", "version": 0,
                "compatible": False, "needs_migration": False,
                "can_migrate": False, "attention": True,
                "message": f"журнал миграции повреждён: {journal_error}",
            }
        interrupted = (not journal_error and journal.get("phase") == "applying")
        if interrupted:
            try:
                if (journal.get("from_version") != 0
                        or journal.get("to_version") != CURRENT_VERSION):
                    raise SessionSchemaError(
                        "журнал относится к неизвестной миграции")
                _validated_backup_name(journal.get("backup"))
                _validated_sha256(journal.get("original_sha256"))
            except SessionSchemaError as exc:
                return {
                    **base, "state": "corrupt", "version": 0,
                    "compatible": False, "needs_migration": False,
                    "can_migrate": False, "attention": True,
                    "message": str(exc),
                }
        return {
            **base,
            "state": "interrupted" if interrupted else "legacy",
            "version": 0, "compatible": True, "needs_migration": True,
            "can_migrate": True, "attention": interrupted,
            "message": ("миграция схемы была прервана; её можно безопасно завершить"
                        if interrupted else
                        "сессия создана до версионирования и обновится при открытии"),
        }
    if manifest_error:
        return {
            **base, "state": "corrupt", "version": None,
            "compatible": False, "needs_migration": False,
            "can_migrate": False, "attention": True,
            "message": f"манифест схемы повреждён: {manifest_error}",
        }
    version = _integer_version(manifest.get("schema_version"))
    if manifest.get("product") != PRODUCT or version is None:
        return {
            **base, "state": "corrupt", "version": version,
            "compatible": False, "needs_migration": False,
            "can_migrate": False, "attention": True,
            "message": "манифест схемы имеет неизвестный формат",
        }
    if version > CURRENT_VERSION:
        return {
            **base, "state": "future", "version": version,
            "compatible": False, "needs_migration": False,
            "can_migrate": False, "attention": True,
            "message": (f"сессия использует схему v{version}; нужна более новая "
                        "версия Blatero"),
        }
    if version < CURRENT_VERSION:
        return {
            **base, "state": "outdated", "version": version,
            "compatible": True, "needs_migration": True,
            "can_migrate": True, "attention": True,
            "message": f"схему v{version} можно обновить до v{CURRENT_VERSION}",
        }
    meta, meta_error = _read_json(session / META_FILE)
    meta_version = _integer_version(meta.get("schema_version")) if not meta_error else None
    if meta_error or meta_version != CURRENT_VERSION:
        return {
            **base, "state": "inconsistent", "version": version,
            "compatible": False, "needs_migration": False,
            "can_migrate": False, "attention": True,
            "message": ("meta.json отсутствует или не соответствует commit-marker "
                        f"схемы v{CURRENT_VERSION}"),
        }
    applying = not journal_error and journal.get("phase") == "applying"
    return {
        **base, "state": "current", "version": version,
        "compatible": True, "needs_migration": False,
        "can_migrate": applying, "attention": applying,
        "message": ("данные обновлены; завершается журнал миграции" if applying else
                    f"схема сессии v{CURRENT_VERSION}"),
    }


def _backup_name(session: Path) -> str:
    for number in range(1, 10_000):
        suffix = "" if number == 1 else f"-{number}"
        name = f"meta.before-schema-v{CURRENT_VERSION}{suffix}.json"
        if not (session / name).exists():
            return name
    raise SessionSchemaError("не удалось подобрать имя резервной копии meta.json")


def _validated_backup_name(value: object) -> str:
    name = str(value or "")
    if not name:
        return ""
    if Path(name).name != name or not _BACKUP_NAME_RE.fullmatch(name):
        raise SessionSchemaError("журнал содержит небезопасное имя резервной копии")
    return name


def _validated_sha256(value: object) -> str:
    digest = str(value or "").lower()
    if not _SHA256_RE.fullmatch(digest):
        raise SessionSchemaError("журнал содержит некорректный хэш meta.json")
    return digest


def _space_preflight(session: Path, source_size: int) -> dict:
    required = max(MIN_FREE_BYTES, source_size * 3 + 64 * 1024)
    try:
        free = int(shutil.disk_usage(session).free)
    except OSError as exc:
        raise SessionSchemaError(
            f"не удалось проверить место для миграции: {type(exc).__name__}") from exc
    if free < required:
        raise SessionSchemaError(
            f"недостаточно места для миграции: нужно {required} байт, "
            f"свободно {free} байт")
    return {"required_bytes": required, "free_bytes": free}


def _complete_journal(session: Path, journal: dict) -> None:
    if journal.get("phase") != "applying":
        return
    completed = dict(journal)
    completed.update(phase="completed", completed_at=_now())
    _atomic_json(session / JOURNAL_FILE, completed)


def migrate(session: Path, *, dry_run: bool = False) -> dict:
    """Migrate one direct session folder forward, never downgrading data."""
    session = Path(session).resolve()
    if not session.is_dir():
        raise SessionSchemaError("папка сессии не найдена")
    with _LOCK:
        current = inspect(session)
        journal, journal_error = _read_json(session / JOURNAL_FILE)
        if current["state"] == "current":
            if not journal_error and journal.get("phase") == "applying":
                if not dry_run:
                    _complete_journal(session, journal)
                    current = inspect(session)
            return {**current, "changed": False, "dry_run": dry_run}
        if not current.get("can_migrate"):
            raise SessionSchemaError(str(current["message"]))
        if current.get("version") not in (0,):
            raise SessionSchemaError(
                f"нет миграции v{current.get('version')} → v{CURRENT_VERSION}")

        meta_path = session / META_FILE
        meta, meta_error = _read_json(meta_path)
        if meta_error not in ("", "missing"):
            raise SessionSchemaError(f"meta.json нельзя мигрировать: {meta_error}")
        source = meta_path.read_bytes() if meta_path.is_file() else b""
        source_sha256 = _digest(source)
        space = _space_preflight(session, len(source))
        applying = (journal if not journal_error
                    and journal.get("phase") == "applying" else {})
        backup_name = _validated_backup_name(
            applying.get("backup") if applying else (
                _backup_name(session) if source else ""))
        if applying:
            if (applying.get("from_version") != 0
                    or applying.get("to_version") != CURRENT_VERSION):
                raise SessionSchemaError("журнал относится к неизвестной миграции")
            original_sha256 = _validated_sha256(
                applying.get("original_sha256"))
        else:
            original_sha256 = source_sha256
        plan = {
            "from_version": 0, "to_version": CURRENT_VERSION,
            "files": [META_FILE], "backup": backup_name,
            "original_sha256": original_sha256, "space": space,
        }
        if dry_run:
            return {**current, **plan, "changed": True, "dry_run": True}

        if not applying:
            applying = {
                "schema_version": 1, "phase": "applying",
                "migration_id": f"session-v0-v{CURRENT_VERSION}",
                "from_version": 0, "to_version": CURRENT_VERSION,
                "started_at": _now(), "backup": backup_name,
                "original_sha256": original_sha256,
            }
            _atomic_json(session / JOURNAL_FILE, applying)
        if backup_name:
            backup = session / backup_name
            if not backup.exists() and source_sha256 != original_sha256:
                raise SessionSchemaError(
                    "исходный meta.json изменился после начала миграции")
            _atomic_backup(meta_path, backup, original_sha256)

        migrated_meta = dict(meta)
        migrated_meta["schema_version"] = CURRENT_VERSION
        _atomic_json(meta_path, migrated_meta)
        completed_at = _now()
        manifest = {
            "product": PRODUCT, "schema_version": CURRENT_VERSION,
            "created_at": completed_at, "updated_at": completed_at,
            "migrations": [{
                "from_version": 0, "to_version": CURRENT_VERSION,
                "completed_at": completed_at, "backup": backup_name,
            }],
        }
        _atomic_json(session / MANIFEST_FILE, manifest)
        _complete_journal(session, applying)
        return {
            **inspect(session), **plan, "changed": True, "dry_run": False,
        }


def ensure(session: Path) -> dict:
    return migrate(session)


def initialize(session: Path, meta: dict | None = None) -> dict:
    """Initialize a newly created session directly at the current schema."""
    session = Path(session).resolve()
    session.mkdir(parents=True, exist_ok=True)
    with _LOCK:
        if (session / MANIFEST_FILE).exists() or (session / META_FILE).exists():
            ensure(session)
            if meta is not None:
                write_meta(session, meta)
            return inspect(session)
        now = _now()
        value = dict(meta or {})
        value["schema_version"] = CURRENT_VERSION
        _space_preflight(session, len(json.dumps(value, ensure_ascii=False).encode("utf-8")))
        _atomic_json(session / META_FILE, value)
        _atomic_json(session / MANIFEST_FILE, {
            "product": PRODUCT, "schema_version": CURRENT_VERSION,
            "created_at": now, "updated_at": now, "migrations": [],
        })
        return inspect(session)


def write_meta(session: Path, meta: dict) -> dict:
    with _LOCK:
        ensure(session)
        value = dict(meta)
        value["schema_version"] = CURRENT_VERSION
        _atomic_json(Path(session).resolve() / META_FILE, value)
        return value


def scan(sessions_root: Path) -> list[dict]:
    root = Path(sessions_root)
    root.mkdir(parents=True, exist_ok=True)
    result = []
    for session in root.iterdir():
        if not session.is_dir():
            continue
        if not ((session / META_FILE).exists() or transcript_segments(session)):
            continue
        item = inspect(session)
        if not item.get("attention"):
            continue
        meta, _error = _read_json(session / META_FILE)
        item["label"] = str(meta.get("name") or session.name)
        result.append(item)
    result.sort(key=lambda item: item["session"].casefold())
    return result


def payload(sessions_root: Path) -> dict:
    items = scan(sessions_root)
    return {
        "state": "needs_attention" if items else "ready",
        "items": items, "count": len(items),
        "current_version": CURRENT_VERSION,
    }


def migrate_named(sessions_root: Path, session_name: str) -> dict:
    session = direct_child(Path(sessions_root), session_name, must_exist=True)
    return migrate(session)
