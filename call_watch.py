"""Opt-in Windows microphone-use watcher for native Telemost and Kontur.Talk.

Uses process/registry metadata, with no window inspection or desktop automation.
The watchdog can launch the panel while its browser and server are closed.
"""
from __future__ import annotations

import argparse
import ctypes as ct
from ctypes import wintypes as wt
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import subprocess
import sys
import time
import urllib.error
import urllib.request
import urllib.parse

from operation_lock import OperationLock, OperationLockError, lock_is_held

APPS = {"telemost": {"telemost.exe", "yandextelemost.exe"},
        "talk": {"ktalk.exe", "kontur.talk.exe", "konturtalk.exe"}}
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_NAME = "BlateroCallWatch"
MIC_KEY = r"Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\microphone\NonPackaged"


def application(path: str) -> str | None:
    executable = PureWindowsPath(path.casefold())
    if executable.name == "qtwebengineprocess.exe" and "yandextelemost" in executable.parts:
        return "telemost"
    return next((app for app, names in APPS.items() if executable.name in names), None)


def enabled(settings: dict) -> bool:
    return settings.get("call_auto_record_acknowledged") is True and any(
        settings.get("call_auto_" + app) is True for app in APPS)


def active_processes() -> dict[str, list[int]]:
    """Exact executable paths and creation FILETIMEs exclude stale registry entries."""
    kernel = ct.WinDLL("kernel32", use_last_error=True)
    class Process(ct.Structure):
        _fields_ = [("size", wt.DWORD), ("usage", wt.DWORD), ("pid", wt.DWORD),
            ("heap", ct.c_size_t), ("module", wt.DWORD), ("threads", wt.DWORD),
            ("parent", wt.DWORD), ("priority", wt.LONG), ("flags", wt.DWORD),
            ("exe", wt.WCHAR * 260)]
    kernel.CreateToolhelp32Snapshot.argtypes = [wt.DWORD, wt.DWORD]
    kernel.CreateToolhelp32Snapshot.restype = wt.HANDLE
    kernel.Process32FirstW.argtypes = kernel.Process32NextW.argtypes = [wt.HANDLE, ct.POINTER(Process)]
    kernel.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
    kernel.OpenProcess.restype = wt.HANDLE
    kernel.QueryFullProcessImageNameW.argtypes = [wt.HANDLE, wt.DWORD, wt.LPWSTR, ct.POINTER(wt.DWORD)]
    kernel.GetProcessTimes.argtypes = [wt.HANDLE, *([ct.POINTER(wt.FILETIME)] * 4)]
    kernel.CloseHandle.argtypes = [wt.HANDLE]
    snapshot = kernel.CreateToolhelp32Snapshot(2, 0)
    if snapshot == ct.c_void_p(-1).value:
        raise ct.WinError(ct.get_last_error())
    result = {}
    names = set().union(*APPS.values()) | {"qtwebengineprocess.exe"}
    try:
        entry = Process(size=ct.sizeof(Process))
        valid = kernel.Process32FirstW(snapshot, ct.byref(entry))
        while valid:
            if entry.exe.casefold() in names:
                handle = kernel.OpenProcess(0x1000, False, entry.pid)
                if handle:
                    try:
                        path, size = ct.create_unicode_buffer(32768), wt.DWORD(32768)
                        times = [wt.FILETIME() for _ in range(4)]
                        if (kernel.QueryFullProcessImageNameW(handle, 0, path, ct.byref(size))
                                and kernel.GetProcessTimes(handle, *(ct.byref(v) for v in times))):
                            born = times[0].dwLowDateTime | (times[0].dwHighDateTime << 32)
                            result.setdefault(path.value.casefold(), []).append(born)
                    finally:
                        kernel.CloseHandle(handle)
            valid = kernel.Process32NextW(snapshot, ct.byref(entry))
    finally:
        kernel.CloseHandle(snapshot)
    return result


def microphone_uses() -> list[dict]:
    if sys.platform != "win32":
        raise OSError("Автозапуск по звонку доступен в Windows.")
    import winreg
    processes = active_processes()
    rows = []
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, MIC_KEY)
    except FileNotFoundError:
        return rows
    with key:
        for index in range(winreg.QueryInfoKey(key)[0]):
            name = winreg.EnumKey(key, index)
            path = name.replace("#", "\\").casefold()
            app = application(path)
            if not app or path not in processes:
                continue
            try:
                with winreg.OpenKey(key, name) as child:
                    start = int(winreg.QueryValueEx(child, "LastUsedTimeStart")[0])
                    stop = int(winreg.QueryValueEx(child, "LastUsedTimeStop")[0])
                if start > 0 and stop == 0 and any(born <= start for born in processes[path]):
                    rows.append({"app": app, "path": path, "start": start})
            except (OSError, ValueError, TypeError):
                continue
    return rows


class Episodes:
    """One capture per microphone-use episode, including short mute/device gaps."""
    def __init__(self, saved: dict | None = None):
        self.rows = {app: row for app, row in (saved or {}).items()
                     if app in APPS and isinstance(row, dict)
                     and isinstance(row.get("first_seen"), (int, float))
                     and isinstance(row.get("last_seen"), (int, float))
                     and isinstance(row.get("event"), str)}

    def observe(self, uses: list[dict], settings: dict, now: float) -> list[dict]:
        pending = []
        for use in uses:
            app = use["app"]
            if not settings.get("call_auto_" + app):
                continue
            previous = self.rows.get(app, {})
            if not previous or now - previous.get("last_seen", 0) > 120:
                event = hashlib.sha256(f"{use['path']}:{use['start']}".encode()).hexdigest()
                previous = {"event": event, "first_seen": now, "handled": False}
            previous["last_seen"] = now
            self.rows[app] = previous
            if not previous.get("handled") and now - previous["first_seen"] >= 2:
                pending.append({**use, "event": previous["event"]})
        return list({event["app"]: event for event in pending}.values())


def _write(path: Path, value: dict) -> None:
    temporary = path.with_name(path.name + f".{os.getpid()}.tmp")
    try:
        temporary.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def synchronize(app: Path, data: Path, token: str, port: int = 8777) -> None:
    """Apply the same saved settings to Windows login and the current login session."""
    import config
    if sys.platform != "win32":
        if enabled(config.load()):
            raise OSError("Автозапуск по звонку доступен в Windows.")
        return
    import winreg
    active = enabled(config.load())
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
        if not active:
            try:
                command = winreg.QueryValueEx(key, RUN_NAME)[0]
                if str(data).casefold() in command.casefold():
                    winreg.DeleteValue(key, RUN_NAME)
            except FileNotFoundError:
                pass
            return
        if not token or len(token) < 16:
            raise ValueError("Для фонового помощника нужен токен локальной панели.")
        python = Path(sys.executable)
        pythonw = python.with_name("pythonw.exe")
        executable = pythonw if pythonw.is_file() else python
        token_file = data / ".call-watch-token"
        token_file.write_text(token, encoding="utf-8")
        command = [str(executable), str(app / "call_watch.py"), "--data-dir", str(data),
                   "--token-file", str(token_file), "--port", str(port)]
        winreg.SetValueEx(key, RUN_NAME, 0, winreg.REG_SZ, subprocess.list2cmdline(command))
    if not lock_is_held(data / ".call-watch.lock"):
        env = {**os.environ, "BLATERO_DATA_DIR": str(data)}
        with (data / "call-watch.log").open("ab") as log:
            subprocess.Popen(command, cwd=app, env=env, stdout=log, stderr=log,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def start_capture(app: Path, data: Path, token_file: Path, port: int, event: dict) -> dict:
    url = f"http://localhost:{port}"
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    launched = False
    deadline = time.monotonic() + 40
    while True:
        token = token_file.read_text(encoding="utf-8").strip()
        request = urllib.request.Request(url + "/api/call-watch/start",
            data=json.dumps(event).encode(), headers={"Authorization": "Bearer " + token,
                "Content-Type": "application/json", "Origin": url})
        try:
            with opener.open(request, timeout=5) as response:
                result = json.load(response)
            if result.get("state") in {"started", "failed"} and not result.get("replayed"):
                os.startfile(url + "/?token=" + urllib.parse.quote(token, safe=""))
            return result
        except urllib.error.HTTPError:
            raise
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if not launched:
                env = {**os.environ, "BLATERO_DATA_DIR": str(data)}
                with (data / "call-watch-panel.log").open("ab") as log:
                    subprocess.Popen([sys.executable, str(app / "panel.py"), "--port", str(port),
                        "--token-file", str(token_file)], cwd=app, env=env, stdout=log, stderr=log,
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                launched = True
            if time.monotonic() >= deadline:
                raise RuntimeError("Blatero не ответил при автоматическом запуске.")
            time.sleep(1)


def run(data: Path, token_file: Path, port: int) -> None:
    import config
    app = Path(__file__).resolve().parent
    state_file = data / "call-watch-state.json"
    try:
        previous = json.loads(state_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        previous = {}
    if not isinstance(previous, dict):
        previous = {}
    episodes = Episodes(previous.get("episodes") if isinstance(previous.get("episodes"), dict) else None)
    error = previous.get("error", "")
    with OperationLock(data / ".call-watch.lock"):
        while enabled(config.load()):
            try:
                for event in episodes.observe(microphone_uses(), config.load(), time.time()):
                    result = start_capture(app, data, token_file, port, event)
                    episodes.rows[event["app"]]["handled"] = True
                    error = result.get("error", "")
            except Exception as exc:
                error = str(exc)
            _write(state_file, {"ts": time.time(), "episodes": episodes.rows, "error": error})
            time.sleep(2)


def status(data: Path) -> dict:
    try:
        value = json.loads((data / "call-watch-state.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        value = {}
    if not isinstance(value, dict) or not isinstance(value.get("ts", 0), (int, float)):
        value = {}
    return {"supported": sys.platform == "win32", "running": 0 <= time.time() - value.get("ts", 0) < 8,
            "error": value.get("error", "")}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--token-file", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8777)
    args = parser.parse_args()
    data = Path(args.data_dir).resolve()
    os.environ["BLATERO_DATA_DIR"] = str(data)
    try:
        run(data, args.token_file, args.port)
    except OperationLockError:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
