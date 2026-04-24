"""Cross-stage consistency checks.

Enforces invariants that span multiple pipeline stages, such as the
stable shape bundle contract, topology/UV compatibility and the
surface control pack schema.
"""

from __future__ import annotations

from typing import Any

from ..backends import (
    BACKEND_SELECTION_STAGES,
    BACKENDS,
    BackendResolutionError,
    evaluate_backend,
    evaluate_stack,
    list_stacks,
    select_stack,
)
from .utils import BACKEND_PATHS, diag


def check_backend_resolution(checker: Any, asset: dict[str, Any]) -> None:
    """Check backend resolution.

    Args:
        checker: checker argument.
        asset: asset argument.
    """
    asset_name = asset["name"]

    for stage in BACKEND_SELECTION_STAGES:
        config = asset.get("package", {}) if stage == "package" else asset.get("build", {}).get(stage, {})
        backend_id = config.get("backend", "auto")
        if backend_id == "auto":
            continue
        if backend_id not in BACKENDS:
            checker.diagnostics.append(
                diag(
                    "L4601",
                    "unknown_backend",
                    "error",
                    "resolve",
                    f"Unknown backend '{backend_id}'",
                    asset=asset_name,
                    stage=stage,
                    path=BACKEND_PATHS[stage],
                )
            )
            continue
        ok, reasons = evaluate_backend(backend_id, asset, stage)
        if not ok:
            for reason in reasons:
                checker.diagnostics.append(_backend_diag(asset_name, stage, backend_id, reason))

    try:
        select_stack(asset)
    except BackendResolutionError:
        stack_reasons: dict[str, list[str]] = {}
        for stack in list_stacks():
            ok, reasons = evaluate_stack(stack["id"], asset)
            if not ok:
                stack_reasons[stack["id"]] = reasons
        checker.diagnostics.append(
            diag(
                "L4604",
                "no_backend_stack_match",
                "error",
                "resolve",
                "No builtin backend stack can satisfy the current asset configuration",
                asset=asset_name,
                details={"candidate_stacks": stack_reasons},
            )
        )


def _backend_diag(asset_name: str, stage: str, backend_id: str, reason: str) -> dict[str, Any]:
    lowered = reason.lower()
    if stage == "uv" and ("tile_mode" in lowered or "unwrap" in lowered or "uv.sets" in lowered):
        code, name = "L4605", "uv_backend_contract_mismatch"
    elif stage == "package" and "package.formats" in lowered:
        code, name = "L4606", "package_backend_format_unsupported"
    elif stage == "shape" and "shape mode" in lowered:
        code, name = "L4607", "shape_backend_mode_unsupported"
    else:
        code, name = "L4602", "backend_contract_mismatch"
    return diag(
        code,
        name,
        "error",
        "resolve",
        f"Backend '{backend_id}' cannot satisfy stage '{stage}': {reason}",
        asset=asset_name,
        stage=stage,
        path=BACKEND_PATHS[stage],
    )
