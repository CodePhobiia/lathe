"""Provider selection, probing, and fallback orchestration.

The selection layer is deliberately thin: it routes declarative runtime
config to the matching adapter in :mod:`lathe.providers.adapters`, handles
strict-vs-permissive fallback policy, and bookkeeps a structured provider
report for the build bundle.

Tests (see ``tests/test_shape_providers.py``) mock the capability probes via
``lathe.shape_providers._probe_vggt`` / ``._probe_hunyuan_endpoint``.  To
preserve that contract even though the implementations now live here, the
probe function looks up those names on the shim module at call time rather
than binding at import time.
"""

from __future__ import annotations

import sys
import urllib.error
import warnings
from copy import deepcopy
from pathlib import Path
from typing import Any

from ..capabilities import probe_hunyuan_endpoint as _probe_hunyuan_endpoint
from ..capabilities import probe_vggt as _probe_vggt
from ..security import redact_secrets
from .adapters.hunyuan import run_hunyuan_http_provider as _run_hunyuan_http_provider
from .adapters.vggt import run_vggt_local_provider as _run_vggt_local_provider
from .errors import ShapeProviderError, ShapeProviderExecutionError, ShapeProviderUnavailable
from .registry import (
    _short_provider_name,
    get_provider,
    list_shape_providers,
    normalize_provider_id,
    provider_config,
)

_MIN_MULTIVIEW_REFS = 2


def _probe_func_for(provider_id: str):
    """Look up the capability probe via the ``lathe.shape_providers`` shim.

    Tests that ``unittest.mock.patch('lathe.shape_providers._probe_vggt')``
    to inject test-double behavior expect this indirection; binding via module
    attribute lookup (rather than a direct ``from`` import) keeps the patch
    point working after the refactor.
    """
    shim = sys.modules.get("lathe.shape_providers")
    if provider_id == "lathe.provider.shape.hunyuan2_1_http_v1":
        if shim is not None and hasattr(shim, "_probe_hunyuan_endpoint"):
            return shim._probe_hunyuan_endpoint
        return _probe_hunyuan_endpoint
    if provider_id == "lathe.provider.shape.vggt_local_v1":
        if shim is not None and hasattr(shim, "_probe_vggt"):
            return shim._probe_vggt
        return _probe_vggt
    return None


def _non_material_image_refs(conditioning: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in conditioning.get("image_refs", []) if item.get("kind") != "material"]


def resolve_shape_provider(
    asset: dict[str, Any],
    conditioning: dict[str, Any],
    runtime_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve shape provider.

    Args:
        asset: asset argument.
        conditioning: conditioning argument.
        runtime_config: runtime_config argument.

    Returns:
        The result.
    """
    mode = asset.get("build", {}).get("shape", {}).get("mode", "generate")
    shape_cfg = (runtime_config or {}).get("shape", {})
    explicit = normalize_provider_id(shape_cfg.get("provider", "auto"))
    strict = bool(shape_cfg.get("strict", False))
    # BL-37 (Plan 08 Phase 8): `allow_fallback` is the explicit opt-in to the
    # legacy "fall back to reference_conditioned" behavior. Only meaningful for
    # learned providers; kept on selection dict so `maybe_run_shape_provider`
    # can emit the V0.1.x DeprecationWarning / enforce the exit-code contract.
    allow_fallback = bool(shape_cfg.get("allow_fallback", False))
    configured_providers = shape_cfg.get("providers", {})
    auto_learned_requested = bool(configured_providers)

    if explicit != "auto":
        provider = get_provider(explicit)
        return {
            "provider": provider,
            "config": provider_config(runtime_config, explicit),
            "selected_via": "explicit",
            "strict": strict,
            "allow_fallback": allow_fallback,
        }

    if not auto_learned_requested:
        provider = get_provider("reference_conditioned")
        return {
            "provider": provider,
            "config": provider_config(runtime_config, provider["id"]),
            "selected_via": "default_fallback",
            "strict": strict,
            "allow_fallback": allow_fallback,
        }

    image_refs = _non_material_image_refs(conditioning)
    if mode == "reconstruct" and len(image_refs) >= _MIN_MULTIVIEW_REFS:
        provider = get_provider("vggt_local")
        return {
            "provider": provider,
            "config": provider_config(runtime_config, provider["id"]),
            "selected_via": "auto_multiview",
            "strict": strict,
            "allow_fallback": allow_fallback,
        }
    if mode in {"generate", "reconstruct"} and image_refs:
        provider = get_provider("hunyuan2_1_http")
        return {
            "provider": provider,
            "config": provider_config(runtime_config, provider["id"]),
            "selected_via": "auto_image",
            "strict": strict,
            "allow_fallback": allow_fallback,
        }
    provider = get_provider("reference_conditioned")
    return {
        "provider": provider,
        "config": provider_config(runtime_config, provider["id"]),
        "selected_via": "auto_fallback",
        "strict": strict,
        "allow_fallback": allow_fallback,
    }


def probe_shape_provider(provider_id: str, runtime_config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Probe shape provider.

    Args:
        provider_id: provider_id argument.
        runtime_config: runtime_config argument.

    Returns:
        The result.
    """
    provider = get_provider(provider_id)
    config = provider_config(runtime_config, provider["id"])
    try:
        if provider["id"] == "lathe.provider.shape.hunyuan2_1_http_v1":
            probe_fn = _probe_func_for(provider["id"])
            probe = probe_fn(
                {
                    "shape": {
                        "providers": {
                            "hunyuan2_1_http": config,
                        }
                    }
                }
            )
            if not probe.get("available", False):
                raise ShapeProviderUnavailable(
                    provider["id"],
                    probe.get("message", "Hunyuan health probe failed"),
                    code=probe.get("code", "probe_failed"),
                    details=probe,
                )
            return {"available": True, "provider_id": provider["id"], "details": probe}
        if provider["id"] == "lathe.provider.shape.vggt_local_v1":
            probe_fn = _probe_func_for(provider["id"])
            probe = probe_fn(
                {
                    "shape": {
                        "providers": {
                            "vggt_local": config,
                        }
                    }
                }
            )
            if not probe.get("available", False):
                raise ShapeProviderUnavailable(
                    provider["id"],
                    "; ".join(probe.get("issues", [])) or "VGGT runtime unavailable",
                    code=probe.get("code", "probe_failed"),
                    details=probe,
                )
            return {"available": True, "provider_id": provider["id"], "details": probe}
        return {"available": True, "provider_id": provider["id"], "details": {}}
    except ShapeProviderError as exc:
        return {
            "available": False,
            "provider_id": provider["id"],
            "code": exc.code,
            "message": str(exc),
            "details": exc.details,
        }
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        return {
            "available": False,
            "provider_id": provider["id"],
            "code": "probe_failed",
            "message": str(exc),
            "details": {},
        }


def probe_all_shape_providers(runtime_config: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Probe all shape providers.

    Args:
        runtime_config: runtime_config argument.

    Returns:
        The result.
    """
    reports = []
    for provider in list_shape_providers():
        reports.append(probe_shape_provider(provider["id"], runtime_config))
    return reports


def _redact_provider_config(provider_id: str, config: dict[str, Any]) -> dict[str, Any]:
    allowed = deepcopy(config)
    if provider_id == "lathe.provider.shape.hunyuan2_1_http_v1":
        return {
            k: allowed.get(k)
            for k in [
                "base_url",
                "remove_background",
                "texture",
                "octree_resolution",
                "num_inference_steps",
                "guidance_scale",
                "face_count",
                "type",
                "timeout_s",
                "request_timeout_s",
                "url_allowlist",
                "max_retries",
                "retry_backoff_s",
            ]
            if k in allowed
        }
    if provider_id == "lathe.provider.shape.vggt_local_v1":
        return {
            k: allowed.get(k)
            for k in [
                "weights",
                "device",
                "dtype",
                "max_views",
                "stride",
                "min_confidence",
                "max_edge_ratio",
                "candidate_variants",
                "use_point_head",
            ]
            if k in allowed
        }
    return redact_secrets(allowed)


def maybe_run_shape_provider(
    asset: dict[str, Any],
    *,
    source_root: Path,
    seed: int,
    candidates_count: int,
    conditioning: dict[str, Any],
    work_dir: Path,
    runtime_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Maybe run shape provider.

    Args:
        asset: asset argument.
        source_root: source_root argument.
        seed: seed argument.
        candidates_count: candidates_count argument.
        conditioning: conditioning argument.
        work_dir: work_dir argument.
        runtime_config: runtime_config argument.

    Returns:
        The result.
    """
    selection = resolve_shape_provider(asset, conditioning, runtime_config)
    provider = selection["provider"]
    provider_id = provider["id"]
    learned = bool(provider.get("learned", False))
    strict = bool(selection.get("strict", False))
    allow_fallback = bool(selection.get("allow_fallback", False))
    fallback_provider = get_provider("reference_conditioned")

    # BL-37 (Plan 08 Phase 8, V0.1.x opt-in rollout): when a learned provider
    # is selected with strict=False and the user has NOT explicitly opted into
    # fallback via ``shape.allow_fallback=true``, emit a DeprecationWarning so
    # users see the upcoming V0.2 default flip one minor version ahead, per
    # Phase 11's deprecation-window policy. The default behavior is unchanged.
    if learned and not strict and not allow_fallback:
        short_name = _short_provider_name(provider_id)
        warnings.warn(
            (
                f"V0.1.x deprecation: shape.strict=False under learned provider "
                f"'{short_name}' will default to True in V0.2. Set "
                f"shape.allow_fallback=true (or pass --allow-fallback) to keep "
                f"legacy fallback behavior explicitly."
            ),
            DeprecationWarning,
            stacklevel=2,
        )

    report = {
        "selected_provider_id": provider_id,
        "selected_provider_version": provider["version"],
        "actual_provider_id": provider_id,
        "actual_provider_version": provider["version"],
        "selected_via": selection["selected_via"],
        "strict": strict,
        "allow_fallback": allow_fallback,
        "learned": learned,
        "status": "selected",
        "probe": probe_shape_provider(provider_id, runtime_config),
        "config": _redact_provider_config(provider_id, selection["config"]),
    }
    if provider_id == "lathe.provider.shape.reference_conditioned_v1":
        report["status"] = "fallback"
        return {"provider_report": report, "runtime_candidates": None}

    if not report["probe"].get("available", False):
        message = (
            f"Selected shape provider '{provider_id}' is unavailable: "
            f"{report['probe'].get('message', 'unknown error')}"
        )
        if strict:
            # BL-37 (Plan 08 Phase 8) exit-code contract: strict + would-fall-back
            # raises ``ShapeProviderExecutionError`` with code
            # ``provider_fallback_blocked`` so CLI callers can gate a non-zero
            # exit. The underlying probe details are preserved under ``details``.
            raise ShapeProviderExecutionError(
                provider_id,
                message,
                code="provider_fallback_blocked",
                details={
                    "reason": "probe_unavailable",
                    "probe": report["probe"],
                    "underlying_code": report["probe"].get("code", "provider_unavailable"),
                },
            )
        report["status"] = "fallback"
        report["fallback_reason"] = message
        report["actual_provider_id"] = fallback_provider["id"]
        report["actual_provider_version"] = fallback_provider["version"]
        return {"provider_report": report, "runtime_candidates": None}

    try:
        if provider_id == "lathe.provider.shape.hunyuan2_1_http_v1":
            provider_result = _run_hunyuan_http_provider(
                asset,
                seed=seed,
                candidates_count=candidates_count,
                conditioning=conditioning,
                work_dir=work_dir,
                config=selection["config"],
            )
        elif provider_id == "lathe.provider.shape.vggt_local_v1":
            provider_result = _run_vggt_local_provider(
                asset,
                candidates_count=candidates_count,
                conditioning=conditioning,
                config=selection["config"],
            )
        else:
            raise ShapeProviderExecutionError(
                provider_id, f"No executor implemented for provider '{provider_id}'", code="not_implemented"
            )
    except ShapeProviderError as exc:
        if strict:
            # BL-37 (Plan 08 Phase 8) exit-code contract: strict + would-fall-back
            # raises ``ShapeProviderExecutionError`` with code
            # ``provider_fallback_blocked``. The underlying error's provider_id,
            # code, and details are preserved under ``details`` so callers can
            # still branch on the root cause.
            raise ShapeProviderExecutionError(
                provider_id,
                str(exc),
                code="provider_fallback_blocked",
                details={
                    "reason": "execution_error",
                    "underlying_provider_id": exc.provider_id,
                    "underlying_code": exc.code,
                    "underlying_details": exc.details,
                },
            ) from exc
        report["status"] = "fallback"
        report["fallback_reason"] = str(exc)
        report["error"] = {"provider_id": exc.provider_id, "code": exc.code, "details": exc.details}
        report["actual_provider_id"] = fallback_provider["id"]
        report["actual_provider_version"] = fallback_provider["version"]
        return {"provider_report": report, "runtime_candidates": None}

    candidates = provider_result["candidates"]
    report["execution"] = provider_result.get("execution", {})
    report["status"] = "success"
    report["candidate_count"] = len(candidates)
    return {"provider_report": report, "runtime_candidates": candidates}
