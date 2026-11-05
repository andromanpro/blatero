"""Crash-safe lifecycle and conservative recovery of live meeting artifacts."""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import shutil
import struct
import time
from pathlib import Path

import transcript_events
from operation_lock import OperationLock, OperationLockError, lock_is_held, process_is_alive
from session_utils import direct_child


SCHEMA_VERSION = 1
STATE_FILE = ".recording-state.json"
RECOVERY_REPORT_FILE = "recovery-report.json"
LEVELS_FILE = "levels.json"
STOP_REQUEST_FILE = ".stop-request"
OWNER_LOCK_FILE = ".recording-owner.lock"
ACTIVE_PHASES = frozenset({"recording", "finalizing", "interrupted"})
STALE_AFTER_SECONDS = 8.0
MIN_FREE_RESERVE_BYTES = 16 * 1024 * 1024
SPACE_OVERHEAD_PERCENT = 5
_TEMP_FILES = frozenset({
    f"{STATE_FILE}.tmp", LEVELS_FILE, f"{LEVELS_FILE}.tmp", STOP_REQUEST_FILE,
})
_RECOVERY_TEMP = re.compile(
    r"^(?:audio-(?:me|guest)(?:-\d+)?\.before-recovery(?:-\d+)?\.wav\.tmp|"
    r"transcript(?:-\d+)?\.before-recovery(?:-\d+)?\.(?:md|jsonl)\.tmp|"
    r"transcript(?:-\d+)?\.jsonl\.recovery\.tmp)$",
    re.IGNORECASE,
)
_OWNER_LOCKS: dict[tuple[str, str], OperationLock] = {}


def _now() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="milliseconds")


def _atomic_json(path: Path, value: dict) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}
    return value if isinstance(value, dict) else {}


def _safe_name(value: object) -> str:
    name = str(value or "").strip()
    return name if name and Path(name).name == name else ""


def begin(session: Path, *, recording_id: str, segment: int,
          transcript_file: str, journal_file: str,
          audio_files: list[str], provider: str) -> dict:
    """Persist enough metadata to recover a recording after an abrupt exit."""
    session = Path(session).resolve()
    owner_key = (str(session), str(recording_id))
    owner = OperationLock(session / OWNER_LOCK_FILE)
    try:
        owner.acquire()
    except OperationLockError as exc:
        raise RuntimeError("в этой сессии уже идёт запись") from exc
    started = _now()
    state = {
        "schema_version": SCHEMA_VERSION,
        "phase": "recording",
        "recording_id": str(recording_id),
        "pid": os.getpid(),
        "segment": max(1, int(segment)),
        "provider": str(provider or "unknown")[:80],
        "started_at": started,
        "updated_at": started,
        "heartbeat_at": started,
        "elapsed_seconds": 0,
        "transcript_file": _safe_name(transcript_file),
        "journal_file": _safe_name(journal_file),
        "audio_files": [name for name in map(_safe_name, audio_files) if name],
    }
    try:
        _atomic_json(session / STATE_FILE, state)
    except Exception:
        owner.release()
        raise
    old = _OWNER_LOCKS.pop(owner_key, None)
    if old is not None:
        old.release()
    _OWNER_LOCKS[owner_key] = owner
    return state


def _release_owner(session: Path, recording_id: str) -> None:
    owner = _OWNER_LOCKS.pop(
        (str(Path(session).resolve()), str(recording_id)), None)
    if owner is not None:
        owner.release()


def _transition(session: Path, phase: str, *, recording_id: str = "",
                elapsed_seconds: float | None = None,
                error: str = "") -> dict:
    path = Path(session) / STATE_FILE
    state = _read_json(path)
    if not state or (recording_id and state.get("recording_id") != recording_id):
        return {}
    now = _now()
    state.update(phase=phase, updated_at=now)
    if elapsed_seconds is not None:
        state["elapsed_seconds"] = max(0, round(float(elapsed_seconds), 1))
    if phase == "recording":
        state["heartbeat_at"] = now
    if error:
        state["error"] = " ".join(str(error).split())[:500]
    _atomic_json(path, state)
    return state


def heartbeat(session: Path, recording_id: str, elapsed_seconds: float) -> dict:
    return _transition(
        session, "recording", recording_id=recording_id,
        elapsed_seconds=elapsed_seconds)


def mark_finalizing(session: Path, recording_id: str,
                    elapsed_seconds: float) -> dict:
    return _transition(
        session, "finalizing", recording_id=recording_id,
        elapsed_seconds=elapsed_seconds)


def mark_interrupted(session: Path, recording_id: str,
                     elapsed_seconds: float, error: str) -> dict:
    try:
        return _transition(
            session, "interrupted", recording_id=recording_id,
            elapsed_seconds=elapsed_seconds, error=error)
    finally:
        _release_owner(session, recording_id)


def complete(session: Path, recording_id: str,
             elapsed_seconds: float) -> dict:
    try:
        result = _transition(
            session, "completed", recording_id=recording_id,
            elapsed_seconds=elapsed_seconds)
        for name in (LEVELS_FILE, f"{LEVELS_FILE}.tmp", STOP_REQUEST_FILE):
            (Path(session) / name).unlink(missing_ok=True)
        return result
    finally:
        _release_owner(session, recording_id)


def _timestamp(value: object) -> float:
    try:
        parsed = dt.datetime.fromisoformat(str(value))
        if parsed.tzinfo is None:
            parsed = parsed.astimezone()
        return parsed.timestamp()
    except (TypeError, ValueError):
        return 0.0


def _fresh_levels(session: Path, now: float) -> bool:
    levels = _read_json(session / LEVELS_FILE)
    try:
        age = now - float(levels.get("ts", 0))
        return -5.0 <= age < 3.0
    except (TypeError, ValueError):
        return False


def _wav_info(path: Path) -> dict:
    result = {
        "name": path.name, "exists": path.is_file(), "valid": False,
        "repairable": False, "size": 0, "duration_seconds": 0.0,
        "issue": "файл отсутствует",
    }
    if not path.is_file():
        return result
    size = path.stat().st_size
    result["size"] = size
    if size < 44:
        result["issue"] = "WAV короче минимального заголовка"
        return result
    try:
        with path.open("rb") as source:
            header = source.read(12)
            if len(header) != 12 or header[:4] != b"RIFF" or header[8:] != b"WAVE":
                result["issue"] = "не распознан RIFF/WAVE-заголовок"
                return result
            riff_size = struct.unpack("<I", header[4:8])[0]
            fmt = None
            data_offset = None
            data_size_offset = None
            declared_data = None
            while source.tell() + 8 <= min(size, 1024 * 1024):
                chunk_header = source.read(8)
                if len(chunk_header) != 8:
                    break
                chunk_id = chunk_header[:4]
                chunk_size = struct.unpack("<I", chunk_header[4:])[0]
                payload_offset = source.tell()
                if chunk_id == b"fmt ":
                    raw = source.read(min(chunk_size, 40))
                    if len(raw) >= 16:
                        fmt = struct.unpack("<HHIIHH", raw[:16])
                elif chunk_id == b"data":
                    data_offset = payload_offset
                    data_size_offset = payload_offset - 4
                    declared_data = chunk_size
                    break
                source.seek(payload_offset + chunk_size + (chunk_size % 2))
    except OSError as exc:
        result["issue"] = f"WAV не читается: {exc}"
        return result
    if fmt is None or data_offset is None or data_size_offset is None:
        result["issue"] = "в WAV отсутствует fmt или data"
        return result
    audio_format, channels, rate, _byte_rate, block_align, bits = fmt
    actual_data = max(0, size - data_offset)
    usable_data = actual_data - (actual_data % max(1, block_align))
    result.update({
        "data_offset": data_offset,
        "data_size_offset": data_size_offset,
        "actual_data_size": usable_data,
        "declared_data_size": declared_data,
        "riff_size": riff_size,
        "sample_rate": rate,
        "channels": channels,
        "bits_per_sample": bits,
        "duration_seconds": round(usable_data / max(1, rate * block_align), 1),
    })
    supported = audio_format == 1 and channels > 0 and rate > 0 and block_align > 0
    if not supported:
        result["issue"] = "неподдерживаемый формат WAV"
        return result
    expected_riff = size - 8
    valid = (riff_size == expected_riff and declared_data == usable_data
             and actual_data - usable_data <= 1)
    result["valid"] = valid
    result["repairable"] = not valid
    result["issue"] = "" if valid else "не завершены размеры RIFF/data"
    return result


def _journal_info(path: Path) -> dict:
    result = {
        "name": path.name, "exists": path.is_file(), "valid": False,
        "repairable": False, "turns": 0, "size": 0,
        "issue": "файл отсутствует",
    }
    if not path.is_file():
        return result
    try:
        result["size"] = path.stat().st_size
        lines = path.read_bytes().splitlines(keepends=True)
    except OSError as exc:
        result["issue"] = f"JSONL не читается: {exc}"
        return result
    valid_lines = []
    invalid = []
    turns = 0
    first_record = None
    for index, raw in enumerate(lines):
        if not raw.strip():
            valid_lines.append(raw)
            continue
        try:
            value = json.loads(raw.decode("utf-8"))
            if not isinstance(value, dict):
                raise ValueError("ожидался объект")
        except (UnicodeDecodeError, ValueError, json.JSONDecodeError):
            invalid.append(index)
            continue
        valid_lines.append(raw)
        if first_record is None:
            first_record = value
        if value.get("record_type") == "utterance":
            turns += 1
    result["turns"] = turns
    result["line_count"] = len(lines)
    result["valid_line_count"] = len(valid_lines)
    if first_record is None or first_record.get("record_type") != "recording":
        result["issue"] = "в JSONL отсутствует recording header"
        return result
    if not invalid:
        result.update(valid=True, issue="")
        return result
    trailing_only = invalid == [len(lines) - 1]
    result["repairable"] = trailing_only
    result["issue"] = ("оборвана последняя строка JSONL" if trailing_only else
                       "повреждение JSONL находится внутри журнала")
    return result


def _artifact_names(session: Path, state: dict) -> tuple[str, str, list[str]]:
    transcript = _safe_name(state.get("transcript_file"))
    journal = _safe_name(state.get("journal_file"))
    if not journal:
        candidates = sorted(session.glob("transcript*.jsonl"),
                            key=lambda item: item.stat().st_mtime, reverse=True)
        journal = candidates[0].name if candidates else ""
    if not transcript and journal:
        transcript = str(Path(journal).with_suffix(".md").name)
    audio = [name for name in map(_safe_name, state.get("audio_files") or []) if name]
    if not audio:
        audio = [item.name for item in sorted(
            session.glob("audio-*.wav"), key=lambda item: item.stat().st_mtime,
            reverse=True)[:2]]
    return transcript, journal, audio


def _recovery_space(session: Path, transcript_name: str, journal: dict,
                    audio: list[dict]) -> dict:
    """Conservative same-volume budget before the first recovery mutation."""
    backup_bytes = 0
    working_bytes = 64 * 1024  # lifecycle and recovery-report atomic JSON files
    journal_name = _safe_name(journal.get("name"))
    journal_size = int(journal.get("size", 0) or 0)
    if journal_name and journal.get("exists"):
        if journal.get("repairable"):
            backup_bytes += journal_size
            working_bytes += journal_size
        transcript = session / _safe_name(transcript_name)
        try:
            transcript_size = transcript.stat().st_size if transcript.is_file() else 0
        except OSError as exc:
            return {
                "checked": False, "sufficient": False,
                "backup_bytes": backup_bytes, "working_bytes": working_bytes,
                "reserve_bytes": MIN_FREE_RESERVE_BYTES,
                "required_bytes": backup_bytes + working_bytes
                + MIN_FREE_RESERVE_BYTES,
                "free_bytes": 0,
                "message": ("не удалось измерить файлы восстановления: "
                            f"{type(exc).__name__}"),
            }
        if transcript_size:
            backup_bytes += transcript_size
        # JSONL is normally larger than rendered Markdown; keep the larger
        # existing artifact as a safe estimate for the atomic render temp.
        working_bytes += max(4096, journal_size, transcript_size)
    for item in audio:
        if item.get("repairable"):
            backup_bytes += int(item.get("size", 0) or 0)
    base = backup_bytes + working_bytes
    reserve_bytes = max(
        MIN_FREE_RESERVE_BYTES,
        (base * SPACE_OVERHEAD_PERCENT + 99) // 100,
    )
    required_bytes = base + reserve_bytes
    try:
        free_bytes = int(shutil.disk_usage(session).free)
    except OSError as exc:
        return {
            "checked": False, "sufficient": False,
            "backup_bytes": backup_bytes, "working_bytes": working_bytes,
            "reserve_bytes": reserve_bytes, "required_bytes": required_bytes,
            "free_bytes": 0,
            "message": ("не удалось проверить свободное место: "
                        f"{type(exc).__name__}"),
        }
    sufficient = free_bytes >= required_bytes
    return {
        "checked": True, "sufficient": sufficient,
        "backup_bytes": backup_bytes, "working_bytes": working_bytes,
        "reserve_bytes": reserve_bytes, "required_bytes": required_bytes,
        "free_bytes": free_bytes,
        "message": ("места достаточно для резервных копий" if sufficient else
                    "недостаточно места для безопасного восстановления"),
    }


def _candidate(session: Path, state: dict, *, source: str, now: float) -> dict:
    transcript, journal_name, audio_names = _artifact_names(session, state)
    journal = (_journal_info(session / journal_name) if journal_name else {
        "name": "", "exists": False, "valid": False, "repairable": False,
        "turns": 0, "issue": "JSONL-журнал не найден",
    })
    audio = [_wav_info(session / name) for name in audio_names]
    issues = []
    if journal["issue"]:
        issues.append(journal["issue"])
    issues.extend(item["issue"] for item in audio if item["issue"])
    if state.get("error"):
        issues.insert(0, str(state["error"]))
    last_activity = max(
        _timestamp(state.get("heartbeat_at")), _timestamp(state.get("updated_at")),
        max((item.stat().st_mtime for item in session.iterdir() if item.is_file()),
            default=session.stat().st_mtime))
    meta = _read_json(session / "meta.json")
    duration = max(
        [float(state.get("elapsed_seconds", 0) or 0)]
        + [float(item.get("duration_seconds", 0) or 0) for item in audio])
    journal_safe = (not journal["exists"] or journal["valid"]
                    or journal["repairable"])
    has_recoverable_data = bool(
        journal.get("valid") or journal.get("repairable")
        or any(item.get("repairable") for item in audio))
    content_repairable = bool(journal_safe and has_recoverable_data)
    space = _recovery_space(session, transcript, journal, audio)
    issues = issues or ["запись не была штатно завершена"]
    if content_repairable and not space["sufficient"]:
        issues.append(str(space["message"]))
    return {
        "session": session.name,
        "label": str(meta.get("name") or session.name),
        "phase": str(state.get("phase") or "interrupted"),
        "source": source,
        "started_at": str(state.get("started_at") or ""),
        "last_activity": dt.datetime.fromtimestamp(
            last_activity, tz=dt.datetime.now().astimezone().tzinfo
        ).isoformat(timespec="seconds"),
        "age_seconds": max(0, round(now - last_activity)),
        "duration_seconds": round(duration, 1),
        "transcript_file": transcript,
        "journal": journal,
        "audio": audio,
        "turns": int(journal.get("turns", 0)),
        "issues": issues,
        "repairable": content_repairable,
        "recovery_ready": bool(content_repairable and space["sufficient"]),
        "space": space,
    }


def scan(sessions_root: Path, *, now: float | None = None) -> list[dict]:
    """Return stale unfinished recordings; never treats a fresh process as stale."""
    root = Path(sessions_root)
    root.mkdir(parents=True, exist_ok=True)
    current = time.time() if now is None else float(now)
    result = []
    for session in root.iterdir():
        if not session.is_dir() or _fresh_levels(session, current):
            continue
        state = _read_json(session / STATE_FILE)
        if state:
            phase = str(state.get("phase") or "")
            last = max(_timestamp(state.get("heartbeat_at")),
                       _timestamp(state.get("updated_at")))
            stale = (current - last >= STALE_AFTER_SECONDS
                     or last - current > 60.0)
            if phase == "interrupted":
                result.append(_candidate(
                    session, state, source="lifecycle", now=current))
            elif phase in ACTIVE_PHASES and stale:
                lock_file = session / OWNER_LOCK_FILE
                owner_active = (
                    lock_is_held(lock_file) if lock_file.exists()
                    else process_is_alive(state.get("pid")))
                if not owner_active:
                    result.append(_candidate(
                        session, state, source="lifecycle", now=current))
            continue
        # Pre-lifecycle versions left levels.json after every normal stop. Offer
        # recovery only when an artifact is demonstrably incomplete.
        if not (session / LEVELS_FILE).exists():
            continue
        legacy_state = {"phase": "interrupted"}
        candidate = _candidate(session, legacy_state, source="legacy", now=current)
        broken = (candidate["journal"]["exists"] and not candidate["journal"]["valid"]
                  or any(item["exists"] and not item["valid"]
                         for item in candidate["audio"]))
        if broken:
            result.append(candidate)
    result.sort(key=lambda item: item["last_activity"], reverse=True)
    return result


def payload(sessions_root: Path) -> dict:
    items = scan(sessions_root)
    return {"state": "needs_attention" if items else "ready", "items": items,
            "count": len(items)}


def _backup(path: Path) -> Path:
    candidate = path.with_name(f"{path.stem}.before-recovery{path.suffix}")
    number = 2
    while candidate.exists():
        candidate = path.with_name(
            f"{path.stem}.before-recovery-{number}{path.suffix}")
        number += 1
    temporary = candidate.with_name(candidate.name + ".tmp")
    try:
        temporary.unlink(missing_ok=True)
        source_size = path.stat().st_size
        shutil.copy2(path, temporary)
        if temporary.stat().st_size != source_size:
            raise OSError(f"неполная резервная копия {path.name}")
        # Windows requires a writable descriptor for FlushFileBuffers/fsync.
        with temporary.open("r+b") as copied:
            os.fsync(copied.fileno())
        os.replace(temporary, candidate)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return candidate


def _repair_wav(path: Path, info: dict) -> tuple[str, str] | None:
    if info.get("valid") or not info.get("repairable"):
        return None
    backup = _backup(path)
    with path.open("r+b") as output:
        output.seek(4)
        output.write(struct.pack("<I", max(0, path.stat().st_size - 8)))
        output.seek(int(info["data_size_offset"]))
        output.write(struct.pack("<I", int(info["actual_data_size"])))
        output.flush()
        os.fsync(output.fileno())
    verified = _wav_info(path)
    if not verified["valid"]:
        shutil.copy2(backup, path)
        raise ValueError(f"не удалось проверить восстановленный {path.name}")
    return path.name, backup.name


def _repair_journal(path: Path, info: dict) -> tuple[str, str] | None:
    if info.get("valid"):
        return None
    if not info.get("repairable"):
        raise ValueError(f"{path.name}: {info.get('issue')}")
    backup = _backup(path)
    lines = path.read_bytes().splitlines(keepends=True)
    valid = b"".join(lines[:-1])
    if valid and not valid.endswith((b"\n", b"\r")):
        valid += b"\n"
    temporary = path.with_name(path.name + ".recovery.tmp")
    temporary.write_bytes(valid)
    os.replace(temporary, path)
    verified = _journal_info(path)
    if not verified["valid"]:
        shutil.copy2(backup, path)
        raise ValueError(f"не удалось проверить восстановленный {path.name}")
    return path.name, backup.name


def cleanup_temporary_files(session: Path) -> list[str]:
    removed = []
    for name in sorted(_TEMP_FILES):
        path = Path(session) / name
        if path.is_file():
            path.unlink()
            removed.append(name)
    for path in sorted(Path(session).iterdir(), key=lambda item: item.name):
        if path.is_file() and _RECOVERY_TEMP.fullmatch(path.name):
            path.unlink()
            removed.append(path.name)
    return removed


def _resolve_candidate(sessions_root: Path, session_name: str) -> tuple[Path, dict]:
    session = direct_child(Path(sessions_root), session_name, must_exist=True)
    item = next((entry for entry in scan(sessions_root)
                 if entry["session"] == session.name), None)
    if item is None:
        raise ValueError("незавершённая запись уже обработана или снова активна")
    return session, item


def recover(sessions_root: Path, session_name: str) -> dict:
    """Repair only provably recoverable tails, preserving every changed original."""
    session, item = _resolve_candidate(sessions_root, session_name)
    transcript_name = _safe_name(item.get("transcript_file"))
    space = _recovery_space(
        session, transcript_name, item.get("journal", {}),
        list(item.get("audio", [])))
    if not space["sufficient"]:
        if space["checked"]:
            raise OSError(
                "недостаточно места для безопасного восстановления: "
                f"нужно {space['required_bytes']} байт, свободно "
                f"{space['free_bytes']} байт")
        raise OSError(str(space["message"]))
    repairs = []
    journal_name = str(item.get("journal", {}).get("name") or "")
    if journal_name:
        repaired = _repair_journal(session / journal_name, item["journal"])
        if repaired:
            repairs.append({"file": repaired[0], "backup": repaired[1]})
        if transcript_name:
            transcript_path = session / transcript_name
            if transcript_path.exists():
                backup = _backup(transcript_path)
                repairs.append({"file": transcript_path.name, "backup": backup.name})
            transcript_events.render_markdown(session / journal_name, transcript_path)
    for audio in item.get("audio", []):
        name = _safe_name(audio.get("name"))
        if name:
            repaired = _repair_wav(session / name, audio)
            if repaired:
                repairs.append({"file": repaired[0], "backup": repaired[1]})
    removed = cleanup_temporary_files(session)
    report = {
        "schema_version": SCHEMA_VERSION, "action": "recovered",
        "created_at": _now(), "session": session.name,
        "repairs": repairs, "removed_temporary_files": removed,
        "space": space,
        "note": "Изменённые оригиналы сохранены рядом с суффиксом before-recovery.",
    }
    _atomic_json(session / RECOVERY_REPORT_FILE, report)
    # Lifecycle state is the commit marker. Publish it only after both the
    # repaired artifacts and the audit report have reached disk atomically.
    state_path = session / STATE_FILE
    state = _read_json(state_path)
    state.update({
        "schema_version": SCHEMA_VERSION, "phase": "recovered",
        "updated_at": _now(), "recovered_at": _now(),
    })
    _atomic_json(state_path, state)
    return report


def finalize_interrupted(sessions_root: Path, session_name: str) -> dict:
    """Acknowledge an interruption without modifying transcript or audio."""
    session, _item = _resolve_candidate(sessions_root, session_name)
    removed = cleanup_temporary_files(session)
    state = _read_json(session / STATE_FILE)
    state.update({
        "schema_version": SCHEMA_VERSION,
        "phase": "interrupted_finalized",
        "updated_at": _now(), "finalized_at": _now(),
    })
    _atomic_json(session / STATE_FILE, state)
    report = {
        "schema_version": SCHEMA_VERSION, "action": "finalized_without_repair",
        "created_at": _now(), "session": session.name,
        "repairs": [], "removed_temporary_files": removed,
        "note": "Аудио и транскрипт оставлены без изменений.",
    }
    _atomic_json(session / RECOVERY_REPORT_FILE, report)
    return report


def cleanup(sessions_root: Path, session_name: str) -> dict:
    session, _item = _resolve_candidate(sessions_root, session_name)
    removed = cleanup_temporary_files(session)
    return {"session": session.name, "removed_temporary_files": removed}
