"""Local-only HTTP server: the overlay page, a JSON snapshot and a Server-Sent Events stream.

  GET /         overlay page (query options: see README)
  GET /state    latest snapshot, JSON
  GET /events   the same snapshot as SSE — pushed on every change and at least every HEARTBEAT_S

Binds 127.0.0.1 only, and answers only requests whose Host is 127.0.0.1 / localhost on this port, so a page on another
site can't read the stream through DNS rebinding. GET only: nothing here changes anything.
"""
from __future__ import annotations

import json
import socket
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional

from .reader import Reader

HOST = "127.0.0.1"
DEFAULT_PORT = 47820
HEARTBEAT_S = 0.5
PAGE = Path(__file__).resolve().parent / "web" / "overlay.html"


class Hub:
    """What the pages see: the reader's pads, the source name and the visibility toggle. Wakes the SSE streams."""

    def __init__(self, reader: Optional[Reader], source: str):
        self.reader, self.source = reader, source
        self.cond = threading.Condition()
        self.version = 0
        self.visible = True
        self.closed = False

    def bump(self) -> None:
        with self.cond:
            self.version += 1
            self.cond.notify_all()

    def toggle_visible(self) -> None:
        with self.cond:
            self.visible = not self.visible
            self.version += 1
            self.cond.notify_all()

    def close(self) -> None:
        with self.cond:
            self.closed = True
            self.cond.notify_all()

    def snapshot(self) -> dict:
        with self.cond:
            version, visible = self.version, self.visible
        pads = self.reader.snapshot() if self.reader is not None else {}
        return {"v": version, "source": self.source, "visible": visible, "pads": pads}


def _handler(hub: Hub, page: Optional[bytes]):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args) -> None:
            pass

        def _host_ok(self) -> bool:
            port = self.server.server_address[1]
            return self.headers.get("Host", "") in (f"127.0.0.1:{port}", f"localhost:{port}")

        def _send(self, code: int, body: bytes, ctype: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            if not self._host_ok():
                self._send(403, b"forbidden", "text/plain")
                return
            path = self.path.split("?", 1)[0]
            if path == "/":
                self._send(200, page if page is not None else PAGE.read_bytes(), "text/html; charset=utf-8")
            elif path == "/state":
                self._send(200, json.dumps(hub.snapshot()).encode(), "application/json")
            elif path == "/events":
                self._events()
            else:
                self._send(404, b"not found", "text/plain")

        def _events(self) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            seen = -1
            try:
                while True:
                    with hub.cond:
                        hub.cond.wait_for(lambda: hub.version != seen or hub.closed, timeout=HEARTBEAT_S)
                        if hub.closed:
                            return
                        seen = hub.version
                    self.wfile.write(b"data: " + json.dumps(hub.snapshot()).encode() + b"\n\n")
                    self.wfile.flush()
            except OSError:
                return                                   # page closed

    return Handler


class _Server(ThreadingHTTPServer):
    """One reader per port. HTTPServer turns SO_REUSEADDR on, and on Windows that lets a second process bind a port
    that is already listening — two readers then share it silently, each with its own hide/show state. Reuse is off
    here and, on Windows, the port is taken exclusively, so a second start fails with "cannot listen"."""

    allow_reuse_address = False
    daemon_threads = True

    def server_bind(self) -> None:
        if sys.platform == "win32":
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def make_server(hub: Hub, port: int = DEFAULT_PORT, page: Optional[bytes] = None) -> ThreadingHTTPServer:
    """page: fixed bytes (tests), or None to read web/overlay.html on each request."""
    return _Server((HOST, port), _handler(hub, page))
