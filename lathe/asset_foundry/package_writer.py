"""Foundry F9 — .lthpkg package writer.

Per docs/asset-quality/lathe-frontier-asset-foundry-masterplan.md §6.6
+ §18.F9 + docs/product/three-lth-lathe-web-studio-v1-product-path.md
§1, the .lthpkg layout is:

```text
asset_name.lthpkg/
  asset.lth                  (optional — when source is available)
  manifest.json              (the .lthpkg manifest)
  mesh.glb                   (or pointer when unbuilt)
  semantic-index.json        (parts, sockets, material slots)
  diagnostics.json           (capability matrix slice + generator diagnostics)
  materials.json             (material slot manifest)
  operations.json            (GeometryOpGraph plan + ShapeProgram if available)
  repair-history.json        (optional before/after repair evidence)
  evidence.json              (runtime manifest + certificate)
  runtime.json               (runtime cook output)
  previews/                  (turntable.png, wireframe.png, etc. if available)
```

The writer is the bridge between the Foundry (server-side execution)
and ``@lathe/three`` (client-side inspection). Per masterplan §3
(no-fake-quality), every artifact path resolves to either an
existing file on disk OR a structured ``"status": "unbuilt"`` record
with a reason.

The writer does NOT generate mesh geometry. It collects the
``FoundryAsset`` spec + ``RuntimeArtifactManifest`` +
``AssetQualityCertificate`` and writes the sidecar JSON files.
External callers wire actual mesh/preview artifacts by passing their
filesystem paths via ``ExternalArtifacts``.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .capability_matrix import (
    FoundryCapabilityMatrix,
    build_capability_matrix,
    capability_matrix_to_dict,
)
from .certificates import (
    AssetQualityCertificate,
    certificate_to_dict,
)
from .generators._base import FoundryAsset
from .op_graph import (
    GeometryOpGraph,
    OpGraphPlan,
    plan_op_graph,
)
from .runtime_cook import (
    RuntimeArtifactManifest,
    runtime_manifest_to_dict,
)

LTHPKG_VERSION = "lathe.asset_foundry.lthpkg_v1"
REPAIR_HISTORY_VERSION = "lathe.asset_foundry.repair_history_v1"


@dataclass(frozen=True)
class ExternalArtifacts:
    """Optional filesystem paths to external artifacts.

    The writer copies them into the .lthpkg directory when present and
    records ``status: "real"``. When absent, it records ``status:
    "unbuilt"`` with a structured reason.
    """

    mesh_glb_path: str | Path | None = None
    asset_lth_path: str | Path | None = None
    preview_paths: tuple[str | Path, ...] = ()
    """Paths to preview images. Filenames are copied verbatim."""


@dataclass(frozen=True)
class LthpkgManifest:
    """The top-level manifest.json inside a .lthpkg directory."""

    version: str
    asset_id: str
    style_pack_id: str
    family: str
    generator_id: str
    seed: int
    """For reproducibility — same seed + parameters -> same asset."""

    parameters_hash: str
    """SHA-256 of the JSON-serialized generator parameters."""

    sidecar_files: Mapping[str, str]
    """sidecar_name -> filename within the .lthpkg directory."""

    quality_ladder_target: int
    quality_ladder_achieved: int
    overall_score: float
    created_utc: float
    """Unix epoch seconds (UTC) for provenance."""

    notes: str = ""


def _parameters_hash(parameters: Mapping[str, Any]) -> str:
    """Deterministic SHA-256 of generator parameters."""
    canonical = json.dumps(parameters, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()[:32]


def _build_semantic_index(asset: FoundryAsset) -> dict[str, Any]:
    """Build the semantic-index.json content."""
    return {
        "version": "lathe.asset_foundry.semantic_index_v1",
        "asset_id": asset.asset_id,
        "family": asset.spec.family,
        "style_pack_id": asset.spec.style_pack_id,
        "semantic_parts": list(asset.spec.semantic_parts),
        "semantic_sockets": [
            {
                "socket_id": s.socket_id,
                "role": s.role,
                "position_cm": list(s.position_cm),
                "orientation_quat": list(s.orientation_quat),
                "capacity": s.capacity,
                "allowed_attachments": list(s.allowed_attachments),
            }
            for s in asset.spec.sockets
        ],
        "material_slots": [
            {
                "slot_id": slot.slot_id,
                "zone_id_prefix": slot.zone_id_prefix,
                "material_class": slot.material_class,
                "palette_token": slot.palette_token,
                "uv_policy": slot.uv_policy,
            }
            for slot in asset.spec.material_slots
        ],
        "bbox_cm": [list(asset.bbox_cm[0]), list(asset.bbox_cm[1])],
        "quality_ladder_target": asset.quality_ladder_target,
    }


def _build_materials_json(asset: FoundryAsset) -> dict[str, Any]:
    """Build the materials.json sidecar (material slots + zone manifest)."""
    return {
        "version": "lathe.asset_foundry.materials_v1",
        "asset_id": asset.asset_id,
        "style_pack_id": asset.spec.style_pack_id,
        "slots": [
            {
                "slot_id": slot.slot_id,
                "zone_id_prefix": slot.zone_id_prefix,
                "material_class": slot.material_class,
                "palette_token": slot.palette_token,
                "uv_policy": slot.uv_policy,
            }
            for slot in asset.spec.material_slots
        ],
    }


def _build_operations_json(
    asset: FoundryAsset,
    op_graph: GeometryOpGraph | None,
    op_graph_plan: OpGraphPlan | None,
) -> dict[str, Any]:
    """Build the operations.json sidecar."""
    payload: dict[str, Any] = {
        "version": "lathe.asset_foundry.operations_v1",
        "asset_id": asset.asset_id,
        "generator_id": asset.spec.generator_id,
        "parameters": dict(asset.spec.parameters),
        "geometry_payload": dict(asset.spec.geometry_payload)
        if isinstance(asset.spec.geometry_payload, dict)
        else asset.spec.geometry_payload,
    }
    if op_graph is not None:
        provenance_summary = _op_graph_provenance_summary(op_graph)
        payload["op_graph"] = {
            "version": "lathe.asset_foundry.op_graph_v1",
            "node_count": len(op_graph.nodes),
            "provenance_summary": provenance_summary,
            "nodes": [
                {
                    "operation_id": node.operation_id,
                    "op": node.op,
                    "semantic_part": node.semantic_part,
                    "inputs": list(node.inputs),
                    "params": dict(node.params),
                    "required_capabilities": list(node.required_capabilities),
                    "fallback_policy": node.fallback_policy,
                    "evidence_requirements": list(node.evidence_requirements),
                    "bounds_cm": [list(node.bounds_cm[0]), list(node.bounds_cm[1])]
                    if node.bounds_cm is not None
                    else None,
                    "attribute_mapping": {
                        "preserved": list(node.attribute_mapping.preserved),
                        "transformed": list(node.attribute_mapping.transformed),
                        "split": list(node.attribute_mapping.split),
                        "merged": list(node.attribute_mapping.merged),
                        "generated": list(node.attribute_mapping.generated),
                        "dropped": list(node.attribute_mapping.dropped),
                    },
                }
                for node in op_graph.nodes
            ],
        }
    if op_graph_plan is not None:
        payload["op_graph_plan"] = {
            "asset_id": op_graph_plan.asset_id,
            "graph_version": op_graph_plan.graph_version,
            "lanes_by_op": dict(op_graph_plan.lanes_by_op),
            "capability_by_op": dict(op_graph_plan.capability_by_op),
            "unsupported_ops": list(op_graph_plan.unsupported_ops),
            "fallback_ops": list(op_graph_plan.fallback_ops),
            "not_started_ops": list(op_graph_plan.not_started_ops),
            "missing_from_matrix": list(op_graph_plan.missing_from_matrix),
            "topo_order": list(op_graph_plan.topo_order),
            "spatial_clusters": [
                {
                    "cluster_id": cluster.cluster_id,
                    "operation_ids": list(cluster.operation_ids),
                    "cluster_op_count": cluster.cluster_op_count,
                    "cluster_reason": cluster.cluster_reason,
                    "bounds_cm": [list(cluster.bounds_cm[0]), list(cluster.bounds_cm[1])]
                    if cluster.bounds_cm is not None
                    else None,
                }
                for cluster in op_graph_plan.spatial_clusters
            ],
            "boolean_clusters": [
                {
                    "cluster_id": cluster.cluster_id,
                    "operation_ids": list(cluster.operation_ids),
                    "boolean_ops": list(cluster.boolean_ops),
                    "input_primitive_ids": list(cluster.input_primitive_ids),
                    "boolean_expression": cluster.boolean_expression,
                    "preferred_backend": cluster.preferred_backend,
                    "actual_execution_mode": cluster.actual_execution_mode,
                    "fallback_diagnostic": cluster.fallback_diagnostic,
                }
                for cluster in op_graph_plan.boolean_clusters
            ],
        }
    return payload


def _op_graph_provenance_summary(op_graph: GeometryOpGraph) -> dict[str, Any]:
    summary = {
        "preserved": 0,
        "transformed": 0,
        "split": 0,
        "merged": 0,
        "generated": 0,
        "dropped": 0,
        "dropped_fields": {},
    }
    dropped_fields: dict[str, int] = {}
    for node in op_graph.nodes:
        mapping = node.attribute_mapping
        summary["preserved"] += len(mapping.preserved)
        summary["transformed"] += len(mapping.transformed)
        summary["split"] += len(mapping.split)
        summary["merged"] += len(mapping.merged)
        summary["generated"] += len(mapping.generated)
        summary["dropped"] += len(mapping.dropped)
        for field_name in mapping.dropped:
            dropped_fields[field_name] = dropped_fields.get(field_name, 0) + 1
    summary["dropped_fields"] = dropped_fields
    summary["provenance_loss_diagnostic"] = (
        "provenance_fields_dropped" if dropped_fields else ""
    )
    return summary


def _build_diagnostics_json(
    asset: FoundryAsset,
    capability_matrix: FoundryCapabilityMatrix,
    certificate: AssetQualityCertificate,
) -> dict[str, Any]:
    """Build the diagnostics.json sidecar.

    Includes the capability matrix slice + generator diagnostics +
    certificate findings.
    """
    return {
        "version": "lathe.asset_foundry.diagnostics_v1",
        "asset_id": asset.asset_id,
        "generator_diagnostics": list(asset.spec.diagnostics),
        "certificate_findings": list(certificate.findings),
        "certificate_repair_recommendations": list(
            certificate.repair_recommendations
        ),
        "capability_matrix": capability_matrix_to_dict(capability_matrix),
    }


def _build_evidence_json(
    asset: FoundryAsset,
    manifest: RuntimeArtifactManifest,
    certificate: AssetQualityCertificate,
    capability_matrix: FoundryCapabilityMatrix,
    external_artifacts: ExternalArtifacts | None = None,
) -> dict[str, Any]:
    """Build the evidence.json sidecar — top-level Foundry evidence."""
    return {
        "version": "lathe.asset_foundry.evidence_v1",
        "asset_id": asset.asset_id,
        "runtime_manifest": runtime_manifest_to_dict(manifest),
        "certificate": certificate_to_dict(certificate),
        "external_backend_evidence": _build_external_backend_evidence(
            capability_matrix
        ),
        "visual_quality_gate": _foundry_visual_quality_gate(
            asset,
            manifest,
            certificate,
            external_artifacts,
        ),
        "rule_of_truth": (
            "Every artifact in this package has a real path OR a status of "
            "'unbuilt'/'proxy' with a reason. Per Foundry §3, no fake-quality."
        ),
    }


def _build_external_backend_evidence(
    capability_matrix: FoundryCapabilityMatrix,
) -> list[dict[str, Any]]:
    """Surface external backend blockers in package evidence."""
    evidence: list[dict[str, Any]] = []
    for record in capability_matrix.records:
        if not record.backend_required:
            continue
        evidence.append(
            {
                "operation_id": record.operation_id,
                "status": "blocked",
                "blocker": record.fallback_reason or "backend_not_configured",
                "backend_required": record.backend_required,
                "artifact_path": None,
                "rule_of_truth": (
                    "No path is claimed until the backend writes an artifact."
                ),
            }
        )
    return evidence


def _foundry_visual_quality_gate(
    asset: FoundryAsset,
    manifest: RuntimeArtifactManifest,
    certificate: AssetQualityCertificate,
    external_artifacts: ExternalArtifacts | None,
) -> dict[str, Any]:
    pipeline_certified = certificate.achieved_level >= asset.quality_ladder_target
    render_mesh_status = manifest.render_mesh_status
    render_mesh_real = render_mesh_status == "real"
    preview_paths = []
    if external_artifacts is not None:
        preview_paths = [
            str(path)
            for path in external_artifacts.preview_paths
            if Path(path).exists()
        ]
    blockers: list[str] = []
    if not pipeline_certified:
        blockers.append("pipeline_not_certified")
    if not render_mesh_real:
        blockers.append(f"render_mesh_status_{render_mesh_status}")
    if not preview_paths:
        blockers.append("preview_evidence_not_present")
    if certificate.findings:
        blockers.append("certificate_findings_require_review")
    if not pipeline_certified:
        visual_quality_gate = "not_approved"
        visual_claim_level = "pipeline_failed"
    elif not render_mesh_real or not preview_paths:
        visual_quality_gate = "not_verified"
        visual_claim_level = "not_verified"
    elif blockers:
        visual_quality_gate = "review_required"
        visual_claim_level = "pipeline_certified_only"
    else:
        visual_quality_gate = "approved"
        visual_claim_level = "visual_approved"
    return {
        "version": "lathe.visual_quality_gate_v1",
        "pipeline_certified": pipeline_certified,
        "visual_quality_gate": visual_quality_gate,
        "human_review_required": visual_quality_gate != "approved",
        "visual_claim_level": visual_claim_level,
        "blockers": sorted(set(blockers)),
        "signals": {
            "render_mesh_real": render_mesh_real,
            "preview_count": len(preview_paths),
            "preview_paths": preview_paths,
            "certificate_finding_count": len(certificate.findings),
        },
    }


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, (str, int, float))]


def _dict_payload(value: Any, *, missing_status: str) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {"status": missing_status}


def _build_repair_history_json(
    asset: FoundryAsset,
    repair_history: Mapping[str, Any],
) -> dict[str, Any]:
    """Build optional repair-history.json without inventing rebuild evidence."""
    history = dict(repair_history)
    return {
        "version": REPAIR_HISTORY_VERSION,
        "asset_id": asset.asset_id,
        "status": str(history.get("status") or "not_verified"),
        "original_package": _dict_payload(
            history.get("original_package"),
            missing_status="not_verified",
        ),
        "diagnostic_ids": _string_list(history.get("diagnostic_ids")),
        "selected_repair_actions": _string_list(history.get("selected_repair_actions")),
        "patched_intent_identifiers": _string_list(history.get("patched_intent_identifiers")),
        "repair_target_layers": _string_list(history.get("repair_target_layers")),
        "attempted_vs_actual": list(history.get("attempted_vs_actual") or [])
        if isinstance(history.get("attempted_vs_actual"), list)
        else [],
        "rebuilt_package": _dict_payload(
            history.get("rebuilt_package"),
            missing_status="not_verified",
        ),
        "metric_deltas": _dict_payload(
            history.get("metric_deltas"),
            missing_status="not_verified",
        ),
        "preview_before_after": _dict_payload(
            history.get("preview_before_after"),
            missing_status="not_verified",
        ),
        "notes": _string_list(history.get("notes")),
        "rule_of_truth": (
            "Repair history records requested and applied semantic repairs. "
            "Missing rebuild or preview paths remain not_verified."
        ),
    }


def _package_reference(value: str | Path | Mapping[str, Any] | None) -> dict[str, Any]:
    """Normalize a package reference without inventing availability."""
    if isinstance(value, Mapping):
        return dict(value)
    if value is None:
        return {"status": "not_verified"}
    path = Path(value)
    return {
        "status": "real" if path.exists() else "not_verified",
        "path": str(path).replace("\\", "/"),
    }


def _repair_trace_actions(repair_traces: list[Mapping[str, Any]]) -> list[str]:
    actions: list[str] = []
    for trace in repair_traces:
        action = trace.get("action") or trace.get("attempted_operation")
        if isinstance(action, (str, int, float)):
            actions.append(str(action))
    return sorted(set(actions))


def _repair_trace_target_layers(repair_traces: list[Mapping[str, Any]]) -> list[str]:
    layers: list[str] = []
    for trace in repair_traces:
        layer = trace.get("repair_target_layer")
        if isinstance(layer, (str, int, float)):
            layers.append(str(layer))
        details = trace.get("details")
        if isinstance(details, Mapping):
            detail_layer = details.get("repair_target_layer")
            if isinstance(detail_layer, (str, int, float)):
                layers.append(str(detail_layer))
            for operation in details.get("executed_operations") or []:
                if isinstance(operation, Mapping):
                    op_layer = operation.get("repair_target_layer")
                    if isinstance(op_layer, (str, int, float)):
                        layers.append(str(op_layer))
    return sorted(set(layers))


def _repair_trace_identifiers(repair_traces: list[Mapping[str, Any]]) -> list[str]:
    identifiers: list[str] = []
    for trace in repair_traces:
        details = trace.get("details")
        if not isinstance(details, Mapping):
            continue
        for operation in details.get("executed_operations") or []:
            if isinstance(operation, Mapping):
                operation_id = operation.get("operation_id")
                if isinstance(operation_id, (str, int, float)):
                    identifiers.append(str(operation_id))
    return sorted(set(identifiers))


def _repair_attempted_vs_actual(
    repair_traces: list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for trace in repair_traces:
        row = {
            "action": str(trace.get("action") or trace.get("attempted_operation") or ""),
            "target": str(trace.get("target") or ""),
            "repair_target_layer": str(trace.get("repair_target_layer") or "not_verified"),
            "attempted_operation": str(trace.get("attempted_operation") or trace.get("action") or ""),
            "actual_operation": str(trace.get("actual_operation") or "not_verified"),
            "applied": bool(trace.get("applied", False)),
        }
        details = trace.get("details")
        if isinstance(details, Mapping):
            executed: list[dict[str, Any]] = []
            for operation in details.get("executed_operations") or []:
                if isinstance(operation, Mapping):
                    executed.append(
                        {
                            "operation_id": str(operation.get("operation_id") or ""),
                            "attempted_operation": str(
                                operation.get("attempted_operation")
                                or operation.get("operation")
                                or ""
                            ),
                            "actual_operation": str(
                                operation.get("actual_operation")
                                or operation.get("operation")
                                or "not_verified"
                            ),
                            "repair_target_layer": str(
                                operation.get("repair_target_layer") or "not_verified"
                            ),
                            "primitive_type": str(operation.get("primitive_type") or ""),
                            "part": str(operation.get("part") or ""),
                            "component": str(operation.get("component") or ""),
                        }
                    )
            if executed:
                row["executed_operations"] = executed
        rows.append(row)
    return rows


def build_repair_history_evidence(
    *,
    original_package: str | Path | Mapping[str, Any] | None,
    diagnostic_ids: list[str] | tuple[str, ...],
    repair_traces: list[Mapping[str, Any]],
    rebuilt_package: str | Path | Mapping[str, Any] | None = None,
    metric_deltas: Mapping[str, Any] | None = None,
    preview_before_after: Mapping[str, Any] | None = None,
    status: str | None = None,
    notes: list[str] | tuple[str, ...] = (),
) -> dict[str, Any]:
    """Build a truthful repair-history payload from deterministic repair traces.

    The payload is intentionally metadata-first: it can prove that a
    diagnostic selected and applied graph/intent repair operations even
    when a full rebuilt render/package is still unavailable. Rebuild and
    preview references default to ``not_verified``.
    """
    rebuilt_ref = _package_reference(rebuilt_package)
    return {
        "status": status
        or (
            "repair_metadata_recorded"
            if repair_traces
            else "not_verified"
        ),
        "original_package": _package_reference(original_package),
        "diagnostic_ids": [str(item) for item in diagnostic_ids],
        "selected_repair_actions": _repair_trace_actions(repair_traces),
        "patched_intent_identifiers": _repair_trace_identifiers(repair_traces),
        "repair_target_layers": _repair_trace_target_layers(repair_traces),
        "attempted_vs_actual": _repair_attempted_vs_actual(repair_traces),
        "rebuilt_package": rebuilt_ref,
        "metric_deltas": dict(metric_deltas) if metric_deltas is not None else {"status": "not_verified"},
        "preview_before_after": dict(preview_before_after)
        if preview_before_after is not None
        else {"status": "not_verified"},
        "notes": [str(item) for item in notes],
    }


def _build_manifest_json(
    asset: FoundryAsset,
    manifest: RuntimeArtifactManifest,
    certificate: AssetQualityCertificate,
    sidecar_files: Mapping[str, str],
) -> dict[str, Any]:
    """Build the manifest.json — the .lthpkg top-level manifest."""
    pkg_manifest = LthpkgManifest(
        version=LTHPKG_VERSION,
        asset_id=asset.asset_id,
        style_pack_id=asset.spec.style_pack_id,
        family=asset.spec.family,
        generator_id=asset.spec.generator_id,
        seed=asset.spec.seed,
        parameters_hash=_parameters_hash(asset.spec.parameters),
        sidecar_files=sidecar_files,
        quality_ladder_target=asset.quality_ladder_target,
        quality_ladder_achieved=certificate.achieved_level,
        overall_score=certificate.overall_score,
        created_utc=time.time(),
        notes=asset.notes,
    )
    return {
        "version": pkg_manifest.version,
        "asset_id": pkg_manifest.asset_id,
        "style_pack_id": pkg_manifest.style_pack_id,
        "family": pkg_manifest.family,
        "generator_id": pkg_manifest.generator_id,
        "seed": pkg_manifest.seed,
        "parameters_hash": pkg_manifest.parameters_hash,
        "sidecar_files": dict(pkg_manifest.sidecar_files),
        "quality_ladder_target": pkg_manifest.quality_ladder_target,
        "quality_ladder_achieved": pkg_manifest.quality_ladder_achieved,
        "overall_score": pkg_manifest.overall_score,
        "created_utc": pkg_manifest.created_utc,
        "notes": pkg_manifest.notes,
    }


def write_lthpkg(
    asset: FoundryAsset,
    manifest: RuntimeArtifactManifest,
    certificate: AssetQualityCertificate,
    output_dir: str | Path,
    *,
    op_graph: GeometryOpGraph | None = None,
    capability_matrix: FoundryCapabilityMatrix | None = None,
    external_artifacts: ExternalArtifacts | None = None,
    repair_history: Mapping[str, Any] | None = None,
) -> Path:
    """Write a .lthpkg directory.

    Args:
        asset: the generator's FoundryAsset spec.
        manifest: the runtime manifest from cook_runtime_artifact.
        certificate: the quality certificate from
            compute_asset_certificate.
        output_dir: parent directory. The .lthpkg will be created at
            ``output_dir / f"{asset.asset_id}.lthpkg"``.
        op_graph: optional GeometryOpGraph; if provided, the writer
            plans it against the capability matrix and emits the plan
            in operations.json.
        capability_matrix: optional pre-built matrix; defaults to a
            fresh build_capability_matrix() call.
        external_artifacts: optional filesystem paths to copy into the
            .lthpkg directory (mesh.glb, asset.lth, previews/).
        repair_history: optional before/after repair evidence sidecar.

    Returns:
        Path to the created .lthpkg directory.
    """
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    pkg_dir = output_root / f"{asset.asset_id}.lthpkg"
    pkg_dir.mkdir(parents=True, exist_ok=True)
    previews_dir = pkg_dir / "previews"
    previews_dir.mkdir(parents=True, exist_ok=True)

    matrix = capability_matrix if capability_matrix is not None else build_capability_matrix()
    op_graph_plan = plan_op_graph(op_graph, matrix) if op_graph is not None else None

    sidecar_files: dict[str, str] = {}

    # Build sidecar dicts.
    semantic_index_dict = _build_semantic_index(asset)
    materials_dict = _build_materials_json(asset)
    operations_dict = _build_operations_json(asset, op_graph, op_graph_plan)
    diagnostics_dict = _build_diagnostics_json(asset, matrix, certificate)
    evidence_dict = _build_evidence_json(
        asset,
        manifest,
        certificate,
        matrix,
        external_artifacts,
    )
    runtime_dict = runtime_manifest_to_dict(manifest)
    repair_history_dict = (
        _build_repair_history_json(asset, repair_history)
        if repair_history is not None
        else None
    )

    # Write sidecars.
    sidecars: tuple[tuple[str, str, dict[str, Any]], ...] = (
        ("semantic_index", "semantic-index.json", semantic_index_dict),
        ("materials", "materials.json", materials_dict),
        ("operations", "operations.json", operations_dict),
        ("diagnostics", "diagnostics.json", diagnostics_dict),
        ("evidence", "evidence.json", evidence_dict),
        ("runtime", "runtime.json", runtime_dict),
    )
    for key, filename, payload in sidecars:
        sidecar_files[key] = filename
        (pkg_dir / filename).write_text(
            json.dumps(payload, indent=2, sort_keys=False),
            encoding="utf-8",
        )
    if repair_history_dict is not None:
        sidecar_files["repair_history"] = "repair-history.json"
        (pkg_dir / "repair-history.json").write_text(
            json.dumps(repair_history_dict, indent=2, sort_keys=False),
            encoding="utf-8",
        )

    # Optional external artifacts.
    if external_artifacts is not None:
        if external_artifacts.mesh_glb_path is not None:
            mesh_src = Path(external_artifacts.mesh_glb_path)
            if mesh_src.exists():
                mesh_dst = pkg_dir / "mesh.glb"
                shutil.copy2(mesh_src, mesh_dst)
                sidecar_files["mesh_glb"] = "mesh.glb"
        if external_artifacts.asset_lth_path is not None:
            lth_src = Path(external_artifacts.asset_lth_path)
            if lth_src.exists():
                lth_dst = pkg_dir / "asset.lth"
                shutil.copy2(lth_src, lth_dst)
                sidecar_files["asset_lth"] = "asset.lth"
        copied_previews: list[str] = []
        for preview_src in external_artifacts.preview_paths:
            src = Path(preview_src)
            if src.exists():
                dst = previews_dir / src.name
                shutil.copy2(src, dst)
                copied_previews.append(f"previews/{src.name}")
        if copied_previews:
            sidecar_files["previews"] = ",".join(copied_previews)

    # Top-level manifest.
    manifest_dict = _build_manifest_json(asset, manifest, certificate, sidecar_files)
    (pkg_dir / "manifest.json").write_text(
        json.dumps(manifest_dict, indent=2, sort_keys=False),
        encoding="utf-8",
    )

    return pkg_dir


__all__ = [
    "LTHPKG_VERSION",
    "REPAIR_HISTORY_VERSION",
    "ExternalArtifacts",
    "LthpkgManifest",
    "build_repair_history_evidence",
    "write_lthpkg",
]
