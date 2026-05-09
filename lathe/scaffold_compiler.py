"""Scaffold compiler for the shape stage.

Lowers an assembly blueprint into parameterized scaffold primitives
that feed feature fusion and the authoritative mesh.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import replace
from typing import Any

import numpy as np
import trimesh

from .assembly_kernel import compile_assembly_blueprint
from .asset_graph import AssetGraph
from .blueprints import resolve_blueprint
from .candidate_search import (
    apply_candidate_params,
    apply_quality_adapters_to_candidate_params,
    apply_style_modifiers_to_candidate_params,
    generate_candidate_params,
    objective_weights,
)
from .constants import RNG_PRIME_OFFSET
from .errors import ContractViolation
from .exact_solids import primitive_mesh as _exact_primitive_mesh
from .feature_grammar import compile_feature_enhancements
from .fidelity import infer_fidelity_profile
from .geometry import resolve_geometry_kernel
from .geometry.shape_ir_program import execute_shape_ir_boolean_program
from .geometry_detail import geometry_detail_controls_from_authoring
from .geometry_kernel import fuse_shape_ir
from .mesh_finalize import finalize_mesh_ir
from .repair_executor import execute_shape_repairs
from .repair_planner import plan_shape_repairs
from .shape_ir import ShapeIR, ShapePrimitive
from .shape_program_driver import compile_grammar_program_candidate
from .style_presets import DEFAULT_PRESET, STYLE_PRESETS


def _construction_grammar_axis(asset_graph: AssetGraph) -> str:
    """Read ``construction_grammar`` axis from the materialized style stack.

    Roadmap §6.8 dispatch: scaffold_compiler reads only this axis. Falls
    back to the default preset when the asset declared no style stack
    (preserves existing free-form behavior for legacy examples).
    """
    stack = asset_graph.authoring.get("style_stack")
    if isinstance(stack, dict):
        value = stack.get("construction_grammar")
        if value:
            return str(value)
    return STYLE_PRESETS[DEFAULT_PRESET]["construction_grammar"]


def _apply_construction_grammar_routing(
    asset_graph: AssetGraph, conditioning: dict[str, Any]
) -> dict[str, Any]:
    """Augment ``conditioning`` with routing flags from ``construction_grammar``.

    * ``free_form`` — no-op, default behavior.
    * ``snap_grid`` — quantize candidate primitive positions to a grid.
    * ``brick_snap`` — route to a brick-style kit (modular brick units).
    * ``modular_kit`` — require an explicit ``assembly.kit`` reference.

    The routing payload is read by downstream candidate-search /
    blueprint-resolution code. Conditioning is copied so we never
    mutate caller state.
    """
    out = dict(conditioning or {})
    grammar = _construction_grammar_axis(asset_graph)
    out["construction_grammar"] = grammar
    if grammar == "snap_grid":
        out["scaffold_position_quantization"] = "grid"
    elif grammar == "brick_snap":
        out["scaffold_position_quantization"] = "brick"
        out["scaffold_kit_hint"] = "brick"
    elif grammar == "modular_kit":
        out["scaffold_position_quantization"] = "kit"
        out["scaffold_requires_kit"] = True
    return out


def _make_color(name: str) -> tuple[int, int, int]:
    digest = hashlib.sha256(name.encode("utf-8")).digest()
    return (80 + digest[0] % 140, 80 + digest[1] % 140, 80 + digest[2] % 140)


def _candidate_rng(seed: int, index: int) -> np.random.Generator:
    return np.random.default_rng(seed + index * RNG_PRIME_OFFSET)


def _translated_box(
    extents: tuple[float, float, float], center: tuple[float, float, float]
) -> trimesh.Trimesh:
    matrix = np.eye(4)
    matrix[:3, 3] = np.array(list(center), dtype=float)
    return trimesh.creation.box(extents=np.array(list(extents), dtype=float), transform=matrix)


def _translated_cylinder(
    radius: float, height: float, center: tuple[float, float, float], axis: str
) -> trimesh.Trimesh:
    mesh = trimesh.creation.cylinder(radius=radius, height=height, sections=40)
    if axis == "y":
        mesh.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2.0, [1.0, 0.0, 0.0]))
    elif axis == "x":
        mesh.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2.0, [0.0, 1.0, 0.0]))
    matrix = np.eye(4)
    matrix[:3, 3] = np.array(list(center), dtype=float)
    mesh.apply_transform(matrix)
    return mesh


def _missing_box_extents_error(primitive: ShapePrimitive) -> ContractViolation:
    return ContractViolation(
        f"invariant violation: box ShapePrimitive requires extents, got None (part={primitive.part!r})"
    )


def _missing_cylinder_dimensions_error(primitive: ShapePrimitive) -> ContractViolation:
    return ContractViolation(
        "invariant violation: cylinder ShapePrimitive requires radius and height, "
        f"got radius={primitive.radius!r}, height={primitive.height!r} "
        f"(part={primitive.part!r})"
    )


def _unsupported_primitive_type_error(primitive_type: str) -> ValueError:
    return ValueError(f"Unsupported primitive type '{primitive_type}'")


def _primitive_mesh(primitive: ShapePrimitive) -> trimesh.Trimesh:
    if primitive.primitive_type == "box":
        if primitive.extents is None:
            raise _missing_box_extents_error(primitive)
        return _translated_box(primitive.extents, primitive.center)
    if primitive.primitive_type == "cylinder":
        if primitive.radius is None or primitive.height is None:
            raise _missing_cylinder_dimensions_error(primitive)
        return _translated_cylinder(primitive.radius, primitive.height, primitive.center, primitive.axis)
    if primitive.primitive_type in {
        "sphere",
        "revolved_profile",
        "extruded_profile",
        "torus",
        "subdivision_box",
        "swept_profile",
        "lofted_solid",
        "heightfield",
        "sdf_mesh",
    }:
        return _exact_primitive_mesh(primitive)
    raise _unsupported_primitive_type_error(primitive.primitive_type)


def _is_additive_grammar_detail_primitive(primitive: ShapePrimitive) -> bool:
    tags = {str(tag) for tag in primitive.tags}
    return "grammar_program" in tags and (primitive.blend_mode or "union") == "union"


def _kernel_program_detail_concat_partition(
    shape_ir: ShapeIR,
) -> tuple[list[ShapePrimitive], list[tuple[int, ShapePrimitive]]] | None:
    signature = shape_ir.signature if isinstance(shape_ir.signature, dict) else {}
    grammar_execution = signature.get("grammar_program_execution")
    augmentation = grammar_execution.get("augmentation") if isinstance(grammar_execution, dict) else {}
    if not (isinstance(augmentation, dict) and bool(augmentation.get("enabled"))):
        return None
    core_primitives: list[ShapePrimitive] = []
    detail_primitives: list[tuple[int, ShapePrimitive]] = []
    for index, primitive in enumerate(shape_ir.primitives):
        if _is_additive_grammar_detail_primitive(primitive):
            detail_primitives.append((index, primitive))
        else:
            core_primitives.append(primitive)
    if not core_primitives or not detail_primitives:
        return None
    return core_primitives, detail_primitives


def _shape_ir_with_primitives(shape_ir: ShapeIR, primitives: list[ShapePrimitive], *, blueprint_suffix: str) -> ShapeIR:
    parts = {primitive.part for primitive in primitives}
    regions = [region for region in shape_ir.regions if region.part in parts]
    signature = dict(shape_ir.signature) if isinstance(shape_ir.signature, dict) else {}
    signature["kernel_program_subset"] = {
        "source_blueprint_id": shape_ir.blueprint_id,
        "source_primitive_count": len(shape_ir.primitives),
        "subset_primitive_count": len(primitives),
        "subset": blueprint_suffix,
    }
    return replace(
        shape_ir,
        blueprint_id=f"{shape_ir.blueprint_id}:{blueprint_suffix}",
        primitives=list(primitives),
        regions=regions,
        primitives_used=sorted({primitive.primitive_type for primitive in primitives}),
        signature=signature,
    )


def _visible_detail_concat_meshes(
    detail_primitives: list[tuple[int, ShapePrimitive]],
) -> tuple[list[trimesh.Trimesh], list[dict[str, Any]]]:
    meshes: list[trimesh.Trimesh] = []
    records: list[dict[str, Any]] = []
    for original_index, primitive in detail_primitives:
        mesh = _primitive_mesh(primitive)
        mesh.remove_infinite_values()
        mesh.remove_unreferenced_vertices()
        mesh.fix_normals()
        meshes.append(mesh)
        records.append(
            {
                "source_index": int(original_index),
                "part": primitive.part,
                "primitive_type": primitive.primitive_type,
                "operation_id": _primitive_operation_id(primitive, original_index),
                "face_count": len(mesh.faces),
                "body_count": len(mesh.split(only_watertight=False)) if len(mesh.faces) > 0 else 0,
                "watertight": bool(mesh.is_watertight),
                "tags": [str(tag) for tag in primitive.tags],
            }
        )
    return meshes, records


def _combined_kernel_program_semantic_handoff(
    *,
    shape_ir: ShapeIR,
    core_details: dict[str, Any],
    detail_records: list[dict[str, Any]],
    combined: trimesh.Trimesh,
) -> dict[str, Any]:
    parts = sorted({primitive.part for primitive in shape_ir.primitives if primitive.part})
    primitive_types = sorted({primitive.primitive_type for primitive in shape_ir.primitives if primitive.primitive_type})
    return {
        "schema": "lathe.geometry.kernel_program_semantic_handoff.v1",
        "source": "scaffold.kernel_program_core_plus_visible_detail_concat",
        "operand_count": len(shape_ir.primitives),
        "source_part_count": len(parts),
        "source_parts": parts,
        "source_primitive_types": primitive_types,
        "result_face_count": len(combined.faces),
        "result_body_count": len(combined.split(only_watertight=False)) if len(combined.faces) > 0 else 0,
        "core_kernel_program": core_details.get("kernel_program_semantic_handoff"),
        "visible_detail_concat_records": detail_records,
        "visible_detail_concat_record_count": len(detail_records),
    }


def _fuse_via_kernel_program_core_plus_visible_details(
    shape_ir: ShapeIR,
    kernel: Any,
) -> tuple[trimesh.Trimesh | None, list[str], dict[str, Any]] | None:
    partition = _kernel_program_detail_concat_partition(shape_ir)
    if partition is None:
        return None
    core_primitives, detail_primitives = partition
    core_shape_ir = _shape_ir_with_primitives(
        shape_ir,
        core_primitives,
        blueprint_suffix="kernel_program_core",
    )
    try:
        core_result = execute_shape_ir_boolean_program(
            kernel,
            core_shape_ir,
            route="scaffold_shape_ir_core_kernel_program",
            backend=getattr(kernel, "name", None),
        )
        detail_meshes, detail_records = _visible_detail_concat_meshes(detail_primitives)
    except (ValueError, RuntimeError, AttributeError, IndexError, OSError, ImportError, TypeError) as exc:
        return (
            None,
            [],
            {
                "mode": "kernel_program_csg",
                "search_mode": "kernel_program_csg",
                "geometry_kernel": getattr(kernel, "name", None),
                "kernel_program_attempted": True,
                "kernel_program_succeeded": False,
                "kernel_program_detail_concat_attempted": True,
                "kernel_program_failure_type": type(exc).__name__,
                "kernel_program_failure_reason": str(exc),
                "shape_ir_primitive_count": len(shape_ir.primitives),
                "kernel_program_core_primitive_count": len(core_primitives),
                "kernel_program_visible_detail_primitive_count": len(detail_primitives),
            },
        )

    meshes = [core_result.mesh, *detail_meshes]
    combined = trimesh.util.concatenate(meshes) if len(meshes) > 1 else core_result.mesh.copy()
    combined.remove_infinite_values()
    combined.remove_unreferenced_vertices()
    combined.fix_normals()
    primitive_indices = _assign_face_primitive_indices_via_bounds(
        combined,
        shape_ir,
        include_boolean_operands=True,
    )
    face_parts = _face_parts_from_primitive_indices(shape_ir, primitive_indices)
    face_operation_ids = _face_operation_ids_from_primitive_indices(shape_ir, primitive_indices)
    face_operation_report = (
        _face_operation_report(
            face_operation_ids,
            source="scaffold_kernel_program.core_csg_plus_visible_detail_concat",
            mode="core_kernel_program_plus_visible_detail_bounds",
            cut_operation_ids=_cut_operation_ids_from_primitive_indices(shape_ir, primitive_indices),
            compound_operations=_compound_operation_reports(shape_ir),
        )
        if len(face_operation_ids) == len(combined.faces)
        else {}
    )
    semantic_handoff = _combined_kernel_program_semantic_handoff(
        shape_ir=shape_ir,
        core_details=core_result.details,
        detail_records=detail_records,
        combined=combined,
    )
    combined.metadata["lathe_kernel_program_semantic_handoff"] = semantic_handoff
    return combined, face_parts, {
        "kernel_program_succeeded": True,
        "kernel_program_detail_concat_succeeded": True,
        "kernel_program_detail_concat_method": "core_kernel_program_plus_visible_detail_mesh_concatenation",
        "kernel_program_route": "scaffold_shape_ir_core_plus_visible_detail_concat",
        "kernel_program_kernel": getattr(kernel, "name", None),
        "kernel_program_operation_count": int(core_result.details.get("kernel_program_operation_count", 0) or 0),
        "kernel_program_kernel_call_count": int(core_result.details.get("kernel_program_kernel_call_count", 0) or 0),
        "kernel_program_operand_count": len(shape_ir.primitives),
        "kernel_program_core_primitive_count": len(core_primitives),
        "kernel_program_visible_detail_primitive_count": len(detail_primitives),
        "kernel_program_visible_detail_face_count": sum(int(record.get("face_count", 0) or 0) for record in detail_records),
        "kernel_program_visible_detail_records": detail_records,
        "kernel_program_core": core_result.details,
        "kernel_program_semantic_handoff": semantic_handoff,
        **face_operation_report,
    }


def _fuse_via_kernel_program(
    shape_ir: ShapeIR,
    kernel: Any,
) -> tuple[trimesh.Trimesh | None, list[str], dict[str, Any]]:
    """Fuse a ShapeIR via the executable kernel-program path.

    Face parts are assigned from KernelProgram operand face spans when the
    backend emitted a pure batch-union trace; destructive programs fall back
    to a centroid-vs-bounds heuristic that includes cutter operands only after
    a kernel boolean has actually succeeded. Failure details are returned
    instead of swallowed so the attempted-vs-actual trace stays honest.
    """
    visible_detail_result = _fuse_via_kernel_program_core_plus_visible_details(shape_ir, kernel)
    if visible_detail_result is not None and visible_detail_result[0] is not None:
        return visible_detail_result

    try:
        result = execute_shape_ir_boolean_program(
            kernel,
            shape_ir,
            route="scaffold_shape_ir_kernel_program",
            backend=getattr(kernel, "name", None),
        )
    except (ValueError, RuntimeError, AttributeError, IndexError, OSError, ImportError, TypeError) as exc:
        failure_details = getattr(exc, "details", None)
        structured_details = dict(failure_details) if isinstance(failure_details, dict) else {}
        diagnostics = []
        if structured_details:
            diagnostics.append(
                {
                    "code": structured_details.get("code", "kernel_program_failed"),
                    "severity": "error",
                    "details": structured_details,
                }
            )
        return (
            None,
            [],
            {
                "mode": "kernel_program_csg",
                "search_mode": "kernel_program_csg",
                "geometry_kernel": getattr(kernel, "name", None),
                "kernel_program_attempted": True,
                "kernel_program_succeeded": False,
                "kernel_program_failure_type": type(exc).__name__,
                "kernel_program_failure_reason": str(exc),
                "shape_ir_primitive_count": len(shape_ir.primitives),
                **(
                    {
                        "kernel_program_failure_details": structured_details,
                        "kernel_program_diagnostics": diagnostics,
                    }
                    if structured_details
                    else {}
                ),
            },
        )

    mesh = result.mesh
    if len(mesh.faces) == 0:
        return (
            None,
            [],
            {
                "mode": "kernel_program_csg",
                "search_mode": "kernel_program_csg",
                "geometry_kernel": getattr(kernel, "name", None),
                "kernel_program_attempted": True,
                "kernel_program_succeeded": False,
                "kernel_program_failure_type": "EmptyMesh",
                "kernel_program_failure_reason": "kernel program produced an empty mesh",
                "shape_ir_primitive_count": len(shape_ir.primitives),
                **result.details,
            },
        )

    direct_attribution = _face_attribution_from_kernel_program(mesh, shape_ir, result.details)
    if direct_attribution is not None:
        face_parts, face_operation_ids, attribution_source = direct_attribution
        primitive_indices: list[int] = []
    else:
        primitive_indices = _assign_face_primitive_indices_via_bounds(
            mesh,
            shape_ir,
            include_boolean_operands=True,
        )
        face_parts = _face_parts_from_primitive_indices(shape_ir, primitive_indices)
        face_operation_ids = _face_operation_ids_from_primitive_indices(shape_ir, primitive_indices)
        attribution_source = "scaffold_kernel_program.primitive_bounds_with_boolean_operands"
    face_operation_report = (
        _face_operation_report(
            face_operation_ids,
            source=attribution_source,
            mode=(
                "primitive_bounds_with_boolean_operands"
                if primitive_indices
                else "batch_union_operand_spans"
            ),
            cut_operation_ids=_cut_operation_ids_from_primitive_indices(shape_ir, primitive_indices),
            compound_operations=_compound_operation_reports(shape_ir),
        )
        if len(face_operation_ids) == len(mesh.faces)
        else {}
    )
    return mesh, face_parts, {
        "kernel_program_succeeded": True,
        **result.details,
        **face_operation_report,
    }


def _needs_kernel_program_rescue(
    fused_mesh_ir: Any | None,
    integration_report: dict[str, Any] | None,
) -> bool:
    if fused_mesh_ir is None:
        return True
    report = integration_report if isinstance(integration_report, dict) else {}
    mode = str(report.get("mode") or "")
    fallback = str(report.get("boolean_fallback") or "")
    fallback_reason = str(report.get("boolean_fallback_reason") or "")
    cutter_count = int(report.get("subtract_primitive_count", 0) or 0) + int(
        report.get("intersect_primitive_count", 0) or 0
    )
    return cutter_count > 0 and (
        "fallback" in mode
        or bool(fallback)
        or "fallback" in fallback_reason
        or "omitted" in fallback_reason
    )


def _primitive_has_semantic_operation(primitive: ShapePrimitive) -> bool:
    semantic_metadata = _metadata_dict(getattr(primitive, "semantic_metadata", None))
    v2_metadata = _metadata_dict(semantic_metadata.get("shape_ir_v2"))
    repair_metadata = _metadata_dict(semantic_metadata.get("semantic_repair"))
    if any(
        (
            v2_metadata.get("v2_op"),
            v2_metadata.get("operation_id"),
            repair_metadata.get("lowered_operation"),
            repair_metadata.get("operation_id"),
            semantic_metadata.get("operation"),
            semantic_metadata.get("operation_id"),
        )
    ):
        return True
    if any(str(key).startswith("v2_") for key in semantic_metadata) or any(
        str(key).startswith("v2_") for key in v2_metadata
    ):
        return True
    if _compound_modifier_payloads(primitive):
        return True
    return any(
        (
            primitive.v2_subdivision_modifier,
            primitive.v2_remesh_modifier,
            primitive.v2_polybevel_modifier,
            primitive.v2_mark_hard_edge_modifier,
            primitive.v2_weighted_normals_modifier,
            primitive.v2_hull_modifier,
            primitive.v2_minkowski_modifier,
            int(primitive.subdivision_levels or 0) > 0,
            primitive.remesh_target_edge_length_cm is not None,
        )
    )


def _shape_ir_has_semantic_operations(shape_ir: ShapeIR) -> bool:
    return any(_primitive_has_semantic_operation(primitive) for primitive in shape_ir.primitives)


def _kernel_capabilities(kernel: Any) -> dict[str, bool]:
    try:
        probe = kernel.probe()
    except (AttributeError, TypeError, ValueError, RuntimeError):
        return {}
    capabilities = probe.get("capabilities") if isinstance(probe, dict) else {}
    if not isinstance(capabilities, dict):
        return {}
    return {
        str(name): bool(value)
        for name, value in capabilities.items()
        if isinstance(name, str)
    }


def _kernel_supports_primary_semantic_program(kernel: Any) -> bool:
    capabilities = _kernel_capabilities(kernel)
    return capabilities.get("watertight_by_construction") is True or capabilities.get("batch_union") is True


def _shape_ir_is_additive_only(shape_ir: ShapeIR) -> bool:
    return all((primitive.blend_mode or "union") == "union" for primitive in shape_ir.primitives)


def _kernel_supports_additive_semantic_program(shape_ir: ShapeIR, kernel: Any) -> bool:
    capabilities = _kernel_capabilities(kernel)
    union_count = sum(1 for primitive in shape_ir.primitives if (primitive.blend_mode or "union") == "union")
    if union_count <= 1:
        return capabilities.get("from_trimesh") is True or any(
            capabilities.get(primitive.primitive_type) is True
            for primitive in shape_ir.primitives
        )
    return capabilities.get("union") is True or capabilities.get("batch_union") is True


def _kernel_program_preference_reason(shape_ir: ShapeIR, kernel: Any | None) -> str:
    """Return why the executable kernel path should run before legacy fusion.

    The northstar path is to move CSG execution into explicit geometry
    backends. Route authored cutters/intersections through KernelProgram
    first, and also route operation-rich additive programs when the
    selected kernel advertises a watertight/batched path.
    """
    for primitive in shape_ir.primitives:
        mode = primitive.blend_mode or "union"
        if mode in {"subtract", "intersect"}:
            return "boolean_cutter_or_intersection"
    if kernel is not None and _shape_ir_has_semantic_operations(shape_ir):
        if _kernel_supports_primary_semantic_program(kernel):
            return "semantic_operations_with_capable_kernel"
        if _shape_ir_is_additive_only(shape_ir) and _kernel_supports_additive_semantic_program(shape_ir, kernel):
            return "additive_semantic_operations_explicit_kernel"
    return ""


def _kernel_program_integration_report(
    *,
    shape_ir: ShapeIR,
    mesh: trimesh.Trimesh,
    geometry_kernel_id: str | None,
    kernel_program_details: dict[str, Any],
    primary: bool,
    attempted_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "mode": "kernel_program_csg",
        "search_mode": "kernel_program_csg",
        "geometry_kernel": geometry_kernel_id,
        "body_count": len(mesh.split(only_watertight=False)) if len(mesh.faces) > 0 else 0,
        "watertight": bool(mesh.is_watertight),
        "primitive_count": len(list(shape_ir.primitives)),
        "kernel_program_primary": bool(primary),
        **kernel_program_details,
    }
    if attempted_report is not None:
        report["attempted"] = attempted_report
    return report


def _metadata_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _operation_id_fragment(value: str) -> str:
    return "".join(char if char.isalnum() else "_" for char in value).strip("_") or "operation"


def _primitive_operation_id(primitive: ShapePrimitive, index: int) -> str:
    semantic_metadata = _metadata_dict(getattr(primitive, "semantic_metadata", None))
    v2_metadata = _metadata_dict(semantic_metadata.get("shape_ir_v2"))
    repair_metadata = _metadata_dict(semantic_metadata.get("semantic_repair"))
    operation_id = (
        v2_metadata.get("operation_id")
        or repair_metadata.get("operation_id")
        or semantic_metadata.get("operation_id")
    )
    if operation_id:
        return str(operation_id)
    for modifier_name in (
        "v2_polybevel_modifier",
        "v2_mark_hard_edge_modifier",
        "v2_weighted_normals_modifier",
        "v2_hull_modifier",
        "v2_minkowski_modifier",
        "v2_subdivision_modifier",
        "v2_remesh_modifier",
    ):
        modifier_metadata = _metadata_dict(getattr(primitive, modifier_name, None))
        if modifier_metadata.get("operation_id"):
            return str(modifier_metadata["operation_id"])
    if "feature" in [str(tag) for tag in primitive.tags]:
        feature_kind = str(primitive.component or primitive.primitive_type or "feature")
        return f"feature.{_operation_id_fragment(feature_kind)}"
    operation = (
        v2_metadata.get("v2_op")
        or repair_metadata.get("lowered_operation")
        or semantic_metadata.get("operation")
        or getattr(primitive, "primitive_type", "")
    )
    return f"primitive:{index:04d}:{_operation_id_fragment(str(operation))}"


_COMPOUND_MODIFIER_COUNT_KEYS = (
    "hole_count",
    "fastener_count",
    "slat_count",
    "rib_count",
    "cross_rib_count",
    "branch_count",
    "root_count",
    "blob_count",
    "placement_count",
    "module_record_count",
    "window_cell_count",
    "source_record_count",
    "source_record_expansion_count",
    "instance_transform_count",
    "count",
    "final_count",
    "instance_count",
)


def _compound_modifier_containers(primitive: ShapePrimitive) -> list[dict[str, Any]]:
    metadata = _metadata_dict(getattr(primitive, "semantic_metadata", None))
    containers = [metadata]
    for value in (
        metadata.get("shape_ir_v2"),
        metadata.get("source_shape_primitive"),
    ):
        nested = _metadata_dict(value)
        if nested:
            containers.append(nested)
            nested_semantic = _metadata_dict(nested.get("semantic_metadata"))
            if nested_semantic:
                containers.append(nested_semantic)
                nested_v2 = _metadata_dict(nested_semantic.get("shape_ir_v2"))
                if nested_v2:
                    containers.append(nested_v2)
    return containers


def _compound_modifier_payloads(primitive: ShapePrimitive) -> list[tuple[str, dict[str, Any]]]:
    payloads: list[tuple[str, dict[str, Any]]] = []
    seen: set[tuple[str, str, str]] = set()
    for container in _compound_modifier_containers(primitive):
        for name, value in container.items():
            if not (
                isinstance(name, str)
                and name.startswith("v2_")
                and name.endswith("_modifier")
                and isinstance(value, dict)
            ):
                continue
            payload = dict(value)
            key = (
                name,
                str(payload.get("method") or ""),
                str(payload.get("operation_id") or payload.get("target") or ""),
            )
            if key in seen:
                continue
            seen.add(key)
            payloads.append((name, payload))
    return payloads


def _positive_int_metadata(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        count = int(value)
    except (TypeError, ValueError):
        return None
    return count if count > 0 else None


def _compound_visible_counts(payload: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for key in _COMPOUND_MODIFIER_COUNT_KEYS:
        count = _positive_int_metadata(payload.get(key))
        if count is not None:
            counts[key] = count
    rows = _positive_int_metadata(payload.get("rows"))
    columns = _positive_int_metadata(payload.get("columns"))
    if rows is not None and columns is not None and "grid_cell_count" not in counts:
        counts["grid_cell_count"] = rows * columns
    floors = _positive_int_metadata(payload.get("floors"))
    bays = _positive_int_metadata(payload.get("bays"))
    if floors is not None and bays is not None and "floor_bay_cell_count" not in counts:
        counts["floor_bay_cell_count"] = floors * bays
    grid_shape = payload.get("grid_shape")
    if isinstance(grid_shape, (list, tuple)) and len(grid_shape) >= 2:
        grid_count = 1
        for value in grid_shape:
            dimension = _positive_int_metadata(value)
            if dimension is None:
                grid_count = 0
                break
            grid_count *= dimension
        if grid_count > 0 and "grid_shape_cell_count" not in counts:
            counts["grid_shape_cell_count"] = grid_count
    return counts


def _compound_operation_reports(shape_ir: ShapeIR) -> list[dict[str, Any]]:
    reports: list[dict[str, Any]] = []
    for index, primitive in enumerate(shape_ir.primitives):
        semantic_metadata = _metadata_dict(getattr(primitive, "semantic_metadata", None))
        v2_metadata = _metadata_dict(semantic_metadata.get("shape_ir_v2"))
        source_metadata = _metadata_dict(semantic_metadata.get("source_shape_primitive"))
        operation = str(
            v2_metadata.get("v2_op")
            or source_metadata.get("v2_op")
            or getattr(primitive, "primitive_type", "")
        )
        operation_id = _primitive_operation_id(primitive, index)
        for modifier_name, payload in _compound_modifier_payloads(primitive):
            visible_counts = _compound_visible_counts(payload)
            kernel_program = _metadata_dict(payload.get("kernel_program"))
            exact_cut_count = _positive_int_metadata(
                kernel_program.get("kernel_program_exact_profile_cut_final_cut_count")
            )
            exact_chamfer_count = _positive_int_metadata(
                kernel_program.get("kernel_program_exact_profile_cut_final_chamfer_face_count")
            )
            exact_bevel_count = _positive_int_metadata(
                kernel_program.get("kernel_program_exact_profile_cut_final_bevel_face_count")
            )
            exact_rim_count = _positive_int_metadata(
                kernel_program.get("kernel_program_exact_profile_cut_final_rim_face_count")
            )
            if exact_cut_count is not None:
                visible_counts["profile_cut_count"] = exact_cut_count
            if exact_chamfer_count is not None:
                visible_counts["profile_cut_chamfer_face_count"] = exact_chamfer_count
            if exact_bevel_count is not None:
                visible_counts["profile_cut_bevel_face_count"] = exact_bevel_count
            if exact_rim_count is not None:
                visible_counts["profile_cut_rim_face_count"] = exact_rim_count
            if not visible_counts:
                continue
            report: dict[str, Any] = {
                "primitive_index": index,
                "operation_id": operation_id,
                "operation": operation,
                "modifier": modifier_name,
                "part": primitive.part,
                "primitive_type": primitive.primitive_type,
                "visible_counts": visible_counts,
            }
            for key in (
                "method",
                "kernel",
                "kernel_selection",
                "result_face_count",
                "result_watertight",
            ):
                value = payload.get(key)
                if value not in (None, "", (), [], {}):
                    report[key] = value
            for key in (
                "kernel_program_operation_count",
                "kernel_program_kernel_call_count",
                "kernel_program_operand_count",
                "kernel_program_body_count",
                "kernel_program_boolean_fallback_count",
                "instances_count",
                "instances_actual_assembly_method",
                "instances_result_body_count",
                "kernel_program_exact_profile_cut_operation_count",
                "kernel_program_exact_profile_cut_final_cut_count",
                "kernel_program_exact_profile_cut_final_chamfer_face_count",
                "kernel_program_exact_profile_cut_final_bevel_face_count",
                "kernel_program_exact_profile_cut_final_rim_face_count",
                "kernel_program_exact_profile_cut_final_bore_wall_face_count",
            ):
                value = kernel_program.get(key)
                if value not in (None, "", (), [], {}):
                    report[key] = value
            reports.append(report)
    return reports


def _face_operation_report(
    face_operation_ids: list[str],
    *,
    source: str,
    mode: str = "primitive_bounds",
    cut_operation_ids: list[str] | None = None,
    compound_operations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    operations = {
        operation_id: face_operation_ids.count(operation_id)
        for operation_id in sorted(set(face_operation_ids))
    }
    cut_ids = list(cut_operation_ids or [])
    cut_operations = {
        operation_id: cut_ids.count(operation_id)
        for operation_id in sorted(set(cut_ids))
    }
    report = {
        "face_operation_attribution_mode": mode,
        "face_operation_attribution_count": len(face_operation_ids),
        "face_operation_attribution_operation_count": len(operations),
        "face_operation_ids": face_operation_ids,
        "face_operation_summary": {
            "schema": "lathe.mesh_ir.face_operation_summary.v1",
            "face_count": len(face_operation_ids),
            "operation_count": len(operations),
            "operations": operations,
            "cut_operations": cut_operations,
            "source": source,
        },
    }
    if compound_operations:
        report["face_operation_summary"]["compound_operations"] = compound_operations
        report["face_operation_summary"]["compound_operation_count"] = len(compound_operations)
        report["compound_operation_count"] = len(compound_operations)
    if cut_ids:
        report["face_operation_cut_attribution_count"] = len(cut_ids)
        report["face_operation_cut_attribution_operation_count"] = len(set(cut_ids))
    return report


def _face_attribution_from_kernel_program(
    mesh: trimesh.Trimesh,
    shape_ir: ShapeIR,
    details: dict[str, Any],
) -> tuple[list[str], list[str], str] | None:
    operations = details.get("kernel_program_operations")
    operands = details.get("kernel_program_operands")
    if not isinstance(operations, list) or len(operations) != 1:
        return None
    operation = operations[0]
    if not isinstance(operation, dict) or operation.get("op") != "batch_union":
        return None
    if not isinstance(operands, list):
        return None

    face_parts: list[str] = []
    face_operation_ids: list[str] = []
    for operand in operands:
        if not isinstance(operand, dict):
            return None
        try:
            face_count = int(operand.get("source_mesh_face_count") or 0)
            source_index = int(operand.get("source_index"))
        except (TypeError, ValueError):
            return None
        if face_count <= 0 or not (0 <= source_index < len(shape_ir.primitives)):
            return None
        part = str(operand.get("part") or shape_ir.primitives[source_index].part or "mesh")
        operation_id = _primitive_operation_id(shape_ir.primitives[source_index], source_index)
        face_parts.extend([part] * face_count)
        face_operation_ids.extend([operation_id] * face_count)
    if len(face_parts) != len(mesh.faces):
        return None
    return face_parts, face_operation_ids, "scaffold_kernel_program.batch_union_operand_spans"


def _constructive_fallback_primitives(shape_ir: ShapeIR) -> tuple[list[ShapePrimitive], dict[str, Any]]:
    primitives = list(shape_ir.primitives)
    if not primitives:
        return [], {
            "boolean_fallback": "empty_shape_ir",
            "omitted_subtract_primitive_count": 0,
            "omitted_intersect_primitive_count": 0,
        }
    union_primitives = [primitive for primitive in primitives if (primitive.blend_mode or "union") == "union"]
    subtract_count = sum(1 for primitive in primitives if (primitive.blend_mode or "union") == "subtract")
    intersect_count = sum(1 for primitive in primitives if (primitive.blend_mode or "union") == "intersect")
    if subtract_count or intersect_count:
        selected = union_primitives or [
            primitive for primitive in primitives if (primitive.blend_mode or "union") != "subtract"
        ]
        return selected, {
            "boolean_fallback": "constructive_fallback_omit_cutters",
            "omitted_subtract_primitive_count": subtract_count,
            "omitted_intersect_primitive_count": intersect_count,
        }
    return primitives, {
        "boolean_fallback": "",
        "omitted_subtract_primitive_count": 0,
        "omitted_intersect_primitive_count": 0,
    }


def _assign_face_primitive_indices_via_bounds(
    mesh: trimesh.Trimesh,
    shape_ir: ShapeIR,
    *,
    include_boolean_operands: bool = False,
) -> list[int]:
    centroids = np.asarray(mesh.triangles_center, dtype=np.float64)
    primitive_entries: list[tuple[int, str, np.ndarray, np.ndarray, np.ndarray, float]] = []
    for index, primitive in enumerate(shape_ir.primitives):
        blend_mode = primitive.blend_mode or "union"
        if blend_mode == "subtract" and not include_boolean_operands:
            continue
        try:
            bounds = _exact_primitive_mesh(primitive).bounds
        except (
            ContractViolation,
            ValueError,
            RuntimeError,
            AttributeError,
            IndexError,
            TypeError,
        ):
            continue
        bmin = np.asarray(bounds[0], dtype=np.float64)
        bmax = np.asarray(bounds[1], dtype=np.float64)
        center = (bmin + bmax) * 0.5
        volume = float(np.prod(np.maximum(bmax - bmin, 1e-6)))
        primitive_entries.append((index, blend_mode, bmin, bmax, center, volume))
    if not primitive_entries:
        return []

    primitive_indices = np.asarray([item[0] for item in primitive_entries], dtype=np.int64)
    blend_modes = np.asarray([item[1] for item in primitive_entries], dtype=object)
    bmins = np.asarray([item[2] for item in primitive_entries], dtype=np.float64)
    bmaxs = np.asarray([item[3] for item in primitive_entries], dtype=np.float64)
    centers = np.asarray([item[4] for item in primitive_entries], dtype=np.float64)
    volumes = np.asarray([item[5] for item in primitive_entries], dtype=np.float64)
    extents = np.maximum((bmaxs - bmins) * 0.5, 1e-6)
    labels = np.full(len(centroids), -1, dtype=np.int64)
    pad = 0.1
    chunk_size = 4096
    boolean_operand_mask = np.isin(blend_modes, ["subtract", "intersect"])
    inside_priority = np.where(boolean_operand_mask, 0.25, 1.0) if include_boolean_operands else 1.0
    for start in range(0, len(centroids), chunk_size):
        chunk = centroids[start : start + chunk_size]
        inside = np.all(
            (chunk[:, None, :] >= bmins[None, :, :] - pad)
            & (chunk[:, None, :] <= bmaxs[None, :, :] + pad),
            axis=2,
        )
        has_inside = np.any(inside, axis=1)
        inside_scores = np.where(inside, volumes[None, :] * inside_priority, np.inf)
        inside_best = np.argmin(inside_scores, axis=1)

        delta = np.abs(chunk[:, None, :] - centers[None, :, :]) - extents[None, :, :]
        outside = np.maximum(delta, 0.0) / extents[None, :, :]
        distances = np.sqrt(np.sum(outside * outside, axis=2)) + volumes[None, :] * 1e-4
        nearest_best = np.argmin(distances, axis=1)
        best = np.where(has_inside, inside_best, nearest_best)
        labels[start : start + len(chunk)] = primitive_indices[best]
    return [int(value) for value in labels.tolist()]


def _cut_operation_ids_from_primitive_indices(shape_ir: ShapeIR, primitive_indices: list[int]) -> list[str]:
    cut_operation_ids: list[str] = []
    for primitive_index in primitive_indices:
        if not (0 <= primitive_index < len(shape_ir.primitives)):
            continue
        primitive = shape_ir.primitives[primitive_index]
        if (primitive.blend_mode or "union") in {"subtract", "intersect"}:
            cut_operation_ids.append(_primitive_operation_id(primitive, primitive_index))
    return cut_operation_ids


def _face_operation_ids_from_primitive_indices(shape_ir: ShapeIR, primitive_indices: list[int]) -> list[str]:
    if not primitive_indices:
        return []
    operation_ids: list[str] = []
    for primitive_index in primitive_indices:
        if 0 <= primitive_index < len(shape_ir.primitives):
            operation_ids.append(_primitive_operation_id(shape_ir.primitives[primitive_index], primitive_index))
        else:
            operation_ids.append("mesh")
    return operation_ids


def _face_parts_from_primitive_indices(shape_ir: ShapeIR, primitive_indices: list[int]) -> list[str]:
    if not primitive_indices:
        return []
    return [
        shape_ir.primitives[index].part
        if 0 <= index < len(shape_ir.primitives)
        else "mesh"
        for index in primitive_indices
    ]


def _assign_face_operation_ids_via_bounds(mesh: trimesh.Trimesh, shape_ir: ShapeIR) -> list[str]:
    primitive_indices = _assign_face_primitive_indices_via_bounds(mesh, shape_ir)
    if len(primitive_indices) != len(mesh.faces):
        return []
    return _face_operation_ids_from_primitive_indices(shape_ir, primitive_indices)


def _assign_face_parts_via_bounds(mesh: trimesh.Trimesh, shape_ir: ShapeIR) -> list[str]:
    """Assign a part label per face by matching centroids to construction bounds."""
    primitive_indices = _assign_face_primitive_indices_via_bounds(mesh, shape_ir)
    if primitive_indices:
        return _face_parts_from_primitive_indices(shape_ir, primitive_indices)

    centroids = np.asarray(mesh.triangles_center, dtype=np.float64)
    primitive_entries: list[tuple[str, np.ndarray, np.ndarray, np.ndarray, float]] = []
    for primitive in shape_ir.primitives:
        if (primitive.blend_mode or "union") == "subtract":
            continue
        try:
            bounds = _exact_primitive_mesh(primitive).bounds
        except (
            ContractViolation,
            ValueError,
            RuntimeError,
            AttributeError,
            IndexError,
            TypeError,
        ):
            continue
        bmin = np.asarray(bounds[0], dtype=np.float64)
        bmax = np.asarray(bounds[1], dtype=np.float64)
        center = (bmin + bmax) * 0.5
        volume = float(np.prod(np.maximum(bmax - bmin, 1e-6)))
        primitive_entries.append((primitive.part, bmin, bmax, center, volume))
    if primitive_entries:
        labels: list[str] = []
        pad = 0.1
        for centroid in centroids:
            inside: list[tuple[str, float]] = []
            nearest: list[tuple[str, float]] = []
            for part, bmin, bmax, center, volume in primitive_entries:
                extent = np.maximum((bmax - bmin) / 2.0, 1e-6)
                if bool(np.all(centroid >= bmin - pad) and np.all(centroid <= bmax + pad)):
                    inside.append((part, volume))
                    continue
                delta = np.abs(centroid - center) - extent
                distance = float(np.linalg.norm(np.maximum(delta, 0.0) / extent))
                nearest.append((part, distance + volume * 1e-4))
            if inside:
                labels.append(min(inside, key=lambda item: item[1])[0])
            elif nearest:
                labels.append(min(nearest, key=lambda item: item[1])[0])
            else:
                labels.append("mesh")
        return labels

    entries: list[tuple[str, np.ndarray, np.ndarray, np.ndarray]] = []
    for region in shape_ir.regions:
        center = np.array(region.center, dtype=np.float64)
        half = np.array(region.extents, dtype=np.float64) / 2.0
        entries.append((region.part, center - half, center + half, center))
    default_part = entries[0][0] if entries else "mesh"
    labels: list[str] = []
    for centroid in centroids:
        best_part = default_part
        best_distance = float("inf")
        for part, bmin, bmax, center in entries:
            extent = np.maximum((bmax - bmin) / 2.0, 1e-6)
            delta = np.abs(centroid - center) - extent
            outside = np.maximum(delta, 0.0)
            distance = float(np.linalg.norm(outside / extent))
            if distance < best_distance:
                best_distance = distance
                best_part = part
        labels.append(best_part)
    return labels


def _native_candidate_score(
    asset_graph: AssetGraph, shape_ir: ShapeIR, conditioning: dict[str, Any], candidate_index: int
) -> float:
    assessment = shape_ir.assessment
    objective_map = objective_weights(asset_graph)
    if objective_map:
        metric_values = {
            "silhouette_readability": assessment.get("silhouette_complexity", 0.0),
            "geometry_integration_quality": min(
                1.0,
                0.55
                + 0.06 * assessment.get("edge_treatment_count", 0)
                + 0.04 * assessment.get("feature_coherence", 0.0),
            ),
            "visual_surface_quality": min(
                1.0,
                0.45
                + 0.12 * assessment.get("feature_density", 0.0)
                + 0.12 * assessment.get("feature_coherence", 0.0),
            ),
            "primitive_likeness_penalty": max(
                0.0,
                0.48
                - 0.20 * assessment.get("feature_coherence", 0.0)
                - 0.08 * assessment.get("edge_treatment_count", 0),
            ),
            "feature_density": assessment.get("feature_density", 0.0),
        }
        total = 0.0
        for metric_name, weight in objective_map.items():
            value = float(metric_values.get(metric_name, 0.0))
            if metric_name.endswith("_penalty"):
                value = 1.0 - min(1.0, value)
            total += value * weight
        total += 0.04 * assessment.get("required_part_coverage", 0.0)
        total -= 0.012 * candidate_index
        return round(min(0.96, max(0.48, total + 0.55)), 6)
    score = 0.66
    score += 0.05 * assessment.get("required_part_coverage", 0.0)
    score += 0.05 * assessment.get("richness_floor", 0.0)
    score += 0.03 * assessment.get("symmetry_region_score", 0.0)
    score += 0.02 * assessment.get("primitive_diversity", 0.0)
    score += 0.04 * assessment.get("feature_density", 0.0)
    score += 0.03 * assessment.get("silhouette_complexity", 0.0)
    score += 0.03 * assessment.get("feature_coherence", 0.0)
    if conditioning.get("image_refs"):
        score += 0.02
    if conditioning.get("mesh_refs"):
        score += 0.03
    if asset_graph.kind == "env_module":
        score += 0.01
    score -= 0.015 * candidate_index
    return round(min(0.96, max(0.52, score)), 6)


def _grammar_authoring_priority_boost(grammar_report: dict[str, Any]) -> dict[str, Any]:
    """Bounded score lift for grammar candidates that executed authored controls."""
    authoring_program = (
        dict(grammar_report.get("authoring_program", {}))
        if isinstance(grammar_report.get("authoring_program"), dict)
        else {}
    )
    authoring_consumption = (
        dict(grammar_report.get("authoring_consumption", {}))
        if isinstance(grammar_report.get("authoring_consumption"), dict)
        else {}
    )
    authoring_context = (
        dict(grammar_report.get("authoring_context", {}))
        if isinstance(grammar_report.get("authoring_context"), dict)
        else {}
    )
    construction_graph = (
        dict(grammar_report.get("construction_graph_consumption", {}))
        if isinstance(grammar_report.get("construction_graph_consumption"), dict)
        else {}
    )
    selected_ops = (
        dict(authoring_consumption.get("selected_records_by_operation", {}))
        if isinstance(authoring_consumption.get("selected_records_by_operation"), dict)
        else {}
    )

    boost = 0.0
    reasons: list[str] = []
    injected = int(authoring_program.get("injected_authoring_op_count", 0) or 0)
    if injected:
        value = min(0.05, 0.012 * injected)
        boost += value
        reasons.append("injected_authoring_ops")
    adjusted = int(authoring_program.get("adjustment_count", 0) or 0)
    edge_adjusted = int(authoring_program.get("edge_adjustment_count", 0) or 0)
    if adjusted or edge_adjusted:
        value = min(0.05, 0.008 * (adjusted + edge_adjusted))
        boost += value
        reasons.append("authoring_adjusted_ops")
    seed_adjusted = int(authoring_program.get("seed_adjustment_count", 0) or 0)
    if seed_adjusted:
        value = min(0.02, 0.004 * seed_adjusted)
        boost += value
        reasons.append("seeded_authoring_ops")
    executed_ops = sum(int(value or 0) for value in selected_ops.values())
    if executed_ops:
        value = min(0.06, 0.003 * executed_ops)
        boost += value
        reasons.append("selected_executable_ops")
    executed_graph_requests = [
        str(item)
        for item in construction_graph.get("executed_feature_requests", [])
        if str(item)
    ] if isinstance(construction_graph.get("executed_feature_requests"), list) else []
    unresolved_graph_requests = [
        str(item)
        for item in construction_graph.get("unresolved_feature_requests", [])
        if str(item)
    ] if isinstance(construction_graph.get("unresolved_feature_requests"), list) else []
    if executed_graph_requests:
        value = min(0.10, 0.012 * len(executed_graph_requests))
        boost += value
        reasons.append("construction_graph_requests_executed")
        if not unresolved_graph_requests:
            boost += 0.025
            reasons.append("construction_graph_requests_fully_resolved")
    if unresolved_graph_requests:
        boost = max(0.0, boost - min(0.05, 0.01 * len(unresolved_graph_requests)))
        reasons.append("construction_graph_requests_unresolved")
    if str(authoring_context.get("feature_density_source") or ""):
        boost += 0.015
        reasons.append("density_source_consumed")
    if any(
        str(authoring_context.get(key) or "")
        for key in ("panelization", "edge_complexity", "style_pack", "silhouette_profile")
    ):
        boost += 0.015
        reasons.append("shape_controls_consumed")
    boost = round(min(0.28, max(0.0, boost)), 6)
    return {
        "boost": boost,
        "reasons": reasons,
        "selected_operation_count": executed_ops,
        "injected_authoring_op_count": injected,
        "adjusted_authoring_op_count": adjusted + edge_adjusted,
        "seed_adjustment_count": seed_adjusted,
        "executed_construction_graph_request_count": len(executed_graph_requests),
        "unresolved_construction_graph_request_count": len(unresolved_graph_requests),
    }


def _runtime_score_report(
    asset_graph: AssetGraph,
    shape_ir: ShapeIR,
    conditioning: dict[str, Any],
    candidate_index: int,
    selection_score: float | None,
) -> dict[str, Any]:
    native_score = _native_candidate_score(asset_graph, shape_ir, conditioning, candidate_index)
    if selection_score is None:
        return {
            "score": native_score,
            "native_candidate_score": native_score,
            "selection_score_source": "native_candidate_score",
        }
    try:
        score = float(selection_score)
    except (TypeError, ValueError):
        score = native_score
        source = "native_candidate_score_after_invalid_selection_score"
    else:
        source = "candidate_pre_score"
    return {
        "score": round(min(0.99, max(0.0, score)), 6),
        "native_candidate_score": native_score,
        "selection_score_source": source,
    }


def _needs_more_repairs(asset_graph: AssetGraph, shape_ir: ShapeIR) -> bool:
    assessment = shape_ir.assessment
    requirements = asset_graph.semantic_requirements
    return (
        assessment.get("feature_density", 0.0) < requirements.get("minimum_detail_density", 0.58)
        or assessment.get("feature_coherence", 0.0) < requirements.get("minimum_feature_coherence", 0.56)
        or assessment.get("edge_treatment_count", 0) < max(4, len(asset_graph.parts))
    )


def _selection_notes(
    asset_graph: AssetGraph,
    shape_ir: ShapeIR,
    conditioning: dict[str, Any],
    candidate_index: int,
    fidelity_tier: str,
    feature_ops_used: list[str],
) -> list[str]:
    notes = [
        f"native assembly candidate for family='{asset_graph.family}'",
        f"blueprint_id={shape_ir.blueprint_id}",
        f"candidate_index={candidate_index}",
        f"primitives_used={','.join(shape_ir.primitives_used)}",
        f"fidelity={fidelity_tier}",
        f"feature_ops={','.join(feature_ops_used)}",
    ]
    if conditioning.get("mesh_refs"):
        notes.insert(0, "reconstructed from mesh-conditioned assembly blueprint")
    elif conditioning.get("image_refs"):
        notes.insert(0, "generated from image-conditioned assembly blueprint")
    else:
        notes.insert(0, "generated from intent assembly blueprint")
    return notes


def _game_pipeline_hints(asset_graph: AssetGraph, shape_ir: ShapeIR) -> dict[str, Any]:
    """Collect authored game-asset structure hints produced by generation."""
    controls = geometry_detail_controls_from_authoring(asset_graph.authoring)
    optimize = asset_graph.authoring.get("optimize", {})
    physics = asset_graph.authoring.get("physics", {})
    package = asset_graph.authoring.get("package", {})
    if not isinstance(optimize, dict):
        optimize = {}
    if not isinstance(physics, dict):
        physics = {}
    if not isinstance(package, dict):
        package = {}

    lod_levels = int(controls.lod_levels or optimize.get("lods", 0) or 0)
    collision_proxy = str(controls.collision_proxy or physics.get("collision", "") or "")
    export_profiles = list(controls.export_profiles)
    package_formats = package.get("formats", [])
    if isinstance(package_formats, list):
        export_profiles = list(dict.fromkeys([*export_profiles, *[str(item) for item in package_formats]]))
    material_id_strategy = (
        "zone_and_part_material_ids"
        if shape_ir.assessment.get("geometry_detail_zone_count", 0)
        else "part_material_ids"
    )
    hints: dict[str, Any] = {
        "material_id_strategy": material_id_strategy,
        "uv_island_strategy": "preserve_part_borders_and_detail_zones",
        "bake_target": "high_to_low" if lod_levels else "single_mesh",
    }
    if lod_levels:
        hints["lod_levels_requested"] = lod_levels
        hints["lod_policy"] = "author_requested"
    if controls.highlow_mode:
        hints["highlow_mode"] = controls.highlow_mode
        hints["highlow_low_lod"] = int(controls.highlow_low_lod)
        hints["highlow_bake_cage_offset_cm"] = float(controls.highlow_bake_cage_offset_cm)
    if collision_proxy:
        hints["collision_proxy"] = collision_proxy
    if export_profiles:
        hints["export_profiles"] = export_profiles
    if shape_ir.assessment.get("geometry_detail_module_sockets"):
        hints["module_sockets"] = list(shape_ir.assessment["geometry_detail_module_sockets"])
    if shape_ir.assessment.get("geometry_detail_attachment_motifs"):
        hints["attachment_motifs"] = list(shape_ir.assessment["geometry_detail_attachment_motifs"])
    if shape_ir.assessment.get("geometry_detail_module_categories"):
        hints["module_categories"] = list(shape_ir.assessment["geometry_detail_module_categories"])
    if shape_ir.assessment.get("geometry_detail_zones"):
        hints["detail_zones"] = list(shape_ir.assessment["geometry_detail_zones"])
    if shape_ir.assessment.get("geometry_detail_style_packs"):
        hints["style_packs"] = list(shape_ir.assessment["geometry_detail_style_packs"])
    if shape_ir.assessment.get("geometry_detail_silhouette_profiles"):
        hints["silhouette_profiles"] = list(shape_ir.assessment["geometry_detail_silhouette_profiles"])
    if shape_ir.assessment.get("geometry_detail_silhouette_motifs"):
        hints["silhouette_motifs"] = list(shape_ir.assessment["geometry_detail_silhouette_motifs"])
    return hints


def _runtime_from_shape_ir(
    asset_graph: AssetGraph,
    shape_ir: ShapeIR,
    *,
    candidate_index: int,
    conditioning: dict[str, Any],
    mode: str,
    repairs_applied: list[dict[str, Any]],
    fidelity_tier: str,
    feature_report: dict[str, Any],
    candidate_params: dict[str, Any],
    fidelity_profile,
    geometry_kernel_id: str | None = None,
    geometry_kernel: Any | None = None,
    selection_score: float | None = None,
) -> dict[str, Any]:
    part_colors = {part.name: _make_color(part.name) for part in asset_graph.parts}
    game_pipeline_hints = _game_pipeline_hints(asset_graph, shape_ir)
    score_report = _runtime_score_report(
        asset_graph,
        shape_ir,
        conditioning,
        candidate_index,
        selection_score,
    )
    kernel_program_failure: dict[str, Any] | None = None
    kernel_program_preference_reason = (
        _kernel_program_preference_reason(shape_ir, geometry_kernel)
        if geometry_kernel is not None
        else ""
    )
    if geometry_kernel is not None and kernel_program_preference_reason:
        combined, face_parts, kernel_program_details = _fuse_via_kernel_program(shape_ir, geometry_kernel)
        kernel_program_details["kernel_program_preference_reason"] = kernel_program_preference_reason
        if combined is not None:
            integration_report = _kernel_program_integration_report(
                shape_ir=shape_ir,
                mesh=combined,
                geometry_kernel_id=geometry_kernel_id,
                kernel_program_details=kernel_program_details,
                primary=True,
            )
            mesh_ir_payload = finalize_mesh_ir(
                combined,
                shape_ir,
                face_parts,
                metadata={"integration_report": integration_report},
            ).to_dict()
            return {
                "mesh": combined,
                "face_parts": face_parts,
                "part_colors": part_colors,
                "units": "cm",
                "meta": {
                    "parts": sorted({region.part for region in shape_ir.regions}),
                    "coarse_material_slots": max(1, len(asset_graph.materials)),
                    **score_report,
                    "selection_notes": _selection_notes(
                        asset_graph,
                        shape_ir,
                        conditioning,
                        candidate_index,
                        fidelity_tier,
                        feature_report.get("feature_ops_used", []),
                    ),
                    "conditioning": {
                        "provider": None,
                        "reference_strength": conditioning.get("reference_strength", 0.0),
                        "family": asset_graph.family,
                        "native_scaffold": True,
                        "mode": mode,
                        "blueprint_id": shape_ir.blueprint_id,
                        "quality_plan_consumed": bool(conditioning.get("quality_plan_consumed")),
                        "quality_generation_source_stage": conditioning.get("quality_generation_source_stage"),
                        "quality_conditioning": dict(conditioning.get("quality_conditioning", {})),
                    },
                    "blueprint_id": shape_ir.blueprint_id,
                    "primitives_used": list(shape_ir.primitives_used),
                    "shape_assessment": dict(shape_ir.assessment),
                    "repairs_applied": repairs_applied,
                    "feature_report": feature_report,
                    "candidate_params": candidate_params,
                    "game_pipeline_hints": game_pipeline_hints,
                    "integration_report": integration_report,
                    "mesh_ir": mesh_ir_payload,
                },
            }
        kernel_program_failure = kernel_program_details

    shape_ir_for_fuse = shape_ir
    if kernel_program_failure is not None:
        signature = dict(shape_ir.signature) if isinstance(shape_ir.signature, dict) else {}
        signature["kernel_program_disabled"] = True
        signature["kernel_program_disabled_reason"] = "primary_kernel_program_failed"
        shape_ir_for_fuse = replace(shape_ir, signature=signature)
    fused_mesh_ir, integration_report = fuse_shape_ir(shape_ir_for_fuse, fidelity_profile)
    if geometry_kernel_id and isinstance(integration_report, dict):
        integration_report.setdefault("geometry_kernel", geometry_kernel_id)
    if (
        geometry_kernel is not None
        and kernel_program_failure is None
        and _needs_kernel_program_rescue(fused_mesh_ir, integration_report)
    ):
        combined, face_parts, kernel_program_details = _fuse_via_kernel_program(shape_ir, geometry_kernel)
        if combined is not None:
            # Preserve the original fuse_shape_ir failure under ``attempted``
            # so the trace still records *why* the primary path declined to
            # produce a mesh. Without this, the manifold report overwrites
            # the failure context, violating CLAUDE.md's mandated
            # attempted-vs-actual provider tracking contract.
            attempted_report = (
                integration_report
                if isinstance(integration_report, dict)
                else {"mode": "fuse_shape_ir", "ok": False}
            )
            integration_report = _kernel_program_integration_report(
                shape_ir=shape_ir,
                mesh=combined,
                geometry_kernel_id=geometry_kernel_id,
                kernel_program_details=kernel_program_details,
                primary=False,
                attempted_report=attempted_report,
            )
            mesh_ir_payload = finalize_mesh_ir(
                combined,
                shape_ir,
                face_parts,
                metadata={"integration_report": integration_report},
            ).to_dict()
            return {
                "mesh": combined,
                "face_parts": face_parts,
                "part_colors": part_colors,
                "units": "cm",
                "meta": {
                    "parts": sorted({region.part for region in shape_ir.regions}),
                    "coarse_material_slots": max(1, len(asset_graph.materials)),
                    **score_report,
                    "selection_notes": _selection_notes(
                        asset_graph,
                        shape_ir,
                        conditioning,
                        candidate_index,
                        fidelity_tier,
                        feature_report.get("feature_ops_used", []),
                    ),
                    "conditioning": {
                        "provider": None,
                        "reference_strength": conditioning.get("reference_strength", 0.0),
                        "family": asset_graph.family,
                        "native_scaffold": True,
                        "mode": mode,
                        "blueprint_id": shape_ir.blueprint_id,
                        "quality_plan_consumed": bool(conditioning.get("quality_plan_consumed")),
                        "quality_generation_source_stage": conditioning.get("quality_generation_source_stage"),
                        "quality_conditioning": dict(conditioning.get("quality_conditioning", {})),
                    },
                    "blueprint_id": shape_ir.blueprint_id,
                    "primitives_used": list(shape_ir.primitives_used),
                    "shape_assessment": dict(shape_ir.assessment),
                    "repairs_applied": repairs_applied,
                    "feature_report": feature_report,
                    "candidate_params": candidate_params,
                    "game_pipeline_hints": game_pipeline_hints,
                    "integration_report": integration_report,
                    "mesh_ir": mesh_ir_payload,
                },
            }
        else:
            kernel_program_failure = kernel_program_details
    if kernel_program_failure is not None and isinstance(integration_report, dict):
        integration_report = {
            **integration_report,
            "kernel_program_attempted": kernel_program_failure,
        }
    if fused_mesh_ir is None:
        named_meshes: list[tuple[str, trimesh.Trimesh]] = []
        face_parts = []
        fallback_primitives, fallback_details = _constructive_fallback_primitives(shape_ir)
        for primitive in fallback_primitives:
            mesh = _primitive_mesh(primitive)
            named_meshes.append((primitive.part, mesh))
            face_parts.extend([primitive.part] * len(mesh.faces))
        combined = (
            trimesh.util.concatenate([mesh for _, mesh in named_meshes])
            if len(named_meshes) > 1
            else named_meshes[0][1] if named_meshes else trimesh.Trimesh()
        )
        integration_report = {
            "mode": "constructive_fallback",
            "reason": "kernel program failed" if kernel_program_failure is not None else "geometry kernel unavailable",
            "primitive_count": len(shape_ir.primitives),
            "fallback_visible_primitive_count": len(fallback_primitives),
            **fallback_details,
        }
        if kernel_program_failure is not None:
            integration_report["kernel_program_attempted"] = kernel_program_failure
        mesh_ir_payload = None
    else:
        combined = fused_mesh_ir.to_trimesh()
        face_parts = list(fused_mesh_ir.face_parts)
        face_operation_ids = _assign_face_operation_ids_via_bounds(combined, shape_ir)
        face_operation_report = (
            _face_operation_report(
                face_operation_ids,
                source="scaffold_legacy_fuse.primitive_bounds",
                compound_operations=_compound_operation_reports(shape_ir),
            )
            if len(face_operation_ids) == len(combined.faces)
            else {}
        )
        if face_operation_report:
            integration_report = {**integration_report, **face_operation_report}
            mesh_metadata = dict(getattr(fused_mesh_ir, "metadata", {}) or {})
            mesh_metadata["integration_report"] = integration_report
            mesh_ir_payload = finalize_mesh_ir(
                combined,
                shape_ir,
                face_parts,
                metadata=mesh_metadata,
            ).to_dict()
        else:
            mesh_ir_payload = fused_mesh_ir.to_dict()
    return {
        "mesh": combined,
        "face_parts": face_parts,
        "part_colors": part_colors,
        "units": "cm",
        "meta": {
            "parts": sorted({region.part for region in shape_ir.regions}),
            "coarse_material_slots": max(1, len(asset_graph.materials)),
            **score_report,
            "selection_notes": _selection_notes(
                asset_graph,
                shape_ir,
                conditioning,
                candidate_index,
                fidelity_tier,
                feature_report.get("feature_ops_used", []),
            ),
            "conditioning": {
                "provider": None,
                "reference_strength": conditioning.get("reference_strength", 0.0),
                "family": asset_graph.family,
                "native_scaffold": True,
                "mode": mode,
                "blueprint_id": shape_ir.blueprint_id,
                "quality_plan_consumed": bool(conditioning.get("quality_plan_consumed")),
                "quality_generation_source_stage": conditioning.get("quality_generation_source_stage"),
                "quality_conditioning": dict(conditioning.get("quality_conditioning", {})),
            },
            "blueprint_id": shape_ir.blueprint_id,
            "primitives_used": list(shape_ir.primitives_used),
            "shape_assessment": dict(shape_ir.assessment),
            "repairs_applied": repairs_applied,
            "feature_report": feature_report,
            "candidate_params": candidate_params,
            "game_pipeline_hints": game_pipeline_hints,
            "integration_report": integration_report,
            "mesh_ir": mesh_ir_payload,
        },
    }


def compile_scaffold_candidates(
    asset_graph: AssetGraph,
    *,
    seed: int,
    candidates_count: int,
    conditioning: dict[str, Any],
    mode: str,
    runtime_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compile scaffold candidates.

    Args:
        asset_graph: asset_graph argument.
        seed: seed argument.
        candidates_count: candidates_count argument.
        conditioning: conditioning argument.
        mode: mode argument.
        runtime_config: runtime_config argument.

    Returns:
        The result.
    """
    candidate_records: list[dict[str, Any]] = []
    fidelity = infer_fidelity_profile(asset_graph)
    geometry_kernel = resolve_geometry_kernel(runtime_config)
    geometry_kernel_id = getattr(geometry_kernel, "name", None)
    # Roadmap §6.8: route on construction_grammar axis. snap_grid/brick_snap/
    # modular_kit thread routing flags through ``conditioning``; free_form
    # is the default and produces no-op routing.
    conditioning = _apply_construction_grammar_routing(asset_graph, conditioning)
    source_best_of = int(asset_graph.authoring.get("space", {}).get("select", {}).get("best_of", 0) or 0)
    tier_floor = 4 if fidelity.tier == "cinematic" else 3 if fidelity.tier == "hero" else 1
    search_count = max(tier_floor, candidates_count, source_best_of)
    # Velocity flags (``lathe quick --candidates``/``--no-search``) bypass the
    # hero-tier floor of 3 by setting ``conditioning["force_search_count"]``.
    force_search_count = conditioning.get("force_search_count") if isinstance(conditioning, dict) else None
    if force_search_count is not None:
        try:
            forced = int(force_search_count)
        except (TypeError, ValueError):
            forced = 0
        if forced >= 1:
            search_count = forced
    for index in range(search_count):
        rng = _candidate_rng(seed, index)
        params = generate_candidate_params(asset_graph, seed=seed, candidate_index=index, fidelity=fidelity)
        params = apply_quality_adapters_to_candidate_params(
            params, conditioning.get("quality_conditioning")
        )
        params = apply_style_modifiers_to_candidate_params(params, asset_graph)
        blueprint = apply_candidate_params(
            resolve_blueprint(asset_graph, conditioning, rng, index), params, asset_graph
        )
        shape_ir = compile_assembly_blueprint(asset_graph, blueprint)
        shape_ir, feature_report = compile_feature_enhancements(
            asset_graph, shape_ir, fidelity=fidelity, params=params
        )
        round_reports = []
        repaired_shape_ir = shape_ir
        applied_repairs: list[dict[str, Any]] = []
        round_index = 0
        while round_index < fidelity.repair_budget:
            planned_repairs = plan_shape_repairs(asset_graph, repaired_shape_ir)
            if not planned_repairs and not _needs_more_repairs(asset_graph, repaired_shape_ir):
                break
            repaired_shape_ir, round_applied = execute_shape_repairs(
                asset_graph,
                repaired_shape_ir,
                planned_repairs,
                max_repairs=max(1, fidelity.repair_budget - round_index),
            )
            round_reports.append(
                {
                    "round": round_index + 1,
                    "planned": [repair.to_dict() for repair in planned_repairs],
                    "applied": round_applied,
                    "shape_assessment": dict(repaired_shape_ir.assessment),
                }
            )
            applied_repairs.extend(round_applied)
            if not round_applied:
                break
            round_index += 1
        feature_report["shape_assessment"] = dict(repaired_shape_ir.assessment)
        feature_report["geometry_detail_feature_count"] = int(
            repaired_shape_ir.assessment.get("geometry_detail_feature_count", 0) or 0
        )
        feature_report["geometry_detail_feature_types"] = list(
            repaired_shape_ir.assessment.get("geometry_detail_feature_types", [])
        )
        feature_report["geometry_detail_operator_counts"] = dict(
            repaired_shape_ir.assessment.get("geometry_detail_operator_counts", {})
        )
        feature_report["geometry_detail_zone_count"] = int(
            repaired_shape_ir.assessment.get("geometry_detail_zone_count", 0) or 0
        )
        feature_report["geometry_detail_zones"] = list(
            repaired_shape_ir.assessment.get("geometry_detail_zones", [])
        )
        feature_report["geometry_detail_edge_metadata"] = list(
            repaired_shape_ir.assessment.get("geometry_detail_edge_metadata", [])
        )
        feature_report["geometry_detail_style_modifiers"] = list(
            repaired_shape_ir.assessment.get("geometry_detail_style_modifiers", [])
        )
        feature_report["geometry_detail_style_packs"] = list(
            repaired_shape_ir.assessment.get("geometry_detail_style_packs", [])
        )
        feature_report["geometry_detail_module_sockets"] = list(
            repaired_shape_ir.assessment.get("geometry_detail_module_sockets", [])
        )
        feature_report["geometry_detail_attachment_motifs"] = list(
            repaired_shape_ir.assessment.get("geometry_detail_attachment_motifs", [])
        )
        feature_report["geometry_detail_module_categories"] = list(
            repaired_shape_ir.assessment.get("geometry_detail_module_categories", [])
        )
        feature_report["geometry_detail_silhouette_profiles"] = list(
            repaired_shape_ir.assessment.get("geometry_detail_silhouette_profiles", [])
        )
        feature_report["geometry_detail_silhouette_motifs"] = list(
            repaired_shape_ir.assessment.get("geometry_detail_silhouette_motifs", [])
        )
        feature_report["game_pipeline_hints"] = _game_pipeline_hints(asset_graph, repaired_shape_ir)
        feature_report["feature_ops_used"] = sorted(
            set(feature_report.get("feature_ops_used", []))
            | set(repaired_shape_ir.assessment.get("feature_types", []))
        )
        candidate_records.append(
            {
                "candidate_index": index,
                "shape_ir": repaired_shape_ir,
                "blueprint": blueprint.to_dict(),
                "feature_report": feature_report,
                "candidate_params": params.to_dict(),
                "repairs": {"candidate_index": index, "rounds": round_reports, "applied": applied_repairs},
                "pre_score": _native_candidate_score(asset_graph, repaired_shape_ir, conditioning, index),
            }
        )

    if candidate_records:
        grammar_candidate = compile_grammar_program_candidate(
            asset_graph,
            candidate_records[0]["shape_ir"],
            geometry_kernel=geometry_kernel,
            augment_template=False,
            materialize_selected_records=False,
        )
        if grammar_candidate is None:
            grammar_candidate = compile_grammar_program_candidate(
                asset_graph,
                candidate_records[0]["shape_ir"],
                geometry_kernel=geometry_kernel,
                augment_template=True,
            )
        if grammar_candidate is not None:
            grammar_shape_ir, grammar_report = grammar_candidate
            grammar_index = len(candidate_records)
            base_record = candidate_records[0]
            grammar_feature_report = dict(base_record["feature_report"])
            grammar_feature_report["shape_assessment"] = dict(grammar_shape_ir.assessment)
            grammar_feature_report["grammar_program"] = grammar_report
            grammar_feature_report["feature_ops_used"] = sorted(
                set(grammar_feature_report.get("feature_ops_used", []))
                | {"grammar_program", "shape_ir_v2_lowering"}
            )
            grammar_score = _native_candidate_score(
                asset_graph,
                grammar_shape_ir,
                conditioning,
                grammar_index,
            )
            grammar_score += min(0.12, 0.002 * grammar_report["executed_primitive_count"])
            grammar_score += min(
                0.08,
                0.003
                * max(
                    int(grammar_report.get("executed_kernel_program_record_count", 0) or 0),
                    int(grammar_report.get("deferred_kernel_program_record_count", 0) or 0),
                ),
            )
            grammar_priority = _grammar_authoring_priority_boost(grammar_report)
            grammar_score += float(grammar_priority["boost"])
            executed_graph_request_count = int(
                grammar_priority.get("executed_construction_graph_request_count", 0) or 0
            )
            unresolved_graph_request_count = int(
                grammar_priority.get("unresolved_construction_graph_request_count", 0) or 0
            )
            if executed_graph_request_count and not unresolved_graph_request_count:
                base_score = float(base_record.get("pre_score", 0.0) or 0.0)
                graph_execution_floor = base_score + min(0.09, 0.015 * executed_graph_request_count)
                grammar_score = max(grammar_score, graph_execution_floor)
            grammar_score = min(0.99, grammar_score)
            grammar_feature_report["grammar_program_selection_priority"] = grammar_priority
            candidate_records.append(
                {
                    "candidate_index": grammar_index,
                    "shape_ir": grammar_shape_ir,
                    "blueprint": {
                        "blueprint_id": grammar_shape_ir.blueprint_id,
                        "source": "grammar_program_candidate",
                        "template_blueprint_id": base_record["shape_ir"].blueprint_id,
                    },
                    "feature_report": grammar_feature_report,
                    "candidate_params": base_record["candidate_params"],
                    "repairs": {"candidate_index": grammar_index, "rounds": [], "applied": []},
                    "pre_score": grammar_score,
                }
            )

    ranked_records = sorted(candidate_records, key=lambda item: (-item["pre_score"], item["candidate_index"]))
    grammar_program_primary = bool(
        ranked_records
        and isinstance(ranked_records[0].get("feature_report"), dict)
        and isinstance(ranked_records[0]["feature_report"].get("grammar_program"), dict)
    )
    requested_runtime_limit = conditioning.get("runtime_candidate_limit") if isinstance(conditioning, dict) else None
    if requested_runtime_limit is not None:
        try:
            runtime_candidate_limit = int(requested_runtime_limit)
        except (TypeError, ValueError):
            runtime_candidate_limit = 1
    elif grammar_program_primary:
        runtime_candidate_limit = 1
    elif candidates_count > 1 or source_best_of > 1:
        runtime_candidate_limit = 2
    else:
        runtime_candidate_limit = 1
    runtime_candidate_limit = (
        max(1, min(runtime_candidate_limit, len(ranked_records)))
        if ranked_records
        else 0
    )
    shortlisted = ranked_records[:runtime_candidate_limit]
    selection_rank_by_candidate_index = {
        int(record["candidate_index"]): rank
        for rank, record in enumerate(shortlisted)
    }

    runtime_candidates: list[dict[str, Any]] = []
    shape_irs: list[ShapeIR] = []
    blueprints: list[dict[str, Any]] = []
    repairs: list[dict[str, Any]] = []
    feature_reports: list[dict[str, Any]] = []
    candidate_params_list: list[dict[str, Any]] = []
    for record in shortlisted:
        runtime_candidates.append(
            _runtime_from_shape_ir(
                asset_graph,
                record["shape_ir"],
                candidate_index=record["candidate_index"],
                conditioning=conditioning,
                mode=mode,
                repairs_applied=record["repairs"]["applied"],
                fidelity_tier=fidelity.tier,
                feature_report=record["feature_report"],
                candidate_params=record["candidate_params"],
                fidelity_profile=fidelity,
                geometry_kernel_id=geometry_kernel_id,
                geometry_kernel=geometry_kernel,
                selection_score=float(record["pre_score"]),
            )
        )
        shape_irs.append(record["shape_ir"])
        blueprints.append(record["blueprint"])
        repairs.append(record["repairs"])
        feature_reports.append(record["feature_report"])
        candidate_params_list.append(record["candidate_params"])

    first_ir = shape_irs[0]
    return {
        "asset_graph": asset_graph,
        "shape_irs": shape_irs,
        "runtime_candidates": runtime_candidates,
        "report": {
            "family": asset_graph.family,
            "generator": "parametric_hard_surface_assembly",
            "asset_graph": asset_graph.to_dict(),
            "shape_irs": [item.to_dict() for item in shape_irs],
            "blueprints": blueprints,
            "feature_reports": feature_reports,
            "grammar_program_candidates": [
                item["grammar_program"]
                for item in feature_reports
                if isinstance(item.get("grammar_program"), dict)
            ],
            "candidate_search": candidate_params_list,
            "candidate_search_summary": [
                {
                    "candidate_index": item["candidate_index"],
                    "pre_score": item["pre_score"],
                    "shortlisted": int(item["candidate_index"]) in selection_rank_by_candidate_index,
                    "selection_rank": selection_rank_by_candidate_index.get(int(item["candidate_index"])),
                    "runtime_executed": int(item["candidate_index"]) in selection_rank_by_candidate_index,
                    "shape_assessment": item["feature_report"].get("shape_assessment", {}),
                }
                for item in candidate_records
            ],
            "runtime_candidate_limit": runtime_candidate_limit,
            "ranked_candidate_count": len(ranked_records),
            "fidelity": fidelity.to_dict(),
            "signature": dict(first_ir.signature),
            "blueprint_id": first_ir.blueprint_id,
            "primitives_used": list(first_ir.primitives_used),
            "shape_assessment": dict(first_ir.assessment),
            "repairs": repairs,
            "authoritative_candidate_reason": (
                "native_assembly_blueprint_with_grammar_program"
                if feature_reports and isinstance(feature_reports[0].get("grammar_program"), dict)
                else "native_assembly_blueprint"
            ),
            "geometry_kernel": geometry_kernel_id,
            "game_pipeline_hints": _game_pipeline_hints(asset_graph, first_ir),
        },
    }
