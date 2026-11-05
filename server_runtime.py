"""Application-owned event-loop factory; never changes the system Python files."""

from __future__ import annotations

import asyncio
import logging
import socket
import sys

LOGGER = logging.getLogger(__name__)
WINDOWS_312 = sys.platform == "win32" and sys.version_info[:2] == (3, 12)
if WINDOWS_312:
    from asyncio.proactor_events import _ProactorSocketTransport

    class _SafeTcpTransport(_ProactorSocketTransport):
        """Always release a TCP transport, including after WinError10054.

        CPython 3.12 can leave Server._active_count attached if shutdown() raises.
        A closed peer is not a reason to retain the transport indefinitely.
        Only this application's TCP transports use the override; pipe/subprocess
        transports, asyncio policies and installed Python files are unchanged.
        """

        def _call_connection_lost(self, exc):
            if self._called_connection_lost:
                return
            try:
                self._protocol.connection_lost(exc)
            finally:
                sock = self._sock
                try:
                    if sock is not None and sock.fileno() != -1:
                        try:
                            sock.shutdown(socket.SHUT_RDWR)
                        except ConnectionResetError as error:
                            if getattr(error, "winerror", None) != 10054:
                                raise
                            LOGGER.warning("Windows TCP reset during close; transport released")
                finally:
                    try:
                        if sock is not None:
                            sock.close()
                    finally:
                        self._sock = None
                        server, self._server = self._server, None
                        self._called_connection_lost = True
                        if server is not None:
                            server._detach()

    class _SafeProactorLoop(asyncio.ProactorEventLoop):
        def _make_socket_transport(self, sock, protocol, waiter=None, extra=None, server=None):
            return _SafeTcpTransport(self, sock, protocol, waiter, extra, server)


def loop_factory():
    """Keep Proactor subprocess support; limit the compatibility shim to 3.12."""
    return _SafeProactorLoop() if WINDOWS_312 else asyncio.new_event_loop()
