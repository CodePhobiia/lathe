"""Static registry of shape provider descriptors.

Pure selection / lookup — no I/O, no network calls, no mesh work.  Importing
this module is safe at interpreter start and exercises no optional
dependencies (``trimesh``, ``torch``, ``PIL`` are all deferred to the adapter
modules).
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any


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
            "request_timeout_s": 600,
            "health_timeout_s": 5,
            "max_retries": 2,
            "retry_backoff_s": 1.0,
        },
    },
    "lathe.provider.shape.vggt_local_v1": {
        "id": "lathe.provider.shape.vggt_local_v1",
        "version": "1.0.0",
        "learned": True,
        "modes": ["reconstruct"],
        "summary": "Official local VGGT package bridge for multiview geometric reconstruction followed by deterministic meshing.",
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
    from .errors import ShapeProviderError

    provider_id = normalize_provider_id(provider_id)
    if provider_id not in PROVIDERS:
        raise ShapeProviderError(provider_id, f"Unknown shape provider '{provider_id}'", code="unknown_provider")
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
    return merged
