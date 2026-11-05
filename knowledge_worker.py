"""Standalone low-priority, restartable knowledge collector. Never calls a model."""
from __future__ import annotations

import argparse
import contextlib
import ctypes
import json
import logging
from logging.handlers import RotatingFileHandler
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import knowledge_collect as collect
from knowledge_hub import Hub, now, sha
from operation_lock import OperationLock, OperationLockError, lock_is_held


def below_normal():
    if os.name == "nt":
        from ctypes import wintypes
        get_process=ctypes.windll.kernel32.GetCurrentProcess
        get_process.restype=wintypes.HANDLE
        set_priority=ctypes.windll.kernel32.SetPriorityClass
        set_priority.argtypes=[wintypes.HANDLE,wintypes.DWORD]
        return bool(set_priority(get_process(),0x4000))
    try:
        os.nice(10)
        return True
    except OSError:
        return False


def windows_metrics(previous=None):
    """System pressure and this worker's memory; no optional runtime dependency."""
    if os.name != "nt":
        return {"cpu_percent":0,"available_mb":2048,"working_set_mb":None},None
    from ctypes import wintypes
    class Memory(ctypes.Structure):
        _fields_ = [("length",wintypes.DWORD),("load",wintypes.DWORD)]+[(name,ctypes.c_ulonglong) for name in ("total","available","page_total","page_available","virtual_total","virtual_available","extended")]
    memory=Memory()
    memory.length=ctypes.sizeof(memory)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory))
    idle,kernel,user = ctypes.c_ulonglong(),ctypes.c_ulonglong(),ctypes.c_ulonglong()
    ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle),ctypes.byref(kernel),ctypes.byref(user))
    current=(idle.value,kernel.value+user.value)
    cpu=0
    if previous and current[1]>previous[1]:
        cpu=round(100*(1-(current[0]-previous[0])/(current[1]-previous[1])),1)
    class Counters(ctypes.Structure):
        _fields_ = [("cb",wintypes.DWORD),("faults",wintypes.DWORD)]+[(n,ctypes.c_size_t) for n in ("peak","working","quota_peak_paged","quota_paged","quota_peak_nonpaged","quota_nonpaged","pagefile","peak_pagefile")]
    counters=Counters()
    counters.cb=ctypes.sizeof(counters)
    get_process=ctypes.windll.kernel32.GetCurrentProcess
    get_process.restype=wintypes.HANDLE
    get_memory=ctypes.windll.psapi.GetProcessMemoryInfo
    get_memory.argtypes=[wintypes.HANDLE,ctypes.c_void_p,wintypes.DWORD]
    get_memory(get_process(),ctypes.byref(counters),counters.cb)
    return {"cpu_percent":cpu,"available_mb":round(memory.available/1024**2),"working_set_mb":round(counters.working/1024**2,1)},current


def recording_busy(hub):
    root=Path(hub.config.get("recording_root",str(hub.root/"absent")))
    if not root.is_dir():
        return False
    for session in root.iterdir():
        if not session.is_dir() or session.is_symlink():
            continue
        lock=session/".recording-owner.lock"
        if lock.exists() and lock_is_held(lock):
            return True
        levels=session/"levels.json"
        try:
            if time.time()-levels.stat().st_mtime<5:
                data=json.loads(levels.read_text(encoding="utf-8"))
                if -5 < time.time()-float(data.get("ts",0))<5:
                    return True
        except (OSError,ValueError,TypeError):
            pass
    return False


def extract(path, max_bytes):
    from transcript_import import _decode_text,docx_text,pdf_text
    before=path.stat()
    if before.st_size>max_bytes:
        raise ValueError("Файл больше лимита 10 МБ; требуется отдельный импорт")
    raw=path.read_bytes()
    after=path.stat()
    if (before.st_mtime_ns,before.st_size)!=(after.st_mtime_ns,after.st_size):
        raise ValueError("Файл меняется; обработка отложена")
    if path.suffix.lower()==".json":
        data=json.loads(raw.decode("utf-8-sig"))
        adrs=data.get("adr") if isinstance(data,dict) else None
        if not isinstance(adrs,list) or len(adrs)>1000 or any(not isinstance(r,dict) or not r.get("id") for r in adrs):
            raise ValueError("Ожидается реестр adr: до1000 записей с id")
        return {"adr":adrs,"content_hash":sha(raw),"signature":f"{after.st_mtime_ns}:{after.st_size}"}
    if path.suffix.lower()==".docx":
        text=docx_text(raw)
    elif path.suffix.lower()==".pdf":
        text=pdf_text(raw,max_pages=300,max_chars=1_000_000)
    else:
        text=_decode_text(raw)
    if not text.strip():
        raise ValueError("Доступного текста нет; OCR не включён")
    return {"text":collect.sanitize(text[:250000]),"content_hash":sha(raw),
            "signature":f"{after.st_mtime_ns}:{after.st_size}","truncated":len(text)>250000}


def process_file(hub, job):
    payload=json.loads(job["payload"])
    roots=[r["path"] for r in hub.config.get("project_roots",[])]+hub.config.get("extra_files",[])+[str(hub.notes)]
    if hub.config.get("recording_root"):
        roots.append(hub.config["recording_root"])
    structured={str(Path(r["path"]).absolute()) for r in hub.config.get("structured_sources",[])}
    path=collect.safe_path(payload["path"],roots,suffixes=collect.SUFFIXES|({".json"} if str(Path(payload["path"]).absolute()) in structured else set()))
    if not path.exists():
        with hub.connect(write=True) as conn:
            previous=conn.execute("SELECT * FROM items WHERE id=?",(job["id"],)).fetchone()
            if previous:
                conn.execute("UPDATE items SET freshness='missing' WHERE id=?",(job["id"],))
            else:
                hub.put({"id":job["id"],"project_id":payload.get("project_id"),"task_id":payload.get("task_id"),"kind":"document","title":path.name,"body":"Источник недоступен. Проверьте путь или восстановите файл.","locator":str(path),"freshness":"missing"},conn)
            hub.invalidate(job["id"],conn)
            conn.execute("UPDATE files SET signature='missing' WHERE id=?",(job["id"],))
        return 0
    # The disposable child bounds document parsers' wall time and memory lifetime.
    executable=Path(sys.executable).with_name("python.exe") if os.name=="nt" else Path(sys.executable)
    result=subprocess.run([str(executable),str(Path(__file__).resolve()),"--extract",str(path),"--max-bytes",str(hub.config.get("max_file_bytes",10*1024*1024))],
                          capture_output=True,timeout=12,creationflags=subprocess.CREATE_NO_WINDOW if os.name=="nt" else 0)
    if result.returncode:
        try:
            error=json.loads(result.stdout.decode("utf-8"))["error"]
        except (ValueError,KeyError,UnicodeError):
            error="Не удалось извлечь текст"
        raise ValueError(error)
    data=json.loads(result.stdout.decode("utf-8"))
    if "adr" in data:
        from knowledge_hub import stable_id
        identities=[]
        with hub.connect(write=True) as conn:
            for adr in data["adr"]:
                identity=stable_id(job["id"],str(adr["id"]))
                identities.append(identity)
                body="\n\n".join(label+":\n"+collect.sanitize(str(adr.get(key,""))) for key,label in (("status","Статус в источнике"),("date","Дата"),("context","Контекст"),("decision","Решение"),("consequences","Последствия")))
                hub.put({"id":identity,"project_id":payload.get("project_id"),"kind":"decision","title":str(adr["id"])+" · "+collect.sanitize(str(adr.get("title",""))),"body":body[:250000],
                         "locator":str(path)+"#adr/"+str(adr["id"]),"content_hash":sha(json.dumps(adr,ensure_ascii=False,sort_keys=True)),
                         "metadata":{"registry_id":job["id"],"adr_id":str(adr["id"]),"source_status":adr.get("status"),"truncated":len(body)>250000}},conn)
            previous=[r[0] for r in conn.execute("SELECT id FROM items WHERE json_extract(metadata,'$.registry_id')=?",(job["id"],))]
            for identity in set(previous)-set(identities):
                conn.execute("UPDATE items SET freshness='missing' WHERE id=?",(identity,))
                hub.invalidate(identity,conn)
    elif path.is_relative_to(hub.notes/"notes") and path.suffix==".md":
        hub.index_note_file(path)
    else:
        hub.put({"id":job["id"],"project_id":payload.get("project_id"),"task_id":payload.get("task_id"),"kind":"document",
                 "title":path.name,"body":data["text"],"locator":str(path),"content_hash":data["content_hash"],
                 "metadata":{"truncated":data["truncated"],"extractor":"local-text-v1"}})
    with hub.connect(write=True) as conn:
        conn.execute("UPDATE files SET signature=? WHERE id=?",(data["signature"],job["id"]))
    return len(data["adr"]) if "adr" in data else 1


def drain_one(hub):
    with hub.connect() as conn:
        row=conn.execute("SELECT * FROM jobs WHERE due<=? AND attempts<3 ORDER BY CASE kind WHEN 'file' THEN 0 ELSE 1 END,due,id LIMIT 1",(time.time(),)).fetchone()
    if not row:
        return None
    job=dict(row)
    started=time.perf_counter()
    try:
        more=False
        if job["kind"]=="file":
            count=process_file(hub,job)
        elif job["kind"]=="stream":
            more,count=collect.read_stream(hub,job["id"])
        elif job["kind"]=="sql_session":
            payload=json.loads(job["payload"])
            more,count=collect.read_sql_session(hub,payload)
            job["payload"]=json.dumps(payload,ensure_ascii=False)
            if not more:
                key="sqlite_versions:"+payload["provider"]
                versions=hub.value(key,{})
                versions[payload["session_id"]]=job["signature"]
                hub.set_value(key,versions)
        else:
            raise ValueError("Неизвестная операция")
        with hub.connect(write=True) as conn:
            if more:
                conn.execute("UPDATE jobs SET payload=?,due=?,attempts=0,error='' WHERE id=? AND signature=?",(job["payload"],time.time()+1,job["id"],job["signature"]))
            else:
                conn.execute("DELETE FROM jobs WHERE id=? AND signature=?",(job["id"],job["signature"]))
        result={"at":now(),"kind":job["kind"],"seconds":round(time.perf_counter()-started,4),"records":count}
        hub.set_value("last_success",result)
        return result
    except (OSError,ValueError,KeyError,TypeError,AttributeError,sqlite3.Error,subprocess.TimeoutExpired) as exc:
        # Permanent failures are visible, not retried on every tick. A changed file resets attempts.
        message=str(exc)[:300] if isinstance(exc,ValueError) else type(exc).__name__
        with hub.connect(write=True) as conn:
            conn.execute("UPDATE jobs SET attempts=attempts+1,error=?,due=? WHERE id=? AND signature=?",(message,time.time()+30*(job["attempts"]+1),job["id"],job["signature"]))
            conn.execute("UPDATE items SET freshness='error' WHERE id=?",(job["id"],))
            if job["kind"]=="file" and not conn.execute("SELECT 1 FROM items WHERE id=?",(job["id"],)).fetchone():
                payload=json.loads(job["payload"])
                hub.put({"id":job["id"],"project_id":payload.get("project_id"),"task_id":payload.get("task_id"),"kind":"document","title":Path(payload["path"]).name,"body":"Текст не извлечён: "+message,"locator":payload["path"],"freshness":"error"},conn)
            hub.invalidate(job["id"],conn)
        return {"error":message,"kind":job["kind"]}


def snapshot_git(hub):
    if not (hub.notes/".git").is_dir():
        return
    flags=subprocess.CREATE_NO_WINDOW if os.name=="nt" else 0
    def git(*args):
        return subprocess.run(["git","-C",str(hub.notes),*args],capture_output=True,timeout=20,creationflags=flags)
    # Stage only our knowledge folders. Never stage unrelated user files.
    added=git("add","--","generated","notes","history","README.md","AGENTS.md",".gitignore")
    if added.returncode:
        hub.set_value("git",{"error":"Не удалось подготовить снимок знаний","at":now()})
        return
    if git("diff","--cached","--quiet").returncode==0:
        return
    committed=git("-c","user.name=Knowledge Hub","-c","user.email=knowledge-hub@localhost","commit","-m","Knowledge snapshot "+now())
    hub.set_value("git",{"at":now(),"ok":committed.returncode==0,"error":"" if committed.returncode==0 else "Git-снимок не создан"})


class Worker:
    def __init__(self,hub):
        self.hub=hub
        self.last_board=0
        self.last_sessions=0
        self.last_git=0
        self.scan_index=hub.value("scan_index",0)
        self.last_scan=0
        self.pressure=None
        self.started=time.monotonic()
        self.priority=below_normal()
        if hub.value("collector_policy") != 3:
            with hub.connect(write=True) as conn:
                conn.execute("UPDATE files SET signature=''")
                conn.execute("UPDATE streams SET offset=0,prefix='',anchor='',signature=''")
                conn.execute("UPDATE jobs SET payload=json_set(payload,'$.offset',0) WHERE kind='sql_session'")
            hub.set_value("sqlite_versions:hermes",{})
            hub.set_value("sqlite_versions:opencode",{})
            hub.set_value("collector_policy",3)

    def tick(self):
        hub=self.hub
        hub.config=json.loads(hub.config_path.read_text(encoding="utf-8")) if hub.config_path.exists() else hub.config
        hub.notes=Path(hub.config.get("notes_root",str(hub.notes))).resolve()
        metrics,self.pressure=windows_metrics(self.pressure)
        paused="manual" if hub.value("paused",False) else "recording" if recording_busy(hub) else "system_load" if metrics["cpu_percent"]>=85 or metrics["available_mb"]<768 else ""
        state={"pid":os.getpid(),"heartbeat":time.time(),"paused_reason":paused,"below_normal":self.priority,"uptime_seconds":round(time.monotonic()-self.started),"cpu_seconds":round(time.process_time(),3),**metrics}
        hub.set_value("worker",state)
        serve_commands(hub)
        if paused:
            return state
        consume_signals(hub)
        clock=time.monotonic()
        if clock-self.last_board>=60:
            if hub.config.get("board_delivery", True):
                from project_queue import drain
                from project_store import Store
                from project_materials import Materials
                board_store=Store(Path(hub.config["board"]).parent,initialize=False)
                drain(board_store,limit=25)
                Materials(board_store,root=Path(hub.config["board"]).parent.parent).refresh()
            def pulse():
                state["heartbeat"]=time.time()
                hub.set_value("worker",state)
                serve_commands(hub)
            collect.mirror_board(hub,pulse=pulse)
            self.last_board=clock
            # Check deletion and edits only among already selected paths.
            with hub.connect() as conn:
                files=[dict(r) for r in conn.execute("SELECT * FROM files")]
            for f in files:
                try:
                    collect.register_file(hub,f["path"],f["project_id"],f["task_id"])
                except (OSError,ValueError):
                    pass
            for path in hub.config.get("extra_files",[]):
                collect.register_file(hub,path)
            for source in hub.config.get("structured_sources",[]):
                collect.register_file(hub,source["path"],source["project_id"])
            notes=hub.notes/"notes"
            if notes.exists():
                for path in notes.glob("*.md"):
                    collect.register_file(hub,path)
        entries=hub.config.get("project_roots",[])
        interval=max(2,hub.config.get("reconcile_seconds",180)/max(1,len(entries)))
        if entries and clock-self.last_scan>=interval:
            entry=entries[self.scan_index%len(entries)]
            result=collect.scan_documents(hub,entry)
            coverage=hub.value("coverage",{})
            coverage.setdefault("documents",{})[entry["path"]]=result
            hub.set_value("coverage",coverage)
            self.scan_index+=1
            hub.set_value("scan_index",self.scan_index)
            self.last_scan=clock
        if clock-self.last_sessions>=hub.config.get("reconcile_seconds",180):
            collect.discover_sessions(hub)
            self.last_sessions=clock
        result=None
        batch_started=time.monotonic()
        jobs=0
        while jobs<5 and time.monotonic()-batch_started<1.5:
            if jobs and (hub.value("paused",False) or recording_busy(hub)):
                break
            latest=drain_one(hub)
            if latest is None:
                break
            result=latest
            jobs+=1
        if clock-self.last_git>=300:
            snapshot_git(hub)
            self.last_git=clock
        state["last_job"]=result
        state["batch_jobs"]=jobs
        state["heartbeat"]=time.time()
        hub.set_value("worker",state)
        return state


def serve_commands(hub):
    from project_store import Conflict
    hub.recover_note_write()
    with hub.connect() as conn:
        commands=[dict(r) for r in conn.execute("SELECT * FROM commands WHERE state='pending' ORDER BY created_at LIMIT 5")]
    for command in commands:
        body,who=json.loads(command["body"]),json.loads(command["who"])
        try:
            if command["action"]=="note":
                body["command_id"]=command["id"]
                body.setdefault("id",command["id"])
                result=hub.save_note(body,who)
            else:
                result=hub.confirm(body.get("id"),body.get("revision"),who,command["id"])
            with hub.connect(write=True) as conn:
                conn.execute("UPDATE commands SET state='complete',result=? WHERE id=?",(json.dumps(result,ensure_ascii=False),command["id"]))
        except (ValueError,OSError,PermissionError,KeyError,TypeError) as exc:
            error={"message":str(exc) if isinstance(exc,ValueError) else type(exc).__name__,"conflict":isinstance(exc,Conflict)}
            with hub.connect(write=True) as conn:
                conn.execute("UPDATE commands SET state='failed',error=? WHERE id=?",(json.dumps(error,ensure_ascii=False),command["id"]))


def consume_signals(hub):
    from session_jsonl import is_jsonl, canonical
    folder=hub.root/"signals"
    if not folder.exists():
        return
    from knowledge_hub import stable_id
    for signal in list(folder.glob("*.json"))[:20]:
        try:
            packet=json.loads(signal.read_text(encoding="utf-8"))
            provider=packet["provider"]
            base=Path(hub.config["session_providers"][provider])
            base=base.parent if provider=="codex" else base
            path=Path(packet["path"]).absolute()
            if provider not in {"codex","claude-code"} or not is_jsonl(path) or not path.is_relative_to(base.absolute()) or path.is_symlink():
                raise ValueError("Источник сигнала не подключён")
            if any(p.is_symlink() or (hasattr(p,"is_junction") and p.is_junction()) for p in path.parents if p.is_relative_to(base.absolute())):
                raise ValueError("Источник является ссылкой")
            stat=path.stat()
            identity=stable_id(provider,str(canonical(path)))
            signature=f"{stat.st_mtime_ns}:{stat.st_size}"
            with hub.connect(write=True) as conn:
                old=conn.execute("SELECT id FROM streams WHERE provider=? AND session_id=? ORDER BY CASE WHEN id=? THEN 0 ELSE 1 END,id LIMIT 1",(provider,str(packet["session_id"]),identity)).fetchone()
                if old:
                    identity=old["id"]
                conn.execute("INSERT OR IGNORE INTO streams(id,path,provider,session_id,cwd) VALUES (?,?,?,?,?)",(identity,str(path),provider,str(packet["session_id"]),str(packet.get("cwd", ""))))
                conn.execute("UPDATE streams SET path=? WHERE id=?",(str(path),identity))
                hub.enqueue(identity,"stream",{"stream_id":identity},signature,delay=0,conn=conn)
            signal.unlink(missing_ok=True)
        except (OSError,ValueError,KeyError,TypeError):
            # Invalid signals are quarantined, with no tool/prompt text interpreted.
            target=hub.root/"rejected-signals"/signal.name
            target.parent.mkdir(exist_ok=True)
            if signal.exists():
                os.replace(signal,target)


def main():
    if sys.stdout is not None:
        sys.stdout.reconfigure(encoding="utf-8")
    parser=argparse.ArgumentParser()
    parser.add_argument("--home")
    parser.add_argument("--once",action="store_true")
    parser.add_argument("--extract")
    parser.add_argument("--max-bytes",type=int,default=10*1024*1024)
    args=parser.parse_args()
    if args.extract:
        below_normal()
        try:
            print(json.dumps(extract(Path(args.extract),args.max_bytes),ensure_ascii=False))
        except Exception as exc:
            print(json.dumps({"error":str(exc) if isinstance(exc,ValueError) else type(exc).__name__},ensure_ascii=False))
            return 1
        return 0
    hub=Hub(args.home,initialize=True)
    logging.basicConfig(handlers=[RotatingFileHandler(hub.root/"worker.log",maxBytes=1024*1024,backupCount=2,encoding="utf-8")],level=logging.WARNING)
    if not hub.config.get("board"):
        raise ValueError("Сначала выполните knowledge_cli.py init")
    try:
        with OperationLock(hub.root/"worker.lock"), contextlib.ExitStack() as connections:
            # Keep idle, autocommit handles open. SQLite otherwise checkpoints
            # WAL on every last-close, briefly excluding new readers on Windows.
            for path in (hub.path,Path(hub.config["board"])):
                keeper=connections.enter_context(contextlib.closing(sqlite3.connect(path,isolation_level=None,timeout=3)))
                keeper.execute("PRAGMA user_version").fetchone()
            worker=Worker(hub)
            while True:
                try:
                    result=worker.tick()
                    if args.once:
                        print(json.dumps(result,ensure_ascii=False))
                        return 0
                except Exception as exc:
                    logging.exception("knowledge collector cycle failed")
                    hub.set_value("worker",{"pid":os.getpid(),"heartbeat":time.time(),"error":type(exc).__name__})
                    if args.once:
                        raise
                time.sleep(max(1,hub.config.get("poll_seconds",2)))
    except OperationLockError:
        print("Worker уже работает")
        return 0


if __name__=="__main__":
    raise SystemExit(main())
