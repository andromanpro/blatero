"""Local derived hint ledger; raw pulses, transcripts and audio are immutable inputs."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
from difflib import SequenceMatcher
import tempfile
import threading

from operation_lock import OperationLock

FILE = "hints-state.json"
MAX_BYTES = 20_000_000
MAX_CARDS = 10_000
_LOCK = threading.RLock()
REASONS = {"irrelevant", "unhelpful", "duplicate", "other"}


def _now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def _key(text):
    return " ".join(re.findall(r"\w+", str(text).casefold().replace("ё", "е")))


def _same(left, right):
    a, b = _key(left), _key(right)
    if a == b:
        return True
    # Different task numbers, negations and question intent must not disappear.
    if min(len(a), len(b)) < 35 or re.findall(r"\d+|\bне\b|\bнет\b", a) != re.findall(
        r"\d+|\bне\b|\bнет\b", b
    ):
        return False
    return a.split()[0] == b.split()[0] and SequenceMatcher(None, a, b).ratio() >= 0.94


def _read(path):
    if path.is_symlink():
        raise ValueError("Состояние подсказок не может быть ссылкой")
    if path.stat().st_size > MAX_BYTES:
        raise ValueError("История подсказок превышает безопасный размер")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise ValueError("История подсказок повреждена; исходный файл сохранён") from exc
    if (
        not isinstance(value, dict)
        or value.get("schema") != 1
        or not isinstance(value.get("cards"), list)
        or not isinstance(value.get("revision"), int)
        or not isinstance(value.get("pulses"), list)
    ):
        raise ValueError("Неизвестный формат истории подсказок")
    if len(value["cards"]) > MAX_CARDS or any(
        not isinstance(c, dict)
        or c.get("kind") not in {"question", "answer", "risk"}
        or c.get("status") not in {"active", "resolved", "dismissed"}
        or any(not isinstance(c.get(k), str) for k in ("id", "text", "reason", "last_pulse"))
        for c in value["cards"]
    ):
        raise ValueError("Повреждены карточки истории подсказок; исходный файл сохранён")
    return value


def _empty():
    return {"schema": 1, "revision": 0, "cards": [], "last_pulse": "", "pulses": []}


def _merge(data, hints, pulse_id):
    if pulse_id in data["pulses"]:
        return False
    for card in data["cards"]:
        card["stale"] = True
    for kind, field, text_field in [
        ("answer", "answers", "answer"),
        ("question", "questions", "q"),
        ("risk", "flags", "text"),
    ]:
        values = hints.get(field, [])
        for item in (values if isinstance(values, list) else [])[:20]:
            text = str(item.get(text_field, "") if isinstance(item, dict) else item).strip()[:2000]
            if not text:
                continue
            existing = next(
                (
                    c
                    for c in reversed(data["cards"])
                    if c["kind"] == kind and _same(c["text"], text)
                ),
                None,
            )
            if existing is not None:
                existing.update(last_pulse=pulse_id, stale=False, seen=existing["seen"] + 1)
                continue
            if len(data["cards"]) >= MAX_CARDS:
                raise ValueError(
                    "История подсказок заполнена; исходный ответ сохранён в hints.jsonl"
                )
            identifier = hashlib.sha256((kind + "\0" + _key(text)).encode()).hexdigest()[:24]
            data["cards"].append(
                {
                    "id": identifier,
                    "kind": kind,
                    "text": text,
                    "why": str(item.get("why", ""))[:500] if isinstance(item, dict) else "",
                    "status": "active",
                    "pinned": False,
                    "archived": False,
                    "stale": False,
                    "created_at": _now(),
                    "last_pulse": pulse_id,
                    "seen": 1,
                    "reason": "",
                }
            )
    data["last_pulse"] = pulse_id
    data["pulses"].append(pulse_id)
    data["revision"] += 1
    return True


def payload(session: Path):
    session = Path(session)
    path = session / FILE
    if path.exists() or path.is_symlink():
        return _read(path)
    data = _empty()
    raw = session / "hints.jsonl"
    if not raw.exists():
        return data
    if raw.is_symlink() or raw.stat().st_size > MAX_BYTES:
        raise ValueError(
            "Исходный журнал подсказок превышает безопасный размер или является ссылкой"
        )
    for index, line in enumerate(raw.read_text(encoding="utf-8").splitlines()):
        if not line.strip():
            continue
        try:
            hints = json.loads(line)
            if not isinstance(hints, dict):
                continue
        except ValueError:
            # A torn final raw response is not a reason to discard earlier ones.
            continue
        meta = hints.get("_meta")
        pulse_id = str(
            (meta.get("pulse_id") if isinstance(meta, dict) else "") or f"legacy-{index}"
        )
        _merge(data, hints, pulse_id)
    return data


def _save(session, data):
    path = Path(session) / FILE
    if path.is_symlink():
        raise ValueError("Состояние подсказок не может быть ссылкой")
    text = json.dumps(data, ensure_ascii=False, indent=2)
    if len(text.encode()) > MAX_BYTES:
        raise ValueError("История подсказок превышает безопасный размер")
    fd, temporary = tempfile.mkstemp(prefix="hints-state-", suffix=".tmp", dir=session)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def _lock(session):
    path = Path(session) / "hints-state.lock"
    if path.is_symlink():
        raise ValueError("Блокировка подсказок не может быть ссылкой")
    return OperationLock(path)


def merge(session: Path, hints: dict, pulse_id: str):
    with _LOCK, _lock(session):
        data = payload(session)
        if _merge(data, hints, pulse_id):
            _save(session, data)
        return data


def act(session: Path, body: dict):
    with _LOCK, _lock(session):
        data = payload(session)
        if body.get("revision") != data["revision"]:
            raise ValueError("Подсказки изменились. Повторите действие с обновлённым списком")
        card = next((c for c in data["cards"] if c["id"] == body.get("id")), None)
        if card is None:
            raise ValueError("Подсказка не найдена")
        action = body.get("action")
        if action == "pin":
            card.update(pinned=True, archived=False)
        elif action == "unpin":
            card["pinned"] = False
        elif action == "archive":
            if not card["pinned"]:
                card["archived"] = True
        elif action == "resolve":
            card.update(status="resolved", pinned=False, changed_at=_now())
        elif action == "dismiss":
            if body.get("reason") not in REASONS:
                raise ValueError("Выберите причину отклонения")
            card.update(status="dismissed", reason=body["reason"], pinned=False, changed_at=_now())
        elif action == "restore":
            card.update(status="active", archived=False, reason="", changed_at=_now())
        else:
            raise ValueError("Неизвестное действие с подсказкой")
        data["revision"] += 1
        _save(session, data)
        return data


def feedback(session: Path):
    data = payload(session)
    rows = [
        {"kind": c["kind"], "text": c["text"], "status": c["status"], "reason": c["reason"]}
        for c in data["cards"]
        if c["status"] != "active"
    ][-50:]
    return json.dumps(rows, ensure_ascii=False) if rows else ""


def safe_payload(session: Path):
    """A damaged derived ledger must not make the whole recording UI unopenable."""
    try:
        return payload(session)
    except (OSError, ValueError, UnicodeError) as exc:
        return {**_empty(), "error": str(exc)}
