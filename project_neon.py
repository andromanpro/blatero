"""Read-only Neon Legion ledger adapter. No network or ledger mutations.

Attribute events only after an explicit session binding, up to its next switch.
Reuse Neon's canonical deduplication helpers; do not infer human time or savings.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import os
from pathlib import Path

import app_paths
import project_connections
from project_store import Store


def timestamp(value):
    try:
        result = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return result.timestamp() if result.tzinfo else None
    except (ValueError, OverflowError, OSError):
        return None


def efficiency(store: Store, project_id: str | None = None, neon_root: Path | None = None) -> dict:
    connected = neon_root is not None or project_connections.enabled(store, "neon")
    root = neon_root or Path(os.environ.get("BLATERO_NEON_ROOT", str(app_paths.APP_ROOT.parent / "neon-legion")))
    tasks = store.tasks(project_id)
    metrics = {t["id"]: {"id": t["id"], "title": t["title"], "status": t["status"],
                         "linked": set(), "covered": set(), "cost": 0.0, "priced": 0, "unpriced": 0}
               for t in tasks}
    bindings = {}
    with store.connect() as conn:
        for row in conn.execute("SELECT event_json FROM events WHERE state='applied' "
                                "AND event_type IN ('session.started','session.checkpoint') ORDER BY received_at"):
            event = json.loads(row[0])
            system, sid = event["source"]["system"], event["source"]["session_id"]
            if system not in {"codex", "claude-code"} or not event["work_item_id"]:
                continue
            key = (system, sid)
            at = timestamp(event["emitted_at"])
            if at is not None:
                bindings.setdefault(key, []).append((at, event["work_item_id"]))
            if event["work_item_id"] in metrics:
                metrics[event["work_item_id"]]["linked"].add(key)
    for items in bindings.values():
        items.sort()
    errors = []
    if connected and (root / "tracker").is_dir() and bindings:
        seen = set()
        for system, filename, provider in (("codex", "codex-events.jsonl", "openai"),
                                            ("claude-code", "claude-events.jsonl", "anthropic")):
            file = root / "tracker" / filename
            if not file.is_file():
                errors.append(filename + ": журнал не найден")
                continue
            try:
                with file.open(encoding="utf-8-sig") as stream:
                    for line in stream:
                        try:
                            event = json.loads(line)
                            if not isinstance(event, dict):
                                raise ValueError("ledger event must be an object")
                            key = (system, event.get("session_id"))
                            ranges = bindings.get(key)
                            if not ranges:
                                continue
                            stamp = timestamp(event.get("ts"))
                            candidates = [b for b in ranges if stamp is not None and b[0] <= stamp]
                            if not candidates or candidates[-1][1] not in metrics:
                                continue
                            identity = ledger_identity(event, provider)
                            if identity in seen:
                                continue
                            seen.add(identity)
                            metric = metrics[candidates[-1][1]]
                            metric["covered"].add(key)
                            cost = event.get("cost_estimate_usd")
                            if isinstance(cost, (int, float)) and not isinstance(cost, bool) and math.isfinite(cost):
                                metric["cost"] += cost  # Negative corrections remain negative.
                                metric["priced"] += 1
                            else:
                                metric["unpriced"] += 1
                        except (ValueError, TypeError, KeyError):
                            errors.append(filename + ": некорректное событие")
            except (OSError, UnicodeError) as exc:
                errors.append(str(exc))
    elif connected and not (root / "tracker").is_dir():
        errors.append("Neon Legion не найден; задайте BLATERO_NEON_ROOT")
    rows = [{k: m[k] for k in ("id", "title", "status")} | {
        "linked_sessions": len(m["linked"]), "covered_sessions": len(m["covered"]),
        "api_equivalent_usd": round(m["cost"], 6) if m["priced"] else None,
        "unpriced_events": m["unpriced"]} for m in metrics.values()]
    linked = set().union(*(m["linked"] for m in metrics.values())) if metrics else set()
    covered = set().union(*(m["covered"] for m in metrics.values())) if metrics else set()
    return {"tasks": rows, "accepted_tasks": sum(t["status"] == "done" or
                (t["status"] == "closed" and t.get("closed_from_status") == "done") for t in tasks),
            "linked_sessions": len(linked), "covered_sessions": len(covered),
            "api_equivalent_usd": round(sum(m["cost"] for m in metrics.values()), 6)
                if any(m["priced"] for m in metrics.values()) else None,
            "unpriced_events": sum(m["unpriced"] for m in metrics.values()),
            "cost_note": "Оценка стоимости API по журналу, не сумма оплаты подписки. Неполное покрытие возможно.",
            "message": "Связь с Neon Legion по идентификаторам сессий. Учитываются события после привязки к задаче; "
                       "при смене задачи затраты разделяются по времени. Для экономии времени нужны отдельные оценки "
                       "работы без ИИ и участия человека." if connected else
                       "Neon Legion отключён. Подключить его можно в настройках интеграций.",
            "enabled": connected, "errors": sorted(set(errors))}


def ledger_identity(event, default_provider):
    """JSONL v1 identity; no import or execution of code from a sibling app.

    Mirrors the documented event_id/tracking_run_id/legacy fallback contract.
    Corrections with distinct event IDs remain distinct monetary events.
    """
    identity = event.get("event_id") or event.get("tracking_run_id")
    if isinstance(identity, str) and identity:
        return "event_id:" + identity
    provider = str(event.get("provider") or "").lower()
    aliases = {"hermes": "hermes", "dsh": "dsh", "openai": "openai", "codex": "openai",
               "openai_codex": "openai", "openrouter": "openrouter", "openclaw": "openrouter",
               "openrouter_openclaw": "openrouter", "opencode": "opencode",
               "opencode_openrouter": "opencode", "openrouter_opencode": "opencode"}
    key = [aliases.get(provider, default_provider)] + [event.get(k) for k in ("session_id", "message_uuid", "ts", "model")]
    key += [event.get(k, 0) for k in ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_tokens", "total_tokens")]
    key.append(event.get("exit_code"))
    return "legacy:" + json.dumps(key, ensure_ascii=False, separators=(",", ":"))
