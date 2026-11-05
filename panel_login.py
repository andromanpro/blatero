"""Explicit login for browser deep links; never disclose the server token."""

from html import escape
from urllib.parse import parse_qsl, urlencode, urlsplit
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
import ipaddress


def local_browser_entry(request, state):
    """Only an opted-in, user-activated top-level loopback page navigation.

    Never bootstrap API/fetch/iframes/LAN requests. Host validation still runs
    first in the caller; the socket peer and URL host must both be loopback.
    """
    if state.get("local_browser_auto_login") is not True or not state.get("access_token"):
        return False
    if request.method != "GET" or request.url.path not in ("/", "/projects"):
        return False
    if "text/html" not in request.headers.get("accept", "") or "token" in request.query_params:
        return False
    try:
        if not request.client or not ipaddress.ip_address(request.client.host).is_loopback:
            return False
        host = request.url.hostname
        if host != "localhost" and not ipaddress.ip_address(host).is_loopback:
            return False
    except ValueError:
        return False
    if request.headers.get("origin") not in (None, str(request.base_url).rstrip("/")):
        return False
    return (
        request.headers.get("sec-fetch-mode") == "navigate"
        and request.headers.get("sec-fetch-dest") == "document"
        and request.headers.get("sec-fetch-user") == "?1"
    )


def remember_local_browser(response, request, token):
    response.set_cookie(
        "blatero_token",
        token,
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="strict",
        path="/",
        max_age=30 * 24 * 60 * 60,
    )
    return response


def destination(value):
    value = str(value or "/")
    if not value.startswith("/") or value.startswith("//") or any(c in value for c in "\\\r\n"):
        return "/"
    parts = urlsplit(value)
    if parts.scheme or parts.netloc:
        return "/"
    return parts.path + (
        "?" + urlencode([(k, v) for k, v in parse_qsl(parts.query) if k != "token"])
        if parts.query
        else ""
    )


def page(next_url, error=False):
    next_url = escape(destination(next_url), quote=True)
    return HTMLResponse(
        """<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Вход в Blatero</title><style>body{margin:0;background:#080e13;color:#eaf0f4;font:16px system-ui;display:grid;min-height:100vh;place-items:center}main{max-width:520px;margin:24px;padding:32px;border:1px solid #34434a;border-radius:18px}h1{color:#d6ff62}p{line-height:1.6;color:#acbbc5}input,button{box-sizing:border-box;padding:13px;width:100%;margin-top:12px;border-radius:8px;border:1px solid #40515d;background:#131f28;color:#fff}button{background:#d6ff62;color:#101710;font-weight:bold}code{overflow-wrap:anywhere}.error{color:#ff9b9b}</style><main><h1>Вход в Blatero</h1><p>В этом браузере ещё нет доступа к локальному Blatero. Открой приложение обычным ярлыком в этом браузере, затем вернись к ссылке.</p><p>Либо введи токен из локального файла <code>%LOCALAPPDATA%/blatero/access-token</code>. После входа откроется выбранный раздел. Адреса localhost и 127.0.0.1 имеют разные cookies.</p>"""
        + ('<p class="error">Токен не подошёл. Проверь файл доступа.</p>' if error else "")
        + '''<form action="/auth/login" method="post"><label>Токен доступа<input type="password" name="token" maxlength="512" required autocomplete="off"></label><input type="hidden" name="next" value="'''
        + next_url
        + """"><button>Войти</button></form></main></html>""",
        status_code=401,
        headers={"Referrer-Policy": "same-origin"},
    )


async def login(request, valid):
    if request.headers.get("origin") != str(request.base_url).rstrip("/"):
        return PlainTextResponse("Недопустимый источник запроса", status_code=403)
    if request.headers.get("content-type", "").split(";")[0] != "application/x-www-form-urlencoded":
        return PlainTextResponse("Недопустимый формат", status_code=415)
    body = b""
    async for part in request.stream():
        body += part
        if len(body) > 4096:
            return PlainTextResponse("Запрос слишком большой", status_code=413)
    try:
        data = dict(parse_qsl(body.decode("utf-8"), max_num_fields=4))
    except (ValueError, UnicodeError):
        return PlainTextResponse("Недопустимый запрос", status_code=400)
    if not valid(data.get("token")):
        return page(data.get("next"), True)
    response = RedirectResponse(destination(data.get("next")), status_code=303)
    response.set_cookie(
        "blatero_token",
        data["token"],
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="strict",
        path="/",
    )
    return response
