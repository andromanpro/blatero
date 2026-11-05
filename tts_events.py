"""Координация TTS панели с live.py для защиты транскрипта от loopback-эха."""
from __future__ import annotations

import difflib
import json
import math
import os
import re
import time
from pathlib import Path

STATE_FILE = ".tts-playback.json"


def _path(sdir: Path) -> Path:
    return sdir / STATE_FILE


def _read(sdir: Path) -> dict:
    try:
        payload = json.loads(_path(sdir).read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except (OSError, ValueError):
        return {}


def _write(sdir: Path, payload: dict) -> None:
    target = _path(sdir)
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, target)


def _fresh(now: float, stamp, seconds: float) -> bool:
    try:
        age = now - float(stamp)
        return math.isfinite(age) and 0 <= age < seconds
    except (ValueError, TypeError, OverflowError):
        return False


def _active(payload: dict, now: float) -> bool:
    # Legacy files without a lease are not evidence of current playback.
    try:
        remaining = float(payload.get("expires", 0)) - now
        return bool(payload.get("active") and _fresh(now, payload.get("started"), 180)
                    and math.isfinite(remaining) and 0 < remaining <= 180)
    except (ValueError, TypeError, OverflowError):
        return False


def start(sdir: Path, text: str, *, lease_seconds: float = 180) -> None:
    now = time.time()
    previous = _read(sdir)
    recent = previous.get("recent") if isinstance(previous.get("recent"), list) else []
    recent = [item for item in recent if isinstance(item, dict) and _fresh(now, item.get("ts"), 45)]
    recent.append({"ts": now, "text": text})
    lease = max(1, min(180, float(lease_seconds)))
    _write(sdir, {"active": True, "started": now, "text": text,
                  "owner_pid": os.getpid(),
                  "lease_seconds": lease, "expires": now + lease,
                  "recent": recent[-5:]})


def refresh(sdir: Path, text: str) -> bool:
    payload = _read(sdir)
    now = time.time()
    if payload.get("text") != text or not _active(payload, now):
        return False
    try:
        lease = float(payload["lease_seconds"])
        if not math.isfinite(lease) or not 1 <= lease <= 180:
            return False
    except (KeyError, ValueError, TypeError, OverflowError):
        return False
    payload["expires"] = min(float(payload["started"]) + 180, now + lease)
    _write(sdir, payload)
    return True


def end(sdir: Path, *, text: str | None = None) -> None:
    payload = _read(sdir)
    if text is not None and payload.get("text") != text:
        return
    payload["active"] = False
    payload["ended"] = time.time()
    recent = payload.get("recent") if isinstance(payload.get("recent"), list) else []
    if payload.get("text"):
        recent.append({"ts": payload["ended"], "text": payload["text"]})
    payload["recent"] = recent[-5:]
    _write(sdir, payload)


def is_active(sdir: Path) -> bool:
    """Идёт ли сейчас синтетическая реплика в системный аудиоканал."""
    payload = _read(sdir)
    try:
        return payload.get("owner_pid") == os.getpid() and _active(payload, time.time())
    except (ValueError, TypeError, OverflowError):
        return False


def _normalized(text: str) -> str:
    return " ".join(re.findall(r"[a-zа-яё0-9]+", text.casefold()))


def _similar(left: str, right: str) -> bool:
    left, right = _normalized(left), _normalized(right)
    if min(len(left.split()), len(right.split())) < 4:
        return False
    ratio = difflib.SequenceMatcher(None, left, right).ratio()
    a, b = set(left.split()), set(right.split())
    jaccard = len(a & b) / max(1, len(a | b))
    return ratio >= 0.86 or (jaccard >= 0.8 and ratio >= 0.75)


def should_suppress_guest(sdir: Path, recognized: str) -> bool:
    """Убрать из канала собеседника воспроизводимый синтетический вопрос."""
    payload = _read(sdir)
    now = time.time()
    # Playback, including a stale active flag, must NEVER blanket-mute another person.
    if (_active(payload, now)
            and _similar(str(payload.get("text", "")), recognized)):
        return True
    recent = payload.get("recent") if isinstance(payload.get("recent"), list) else []
    return any(isinstance(item, dict) and _fresh(now, item.get("ts"), 30)
               and _similar(str(item.get("text", "")), recognized)
               for item in recent)
