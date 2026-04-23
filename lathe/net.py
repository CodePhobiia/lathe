"""SSRF-hardened HTTP wrapper for outbound Lathe network calls.

Provides :func:`safe_urlopen`, a narrow replacement for
``urllib.request.urlopen`` that enforces:

- URL scheme allowlist (``http`` only for loopback, otherwise ``https``)
- DNS resolution + rejection of RFC1918 / loopback / link-local / CGNAT /
  metadata (169.254.169.254) / IPv6 ULA / link-local / multicast addresses
- TLS defaults (``check_hostname=True``, ``CERT_REQUIRED``, min TLS 1.2)
- Pre-check of ``Content-Type`` against caller expectation BEFORE reading the
  full body (so JSON-error responses masquerading as mesh artifacts are
  rejected with a typed error and the caller gets a body prefix for diagnostics)
- Hard streaming byte cap on the response body.

This module is consumed by
``lathe.providers.adapters.hunyuan._hunyuan_request`` and is the intended
migration target for ``lathe.capabilities.probe_hunyuan_endpoint`` (see the
``TODO(Stage 2.V)`` comment there).

Plan reference: ``plans/07_security.md`` Phase 3.
"""
from __future__ import annotations

import ipaddress
import socket
import ssl
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Iterable


DEFAULT_MAX_BYTES: int = 256 * 1024 * 1024  # 256 MiB
_LOOPBACK_HOSTS: frozenset[str] = frozenset({"localhost", "127.0.0.1", "::1"})
_BODY_PREFIX_LIMIT: int = 256


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
    if addr.is_loopback or addr.is_private or addr.is_link_local or addr.is_multicast or addr.is_reserved or addr.is_unspecified:
        return True
    if isinstance(addr, ipaddress.IPv4Address):
        # CGNAT 100.64.0.0/10 is not flagged as private by ipaddress.
        if ipaddress.IPv4Address("100.64.0.0") <= addr <= ipaddress.IPv4Address("100.127.255.255"):
            return True
    return False


def _resolve_host_addresses(host: str) -> list[str]:
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return []
    addresses: list[str] = []
    for info in infos:
        sockaddr = info[4]
        if sockaddr and isinstance(sockaddr[0], str):
            addresses.append(sockaddr[0])
    return addresses


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
    if isinstance(expected, str):
        expected_list = [expected]
    else:
        expected_list = list(expected)
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
        raise NetGuardError("scheme_insecure", f"Only http/https schemes are permitted, got '{parsed.scheme}'")

    hostname = (parsed.hostname or "").lower()
    if not hostname:
        raise NetGuardError("invalid_url", "URL is missing a hostname")

    host_is_loopback = _is_loopback_host(hostname)
    if scheme == "http":
        if not (host_is_loopback and allow_loopback_http):
            raise NetGuardError(
                "scheme_insecure",
                "Plain http is only permitted for loopback hosts (localhost, 127.0.0.1, ::1)",
            )

    if allowlist is not None:
        allow_set = {str(item).lower() for item in allowlist}
        if allow_set and hostname not in allow_set:
            raise NetGuardError(
                "host_not_allowlisted",
                f"Host '{hostname}' is not in the configured allowlist",
                details={"allowlist": sorted(allow_set)},
            )

    if not host_is_loopback:
        resolved = _resolve_host_addresses(hostname)
        if not resolved:
            raise NetGuardError("dns_resolution_failed", f"Could not resolve host '{hostname}'")
        for addr in resolved:
            if _is_private_address(addr):
                raise NetGuardError(
                    "private_ip_rejected",
                    f"Host '{hostname}' resolves to a private/loopback/link-local/CGNAT address ({addr})",
                    details={"host": hostname, "resolved": resolved},
                )

    merged_headers = dict(headers or {})
    request = urllib.request.Request(url, data=data, method=method, headers=merged_headers)
    context = _make_tls_context() if scheme == "https" else None

    resp = urllib.request.urlopen(request, timeout=timeout_s, context=context)
    try:
        status = getattr(resp, "status", 200)
        content_type = resp.headers.get("Content-Type", "") or ""
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
        resp.close()


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


