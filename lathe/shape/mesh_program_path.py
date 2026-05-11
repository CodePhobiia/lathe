"""Source-authored ``mesh_program{}`` dispatch for the shape stage.

Phase 1 §5.1d wiring: when an asset declares a ``mesh_program {}`` block
in source (parsed by ``lathe.parser`` into
``asset["build"]["shape"]["mesh_program"]``), the shape stage takes
this path instead of the family-blueprint candidate-search path.

The ``mesh_program`` AST is lowered by
:func:`lathe.mesh_program.lower_mesh_program` into a deterministic
``list[ShapePrimitive]`` (with ``boolean_seam_groups`` and the
``v2_polybevel_modifier`` records produced by ``fillet_edge``). That
primitive list is wrapped in a single :class:`~lathe.shape_ir.ShapeIR`
and fed straight to
:func:`lathe.exact_solids.compile_explicit_surface_mesh` — the same
exact-solid + post-boolean-polybevel chain that the hand-written
``examples/bevel_demo.py`` uses to produce the canonical 112v / 172f
beveled cube.

Output is a ``scaffold_result``-shaped dict with one runtime candidate
so the rest of the shape backend (provider mux, conformance fit,
bundle assembly) is unchanged. The stable
``lathe.shape.intent_mesh_handoff_v1`` contract still holds — this
module only changes *where* the ShapeIR comes from.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from ..asset_graph import AssetGraph
from ..exact_solids import compile_explicit_surface_mesh, primitive_mesh
from ..fidelity import infer_fidelity_profile
from ..geometry import resolve_geometry_kernel
from ..mesh_finalize import finalize_mesh_ir
from ..mesh_program import lower_mesh_program
from ..scaffold_compiler import _game_pipeline_hints, _make_color
from ..shape_ir import ShapeIR, ShapeRegion

__all__ = ["compile_mesh_program_candidate", "mesh_program_ast_from_asset"]

_NUMERIC_EPSILON = 1e-6
_FEATURE_COMPONENTS = {
    "edge_treatment",
    "fastener_grid",
    "scatter",
    "trim_band",
    "vent_slats",
}
_PANEL_FEATURE_COMPONENTS = {
    "fastener_grid",
    "trim_band",
    "vent_slats",
}


def mesh_program_ast_from_asset(asset: dict[str, Any]) -> dict[str, Any] | None:
    """Return the parsed ``mesh_program`` AST node if the asset declares one.

    Returns ``None`` when the source has no ``mesh_program {}`` block, or
    when the block is structurally empty (no statements). Empty programs
    fall through to the family-blueprint path so a stray empty block
    cannot accidentally suppress the existing family lowering.
    """
    shape_cfg = asset.get("build", {}).get("shape")
    if not isinstance(shape_cfg, dict):
        return None
    program = shape_cfg.get("mesh_program")
    if not isinstance(program, dict):
        return None
    if program.get("node_type") != "mesh_program":
        return None
    statements = program.get("statements")
    if not isinstance(statements, list) or not statements:
        return None
    return program


def _regions_from_primitives(primitives: list[Any]) -> list[ShapeRegion]:
    regions: list[ShapeRegion] = []
    for index, primitive in enumerate(primitives):
        if primitive.blend_mode == "subtract":
            continue
        center = tuple(primitive.center)
        extents = None
        try:
            bounds = primitive_mesh(primitive).bounds
            center = tuple(float(value) for value in ((bounds[0] + bounds[1]) * 0.5))
            extents = tuple(
                max(float(value), 1e-3)
                for value in (bounds[1] - bounds[0])
            )
        except (AttributeError, TypeError, ValueError, RuntimeError, IndexError):
            extents = primitive.extents
        if extents is None:
            radius = float(primitive.radius or 0.0)
            height = float(primitive.height or 0.0)
            extents = (max(radius * 2, 1e-3), max(height, 1e-3), max(radius * 2, 1e-3))
        regions.append(
            ShapeRegion(
                name=f"{primitive.part}_{index}",
                part=primitive.part,
                component=primitive.part,
                center=center,
                extents=tuple(extents),
                tags=["mesh_program"],
                adjacency=[],
            )
        )
    if not regions and primitives:
        primitive = primitives[0]
        extents = primitive.extents or (1.0, 1.0, 1.0)
        regions.append(
            ShapeRegion(
                name=f"{primitive.part}_0",
                part=primitive.part,
                component=primitive.part,
                center=tuple(primitive.center),
                extents=tuple(extents),
                tags=["mesh_program"],
                adjacency=[],
            )
        )
    return regions


def _ratio_signature(extents: list[float]) -> list[float]:
    largest = max(_NUMERIC_EPSILON, *extents) if extents else _NUMERIC_EPSILON
    return [round(float(value) / largest, 6) for value in extents]


def _profile_bins(values: list[float], span: float) -> list[float]:
    if not values:
        return [0.0, 0.0, 0.0]
    lo = min(values)
    safe_span = max(_NUMERIC_EPSILON, span)
    bins = [0.0, 0.0, 0.0]
    for value in values:
        normalized = (float(value) - lo) / safe_span
        index = max(0, min(2, int(normalized * 3.0)))
        bins[index] += 1.0
    total = max(1.0, sum(bins))
    return [round(item / total, 6) for item in bins]


def _expected_extents(regions: list[ShapeRegion], primitives: list[Any]) -> list[float]:
    mins: list[list[float]] = []
    maxs: list[list[float]] = []
    for region in regions:
        center = [float(value) for value in region.center]
        extents = [float(value) for value in region.extents]
        half = [max(value, _NUMERIC_EPSILON) * 0.5 for value in extents]
        mins.append([center[index] - half[index] for index in range(3)])
        maxs.append([center[index] + half[index] for index in range(3)])
    if not mins:
        for primitive in primitives:
            extents = primitive.extents
            if extents is None:
                radius = float(primitive.radius or 0.0)
                height = float(primitive.height or 0.0)
                extents = (radius * 2.0, height, radius * 2.0)
            center = [float(value) for value in primitive.center]
            half = [max(float(value), _NUMERIC_EPSILON) * 0.5 for value in extents]
            mins.append([center[index] - half[index] for index in range(3)])
            maxs.append([center[index] + half[index] for index in range(3)])
    if not mins:
        return [1.0, 1.0, 1.0]
    return [
        round(max(item[index] for item in maxs) - min(item[index] for item in mins), 6)
        for index in range(3)
    ]


def _operation_history_entries(primitive: Any) -> list[dict[str, Any]]:
    metadata = primitive.semantic_metadata if isinstance(primitive.semantic_metadata, dict) else {}
    entries = metadata.get("mesh_program_operation_history")
    if isinstance(entries, list):
        return [entry for entry in entries if isinstance(entry, dict)]
    v2_metadata = metadata.get("shape_ir_v2")
    if isinstance(v2_metadata, dict):
        entries = v2_metadata.get("mesh_program_operation_history")
        if isinstance(entries, list):
            return [entry for entry in entries if isinstance(entry, dict)]
    return []


def _int_value(value: Any, *, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _mesh_program_feature_summary(
    regions: list[ShapeRegion],
    primitives: list[Any],
    *,
    seam_group_count: int,
    bevel_modifier_count: int,
) -> dict[str, Any]:
    feature_records: dict[str, dict[str, Any]] = {}
    for primitive in primitives:
        for entry in _operation_history_entries(primitive):
            component = str(entry.get("component") or "")
            operation = str(entry.get("operation") or entry.get("mesh_program_op") or "")
            if component not in _FEATURE_COMPONENTS and not operation.startswith("op."):
                continue
            operation_id = str(entry.get("operation_id") or f"{operation}:{component}:{len(feature_records)}")
            feature_records.setdefault(operation_id, entry)

    feature_count = 0
    panel_feature_count = 0
    feature_components: set[str] = set()
    for entry in feature_records.values():
        component = str(entry.get("component") or "")
        operation = str(entry.get("operation") or "")
        count = max(1, _int_value(entry.get("feature_primitive_count"), default=1))
        feature_count += count
        if component:
            feature_components.add(component)
        if component in _PANEL_FEATURE_COMPONENTS or operation in {"op.trim_band", "op.vent_slats"}:
            panel_feature_count += count

    support_feature_count = sum(1 for region in regions if str(region.part).startswith("foot_"))
    attachment_region_count = sum(
        1
        for primitive in primitives
        if primitive.boolean_seam_groups
        or primitive.v2_polybevel_modifier
        or str(primitive.component or "") in _FEATURE_COMPONENTS
    )
    feature_count = max(feature_count, bevel_modifier_count + seam_group_count)
    return {
        "feature_count": feature_count,
        "feature_types": sorted(feature_components),
        "panel_feature_count": panel_feature_count,
        "support_feature_count": support_feature_count,
        "attachment_region_count": attachment_region_count,
        "operation_record_count": len(feature_records),
    }


def _mesh_program_signature(
    asset_graph: AssetGraph,
    regions: list[ShapeRegion],
    primitives: list[Any],
    primitives_used: list[str],
    *,
    statement_count: int,
    seam_group_count: int,
    bevel_modifier_count: int,
) -> dict[str, Any]:
    extents = _expected_extents(regions, primitives)
    largest = max(_NUMERIC_EPSILON, *extents)
    region_x = [float(region.center[0]) / largest for region in regions]
    region_y = [float(region.center[1]) / largest for region in regions]
    region_z = [float(region.center[2]) / largest for region in regions]
    part_targets = {
        region.name: {
            "part": region.part,
            "center": [round(float(value), 6) for value in region.center],
            "extents": [round(float(value), 6) for value in region.extents],
            "component": region.component,
        }
        for region in regions
    }
    adjacency_pairs = []
    for pair in asset_graph.part_graph:
        if not isinstance(pair, dict):
            continue
        left = pair.get("from")
        right = pair.get("to")
        if not left or not right:
            continue
        adjacency_pairs.append(
            {
                "from": str(left),
                "to": str(right),
                "source": "mesh_program_authored_adjacency",
                "measurement": "source_operation_and_part_presence",
            }
        )
    return {
        "shape_source": "mesh_program",
        "statement_count": statement_count,
        "primitive_count": len(primitives),
        "boolean_seam_group_count": seam_group_count,
        "polybevel_modifier_count": bevel_modifier_count,
        "expected_extents": extents,
        "projected_ratio": _ratio_signature(extents),
        "minimum_triangle_density": round(
            min(0.88, 0.42 + 0.05 * len(primitives_used) + 0.03 * len(regions)),
            6,
        ),
        "expected_part_names": [part.name for part in asset_graph.parts],
        "asset_kind": asset_graph.kind,
        "asset_class": str(asset_graph.authoring.get("asset_class") or ""),
        "part_targets": part_targets,
        "adjacency_pairs": adjacency_pairs,
        "region_spread": [
            round(max(region_x) - min(region_x), 6) if region_x else 0.0,
            round(max(region_y) - min(region_y), 6) if region_y else 0.0,
            round(max(region_z) - min(region_z), 6) if region_z else 0.0,
        ],
        "vertical_profile": _profile_bins(
            region_y,
            max(_NUMERIC_EPSILON, max(region_y) - min(region_y) if region_y else 1.0),
        ),
        "depth_profile": _profile_bins(
            region_z,
            max(_NUMERIC_EPSILON, max(region_z) - min(region_z) if region_z else 1.0),
        ),
        "width_profile": _profile_bins(
            region_x,
            max(_NUMERIC_EPSILON, max(region_x) - min(region_x) if region_x else 1.0),
        ),
        "expected_region_count": len(regions),
        "fragmentation_ceiling": max(4, len(regions) * 3),
        "primitives_used": list(primitives_used),
        "blueprint_notes": ["shape sourced from authored mesh_program{} block"],
    }


def _mesh_program_assessment(
    asset_graph: AssetGraph,
    regions: list[ShapeRegion],
    primitives: list[Any],
    *,
    seam_group_count: int,
    bevel_modifier_count: int,
) -> dict[str, Any]:
    expected_parts = {part.name for part in asset_graph.parts}
    realized_parts = {region.part for region in regions}
    feature_summary = _mesh_program_feature_summary(
        regions,
        primitives,
        seam_group_count=seam_group_count,
        bevel_modifier_count=bevel_modifier_count,
    )
    expected_count = max(1, len(expected_parts))
    feature_count = int(feature_summary["feature_count"])
    attachment_region_count = int(feature_summary["attachment_region_count"])
    feature_density = round(min(1.0, feature_count / max(1.0, expected_count * 2.0)), 6)
    feature_coherence = round(
        min(
            1.0,
            (0.45 * feature_density)
            + (0.25 * min(1.0, len(feature_summary["feature_types"]) / max(1.0, expected_count)))
            + (0.30 * min(1.0, attachment_region_count / max(1.0, expected_count / 2.0))),
        ),
        6,
    )
    silhouette_complexity = round(
        min(
            1.0,
            (len(realized_parts) * 0.04)
            + (feature_count * 0.012)
            + (attachment_region_count * 0.025),
        ),
        6,
    )
    return {
        "shape_source": "mesh_program",
        "primitive_count": len(primitives),
        "region_count": len(regions),
        "primitive_diversity": round(
            len({primitive.component or primitive.primitive_type for primitive in primitives})
            / max(1, len(primitives)),
            6,
        ),
        "boolean_seam_group_count": seam_group_count,
        "polybevel_modifier_count": bevel_modifier_count,
        "richness_floor": round(
            min(1.0, (len(primitives) + feature_count) / max(4.0, expected_count * 2.4)),
            6,
        ),
        "feature_count": feature_count,
        "feature_types": feature_summary["feature_types"],
        "feature_density": feature_density,
        "edge_treatment_count": max(bevel_modifier_count, seam_group_count),
        "panel_feature_count": int(feature_summary["panel_feature_count"]),
        "support_feature_count": int(feature_summary["support_feature_count"]),
        "attachment_region_count": attachment_region_count,
        "silhouette_complexity": silhouette_complexity,
        "feature_coherence": feature_coherence,
        "mesh_program_operation_record_count": int(feature_summary["operation_record_count"]),
        "required_part_coverage": round(
            len(expected_parts & realized_parts) / max(1, len(expected_parts)),
            6,
        ),
    }


def compile_mesh_program_candidate(
    asset_graph: AssetGraph,
    program: dict[str, Any],
    *,
    mode: str,
    conditioning: dict[str, Any],
    runtime_config: dict[str, Any] | None = None,
    work_dir: Path | None = None,
) -> dict[str, Any]:
    """Lower the ``mesh_program{}`` AST and assemble a scaffold-shaped result.

    The returned dict matches the shape of
    :func:`lathe.scaffold_compiler.compile_scaffold_candidates` so
    :func:`lathe.conformance.fit_provider_proposals` and the rest of
    :func:`lathe.shape.backend.run_shape_backend` consume it unchanged.
    """
    trace_path: Path | None = None
    latest_trace_path: Path | None = None
    if work_dir is not None:
        work_dir.mkdir(parents=True, exist_ok=True)
        trace_path = work_dir / "mesh_program_progress.jsonl"
        latest_trace_path = work_dir / "mesh_program_progress_latest.json"
        trace_path.write_text("", encoding="utf-8")

    def _trace(event: dict[str, Any]) -> None:
        if trace_path is None:
            return
        payload = {
            "time": time.time(),
            "asset": asset_graph.name,
            **event,
        }
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
            "statement_count": len(program.get("statements") or []),
        }
    )
    target_part = "body"
    if asset_graph.parts:
        target_part = asset_graph.parts[0].name
    _trace({"event": "lower_call_start", "target_part": target_part})
    primitives = lower_mesh_program(program, part=target_part, progress=_trace)
    _trace({"event": "lower_call_end", "primitive_count": len(primitives)})
    primitives_used = sorted({primitive.primitive_type for primitive in primitives})
    seam_group_count = sum(len(primitive.boolean_seam_groups) for primitive in primitives)
    bevel_modifier_count = sum(
        1 for primitive in primitives if primitive.v2_polybevel_modifier
    )
    statements = list(program.get("statements", []))
    _trace({"event": "regions_start", "primitive_count": len(primitives)})
    regions = _regions_from_primitives(primitives)
    _trace({"event": "regions_end", "region_count": len(regions)})
    signature = _mesh_program_signature(
        asset_graph,
        regions,
        primitives,
        primitives_used,
        statement_count=len(statements),
        seam_group_count=seam_group_count,
        bevel_modifier_count=bevel_modifier_count,
    )
    assessment = _mesh_program_assessment(
        asset_graph,
        regions,
        primitives,
        seam_group_count=seam_group_count,
        bevel_modifier_count=bevel_modifier_count,
    )
    shape_ir = ShapeIR(
        asset_name=asset_graph.name,
        family=asset_graph.family,
        blueprint_id="mesh_program_v1",
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
    geometry_kernel = resolve_geometry_kernel(runtime_config)
    geometry_kernel_id = getattr(geometry_kernel, "name", None)
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
        "mode": "mesh_program_explicit_surface",
        "shape_source": "mesh_program",
        "primitive_count": len(primitives),
        "boolean_seam_group_count": seam_group_count,
        "polybevel_modifier_count": bevel_modifier_count,
        "exact_report": exact_report,
    }
    _trace({"event": "finalize_mesh_ir_start", "face_count": len(mesh.faces)})
    mesh_ir_payload = finalize_mesh_ir(
        mesh,
        shape_ir,
        list(face_parts),
        metadata={"integration_report": integration_report},
    ).to_dict()
    _trace({"event": "finalize_mesh_ir_end"})
    selection_notes = [
        "shape sourced from authored mesh_program{} block",
        f"statement_count={len(statements)}",
        f"primitives_used={','.join(primitives_used)}",
        f"boolean_seam_group_count={seam_group_count}",
        f"polybevel_modifier_count={bevel_modifier_count}",
        f"fidelity={fidelity.tier}",
    ]
    candidate_score = 0.86 if bevel_modifier_count else 0.78
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
                "shape_source": "mesh_program",
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
                "shape_source": "mesh_program",
                "feature_ops_used": ["fillet_edge"] if bevel_modifier_count else [],
                "shape_assessment": dict(shape_ir.assessment),
                "game_pipeline_hints": game_pipeline_hints,
            },
            "candidate_params": {"shape_source": "mesh_program"},
            "game_pipeline_hints": game_pipeline_hints,
            "integration_report": integration_report,
            "mesh_ir": mesh_ir_payload,
        },
    }

    _trace({"event": "compile_end"})
    return {
        "asset_graph": asset_graph,
        "shape_irs": [shape_ir],
        "runtime_candidates": [runtime_candidate],
        "report": {
            "family": asset_graph.family,
            "generator": "mesh_program_authored",
            "shape_source": "mesh_program",
            "asset_graph": asset_graph.to_dict(),
            "shape_irs": [shape_ir.to_dict()],
            "blueprints": [],
            "feature_reports": [runtime_candidate["meta"]["feature_report"]],
            "candidate_search": [{"shape_source": "mesh_program"}],
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
            "authoritative_candidate_reason": "authored_mesh_program",
            "geometry_kernel": exact_report.get("boolean_kernel") or geometry_kernel_id,
            "game_pipeline_hints": game_pipeline_hints,
        },
    }
