"""Explicit per-turn outcome receipts. No model calls, inferred ids or acceptance."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from project_contract import canonical
from project_provenance import context
from project_queue import atomic_json, event_path
from project_store import make_event, now

FIELDS = ("summary", "method", "rationale", "next_step")


def receipt(event: dict, task: dict, recorded_at: str) -> dict:
    """Called inside the event transaction; its result is stored with that event."""
    return {"event_id": event["event_id"], **{key: event["source"][key]
            for key in ("system", "session_id", "turn_id")},
            "work_item_id": task["id"], "applied_revision": task["revision"],
            "snapshot_sha256": hashlib.sha256(canonical(task).encode()).hexdigest(),
            "summary": event["payload"]["summary"], "recorded_at": recorded_at}


def event_for(store, task, who, provenance, payload):
    if not provenance or not provenance.get("turn_id"):
        raise ValueError("итог хода требует --system, --session и --turn")
    source = context(**provenance)
    for key in FIELDS:
        if not isinstance(payload.get(key), str) or not payload[key].strip():
            raise ValueError(f"нужно непустое поле итога: {key}")
    # Stable identity for retry after an unknown delivery. The original emitted
    # time/event_key must be retained, not regenerated under the same id.
    identity = {"task": task["id"], "revision": task["revision"],
                "actor": who["id"], "source": source, "payload": payload}
    eid = "turn:" + hashlib.sha256(canonical(identity).encode()).hexdigest()
    previous = store.recorded_event(eid)
    if previous:
        return previous["event"]
    path = event_path(store.root, eid)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))["event"]
    event = make_event(task, who, "session.outcome", payload, event_id=eid, **source)
    return event


def current_turn(system, session_id, transcript):
    """Compatibility with clients omitting turn_id: exact local journal only.

    No cwd/global latest session or previous cached id. Fail closed if a client
    changes its private journal schema, the context is outside the bounded tail,
    or the latest known turn has ended. This is not a public Codex API.
    """
    if system != "codex":
        raise ValueError("этот клиент должен передать turn_id явно")
    path = Path(transcript)
    if not path.is_absolute() or path.suffix != ".jsonl":
        raise ValueError("нужен абсолютный путь первичного JSONL текущей сессии")
    with path.open("rb") as stream:
        first = stream.readline(64 * 1024)
        header = json.loads(first)
        if header.get("type") != "session_meta" or header.get("payload", {}).get("id") != session_id:
            raise ValueError("журнал относится к другой сессии")
        size = stream.seek(0, 2)
        offset = max(0, size - 8 * 1024 * 1024)
        stream.seek(offset)
        tail = stream.read(8 * 1024 * 1024)
    lines = tail.split(b"\n")
    if offset:
        lines = lines[1:]  # A partial first record cannot establish identity.
    candidate = None
    for raw in lines[:-1]:  # Never trust a not-yet-complete final record.
        try:
            row = json.loads(raw)
        except (ValueError, UnicodeError):
            continue
        if not isinstance(row, dict):
            continue
        payload = row.get("payload", {})
        if not isinstance(payload, dict):
            continue
        if row.get("type") == "turn_context":
            candidate = payload.get("turn_id")
        elif row.get("type") == "event_msg":
            kind = payload.get("type")
            if kind == "task_started":
                # A newer turn without a context is not the previous turn.
                if payload.get("turn_id") != candidate:
                    candidate = None
            elif kind in {"task_complete", "turn_aborted"}:
                candidate = None
    if not candidate:
        raise ValueError("активный turn_id не подтверждён в ограниченном хвосте журнала")
    return {**context(system, session_id, candidate), "identity_source": "transcript_context"}


def outcome_status(store, system, session_id, turn_id, task_id=None):
    source = context(system, session_id, turn_id)
    binding = store.session(system, session_id)
    bound = binding.get("work_item_id") if binding else None
    if not bound:
        return {"state": "unbound", **source}
    if task_id and task_id != bound:
        return {"state": "other_task", **source, "work_item_id": bound}
    # Source ids are JSON data, never SQL fragments. The task's indexed history
    # is bounded to this card rather than scanning all projects' transcripts.
    with store.connect() as conn:
        rows = conn.execute("SELECT rowid,event_json,result_json FROM events "
                            "WHERE work_item_id=? AND state='applied' ORDER BY rowid DESC", (bound,))
        changed = False
        for row in rows:
            event = json.loads(row["event_json"])
            if any(event["source"].get(key) != value for key, value in source.items()):
                continue
            if event["event_type"] == "session.outcome":
                result = json.loads(row["result_json"])
                if "receipt" in result:
                    return {"state": "stale" if changed else "recorded", **source,
                            "work_item_id": bound, "receipt": result["receipt"]}
            if event["event_type"] in {"task.updated", "task.status_changed", "session.checkpoint"}:
                changed = True
    return {"state": "missing", **source, "work_item_id": bound}


def stop_check(store, system, data):
    """One continuation at most. Missing identity is visible, never guessed."""
    sid, turn = data.get("session_id"), data.get("turn_id")
    binding = store.session(system, sid)
    if not binding or not binding.get("work_item_id"):
        return {}
    if not turn and data.get("transcript_path"):
        try:
            turn = current_turn(system, sid, data["transcript_path"])["turn_id"]
        except (OSError, ValueError, TypeError):
            pass
    status = outcome_status(store, system, sid, turn) if turn else {"state": "unverifiable"}
    # An audit gap remains visible even if a client cannot continue or has
    # already continued once. Never store the user's prompt/final response here.
    identity = hashlib.sha256(canonical([system, sid, turn]).encode()).hexdigest()
    atomic_json(store.root / "turn-checks" / (identity + ".json"),
                {"checked_at": now(), "system": system, "session_id": sid, "turn_id": turn,
                 "work_item_id": binding["work_item_id"], "state": status["state"],
                 "receipt_event_id": status.get("receipt", {}).get("event_id"),
                 "stop_hook_active": bool(data.get("stop_hook_active"))})
    if not turn:
        return {"systemMessage": "Blatero: итог хода не проверен — клиент не передал turn_id. "
                "Предыдущая квитанция не используется. Карточка не принята автоматически."}
    if status["state"] == "unbound":
        return {"systemMessage": "Blatero: сессия не связана с карточкой; итог хода не проверен."}
    if status["state"] == "recorded":
        r = status["receipt"]
        return {"systemMessage": f"Blatero: итог хода сохранён, редакция {r['applied_revision']}. "
                "Это не приёмка задачи."}
    message = (f"Blatero: нет актуальной квитанции итога хода {turn} для карточки "
               f"{status['work_item_id']}. Перечитай context, затем выполни finish-turn TASK "
               "--revision N --summary TEXT --method TEXT --rationale TEXT --next-step TEXT "
               f"--system {system} --session {sid} --turn {turn}. Сохрани фактический итог, "
               "проверки, ограничения и следующий шаг. queued/conflict не означают сохранение; "
               "проверь outcome-status. Не принимай и не закрывай задачу за пользователя.")
    if data.get("stop_hook_active"):
        return {"systemMessage": message + " Повторное продолжение не запрашивается."}
    return {"decision": "block", "reason": message}
