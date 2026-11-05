"""Local Win32 source identities. No screenshot, activation, or desktop fallback."""

from __future__ import annotations

import ctypes as ct
from ctypes import wintypes as wt
import os
import sys


def _api():
    if sys.platform != "win32":
        raise ValueError("video_windows_only")
    user, kernel = (
        ct.WinDLL("user32", use_last_error=True),
        ct.WinDLL("kernel32", use_last_error=True),
    )
    user.IsWindow.argtypes = [wt.HWND]
    user.IsWindowVisible.argtypes = [wt.HWND]
    user.IsIconic.argtypes = [wt.HWND]
    user.GetWindowTextLengthW.argtypes = [wt.HWND]
    user.GetWindowTextW.argtypes = [wt.HWND, wt.LPWSTR, ct.c_int]
    user.GetClassNameW.argtypes = [wt.HWND, wt.LPWSTR, ct.c_int]
    user.GetWindowThreadProcessId.argtypes = [wt.HWND, ct.POINTER(wt.DWORD)]
    user.GetWindowLongW.argtypes = [wt.HWND, ct.c_int]
    user.GetWindowRect.argtypes = [wt.HWND, ct.POINTER(wt.RECT)]
    kernel.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
    kernel.OpenProcess.restype = wt.HANDLE
    kernel.GetProcessTimes.argtypes = [wt.HANDLE, *([ct.POINTER(wt.FILETIME)] * 4)]
    kernel.CloseHandle.argtypes = [wt.HANDLE]
    return user, kernel


def window_identity(hwnd: int) -> dict:
    user, kernel = _api()
    if not isinstance(hwnd, int) or isinstance(hwnd, bool) or not 0 < hwnd < 2**63:
        raise ValueError("video_invalid_source")
    if not user.IsWindow(hwnd) or not user.IsWindowVisible(hwnd) or user.IsIconic(hwnd):
        raise ValueError("video_window_unavailable")
    if user.GetWindowLongW(hwnd, -20) & (0x80 | 0x08000000):
        raise ValueError(
            "video_window_unavailable"
        )  # Tool/no-activate windows are not WGC targets.
    pid = wt.DWORD()
    thread = user.GetWindowThreadProcessId(hwnd, ct.byref(pid))
    handle = kernel.OpenProcess(0x1000, False, pid.value)
    if not handle:
        raise ValueError("video_window_unavailable")
    times = [wt.FILETIME() for _ in range(4)]
    try:
        if not kernel.GetProcessTimes(handle, *(ct.byref(value) for value in times)):
            raise ValueError("video_window_unavailable")
    finally:
        kernel.CloseHandle(handle)
    title = ct.create_unicode_buffer(min(512, user.GetWindowTextLengthW(hwnd) + 1))
    user.GetWindowTextW(hwnd, title, len(title))
    name = ct.create_unicode_buffer(256)
    user.GetClassNameW(hwnd, name, len(name))
    return {
        "kind": "window",
        "hwnd": hwnd,
        "pid": pid.value,
        "thread": thread,
        "created": str((times[0].dwHighDateTime << 32) | times[0].dwLowDateTime),
        "class": name.value,
        "label": title.value[:300] or name.value,
    }


def monitors() -> list[dict]:
    user, _kernel = _api()

    class MonitorInfo(ct.Structure):
        _fields_ = [
            ("size", wt.DWORD),
            ("monitor", wt.RECT),
            ("work", wt.RECT),
            ("flags", wt.DWORD),
            ("device", wt.WCHAR * 32),
        ]

    callback_type = ct.WINFUNCTYPE(wt.BOOL, wt.HMONITOR, wt.HDC, ct.POINTER(wt.RECT), wt.LPARAM)
    rows = []
    user.GetMonitorInfoW.argtypes = [wt.HMONITOR, ct.POINTER(MonitorInfo)]

    @callback_type
    def collect(handle, _hdc, _rect, _data):
        info = MonitorInfo()
        info.size = ct.sizeof(info)
        if user.GetMonitorInfoW(handle, ct.byref(info)):
            rect = [info.monitor.left, info.monitor.top, info.monitor.right, info.monitor.bottom]
            rows.append(
                {
                    "kind": "monitor",
                    "index": len(rows) + 1,
                    "device": info.device,
                    "handle": int(handle),
                    "rect": rect,
                    "label": info.device,
                }
            )
        return True

    user.EnumDisplayMonitors.argtypes = [wt.HDC, ct.c_void_p, callback_type, wt.LPARAM]
    if not user.EnumDisplayMonitors(None, None, collect, 0):
        raise ValueError("video_sources_failed")
    return rows


def sources() -> list[dict]:
    user, _kernel = _api()
    callback_type = ct.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    rows = []

    @callback_type
    def collect(hwnd, _data):
        try:
            item = window_identity(int(hwnd))
            if item["pid"] != os.getpid() and item["label"] not in {"Program Manager"}:
                rows.append(item)
        except (OSError, ValueError):
            pass
        return len(rows) < 150

    user.EnumWindows.argtypes = [callback_type, wt.LPARAM]
    user.EnumWindows(collect, 0)
    return monitors() + sorted(rows, key=lambda row: row["label"].casefold())


def validate(source: dict) -> dict:
    if not isinstance(source, dict):
        raise ValueError("video_invalid_source")
    if source.get("kind") == "window":
        actual = window_identity(source.get("hwnd"))
        if any(source.get(key) != actual[key] for key in ("pid", "thread", "created", "class")):
            raise ValueError("video_source_changed")
        return actual
    if source.get("kind") == "monitor":
        for actual in monitors():
            if all(source.get(key) == actual[key] for key in ("index", "device", "handle", "rect")):
                return actual
        raise ValueError("video_source_changed")
    raise ValueError("video_invalid_source")
