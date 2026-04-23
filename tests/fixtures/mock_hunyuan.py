"""Mock Hunyuan HTTP server fixture.

Spins up a tiny in-process ``http.server.ThreadingHTTPServer`` on a random
free port that impersonates the Hunyuan GLB-generation endpoint:

- ``POST /generate`` returns the configured GLB bytes (``model/gltf-binary``).
  If ``failures_before_success`` is set, the first N requests return 503.
- ``GET /health`` returns 200.

The ``hunyuan_server`` fixture yields a small handle exposing ``base_url``
and the underlying server state so tests can assert on request counts.

This mirrors the inline ``MockHunyuanServer`` in
``tests/test_shape_providers.py``. Wave 3 will migrate that test to this
fixture; for now both co-exist.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Iterator

import pytest


class _MockHunyuanHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            body = json.dumps({"status": "ok"}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_error(404)

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/generate":
            self.send_error(404)
            return
        server = self.server
        server.request_count += 1  # type: ignore[attr-defined]
        if server.request_count <= server.failures_before_success:  # type: ignore[attr-defined]
            body = json.dumps({"status": "retry"}).encode("utf-8")
            self.send_response(503)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        length = int(self.headers.get("Content-Length", "0"))
        payload_raw = self.rfile.read(length).decode("utf-8") if length else "{}"
        try:
            payload = json.loads(payload_raw)
        except json.JSONDecodeError:
            self.send_error(400, "invalid JSON body")
            return
        required = {"image", "seed", "type"}
        missing = sorted(required - set(payload))
        if missing:
            self.send_error(400, f"Missing keys: {missing}")
            return
        body = server.glb_bytes  # type: ignore[attr-defined]
        self.send_response(200)
        self.send_header("Content-Type", "model/gltf-binary")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        return


class HunyuanServerHandle:
    """Lightweight handle over the running mock server.

    Provides ``base_url`` and read-access to request counters. Not a context
    manager — the ``hunyuan_server`` fixture owns lifecycle.
    """

    def __init__(self, server: ThreadingHTTPServer) -> None:
        self._server = server

    @property
    def base_url(self) -> str:
        host, port = self._server.server_address
        return f"http://{host}:{port}"

    @property
    def request_count(self) -> int:
        return int(self._server.request_count)  # type: ignore[attr-defined]

    def set_glb_bytes(self, glb_bytes: bytes) -> None:
        self._server.glb_bytes = glb_bytes  # type: ignore[attr-defined]

    def set_failures_before_success(self, count: int) -> None:
        self._server.failures_before_success = count  # type: ignore[attr-defined]


_DEFAULT_GLB_STUB = (
    b"glTF"  # magic
    + (2).to_bytes(4, "little")  # version
    + (12).to_bytes(4, "little")  # total length (header-only stub)
)


@pytest.fixture()
def hunyuan_server() -> Iterator[HunyuanServerHandle]:
    """Yield a running mock Hunyuan server bound to a random free port.

    The default response body is a minimal 12-byte header-only GLB stub;
    tests that need a real mesh can overwrite it via
    ``handle.set_glb_bytes(trimesh.export(...))``.
    """
    server = ThreadingHTTPServer(("127.0.0.1", 0), _MockHunyuanHandler)
    server.glb_bytes = _DEFAULT_GLB_STUB  # type: ignore[attr-defined]
    server.failures_before_success = 0  # type: ignore[attr-defined]
    server.request_count = 0  # type: ignore[attr-defined]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield HunyuanServerHandle(server)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
