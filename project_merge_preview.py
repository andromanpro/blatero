"""Read-only candidate discovery and comparison. Deliberately has no merge operation."""

from __future__ import annotations

import hashlib
import itertools
import json
import re

from project_store import identifier, now

FIELDS = (
    "title",
    "goal",
    "method",
    "rationale",
    "next_step",
    "status",
    "project_id",
    "parent_id",
    "priority",
    "due",
    "planned_start",
    "estimate_minutes",
)


def pair_id(a, b):
    return hashlib.sha256((":".join(sorted((a, b)))).encode()).hexdigest()[:24]


def reviewed(store):
    path = store.root / "merge-preview-reviews.json"
    if not path.exists():
        return {"pairs": []}
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("Слишком большой файл оснований просмотра")
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("version") != 1 or not isinstance(value.get("pairs"), list):
        raise ValueError("Неверный формат оснований просмотра")
    return value


def card(task):
    fields = {key: task.get(key) for key in FIELDS}
    truncated = []
    for key in FIELDS:
        if isinstance(fields[key], str) and len(fields[key]) > 4000:
            fields[key] = fields[key][:4000]
            truncated.append(key)
    return {
        "id": task["id"],
        "revision": task["revision"],
        "merged_into": task["merged_into"],
        **fields,
        "truncated_fields": truncated,
    }


def candidates(store, project=None):
    """Metadata-only GET: no journal extraction, writes or model calls."""
    document = reviewed(store)
    with store.connect() as conn:
        conn.execute("PRAGMA query_only=ON")
        conn.execute("BEGIN")
        tasks = {r["id"]: dict(r) for r in conn.execute("SELECT * FROM tasks")}
        general = {
            r[0] for r in conn.execute("SELECT work_item_id FROM task_triage WHERE kind='general'")
        }

    def visible(task):
        return (
            not project
            or (project == "__unbound" and not task["project_id"] and task["id"] not in general)
            or (project == "__general" and not task["project_id"] and task["id"] in general)
            or task["project_id"] == project
        )

    pairs = {}
    for item in document.get("pairs", []):
        a, b = tasks.get(item["a"]), tasks.get(item["b"])
        if not a or not b or a["merged_into"] or b["merged_into"]:
            continue
        if not (visible(a) or visible(b)):
            continue
        baseline = item.get("current_revisions", {})
        pairs[pair_id(a["id"], b["id"])] = {
            **item,
            "id": pair_id(a["id"], b["id"]),
            "a_card": card(a),
            "b_card": card(b),
            "reviewed": True,
            "changed_since_snapshot": any(baseline.get(t["id"]) != t["revision"] for t in (a, b)),
        }
    # Broad metadata scan; a matching title is only a lead, never a duplicate verdict.
    groups = {}
    for task in tasks.values():
        if task["merged_into"] or task["status"] == "closed":
            continue
        title = re.sub(r"\s+", " ", task["title"]).strip().casefold()
        if len(title) >= 4:
            groups.setdefault(title, []).append(task)
    unreviewed_count = 0
    for group in groups.values():
        for a, b in itertools.combinations(group, 2):
            if not (visible(a) or visible(b)):
                continue
            key = pair_id(a["id"], b["id"])
            if key in pairs:
                continue
            unreviewed_count += 1
            if unreviewed_count > 200:
                continue
            pairs[key] = {
                "id": key,
                "a": a["id"],
                "b": b["id"],
                "a_card": card(a),
                "b_card": card(b),
                "relation": "unreviewed",
                "reviewed": False,
                "rationale": "Совпадает нормализованное название. Содержание и результат не сопоставлены; это только повод для разбора.",
                "unknowns": ["Нужно прочитать первичные сессии и сравнить фактический результат."],
                "evidence": [],
                "changed_since_snapshot": False,
            }
    order = {
        "duplicate": 0,
        "uncertain": 1,
        "unreviewed": 2,
        "continuation": 3,
        "related": 4,
        "unrelated": 5,
    }
    rows = sorted(
        pairs.values(), key=lambda r: (order.get(r["relation"], 9), r.get("group_id", ""), r["id"])
    )
    counts = {key: sum(x["relation"] == key for x in rows) for key in order}
    return {
        "read_only": True,
        "generated_at": now(),
        "reviewed_at": document.get("reviewed_at"),
        "source_checked_at": document.get("source_checked_at"),
        "counts": counts,
        "pairs": rows,
        "total": len(rows),
        "unreviewed_total": unreviewed_count,
        "truncated": unreviewed_count > 200,
        "scope": "Ранее разобранные пары и совпадения названий текущих открытых карточек. Семантический аудит всей доски не выполнялся.",
    }


def compare(store, a, b):
    a, b = identifier(a), identifier(b)
    if a == b:
        raise ValueError("Выберите две разные карточки")
    related = {}
    graph = {}
    with store.connect() as conn:
        conn.execute("PRAGMA query_only=ON")
        conn.execute("BEGIN")
        left, right = store.task(a, conn), store.task(b, conn)
        for tid in (a, b):
            graph[tid] = {
                table: [
                    dict(x)
                    # Table comes only from the literal list below; values are bound.
                    for x in conn.execute(
                        "SELECT * FROM " + table + " WHERE work_item_id=?", (tid,)  # nosec B608
                    )
                ]
                for table in [
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
                ]
            }
            graph[tid]["related_history"] = [
                dict(x) for x in conn.execute("SELECT * FROM tasks WHERE merged_into=?", (tid,))
            ]
            graph[tid]["children"] = [
                dict(x) for x in conn.execute("SELECT * FROM tasks WHERE parent_id=?", (tid,))
            ]
            graph[tid]["recall_basis"] = [
                dict(x)
                for x in conn.execute(
                    "SELECT b.* FROM recall_basis b JOIN recalls r ON r.id=b.recall_id WHERE r.work_item_id=?",
                    (tid,),
                )
            ]
            related[tid] = {
                "children": [
                    dict(x)
                    for x in conn.execute(
                        "SELECT id,title,revision,status FROM tasks WHERE parent_id=?", (tid,)
                    )
                ],
                "materials": [
                    dict(x)
                    for x in conn.execute(
                        "SELECT * FROM material_links WHERE work_item_id=?", (tid,)
                    )
                ],
            }
    conflicts = [
        {"field": field, "a": card(left)[field], "b": card(right)[field]}
        for field in FIELDS
        if left.get(field) != right.get(field)
    ]
    blockers = []
    if not left["project_id"] or not right["project_id"]:
        blockers.append("Проект не установлен хотя бы у одной карточки.")
    elif left["project_id"] != right["project_id"]:
        blockers.append("Карточки принадлежат разным проектам; автоматически объединять нельзя.")
    if left["merged_into"] or right["merged_into"]:
        blockers.append("Одна из карточек уже связана с другой основной записью.")
    if any(t["status"] == "closed" for t in (left, right)):
        blockers.append("Есть закрытая карточка; её состояние нельзя переносить автоматически.")
    if left["status"] != right["status"]:
        blockers.append("Статусы различаются; приёмка и закрытие не наследуются автоматически.")
    if left["parent_id"] == right["id"] or right["parent_id"] == left["id"]:
        blockers.append("Есть связь родитель–подзадача; это не дубликаты по умолчанию.")

    def inventory(tid):
        return {key: len(value) for key, value in graph[tid].items()}

    source_left = {(s["kind"], s["locator"], s["snapshot_sha256"]) for s in graph[a]["sources"]}
    source_right = {(s["kind"], s["locator"], s["snapshot_sha256"]) for s in graph[b]["sources"]}
    session_left = {
        (s["system"], s["session_id"]) for s in graph[a]["imported_sessions"] + graph[a]["sessions"]
    }
    session_right = {
        (s["system"], s["session_id"]) for s in graph[b]["imported_sessions"] + graph[b]["sessions"]
    }
    fingerprint = hashlib.sha256(
        json.dumps(
            {"left": left, "right": right, "graph": graph}, sort_keys=True, ensure_ascii=False
        ).encode()
    ).hexdigest()
    return {
        "read_only": True,
        "can_merge": False,
        "fingerprint": fingerprint,
        "a": card(left),
        "b": card(right),
        "conflicts": conflicts,
        "blockers": blockers,
        "inventory_a": inventory(a),
        "inventory_b": inventory(b),
        "related": related,
        "unique_sources_a": len(source_left - source_right),
        "unique_sources_b": len(source_right - source_left),
        "common_sources": len(source_left & source_right),
        "common_sessions": len(session_left & session_right),
        "sources_a": graph[a]["sources"],
        "sources_b": graph[b]["sources"],
        "note": "Это снимок для сравнения, не разрешение и не план применения слияния. Совпадение источника не доказывает равенство целей или результатов; разные ссылки не доказывают разное содержание. Количества зависимостей прочитаны полностью; длинные текстовые поля показаны фрагментами.",
    }
