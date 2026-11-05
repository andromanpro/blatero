"""Explicit command provenance. No global active-session lookup or inference."""

from __future__ import annotations

import json
import os


def context(system: str, session_id: str, turn_id: str | None = None) -> dict:
    result = {"system": system, "session_id": session_id}
    if turn_id is not None:
        result["turn_id"] = turn_id
    for key, value in result.items():
        limit = 80 if key == "system" else 160
        if (
            not isinstance(value, str)
            or not value
            or value != value.strip()
            or len(value) > limit
            or any(ord(c) < 32 or ord(c) == 127 for c in value)
            or (key == "turn_id" and any(c.isspace() for c in value))
        ):
            raise ValueError(f"неверный идентификатор происхождения: {key}")
        try:
            value.encode("utf-8")
        except UnicodeError as exc:
            raise ValueError(f"неверная кодировка идентификатора: {key}") from exc
    return result


def from_args(args) -> dict | None:
    """Explicit flags take precedence as a group; never mix sessions and turns."""
    values = [getattr(args, key, None) for key in ("system", "session", "turn")]
    legacy = args.command in {"bind", "checkpoint"}
    if any(value is not None for value in values):
        system, session, turn = values
        if session is None:
            raise ValueError("для происхождения команды нужен --session")
        return context(system or ("codex" if legacy else "agent-cli"), session, turn)
    if not hasattr(args, "turn"):
        return None
    values = [
        os.environ.get(key)
        for key in ("BLATERO_AGENT_SYSTEM", "BLATERO_AGENT_SESSION_ID", "BLATERO_AGENT_TURN_ID")
    ]
    if any(value is not None for value in values):
        if any(value is None for value in values):
            raise ValueError(
                "контекст процесса требует BLATERO_AGENT_SYSTEM, "
                "BLATERO_AGENT_SESSION_ID и BLATERO_AGENT_TURN_ID вместе"
            )
        return context(*values)
    if legacy:
        raise ValueError("нужен --session либо полный контекст процесса")
    return None


def event_source(provenance: dict | None, *, system="agent-cli", session_id="manual") -> dict:
    return (
        context(**provenance)
        if provenance is not None
        else {"system": system, "session_id": session_id}
    )


def record(conn, kind: str, identity: str, provenance: dict | None) -> dict | None:
    """Sidecar for existing non-event entities, in their own transaction."""
    if provenance is None:
        return None
    value = context(**provenance)
    conn.execute(
        "INSERT INTO settings(key,value) VALUES (?,?)",
        (f"command.provenance.{kind}.{identity}", json.dumps(value, ensure_ascii=False)),
    )
    return value


def read(conn, kind: str, identity: str) -> dict | None:
    row = conn.execute(
        "SELECT value FROM settings WHERE key=?", (f"command.provenance.{kind}.{identity}",)
    ).fetchone()
    return json.loads(row[0]) if row else None
