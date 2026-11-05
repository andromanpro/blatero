"""Local project UI and authenticated agent API, shared by panel and test server."""

from __future__ import annotations

import asyncio
import functools
import json
import logging
import sqlite3
import time
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse

import panel_transport
from project_queue import drain, status
from project_store import Conflict, Store, make_event

ASSETS = Path(__file__).parent / "assets"
OWNER = {"id": "local-user", "role": "owner"}


@functools.lru_cache(maxsize=1)
def default_store() -> Store:
    return Store()


async def queue_worker():
    material_sync = 0
    while True:
        try:
            await asyncio.to_thread(drain, default_store())
            await asyncio.to_thread(default_store().reconcile_history)
            if time.monotonic() - material_sync >= 60:
                from project_materials import Materials

                await asyncio.to_thread(Materials(default_store()).refresh)
                material_sync = time.monotonic()
        except (OSError, sqlite3.Error, ValueError):
            logging.getLogger(__name__).exception("project queue delivery failed")
        await asyncio.sleep(2)


def local_request(request: Request, *, mutation=False) -> None:
    if not panel_transport.is_loopback(request.client.host if request.client else None):
        raise PermissionError("режим проектов доступен с локального компьютера")
    origin = request.headers.get("origin")
    if origin and origin != f"{request.url.scheme}://{request.headers.get('host', '')}":
        raise PermissionError("неверный источник запроса")
    if mutation and request.headers.get("content-type", "").split(";", 1)[0] != "application/json":
        raise ValueError("нужен application/json")


def create_router(
    store_factory=None, *, meeting_root_factory=None, hub_factory=None, recording_guard=None
) -> APIRouter:
    router = APIRouter()

    @router.get("/projects")
    def page(request: Request):
        try:
            local_request(request)
        except PermissionError as exc:
            return JSONResponse({"error": str(exc)}, status_code=403)
        return FileResponse(ASSETS / "projects.html", media_type="text/html")

    @router.get("/projects/assets/{name}")
    def asset(request: Request, name: str):
        if name not in {
            "projects.css",
            "projects-layout.css",
            "projects.js",
            "projects-i18n.js",
            "projects-integrations.js",
            "projects-integrations.css",
            "projects-motion.js",
            "projects-daily.js",
            "projects-daily.css",
            "projects-library.js",
            "projects-library.css",
            "projects-closure.js",
            "projects-merge.js",
            "projects-merge.css",
            "projects-lifecycle.js",
            "projects-lifecycle.css",
        }:
            return JSONResponse({"error": "файл не найден"}, status_code=404)
        return FileResponse(
            ASSETS / name, media_type="text/css" if name.endswith("css") else "text/javascript"
        )

    def principal(request: Request, agent: bool) -> dict:
        if not agent:
            return OWNER
        authorization = request.headers.get("authorization", "")
        if not authorization.lower().startswith("bearer "):
            raise PermissionError("нужен Bearer ключ агента")
        return (store_factory or default_store)().principal(authorization[7:])

    def operation(request: Request, path: str, body: dict, agent: bool):
        store = (store_factory or default_store)()
        who = principal(request, agent)
        method = request.method
        if path == "connections" and not agent:
            import project_connections

            if method == "GET":
                return project_connections.read(store)
            if method == "POST":
                return project_connections.update(store, body)
        if path == "project-lifecycle" and method == "POST":
            from project_lifecycle import change

            return change(store, body, who)
        if path == "merge-preview" and method == "GET":
            from project_merge_preview import candidates, compare

            a, b = request.query_params.get("a"), request.query_params.get("b")
            if bool(a) != bool(b):
                raise ValueError("Нужны обе карточки для сравнения")
            return (
                compare(store, a, b)
                if a and b
                else candidates(store, request.query_params.get("project_id"))
            )
        if path == "quick-meeting/options" and method == "GET" and not agent:
            project_id = request.query_params.get("project_id")
            keys = (
                "id",
                "project_id",
                "title",
                "status",
                "goal",
                "next_step",
                "revision",
                "origin",
            )
            return {
                "projects": store.projects(),
                "tasks": [{k: t.get(k) for k in keys} for t in store.tasks(project_id)]
                if project_id
                else [],
            }
        if (
            path in {"quick-meeting/preview", "quick-meeting/create"}
            and method == "POST"
            and not agent
        ):
            import app_paths
            import meeting_quick

            root = meeting_root_factory() if meeting_root_factory else app_paths.DATA_ROOT
            if path.endswith("preview"):
                return meeting_quick.preview(store, root, body)
            return meeting_quick.create(
                store, root, body, who, recording_guard=recording_guard or (lambda: False)
            )
        if path == "library" or path.startswith("library/"):
            from knowledge_hub import Hub

            hub = (hub_factory or Hub)()
            if method == "GET":
                if path == "library/status":
                    return hub.health()
                if path.startswith("library/item/"):
                    return hub.detail(path.split("/", 2)[2], request.query_params.get("revision"))
                if path.startswith("library/commands/"):
                    return hub.command(path.split("/", 2)[2])
                if path == "library":
                    q = request.query_params
                    return hub.query(
                        q=q.get("q", ""),
                        project=q.get("project_id"),
                        task=q.get("task_id"),
                        kind=q.get("kind"),
                        freshness=q.get("freshness"),
                        offset=q.get("offset", 0),
                        limit=q.get("limit", 30),
                    )
            elif method == "POST":
                if not hub.path.exists():
                    raise ValueError("База знаний ещё не настроена")
                if path == "library/notes":
                    from project_store import identifier

                    if body.get("project_id"):
                        project_id = identifier(body["project_id"])
                        if not any(p["id"] == project_id for p in store.projects()):
                            raise ValueError("Проект не найден")
                    if body.get("task_id"):
                        task = store.task(body["task_id"])
                        if body.get("project_id") != task["project_id"]:
                            raise ValueError("Задача относится к другому проекту")
                    return hub.submit("note", body, who)
                if who["role"] != "owner":
                    raise PermissionError(
                        "Управление обработчиком и подтверждение доступны пользователю"
                    )
                if path == "library/confirm":
                    return hub.submit("confirm", body, who)
                if path == "library/pause":
                    if type(body.get("paused")) is not bool:
                        raise ValueError("Нужно явно задать paused")
                    hub.set_value("paused", body["paused"])
                    return hub.health()
                if path == "library/retry":
                    with hub.connect(write=True) as conn:
                        conn.execute("UPDATE jobs SET attempts=0,error='',due=0 WHERE error!=''")
                    return hub.health()
            raise ValueError("Операция библиотеки не найдена")
        if path.startswith("daily"):
            from project_daily import snapshot, task_context, mutate

            if path == "daily" and method == "GET":
                return snapshot(
                    store,
                    request.query_params.get("project_id"),
                    root=meeting_root_factory() if meeting_root_factory else None,
                    all_questions=request.query_params.get("questions") == "all",
                )
            if path.startswith("daily/task/") and method == "GET":
                task_id = store.task(path.split("/", 2)[2])["id"]
                return task_context(store, task_id)
            if (
                path in {"daily/focus", "daily/recall", "daily/request", "daily/resolve"}
                and method == "POST"
            ):
                return mutate(store, path, body, who)
        if path == "state" and method == "GET":
            with store.connect() as conn:
                links = [
                    dict(r)
                    for r in conn.execute(
                        "SELECT l.material_id,l.work_item_id,m.provider FROM material_links l JOIN materials m ON m.id=l.material_id"
                    )
                ]
                triage = [dict(r) for r in conn.execute("SELECT * FROM task_triage")]
            return {
                "projects": store.projects(),
                "tasks": store.tasks(),
                "queue": status(store.root),
                "material_links": links,
                "triage": triage,
                "import_summary": store.import_summary(),
            }
        if path in {
            "materials",
            "materials/refresh",
            "materials/link",
            "materials/unlink",
            "planning",
            "meeting-context",
            "meeting-sync",
        }:
            from project_materials import Materials, planning, meeting_context

            root = meeting_root_factory() if meeting_root_factory else None
            materials = Materials(store, root=root)
            if path == "meeting-context" and method == "GET":
                return meeting_context(store, request.query_params.get("session"), root=root)
            if path == "meeting-sync" and method == "POST":
                return materials.refresh_meeting(body.get("session"))
            if path == "materials" and method == "GET":
                return materials.catalog()
            if path == "materials/refresh" and method == "POST":
                return materials.refresh()
            if path == "materials/link" and method == "POST":
                return materials.link(body, who)
            if path == "materials/unlink" and method == "POST":
                return materials.unlink(body, who)
            if path == "planning" and method == "GET":
                project_id = request.query_params.get("project_id")
                if project_id:
                    from project_store import identifier

                    project_id = identifier(project_id)
                return planning(store, request.query_params.get("anchor"), project_id, root=root)
        if path == "efficiency" and method == "GET":
            from project_neon import efficiency

            return efficiency(store, request.query_params.get("project_id"))
        if path.startswith("context/") and method == "GET":
            return store.context(path.split("/", 1)[1])
        if path.startswith("projects/") and method == "GET":
            return store.project_detail(path.split("/", 1)[1])
        if path in {"project-preview", "project-update"} and method == "POST" and not agent:
            return store.edit_project(body, who, preview=path == "project-preview")
        parts = path.split("/")
        if len(parts) == 3 and parts[0] == "tasks" and parts[2] == "history" and method == "GET":
            return store.task_history(parts[1], request.query_params.get("section", "sources"),
                                      cursor=request.query_params.get("cursor"),
                                      limit=int(request.query_params.get("limit", "100")))
        if path.startswith("tasks/") and method == "GET":
            return store.detail(path.split("/", 1)[1])
        if path == "events" and method == "POST" and agent:
            return store.apply(body, who)
        if path == "projects" and method == "POST" and not agent:
            return store.create_project(
                body.get("name"), body.get("workspace", ""), body.get("description", "")
            )
        if path == "tasks" and method == "POST":
            return store.create_task(body, who)
        if path == "sources" and method == "POST":
            return store.add_source(
                body.get("work_item_id"),
                body.get("kind"),
                body.get("label"),
                body.get("locator", ""),
                body.get("snapshot_sha256"),
            )
        if path == "triage" and method == "POST":
            return store.triage(
                body.get("work_item_id"),
                body.get("revision"),
                body.get("kind"),
                body.get("reason"),
                body.get("source_id"),
                who,
            )
        if path == "queue/drain" and method == "POST" and not agent:
            return drain(store)
        if path == "knowledge/confirm" and method == "POST" and not agent:
            return store.confirm_knowledge(
                body.get("id"), body.get("work_item_id"), body.get("revision"), who
            )
        if path == "recall" and method == "POST" and not agent:
            return store.record_recall(
                body.get("work_item_id"),
                body.get("revision"),
                body.get("score"),
                body.get("hints", 0),
            )
        if path in {"update", "status", "knowledge", "check", "bind"} and method == "POST":
            task = store.task(body.get("work_item_id"))
            if path != "bind" and type(body.get("revision")) is not int:
                raise ValueError("нужна прочитанная редакция карточки")
            if "revision" in body:
                task["revision"] = body["revision"]
            refs = body.get("references", [])
            human_evidence = None
            if path == "update":
                kind, payload = "task.updated", {"patch": body.get("patch")}
            elif path == "status":
                kind, payload = (
                    "task.status_changed",
                    {"from": body.get("from"), "to": body.get("to"), "reason": body.get("reason")},
                )
                if payload["to"] == "closed" and not agent:
                    reason = body.get("reason")
                    if not isinstance(reason, str) or not reason.strip() or len(reason) > 2000:
                        raise ValueError("укажите причину закрытия: 1–2000 символов")
                    if store.task(task["id"])["revision"] != task["revision"]:
                        raise Conflict("карточка уже изменилась", store.task(task["id"]))
                    if task["status"] == "closed" or payload["from"] != task["status"]:
                        raise Conflict("исходный статус уже изменён или задача закрыта", task)
                    human_evidence = ("source_span", "Закрытие пользователем: " + reason.strip()[:1950], "")
                if payload["to"] == "done":
                    payload["policy_id"] = "owner-or-reviewer"
                    if not agent:
                        # Explicit human acceptance is evidence in its own right.
                        reason = body.get("reason")
                        if not isinstance(reason, str) or not reason.strip():
                            raise ValueError("укажите, какой результат вы приняли")
                        if store.task(task["id"])["revision"] != task["revision"]:
                            raise Conflict("карточка уже изменилась", store.task(task["id"]))
                        human_evidence = ("acceptance", reason, f"blatero:acceptance/revision/{task['revision']}")
                        refs = []
            elif path == "knowledge":
                kind, payload = (
                    "knowledge.proposed",
                    {"kind": body.get("kind"), "text": body.get("text"), "state": "draft"},
                )
            elif path == "check":
                kind, payload = (
                    "check.recorded",
                    {
                        "name": body.get("name"),
                        "result": body.get("result"),
                        "limitations": body.get("limitations", ""),
                    },
                )
            else:
                kind, payload = (
                    "session.started",
                    {"context_requested": True, "switch_task": bool(body.get("switch_task"))},
                )
            def event(references):
                return make_event(
                    task,
                    who,
                    kind,
                    payload,
                    references=references,
                    system=body.get("system", "panel"),
                    session_id=body.get("session_id", "manual"),
                )
            if human_evidence is None:
                return store.apply(event(refs), who)
            with store.transaction() as conn:
                conn.execute("SAVEPOINT status_evidence")
                source = store.add_source(task["id"], *human_evidence, conn=conn)
                result = store.apply(event([*refs, store.source_reference(source)]), who, conn=conn)
                if result["state"] != "applied":
                    conn.execute("ROLLBACK TO status_evidence")
                conn.execute("RELEASE status_evidence")
                return result
        return JSONResponse({"error": "маршрут не найден"}, status_code=404)

    async def handle(request: Request, path: str, agent: bool):
        try:
            local_request(request, mutation=request.method != "GET")
            # Authenticate before reading an attacker-controlled body.
            await asyncio.to_thread(principal, request, agent)
            raw = bytearray()
            if request.method != "GET":
                async for chunk in request.stream():
                    raw.extend(chunk)
                    if len(raw) > 65536:
                        return JSONResponse({"error": "запрос превышает 64 КБ"}, status_code=413)
            body = json.loads(raw) if raw else {}
            if not isinstance(body, dict):
                raise ValueError("нужен JSON-объект")
            result = await asyncio.to_thread(operation, request, path, body, agent)
            if isinstance(result, dict) and result.get("state") in {"conflict", "rejected"}:
                return JSONResponse(
                    result, status_code=409 if result["state"] == "conflict" else 422
                )
            return result
        except PermissionError as exc:
            return JSONResponse({"error": str(exc)}, status_code=403)
        except Conflict as exc:
            return JSONResponse({"error": str(exc), "current": exc.current}, status_code=409)
        except (ValueError, TypeError, KeyError) as exc:
            return JSONResponse({"error": str(exc)}, status_code=422)
        except sqlite3.OperationalError:
            return JSONResponse({"error": "база занята; повторите запрос"}, status_code=503)

    @router.api_route("/api/projects/agent/{path:path}", methods=["GET", "POST"])
    async def agent_route(request: Request, path: str):
        return await handle(request, path, True)

    @router.api_route("/api/projects/{path:path}", methods=["GET", "POST"])
    async def user_route(request: Request, path: str):
        return await handle(request, path, False)

    return router
