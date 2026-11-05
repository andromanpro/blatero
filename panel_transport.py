"""Транспортные границы веб-панели: Host/auth/rate-limit и broadcast."""

import asyncio
import ipaddress
import os
import secrets
import socket
import time
from urllib.parse import urlparse, urlsplit


APP_CONTENT_SECURITY_POLICY = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; media-src 'self' blob:; connect-src 'self'; "
    "object-src 'none'; base-uri 'none'; frame-ancestors 'none'; "
    "form-action 'self'; worker-src 'none'"
)


def apply_security_headers(headers, path: str = "") -> None:
    """Добавить browser hardening, не затирая более строгую политику route."""
    defaults = {
        "Content-Security-Policy": APP_CONTENT_SECURITY_POLICY,
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "no-referrer",
        "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
        "Cross-Origin-Opener-Policy": "same-origin",
    }
    if not str(path).startswith("/assets/"):
        defaults["Cache-Control"] = "no-store"
    for name, value in defaults.items():
        if name not in headers:
            headers[name] = value


def token_ok(state: dict, value: str | None) -> bool:
    expected = state.get("access_token")
    return bool(expected and value and secrets.compare_digest(str(value), expected))


def hostname_from_authority(authority: str | None) -> str | None:
    """Безопасно извлечь hostname из Host/authority без userinfo и путей."""
    value = str(authority or "").strip()
    if (not value or len(value) > 253 or "@" in value
            or any(character.isspace() for character in value)
            or any(character in value for character in "/\\?#")):
        return None
    try:
        parsed = urlsplit(f"//{value}")
        # Обращение к port дополнительно отсекает нечисловой/вне диапазона порт.
        parsed.port
    except ValueError:
        return None
    hostname = (parsed.hostname or "").rstrip(".").casefold()
    return hostname or None


def configured_allowed_hosts(lan_mode: bool) -> frozenset[str]:
    """Имена машины плюс явный allowlist; wildcard намеренно запрещён."""
    candidates = {"localhost"}
    if lan_mode:
        candidates.update({socket.gethostname(), socket.getfqdn()})
    candidates.update(
        item.strip() for item in os.environ.get("BLATERO_ALLOWED_HOSTS", "").split(",")
        if item.strip()
    )
    normalized = set()
    for candidate in candidates:
        hostname = hostname_from_authority(candidate)
        if not hostname or hostname == "*":
            raise ValueError(f"некорректный BLATERO_ALLOWED_HOSTS: {candidate!r}")
        normalized.add(hostname)
    return frozenset(normalized)


def host_allowed(state: dict, authority: str | None) -> bool:
    """Закрыть DNS-rebinding: принимать только loopback/LAN IP или allowlist."""
    hostname = hostname_from_authority(authority)
    if not hostname:
        return False
    if hostname in state.get("allowed_hosts", ()) or hostname == "localhost":
        return True
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        return False
    if address.is_loopback:
        return True
    return bool(state.get("lan_mode") and (address.is_private or address.is_link_local))


def rate_allowed(rate_limits: dict, area: str, client: str, limit: int,
                 window: float = 60.0) -> bool:
    now = time.monotonic()
    key = (area, client or "unknown")
    started, count = rate_limits.get(key, (now, 0))
    if now - started >= window:
        started, count = now, 0
    count += 1
    rate_limits[key] = (started, count)
    return count <= limit


def same_origin(origin: str | None, host: str | None) -> bool:
    """Разрешить запрос без Origin или только с Origin текущего Host."""
    return not origin or urlparse(origin).netloc == str(host or "")


def is_loopback(host: str | None) -> bool:
    try:
        return ipaddress.ip_address(str(host)).is_loopback
    except (ValueError, TypeError):
        return False


async def broadcast_json(clients: set, message: dict, timeout: float = 3.0) -> None:
    """Разослать сообщение параллельно и удалить зависшие соединения."""
    targets = tuple(clients)
    if not targets:
        return

    async def send(ws):
        try:
            await asyncio.wait_for(ws.send_json(message), timeout=timeout)
            return None
        except Exception:
            return ws

    dead = await asyncio.gather(*(send(ws) for ws in targets))
    for ws in dead:
        if ws is not None:
            clients.discard(ws)
