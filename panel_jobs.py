"""Жизненный цикл фоновых задач веб-панели.

Модуль не знает о FastAPI и глобальном состоянии ``panel``: словарь состояния
передаётся явно. Это оставляет session-generation boundary пригодной для
повторного использования и отдельного тестирования.
"""

import asyncio
import logging
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path


LOGGER = logging.getLogger("blatero.panel.jobs")
BACKGROUND_TASKS: set[asyncio.Task] = set()
ACTIVE_SESSION_JOBS: dict[tuple[str, Path], "SessionJob"] = {}
SESSION_JOB_CONTEXT: ContextVar["SessionJob | None"] = ContextVar(
    "blatero_session_job", default=None)


def background_task_done(task: asyncio.Task) -> None:
    """Освободить сильную ссылку и не потерять исключение фоновой задачи."""
    BACKGROUND_TASKS.discard(task)
    if task.cancelled():
        return
    try:
        error = task.exception()
    except asyncio.CancelledError:
        return
    if error is not None:
        LOGGER.error(
            "фоновая задача %s завершилась с ошибкой", task.get_name(),
            exc_info=(type(error), error, error.__traceback__))


def spawn_background(awaitable, name: str = "blatero-background") -> asyncio.Task:
    """Создать задачу с сильной ссылкой до завершения."""
    task = asyncio.create_task(awaitable, name=name)
    BACKGROUND_TASKS.add(task)
    task.add_done_callback(background_task_done)
    return task


@dataclass(frozen=True, eq=False)
class SessionJob:
    """Снимок сессии для фоновой задачи; сравнивается только по идентичности."""

    sdir: Path
    generation: int


def capture_session_job(state: dict, sdir: Path | None = None) -> SessionJob:
    """Зафиксировать сессию сейчас, не откладывая это до старта coroutine."""
    inherited = SESSION_JOB_CONTEXT.get()
    requested = Path(sdir) if sdir is not None else None
    if inherited is not None and (requested is None or requested == inherited.sdir):
        return inherited
    target = requested if requested is not None else Path(state["sdir"])
    return SessionJob(target, int(state["generation"]))


def session_job_is_current(state: dict, job: SessionJob) -> bool:
    return state.get("sdir") == job.sdir and state.get("generation") == job.generation


async def run_session_background(awaitable, job: SessionJob):
    context_token = SESSION_JOB_CONTEXT.set(job)
    try:
        return await awaitable
    finally:
        SESSION_JOB_CONTEXT.reset(context_token)


def spawn_session_background(state: dict, awaitable,
                             name: str = "blatero-session-job",
                             sdir: Path | None = None) -> asyncio.Task:
    """Запустить session-scoped задачу с generation-ID момента запуска."""
    job = capture_session_job(state, sdir)
    return spawn_background(run_session_background(awaitable, job), name=name)


def session_job_owns(state: dict, slot: str, job: SessionJob) -> bool:
    """Задача всё ещё владеет своим UI/state-слотом в текущей сессии."""
    return state.get(slot) is job and session_job_is_current(state, job)


def claim_session_job(kind: str, job: SessionJob) -> bool:
    """Не допускать две пишущие задачи одного типа в одной папке сессии."""
    key = (kind, job.sdir)
    if key in ACTIVE_SESSION_JOBS:
        return False
    ACTIVE_SESSION_JOBS[key] = job
    return True


def release_session_job(kind: str, job: SessionJob) -> None:
    key = (kind, job.sdir)
    if ACTIVE_SESSION_JOBS.get(key) is job:
        ACTIVE_SESSION_JOBS.pop(key, None)


def session_job_active(state: dict, kind: str, sdir: Path | None = None) -> bool:
    target = Path(sdir) if sdir is not None else Path(state["sdir"])
    return (kind, target) in ACTIVE_SESSION_JOBS


def advance_session_generation(state: dict) -> int:
    """Инвалидировать результаты и UI-слоты текущего поколения сессии."""
    state["generation"] += 1
    state.update(
        pulse_job=None, busy=False,
        report_job=None, report_busy=False,
        training_job=None, training_busy=False,
        emulation_job=None, emulation_busy=False,
        workspace_job=None, workspace_busy=False, workspace_sdir=None,
        memory_job=None, memory_busy=False,
    )
    return state["generation"]
