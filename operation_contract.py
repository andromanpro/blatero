"""Public background-operation envelope; no web framework or persistence policy."""
from __future__ import annotations

import datetime as dt
import re

SCHEMA = "blatero.operation/v1"
STATES = frozenset({"queued", "running", "succeeded", "failed", "cancelled", "outcome_unknown"})


def build(*, identity: str, session: str, kind: str, state: str, stage: str,
          revision: int = 1, generation: int = 0, started_at: str = "", updated_at: str = "",
          error_code: str = "", result: dict | None = None) -> dict:
    if state not in STATES:
        raise ValueError("unknown operation state")
    code = error_code if re.fullmatch(r"[a-z][a-z0-9_]{0,79}", error_code) else ""
    try:
        start = dt.datetime.fromisoformat(started_at)
        end = dt.datetime.now().astimezone() if state in {"queued", "running"} else dt.datetime.fromisoformat(updated_at)
        elapsed = max(0, (end - start).total_seconds())
    except (ValueError, TypeError):
        elapsed = 0
    return {
        "schema": SCHEMA, "operation_id": str(identity), "session_id": str(session),
        "session_generation": int(generation or 0), "kind": kind,
        "revision": max(1, int(revision or 1)), "state": state, "stage": stage,
        "started_at": started_at, "updated_at": updated_at,
        "elapsed_seconds": round(elapsed, 1), "terminal": state not in {"queued", "running"},
        "error": {"code": code} if code else None, "result": result,
        # A timeout/disconnected UI cannot prove cancellation or zero billing.
        "automatic_retry": False,
        "retry_requires_confirmation": state in {"failed", "outcome_unknown"},
    }
