"""Adapter-facing HTTP helper.

Thin wrapper around :func:`lathe.net.safe_urlopen` that maps the generic
:class:`lathe.net.NetGuardError` onto the shape-provider error hierarchy and
preserves the retry/timing-metadata shape previously returned by
``_hunyuan_request``.
"""
from __future__ import annotations

import json
import time
import urllib.error
from typing import Any, Iterable

from ..errors import ShapeProviderExecutionError
from ...net import DEFAULT_MAX_BYTES, NetGuardError, SafeResponse, safe_urlopen


def hunyuan_transient_status(status: int) -> bool:
    return status in {408, 425, 429, 500, 502, 503, 504}


def hunyuan_safe_text(payload: bytes, *, limit: int = 400) -> str:
    return payload.decode("utf-8", errors="replace")[:limit]


def hunyuan_post_json(
    provider_id: str,
    *,
    url: str,
    payload: dict[str, Any],
    timeout_s: int,
    max_retries: int,
    retry_backoff_s: float,
    expect_content_type: Iterable[str] | str | None,
    max_bytes: int = DEFAULT_MAX_BYTES,
    allowlist: Iterable[str] | None = None,
) -> tuple[bytes, dict[str, Any]]:
    """POST JSON and return ``(body, metadata)`` on success.

    ``expect_content_type`` is checked BEFORE the full body is read (Plan 10
    M1).  Mismatches raise
    :class:`ShapeProviderExecutionError("unexpected_media_type", ...)` with a
    body prefix for diagnostics — they do not get retried.

    HTTP 4xx (non-transient) and SSRF policy violations abort immediately;
    transient 5xx + network errors retry with exponential backoff up to
    ``max_retries`` times.
    """
    encoded = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    attempts: list[dict[str, Any]] = []

    for attempt_index in range(max_retries + 1):
        start = time.perf_counter()
        try:
            response: SafeResponse = safe_urlopen(
                url,
                data=encoded,
                method="POST",
                headers=headers,
                timeout_s=timeout_s,
                max_bytes=max_bytes,
                expect_content_type=expect_content_type,
                allowlist=allowlist,
                allow_loopback_http=True,
            )
        except NetGuardError as exc:
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            attempt_meta: dict[str, Any] = {
                "attempt": attempt_index + 1,
                "elapsed_ms": elapsed_ms,
                "guard_code": exc.code,
                "error": str(exc),
            }
            if exc.code == "unexpected_media_type":
                details = exc.details or {}
                attempt_meta["status"] = details.get("status")
                attempt_meta["content_type"] = details.get("content_type")
                attempt_meta["body"] = details.get("body_prefix", "")
                attempts.append(attempt_meta)
                raise ShapeProviderExecutionError(
                    provider_id,
                    str(exc),
                    code="unexpected_media_type",
                    details={
                        "status": details.get("status"),
                        "content_type": details.get("content_type"),
                        "body_prefix": details.get("body_prefix", ""),
                        "attempts": attempts,
                    },
                ) from exc
            attempts.append(attempt_meta)
            raise ShapeProviderExecutionError(
                provider_id,
                f"Hunyuan generate request rejected by net guard: {exc}",
                code=exc.code,
                details={"attempts": attempts, **(exc.details or {})},
            ) from exc
        except urllib.error.HTTPError as exc:
            body = exc.read()
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            attempt_meta = {
                "attempt": attempt_index + 1,
                "status": exc.code,
                "elapsed_ms": elapsed_ms,
                "body": hunyuan_safe_text(body),
            }
            attempts.append(attempt_meta)
            if hunyuan_transient_status(exc.code) and attempt_index < max_retries:
                time.sleep(retry_backoff_s * (2**attempt_index))
                continue
            error_code = "auth_failed" if exc.code in {401, 403} else "http_error"
            raise ShapeProviderExecutionError(
                provider_id,
                f"Hunyuan generate request failed: HTTP {exc.code}",
                code=error_code,
                details={"status": exc.code, "body": attempt_meta["body"], "attempts": attempts},
            ) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            attempts.append({"attempt": attempt_index + 1, "elapsed_ms": elapsed_ms, "error": str(exc)})
            if attempt_index < max_retries:
                time.sleep(retry_backoff_s * (2**attempt_index))
                continue
            raise ShapeProviderExecutionError(
                provider_id,
                f"Hunyuan generate request failed: {exc}",
                code="request_failed",
                details={"attempts": attempts},
            ) from exc

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        attempt_meta = {
            "attempt": attempt_index + 1,
            "status": response.status,
            "content_type": response.content_type,
            "elapsed_ms": elapsed_ms,
        }
        attempts.append(attempt_meta)
        if not response.body:
            raise ShapeProviderExecutionError(
                provider_id,
                "Provider response body was empty",
                code="empty_response",
                details={"attempts": attempts},
            )
        return response.body, {"attempts": attempts, "final_attempt": attempt_meta}

    raise ShapeProviderExecutionError(provider_id, "Hunyuan request exhausted retries", code="request_failed")
