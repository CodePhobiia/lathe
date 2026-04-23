"""Shape stage step body.

Extracted from ``lathe/executor.py`` during Stage 2.IV. The shape stage is
the only probabilistic stage in the pipeline; it emits the stable contract
``lathe.shape.intent_mesh_handoff_v1`` whose bytes come from the provider
result assembled below. Do not change the contract payload without an
explicit migration task.
"""

from __future__ import annotations

import math
from typing import Any

from ...assembly_ir import AssemblyIR
from ...feature_ir import FeatureIR
from ...fit_ir import FitIR
from ...kit_ir import KitIR
from ...reference_ir import ReferenceIR
from ...repair_policy import RepairPolicyIR
from ...shape_backend import (
    collect_shape_conditioning as _shape_collect_conditioning,
    run_shape_backend as _shape_run_backend,
)
from ...surface_ir import SurfaceIR
from ...transfer_ir import TransferIR
from ..common import dump_json, relpath, resolve_seed
from ..errors import BuildError
from ..io import export_glb
from ..geometry import mesh_stats
from ..mesh import RuntimeMesh
from ..rendering import render_mesh_preview


def run(executor: Any) -> dict[str, Any]:
    shape_cfg = executor.asset["build"]["shape"]
    backend = executor.selected_backends["shape"]
    seed = resolve_seed(shape_cfg.get("seed", "auto"), executor.asset_name)
    candidates_count = int(shape_cfg.get("candidates", 1) or 1)
    assembly_ir = AssemblyIR.from_asset(executor.asset)
    feature_ir = FeatureIR.from_asset(executor.asset)
    surface_ir = SurfaceIR.from_asset(executor.asset)
    repair_policy_ir = RepairPolicyIR.from_asset(executor.asset)
    reference_ir = ReferenceIR.from_asset(executor.asset)
    fit_ir = FitIR.from_asset(executor.asset)
    transfer_ir = TransferIR.from_asset(executor.asset)
    kit_ir = KitIR.from_asset(executor.asset)
    conditioning = _shape_collect_conditioning(executor.asset, executor.source_root)
    provider_result = _shape_run_backend(
        backend["id"],
        executor.asset,
        source_root=executor.source_root,
        seed=seed,
        candidates_count=candidates_count,
        conditioning=conditioning,
        work_dir=executor.stage_dirs["shape"],
        runtime_config=executor.runtime_config,
    )
    runtime_candidates = provider_result["runtime_candidates"]
    provider_report = provider_result["provider_report"]
    asset_graph = provider_result.get("asset_graph")
    shape_ir = provider_result.get("shape_ir")
    scaffold_report = provider_result.get("scaffold_report", {})
    conformance_report = provider_result.get("conformance_report", {})
    candidates: list[dict[str, Any]] = []
    selected: dict[str, Any] | None = None
    selected_runtime: RuntimeMesh | None = None
    runtime_candidates_by_id: dict[str, RuntimeMesh] = {}
    consumed_refs = conditioning.get("consumed_refs", [])
    for index, candidate_runtime in enumerate(runtime_candidates):
        runtime_mesh = RuntimeMesh(
            mesh=candidate_runtime["mesh"],
            face_parts=list(candidate_runtime["face_parts"]),
            part_colors=dict(candidate_runtime["part_colors"]),
            units=candidate_runtime.get("units", "cm"),
        )
        meta = candidate_runtime["meta"]
        candidate_id = f"candidate_{index:02d}"
        runtime_candidates_by_id[candidate_id] = runtime_mesh
        mesh_path = executor.stage_dirs["shape"] / f"{candidate_id}.glb"
        export_glb(runtime_mesh.mesh, mesh_path)
        preview_path = executor.stage_dirs["shape"] / f"{candidate_id}.png"
        render_mesh_preview(runtime_mesh, preview_path, mode="material_ids")
        candidate = {
            "candidate_id": candidate_id,
            "mesh_uri": relpath(executor.out_dir, mesh_path),
            "preview_uri": relpath(executor.out_dir, preview_path),
            "units": runtime_mesh.units,
            "frame": {"handedness": "right", "up": "+Y", "forward": "+Z"},
            "part_labels": sorted(meta["parts"]),
            "coarse_material_slots": int(meta.get("coarse_material_slots", 1)),
            "mesh_stats": mesh_stats(runtime_mesh.mesh),
            "score": meta["score"],
            "selection_notes": meta["selection_notes"],
            "conditioning": meta.get("conditioning", {}),
            "provider": meta.get("conditioning", {}).get("provider"),
            "blueprint_id": meta.get("blueprint_id"),
            "primitives_used": meta.get("primitives_used", []),
            "shape_assessment": meta.get("shape_assessment", {}),
            "repairs_applied": meta.get("repairs_applied", []),
            "feature_report": meta.get("feature_report", {}),
            "candidate_params": meta.get("candidate_params", {}),
            "integration_report": meta.get("integration_report", {}),
        }
        candidates.append(candidate)
        if selected is None or candidate["score"] > selected["score"] or (
            math.isclose(candidate["score"], selected["score"]) and candidate_id < selected["candidate_id"]
        ):
            selected = candidate
            selected_runtime = runtime_mesh

    assert selected is not None and selected_runtime is not None
    bundle = {
        "backend_id": backend["id"],
        "backend_version": backend["version"],
        "determinism_class": backend["determinism_class"],
        "seed": seed,
        "selected_candidate_id": selected["candidate_id"],
        "blueprint_id": scaffold_report.get("blueprint_id"),
        "primitives_used": scaffold_report.get("primitives_used", []),
        "conditioning_report": conditioning,
        "provider_report": provider_report,
        "assembly_ir": assembly_ir.to_dict(),
        "feature_ir": feature_ir.to_dict(),
        "surface_ir": surface_ir.to_dict(),
        "repair_policy_ir": repair_policy_ir.to_dict(),
        "reference_ir": reference_ir.to_dict(),
        "fit_ir": fit_ir.to_dict(),
        "transfer_ir": transfer_ir.to_dict(),
        "kit_ir": kit_ir.to_dict(),
        "asset_graph": asset_graph,
        "shape_ir": shape_ir,
        "scaffold_report": scaffold_report,
        "conformance_report": conformance_report,
        "proposal_sources_attempted": conformance_report.get("proposal_sources_attempted", []),
        "proposal_sources_used": conformance_report.get("proposal_sources_used", []),
        "accepted_deltas": conformance_report.get("accepted_deltas", []),
        "rejected_deltas": conformance_report.get("rejected_deltas", []),
        "conformance_failures": conformance_report.get("conformance_failures", []),
        "authoritative_candidate_reason": conformance_report.get("authoritative_candidate_reason", scaffold_report.get("authoritative_candidate_reason")),
        "shape_assessment": scaffold_report.get("shape_assessment", {}),
        "candidates": candidates,
        "provenance": {
            "backend_id": backend["id"],
            "backend_version": backend["version"],
            "seed": seed,
            "consumed_refs": consumed_refs,
            "shape_provider_id": provider_report.get("actual_provider_id"),
            "shape_provider_version": provider_report.get("actual_provider_version"),
            "attempted_shape_provider_id": provider_report.get("selected_provider_id"),
            "attempted_shape_provider_version": provider_report.get("selected_provider_version"),
        },
    }
    executor.runtime["shape"] = {
        "bundle": bundle,
        "selected": selected,
        "runtime_mesh": selected_runtime,
        "runtime_candidates": runtime_candidates_by_id,
        "conditioning": conditioning,
    }
    dump_json(executor.stage_dirs["shape"] / "bundle.json", bundle)
    return bundle


def select_candidate(executor: Any, candidate_id: str, reason: str) -> None:
    bundle = executor.runtime["shape"]["bundle"]
    selected = next((item for item in bundle.get("candidates", []) if item.get("candidate_id") == candidate_id), None)
    runtime_mesh = executor.runtime["shape"].get("runtime_candidates", {}).get(candidate_id)
    if selected is None or runtime_mesh is None:
        raise BuildError(f"Unknown shape candidate '{candidate_id}' for reselection")
    bundle["selected_candidate_id"] = candidate_id
    bundle["authoritative_candidate_reason"] = reason
    executor.runtime["shape"]["selected"] = selected
    executor.runtime["shape"]["runtime_mesh"] = runtime_mesh
    attempts = executor.runtime["shape"].setdefault("reselection_attempts", [])
    attempts.append({"candidate_id": candidate_id, "reason": reason, "score": selected.get("score")})
    dump_json(executor.stage_dirs["shape"] / "bundle.json", bundle)
