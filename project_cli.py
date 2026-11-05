"""Local agent interface. Never depends on the panel, a model, or network access."""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
import uuid
from pathlib import Path

from project_queue import atomic_json, drain, enqueue, status
from project_store import Store, make_event
from project_provenance import event_source, from_args


def deliver(store: Store, event: dict, principal: dict, token: str) -> dict:
    # Put the durable receipt first, so killing the process cannot lose a command.
    queued = enqueue(store.root, event, token)
    try:
        result = store.apply(event, principal)
        drain(store)
        return result
    except sqlite3.OperationalError:
        return queued


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Blatero: задачи и контекст для агентов")
    p.add_argument("--data-root", type=Path, help="отдельная папка .projects для испытаний")
    p.add_argument("--key-file", type=Path, help="ключ уполномоченного агента; по умолчанию worker")
    commands = p.add_subparsers(dest="command", required=True)
    commands.add_parser("projects")
    create = commands.add_parser("project-create")
    create.add_argument("name")
    create.add_argument("--workspace", default="")
    create.add_argument("--description", default="")
    tasks = commands.add_parser("tasks")
    tasks.add_argument("--project")
    tasks.add_argument("--query", default="")
    create = commands.add_parser("create")
    create.add_argument("title")
    create.add_argument("--project")
    create.add_argument("--goal", default="")
    for name in ("context", "detail"):
        commands.add_parser(name).add_argument("task")
    update = commands.add_parser("update")
    update.add_argument("task")
    update.add_argument("--revision", required=True, type=int)
    update.add_argument("--planned-start")
    update.add_argument("--estimate-minutes", type=int)
    for name in ("title", "goal", "method", "rationale", "next-step", "priority", "due"):
        update.add_argument("--" + name)
    update.add_argument("--parent-id", help="UUID родительской задачи; пусто снимает связь")
    update.add_argument("--project-id", help="явно привязать входящую задачу к проекту")
    change = commands.add_parser("status")
    change.add_argument("task")
    change.add_argument("to", choices=("inbox", "active", "waiting", "review", "done", "closed"))
    change.add_argument("--revision", required=True, type=int)
    change.add_argument("--reason", required=True)
    change.add_argument("--reference", action="append", default=[])
    checkpoint = commands.add_parser("checkpoint")
    checkpoint.add_argument("task")
    checkpoint.add_argument("--revision", required=True, type=int)
    checkpoint.add_argument("--summary", required=True)
    checkpoint.add_argument("--next-step", required=True)
    checkpoint.add_argument("--method")
    checkpoint.add_argument("--rationale")
    finish = commands.add_parser("finish-turn", help="Сохранить итог хода и получить квитанцию редакции")
    finish.add_argument("task")
    finish.add_argument("--revision", required=True, type=int)
    for name in ("summary", "method", "rationale", "next-step"):
        finish.add_argument("--" + name, required=True)
    outcome = commands.add_parser("outcome-status", help="Проверить квитанцию конкретного хода")
    outcome.add_argument("--system", required=True)
    outcome.add_argument("--session", required=True)
    outcome.add_argument("--turn", required=True)
    outcome.add_argument("--task")
    turn = commands.add_parser("current-turn", help="Проверить ID активного хода в его первичном журнале")
    turn.add_argument("--system", required=True)
    turn.add_argument("--session", required=True)
    turn.add_argument("--transcript", required=True)
    bind = commands.add_parser("bind")
    bind.add_argument("task")
    bind.add_argument("--switch", action="store_true", help="явно сменить текущую задачу сессии")
    source = commands.add_parser("source")
    source.add_argument("task")
    source.add_argument("--kind", choices=("source_span", "artifact", "check", "acceptance"), required=True)
    source.add_argument("--label", required=True)
    source.add_argument("--locator", default="")
    source.add_argument("--sha256", help="SHA-256 основания; для source_span JSONL:строка точный префикс вычисляется и проверяется автоматически")
    for name in ("knowledge", "check"):
        sub = commands.add_parser(name)
        sub.add_argument("task")
        sub.add_argument("--reference", action="append", default=[])
        if name == "knowledge":
            sub.add_argument("--kind", choices=("decision", "fact", "constraint", "open_question"), required=True)
            sub.add_argument("--text", required=True)
        else:
            sub.add_argument("--name", required=True)
            sub.add_argument("--result", choices=("passed", "failed", "not_run"), required=True)
            sub.add_argument("--limitations", default="")
    event = commands.add_parser("event")
    event.add_argument("file", help="JSON-файл или - для stdin")
    key = commands.add_parser("agent-key")
    key.add_argument("name")
    key.add_argument("--role", choices=("worker", "reviewer"), default="worker")
    key.add_argument("--output", required=True, type=Path)
    commands.add_parser("drain")
    commands.add_parser("queue")
    commands.add_parser("watch")
    commands.add_parser("materials")
    commands.add_parser("materials-refresh")
    plan = commands.add_parser("planning")
    plan.add_argument("--anchor")
    plan.add_argument("--project")
    daily = commands.add_parser("daily")
    daily.add_argument("--project")
    request = commands.add_parser("decision-request")
    request.add_argument("task")
    request.add_argument("--revision", type=int, required=True)
    request.add_argument("--question", required=True)
    request.add_argument("--recommendation", default="")
    answer = commands.add_parser("decision-answer", help="Записать полученный ответ пользователя из первичного сообщения Codex")
    answer.add_argument("--json-file", required=True, help="request_id,work_item_id,revision,id,decision_revision,question,answer,quote,session_id,reference_id")
    material = commands.add_parser("material-link")
    material.add_argument("material_id")
    material.add_argument("--sha256", required=True)
    material.add_argument("--task")
    material.add_argument("--revision", type=int)
    material.add_argument("--project")
    for command in (create, update, change, checkpoint, finish, bind, source, event,
                    request, answer, material):
        command.add_argument("--system", help="система, выполнившая команду")
        command.add_argument("--session", "--session-id", help="сессия исполнителя")
        command.add_argument("--turn", "--turn-id", help="ход сессии исполнителя")
    for name in ("knowledge", "check"):
        command = commands.choices[name]
        command.add_argument("--system", help="система, выполнившая команду")
        command.add_argument("--session", "--session-id", help="сессия исполнителя")
        command.add_argument("--turn", "--turn-id", help="ход сессии исполнителя")
    return p


def execute(args) -> dict | list:
    cmd = args.command
    if cmd == "current-turn":
        from project_turn_outcomes import current_turn
        return current_turn(args.system, args.session, args.transcript)
    provenance = from_args(args)
    store = Store(args.data_root)
    if cmd == "projects":
        return store.projects()
    if cmd == "project-create":
        return store.create_project(args.name, args.workspace, args.description)
    if cmd == "tasks":
        return store.tasks(args.project, args.query)
    if cmd in {"context", "detail"}:
        return getattr(store, cmd)(args.task)
    if cmd == "outcome-status":
        from project_turn_outcomes import outcome_status
        return outcome_status(store, args.system, args.session, args.turn, args.task)
    if cmd == "decision-answer":
        from project_chat_answers import record_answer
        who = store.principal(json.loads(args.key_file.read_text(encoding="utf-8"))["token"]) if args.key_file else store.local_agent()[0]
        return record_answer(store, json.loads(Path(args.json_file).read_text(encoding="utf-8")), who,
                             provenance=provenance)
    if cmd in {"daily", "decision-request"}:
        from project_daily import snapshot, mutate
        if cmd == "daily":
            return snapshot(store, args.project)
        who = store.principal(json.loads(args.key_file.read_text(encoding="utf-8"))["token"]) if args.key_file else store.local_agent()[0]
        return mutate(store, "daily/request", {"work_item_id": args.task, "revision": args.revision,
                      "question": args.question, "recommendation": args.recommendation}, who,
                      provenance=provenance)
    if cmd in {"materials", "materials-refresh", "planning", "material-link"}:
        from project_materials import Materials, planning
        materials = Materials(store)
        if cmd == "materials":
            return materials.catalog()
        if cmd == "materials-refresh":
            return materials.refresh()
        if cmd == "planning":
            return planning(store, args.anchor, args.project)
        if args.key_file:
            who = store.principal(json.loads(args.key_file.read_text(encoding="utf-8"))["token"])
        else:
            who = store.local_agent()[0]
        return materials.link({"material_id": args.material_id, "snapshot_sha256": args.sha256,
                               "work_item_id": args.task, "revision": args.revision, "project_id": args.project}, who,
                              provenance=provenance)
    if cmd == "source":
        return store.add_source(args.task, args.kind, args.label, args.locator, args.sha256,
                                provenance=provenance)
    if cmd == "agent-key":
        if args.output.exists():
            raise ValueError("файл ключа уже существует")
        principal, token = store.issue_agent(args.name, args.role)
        atomic_json(args.output, {**principal, "token": token})
        return {"id": principal["id"], "role": principal["role"], "key_file": str(args.output.resolve())}
    if cmd == "queue":
        return status(store.root)
    if cmd == "drain":
        return drain(store)
    if cmd == "watch":
        while True:
            drain(store)
            time.sleep(2)
    if args.key_file:
        token = json.loads(args.key_file.read_text(encoding="utf-8"))["token"]
        principal = store.principal(token)
    else:
        principal, token = store.local_agent()
    if cmd == "event":
        raw = sys.stdin.read(65537) if args.file == "-" else Path(args.file).read_text(encoding="utf-8")
        event = json.loads(raw)
        if provenance and any(event.get("source", {}).get(key) != value for key, value in provenance.items()):
            raise ValueError("происхождение JSON-события не совпадает с контекстом команды")
        return deliver(store, event, principal, token)
    task = store.task(args.task) if hasattr(args, "task") else None
    refs = [store.source_reference(s) for s in store.detail(task["id"])["sources"]
            if s["id"] in args.reference] if hasattr(args, "reference") else []
    if hasattr(args, "reference") and len(refs) != len(set(args.reference)):
        raise ValueError("основание не найдено в этой задаче")
    if hasattr(args, "revision"):
        # Preserve the revision the agent actually read; Store rejects stale patches.
        task["revision"] = args.revision
    if cmd == "finish-turn":
        from project_turn_outcomes import event_for
        from operation_lock import OperationLock, OperationLockError
        payload = {key: getattr(args, key) for key in ("summary", "method", "rationale", "next_step")}
        try:
            with OperationLock(store.root / "turn-outcome.lock"):
                return deliver(store, event_for(store, task, principal, provenance, payload), principal, token)
        except OperationLockError as exc:
            raise ValueError("сохранение итога уже выполняется; проверь outcome-status и повтори") from exc
    if cmd == "create":
        task = {"id": str(uuid.uuid4()), "project_id": args.project}
        kind, payload = "task.created", {"title": args.title, "goal": args.goal, "initial_status": "inbox"}
    elif cmd == "update":
        patch = {key: getattr(args, key) for key in
                 ("title", "goal", "method", "rationale", "next_step", "priority", "due", "parent_id", "project_id", "planned_start", "estimate_minutes")
                 if getattr(args, key) is not None}
        for key in ("due", "parent_id", "project_id", "planned_start"):
            if patch.get(key) == "":
                patch[key] = None
        kind, payload = "task.updated", {"patch": patch}
    elif cmd == "status":
        kind, payload = "task.status_changed", {"from": task["status"], "to": args.to, "reason": args.reason}
        if args.to == "done":
            payload["policy_id"] = "owner-or-reviewer"
    elif cmd == "checkpoint":
        kind = "session.checkpoint"
        payload = {key: getattr(args, key) for key in ("summary", "next_step", "method", "rationale")
                   if getattr(args, key) is not None}
    elif cmd == "bind":
        kind, payload = "session.started", {"context_requested": True}
        if args.switch:
            payload["switch_task"] = True
    elif cmd == "knowledge":
        kind, payload = "knowledge.proposed", {"kind": args.kind, "text": args.text, "state": "draft"}
    elif cmd == "check":
        kind, payload = "check.recorded", {"name": args.name, "result": args.result, "limitations": args.limitations}
    else:
        raise ValueError("неизвестная команда")
    return deliver(store, make_event(task, principal, kind, payload, references=refs,
                                    **event_source(provenance)), principal, token)


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    try:
        result = execute(parser().parse_args(argv))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2 if isinstance(result, dict) and result.get("state") in {"conflict", "rejected"} else 0
    except (ValueError, PermissionError, OSError, sqlite3.Error) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
