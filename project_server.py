"""Open only the Projects mode locally without restarting meeting capture."""
from __future__ import annotations

import argparse
import asyncio
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse

import app_paths
import panel_transport
import project_api


@asynccontextmanager
async def lifespan(app):
    project_api.default_store().local_agent()
    worker = asyncio.create_task(project_api.queue_worker())
    try:
        yield
    finally:
        worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)


app = FastAPI(lifespan=lifespan)
app.include_router(project_api.create_router())


@app.middleware("http")
async def host_guard(request: Request, call_next):
    if not panel_transport.host_allowed({}, request.headers.get("host")):
        return JSONResponse({"error": "неверный Host"}, status_code=400)
    response = await call_next(request)
    panel_transport.apply_security_headers(response.headers, request.url.path)
    return response


@app.get("/")
def root():
    return RedirectResponse("/projects")


@app.get("/assets/fonts/{name}")
def font(name: str):
    if name not in {"Inter-400.ttf", "Inter-600.ttf", "Manrope-700.ttf", "Manrope-800.ttf"}:
        return JSONResponse({"error": "файл не найден"}, status_code=404)
    return FileResponse(app_paths.APP_ROOT / "assets/fonts" / name, media_type="font/ttf")


@app.get("/assets/{name}")
def workspace_asset(name: str):
    types = {"workspace.css": "text/css", "workspace.js": "text/javascript",
             "i18n.js": "text/javascript", "settings-i18n.js": "text/javascript",
             "wizard-i18n.js": "text/javascript",
             "meeting-i18n.js": "text/javascript",
             "projects-i18n.js": "text/javascript",
             "workspace-preferences.js": "text/javascript",
             "workspace-guide.js": "text/javascript", "training-avatars.js": "text/javascript",
             "scene-live.js": "text/javascript", "studio-i18n.js": "text/javascript",
             "scene-audio.js": "text/javascript",
             "brand.css": "text/css", "brand.js": "text/javascript",
             "blatero-mark.svg": "image/svg+xml", "blatero.ico": "image/vnd.microsoft.icon",
             "blatero-icon-256.png": "image/png"}
    if name not in types:
        return JSONResponse({"error": "файл не найден"}, status_code=404)
    return FileResponse(app_paths.APP_ROOT / "assets" / name,
                        media_type=types[name])


def main():
    parser = argparse.ArgumentParser(description="Локальная доска задач Blatero")
    parser.add_argument("--port", type=int, default=8790)
    args = parser.parse_args()
    uvicorn.run(app, host="127.0.0.1", port=args.port, loop="server_runtime:loop_factory")


if __name__ == "__main__":
    main()
