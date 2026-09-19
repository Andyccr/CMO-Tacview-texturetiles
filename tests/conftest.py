from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict, Optional
from urllib.parse import unquote, urlparse

import pytest

from tests.helpers import make_webp


class TileHTTPServer(ThreadingHTTPServer):
    """In-process texture host used by tests."""

    allow_reuse_address = True

    def __init__(self, files: Dict[str, bytes], html_for: Optional[set] = None):
        super().__init__(("127.0.0.1", 0), _make_handler())
        self.files = files
        self.html_for = html_for or set()
        self.requests = []  # (method, path, range)
        self._lock = threading.Lock()

    @property
    def origin(self) -> str:
        host, port = self.server_address[:2]
        return f"http://{host}:{port}"

    @property
    def base_url(self) -> str:
        return f"{self.origin}/Tacview_Textures/"

    def record(self, method: str, path: str, rng: Optional[str]) -> None:
        with self._lock:
            self.requests.append((method, path, rng))


def _make_handler():
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, format: str, *args) -> None:  # noqa: A003
            return

        def do_HEAD(self) -> None:
            self._respond(body=False)

        def do_GET(self) -> None:
            self._respond(body=True)

        def _respond(self, body: bool) -> None:
            parsed = urlparse(self.path)
            name = unquote(parsed.path.rsplit("/", 1)[-1])
            rng = self.headers.get("Range")
            self.server.record(self.command, parsed.path, rng)

            if name in self.server.html_for:
                payload = b"<html>nope</html>"
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.send_header("Content-Length", str(len(payload)))
                self.send_header("Connection", "close")
                self.end_headers()
                if body:
                    self.wfile.write(payload)
                return

            data = self.server.files.get(name)
            if data is None:
                self.send_response(404)
                self.send_header("Content-Length", "0")
                self.send_header("Connection", "close")
                self.end_headers()
                return

            start = 0
            status = 200
            chunk = data
            if rng and rng.lower().startswith("bytes="):
                spec = rng.split("=", 1)[1]
                start_s, _, _end_s = spec.partition("-")
                try:
                    start = int(start_s or "0")
                except ValueError:
                    start = 0
                chunk = data[start:]
                status = 206
                self.send_response(status)
                self.send_header(
                    "Content-Range", f"bytes {start}-{len(data) - 1}/{len(data)}"
                )
            else:
                self.send_response(status)
            self.send_header("Content-Type", "image/webp")
            self.send_header("Content-Length", str(len(chunk)))
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Connection", "close")
            self.end_headers()
            if body:
                self.wfile.write(chunk)

    return Handler


@pytest.fixture
def tile_server():
    files = {
        "N25E121.webp": make_webp(1024, b"A"),
        "N25E122.webp": make_webp(2048, b"B"),
        "S51W060.webp": make_webp(768, b"C"),
    }
    server = TileHTTPServer(files)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        thread.join(timeout=5)
