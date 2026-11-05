"""Local knowledge catalogue. Originals and approval are separate from freshness."""
from __future__ import annotations

import contextlib
import datetime as dt
import hashlib
import json
import os
import re
import sqlite3
import uuid
from pathlib import Path

import app_paths
from operation_lock import OperationLock
from project_store import Conflict

VERSION = 5
# Version 6 was used only by rc.6 for an additive extension; never reuse it
# for an incompatible format.
PREVIEW_VERSION = 6
KINDS = {"passport", "task", "decision", "fact", "constraint", "open_question", "document", "session", "material"}
META = "<!-- knowledge-hub "


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="milliseconds")


def sha(value):
    return hashlib.sha256(value if isinstance(value, bytes) else value.encode("utf-8")).hexdigest()


def stable_id(*values):
    return sha(json.dumps(values, ensure_ascii=False))[:40]


def _has_note_extension(conn):
    columns = [tuple(row)[1:3] for row in conn.execute("PRAGMA table_info(note_files)")]
    if columns != [("id", "TEXT"), ("sha256", "TEXT")]:
        return False
    row = conn.execute("SELECT value FROM state WHERE key='index_identity'").fetchone()
    return bool(row and re.fullmatch(r'"[0-9a-f]{32}"', row[0]))


def atomic(path, text, *, before_replace=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        if before_replace is not None:
            before_replace()
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def runtime_root():
    explicit = os.environ.get("BLATERO_KNOWLEDGE_HOME")
    if explicit:
        return Path(explicit).resolve()
    if os.environ.get("BLATERO_DATA_DIR"):
        return app_paths.DATA_ROOT / ".knowledge"
    pointer=app_paths.APP_ROOT/".knowledge-hub-path"
    if pointer.exists():
        return Path(pointer.read_text(encoding="utf-8").strip()).resolve()
    return Path(os.environ.get("LOCALAPPDATA", str(app_paths.DATA_ROOT))) / "knowledge-hub"


class Hub:
    def __init__(self, root=None, *, initialize=False):
        self.root = Path(root or runtime_root()).resolve()
        self.path = self.root / "index.sqlite3"
        self.config_path = self.root / "config.json"
        self.config = json.loads(self.config_path.read_text(encoding="utf-8")) if self.config_path.exists() else {}
        self.notes = Path(self.config.get("notes_root", str(self.root / "notes"))).resolve()
        if initialize:
            self.root.mkdir(parents=True, exist_ok=True)
            with self.connect(write=True) as conn:
                version = conn.execute("PRAGMA user_version").fetchone()[0]
                if version > VERSION and not (version == PREVIEW_VERSION and _has_note_extension(conn)):
                    raise ValueError("Индекс знаний создан более новой версией")
                if version == VERSION and _has_note_extension(conn):
                    return
                if version >= VERSION:
                    conn.execute("BEGIN IMMEDIATE")
                    current = conn.execute("PRAGMA user_version").fetchone()[0]
                    if current > VERSION and not (current == PREVIEW_VERSION and _has_note_extension(conn)):
                        raise ValueError("Индекс знаний создан более новой версией")
                    conn.execute("CREATE TABLE IF NOT EXISTS note_files (id TEXT PRIMARY KEY, sha256 TEXT NOT NULL)")
                    conn.execute("""INSERT OR IGNORE INTO state VALUES ('index_identity', '"'||lower(hex(randomblob(16)))||'"')""")
                    if not _has_note_extension(conn):
                        raise ValueError("Повреждён индекс файлов Библиотеки")
                    if current == PREVIEW_VERSION:
                        conn.execute(f"PRAGMA user_version={VERSION}")
                    return
                conn.execute("PRAGMA journal_mode=WAL")
                conn.executescript("""
                    BEGIN IMMEDIATE;
                    CREATE TABLE IF NOT EXISTS items (
                      id TEXT PRIMARY KEY, project_id TEXT, task_id TEXT, kind TEXT NOT NULL,
                      title TEXT NOT NULL, body TEXT NOT NULL, locator TEXT NOT NULL,
                      content_hash TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'source',
                      freshness TEXT NOT NULL DEFAULT 'current', indexed_at TEXT NOT NULL,
                      revision INTEGER NOT NULL DEFAULT 1, metadata TEXT NOT NULL DEFAULT '{}');
                    CREATE VIRTUAL TABLE IF NOT EXISTS search USING fts5(id UNINDEXED,title,body,tokenize='unicode61');
                    CREATE INDEX IF NOT EXISTS item_scope ON items(project_id,kind,indexed_at);
                    CREATE TABLE IF NOT EXISTS dependencies (note_id TEXT NOT NULL,source_id TEXT NOT NULL,
                      source_hash TEXT NOT NULL,PRIMARY KEY(note_id,source_id));
                    CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY,kind TEXT NOT NULL,payload TEXT NOT NULL,
                      signature TEXT NOT NULL,due REAL NOT NULL,attempts INTEGER NOT NULL DEFAULT 0,error TEXT NOT NULL DEFAULT '');
                    CREATE TABLE IF NOT EXISTS files (id TEXT PRIMARY KEY,path TEXT NOT NULL,project_id TEXT,
                      task_id TEXT,signature TEXT NOT NULL DEFAULT '',seen_at TEXT NOT NULL,scan_root TEXT NOT NULL DEFAULT '');
                    CREATE TABLE IF NOT EXISTS streams (id TEXT PRIMARY KEY,path TEXT NOT NULL,provider TEXT NOT NULL,
                      session_id TEXT NOT NULL,cwd TEXT NOT NULL DEFAULT '',offset INTEGER NOT NULL DEFAULT 0,
                      prefix TEXT NOT NULL DEFAULT '',generation INTEGER NOT NULL DEFAULT 0,
                      line INTEGER NOT NULL DEFAULT 0,discard INTEGER NOT NULL DEFAULT 0,signature TEXT NOT NULL DEFAULT '',anchor TEXT NOT NULL DEFAULT '');
                    CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY,value TEXT NOT NULL);
                    INSERT OR IGNORE INTO state VALUES ('index_identity', '"'||lower(hex(randomblob(16)))||'"');
                    CREATE TABLE IF NOT EXISTS note_files (id TEXT PRIMARY KEY, sha256 TEXT NOT NULL);
                    CREATE TABLE IF NOT EXISTS revisions (id INTEGER PRIMARY KEY,item_id TEXT NOT NULL,
                      revision INTEGER NOT NULL,snapshot TEXT NOT NULL,recorded_at TEXT NOT NULL);
                    CREATE TABLE IF NOT EXISTS item_links (item_id TEXT NOT NULL,task_id TEXT NOT NULL,PRIMARY KEY(item_id,task_id));
                    CREATE TABLE IF NOT EXISTS commands (id TEXT PRIMARY KEY,action TEXT NOT NULL,body TEXT NOT NULL,
                      who TEXT NOT NULL,state TEXT NOT NULL DEFAULT 'pending',result TEXT,error TEXT,created_at TEXT NOT NULL);
                    CREATE TABLE IF NOT EXISTS search_rows (id TEXT PRIMARY KEY,fts_rowid INTEGER NOT NULL UNIQUE);
                    INSERT OR IGNORE INTO search_rows SELECT id,rowid FROM search;
                    CREATE INDEX IF NOT EXISTS item_recent ON items(indexed_at DESC,id);
                    CREATE INDEX IF NOT EXISTS item_project_recent ON items(project_id,indexed_at DESC,id);
                    CREATE INDEX IF NOT EXISTS item_kind_recent ON items(kind,indexed_at DESC,id);
                    CREATE INDEX IF NOT EXISTS item_freshness ON items(freshness);
                    CREATE INDEX IF NOT EXISTS item_task ON items(task_id,id);
                    CREATE INDEX IF NOT EXISTS link_task ON item_links(task_id,item_id);
                    PRAGMA user_version=5;
                    COMMIT;
                """)

    @contextlib.contextmanager
    def connect(self, *, write=False):
        conn = sqlite3.connect(self.path if write else self.path.as_uri()+"?mode=ro", uri=not write, timeout=2)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            if write:
                conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def value(self, key, default=None):
        if not self.path.exists():
            return default
        with self.connect() as conn:
            row = conn.execute("SELECT value FROM state WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def set_value(self, key, value):
        with self.connect(write=True) as conn:
            conn.execute("INSERT OR REPLACE INTO state VALUES (?,?)", (key, json.dumps(value, ensure_ascii=False)))

    def submit(self,action,body,who):
        if action not in {"note","confirm"}:
            raise ValueError("Неизвестное действие со знанием")
        identity=str(uuid.UUID(body.get("command_id"))) if body.get("command_id") else str(uuid.uuid4())
        payload=json.dumps(body,ensure_ascii=False,sort_keys=True)
        actor=json.dumps(who,ensure_ascii=False,sort_keys=True)
        with self.connect(write=True) as conn:
            existing=conn.execute("SELECT * FROM commands WHERE id=?",(identity,)).fetchone()
            if existing and (existing["action"]!=action or existing["body"]!=payload or existing["who"]!=actor):
                raise Conflict("Идентификатор запроса уже использован для другого содержания")
            if not existing:
                conn.execute("INSERT INTO commands(id,action,body,who,created_at) VALUES (?,?,?,?,?)",(identity,action,payload,actor,now()))
        return self.command(identity)

    def command(self,identity):
        identity=str(uuid.UUID(identity))
        with self.connect() as conn:
            row=conn.execute("SELECT id,state,result,error FROM commands WHERE id=?",(identity,)).fetchone()
        if not row:
            raise ValueError("Запрос не найден")
        return {"command_id":row["id"],"state":row["state"],"result":json.loads(row["result"]) if row["result"] else None,"error":json.loads(row["error"]) if row["error"] else None}

    def put(self, item, conn=None):
        if conn is None:
            with self.connect(write=True) as conn:
                return self.put(item, conn)
        item = dict(item)
        item.setdefault("project_id", None)
        item.setdefault("task_id", None)
        item.setdefault("state", "source")
        item.setdefault("freshness", "current")
        item.setdefault("metadata", {})
        item.setdefault("content_hash", sha(item["body"]))
        previous = conn.execute("SELECT * FROM items WHERE id=?", (item["id"],)).fetchone()
        compare = ("content_hash", "body", "project_id", "task_id", "title", "state", "freshness", "locator")
        if previous and all(previous[key] == item[key] for key in compare):
            return False
        if previous:
            conn.execute("INSERT INTO revisions(item_id,revision,snapshot,recorded_at) VALUES (?,?,?,?)",
                         (previous["id"], previous["revision"], json.dumps(dict(previous), ensure_ascii=False), now()))
            if previous["content_hash"] != item["content_hash"] or previous["project_id"] != item["project_id"] or item["freshness"] != "current":
                self.invalidate(item["id"],conn)
        item["revision"] = (previous["revision"] + 1) if previous else item.get("revision", 1)
        item["indexed_at"] = now()
        item["metadata"] = json.dumps(item["metadata"], ensure_ascii=False)
        fields = ("id", "project_id", "task_id", "kind", "title", "body", "locator", "content_hash", "state", "freshness", "indexed_at", "revision", "metadata")
        conn.execute("INSERT OR REPLACE INTO items VALUES ("+",".join("?" for _ in fields)+")", tuple(item[key] for key in fields))
        indexed=conn.execute("SELECT fts_rowid FROM search_rows WHERE id=?",(item["id"],)).fetchone()
        if indexed:
            conn.execute("DELETE FROM search WHERE rowid=?",(indexed[0],))
        inserted=conn.execute("INSERT INTO search VALUES (?,?,?)", (item["id"], item["title"], item["body"]))
        conn.execute("INSERT OR REPLACE INTO search_rows VALUES (?,?)",(item["id"],inserted.lastrowid))
        return True

    def invalidate(self, identity, conn):
        conn.execute("WITH RECURSIVE affected(id) AS (SELECT note_id FROM dependencies WHERE source_id=? UNION SELECT d.note_id FROM dependencies d JOIN affected a ON d.source_id=a.id) UPDATE items SET freshness='needs_review' WHERE id IN (SELECT id FROM affected)",(identity,))

    def enqueue(self, identity, kind, payload, signature="", *, delay=2, conn=None):
        import time
        if conn is None:
            with self.connect(write=True) as conn:
                return self.enqueue(identity,kind,payload,signature,delay=delay,conn=conn)
        old = conn.execute("SELECT signature FROM jobs WHERE id=?", (identity,)).fetchone()
        if old and old[0] == signature:
            return
        conn.execute("INSERT OR REPLACE INTO jobs VALUES (?,?,?,?,?,0,'')",
                     (identity, kind, json.dumps(payload, ensure_ascii=False), signature, time.time()+delay))

    def detail(self, identity, revision=None):
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM items WHERE id=?", (identity,)).fetchone()
            if not row:
                raise ValueError("Материал не найден")
            value = dict(row)
            if revision is not None and int(revision) != value["revision"]:
                historic=conn.execute("SELECT snapshot FROM revisions WHERE item_id=? AND revision=? ORDER BY id DESC LIMIT 1",(identity,int(revision))).fetchone()
                if not historic:
                    raise ValueError("Редакция не найдена")
                value=json.loads(historic[0])
            value["metadata"] = json.loads(value["metadata"])
            if revision is not None:
                value["metadata"]["historical_version"]=True
            value["dependencies"] = [dict(r) for r in conn.execute("SELECT d.*,i.title,i.content_hash AS current_hash,i.freshness FROM dependencies d LEFT JOIN items i ON i.id=d.source_id WHERE note_id=?", (identity,))]
            if revision is not None:
                value["dependencies"]=[]
                for ref in value["metadata"].get("references",[]):
                    source=conn.execute("SELECT title,content_hash,freshness FROM items WHERE id=?",(ref["id"],)).fetchone()
                    value["dependencies"].append({"source_id":ref["id"],"source_hash":ref["content_hash"],"title":source["title"] if source else None,"current_hash":source["content_hash"] if source else None,"freshness":source["freshness"] if source else "missing"})
            value["history"] = [dict(r) for r in conn.execute("SELECT revision,recorded_at FROM revisions WHERE item_id=? ORDER BY id DESC LIMIT 20", (identity,))]
            value["linked_tasks"] = [r[0] for r in conn.execute("SELECT task_id FROM item_links WHERE item_id=? LIMIT 20",(identity,))]
            return value

    def query(self, *, q="", project=None, task=None, kind=None, freshness=None, offset=0, limit=30):
        if len(q) > 300:
            raise ValueError("Поиск: не более 300 символов")
        limit, offset = max(1, min(50, int(limit))), max(0, min(100000, int(offset)))
        if not self.path.exists():
            return {"items": [], "total": 0, "offset": offset, "limit": limit}
        terms = re.findall(r"[^\W_]+", q, re.UNICODE)[:12]
        match = " AND ".join('"'+term+'"*' for term in terms)
        where, values = ["1=1"], []
        for column, value in (("project_id", project), ("task_id", task), ("kind", kind), ("freshness", freshness)):
            if value:
                if value == "__unbound" and column == "project_id":
                    where.append("i.project_id IS NULL")
                elif column == "task_id":
                    where.append("i.id IN (SELECT id FROM items WHERE task_id=? UNION SELECT item_id FROM item_links WHERE task_id=?)")
                    values.extend([value,value])
                else:
                    where.append("i."+column+"=?")
                    values.append(value)
        source = "items i"
        snippet = "substr(i.body,1,280)"
        order = "i.indexed_at DESC,i.id"
        if match:
            source += " JOIN search ON search.id=i.id"
            where.append("search MATCH ?")
            values.append(match)
            snippet = "snippet(search,2,'','', ' … ',36)"
            order = "bm25(search,0,4,1),i.indexed_at DESC"
        condition = " AND ".join(where)
        with self.connect() as conn:
            # Fixed SQL fragments above; every search/filter value is bound.
            total = conn.execute(f"SELECT count(*) FROM {source} WHERE {condition}", values).fetchone()[0]  # nosec B608
            rows = conn.execute(f"SELECT i.id,i.project_id,i.task_id,i.kind,i.title,i.state,i.freshness,i.indexed_at,i.revision,{snippet} AS snippet FROM {source} WHERE {condition} ORDER BY {order} LIMIT ? OFFSET ?", [*values, limit, offset]).fetchall()  # nosec B608
        return {"items": [dict(r) for r in rows], "total": total, "offset": offset, "limit": limit}

    def health(self):
        import time
        if not self.path.exists():
            return {"configured": False, "running": False, "items": 0, "pending": 0, "errors": []}
        worker = self.value("worker", {})
        with self.connect() as conn:
            counts = dict(conn.execute("SELECT kind,count(*) FROM items GROUP BY kind"))
            freshness = dict(conn.execute("SELECT freshness,count(*) FROM items GROUP BY freshness"))
            pending = conn.execute("SELECT count(*) FROM jobs WHERE attempts<3").fetchone()[0]
            error_count=conn.execute("SELECT count(*) FROM jobs WHERE error!=''").fetchone()[0]
            blocked_count=conn.execute("SELECT count(*) FROM jobs WHERE attempts>=3").fetchone()[0]
            pending_commands=conn.execute("SELECT count(*) FROM commands WHERE state='pending'").fetchone()[0]
            errors = [dict(r) for r in conn.execute("SELECT j.id,j.kind,j.error,j.attempts,json_extract(j.payload,'$.path') AS path FROM jobs j WHERE error!='' ORDER BY due LIMIT 10")]
        return {"configured": True, "running": time.time()-worker.get("heartbeat", 0)<20,
                "worker": worker, "items": sum(counts.values()), "counts": counts,
                "freshness": freshness, "pending": pending, "errors": errors,
                "error_count":error_count,"blocked_count":blocked_count,
                "pending_commands":pending_commands,
                "paused": bool(self.value("paused", False)), "git": self.value("git", {}),
                "coverage": self.value("coverage", {}), "last_success": self.value("last_success"),
                "notes_root": str(self.notes)}

    def save_note(self, body, who):
        from knowledge_collect import sanitize
        if body.get("kind", "decision") not in {"decision", "fact", "constraint", "open_question"}:
            raise ValueError("Выберите тип знания")
        title, text = body.get("title", ""), body.get("body", "")
        if not isinstance(title, str) or not title.strip() or len(title)>240 or not isinstance(text, str) or not text.strip() or len(text)>20000:
            raise ValueError("Нужны название (до 240) и текст (до 20000 символов)")
        title,text=sanitize(title),sanitize(text)
        refs = body.get("references", [])
        if not isinstance(refs, list) or not 1<=len(refs)<=20:
            raise ValueError("Укажите 1–20 оснований с прочитанным content_hash")
        with OperationLock(self.root / "notes.lock"):
            self._recover_note_write()
            identity = str(uuid.UUID(str(body.get("id") or uuid.uuid4())))
            with self.connect(write=True) as conn:
                conn.execute("BEGIN IMMEDIATE")
                old = conn.execute("SELECT * FROM items WHERE id=?", (identity,)).fetchone()
                if old and body.get("command_id") and json.loads(old["metadata"]).get("request_id")==body["command_id"]:
                    return self.detail(identity)
                if old and (old["state"] == "source" or old["revision"] != body.get("revision")):
                    raise Conflict("Знание изменилось; перечитайте его", dict(old))
                project, task = body.get("project_id"), body.get("task_id")
                dependencies = []
                for ref in refs:
                    if not isinstance(ref, dict) or ref.get("id") == identity:
                        raise ValueError("Ссылка на себя запрещена")
                    source = conn.execute("SELECT * FROM items WHERE id=?", (ref.get("id"),)).fetchone()
                    if not source or source["freshness"] != "current" or ref.get("content_hash") != source["content_hash"]:
                        raise Conflict("Основание изменилось или недоступно; перечитайте источник")
                    if project and source["project_id"] and source["project_id"] != project:
                        raise ValueError("Основание относится к другому проекту")
                    dependencies.append({"id": source["id"], "content_hash": source["content_hash"]})
                metadata = {"id": identity, "kind": body.get("kind", "decision"), "project_id": project,
                            "task_id": task, "title": title.strip(), "references": dependencies,
                            "author": who["id"], "state": "draft", "request_id": body.get("command_id")}
                content = META + json.dumps(metadata, ensure_ascii=False) + " -->\n\n# " + title.strip() + "\n\n" + text.strip() + "\n"
                path = self.notes / "notes" / (identity + ".md")
                before = self._require_current_note(conn, path, old)
                self.index_note(path, metadata, text.strip(), conn=conn)
                self._remember_note(conn, identity, content)
                self._publish_note_file(conn, path, content, before=before)
        return self.detail(identity)

    @property
    def _note_journal(self):
        return self.root / "note-publication.json"

    def _note_bytes(self, path):
        if path.is_symlink() or not path.resolve().is_relative_to(self.notes):
            raise ValueError("Файл знаний должен находиться в каталоге Библиотеки")
        try:
            with path.open("rb") as stream:
                data = stream.read(512_001)
        except FileNotFoundError:
            return None
        if len(data) > 512_000:
            raise ValueError("Файл знаний слишком велик")
        return data.decode("utf-8")

    def _require_current_note(self, conn, path, old):
        before = self._note_bytes(path)
        if old is None and before is None:
            return None
        if old is not None and before is not None:
            indexed = conn.execute("SELECT sha256 FROM note_files WHERE id=?", (old["id"],)).fetchone()
            if indexed and sha(before) == indexed["sha256"]:
                return before
            if not indexed:
                metadata = json.loads(old["metadata"])
                metadata.pop("confirmation", None)  # In history, never in the Markdown written by the UI.
                canonical = (META + json.dumps(metadata, ensure_ascii=False) + " -->\n\n# "
                             + old["title"] + "\n\n" + old["body"] + "\n")
                if before == canonical:
                    return before
        raise Conflict("Файл заметки изменился вне Библиотеки. Дождитесь переиндексации и перечитайте заметку.")

    @staticmethod
    def _remember_note(conn, identity, content):
        conn.execute("INSERT OR REPLACE INTO note_files VALUES (?,?)", (identity, sha(content)))

    def _recover_note_write(self):
        # A committed SQLite marker chooses the new file; otherwise undo publication.
        if not self._note_journal.exists():
            return
        journal = json.loads(self._note_journal.read_text(encoding="utf-8"))
        if journal.get("notes_root") != str(self.notes):
            raise Conflict("Каталог Библиотеки изменился; журнал сохранён для восстановления")
        committed = self.value("note_publication") == journal["id"]
        index_id = journal.get("index_identity")
        if (index_id and index_id != self.value("index_identity")) or (not index_id and not committed):
            raise Conflict("Индекс Библиотеки заменён или не подтверждён. Файл и журнал сохранены для восстановления.")
        relative = journal["path"]
        if not re.fullmatch(r"(?:notes/[0-9a-f-]{36}\.md|history/[0-9a-f-]{36}-r[0-9]+\.json)", relative):
            raise ValueError("Недопустимый путь в журнале знаний")
        path = self.notes / relative
        if path.is_symlink() or not path.resolve().is_relative_to(self.notes):
            raise ValueError("Журнал знаний указывает за пределы каталога")
        current = self._note_bytes(path)
        before, after = journal["before"], journal["after"]
        if current not in (before, after):
            raise Conflict("Файл изменён вне Библиотеки; журнал сохранён для восстановления")
        expected = after if committed else before
        if current != expected:
            if expected is None:
                path.unlink()
            else:
                atomic(path, expected)
        self._note_journal.unlink()

    def _publish_note_file(self, conn, path, content, *, before):
        def check():
            if self._note_bytes(path) != before:
                raise Conflict("Файл изменён вне Библиотеки; операция не записана")

        check()
        index_id = json.loads(conn.execute("SELECT value FROM state WHERE key='index_identity'").fetchone()[0])
        identity = uuid.uuid4().hex
        journal = {"id": identity, "notes_root": str(self.notes), "path": path.relative_to(self.notes).as_posix(),
                   "before": before, "after": content, "index_identity": index_id}
        atomic(self._note_journal, json.dumps(journal, ensure_ascii=False))
        try:
            conn.execute("INSERT OR REPLACE INTO state VALUES ('note_publication',?)", (json.dumps(identity),))
            atomic(path, content, before_replace=check)
            conn.commit()
        except Exception:
            conn.rollback()
            self._recover_note_write()
            if self.value("note_publication") != identity:
                raise
        # A crash or unlink error here leaves a committed marker for the next recovery.
        with contextlib.suppress(OSError):
            self._note_journal.unlink(missing_ok=True)

    def index_note(self, path, metadata, text, *, conn=None):
        if conn is None:
            with OperationLock(self.root / "notes.lock"):
                self._recover_note_write()
                with self.connect(write=True) as owned:
                    owned.execute("BEGIN IMMEDIATE")
                    return self.index_note(path, metadata, text, conn=owned)
        identity = str(uuid.UUID(metadata["id"]))
        if metadata.get("kind") not in {"decision", "fact", "constraint", "open_question"}:
            raise ValueError("Неизвестный тип знания")
        if conn is not None:
            old = conn.execute("SELECT * FROM items WHERE id=?", (identity,)).fetchone()
            refs = metadata.get("references", [])
            if not isinstance(refs,list) or not 1<=len(refs)<=20 or any(not isinstance(ref,dict) or not ref.get("id") or not ref.get("content_hash") or ref["id"]==identity for ref in refs):
                raise ValueError("Знанию нужны корректные основания; ссылка на себя запрещена")
            note_hash = sha(json.dumps({"body":text,**{key:metadata.get(key) for key in ("title","kind","project_id","task_id","references")}},ensure_ascii=False,sort_keys=True))
            state = old["state"] if old and old["content_hash"] == note_hash else "draft"
            if not old:
                for event_path in (self.notes/"history").glob(identity+"-r*.json"):
                    event=json.loads(event_path.read_text(encoding="utf-8"))
                    if event.get("type")=="knowledge.confirmed" and event.get("confirmation",{}).get("content_hash")==note_hash:
                        state="confirmed"
            freshness = "current"
            for ref in refs:
                source = conn.execute("SELECT * FROM items WHERE id=?", (ref["id"],)).fetchone()
                if source and metadata.get("project_id") and source["project_id"] and source["project_id"] != metadata["project_id"]:
                    raise ValueError("Основание относится к другому проекту")
                if not source or source["freshness"] != "current" or source["content_hash"] != ref["content_hash"]:
                    freshness = "needs_review"
            self.put({"id": identity, "kind": metadata["kind"], "project_id": metadata.get("project_id"),
                      "task_id": metadata.get("task_id"), "title": metadata["title"], "body": text,
                      "locator": str(path), "metadata": metadata, "state": state, "freshness": freshness,"content_hash":note_hash}, conn)
            conn.execute("DELETE FROM dependencies WHERE note_id=?", (identity,))
            conn.executemany("INSERT INTO dependencies VALUES (?,?,?)", [(identity,r["id"],r["content_hash"]) for r in refs])

    def index_note_file(self, path):
        from knowledge_collect import sanitize
        with OperationLock(self.root / "notes.lock"):
            self._recover_note_write()
            if path.is_symlink() or not path.resolve().is_relative_to(self.notes / "notes"):
                raise ValueError("Заметка должна находиться в каталоге Библиотеки")
            raw = self._note_bytes(path)
            if raw is None:
                raise FileNotFoundError(path)
            content = raw.removeprefix("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
            if len(content) > 128_000:
                raise ValueError("Заметка слишком велика")
            first, _, body = content.partition("\n")
            if not first.startswith(META) or not first.endswith(" -->"):
                raise ValueError("Заметка не содержит метаданные knowledge-hub")
            metadata = json.loads(first[len(META):-4])
            if str(uuid.UUID(metadata["id"])) != path.stem:
                raise ValueError("Идентификатор заметки не соответствует имени файла")
            text = body.strip()
            if text.startswith("# "):
                text = text.partition("\n")[2].strip()
            metadata["title"] = sanitize(metadata["title"])
            with self.connect(write=True) as conn:
                conn.execute("BEGIN IMMEDIATE")
                self.index_note(path, metadata, sanitize(text), conn=conn)
                self._remember_note(conn, path.stem, raw)

    def recover_note_write(self):
        if self._note_journal.exists():
            with OperationLock(self.root / "notes.lock"):
                self._recover_note_write()

    def confirm(self, identity, revision, who, command_id=None):
        if who["role"] != "owner":
            raise PermissionError("Содержание подтверждает пользователь")
        identity = str(uuid.UUID(str(identity)))
        with OperationLock(self.root / "notes.lock"):
            self._recover_note_write()
            with self.connect(write=True) as conn:
                conn.execute("BEGIN IMMEDIATE")
                row = conn.execute("SELECT * FROM items WHERE id=?", (identity,)).fetchone()
                if row and command_id and json.loads(row["metadata"]).get("confirmation",{}).get("command_id")==command_id:
                    return self.detail(identity)
                if not row or row["revision"] != revision:
                    raise Conflict("Знание изменилось; перечитайте его")
                if row["freshness"] != "current" or row["state"] == "source":
                    raise ValueError("Сначала перепроверьте знание и его основания")
                if row["state"] == "confirmed":
                    return self.detail(identity)
                self._require_current_note(conn, self.notes/"notes"/(identity+".md"), row)
                item = dict(row)
                item["metadata"] = json.loads(item["metadata"])
                confirmation = {"by": who["id"], "at": now(), "content_hash": row["content_hash"],"command_id":command_id}
                item["metadata"]["confirmation"] = confirmation
                item["state"] = "confirmed"
                self.put(item, conn)
                event = {"type":"knowledge.confirmed", "id":identity, "revision":revision, "confirmation":confirmation}
                history = self.notes/"history"/f"{identity}-r{revision}.json"
                self._publish_note_file(conn, history, json.dumps(event,ensure_ascii=False,indent=2)+"\n",
                                        before=self._note_bytes(history))
        return self.detail(identity)
