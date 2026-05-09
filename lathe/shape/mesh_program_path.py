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


def compile_mesh_program_candidate(
    asset_graph: AssetGraph,
    program: dict[str, Any],
    *,
    mode: str,
    conditioning: dict[str, Any],
    runtime_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Lower the ``mesh_program{}`` AST and assemble a scaffold-shaped result.

    The returned dict matches the shape of
    :func:`lathe.scaffold_compiler.compile_scaffold_candidates` so
    :func:`lathe.conformance.fit_provider_proposals` and the rest of
    :func:`lathe.shape.backend.run_shape_backend` consume it unchanged.
    """
    target_part = "body"
    if asset_graph.parts:
        target_part = asset_graph.parts[0].name
    primitives = lower_mesh_program(program, part=target_part)
    primitives_used = sorted({primitive.primitive_type for primitive in primitives})
    seam_group_count = sum(len(primitive.boolean_seam_groups) for primitive in primitives)
    bevel_modifier_count = sum(
        1 for primitive in primitives if primitive.v2_polybevel_modifier
    )
    statements = list(program.get("statements", []))
    regions = _regions_from_primitives(primitives)
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
        signature={
            "shape_source": "mesh_program",
            "statement_count": len(statements),
            "primitive_count": len(primitives),
            "boolean_seam_group_count": seam_group_count,
            "polybevel_modifier_count": bevel_modifier_count,
        },
        assessment={
            "shape_source": "mesh_program",
            "primitive_count": len(primitives),
            "boolean_seam_group_count": seam_group_count,
            "polybevel_modifier_count": bevel_modifier_count,
            "feature_density": 0.6 if bevel_modifier_count else 0.4,
            "feature_coherence": 0.7 if bevel_modifier_count else 0.5,
            "edge_treatment_count": bevel_modifier_count,
            "required_part_coverage": 1.0,
        },
    )

    fidelity = infer_fidelity_profile(asset_graph)
    geometry_kernel = resolve_geometry_kernel(runtime_config)
    geometry_kernel_id = getattr(geometry_kernel, "name", None)
    mesh, face_parts, exact_report = compile_explicit_surface_mesh(
        shape_ir,
        fidelity,
        combine_mode="kernel_program",
        geometry_kernel=geometry_kernel,
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
    mesh_ir_payload = finalize_mesh_ir(
        mesh,
        shape_ir,
        list(face_parts),
        metadata={"integration_report": integration_report},
    ).to_dict()
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
