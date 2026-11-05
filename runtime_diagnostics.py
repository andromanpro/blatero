"""Bounded, content-free local diagnostics. Never put exception messages here."""
from __future__ import annotations

import datetime as dt
import json
import math
import os
from pathlib import Path
import re
import threading
from collections import Counter
from operation_lock import OperationLock, OperationLockError

FILE_NAME = "diagnostics.jsonl"
LOCK_FILE = ".diagnostics.lock"
MAX_BYTES = 4 * 1024 * 1024
_LOCK = threading.RLock()
_LABEL = re.compile(r"[a-zA-Z0-9_.:-]{1,128}\Z")
_LABEL_FIELDS = {"component", "provider", "model", "code", "outcome", "stage",
                 "recording_id", "pulse_id", "request_id", "session_id", "error_type"}
_NUMERIC_FIELDS = {"segment", "audio_ms", "duration_ms", "wait_ms", "inference_ms",
                   "queue_ms", "start_ms", "end_ms", "result_chars", "input_chars",
                   "rtf", "attempt", "beam_size", "cpu_threads", "workers",
                   "backoff_ms", "dropped_chunks", "latency_ms", "exit_code", "http_status"}
_ROLES = {"Я": "mic", "Собеседник": "guest", "mic": "mic", "guest": "guest"}
EVENTS = {"capture.device_changed", "stt.inference", "stt.final", "stt.rpc_error", "stt.rpc_started", "stt.rpc_finished",
          "stt.switch.applied", "stt.switch.failed",
          "stt.switch.requested", "capture.started", "capture.stopped", "capture.stop_requested",
          "pulse.started", "pulse.context", "pulse.request_started", "pulse.request", "pulse.parse",
          "pulse.attempt_error", "pulse.error"}
_SAFE_CODES = {"ok", "timeout", "invalid_data", "io_error", "runtime_error", "cli_exit", "empty_response",
               "auth_error", "quota_error", "provider_server_error", "http_error",
               "CANCELLED", "UNKNOWN", "INVALID_ARGUMENT", "DEADLINE_EXCEEDED",
               "NOT_FOUND", "ALREADY_EXISTS", "PERMISSION_DENIED", "RESOURCE_EXHAUSTED",
               "FAILED_PRECONDITION", "ABORTED", "OUT_OF_RANGE", "UNIMPLEMENTED",
               "INTERNAL", "UNAVAILABLE", "DATA_LOSS", "UNAUTHENTICATED"}


def _number(value):
    if type(value) not in (int,float) or (isinstance(value,float) and not math.isfinite(value)):
        return None
    return round(max(0,min(value,1e12)),4)


def error_code(error: BaseException, _depth: int = 0) -> str:
    """Useful classification without copying a message, URL, token or user data."""
    category = getattr(error,"diagnostic_code",None)
    if isinstance(category,str) and category in _SAFE_CODES:
        return category
    if isinstance(error, TimeoutError) or type(error).__name__ in {"Timeout", "ReadTimeout", "ConnectTimeout", "TimeoutExpired"}:
        return "timeout"
    status = getattr(getattr(error,"response",None),"status_code",None)
    if type(status) is int and status >= 400:
        return ("auth_error" if status in {401,403} else "quota_error" if status == 429
                else "provider_server_error" if status >= 500 else "http_error")
    if isinstance(error, (ValueError, TypeError)):
        return "invalid_data"
    if isinstance(error, OSError):
        return "io_error"
    if _depth < 8 and error.__cause__ is not None and error.__cause__ is not error:
        # Wrappers preserve the useful category, not the provider's message.
        return error_code(error.__cause__, _depth+1)
    return "runtime_error"


def record(session: Path | None, event: str, **fields) -> None:
    if session is None or not isinstance(event,str) or event not in EVENTS:
        return
    row = {"schema_version": 1, "occurred_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="milliseconds"),
           "event": event, "pid": os.getpid()}
    for key, value in fields.items():
        if key in _LABEL_FIELDS and isinstance(value, str) and _LABEL.fullmatch(value):
            row[key] = value
        elif key in _NUMERIC_FIELDS and type(value) in (int, float):
            bounded = _number(value)
            if bounded is not None:
                row[key] = bounded
        elif key == "role" and isinstance(value,str) and value in _ROLES:
            row[key] = _ROLES[value]
    try:
        folder = Path(session)
        target = folder / FILE_NAME
        rotated = folder / (FILE_NAME + ".1")
        lock_path = folder / LOCK_FILE
        if (not folder.is_dir() or folder.is_symlink() or target.is_symlink()
                or rotated.is_symlink() or lock_path.is_symlink()):
            return
        line = json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
        # Panel and the live child write here concurrently. A failed nonblocking
        # lock drops only this diagnostic event, never stalls audio/corrupts JSONL.
        with _LOCK, OperationLock(lock_path):
            if target.exists() and target.stat().st_size + len(line.encode("utf-8")) > MAX_BYTES:
                os.replace(target, rotated)
            with target.open("a", encoding="utf-8", newline="") as output:
                output.write(line)
    except (OSError, OperationLockError):
        # Diagnostics must not stop audio or a successful model response.
        return


def summary(session: Path) -> dict:
    """Aggregate recent metrics, never include raw events or identifiers in export."""
    rows = []
    for name in (FILE_NAME+".1",FILE_NAME):
        path = Path(session)/name
        if not path.is_file() or path.is_symlink():
            continue
        try:
            with path.open("rb") as source:
                offset=max(0,path.stat().st_size-512_000)
                source.seek(offset)
                if offset:
                    source.readline(4096)
                lines=source.read(512_000).decode("utf-8",errors="replace").splitlines()
            for line in lines:
                try:
                    row=json.loads(line)
                except ValueError:
                    continue
                if isinstance(row,dict) and isinstance(row.get("event"),str) and row["event"] in EVENTS:
                    rows.append(row)
        except OSError:
            continue
    rows=rows[-2000:]
    events=Counter(row["event"] for row in rows)
    codes=Counter(row["code"] if row.get("code") in _SAFE_CODES else "other"
                  for row in rows if isinstance(row.get("code"),str))
    durations={}
    for event in sorted(events):
        values=sorted(value for row in rows if row["event"]==event
                      and (value:=_number(row.get("duration_ms"))) is not None)
        if values:
            durations[event]={"count":len(values),"median_ms":values[len(values)//2],
                              "p95_ms":values[min(len(values)-1,int(len(values)*.95))],"max_ms":values[-1]}
    return {"sampled_events":len(rows),"limit":2000,"event_counts":dict(events),
            "code_counts":dict(codes),"duration_ms":durations}
