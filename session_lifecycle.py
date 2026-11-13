"""Encrypted portable session packages and explicit local data retention."""
from __future__ import annotations

import base64
import datetime as dt
import hashlib
import io
import json
import os
import re
import shutil
import struct
import tempfile
import uuid
import zipfile
from pathlib import Path, PurePosixPath

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from session_utils import direct_child, unique_session_dir


PRODUCT = "blatero-session"
SCHEMA_VERSION = 1
MAGIC = b"BLATERO-SESSION\0"
HEADER_LIMIT = 8192
TAG_BYTES = 16
SALT_BYTES = 16
NONCE_BYTES = 12
SCRYPT_N = 2**15
SCRYPT_R = 8
SCRYPT_P = 1
KEY_BYTES = 32
CHUNK_BYTES = 1024 * 1024
MAX_FILES = 20_000
MAX_EXPANDED_BYTES = 20 * 1024**3
MAX_SINGLE_FILE_BYTES = 5 * 1024**3
MAX_PASSWORD_CHARS = 256
MIN_PASSWORD_CHARS = 10
MIN_FREE_BYTES = 128 * 1024**2
PACKAGE_SUFFIX = ".blatero-session"
PACKAGES_DIR = ".session-packages"
AUDIT_DIR = ".session-lifecycle"
AUDIT_FILE = "audit.jsonl"
RETENTION_FILE = "retention.json"
_TEMP_NAMES = re.compile(r"(?:\.tmp|\.part|\.lock)$", re.IGNORECASE)
_PACKAGE_NAME = re.compile(
    r"blatero-session-\d{8}T\d{6}-[0-9a-f]{8}\.blatero-session\Z")

CATEGORY_LABELS = {
    "audio": "аудио",
    "video": "видео и предпросмотры",
    "transcripts": "транскрипты",
    "reports": "отчёты и доказательства",
    "derived": "производные разборы",
    "all": "вся сессия",
}
DEFAULT_RETENTION = {
    "audio": 0, "video": 0, "transcripts": 0, "reports": 0, "derived": 0, "all": 0,
}
_AUDIO_SUFFIXES = {".wav", ".mp3", ".ogg", ".flac", ".m4a", ".aac"}
_REPORT_PREFIXES = ("report", "evidence")
_DERIVED_DIRS = {"replay-runs", "diarization", "speaker-analysis", "live-materials"}
_DERIVED_PREFIXES = (
    "diarization", "speaker-map", "speaker-identification", "quality-reference",
    "transcript.local", "transcript.refined", "transcript.reference",
    "hints", "asked", "emulation", "pulse-timing", "levels", "audio-watch",
    "preflight", "diagnostics", ".diagnostics", "training-", "training_", "ai-scene",
    "workspace-", "dossier", "questions", "memory-draft", "capture-",
)
_PERSONAL_GROUPS = {
    "sessions": ("встречи, аудио и отчёты", ("sessions",)),
    "packages": ("зашифрованные переносимые пакеты", (PACKAGES_DIR,)),
    "memory": ("память клиентов и проектов", (".meeting-memory",)),
    "biometrics": ("голосовые образцы и отпечатки",
                   (".voice-profile", ".speaker-profiles")),
    "calendar": ("календарные данные и OAuth-токены",
                 (".calendar-tokens", "calendar_sources.json",
                  "calendar_cache.json", "google-calendar-credentials.json")),
    "settings": ("настройки, повестка и локальные промпты",
                 ("config.json", "schedule.json", "prompt_overrides.json",
                  "training-profiles.json", ".audio-calibration.json")),
    "audit": ("локальные журналы жизненного цикла и диагностики",
              (AUDIT_DIR, "panel.err.log", "panel-runtime-error.log",
               "mcp-server.log")),
}


class SessionPackageError(RuntimeError):
    """A package cannot be safely exported, decrypted, or imported."""


def _now() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _password(value: str) -> bytes:
    text = str(value or "")
    if len(text) < MIN_PASSWORD_CHARS:
        raise SessionPackageError(
            f"парольная фраза должна содержать не менее {MIN_PASSWORD_CHARS} символов")
    if len(text) > MAX_PASSWORD_CHARS:
        raise SessionPackageError("парольная фраза слишком длинная")
    return text.encode("utf-8")


def _derive_key(password: bytes, salt: bytes, *, n: int | None = None,
                r: int | None = None, p: int | None = None) -> bytes:
    n = SCRYPT_N if n is None else n
    r = SCRYPT_R if r is None else r
    p = SCRYPT_P if p is None else p
    if n != SCRYPT_N or r != SCRYPT_R or p != SCRYPT_P:
        raise SessionPackageError("параметры защиты пакета не поддерживаются")
    try:
        return Scrypt(salt=salt, length=KEY_BYTES, n=n, r=r, p=p).derive(password)
    except (TypeError, ValueError) as exc:
        raise SessionPackageError("не удалось получить ключ пакета") from exc


def packages_root(data_root: Path) -> Path:
    root = Path(data_root).resolve() / PACKAGES_DIR
    root.mkdir(parents=True, exist_ok=True)
    return root


def _package_path(root: Path) -> Path:
    stamp = dt.datetime.now().strftime("%Y%m%dT%H%M%S")
    for _ in range(100):
        name = f"blatero-session-{stamp}-{uuid.uuid4().hex[:8]}{PACKAGE_SUFFIX}"
        candidate = root / name
        if not candidate.exists():
            return candidate
    raise SessionPackageError("не удалось подобрать имя переносимого пакета")


def package_file(root: Path, name: str) -> Path:
    raw = str(name or "")
    if Path(raw).name != raw or not _PACKAGE_NAME.fullmatch(raw):
        raise SessionPackageError("небезопасное имя пакета")
    candidate = (Path(root).resolve() / raw).resolve()
    if candidate.parent != Path(root).resolve() or not candidate.is_file():
        raise SessionPackageError("пакет не найден")
    return candidate


def list_packages(data_root: Path) -> list[dict]:
    root = packages_root(data_root)
    items = []
    for path in sorted(root.iterdir(), key=lambda item: item.stat().st_mtime,
                       reverse=True):
        if (path.is_symlink() or not path.is_file()
                or not _PACKAGE_NAME.fullmatch(path.name)):
            continue
        items.append({
            "name": path.name,
            "bytes": path.stat().st_size,
            "modified_at": dt.datetime.fromtimestamp(
                path.stat().st_mtime).astimezone().isoformat(timespec="seconds"),
            "download_url": f"/api/session-packages/{path.name}",
        })
    return items[:100]


def delete_package(data_root: Path, name: str) -> dict:
    """Удалить явный зашифрованный пакет; копия не исчезает с purge сессии."""
    root = packages_root(data_root)
    target = package_file(root, name)
    size = target.stat().st_size
    _audit(data_root, "package_delete_intent", details={
        "package": target.name, "bytes": size,
    })
    target.unlink()
    result = {"name": target.name, "bytes": size, "deleted": True}
    try:
        _audit(data_root, "package_delete", details={**result, "committed": True})
    except OSError as exc:
        result["audit_warning"] = (
            "пакет удалён, но итоговая запись журнала не сохранена: "
            f"{type(exc).__name__}")
    return result


def personal_data_inventory(data_root: Path) -> dict:
    """Посчитать только известные приложению локальные хранилища ПД."""
    root = Path(data_root).resolve()
    groups = []
    total_files = total_bytes = total_links = 0
    for key, (label, relatives) in _PERSONAL_GROUPS.items():
        files = size = links = 0
        for relative in relatives:
            target = root / relative
            if target.is_symlink():
                links += 1
                continue
            if target.is_file():
                try:
                    size += target.stat().st_size
                    files += 1
                except OSError:
                    pass
                continue
            if not target.is_dir():
                continue
            for item in target.rglob("*"):
                if item.is_symlink():
                    links += 1
                elif item.is_file():
                    try:
                        size += item.stat().st_size
                        files += 1
                    except OSError:
                        pass
        groups.append({"key": key, "label": label, "files": files,
                       "bytes": size, "links_skipped": links})
        total_files += files
        total_bytes += size
        total_links += links
    return {
        "groups": groups, "files": total_files, "bytes": total_bytes,
        "links_skipped": total_links,
        "external": [
            "Windows Credential Manager: LLM, CalDAV и Google OAuth",
            "OAuth/Codex login и переменные окружения вне каталога Blatero",
            "копии, скачанные пользователем, backup, облачная синхронизация и shadow copies",
        ],
    }


def _source_files(session: Path) -> list[tuple[Path, str, int, str]]:
    result: list[tuple[Path, str, int, str]] = []
    total = 0
    for path in sorted(session.rglob("*"), key=lambda item: item.as_posix().casefold()):
        if path.is_symlink():
            raise SessionPackageError(
                f"символическая ссылка не включена в пакет: {path.relative_to(session)}")
        if not path.is_file():
            continue
        relative = path.relative_to(session).as_posix()
        if _TEMP_NAMES.search(path.name):
            continue
        size = path.stat().st_size
        if size > MAX_SINGLE_FILE_BYTES:
            raise SessionPackageError(f"файл слишком велик для пакета: {relative}")
        total += size
        if total > MAX_EXPANDED_BYTES:
            raise SessionPackageError("сессия превышает допустимый размер пакета")
        result.append((path, relative, size, _file_digest(path)))
        if len(result) > MAX_FILES:
            raise SessionPackageError("в сессии слишком много файлов")
    if not result:
        raise SessionPackageError("сессия не содержит файлов")
    return result


def _build_zip(session: Path, temporary: Path,
               files: list[tuple[Path, str, int, str]] | None = None
               ) -> tuple[dict, str, int]:
    files = _source_files(session) if files is None else files
    manifest = {
        "product": PRODUCT,
        "schema_version": SCHEMA_VERSION,
        "created_at": _now(),
        "source_session": session.name,
        "files": [
            {"path": relative, "size": size, "sha256": digest}
            for _, relative, size, digest in files
        ],
    }
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=6, allowZip64=True) as archive:
        archive.writestr("blatero-session-manifest.json", json.dumps(
            manifest, ensure_ascii=False, indent=2).encode("utf-8"))
        for path, relative, _, _ in files:
            archive.write(path, relative)
    digest = hashlib.sha256()
    size = 0
    with temporary.open("rb") as source:
        for chunk in iter(lambda: source.read(CHUNK_BYTES), b""):
            size += len(chunk)
            digest.update(chunk)
    return manifest, digest.hexdigest(), size


def _header_bytes(*, salt: bytes, nonce: bytes, payload_sha256: str,
                  payload_size: int, expanded_size: int) -> bytes:
    value = {
        "product": PRODUCT,
        "schema_version": SCHEMA_VERSION,
        "encrypted": True,
        "cipher": "AES-256-GCM",
        "kdf": {"name": "scrypt", "n": SCRYPT_N, "r": SCRYPT_R,
                "p": SCRYPT_P, "salt": base64.b64encode(salt).decode("ascii")},
        "nonce": base64.b64encode(nonce).decode("ascii"),
        "payload_sha256": payload_sha256,
        "payload_size": payload_size,
        "expanded_size": expanded_size,
    }
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def _write_encrypted(zip_path: Path, target: Path, password: str,
                     payload_sha256: str, payload_size: int,
                     expanded_size: int | None = None) -> None:
    salt, nonce = os.urandom(SALT_BYTES), os.urandom(NONCE_BYTES)
    header = _header_bytes(salt=salt, nonce=nonce,
                           payload_sha256=payload_sha256,
                           payload_size=payload_size,
                           expanded_size=(payload_size if expanded_size is None
                                          else expanded_size))
    if len(header) > HEADER_LIMIT:
        raise SessionPackageError("заголовок пакета слишком велик")
    prefix = MAGIC + struct.pack(">I", len(header)) + header
    key = _derive_key(_password(password), salt)
    encryptor = Cipher(algorithms.AES(key), modes.GCM(nonce)).encryptor()
    encryptor.authenticate_additional_data(prefix)
    temporary = target.with_name(target.name + ".tmp")
    try:
        with zip_path.open("rb") as source, temporary.open("xb") as output:
            output.write(prefix)
            for chunk in iter(lambda: source.read(CHUNK_BYTES), b""):
                output.write(encryptor.update(chunk))
            output.write(encryptor.finalize())
            output.write(encryptor.tag)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def _audit(data_root: Path, operation: str, *, session: str = "",
           details: dict | None = None) -> None:
    directory = Path(data_root).resolve() / AUDIT_DIR
    directory.mkdir(parents=True, exist_ok=True)
    record = {
        "schema_version": 1,
        "timestamp": _now(),
        "operation": operation,
        "session_sha256": hashlib.sha256(session.encode("utf-8")).hexdigest()
        if session else "",
        "details": details or {},
    }
    path = directory / AUDIT_FILE
    with path.open("a", encoding="utf-8", newline="\n") as output:
        output.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
        output.flush()
        os.fsync(output.fileno())


def record_recording_basis(session: Path) -> dict:
    """Persist the operator's statement without calling it legal consent."""
    session = Path(session).resolve()
    session.mkdir(parents=True, exist_ok=True)
    record = {
        "schema_version": 1,
        "timestamp": _now(),
        "statement": "participants_notified_or_other_applicable_basis",
        "statement_version": 1,
    }
    path = session / "recording-basis.jsonl"
    with path.open("a", encoding="utf-8", newline="\n") as output:
        output.write(json.dumps(
            record, ensure_ascii=False, separators=(",", ":")) + "\n")
        output.flush()
        os.fsync(output.fileno())
    return record


def _validated_policies(policies: dict) -> dict[str, int]:
    if not isinstance(policies, dict):
        raise SessionPackageError("retention должен быть JSON-объектом")
    checked = dict(DEFAULT_RETENTION)
    if set(policies) - set(DEFAULT_RETENTION):
        raise SessionPackageError("retention содержит неизвестную категорию")
    for category, raw_days in policies.items():
        if isinstance(raw_days, bool):
            raise SessionPackageError("срок хранения должен быть числом дней")
        try:
            days = int(raw_days)
        except (TypeError, ValueError) as exc:
            raise SessionPackageError("срок хранения должен быть числом дней") from exc
        if not 0 <= days <= 36500:
            raise SessionPackageError("срок хранения должен быть от 0 до 36500 дней")
        checked[category] = days
    return checked


def load_retention_policy(data_root: Path) -> dict[str, int]:
    path = Path(data_root).resolve() / AUDIT_DIR / RETENTION_FILE
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or value.get("schema_version") != 1:
            raise SessionPackageError("формат retention-политики не поддерживается")
        return _validated_policies(value.get("days"))
    except FileNotFoundError:
        return dict(DEFAULT_RETENTION)
    except (OSError, UnicodeError, ValueError) as exc:
        raise SessionPackageError("retention-политика повреждена") from exc


def save_retention_policy(data_root: Path, policies: dict) -> dict[str, int]:
    checked = _validated_policies(policies)
    directory = Path(data_root).resolve() / AUDIT_DIR
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / RETENTION_FILE
    temporary = path.with_name(path.name + ".tmp")
    value = {"schema_version": 1, "updated_at": _now(), "days": checked}
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as output:
            json.dump(value, output, ensure_ascii=False, indent=2)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    _audit(data_root, "retention_policy", details={"days": checked})
    return checked


def export_session(sessions_root: Path, session_name: str, data_root: Path,
                   password: str) -> dict:
    """Create a verified encrypted package without mutating the session."""
    root = Path(sessions_root).resolve(strict=True)
    session = direct_child(root, session_name, must_exist=True)
    if session.is_symlink():
        raise SessionPackageError("символическая ссылка не может быть сессией")
    output_root = packages_root(data_root)
    target = _package_path(output_root)
    source_files = _source_files(session)
    expanded_size = sum(item[2] for item in source_files)
    required = expanded_size * 2 + MIN_FREE_BYTES
    if shutil.disk_usage(output_root).free < required:
        raise SessionPackageError(
            "недостаточно свободного места для временного ZIP и шифрования")
    with tempfile.TemporaryDirectory(prefix="blatero-package-",
                                     dir=output_root) as temp_dir:
        zip_path = Path(temp_dir) / "payload.zip"
        manifest, digest, size = _build_zip(session, zip_path, source_files)
        candidate = Path(temp_dir) / "verified.blatero-session"
        _write_encrypted(
            zip_path, candidate, password, digest, size, expanded_size)
        verified = inspect_package(candidate, password)
        if verified["payload_sha256"] != digest:
            raise SessionPackageError("контрольная проверка созданного пакета не прошла")
        # Publish only a package whose *member bytes* have been verified. A
        # changed source cancels export and leaves no apparently valid package.
        os.replace(candidate, target)
    _audit(data_root, "export", session=session.name, details={
        "package": target.name, "files": len(manifest["files"]),
        "expanded_bytes": sum(item["size"] for item in manifest["files"]),
    })
    return {
        "name": target.name,
        "path": str(target),
        "files": len(manifest["files"]),
        "expanded_bytes": sum(item["size"] for item in manifest["files"]),
        "package_bytes": target.stat().st_size,
        "encrypted": True,
        "payload_sha256": digest,
    }


def _read_header(source: io.BufferedReader) -> tuple[dict, bytes]:
    magic = source.read(len(MAGIC))
    if magic != MAGIC:
        raise SessionPackageError("это не пакет сессии Blatero")
    raw_length = source.read(4)
    if len(raw_length) != 4:
        raise SessionPackageError("заголовок пакета оборван")
    length = struct.unpack(">I", raw_length)[0]
    if not 1 <= length <= HEADER_LIMIT:
        raise SessionPackageError("некорректная длина заголовка пакета")
    raw = source.read(length)
    try:
        header = json.loads(raw.decode("utf-8"))
    except (UnicodeError, ValueError) as exc:
        raise SessionPackageError("заголовок пакета повреждён") from exc
    if (not isinstance(header, dict) or header.get("product") != PRODUCT
            or header.get("schema_version") != SCHEMA_VERSION
            or header.get("cipher") != "AES-256-GCM"
            or header.get("encrypted") is not True):
        raise SessionPackageError("формат пакета не поддерживается")
    return header, magic + raw_length + raw


def _decode_bytes(value: object, expected: int, field: str) -> bytes:
    try:
        decoded = base64.b64decode(str(value or ""), validate=True)
    except (ValueError, TypeError) as exc:
        raise SessionPackageError(f"поле {field} повреждено") from exc
    if len(decoded) != expected:
        raise SessionPackageError(f"поле {field} имеет неверную длину")
    return decoded


def _validated_sizes(header: dict) -> tuple[int, int]:
    payload_size = header.get("payload_size")
    expanded_size = header.get("expanded_size")
    if not isinstance(payload_size, int) or not 1 <= payload_size <= MAX_EXPANDED_BYTES:
        raise SessionPackageError("некорректный размер содержимого")
    if (not isinstance(expanded_size, int)
            or not 1 <= expanded_size <= MAX_EXPANDED_BYTES):
        raise SessionPackageError("некорректный распакованный размер")
    return payload_size, expanded_size


def _decrypt_to(package: Path, password: str, target_zip: Path) -> tuple[dict, str]:
    size = package.stat().st_size
    if size <= len(MAGIC) + 4 + TAG_BYTES:
        raise SessionPackageError("пакет оборван")
    with package.open("rb") as source:
        header, prefix = _read_header(source)
        kdf = header.get("kdf")
        if not isinstance(kdf, dict) or kdf.get("name") != "scrypt":
            raise SessionPackageError("неподдерживаемая функция получения ключа")
        salt = _decode_bytes(kdf.get("salt"), SALT_BYTES, "salt")
        nonce = _decode_bytes(header.get("nonce"), NONCE_BYTES, "nonce")
        payload_size, _ = _validated_sizes(header)
        ciphertext_start = source.tell()
        ciphertext_size = size - ciphertext_start - TAG_BYTES
        if ciphertext_size != payload_size:
            raise SessionPackageError("размер зашифрованного содержимого не совпал")
        source.seek(size - TAG_BYTES)
        tag = source.read(TAG_BYTES)
        key = _derive_key(
            _password(password), salt, n=kdf.get("n"), r=kdf.get("r"), p=kdf.get("p"))
        decryptor = Cipher(algorithms.AES(key), modes.GCM(nonce, tag)).decryptor()
        decryptor.authenticate_additional_data(prefix)
        source.seek(ciphertext_start)
        remaining = ciphertext_size
        digest = hashlib.sha256()
        try:
            with target_zip.open("xb") as output:
                while remaining:
                    chunk = source.read(min(CHUNK_BYTES, remaining))
                    if not chunk:
                        raise SessionPackageError("зашифрованное содержимое оборвано")
                    remaining -= len(chunk)
                    plain = decryptor.update(chunk)
                    output.write(plain)
                    digest.update(plain)
                final = decryptor.finalize()
                output.write(final)
                digest.update(final)
                output.flush()
                os.fsync(output.fileno())
        except SessionPackageError:
            raise
        except Exception as exc:
            raise SessionPackageError(
                "пакет не расшифрован: неверный пароль или повреждение") from exc
    actual = digest.hexdigest()
    expected = str(header.get("payload_sha256") or "").lower()
    if not re.fullmatch(r"[0-9a-f]{64}", expected) or actual != expected:
        raise SessionPackageError("SHA-256 содержимого пакета не совпал")
    return header, actual


def _safe_member(name: str) -> str:
    if "\\" in name or "\x00" in name:
        raise SessionPackageError("пакет содержит небезопасный путь")
    path = PurePosixPath(name)
    if path.is_absolute() or not path.parts or any(
            part in {"", ".", ".."} for part in path.parts):
        raise SessionPackageError("пакет содержит путь за пределы сессии")
    return path.as_posix()


def _manifest_from_zip(path: Path) -> tuple[dict, dict[str, zipfile.ZipInfo]]:
    try:
        archive = zipfile.ZipFile(path, "r")
    except (OSError, zipfile.BadZipFile) as exc:
        raise SessionPackageError("внутренний ZIP повреждён") from exc
    with archive:
        infos: dict[str, zipfile.ZipInfo] = {}
        total = 0
        for info in archive.infolist():
            name = _safe_member(info.filename)
            mode = (info.external_attr >> 16) & 0o170000
            if mode == 0o120000 or info.is_dir():
                if mode == 0o120000:
                    raise SessionPackageError("символические ссылки в пакете запрещены")
                continue
            if name in infos:
                raise SessionPackageError("в пакете повторяется имя файла")
            if info.file_size > MAX_SINGLE_FILE_BYTES:
                raise SessionPackageError(f"слишком большой файл в пакете: {name}")
            total += info.file_size
            if total > MAX_EXPANDED_BYTES or len(infos) >= MAX_FILES + 1:
                raise SessionPackageError("распакованное содержимое превышает лимит")
            infos[name] = info
        manifest_info = infos.get("blatero-session-manifest.json")
        if manifest_info is None or manifest_info.file_size > HEADER_LIMIT * 64:
            raise SessionPackageError("манифест пакета отсутствует или слишком велик")
        try:
            manifest = json.loads(archive.read(manifest_info).decode("utf-8"))
        except (UnicodeError, ValueError, zipfile.BadZipFile) as exc:
            raise SessionPackageError("манифест пакета повреждён") from exc
    if (not isinstance(manifest, dict) or manifest.get("product") != PRODUCT
            or manifest.get("schema_version") != SCHEMA_VERSION
            or not isinstance(manifest.get("files"), list)):
        raise SessionPackageError("формат манифеста пакета не поддерживается")
    return manifest, infos


def _validate_manifest(manifest: dict, infos: dict[str, zipfile.ZipInfo]) -> list[dict]:
    expected = set(infos) - {"blatero-session-manifest.json"}
    records = []
    seen = set()
    for item in manifest["files"]:
        if not isinstance(item, dict):
            raise SessionPackageError("некорректная запись в манифесте")
        name = _safe_member(str(item.get("path") or ""))
        digest = str(item.get("sha256") or "").lower()
        size = item.get("size")
        if name in seen or name not in infos or not isinstance(size, int):
            raise SessionPackageError("манифест не соответствует содержимому ZIP")
        if size != infos[name].file_size or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise SessionPackageError("размер или SHA-256 файла в манифесте неверен")
        seen.add(name)
        records.append({"path": name, "size": size, "sha256": digest})
    if seen != expected:
        raise SessionPackageError("в ZIP есть файлы, не перечисленные в манифесте")
    return records


def inspect_package(package: Path, password: str) -> dict:
    source = Path(package).resolve(strict=True)
    if source.is_symlink() or not source.is_file():
        raise SessionPackageError("пакет должен быть обычным файлом")
    with tempfile.TemporaryDirectory(prefix="blatero-inspect-",
                                     dir=source.parent) as temp_dir:
        zip_path = Path(temp_dir) / "payload.zip"
        header, digest = _decrypt_to(source, password, zip_path)
        manifest, infos = _manifest_from_zip(zip_path)
        records = _validate_manifest(manifest, infos)
        with zipfile.ZipFile(zip_path, "r") as archive:
            for item in records:
                member_digest = hashlib.sha256()
                actual_size = 0
                try:
                    with archive.open(infos[item["path"]], "r") as member:
                        for chunk in iter(lambda: member.read(CHUNK_BYTES), b""):
                            member_digest.update(chunk)
                            actual_size += len(chunk)
                except (zipfile.BadZipFile, EOFError, RuntimeError) as exc:
                    raise SessionPackageError("повреждено содержимое файла в пакете") from exc
                if actual_size != item["size"] or member_digest.hexdigest() != item["sha256"]:
                    raise SessionPackageError(
                        f"SHA-256 файла в пакете не совпал: {item['path']}; "
                        "возможно, исходный файл изменился во время экспорта")
    return {
        "encrypted": True,
        "source_session": str(manifest.get("source_session") or "meeting"),
        "files": len(records),
        "expanded_bytes": sum(item["size"] for item in records),
        "payload_sha256": digest,
        "created_at": str(manifest.get("created_at") or ""),
        "cipher": header["cipher"],
    }


def import_package(package: Path, password: str, sessions_root: Path,
                   data_root: Path) -> dict:
    """Verify and atomically publish a package as a new unique session."""
    source = Path(package).resolve(strict=True)
    if source.is_symlink() or not source.is_file():
        raise SessionPackageError("пакет должен быть обычным файлом")
    root = Path(sessions_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as package_stream:
        header, _ = _read_header(package_stream)
    payload_size, expanded_size = _validated_sizes(header)
    required = payload_size + expanded_size + MIN_FREE_BYTES
    if shutil.disk_usage(root).free < required:
        raise SessionPackageError(
            "недостаточно свободного места для проверки и импорта пакета")
    with tempfile.TemporaryDirectory(prefix="blatero-import-", dir=root) as temp_dir:
        temporary_root = Path(temp_dir)
        zip_path = temporary_root / "payload.zip"
        _, payload_digest = _decrypt_to(source, password, zip_path)
        manifest, infos = _manifest_from_zip(zip_path)
        records = _validate_manifest(manifest, infos)
        extracted = temporary_root / "session"
        extracted.mkdir()
        with zipfile.ZipFile(zip_path, "r") as archive:
            for item in records:
                target = extracted.joinpath(*PurePosixPath(item["path"]).parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                digest = hashlib.sha256()
                with (archive.open(infos[item["path"]], "r") as input_stream,
                      target.open("xb") as output):
                    for chunk in iter(lambda: input_stream.read(CHUNK_BYTES), b""):
                        output.write(chunk)
                        digest.update(chunk)
                    output.flush()
                    os.fsync(output.fileno())
                if digest.hexdigest() != item["sha256"]:
                    raise SessionPackageError(
                        f"SHA-256 распакованного файла не совпал: {item['path']}")
        base = re.sub(r"[^\w-]+", "_", str(
            manifest.get("source_session") or "imported"), flags=re.UNICODE).strip("_.-")
        published = unique_session_dir(root, (base[:60] or "imported") + "-import")
        # unique_session_dir reserves the target. Replace that empty reservation
        # with the fully verified tree on the same filesystem.
        published.rmdir()
        os.replace(extracted, published)
    _audit(data_root, "import", session=published.name, details={
        "package_sha256": _file_digest(source),
        "payload_sha256": payload_digest,
        "files": len(records),
    })
    return {
        "session": published.name,
        "files": len(records),
        "expanded_bytes": sum(item["size"] for item in records),
        "payload_sha256": payload_digest,
    }


def _category_for(relative: Path) -> set[str]:
    name = relative.name.casefold()
    parts = {part.casefold() for part in relative.parts[:-1]}
    result = set()
    # Only our capture artifacts, not a user's arbitrary nested "video" directory.
    if (len(relative.parts) == 3 and relative.parts[0].casefold() == "video"
            and re.fullmatch(r"[0-9a-f]{32}", relative.parts[1])
            and (name in {"recording.mkv", "recording.partial.mkv", "preview.png", "state.json", "worker.log"}
                 or re.fullmatch(r"state-[0-9a-f]{32}\.tmp", name))):
        result.add("video")
    if relative.suffix.casefold() in _AUDIO_SUFFIXES:
        result.add("audio")
    if name.startswith("transcript") and relative.suffix.casefold() in {
            ".md", ".jsonl", ".json", ".txt"}:
        result.add("transcripts")
    if (name.startswith(_REPORT_PREFIXES)
            or name.startswith("evidence")):
        result.add("reports")
    if parts & _DERIVED_DIRS or name.startswith(_DERIVED_PREFIXES):
        result.add("derived")
    return result


def purge_preview(sessions_root: Path, session_name: str,
                  categories: set[str]) -> dict:
    checked = {str(item) for item in categories}
    if not checked or not checked <= set(CATEGORY_LABELS):
        raise SessionPackageError("не выбраны допустимые категории удаления")
    root = Path(sessions_root).resolve(strict=True)
    session = direct_child(root, session_name, must_exist=True)
    if "all" in checked:
        files = [path for path in session.rglob("*")
                 if path.is_file() and not path.is_symlink()]
    else:
        files = [path for path in session.rglob("*")
                 if path.is_file() and not path.is_symlink()
                 and (_category_for(path.relative_to(session)) & checked)]
    return {
        "session": session.name,
        "categories": sorted(checked),
        "files": len(files),
        "bytes": sum(path.stat().st_size for path in files),
        "sample": [path.relative_to(session).as_posix() for path in files[:12]],
    }


def purge(sessions_root: Path, session_name: str, categories: set[str],
          data_root: Path) -> dict:
    """Apply an already confirmed purge; caller must block active sessions."""
    preview = purge_preview(sessions_root, session_name, categories)
    # A durable intent must exist before the first irreversible mutation. If the
    # audit volume is unavailable, leave user data untouched.
    _audit(data_root, "purge_intent", session=session_name, details={
        "categories": preview["categories"], "files": preview["files"],
        "bytes": preview["bytes"],
    })
    root = Path(sessions_root).resolve(strict=True)
    session = direct_child(root, session_name, must_exist=True)
    if "all" in preview["categories"]:
        shutil.rmtree(session)
    else:
        checked = set(preview["categories"])
        targets = [path for path in session.rglob("*")
                   if path.is_file() and not path.is_symlink()
                   and (_category_for(path.relative_to(session)) & checked)]
        for path in targets:
            path.unlink()
        for directory in sorted(
                (path for path in session.rglob("*") if path.is_dir()),
                key=lambda path: len(path.parts), reverse=True):
            try:
                directory.rmdir()
            except OSError:
                pass
    try:
        _audit(data_root, "purge", session=session_name, details={
            "categories": preview["categories"], "files": preview["files"],
            "bytes": preview["bytes"], "committed": True,
        })
    except OSError as exc:
        # Deletion has committed and cannot truthfully be reported as failed.
        # The pre-commit intent remains as the durable audit breadcrumb.
        preview["audit_warning"] = (
            "данные удалены, но итоговая запись журнала не сохранена: "
            f"{type(exc).__name__}")
    return preview


def retention_preview(sessions_root: Path, policies: dict[str, int],
                      *, now: dt.datetime | None = None) -> dict:
    """Calculate an age-based purge plan without changing any file."""
    checked = {category: days for category, days in
               _validated_policies(policies).items() if days}
    current = now or dt.datetime.now().astimezone()
    root = Path(sessions_root).resolve(strict=True)
    items = []
    for session in sorted(root.iterdir(), key=lambda item: item.name.casefold()):
        if not session.is_dir() or session.is_symlink() or session.name.startswith("."):
            continue
        modified = dt.datetime.fromtimestamp(session.stat().st_mtime,
                                             tz=current.tzinfo)
        age_days = max(0, (current - modified).days)
        due = {category for category, days in checked.items() if age_days >= days}
        if not due:
            continue
        preview = purge_preview(root, session.name, due)
        if preview["files"]:
            items.append({**preview, "age_days": age_days})
    return {
        "policies": checked,
        "sessions": len(items),
        "files": sum(item["files"] for item in items),
        "bytes": sum(item["bytes"] for item in items),
        "items": items,
    }


def apply_retention(sessions_root: Path, policies: dict[str, int],
                    data_root: Path, *, now: dt.datetime | None = None) -> dict:
    plan = retention_preview(sessions_root, policies, now=now)
    results = []
    for item in plan["items"]:
        results.append(purge(
            sessions_root, item["session"], set(item["categories"]), data_root))
    return {**plan, "applied": True, "results": results}
