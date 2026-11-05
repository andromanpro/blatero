"""Durable leases for restart-safe background report and workspace jobs."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import threading
import time
import uuid
from pathlib import Path

from operation_lock import OperationLock, OperationLockError, lock_is_held, process_is_alive
from session_utils import direct_child
import operation_contract


SCHEMA_VERSION = 1
STATE_FILE = ".background-jobs.json"
STALE_AFTER_SECONDS = 12.0
HEARTBEAT_SECONDS = 5.0
SUPPORTED_KINDS = frozenset({"report", "workspace"})
_LOCK = threading.RLock()
_TEMP_FILES = {
    "report": frozenset(
        {
            "report.draft.md.tmp",
            "report.md.tmp",
            "report.tmp.docx",
            "report-review.json.tmp",
            "report.draft.json.tmp",
            "report.draft.undo.md.tmp",
        }
    ),
    "workspace": frozenset(
        {
            "workspace-status.json.tmp",
            "workspace-scan.md.tmp",
            "workspace-context.md.tmp",
            "workspace-questions.md.tmp",
        }
    ),
}


def _owner_lock_file(session: Path, kind: str) -> Path:
    return Path(session) / f".background-{kind}-owner.lock"


def _now() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="milliseconds")


def _timestamp(value: object) -> float:
    try:
        parsed = dt.datetime.fromisoformat(str(value))
        if parsed.tzinfo is None:
            parsed = parsed.astimezone()
        return parsed.timestamp()
    except (TypeError, ValueError):
        return 0.0


def _read(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _atomic(path: Path, value: dict) -> None:
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as output:
        output.write(json.dumps(value, ensure_ascii=False, indent=2))
        output.flush()
        os.fsync(output.fileno())
    os.replace(temporary, path)


def _clean(value: object, limit: int = 300) -> str:
    return " ".join(str(value or "").split()).strip()[:limit]


def _load_state(session: Path) -> dict:
    state = _read(Path(session) / STATE_FILE)
    jobs = state.get("jobs") if isinstance(state.get("jobs"), dict) else {}
    return {"schema_version": SCHEMA_VERSION, "jobs": jobs}


def _save_job(session: Path, kind: str, job: dict) -> None:
    if kind not in SUPPORTED_KINDS:
        raise ValueError(f"неподдерживаемый тип фоновой задачи: {kind}")
    with _LOCK:
        path = Path(session) / STATE_FILE
        state = _load_state(session)
        state["jobs"][kind] = job
        _atomic(path, state)


def _transition(
    session: Path,
    kind: str,
    job_id: str,
    phase: str,
    *,
    stage: str = "",
    outcome: str = "",
    error: str = "",
) -> dict:
    with _LOCK:
        path = Path(session) / STATE_FILE
        state = _load_state(session)
        current = state["jobs"].get(kind)
        if not isinstance(current, dict) or current.get("job_id") != job_id:
            return {}
        if current.get("phase") != "running" and phase != "dismissed":
            return dict(current)  # A late heartbeat must not resurrect a terminal job.
        now = _now()
        current.update(phase=phase, updated_at=now, revision=int(current.get("revision") or 1) + 1)
        if phase == "running":
            current["heartbeat_at"] = now
        if stage:
            current["stage"] = _clean(stage, 120)
        if outcome:
            current["outcome"] = _clean(outcome, 120)
        if error:
            current["error"] = _clean(error, 500)
        state["jobs"][kind] = current
        _atomic(path, state)
        return dict(current)


class JobLease:
    """A small heartbeat thread whose disappearance makes a job recoverable."""

    def __init__(
        self,
        session: Path,
        kind: str,
        operation: str,
        *,
        generation: int = 0,
        retry: dict | None = None,
    ):
        if kind not in SUPPORTED_KINDS:
            raise ValueError(f"неподдерживаемый тип фоновой задачи: {kind}")
        self.session = Path(session).resolve()
        self.kind = kind
        self.job_id = uuid.uuid4().hex
        self._stop = threading.Event()
        self._finished = False
        self._owner = OperationLock(_owner_lock_file(self.session, kind))
        try:
            self._owner.acquire()
        except OperationLockError as exc:
            raise RuntimeError(f"задача {kind} в этой сессии уже выполняется") from exc
        started = _now()
        safe_retry = {
            key: value
            for key, value in (retry or {}).items()
            if key in {"force", "decision"}
            and isinstance(value, (str, bool, int, float, type(None)))
        }
        try:
            _save_job(
                self.session,
                kind,
                {
                    "schema_version": SCHEMA_VERSION,
                    "job_id": self.job_id,
                    "revision": 1,
                    "kind": kind,
                    "operation": _clean(operation, 80),
                    "phase": "running",
                    "stage": "starting",
                    "pid": os.getpid(),
                    "generation": int(generation),
                    "started_at": started,
                    "updated_at": started,
                    "heartbeat_at": started,
                    "retry": safe_retry,
                },
            )
        except Exception:
            self._owner.release()
            raise
        self._thread = threading.Thread(
            target=self._heartbeat_loop, daemon=True, name=f"job-heartbeat-{kind}"
        )
        try:
            self._thread.start()
        except Exception:
            self._owner.release()
            raise

    def _heartbeat_loop(self) -> None:
        while not self._stop.wait(HEARTBEAT_SECONDS):
            try:
                _transition(self.session, self.kind, self.job_id, "running")
            except OSError:
                # The foreground operation will surface a persistent disk error.
                continue

    def stage(self, value: str) -> None:
        if not self._finished:
            _transition(self.session, self.kind, self.job_id, "running", stage=value)

    def finish(self, phase: str = "completed", *, outcome: str = "", error: str = "") -> None:
        if self._finished:
            return
        self._finished = True
        self._stop.set()
        self._thread.join(timeout=1)
        try:
            _transition(self.session, self.kind, self.job_id, phase, outcome=outcome, error=error)
        finally:
            self._owner.release()

    def completed(self, outcome: str = "") -> None:
        self.finish("completed", outcome=outcome)

    def failed(self, error: object) -> None:
        self.finish("failed", error=f"{type(error).__name__}: {error}")

    def interrupted(self, reason: str = "server stopped") -> None:
        self.finish("interrupted", error=reason)


def start(
    session: Path, kind: str, operation: str, *, generation: int = 0, retry: dict | None = None
) -> JobLease:
    return JobLease(session, kind, operation, generation=generation, retry=retry)


def report_activity(session: Path) -> dict:
    """Read the actual durable job, without starting work or inventing a percent."""
    job = _load_state(Path(session))["jobs"].get("report", {})
    if not job:
        return {"phase": "idle", "session": Path(session).name}
    if job.get("phase") == "running":
        owner = _owner_lock_file(Path(session), "report")
        active = lock_is_held(owner) if owner.exists() else process_is_alive(job.get("pid"))
        if not active:
            job = {**job, "phase": "interrupted"}
    started = _timestamp(job.get("started_at"))
    end = time.time() if job.get("phase") == "running" else _timestamp(job.get("updated_at"))
    return {
        key: job.get(key, "")
        for key in ("job_id", "phase", "stage", "operation", "outcome", "generation")
    } | {
        "session": Path(session).name,
        "elapsed_seconds": round(max(0, end - started), 1) if started else 0,
        "operation_status": operation_status(session, "report", job=job),
    }


def operation_status(session: Path, kind: str, *, job: dict | None = None) -> dict | None:
    """Project v1 leases into the common contract without rewriting old records."""
    session = Path(session)
    job = dict(job if job is not None else _load_state(session)["jobs"].get(kind, {}))
    if not job:
        return None
    phase = job.get("phase")
    if phase == "running":
        owner = _owner_lock_file(session, kind)
        active = lock_is_held(owner) if owner.exists() else process_is_alive(job.get("pid"))
        if not active:
            phase = "interrupted"
    state = {"running": "running", "completed": "succeeded", "failed": "failed",
             "interrupted": "outcome_unknown", "dismissed": "outcome_unknown"}.get(phase, "outcome_unknown")
    result = {"outcome": str(job.get("outcome") or "")} if state == "succeeded" else None
    return operation_contract.build(identity=str(job.get("job_id") or ""), session=session.name,
        kind=kind, state=state, stage=str(job.get("stage") or ""),
        revision=job.get("revision", 1), generation=job.get("generation", 0),
        started_at=str(job.get("started_at") or ""), updated_at=str(job.get("updated_at") or ""),
        error_code="outcome_unknown" if state == "outcome_unknown" else "operation_failed" if state == "failed" else "",
        result=result)


def _report_recovery(session: Path, job: dict) -> tuple[str, str, bool]:
    operation = str(job.get("operation") or "prepare")
    draft = session / "report.draft.md"
    review = _read(session / "report-review.json")
    if review.get("state") == "finalized" and (session / "report.md").is_file():
        return "already_completed", "Итоговый отчёт уже сохранён.", False
    if draft.is_file():
        if operation == "finalize":
            return (
                "local_finalize",
                "Черновик цел; можно повторить локальную сборку DOCX без нового запроса к LLM.",
                False,
            )
        checkpoint = _read(session / "report.draft.json")
        try:
            digest = hashlib.sha256(draft.read_text(encoding="utf-8").encode("utf-8")).hexdigest()
        except (OSError, UnicodeError):
            digest = ""
        if checkpoint.get("draft_sha256") == digest and digest:
            return (
                "saved_draft",
                "Ответ LLM уже сохранён; очередь проверки можно "
                "восстановить локально без повторной оплаты.",
                False,
            )
    return (
        "retry_llm",
        "Черновик не успел сохраниться. Повтор выполнит новый "
        "запрос к выбранной LLM только после подтверждения.",
        True,
    )


def _workspace_recovery(session: Path, _job: dict) -> tuple[str, str, bool]:
    status = _read(session / "workspace-status.json")
    if status.get("state") == "ready" and (session / "workspace-context.md").is_file():
        return "already_completed", "Контекст проекта уже сохранён.", False
    return (
        "retry_llm",
        "Облачный ответ не был сохранён. Повтор снова "
        "проанализирует текущую папку и может выполнить новый LLM-запрос.",
        True,
    )


def _item(session: Path, job: dict, current: float) -> dict:
    kind = str(job.get("kind") or "")
    if kind == "report":
        mode, message, costs = _report_recovery(session, job)
        label = "Отчёт встречи"
    else:
        mode, message, costs = _workspace_recovery(session, job)
        label = "Анализ рабочей папки"
    meta = _read(session / "meta.json")
    last = max(_timestamp(job.get("heartbeat_at")), _timestamp(job.get("updated_at")))
    return {
        "session": session.name,
        "session_label": str(meta.get("name") or session.name),
        "kind": kind,
        "label": label,
        "operation": str(job.get("operation") or ""),
        "phase": str(job.get("phase") or "interrupted"),
        "stage": str(job.get("stage") or ""),
        "started_at": str(job.get("started_at") or ""),
        "last_activity": dt.datetime.fromtimestamp(
            last or session.stat().st_mtime,
            tz=dt.datetime.now().astimezone().tzinfo,
        ).isoformat(timespec="seconds"),
        "age_seconds": max(0, round(current - last)) if last else 0,
        "recovery_mode": mode,
        "message": message,
        "new_llm_request": costs,
        "error": str(job.get("error") or ""),
        "retry": dict(job.get("retry") or {}),
    }


def scan(sessions_root: Path, *, now: float | None = None) -> list[dict]:
    root = Path(sessions_root)
    root.mkdir(parents=True, exist_ok=True)
    current = time.time() if now is None else float(now)
    result = []
    for session in root.iterdir():
        if not session.is_dir():
            continue
        state = _load_state(session)
        for kind, job in state["jobs"].items():
            if kind not in SUPPORTED_KINDS or not isinstance(job, dict):
                continue
            phase = str(job.get("phase") or "")
            last = max(_timestamp(job.get("heartbeat_at")), _timestamp(job.get("updated_at")))
            stale = current - last >= STALE_AFTER_SECONDS or last - current > 60.0
            if phase == "interrupted":
                item = _item(session, job, current)
                if item["recovery_mode"] != "already_completed":
                    result.append(item)
            elif phase == "running" and stale:
                lock_file = _owner_lock_file(session, kind)
                owner_active = (
                    lock_is_held(lock_file)
                    if lock_file.exists()
                    else process_is_alive(job.get("pid"))
                )
                if not owner_active:
                    item = _item(session, job, current)
                    if item["recovery_mode"] != "already_completed":
                        result.append(item)
    result.sort(key=lambda item: item["last_activity"], reverse=True)
    return result


def payload(sessions_root: Path) -> dict:
    items = scan(sessions_root)
    return {"state": "needs_attention" if items else "ready", "items": items, "count": len(items)}


def _resolve(sessions_root: Path, session_name: str, kind: str) -> tuple[Path, dict]:
    if kind not in SUPPORTED_KINDS:
        raise ValueError("неизвестный тип фоновой задачи")
    session = direct_child(Path(sessions_root), session_name, must_exist=True)
    state = _load_state(session)
    job = state["jobs"].get(kind)
    if not isinstance(job, dict):
        raise ValueError("фоновая задача не найдена")
    pending = next(
        (
            item
            for item in scan(sessions_root)
            if item["session"] == session.name and item["kind"] == kind
        ),
        None,
    )
    if pending is None:
        raise ValueError("задача уже обработана или снова выполняется")
    return session, job


def dismiss(sessions_root: Path, session_name: str, kind: str) -> dict:
    session, job = _resolve(sessions_root, session_name, kind)
    return _transition(session, kind, str(job["job_id"]), "dismissed", outcome="user_dismissed")


def cleanup(sessions_root: Path, session_name: str, kind: str) -> dict:
    session, _job = _resolve(sessions_root, session_name, kind)
    removed = []
    for name in sorted(_TEMP_FILES[kind]):
        path = session / name
        if path.is_file():
            path.unlink()
            removed.append(name)
    return {"session": session.name, "kind": kind, "removed_temporary_files": removed}
