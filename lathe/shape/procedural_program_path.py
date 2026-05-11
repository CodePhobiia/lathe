"""Procedural-synthesizer shape backend dispatch.

Mirrors :mod:`lathe.shape.mesh_program_path` but consumes the
procedural synthesizer's :class:`SynthesisResult` instead of a
parsed ``mesh_program{}`` AST. Lowers the synthesizer's ShapeIR v2
:class:`ShapeProgram` through ``lower_to_v1`` to dict-form v1 records,
materializes those into :class:`ShapePrimitive` instances, wraps in a
:class:`ShapeIR`, and feeds the same exact-solid compilation chain.

Output is a scaffold-shaped dict identical in structure to what
:func:`lathe.scaffold_compiler.compile_scaffold_candidates` and
:func:`lathe.shape.mesh_program_path.compile_mesh_program_candidate`
return — so the rest of the shape backend (provider mux, conformance
fit, bundle assembly) consumes it unchanged.

This is the architectural placement called out by
``docs/asset-quality/procedural-synthesizer-architecture-correction.md``:
the synthesizer feeds real geometry, not a validate-stage report.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from ..asset_graph import AssetGraph
from ..asset_quality.procedural_synthesizer import SynthesisResult
from ..asset_quality.shape_ir_v2 import _primitive_from_v1_record, lower_to_v1
from ..exact_solids import compile_explicit_surface_mesh
from ..fidelity import infer_fidelity_profile
from ..geometry import resolve_geometry_kernel
from ..mesh_finalize import finalize_mesh_ir
from ..scaffold_compiler import _game_pipeline_hints, _make_color
from ..shape_ir import ShapeIR, ShapePrimitive, ShapeRegion


__all__ = [
    "compile_procedural_program_candidate",
    "runtime_from_asset",
    "synthesizer_eligible",
]


def synthesizer_eligible(
    asset: dict[str, Any], runtime_config: dict[str, Any] | None
) -> bool:
    """Return True iff the procedural synthesizer can produce a program.

    Predicate is conservative: only true when the asset carries enough
    authored intent for the synthesizer to compose something. The
    fallback to legacy ``compile_scaffold_candidates`` covers everything
    else.

    Eligibility requires:
      - No ``mesh_program{}`` block in source (the mesh_program path
        takes precedence — it is the explicit authored procedural path).
      - Either ``asset["build"]["shape"]["procedural"]`` OR
        ``asset["intent"]["construction_graph"]`` carries a graph with
        at least one node.
    """
    shape_cfg = asset.get("build", {}).get("shape") if isinstance(asset, dict) else None
    if isinstance(shape_cfg, dict):
        # mesh_program takes precedence — never displace it.
        mesh_program = shape_cfg.get("mesh_program")
        if isinstance(mesh_program, dict) and mesh_program.get("statements"):
            return False
        # Procedural block on the build.shape — preferred location.
        procedural = shape_cfg.get("procedural")
        if isinstance(procedural, dict):
            cg = procedural.get("construction_graph")
            if isinstance(cg, dict):
                nodes = cg.get("nodes")
                if isinstance(nodes, list) and nodes:
                    return True
    # Fallback location: asset.intent.construction_graph.
    intent = asset.get("intent") if isinstance(asset, dict) else None
    if isinstance(intent, dict):
        cg = intent.get("construction_graph")
        if isinstance(cg, dict):
            nodes = cg.get("nodes")
            if isinstance(nodes, list) and nodes:
                return True
    return False


def runtime_from_asset(asset: dict[str, Any]) -> dict[str, Any]:
    """Construct a synthesizer runtime from authored asset fields.

    The synthesizer's runtime is a dict containing ``design_brief`` and
    ``construction_graph``. At shape-stage time the validate-stage's
    runtime is not yet populated, so we synthesize one from the
    authored asset:

      - design_brief.brief: from asset.build.shape.procedural.brief OR
        asset.intent.brief OR {}.
      - construction_graph: from asset.build.shape.procedural.construction_graph
        OR asset.intent.construction_graph.
    """
    shape_cfg = asset.get("build", {}).get("shape", {}) or {}
    procedural = shape_cfg.get("procedural") if isinstance(shape_cfg, dict) else None
    intent = asset.get("intent") if isinstance(asset, dict) else None

    brief: dict[str, Any] = {}
    if isinstance(procedural, dict):
        b = procedural.get("brief")
        if isinstance(b, dict):
            brief.update(b)
    if not brief and isinstance(intent, dict):
        b = intent.get("brief")
        if isinstance(b, dict):
            brief.update(b)

    construction_graph: dict[str, Any] = {}
    if isinstance(procedural, dict):
        cg = procedural.get("construction_graph")
        if isinstance(cg, dict):
            construction_graph = cg
    if not construction_graph and isinstance(intent, dict):
        cg = intent.get("construction_graph")
        if isinstance(cg, dict):
            construction_graph = cg

    return {
        "design_brief": {"brief": brief},
        "construction_graph": construction_graph,
    }


def _regions_from_primitives(primitives: list[ShapePrimitive]) -> list[ShapeRegion]:
    """Build ShapeRegion records from primitives (mirror mesh_program path)."""
    regions: list[ShapeRegion] = []
    for index, primitive in enumerate(primitives):
        if primitive.blend_mode == "subtract":
            continue
        # Use placeholder center/extents — downstream surface/UV stages
        # consume the primitive's own bounds for material zoning, not
        # the region's stored bounds. The region exists to give the
        # primitive a stable name/component label for the topology /
        # surface stages.
        regions.append(
            ShapeRegion(
                name=f"procedural.region.{index}",
                part=str(primitive.part or "body"),
                component=str(primitive.primitive_type or "primitive"),
                center=tuple(primitive.center) if primitive.center else (0.0, 0.0, 0.0),
                extents=(1.0, 1.0, 1.0),
                tags=["procedural"],
            )
        )
    return regions


def compile_procedural_program_candidate(
    asset_graph: AssetGraph,
    synthesis_result: SynthesisResult,
    *,
    mode: str,
    conditioning: dict[str, Any],
    runtime_config: dict[str, Any] | None = None,
    work_dir: Path | None = None,
) -> dict[str, Any]:
    """Lower the synthesizer's ShapeProgram into a scaffold-shaped result.

    Returns a dict whose shape matches
    :func:`lathe.scaffold_compiler.compile_scaffold_candidates` so the
    rest of :func:`lathe.shape.backend.run_shape_backend` consumes it
    unchanged.
    """
    trace_path: Path | None = None
    latest_trace_path: Path | None = None
    if work_dir is not None:
        work_dir.mkdir(parents=True, exist_ok=True)
        trace_path = work_dir / "procedural_program_progress.jsonl"
        latest_trace_path = work_dir / "procedural_program_progress_latest.json"
        trace_path.write_text("", encoding="utf-8")

    def _trace(event: dict[str, Any]) -> None:
        if trace_path is None:
            return
        payload = {"time": time.time(), "asset": asset_graph.name, **event}
        line = json.dumps(payload, sort_keys=True, default=str)
        with trace_path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
            handle.flush()
        if latest_trace_path is not None:
            latest_trace_path.write_text(
                json.dumps(payload, indent=2, sort_keys=True, default=str),
                encoding="utf-8",
            )

    _trace(
        {
            "event": "compile_start",
            "mode": mode,
            "shape_program_op_count": len(synthesis_result.shape_program.ops),
            "synthesized_node_count": len(synthesis_result.synthesized_graph_nodes),
            "family_dispatch_used": synthesis_result.trace.family_dispatch_used,
        }
    )

    shape_program = synthesis_result.shape_program
    geometry_kernel = resolve_geometry_kernel(runtime_config)
    geometry_kernel_id = getattr(geometry_kernel, "name", None)

    # Lower ShapeIR v2 ShapeProgram -> v1 records (dict form)
    _trace({"event": "lower_to_v1_start", "op_count": len(shape_program.ops)})
    adapter = lower_to_v1(shape_program, geometry_kernel=geometry_kernel)
    _trace(
        {
            "event": "lower_to_v1_end",
            "v1_record_count": len(adapter.v1_records),
            "diagnostic_count": len(adapter.diagnostics),
        }
    )

    # Convert v1 records to ShapePrimitive instances
    target_part = (
        asset_graph.parts[0].name if asset_graph.parts else "body"
    )
    primitives: list[ShapePrimitive] = []
    for record in adapter.v1_records:
        try:
            primitive = _primitive_from_v1_record(record)
        except (TypeError, ValueError) as exc:
            _trace(
                {
                    "event": "primitive_skipped",
                    "primitive_type": record.get("primitive_type"),
                    "reason": str(exc),
                }
            )
            continue
        # Ensure every primitive has a part assignment
        if not primitive.part:
            primitive.part = target_part
        primitives.append(primitive)

    if not primitives:
        _trace({"event": "no_primitives", "reason": "lower_to_v1_produced_no_primitives"})
        # Empty primitive list — synthesizer ran but produced nothing
        # the kernel can build. Caller falls through to scaffold compiler.
        raise RuntimeError(
            "procedural synthesizer produced no convertible primitives "
            "(shape_program.ops=%d, v1_records=%d). Construction graph "
            "may be empty or generators unsupported."
            % (len(shape_program.ops), len(adapter.v1_records))
        )

    primitives_used = sorted({primitive.primitive_type for primitive in primitives})
    regions = _regions_from_primitives(primitives)

    signature = {
        "shape_source": "procedural_synthesizer",
        "primitive_count": len(primitives),
        "primitives_used": primitives_used,
        "synthesized_node_count": len(synthesis_result.synthesized_graph_nodes),
    }
    assessment = {
        "shape_source": "procedural_synthesizer",
        "family_dispatch_used": synthesis_result.trace.family_dispatch_used,
        "attempted_via": synthesis_result.trace.attempted_via,
    }

    shape_ir = ShapeIR(
        asset_name=asset_graph.name,
        family=asset_graph.family,
        blueprint_id="procedural_synthesizer_v1",
        symmetry_axis=asset_graph.symmetry_axis,
        units="cm",
        primitives=primitives,
        regions=regions,
        primitives_used=primitives_used,
        part_graph=list(asset_graph.part_graph),
        signature=signature,
        assessment=assessment,
    )

    fidelity = infer_fidelity_profile(asset_graph)
    _trace(
        {
            "event": "exact_surface_start",
            "primitive_count": len(primitives),
            "geometry_kernel": geometry_kernel_id,
            "fidelity": fidelity.tier,
        }
    )
    mesh, face_parts, exact_report = compile_explicit_surface_mesh(
        shape_ir,
        fidelity,
        combine_mode="explicit_mesh",
        geometry_kernel=geometry_kernel,
    )
    _trace(
        {
            "event": "exact_surface_end",
            "vertex_count": len(mesh.vertices),
            "face_count": len(mesh.faces),
            "mode": exact_report.get("mode"),
            "boolean_kernel": exact_report.get("boolean_kernel"),
        }
    )
    if not face_parts:
        face_parts = [target_part] * len(mesh.faces)

    part_colors = {part.name: _make_color(part.name) for part in asset_graph.parts}
    if target_part not in part_colors:
        part_colors[target_part] = _make_color(target_part)

    game_pipeline_hints = _game_pipeline_hints(asset_graph, shape_ir)
    integration_report = {
        "mode": "procedural_synthesizer_explicit_surface",
        "shape_source": "procedural_synthesizer",
        "primitive_count": len(primitives),
        "synthesized_node_count": len(synthesis_result.synthesized_graph_nodes),
        "exact_report": exact_report,
        "synthesizer_trace_entry_count": len(synthesis_result.trace.entries),
    }
    mesh_ir_payload = finalize_mesh_ir(
        mesh,
        shape_ir,
        list(face_parts),
        metadata={"integration_report": integration_report},
    ).to_dict()

    selection_notes = [
        "shape sourced from procedural synthesizer",
        f"shape_program_op_count={len(shape_program.ops)}",
        f"primitive_count={len(primitives)}",
        f"primitives_used={','.join(primitives_used)}",
        f"family_dispatch_used={synthesis_result.trace.family_dispatch_used}",
        f"fidelity={fidelity.tier}",
    ]
    candidate_score = 0.80
    runtime_candidate = {
        "mesh": mesh,
        "face_parts": list(face_parts),
        "part_colors": part_colors,
        "units": "cm",
        "meta": {
            "parts": sorted({region.part for region in regions}) or [target_part],
            "coarse_material_slots": max(1, len(asset_graph.materials)),
            "score": candidate_score,
            "selection_notes": selection_notes,
            "conditioning": {
                "provider": None,
                "reference_strength": float(conditioning.get("reference_strength", 0.0)),
                "family": asset_graph.family,
                "native_scaffold": True,
                "mode": mode,
                "blueprint_id": shape_ir.blueprint_id,
                "shape_source": "procedural_synthesizer",
                "quality_plan_consumed": bool(conditioning.get("quality_plan_consumed")),
                "quality_generation_source_stage": conditioning.get(
                    "quality_generation_source_stage"
                ),
                "quality_conditioning": dict(conditioning.get("quality_conditioning", {})),
            },
            "blueprint_id": shape_ir.blueprint_id,
            "primitives_used": list(primitives_used),
            "shape_assessment": dict(shape_ir.assessment),
            "repairs_applied": [],
            "feature_report": {
                "shape_source": "procedural_synthesizer",
                "feature_ops_used": [],
                "shape_assessment": dict(shape_ir.assessment),
                "game_pipeline_hints": game_pipeline_hints,
            },
            "candidate_params": {"shape_source": "procedural_synthesizer"},
            "game_pipeline_hints": game_pipeline_hints,
            "integration_report": integration_report,
            "mesh_ir": mesh_ir_payload,
            "synthesizer_trace": synthesis_result.trace.to_dict(),
        },
    }

    _trace({"event": "compile_end"})
    return {
        "asset_graph": asset_graph,
        "shape_irs": [shape_ir],
        "runtime_candidates": [runtime_candidate],
        "report": {
            "family": asset_graph.family,
            "generator": "procedural_synthesizer",
            "shape_source": "procedural_synthesizer",
            "asset_graph": asset_graph.to_dict(),
            "shape_irs": [shape_ir.to_dict()],
            "blueprints": [],
            "feature_reports": [runtime_candidate["meta"]["feature_report"]],
            "candidate_search": [{"shape_source": "procedural_synthesizer"}],
            "candidate_search_summary": [
                {
                    "candidate_index": 0,
                    "pre_score": candidate_score,
                    "shortlisted": True,
                    "shape_assessment": dict(shape_ir.assessment),
                }
            ],
            "fidelity": fidelity.to_dict(),
            "signature": dict(shape_ir.signature),
            "blueprint_id": shape_ir.blueprint_id,
            "primitives_used": list(primitives_used),
            "shape_assessment": dict(shape_ir.assessment),
            "repairs": [],
            "authoritative_candidate_reason": "procedural_synthesizer",
            "geometry_kernel": exact_report.get("boolean_kernel") or geometry_kernel_id,
            "game_pipeline_hints": game_pipeline_hints,
            "synthesizer_trace": synthesis_result.trace.to_dict(),
            "synthesized_graph_nodes": [
                dict(node) for node in synthesis_result.synthesized_graph_nodes
            ],
        },
    }
