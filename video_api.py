"""Loopback-only video boundary. Captures require explicit prepare, preview, then start."""

import asyncio
import json

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse

import video_capture
import video_sources


def create_router(*, manager, scope, loopback, origin, is_json, rate_allowed):
    router = APIRouter(prefix="/api/video")

    def forbidden(request, write=False):
        if not loopback(request) or (write and not origin(request)):
            return PlainTextResponse("video_local_only", status_code=403)
        if write and not is_json(request):
            return PlainTextResponse("video_json_required", status_code=415)
        return None

    @router.get("/sources")
    async def sources(request: Request, session: str, generation: int):
        denied = forbidden(request)
        if denied is not None:
            return denied
        try:
            scope(session, generation)
            capability = video_capture.capability()
            return JSONResponse(
                {
                    **capability,
                    "sources": await asyncio.to_thread(video_sources.sources)
                    if capability["available"]
                    else [],
                }
            )
        except (OSError, ValueError) as exc:
            return PlainTextResponse(str(exc), status_code=400)

    @router.get("/status")
    async def status(request: Request, session: str, generation: int):
        denied = forbidden(request)
        if denied is not None:
            return denied
        try:
            job = scope(session, generation)
            return JSONResponse({"items": await asyncio.to_thread(video_capture.listing, job.sdir)})
        except (OSError, ValueError) as exc:
            return PlainTextResponse(str(exc), status_code=400)

    @router.post("/action")
    async def action(request: Request):
        denied = forbidden(request, True)
        if denied is not None:
            return denied
        if not rate_allowed(request, "video-action", 40):
            return PlainTextResponse("video_rate_limited", status_code=429)
        raw = bytearray()
        async for chunk in request.stream():
            if len(raw) + len(chunk) > 8192:
                return PlainTextResponse("video_request_too_large", status_code=413)
            raw.extend(chunk)
        try:
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError("video_invalid_request")
            job = scope(data.get("session"), data.get("generation"))
            if data.get("action") == "prepare":
                if not video_capture.capability()["available"]:
                    return PlainTextResponse("video_component_missing", status_code=503)
                value = await asyncio.to_thread(
                    manager.prepare,
                    job.sdir,
                    data.get("source"),
                    data.get("id"),
                    fps=data.get("fps", 15),
                )
            else:
                value = await asyncio.to_thread(
                    manager.action, job.sdir, data.get("id"), data.get("action")
                )
            return JSONResponse(value, status_code=202)
        except (OSError, ValueError, RuntimeError) as exc:
            message = str(exc) if str(exc).startswith("video_") else "video_action_failed"
            return PlainTextResponse(message, status_code=409)

    @router.get("/file/{run}/{name}")
    async def file(request: Request, run: str, name: str, session: str, generation: int):
        denied = forbidden(request)
        if denied is not None:
            return denied
        try:
            job = scope(session, generation)
            if name not in {"preview.png", "recording.mkv", "recording.partial.mkv"}:
                raise ValueError("video_invalid_file")
            folder = video_capture.run_folder(job.sdir, run)
            value = video_capture.effective_state(folder)
            if name != "preview.png" and value["phase"] in video_capture.ACTIVE:
                return PlainTextResponse("video_still_recording", status_code=409)
            target = folder / name
            if not target.is_file() or target.is_symlink():
                raise ValueError("video_file_missing")
            return FileResponse(
                target,
                media_type="image/png" if name.endswith(".png") else "video/x-matroska",
                filename=None if name.endswith(".png") else f"video-{run}.mkv",
                headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
            )
        except (OSError, ValueError) as exc:
            return PlainTextResponse(str(exc), status_code=404)

    return router
