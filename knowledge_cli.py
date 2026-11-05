"""Agent-friendly local interface to the independent knowledge hub."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from knowledge_hub import Hub, atomic


def install_startup(hub):
    if os.name != "nt":
        raise ValueError("Автозапуск этого установщика доступен в Windows")
    # pythonw hosts the worker without a console. A per-user Startup launcher is reversible.
    executable=Path(sys.executable).with_name("pythonw.exe")
    if not executable.exists():
        raise ValueError("В текущем окружении отсутствует pythonw.exe")
    script=Path(__file__).with_name("knowledge_worker.py").resolve()
    launcher=hub.root/"start-worker.vbs"
    def quote(value):
        return '"'+str(value).replace('"','""')+'"'
    command=subprocess.list2cmdline([str(executable),str(script),"--home",str(hub.root)])
    content='Set shell = CreateObject("WScript.Shell")\r\nshell.Run '+quote(command)+', 0, False\r\n'
    atomic(launcher,content)
    startup=Path(os.environ["APPDATA"])/"Microsoft/Windows/Start Menu/Programs/Startup/Knowledge Hub.vbs"
    atomic(startup,'Set shell = CreateObject("WScript.Shell")\r\nshell.Run '+quote(subprocess.list2cmdline(["wscript.exe",str(launcher)]))+', 0, False\r\n')
    return {"startup":str(startup),"launcher":str(launcher)}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser=argparse.ArgumentParser(description="Локальная база знаний: поиск, источники и предложения агента")
    parser.add_argument("--home")
    sub=parser.add_subparsers(dest="command",required=True)
    init=sub.add_parser("init")
    init.add_argument("--board",required=True)
    init.add_argument("--notes",required=True)
    init.add_argument("--without-history",action="store_true")
    search=sub.add_parser("search")
    search.add_argument("query",nargs="?",default="")
    search.add_argument("--project")
    search.add_argument("--task")
    search.add_argument("--kind")
    search.add_argument("--offset",type=int,default=0)
    search.add_argument("--limit",type=int,default=20)
    detail=sub.add_parser("detail")
    detail.add_argument("id")
    note=sub.add_parser("propose")
    note.add_argument("--json-file",required=True,help="UTF-8 JSON: title, body, project_id/task_id, kind, references:[{id,content_hash}], id/revision для правки")
    notify=sub.add_parser("notify")
    notify.add_argument("--path",required=True)
    sub.add_parser("status")
    sub.add_parser("pause")
    sub.add_parser("resume")
    sub.add_parser("retry")
    sub.add_parser("install-startup")
    args=parser.parse_args()
    hub=Hub(args.home,initialize=args.command in {"init","propose","notify"})
    if args.command=="init":
        from knowledge_collect import configure
        if hub.config:
            raise ValueError("Конфигурация уже существует; правьте выбранные источники в config.json")
        config=configure(hub,args.board,args.notes,history=not args.without_history)
        hub.notes.mkdir(parents=True,exist_ok=True)
        for folder in ("notes","generated","history"):
            (hub.notes/folder).mkdir(exist_ok=True)
            atomic(hub.notes/folder/".gitkeep","")
        atomic(hub.notes/".gitignore","*.tmp\n*.sqlite3*\n*.log\n")
        atomic(hub.notes/"README.md","# Общая база знаний\n\nОригиналы находятся в проектах. `generated` — актуальные снимки доски; править их нужно через карточки. `notes` — знания с основаниями, добавляемые агентами через knowledge_cli.py propose. `history` — события подтверждения. Поиск и очередь находятся отдельно в локальном runtime, конфигурация: "+str(hub.config_path)+".\n\nGit сохраняет локальные пакетные снимки; удалённая публикация не настроена.\n")
        atomic(hub.notes/"AGENTS.md","# Knowledge Hub\n\nКаждый факт требует источника своего проекта. Не переносить контекст между проектами. Не редактировать generated: обновлять карточку Blatero. Знания добавлять knowledge_cli.py propose с id/content_hash оснований. При изменении перечитать revision. Агент создаёт draft; подтверждает пользователь. Следовать происхождению и freshness, не считать changed доказательством неверности решения.\n")
        result={"configured":True,"projects":len(config["project_roots"]),"notes_root":str(hub.notes),"runtime":str(hub.root)}
    elif args.command=="search":
        result=hub.query(q=args.query,project=args.project,task=args.task,kind=args.kind,offset=args.offset,limit=args.limit)
    elif args.command=="detail":
        result=hub.detail(args.id)
    elif args.command=="status":
        result=hub.health()
    elif args.command=="propose":
        body=json.loads(Path(args.json_file).read_text(encoding="utf-8"))
        result=hub.save_note(body,{"id":"local-agent","role":"worker"})
    elif args.command=="notify":
        from knowledge_collect import register_file,scope_for
        register_file(hub,args.path,scope_for(str(Path(args.path).parent),hub.value("projects",[])))
        result={"queued":True}
    elif args.command in {"pause","resume"}:
        hub.set_value("paused",args.command=="pause")
        result={"paused":args.command=="pause"}
    elif args.command=="retry":
        with hub.connect(write=True) as conn:
            conn.execute("UPDATE jobs SET attempts=0,error='',due=0 WHERE error!=''")
        result={"queued":True}
    else:
        result=install_startup(hub)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
