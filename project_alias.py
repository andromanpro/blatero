"""Explicit, reversible folding of an import duplicate. No dependency reparenting.

This narrow operation keeps all records on their original card. It is deliberately
not the proposed general graph-transfer merge. Unsupported graphs are rejected.
"""

import json
import uuid
from project_store import canonical, digest, make_event, now, Conflict, identifier

TABLES = (
    "sources",
    "knowledge",
    "knowledge_confirmations",
    "checks",
    "recalls",
    "events",
    "sessions",
    "imported_sessions",
    "daily_decisions",
    "daily_tasks",
    "task_triage",
    "material_links",
)
UNSUPPORTED = (
    "knowledge_confirmations",
    "checks",
    "recalls",
    "sessions",
    "daily_decisions",
    "daily_tasks",
    "material_links",
)


def snapshot(store, conn, a, b):
    value = {"schema": conn.execute("PRAGMA user_version").fetchone()[0], "cards": {}, "rows": {}}
    for tid in sorted((a, b)):
        value["cards"][tid] = store.task(tid, conn)
        value["rows"][tid] = {
            table: sorted(
                [
                    dict(r)
                    # Identifiers are the fixed TABLES tuple; values are bound.
                    for r in conn.execute(
                        "SELECT * FROM " + table + " WHERE work_item_id=?", (tid,)  # nosec B608
                    )
                ],
                key=canonical,
            )
            for table in TABLES
        }
        value["rows"][tid]["children"] = [
            dict(r)
            for r in conn.execute("SELECT * FROM tasks WHERE parent_id=? ORDER BY id", (tid,))
        ]
        value["rows"][tid]["aliases"] = [
            dict(r)
            for r in conn.execute("SELECT * FROM tasks WHERE merged_into=? ORDER BY id", (tid,))
        ]
    return value


def validate(value, source, target):
    if source == target:
        raise ValueError("Нужны разные карточки")
    a, b = value["cards"][source], value["cards"][target]
    if not a["project_id"] or a["project_id"] != b["project_id"]:
        raise ValueError("Нужен один установленный проект")
    if any(
        t["origin"] != "history" or t["merged_into"] or t["status"] in ("closed", "done")
        for t in (a, b)
    ):
        raise ValueError("Только несвязанные незавершённые исторические записи")
    if a["status"] != b["status"] or a["parent_id"] != b["parent_id"]:
        raise ValueError("Различаются статус или родитель")
    for rows in value["rows"].values():
        if any(rows[k] for k in UNSUPPORTED + ("children", "aliases")):
            raise ValueError("Граф требует общего механизма слияния; свёртка запрещена")


def plan(store, source, target):
    source, target = identifier(source), identifier(target)
    with store.connect() as c:
        c.execute("BEGIN")
        value = snapshot(store, c, source, target)
    validate(value, source, target)
    return {
        "id": str(uuid.uuid4()),
        "source": source,
        "target": target,
        "fingerprint": digest(value),
        "snapshot": value,
        "created_at": now(),
        "mode": "preserve-original-records",
    }


def _event(store, c, tid, who, session):
    t = store.task(tid, c)
    # Native events preserve the fields and bump both revisions; receipt records intent.
    result = store.apply(
        make_event(
            t,
            who,
            "task.updated",
            {"patch": {"next_step": t["next_step"]}},
            system="codex",
            session_id=session,
        ),
        who,
        conn=c,
    )
    if result["state"] != "applied":
        raise Conflict(result.get("error", "Не применено"))


def apply(store, proposal, who, *, authorization, session):
    if not authorization.strip():
        raise PermissionError("Нужно явное разрешение владельца")
    a, b = proposal["source"], proposal["target"]
    key = "import-fold:" + proposal["id"]
    with store.transaction() as c:
        old = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        if old:
            receipt = json.loads(old[0])
            if receipt["plan_hash"] != digest(proposal):
                raise Conflict("Ключ использован с другим планом")
            return {**receipt, "replayed": True}
        current = snapshot(store, c, a, b)
        if digest(current) != proposal["fingerprint"] or digest(current) != digest(
            proposal["snapshot"]
        ):
            raise Conflict("План устарел; перечитайте обе карточки и связи")
        validate(current, a, b)
        for tid in (a, b):
            _event(store, c, tid, who, session)
        c.execute("UPDATE tasks SET merged_into=? WHERE id=?", (b, a))
        receipt = {
            "id": proposal["id"],
            "source": a,
            "target": b,
            "plan_hash": digest(proposal),
            "authorization": authorization,
            "actor": who["id"],
            "session": session,
            "at": now(),
            "before": proposal["snapshot"],
            "after_hash": digest(snapshot(store, c, a, b)),
            "state": "applied",
            "mode": "preserve-original-records",
        }
        c.execute("INSERT INTO settings(key,value) VALUES (?,?)", (key, canonical(receipt)))
    return receipt


def undo(store, identity, who, *, session):
    key = "import-fold:" + str(uuid.UUID(identity))
    with store.transaction() as c:
        row = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        if not row:
            raise ValueError("Квитанция не найдена")
        receipt = json.loads(row[0])
        a, b = receipt["source"], receipt["target"]
        if receipt["state"] == "undone":
            return {**receipt, "replayed": True}
        if digest(snapshot(store, c, a, b)) != receipt["after_hash"]:
            raise Conflict("После слияния есть изменения; автоматическая отмена запрещена")
        c.execute("UPDATE tasks SET merged_into=NULL WHERE id=?", (a,))
        for tid in (a, b):
            _event(store, c, tid, who, session)
        receipt.update(state="undone", undone_at=now(), undone_by=who["id"])
        c.execute("UPDATE settings SET value=? WHERE key=?", (canonical(receipt), key))
    return receipt


if __name__ == "__main__":
    import argparse
    import sys
    from project_store import Store

    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        description="Отмена свёртки импортной копии без перезаписи новых изменений"
    )
    parser.add_argument("command", choices=["undo"])
    parser.add_argument("receipt")
    parser.add_argument("--session", required=True)
    args = parser.parse_args()
    store = Store(initialize=False)
    who, _ = store.local_agent()
    result = undo(store, args.receipt, who, session=args.session)
    print(
        json.dumps(
            {k: result[k] for k in ("id", "source", "target", "state")},
            ensure_ascii=False,
            indent=2,
        )
    )
