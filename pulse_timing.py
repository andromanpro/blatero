"""Локальная телеметрия времени формирования подсказок.

Файл намеренно не хранит текст транскрипта, промпт или ответ модели. Две
JSONL-записи на pulse (started/finished) позволяют отличить реальную задержку
от симуляции и увидеть оборванный запрос после аварийного завершения процесса.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import threading
import time
import uuid
from pathlib import Path

import transcript_events
import operation_contract


FILE_NAME = "pulse-timings.jsonl"
SCHEMA_VERSION = 1
_TRANSCRIPT = re.compile(r"transcript(?:-\d+)?\.jsonl")
_LOCK = threading.RLock()
_MAX_EVENTS = 5000
_MAX_LINE = 16_384


def _now() -> dt.datetime:
    return dt.datetime.now().astimezone()


def _iso(value: dt.datetime) -> str:
    return value.isoformat(timespec="milliseconds")


def _append(session: Path, event: dict) -> None:
    session = Path(session).resolve()
    if not session.is_dir():
        raise FileNotFoundError("папка встречи не найдена")
    path = session / FILE_NAME
    if path.is_symlink():
        raise ValueError("файл телеметрии pulse не может быть ссылкой")
    public = {key: value for key, value in event.items()
              if not str(key).startswith("_")}
    line = json.dumps(public, ensure_ascii=False, separators=(",", ":")) + "\n"
    if len(line.encode("utf-8")) > _MAX_LINE:
        raise ValueError("запись телеметрии pulse слишком велика")
    with _LOCK, path.open("a", encoding="utf-8", newline="") as output:
        output.write(line)
        output.flush()
        os.fsync(output.fileno())


def _snapshot(session: Path, transcript: Path, now: dt.datetime) -> dict:
    session = Path(session).resolve()
    transcript = Path(transcript).resolve()
    journal = transcript.with_suffix(".jsonl") if transcript.suffix == ".md" else transcript
    if (journal.parent != session or not _TRANSCRIPT.fullmatch(journal.name)
            or not journal.is_file()):
        return {"transcript_file": "", "transcript_bytes": 0,
                "transcript_end_ms": 0, "meeting_offset_ms": None}
    try:
        records = transcript_events.read_records(journal)
        header = records[0]
        started = dt.datetime.fromisoformat(str(header["started_at"]))
        if started.tzinfo is None:
            started = started.replace(tzinfo=now.tzinfo)
        end_ms = max((int(item.get("end_ms", 0)) for item in records
                      if item.get("record_type") == "utterance"), default=0)
        offset = max(0, round((now - started).total_seconds() * 1000))
    except (OSError, ValueError, TypeError, KeyError, IndexError):
        end_ms, offset = 0, None
    try:
        size = journal.stat().st_size
    except OSError:
        size = 0
    return {"transcript_file": journal.name, "transcript_bytes": size,
            "transcript_end_ms": end_ms, "meeting_offset_ms": offset}


def start(session: Path, transcript: Path, *, trigger: str, model: str,
          signal_count: int = 0, generation: int = 0) -> dict:
    """Зафиксировать начало pulse и вернуть маркер для :func:`finish`."""
    now = _now()
    event = {
        "schema_version": SCHEMA_VERSION, "event": "started",
        "pulse_id": uuid.uuid4().hex, "requested_at": _iso(now),
        "trigger": "auto" if trigger == "auto" else "manual",
        "requested_model": str(model or "")[:160],
        "signal_count": max(0, min(int(signal_count), 100)),
        "generation": int(generation),
        **_snapshot(Path(session), Path(transcript), now),
        "_monotonic": time.monotonic(),
    }
    _append(Path(session), event)
    return event


def finish(session: Path, started: dict, *, outcome: str,
           error_type: str = "", error_code: str = "") -> dict:
    """Зафиксировать терминальное состояние pulse без содержимого подсказки."""
    if outcome not in {"success", "error", "cancelled"}:
        raise ValueError("неизвестный результат pulse")
    now = _now()
    try:
        elapsed = max(0, round((time.monotonic()
                                - float(started["_monotonic"])) * 1000))
    except (KeyError, TypeError, ValueError):
        requested = dt.datetime.fromisoformat(str(started["requested_at"]))
        elapsed = max(0, round((now - requested).total_seconds() * 1000))
    event = {
        "schema_version": SCHEMA_VERSION, "event": "finished",
        "pulse_id": str(started.get("pulse_id") or "")[:64],
        "completed_at": _iso(now), "duration_ms": elapsed,
        "outcome": outcome, "error_type": str(error_type or "")[:120],
        "error_code": str(error_code or "")[:80],
    }
    _append(Path(session), event)
    return event


def read(session: Path) -> list[dict]:
    """Прочитать валидные события; повреждённые строки изолируются."""
    path = Path(session).resolve() / FILE_NAME
    if path.is_symlink() or not path.is_file():
        return []
    result: list[dict] = []
    with _LOCK, path.open("r", encoding="utf-8", errors="replace") as source:
        for line in source:
            if len(line.encode("utf-8", errors="replace")) > _MAX_LINE:
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if (isinstance(value, dict)
                    and value.get("schema_version") == SCHEMA_VERSION
                    and value.get("event") in {"started", "finished"}
                    and re.fullmatch(r"[a-f0-9]{32}", str(value.get("pulse_id") or ""))):
                result.append(value)
    return result[-_MAX_EVENTS:]


def operation_status(session: Path, *, live_id: str = "") -> dict | None:
    """Read the latest pulse's durable outcome; an absent owner means unknown."""
    events = read(session)
    started = next((e for e in reversed(events) if e["event"] == "started"), None)
    if started is None:
        return None
    identity = started["pulse_id"]
    finished = next((e for e in reversed(events) if e["event"] == "finished" and e["pulse_id"] == identity), None)
    code, result = "", None
    if finished:
        if finished.get("outcome") == "success":
            state = "succeeded"
            result = {"history": "hints.jsonl", "pulse_id": identity}
        elif finished.get("outcome") == "cancelled" or finished.get("error_type") == "TimeoutError":
            state, code = "outcome_unknown", "outcome_unknown"
        elif finished.get("outcome") == "error":
            state, code = "failed", str(finished.get("error_code") or "pulse_failed")
        else:
            state, code = "outcome_unknown", "invalid_operation_journal"
    elif live_id == identity:
        state = "running"
    else:
        state, code = "outcome_unknown", "outcome_unknown"
    requested = str(started.get("requested_at") or "")
    try:
        generation = int(started.get("generation") or 0)
        dt.datetime.fromisoformat(requested)
    except (ValueError, TypeError):
        state, code, generation, result = "outcome_unknown", "invalid_operation_journal", 0, None
    return operation_contract.build(identity=identity, session=Path(session).name, kind="pulse", state=state,
        stage="request" if state == "running" else "finished", revision=2 if finished else 1,
        generation=generation, started_at=requested,
        updated_at=str((finished or {}).get("completed_at") or requested),
        error_code=code, result=result)


def completed(session: Path) -> list[dict]:
    """Собрать пары started/finished; незавершённые начала не теряются."""
    starts: dict[str, dict] = {}
    result: list[dict] = []
    for event in read(session):
        pulse_id = str(event["pulse_id"])
        if event["event"] == "started":
            starts[pulse_id] = event
        else:
            start_event = starts.pop(pulse_id, None)
            if start_event:
                result.append({**start_event, **event})
    for event in starts.values():
        result.append({**event, "outcome": "interrupted", "duration_ms": None})
    return result
