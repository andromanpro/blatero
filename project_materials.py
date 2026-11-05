"""Local meeting/editorial projections and explicit links to versioned board cards."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid
from urllib.parse import urlencode, urlsplit

import app_paths
import project_connections
from project_session_catalog import redact
from project_store import Conflict, Store, digest, identifier, make_event, now
from session_utils import direct_child, schedule_slug

TZ = dt.timezone(dt.timedelta(hours=3))


def text(value, limit=2000):
    return redact(str(value or ""))[:limit]


def read_json(path, fallback):
    if not path.exists():
        return fallback
    if path.is_symlink() or path.stat().st_size > 8 * 1024 * 1024:
        raise ValueError("источник слишком большой или является ссылкой")
    return json.loads(path.read_text(encoding="utf-8-sig"))


def valid_date(value):
    try:
        return dt.date.fromisoformat(value).isoformat() if value else None
    except (TypeError, ValueError):
        return None


def meeting_materials(root):
    root = Path(root).resolve()
    sessions = root / "sessions"
    result = {}
    errors = []
    for folder in sorted(sessions.iterdir()) if sessions.is_dir() else []:
        if not folder.is_dir() or folder.is_symlink():
            continue
        try:
            folder = direct_child(sessions, folder.name, must_exist=True)
            meta = read_json(folder / "meta.json", {})
            if not isinstance(meta, dict):
                raise ValueError("метаданные должны быть объектом")
            report = folder / "report.md"
            summary = ""
            revision = digest(meta)
            if report.is_file() and not report.is_symlink() and report.stat().st_size <= 1024 * 1024:
                report_bytes = report.read_bytes()
                summary = text(report_bytes.decode("utf-8-sig"), 4000)
                revision = hashlib.sha256(report_bytes).hexdigest()
            item = {"id": "meeting:" + folder.name, "provider": "blatero", "kind": "meeting",
                    "title": text(meta.get("name") or meta.get("title") or folder.name, 240),
                    "summary": summary, "locator": str(report if report.is_file() else folder / "meta.json"),
                    "source_revision": revision,
                    "workspace": str(meta.get("workspace_path") or meta.get("workspace") or meta.get("project_path") or ""),
                    "project_name": text(meta.get("project_name"), 160), "client_name": text(meta.get("client_name"), 160),
                    "source_status": "report" if summary else "recorded", "date": valid_date(meta.get("date")),
                    "session": folder.name, "role": text(meta.get("meeting_type") or meta.get("role"), 160)}
            result[item["id"]] = item
        except (OSError, ValueError, TypeError) as exc:
            errors.append(f"Встреча {folder.name}: {type(exc).__name__}")
    schedule = read_json(root / "schedule.json", [])
    if not isinstance(schedule, list):
        raise ValueError("расписание должно быть массивом")
    for meeting in schedule:
        try:
            slug = schedule_slug(meeting)
            identity = "meeting:" + slug
            begin = dt.datetime.fromisoformat(f"{meeting['date']}T{meeting['time']}").replace(tzinfo=TZ)
            duration = int(meeting.get("duration") or 30)
            if not 1 <= duration <= 1440:
                raise ValueError("длительность вне диапазона")
            original = result.get(identity, {})
            result[identity] = {"id": identity, "provider": "blatero", "kind": "meeting",
                                "title": text(meeting.get("name") or meeting.get("role") or "Встреча", 240),
                                "summary": text(meeting.get("goal") or meeting.get("brief") or ""),
                                "source_status": "scheduled", "locator": str(root / "schedule.json") + "#" + slug,
                                **original, "start": begin.isoformat(), "date": begin.date().isoformat(),
                                "duration": duration, "end": (begin + dt.timedelta(minutes=duration)).isoformat()}
        except (ValueError, KeyError, TypeError):
            errors.append("Пропущена встреча с неверной датой или длительностью")
    memory_path = root / ".meeting-memory" / "memory.json"
    memory = read_json(memory_path, {})
    for scope in ("projects", "clients"):
        profiles = memory.get(scope, {})
        if not isinstance(profiles, dict):
            continue
        for key, profile in profiles.items():
            for entry in profile.get("entries", []) if isinstance(profile, dict) else []:
                if not isinstance(entry, dict) or entry.get("kind") not in {"commitment", "open_question"} or entry.get("verified") is not True:
                    continue
                if not entry.get("id"):
                    continue
                identity = "commitment:" + scope + ":" + key + ":" + str(entry["id"])
                result[identity] = {"id": identity, "provider": "blatero", "kind": "commitment",
                                    "title": text(entry.get("text"), 240), "summary": text(entry.get("text"), 1200) + "\n\n" + text(entry.get("evidence"), 800),
                                    "source_revision": digest(entry),
                                    "owner": text(entry.get("owner"), 160), "date": valid_date(entry.get("due")),
                                    "source_status": text(entry.get("status") or "active", 80),
                                    "locator": str(memory_path) + "#" + scope + "/" + key + "/" + str(entry["id"]),
                                    "session": text(entry.get("source_session"), 200),
                                    "scope_label": text(profile.get("label"), 160)}
    return list(result.values()), errors


def granka_materials():
    root = Path(os.getenv("BLATERO_GRANKA_ROOT", str(app_paths.APP_ROOT.parent / "granka"))).resolve()
    bridge = root / "tools" / "blatero_export.py"
    if not bridge.is_file():
        return [], ["Гранка не подключена: задайте BLATERO_GRANKA_ROOT"]
    configured = os.getenv("BLATERO_GRANKA_PYTHON")
    python = ([configured] if configured else ["py", "-3.14"]
              if os.name == "nt" and shutil.which("py") else [sys.executable])
    run = subprocess.run([*python, str(bridge)], cwd=root, capture_output=True, timeout=30,
                         encoding="utf-8", errors="replace", creationflags=0x08000000 if os.name == "nt" else 0)
    if run.returncode:
        raise ValueError("Локальный экспорт Гранки завершился ошибкой; проверьте её Python и зависимости")
    if len(run.stdout) > 8 * 1024 * 1024:
        raise ValueError("каталог Гранки превышает 8 МБ")
    exported = json.loads(run.stdout)
    if not isinstance(exported, dict) or exported.get("schema_version") != 1 or not isinstance(exported.get("entries"), list):
        raise ValueError("неизвестный формат каталога Гранки")
    result = []
    port = exported.get("port", 8901)
    if type(port) is not int or not 1024 <= port <= 65535:
        raise ValueError("неверный порт Гранки")
    for entry in exported["entries"]:
        if not isinstance(entry, dict):
            raise ValueError("запись каталога Гранки должна быть объектом")
        destination = ""
        if entry.get("root") and entry.get("file"):
            if entry.get("has_granka") or not entry.get("source_rel"):
                destination = urlencode({"root": entry["root"], "f": entry["file"]})
            else:
                destination = urlencode({"root": entry["root"], "source_file": entry["source_rel"]})
        publication_url = entry.get("url") or ""
        if not isinstance(publication_url, str) or len(publication_url) > 2000:
            publication_url = ""
        try:
            parts = urlsplit(publication_url)
            if (parts.scheme not in {"http", "https"} or not parts.hostname or parts.username or parts.password
                    or any(ord(c) < 32 for c in publication_url)):
                publication_url = ""
        except (TypeError, ValueError):
            publication_url = ""
        result.append({"id": "article:" + str(entry["id"]), "provider": "granka", "kind": "article",
                       "title": text(entry.get("title"), 240), "summary": text(entry.get("notes")),
                       "locator": text(entry.get("locator"), 2000), "date": valid_date(entry.get("date")),
                       "source_status": text(entry.get("status"), 80), "excluded": bool(entry.get("excluded")),
                       "source_revision": text(entry.get("source_revision"), 80),
                       "readiness": entry.get("readiness", {}), "source_error": text(entry.get("source_error"), 400),
                       "open_url": f"http://127.0.0.1:{port}/?{destination}" if destination else "",
                       "publication_url": publication_url})
    return result, []


def meeting_folder(root, session):
    if not isinstance(session, str) or not session or len(session) > 200:
        raise ValueError("выберите встречу")
    return direct_child(Path(root) / "sessions", session, must_exist=True)


def meeting_url(item, root):
    session = item.get("session")
    if session:
        try:
            meeting_folder(root, session)
            return "/?" + urlencode({"session": session})
        except (OSError, ValueError):
            pass
    return "/?" + urlencode({"panel": "calendar", "date": item.get("date") or ""})


def meeting_context(store, session, *, root=None):
    root = Path(root) if root is not None else app_paths.DATA_ROOT
    folder = meeting_folder(root, session)
    meta = read_json(folder / "meta.json", {})
    if not isinstance(meta, dict):
        raise ValueError("неверные метаданные встречи")
    catalog = Materials(store, root=root).catalog()
    materials = [item for item in catalog["entries"] if item.get("session") == session]
    linked_ids = {link["work_item_id"] for item in materials for link in item["links"]}
    tasks = [task for task in store.tasks() if task["id"] in linked_ids]
    project_ids = {task["project_id"] for task in tasks if task["project_id"]}
    projects = store.projects()
    project = next((p for p in projects if p["id"] in project_ids), None) if len(project_ids) == 1 else None
    basis = "linked" if project else ""
    if not project and not project_ids:
        workspace = meta.get("workspace_path") or meta.get("workspace") or ""
        project = store.project_for_workspace(workspace) if workspace else None
        if project:
            basis = "workspace"
        else:
            matches = [p for p in projects if p["name"].casefold() == str(meta.get("project_name") or "").casefold()]
            if len(matches) == 1:
                project, basis = matches[0], "name"
    return {"session": session, "title": text(meta.get("name") or meta.get("title") or session, 240),
            "project": project, "project_basis": basis, "projects": projects,
            "tasks": tasks, "related_tasks": [t for t in store.tasks(project["id"]) if t["id"] not in linked_ids] if project else [],
            "material": next((item for item in materials if item["kind"] == "meeting"), None),
            "materials": materials, "open_url": "/?" + urlencode({"session": session})}


class Materials:
    def __init__(self, store: Store, *, root=None, granka_reader=None):
        self.store = store
        self.root = Path(root) if root is not None else app_paths.DATA_ROOT
        # An injected reader is an explicit integration-test capability.
        self.granka_opt_in = granka_reader is not None
        self.granka_reader = granka_reader or granka_materials

    def granka_enabled(self):
        return self.granka_opt_in or project_connections.enabled(self.store, "granka")

    def refresh(self):
        errors = []
        for provider, reader in (("blatero", lambda: meeting_materials(self.root)), ("granka", self.granka_reader)):
            if provider == "granka" and not self.granka_enabled():
                continue
            try:
                entries, warnings = reader()
                errors.extend(warnings)
                # A disconnected source must not mark its last good snapshot as removed.
                if warnings and not entries:
                    continue
                with self.store.transaction() as conn:
                    conn.execute("UPDATE materials SET available=0 WHERE provider=?", (provider,))
                    for item in entries:
                        conn.execute("INSERT INTO materials VALUES (?,?,?,?,?,1) ON CONFLICT(id) DO UPDATE SET "
                                     "data_json=excluded.data_json,snapshot_sha256=excluded.snapshot_sha256,"
                                     "observed_at=excluded.observed_at,available=1",
                                     (item["id"], provider, json.dumps(item, ensure_ascii=False), digest(item), now()))
            except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
                errors.append(f"{provider}: каталог не обновлен; сохранен предыдущий снимок")
        with self.store.transaction() as conn:
            conn.execute("INSERT OR REPLACE INTO settings VALUES ('materials-sync',?)",
                         (json.dumps({"observed_at": now(), "errors": errors}, ensure_ascii=False),))
        return self.catalog()

    def catalog(self):
        granka_enabled = self.granka_enabled()
        with self.store.connect() as conn:
            links = [dict(r) for r in conn.execute("SELECT l.*,s.snapshot_sha256 AS linked_sha FROM material_links l "
                                                  "JOIN sources s ON s.id=l.source_id")]
            entries = []
            for row in conn.execute("SELECT * FROM materials ORDER BY observed_at DESC,id"):
                item = json.loads(row["data_json"])
                item_links = [dict(r, changed=r["linked_sha"] != row["snapshot_sha256"]) for r in links if r["material_id"] == row["id"]]
                if item.get("kind") == "meeting":
                    item["open_url"] = meeting_url(item, self.root)
                if row["provider"] == "granka" and not granka_enabled:
                    # Retain prior snapshots and links, but do not offer a launch.
                    item["open_url"] = ""
                    item["connection_disabled"] = True
                entries.append({**item, "available": bool(row["available"]), "snapshot_sha256": row["snapshot_sha256"],
                                "observed_at": row["observed_at"], "links": item_links})
            sync = conn.execute("SELECT value FROM settings WHERE key='materials-sync'").fetchone()
        return {"entries": entries, **(json.loads(sync[0]) if sync else {"observed_at": None, "errors": []})}

    def refresh_meeting(self, session):
        folder = meeting_folder(self.root, session)
        entries, errors = meeting_materials(self.root)
        current = [item for item in entries if item.get("session") == folder.name]
        with self.store.transaction() as conn:
            for row in conn.execute("SELECT id,data_json FROM materials WHERE provider='blatero'").fetchall():
                if json.loads(row["data_json"]).get("session") == folder.name:
                    conn.execute("UPDATE materials SET available=0 WHERE id=?", (row["id"],))
            for item in current:
                conn.execute("INSERT INTO materials VALUES (?,?,?,?,?,1) ON CONFLICT(id) DO UPDATE SET "
                             "data_json=excluded.data_json,snapshot_sha256=excluded.snapshot_sha256,"
                             "observed_at=excluded.observed_at,available=1",
                             (item["id"], "blatero", json.dumps(item, ensure_ascii=False), digest(item), now()))
        return {**meeting_context(self.store, session, root=self.root), "errors": errors}

    def link(self, body, who, *, provenance=None):
        from project_provenance import context, event_source, record
        provenance = context(**provenance) if provenance is not None else None
        if not isinstance(body.get("material_id"), str):
            raise ValueError("выберите материал")
        task_id = body.get("work_item_id")
        with self.store.transaction() as conn:
            row = conn.execute("SELECT * FROM materials WHERE id=?", (body["material_id"],)).fetchone()
            if not row or not row["available"]:
                raise ValueError("материал не найден; обновите каталог")
            if row["snapshot_sha256"] != body.get("snapshot_sha256"):
                raise Conflict("материал изменился; обновите каталог")
            item = json.loads(row["data_json"])
            if item.get("provider") == "granka" and not self.granka_enabled():
                raise ValueError("Granka connection is disabled")
            if not task_id:
                # Same source always proposes the same card; retry cannot duplicate it.
                task_id = str(uuid.uuid5(uuid.NAMESPACE_URL, "blatero-material:" + item["id"]))
                exists = conn.execute("SELECT id FROM tasks WHERE id=?", (task_id,)).fetchone()
                if exists and self.store.task(task_id, conn)["project_id"] != body.get("project_id"):
                    raise Conflict("материал уже имеет карточку в другом проекте", self.store.task(task_id, conn))
                if not exists:
                    project_id = identifier(body.get("project_id"))
                    stub = {"id": task_id, "project_id": project_id}
                    created = self.store.apply(make_event(stub, who, "task.created", {
                        "title": item["title"] or "Материал", "goal": text(item.get("summary"), 4000),
                        "initial_status": "inbox"}, **event_source(provenance, system="materials",
                            session_id=item["id"][:160])), who, conn=conn)
                    if created["state"] != "applied":
                        raise ValueError(created.get("error"))
                    task = created["task"]
                    patch = {"next_step": "Сверить исходный материал и определить следующее действие"}
                    if item.get("date"):
                        patch["due"] = item["date"]
                    if item.get("start"):
                        patch.update(planned_start=item["start"], estimate_minutes=item["duration"])
                    updated = self.store.apply(make_event(task, who, "task.updated", {"patch": patch},
                        **event_source(provenance)), who, conn=conn)
                    if updated["state"] != "applied":
                        raise ValueError(updated.get("error"))
            task = self.store.task(task_id, conn)
            if task["merged_into"]:
                raise ValueError("выберите актуальную карточку")
            existing = conn.execute("SELECT * FROM material_links WHERE material_id=? AND work_item_id=?",
                                    (item["id"], task_id)).fetchone()
            if existing:
                return {"state": "applied", "task": task, "replayed": True}
            if body.get("work_item_id") and body.get("revision") != task["revision"]:
                raise Conflict("карточка изменилась; перечитайте контекст", task)
            source = {"id": str(uuid.uuid4()), "kind": "source_span", "snapshot_sha256": row["snapshot_sha256"]}
            conn.execute("INSERT INTO sources VALUES (?,?,?,?,?,?,?)",
                         (source["id"], task_id, source["kind"], text(item["title"], 2000), item.get("locator", ""),
                          source["snapshot_sha256"], now()))
            record(conn, "source", source["id"], provenance)
            linked = self.store.apply(make_event(task, who, "task.updated", {"patch": {"next_step": task["next_step"]}},
                                                references=[self.store.source_reference(source)],
                                                **event_source(provenance, system="materials", session_id=item["id"][:160])), who, conn=conn)
            if linked["state"] != "applied":
                raise Conflict(linked.get("error"), task)
            conn.execute("INSERT INTO material_links VALUES (?,?,?,?,?)",
                         (item["id"], task_id, source["id"], now(), who["id"]))
            return linked

    def unlink(self, body, who):
        with self.store.transaction() as conn:
            task = self.store.task(body.get("work_item_id"), conn)
            if task["revision"] != body.get("revision"):
                raise Conflict("карточка изменилась; перечитайте контекст", task)
            result = self.store.apply(make_event(task, who, "task.updated", {"patch": {"next_step": task["next_step"]}},
                                                system="materials"), who, conn=conn)
            if result["state"] != "applied":
                raise Conflict(result.get("error"), task)
            conn.execute("DELETE FROM material_links WHERE material_id=? AND work_item_id=?",
                         (body.get("material_id"), task["id"]))
            # The original evidence stays in the audit history.
            return result


def planning(store, anchor=None, project_id=None, *, root=None):
    day = dt.date.fromisoformat(anchor) if anchor else dt.datetime.now(TZ).date()
    day -= dt.timedelta(days=day.weekday())
    begin = dt.datetime.combine(day, dt.time.min, TZ)
    end = begin + dt.timedelta(days=7)
    items = []
    for task in store.tasks(project_id):
        if task["status"] in {"done", "closed"}:
            continue
        start = task.get("planned_start")
        if start:
            stamp = dt.datetime.fromisoformat(start.replace("Z", "+00:00")).astimezone(TZ)
            finish = stamp + dt.timedelta(minutes=task.get("estimate_minutes") or 30)
            if stamp < end and finish > begin:
                items.append({"id": task["id"], "kind": "task", "title": task["title"], "start": stamp.isoformat(),
                              "end": finish.isoformat(), "date": stamp.date().isoformat(), "task_id": task["id"],
                              "project_id": task["project_id"], "status": task["status"]})
        if task.get("due") and day.isoformat() <= task["due"] < end.date().isoformat():
            items.append({"id": "due:" + task["id"], "kind": "due", "title": task["title"], "date": task["due"],
                          "task_id": task["id"], "project_id": task["project_id"], "all_day": True})
    catalog = Materials(store, root=root).catalog()
    for material in catalog["entries"]:
        if not material["available"] or material.get("excluded") or material.get("connection_disabled"):
            continue
        links = material["links"]
        projects = {store.task(link["work_item_id"])["project_id"] for link in links}
        if project_id and project_id not in projects:
            continue
        if material.get("date") and day.isoformat() <= material["date"] < end.date().isoformat():
            items.append({**material, "task_id": links[0]["work_item_id"] if links else None,
                          "all_day": not bool(material.get("start"))})
    # Existing external calendar snapshots are read offline; no OAuth or network calls here.
    errors = list(catalog["errors"])
    try:
        cached = read_json((Path(root) if root is not None else app_paths.DATA_ROOT) / "calendar_cache.json", {})
        for event in cached.get("events", []):
            start = dt.datetime.fromisoformat(event["start"]).replace(tzinfo=TZ) if len(event["start"]) == 10 else dt.datetime.fromisoformat(event["start"])
            start = start.replace(tzinfo=TZ) if start.tzinfo is None else start.astimezone(TZ)
            finish = dt.datetime.fromisoformat(event["end"])
            finish = finish.replace(tzinfo=TZ) if finish.tzinfo is None else finish.astimezone(TZ)
            if finish > begin and start < end:
                items.append({**event, "id": "calendar:" + event["id"], "kind": "calendar", "date": start.date().isoformat(),
                              "start": start.isoformat(), "end": finish.isoformat(), "task_id": None})
    except (OSError, ValueError, TypeError, KeyError):
        errors.append("Кэш внешнего календаря недоступен")
    # The linked card copied from a meeting does not occupy a second calendar slot.
    source_slots = {(item.get("task_id"), item.get("start"), item.get("end")) for item in items
                    if item.get("kind") == "meeting" and item.get("task_id")}
    items = [item for item in items if item.get("kind") != "task" or
             (item.get("task_id"), item.get("start"), item.get("end")) not in source_slots]
    # A meeting and its related work are not reported as a conflict with itself.
    conflicts = []
    timed = [item for item in items if item.get("start") and item.get("end") and not item.get("all_day")]
    for i, left in enumerate(timed):
        for right in timed[i + 1:]:
            if left.get("task_id") and left.get("task_id") == right.get("task_id"):
                continue
            if dt.datetime.fromisoformat(left["start"]) < dt.datetime.fromisoformat(right["end"]) and dt.datetime.fromisoformat(right["start"]) < dt.datetime.fromisoformat(left["end"]):
                conflicts.append({"left": left["id"], "right": right["id"], "titles": [left["title"], right["title"]]})
    return {"anchor": day.isoformat(), "timezone": "Europe/Moscow", "items": items, "conflicts": conflicts,
            "errors": errors, "observed_at": catalog["observed_at"],
            "unscheduled": [{k: t.get(k) for k in ("id", "title", "project_id", "status", "due")}
                            for t in store.tasks(project_id) if t["status"] not in {"done", "closed"} and not t.get("planned_start")]}
