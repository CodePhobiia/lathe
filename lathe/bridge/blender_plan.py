"""Blender bridge: execution plan for the Codex-operated Blender runner.

Builds a deterministic, JSON-serialisable plan describing bakes,
renders and retained ``.blend`` artefacts so the Blender worker can
run headlessly and the result can be inspected with ``lathe
inspect-blend``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..capabilities import probe_blender
from ..inspection.evidence import build_inspection_policy_ir


BRIDGE_BACKEND_ID = "lathe.bridge.blender_execution_v1"

LATHE_TOOL_CONTRACTS = [
    ("lathe.parse", "deterministic", "read_only", "none"),
    ("lathe.normalize", "deterministic", "read_only", "none"),
    ("lathe.check", "deterministic", "read_only", "none"),
    ("lathe.plan", "deterministic", "read_only", "none"),
    ("lathe.build", "seeded", "artifact_write", "artifact_write"),
    ("lathe.audit", "deterministic", "read_only", "none"),
    ("lathe.bench", "seeded", "artifact_write", "artifact_write"),
    ("lathe.test", "deterministic", "read_only", "none"),
    ("lathe.explain", "deterministic", "read_only", "none"),
    ("lathe.patch_source", "deterministic", "source_write", "workspace_write"),
    ("lathe.materialize_variant", "deterministic", "read_only", "none"),
    ("lathe.diff_builds", "deterministic", "read_only", "none"),
    ("lathe.list_backends", "deterministic", "read_only", "none"),
    ("lathe.list_benchmarks", "deterministic", "read_only", "none"),
    ("lathe.inspect_trace", "deterministic", "read_only", "none"),
    ("lathe.inspect_package", "deterministic", "read_only", "none"),
    ("lathe.run_doctor", "deterministic", "read_only", "none"),
]

BLENDER_TOOL_CONTRACTS = [
    ("blender.execute_build_plan", "seeded", "artifact_write", "artifact_write"),
    ("blender.open_artifact", "deterministic", "read_only", "none"),
    ("blender.render_preview", "deterministic", "artifact_write", "artifact_write"),
    ("blender.render_wireframe", "deterministic", "artifact_write", "artifact_write"),
    ("blender.render_normals", "deterministic", "artifact_write", "artifact_write"),
    ("blender.render_depth", "deterministic", "artifact_write", "artifact_write"),
    ("blender.render_uv_overlay", "deterministic", "artifact_write", "artifact_write"),
    ("blender.inspect_mesh_stats", "deterministic", "read_only", "none"),
    ("blender.inspect_topology", "deterministic", "read_only", "none"),
    ("blender.inspect_nonmanifold_regions", "deterministic", "read_only", "none"),
    ("blender.inspect_hard_edges", "deterministic", "read_only", "none"),
    ("blender.inspect_material_slots", "deterministic", "read_only", "none"),
    ("blender.inspect_uv_sets", "deterministic", "read_only", "none"),
    ("blender.inspect_bake_outputs", "deterministic", "read_only", "none"),
    ("blender.inspect_scene_hierarchy", "deterministic", "read_only", "none"),
    ("blender.inspect_geometry_nodes", "deterministic", "read_only", "none"),
    ("blender.export_package", "deterministic", "external_export", "artifact_write"),
    ("blender.snapshot_artifact", "deterministic", "artifact_write", "artifact_write"),
]


def _contract(name: str, determinism_class: str, side_effect_class: str, approval_class: str) -> dict[str, Any]:
    return {
        "name": name,
        "input_schema": "declared",
        "output_schema": "declared",
        "determinism_class": determinism_class,
        "side_effect_class": side_effect_class,
        "approval_class": approval_class,
    }


def lathe_tool_contracts() -> list[dict[str, Any]]:
    """Lathe tool contracts.

    Returns:
        The result.
    """
    return [_contract(*item) for item in LATHE_TOOL_CONTRACTS]


def blender_tool_contracts() -> list[dict[str, Any]]:
    """Blender tool contracts.

    Returns:
        The result.
    """
    return [_contract(*item) for item in BLENDER_TOOL_CONTRACTS]


def build_bridge_plan(asset: dict[str, Any], runtime_config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build bridge plan.

    Args:
        asset: asset argument.
        runtime_config: runtime_config argument.

    Returns:
        The result.
    """
    execution = asset.get("execution", {})
    inspection_policy_ir = build_inspection_policy_ir(asset)
    requested = bool(execution.get("profile") or execution.get("engine"))
    return {
        "schema": "lathe.blender_bridge_plan.v1",
        "backend_id": BRIDGE_BACKEND_ID,
        "requested": requested,
        "source_of_truth": "lathe_source",
        "generated_artifacts_are_authoritative": False,
        "execution_profile": execution.get("profile", ""),
        "engine": execution.get("engine", ""),
        "mode": execution.get("mode", ""),
        "inspection_policy_ir": inspection_policy_ir,
        "bridge_handoff": [
            "lathe_source",
            "normalized_ast",
            "intent_ir",
            "asset_graph_ir",
            "assembly_ir",
            "feature_ir",
            "mesh_surface_package_plans",
            "blender_execution_plan",
            "blender_artifacts_and_evidence",
            "validation_evidence_ir",
            "trace_ir",
        ],
        "recovery_branches": inspection_policy_ir["recovery_branches"],
        "tool_plane": {
            "lathe_mcp": lathe_tool_contracts(),
            "blender_mcp": blender_tool_contracts(),
            "unsafe_arbitrary_blender_python_exposed": False,
        },
        "cache_key_inputs": [
            "source_hash",
            "normalized_hash",
            "execution_profile_hash",
            "backend_identity_and_version",
            "blender_version",
            "library_asset_versions",
            "seed",
        ],
        "runtime_probe": probe_blender(runtime_config),
    }


def build_bridge_doctor(runtime_config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build bridge doctor.

    Args:
        runtime_config: runtime_config argument.

    Returns:
        The result.
    """
    probe = probe_blender(runtime_config)
    return {
        "schema": "lathe.bridge_doctor.v1",
        "bridge_backend": BRIDGE_BACKEND_ID,
        "blender": probe,
        "tool_contracts": {
            "lathe_mcp_count": len(LATHE_TOOL_CONTRACTS),
            "blender_mcp_count": len(BLENDER_TOOL_CONTRACTS),
            "lathe_mcp": lathe_tool_contracts(),
            "blender_mcp": blender_tool_contracts(),
        },
        "safety": {
            "arbitrary_blender_python_default": "blocked",
            "blend_files_are_source_of_truth": False,
        },
    }


def _read_execution_bundle(build_dir: Path) -> dict[str, Any]:
    # JSON ingress — internal controlled payload from our own execution stage bundle emitted by build_asset; safe without schema validation.
    return json.loads((build_dir / "stages" / "execution" / "bundle.json").read_text(encoding="utf-8"))


def inspect_completed_build(build_dir: Path) -> dict[str, Any]:
    """Inspect completed build.

    Args:
        build_dir: build_dir argument.

    Returns:
        The result.
    """
    bundle = _read_execution_bundle(build_dir)
    return {
        "schema": "lathe.inspect.v1",
        "build_dir": str(build_dir),
        "bridge_plan_ir": bundle.get("bridge_plan_ir", {}),
        "inspection_policy_ir": bundle.get("inspection_policy_ir", {}),
        "validation_evidence_ir": bundle.get("validation_evidence_ir", {}),
        "render_eval_ir": bundle.get("render_eval_ir", {}),
        "blend_artifact_ir": bundle.get("blend_artifact_ir", {}),
        "diagnostics": bundle.get("diagnostics", []),
    }


def build_render_fixture_report(build_dir: Path) -> dict[str, Any]:
    """Build render fixture report.

    Args:
        build_dir: build_dir argument.

    Returns:
        The result.
    """
    bundle = _read_execution_bundle(build_dir)
    return {
        "schema": "lathe.render_fixture_report.v1",
        "build_dir": str(build_dir),
        "render_eval_ir": bundle.get("render_eval_ir", {}),
        "validation_evidence_ir": bundle.get("validation_evidence_ir", {}),
    }


def build_bake_audit(build_dir: Path) -> dict[str, Any]:
    """Build bake audit.

    Args:
        build_dir: build_dir argument.

    Returns:
        The result.
    """
    bundle = _read_execution_bundle(build_dir)
    return {
        "schema": "lathe.bake_audit.v1",
        "build_dir": str(build_dir),
        "bake_plan_ir": bundle.get("bake_plan_ir", {}),
        "validation_evidence_ir": bundle.get("validation_evidence_ir", {}),
        "diagnostics": [
            item
            for item in bundle.get("diagnostics", [])
            if item.get("name") in {"bake_runtime_failed", "bake_evidence_missing"}
        ],
    }
