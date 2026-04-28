"""Static registry of shape provider descriptors.

Pure selection / lookup — no I/O, no network calls, no mesh work.  Importing
this module is safe at interpreter start and exercises no optional
dependencies (``trimesh``, ``torch``, ``PIL`` are all deferred to the adapter
modules).
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any
from urllib.parse import urlsplit

from .errors import ShapeProviderError, ShapeProviderExecutionError

PROVIDER_ALIASES: dict[str, str] = {
    "auto": "auto",
    "reference_conditioned": "lathe.provider.shape.reference_conditioned_v1",
    "hunyuan2_1_http": "lathe.provider.shape.hunyuan2_1_http_v1",
    "vggt_local": "lathe.provider.shape.vggt_local_v1",
}


PROVIDERS: dict[str, dict[str, Any]] = {
    "lathe.provider.shape.reference_conditioned_v1": {
        "id": "lathe.provider.shape.reference_conditioned_v1",
        "version": "1.0.0",
        "learned": False,
        "modes": ["generate", "reconstruct", "adapt", "assemble"],
        "summary": "Built-in heuristic fallback shape provider.",
    },
    "lathe.provider.shape.hunyuan2_1_http_v1": {
        "id": "lathe.provider.shape.hunyuan2_1_http_v1",
        "version": "1.0.0",
        "learned": True,
        "modes": ["generate", "reconstruct"],
        "summary": "Official Hunyuan3D-2.1 FastAPI server bridge for image-conditioned mesh generation.",
        "config": {
            "base_url": "http://localhost:8081",
            "remove_background": True,
            "texture": False,
            "octree_resolution": 256,
            "num_inference_steps": 5,
            "guidance_scale": 5.0,
            "num_chunks": 8000,
            "face_count": 40000,
            "type": "glb",
            "timeout_s": 600,
            "health_timeout_s": 5,
            "url_allowlist": [],
            "max_retries": 2,
            "retry_backoff_s": 1.0,
        },
    },
    "lathe.provider.shape.vggt_local_v1": {
        "id": "lathe.provider.shape.vggt_local_v1",
        "version": "1.0.0",
        "learned": True,
        "modes": ["reconstruct"],
        "summary": (
            "Official local VGGT package bridge for multiview geometric reconstruction "
            "followed by deterministic meshing."
        ),
        "config": {
            "weights": "facebook/VGGT-1B",
            "device": "auto",
            "dtype": "auto",
            "max_views": 8,
            "stride": 8,
            "min_confidence": 0.20,
            "max_edge_ratio": 6.0,
            "candidate_variants": 2,
            "use_point_head": False,
        },
    },
}

_HUNYUAN_PROVIDER_ID = "lathe.provider.shape.hunyuan2_1_http_v1"
_LOOPBACK_HOSTS: frozenset[str] = frozenset({"localhost", "127.0.0.1", "::1"})


def _is_loopback_host(host: str) -> bool:
    return host.strip("[]").lower() in _LOOPBACK_HOSTS


def _require_number(
    provider_id: str,
    config: dict[str, Any],
    key: str,
    *,
    minimum: float,
    maximum: float | None = None,
    integer: bool = False,
) -> None:
    if key not in config:
        return
    value = config[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ShapeProviderExecutionError(
            provider_id,
            f"Hunyuan provider config '{key}' must be {'an integer' if integer else 'a number'}",
            code="invalid_runtime_config",
            details={"key": key, "value": value},
        )
    if integer and not isinstance(value, int):
        raise ShapeProviderExecutionError(
            provider_id,
            f"Hunyuan provider config '{key}' must be an integer",
            code="invalid_runtime_config",
            details={"key": key, "value": value},
        )
    if value < minimum or (maximum is not None and value > maximum):
        raise ShapeProviderExecutionError(
            provider_id,
            f"Hunyuan provider config '{key}' must be between {minimum:g} and {maximum:g}"
            if maximum is not None
            else f"Hunyuan provider config '{key}' must be >= {minimum:g}",
            code="invalid_runtime_config",
            details={"key": key, "value": value, "minimum": minimum, "maximum": maximum},
        )


def _validate_hunyuan_provider_config(provider_id: str, config: dict[str, Any]) -> None:
    base_url = config.get("base_url")
    if not isinstance(base_url, str) or not base_url.strip():
        raise ShapeProviderExecutionError(
            provider_id,
            "Missing base_url for Hunyuan HTTP provider",
            code="missing_base_url",
        )

    try:
        parsed = urlsplit(base_url.rstrip("/"))
    except ValueError as exc:
        raise ShapeProviderExecutionError(
            provider_id,
            f"Invalid base_url for Hunyuan HTTP provider: {exc}",
            code="invalid_url",
        ) from exc

    scheme = parsed.scheme.lower()
    hostname = (parsed.hostname or "").lower()
    if not hostname:
        raise ShapeProviderExecutionError(
            provider_id,
            "Hunyuan provider base_url is missing a hostname",
            code="invalid_url",
        )
    if scheme not in {"http", "https"}:
        raise ShapeProviderExecutionError(
            provider_id,
            f"Only http/https schemes are permitted for Hunyuan base_url, got '{parsed.scheme}'",
            code="scheme_insecure",
        )
    if scheme == "http" and not _is_loopback_host(hostname):
        raise ShapeProviderExecutionError(
            provider_id,
            "Plain http is only permitted for loopback Hunyuan hosts (localhost, 127.0.0.1, ::1)",
            code="scheme_insecure",
        )

    try:
        _ = parsed.port
    except ValueError as exc:
        raise ShapeProviderExecutionError(
            provider_id,
            f"Invalid Hunyuan base_url port: {exc}",
            code="invalid_url",
        ) from exc

    allowlist = config.get("url_allowlist")
    if allowlist is not None:
        if not isinstance(allowlist, list) or any(
            not isinstance(item, str) or not item for item in allowlist
        ):
            raise ShapeProviderExecutionError(
                provider_id,
                "Hunyuan provider config 'url_allowlist' must be a list of non-empty host strings",
                code="invalid_runtime_config",
                details={"key": "url_allowlist", "value": allowlist},
            )
        allow_set = {item.lower() for item in allowlist}
        if allow_set and hostname not in allow_set:
            raise ShapeProviderExecutionError(
                provider_id,
                f"Host '{hostname}' is not in the configured allowlist",
                code="host_not_allowlisted",
                details={"allowlist": sorted(allow_set)},
            )

    _require_number(provider_id, config, "timeout_s", minimum=1, maximum=3600, integer=True)
    _require_number(provider_id, config, "request_timeout_s", minimum=1, maximum=3600, integer=True)
    _require_number(provider_id, config, "health_timeout_s", minimum=1, maximum=3600, integer=True)
    _require_number(provider_id, config, "max_retries", minimum=0, integer=True)
    _require_number(provider_id, config, "retry_backoff_s", minimum=0)


def normalize_provider_id(provider: str | None) -> str:
    """Normalize provider id.

    Args:
        provider: provider argument.

    Returns:
        The result.
    """
    if not provider:
        return "auto"
    return PROVIDER_ALIASES.get(provider, provider)


def list_shape_providers() -> list[dict[str, Any]]:
    """List shape providers.

    Returns:
        The result.
    """
    return [deepcopy(PROVIDERS[key]) for key in sorted(PROVIDERS)]


def get_provider(provider_id: str) -> dict[str, Any]:
    """Get provider.

    Args:
        provider_id: provider_id argument.

    Returns:
        The result.
    """
    provider_id = normalize_provider_id(provider_id)
    if provider_id not in PROVIDERS:
        raise ShapeProviderError(
            provider_id,
            f"Unknown shape provider '{provider_id}'",
            code="unknown_provider",
        )
    return deepcopy(PROVIDERS[provider_id])


def _short_provider_name(provider_id: str) -> str:
    if provider_id.startswith("lathe.provider.shape.") and provider_id.endswith("_v1"):
        return provider_id[len("lathe.provider.shape.") : -len("_v1")]
    return provider_id


def provider_config(runtime_config: dict[str, Any] | None, provider_id: str) -> dict[str, Any]:
    """Provider config.

    Args:
        runtime_config: runtime_config argument.
        provider_id: provider_id argument.

    Returns:
        The result.
    """
    provider = get_provider(provider_id)
    defaults = provider.get("config", {})
    shape_cfg = (runtime_config or {}).get("shape", {})
    providers = shape_cfg.get("providers", {})
    merged = deepcopy(defaults)
    for key in {provider_id, _short_provider_name(provider_id)}:
        if key in providers and isinstance(providers[key], dict):
            merged.update(deepcopy(providers[key]))
    if provider["id"] == _HUNYUAN_PROVIDER_ID:
        _validate_hunyuan_provider_config(provider["id"], merged)
    return merged
