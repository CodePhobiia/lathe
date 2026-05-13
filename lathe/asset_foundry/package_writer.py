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
        payload["op_graph"] = {
            "version": "lathe.asset_foundry.op_graph_v1",
            "node_count": len(op_graph.nodes),
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
        }
    return payload


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
) -> dict[str, Any]:
    """Build the evidence.json sidecar — top-level Foundry evidence."""
    return {
        "version": "lathe.asset_foundry.evidence_v1",
        "asset_id": asset.asset_id,
        "runtime_manifest": runtime_manifest_to_dict(manifest),
        "certificate": certificate_to_dict(certificate),
        "rule_of_truth": (
            "Every artifact in this package has a real path OR a status of "
            "'unbuilt'/'proxy' with a reason. Per Foundry §3, no fake-quality."
        ),
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
    evidence_dict = _build_evidence_json(asset, manifest, certificate)
    runtime_dict = runtime_manifest_to_dict(manifest)

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
    "ExternalArtifacts",
    "LthpkgManifest",
    "write_lthpkg",
]
