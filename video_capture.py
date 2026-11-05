"""Independent video process ownership; never imports/calls microphone or STT code."""

from __future__ import annotations

import importlib.util
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import sysconfig
import threading
import time
import uuid

import app_paths
from operation_lock import OperationLock, process_is_alive
from session_utils import direct_child
import video_sources

ACTIVE = {"starting", "preview", "recording", "stopping"}
RUN_ID = re.compile(r"[0-9a-f]{32}")


def atomic_state(folder: Path, value: dict) -> None:
    target = folder / "state.json"
    temporary = folder / ("state-" + uuid.uuid4().hex + ".tmp")
    try:
        with temporary.open("x", encoding="utf-8") as output:
            json.dump(value, output, ensure_ascii=False)
            output.flush()
            os.fsync(output.fileno())
        for attempt in range(5):
            try:
                os.replace(temporary, target)
                break
            except PermissionError:
                if attempt == 4:
                    raise
                # A concurrent Windows reader/AV can briefly deny replacement.
                # Retry this same state only; permanent denial still fails closed.
                time.sleep(.01 * 2**attempt)
    finally:
        temporary.unlink(missing_ok=True)


def video_root(session: Path, create: bool = False) -> Path:
    parent = Path(session).resolve(strict=True)
    raw = parent / "video"
    if raw.is_symlink() or (hasattr(raw, "is_junction") and raw.is_junction()):
        raise ValueError("video_invalid_path")
    if create:
        raw.mkdir(exist_ok=True)
    return raw


def run_folder(session: Path, run: str) -> Path:
    if not isinstance(run, str) or not RUN_ID.fullmatch(run):
        raise ValueError("video_invalid_run")
    root = video_root(session)
    raw = root / run
    if raw.is_symlink() or (hasattr(raw, "is_junction") and raw.is_junction()):
        raise ValueError("video_invalid_path")
    return direct_child(root, run, must_exist=True)


def read_state(folder: Path) -> dict:
    path = folder / "state.json"
    if path.is_symlink() or path.stat().st_size > 32768:
        raise ValueError("video_invalid_state")
    data = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(data, dict)
        or data.get("id") != folder.name
        or not isinstance(data.get("phase"), str)
        or data.get("phase") not in ACTIVE | {"completed", "interrupted", "failed", "cancelled"}
        or not isinstance(data.get("created_at"), (int, float))
        or not math.isfinite(data["created_at"])
        or not isinstance(data.get("file", ""), str)
        or data.get("file", "") not in {"", "recording.mkv", "recording.partial.mkv"}
        or not isinstance(data.get("source", {}), dict)
    ):
        raise ValueError("video_invalid_state")
    return data


def effective_state(folder: Path) -> dict:
    state = read_state(folder)
    starting = state.get("phase") == "starting" and time.time() - state["created_at"] < 15
    if (
        state.get("phase") in ACTIVE
        and not starting
        and not process_is_alive(state.get("worker_pid"))
    ):
        state = {**state, "phase": "interrupted", "error": "video_worker_lost"}
        state["file"] = next(
            (
                name
                for name in ("recording.mkv", "recording.partial.mkv")
                if (folder / name).is_file() and not (folder / name).is_symlink()
            ),
            "",
        )
    return state


def listing(session: Path) -> list[dict]:
    root = video_root(session)
    if not root.exists():
        return []
    rows = []
    for path in sorted(root.iterdir(), key=lambda item: item.name, reverse=True):
        if not RUN_ID.fullmatch(path.name):
            continue
        try:
            folder = run_folder(session, path.name)
            state = effective_state(folder)
            rows.append(state)
        except (OSError, ValueError):
            continue
    return sorted(rows, key=lambda item: item.get("created_at", 0), reverse=True)[:100]


def active(session: Path | None) -> bool:
    if not session or not Path(session).is_dir():
        return False
    try:
        return any(item.get("phase") in ACTIVE for item in listing(session))
    except (OSError, ValueError):
        return True  # Invalid capture paths are not permission to remove an active session.


def capability() -> dict:
    available = sys.platform == "win32" and all(
        importlib.util.find_spec(name) for name in ("av", "numpy", "cv2", "windows_capture")
    )
    return {
        "available": bool(available),
        "error": "" if available else "video_component_missing",
        "container": "mkv",
        "audio": "separate_wav",
        "minimized": False,
    }


class VideoManager:
    def __init__(self, *, command: list[str] | None = None):
        # Windows venv python.exe may be a redirector spawning a second process.
        # Own the actual worker handle, not a shim which can leave capture running.
        executable = getattr(sys, "_base_executable", None) or sys.executable
        self.command = command or [executable, str(app_paths.APP_ROOT / "video_worker.py")]
        self.jobs = {}
        self.lock = threading.RLock()

    def _check_health(self, job, now: float) -> bool:
        """Bound only our worker's startup/encoder stalls; a static image is not a stall."""
        if job["process"].poll() is not None:
            return False
        try:
            value = read_state(job["folder"])
        except (OSError, ValueError):
            value = job["initial"]
        heartbeat = value.get("heartbeat")
        if heartbeat != job.get("last_heartbeat"):
            job.update(last_heartbeat=heartbeat, last_progress=now)
        limit = 20
        if value.get("phase") == "stopping" or job.get("stop_requested"):
            size = max(
                (
                    path.stat().st_size
                    for path in job["folder"].glob("recording*.mkv")
                    if path.is_file()
                ),
                default=0,
            )
            limit = min(180, 20 + size / (32 * 1024**2))
        if now - job["last_progress"] <= limit:
            return False
        job["process"].terminate()
        job["process"].wait(timeout=5)
        try:
            recovered = effective_state(job["folder"])
        except (OSError, ValueError):
            recovered = dict(job["initial"])
            recovered["file"] = next(
                (
                    name
                    for name in ("recording.mkv", "recording.partial.mkv")
                    if (job["folder"] / name).is_file()
                ),
                "",
            )
        recovered.update(
            phase="interrupted" if recovered.get("file") else "failed",
            error="video_worker_timeout",
            ended_at=time.time(),
        )
        atomic_state(job["folder"], recovered)
        return True

    def _watch(self, job):
        while job["process"].poll() is None:
            try:
                self._check_health(job, time.monotonic())
            except (OSError, ValueError, subprocess.SubprocessError):
                pass
            time.sleep(0.5)
        with self.lock:
            self._release_finished()

    def _release_finished(self):
        for job in self.jobs.values():
            if job["process"].poll() is not None and not job.get("released"):
                job["guard"].release()
                job["log"].close()
                if job["process"].stdin:
                    job["process"].stdin.close()
                job["released"] = True

    def is_active(self, session: Path | None) -> bool:
        if session is None:
            return False
        with self.lock:
            owned = any(
                job["session"] == Path(session).resolve() and job["process"].poll() is None
                for job in self.jobs.values()
            )
        return owned or active(session)

    def prepare(self, session: Path, source: dict, request_id: str, *, fps: int = 15) -> dict:
        if (
            not isinstance(source, dict)
            or not RUN_ID.fullmatch(str(request_id))
            or type(fps) is not int
            or fps not in (15, 30)
        ):
            raise ValueError("video_invalid_request")
        with self.lock:
            self._release_finished()
            if request_id in self.jobs:
                job = self.jobs[request_id]

                def identity(item):
                    return {key: value for key, value in item.items() if key != "label"}

                if (
                    job["session"] != Path(session).resolve()
                    or identity(job["source"]) != identity(source)
                    or job["fps"] != fps
                ):
                    raise ValueError("video_request_conflict")
                return read_state(job["folder"])
            source = video_sources.validate(source)
            # The final manifest is published before WGC/control teardown ends.
            # Do not race the preceding owned worker's data-root lock or kill it.
            for previous in self.jobs.values():
                if previous['process'].poll() is not None:
                    continue
                value = read_state(previous['folder'])
                if value.get('phase') not in ACTIVE:
                    try:
                        previous['process'].wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        raise RuntimeError('video_previous_still_finishing') from None
            self._release_finished()
            root = video_root(session, True)
            # A data-root lock prevents two local panels from starting competing captures.
            guard = OperationLock(app_paths.DATA_ROOT / ".video-capture.lock").acquire()
            folder = root / request_id
            try:
                folder.mkdir()  # Exclusive: a retry never overwrites a previous capture.
                initial = {
                    "id": request_id,
                    "phase": "starting",
                    "source": source,
                    "fps": fps,
                    "created_at": time.time(),
                    "frames": 0,
                    "worker_pid": 0,
                    "error": "",
                    "file": "",
                }
                atomic_state(folder, initial)
                log = (folder / "worker.log").open("x", encoding="utf-8")
                env = dict(
                    os.environ, PYTHONUTF8="1", OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1"
                )
                inherited = os.environ.get("PYTHONPATH", "")
                env["PYTHONPATH"] = os.pathsep.join(
                    filter(
                        None,
                        [inherited, sysconfig.get_path("purelib"), sysconfig.get_path("platlib")],
                    )
                )
                env["PYTHONNOUSERSITE"] = "1"
                process = subprocess.Popen(
                    self.command,
                    stdin=subprocess.PIPE,
                    stdout=log,
                    stderr=log,
                    text=True,
                    encoding="utf-8",
                    env=env,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                self.jobs[request_id] = {
                    "process": process,
                    "folder": folder,
                    "session": Path(session).resolve(),
                    "source": source,
                    "fps": fps,
                    "guard": guard,
                    "log": log,
                    "initial": initial,
                    "last_progress": time.monotonic(),
                    "last_heartbeat": None,
                }
                process.stdin.write(
                    json.dumps({"folder": str(folder), "source": source, "fps": fps}) + "\n"
                )
                process.stdin.flush()
                threading.Thread(
                    target=self._watch, args=(self.jobs[request_id],), daemon=True
                ).start()
                return initial
            except Exception:
                if "initial" in locals():
                    atomic_state(
                        folder, {**initial, "phase": "failed", "error": "video_start_failed"}
                    )
                job = self.jobs.get(request_id)
                if job:
                    job["process"].terminate()
                    job["process"].wait(timeout=5)
                    self._release_finished()
                else:
                    if "log" in locals():
                        log.close()
                    guard.release()
                raise

    def require_preview(self, session: Path, run: str) -> dict:
        """Validate the exact owned preview before starting combined recording."""
        with self.lock:
            job = self.jobs.get(run)
            if not job or job['session'] != Path(session).resolve():
                raise ValueError('video_not_owned')
            value = effective_state(run_folder(session, run))
            if job['process'].poll() is not None or value['phase'] != 'preview':
                raise ValueError('video_preview_required')
            return value

    def action(self, session: Path, run: str, action: str) -> dict:
        if action not in {"start", "stop", "cancel"}:
            raise ValueError("video_invalid_action")
        with self.lock:
            self._release_finished()
            folder = run_folder(session, run)
            value = read_state(folder)
            job = self.jobs.get(run)
            if not job or job["session"] != Path(session).resolve():
                raise ValueError("video_not_owned")
            if job["process"].poll() is not None:
                return value
            if action == "start" and value.get("phase") not in {"preview", "recording"}:
                raise ValueError("video_preview_required")
            job["process"].stdin.write(json.dumps({"action": action}) + "\n")
            job["process"].stdin.flush()
            if action in {"stop", "cancel"}:
                job["stop_requested"] = True
            return value

    def close(self) -> None:
        # Only our child processes. An unresponsive video worker cannot hold audio shutdown.
        with self.lock:
            jobs = list(self.jobs.values())
            for job in jobs:
                if job["process"].poll() is None:
                    try:
                        job["process"].stdin.write('{"action":"abort"}\n')
                        job["process"].stdin.flush()
                    except OSError:
                        pass
            for job in jobs:
                try:
                    job["process"].wait(timeout=8)
                except subprocess.TimeoutExpired:
                    job["process"].terminate()
                    job["process"].wait(timeout=5)
            self._release_finished()
