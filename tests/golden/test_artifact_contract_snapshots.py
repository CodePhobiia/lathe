"""Golden contract snapshot for release-visible build artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from lathe.executor import build_asset
from lathe.parser import parse_file

pytestmark = pytest.mark.golden

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE = REPO_ROOT / "examples" / "courier_drone.lth"
ASSET = "courier_drone"

EXPECTED_ARTIFACT_CONTRACT_SNAPSHOT: dict[str, Any] = {
    "build_report": {
        "asset": "courier_drone",
        "certified": True,
        "kind": "mechanical_assembly",
        "output_formats": [
            "usd",
            "glb",
            "lod_glb",
            "lod_glb",
            "lod_glb",
            "lod_glb",
            "collision_hull",
            "collision_parts",
        ],
        "selected_backend_ids": {
            "package": "lathe.package.openusd_gltf_v1",
            "shape": "lathe.shape.intent_mesh_handoff_v1",
            "topology": "lathe.topology.blender_hard_surface_v1",
            "uv": "lathe.uv.xatlas_v1",
        },
    },
    "diagnostics": [
        ("L6201", "warning", "validate"),
        ("L6410", "warning", "validate"),
        ("L6410", "warning", "validate"),
        ("L6410", "warning", "validate"),
    ],
    "engine_manifests": {
        "godot": {
            "assetName": "courier_drone",
            "engine": "godot",
            "lod_count": 4,
            "schemaVersion": 1,
            "socket_count": 2,
        },
        "unity": {
            "assetName": True,
            "engine": True,
            "lod_lines": 4,
            "schemaVersion": True,
        },
        "unreal": {
            "assetName": "courier_drone",
            "component_count": 10,
            "engine": "unreal",
            "schemaVersion": 1,
        },
    },
    "package_manifest": {
        "asset_id": "courier_drone",
        "formats": ["usd", "glb"],
        "has_trace": True,
        "kind": "mechanical_assembly",
        "output_formats": [
            "usd",
            "glb",
            "lod_glb",
            "lod_glb",
            "lod_glb",
            "lod_glb",
            "collision_hull",
            "collision_parts",
        ],
        "preview_names": [
            "collision.png",
            "lod_sheet.png",
            "material_ids.png",
            "turntable.png",
            "uv_layout.png",
            "wireframe.png",
        ],
    },
    "trace_manifest": {
        "approval_state": "pending_required_approval",
        "asset_id": "courier_drone",
        "backend_version_keys": ["package", "shape", "topology", "uv"],
        "determinism_by_stage": {
            "package": "deterministic",
            "shape": "seeded",
            "topology": "deterministic",
            "uv": "deterministic",
        },
        "diagnostics": [
            ("L6201", "warning", "validate"),
            ("L6410", "warning", "validate"),
            ("L6410", "warning", "validate"),
            ("L6410", "warning", "validate"),
        ],
        "stage_execution_keys": {
            "execution": [
                "backend_id",
                "bake_plan_ir",
                "blend_artifact_ir",
                "blender_execution_ir",
                "bridge_plan_ir",
                "diagnostics",
                "execution_ir",
                "inspection_policy_ir",
                "library_asset_ir",
                "render_eval_ir",
                "requested",
                "requested_engine",
                "requested_profile",
                "schema",
                "status",
                "validation_evidence_ir",
            ],
            "flow_quality": ["metrics", "mode", "thresholds"],
            "package": ["adapter"],
            "shape": [
                "accepted_deltas",
                "authoritative_candidate_reason",
                "blueprint_id",
                "conformance_failures",
                "fit_ir",
                "kit_ir",
                "primitives_used",
                "proposal_sources_attempted",
                "proposal_sources_used",
                "provider_report",
                "reference_ir",
                "rejected_deltas",
                "shape_assessment",
                "transfer_ir",
            ],
            "surface": [
                "atlas_assembly_ir",
                "codex_imagegen_outputs",
                "codex_imagegen_requests",
                "surface_backend_report",
                "surface_control_pack",
                "surface_repair_ir",
                "surface_validation_ir",
            ],
            "topology": [
                "actual_adapter",
                "available",
                "backend_id",
                "error",
                "execution",
                "fallback_available",
                "fallback_reason",
                "probe",
                "real_adapter_available",
                "requested_adapter",
                "selected_adapter",
                "status",
                "strict",
            ],
            "uv": [
                "actual_adapter",
                "available",
                "backend_id",
                "execution",
                "fallback_available",
                "probe",
                "real_adapter_available",
                "requested_adapter",
                "selected_adapter",
                "status",
                "strict",
            ],
        },
        "stage_output_keys": [
            "execution",
            "interfaces",
            "optimize",
            "package",
            "physics",
            "rig",
            "shape",
            "surface",
            "topology",
            "uv",
            "validate",
        ],
    },
}


@pytest.fixture(scope="module")
def courier_build(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out_dir = tmp_path_factory.mktemp("artifact_contract") / ASSET
    build_asset(parse_file(SOURCE), ASSET, out_dir)
    return out_dir


def _diagnostic_snapshot(
    diagnostics: list[dict[str, Any]],
) -> list[tuple[str | None, str | None, str | None]]:
    return [(diag.get("code"), diag.get("severity"), diag.get("stage")) for diag in diagnostics]


def _artifact_contract_snapshot(out_dir: Path) -> dict[str, Any]:
    build_report = json.loads((out_dir / "build_report.json").read_text(encoding="utf-8"))
    package_manifest = json.loads(
        (out_dir / "stages/package/package_manifest.json").read_text(encoding="utf-8")
    )
    trace_manifest = json.loads((out_dir / "stages/package/trace_manifest.json").read_text(encoding="utf-8"))
    validate_report = json.loads((out_dir / "stages/validate/report.json").read_text(encoding="utf-8"))
    godot = json.loads((out_dir / f"{ASSET}.lathe_for_godot.json").read_text(encoding="utf-8"))
    unreal = json.loads((out_dir / f"{ASSET}.lathe_for_unreal.json").read_text(encoding="utf-8"))
    unity = (out_dir / f"{ASSET}.lathe_for_unity.yaml").read_text(encoding="utf-8")

    return {
        "build_report": {
            "asset": build_report["asset"],
            "certified": build_report["certified"],
            "kind": build_report["kind"],
            "output_formats": [item["format"] for item in build_report["outputs"]],
            "selected_backend_ids": {
                stage: data["id"] for stage, data in sorted(build_report["selected_backends"].items())
            },
        },
        "diagnostics": _diagnostic_snapshot(validate_report["diagnostics"]),
        "engine_manifests": {
            "godot": {
                "assetName": godot["assetName"],
                "engine": godot["engine"],
                "lod_count": len(godot["lodGroup"]),
                "schemaVersion": godot["schemaVersion"],
                "socket_count": len(godot["sockets"]),
            },
            "unity": {
                "assetName": "assetName: courier_drone" in unity,
                "engine": "engine: unity" in unity,
                "lod_lines": unity.count("level:"),
                "schemaVersion": "schemaVersion: 1" in unity,
            },
            "unreal": {
                "assetName": unreal["assetName"],
                "component_count": len(unreal["actor"]["components"]),
                "engine": unreal["engine"],
                "schemaVersion": unreal["schemaVersion"],
            },
        },
        "package_manifest": {
            "asset_id": package_manifest["asset_id"],
            "formats": package_manifest["formats"],
            "has_trace": bool(package_manifest.get("trace_path")),
            "kind": package_manifest["kind"],
            "output_formats": [item["format"] for item in package_manifest["outputs"]],
            "preview_names": sorted(Path(preview).name for preview in package_manifest["previews"]),
        },
        "trace_manifest": {
            "approval_state": trace_manifest["approval_state"],
            "asset_id": trace_manifest["asset_id"],
            "backend_version_keys": sorted(trace_manifest["backend_versions"]),
            "determinism_by_stage": trace_manifest["determinism_by_stage"],
            "diagnostics": _diagnostic_snapshot(trace_manifest["diagnostics"]),
            "stage_execution_keys": {
                stage: sorted(value) if isinstance(value, dict) else []
                for stage, value in sorted(trace_manifest["stage_execution"].items())
            },
            "stage_output_keys": sorted(trace_manifest["stage_outputs"]),
        },
    }


def test_release_artifact_contract_snapshot(courier_build: Path) -> None:
    assert _artifact_contract_snapshot(courier_build) == EXPECTED_ARTIFACT_CONTRACT_SNAPSHOT
