"""Unit tests for SSRF-hardened network requests."""

from __future__ import annotations

import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from lathe.net import NetGuardError, safe_urlopen

_RERESOLVE_ERROR = "safe_urlopen re-resolved the host after vetting"


class _NetTestHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/json":
            body = b'{"ok": true}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if self.path == "/redirect-private":
            self.send_response(302)
            self.send_header("Location", "http://169.254.169.254/latest/meta-data")
            self.end_headers()
            return

        self.send_response(404)
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        return


@pytest.fixture()
def http_server() -> tuple[ThreadingHTTPServer, str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _NetTestHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        yield server, f"http://{host}:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_safe_urlopen_blocks_private_redirect(http_server: tuple[ThreadingHTTPServer, str]) -> None:
    _, base_url = http_server

    with pytest.raises(NetGuardError) as exc:
        safe_urlopen(
            f"{base_url}/redirect-private",
            timeout_s=2,
            expect_content_type="application/json",
            allowlist=["127.0.0.1"],
        )

    assert exc.value.code == "redirect_rejected"
    assert exc.value.details["location"] == "http://169.254.169.254/latest/meta-data"


def test_safe_urlopen_uses_only_vetted_dns_result(
    http_server: tuple[ThreadingHTTPServer, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server, _ = http_server
    _, port = server.server_address
    calls: list[tuple[str, int]] = []

    def one_shot_getaddrinfo(host: str, port_arg: int, *args: object, **kwargs: object) -> list[tuple]:
        calls.append((host, port_arg))
        if len(calls) > 1:
            raise AssertionError(_RERESOLVE_ERROR)
        return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("127.0.0.1", port_arg))]

    monkeypatch.setattr(socket, "getaddrinfo", one_shot_getaddrinfo)

    response = safe_urlopen(
        f"http://localhost:{port}/json",
        timeout_s=2,
        expect_content_type="application/json",
        allowlist=["localhost"],
    )

    assert response.status == 200
    assert response.body == b'{"ok": true}'
    assert calls == [("localhost", port)]


def test_safe_urlopen_requires_explicit_allowlist(http_server: tuple[ThreadingHTTPServer, str]) -> None:
    _, base_url = http_server

    with pytest.raises(NetGuardError) as exc:
        safe_urlopen(f"{base_url}/json", timeout_s=2, expect_content_type="application/json")

    assert exc.value.code == "host_not_allowlisted"
    assert exc.value.details["allowlist"] == []


def test_safe_urlopen_rejects_non_http_schemes() -> None:
    with pytest.raises(NetGuardError) as exc:
        safe_urlopen(
            "file:///etc/passwd",
            timeout_s=2,
            expect_content_type="application/json",
            allowlist=["localhost"],
        )

    assert exc.value.code == "scheme_insecure"


def test_safe_urlopen_rejects_non_loopback_http_even_when_allowlisted() -> None:
    with pytest.raises(NetGuardError) as exc:
        safe_urlopen(
            "http://example.test/json",
            timeout_s=2,
            expect_content_type="application/json",
            allowlist=["example.test"],
        )

    assert exc.value.code == "scheme_insecure"


def test_safe_urlopen_rejects_private_dns_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    def private_getaddrinfo(host: str, port_arg: int, *args: object, **kwargs: object) -> list[tuple]:
        return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("169.254.169.254", port_arg))]

    monkeypatch.setattr(socket, "getaddrinfo", private_getaddrinfo)

    with pytest.raises(NetGuardError) as exc:
        safe_urlopen(
            "https://example.test/json",
            timeout_s=2,
            expect_content_type="application/json",
            allowlist=["example.test"],
        )

    assert exc.value.code == "private_ip_rejected"
