"""Project visibility lifecycle, independent of task acceptance and status."""

import json
import uuid
import os
from pathlib import Path
from project_store import Conflict, identifier, now, canonical

PREFIX = "project-lifecycle:"


def metadata(conn, project):
    row = conn.execute("SELECT value FROM settings WHERE key=?", ("project-revision:"+project["id"],)).fetchone()
    return {**project, "revision": int(json.loads(row[0])) if row else 1}


def edit(store, body, who, *, preview=False):
    """Edit a passport, never move files or rewrite past meetings/memory."""
    if who.get("role") != "owner":
        raise PermissionError("Изменение проекта доступно владельцу")
    identity = identifier(body.get("project_id"))
    name, workspace, description = (body.get(k, "") for k in ("name", "workspace", "description"))
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 160:
        raise ValueError("название проекта должно содержать 1–160 символов")
    if not isinstance(workspace, str) or not isinstance(description, str) or len(description) > 8000:
        raise ValueError("неверное описание проекта")
    selected = str(Path(workspace).expanduser().resolve()) if workspace.strip() else ""
    with (store.connect() if preview else store.transaction()) as conn:
        row = conn.execute("SELECT * FROM projects WHERE id=?", (identity,)).fetchone()
        if not row:
            raise ValueError("проект не найден")
        before = metadata(conn, dict(row))
        if type(body.get("revision")) is not int or body["revision"] != before["revision"]:
            raise Conflict("Проект уже изменён; обновите паспорт", before)
        if selected != before["workspace"] and selected and not Path(selected).is_dir():
            raise ValueError("рабочая папка не найдена")
        for other in conn.execute("SELECT * FROM projects WHERE id<>? AND workspace<>''", (identity,)):
            if selected and os.path.normcase(selected) == os.path.normcase(other["workspace"]):
                raise Conflict("Эта папка уже связана с другим проектом", dict(other))
        after = {**before, "name": name.strip(), "workspace": selected, "description": description.strip()}
        from project_store import digest
        token = digest(after)
        changed = [k for k in ("name", "workspace", "description") if before[k] != after[k]]
        if preview:
            return {"project": after, "before": before, "changed_fields": changed,
                    "tasks": conn.execute("SELECT COUNT(*) FROM tasks WHERE project_id=?", (identity,)).fetchone()[0],
                    "documents": conn.execute("SELECT COUNT(*) FROM project_documents WHERE project_id=?", (identity,)).fetchone()[0],
                    "files_moved": False, "confirmation": token}
        if body.get("confirmation") != token:
            raise ValueError("Сначала проверьте изменения проекта")
        if not changed:
            return before
        after["revision"] += 1
        conn.execute("UPDATE projects SET name=?,workspace=?,description=? WHERE id=?",
                     (after["name"], selected, after["description"], identity))
        conn.execute("INSERT INTO settings(key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                     ("project-revision:"+identity, canonical(after["revision"])))
        conn.execute("INSERT INTO settings(key,value) VALUES (?,?)", ("project-edit-log:"+str(uuid.uuid4()),
                     canonical({"project_id":identity,"at":now(),"by":who["id"],"before":before,"after":after})))
        return after


def values(conn):
    return {
        r["key"][len(PREFIX) :]: json.loads(r["value"])
        for r in conn.execute("SELECT key,value FROM settings WHERE key LIKE ?", (PREFIX + "%",))
    }


def decorate(project, states):
    return {
        **project,
        "lifecycle": states.get(
            project["id"], {"revision": 0, "closed": False, "closed_at": None, "reason": ""}
        ),
    }


def change(store, body, who):
    if who.get("role") != "owner":
        raise PermissionError("Закрытие и восстановление проектов доступны владельцу")
    project = identifier(body.get("project_id"))
    if type(body.get("revision")) is not int or type(body.get("closed")) is not bool:
        raise ValueError("Нужны прочитанная редакция проекта и признак закрытия")
    reason = body.get("reason", "")
    if not isinstance(reason, str) or len(reason) > 2000:
        raise ValueError("Причина должна быть строкой до 2000 знаков")
    with store.transaction() as c:
        row = c.execute("SELECT * FROM projects WHERE id=?", (project,)).fetchone()
        if not row:
            raise ValueError("Проект не найден")
        old = decorate(dict(row), values(c))["lifecycle"]
        if old["revision"] != body["revision"]:
            raise Conflict("Проект уже изменён; обновите список", decorate(dict(row), values(c)))
        if old["closed"] == body["closed"]:
            return decorate(dict(row), {project: old})
        stamp = now()
        value = {
            "revision": old["revision"] + 1,
            "closed": body["closed"],
            "closed_at": stamp if body["closed"] else None,
            "reason": (reason.strip() or "Закрыт пользователем из списка проектов")
            if body["closed"]
            else "",
            "updated_at": stamp,
            "updated_by": who["id"],
        }
        c.execute(
            "INSERT INTO settings(key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (PREFIX + project, canonical(value)),
        )
        audit = {
            "project_id": project,
            "at": stamp,
            "by": who["id"],
            "before": old,
            "after": value,
            "event_type": "project.closed" if body["closed"] else "project.reopened",
        }
        c.execute(
            "INSERT INTO settings(key,value) VALUES (?,?)",
            ("project-lifecycle-log:" + str(uuid.uuid4()), canonical(audit)),
        )
        return decorate(dict(row), {project: value})
