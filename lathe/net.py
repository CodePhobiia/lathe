"""SSRF-hardened HTTP wrapper for outbound Lathe network calls.

Provides :func:`safe_urlopen`, a narrow replacement for
``urllib.request.urlopen`` that enforces:

- URL scheme allowlist (``http`` only for loopback, otherwise ``https``)
- DNS resolution + rejection of RFC1918 / loopback / link-local / CGNAT /
  metadata (169.254.169.254) / IPv6 ULA / link-local / multicast addresses;
  the eventual socket is pinned to the already-vetted DNS result so the
  transport layer cannot re-resolve the hostname
- Redirect blocking. Callers that need redirects must issue a fresh guarded
  request for the redirected URL.
- TLS defaults (``check_hostname=True``, ``CERT_REQUIRED``, min TLS 1.2)
- Pre-check of ``Content-Type`` against caller expectation BEFORE reading the
  full body (so JSON-error responses masquerading as mesh artifacts are
  rejected with a typed error and the caller gets a body prefix for diagnostics)
- Hard streaming byte cap on the response body.

This module is consumed by
``lathe.providers.adapters.hunyuan._hunyuan_request`` and is the intended
migration target for ``lathe.capabilities.probe_hunyuan_endpoint`` (tracked
under Wave 3 backlog BL-12).

Plan reference: ``plans/07_security.md`` Phase 3.
"""

from __future__ import annotations

import http.client
import io
import ipaddress
import socket
import ssl
import urllib.error
import urllib.parse
from collections.abc import Iterable
from dataclasses import dataclass, field

from .security import InputClass, TrustLevel, boundary_policy, ingress_boundary

DEFAULT_MAX_BYTES: int = 256 * 1024 * 1024  # 256 MiB
_LOOPBACK_HOSTS: frozenset[str] = frozenset({"localhost", "127.0.0.1", "::1"})
_BODY_PREFIX_LIMIT: int = 256
_REDIRECT_STATUSES: frozenset[int] = frozenset({301, 302, 303, 307, 308})
_NO_RESOLVED_ENDPOINTS = "no resolved endpoints available"
_NETWORK_PROVIDER_BOUNDARY = boundary_policy(
    name="provider_network_io",
    input_class=InputClass.NETWORK_PROVIDER,
    trust_level=TrustLevel.UNTRUSTED,
    controls=(
        "scheme_allowlist",
        "host_allowlist",
        "private_ip_rejection",
        "redirect_blocking",
        "tls_verification",
        "content_type_check",
        "response_byte_cap",
    ),
)


@dataclass(frozen=True)
class _ResolvedEndpoint:
    address: str
    family: socket.AddressFamily
    socktype: socket.SocketKind
    proto: int
    sockaddr: tuple


class NetGuardError(RuntimeError):
    """Raised when a URL/host/response violates the SSRF policy.

    ``code`` is a stable short string for callers to branch on; ``details``
    carries structured data suitable for structured logging.
    """

    def __init__(self, code: str, message: str, *, details: dict | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.details = details or {}


@dataclass
class SafeResponse:
    """Return value of :func:`safe_urlopen`.

    ``body`` is the streamed response payload, capped at the caller's
    ``max_bytes``.  ``body_prefix`` is always set when the response was read
    far enough to include a prefix — useful for error diagnostics even on the
    success path.
    """

    status: int
    content_type: str
    body: bytes
    headers: dict[str, str] = field(default_factory=dict)
    body_prefix: str = ""


def _is_loopback_host(host: str) -> bool:
    return host.strip("[]").lower() in _LOOPBACK_HOSTS


def _is_private_address(addr_str: str) -> bool:
    try:
        addr = ipaddress.ip_address(addr_str)
    except ValueError:
        return False
    if (
        addr.is_loopback
        or addr.is_private
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
    ):
        return True
    # CGNAT 100.64.0.0/10 is not flagged as private by ipaddress.
    return isinstance(addr, ipaddress.IPv4Address) and (
        ipaddress.IPv4Address("100.64.0.0") <= addr <= ipaddress.IPv4Address("100.127.255.255")
    )


def _resolve_host_endpoints(host: str, port: int) -> list[_ResolvedEndpoint]:
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError:
        return []
    endpoints: list[_ResolvedEndpoint] = []
    seen: set[tuple[str, int]] = set()
    for family, socktype, proto, _, sockaddr in infos:
        if sockaddr and isinstance(sockaddr[0], str):
            address = sockaddr[0]
            key = (address, int(sockaddr[1]))
            if key in seen:
                continue
            seen.add(key)
            endpoints.append(
                _ResolvedEndpoint(
                    address=address,
                    family=socket.AddressFamily(family),
                    socktype=socket.SocketKind(socktype),
                    proto=int(proto),
                    sockaddr=sockaddr,
                )
            )
    return endpoints


def _connect_to_resolved(endpoints: list[_ResolvedEndpoint], timeout) -> socket.socket:
    last_error: OSError | None = None
    for endpoint in endpoints:
        sock = socket.socket(endpoint.family, endpoint.socktype, endpoint.proto)
        try:
            sock.settimeout(timeout)
            sock.connect(endpoint.sockaddr)
        except OSError as exc:
            last_error = exc
            sock.close()
        else:
            return sock
    if last_error is not None:
        raise last_error
    raise OSError(_NO_RESOLVED_ENDPOINTS)


class _PinnedHTTPConnection(http.client.HTTPConnection):
    """HTTP connection that connects only to pre-vetted DNS endpoints."""

    def __init__(self, host: str, port: int, *, endpoints: list[_ResolvedEndpoint], timeout: float) -> None:
        super().__init__(host, port=port, timeout=timeout)
        self._endpoints = endpoints

    def connect(self) -> None:
        self.sock = _connect_to_resolved(self._endpoints, self.timeout)
        if self._tunnel_host:
            self._tunnel()


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    """HTTPS connection that pins TCP to vetted IPs while preserving TLS SNI."""

    def __init__(
        self,
        host: str,
        port: int,
        *,
        endpoints: list[_ResolvedEndpoint],
        timeout: float,
        context: ssl.SSLContext,
    ) -> None:
        super().__init__(host, port=port, timeout=timeout, context=context)
        self._endpoints = endpoints

    def connect(self) -> None:
        raw_sock = _connect_to_resolved(self._endpoints, self.timeout)
        try:
            if self._tunnel_host:
                self.sock = raw_sock
                self._tunnel()
                raw_sock = self.sock
            self.sock = self._context.wrap_socket(raw_sock, server_hostname=self.host)
        except (OSError, ssl.SSLError, ValueError):
            raw_sock.close()
            raise


def _make_tls_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.check_hostname = True
    ctx.verify_mode = ssl.CERT_REQUIRED
    if hasattr(ssl, "TLSVersion"):
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    return ctx


def _content_type_matches(actual: str, expected: Iterable[str] | str | None) -> bool:
    if expected is None:
        return True
    normalized = actual.split(";", 1)[0].strip().lower()
    expected_list = [expected] if isinstance(expected, str) else list(expected)
    for candidate in expected_list:
        candidate_norm = candidate.split(";", 1)[0].strip().lower()
        if candidate_norm == normalized:
            return True
        if candidate_norm.endswith("/*"):
            prefix = candidate_norm[:-1]
            if normalized.startswith(prefix):
                return True
    return False


def _safe_body_prefix(raw: bytes, *, limit: int = _BODY_PREFIX_LIMIT) -> str:
    return raw[:limit].decode("utf-8", errors="replace")


def _request_target(parsed: urllib.parse.SplitResult) -> str:
    target = parsed.path or "/"
    if parsed.query:
        target = f"{target}?{parsed.query}"
    return target


def _open_pinned_response(
    *,
    parsed: urllib.parse.SplitResult,
    hostname: str,
    port: int,
    endpoints: list[_ResolvedEndpoint],
    data: bytes | None,
    method: str,
    headers: dict[str, str],
    timeout_s: float,
    context: ssl.SSLContext | None,
) -> tuple[http.client.HTTPResponse, http.client.HTTPConnection]:
    connection: http.client.HTTPConnection
    if parsed.scheme.lower() == "https":
        if context is None:
            raise NetGuardError("internal_error", "Missing TLS context for https request")
        connection = _PinnedHTTPSConnection(
            hostname,
            port,
            endpoints=endpoints,
            timeout=timeout_s,
            context=context,
        )
    else:
        connection = _PinnedHTTPConnection(hostname, port, endpoints=endpoints, timeout=timeout_s)
    try:
        connection.request(method, _request_target(parsed), body=data, headers=headers)
        response = connection.getresponse()
    except BaseException:
        # Cover any failure between connection creation and the response
        # handing back to safe_urlopen — otherwise the underlying socket is
        # leaked.
        connection.close()
        raise
    return response, connection


@ingress_boundary(_NETWORK_PROVIDER_BOUNDARY)
def safe_urlopen(
    url: str,
    *,
    data: bytes | None = None,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    timeout_s: float,
    max_bytes: int = DEFAULT_MAX_BYTES,
    expect_content_type: Iterable[str] | str | None = None,
    allowlist: Iterable[str] | None = None,
    allow_loopback_http: bool = True,
) -> SafeResponse:
    """Perform an SSRF-guarded HTTP(S) request.

    ``expect_content_type`` is checked against the response ``Content-Type``
    header BEFORE a full body read.  If it does not match, we read at most
    ``_BODY_PREFIX_LIMIT`` bytes for diagnostics and raise
    ``NetGuardError("unexpected_media_type", ...)``.

    On success, returns a :class:`SafeResponse` with the full body (up to
    ``max_bytes``) and a populated ``body_prefix``.

    Raises :class:`NetGuardError` for SSRF policy violations or for
    non-retryable network errors at the wrapper layer.  HTTP-level errors
    (4xx/5xx) are surfaced via :class:`urllib.error.HTTPError` so callers can
    distinguish transient server-side failures from policy violations.
    """
    try:
        parsed = urllib.parse.urlsplit(url)
    except ValueError as exc:
        raise NetGuardError("invalid_url", f"Could not parse URL: {exc}") from exc

    scheme = (parsed.scheme or "").lower()
    if scheme not in {"http", "https"}:
        raise NetGuardError(
            "scheme_insecure",
            f"Only http/https schemes are permitted, got '{parsed.scheme}'",
        )

    hostname = (parsed.hostname or "").lower()
    if not hostname:
        raise NetGuardError("invalid_url", "URL is missing a hostname")

    host_is_loopback = _is_loopback_host(hostname)
    if scheme == "http" and not (host_is_loopback and allow_loopback_http):
        raise NetGuardError(
            "scheme_insecure",
            "Plain http is only permitted for loopback hosts (localhost, 127.0.0.1, ::1)",
        )

    allow_set = {str(item).strip().lower() for item in allowlist or [] if str(item).strip()}
    if not allow_set:
        raise NetGuardError(
            "host_not_allowlisted",
            "Network egress requires a non-empty host allowlist",
            details={"host": hostname, "allowlist": []},
        )
    if hostname not in allow_set:
        raise NetGuardError(
            "host_not_allowlisted",
            f"Host '{hostname}' is not in the configured allowlist",
            details={"allowlist": sorted(allow_set)},
        )

    try:
        port = parsed.port or (443 if scheme == "https" else 80)
    except ValueError as exc:
        raise NetGuardError("invalid_url", f"Invalid URL port: {exc}") from exc
    resolved = _resolve_host_endpoints(hostname, port)
    if not resolved:
        raise NetGuardError("dns_resolution_failed", f"Could not resolve host '{hostname}'")

    if not host_is_loopback:
        resolved_addresses = [endpoint.address for endpoint in resolved]
        for addr in resolved_addresses:
            if _is_private_address(addr):
                raise NetGuardError(
                    "private_ip_rejected",
                    f"Host '{hostname}' resolves to a private/loopback/link-local/CGNAT address ({addr})",
                    details={"host": hostname, "resolved": resolved_addresses},
                )

    merged_headers = dict(headers or {})
    context = _make_tls_context() if scheme == "https" else None

    resp, connection = _open_pinned_response(
        parsed=parsed,
        hostname=hostname,
        port=port,
        endpoints=resolved,
        data=data,
        method=method,
        headers=merged_headers,
        timeout_s=timeout_s,
        context=context,
    )
    try:
        status = int(resp.status)
        content_type = resp.getheader("Content-Type", "") or ""
        location = resp.getheader("Location")
        if status in _REDIRECT_STATUSES and location:
            raise NetGuardError(
                "redirect_rejected",
                "Redirect responses are not followed by safe_urlopen; issue a fresh guarded request instead",
                details={"status": status, "location": location},
            )
        if status >= 400:
            error_body = resp.read(_BODY_PREFIX_LIMIT)
            raise urllib.error.HTTPError(
                url,
                status,
                resp.reason,
                resp.headers,
                io.BytesIO(error_body),
            )
        if not _content_type_matches(content_type, expect_content_type):
            prefix_bytes = resp.read(_BODY_PREFIX_LIMIT)
            raise NetGuardError(
                "unexpected_media_type",
                f"Expected content-type {expect_content_type!r}, got '{content_type or '<missing>'}'",
                details={
                    "status": status,
                    "content_type": content_type,
                    "body_prefix": _safe_body_prefix(prefix_bytes),
                },
            )

        body = _stream_with_cap(resp, max_bytes=max_bytes)
        return SafeResponse(
            status=status,
            content_type=content_type,
            body=body,
            headers={k: v for k, v in resp.headers.items()},
            body_prefix=_safe_body_prefix(body),
        )
    finally:
        # Close the response then the underlying pinned connection — without
        # the connection close, the socket leaks per call.
        resp.close()
        connection.close()


def _stream_with_cap(resp, *, max_bytes: int) -> bytes:
    """Read response body in chunks, enforcing ``max_bytes`` hard cap."""
    chunk_size = 64 * 1024
    collected = bytearray()
    remaining = max_bytes
    while remaining > 0:
        chunk = resp.read(min(chunk_size, remaining))
        if not chunk:
            break
        collected.extend(chunk)
        remaining -= len(chunk)
    # Peek one more byte to detect oversize.
    overflow = resp.read(1)
    if overflow:
        raise NetGuardError(
            "response_too_large",
            f"Response body exceeded {max_bytes} bytes",
            details={"max_bytes": max_bytes},
        )
    return bytes(collected)
