"""Blender execution result dataclasses.

Structured output (artefacts, logs, timings, exit status) returned
from the Blender driver back to the host process.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..paths import PathGuardError, safe_resolve
from .plan_adapter import _dump_json


def inspect_blend_artifact(build_dir: Path) -> dict[str, Any]:
    """Inspect blend artifact.

    Args:
        build_dir: build_dir argument.

    Returns:
        The result.
    """
    stage_dir = build_dir / "stages" / "execution"
    bundle = json.loads((stage_dir / "bundle.json").read_text(encoding="utf-8"))
    return {
        "asset": bundle.get("requested_profile") or build_dir.name,
        "backend_id": bundle.get("backend_id"),
        "probe": bundle.get("probe", {}),
        "blend_artifact_ir": bundle.get("blend_artifact_ir", {}),
        "render_eval_ir": bundle.get("render_eval_ir", {}),
        "library_asset_ir": bundle.get("library_asset_ir", {}),
        "bridge_plan_ir": bundle.get("bridge_plan_ir", {}),
        "inspection_policy_ir": bundle.get("inspection_policy_ir", {}),
        "validation_evidence_ir": bundle.get("validation_evidence_ir", {}),
    }


def export_blend_artifact(build_dir: Path, destination: Path | None = None) -> dict[str, Any]:
    """Export blend artifact.

    Args:
        build_dir: build_dir argument.
        destination: destination argument.

    Returns:
        The result.
    """
    inspect = inspect_blend_artifact(build_dir)
    artifact_path = inspect.get("blend_artifact_ir", {}).get("artifact_path")
    if not artifact_path:
        raise FileNotFoundError("No retained .blend artifact is recorded for this build")
    try:
        source = safe_resolve(build_dir, str(artifact_path))
    except PathGuardError as exc:
        raise FileNotFoundError("Recorded .blend artifact path is outside the build directory") from exc
    if not source.is_file():
        raise FileNotFoundError(f"Recorded .blend artifact is missing: {artifact_path}")
    if destination is not None:
        if destination.exists():
            raise FileExistsError(f"Destination already exists: {destination}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())
    return {
        "artifact_path": str(source),
        "artifact_hash": inspect.get("blend_artifact_ir", {}).get("artifact_hash"),
        "exported_to": str(destination) if destination is not None else str(source),
    }


def build_library_sync_manifest(program: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    """Build library sync manifest.

    Args:
        program: program argument.
        out_dir: out_dir argument.

    Returns:
        The result.
    """
    bindings = []
    for binding in program.get("library_bindings", []):
        values = binding.get("values", {})
        bindings.append(
            {
                "name": binding.get("name"),
                "target": values.get("target", ""),
                "catalog": values.get("catalog", ""),
                "maps": dict(values.get("maps", {})),
            }
        )
    manifest = {
        "schema": "lathe.library_sync_manifest.v1",
        "binding_count": len(bindings),
        "bindings": bindings,
    }
    _dump_json(out_dir / "library_sync_manifest.json", manifest)
    return manifest
