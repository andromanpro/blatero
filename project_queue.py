"""Atomic per-event spool. Usable by hooks even when the UI/server is closed."""
from __future__ import annotations

import ctypes
import hashlib
import hmac
import json
import os
import sqlite3
import time
import uuid
from pathlib import Path

from operation_lock import OperationLock, OperationLockError
from project_contract import canonical, validate
from project_store import Store, now


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    try:
        with temp.open("w", encoding="utf-8", newline="\n") as stream:
            stream.write(canonical(value) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def event_path(root: Path, event_id: str) -> Path:
    return root / "inbox" / (hashlib.sha256(event_id.encode()).hexdigest() + ".json")


def publish_once(path: Path, packet: dict) -> bool:
    """Publish complete bytes without replacing a concurrent delivery."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        atomic_json(temp, packet)
        deadline = time.monotonic() + 1
        while True:
            try:
                os.link(temp, path)
                return True
            except FileExistsError:
                try:
                    existing = json.loads(path.read_text(encoding="utf-8"))
                except (FileNotFoundError, PermissionError):
                    # The consumer may claim the existing packet between link
                    # and comparison. Retry publication of the same complete bytes.
                    if time.monotonic() >= deadline:
                        raise
                    time.sleep(.01)
                    continue
                if existing != packet:
                    raise ValueError("event_id в очереди уже использован для другого содержимого")
                return False
            except PermissionError:
                # Windows can briefly deny the destination during a rename.
                # A persistent permission error is still returned to the caller.
                if time.monotonic() >= deadline:
                    raise
                time.sleep(.01)
    finally:
        temp.unlink(missing_ok=True)


def enqueue(root: Path, event: dict, token: str) -> dict:
    validate(event)
    hashed = hashlib.sha256(token.encode()).hexdigest()
    packet = {"event": event, "actor_id": event["actor"]["id"],
              "signature": hmac.new(hashed.encode(), canonical(event).encode(), hashlib.sha256).hexdigest()}
    path = event_path(root, event["event_id"])
    fresh = publish_once(path, packet)
    return {"state": "queued", "event_id": event["event_id"], "replayed": not fresh}


def process_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
        kernel.OpenProcess.restype = ctypes.c_void_p
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            return ctypes.get_last_error() == 5
        try:
            code = ctypes.c_uint32()
            kernel.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
            return bool(kernel.GetExitCodeProcess(handle, ctypes.byref(code))) and code.value == 259
        finally:
            kernel.CloseHandle.argtypes = [ctypes.c_void_p]
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def recover(root: Path, *, include_live: bool = False) -> int:
    count = 0
    (root / "inbox").mkdir(parents=True, exist_ok=True)
    for path in (root / "processing").glob("*.json"):
        try:
            pid = int(path.name.split("-", 1)[0])
            # include_live is only used by the exclusive delivery-lock owner:
            # a live PID can have abandoned a claim after a transient I/O error.
            if not include_live and (process_alive(pid) or time.time() - path.stat().st_mtime < 1):
                continue
            packet = json.loads(path.read_text(encoding="utf-8"))
            target = event_path(root, packet["event"]["event_id"])
            # An existing retry must not be overwritten by a different event body.
            publish_once(target, packet)
            path.unlink()
            count += 1
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return count


def drain(store: Store, limit: int = 50) -> dict:
    # Exactly one consumer owns file claims/recovery at a time. The OS releases
    # this lock after a crash; producers still publish without waiting for it.
    lock = OperationLock(store.root / "delivery.lock")
    try:
        lock.acquire()
    except OperationLockError:
        return {"applied": 0, "conflict": 0, "rejected": 0, "replayed": 0,
                "recovered": 0, **status(store.root)}
    try:
        return _drain(store, limit)
    finally:
        lock.release()


def _drain(store: Store, limit: int) -> dict:
    root = store.root
    (root / "processing").mkdir(parents=True, exist_ok=True)
    counts = {"applied": 0, "conflict": 0, "rejected": 0, "replayed": 0,
              "deferred": 0, "recovered": recover(root, include_live=True)}
    def delivery_order(path):
        try:
            if path.stat().st_size > 128 * 1024:
                return (0, "", 0, path.name)
            event = json.loads(path.read_text(encoding="utf-8"))["event"]
            return (0 if event["event_type"] == "task.created" else 1,
                    str(event["emitted_at"]), int(event["source"]["sequence"]), path.name)
        except (OSError, ValueError, KeyError, TypeError):
            return (0, "", 0, path.name)
    for path in sorted((root / "inbox").glob("*.json"), key=delivery_order)[:limit]:
        claimed = root / "processing" / f"{os.getpid()}-{uuid.uuid4().hex}-{path.name}"
        try:
            os.replace(path, claimed)
        except FileNotFoundError:
            continue
        except PermissionError as exc:
            # A competing Windows consumer can still be reading delivery_order.
            # Leave the durable inbox entry for the next pass; ACL errors propagate.
            if getattr(exc, "winerror", None) not in {32, 33}:
                raise
            continue
        try:
            oversized = claimed.stat().st_size > 128 * 1024
            with claimed.open(encoding="utf-8", errors="replace") as stream:
                raw = stream.read(65536 if oversized else 128 * 1024)
            try:
                if oversized:
                    raise ValueError("поврежденная запись очереди превышает лимит")
                packet = json.loads(raw)
                event = packet["event"]
                # PermissionError here is an authentication rejection, not disk I/O.
                principal = store.queued_principal(packet["actor_id"], event, packet["signature"])
                result = store.apply(event, principal)
                receipt = {"event": event, "result": result, "processed_at": now()}
            except (ValueError, PermissionError, KeyError, TypeError) as exc:
                result = {"state": "rejected"}
                receipt = {"error": str(exc), "processed_at": now(), "packet": raw[:65536]}
            target = root / ("processed" if result["state"] == "applied" else "rejected") / path.name
            _save_receipt(target, receipt)
            claimed.unlink()
            counts["replayed" if result.get("replayed") else result["state"]] += 1
        except (sqlite3.OperationalError, OSError):
            counts["deferred"] += 1
            # Keep at least one durable packet even if the disk is completely full.
            # The next lock owner also recovers abandoned claims of this live PID.
            try:
                publish_once(path, json.loads(claimed.read_text(encoding="utf-8")))
                claimed.unlink()
            except (OSError, ValueError, KeyError, TypeError):
                pass
            break
    return {**counts, **status(root)}


def _save_receipt(path, receipt):
    """One receipt per delivery; keep the first durable result on replay."""
    try:
        existing = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        atomic_json(path, receipt)
        return
    except (ValueError, UnicodeError) as exc:
        raise OSError("повреждена квитанция доставки; исходный пакет сохранён") from exc
    key = "event" if "event" in receipt else "packet"
    if not isinstance(existing, dict) or existing.get(key) != receipt.get(key):
        raise ValueError("квитанция уже относится к другому содержимому")


def status(root: Path) -> dict:
    return {"pending": len(list((root / "inbox").glob("*.json"))),
            "processing": len(list((root / "processing").glob("*.json"))),
            "rejected_total": len(list((root / "rejected").glob("*.json")))}
