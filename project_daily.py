"""Daily workspace: explicit personal focus, human decisions and bounded retrieval."""
from __future__ import annotations

import datetime as dt
import json
import uuid

from project_materials import TZ, planning
from project_store import Conflict, digest, identifier, now, recall_fingerprint


def decision_fingerprint(task):
    return digest({key: task[key] for key in ("goal", "method", "rationale", "next_step")})


def revision(value):
    if type(value) is not int or value < 0:
        raise ValueError("Нужна прочитанная редакция")
    return value


def checked_task(store, conn, body):
    task = store.task(body.get("work_item_id"), conn)
    if task["revision"] != revision(body.get("revision")):
        raise Conflict("Карточка изменилась; перечитайте её", task)
    if task["merged_into"]:
        raise Conflict("Откройте актуальную карточку", task)
    return task


def owner(who):
    if who["role"] != "owner":
        raise PermissionError("Выбор фокуса и ответ на решение доступны пользователю")


def focus_value(conn):
    row = conn.execute("SELECT value FROM settings WHERE key='daily.focus'").fetchone()
    return json.loads(row[0]) if row else {"work_item_id": None, "revision": 0}


def mutate(store, path, body, who, *, provenance=None):
    from project_provenance import context, read, record
    provenance = context(**provenance) if provenance is not None else None
    with store.transaction() as conn:
        if path == "daily/focus":
            owner(who)
            current = focus_value(conn)
            if current["revision"] != revision(body.get("focus_revision")):
                raise Conflict("Фокус уже изменён в другом окне", current)
            task = checked_task(store, conn, body) if body.get("work_item_id") else None
            if task and task["status"] in {"done", "closed"}:
                raise ValueError("Выберите открытую незавершённую задачу")
            result = {"work_item_id": task["id"] if task else None, "revision": current["revision"] + 1}
            conn.execute("INSERT OR REPLACE INTO settings VALUES ('daily.focus',?)", (json.dumps(result),))
            return result
        task = checked_task(store, conn, body)
        if task["status"] == "closed" and path in {"daily/recall", "daily/request"}:
            raise Conflict("Задача закрыта; сначала явно восстановите её", task)
        if path == "daily/recall":
            owner(who)
            enabled = body.get("enabled")
            if type(enabled) is not bool:
                raise ValueError("Нужно явно включить или выключить закрепление")
            row = conn.execute("SELECT * FROM daily_tasks WHERE work_item_id=?", (task["id"],)).fetchone()
            current = dict(row) if row else {"revision": 0}
            if current["revision"] != revision(body.get("daily_revision")):
                raise Conflict("Настройка закрепления изменилась", current)
            conn.execute("INSERT OR REPLACE INTO daily_tasks VALUES (?,?,?)",
                         (task["id"], int(enabled), current["revision"] + 1))
            return {"enabled": enabled, "revision": current["revision"] + 1}
        if path == "daily/request":
            question, recommendation = body.get("question"), body.get("recommendation", "")
            if not isinstance(question, str) or not question.strip() or len(question) > 2000:
                raise ValueError("Запишите вопрос: 1–2000 символов")
            if not isinstance(recommendation, str) or len(recommendation) > 2000:
                raise ValueError("Рекомендация слишком длинная")
            existing = conn.execute("SELECT * FROM daily_decisions WHERE work_item_id=? AND state='open'", (task["id"],)).fetchone()
            if existing:
                if (existing["question"], existing["recommendation"], existing["context_hash"]) == (question.strip(), recommendation.strip(), decision_fingerprint(task)):
                    result = dict(existing)
                    saved = read(conn, "decision-request", result["id"])
                    if saved is not None:
                        result["provenance"] = saved
                    return result
                raise Conflict("У задачи уже есть открытый вопрос. Сначала нужен ответ пользователя", dict(existing))
            result = {"id": str(uuid.uuid4()), "work_item_id": task["id"], "question": question.strip(),
                      "recommendation": recommendation.strip(), "context_hash": decision_fingerprint(task),
                      "requested_at": now(), "actor_id": who["id"], "state": "open", "answer": "",
                      "resolved_at": None, "resolved_by": None, "revision": 1}
            conn.execute("INSERT INTO daily_decisions VALUES (:id,:work_item_id,:question,:recommendation,:context_hash,:requested_at,:actor_id,:state,:answer,:resolved_at,:resolved_by,:revision)", result)
            if provenance is not None:
                result["provenance"] = record(conn, "decision-request", result["id"], provenance)
            return result
        if path == "daily/resolve":
            owner(who)
            row = conn.execute("SELECT * FROM daily_decisions WHERE id=? AND work_item_id=?",
                               (identifier(body.get("id")), task["id"])).fetchone()
            if not row:
                raise ValueError("Вопрос не найден в этой задаче")
            result = dict(row)
            if result["revision"] != revision(body.get("decision_revision")) or result["state"] != "open":
                raise Conflict("На вопрос уже ответили; перечитайте историю", result)
            answer = body.get("answer")
            if not isinstance(answer, str) or not answer.strip() or len(answer) > 4000:
                raise ValueError("Запишите решение: 1–4000 символов")
            result.update(state="resolved", answer=answer.strip(), resolved_at=now(), resolved_by=who["id"], revision=result["revision"] + 1)
            conn.execute("UPDATE daily_decisions SET state=:state,answer=:answer,resolved_at=:resolved_at,resolved_by=:resolved_by,revision=:revision WHERE id=:id", result)
            # An agent that read the card before the human answer must re-read it.
            conn.execute("UPDATE tasks SET revision=revision+1,updated_at=?,updated_by=? WHERE id=?",
                         (result["resolved_at"], who["id"], task["id"]))
            return result
        raise ValueError("Неизвестное действие ежедневного экрана")


def task_context(store, task_id):
    from project_chat_answers import with_origins
    with store.connect() as conn:
        row = conn.execute("SELECT * FROM daily_tasks WHERE work_item_id=?", (task_id,)).fetchone()
        return {"recall": dict(row) if row else {"recall_enabled": 0, "revision": 0},
                "decisions": with_origins(conn, [dict(r) for r in conn.execute("SELECT * FROM daily_decisions WHERE work_item_id=? ORDER BY requested_at DESC", (task_id,))]),
                "focus": focus_value(conn)}


def snapshot(store, project=None, *, root=None, at=None, all_questions=False):
    from project_chat_answers import with_origins
    moment = at or dt.datetime.now(dt.timezone.utc)
    day = moment.astimezone(TZ).date()
    until = day + dt.timedelta(days=7)
    tasks = store.tasks()
    with store.connect() as conn:
        focus = focus_value(conn)
        pins = {r["work_item_id"]: dict(r) for r in conn.execute("SELECT * FROM daily_tasks WHERE recall_enabled=1")}
        requests = [dict(r) for r in conn.execute("SELECT * FROM daily_decisions WHERE state='open' ORDER BY requested_at,id")]
        answered = with_origins(conn, [dict(r) for r in conn.execute("SELECT * FROM daily_decisions WHERE state IN ('answered','resolved') ORDER BY resolved_at DESC,id")])
        general = {r[0] for r in conn.execute("SELECT work_item_id FROM task_triage WHERE kind='general'")}
        recalls = {}
        for row in conn.execute("SELECT r.*,b.content_hash FROM recalls r LEFT JOIN recall_basis b ON b.recall_id=r.id ORDER BY r.created_at DESC,r.id DESC"):
            recalls.setdefault(row["work_item_id"], dict(row))
    if project not in {None, "", "__unbound", "__general"}:
        project = identifier(project)
    scoped = [t for t in tasks if not project or t["project_id"] == project or
              (project == "__unbound" and not t["project_id"] and t["id"] not in general) or
              (project == "__general" and not t["project_id"] and t["id"] in general)]
    by_id = {t["id"]: t for t in tasks}
    visible = {t["id"]: t for t in scoped if t["status"] != "closed"}
    scope_ids = {t["id"] for t in scoped}
    answered = [{**r, 'task':by_id[r['work_item_id']]} for r in answered if r['work_item_id'] in scope_ids]
    focus_task = by_id.get(focus["work_item_id"])
    focus["task"] = focus_task
    focus["inactive"] = bool(focus["work_item_id"] and (not focus_task or focus_task["status"] in {"done", "closed"}))
    attention = [{**r, "task": visible[r["work_item_id"]],
                  "changed": r["context_hash"] != decision_fingerprint(visible[r["work_item_id"]])}
                 for r in requests if r["work_item_id"] in visible]
    reviews = [t for t in scoped if t["origin"] != "history" and t["status"] == "review"]
    reviews.sort(key=lambda t: (t["priority"] != "high", t["updated_at"], t["id"]))
    queue = []
    incomplete = 0
    for task in scoped:
        if task["status"] == "closed" or task["id"] not in pins:
            continue
        if not all(task[k].strip() for k in ("goal", "method", "rationale")):
            incomplete += 1
            continue
        trial = recalls.get(task["id"])
        changed = bool(trial and (trial["content_hash"] != recall_fingerprint(task) if trial["content_hash"] else trial["revision"] != task["revision"]))
        due = not trial or changed or dt.datetime.fromisoformat(trial["next_review"]) <= moment
        if due:
            # Only the title is rendered before the user retrieves the explanation.
            queue.append({"task": task, "reason": "Метод или суть изменились" if changed else "Первое возвращение" if not trial else "Пора вспомнить",
                          "next_review": trial["next_review"] if trial else None})
    queue.sort(key=lambda r: (r["task"]["id"] != focus["work_item_id"], r["next_review"] or "", r["task"]["priority"] != "high", r["task"]["id"]))
    items, conflicts, errors = {}, {}, []
    for anchor in (day, day + dt.timedelta(days=6)):
        plan = planning(store, anchor.isoformat(), project if project and not project.startswith("__") else None, root=root)
        errors.extend(plan["errors"])
        for item in plan["items"]:
            if project and item.get("task_id") not in scope_ids and (project.startswith("__") or item["kind"] != "calendar"):
                continue
            if not day.isoformat() <= item["date"] < until.isoformat():
                continue
            if item.get("end") and not item.get("all_day") and dt.datetime.fromisoformat(item["end"]) <= moment:
                continue
            items[(item["id"], item.get("start"), item["date"])] = item
        for conflict in plan["conflicts"]:
            conflicts[(conflict["left"], conflict["right"])] = conflict
    schedule = sorted(items.values(), key=lambda i: (i["date"], i.get("start") or "", i["title"]))
    kept = {i["id"] for i in schedule}
    return {"date": day.isoformat(), "timezone": "Europe/Moscow", "focus": focus,
            "attention": attention if all_questions else attention[:3], "attention_count": len(attention),
            "answered": answered, "answered_count": len(answered),
            "reviews": reviews[:3], "review_count": len(reviews),
            "recall": queue[:2], "recall_count": len(queue), "recall_incomplete": incomplete,
            "recall_pinned": len(set(pins) & set(visible)),
            "plan": schedule[:6], "plan_count": len(schedule),
            "conflicts": [c for c in conflicts.values() if c["left"] in kept and c["right"] in kept],
            "errors": sorted(set(errors))}
