"""Оркестрация переноса, retention и удаления сессий для веб-панели.

Модуль не импортирует ``panel`` и получает все UI/session зависимости явно.
Криптографическая и файловая граница остаётся в :mod:`session_lifecycle`.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable, Mapping

import session_lifecycle
from session_utils import direct_child


def session_has_active_job(sdir: Path, active_jobs: Mapping) -> bool:
    target = Path(sdir).resolve()
    return any(Path(job.sdir).resolve() == target for job in active_jobs.values())


def lifecycle_payload(base: Path, state: dict, *, message: str = "",
                      error: bool = False, busy: bool | None = None) -> dict:
    try:
        policy = session_lifecycle.load_retention_policy(base)
        retention = session_lifecycle.retention_preview(base / "sessions", policy)
    except (OSError, ValueError, session_lifecycle.SessionPackageError) as exc:
        policy = dict(session_lifecycle.DEFAULT_RETENTION)
        retention = {"policies": {}, "sessions": 0, "files": 0,
                     "bytes": 0, "items": [], "error": str(exc)}
    return {
        "type": "session_lifecycle",
        "busy": bool(state.get("lifecycle_busy")) if busy is None else busy,
        "packages": session_lifecycle.list_packages(base),
        "privacy_inventory": session_lifecycle.personal_data_inventory(base),
        "retention_policy": policy,
        "retention": retention,
        "message": message,
        "error": error,
    }


@dataclass(frozen=True)
class LifecyclePanel:
    base: Path
    state: dict
    has_active_job: Callable[[Path], bool]
    recording_active: Callable[[Path | None], bool]
    recording_locked: Callable[[], bool]
    choose_package: Callable[[], str]
    open_directory: Callable[[Path], None]
    archive_items: Callable[[str | None], list[dict]]
    session_contour: Callable[[Path | None], str]
    list_sessions: Callable[[str | None], list[dict]]
    advance_generation: Callable[[], int]
    init_payload: Callable[[], dict]
    broadcast: Callable[[dict], Awaitable[None]]

    @property
    def sessions_root(self) -> Path:
        return (self.base / "sessions").resolve()

    def payload(self, *, message: str = "", error: bool = False,
                busy: bool | None = None) -> dict:
        return lifecycle_payload(
            self.base, self.state, message=message, error=error, busy=busy)

    async def _broadcast_archive(self) -> None:
        await self.broadcast({
            "type": "archive",
            "items": self.archive_items(self.session_contour(self.state["sdir"])),
        })

    async def _validate_session_target(self, command: str, session_name: str):
        if command not in {
                "session_export", "session_purge_preview", "session_purge_apply"}:
            return None
        target = direct_child(self.sessions_root, session_name, must_exist=True)
        if self.recording_active(target) or self.has_active_job(target):
            raise RuntimeError(
                "сначала завершите запись и фоновые задачи этой встречи")
        return target

    async def handle(self, ws: Any, msg: dict) -> None:
        command = str(msg.get("type") or "")
        if command == "lifecycle_status":
            await ws.send_json(self.payload())
            return
        if self.state.get("lifecycle_busy"):
            await ws.send_json(self.payload(
                message="другая операция с архивом ещё выполняется", error=True))
            return

        session_name = str(msg.get("session") or "")
        try:
            target = await self._validate_session_target(command, session_name)
        except (OSError, ValueError, RuntimeError) as exc:
            await ws.send_json(self.payload(message=str(exc), error=True))
            return

        if command == "session_purge_preview":
            try:
                preview = session_lifecycle.purge_preview(
                    self.sessions_root, session_name,
                    set(msg.get("categories") or []))
            except (OSError, ValueError,
                    session_lifecycle.SessionPackageError) as exc:
                await ws.send_json(self.payload(message=str(exc), error=True))
                return
            await ws.send_json({**self.payload(), "purge_preview": preview})
            return

        if command == "retention_save":
            try:
                session_lifecycle.save_retention_policy(
                    self.base, dict(msg.get("policies") or {}))
            except (OSError, ValueError,
                    session_lifecycle.SessionPackageError) as exc:
                await ws.send_json(self.payload(message=str(exc), error=True))
                return
            await ws.send_json(self.payload(
                message="сроки сохранены; удаление не запускалось"))
            return

        self.state["lifecycle_busy"] = True
        await ws.send_json(self.payload(message="операция с архивом выполняется…"))
        try:
            if command == "session_export":
                await self._export(ws, msg, session_name)
            elif command == "session_import":
                await self._import(ws, msg)
            elif command == "session_purge_apply":
                await self._purge(ws, msg, session_name, target)
            elif command == "retention_apply":
                await self._apply_retention(ws, msg)
            elif command == "lifecycle_open_packages":
                await asyncio.to_thread(
                    self.open_directory, session_lifecycle.packages_root(self.base))
                await ws.send_json(self.payload(
                    message="папка пакетов открыта", busy=False))
            elif command == "session_package_delete":
                await self._delete_package(ws, msg)
            else:
                raise ValueError("неизвестная операция жизненного цикла")
        except (OSError, ValueError, RuntimeError,
                session_lifecycle.SessionPackageError) as exc:
            await ws.send_json(self.payload(
                message=str(exc), error=True, busy=False))
        finally:
            self.state["lifecycle_busy"] = False

    async def _export(self, ws: Any, msg: dict, session_name: str) -> None:
        result = await asyncio.to_thread(
            session_lifecycle.export_session, self.sessions_root, session_name,
            self.base, str(msg.get("password") or ""))
        await ws.send_json({
            **self.payload(message=(
                f"зашифрованный пакет готов · {result['files']} файлов"),
                busy=False),
            "exported": {key: value for key, value in result.items()
                         if key != "path"},
            "download_url": f"/api/session-packages/{result['name']}",
        })

    async def _import(self, ws: Any, msg: dict) -> None:
        if self.recording_locked():
            raise RuntimeError("остановите запись перед импортом архива")
        selected = await asyncio.to_thread(self.choose_package)
        if not selected:
            await ws.send_json(self.payload(message="импорт отменён", busy=False))
            return
        result = await asyncio.to_thread(
            session_lifecycle.import_package, Path(selected),
            str(msg.get("password") or ""), self.sessions_root, self.base)
        await self._broadcast_archive()
        sessions = self.list_sessions(self.session_contour(self.state["sdir"]))
        self.state["sessions_cache"] = sessions
        await self.broadcast({"type": "sessions", "sessions": sessions,
                              "current_dir": self.state["sdir"].name})
        await ws.send_json(self.payload(
            message=(f"сессия импортирована как {result['session']} · "
                     f"{result['files']} файлов"), busy=False))

    async def _delete_package(self, ws: Any, msg: dict) -> None:
        name = str(msg.get("name") or "")
        if str(msg.get("confirmation") or "") != f"DELETE PACKAGE:{name}":
            raise ValueError("удаление пакета не подтверждено")
        result = await asyncio.to_thread(
            session_lifecycle.delete_package, self.base, name)
        await ws.send_json(self.payload(message=(
            f"зашифрованный пакет удалён · {result['bytes'] / 1048576:.1f} МБ"),
            busy=False))

    async def _purge(self, ws: Any, msg: dict, session_name: str,
                     target: Path | None) -> None:
        if target is None:
            raise ValueError("сессия для удаления не выбрана")
        categories = set(msg.get("categories") or [])
        if str(msg.get("confirmation") or "") != f"DELETE:{session_name}":
            raise ValueError("подтверждение удаления не совпало с именем сессии")
        current = target.resolve() == self.state["sdir"].resolve()
        if "all" in categories and current:
            raise ValueError(
                "нельзя удалить открытую сессию целиком; сначала переключитесь")
        result = await asyncio.to_thread(
            session_lifecycle.purge, self.sessions_root, session_name,
            categories, self.base)
        if current:
            self.advance_generation()
            self.state.update(prev=[], signals=[], last_asked=None,
                              transcript_cache=None)
            await self.broadcast(self.init_payload())
        await self._broadcast_archive()
        await ws.send_json(self.payload(message=(
            f"удалено: {result['files']} файлов · "
            f"{result['bytes'] / 1048576:.1f} МБ"), busy=False))

    async def _apply_retention(self, ws: Any, msg: dict) -> None:
        if str(msg.get("confirmation") or "") != "APPLY RETENTION":
            raise ValueError("не подтверждено применение сроков хранения")
        policy = session_lifecycle.load_retention_policy(self.base)
        plan = session_lifecycle.retention_preview(self.sessions_root, policy)
        for item in plan["items"]:
            candidate = direct_child(
                self.sessions_root, item["session"], must_exist=True)
            if self.recording_active(candidate) or self.has_active_job(candidate):
                raise RuntimeError(
                    f"у встречи {item['session']} ещё идёт запись или задача")
            if ("all" in item["categories"]
                    and candidate.resolve() == self.state["sdir"].resolve()):
                raise RuntimeError(
                    "retention не удаляет открытую сессию целиком; переключитесь")
        result = await asyncio.to_thread(
            session_lifecycle.apply_retention, self.sessions_root, policy, self.base)
        current_changed = any(
            item["session"] == self.state["sdir"].name for item in result["items"])
        if current_changed:
            self.advance_generation()
            self.state.update(prev=[], signals=[], last_asked=None,
                              transcript_cache=None)
            await self.broadcast(self.init_payload())
        await self._broadcast_archive()
        await ws.send_json(self.payload(message=(
            f"retention применён: {result['sessions']} встреч · "
            f"{result['files']} файлов"), busy=False))
