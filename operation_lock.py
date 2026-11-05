"""Small cross-process ownership locks for recoverable local operations."""
from __future__ import annotations

import os
from pathlib import Path


class OperationLockError(RuntimeError):
    """Another process still owns the operation lock."""


class OperationLock:
    """Hold a one-byte advisory lock until ``release`` or process exit."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self._handle = None

    def acquire(self) -> "OperationLock":
        if self._handle is not None:
            return self
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = self.path.open("a+b")
        try:
            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b"\0")
                handle.flush()
            handle.seek(0)
        except Exception:
            handle.close()
            raise
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            handle.close()
            raise OperationLockError(
                f"операция уже выполняется: {self.path.name}") from exc
        self._handle = handle
        return self

    def release(self) -> None:
        handle, self._handle = self._handle, None
        if handle is None:
            return
        try:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()

    def __enter__(self) -> "OperationLock":
        return self.acquire()

    def __exit__(self, _type, _value, _traceback) -> None:
        self.release()


def lock_is_held(path: Path) -> bool:
    """Conservatively report whether another owner holds ``path``."""
    lock = OperationLock(path)
    try:
        lock.acquire()
    except OperationLockError:
        return True
    try:
        return False
    finally:
        lock.release()


def process_is_alive(raw_pid: object) -> bool:
    """Best-effort liveness check used only as a legacy-lock fallback."""
    try:
        pid = int(raw_pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    if pid == os.getpid():
        return True
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        process_query_limited_information = 0x1000
        still_active = 259
        kernel32 = ctypes.windll.kernel32
        open_process = kernel32.OpenProcess
        open_process.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        open_process.restype = wintypes.HANDLE
        get_exit_code = kernel32.GetExitCodeProcess
        get_exit_code.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        get_exit_code.restype = wintypes.BOOL
        close_handle = kernel32.CloseHandle
        close_handle.argtypes = [wintypes.HANDLE]
        close_handle.restype = wintypes.BOOL
        handle = open_process(
            process_query_limited_information, False, pid)
        if not handle:
            return False
        try:
            exit_code = wintypes.DWORD()
            return bool(get_exit_code(
                handle, ctypes.byref(exit_code)) and exit_code.value == still_active)
        finally:
            close_handle(handle)
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
