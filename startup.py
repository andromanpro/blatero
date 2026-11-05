"""Small startup helpers used by ``start_blatero.cmd`` and portable launcher.

The launcher deliberately keeps secrets out of command-line arguments.  The
server receives only a token-file path; browser opening reads the token from
disk locally and appends it to the localhost URL.
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

TOKEN_BYTES = 32
PORT = 8777


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """Treat auth redirect as a successful readiness signal for the real browser."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def prepare_token(path: str | Path) -> Path:
    target = Path(path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    current = ""
    if target.is_file():
        current = target.read_text(encoding="utf-8", errors="ignore").strip()
    if len(current) < 24:
        target.write_text(secrets.token_urlsafe(TOKEN_BYTES), encoding="utf-8")
    return target


def token_url(path: str | Path, *, port: int = PORT) -> str:
    token = Path(path).read_text(encoding="utf-8").strip()
    if not token:
        raise ValueError("access token file is empty")
    return f"http://localhost:{port}/?token={urllib.parse.quote(token, safe='')}"


def open_when_ready(path: str | Path, *, seconds: float, port: int = PORT) -> bool:
    url = token_url(path, port=port)
    deadline = time.monotonic() + max(0.0, seconds)
    opener = urllib.request.build_opener(NoRedirect)
    while True:
        try:
            with opener.open(url, timeout=2) as response:  # nosec B310
                if response.status == 200:
                    os.startfile(url)  # type: ignore[attr-defined]
                    return True
        except urllib.error.HTTPError as exc:
            if exc.code in {302, 303, 307, 308}:
                os.startfile(url)  # type: ignore[attr-defined]
                return True
        except (OSError, urllib.error.URLError, TimeoutError):
            pass
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.3)


def check_install(app_dir: str | Path, data_dir: str | None = None) -> dict:
    app = Path(app_dir).resolve()
    checks = []

    def add(key: str, ok: bool, message: str) -> None:
        checks.append({"key": key, "ok": ok, "message": message})

    add("panel", (app / "panel.py").is_file(), "найден panel.py")
    add("startup", (app / "startup.py").is_file(), "найден startup.py")
    add("launcher", (app / "start_blatero.cmd").is_file(), "найден start_blatero.cmd")
    add("write_app", os.access(app, os.R_OK), "каталог приложения доступен для чтения")
    if data_dir:
        data = Path(data_dir).expanduser()
        try:
            data.mkdir(parents=True, exist_ok=True)
            probe = data / ".blatero-startup-write.tmp"
            probe.write_text("ok", encoding="ascii")
            probe.unlink(missing_ok=True)
            add("write_data", True, "каталог данных доступен для записи")
        except OSError as exc:
            add("write_data", False, f"каталог данных недоступен: {exc}")
    ok = all(item["ok"] for item in checks)
    return {"ok": ok, "checks": checks}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("prepare-token")
    prepare.add_argument("path")
    open_ready = sub.add_parser("open-when-ready")
    open_ready.add_argument("path")
    open_ready.add_argument("--seconds", type=float, default=30.0)
    open_ready.add_argument("--port", type=int, default=PORT)
    check = sub.add_parser("check")
    check.add_argument("--app-dir", default=".")
    check.add_argument("--data-dir")
    args = parser.parse_args(argv)
    if args.command == "prepare-token":
        prepare_token(args.path)
        return 0
    if args.command == "open-when-ready":
        return 0 if open_when_ready(args.path, seconds=args.seconds, port=args.port) else 1
    if args.command == "check":
        payload = check_install(args.app_dir, args.data_dir)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if payload["ok"] else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
