"""Bounded discovery and read-only adapters. No models or remote requests."""
from __future__ import annotations

import contextlib
import datetime as dt
from bisect import bisect_right
import json
import os
import re
import sqlite3
from pathlib import Path

from knowledge_hub import META, atomic, now, sha, stable_id
from project_session_catalog import INJECTED, clean, redact, text_content
from session_jsonl import canonical, session_files, materialize
from session_paths import codex_state_path

SUFFIXES = {".md", ".txt", ".rst", ".docx", ".pdf"}
SKIP = {".git", "node_modules", "__pycache__", "venv", ".venv", "build", "dist", "bin", "obj", "temp", "tmp", "logs", "sessions", "internal", "backups", "outputs", "work"}
SECRET_NAME = re.compile(r"(?i)(?:^|[._-])(?:secret|credential|password|passwd|token|private|api.?key|\.env)(?:[._-]|$)")
SECRET_VALUE = re.compile(r"(?im)((?<![\w])[\"']?(?:api[_ -]?key|access[_ -]?token|authorization|client[_ -]?secret|password|passwd|pwd|пароль|токен)[\"']?\s*[:=]\s*[\"']?)[^\s\"',;\]}]{1,}")
PRIVATE = re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----.*?-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", re.S)
BEARER = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/-]{16,}")
CREDENTIAL_URL = re.compile(r"(?i)\b((?:https?|postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis)://)[^/\s:@]+:[^@\s/]+@")
DOC_DIRS = ("docs", "discussion/decisions", "decisions", "documentation", "Документация", "База знаний", "поставка-руководству/Документация/База знаний")


def shared_workspace_roots(config=None, projects=()):
    """Only explicit exclusions identify a shared root, never nesting alone."""
    raw = os.environ.get("BLATERO_WORKSPACE_ROOT", "").strip()
    if raw:
        return [Path(raw).absolute()]
    config = config or {}
    if "shared_workspace_roots" in config:
        return sorted({Path(p).absolute() for p in config["shared_workspace_roots"] if p}, key=str)
    # Legacy migration requires an actual saved exclusion as well as nesting.
    paths = {Path(p["workspace"]).absolute() for p in projects if p.get("workspace")}
    selected = {Path(r["path"]).absolute() for r in config.get("project_roots", [])}
    registered = {Path(p["workspace"]).absolute() for p in projects
                  if p.get("workspace") and p.get("name") in config.get("excluded_workspaces", [])
                  and Path(p["workspace"]).absolute() not in selected
                  and any(q != Path(p["workspace"]).absolute() and q.is_relative_to(Path(p["workspace"]).absolute()) for q in paths)}
    return sorted(registered, key=str)


def common_workspace_root(config=None, projects=()):
    roots = shared_workspace_roots(config, projects)
    return roots[0] if len(roots) == 1 else None


def sanitize(text):
    text = PRIVATE.sub("[секрет скрыт]", text)
    text = BEARER.sub("Bearer [секрет скрыт]",text)
    text = CREDENTIAL_URL.sub(r"\1[секрет скрыт]@",text)
    return SECRET_VALUE.sub(r"\1[секрет скрыт]", redact(text))


def safe_path(path, roots, *, suffixes=SUFFIXES):
    if str(path).startswith(("\\\\","//")) or "://" in str(path):
        raise ValueError("Нужен выбранный локальный файл")
    path = Path(path).absolute()
    if path.suffix.lower() not in suffixes or path.name.startswith((".", "~$")) or SECRET_NAME.search(path.name):
        raise ValueError("Файл исключён из каталога знаний")
    # Reject unrelated trees before filesystem resolution (dead network paths can block).
    selected = [Path(root).absolute() for root in roots if path == Path(root).absolute() or path.is_relative_to(Path(root).absolute())]
    if not selected:
        raise ValueError("Файл находится вне выбранных источников")
    nearest=max(selected,key=lambda r:len(r.parts))
    # Never follow symbolic links or Windows directory junctions to an unselected tree.
    for part in (path, *[p for p in path.parents if p==nearest or p.is_relative_to(nearest)]):
        if part.is_symlink() or (hasattr(part, "is_junction") and part.is_junction()):
            raise ValueError("Ссылки и junction не индексируются")
    resolved = path.resolve()
    selected = [root for root in selected if resolved == root or resolved.is_relative_to(root)]
    if not selected:
        raise ValueError("Файл находится вне выбранных источников")
    nearest = max(selected,key=lambda r:len(r.parts))
    relative = resolved.relative_to(nearest)
    if any(part.lower() in SKIP or part.startswith(".") for part in relative.parts[:-1]):
        raise ValueError("Служебный каталог исключён")
    return resolved


@contextlib.contextmanager
def ro(path):
    conn = sqlite3.connect(Path(path).resolve().as_uri()+"?mode=ro", uri=True, timeout=1)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def scope_for(cwd, projects, config=None):
    if not cwd:
        return None
    if str(cwd).startswith(("\\\\","//")):
        return None
    target = Path(cwd).absolute()
    roots = shared_workspace_roots(config, projects)
    candidates = [(len(Path(p["workspace"]).parts), p["id"]) for p in projects if p.get("workspace") and
                  target.is_relative_to(Path(p["workspace"]).absolute())
                  and Path(p["workspace"]).absolute() not in roots]
    if not candidates:
        return None
    maximum = max(c[0] for c in candidates)
    found = {c[1] for c in candidates if c[0] == maximum}
    return found.pop() if len(found) == 1 else None


def configure(hub, board, notes_root, *, history=True):
    """Explicit CLI installation: register document trees, never all work files."""
    with ro(board) as conn:
        projects = [dict(r) for r in conn.execute("SELECT * FROM projects")]
    roots = []
    excluded = []
    shared = shared_workspace_roots(hub.config, projects)
    for project in projects:
        raw = project.get("workspace") or ""
        path = Path(raw).absolute() if raw and not str(raw).startswith(("\\\\", "//")) else None
        if (not path or not path.is_dir() or path in shared
                or path == path.parent or path == Path.home().absolute()
                or path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction())):
            excluded.append(project["name"])
            continue
        path = path.resolve()
        roots.append({"path": str(path), "project_id": project["id"], "name": project["name"]})
    config = {"version": 1, "board": str(Path(board).resolve()), "notes_root": str(Path(notes_root).resolve()),
              "shared_workspace_roots": [str(p) for p in shared],
              "project_roots": roots, "extra_files": [], "poll_seconds": 2, "reconcile_seconds": 180,
              "history": history, "session_providers": {}, "recording_root": str(Path(board).parent.parent / "sessions"),
              "excluded_workspaces": excluded, "max_file_bytes": 10*1024*1024}
    config["structured_sources"]=[{"path":str(Path(entry["path"])/"_meta/roadmap-data.json"),"project_id":entry["project_id"]} for entry in roots if (Path(entry["path"])/"_meta/roadmap-data.json").is_file()]
    if history:
        home = Path.home()
        config["session_providers"] = {"codex": str(codex_state_path()),
                                       "claude-code": str(home / ".claude/projects"),
                                       "hermes": str(home / ".hermes/state.db"),
                                       "opencode": str(home / ".local/share/opencode/opencode.db")}
    atomic(hub.config_path, json.dumps(config, ensure_ascii=False, indent=2)+"\n")
    hub.config, hub.notes = config, Path(config["notes_root"])
    return config


def register_file(hub, path, project=None, task=None, scan_root="", *, explicit=False):
    roots = [r["path"] for r in hub.config.get("project_roots", [])] + hub.config.get("extra_files", []) + [str(hub.notes)]
    if hub.config.get("recording_root"):
        roots.append(hub.config["recording_root"])
    structured={str(Path(r["path"]).absolute()) for r in hub.config.get("structured_sources",[])}
    path = safe_path(path, roots,suffixes=SUFFIXES|({".json"} if str(Path(path).absolute()) in structured else set()))
    identity = stable_id("file", str(path))
    binding = hub.value("file_binding:" + identity, {})
    if (not explicit or not project) and binding:
        project, task, explicit = binding["project_id"], binding.get("task_id"), True
    physical_project = scope_for(str(path.parent),[{"workspace":r["path"],"id":r["project_id"]} for r in hub.config.get("project_roots",[])], hub.config)
    # The application stores different clients' meetings under one data root.
    if hub.config.get("recording_root") and path.is_relative_to(Path(hub.config["recording_root"]).absolute()):
        physical_project = None
    if explicit and project and physical_project and physical_project != project:
        raise ValueError("Файл относится к другому проекту; проверьте привязку")
    if explicit and project:
        physical_project=project
    if project and physical_project != project:
        task=None
    project=physical_project
    if explicit and project and binding != {"project_id": project, "task_id": task}:
        hub.set_value("file_binding:" + identity, {"project_id": project, "task_id": task})
    try:
        stat = path.stat()
        signature = f"{stat.st_mtime_ns}:{stat.st_size}"
    except FileNotFoundError:
        signature = "missing"
    with hub.connect() as conn:
        old = conn.execute("SELECT * FROM files WHERE id=?", (identity,)).fetchone()
        queued = conn.execute("SELECT signature FROM jobs WHERE id=?",(identity,)).fetchone()
    if task:
        with hub.connect(write=True) as conn:
            conn.execute("INSERT OR IGNORE INTO item_links VALUES (?,?)",(identity,task))
    if old and old["task_id"] and task and old["task_id"] != task:
        with hub.connect(write=True) as conn:
            conn.execute("INSERT OR IGNORE INTO item_links VALUES (?,?)",(identity,old["task_id"]))
        task=None
    if old and old["signature"] == signature and old["project_id"] == project and (not task or old["task_id"] == task):
        return
    if old and queued and queued[0]==signature and old["project_id"]==project and (not task or old["task_id"]==task):
        return
    with hub.connect(write=True) as conn:
        conn.execute("INSERT INTO files VALUES (?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET project_id=excluded.project_id,task_id=excluded.task_id,seen_at=excluded.seen_at",
                     (identity, str(path), project, task, old["signature"] if old else "", now(), scan_root))
        hub.enqueue(identity, "file", {"path": str(path), "project_id": project, "task_id": task}, signature,conn=conn)
        if old and old["signature"] != signature:
            conn.execute("UPDATE items SET freshness=? WHERE id=?",("missing" if signature=="missing" else "pending",identity))
            hub.invalidate(identity,conn)


def scan_documents(hub, entry):
    root = Path(entry["path"])
    candidates = []
    if root.is_dir():
        candidates.extend(p for p in root.iterdir() if p.is_file() and p.suffix.lower() in SUFFIXES)
    visited, truncated = 0, False
    for folder in DOC_DIRS:
        selected = root / folder
        if not selected.is_dir():
            continue
        for current, dirs, names in os.walk(selected, followlinks=False):
            dirs[:] = sorted(d for d in dirs if d.lower() not in SKIP and not d.startswith(".") and not (Path(current)/d).is_symlink() and not (hasattr(Path(current)/d,"is_junction") and (Path(current)/d).is_junction()))
            if len(Path(current).relative_to(selected).parts) >= 6:
                dirs.clear()
            visited += 1
            candidates.extend(Path(current)/name for name in sorted(names) if Path(name).suffix.lower() in SUFFIXES)
            if visited >= 300 or len(candidates) >= 3000:
                truncated = True
                break
        if truncated:
            break
    for path in sorted(set(candidates))[:3000]:
        try:
            register_file(hub, path, entry.get("project_id"), scan_root=str(root))
        except (ValueError, OSError):
            continue
    # Registered files are checked separately too, so deletion is detected even after a rename.
    return {"files": min(len(set(candidates)),3000), "truncated": truncated, "scanned_at": now()}


def export_snapshot(hub, item):
    folder = "projects" if item["kind"] == "passport" else "tasks" if item["kind"] == "task" else "knowledge"
    path = hub.notes / "generated" / folder / (item["id"] + ".md")
    content = META + json.dumps({k:item.get(k) for k in ("id","project_id","task_id","kind","state","content_hash")}, ensure_ascii=False) + " -->\n\n# " + item["title"] + "\n\n" + item["body"] + "\n"
    if not path.exists() or path.read_text(encoding="utf-8") != content:
        atomic(path, content)


def mirror_board(hub, pulse=None):
    with ro(hub.config["board"]) as conn:
        projects = [dict(r) for r in conn.execute("SELECT * FROM projects")]
        tasks = [dict(r) for r in conn.execute("SELECT * FROM tasks WHERE merged_into IS NULL")]
        knowledge = [dict(r) for r in conn.execute("SELECT k.* FROM knowledge k JOIN tasks t ON t.id=k.work_item_id WHERE t.merged_into IS NULL")]
        docs = [dict(r) for r in conn.execute("SELECT * FROM project_documents")]
        sessions = [dict(r) for r in conn.execute("SELECT * FROM imported_sessions")]
        bindings = [dict(r) for r in conn.execute("SELECT json_extract(event_json,'$.source.system') AS system,json_extract(event_json,'$.source.session_id') AS session_id,json_extract(event_json,'$.emitted_at') AS since,work_item_id,json_extract(event_json,'$.project_id') AS project_id FROM events WHERE event_type='session.started' AND work_item_id IS NOT NULL AND state='applied' ORDER BY received_at")]
        materials = [dict(r) for r in conn.execute("SELECT * FROM materials")]
        material_links = [dict(r) for r in conn.execute("SELECT * FROM material_links")]
        sources = [dict(r) for r in conn.execute("SELECT s.* FROM sources s JOIN tasks t ON t.id=s.work_item_id WHERE t.merged_into IS NULL")]
    shared = shared_workspace_roots(hub.config, projects)
    filtered_roots = [r for r in hub.config.get("project_roots", []) if Path(r["path"]).absolute() not in shared]
    if "shared_workspace_roots" not in hub.config or filtered_roots != hub.config.get("project_roots", []):
        hub.config.setdefault("shared_workspace_roots", [str(p) for p in shared])
        hub.config["project_roots"] = filtered_roots
        atomic(hub.config_path, json.dumps(hub.config, ensure_ascii=False, indent=2)+"\n")
    hub.set_value("projects", projects)
    hub.set_value("bindings", bindings)
    if hub.config.get("auto_project_documents",True):
        registered={(r["project_id"],str(Path(r["path"]).absolute())) for r in hub.config.get("project_roots",[])}
        added=[]
        shared=shared_workspace_roots(hub.config, projects)
        if shared:
            for project in projects:
                if not project.get("workspace"):
                    continue
                path=Path(project["workspace"]).absolute()
                if ((project["id"],str(path)) not in registered and path not in shared
                        and any(path.is_relative_to(root) for root in shared) and path.is_dir()
                        and not path.is_symlink() and not (hasattr(path,"is_junction") and path.is_junction())):
                    added.append({"project_id":project["id"],"path":str(path),"name":project["name"]})
        if added:
            hub.config.setdefault("project_roots",[]).extend(added)
            atomic(hub.config_path,json.dumps(hub.config,ensure_ascii=False,indent=2)+"\n")
    lookup = {t["id"]:t for t in tasks}
    changed = 0
    items = []
    for p in projects:
        body = sanitize(p["description"] or "Описание проекта ещё не записано.") + "\n\nРабочая папка: " + p["workspace"]
        items.append({"id": "project-"+p["id"], "project_id":p["id"], "task_id":None, "kind":"passport", "title":sanitize(p["name"]), "body":body,
                      "locator":"blatero:project/"+p["id"], "metadata":{"origin":"board","generated":True}})
    for t in tasks:
        body = "\n\n".join(label+":\n"+sanitize(t.get(field) or "Ещё не записано") for label,field in (("Суть","goal"),("Метод","method"),("Почему выбран","rationale"),("Следующий шаг","next_step"),("Статус","status")))
        if t.get("closed_at"):
            body += "\n\nПоследнее закрытие:\n" + sanitize(t["closed_at"]) + "\n" + sanitize(t.get("closed_reason") or "Причина не записана")
        items.append({"id":"task-"+t["id"], "project_id":t["project_id"], "task_id":t["id"], "kind":"task", "title":sanitize(t["title"]), "body":body,
                      "locator":"blatero:task/"+t["id"], "metadata":{"origin":"board", "generated":True, "task_revision":t["revision"], "historical":t["origin"]=="history"}})
    for k in knowledge:
        t = lookup.get(k["work_item_id"])
        if not t:
            continue
        items.append({"id":"knowledge-"+k["id"], "project_id":t["project_id"], "task_id":t["id"], "kind":k["kind"],
                      "title":t["title"], "body":sanitize(k["text"]), "state":k["state"], "locator":"blatero:knowledge/"+k["id"], "metadata":{"origin":"board"}})
    for m in materials:
        material = json.loads(m["data_json"])
        linked = {link["work_item_id"] for link in material_links if link["material_id"]==m["id"]}
        task = next(iter(linked)) if len(linked)==1 else None
        project_ids = {lookup[t]["project_id"] for t in linked if t in lookup and lookup[t]["project_id"]}
        project = next(iter(project_ids)) if len(project_ids)==1 else None
        # A provider's workspace proposal remains unbound until a task link confirms it.
        items.append({"id":"material-"+m["id"],"project_id":project,"task_id":task,"kind":"material",
                      "title":sanitize(material.get("title") or "Материал"),"body":sanitize(material.get("summary") or "Описание ещё не записано"),
                      "locator":material.get("locator", ""),"content_hash":m["snapshot_sha256"],
                      "freshness":"current" if m["available"] else "missing","metadata":{"origin":"board","provider":m["provider"],"material_id":m["id"],"summary_only":True}})
        session=material.get("session")
        if m["provider"]=="blatero" and session and Path(session).name==session and hub.config.get("recording_root"):
            folder=Path(hub.config["recording_root"])/session
            for path in [folder/"report.md",*list(folder.glob("transcript*.md"))[:100]]:
                if path.is_file():
                    try:
                        register_file(hub,path,project,task,explicit=True)
                    except (OSError,ValueError):
                        pass
    for start in range(0,len(items),100):
        exports=[]
        with hub.connect(write=True) as conn:
            for item in items[start:start+100]:
                item["content_hash"] = sha(item["body"])
                if hub.put(item, conn):
                    changed += 1
                    if item["kind"]!="material":
                        exports.append(item)
        # Disk flushes never hold the index's writer transaction.
        for item in exports:
            export_snapshot(hub,item)
        if pulse:
            pulse()
    for doc in docs:
        try:
            register_file(hub, doc["locator"], doc["project_id"],explicit=True)
        except (OSError, ValueError):
            pass
    for source in sources:
        task = lookup[source["work_item_id"]]
        try:
            register_file(hub,source["locator"],task["project_id"],task["id"],explicit=True)
        except (OSError,ValueError):
            pass
    # Imported session attribution is evidence; a common launch directory is not.
    hub.set_value("session_links", {r["system"]+":"+r["session_id"]:{"project_id":r["project_id"],"task_id":r["work_item_id"],"title":r["title"]} for r in sessions})
    hub.set_value("material_count", len(materials))
    return changed


def discover_sessions(hub):
    counts = {}
    for provider, location in hub.config.get("session_providers", {}).items():
        path = Path(location)
        try:
            if not path.exists():
                counts[provider] = {"available":False, "error":"Источник не найден"}
                continue
            found = []
            if provider == "codex":
                with ro(path) as conn:
                    rows = conn.execute("SELECT id,rollout_path,cwd,title,source FROM threads").fetchall()
                lookup = None
                for row in rows:
                    if row["source"] not in {"cli","vscode","desktop"}:
                        continue
                    source = Path(row["rollout_path"].removeprefix("\\\\?\\"))
                    if canonical(source).is_file():
                        source = canonical(source)
                    if not source.is_file():
                        compressed = Path(str(canonical(source)) + ".zst")
                        if compressed.is_file():
                            source = compressed
                        else:
                            if lookup is None:
                                lookup = {}
                                for folder in (path.parent/"sessions", path.parent/"archived_sessions"):
                                    for candidate in session_files(folder):
                                        match = re.search(r'([0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12})\.jsonl$', canonical(candidate).name, re.I)
                                        if match and (match[1] not in lookup or candidate.suffix == '.jsonl'):
                                            lookup[match[1]] = candidate
                            source = lookup.get(row["id"], source)
                    if source.is_file():
                        found.append((source, row["id"], row["cwd"] or ""))
            elif provider == "claude-code":
                for source in session_files(path, exclude={"subagents", "workflows"}):
                    if not set(source.relative_to(path).parts) & {"subagents", "workflows"} and not source.name.startswith("agent-"):
                        found.append((source, canonical(source).stem, ""))
                    if len(found)>10000:
                        break
            else:
                discover_sqlite(hub, provider, path)
                counts[provider] = {"available":True, "kind":"sqlite", "checked_at":now()}
                continue
            entries=[]
            for source, sid, cwd in found:
                if source.is_symlink():
                    continue
                signature = f"{source.stat().st_mtime_ns}:{source.stat().st_size}"
                identity = stable_id(provider,str(canonical(source)))
                entries.append((identity,str(source),provider,sid,cwd,signature))
            with hub.connect(write=True) as conn:
                for identity,source,provider,sid,cwd,signature in entries:
                    old = conn.execute("SELECT id,signature FROM streams WHERE provider=? AND session_id=? ORDER BY CASE WHEN id=? THEN 0 ELSE 1 END,id LIMIT 1", (provider,sid,identity)).fetchone()
                    if old:
                        identity = old["id"]
                    conn.execute("INSERT OR IGNORE INTO streams(id,path,provider,session_id,cwd) VALUES (?,?,?,?,?)", (identity,source,provider,sid,cwd))
                    conn.execute("UPDATE streams SET path=? WHERE id=?", (source,identity))
                    if not old or old["signature"] != signature:
                        hub.enqueue(identity,"stream",{"stream_id":identity},signature,conn=conn)
            counts[provider] = {"available":True,"files":len(found),"checked_at":now()}
        except (sqlite3.Error, OSError, ValueError) as exc:
            counts[provider] = {"available":False,"error":type(exc).__name__}
    coverage = hub.value("coverage", {})
    coverage["sessions"] = counts
    coverage["unsupported"] = ["HerdR: источник истории не подключён", "Закрытые приложения без экспорта/API", "OCR и сканы PDF"]
    hub.set_value("coverage", coverage)


def timestamp(value):
    if isinstance(value,(int,float)):
        return value/1000 if value>10**12 else value
    try:
        return dt.datetime.fromisoformat(str(value).replace("Z","+00:00")).timestamp()
    except (ValueError,TypeError):
        return 0


def session_scope(hub, provider, sid, cwd, cached=None, stamp=None):
    cache = cached or {"links":hub.value("session_links",{}),"bindings":hub.value("bindings",[]),"projects":hub.value("projects",[])}
    links = cache["links"]
    if "_timelines" not in cache:
        timelines={}
        for row in cache["bindings"]:
            timelines.setdefault(row["system"]+":"+row["session_id"],[]).append(row)
        cache["_timelines"]={key:sorted(rows,key=lambda r:timestamp(r["since"])) for key,rows in timelines.items()}
        cache["_times"]={key:[timestamp(r["since"]) for r in rows] for key,rows in cache["_timelines"].items()}
    key=provider+":"+sid
    index=bisect_right(cache["_times"].get(key,[]),timestamp(stamp))-1
    explicit=cache["_timelines"][key][index] if index>=0 else None
    if explicit:
        return explicit["project_id"],explicit["work_item_id"]
    if provider+":"+sid in links:
        link = links[provider+":"+sid]
        return link["project_id"],link["task_id"]
    scopes=cache.setdefault("_cwd",{})
    if cwd not in scopes:
        scopes[cwd]=scope_for(cwd,cache["projects"],hub.config)
    return scopes[cwd], None


def conversation(text, role):
    text = clean(text)
    if not text or (role == "user" and text.startswith(INJECTED)):
        return ""
    return sanitize(text)


def read_stream(hub, identity):
    with hub.connect() as conn:
        row = dict(conn.execute("SELECT * FROM streams WHERE id=?",(identity,)).fetchone())
    path = Path(row["path"])
    before = path.stat()
    readable = materialize(path, hub.root/"session-cache")
    logical_size = readable.stat().st_size
    cache = {"links":hub.value("session_links",{}),"bindings":hub.value("bindings",[]),"projects":hub.value("projects",[])}
    partial = False
    replaced = False
    with readable.open("rb") as stream:
        length = int(row["prefix"].split(":",1)[0]) if row["prefix"] else min(128,logical_size)
        prefix = str(length)+":"+sha(stream.read(length))
        stream.seek(max(0,row["offset"]-128))
        old_anchor=sha(stream.read(min(row["offset"],128)))
        if (row["prefix"] and prefix != row["prefix"]) or logical_size < row["offset"] or (row["anchor"] and old_anchor!=row["anchor"]):
            row.update(offset=0,line=0,discard=0,generation=row["generation"]+1)
            replaced = True
        stream.seek(row["offset"])
        budget = 1024*1024
        items = []
        while budget>0:
            start = stream.tell()
            # Finish a normal line even when the batch budget ends in its middle.
            # Only the per-line cap identifies oversized records, not the remaining batch.
            raw = stream.readline(512*1024)
            if not raw:
                break
            budget -= len(raw)
            if not raw.endswith(b"\n"):
                if len(raw) < 512*1024:
                    if path.suffix == '.zst':
                        try:
                            json.loads(raw)
                        except ValueError as exc:
                            raise ValueError('Незавершённая строка в архиве JSONL.zst') from exc
                    else:
                        stream.seek(start)
                        partial = True
                        break
                else:
                    row["discard"] = 1
                    continue
            row["line"] += 1
            if row["discard"]:
                row["discard"] = 0
                continue
            try:
                event = json.loads(raw)
                if row["provider"] == "codex":
                    payload = event.get("payload",{})
                    if event.get("type")=="session_meta":
                        row["cwd"] = payload.get("cwd") or row["cwd"]
                    if event.get("type")!="response_item" or payload.get("type")!="message" or payload.get("channel")=="analysis":
                        continue
                    role,text = payload.get("role"),text_content(payload.get("content"))
                else:
                    row["cwd"] = event.get("cwd") or row["cwd"]
                    if event.get("isCompactSummary"):
                        continue
                    role,text = event.get("type"),text_content(event.get("message",{}).get("content"))
                if role not in {"user","assistant"}:
                    continue
                text = conversation(text,role)
                if not text:
                    continue
                project,task = session_scope(hub,row["provider"],row["session_id"],row["cwd"],cache,event.get("timestamp"))
                items.append({"id":stable_id(identity,row["generation"],start),"project_id":project,"task_id":task,"kind":"session",
                              "title":row["provider"]+" · "+role+" · "+text[:110].replace("\n"," "),"body":text[:32000],
                              "locator":str(path)+":"+str(row["line"]),"content_hash":sha(raw),
                              "metadata":{"provider":row["provider"],"session_id":row["session_id"],"role":role,"truncated":len(text)>32000,"byte_offset":start}})
            except (ValueError, TypeError, AttributeError):
                # Individual malformed messages must not stop all subsequent sessions.
                continue
        row["offset"] = stream.tell()
        stream.seek(max(0,row["offset"]-128))
        anchor=sha(stream.read(min(row["offset"],128)))
    # Commit small message batches before the cursor. After a crash, stable IDs
    # replay already committed messages without duplication; none can be skipped.
    if replaced:
        with hub.connect(write=True) as conn:
            conn.execute("UPDATE items SET freshness='missing' WHERE kind='session' AND json_extract(metadata,'$.provider')=? AND json_extract(metadata,'$.session_id')=?", (row["provider"],row["session_id"]))
    for start in range(0,len(items),100):
        with hub.connect(write=True) as conn:
            for item in items[start:start+100]:
                hub.put(item,conn)
    with hub.connect(write=True) as conn:
        conn.execute("UPDATE streams SET offset=?,prefix=?,generation=?,line=?,discard=?,cwd=?,signature=?,anchor=? WHERE id=?",
                     (row["offset"],prefix,row["generation"],row["line"],row["discard"],row["cwd"],f"{before.st_mtime_ns}:{before.st_size}",anchor,identity))
    more = row["offset"] < logical_size and not partial
    if readable != path and not more:
        readable.unlink(missing_ok=True)
    return more, len(items)


def discover_sqlite(hub, provider, path):
    with ro(path) as conn:
        if provider == "hermes":
            rows = conn.execute("SELECT id,cwd,title,last_activity_at AS stamp FROM sessions WHERE parent_session_id IS NULL").fetchall()
        else:
            rows = conn.execute("SELECT id,directory AS cwd,title,time_updated AS stamp FROM session WHERE parent_id IS NULL").fetchall()
    versions = hub.value("sqlite_versions:"+provider,{})
    with hub.connect(write=True) as conn:
        for row in rows:
            if versions.get(row["id"]) == str(row["stamp"]):
                continue
            identity = stable_id(provider,row["id"])
            hub.enqueue(identity,"sql_session",{"provider":provider,"path":str(path),"session_id":row["id"],"cwd":row["cwd"] or "","title":row["title"] or "","offset":0},str(row["stamp"]),conn=conn)


def read_sql_session(hub, payload):
    provider,path,sid = payload["provider"],Path(payload["path"]),payload["session_id"]
    offset = payload.get("offset",0)
    with ro(path) as conn:
        if provider == "hermes":
            rows = conn.execute("SELECT id,role,content,timestamp FROM messages WHERE session_id=? AND role IN ('user','assistant') ORDER BY id LIMIT 100 OFFSET ?",(sid,offset)).fetchall()
        else:
            rows = conn.execute("SELECT p.id,m.data,p.data AS part FROM message m JOIN part p ON p.message_id=m.id WHERE m.session_id=? ORDER BY m.time_created,p.time_created,p.id LIMIT 100 OFFSET ?",(sid,offset)).fetchall()
    cached={"links":hub.value("session_links",{}),"bindings":hub.value("bindings",[]),"projects":hub.value("projects",[])}
    count = 0
    with hub.connect(write=True) as conn:
        for row in rows:
            try:
                if provider == "hermes":
                    role,text = row["role"],row["content"] or ""
                    stamp=row["timestamp"]
                else:
                    meta,part = json.loads(row["data"]),json.loads(row["part"])
                    if part.get("type")!="text":
                        continue
                    role,text = meta.get("role"),part.get("text","")
                    stamp=meta.get("time",{}).get("created")
                if role not in {"user","assistant"}:
                    continue
                text = conversation(text,role)
                if not text:
                    continue
                project,task = session_scope(hub,provider,sid,payload["cwd"],cached,stamp)
                item = {"id":stable_id(provider,sid,row["id"]),"project_id":project,"task_id":task,"kind":"session",
                        "title":provider+" · "+role+" · "+(payload["title"] or text[:110]),"body":text[:32000],
                        "locator":str(path)+"#"+sid+"/"+str(row["id"]),"content_hash":sha(text),
                        "metadata":{"provider":provider,"session_id":sid,"role":role,"truncated":len(text)>32000}}
                hub.put(item,conn)
                count += 1
            except (ValueError, TypeError, AttributeError):
                continue
    payload["offset"] = offset+len(rows)
    return len(rows)==100,count
