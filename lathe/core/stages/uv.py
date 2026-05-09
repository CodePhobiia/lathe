"""UV stage step body.

Extracted from ``lathe/executor.py`` during Stage 2.IV.
"""

from __future__ import annotations

from typing import Any

from ...backends import stage_bundle_contract_version_issue
from ...capabilities import probe_uv_backend
from ...style_presets import stage_axis
from ...uv_runtime import derive_uv_semantics, enrich_chart_manifest_with_semantics
from ..common import dump_json, relpath
from ..errors import contract_version_stage_error, runtime_stage_error
from ..io import export_glb, export_runtime_scene_glb
from ..mesh import RuntimeMesh
from ..uv_ops import apply_box_uv, apply_xatlas_uv, apply_xatlas_uv_per_part


def run(executor: Any, topology_bundle: dict[str, Any]) -> dict[str, Any]:
    """Run.

    Args:
        executor: executor argument.
        topology_bundle: topology_bundle argument.

    Returns:
        The result.
    """
    backend = executor.selected_backends["uv"]
    topology_version_issue = stage_bundle_contract_version_issue("topology", topology_bundle)
    if topology_version_issue is not None:
        raise contract_version_stage_error(
            executor.asset_name,
            "topology",
            str(topology_bundle.get("backend_id") or ""),
            topology_version_issue,
            details={
                "consumer_stage": "uv",
                "backend_version": topology_bundle.get("backend_version"),
            },
        )
    topology_runtime: RuntimeMesh = executor.runtime["topology"]["runtime_mesh"]
    # Roadmap §6.8: route on texture_authoring axis. flat_vertex_color skips
    # unwrap; hand_painted picks single 0..1 UV; procedural_designer picks
    # unique UDIMs. We record the decision in the bundle so downstream
    # surface_graph can consume it; the actual unwrap path remains the
    # existing xatlas/box dispatch to avoid breaking legacy examples.
    style_authoring = stage_axis(executor.asset, "texture_authoring")
    style_routing = {
        "texture_authoring": style_authoring,
        "skip_unwrap": style_authoring == "flat_vertex_color",
        "uv_layout_hint": (
            "single_zero_to_one" if style_authoring == "hand_painted"
            else "unique_udim" if style_authoring == "procedural_designer"
            else "tileable" if style_authoring == "procedural_painted_feel"
            else "vertex_color"
        ),
    }
    adapter_report = probe_uv_backend(executor.runtime_config)
    strict = bool(adapter_report.get("strict", False))
    if (
        adapter_report["requested_adapter"] == "xatlas"
        and not adapter_report["real_adapter_available"]
        and strict
    ):
        raise runtime_stage_error(
            executor.asset_name,
            "uv",
            backend["id"],
            "Requested xatlas UV adapter is unavailable and strict mode is enabled",
            details=adapter_report,
        )
    try:
        if adapter_report["selected_adapter"] == "xatlas":
            multi_part_scene = executor.runtime["topology"].get("multi_part_scene")
            scene_part_count = 0
            if multi_part_scene is not None:
                manifest = getattr(multi_part_scene, "manifest", None)
                if manifest:
                    scene_part_count = sum(
                        1
                        for entry in manifest
                        if getattr(entry, "face_count", 0) > 0
                    )
            distinct_face_parts = (
                len(set(topology_runtime.face_parts))
                if len(topology_runtime.face_parts) == len(topology_runtime.mesh.faces)
                else 0
            )
            if scene_part_count > 1 or distinct_face_parts > 1:
                uv_mesh, uv_meta, execution = apply_xatlas_uv_per_part(
                    topology_runtime,
                    executor.asset,
                    executor.runtime_config,
                    multi_part_scene=multi_part_scene,
                )
            else:
                uv_mesh, uv_meta, execution = apply_xatlas_uv(
                    topology_runtime, executor.asset, executor.runtime_config
                )
            adapter_report["status"] = "success"
        else:
            uv_mesh, uv_meta = apply_box_uv(topology_runtime, executor.asset)
            execution = {"mode": "reference_box"}
            adapter_report["status"] = (
                "forced" if adapter_report["requested_adapter"] in {"box", "reference_box"} else "fallback"
            )
            if not adapter_report["real_adapter_available"]:
                adapter_report["fallback_reason"] = adapter_report["probe"].get(
                    "message", "xatlas unavailable"
                )
    except (ImportError, OSError, ValueError, RuntimeError, AttributeError, IndexError, TypeError) as exc:
        # The xatlas path dispatches into a compiled C extension and trimesh
        # mesh IO; failure modes span import/load errors, parametrization
        # errors, and mesh-shape mismatches. Fall back to reference box UV.
        if strict:
            raise runtime_stage_error(
                executor.asset_name,
                "uv",
                backend["id"],
                f"UV adapter failed in strict mode: {exc}",
                details={"adapter_report": adapter_report, "error_type": type(exc).__name__},
            ) from exc
        uv_mesh, uv_meta = apply_box_uv(topology_runtime, executor.asset)
        execution = {"mode": "reference_box"}
        adapter_report["status"] = "fallback"
        adapter_report["fallback_reason"] = str(exc)
        adapter_report["error"] = {"type": type(exc).__name__, "message": str(exc)}
    actual_adapter = execution.get("mode", adapter_report["selected_adapter"])
    uv_path = executor.stage_dirs["uv"] / "uv.glb"
    if actual_adapter == "xatlas_per_part" and len(set(uv_mesh.face_parts)) > 1:
        # Preserve named-part identity through the UV stage GLB so downstream
        # consumers and external inspection can see per-part islands.
        export_runtime_scene_glb(uv_mesh, uv_path)
    else:
        export_glb(uv_mesh.mesh, uv_path)
    uv_semantics = derive_uv_semantics(
        executor.runtime["topology"]["bundle"], executor.runtime["shape"]["bundle"]
    )
    generated_uv_atlas_hints = uv_semantics.get("generated_uv_atlas_hints", {})
    if isinstance(generated_uv_atlas_hints, dict) and generated_uv_atlas_hints:
        generated_source_uv_remap = dict(
            uv_meta.get("packing_report", {}).get("generated_source_uv_remap", {})
        )
        enriched_hints = {
            **generated_uv_atlas_hints,
            "xatlas_source_uv_remap": generated_source_uv_remap,
        }
        uv_meta["packing_report"] = {
            **uv_meta.get("packing_report", {}),
            "generated_uv_atlas_hints": dict(enriched_hints),
        }
        uv_meta["uv_organization"] = {
            **uv_meta.get("uv_organization", {}),
            "generated_uv_atlas_hints": dict(enriched_hints),
        }
        strip_records = generated_uv_atlas_hints.get("strips", [])
        if isinstance(strip_records, list) and strip_records:
            generated_charts = [
                {
                    "chart_id": f"uvc_generated_bevel_strip_{index + 1:02d}",
                    "group": "generated_post_boolean_polybevel",
                    "grouping": "generated_bevel_strip",
                    "island_name": f"generated_bevel_strip_{index + 1:02d}",
                    "parts": [],
                    "material": "",
                    "material_id": "",
                    "uv_sets": [
                        str(entry.get("name", "base"))
                        for entry in uv_meta.get("uv_sets", [])
                        if isinstance(entry, dict)
                    ],
                    "texel_density_scale": 1.0,
                    "source": "exact_solid_generated_uv_semantics",
                    "uv_span_cm": record.get("uv_span_cm", 0.0),
                    "closed": bool(record.get("closed", False)),
                    "edge_count": int(record.get("edge_count", 0) or 0),
                    "source_uv_bounds": list(record.get("source_uv_bounds", []))
                    if isinstance(record.get("source_uv_bounds"), list)
                    else [],
                    "source_uv_polygon": list(record.get("source_uv_polygon", []))
                    if isinstance(record.get("source_uv_polygon"), list)
                    else [],
                    "source_uv_space": str(record.get("source_uv_space", "")),
                }
                for index, record in enumerate(strip_records)
                if isinstance(record, dict)
            ]
            if generated_charts:
                uv_meta["chart_manifest"] = list(uv_meta.get("chart_manifest", [])) + generated_charts
    uv_meta["chart_manifest"] = enrich_chart_manifest_with_semantics(
        uv_meta.get("chart_manifest", []),
        uv_semantics,
    )
    bundle = {
        "backend_id": backend["id"],
        "backend_version": backend["version"],
        "mesh_uri": relpath(executor.out_dir, uv_path),
        "uv_sets": uv_meta["uv_sets"],
        "packing_report": uv_meta["packing_report"],
        "texel_density": uv_meta["texel_density"],
        "uv_organization": uv_meta.get("uv_organization", {}),
        "chart_manifest": uv_meta.get("chart_manifest", []),
        "material_id_layout": uv_meta.get("material_id_layout", {}),
        **uv_semantics,
        "adapter_report": {**adapter_report, "actual_adapter": actual_adapter, "execution": execution},
        "style_routing": style_routing,
        "provenance": {
            "backend_id": backend["id"],
            "backend_version": backend["version"],
            "runtime_adapter": actual_adapter,
        },
    }
    executor.runtime["uv"] = {"bundle": bundle, "runtime_mesh": uv_mesh, "uv_meta": uv_meta}
    dump_json(executor.stage_dirs["uv"] / "bundle.json", bundle)
    return bundle
