"""Internal executable geometry-kernel program.

This module is the narrow seam between Lathe construction intent and concrete
kernel calls. It does not change the public shape handoff contract; it gives
the shape stage a reusable way to execute and trace ordered boolean programs
against any object that satisfies ``GeometryKernel``.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from contextlib import suppress
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import trimesh

from ..kernel import GeometryKernel
from ._core import (
    KernelOperand,
    KernelProgramCapabilityError,
    KernelProgramResult,
    _capability_names,
    _exact_rebuild_required_capabilities,
    _required_capability_list,
    boolean_kernel_call_count,
    boolean_operation_count,
    carve_operation_count,
    component_assembly_operation_count,
    deform_operation_count,
    hull_operation_count,
    import_operation_count,
    instances_operation_count,
    minkowski_operation_count,
    polyextrude_operation_count,
    profile_path_operation_count,
    refine_operation_count,
    sdf_field_operation_count,
    terrain_field_operation_count,
    transform_operation_count,
)
from ._serialize import (
    _compact_face_operation_ids,
    _compact_kernel_handoff_value,
    _compact_kernel_program_payload,
    _compact_kernel_result_metadata,
    _compact_kernel_semantic_handoff,
    _compact_semantic_metadata_record,
    _compact_shape_record_summary,
    _compact_source_shape_record,
    _dict_metadata,
    _stable_unique_strings,
)
from ._capabilities import (
    _SUPPORTED_BLEND_MODES,
    _kernel_capabilities,
    _require_capabilities,
    _required_boolean_capabilities,
    _validate_hull_operands,
    _validate_minkowski_operands,
    _validate_operands,
    _validate_transform_operand,
    _validated_transform_matrix,
)

KERNEL_PROGRAM_VERSION = "lathe.geometry.kernel_program_v1"


def semantic_metadata_from_primitive(primitive: Any) -> dict[str, Any]:
    """Extract serializable construction metadata for KernelProgram traces."""
    metadata: dict[str, Any] = {}
    for name in ("component", "region"):
        value = getattr(primitive, name, None)
        if value:
            metadata[name] = str(value)
    for name in (
        "boolean_seam_groups",
        "bevel_seam_groups",
        "hard_edge_groups",
    ):
        value = getattr(primitive, name, None)
        if value:
            metadata[name] = [dict(item) if isinstance(item, dict) else item for item in value]
    modifier_items = [
        (name, value)
        for name, value in vars(primitive).items()
        if isinstance(name, str)
        and name.startswith("v2_")
        and name.endswith("_modifier")
        and value not in (None, "", (), [], {})
    ]
    for name, value in modifier_items:
        if value:
            metadata[name] = dict(value) if isinstance(value, dict) else value
    extra = getattr(primitive, "semantic_metadata", None)
    if isinstance(extra, dict) and extra:
        metadata["semantic_metadata"] = _compact_kernel_handoff_value(extra)
    if getattr(primitive, "primitive_type", None) == "component_assembly":
        assembly_primitives = _component_assembly_records_from_primitive(primitive)
        if assembly_primitives:
            metadata["assembly_primitives"] = assembly_primitives
            metadata["component_assembly"] = _component_assembly_summary_from_records(
                primitive,
                assembly_primitives,
            )
    return metadata


def _copy_kernel_import_stats(stats: dict[str, Any], kernel_import: dict[str, Any]) -> None:
    if not kernel_import:
        return
    stats["kernel_import_route"] = str(kernel_import.get("route") or "")
    stats["kernel_import_backend"] = str(kernel_import.get("backend") or "")
    stats["kernel_import_primitive_type"] = str(kernel_import.get("primitive_type") or "")
    stats["kernel_import_succeeded"] = bool(kernel_import.get("succeeded", False))
    for text_key in (
        "internal_build_route",
        "actual_construction_backend",
    ):
        if kernel_import.get(text_key) not in (None, "", (), [], {}):
            stats[text_key] = str(kernel_import.get(text_key) or "")
    for list_key in (
        "construction_backends",
        "kernel_assisted_backends",
        "construction_methods",
        "construction_trace",
    ):
        value = kernel_import.get(list_key)
        if isinstance(value, list):
            stats[list_key] = [dict(item) if isinstance(item, dict) else item for item in value]
    if isinstance(kernel_import.get("construction_trace_count"), (int, float)):
        stats["construction_trace_count"] = int(kernel_import["construction_trace_count"])
    for bool_key in (
        "construction_fallback",
        "construction_passthrough",
        "construction_geometry_applied",
    ):
        if bool_key in kernel_import:
            stats[bool_key] = bool(kernel_import.get(bool_key))
    build_attempt = _dict_metadata(kernel_import.get("build_primitive_attempt"))
    if build_attempt:
        stats["kernel_build_primitive_attempt"] = dict(build_attempt)


_FEATURE_DETAIL_MODIFIER_KINDS: dict[str, str] = {
    "v2_boolean_modifier": "boolean",
    "v2_bracket_modifier": "support_bracket",
    "v2_branching_tree_modifier": "branching_tree",
    "v2_capsule_modifier": "capsule",
    "v2_corner_guard_set_modifier": "corner_guard_set",
    "v2_countersunk_hole_modifier": "countersunk_hole",
    "v2_countersunk_hole_set_modifier": "countersunk_hole_set",
    "v2_carve_modifier": "carve",
    "v2_cga_facade_modifier": "cga_facade",
    "v2_component_assembly_transform_modifier": "component_assembly_transform",
    "v2_context_aggregate_modifier": "context_aggregate",
    "v2_cut_panel_line_modifier": "panel_line_cut",
    "v2_curved_tube_modifier": "curved_tube",
    "v2_curve_loft_modifier": "curve_loft",
    "v2_curve_profile_modifier": "curve_profile",
    "v2_curve_sweep_modifier": "curve_sweep",
    "v2_deform_modifier": "deform",
    "v2_extrude_modifier": "extrude",
    "v2_fastener_grid_modifier": "fastener_grid",
    "v2_flange_modifier": "flange",
    "v2_gear_modifier": "gear",
    "v2_handle_modifier": "handle",
    "v2_helical_sweep_modifier": "helical_sweep",
    "v2_hinge_modifier": "hinge",
    "v2_hull_modifier": "hull",
    "v2_inset_modifier": "inset",
    "v2_ladder_frame_modifier": "ladder_frame",
    "v2_loft_modifier": "loft",
    "v2_louver_panel_modifier": "louver_panel",
    "v2_minkowski_modifier": "minkowski",
    "v2_mount_plate_modifier": "mount_plate",
    "v2_output_materialize_modifier": "output_materialize",
    "v2_panel_frame_modifier": "panel_frame",
    "v2_panel_modifier": "panel",
    "v2_perforated_panel_modifier": "perforated_panel",
    "v2_polywire_modifier": "polywire",
    "v2_polyextrude_exact_mesh_modifier": "polyextrude_exact_mesh",
    "v2_polyextrude_modifier": "polyextrude",
    "v2_prism_modifier": "prism",
    "v2_rail_modifier": "rail",
    "v2_record_materialize_modifier": "record_materialize",
    "v2_ribbed_panel_modifier": "ribbed_panel",
    "v2_rounded_slot_modifier": "rounded_slot",
    "v2_remesh_modifier": "remesh",
    "v2_sdf_metaball_cluster_modifier": "sdf_metaball_cluster",
    "v2_shell_modifier": "shell",
    "v2_sop_boolean_modifier": "sop_boolean",
    "v2_socket_modifier": "socket",
    "v2_spring_modifier": "spring",
    "v2_structural_beam_modifier": "structural_beam",
    "v2_subdivision_modifier": "subdivision",
    "v2_sweep_modifier": "sweep",
    "v2_tessellation_modifier": "tessellation",
    "v2_terrain_patch_modifier": "terrain_patch",
    "v2_threaded_cylinder_modifier": "threaded_cylinder",
    "v2_transform_modifier": "transform",
    "v2_trim_band_modifier": "trim_band",
    "v2_tube_modifier": "tube",
    "v2_truss_frame_modifier": "truss_frame",
    "v2_vent_slats_modifier": "vent_slats",
    "v2_weld_seam_modifier": "weld_seam",
    "v2_wfc_modular_assembly_modifier": "wfc_modular_assembly",
}
_FEATURE_DETAIL_OPERATION_KINDS: dict[str, str] = {
    "solid.branching_tree": "branching_tree",
    "solid.capsule": "capsule",
    "solid.cga_facade": "cga_facade",
    "solid.curve_extruded_profile": "curve_extruded_profile",
    "solid.curve_lofted_solid": "curve_loft",
    "solid.curve_revolved_profile": "curve_revolved_profile",
    "solid.curve_swept_profile": "curve_sweep",
    "solid.extruded_profile": "extruded_profile",
    "solid.flange": "flange",
    "solid.curved_tube": "curved_tube",
    "solid.gear": "gear",
    "solid.handle": "handle",
    "solid.hinge": "hinge",
    "solid.ladder_frame": "ladder_frame",
    "solid.louver_panel": "louver_panel",
    "solid.perforated_panel": "perforated_panel",
    "solid.prism": "prism",
    "solid.rail": "rail",
    "solid.revolved_profile": "revolved_profile",
    "solid.ribbed_panel": "ribbed_panel",
    "solid.sdf_metaball_cluster": "sdf_metaball_cluster",
    "solid.spring": "spring",
    "solid.structural_beam": "structural_beam",
    "solid.swept_profile": "swept_profile",
    "solid.terrain_patch": "terrain_patch",
    "solid.threaded_cylinder": "threaded_cylinder",
    "solid.truss_frame": "truss_frame",
    "solid.tube": "tube",
    "solid.wfc_modular_assembly": "wfc_modular_assembly",
    "op.bracket": "support_bracket",
    "op.corner_guard_set": "corner_guard_set",
    "op.countersunk_hole": "countersunk_hole",
    "op.cut_panel_line": "panel_line_cut",
    "op.distribute": "distribute",
    "op.extrude": "extrude",
    "op.fastener_grid": "fastener_grid",
    "op.hull": "hull",
    "op.inset": "inset",
    "op.mark_hard_edge": "mark_hard_edge",
    "op.mirror": "mirror",
    "op.minkowski": "minkowski",
    "op.mount_plate": "mount_plate",
    "op.panel_frame": "panel_frame",
    "op.repeat": "repeat",
    "op.rounded_slot": "rounded_slot",
    "op.shell": "shell",
    "op.intersect": "boolean_intersection",
    "op.subtract": "boolean_cut",
    "op.socket": "socket",
    "op.trim_band": "trim_band",
    "op.union": "boolean_union",
    "op.vent_slats": "vent_slats",
    "op.weighted_normals": "weighted_normals",
    "op.weld_seam": "weld_seam",
    "sop.boolean": "boolean",
    "sop.carve": "carve",
    "sop.copy_to_points": "copy_to_points",
    "sop.helical_sweep": "helical_sweep",
    "sop.loft": "loft",
    "sop.polyextrude": "polyextrude",
    "sop.polywire": "polywire",
    "sop.remesh": "remesh",
    "sop.scatter_on_surface": "surface_scatter",
    "sop.subdivide": "subdivision",
    "sop.sweep": "sweep",
    "sop.taper": "taper",
    "sop.transform": "transform",
    "sop.twist": "twist",
    "sop.bend": "bend",
}
_PATTERN_INSTANCE_MODIFIER_KINDS: dict[str, str] = {
    "v2_copy_to_points_modifier": "copy_to_points",
    "v2_distribution_modifier": "distribute",
    "v2_mirror_modifier": "mirror",
    "v2_repeat_modifier": "repeat",
    "v2_surface_scatter_modifier": "surface_scatter",
}
_PATTERN_INSTANCE_OPERATION_KINDS: dict[str, str] = {
    "op.distribute": "distribute",
    "op.mirror": "mirror",
    "op.repeat": "repeat",
    "sop.copy_to_points": "copy_to_points",
    "sop.scatter_on_surface": "surface_scatter",
}

_MODIFIER_OPERATION_DEFAULTS: dict[str, str] = {
    "branching_tree": "solid.branching_tree",
    "boolean": "sop.boolean",
    "bracket": "op.bracket",
    "carve": "sop.carve",
    "capsule": "solid.capsule",
    "cga_facade": "solid.cga_facade",
    "chip_edges": "op.chip_edges",
    "component_assembly_transform": "op.transform",
    "context_aggregate": "source_context.aggregate",
    "copy_to_points": "sop.copy_to_points",
    "corner_guard_set": "op.corner_guard_set",
    "countersunk_hole": "op.countersunk_hole",
    "countersunk_hole_set": "op.countersunk_hole_set",
    "curved_tube": "solid.curved_tube",
    "curve_loft": "solid.curve_lofted_solid",
    "curve_profile": "solid.curve_profile",
    "curve_sweep": "solid.curve_swept_profile",
    "cut_panel_line": "op.cut_panel_line",
    "deform": "sop.deform",
    "dent_mask": "op.dent_mask",
    "distribution": "op.distribute",
    "extrude": "op.extrude",
    "fastener_grid": "op.fastener_grid",
    "flange": "solid.flange",
    "gear": "solid.gear",
    "grime_mask": "op.grime_mask",
    "handle": "solid.handle",
    "helical_sweep": "sop.helical_sweep",
    "hinge": "solid.hinge",
    "hull": "op.hull",
    "inset": "op.inset",
    "ladder_frame": "solid.ladder_frame",
    "loft": "sop.loft",
    "louver_panel": "solid.louver_panel",
    "mark_hard_edge": "op.mark_hard_edge",
    "minkowski": "op.minkowski",
    "mirror": "op.mirror",
    "mount_plate": "op.mount_plate",
    "output_materialize": "shape_ir_v2.output_materialize",
    "panel": "op.panel",
    "panel_frame": "op.panel_frame",
    "perforated_panel": "solid.perforated_panel",
    "polybevel": "sop.polybevel",
    "polyextrude": "sop.polyextrude",
    "polyextrude_exact_mesh": "sop.polyextrude",
    "polywire": "sop.polywire",
    "prism": "solid.prism",
    "rail": "solid.rail",
    "record_materialize": "op.record_materialize",
    "remesh": "sop.remesh",
    "repeat": "op.repeat",
    "ribbed_panel": "solid.ribbed_panel",
    "rounded_slot": "op.rounded_slot",
    "sdf_metaball_cluster": "solid.sdf_metaball_cluster",
    "scratch_mask": "op.scratch_mask",
    "shell": "op.shell",
    "socket": "op.socket",
    "sop_boolean": "sop.boolean",
    "spring": "solid.spring",
    "structural_beam": "solid.structural_beam",
    "subdivision": "sop.subdivide",
    "surface_scatter": "sop.scatter_on_surface",
    "sweep": "sop.sweep",
    "terrain_patch": "solid.terrain_patch",
    "threaded_cylinder": "solid.threaded_cylinder",
    "transform": "op.transform",
    "trim_band": "op.trim_band",
    "tube": "solid.tube",
    "truss_frame": "solid.truss_frame",
    "vent_slats": "op.vent_slats",
    "weighted_normals": "op.weighted_normals",
    "weld_seam": "op.weld_seam",
    "wfc_modular_assembly": "solid.wfc_modular_assembly",
}
_SURFACE_DAMAGE_MODIFIER_KINDS: dict[str, str] = {
    "v2_chip_edges_modifier": "edge_chip",
    "v2_dent_mask_modifier": "dent",
    "v2_grime_mask_modifier": "grime",
    "v2_scratch_mask_modifier": "scratch",
}
_SURFACE_DAMAGE_OPERATION_KINDS: dict[str, str] = {
    "op.chip_edges": "edge_chip",
    "op.dent_mask": "dent",
    "op.grime_mask": "grime",
    "op.scratch_mask": "scratch",
}
_EDGE_TREATMENT_OPERATION_KINDS: dict[str, str] = {
    "op.bevel": "bevel",
    "op.chamfer": "chamfer",
    "sop.polybevel": "polybevel",
}
_ASSEMBLY_RECORD_COPY_KEYS = (
    "primitive_type",
    "part",
    "component",
    "region",
    "blend_mode",
    "center",
    "axis",
    "tags",
    "v2_op",
    "v2_source_op",
    "v2_purpose",
    "v2_context_aggregate",
    "v2_context_parts",
    "v2_context_record_count",
    "v2_context_primitive_types",
    "assembly_kind",
)
_ASSEMBLY_RECORD_LIMIT = 128
_ASSEMBLY_RECORD_DEPTH_LIMIT = 4


def _operation_id_fragment(value: str) -> str:
    return "".join(char if char.isalnum() else "_" for char in value).strip("_") or "operation"


def _modifier_operation_default(modifier_name: str) -> str:
    token = str(modifier_name or "").strip()
    if token.startswith("v2_"):
        token = token[3:]
    if token.endswith("_modifier"):
        token = token[:-9]
    return _MODIFIER_OPERATION_DEFAULTS.get(token, f"modifier.{token or 'unknown'}")


def _modifier_payload_operation(
    modifier_name: str,
    payload: dict[str, Any],
    *,
    base_operation: str = "",
) -> str:
    return str(
        payload.get("v2_op")
        or payload.get("operation")
        or base_operation
        or _modifier_operation_default(modifier_name)
    )


def _operand_modifier_payloads(metadata: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    payloads: list[tuple[str, dict[str, Any]]] = []
    seen: set[tuple[str, str, str]] = set()
    for container in _kernel_modifier_payload_containers(metadata):
        for name, value in container.items():
            if not (
                isinstance(name, str)
                and name.startswith("v2_")
                and name.endswith("_modifier")
            ):
                continue
            payload = _dict_metadata(value)
            if not payload:
                continue
            key = (
                name,
                str(payload.get("operation_id") or ""),
                str(payload.get("method") or payload.get("operation") or ""),
            )
            if key in seen:
                continue
            seen.add(key)
            payloads.append((name, payload))
    return payloads


def _record_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        try:
            converted = to_dict()
        except (TypeError, ValueError, RuntimeError):
            return {}
        return converted if isinstance(converted, dict) else {}
    return {}


def _shape_record_v2_metadata(record: dict[str, Any]) -> dict[str, Any]:
    semantic_metadata = _dict_metadata(record.get("semantic_metadata"))
    return _dict_metadata(semantic_metadata.get("shape_ir_v2"))


def _shape_record_operation(record: dict[str, Any]) -> tuple[str, str, str]:
    v2_metadata = _shape_record_v2_metadata(record)
    operation = str(
        v2_metadata.get("v2_op")
        or record.get("v2_op")
        or record.get("operation")
        or ""
    )
    operation_id = str(v2_metadata.get("operation_id") or record.get("operation_id") or "")
    repair_action = str(v2_metadata.get("repair_action") or record.get("repair_action") or "")
    return operation, operation_id, repair_action


def _compact_component_assembly_record(
    raw_record: Any,
    *,
    depth: int = 0,
    remaining: list[int] | None = None,
) -> dict[str, Any]:
    record = _record_dict(raw_record)
    if not record or depth > _ASSEMBLY_RECORD_DEPTH_LIMIT:
        return {}
    if remaining is None:
        remaining = [_ASSEMBLY_RECORD_LIMIT]
    if remaining[0] <= 0:
        return {}
    remaining[0] -= 1

    compact: dict[str, Any] = {}
    for key in _ASSEMBLY_RECORD_COPY_KEYS:
        value = record.get(key)
        if value not in (None, "", (), [], {}):
            compact[key] = _json_safe(value)
    v2_metadata = _shape_record_v2_metadata(record)
    if v2_metadata:
        compact["semantic_metadata"] = {"shape_ir_v2": _json_safe(v2_metadata)}
    children = record.get("assembly_primitives")
    if isinstance(children, list) and depth < _ASSEMBLY_RECORD_DEPTH_LIMIT:
        compact_children = [
            child
            for child in (
                _compact_component_assembly_record(
                    item,
                    depth=depth + 1,
                    remaining=remaining,
                )
                for item in children
            )
            if child
        ]
        if compact_children:
            compact["assembly_primitives"] = compact_children
    return compact


def _component_assembly_records_from_primitive(primitive: Any) -> list[dict[str, Any]]:
    raw_records = getattr(primitive, "assembly_primitives", None)
    if not isinstance(raw_records, list):
        return []
    remaining = [_ASSEMBLY_RECORD_LIMIT]
    records = [
        compact
        for compact in (
            _compact_component_assembly_record(item, remaining=remaining)
            for item in raw_records
        )
        if compact
    ]
    return records


def _component_assembly_summary_from_records(
    primitive: Any,
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    primitive_types: list[Any] = []
    components: list[Any] = []
    regions: list[Any] = []
    operations: list[Any] = []

    def walk(record: dict[str, Any]) -> None:
        primitive_types.append(record.get("primitive_type"))
        components.append(record.get("component"))
        regions.append(record.get("region"))
        operation, _operation_id, _repair_action = _shape_record_operation(record)
        if operation:
            operations.append(operation)
        for child in record.get("assembly_primitives") or []:
            if isinstance(child, dict):
                walk(child)

    for record in records:
        walk(record)
    return {
        "schema": "lathe.geometry.component_assembly_semantic_summary.v1",
        "assembly_kind": str(getattr(primitive, "assembly_kind", None) or ""),
        "component_count": len(records),
        "component_primitive_types": _stable_unique_strings(primitive_types),
        "components": _stable_unique_strings(components),
        "regions": _stable_unique_strings(regions),
        "source_operations": _stable_unique_strings(operations),
        "truncated": _ASSEMBLY_RECORD_LIMIT <= _flattened_assembly_record_count(records),
    }


def _component_operand_semantic_summary(operands: list[KernelOperand]) -> dict[str, Any]:
    components: list[Any] = []
    regions: list[Any] = []
    assembly_kinds: list[Any] = []
    component_sources: list[Any] = []
    cga_terminals: list[Any] = []
    cga_terminal_param_keys: list[Any] = []
    cga_parametric_terminal_count = 0
    nested_component_count = 0
    for operand in operands:
        metadata = _dict_metadata(operand.metadata)
        semantic_metadata = _dict_metadata(metadata.get("semantic_metadata"))
        components.append(metadata.get("component"))
        regions.append(metadata.get("region"))
        component_sources.append(semantic_metadata.get("component_source"))
        cga = _dict_metadata(semantic_metadata.get("cga_rule_component"))
        cga_terminals.append(cga.get("terminal"))
        terminal_params = _dict_metadata(cga.get("terminal_params"))
        if terminal_params:
            cga_parametric_terminal_count += 1
            cga_terminal_param_keys.extend(terminal_params.keys())
        component_assembly = _dict_metadata(metadata.get("component_assembly"))
        if component_assembly:
            assembly_kinds.append(component_assembly.get("assembly_kind"))
            with suppress(TypeError, ValueError):
                nested_component_count += int(component_assembly.get("component_count") or 0)
    component_names = _stable_unique_strings(components)
    region_names = _stable_unique_strings(regions)
    kind_names = _stable_unique_strings(assembly_kinds)
    source_names = _stable_unique_strings(component_sources)
    terminal_names = _stable_unique_strings(cga_terminals)
    payload: dict[str, Any] = {}
    if component_names:
        payload["source_components"] = component_names
        payload["source_component_counts"] = {
            component: sum(
                1
                for operand in operands
                if str(_dict_metadata(operand.metadata).get("component") or "") == component
            )
            for component in component_names
        }
    if region_names:
        payload["source_regions"] = region_names
    if kind_names:
        payload["nested_assembly_kinds"] = kind_names
    if source_names:
        payload["component_sources"] = source_names
    if terminal_names:
        payload["cga_terminals"] = terminal_names
    if cga_parametric_terminal_count:
        payload["cga_parametric_terminal_count"] = int(cga_parametric_terminal_count)
        payload["cga_terminal_param_keys"] = _stable_unique_strings(cga_terminal_param_keys)
    if nested_component_count:
        payload["nested_component_count"] = int(nested_component_count)
    return payload


def _flattened_assembly_record_count(records: list[dict[str, Any]]) -> int:
    total = 0
    for record in records:
        total += 1
        children = record.get("assembly_primitives")
        if isinstance(children, list):
            total += _flattened_assembly_record_count(
                [child for child in children if isinstance(child, dict)]
            )
    return total


def _shape_record_operation_records(
    records: list[dict[str, Any]],
    operand: KernelOperand,
    operand_index: int,
    *,
    source: str,
    path_prefix: str,
) -> list[dict[str, Any]]:
    operation_records: list[dict[str, Any]] = []

    def walk(record: dict[str, Any], path: tuple[int, ...]) -> None:
        operation, operation_id, repair_action = _shape_record_operation(record)
        if operation or operation_id or repair_action:
            path_fragment = "_".join(f"{index:02d}" for index in path) or "root"
            operation_text = operation or repair_action or "shape_record"
            operation_records.append(
                {
                    "operation_id": operation_id
                    or (
                        f"operand:{operand_index:04d}:{path_prefix}:"
                        f"{path_fragment}:{_operation_id_fragment(operation_text)}"
                    ),
                    "operation": operation,
                    "repair_action": repair_action,
                    "operand_id": operand.operand_id,
                    "operand_index": operand_index,
                    "part": str(record.get("part") or operand.part or ""),
                    "primitive_type": str(
                        record.get("primitive_type") or operand.primitive_type or ""
                    ),
                    "blend_mode": str(record.get("blend_mode") or operand.blend_mode or ""),
                    "source": source,
                    "source_record_path": list(path),
                    "source_record_component": str(record.get("component") or ""),
                    "source_record_region": str(record.get("region") or ""),
                    "component_assembly_kind": str(record.get("assembly_kind") or ""),
                }
            )
        children = record.get("assembly_primitives")
        if not isinstance(children, list):
            return
        for child_index, child in enumerate(children):
            if isinstance(child, dict):
                walk(child, (*path, child_index))

    for index, record in enumerate(records):
        if isinstance(record, dict):
            walk(record, (index,))
    return operation_records


def _operand_operation_records(operands: list[KernelOperand]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for index, operand in enumerate(operands):
        metadata = _dict_metadata(operand.metadata)
        semantic_metadata = _dict_metadata(metadata.get("semantic_metadata"))
        v2_metadata = _dict_metadata(semantic_metadata.get("shape_ir_v2"))
        repair_metadata = _dict_metadata(semantic_metadata.get("semantic_repair"))
        operation = (
            v2_metadata.get("v2_op")
            or repair_metadata.get("lowered_operation")
            or semantic_metadata.get("operation")
        )
        repair_action = repair_metadata.get("action") or v2_metadata.get("repair_action")
        operation_id = (
            v2_metadata.get("operation_id")
            or repair_metadata.get("operation_id")
            or semantic_metadata.get("operation_id")
        )
        surface_scatter = _dict_metadata(semantic_metadata.get("surface_scatter"))
        point_scatter = _dict_metadata(semantic_metadata.get("point_scatter"))
        if any((operation, repair_action, operation_id)):
            op_text = str(operation or repair_action or "operand")
            record = {
                "operation_id": str(
                    operation_id
                    or f"operand:{index:04d}:{_operation_id_fragment(op_text)}"
                ),
                "operation": str(operation or ""),
                "repair_action": str(repair_action or ""),
                "operand_id": operand.operand_id,
                "operand_index": index,
                "part": operand.part or "",
                "primitive_type": operand.primitive_type or "",
                "blend_mode": operand.blend_mode,
                "source": "kernel_operand.semantic_metadata",
            }
            if surface_scatter:
                record["surface_scatter"] = surface_scatter
            if point_scatter:
                record["point_scatter"] = point_scatter
            records.append(record)
        elif "feature" in operand.tags:
            component = str(metadata.get("component") or operand.primitive_type or "feature")
            authoring_feature = _dict_metadata(semantic_metadata.get("authoring_feature"))
            records.append(
                {
                    "operation_id": f"operand:{index:04d}:feature_{_operation_id_fragment(component)}",
                    "operation": f"feature.{component}",
                    "repair_action": "",
                    "operand_id": operand.operand_id,
                    "operand_index": index,
                    "part": operand.part or "",
                    "primitive_type": operand.primitive_type or "",
                    "blend_mode": operand.blend_mode,
                    "source": "kernel_operand.feature_component",
                    "authoring_feature_density": str(authoring_feature.get("feature_density") or ""),
                    "authoring_filter_state": str(authoring_feature.get("filter_state") or ""),
                }
            )
        for modifier_name, modifier in _operand_modifier_payloads(metadata):
            modifier_operation = _modifier_operation_default(modifier_name)
            record = {
                "operation_id": str(
                    modifier.get("operation_id")
                    or f"operand:{index:04d}:{_operation_id_fragment(modifier_operation)}"
                ),
                "operation": str(
                    modifier.get("v2_op")
                    or modifier.get("operation")
                    or modifier_operation
                ),
                "repair_action": str(repair_action or ""),
                "operand_id": operand.operand_id,
                "operand_index": index,
                "part": operand.part or "",
                "primitive_type": operand.primitive_type or "",
                "blend_mode": operand.blend_mode,
                "source": modifier_name,
            }
            for key in (
                "method",
                "actual_method",
                "actual_backend",
                "actual_geometry_backend",
                "result_face_count",
                "result_vertex_count",
                "result_watertight",
                "source_face_count",
                "source_vertex_count",
            ):
                if key in modifier:
                    record[key] = _json_safe(modifier[key])
            records.append(record)
        assembly_records = [
            dict(item)
            for item in metadata.get("assembly_primitives", [])
            if isinstance(item, dict)
        ]
        if assembly_records:
            records.extend(
                _shape_record_operation_records(
                    assembly_records,
                    operand,
                    index,
                    source="kernel_operand.component_assembly_child",
                    path_prefix="assembly",
                )
            )
        elif isinstance(semantic_metadata.get("source_shape_primitives"), list):
            source_records = [
                dict(item)
                for item in semantic_metadata.get("source_shape_primitives", [])
                if isinstance(item, dict)
            ]
            records.extend(
                _shape_record_operation_records(
                    source_records,
                    operand,
                    index,
                    source="kernel_operand.source_shape_primitive",
                    path_prefix="source",
                )
            )
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for record in records:
        key = (
            str(record.get("operation_id") or ""),
            str(record.get("operation") or ""),
            str(record.get("operand_id") or ""),
            str(record.get("source") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(record)
    return deduped


def _operation_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        operation = str(record.get("operation") or record.get("repair_action") or "")
        if not operation:
            continue
        counts[operation] = counts.get(operation, 0) + 1
    return dict(sorted(counts.items()))


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _semantic_operation_records_from_manifest(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    records = manifest.get("semantic_operation_records")
    if not isinstance(records, list):
        return []
    return [dict(record) for record in records if isinstance(record, dict)]


def _dedupe_operation_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for record in records:
        key = (
            str(record.get("operation_id") or ""),
            str(record.get("operation") or ""),
            str(record.get("operand_id") or ""),
            str(record.get("source") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(dict(record))
    return deduped


def _final_semantic_operation_record(
    records: list[dict[str, Any]],
    semantic_operation: str,
) -> dict[str, Any]:
    clean_records = [dict(record) for record in records if isinstance(record, dict)]
    operation = str(semantic_operation or "")
    if operation:
        for record in reversed(clean_records):
            if str(record.get("operation") or "") == operation:
                return record
    return clean_records[-1] if clean_records else {}


def _final_semantic_operation_face_id(
    records: list[dict[str, Any]],
    semantic_operation: str,
    *,
    fallback: str,
) -> tuple[str, dict[str, Any]]:
    record = _final_semantic_operation_record(records, semantic_operation)
    operation_id = str(record.get("operation_id") or "")
    return operation_id or str(fallback), record


def _semantic_operation_for_kind(
    records: list[dict[str, Any]],
    operation_kinds: dict[str, str],
    *,
    fallback: str = "",
) -> str:
    fallback_text = str(fallback or "")
    if fallback_text in operation_kinds:
        return fallback_text
    for record in reversed(records):
        operation = str(record.get("operation") or "")
        if operation in operation_kinds:
            return operation
    return fallback_text


def _trace_semantic_operation_records(trace_operations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for operation_index, operation in enumerate(trace_operations):
        if not isinstance(operation, dict):
            continue
        record = operation.get("semantic_operation_record")
        if not isinstance(record, dict):
            continue
        copied = dict(record)
        copied.setdefault("source", "kernel_program.trace_operation")
        copied.setdefault("trace_operation_index", int(operation_index))
        records.append(copied)
    return records


def _metadata_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _copy_source_context_summary(
    record: dict[str, Any],
    context_source: Any,
) -> None:
    source = _dict_metadata(context_source)
    if not source:
        return
    raw_count = (
        source.get("v2_context_record_count")
        or source.get("context_record_count")
        or 0
    )
    has_context = bool(
        source.get("v2_context_aggregate")
        or source.get("context_aggregate")
        or raw_count
    )
    if not has_context:
        return
    with suppress(TypeError, ValueError):
        record.setdefault("source_context_record_count", int(raw_count or 1))
    context_parts = _stable_unique_strings(
        source.get("v2_context_parts") or source.get("context_parts") or []
    )
    if context_parts:
        existing_parts = record.get("source_context_parts") or []
        record["source_context_parts"] = _stable_unique_strings(
            [*existing_parts, *context_parts]
        )
    context_primitive_types = _stable_unique_strings(
        source.get("v2_context_primitive_types")
        or source.get("context_primitive_types")
        or []
    )
    if context_primitive_types:
        existing_types = record.get("source_context_primitive_types") or []
        record["source_context_primitive_types"] = _stable_unique_strings(
            [*existing_types, *context_primitive_types]
        )


def _kernel_program_face_operation_summary(
    face_operation_ids: list[str],
    *,
    source: str,
) -> dict[str, Any]:
    operations = {
        operation_id: face_operation_ids.count(operation_id)
        for operation_id in sorted(set(face_operation_ids))
    }
    return {
        "schema": "lathe.mesh_ir.face_operation_summary.v1",
        "face_count": len(face_operation_ids),
        "operation_count": len(operations),
        "operations": operations,
        "source": source,
    }


def _instance_face_operation_ids(
    instance_operands: list[KernelOperand],
    instance_meshes: list[trimesh.Trimesh],
    result_mesh: trimesh.Trimesh,
    *,
    assembly_method: str,
) -> list[str]:
    if not instance_operands:
        return []
    method = str(assembly_method or "")
    if method != "single_transform" and "mesh_concatenation" not in method:
        return []
    face_operation_ids: list[str] = []
    for operand, instance_mesh in zip(instance_operands, instance_meshes):
        if not isinstance(instance_mesh, trimesh.Trimesh):
            return []
        metadata = getattr(instance_mesh, "metadata", None)
        source_face_operation_ids = (
            metadata.get("face_operation_ids")
            if isinstance(metadata, dict)
            else None
        )
        if (
            isinstance(source_face_operation_ids, list)
            and len(source_face_operation_ids) == len(instance_mesh.faces)
        ):
            face_operation_ids.extend(
                str(operation_id) for operation_id in source_face_operation_ids
            )
            continue
        face_operation_ids.extend([operand.operand_id] * len(instance_mesh.faces))
    if len(face_operation_ids) != len(result_mesh.faces):
        return []
    return face_operation_ids


def _attach_direct_face_operation_metadata(
    mesh: trimesh.Trimesh,
    operation_id: str,
    *,
    source: str,
    method: str,
) -> tuple[list[str], dict[str, Any], dict[str, Any]]:
    face_operation_ids = [str(operation_id)] * len(mesh.faces)
    face_operation_summary = _kernel_program_face_operation_summary(
        face_operation_ids,
        source=source,
    )
    face_operation_attribution = {
        "schema": "lathe.geometry.kernel_program_face_operation_attribution.v1",
        "source": source,
        "attributed": True,
        "method": method,
        "result_face_count": len(mesh.faces),
        "face_operation_count": 1 if face_operation_ids else 0,
        "face_operation_attribution_count": len(face_operation_ids),
    }
    mesh.metadata["face_operation_ids"] = list(face_operation_ids)
    mesh.metadata["face_operation_summary"] = dict(face_operation_summary)
    mesh.metadata["lathe_kernel_program_face_operation_attribution"] = dict(
        face_operation_attribution
    )
    return face_operation_ids, face_operation_summary, face_operation_attribution


def _attach_whole_result_face_operation_metadata(
    mesh: trimesh.Trimesh,
    operation_id: str,
    *,
    source: str,
    method: str,
    reason: str,
    source_face_ranges_preserved: bool = False,
    extra: dict[str, Any] | None = None,
) -> tuple[list[str], dict[str, Any], dict[str, Any]]:
    face_operation_ids, face_operation_summary, face_operation_attribution = (
        _attach_direct_face_operation_metadata(
            mesh,
            operation_id,
            source=source,
            method=method,
        )
    )
    face_operation_attribution = {
        **dict(face_operation_attribution),
        "attribution_scope": "whole_result_operation",
        "source_face_ranges_preserved": bool(source_face_ranges_preserved),
        "reason": reason,
    }
    if extra:
        face_operation_attribution.update(_json_safe(extra))
    mesh.metadata["lathe_kernel_program_face_operation_attribution"] = dict(
        face_operation_attribution
    )
    return face_operation_ids, face_operation_summary, face_operation_attribution


def _attach_semantic_whole_result_face_metadata(
    mesh: trimesh.Trimesh,
    operation_records: list[dict[str, Any]],
    semantic_operation: str,
    *,
    source: str,
    method: str,
    reason: str,
    extra: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[str], dict[str, Any], dict[str, Any]]:
    final_operation_record = _final_semantic_operation_record(
        operation_records,
        semantic_operation,
    )
    face_operation_ids: list[str] = []
    face_operation_summary: dict[str, Any] = {}
    face_operation_attribution: dict[str, Any] = {
        "schema": "lathe.geometry.kernel_program_face_operation_attribution.v1",
        "source": source,
        "attributed": False,
        "method": method,
        "result_face_count": len(mesh.faces),
        "reason": reason,
    }
    final_operation_id = str(final_operation_record.get("operation_id") or "")
    if final_operation_id:
        (
            face_operation_ids,
            face_operation_summary,
            face_operation_attribution,
        ) = _attach_whole_result_face_operation_metadata(
            mesh,
            final_operation_id,
            source=source,
            method=method,
            reason=reason,
            extra=extra,
        )
    else:
        if extra:
            face_operation_attribution.update(_json_safe(extra))
        mesh.metadata["lathe_kernel_program_face_operation_attribution"] = dict(
            face_operation_attribution
        )
    return (
        final_operation_record,
        face_operation_ids,
        face_operation_summary,
        face_operation_attribution,
    )


def _operand_semantic_records(operand: KernelOperand, index: int) -> dict[str, Any]:
    metadata = _dict_metadata(operand.metadata)
    semantic_metadata = _dict_metadata(metadata.get("semantic_metadata"))
    v2_metadata = _dict_metadata(semantic_metadata.get("shape_ir_v2"))
    tags = [str(tag) for tag in operand.tags if str(tag)]
    record = {
        "operand_id": operand.operand_id,
        "operand_index": index,
        "source_index": operand.source_index,
        "part": operand.part or "",
        "primitive_type": operand.primitive_type or "",
        "blend_mode": operand.blend_mode,
        "component": str(metadata.get("component") or semantic_metadata.get("component") or ""),
        "region": str(metadata.get("region") or semantic_metadata.get("region") or ""),
        "tags": tags,
        "boolean_seam_groups": _metadata_list(metadata.get("boolean_seam_groups")),
        "bevel_seam_groups": _metadata_list(metadata.get("bevel_seam_groups")),
        "hard_edge_groups": _metadata_list(metadata.get("hard_edge_groups")),
    }
    if metadata.get("instance_index") is not None:
        record["instance_index"] = metadata.get("instance_index")
    if metadata.get("instance_id") is not None:
        record["instance_id"] = str(metadata.get("instance_id") or "")
    _copy_source_context_summary(record, metadata)
    _copy_source_context_summary(record, v2_metadata)
    source_shape = semantic_metadata.get("source_shape_primitive")
    if isinstance(source_shape, dict):
        record["source_shape_primitive"] = _compact_source_shape_record(source_shape)
        _copy_source_context_summary(record, source_shape)
    source_shapes = semantic_metadata.get("source_shape_primitives")
    if isinstance(source_shapes, list):
        source_shape_records = [item for item in source_shapes if isinstance(item, dict)]
        record["source_shape_primitive_summary"] = _compact_shape_record_summary(
            source_shape_records
        )
    component_assembly = metadata.get("component_assembly")
    if isinstance(component_assembly, dict):
        record["component_assembly"] = _compact_kernel_handoff_value(component_assembly)
    assembly_primitives = metadata.get("assembly_primitives")
    if isinstance(assembly_primitives, list):
        assembly_records = [item for item in assembly_primitives if isinstance(item, dict)]
        record["assembly_primitive_summary"] = _compact_shape_record_summary(
            assembly_records
        )
    if semantic_metadata:
        record["semantic_metadata"] = _compact_semantic_metadata_record(semantic_metadata)
    return record


def _sdf_lineage_stats(metadata: dict[str, Any]) -> dict[str, Any]:
    operation_count = 0
    smooth_operation_count = 0
    max_blend_width = 0.0
    leaf_types: list[str] = []
    boolean_ops: list[str] = []

    def walk(node: Any) -> None:
        nonlocal operation_count, smooth_operation_count, max_blend_width
        if not isinstance(node, dict):
            return
        primitive_type = str(node.get("primitive_type") or "")
        op = str(node.get("op") or "")
        if primitive_type == "sdf_boolean":
            operation_count += 1
            if op:
                boolean_ops.append(op)
            try:
                blend_width = float(node.get("blend_width_cm") or 0.0)
            except (TypeError, ValueError):
                blend_width = 0.0
            if bool(node.get("smooth_boolean")) or blend_width > 0.0:
                smooth_operation_count += 1
                max_blend_width = max(max_blend_width, blend_width)
            walk(node.get("source"))
            walk(node.get("cutter"))
            return
        if primitive_type:
            leaf_types.append(primitive_type)

    operation_count = 1
    if metadata.get("op"):
        boolean_ops.append(str(metadata.get("op") or ""))
    try:
        root_blend_width = float(metadata.get("blend_width_cm") or 0.0)
    except (TypeError, ValueError):
        root_blend_width = 0.0
    if bool(metadata.get("smooth_boolean")) or root_blend_width > 0.0:
        smooth_operation_count += 1
        max_blend_width = max(max_blend_width, root_blend_width)
    walk(metadata.get("source"))
    walk(metadata.get("cutter"))
    return {
        "operation_count": int(operation_count),
        "smooth_operation_count": int(smooth_operation_count),
        "max_blend_width_cm": round(float(max_blend_width), 6),
        "boolean_ops": _stable_unique_strings(boolean_ops),
        "leaf_primitive_types": _stable_unique_strings(leaf_types),
    }


def _kernel_program_semantic_handoff(
    operands: list[KernelOperand],
    trace_operations: list[dict[str, Any]],
    result_mesh: trimesh.Trimesh,
) -> dict[str, Any]:
    operand_records = [
        _operand_semantic_records(operand, index)
        for index, operand in enumerate(operands)
    ]
    operation_records = _dedupe_operation_records(
        [
            *_operand_operation_records(operands),
            *_trace_semantic_operation_records(trace_operations),
        ]
    )
    seam_records: list[dict[str, Any]] = []
    hard_edge_records: list[dict[str, Any]] = []
    material_zone_candidates: list[dict[str, Any]] = []
    for operand_record in operand_records:
        part = str(operand_record.get("part") or "")
        component = str(operand_record.get("component") or "")
        primitive_type = str(operand_record.get("primitive_type") or "")
        tags = [str(tag) for tag in operand_record.get("tags", []) if str(tag)]
        operand_lineage = {
            "operand_id": str(operand_record.get("operand_id") or ""),
            "operand_index": int(operand_record.get("operand_index") or 0),
            **(
                {"source_index": int(operand_record["source_index"])}
                if operand_record.get("source_index") is not None
                else {}
            ),
            **(
                {"instance_index": int(operand_record["instance_index"])}
                if operand_record.get("instance_index") is not None
                else {}
            ),
            **(
                {"instance_id": str(operand_record.get("instance_id") or "")}
                if operand_record.get("instance_id")
                else {}
            ),
        }
        for field, target in (
            ("boolean_seam_groups", seam_records),
            ("bevel_seam_groups", seam_records),
        ):
            for index, group in enumerate(_metadata_list(operand_record.get(field))):
                target.append(
                    {
                        **group,
                        "part": part,
                        "component": component,
                        "primitive_type": primitive_type,
                        "source": f"kernel_operand.{field}",
                        "group_index": int(index),
                        **operand_lineage,
                    }
                )
        for index, group in enumerate(_metadata_list(operand_record.get("hard_edge_groups"))):
            hard_edge_records.append(
                {
                    **group,
                    "part": part,
                    "component": component,
                    "primitive_type": primitive_type,
                    "source": "kernel_operand.hard_edge_groups",
                    "group_index": int(index),
                    **operand_lineage,
                }
            )
        semantic_metadata = _dict_metadata(operand_record.get("semantic_metadata"))
        material_hint = (
            semantic_metadata.get("material_hint")
            or semantic_metadata.get("material_zone")
            or component
        )
        if (
            operand_record.get("blend_mode") != "subtract"
            and ("material_zone" in tags or "wear_zone" in tags or material_hint)
        ):
            material_zone_candidates.append(
                {
                    "name": f"kernel_material_{len(material_zone_candidates):03d}_{part or 'mesh'}",
                    "part": part,
                    "component": component,
                    "primitive_type": primitive_type,
                    "material_hint": str(material_hint or primitive_type or "material"),
                    "source": "kernel_operand.semantic_handoff",
                    "tags": tags,
                    **operand_lineage,
                }
            )

    sdf_records: list[dict[str, Any]] = []
    exact_records: list[dict[str, Any]] = []
    backend_records: list[dict[str, Any]] = []
    fallback_records: list[dict[str, Any]] = []
    for operation_index, operation in enumerate(trace_operations):
        if not isinstance(operation, dict):
            continue
        sdf = operation.get("kernel_sdf_boolean")
        if isinstance(sdf, dict):
            sdf_records.append(
                {
                    "operation_index": int(operation_index),
                    "op": str(operation.get("op") or sdf.get("op") or ""),
                    "method": str(sdf.get("method") or ""),
                    "backend": str(sdf.get("backend") or ""),
                    "source_primitive_type": str(sdf.get("source_primitive_type") or ""),
                    "cutter_primitive_type": str(sdf.get("cutter_primitive_type") or ""),
                    "result_face_count": int(sdf.get("result_face_count") or 0),
                    "result_watertight": bool(sdf.get("result_watertight", False)),
                    "lineage": _sdf_lineage_stats(sdf),
                }
            )
        exact = operation.get("kernel_exact_boolean")
        if isinstance(exact, dict):
            exact_records.append({"operation_index": int(operation_index), **dict(exact)})
        backend = operation.get("kernel_boolean_backend")
        if isinstance(backend, dict):
            backend_records.append({"operation_index": int(operation_index), **dict(backend)})
        fallback = operation.get("kernel_fallback")
        if isinstance(fallback, dict):
            fallback_records.append({"operation_index": int(operation_index), **dict(fallback)})

    part_names = _stable_unique_strings([record.get("part") for record in operand_records])
    component_names = _stable_unique_strings(
        [record.get("component") for record in operand_records]
    )
    region_names = _stable_unique_strings(
        [record.get("region") for record in operand_records]
    )
    component_source_names = _stable_unique_strings(
        [
            _dict_metadata(record.get("semantic_metadata")).get("component_source")
            for record in operand_records
        ]
    )
    cga_terminal_names = _stable_unique_strings(
        [
            _dict_metadata(
                _dict_metadata(record.get("semantic_metadata")).get("cga_rule_component")
            ).get("terminal")
            for record in operand_records
        ]
    )
    cga_param_records = [
        _dict_metadata(
            _dict_metadata(
                _dict_metadata(record.get("semantic_metadata")).get("cga_rule_component")
            ).get("terminal_params")
        )
        for record in operand_records
    ]
    cga_terminal_param_keys = _stable_unique_strings(
        key
        for params in cga_param_records
        if params
        for key in params.keys()
    )
    context_record_count = 0
    for record in operand_records:
        with suppress(TypeError, ValueError):
            context_record_count += int(record.get("source_context_record_count") or 0)
    context_part_names = _stable_unique_strings(
        part
        for record in operand_records
        for part in record.get("source_context_parts", [])
    )
    context_primitive_types = _stable_unique_strings(
        primitive_type
        for record in operand_records
        for primitive_type in record.get("source_context_primitive_types", [])
    )
    result_metadata = result_mesh.metadata if isinstance(result_mesh.metadata, dict) else {}
    result_sdf = result_metadata.get("lathe_reference_sdf_boolean")
    return _json_safe(
        {
            "schema": "lathe.geometry.kernel_program_semantic_handoff.v1",
            "source": "kernel_program.operands_and_operation_trace",
            "operand_count": len(operand_records),
            "source_part_count": len(part_names),
            "source_parts": part_names,
            "source_primitive_types": _stable_unique_strings(
                [record.get("primitive_type") for record in operand_records]
            ),
            "source_context_record_count": context_record_count,
            "source_context_parts": context_part_names,
            "source_context_primitive_types": context_primitive_types,
            "source_components": component_names,
            "source_regions": region_names,
            "component_sources": component_source_names,
            "cga_terminals": cga_terminal_names,
            "cga_parametric_terminal_count": sum(1 for params in cga_param_records if params),
            "cga_terminal_param_keys": cga_terminal_param_keys,
            "operand_records": operand_records,
            "operation_records": operation_records,
            "operation_record_count": len(operation_records),
            "operation_counts": _operation_counts(operation_records),
            "seam_records": seam_records,
            "seam_record_count": len(seam_records),
            "hard_edge_records": hard_edge_records,
            "hard_edge_record_count": len(hard_edge_records),
            "material_zone_candidates": material_zone_candidates,
            "material_zone_candidate_count": len(material_zone_candidates),
            "sdf_boolean_records": sdf_records,
            "sdf_boolean_count": len(sdf_records),
            "exact_boolean_count": len(exact_records),
            "backend_boolean_count": len(backend_records),
            "fallback_count": len(fallback_records),
            "exact_boolean_records": exact_records,
            "backend_boolean_records": backend_records,
            "fallback_records": fallback_records,
            "result_sdf_lineage": (
                _sdf_lineage_stats(result_sdf)
                if isinstance(result_sdf, dict)
                else {}
            ),
            "result_face_count": len(result_mesh.faces),
            "result_watertight": bool(result_mesh.is_watertight),
        }
    )


def _attach_kernel_program_semantic_handoff(
    mesh: trimesh.Trimesh,
    operands: list[KernelOperand],
    trace_operations: list[dict[str, Any]],
) -> dict[str, Any]:
    """Attach source-operation lineage to a kernel-program result mesh."""
    semantic_handoff = _kernel_program_semantic_handoff(
        operands,
        trace_operations,
        mesh,
    )
    mesh.metadata["lathe_kernel_program_semantic_handoff"] = semantic_handoff
    return semantic_handoff


def build_boolean_program_manifest(
    operands: list[KernelOperand],
    *,
    route: str = "ordered_boolean_program",
    backend: str | None = None,
    operation_limit: int | None = None,
    batch_union_available: bool = False,
) -> dict[str, Any]:
    """Return a deterministic, handle-free manifest for a boolean program."""
    operation_records = _operand_operation_records(operands)
    union_count = sum(1 for operand in operands if operand.blend_mode == "union")
    subtract_count = sum(1 for operand in operands if operand.blend_mode == "subtract")
    intersect_count = sum(1 for operand in operands if operand.blend_mode == "intersect")
    for operation, count in (
        ("sop.boolean.union", max(0, union_count - 1)),
        ("sop.boolean.difference", subtract_count),
        ("sop.boolean.intersection", intersect_count),
    ):
        if count <= 0:
            continue
        operation_records.append(
            {
                "operation_id": f"program:{_operation_id_fragment(route)}:{_operation_id_fragment(operation)}",
                "operation": operation,
                "repair_action": "",
                "operand_id": "",
                "operand_index": -1,
                "part": "",
                "primitive_type": "",
                "blend_mode": "",
                "source": "kernel_program.boolean",
                "semantic_equivalent_operation_count": count,
            }
        )
    unsupported_blend_modes = sorted(
        {
            str(operand.blend_mode)
            for operand in operands
            if operand.blend_mode not in _SUPPORTED_BLEND_MODES
        }
    )
    missing_handle_ids = [operand.operand_id for operand in operands if operand.handle is None]
    diagnostics: list[dict[str, Any]] = []
    if unsupported_blend_modes:
        diagnostics.append(
            {
                "code": "unsupported_kernel_program_blend_mode",
                "severity": "error",
                "blend_modes": unsupported_blend_modes,
            }
        )
    if missing_handle_ids:
        diagnostics.append(
            {
                "code": "missing_kernel_operand_handle",
                "severity": "error",
                "operand_ids": missing_handle_ids,
            }
        )

    kernel_call_count = boolean_kernel_call_count(
        operands,
        batch_union_available=batch_union_available,
    )
    if operation_limit is not None and kernel_call_count > operation_limit:
        diagnostics.append(
            {
                "code": "kernel_program_operation_limit_exceeded",
                "severity": "error",
                "kernel_call_count": kernel_call_count,
                "operation_limit": operation_limit,
            }
        )

    return {
        "schema": "lathe.geometry.kernel_program_manifest.v1",
        "version": KERNEL_PROGRAM_VERSION,
        "program_kind": "boolean",
        "route": route,
        "backend": backend,
        "operation_count": boolean_operation_count(operands),
        "kernel_call_count": kernel_call_count,
        "operation_limit": operation_limit,
        "required_capabilities": sorted(
            _required_boolean_capabilities(
                operands,
                batch_union_available=batch_union_available,
            )
        ),
        "operand_count": len(operands),
        "operands": [_json_safe(operand.trace_record()) for operand in operands],
        "semantic_operation_record_count": len(operation_records),
        "semantic_operation_counts": _operation_counts(operation_records),
        "semantic_operation_records": _json_safe(operation_records),
        "diagnostics": diagnostics,
    }


def build_hull_program_manifest(
    operands: list[KernelOperand],
    *,
    route: str = "convex_hull_program",
    backend: str | None = None,
    operation_limit: int | None = None,
) -> dict[str, Any]:
    """Return a deterministic, handle-free manifest for a hull program."""
    operation_records = _operand_operation_records(operands)
    if not any(str(record.get("operation") or "") == "op.hull" for record in operation_records):
        operation_records.append(
            {
                "operation_id": f"program:{_operation_id_fragment(route)}:op_hull",
                "operation": "op.hull",
                "repair_action": "",
                "operand_id": "",
                "operand_index": -1,
                "part": "",
                "primitive_type": "",
                "blend_mode": "",
                "source": "kernel_program.hull",
            }
        )
    missing_handle_ids = [operand.operand_id for operand in operands if operand.handle is None]
    diagnostics: list[dict[str, Any]] = []
    if missing_handle_ids:
        diagnostics.append(
            {
                "code": "missing_kernel_operand_handle",
                "severity": "error",
                "operand_ids": missing_handle_ids,
            }
        )
    operation_count = hull_operation_count(operands)
    if operation_limit is not None and operation_count > operation_limit:
        diagnostics.append(
            {
                "code": "kernel_program_operation_limit_exceeded",
                "severity": "error",
                "operation_count": operation_count,
                "operation_limit": operation_limit,
            }
        )
    return {
        "schema": "lathe.geometry.kernel_program_manifest.v1",
        "version": KERNEL_PROGRAM_VERSION,
        "program_kind": "hull",
        "route": route,
        "backend": backend,
        "operation_count": operation_count,
        "kernel_call_count": operation_count,
        "operation_limit": operation_limit,
        "required_capabilities": ["hull", "to_trimesh"],
        "operand_count": len(operands),
        "operands": [_json_safe(operand.trace_record()) for operand in operands],
        "semantic_operation_record_count": len(operation_records),
        "semantic_operation_counts": _operation_counts(operation_records),
        "semantic_operation_records": _json_safe(operation_records),
        "diagnostics": diagnostics,
    }


def build_minkowski_program_manifest(
    source: KernelOperand,
    structuring: KernelOperand,
    *,
    route: str = "convex_minkowski_program",
    backend: str | None = None,
    operation_limit: int | None = None,
    sample_limit: int = 50_000,
    pair_count: int | None = None,
    sample_stride: int | None = None,
    sample_count: int | None = None,
    approximation: str = "convex_vertex_sum_hull",
    required_capabilities: list[str] | None = None,
) -> dict[str, Any]:
    """Return a deterministic, handle-free manifest for a Minkowski program."""
    operands = [source, structuring]
    operation_records = _operand_operation_records(operands)
    if not any(str(record.get("operation") or "") == "op.minkowski" for record in operation_records):
        operation_records.append(
            {
                "operation_id": f"program:{_operation_id_fragment(route)}:op_minkowski",
                "operation": "op.minkowski",
                "repair_action": "",
                "operand_id": "",
                "operand_index": -1,
                "part": "",
                "primitive_type": "",
                "blend_mode": "",
                "source": "kernel_program.minkowski",
            }
        )
    missing_handle_ids = [operand.operand_id for operand in operands if operand.handle is None]
    diagnostics: list[dict[str, Any]] = []
    if missing_handle_ids:
        diagnostics.append(
            {
                "code": "missing_kernel_operand_handle",
                "severity": "error",
                "operand_ids": missing_handle_ids,
            }
        )
    operation_count = minkowski_operation_count(source, structuring)
    if operation_limit is not None and operation_count > operation_limit:
        diagnostics.append(
            {
                "code": "kernel_program_operation_limit_exceeded",
                "severity": "error",
                "operation_count": operation_count,
                "operation_limit": operation_limit,
            }
        )
    if sample_limit <= 0:
        diagnostics.append(
            {
                "code": "invalid_minkowski_sample_limit",
                "severity": "error",
                "sample_limit": sample_limit,
            }
        )
    return {
        "schema": "lathe.geometry.kernel_program_manifest.v1",
        "version": KERNEL_PROGRAM_VERSION,
        "program_kind": "minkowski",
        "route": route,
        "backend": backend,
        "operation_count": operation_count,
        "kernel_call_count": operation_count,
        "operation_limit": operation_limit,
        "required_capabilities": _required_capability_list(
            required_capabilities or ["hull"],
            "to_trimesh",
        ),
        "operand_count": len(operands),
        "operands": [_json_safe(operand.trace_record()) for operand in operands],
        "semantic_operation_record_count": len(operation_records),
        "semantic_operation_counts": _operation_counts(operation_records),
        "semantic_operation_records": _json_safe(operation_records),
        "approximation": approximation,
        "sample_limit": int(sample_limit),
        "pair_count": pair_count,
        "sample_stride": sample_stride,
        "sample_count": sample_count,
        "diagnostics": diagnostics,
    }


def build_transform_program_manifest(
    source: KernelOperand,
    *,
    matrix: list[list[float]],
    route: str = "transform_program",
    backend: str | None = None,
    operation_limit: int | None = None,
) -> dict[str, Any]:
    """Return a deterministic, handle-free manifest for a transform program."""
    operation_records = _operand_operation_records([source])
    if not any(str(record.get("operation") or "") == "sop.transform" for record in operation_records):
        operation_records.append(
            {
                "operation_id": f"program:{_operation_id_fragment(route)}:sop_transform",
                "operation": "sop.transform",
                "repair_action": "",
                "operand_id": source.operand_id,
                "operand_index": 0,
                "part": source.part or "",
                "primitive_type": source.primitive_type or "",
                "blend_mode": source.blend_mode,
                "source": "kernel_program.transform",
            }
        )
    diagnostics: list[dict[str, Any]] = []
    if source.handle is None:
        diagnostics.append(
            {
                "code": "missing_kernel_operand_handle",
                "severity": "error",
                "operand_ids": [source.operand_id],
            }
        )
    operation_count = transform_operation_count(source)
    if operation_limit is not None and operation_count > operation_limit:
        diagnostics.append(
            {
                "code": "kernel_program_operation_limit_exceeded",
                "severity": "error",
                "operation_count": operation_count,
                "operation_limit": operation_limit,
            }
        )
    return {
        "schema": "lathe.geometry.kernel_program_manifest.v1",
        "version": KERNEL_PROGRAM_VERSION,
        "program_kind": "transform",
        "route": route,
        "backend": backend,
        "operation_count": operation_count,
        "kernel_call_count": operation_count,
        "operation_limit": operation_limit,
        "required_capabilities": ["transform", "to_trimesh"],
        "operand_count": 1,
        "operands": [_json_safe(source.trace_record())],
        "semantic_operation_record_count": len(operation_records),
        "semantic_operation_counts": _operation_counts(operation_records),
        "semantic_operation_records": _json_safe(operation_records),
        "matrix": _json_safe(matrix),
        "diagnostics": diagnostics,
    }


def build_deform_program_manifest(
    source: KernelOperand,
    *,
    deform_operation: str,
    axis: str,
    angle_degrees: float | None = None,
    start_scale: float | None = None,
    end_scale: float | None = None,
    direction_axis: str | None = None,
    origin: list[float] | None = None,
    subdivision_levels: int | None = None,
    segments: int | None = None,
    route: str = "deform_program",
    backend: str | None = None,
    operation_limit: int | None = None,
) -> dict[str, Any]:
    """Return a deterministic, handle-free manifest for a mesh deform program."""
    operation_records = _operand_operation_records([source])
    if not any(str(record.get("operation") or "") == deform_operation for record in operation_records):
        operation_records.append(
            {
                "operation_id": f"program:{_operation_id_fragment(route)}:{_operation_id_fragment(deform_operation)}",
                "operation": deform_operation,
                "repair_action": "",
                "operand_id": source.operand_id,
                "operand_index": 0,
                "part": source.part or "",
                "primitive_type": source.primitive_type or "",
                "blend_mode": source.blend_mode,
                "source": "kernel_program.deform",
            }
        )
    diagnostics: list[dict[str, Any]] = []
    if source.handle is None:
        diagnostics.append(
            {
                "code": "missing_kernel_operand_handle",
                "severity": "error",
                "operand_ids": [source.operand_id],
            }
        )
    operation_count = deform_operation_count(source)
    if operation_limit is not None and operation_count > operation_limit:
        diagnostics.append(
            {
                "code": "kernel_program_operation_limit_exceeded",
                "severity": "error",
                "operation_count": operation_count,
                "operation_limit": operation_limit,
            }
        )
    return {
        "schema": "lathe.geometry.kernel_program_manifest.v1",
        "version": KERNEL_PROGRAM_VERSION,
        "program_kind": "deform",
        "route": route,
        "backend": backend,
        "operation_count": operation_count,
        "kernel_call_count": operation_count,
        "operation_limit": operation_limit,
        "required_capabilities": ["from_trimesh", "to_trimesh"],
        "operand_count": 1,
        "operands": [_json_safe(source.trace_record())],
        "semantic_operation_record_count": len(operation_records),
        "semantic_operation_counts": _operation_counts(operation_records),
        "semantic_operation_records": _json_safe(operation_records),
        "deform_operation": deform_operation,
        "axis": axis,
        "angle_degrees": angle_degrees,
        "start_scale": start_scale,
        "end_scale": end_scale,
        "direction_axis": direction_axis,
        "origin_cm": _json_safe(origin),
        "subdivision_levels": subdivision_levels,
        "segments": segments,
        "diagnostics": diagnostics,
    }


def build_refine_program_manifest(
    source: KernelOperand,
    *,
    refine_operation: str,
    levels: int | None = None,
    scheme: str | None = None,
    target_edge_length_cm: float | None = None,
    mode: str | None = None,
    max_iterations: int | None = None,
    route: str = "refine_program",
    backend: str | None = None,
    operation_limit: int | None = None,
) -> dict[str, Any]:
    """Return a deterministic, handle-free manifest for mesh refinement."""
    operation_records = _operand_operation_records([source])
    if not any(str(record.get("operation") or "") == refine_operation for record in operation_records):
        operation_records.append(
            {
                "operation_id": f"program:{_operation_id_fragment(route)}:{_operation_id_fragment(refine_operation)}",
                "operation": refine_operation,
                "repair_action": "",
                "operand_id": source.operand_id,
                "operand_index": 0,
                "part": source.part or "",
                "primitive_type": source.primitive_type or "",
                "blend_mode": source.blend_mode,
                "source": "kernel_program.refine",
            }
        )
    diagnostics: list[dict[str, Any]] = []
    if source.handle is None:
        diagnostics.append(
            {
                "code": "missing_kernel_operand_handle",
                "severity": "error",
                "operand_ids": [source.operand_id],
            }
        )
    operation_count = refine_operation_count(source)
    if operation_limit is not None and operation_count > operation_limit:
        diagnostics.append(
            {
                "code": "kernel_program_operation_limit_exceeded",
                "severity": "error",
                "operation_count": operation_count,
                "operation_limit": operation_limit,
            }
        )
    return {
        "schema": "lathe.geometry.kernel_program_manifest.v1",
        "version": KERNEL_PROGRAM_VERSION,
        "program_kind": "refine",
        "route": route,
        "backend": backend,
        "operation_count": operation_count,
        "kernel_call_count": operation_count,
        "operation_limit": operation_limit,
        "required_capabilities": ["from_trimesh", "to_trimesh"],
        "operand_count": 1,
        "operands": [_json_safe(source.trace_record())],
        "semantic_operation_record_count": len(operation_records),
        "semantic_operation_counts": _operation_counts(operation_records),
        "semantic_operation_records": _json_safe(operation_records),
        "refine_operation": refine_operation,
        "levels": levels,
        "scheme": scheme,
        "target_edge_length_cm": target_edge_length_cm,
        "mode": mode,
        "max_iterations": max_iterations,
        "diagnostics": diagnostics,
    }


def build_carve_program_manifest(
    source: KernelOperand,
    *,
    u_start: float,
    u_end: float,
    axis: str,
    route: str = "carve_program",
    backend: str | None = None,
    operation_limit: int | None = None,
) -> dict[str, Any]:
    """Return a deterministic, handle-free manifest for axis carve refinement."""
    operation_records = _operand_operation_records([source])
    if not any(str(record.get("operation") or "") == "sop.carve" for record in operation_records):
        operation_records.append(
            {
                "operation_id": f"program:{_operation_id_fragment(route)}:sop_carve",
                "operation": "sop.carve",
                "repair_action": "",
                "operand_id": source.operand_id,
                "operand_index": 0,
                "part": source.part or "",
                "primitive_type": source.primitive_type or "",
                "blend_mode": source.blend_mode,
                "source": "kernel_program.carve",
            }
        )
    diagnostics: list[dict[str, Any]] = []
    if source.handle is None:
        diagnostics.append(
            {
                "code": "missing_kernel_operand_handle",
                "severity": "error",
                "operand_ids": [source.operand_id],
            }
        )
    operation_count = carve_operation_count(source)
    if operation_limit is not None and operation_count > operation_limit:
        diagnostics.append(
            {
                "code": "kernel_program_operation_limit_exceeded",
                "severity": "error",
                "operation_count": operation_count,
                "operation_limit": operation_limit,
            }
        )
    return {
        "schema": "lathe.geometry.kernel_program_manifest.v1",
        "version": KERNEL_PROGRAM_VERSION,
        "program_kind": "carve",
        "route": route,
        "backend": backend,
        "operation_count": operation_count,
        "kernel_call_count": operation_count,
        "operation_limit": operation_limit,
        "required_capabilities": ["from_trimesh", "to_trimesh"],
        "operand_count": 1,
        "operands": [_json_safe(source.trace_record())],
        "semantic_operation_record_count": len(operation_records),
        "semantic_operation_counts": _operation_counts(operation_records),
        "semantic_operation_records": _json_safe(operation_records),
        "u_start": u_start,
        "u_end": u_end,
        "axis": axis,
        "diagnostics": diagnostics,
    }


def build_polyextrude_program_manifest(
    source: KernelOperand,
    *,
    axis: str,
    distance_cm: float,
    semantic_operation: str = "sop.polyextrude",
    route: str = "polyextrude_program",
    backend: str | None = None,
    operation_limit: int | None = None,
) -> dict[str, Any]:
    """Return a deterministic, handle-free manifest for source polyextrusion."""
    operation_records = _operand_operation_records([source])
    if not any(str(record.get("operation") or "") == semantic_operation for record in operation_records):
        operation_records.append(
            {
                "operation_id": f"program:{_operation_id_fragment(route)}:{_operation_id_fragment(semantic_operation)}",
                "operation": semantic_operation,
                "repair_action": "",
                "operand_id": source.operand_id,
                "operand_index": 0,
                "part": source.part or "",
                "primitive_type": source.primitive_type or "",
                "blend_mode": source.blend_mode,
                "source": "kernel_program.polyextrude",
            }
        )
    diagnostics: list[dict[str, Any]] = []
    if source.handle is None:
        diagnostics.append(
            {
                "code": "missing_kernel_operand_handle",
                "severity": "error",
                "operand_ids": [source.operand_id],
            }
        )
    operation_count = polyextrude_operation_count(source)
    if operation_limit is not None and operation_count > operation_limit:
        diagnostics.append(
            {
                "code": "kernel_program_operation_limit_exceeded",
                "severity": "error",
                "operation_count": operation_count,
                "operation_limit": operation_limit,
            }
        )
    return {
        "schema": "lathe.geometry.kernel_program_manifest.v1",
        "version": KERNEL_PROGRAM_VERSION,
        "program_kind": "polyextrude",
        "route": route,
        "backend": backend,
        "operation_count": operation_count,
        "kernel_call_count": operation_count,
        "operation_limit": operation_limit,
        "required_capabilities": ["from_trimesh", "to_trimesh"],
        "operand_count": 1,
        "operands": [_json_safe(source.trace_record())],
        "semantic_operation_record_count": len(operation_records),
        "semantic_operation_counts": _operation_counts(operation_records),
        "semantic_operation_records": _json_safe(operation_records),
        "semantic_operation": semantic_operation,
        "axis": axis,
        "distance_cm": distance_cm,
        "diagnostics": diagnostics,
    }


def build_component_assembly_program_manifest(
    operands: list[KernelOperand],
    *,
    semantic_operation: str = "component_assembly",
    assembly_kind: str = "component_assembly",
    route: str = "component_assembly_program",
    backend: str | None = None,
    operation_limit: int | None = None,
) -> dict[str, Any]:
    """Return a deterministic, handle-free manifest for visible component assembly."""
    operation_records = _operand_operation_records(operands)
    destructive = any(
        str(operand.blend_mode or "union") in {"subtract", "intersect"}
        for operand in operands
    )
    component_blend_modes = {
        mode: sum(1 for operand in operands if str(operand.blend_mode or "union") == mode)
        for mode in sorted({str(operand.blend_mode or "union") for operand in operands})
    }
    component_semantics = _component_operand_semantic_summary(operands)
    if not any(str(record.get("operation") or "") == semantic_operation for record in operation_records):
        operation_records.append(
            {
                "operation_id": f"program:{_operation_id_fragment(route)}:{_operation_id_fragment(semantic_operation)}",
                "operation": semantic_operation,
                "repair_action": "",
                "operand_id": "",
                "operand_index": -1,
                "part": "",
                "primitive_type": "",
                "blend_mode": "union",
                "source": "kernel_program.component_assembly",
                "component_operand_count": len(operands),
                "assembly_kind": assembly_kind,
            }
        )
    missing_handle_ids = [operand.operand_id for operand in operands if operand.handle is None]
    invalid_blend_modes = sorted(
        {
            str(operand.blend_mode)
            for operand in operands
            if str(operand.blend_mode or "union") not in _SUPPORTED_BLEND_MODES
        }
    )
    diagnostics: list[dict[str, Any]] = []
    if not operands:
        diagnostics.append(
            {
                "code": "kernel_component_assembly_empty_operand_list",
                "severity": "error",
            }
        )
    if missing_handle_ids:
        diagnostics.append(
            {
                "code": "missing_kernel_operand_handle",
                "severity": "error",
                "operand_ids": missing_handle_ids,
            }
        )
    if invalid_blend_modes:
        diagnostics.append(
            {
                "code": "unsupported_kernel_program_blend_mode",
                "severity": "error",
                "blend_modes": invalid_blend_modes,
            }
        )
    operation_count = component_assembly_operation_count(operands)
    required_capabilities = (
        sorted(_required_boolean_capabilities(operands))
        if destructive
        else ["from_trimesh", "to_trimesh"]
    )
    kernel_call_count = (
        boolean_kernel_call_count(operands)
        if destructive
        else len(operands) + (1 if operands else 0)
    )
    limit_count = kernel_call_count if destructive else operation_count
    if operation_limit is not None and limit_count > operation_limit:
        limit_payload_key = "kernel_call_count" if destructive else "operation_count"
        diagnostics.append(
            {
                "code": "kernel_program_operation_limit_exceeded",
                "severity": "error",
                limit_payload_key: limit_count,
                "operation_limit": operation_limit,
            }
        )
    return {
        "schema": "lathe.geometry.kernel_program_manifest.v1",
        "version": KERNEL_PROGRAM_VERSION,
        "program_kind": "component_assembly",
        "route": route,
        "backend": backend,
        "operation_count": operation_count,
        "kernel_call_count": kernel_call_count,
        "operation_limit": operation_limit,
        "required_capabilities": required_capabilities,
        "operand_count": len(operands),
        "operands": [_json_safe(operand.trace_record()) for operand in operands],
        "semantic_operation_record_count": len(operation_records),
        "semantic_operation_counts": _operation_counts(operation_records),
        "semantic_operation_records": _json_safe(operation_records),
        "semantic_operation": semantic_operation,
        "assembly_kind": assembly_kind,
        "component_blend_modes": component_blend_modes,
        **component_semantics,
        "boolean_route": bool(destructive),
        "source_primitive_types": _stable_unique_strings(
            [operand.primitive_type for operand in operands]
        ),
        "source_parts": _stable_unique_strings([operand.part for operand in operands]),
        "diagnostics": diagnostics,
    }


def build_profile_path_program_manifest(
    source: KernelOperand,
    *,
    semantic_operation: str = "sop.sweep",
    profile_kind: str = "profile_path",
    route: str = "profile_path_program",
    backend: str | None = None,
    operation_limit: int | None = None,
) -> dict[str, Any]:
    """Return a deterministic, handle-free manifest for sweep/loft/profile geometry."""
    operation_records = _operand_operation_records([source])
    if not any(str(record.get("operation") or "") == semantic_operation for record in operation_records):
        operation_records.append(
            {
                "operation_id": f"program:{_operation_id_fragment(route)}:{_operation_id_fragment(semantic_operation)}",
                "operation": semantic_operation,
                "repair_action": "",
                "operand_id": source.operand_id,
                "operand_index": 0,
                "part": source.part or "",
                "primitive_type": source.primitive_type or "",
                "blend_mode": source.blend_mode,
                "source": "kernel_program.profile_path",
                "profile_kind": profile_kind,
            }
        )
    diagnostics: list[dict[str, Any]] = []
    if source.handle is None:
        diagnostics.append(
            {
                "code": "missing_kernel_operand_handle",
                "severity": "error",
                "operand_ids": [source.operand_id],
            }
        )
    operation_count = profile_path_operation_count(source)
    if operation_limit is not None and operation_count > operation_limit:
        diagnostics.append(
            {
                "code": "kernel_program_operation_limit_exceeded",
                "severity": "error",
                "operation_count": operation_count,
                "operation_limit": operation_limit,
            }
        )
    return {
        "schema": "lathe.geometry.kernel_program_manifest.v1",
        "version": KERNEL_PROGRAM_VERSION,
        "program_kind": "profile_path",
        "route": route,
        "backend": backend,
        "operation_count": operation_count,
        "kernel_call_count": operation_count,
        "operation_limit": operation_limit,
        "required_capabilities": ["to_trimesh"],
        "operand_count": 1,
        "operands": [_json_safe(source.trace_record())],
        "semantic_operation_record_count": len(operation_records),
        "semantic_operation_counts": _operation_counts(operation_records),
        "semantic_operation_records": _json_safe(operation_records),
        "semantic_operation": semantic_operation,
        "profile_kind": profile_kind,
        "source_primitive_type": source.primitive_type or "",
        "diagnostics": diagnostics,
    }


def build_sdf_field_program_manifest(
    source: KernelOperand,
    *,
    semantic_operation: str = "solid.sdf_metaball_cluster",
    field_kind: str = "sdf_field",
    route: str = "sdf_field_program",
    backend: str | None = None,
    operation_limit: int | None = None,
) -> dict[str, Any]:
    """Return a deterministic, handle-free manifest for implicit-field geometry."""
    operation_records = _operand_operation_records([source])
    if not any(str(record.get("operation") or "") == semantic_operation for record in operation_records):
        operation_records.append(
            {
                "operation_id": f"program:{_operation_id_fragment(route)}:{_operation_id_fragment(semantic_operation)}",
                "operation": semantic_operation,
                "repair_action": "",
                "operand_id": source.operand_id,
                "operand_index": 0,
                "part": source.part or "",
                "primitive_type": source.primitive_type or "",
                "blend_mode": source.blend_mode,
                "source": "kernel_program.sdf_field",
                "field_kind": field_kind,
            }
        )
    diagnostics: list[dict[str, Any]] = []
    if source.handle is None:
        diagnostics.append(
            {
                "code": "missing_kernel_operand_handle",
                "severity": "error",
                "operand_ids": [source.operand_id],
            }
        )
    operation_count = sdf_field_operation_count(source)
    if operation_limit is not None and operation_count > operation_limit:
        diagnostics.append(
            {
                "code": "kernel_program_operation_limit_exceeded",
                "severity": "error",
                "operation_count": operation_count,
                "operation_limit": operation_limit,
            }
        )
    return {
        "schema": "lathe.geometry.kernel_program_manifest.v1",
        "version": KERNEL_PROGRAM_VERSION,
        "program_kind": "sdf_field",
        "route": route,
        "backend": backend,
        "operation_count": operation_count,
        "kernel_call_count": operation_count,
        "operation_limit": operation_limit,
        "required_capabilities": ["to_trimesh"],
        "operand_count": 1,
        "operands": [_json_safe(source.trace_record())],
        "semantic_operation_record_count": len(operation_records),
        "semantic_operation_counts": _operation_counts(operation_records),
        "semantic_operation_records": _json_safe(operation_records),
        "semantic_operation": semantic_operation,
        "field_kind": field_kind,
        "source_primitive_type": source.primitive_type or "",
        "diagnostics": diagnostics,
    }


def build_terrain_field_program_manifest(
    source: KernelOperand,
    *,
    semantic_operation: str = "solid.terrain_patch",
    terrain_kind: str = "terrain_patch",
    route: str = "terrain_field_program",
    backend: str | None = None,
    operation_limit: int | None = None,
) -> dict[str, Any]:
    """Return a deterministic, handle-free manifest for terrain heightfield geometry."""
    operation_records = _operand_operation_records([source])
    if not any(str(record.get("operation") or "") == semantic_operation for record in operation_records):
        operation_records.append(
            {
                "operation_id": f"program:{_operation_id_fragment(route)}:{_operation_id_fragment(semantic_operation)}",
                "operation": semantic_operation,
                "repair_action": "",
                "operand_id": source.operand_id,
                "operand_index": 0,
                "part": source.part or "",
                "primitive_type": source.primitive_type or "",
                "blend_mode": source.blend_mode,
                "source": "kernel_program.terrain_field",
                "terrain_kind": terrain_kind,
            }
        )
    diagnostics: list[dict[str, Any]] = []
    if source.handle is None:
        diagnostics.append(
            {
                "code": "missing_kernel_operand_handle",
                "severity": "error",
                "operand_ids": [source.operand_id],
            }
        )
    operation_count = terrain_field_operation_count(source)
    if operation_limit is not None and operation_count > operation_limit:
        diagnostics.append(
            {
                "code": "kernel_program_operation_limit_exceeded",
                "severity": "error",
                "operation_count": operation_count,
                "operation_limit": operation_limit,
            }
        )
    return {
        "schema": "lathe.geometry.kernel_program_manifest.v1",
        "version": KERNEL_PROGRAM_VERSION,
        "program_kind": "terrain_field",
        "route": route,
        "backend": backend,
        "operation_count": operation_count,
        "kernel_call_count": operation_count,
        "operation_limit": operation_limit,
        "required_capabilities": ["to_trimesh"],
        "operand_count": 1,
        "operands": [_json_safe(source.trace_record())],
        "semantic_operation_record_count": len(operation_records),
        "semantic_operation_counts": _operation_counts(operation_records),
        "semantic_operation_records": _json_safe(operation_records),
        "semantic_operation": semantic_operation,
        "terrain_kind": terrain_kind,
        "source_primitive_type": source.primitive_type or "",
        "diagnostics": diagnostics,
    }


def _import_edge_treatment_requires_reimport(
    source: KernelOperand,
    semantic_operation: str,
) -> bool:
    treatments = _kernel_edge_treatment_payloads([source])
    treatment_operation = _EDGE_TREATMENT_OPERATION_KINDS.get(semantic_operation)
    if not treatments and not treatment_operation:
        return False
    width, _, _, _ = _edge_treatment_geometry_parameters(treatments)
    return width > 0.0


def _import_required_capabilities(
    source: KernelOperand,
    semantic_operation: str = "",
) -> list[str]:
    required = ["to_trimesh"]
    metadata = _dict_metadata(source.metadata)
    kernel_import = _dict_metadata(metadata.get("kernel_import"))
    route = str(kernel_import.get("route") or "")
    if route == "exact_mesh.from_trimesh":
        required.append("from_trimesh")
    if route == "kernel.build_primitive" and source.primitive_type:
        required.append(source.primitive_type)
    if _import_edge_treatment_requires_reimport(source, semantic_operation):
        required.append("from_trimesh")
    return _required_capability_list(required)


def build_import_program_manifest(
    source: KernelOperand,
    *,
    semantic_operation: str = "shape.import",
    route: str = "import_program",
    backend: str | None = None,
    operation_limit: int | None = None,
) -> dict[str, Any]:
    """Return a deterministic, handle-free manifest for one imported source."""
    operation_records = _operand_operation_records([source])
    if not any(str(record.get("operation") or "") == semantic_operation for record in operation_records):
        operation_records.append(
            {
                "operation_id": f"program:{_operation_id_fragment(route)}:{_operation_id_fragment(semantic_operation)}",
                "operation": semantic_operation,
                "repair_action": "",
                "operand_id": source.operand_id,
                "operand_index": 0,
                "part": source.part or "",
                "primitive_type": source.primitive_type or "",
                "blend_mode": source.blend_mode,
                "source": "kernel_program.import",
            }
        )
    diagnostics: list[dict[str, Any]] = []
    if source.handle is None:
        diagnostics.append(
            {
                "code": "missing_kernel_operand_handle",
                "severity": "error",
                "operand_ids": [source.operand_id],
            }
        )
    operation_count = import_operation_count(source)
    if operation_limit is not None and operation_count > operation_limit:
        diagnostics.append(
            {
                "code": "kernel_program_operation_limit_exceeded",
                "severity": "error",
                "operation_count": operation_count,
                "operation_limit": operation_limit,
            }
        )
    return {
        "schema": "lathe.geometry.kernel_program_manifest.v1",
        "version": KERNEL_PROGRAM_VERSION,
        "program_kind": "import",
        "route": route,
        "backend": backend,
        "operation_count": operation_count,
        "kernel_call_count": operation_count,
        "operation_limit": operation_limit,
        "required_capabilities": _import_required_capabilities(
            source,
            semantic_operation,
        ),
        "operand_count": 1,
        "operands": [_json_safe(source.trace_record())],
        "semantic_operation_record_count": len(operation_records),
        "semantic_operation_counts": _operation_counts(operation_records),
        "semantic_operation_records": _json_safe(operation_records),
        "semantic_operation": semantic_operation,
        "diagnostics": diagnostics,
    }


def build_instances_program_manifest(
    source: KernelOperand,
    *,
    matrices: list[list[list[float]]],
    semantic_operation: str = "sop.copy_to_points",
    route: str = "instances_program",
    backend: str | None = None,
    operation_limit: int | None = None,
    batch_union_available: bool = False,
) -> dict[str, Any]:
    """Return a deterministic, handle-free manifest for an instancing program."""
    operation_records = _operand_operation_records([source])
    if not any(str(record.get("operation") or "") == semantic_operation for record in operation_records):
        operation_records.append(
            {
                "operation_id": f"program:{_operation_id_fragment(route)}:{_operation_id_fragment(semantic_operation)}",
                "operation": semantic_operation,
                "repair_action": "",
                "operand_id": source.operand_id,
                "operand_index": 0,
                "part": source.part or "",
                "primitive_type": source.primitive_type or "",
                "blend_mode": source.blend_mode,
                "source": "kernel_program.instances",
                "instance_count": len(matrices),
            }
        )
    diagnostics: list[dict[str, Any]] = []
    if source.handle is None:
        diagnostics.append(
            {
                "code": "missing_kernel_operand_handle",
                "severity": "error",
                "operand_ids": [source.operand_id],
            }
        )
    if not matrices:
        diagnostics.append(
            {
                "code": "kernel_instances_empty_matrix_list",
                "severity": "error",
            }
        )
    operation_count = instances_operation_count(source, matrices)
    if operation_limit is not None and operation_count > operation_limit:
        diagnostics.append(
            {
                "code": "kernel_program_operation_limit_exceeded",
                "severity": "error",
                "operation_count": operation_count,
                "operation_limit": operation_limit,
            }
        )
    required_capabilities = ["transform", "to_trimesh", "from_trimesh"]
    if len(matrices) > 1:
        required_capabilities.append("batch_union" if batch_union_available else "union")
    return {
        "schema": "lathe.geometry.kernel_program_manifest.v1",
        "version": KERNEL_PROGRAM_VERSION,
        "program_kind": "instances",
        "route": route,
        "backend": backend,
        "operation_count": operation_count,
        "kernel_call_count": operation_count,
        "operation_limit": operation_limit,
        "required_capabilities": required_capabilities,
        "operand_count": 1,
        "operands": [_json_safe(source.trace_record())],
        "semantic_operation_record_count": len(operation_records),
        "semantic_operation_counts": _operation_counts(operation_records),
        "semantic_operation_records": _json_safe(operation_records),
        "semantic_operation": semantic_operation,
        "instance_count": len(matrices),
        "matrices": _json_safe(matrices),
        "diagnostics": diagnostics,
    }


def _validated_transform_matrices(matrices: list[list[list[float]]]) -> list[list[list[float]]]:
    if not isinstance(matrices, list) or not matrices:
        raise ValueError("kernel instances requires at least one transform matrix")
    return [_validated_transform_matrix(matrix) for matrix in matrices]


def _validated_deform_operation(operation: str) -> str:
    key = str(operation or "").strip().lower()
    aliases = {
        "twist": "sop.twist",
        "sop.twist": "sop.twist",
        "taper": "sop.taper",
        "sop.taper": "sop.taper",
        "bend": "sop.bend",
        "sop.bend": "sop.bend",
    }
    if key not in aliases:
        raise ValueError("kernel deform operation must be one of: sop.twist, sop.taper, sop.bend")
    return aliases[key]


def _validated_deform_axis(axis: str, *, field: str = "axis") -> str:
    value = str(axis or "").strip().lower()
    if value not in {"x", "y", "z"}:
        raise ValueError(f"kernel deform {field} must be one of: x, y, z")
    return value


def _axis_index(axis: str) -> int:
    if axis == "x":
        return 0
    if axis == "y":
        return 1
    if axis == "z":
        return 2
    raise ValueError("axis must be one of: x, y, z")


def _axis_name_from_index(index: int) -> str:
    return ("x", "y", "z")[index]


def _perpendicular_axis_indices(axis: str) -> tuple[int, int]:
    axis_index = _axis_index(axis)
    indices = tuple(index for index in (0, 1, 2) if index != axis_index)
    return (indices[0], indices[1])


def _finite_float(value: Any, *, field: str) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"kernel deform {field} must be numeric") from exc
    if not math.isfinite(out):
        raise ValueError(f"kernel deform {field} must be finite")
    return out


def _validated_origin(origin: Any | None) -> list[float] | None:
    if origin is None:
        return None
    if not isinstance(origin, (list, tuple)) or len(origin) != 3:
        raise ValueError("kernel deform origin must be a 3-item numeric sequence")
    return [_finite_float(value, field="origin") for value in origin]


def _mesh_origin(mesh: trimesh.Trimesh, origin: list[float] | None) -> np.ndarray:
    if origin is not None:
        return np.asarray(origin, dtype=np.float64)
    bounds = np.asarray(mesh.bounds, dtype=np.float64)
    return (bounds[0] + bounds[1]) * 0.5


def _axis_span(vertices: np.ndarray, axis_index: int) -> tuple[float, float, float]:
    axis_min = float(vertices[:, axis_index].min())
    axis_max = float(vertices[:, axis_index].max())
    return axis_min, axis_max, max(axis_max - axis_min, 1e-6)


def _mesh_with_vertices(source_mesh: trimesh.Trimesh, vertices: np.ndarray) -> trimesh.Trimesh:
    mesh = trimesh.Trimesh(
        vertices=np.asarray(vertices, dtype=np.float64),
        faces=np.asarray(source_mesh.faces, dtype=np.int64).copy(),
        process=False,
    )
    mesh.metadata.update(dict(source_mesh.metadata))
    mesh.remove_unreferenced_vertices()
    mesh.merge_vertices()
    try:
        mesh.fix_normals()
    except (ValueError, RuntimeError, AttributeError, IndexError, TypeError):
        pass
    return mesh


def _subdivided_deform_mesh(
    mesh: trimesh.Trimesh,
    *,
    axis: str,
    subdivision_levels: int | None,
    segments: int | None,
) -> tuple[trimesh.Trimesh, dict[str, Any]]:
    if len(mesh.vertices) == 0 or len(mesh.faces) == 0:
        raise ValueError("kernel deform source produced an empty mesh")
    explicit_levels = subdivision_levels is not None
    if explicit_levels:
        levels = int(subdivision_levels)
        if levels < 0 or levels > 6:
            raise ValueError("kernel deform subdivision_levels must be between 0 and 6")
        target_segments = max(1, 2**levels)
    elif segments is not None:
        target_segments = int(segments)
        if target_segments < 1:
            raise ValueError("kernel deform segments must be >= 1")
        target_segments = min(target_segments, 64)
        levels = max(1, min(6, int(math.ceil(math.log2(float(target_segments))))))
    else:
        target_segments = 12
        levels = max(1, min(6, int(math.ceil(math.log2(float(target_segments))))))

    axis_index = _axis_index(axis)
    _, _, span = _axis_span(np.asarray(mesh.vertices, dtype=np.float64), axis_index)
    details: dict[str, Any] = {
        "source_face_count": len(mesh.faces),
        "source_vertex_count": len(mesh.vertices),
        "deform_segments": target_segments,
        "subdivision_request": "levels" if explicit_levels else "segments",
    }
    if levels <= 0 or target_segments <= 1:
        details.update(
            {
                "subdivision_applied": False,
                "subdivision_levels": levels,
                "subdivision_target_segments": target_segments,
                "subdivision_axis_span_cm": span,
            }
        )
        return mesh.copy(), details

    try:
        vertices = np.asarray(mesh.vertices, dtype=np.float64)
        faces = np.asarray(mesh.faces, dtype=np.int64)
        for _ in range(levels):
            vertices, faces = trimesh.remesh.subdivide(vertices, faces)
    except (ValueError, RuntimeError, AttributeError, IndexError, TypeError) as exc:
        raise ValueError(f"kernel deform subdivision failed: {exc}") from exc
    refined = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    refined.metadata.update(dict(mesh.metadata))
    refined.remove_unreferenced_vertices()
    refined.merge_vertices()
    try:
        refined.fix_normals()
    except (ValueError, RuntimeError, AttributeError, IndexError, TypeError):
        pass
    if len(refined.vertices) == 0 or len(refined.faces) == 0:
        raise ValueError("kernel deform subdivision produced an empty mesh")
    details.update(
        {
            "subdivision_applied": True,
            "subdivision_levels": levels,
            "subdivision_target_segments": target_segments,
            "subdivision_axis_span_cm": span,
            "subdivided_face_count": len(refined.faces),
            "subdivided_vertex_count": len(refined.vertices),
        }
    )
    return refined, details


def _validated_refine_operation(operation: str) -> str:
    key = str(operation or "").strip().lower()
    aliases = {
        "subdivide": "sop.subdivide",
        "sop.subdivide": "sop.subdivide",
        "remesh": "sop.remesh",
        "sop.remesh": "sop.remesh",
    }
    if key not in aliases:
        raise ValueError("kernel refine operation must be one of: sop.subdivide, sop.remesh")
    return aliases[key]


def _normalize_refine_mode(value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("kernel refine mode must be a non-empty string")
    mode = value.strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "target_edge": "adaptive",
        "target_edge_subdivide": "adaptive",
        "subdivide_to_size": "adaptive",
        "uniform_subdivide": "uniform",
        "isotropic": "smooth",
        "relax": "smooth",
        "hard": "feature_preserving",
        "hard_surface": "feature_preserving",
        "faceted": "feature_preserving",
    }
    mode = aliases.get(mode, mode)
    if mode not in {"adaptive", "uniform", "smooth", "feature_preserving"}:
        raise ValueError("kernel refine mode must be adaptive, uniform, smooth, or feature_preserving")
    return mode


def _subdivide_mesh(
    mesh: trimesh.Trimesh,
    *,
    levels: int,
) -> trimesh.Trimesh:
    if levels <= 0:
        return mesh.copy()
    vertices = np.asarray(mesh.vertices, dtype=np.float64)
    faces = np.asarray(mesh.faces, dtype=np.int64)
    try:
        for _ in range(levels):
            vertices, faces = trimesh.remesh.subdivide(vertices, faces)
    except (ValueError, RuntimeError, AttributeError, IndexError, TypeError) as exc:
        raise ValueError(f"kernel refine subdivision failed: {exc}") from exc
    refined = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    refined.metadata.update(dict(mesh.metadata))
    refined.remove_unreferenced_vertices()
    refined.merge_vertices()
    try:
        refined.fix_normals()
    except (ValueError, RuntimeError, AttributeError, IndexError, TypeError):
        pass
    if len(refined.vertices) == 0 or len(refined.faces) == 0:
        raise ValueError("kernel refine subdivision produced an empty mesh")
    return refined


def _remesh_to_edge_length(
    mesh: trimesh.Trimesh,
    *,
    target_edge_length_cm: float,
    mode: str,
    max_iterations: int,
) -> trimesh.Trimesh:
    vertices = np.asarray(mesh.vertices, dtype=np.float64)
    faces = np.asarray(mesh.faces, dtype=np.int64)
    try:
        for _ in range(max_iterations):
            edge_pairs = np.vstack(
                (
                    faces[:, [0, 1]],
                    faces[:, [1, 2]],
                    faces[:, [2, 0]],
                )
            )
            edge_lengths = np.linalg.norm(
                vertices[edge_pairs[:, 0]] - vertices[edge_pairs[:, 1]],
                axis=1,
            )
            if float(edge_lengths.max(initial=0.0)) <= target_edge_length_cm:
                break
            vertices, faces = trimesh.remesh.subdivide(vertices, faces)
    except (ValueError, RuntimeError, AttributeError, IndexError, TypeError) as exc:
        raise ValueError(f"kernel refine remesh failed: {exc}") from exc
    remeshed = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    remeshed.metadata.update(dict(mesh.metadata))
    if mode == "smooth":
        try:
            trimesh.smoothing.filter_laplacian(
                remeshed,
                lamb=0.35,
                iterations=1,
                volume_constraint=True,
            )
        except (ValueError, RuntimeError, AttributeError, IndexError, TypeError):
            pass
    remeshed.remove_unreferenced_vertices()
    remeshed.merge_vertices()
    try:
        remeshed.fix_normals()
    except (ValueError, RuntimeError, AttributeError, IndexError, TypeError):
        pass
    if len(remeshed.vertices) == 0 or len(remeshed.faces) == 0:
        raise ValueError("kernel refine remesh produced an empty mesh")
    return remeshed


def _carved_axis_interval_mesh(
    mesh: trimesh.Trimesh,
    *,
    axis: str,
    u_start: float,
    u_end: float,
) -> tuple[trimesh.Trimesh, dict[str, Any]]:
    axis_index = _axis_index(axis)
    vertices = np.asarray(mesh.vertices, dtype=np.float64)
    source_min, source_max, source_span = _axis_span(vertices, axis_index)
    carved_min = source_min + source_span * u_start
    carved_max = source_min + source_span * u_end
    carved_span = max(carved_max - carved_min, 1e-6)
    exact_slice_failure: str | None = None
    exact_slice_mesh = None
    try:
        from trimesh.intersections import slice_mesh_plane

        plane_normal = np.zeros(3, dtype=np.float64)
        plane_normal[axis_index] = 1.0
        lower_origin = np.zeros(3, dtype=np.float64)
        lower_origin[axis_index] = carved_min
        upper_origin = np.zeros(3, dtype=np.float64)
        upper_origin[axis_index] = carved_max
        lower_clipped = slice_mesh_plane(
            mesh,
            plane_normal,
            lower_origin,
            cap=True,
        )
        upper_clipped = slice_mesh_plane(
            lower_clipped,
            -plane_normal,
            upper_origin,
            cap=True,
        )
        if isinstance(upper_clipped, trimesh.Trimesh) and len(upper_clipped.faces) > 0:
            upper_clipped.metadata.update(dict(mesh.metadata))
            upper_clipped.remove_unreferenced_vertices()
            try:
                upper_clipped.fix_normals()
            except (AttributeError, TypeError, ValueError, RuntimeError):
                pass
            exact_slice_mesh = upper_clipped
        else:
            exact_slice_failure = "empty_or_non_mesh_slice_result"
    except (
        AttributeError,
        ImportError,
        IndexError,
        ModuleNotFoundError,
        NotImplementedError,
        TypeError,
        ValueError,
        RuntimeError,
    ) as exc:
        exact_slice_failure = f"{type(exc).__name__}: {exc}"
    if exact_slice_mesh is not None:
        return exact_slice_mesh, {
            "method": "axis_slab_slice_cap_v1",
            "fallback": False,
            "fallback_from": "",
            "fallback_reason": "",
            "source_min_cm": source_min,
            "source_max_cm": source_max,
            "source_span_cm": source_span,
            "carved_min_cm": carved_min,
            "carved_max_cm": carved_max,
            "carved_span_cm": carved_span,
        }

    measured_mesh: trimesh.Trimesh | None = None
    measured_failure: str | None = None
    try:
        bounds = np.asarray(mesh.bounds, dtype=np.float64)
        bounds_min = bounds[0].astype(np.float64)
        bounds_max = bounds[1].astype(np.float64)
        bounds_min[axis_index] = carved_min
        bounds_max[axis_index] = carved_max
        extents = bounds_max - bounds_min
        if np.any(extents <= 1e-6):
            measured_failure = "measured_bounds_axis_slab_collapsed"
        else:
            center = (bounds_min + bounds_max) * 0.5
            candidate = trimesh.creation.box(extents=extents)
            candidate.apply_translation(center)
            candidate.metadata.update(dict(mesh.metadata))
            candidate.remove_unreferenced_vertices()
            try:
                candidate.fix_normals()
            except (AttributeError, TypeError, ValueError, RuntimeError):
                pass
            if len(candidate.faces) == 0:
                measured_failure = "measured_bounds_axis_slab_result_empty"
            elif not bool(candidate.is_watertight):
                measured_failure = "measured_bounds_axis_slab_result_not_watertight"
            else:
                measured_mesh = candidate
    except (
        AttributeError,
        IndexError,
        TypeError,
        ValueError,
        RuntimeError,
    ) as exc:
        measured_failure = f"{type(exc).__name__}: {exc}"

    if measured_mesh is not None:
        return measured_mesh, {
            "method": "measured_bounds_axis_slab_carve_v1",
            "fallback": True,
            "fallback_from": "axis_slab_slice_cap_v1",
            "fallback_reason": exact_slice_failure or "slice_backend_unavailable",
            "source_min_cm": source_min,
            "source_max_cm": source_max,
            "source_span_cm": source_span,
            "carved_min_cm": carved_min,
            "carved_max_cm": carved_max,
            "carved_span_cm": carved_span,
            "source_face_count": int(len(mesh.faces)),
            "source_vertex_count": int(len(mesh.vertices)),
            "result_face_count": int(len(measured_mesh.faces)),
            "result_vertex_count": int(len(measured_mesh.vertices)),
            "result_watertight": bool(measured_mesh.is_watertight),
        }

    transformed = vertices.copy()
    transformed[:, axis_index] = carved_min + (
        (transformed[:, axis_index] - source_min) / source_span
    ) * carved_span
    fallback = _mesh_with_vertices(mesh, transformed)
    return fallback, {
        "method": "axis_interval_scale_v1",
        "fallback": True,
        "fallback_from": "measured_bounds_axis_slab_carve_v1",
        "fallback_chain": [
            "axis_slab_slice_cap_v1",
            "measured_bounds_axis_slab_carve_v1",
        ],
        "fallback_reason": measured_failure or exact_slice_failure or "measured_bounds_axis_slab_unavailable",
        "exact_carve_failure": exact_slice_failure or "",
        "measured_carve_failure": measured_failure or "",
        "source_min_cm": source_min,
        "source_max_cm": source_max,
        "source_span_cm": source_span,
        "carved_min_cm": carved_min,
        "carved_max_cm": carved_max,
        "carved_span_cm": carved_span,
    }


def _axis_interval_center_and_span(
    center: tuple[float, float, float],
    *,
    axis: str,
    span: float,
    u_start: float,
    u_end: float,
) -> tuple[tuple[float, float, float], float, float, float]:
    axis_index = _axis_index(axis)
    source_min = float(center[axis_index]) - float(span) * 0.5
    source_max = float(center[axis_index]) + float(span) * 0.5
    carved_min = source_min + float(span) * float(u_start)
    carved_max = source_min + float(span) * float(u_end)
    carved_span = max(carved_max - carved_min, 1e-6)
    result_center = list(float(value) for value in center)
    result_center[axis_index] = (carved_min + carved_max) * 0.5
    return (
        (float(result_center[0]), float(result_center[1]), float(result_center[2])),
        carved_span,
        carved_min,
        carved_max,
    )


def _exact_primitive_carve_params(
    mesh: trimesh.Trimesh,
    *,
    axis: str,
    u_start: float,
    u_end: float,
) -> dict[str, Any] | None:
    box = _axis_aligned_box_metadata(mesh)
    if box is not None:
        axis_index = _axis_index(axis)
        bounds_min = list(float(value) for value in box["bounds_min"])
        bounds_max = list(float(value) for value in box["bounds_max"])
        source_span = float(bounds_max[axis_index] - bounds_min[axis_index])
        if source_span <= 1e-9:
            return None
        carved_min = bounds_min[axis_index] + source_span * float(u_start)
        carved_max = bounds_min[axis_index] + source_span * float(u_end)
        bounds_min[axis_index] = carved_min
        bounds_max[axis_index] = carved_max
        extents = tuple(bounds_max[index] - bounds_min[index] for index in range(3))
        center = tuple((bounds_min[index] + bounds_max[index]) * 0.5 for index in range(3))
        return {
            "method": "exact_box_axis_interval_carve_v1",
            "primitive_type": "box",
            "required_capabilities": ["box", "to_trimesh"],
            "build_params": {
                "center": center,
                "extents": extents,
                "part": "carved_box",
            },
            "source_primitive_type": "box",
            "result_primitive_type": "box",
            "result_axis": axis,
            "result_extents": extents,
            "source_min_cm": float(box["bounds_min"][axis_index]),
            "source_max_cm": float(box["bounds_max"][axis_index]),
            "source_span_cm": source_span,
            "carved_min_cm": carved_min,
            "carved_max_cm": carved_max,
            "carved_span_cm": carved_max - carved_min,
        }

    cylinder = _cylinder_metadata(mesh)
    if cylinder is not None and str(cylinder["axis"]) == axis:
        center, carved_height, carved_min, carved_max = _axis_interval_center_and_span(
            tuple(float(value) for value in cylinder["center"]),
            axis=axis,
            span=float(cylinder["height"]),
            u_start=u_start,
            u_end=u_end,
        )
        return {
            "method": "exact_cylinder_axis_interval_carve_v1",
            "primitive_type": "cylinder",
            "required_capabilities": ["cylinder", "to_trimesh"],
            "build_params": {
                "center": center,
                "axis": axis,
                "radius": float(cylinder["radius"]),
                "height": carved_height,
                "part": "carved_cylinder",
            },
            "source_primitive_type": "cylinder",
            "result_primitive_type": "cylinder",
            "result_axis": axis,
            "result_radius": float(cylinder["radius"]),
            "result_height": carved_height,
            "source_min_cm": float(cylinder["center"][_axis_index(axis)]) - float(cylinder["height"]) * 0.5,
            "source_max_cm": float(cylinder["center"][_axis_index(axis)]) + float(cylinder["height"]) * 0.5,
            "source_span_cm": float(cylinder["height"]),
            "carved_min_cm": carved_min,
            "carved_max_cm": carved_max,
            "carved_span_cm": carved_height,
        }

    profile = _extruded_profile_metadata(mesh)
    if profile is not None and str(profile["axis"]) == axis:
        if abs(float(profile["extrude_twist_degrees"])) > 1e-9:
            return None
        source_height = float(profile["extrude_height"])
        center, carved_height, carved_min, carved_max = _axis_interval_center_and_span(
            tuple(float(value) for value in profile["center"]),
            axis=axis,
            span=source_height,
            u_start=u_start,
            u_end=u_end,
        )
        source_start_scale = float(profile["extrude_start_scale"])
        source_end_scale = float(profile["extrude_end_scale"])
        result_start_scale = source_start_scale + (source_end_scale - source_start_scale) * float(u_start)
        result_end_scale = source_start_scale + (source_end_scale - source_start_scale) * float(u_end)
        shape = dict(profile["shape"])
        shape["center"] = center
        shape["axis"] = axis
        shape["extrude_height"] = carved_height
        shape["extrude_start_scale"] = result_start_scale
        shape["extrude_end_scale"] = result_end_scale
        shape["extrude_twist_degrees"] = None
        shape["part"] = "carved_extruded_profile"
        return {
            "method": "exact_extruded_profile_axis_interval_carve_v1",
            "primitive_type": "extruded_profile",
            "required_capabilities": ["extruded_profile", "to_trimesh"],
            "build_params": shape,
            "source_primitive_type": "extruded_profile",
            "result_primitive_type": "extruded_profile",
            "result_axis": axis,
            "result_height": carved_height,
            "result_profile_point_count": len(profile["profile_polygon"]),
            "result_start_scale": result_start_scale,
            "result_end_scale": result_end_scale,
            "source_min_cm": float(profile["center"][_axis_index(axis)]) - source_height * 0.5,
            "source_max_cm": float(profile["center"][_axis_index(axis)]) + source_height * 0.5,
            "source_span_cm": source_height,
            "carved_min_cm": carved_min,
            "carved_max_cm": carved_max,
            "carved_span_cm": carved_height,
        }
    return None


def _axis_extruded_center_and_span(
    center: tuple[float, float, float],
    *,
    axis: str,
    span: float,
    distance: float,
) -> tuple[tuple[float, float, float], float, float, float, float]:
    axis_index = _axis_index(axis)
    source_min = float(center[axis_index]) - float(span) * 0.5
    source_max = float(center[axis_index]) + float(span) * 0.5
    result_min = source_min + min(0.0, float(distance))
    result_max = source_max + max(0.0, float(distance))
    result_span = max(result_max - result_min, 1e-6)
    result_center = list(float(value) for value in center)
    result_center[axis_index] = (result_min + result_max) * 0.5
    return (
        (float(result_center[0]), float(result_center[1]), float(result_center[2])),
        result_span,
        source_min,
        source_max,
        result_min,
    )


def _exact_primitive_polyextrude_params(
    mesh: trimesh.Trimesh,
    *,
    axis: str,
    distance_cm: float,
) -> dict[str, Any] | None:
    distance = float(distance_cm)
    if abs(distance) <= 1e-9:
        return None
    box = _axis_aligned_box_metadata(mesh)
    if box is not None:
        axis_index = _axis_index(axis)
        bounds_min = list(float(value) for value in box["bounds_min"])
        bounds_max = list(float(value) for value in box["bounds_max"])
        source_min = float(bounds_min[axis_index])
        source_max = float(bounds_max[axis_index])
        if distance >= 0.0:
            bounds_max[axis_index] += distance
        else:
            bounds_min[axis_index] += distance
        extents = tuple(bounds_max[index] - bounds_min[index] for index in range(3))
        if not _positive_triplet(extents):
            return None
        center = tuple((bounds_min[index] + bounds_max[index]) * 0.5 for index in range(3))
        return {
            "method": "exact_box_axis_polyextrude_v1",
            "primitive_type": "box",
            "required_capabilities": ["box", "to_trimesh"],
            "build_params": {
                "center": center,
                "extents": extents,
                "part": "polyextruded_box",
            },
            "source_primitive_type": "box",
            "result_primitive_type": "box",
            "result_axis": axis,
            "result_extents": extents,
            "source_min_cm": source_min,
            "source_max_cm": source_max,
            "source_extent_cm": source_max - source_min,
            "result_min_cm": float(bounds_min[axis_index]),
            "result_max_cm": float(bounds_max[axis_index]),
            "result_extent_cm": float(extents[axis_index]),
            "side": "max" if distance >= 0.0 else "min",
        }

    cylinder = _cylinder_metadata(mesh)
    if cylinder is not None and str(cylinder["axis"]) == axis:
        center, result_height, source_min, source_max, result_min = _axis_extruded_center_and_span(
            tuple(float(value) for value in cylinder["center"]),
            axis=axis,
            span=float(cylinder["height"]),
            distance=distance,
        )
        return {
            "method": "exact_cylinder_axis_polyextrude_v1",
            "primitive_type": "cylinder",
            "required_capabilities": ["cylinder", "to_trimesh"],
            "build_params": {
                "center": center,
                "axis": axis,
                "radius": float(cylinder["radius"]),
                "height": result_height,
                "part": "polyextruded_cylinder",
            },
            "source_primitive_type": "cylinder",
            "result_primitive_type": "cylinder",
            "result_axis": axis,
            "result_radius": float(cylinder["radius"]),
            "result_height": result_height,
            "source_min_cm": source_min,
            "source_max_cm": source_max,
            "source_extent_cm": float(cylinder["height"]),
            "result_min_cm": result_min,
            "result_max_cm": result_min + result_height,
            "result_extent_cm": result_height,
            "side": "max" if distance >= 0.0 else "min",
        }

    profile = _extruded_profile_metadata(mesh)
    if profile is not None and str(profile["axis"]) == axis:
        if (
            abs(float(profile["extrude_twist_degrees"])) > 1e-9
            or abs(float(profile["extrude_start_scale"]) - float(profile["extrude_end_scale"])) > 1e-9
        ):
            return None
        source_height = float(profile["extrude_height"])
        center, result_height, source_min, source_max, result_min = _axis_extruded_center_and_span(
            tuple(float(value) for value in profile["center"]),
            axis=axis,
            span=source_height,
            distance=distance,
        )
        shape = dict(profile["shape"])
        shape["center"] = center
        shape["axis"] = axis
        shape["extrude_height"] = result_height
        shape["part"] = "polyextruded_extruded_profile"
        return {
            "method": "exact_extruded_profile_axis_polyextrude_v1",
            "primitive_type": "extruded_profile",
            "required_capabilities": ["extruded_profile", "to_trimesh"],
            "build_params": shape,
            "source_primitive_type": "extruded_profile",
            "result_primitive_type": "extruded_profile",
            "result_axis": axis,
            "result_height": result_height,
            "result_profile_point_count": len(profile["profile_polygon"]),
            "result_start_scale": float(profile["extrude_start_scale"]),
            "result_end_scale": float(profile["extrude_end_scale"]),
            "source_min_cm": source_min,
            "source_max_cm": source_max,
            "source_extent_cm": source_height,
            "result_min_cm": result_min,
            "result_max_cm": result_min + result_height,
            "result_extent_cm": result_height,
            "side": "max" if distance >= 0.0 else "min",
        }
    return None


def _polyextruded_axis_mesh(
    mesh: trimesh.Trimesh,
    *,
    axis: str,
    distance_cm: float,
) -> tuple[trimesh.Trimesh, dict[str, Any]]:
    axis_index = _axis_index(axis)
    distance = float(distance_cm)
    source_vertices = np.asarray(mesh.vertices, dtype=np.float64)
    source_min, source_max, source_extent = _axis_span(source_vertices, axis_index)
    if abs(distance) <= 1e-9:
        candidate = mesh.copy()
        candidate.metadata.update(dict(mesh.metadata))
        return candidate, {
            "method": "identity_noop_v1",
            "fallback": False,
            "fallback_from": "",
            "fallback_reason": "",
            "axis": axis,
            "distance_cm": 0.0,
            "source_min_cm": source_min,
            "source_max_cm": source_max,
            "source_extent_cm": source_extent,
            "result_extent_cm": source_extent,
        }

    sign = 1.0 if distance >= 0.0 else -1.0
    depth = abs(distance)
    cap_coord = source_max if sign > 0.0 else source_min
    exact_failure: str | None = None
    exact_mesh = None
    exact_details: dict[str, Any] = {}
    try:
        faces = np.asarray(mesh.faces, dtype=np.int64)
        diagonal = float(np.linalg.norm(np.asarray(mesh.bounds[1]) - np.asarray(mesh.bounds[0])))
        tolerance = max(1e-6, diagonal * 1e-7)
        cap_vertex_mask = np.abs(source_vertices[:, axis_index] - cap_coord) <= tolerance
        cap_face_mask = np.asarray(
            [bool(np.all(cap_vertex_mask[face])) for face in faces],
            dtype=bool,
        )
        cap_face_indices = np.nonzero(cap_face_mask)[0]
        if len(cap_face_indices) == 0:
            exact_failure = "no_planar_cap_faces_on_extrude_side"
        else:
            cap_faces = faces[cap_face_indices]
            cap_vertices = sorted({int(index) for face in cap_faces for index in face})
            if len(cap_vertices) < 3:
                exact_failure = "planar_cap_has_too_few_vertices"
            else:
                edge_counts: dict[tuple[int, int], int] = {}
                for face in cap_faces:
                    for offset in range(3):
                        edge = tuple(sorted((int(face[offset]), int(face[(offset + 1) % 3]))))
                        edge_counts[edge] = edge_counts.get(edge, 0) + 1
                boundary_edges = [edge for edge, count in edge_counts.items() if count == 1]
                if not boundary_edges:
                    exact_failure = "planar_cap_boundary_loop_missing"
                else:
                    translation = np.zeros(3, dtype=np.float64)
                    translation[axis_index] = sign * depth
                    new_vertices = source_vertices.tolist()
                    duplicate_index: dict[int, int] = {}
                    for old_index in cap_vertices:
                        duplicate_index[old_index] = len(new_vertices)
                        new_vertices.append((source_vertices[old_index] + translation).tolist())

                    new_faces: list[list[int]] = [
                        [int(value) for value in face]
                        for face in faces[~cap_face_mask].tolist()
                    ]
                    for face in cap_faces.tolist():
                        new_faces.append([duplicate_index[int(value)] for value in face])
                    for left, right in boundary_edges:
                        left_new = duplicate_index[int(left)]
                        right_new = duplicate_index[int(right)]
                        new_faces.append([int(left), int(right), right_new])
                        new_faces.append([int(left), right_new, left_new])

                    candidate = trimesh.Trimesh(
                        vertices=np.asarray(new_vertices, dtype=np.float64),
                        faces=np.asarray(new_faces, dtype=np.int64),
                        process=False,
                    )
                    candidate.metadata.update(dict(mesh.metadata))
                    candidate.remove_unreferenced_vertices()
                    try:
                        candidate.fix_normals()
                    except (AttributeError, TypeError, ValueError, RuntimeError):
                        pass
                    if len(candidate.faces) == 0:
                        exact_failure = "planar_cap_extend_result_empty"
                    elif not bool(candidate.is_watertight):
                        exact_failure = "planar_cap_extend_result_not_watertight"
                    else:
                        exact_mesh = candidate
                        exact_details = {
                            "cap_coordinate_cm": cap_coord,
                            "cap_face_count": int(len(cap_face_indices)),
                            "cap_vertex_count": int(len(cap_vertices)),
                            "cap_boundary_edge_count": int(len(boundary_edges)),
                        }
    except (
        AttributeError,
        IndexError,
        TypeError,
        ValueError,
        RuntimeError,
    ) as exc:
        exact_failure = f"{type(exc).__name__}: {exc}"

    if exact_mesh is not None:
        _, result_max, result_extent = _axis_span(np.asarray(exact_mesh.vertices), axis_index)
        result_min = float(np.asarray(exact_mesh.vertices)[:, axis_index].min())
        return exact_mesh, {
            "method": "axis_planar_cap_polyextrude_v1",
            "fallback": False,
            "fallback_from": "",
            "fallback_reason": "",
            "axis": axis,
            "distance_cm": distance,
            "side": "positive" if sign > 0.0 else "negative",
            "source_min_cm": source_min,
            "source_max_cm": source_max,
            "source_extent_cm": source_extent,
            "result_min_cm": result_min,
            "result_max_cm": result_max,
            "result_extent_cm": result_extent,
            **exact_details,
        }

    measured_mesh: trimesh.Trimesh | None = None
    measured_failure: str | None = None
    measured_details: dict[str, Any] = {}
    try:
        bounds = np.asarray(mesh.bounds, dtype=np.float64)
        source_min_vector = bounds[0].astype(np.float64)
        source_max_vector = bounds[1].astype(np.float64)
        source_span_vector = np.maximum(source_max_vector - source_min_vector, 1e-6)
        tangent_axes = [index for index in range(3) if index != axis_index]
        if any(float(source_span_vector[index]) <= 1e-6 for index in tangent_axes):
            measured_failure = "source_tangent_bounds_collapsed"
        else:
            out_coord = cap_coord + sign * depth
            cap_points: list[list[float]] = []
            for first, second in ((0, 0), (1, 0), (1, 1), (0, 1)):
                point = source_min_vector.copy()
                point[axis_index] = out_coord
                point[tangent_axes[0]] = (
                    source_max_vector[tangent_axes[0]]
                    if first
                    else source_min_vector[tangent_axes[0]]
                )
                point[tangent_axes[1]] = (
                    source_max_vector[tangent_axes[1]]
                    if second
                    else source_min_vector[tangent_axes[1]]
                )
                cap_points.append([float(value) for value in point.tolist()])
            cloud = trimesh.Trimesh(
                vertices=np.vstack([source_vertices, np.asarray(cap_points, dtype=np.float64)]),
                faces=None,
                process=False,
            )
            candidate = cloud.convex_hull
            if not isinstance(candidate, trimesh.Trimesh) or len(candidate.faces) == 0:
                measured_failure = "measured_bounds_cap_hull_result_empty"
            elif not bool(candidate.is_watertight):
                measured_failure = "measured_bounds_cap_hull_result_not_watertight"
            else:
                candidate.metadata.update(dict(mesh.metadata))
                candidate.remove_unreferenced_vertices()
                try:
                    candidate.fix_normals()
                except (AttributeError, TypeError, ValueError, RuntimeError):
                    pass
                measured_mesh = candidate
                measured_details = {
                    "cap_coordinate_cm": cap_coord,
                    "result_cap_coordinate_cm": out_coord,
                    "measured_cap_vertex_count": len(cap_points),
                }
    except (
        AttributeError,
        IndexError,
        TypeError,
        ValueError,
        RuntimeError,
    ) as exc:
        measured_failure = f"{type(exc).__name__}: {exc}"

    if measured_mesh is not None:
        result_min, result_max, result_extent = _axis_span(np.asarray(measured_mesh.vertices), axis_index)
        return measured_mesh, {
            "method": "measured_bounds_cap_hull_polyextrude_v1",
            "fallback": True,
            "fallback_from": "axis_planar_cap_polyextrude_v1",
            "fallback_reason": exact_failure or "planar_cap_extend_unavailable",
            "axis": axis,
            "distance_cm": distance,
            "side": "positive" if sign > 0.0 else "negative",
            "source_min_cm": source_min,
            "source_max_cm": source_max,
            "source_extent_cm": source_extent,
            "result_min_cm": result_min,
            "result_max_cm": result_max,
            "result_extent_cm": result_extent,
            "source_vertex_count": int(len(source_vertices)),
            "source_face_count": int(len(mesh.faces)),
            "result_face_count": int(len(measured_mesh.faces)),
            "result_vertex_count": int(len(measured_mesh.vertices)),
            "result_watertight": bool(measured_mesh.is_watertight),
            **measured_details,
        }

    anchor = source_min if sign > 0.0 else source_max
    scale = (source_extent + depth) / source_extent
    transformed = source_vertices.copy()
    transformed[:, axis_index] = anchor + (transformed[:, axis_index] - anchor) * scale
    fallback = _mesh_with_vertices(mesh, transformed)
    result_min, result_max, result_extent = _axis_span(np.asarray(fallback.vertices), axis_index)
    return fallback, {
        "method": "axis_interval_scale_polyextrude_v1",
        "fallback": True,
        "fallback_from": "measured_bounds_cap_hull_polyextrude_v1",
        "fallback_chain": [
            "axis_planar_cap_polyextrude_v1",
            "measured_bounds_cap_hull_polyextrude_v1",
        ],
        "fallback_reason": measured_failure or exact_failure or "measured_bounds_cap_hull_unavailable",
        "exact_polyextrude_failure": exact_failure or "",
        "measured_polyextrude_failure": measured_failure or "",
        "axis": axis,
        "distance_cm": distance,
        "side": "positive" if sign > 0.0 else "negative",
        "source_min_cm": source_min,
        "source_max_cm": source_max,
        "source_extent_cm": source_extent,
        "result_min_cm": result_min,
        "result_max_cm": result_max,
        "result_extent_cm": result_extent,
    }


def _non_empty_mesh(kernel: GeometryKernel, handle: Any) -> trimesh.Trimesh:
    mesh = kernel.to_trimesh(handle)
    if not isinstance(mesh, trimesh.Trimesh) or len(mesh.faces) == 0:
        raise ValueError("kernel program produced an empty or non-mesh result")
    return mesh


def _numeric_triplet(value: Any) -> tuple[float, float, float] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        return None
    try:
        out = tuple(float(item) for item in value)
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(item) for item in out):
        return None
    return out  # type: ignore[return-value]


def _positive_triplet(value: tuple[float, float, float]) -> bool:
    return all(item > 0.0 and math.isfinite(item) for item in value)


def _numeric_pair(value: Any) -> tuple[float, float] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return None
    try:
        out = (float(value[0]), float(value[1]))
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(item) for item in out):
        return None
    return out


def _profile_polygon_2d(value: Any) -> tuple[tuple[float, float], ...] | None:
    if not isinstance(value, (list, tuple)) or len(value) < 3:
        return None
    points: list[tuple[float, float]] = []
    for item in value:
        point = _numeric_pair(item)
        if point is None:
            return None
        points.append(point)
    return tuple(points)


def _rotate_profile_polygon_2d(
    polygon: tuple[tuple[float, float], ...],
    angle_degrees: float,
) -> tuple[tuple[float, float], ...]:
    if abs(angle_degrees) <= 1e-12:
        return polygon
    angle = math.radians(float(angle_degrees))
    cos_value = math.cos(angle)
    sin_value = math.sin(angle)
    return tuple(
        (
            float(u) * cos_value - float(v) * sin_value,
            float(u) * sin_value + float(v) * cos_value,
        )
        for u, v in polygon
    )


def _box_metadata_from_bounds(
    bounds_min: tuple[float, float, float],
    bounds_max: tuple[float, float, float],
    *,
    source: str,
) -> dict[str, Any] | None:
    extents = tuple(bounds_max[axis] - bounds_min[axis] for axis in range(3))
    if not _positive_triplet(extents):
        return None
    center = tuple((bounds_min[axis] + bounds_max[axis]) * 0.5 for axis in range(3))
    return {
        "source": source,
        "center": center,
        "extents": extents,
        "bounds_min": bounds_min,
        "bounds_max": bounds_max,
    }


def _axis_aligned_box_metadata(mesh: trimesh.Trimesh) -> dict[str, Any] | None:
    metadata = mesh.metadata if isinstance(mesh.metadata, dict) else {}
    shape = metadata.get("lathe_shape_primitive")
    if isinstance(shape, dict) and str(shape.get("primitive_type") or "") == "box":
        try:
            rounding = float(shape.get("rounding") or shape.get("rounding_cm") or 0.0)
        except (TypeError, ValueError):
            rounding = 0.0
        if rounding > 1e-9:
            return None
        for modifier_name in (
            "v2_polybevel_modifier",
            "v2_subdivision_modifier",
            "v2_remesh_modifier",
        ):
            if shape.get(modifier_name) not in (None, {}, [], ()):
                return None
        extents = _numeric_triplet(shape.get("extents"))
        center = _numeric_triplet(shape.get("center")) or (0.0, 0.0, 0.0)
        if extents is not None and _positive_triplet(extents):
            half = tuple(item * 0.5 for item in extents)
            return {
                "source": "lathe_shape_primitive",
                "center": center,
                "extents": extents,
                "bounds_min": tuple(center[axis] - half[axis] for axis in range(3)),
                "bounds_max": tuple(center[axis] + half[axis] for axis in range(3)),
            }

    reference = metadata.get("lathe_reference_primitive")
    if isinstance(reference, dict) and str(reference.get("kind") or "") == "box":
        bounds_min = _numeric_triplet(reference.get("bounds_min"))
        bounds_max = _numeric_triplet(reference.get("bounds_max"))
        if bounds_min is not None and bounds_max is not None:
            return _box_metadata_from_bounds(
                bounds_min,
                bounds_max,
                source="lathe_reference_primitive",
            )
    return None


def _extruded_profile_metadata(mesh: trimesh.Trimesh) -> dict[str, Any] | None:
    metadata = mesh.metadata if isinstance(mesh.metadata, dict) else {}
    shape = metadata.get("lathe_shape_primitive")
    if not isinstance(shape, dict) or str(shape.get("primitive_type") or "") != "extruded_profile":
        return None
    polygon = _profile_polygon_2d(shape.get("profile_polygon"))
    if polygon is None:
        return None
    try:
        height = float(shape.get("extrude_height"))
    except (TypeError, ValueError):
        return None
    if height <= 0.0 or not math.isfinite(height):
        return None
    axis = str(shape.get("axis") or "y")
    if axis not in {"x", "y", "z"}:
        return None
    center = _numeric_triplet(shape.get("center")) or (0.0, 0.0, 0.0)
    start_scale = shape.get("extrude_start_scale")
    end_scale = shape.get("extrude_end_scale")
    twist = shape.get("extrude_twist_degrees")
    segments = shape.get("extrude_segments")

    def optional_float(value: Any, default: float) -> float:
        if value is None:
            return default
        parsed = float(value)
        if not math.isfinite(parsed):
            raise ValueError
        return parsed

    def optional_int(value: Any, default: int) -> int:
        if value is None:
            return default
        parsed = int(value)
        if parsed < 1:
            raise ValueError
        return parsed

    try:
        parsed_start_scale = optional_float(start_scale, 1.0)
        parsed_end_scale = optional_float(end_scale, 1.0)
        parsed_twist = optional_float(twist, 0.0)
        parsed_segments = optional_int(segments, 1)
    except (TypeError, ValueError):
        return None
    if parsed_start_scale <= 0.0 or parsed_end_scale <= 0.0:
        return None
    return {
        "source": "lathe_shape_primitive",
        "shape": dict(shape),
        "center": center,
        "axis": axis,
        "profile_polygon": polygon,
        "extrude_height": height,
        "extrude_start_scale": parsed_start_scale,
        "extrude_end_scale": parsed_end_scale,
        "extrude_twist_degrees": parsed_twist,
        "extrude_segments": parsed_segments,
    }


def _exact_extruded_profile_deform_params(
    mesh: trimesh.Trimesh,
    *,
    operation: str,
    axis: str,
    angle_degrees: float | None,
    start_scale: float | None,
    end_scale: float | None,
    origin: list[float] | None,
    segments: int | None,
    subdivision_levels: int | None,
) -> dict[str, Any] | None:
    profile = _extruded_profile_metadata(mesh)
    if profile is None or str(profile["axis"]) != axis:
        return None
    if origin is not None:
        origin_tuple = tuple(float(value) for value in origin)
        center = tuple(float(value) for value in profile["center"])
        if any(abs(origin_tuple[index] - center[index]) > 1e-7 for index in range(3)):
            return None
    if operation not in {"sop.twist", "sop.taper"}:
        return None
    existing_start = float(profile["extrude_start_scale"])
    existing_end = float(profile["extrude_end_scale"])
    existing_twist = float(profile["extrude_twist_degrees"])
    existing_segments = int(profile["extrude_segments"])
    polygon = tuple(profile["profile_polygon"])
    method = ""
    result_start = existing_start
    result_end = existing_end
    result_twist = existing_twist
    result_polygon = polygon
    if operation == "sop.twist":
        angle = _finite_float(angle_degrees, field="angle_degrees")
        if abs(existing_start - existing_end) > 1e-9:
            return None
        result_polygon = _rotate_profile_polygon_2d(polygon, -0.5 * angle)
        result_twist = existing_twist + angle
        method = "exact_extruded_profile_twist_rebuild_v1"
    else:
        start = _finite_float(1.0 if start_scale is None else start_scale, field="start_scale")
        end = _finite_float(end_scale, field="end_scale")
        if start <= 0.0 or end <= 0.0:
            raise ValueError("kernel deform taper scale values must be > 0")
        if abs(existing_twist) > 1e-9 or abs(existing_start - existing_end) > 1e-9:
            return None
        result_start = existing_start * start
        result_end = existing_end * end
        method = "exact_extruded_profile_taper_rebuild_v1"
    requested_segments = segments
    if requested_segments is None and subdivision_levels is not None:
        requested_segments = max(1, 2 ** int(subdivision_levels))
    twist_segments = max(existing_segments, 1)
    if operation == "sop.twist":
        twist_segments = max(twist_segments, int(math.ceil(abs(result_twist) / 30.0)))
    if requested_segments is not None:
        twist_segments = max(twist_segments, int(requested_segments))
    twist_segments = max(1, min(96, twist_segments))
    shape = dict(profile["shape"])
    shape["profile_polygon"] = [tuple(point) for point in result_polygon]
    shape["extrude_start_scale"] = result_start
    shape["extrude_end_scale"] = result_end
    shape["extrude_twist_degrees"] = result_twist if abs(result_twist) > 1e-9 else None
    shape["extrude_segments"] = twist_segments
    shape["semantic_metadata"] = dict(_dict_metadata(shape.get("semantic_metadata")))
    shape["semantic_metadata"]["exact_deform_rebuild"] = {
        "schema": "lathe.geometry.exact_extruded_profile_deform.v1",
        "method": method,
        "operation": operation,
        "source_axis": axis,
        "source_start_scale": existing_start,
        "source_end_scale": existing_end,
        "source_twist_degrees": existing_twist,
        "result_start_scale": result_start,
        "result_end_scale": result_end,
        "result_twist_degrees": result_twist,
        "result_segments": twist_segments,
    }
    return {
        "method": method,
        "primitive_type": "extruded_profile",
        "required_capabilities": ["extruded_profile", "to_trimesh"],
        "build_params": shape,
        "source_profile": profile,
        "result_profile_point_count": len(result_polygon),
        "result_start_scale": result_start,
        "result_end_scale": result_end,
        "result_twist_degrees": result_twist,
        "result_segments": twist_segments,
    }


def _origin_matches_center(
    origin: list[float] | None,
    center: tuple[float, float, float],
    *,
    tolerance: float = 1e-7,
) -> bool:
    if origin is None:
        return True
    return all(abs(float(origin[index]) - float(center[index])) <= tolerance for index in range(3))


def _capsule_taper_profile_points(
    *,
    radius: float,
    length: float,
    start_scale: float,
    end_scale: float,
    segments: int,
) -> tuple[tuple[float, float], ...]:
    sample_count = max(16, min(128, int(segments)))
    shaft = max(0.0, float(length) - 2.0 * float(radius))
    half_shaft = shaft * 0.5
    half_length = float(length) * 0.5
    points: list[tuple[float, float]] = []
    for index in range(sample_count + 1):
        axial = -half_length + float(length) * (index / float(sample_count))
        if axial < -half_shaft:
            local = axial + half_shaft
            base_radius = math.sqrt(max(0.0, float(radius) ** 2 - local * local))
        elif axial > half_shaft:
            local = axial - half_shaft
            base_radius = math.sqrt(max(0.0, float(radius) ** 2 - local * local))
        else:
            base_radius = float(radius)
        t = (axial + half_length) / max(float(length), 1e-9)
        scale = start_scale + (end_scale - start_scale) * t
        points.append((float(axial), max(0.0, base_radius * scale)))
    return tuple(points)


def _curved_tube_basis_axes(plane_axis: str) -> tuple[str, str] | None:
    if plane_axis == "x":
        return "y", "z"
    if plane_axis == "y":
        return "x", "z"
    if plane_axis == "z":
        return "x", "y"
    return None


def _remaining_axis(first_axis: str, second_axis: str) -> str | None:
    axes = {"x", "y", "z"}
    remaining = axes - {first_axis, second_axis}
    if len(remaining) != 1:
        return None
    return next(iter(remaining))


def _axis_unit_vector(axis: str) -> tuple[float, float, float]:
    vector = [0.0, 0.0, 0.0]
    vector[_axis_index(axis)] = 1.0
    return (float(vector[0]), float(vector[1]), float(vector[2]))


def _round_primitive_deform_params(
    mesh: trimesh.Trimesh,
    *,
    operation: str,
    axis: str,
    angle_degrees: float | None,
    start_scale: float | None,
    end_scale: float | None,
    direction_axis: str | None,
    origin: list[float] | None,
    segments: int | None,
    subdivision_levels: int | None,
) -> dict[str, Any] | None:
    sphere = _sphere_metadata(mesh)
    cylinder = _cylinder_metadata(mesh)
    capsule = _capsule_metadata(mesh)
    source = sphere or cylinder or capsule
    if source is None:
        return None
    center = tuple(float(value) for value in source["center"])
    if not _origin_matches_center(origin, center):
        return None
    requested_segments = segments
    if requested_segments is None and subdivision_levels is not None:
        requested_segments = max(1, 2 ** int(subdivision_levels))
    result_segments = max(1, min(128, int(requested_segments or 24)))

    if operation == "sop.twist":
        _finite_float(angle_degrees, field="angle_degrees")
        if sphere is not None:
            return {
                "method": "exact_axisymmetric_sphere_twist_noop_v1",
                "primitive_type": "sphere",
                "required_capabilities": ["sphere", "to_trimesh"],
                "exact": True,
                "build_params": {
                    "center": center,
                    "radius": float(sphere["radius"]),
                    "part": "deformed_sphere",
                },
                "source_profile": {"center": center, "primitive_type": "sphere"},
                "result_radius": float(sphere["radius"]),
                "result_profile_point_count": 0,
                "result_start_scale": 1.0,
                "result_end_scale": 1.0,
                "result_twist_degrees": float(angle_degrees or 0.0),
                "result_segments": result_segments,
                "result_primitive_type": "sphere",
            }
        round_source = cylinder or capsule
        if round_source is None or str(round_source["axis"]) != axis:
            return None
        primitive_type = "cylinder" if cylinder is not None else "capsule"
        build_params = {
            "center": center,
            "axis": axis,
            "part": f"deformed_{primitive_type}",
        }
        if cylinder is not None:
            build_params.update(
                {
                    "radius": float(cylinder["radius"]),
                    "height": float(cylinder["height"]),
                }
            )
        else:
            build_params.update(
                {
                    "radius": float(capsule["radius"]),
                    "length": float(capsule["length"]),
                }
            )
        return {
            "method": f"exact_axisymmetric_{primitive_type}_twist_noop_v1",
            "primitive_type": primitive_type,
            "required_capabilities": [primitive_type, "to_trimesh"],
            "exact": True,
            "build_params": build_params,
            "source_profile": {"center": center, "primitive_type": primitive_type},
            "result_axis": axis,
            "result_radius": float(round_source["radius"]),
            **(
                {"result_height": float(cylinder["height"])}
                if cylinder is not None
                else {"result_length": float(capsule["length"])}
            ),
            "result_profile_point_count": 0,
            "result_start_scale": 1.0,
            "result_end_scale": 1.0,
            "result_twist_degrees": float(angle_degrees or 0.0),
            "result_segments": result_segments,
            "result_primitive_type": primitive_type,
        }

    if operation == "sop.bend":
        if cylinder is None:
            return None
        if str(cylinder["axis"]) != axis:
            return None
        bend_angle = _finite_float(angle_degrees, field="angle_degrees")
        if abs(bend_angle) <= 1e-9 or abs(bend_angle) > 330.0:
            return None
        bend_axis = direction_axis
        if bend_axis is None:
            first, _ = _perpendicular_axis_indices(axis)
            bend_axis = _axis_name_from_index(first)
        if bend_axis == axis:
            return None
        plane_axis = _remaining_axis(axis, bend_axis)
        if plane_axis is None:
            return None
        basis = _curved_tube_basis_axes(plane_axis)
        if basis is None:
            return None
        radius = float(cylinder["radius"])
        height = float(cylinder["height"])
        bend_radius = height / abs(math.radians(bend_angle))
        if radius >= bend_radius:
            return None
        basis_u, basis_v = basis
        if basis_u == bend_axis and basis_v == axis:
            path_angle = bend_angle
            start_angle = -0.5 * bend_angle
        elif basis_u == axis and basis_v == bend_axis:
            path_angle = -bend_angle
            start_angle = 90.0 + 0.5 * bend_angle
        else:
            return None
        direction_vector = _axis_unit_vector(bend_axis)
        bend_center = tuple(
            center[index] - direction_vector[index] * bend_radius
            for index in range(3)
        )
        path_segments = max(
            8,
            min(
                256,
                int(segments or math.ceil(abs(bend_angle) / 10.0)),
            ),
        )
        cross_section_segments = max(8, min(128, int(segments or 32)))
        return {
            "method": "exact_cylinder_bend_curved_tube_v1",
            "primitive_type": "curved_tube",
            "required_capabilities": ["curved_tube", "to_trimesh"],
            "exact": True,
            "build_params": {
                "center": bend_center,
                "radius": bend_radius,
                "tube_radius": radius,
                "angle_degrees": path_angle,
                "start_angle_degrees": start_angle,
                "plane_axis": plane_axis,
                "path_segments": path_segments,
                "cross_section_segments": cross_section_segments,
                "part": "deformed_cylinder_bend",
            },
            "source_profile": {"center": center, "primitive_type": "cylinder"},
            "result_primitive_type": "curved_tube",
            "result_axis": axis,
            "result_direction_axis": bend_axis,
            "result_plane_axis": plane_axis,
            "result_radius": bend_radius,
            "result_tube_radius": radius,
            "result_height": height,
            "result_angle_degrees": path_angle,
            "result_start_angle_degrees": start_angle,
            "result_profile_point_count": cross_section_segments,
            "result_segments": path_segments,
        }

    if operation != "sop.taper":
        return None
    start = _finite_float(1.0 if start_scale is None else start_scale, field="start_scale")
    end = _finite_float(end_scale, field="end_scale")
    if start <= 0.0 or end <= 0.0:
        raise ValueError("kernel deform taper scale values must be > 0")
    if cylinder is not None:
        if str(cylinder["axis"]) != axis:
            return None
        radius = float(cylinder["radius"])
        height = float(cylinder["height"])
        profile_points = (
            (-height * 0.5, radius * start),
            (height * 0.5, radius * end),
        )
        return {
            "method": "exact_cylinder_taper_revolved_profile_v1",
            "primitive_type": "revolved_profile",
            "required_capabilities": ["revolved_profile", "to_trimesh"],
            "exact": True,
            "build_params": {
                "center": center,
                "axis": axis,
                "profile_points": profile_points,
                "part": "deformed_cylinder_taper",
            },
            "source_profile": {"center": center, "primitive_type": "cylinder"},
            "result_axis": axis,
            "result_radius": max(radius * start, radius * end),
            "result_start_radius": radius * start,
            "result_end_radius": radius * end,
            "result_height": height,
            "result_profile_point_count": len(profile_points),
            "result_start_scale": start,
            "result_end_scale": end,
            "result_twist_degrees": 0.0,
            "result_segments": result_segments,
            "result_primitive_type": "revolved_profile",
        }
    if capsule is not None:
        if str(capsule["axis"]) != axis:
            return None
        profile_points = _capsule_taper_profile_points(
            radius=float(capsule["radius"]),
            length=float(capsule["length"]),
            start_scale=start,
            end_scale=end,
            segments=result_segments,
        )
        return {
            "method": "sampled_capsule_taper_revolved_profile_v1",
            "primitive_type": "revolved_profile",
            "required_capabilities": ["revolved_profile", "to_trimesh"],
            "build_params": {
                "center": center,
                "axis": axis,
                "profile_points": profile_points,
                "part": "deformed_capsule_taper",
            },
            "source_profile": {"center": center, "primitive_type": "capsule"},
            "result_axis": axis,
            "result_radius": max(float(capsule["radius"]) * start, float(capsule["radius"]) * end),
            "result_start_radius": float(capsule["radius"]) * start,
            "result_end_radius": float(capsule["radius"]) * end,
            "result_length": float(capsule["length"]),
            "result_profile_point_count": len(profile_points),
            "result_start_scale": start,
            "result_end_scale": end,
            "result_twist_degrees": 0.0,
            "result_segments": result_segments,
            "result_primitive_type": "revolved_profile",
            "exact": False,
            "approximation": "sampled_capsule_taper_profile",
        }
    return None


def _sphere_metadata(mesh: trimesh.Trimesh) -> dict[str, Any] | None:
    metadata = mesh.metadata if isinstance(mesh.metadata, dict) else {}
    shape = metadata.get("lathe_shape_primitive")
    if not isinstance(shape, dict) or str(shape.get("primitive_type") or "") != "sphere":
        return None
    try:
        radius = float(shape.get("radius"))
    except (TypeError, ValueError):
        return None
    if radius <= 0.0 or not math.isfinite(radius):
        return None
    center = _numeric_triplet(shape.get("center")) or (0.0, 0.0, 0.0)
    return {
        "source": "lathe_shape_primitive",
        "center": center,
        "radius": radius,
    }


def _cylinder_metadata(mesh: trimesh.Trimesh) -> dict[str, Any] | None:
    metadata = mesh.metadata if isinstance(mesh.metadata, dict) else {}
    shape = metadata.get("lathe_shape_primitive")
    if not isinstance(shape, dict) or str(shape.get("primitive_type") or "") != "cylinder":
        return None
    try:
        radius = float(shape.get("radius"))
        height = float(shape.get("height"))
    except (TypeError, ValueError):
        return None
    if radius <= 0.0 or height <= 0.0 or not math.isfinite(radius) or not math.isfinite(height):
        return None
    axis = str(shape.get("axis") or "y")
    if axis not in {"x", "y", "z"}:
        return None
    center = _numeric_triplet(shape.get("center")) or (0.0, 0.0, 0.0)
    return {
        "source": "lathe_shape_primitive",
        "center": center,
        "radius": radius,
        "height": height,
        "axis": axis,
    }


def _capsule_metadata(mesh: trimesh.Trimesh) -> dict[str, Any] | None:
    metadata = mesh.metadata if isinstance(mesh.metadata, dict) else {}
    shape = metadata.get("lathe_shape_primitive")
    if not isinstance(shape, dict) or str(shape.get("primitive_type") or "") != "capsule":
        return None
    try:
        radius = float(shape.get("radius"))
        length = float(shape.get("length"))
    except (TypeError, ValueError):
        return None
    if radius <= 0.0 or length <= 2.0 * radius or not math.isfinite(radius) or not math.isfinite(length):
        return None
    axis = str(shape.get("axis") or "y")
    if axis not in {"x", "y", "z"}:
        return None
    center = _numeric_triplet(shape.get("center")) or (0.0, 0.0, 0.0)
    return {
        "source": "lathe_shape_primitive",
        "center": center,
        "radius": radius,
        "length": length,
        "axis": axis,
        "shaft_length": length - 2.0 * radius,
    }


def _exact_axis_aligned_box_minkowski_params(
    source_mesh: trimesh.Trimesh,
    structuring_mesh: trimesh.Trimesh,
    *,
    structuring_center: tuple[float, float, float],
) -> dict[str, Any] | None:
    source_box = _axis_aligned_box_metadata(source_mesh)
    structuring_box = _axis_aligned_box_metadata(structuring_mesh)
    if source_box is None or structuring_box is None:
        return None
    center_offset = tuple(
        float(structuring_box["center"][axis]) - float(structuring_center[axis])
        for axis in range(3)
    )
    center = tuple(
        float(source_box["center"][axis]) + center_offset[axis]
        for axis in range(3)
    )
    extents = tuple(
        float(source_box["extents"][axis]) + float(structuring_box["extents"][axis])
        for axis in range(3)
    )
    if not _positive_triplet(extents):
        return None
    return {
        "center": center,
        "extents": extents,
        "source_box": source_box,
        "structuring_box": structuring_box,
        "structuring_center": structuring_center,
        "structuring_center_offset": center_offset,
    }


def _exact_axis_aligned_box_sphere_minkowski_params(
    source_mesh: trimesh.Trimesh,
    structuring_mesh: trimesh.Trimesh,
    *,
    structuring_center: tuple[float, float, float],
) -> dict[str, Any] | None:
    source_box = _axis_aligned_box_metadata(source_mesh)
    structuring_sphere = _sphere_metadata(structuring_mesh)
    if source_box is not None and structuring_sphere is not None:
        radius = float(structuring_sphere["radius"])
        center_offset = tuple(
            float(structuring_sphere["center"][axis]) - float(structuring_center[axis])
            for axis in range(3)
        )
        center = tuple(
            float(source_box["center"][axis]) + center_offset[axis]
            for axis in range(3)
        )
        extents = tuple(float(source_box["extents"][axis]) + 2.0 * radius for axis in range(3))
        if _positive_triplet(extents) and radius <= min(extents) * 0.5 * 0.92:
            return {
                "center": center,
                "extents": extents,
                "rounding": radius,
                "source_box": source_box,
                "structuring_sphere": structuring_sphere,
                "structuring_center": structuring_center,
                "structuring_center_offset": center_offset,
            }

    source_sphere = _sphere_metadata(source_mesh)
    structuring_box = _axis_aligned_box_metadata(structuring_mesh)
    if source_sphere is not None and structuring_box is not None:
        radius = float(source_sphere["radius"])
        center = tuple(
            float(source_sphere["center"][axis])
            + float(structuring_box["center"][axis])
            - float(structuring_center[axis])
            for axis in range(3)
        )
        extents = tuple(float(structuring_box["extents"][axis]) + 2.0 * radius for axis in range(3))
        if _positive_triplet(extents) and radius <= min(extents) * 0.5 * 0.92:
            return {
                "center": center,
                "extents": extents,
                "rounding": radius,
                "source_sphere": source_sphere,
                "structuring_box": structuring_box,
                "structuring_center": structuring_center,
                "structuring_center_offset": tuple(
                    float(structuring_box["center"][axis]) - float(structuring_center[axis])
                    for axis in range(3)
                ),
            }
    return None


def _exact_sphere_sphere_minkowski_params(
    source_mesh: trimesh.Trimesh,
    structuring_mesh: trimesh.Trimesh,
    *,
    structuring_center: tuple[float, float, float],
) -> dict[str, Any] | None:
    source_sphere = _sphere_metadata(source_mesh)
    structuring_sphere = _sphere_metadata(structuring_mesh)
    if source_sphere is None or structuring_sphere is None:
        return None
    radius = float(source_sphere["radius"]) + float(structuring_sphere["radius"])
    if radius <= 0.0 or not math.isfinite(radius):
        return None
    center_offset = tuple(
        float(structuring_sphere["center"][axis]) - float(structuring_center[axis])
        for axis in range(3)
    )
    center = tuple(
        float(source_sphere["center"][axis]) + center_offset[axis]
        for axis in range(3)
    )
    return {
        "center": center,
        "radius": radius,
        "source_sphere": source_sphere,
        "structuring_sphere": structuring_sphere,
        "structuring_center": structuring_center,
        "structuring_center_offset": center_offset,
    }


def _exact_cylinder_sphere_minkowski_params(
    source_mesh: trimesh.Trimesh,
    structuring_mesh: trimesh.Trimesh,
    *,
    structuring_center: tuple[float, float, float],
) -> dict[str, Any] | None:
    source_cylinder = _cylinder_metadata(source_mesh)
    structuring_sphere = _sphere_metadata(structuring_mesh)
    if source_cylinder is not None and structuring_sphere is not None:
        sphere_radius = float(structuring_sphere["radius"])
        center_offset = tuple(
            float(structuring_sphere["center"][axis]) - float(structuring_center[axis])
            for axis in range(3)
        )
        center = tuple(
            float(source_cylinder["center"][axis]) + center_offset[axis]
            for axis in range(3)
        )
        radius = float(source_cylinder["radius"]) + sphere_radius
        length = float(source_cylinder["height"]) + 2.0 * sphere_radius
        if length > 2.0 * radius and radius > 0.0:
            return {
                "center": center,
                "radius": radius,
                "length": length,
                "axis": str(source_cylinder["axis"]),
                "source_cylinder": source_cylinder,
                "structuring_sphere": structuring_sphere,
                "structuring_center": structuring_center,
                "structuring_center_offset": center_offset,
            }

    source_sphere = _sphere_metadata(source_mesh)
    structuring_cylinder = _cylinder_metadata(structuring_mesh)
    if source_sphere is not None and structuring_cylinder is not None:
        sphere_radius = float(source_sphere["radius"])
        center = tuple(
            float(source_sphere["center"][axis])
            + float(structuring_cylinder["center"][axis])
            - float(structuring_center[axis])
            for axis in range(3)
        )
        radius = float(structuring_cylinder["radius"]) + sphere_radius
        length = float(structuring_cylinder["height"]) + 2.0 * sphere_radius
        if length > 2.0 * radius and radius > 0.0:
            return {
                "center": center,
                "radius": radius,
                "length": length,
                "axis": str(structuring_cylinder["axis"]),
                "source_sphere": source_sphere,
                "structuring_cylinder": structuring_cylinder,
                "structuring_center": structuring_center,
                "structuring_center_offset": tuple(
                    float(structuring_cylinder["center"][axis]) - float(structuring_center[axis])
                    for axis in range(3)
                ),
            }
    return None


def _exact_cylinder_cylinder_minkowski_params(
    source_mesh: trimesh.Trimesh,
    structuring_mesh: trimesh.Trimesh,
    *,
    structuring_center: tuple[float, float, float],
) -> dict[str, Any] | None:
    source_cylinder = _cylinder_metadata(source_mesh)
    structuring_cylinder = _cylinder_metadata(structuring_mesh)
    if source_cylinder is None or structuring_cylinder is None:
        return None
    source_axis = str(source_cylinder["axis"])
    structuring_axis = str(structuring_cylinder["axis"])
    if source_axis != structuring_axis:
        return None
    radius = float(source_cylinder["radius"]) + float(structuring_cylinder["radius"])
    height = float(source_cylinder["height"]) + float(structuring_cylinder["height"])
    if radius <= 0.0 or height <= 0.0 or not math.isfinite(radius) or not math.isfinite(height):
        return None
    center_offset = tuple(
        float(structuring_cylinder["center"][axis]) - float(structuring_center[axis])
        for axis in range(3)
    )
    center = tuple(
        float(source_cylinder["center"][axis]) + center_offset[axis]
        for axis in range(3)
    )
    return {
        "center": center,
        "radius": radius,
        "height": height,
        "axis": source_axis,
        "source_cylinder": source_cylinder,
        "structuring_cylinder": structuring_cylinder,
        "structuring_center": structuring_center,
        "structuring_center_offset": center_offset,
    }


def _exact_cylinder_capsule_minkowski_params(
    source_mesh: trimesh.Trimesh,
    structuring_mesh: trimesh.Trimesh,
    *,
    structuring_center: tuple[float, float, float],
) -> dict[str, Any] | None:
    source_cylinder = _cylinder_metadata(source_mesh)
    structuring_capsule = _capsule_metadata(structuring_mesh)
    if source_cylinder is not None and structuring_capsule is not None:
        axis = str(source_cylinder["axis"])
        if axis != str(structuring_capsule["axis"]):
            return None
        radius = float(source_cylinder["radius"]) + float(structuring_capsule["radius"])
        length = float(source_cylinder["height"]) + float(structuring_capsule["length"])
        if length <= 2.0 * radius or radius <= 0.0:
            return None
        center_offset = tuple(
            float(structuring_capsule["center"][index]) - float(structuring_center[index])
            for index in range(3)
        )
        center = tuple(
            float(source_cylinder["center"][index]) + center_offset[index]
            for index in range(3)
        )
        return {
            "center": center,
            "radius": radius,
            "length": length,
            "axis": axis,
            "source_cylinder": source_cylinder,
            "structuring_capsule": structuring_capsule,
            "structuring_center": structuring_center,
            "structuring_center_offset": center_offset,
        }

    source_capsule = _capsule_metadata(source_mesh)
    structuring_cylinder = _cylinder_metadata(structuring_mesh)
    if source_capsule is not None and structuring_cylinder is not None:
        axis = str(source_capsule["axis"])
        if axis != str(structuring_cylinder["axis"]):
            return None
        radius = float(source_capsule["radius"]) + float(structuring_cylinder["radius"])
        length = float(source_capsule["length"]) + float(structuring_cylinder["height"])
        if length <= 2.0 * radius or radius <= 0.0:
            return None
        center = tuple(
            float(source_capsule["center"][index])
            + float(structuring_cylinder["center"][index])
            - float(structuring_center[index])
            for index in range(3)
        )
        return {
            "center": center,
            "radius": radius,
            "length": length,
            "axis": axis,
            "source_capsule": source_capsule,
            "structuring_cylinder": structuring_cylinder,
            "structuring_center": structuring_center,
            "structuring_center_offset": tuple(
                float(structuring_cylinder["center"][index]) - float(structuring_center[index])
                for index in range(3)
            ),
        }
    return None


def _exact_capsule_sphere_minkowski_params(
    source_mesh: trimesh.Trimesh,
    structuring_mesh: trimesh.Trimesh,
    *,
    structuring_center: tuple[float, float, float],
) -> dict[str, Any] | None:
    source_capsule = _capsule_metadata(source_mesh)
    structuring_sphere = _sphere_metadata(structuring_mesh)
    if source_capsule is not None and structuring_sphere is not None:
        sphere_radius = float(structuring_sphere["radius"])
        center_offset = tuple(
            float(structuring_sphere["center"][axis]) - float(structuring_center[axis])
            for axis in range(3)
        )
        center = tuple(
            float(source_capsule["center"][axis]) + center_offset[axis]
            for axis in range(3)
        )
        radius = float(source_capsule["radius"]) + sphere_radius
        length = float(source_capsule["length"]) + 2.0 * sphere_radius
        if length > 2.0 * radius and radius > 0.0:
            return {
                "center": center,
                "radius": radius,
                "length": length,
                "axis": str(source_capsule["axis"]),
                "source_capsule": source_capsule,
                "structuring_sphere": structuring_sphere,
                "structuring_center": structuring_center,
                "structuring_center_offset": center_offset,
            }

    source_sphere = _sphere_metadata(source_mesh)
    structuring_capsule = _capsule_metadata(structuring_mesh)
    if source_sphere is not None and structuring_capsule is not None:
        sphere_radius = float(source_sphere["radius"])
        center = tuple(
            float(source_sphere["center"][axis])
            + float(structuring_capsule["center"][axis])
            - float(structuring_center[axis])
            for axis in range(3)
        )
        radius = float(structuring_capsule["radius"]) + sphere_radius
        length = float(structuring_capsule["length"]) + 2.0 * sphere_radius
        if length > 2.0 * radius and radius > 0.0:
            return {
                "center": center,
                "radius": radius,
                "length": length,
                "axis": str(structuring_capsule["axis"]),
                "source_sphere": source_sphere,
                "structuring_capsule": structuring_capsule,
                "structuring_center": structuring_center,
                "structuring_center_offset": tuple(
                    float(structuring_capsule["center"][axis]) - float(structuring_center[axis])
                    for axis in range(3)
                ),
            }
    return None


def _exact_capsule_capsule_minkowski_params(
    source_mesh: trimesh.Trimesh,
    structuring_mesh: trimesh.Trimesh,
    *,
    structuring_center: tuple[float, float, float],
) -> dict[str, Any] | None:
    source_capsule = _capsule_metadata(source_mesh)
    structuring_capsule = _capsule_metadata(structuring_mesh)
    if source_capsule is None or structuring_capsule is None:
        return None
    source_axis = str(source_capsule["axis"])
    structuring_axis = str(structuring_capsule["axis"])
    if source_axis != structuring_axis:
        return None
    radius = float(source_capsule["radius"]) + float(structuring_capsule["radius"])
    length = float(source_capsule["length"]) + float(structuring_capsule["length"])
    if length <= 2.0 * radius or radius <= 0.0:
        return None
    center_offset = tuple(
        float(structuring_capsule["center"][axis]) - float(structuring_center[axis])
        for axis in range(3)
    )
    center = tuple(
        float(source_capsule["center"][axis]) + center_offset[axis]
        for axis in range(3)
    )
    return {
        "center": center,
        "radius": radius,
        "length": length,
        "axis": source_axis,
        "source_capsule": source_capsule,
        "structuring_capsule": structuring_capsule,
        "structuring_center": structuring_center,
        "structuring_center_offset": center_offset,
    }


def _rounded_rectangle_profile_points(
    *,
    width: float,
    height: float,
    radius: float,
    segments: int = 8,
) -> list[tuple[float, float]]:
    half_width = float(width) * 0.5
    half_height = float(height) * 0.5
    corner_radius = min(float(radius), half_width, half_height)
    if corner_radius <= 1e-9:
        return [
            (-half_width, -half_height),
            (half_width, -half_height),
            (half_width, half_height),
            (-half_width, half_height),
        ]
    core_half_width = max(0.0, half_width - corner_radius)
    core_half_height = max(0.0, half_height - corner_radius)
    corner_specs = (
        ((core_half_width, core_half_height), 0.0, math.pi * 0.5),
        ((-core_half_width, core_half_height), math.pi * 0.5, math.pi),
        ((-core_half_width, -core_half_height), math.pi, math.pi * 1.5),
        ((core_half_width, -core_half_height), math.pi * 1.5, math.tau),
    )
    points: list[tuple[float, float]] = []
    steps = max(2, min(32, int(segments)))
    for (center_u, center_v), start, end in corner_specs:
        for index in range(steps + 1):
            if points and index == 0:
                continue
            t = index / float(steps)
            angle = start + (end - start) * t
            points.append(
                (
                    float(center_u + math.cos(angle) * corner_radius),
                    float(center_v + math.sin(angle) * corner_radius),
                )
            )
    return points


def _box_extents_in_extruded_profile_plane(
    box: dict[str, Any],
    *,
    axis: str,
) -> tuple[float, float, float] | None:
    extents = box.get("extents")
    if not isinstance(extents, (list, tuple)) or len(extents) != 3:
        return None
    values = [float(value) for value in extents]
    if axis == "z":
        return values[0], values[1], values[2]
    if axis == "y":
        return values[0], values[2], values[1]
    if axis == "x":
        return values[2], values[1], values[0]
    return None


def _exact_axis_aligned_box_cylinder_minkowski_params(
    source_mesh: trimesh.Trimesh,
    structuring_mesh: trimesh.Trimesh,
    *,
    structuring_center: tuple[float, float, float],
) -> dict[str, Any] | None:
    source_box = _axis_aligned_box_metadata(source_mesh)
    structuring_cylinder = _cylinder_metadata(structuring_mesh)
    if source_box is not None and structuring_cylinder is not None:
        axis = str(structuring_cylinder["axis"])
        plane_extents = _box_extents_in_extruded_profile_plane(source_box, axis=axis)
        if plane_extents is None:
            return None
        plane_u, plane_v, axial = plane_extents
        radius = float(structuring_cylinder["radius"])
        height = float(structuring_cylinder["height"])
        center_offset = tuple(
            float(structuring_cylinder["center"][axis_index]) - float(structuring_center[axis_index])
            for axis_index in range(3)
        )
        center = tuple(
            float(source_box["center"][axis_index]) + center_offset[axis_index]
            for axis_index in range(3)
        )
        if radius > 0.0 and height > 0.0 and plane_u > 0.0 and plane_v > 0.0 and axial > 0.0:
            profile = _rounded_rectangle_profile_points(
                width=plane_u + 2.0 * radius,
                height=plane_v + 2.0 * radius,
                radius=radius,
            )
            return {
                "center": center,
                "axis": axis,
                "profile_polygon": profile,
                "extrude_height": axial + height,
                "rounding_radius": radius,
                "profile_width": plane_u + 2.0 * radius,
                "profile_height": plane_v + 2.0 * radius,
                "source_box": source_box,
                "structuring_cylinder": structuring_cylinder,
                "structuring_center": structuring_center,
                "structuring_center_offset": center_offset,
            }

    source_cylinder = _cylinder_metadata(source_mesh)
    structuring_box = _axis_aligned_box_metadata(structuring_mesh)
    if source_cylinder is not None and structuring_box is not None:
        axis = str(source_cylinder["axis"])
        plane_extents = _box_extents_in_extruded_profile_plane(structuring_box, axis=axis)
        if plane_extents is None:
            return None
        plane_u, plane_v, axial = plane_extents
        radius = float(source_cylinder["radius"])
        height = float(source_cylinder["height"])
        center = tuple(
            float(source_cylinder["center"][axis_index])
            + float(structuring_box["center"][axis_index])
            - float(structuring_center[axis_index])
            for axis_index in range(3)
        )
        if radius > 0.0 and height > 0.0 and plane_u > 0.0 and plane_v > 0.0 and axial > 0.0:
            profile = _rounded_rectangle_profile_points(
                width=plane_u + 2.0 * radius,
                height=plane_v + 2.0 * radius,
                radius=radius,
            )
            return {
                "center": center,
                "axis": axis,
                "profile_polygon": profile,
                "extrude_height": axial + height,
                "rounding_radius": radius,
                "profile_width": plane_u + 2.0 * radius,
                "profile_height": plane_v + 2.0 * radius,
                "source_cylinder": source_cylinder,
                "structuring_box": structuring_box,
                "structuring_center": structuring_center,
                "structuring_center_offset": tuple(
                    float(structuring_box["center"][axis_index]) - float(structuring_center[axis_index])
                    for axis_index in range(3)
                ),
            }
    return None


def _exact_axis_aligned_box_capsule_minkowski_params(
    source_mesh: trimesh.Trimesh,
    structuring_mesh: trimesh.Trimesh,
    *,
    structuring_center: tuple[float, float, float],
) -> dict[str, Any] | None:
    source_box = _axis_aligned_box_metadata(source_mesh)
    structuring_capsule = _capsule_metadata(structuring_mesh)
    if source_box is not None and structuring_capsule is not None:
        axis = str(structuring_capsule["axis"])
        axis_index = _axis_index(axis)
        radius = float(structuring_capsule["radius"])
        extents = [
            float(value) + 2.0 * radius
            for value in source_box["extents"]
        ]
        extents[axis_index] = float(source_box["extents"][axis_index]) + float(structuring_capsule["length"])
        center_offset = tuple(
            float(structuring_capsule["center"][index]) - float(structuring_center[index])
            for index in range(3)
        )
        center = tuple(
            float(source_box["center"][index]) + center_offset[index]
            for index in range(3)
        )
        if _positive_triplet((extents[0], extents[1], extents[2])) and radius <= min(extents) * 0.5 * 0.92:
            return {
                "center": center,
                "extents": tuple(extents),
                "rounding": radius,
                "axis": axis,
                "source_box": source_box,
                "structuring_capsule": structuring_capsule,
                "structuring_center": structuring_center,
                "structuring_center_offset": center_offset,
            }

    source_capsule = _capsule_metadata(source_mesh)
    structuring_box = _axis_aligned_box_metadata(structuring_mesh)
    if source_capsule is not None and structuring_box is not None:
        axis = str(source_capsule["axis"])
        axis_index = _axis_index(axis)
        radius = float(source_capsule["radius"])
        extents = [
            float(value) + 2.0 * radius
            for value in structuring_box["extents"]
        ]
        extents[axis_index] = float(structuring_box["extents"][axis_index]) + float(source_capsule["length"])
        center = tuple(
            float(source_capsule["center"][index])
            + float(structuring_box["center"][index])
            - float(structuring_center[index])
            for index in range(3)
        )
        if _positive_triplet((extents[0], extents[1], extents[2])) and radius <= min(extents) * 0.5 * 0.92:
            return {
                "center": center,
                "extents": tuple(extents),
                "rounding": radius,
                "axis": axis,
                "source_capsule": source_capsule,
                "structuring_box": structuring_box,
                "structuring_center": structuring_center,
                "structuring_center_offset": tuple(
                    float(structuring_box["center"][index]) - float(structuring_center[index])
                    for index in range(3)
                ),
            }
    return None


def _axis_aligned_center_delta(
    left: tuple[float, float, float],
    right: tuple[float, float, float],
) -> tuple[str, float] | None:
    delta = tuple(float(right[index]) - float(left[index]) for index in range(3))
    active = [index for index, value in enumerate(delta) if abs(value) > 1e-9]
    if len(active) != 1:
        return None
    axis_index = active[0]
    return _axis_name_from_index(axis_index), abs(float(delta[axis_index]))


def _exact_sphere_pair_hull_params(
    operands: list[KernelOperand],
) -> dict[str, Any] | None:
    if len(operands) != 2:
        return None
    left_mesh = operands[0].source_mesh or operands[0].handle
    right_mesh = operands[1].source_mesh or operands[1].handle
    if not isinstance(left_mesh, trimesh.Trimesh) or not isinstance(right_mesh, trimesh.Trimesh):
        return None
    left_sphere = _sphere_metadata(left_mesh)
    right_sphere = _sphere_metadata(right_mesh)
    if left_sphere is None or right_sphere is None:
        return None
    radius = float(left_sphere["radius"])
    right_radius = float(right_sphere["radius"])
    left_center = tuple(float(value) for value in left_sphere["center"])
    right_center = tuple(float(value) for value in right_sphere["center"])
    distance = math.dist(left_center, right_center)
    if distance + min(radius, right_radius) <= max(radius, right_radius) + 1e-9:
        source = left_sphere if radius >= right_radius else right_sphere
        return {
            "primitive_type": "sphere",
            "required_capabilities": ["sphere"],
            "method": "exact_contained_sphere_hull_v1",
            "actual_operation": "contained_sphere_hull",
            "result_kind": "sphere",
            "center": tuple(float(value) for value in source["center"]),
            "radius": max(radius, right_radius),
            "source_spheres": [left_sphere, right_sphere],
        }
    if distance <= 1e-9:
        return {
            "primitive_type": "sphere",
            "required_capabilities": ["sphere"],
            "method": "exact_coincident_sphere_hull_v1",
            "actual_operation": "coincident_sphere_hull",
            "result_kind": "sphere",
            "center": left_center,
            "radius": radius,
            "source_spheres": [left_sphere, right_sphere],
        }
    axis = _axis_aligned_center_delta(left_center, right_center)
    if axis is None:
        return None
    axis_name, axis_distance = axis
    if abs(radius - right_radius) > max(1e-7, max(radius, right_radius) * 1e-6):
        axis_index = _axis_index(axis_name)
        samples = _upper_hull_axial_radius_points(
            [
                *_sphere_axis_profile_samples(left_center[axis_index], radius),
                *_sphere_axis_profile_samples(right_center[axis_index], right_radius),
            ]
        )
        if len(samples) < 3:
            return None
        result_min = min(float(axial) for axial, _radius in samples)
        result_max = max(float(axial) for axial, _radius in samples)
        center = list(left_center)
        center[axis_index] = (result_min + result_max) * 0.5
        center_axis = float(center[axis_index])
        profile_points = tuple(
            (float(axial) - center_axis, float(profile_radius))
            for axial, profile_radius in samples
        )
        return {
            "primitive_type": "revolved_profile",
            "required_capabilities": ["revolved_profile"],
            "method": "sampled_axis_aligned_unequal_sphere_hull_profile_v1",
            "actual_operation": "axis_aligned_unequal_sphere_hull_profile",
            "result_kind": "revolved_profile",
            "center": tuple(center),
            "axis": axis_name,
            "profile_points": profile_points,
            "profile_point_count": len(profile_points),
            "profile_approximation": "sampled_upper_spherocone_profile",
            "profile_sample_count": len(samples),
            "exact": False,
            "source_spheres": [left_sphere, right_sphere],
        }
    center = tuple((left_center[index] + right_center[index]) * 0.5 for index in range(3))
    return {
        "primitive_type": "capsule",
        "required_capabilities": ["capsule"],
        "method": "exact_axis_aligned_equal_sphere_capsule_hull_v1",
        "actual_operation": "axis_aligned_equal_sphere_hull",
        "result_kind": "capsule",
        "center": center,
        "radius": radius,
        "length": axis_distance + 2.0 * radius,
        "axis": axis_name,
        "source_spheres": [left_sphere, right_sphere],
    }


def _sphere_axis_profile_samples(
    center_axis: float,
    radius: float,
    *,
    segments: int = 24,
) -> list[tuple[float, float]]:
    steps = max(8, min(96, int(segments)))
    samples: list[tuple[float, float]] = []
    for index in range(steps + 1):
        theta = math.pi - math.pi * (index / float(steps))
        samples.append(
            (
                float(center_axis) + math.cos(theta) * float(radius),
                max(0.0, math.sin(theta) * float(radius)),
            )
        )
    return samples


def _capsule_axis_profile_samples(
    interval_min: float,
    interval_max: float,
    radius: float,
    *,
    segments: int = 24,
) -> list[tuple[float, float]]:
    if interval_max < interval_min:
        return _sphere_axis_profile_samples((interval_min + interval_max) * 0.5, radius, segments=segments)
    steps = max(8, min(96, int(segments)))
    samples: list[tuple[float, float]] = []
    for index in range(steps + 1):
        theta = math.pi - (math.pi * 0.5) * (index / float(steps))
        samples.append(
            (
                float(interval_min) + math.cos(theta) * float(radius),
                max(0.0, math.sin(theta) * float(radius)),
            )
        )
    samples.append((float(interval_max), float(radius)))
    for index in range(steps + 1):
        theta = (math.pi * 0.5) - (math.pi * 0.5) * (index / float(steps))
        samples.append(
            (
                float(interval_max) + math.cos(theta) * float(radius),
                max(0.0, math.sin(theta) * float(radius)),
            )
        )
    return samples


def _round_profile_source_for_axis(
    mesh: trimesh.Trimesh,
    *,
    axis: str | None = None,
) -> dict[str, Any] | None:
    sphere = _sphere_metadata(mesh)
    if sphere is not None:
        return {
            "kind": "sphere",
            "center": tuple(float(value) for value in sphere["center"]),
            "axis": axis,
            "radius": float(sphere["radius"]),
            "metadata": sphere,
        }
    cylinder = _cylinder_metadata(mesh)
    if cylinder is not None:
        return {
            "kind": "cylinder",
            "center": tuple(float(value) for value in cylinder["center"]),
            "axis": str(cylinder["axis"]),
            "radius": float(cylinder["radius"]),
            "height": float(cylinder["height"]),
            "metadata": cylinder,
        }
    capsule = _capsule_metadata(mesh)
    if capsule is not None:
        return {
            "kind": "capsule",
            "center": tuple(float(value) for value in capsule["center"]),
            "axis": str(capsule["axis"]),
            "radius": float(capsule["radius"]),
            "length": float(capsule["length"]),
            "metadata": capsule,
        }
    return None


def _round_profile_samples_for_source(
    source: dict[str, Any],
    *,
    axis: str,
) -> list[tuple[float, float]] | None:
    axis_index = _axis_index(axis)
    center = tuple(float(value) for value in source["center"])
    radius = float(source["radius"])
    kind = str(source["kind"])
    if kind == "sphere":
        return _sphere_axis_profile_samples(center[axis_index], radius)
    if kind == "cylinder":
        half_height = float(source["height"]) * 0.5
        return [
            (center[axis_index] - half_height, radius),
            (center[axis_index] + half_height, radius),
        ]
    if kind == "capsule":
        shaft = float(source["length"]) - 2.0 * radius
        if shaft < -1e-9:
            return None
        interval_min = center[axis_index] - max(0.0, shaft) * 0.5
        interval_max = center[axis_index] + max(0.0, shaft) * 0.5
        return _capsule_axis_profile_samples(interval_min, interval_max, radius)
    return None


def _sampled_mixed_coaxial_profile_hull_params(
    operands: list[KernelOperand],
) -> dict[str, Any] | None:
    if len(operands) != 2:
        return None
    left_mesh = operands[0].source_mesh or operands[0].handle
    right_mesh = operands[1].source_mesh or operands[1].handle
    if not isinstance(left_mesh, trimesh.Trimesh) or not isinstance(right_mesh, trimesh.Trimesh):
        return None
    left = _round_profile_source_for_axis(left_mesh)
    right = _round_profile_source_for_axis(right_mesh)
    if left is None or right is None:
        return None
    if str(left["kind"]) == str(right["kind"]):
        return None
    axes = {str(source["axis"]) for source in (left, right) if source.get("axis")}
    if len(axes) != 1:
        return None
    axis = axes.pop()
    left["axis"] = axis
    right["axis"] = axis
    left_center = tuple(float(value) for value in left["center"])
    right_center = tuple(float(value) for value in right["center"])
    center_delta = _axis_aligned_center_delta(left_center, right_center)
    if center_delta is not None and center_delta[0] != axis:
        return None
    if center_delta is None and any(abs(left_center[index] - right_center[index]) > 1e-9 for index in range(3)):
        return None
    axis_index = _axis_index(axis)
    left_samples = _round_profile_samples_for_source(left, axis=axis)
    right_samples = _round_profile_samples_for_source(right, axis=axis)
    if left_samples is None or right_samples is None:
        return None
    samples = _upper_hull_axial_radius_points([*left_samples, *right_samples])
    if len(samples) < 2:
        return None
    sample_min = min(float(axial) for axial, _radius in samples)
    sample_max = max(float(axial) for axial, _radius in samples)
    center = list(left_center)
    center[axis_index] = (sample_min + sample_max) * 0.5
    center_axis = float(center[axis_index])
    profile_points = tuple(
        (float(axial) - center_axis, float(profile_radius))
        for axial, profile_radius in samples
    )
    kind_pair = "_".join(sorted((str(left["kind"]), str(right["kind"]))))
    return {
        "primitive_type": "revolved_profile",
        "required_capabilities": ["revolved_profile"],
        "method": f"sampled_coaxial_{kind_pair}_hull_profile_v1",
        "actual_operation": f"coaxial_{kind_pair}_hull_profile",
        "result_kind": "revolved_profile",
        "center": tuple(center),
        "height": sample_max - sample_min,
        "axis": axis,
        "profile_points": profile_points,
        "profile_point_count": len(profile_points),
        "profile_approximation": "sampled_upper_coaxial_mixed_profile",
        "profile_sample_count": len(samples),
        "exact": False,
        "source_profile_hull_operands": [
            {"kind": left["kind"], **_dict_metadata(left.get("metadata"))},
            {"kind": right["kind"], **_dict_metadata(right.get("metadata"))},
        ],
    }


def _box_contains_box(
    outer: dict[str, Any],
    inner: dict[str, Any],
    *,
    tolerance: float = 1e-9,
) -> bool:
    outer_min = tuple(float(value) for value in outer["bounds_min"])
    outer_max = tuple(float(value) for value in outer["bounds_max"])
    inner_min = tuple(float(value) for value in inner["bounds_min"])
    inner_max = tuple(float(value) for value in inner["bounds_max"])
    return all(
        outer_min[index] <= inner_min[index] + tolerance
        and outer_max[index] >= inner_max[index] - tolerance
        for index in range(3)
    )


def _exact_axis_aligned_box_pair_hull_params(
    operands: list[KernelOperand],
) -> dict[str, Any] | None:
    if len(operands) != 2:
        return None
    left_mesh = operands[0].source_mesh or operands[0].handle
    right_mesh = operands[1].source_mesh or operands[1].handle
    if not isinstance(left_mesh, trimesh.Trimesh) or not isinstance(right_mesh, trimesh.Trimesh):
        return None
    left = _axis_aligned_box_metadata(left_mesh)
    right = _axis_aligned_box_metadata(right_mesh)
    if left is None or right is None:
        return None
    left_min = tuple(float(value) for value in left["bounds_min"])
    left_max = tuple(float(value) for value in left["bounds_max"])
    right_min = tuple(float(value) for value in right["bounds_min"])
    right_max = tuple(float(value) for value in right["bounds_max"])
    method = ""
    actual_operation = ""
    if _box_contains_box(left, right):
        result_min = left_min
        result_max = left_max
        method = "exact_nested_axis_aligned_box_hull_v1"
        actual_operation = "nested_axis_aligned_box_hull"
    elif _box_contains_box(right, left):
        result_min = right_min
        result_max = right_max
        method = "exact_nested_axis_aligned_box_hull_v1"
        actual_operation = "nested_axis_aligned_box_hull"
    else:
        left_center = tuple(float(value) for value in left["center"])
        right_center = tuple(float(value) for value in right["center"])
        center_delta = _axis_aligned_center_delta(left_center, right_center)
        if center_delta is None:
            return None
        axis_index = _axis_index(center_delta[0])
        for index in range(3):
            if index == axis_index:
                continue
            if abs(left_min[index] - right_min[index]) > 1e-9:
                return None
            if abs(left_max[index] - right_max[index]) > 1e-9:
                return None
        result_min = tuple(min(left_min[index], right_min[index]) for index in range(3))
        result_max = tuple(max(left_max[index], right_max[index]) for index in range(3))
        method = "exact_axis_aligned_box_strip_hull_v1"
        actual_operation = "axis_aligned_box_strip_hull"
    extents = tuple(result_max[index] - result_min[index] for index in range(3))
    if not _positive_triplet(extents):
        return None
    center = tuple((result_min[index] + result_max[index]) * 0.5 for index in range(3))
    return {
        "primitive_type": "box",
        "required_capabilities": ["box"],
        "method": method,
        "actual_operation": actual_operation,
        "result_kind": "box",
        "center": center,
        "extents": extents,
        "bounds_min": result_min,
        "bounds_max": result_max,
        "source_boxes": [left, right],
    }


def _upper_hull_axial_radius_points(
    points: list[tuple[float, float]],
) -> tuple[tuple[float, float], ...]:
    merged: dict[float, float] = {}
    for axial, radius in points:
        axial_value = float(axial)
        radius_value = float(radius)
        if not math.isfinite(axial_value) or not math.isfinite(radius_value) or radius_value <= 0.0:
            continue
        key = round(axial_value, 9)
        merged[key] = max(radius_value, merged.get(key, 0.0))
    ordered = sorted((float(axial), float(radius)) for axial, radius in merged.items())
    if len(ordered) <= 2:
        return tuple(ordered)

    def cross(
        origin: tuple[float, float],
        left: tuple[float, float],
        right: tuple[float, float],
    ) -> float:
        return (
            (left[0] - origin[0]) * (right[1] - origin[1])
            - (left[1] - origin[1]) * (right[0] - origin[0])
        )

    upper: list[tuple[float, float]] = []
    for point in ordered:
        while len(upper) >= 2 and cross(upper[-2], upper[-1], point) >= -1e-9:
            upper.pop()
        upper.append(point)
    return tuple(upper)


def _exact_cylinder_pair_hull_params(
    operands: list[KernelOperand],
) -> dict[str, Any] | None:
    if len(operands) != 2:
        return None
    left_mesh = operands[0].source_mesh or operands[0].handle
    right_mesh = operands[1].source_mesh or operands[1].handle
    if not isinstance(left_mesh, trimesh.Trimesh) or not isinstance(right_mesh, trimesh.Trimesh):
        return None
    left = _cylinder_metadata(left_mesh)
    right = _cylinder_metadata(right_mesh)
    if left is None or right is None:
        return None
    axis = str(left["axis"])
    if axis != str(right["axis"]):
        return None
    radius = float(left["radius"])
    right_radius = float(right["radius"])
    left_center = tuple(float(value) for value in left["center"])
    right_center = tuple(float(value) for value in right["center"])
    center_delta = _axis_aligned_center_delta(left_center, right_center)
    if center_delta is not None and center_delta[0] != axis:
        return None
    if center_delta is None and any(abs(left_center[index] - right_center[index]) > 1e-9 for index in range(3)):
        return None
    axis_index = _axis_index(axis)
    left_min = left_center[axis_index] - float(left["height"]) * 0.5
    left_max = left_center[axis_index] + float(left["height"]) * 0.5
    right_min = right_center[axis_index] - float(right["height"]) * 0.5
    right_max = right_center[axis_index] + float(right["height"]) * 0.5
    result_min = min(left_min, right_min)
    result_max = max(left_max, right_max)
    center = list(left_center)
    center[axis_index] = (result_min + result_max) * 0.5
    height = result_max - result_min
    if height <= 0.0:
        return None
    if abs(radius - right_radius) > max(1e-7, max(radius, right_radius) * 1e-6):
        upper_profile = _upper_hull_axial_radius_points(
            [
                (left_min, radius),
                (left_max, radius),
                (right_min, right_radius),
                (right_max, right_radius),
            ]
        )
        if len(upper_profile) < 2:
            return None
        center_axis = float(center[axis_index])
        profile_points = tuple(
            (float(axial) - center_axis, float(profile_radius))
            for axial, profile_radius in upper_profile
        )
        return {
            "primitive_type": "revolved_profile",
            "required_capabilities": ["revolved_profile"],
            "method": "exact_coaxial_cylinder_frustum_hull_v1",
            "actual_operation": "coaxial_cylinder_frustum_hull",
            "result_kind": "revolved_profile",
            "center": tuple(center),
            "height": height,
            "axis": axis,
            "profile_points": profile_points,
            "profile_point_count": len(profile_points),
            "source_cylinders": [left, right],
        }
    return {
        "primitive_type": "cylinder",
        "required_capabilities": ["cylinder"],
        "method": "exact_coaxial_equal_radius_cylinder_hull_v1",
        "actual_operation": "coaxial_equal_radius_cylinder_hull",
        "result_kind": "cylinder",
        "center": tuple(center),
        "radius": radius,
        "height": height,
        "axis": axis,
        "source_cylinders": [left, right],
    }


def _capsule_axis_interval(capsule: dict[str, Any]) -> tuple[float, float] | None:
    radius = float(capsule["radius"])
    length = float(capsule["length"])
    shaft = length - 2.0 * radius
    if shaft < -1e-9:
        return None
    center = tuple(float(value) for value in capsule["center"])
    axis_index = _axis_index(str(capsule["axis"]))
    return (
        center[axis_index] - max(0.0, shaft) * 0.5,
        center[axis_index] + max(0.0, shaft) * 0.5,
    )


def _exact_capsule_pair_hull_params(
    operands: list[KernelOperand],
) -> dict[str, Any] | None:
    if len(operands) != 2:
        return None
    left_mesh = operands[0].source_mesh or operands[0].handle
    right_mesh = operands[1].source_mesh or operands[1].handle
    if not isinstance(left_mesh, trimesh.Trimesh) or not isinstance(right_mesh, trimesh.Trimesh):
        return None
    left = _capsule_metadata(left_mesh)
    right = _capsule_metadata(right_mesh)
    if left is None or right is None:
        return None
    axis = str(left["axis"])
    if axis != str(right["axis"]):
        return None
    radius = float(left["radius"])
    right_radius = float(right["radius"])
    left_center = tuple(float(value) for value in left["center"])
    right_center = tuple(float(value) for value in right["center"])
    center_delta = _axis_aligned_center_delta(left_center, right_center)
    if center_delta is not None and center_delta[0] != axis:
        return None
    if center_delta is None and any(abs(left_center[index] - right_center[index]) > 1e-9 for index in range(3)):
        return None
    left_interval = _capsule_axis_interval(left)
    right_interval = _capsule_axis_interval(right)
    if left_interval is None or right_interval is None:
        return None
    result_min = min(left_interval[0], right_interval[0])
    result_max = max(left_interval[1], right_interval[1])
    axis_index = _axis_index(axis)
    center = list(left_center)
    if abs(radius - right_radius) > max(1e-7, max(radius, right_radius) * 1e-6):
        samples = _upper_hull_axial_radius_points(
            [
                *_capsule_axis_profile_samples(left_interval[0], left_interval[1], radius),
                *_capsule_axis_profile_samples(right_interval[0], right_interval[1], right_radius),
            ]
        )
        if len(samples) < 3:
            return None
        sample_min = min(float(axial) for axial, _radius in samples)
        sample_max = max(float(axial) for axial, _radius in samples)
        center[axis_index] = (sample_min + sample_max) * 0.5
        center_axis = float(center[axis_index])
        profile_points = tuple(
            (float(axial) - center_axis, float(profile_radius))
            for axial, profile_radius in samples
        )
        return {
            "primitive_type": "revolved_profile",
            "required_capabilities": ["revolved_profile"],
            "method": "sampled_coaxial_unequal_capsule_hull_profile_v1",
            "actual_operation": "coaxial_unequal_capsule_hull_profile",
            "result_kind": "revolved_profile",
            "center": tuple(center),
            "height": sample_max - sample_min,
            "axis": axis,
            "profile_points": profile_points,
            "profile_point_count": len(profile_points),
            "profile_approximation": "sampled_upper_capsule_hull_profile",
            "profile_sample_count": len(samples),
            "exact": False,
            "source_capsules": [left, right],
        }
    center[axis_index] = (result_min + result_max) * 0.5
    length = (result_max - result_min) + 2.0 * radius
    if length <= 2.0 * radius:
        return {
            "primitive_type": "sphere",
            "required_capabilities": ["sphere"],
            "method": "exact_coincident_capsule_sphere_hull_v1",
            "actual_operation": "coincident_capsule_hull",
            "result_kind": "sphere",
            "center": tuple(center),
            "radius": radius,
            "source_capsules": [left, right],
        }
    return {
        "primitive_type": "capsule",
        "required_capabilities": ["capsule"],
        "method": "exact_coaxial_equal_radius_capsule_hull_v1",
        "actual_operation": "coaxial_equal_radius_capsule_hull",
        "result_kind": "capsule",
        "center": tuple(center),
        "radius": radius,
        "length": length,
        "axis": axis,
        "source_capsules": [left, right],
    }


def _mesh_bounds_overlap(a: trimesh.Trimesh, b: trimesh.Trimesh, *, epsilon: float = 1e-7) -> bool:
    try:
        a_min, a_max = a.bounds
        b_min, b_max = b.bounds
    except (AttributeError, TypeError, ValueError, IndexError):
        return True
    for axis in range(3):
        if float(a_max[axis]) < float(b_min[axis]) - epsilon:
            return False
        if float(b_max[axis]) < float(a_min[axis]) - epsilon:
            return False
    return True


def _disjoint_mesh_group_count(meshes: list[trimesh.Trimesh]) -> int:
    non_empty = [mesh for mesh in meshes if isinstance(mesh, trimesh.Trimesh) and len(mesh.faces) > 0]
    if not non_empty:
        return 0
    parent = list(range(len(non_empty)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    for left in range(len(non_empty)):
        for right in range(left + 1, len(non_empty)):
            if _mesh_bounds_overlap(non_empty[left], non_empty[right]):
                union(left, right)
    return len({find(index) for index in range(len(non_empty))})


def _operation_record(
    *,
    op: str,
    left: str,
    right: str,
    kernel: GeometryKernel,
) -> dict[str, Any]:
    return {
        "op": op,
        "left": left,
        "right": right,
        "attempted_kernel": kernel.name,
        "actual_kernel": kernel.name,
    }


def _attach_kernel_boolean_execution_metadata(
    record: dict[str, Any],
    mesh: trimesh.Trimesh,
) -> None:
    sources = (
        (
            "lathe_reference_boolean_fallback",
            mesh.metadata.get("lathe_reference_boolean_fallback"),
        ),
        (
            "lathe_manifold_boolean",
            mesh.metadata.get("lathe_manifold_boolean"),
        ),
        (
            "lathe_reference_exact_boolean",
            mesh.metadata.get("lathe_reference_exact_boolean"),
        ),
        (
            "lathe_reference_boolean_backend",
            mesh.metadata.get("lathe_reference_boolean_backend"),
        ),
        (
            "lathe_reference_sdf_boolean",
            mesh.metadata.get("lathe_reference_sdf_boolean"),
        ),
        (
            "lathe_reference_batch_union",
            mesh.metadata.get("lathe_reference_batch_union"),
        ),
        (
            "lathe_manifold_batch_union",
            mesh.metadata.get("lathe_manifold_batch_union"),
        ),
    )
    for source, payload in sources:
        if not isinstance(payload, dict):
            continue
        if "attempted_backend" not in payload and "requested_backend" in payload:
            record.setdefault("attempted_backend", payload.get("requested_backend"))
        if source == "lathe_reference_batch_union":
            record.setdefault("attempted_backend", "lathe.reference.batch_union")
            record.setdefault("actual_backend", "lathe.reference.batch_union")
        for key in (
            "attempted_backend",
            "actual_backend",
            "actual_operation",
            "exact_kernel_path",
            "fallback",
            "passthrough",
        ):
            if key in payload and key not in record:
                record[key] = payload[key]
        method = payload.get("method")
        if method and "kernel_boolean_method" not in record:
            record["kernel_boolean_method"] = str(method)
        if method and "actual_operation" not in record:
            record["actual_operation"] = str(method)
        record.setdefault("kernel_boolean_execution_source", source)
        break


def _record_result_probe(
    record: dict[str, Any],
    *,
    kernel: GeometryKernel,
    result_handle: Any,
) -> None:
    try:
        mesh = kernel.to_trimesh(result_handle)
    except (AttributeError, TypeError, ValueError, RuntimeError):
        mesh = None
    if isinstance(mesh, trimesh.Trimesh):
        record["result_face_count"] = len(mesh.faces)
        record["result_watertight"] = bool(mesh.is_watertight)
        batch_union = mesh.metadata.get("lathe_reference_batch_union")
        if not isinstance(batch_union, dict):
            batch_union = mesh.metadata.get("lathe_manifold_batch_union")
        if isinstance(batch_union, dict):
            record["kernel_batch_union"] = dict(batch_union)
        exact_boolean = mesh.metadata.get("lathe_reference_exact_boolean")
        if isinstance(exact_boolean, dict):
            record["kernel_exact_boolean"] = dict(exact_boolean)
        backend_boolean = mesh.metadata.get("lathe_reference_boolean_backend")
        if isinstance(backend_boolean, dict):
            record["kernel_boolean_backend"] = dict(backend_boolean)
        manifold_boolean = mesh.metadata.get("lathe_manifold_boolean")
        if isinstance(manifold_boolean, dict):
            record["kernel_manifold_boolean"] = dict(manifold_boolean)
            record.setdefault("kernel_boolean_backend", dict(manifold_boolean))
        sdf_boolean = mesh.metadata.get("lathe_reference_sdf_boolean")
        if isinstance(sdf_boolean, dict):
            record["kernel_sdf_boolean"] = dict(sdf_boolean)
        hull_metadata = mesh.metadata.get("lathe_reference_hull")
        if not isinstance(hull_metadata, dict):
            hull_metadata = mesh.metadata.get("lathe_manifold_hull")
        if isinstance(hull_metadata, dict):
            record["kernel_hull"] = dict(hull_metadata)
            record.setdefault("kernel_hull_method", str(hull_metadata.get("method") or ""))
            record.setdefault("attempted_backend", str(hull_metadata.get("attempted_backend") or ""))
            record.setdefault("actual_backend", str(hull_metadata.get("actual_backend") or ""))
            record.setdefault("actual_operation", str(hull_metadata.get("actual_operation") or ""))
        transform_metadata = mesh.metadata.get("lathe_reference_transform")
        if not isinstance(transform_metadata, dict):
            transform_metadata = mesh.metadata.get("lathe_manifold_transform")
        if isinstance(transform_metadata, dict):
            record["kernel_transform"] = dict(transform_metadata)
            record.setdefault(
                "kernel_transform_method",
                str(transform_metadata.get("method") or ""),
            )
            record.setdefault(
                "attempted_backend",
                str(transform_metadata.get("attempted_backend") or ""),
            )
            record.setdefault(
                "actual_backend",
                str(transform_metadata.get("actual_backend") or ""),
            )
            record.setdefault(
                "actual_operation",
                str(transform_metadata.get("actual_operation") or ""),
            )
        deform_metadata = mesh.metadata.get("lathe_kernel_deform")
        if isinstance(deform_metadata, dict):
            record["kernel_deform"] = dict(deform_metadata)
            record.setdefault(
                "kernel_deform_method",
                str(deform_metadata.get("method") or ""),
            )
            record.setdefault(
                "attempted_backend",
                str(deform_metadata.get("attempted_backend") or ""),
            )
            record.setdefault(
                "actual_backend",
                str(deform_metadata.get("actual_backend") or ""),
            )
            record.setdefault(
                "actual_operation",
                str(deform_metadata.get("actual_operation") or ""),
            )
        refine_metadata = mesh.metadata.get("lathe_kernel_refine")
        if isinstance(refine_metadata, dict):
            record["kernel_refine"] = dict(refine_metadata)
            record.setdefault(
                "kernel_refine_method",
                str(refine_metadata.get("method") or ""),
            )
            record.setdefault(
                "attempted_backend",
                str(refine_metadata.get("attempted_backend") or ""),
            )
            record.setdefault(
                "actual_backend",
                str(refine_metadata.get("actual_backend") or ""),
            )
            record.setdefault(
                "actual_operation",
                str(refine_metadata.get("actual_operation") or ""),
            )
        carve_metadata = mesh.metadata.get("lathe_kernel_carve")
        if isinstance(carve_metadata, dict):
            record["kernel_carve"] = dict(carve_metadata)
            record.setdefault(
                "kernel_carve_method",
                str(carve_metadata.get("method") or ""),
            )
            record.setdefault(
                "attempted_backend",
                str(carve_metadata.get("attempted_backend") or ""),
            )
            record.setdefault(
                "actual_backend",
                str(carve_metadata.get("actual_backend") or ""),
            )
            record.setdefault(
                "actual_operation",
                str(carve_metadata.get("actual_operation") or ""),
            )
        polyextrude_metadata = mesh.metadata.get("lathe_kernel_polyextrude")
        if isinstance(polyextrude_metadata, dict):
            record["kernel_polyextrude"] = dict(polyextrude_metadata)
            record.setdefault(
                "kernel_polyextrude_method",
                str(polyextrude_metadata.get("method") or ""),
            )
            record.setdefault(
                "attempted_backend",
                str(polyextrude_metadata.get("attempted_backend") or ""),
            )
            record.setdefault(
                "actual_backend",
                str(polyextrude_metadata.get("actual_backend") or ""),
            )
            record.setdefault(
                "actual_operation",
                str(polyextrude_metadata.get("actual_operation") or ""),
            )
        component_assembly_metadata = mesh.metadata.get("lathe_kernel_component_assembly")
        if isinstance(component_assembly_metadata, dict):
            record["kernel_component_assembly"] = dict(component_assembly_metadata)
            record.setdefault(
                "kernel_component_assembly_method",
                str(component_assembly_metadata.get("method") or ""),
            )
            record.setdefault(
                "attempted_backend",
                str(component_assembly_metadata.get("attempted_backend") or ""),
            )
            record.setdefault(
                "actual_backend",
                str(component_assembly_metadata.get("actual_backend") or ""),
            )
            record.setdefault(
                "actual_operation",
                str(component_assembly_metadata.get("actual_operation") or ""),
            )
        profile_path_metadata = mesh.metadata.get("lathe_kernel_profile_path")
        if isinstance(profile_path_metadata, dict):
            record["kernel_profile_path"] = dict(profile_path_metadata)
            record.setdefault(
                "kernel_profile_path_method",
                str(profile_path_metadata.get("method") or ""),
            )
            record.setdefault(
                "attempted_backend",
                str(profile_path_metadata.get("attempted_backend") or ""),
            )
            record.setdefault(
                "actual_backend",
                str(profile_path_metadata.get("actual_backend") or ""),
            )
            record.setdefault(
                "actual_operation",
                str(profile_path_metadata.get("actual_operation") or ""),
            )
        sdf_field_metadata = mesh.metadata.get("lathe_kernel_sdf_field")
        if isinstance(sdf_field_metadata, dict):
            record["kernel_sdf_field"] = dict(sdf_field_metadata)
            record.setdefault(
                "kernel_sdf_field_method",
                str(sdf_field_metadata.get("method") or ""),
            )
            record.setdefault(
                "attempted_backend",
                str(sdf_field_metadata.get("attempted_backend") or ""),
            )
            record.setdefault(
                "actual_backend",
                str(sdf_field_metadata.get("actual_backend") or ""),
            )
            record.setdefault(
                "actual_operation",
                str(sdf_field_metadata.get("actual_operation") or ""),
            )
        terrain_field_metadata = mesh.metadata.get("lathe_kernel_terrain_field")
        if isinstance(terrain_field_metadata, dict):
            record["kernel_terrain_field"] = dict(terrain_field_metadata)
            record.setdefault(
                "kernel_terrain_field_method",
                str(terrain_field_metadata.get("method") or ""),
            )
            record.setdefault(
                "attempted_backend",
                str(terrain_field_metadata.get("attempted_backend") or ""),
            )
            record.setdefault(
                "actual_backend",
                str(terrain_field_metadata.get("actual_backend") or ""),
            )
            record.setdefault(
                "actual_operation",
                str(terrain_field_metadata.get("actual_operation") or ""),
            )
        scatter_metadata = mesh.metadata.get("lathe_kernel_scatter")
        if isinstance(scatter_metadata, dict):
            record["kernel_scatter"] = dict(scatter_metadata)
            record.setdefault(
                "kernel_scatter_method",
                str(scatter_metadata.get("method") or ""),
            )
            record.setdefault(
                "attempted_backend",
                str(scatter_metadata.get("attempted_backend") or ""),
            )
            record.setdefault(
                "actual_backend",
                str(scatter_metadata.get("actual_backend") or ""),
            )
            record.setdefault(
                "actual_operation",
                str(scatter_metadata.get("actual_operation") or ""),
            )
        pattern_instances_metadata = mesh.metadata.get("lathe_kernel_pattern_instances")
        if isinstance(pattern_instances_metadata, dict):
            record["kernel_pattern_instances"] = dict(pattern_instances_metadata)
            record.setdefault(
                "kernel_pattern_instances_method",
                str(pattern_instances_metadata.get("method") or ""),
            )
            record.setdefault(
                "attempted_backend",
                str(pattern_instances_metadata.get("attempted_backend") or ""),
            )
            record.setdefault(
                "actual_backend",
                str(pattern_instances_metadata.get("actual_backend") or ""),
            )
            record.setdefault(
                "actual_operation",
                str(pattern_instances_metadata.get("actual_operation") or ""),
            )
        edge_control_metadata = mesh.metadata.get("lathe_kernel_edge_control")
        if isinstance(edge_control_metadata, dict):
            record["kernel_edge_control"] = dict(edge_control_metadata)
            record.setdefault(
                "kernel_edge_control_method",
                str(edge_control_metadata.get("method") or ""),
            )
            record.setdefault(
                "attempted_backend",
                str(edge_control_metadata.get("attempted_backend") or ""),
            )
            record.setdefault(
                "actual_backend",
                str(edge_control_metadata.get("actual_backend") or ""),
            )
            record.setdefault(
                "actual_operation",
                str(edge_control_metadata.get("actual_operation") or ""),
            )
        edge_treatment_metadata = mesh.metadata.get("lathe_kernel_edge_treatment")
        if isinstance(edge_treatment_metadata, dict):
            record["kernel_edge_treatment"] = dict(edge_treatment_metadata)
            record.setdefault(
                "kernel_edge_treatment_method",
                str(edge_treatment_metadata.get("method") or ""),
            )
            record.setdefault(
                "attempted_backend",
                str(edge_treatment_metadata.get("attempted_backend") or ""),
            )
            record.setdefault(
                "actual_backend",
                str(edge_treatment_metadata.get("actual_backend") or ""),
            )
            record.setdefault(
                "actual_operation",
                str(edge_treatment_metadata.get("actual_operation") or ""),
            )
        feature_detail_metadata = mesh.metadata.get("lathe_kernel_feature_detail")
        if isinstance(feature_detail_metadata, dict):
            record["kernel_feature_detail"] = dict(feature_detail_metadata)
            record.setdefault(
                "kernel_feature_detail_method",
                str(feature_detail_metadata.get("method") or ""),
            )
            record.setdefault(
                "attempted_backend",
                str(feature_detail_metadata.get("attempted_backend") or ""),
            )
            record.setdefault(
                "actual_backend",
                str(feature_detail_metadata.get("actual_backend") or ""),
            )
            record.setdefault(
                "actual_operation",
                str(feature_detail_metadata.get("actual_operation") or ""),
            )
        surface_damage_metadata = mesh.metadata.get("lathe_kernel_surface_damage")
        if isinstance(surface_damage_metadata, dict):
            record["kernel_surface_damage"] = dict(surface_damage_metadata)
            record.setdefault(
                "kernel_surface_damage_method",
                str(surface_damage_metadata.get("method") or ""),
            )
            record.setdefault(
                "attempted_backend",
                str(surface_damage_metadata.get("attempted_backend") or ""),
            )
            record.setdefault(
                "actual_backend",
                str(surface_damage_metadata.get("actual_backend") or ""),
            )
            record.setdefault(
                "actual_operation",
                str(surface_damage_metadata.get("actual_operation") or ""),
            )
        minkowski_metadata = mesh.metadata.get("lathe_kernel_minkowski")
        if isinstance(minkowski_metadata, dict):
            record["kernel_minkowski"] = dict(minkowski_metadata)
            record.setdefault(
                "kernel_minkowski_method",
                str(minkowski_metadata.get("method") or ""),
            )
            record.setdefault(
                "attempted_backend",
                str(minkowski_metadata.get("attempted_backend") or ""),
            )
            record.setdefault(
                "actual_backend",
                str(minkowski_metadata.get("actual_backend") or ""),
            )
            record.setdefault(
                "actual_operation",
                str(minkowski_metadata.get("actual_operation") or ""),
            )
        boss_state = mesh.metadata.get("lathe_reference_boss_state")
        if isinstance(boss_state, dict):
            record["kernel_boss_state"] = dict(boss_state)
        _attach_kernel_boolean_execution_metadata(record, mesh)
    try:
        record["result_body_count"] = kernel.body_count(result_handle)
    except (AttributeError, TypeError, ValueError, RuntimeError):
        pass


def _record_operation_result(
    record: dict[str, Any],
    *,
    kernel: GeometryKernel,
    result_handle: Any,
    left_handle: Any,
) -> None:
    _record_result_probe(record, kernel=kernel, result_handle=result_handle)
    try:
        mesh = kernel.to_trimesh(result_handle)
    except (AttributeError, TypeError, ValueError, RuntimeError):
        mesh = None
    if isinstance(mesh, trimesh.Trimesh):
        fallback = mesh.metadata.get("lathe_reference_boolean_fallback")
        if isinstance(fallback, dict):
            record["kernel_fallback"] = dict(fallback)
            record["passthrough_fallback_suspected"] = bool(fallback.get("passthrough", True))
        exact_boolean = mesh.metadata.get("lathe_reference_exact_boolean")
        if isinstance(exact_boolean, dict):
            record["kernel_exact_boolean"] = dict(exact_boolean)
        backend_boolean = mesh.metadata.get("lathe_reference_boolean_backend")
        if isinstance(backend_boolean, dict):
            record["kernel_boolean_backend"] = dict(backend_boolean)
        sdf_boolean = mesh.metadata.get("lathe_reference_sdf_boolean")
        if isinstance(sdf_boolean, dict):
            record["kernel_sdf_boolean"] = dict(sdf_boolean)
        decomposition = mesh.metadata.get("lathe_reference_boolean_decomposition")
        if isinstance(decomposition, dict):
            record["kernel_boolean_decomposition"] = dict(decomposition)
        nested_exact = mesh.metadata.get("lathe_reference_nested_exact_booleans")
        if isinstance(nested_exact, list):
            record["kernel_nested_exact_booleans"] = [
                dict(item) for item in nested_exact if isinstance(item, dict)
            ]
        nested_backend = mesh.metadata.get("lathe_reference_nested_backend_booleans")
        if isinstance(nested_backend, list):
            record["kernel_nested_backend_booleans"] = [
                dict(item) for item in nested_backend if isinstance(item, dict)
            ]
    if record.get("op") in {"subtract", "intersect"} and result_handle is left_handle:
        record["passthrough_fallback_suspected"] = True


def _boolean_fallback_diagnostics(
    fallback_records: list[dict[str, Any]],
    *,
    code: str = "boolean_csg_fallback",
) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    for index, record in enumerate(fallback_records):
        fallback = _dict_metadata(record.get("kernel_fallback"))
        method = str(fallback.get("method") or "")
        reason = str(
            method
            or fallback.get("reason")
            or record.get("fallback_reason")
            or "passthrough_fallback_suspected"
        )
        diagnostic = {
            "code": code,
            "severity": "warning",
            "operation_index": index,
            "operation": str(record.get("op") or ""),
            "reason": reason,
            "attempted_kernel": str(record.get("attempted_kernel") or ""),
            "actual_kernel": str(record.get("actual_kernel") or ""),
            "attempted_backend": str(
                fallback.get("attempted_backend")
                or record.get("attempted_backend")
                or ""
            ),
            "actual_backend": str(
                fallback.get("actual_backend")
                or record.get("actual_backend")
                or ""
            ),
            "actual_operation": str(
                fallback.get("actual_operation")
                or record.get("actual_operation")
                or ""
            ),
            "passthrough_fallback_suspected": bool(
                record.get("passthrough_fallback_suspected")
            ),
        }
        if method:
            diagnostic["fallback_method"] = method
        diagnostics.append(diagnostic)
    return diagnostics


def _manifest_with_runtime_diagnostics(
    manifest: dict[str, Any],
    diagnostics: list[dict[str, Any]],
) -> dict[str, Any]:
    if not diagnostics:
        return manifest
    updated = dict(manifest)
    existing = updated.get("diagnostics")
    updated["diagnostics"] = [
        *([dict(item) for item in existing if isinstance(item, dict)] if isinstance(existing, list) else []),
        *diagnostics,
    ]
    return updated


def _exact_profile_cut_record(
    exact_boolean: Any,
    *,
    operation_index: int,
) -> dict[str, Any] | None:
    if not isinstance(exact_boolean, dict):
        return None
    method = str(exact_boolean.get("method") or "")
    profile_cut_count = exact_boolean.get("profile_cut_count")
    if "profile" not in method and profile_cut_count in (None, 0, "0"):
        return None
    record: dict[str, Any] = {
        "operation_index": int(operation_index),
        "method": method,
        "profile_cut_count": int(profile_cut_count or 0),
        "cutter_part": str(exact_boolean.get("cutter_part") or ""),
        "result_face_count": int(exact_boolean.get("result_face_count") or 0),
        "result_vertex_count": int(exact_boolean.get("result_vertex_count") or 0),
        "result_body_count": int(exact_boolean.get("result_body_count") or 0),
        "result_watertight": bool(exact_boolean.get("result_watertight", False)),
    }
    for key in (
        "profile_cut_kinds",
        "profile_styles",
    ):
        value = exact_boolean.get(key)
        if isinstance(value, list):
            record[key] = [str(item) for item in value]
    for key in (
        "bore_wall_face_count",
        "bevel_face_count",
        "bevel_segments",
        "shoulder_face_count",
        "chamfer_face_count",
        "ring_count",
        "radial_section_count",
        "cut_count",
        "extruded_cut_count",
        "revolved_cut_count",
    ):
        value = exact_boolean.get(key)
        if value not in (None, "", (), [], {}):
            try:
                record[key] = int(value)
            except (TypeError, ValueError):
                pass
    return record


def _exact_profile_cut_records(trace_operations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for operation_index, operation in enumerate(trace_operations):
        direct = _exact_profile_cut_record(
            operation.get("kernel_exact_boolean"),
            operation_index=operation_index,
        )
        if direct is not None:
            records.append(direct)
        nested = operation.get("kernel_nested_exact_booleans")
        if isinstance(nested, list):
            for item in nested:
                nested_record = _exact_profile_cut_record(
                    item,
                    operation_index=operation_index,
                )
                if nested_record is not None:
                    records.append(nested_record)
    return records


def _exact_profile_cut_summary(trace_operations: list[dict[str, Any]]) -> dict[str, Any]:
    records = _exact_profile_cut_records(trace_operations)
    if not records:
        return {}
    final_record = dict(records[-1])
    final_chamfer_face_count = int(final_record.get("chamfer_face_count") or 0)
    final_bevel_face_count = int(final_record.get("bevel_face_count") or 0)
    return {
        "kernel_program_exact_profile_cut_operation_count": len(records),
        "kernel_program_exact_profile_cut_methods": sorted(
            {str(record.get("method") or "") for record in records if record.get("method")}
        ),
        "kernel_program_exact_profile_cut_final": final_record,
        "kernel_program_exact_profile_cut_final_cut_count": int(
            final_record.get("profile_cut_count") or 0
        ),
        "kernel_program_exact_profile_cut_final_chamfer_face_count": final_chamfer_face_count,
        "kernel_program_exact_profile_cut_final_bevel_face_count": final_bevel_face_count,
        "kernel_program_exact_profile_cut_final_rim_face_count": final_chamfer_face_count + final_bevel_face_count,
        "kernel_program_exact_profile_cut_final_bore_wall_face_count": int(
            final_record.get("bore_wall_face_count") or 0
        ),
    }


def execute_boolean_program(
    kernel: GeometryKernel,
    operands: list[KernelOperand],
    *,
    operation_limit: int | None = None,
    route: str = "ordered_boolean_program",
    backend: str | None = None,
) -> KernelProgramResult:
    """Execute an ordered boolean program against ``kernel``.

    The first union operand is the base when any unions are present; otherwise
    the first intersection operand becomes the base. Subtract operands are
    applied last so cutters do not accidentally become the root body.
    """
    _validate_operands(operands)
    operation_count = boolean_operation_count(operands)
    capabilities = _kernel_capabilities(kernel)
    batch_union = getattr(kernel, "batch_union", None)
    batch_union_available = (
        sum(1 for operand in operands if operand.blend_mode == "union") > 1
        and capabilities.get("batch_union") is True
        and callable(batch_union)
    )
    required_capabilities = _required_boolean_capabilities(
        operands,
        batch_union_available=batch_union_available,
    )
    _require_capabilities(kernel, capabilities, required_capabilities)
    kernel_call_count = boolean_kernel_call_count(
        operands,
        batch_union_available=batch_union_available,
    )
    manifest = build_boolean_program_manifest(
        operands,
        route=route,
        backend=backend,
        operation_limit=operation_limit,
        batch_union_available=batch_union_available,
    )
    if operation_limit is not None and kernel_call_count > operation_limit:
        raise ValueError(
            f"kernel program kernel_call_count={kernel_call_count} exceeds limit={operation_limit} "
            f"(semantic_operation_count={operation_count})"
        )

    union_operands = [operand for operand in operands if operand.blend_mode == "union"]
    subtract_operands = [operand for operand in operands if operand.blend_mode == "subtract"]
    intersect_operands = [operand for operand in operands if operand.blend_mode == "intersect"]
    trace_operations: list[dict[str, Any]] = []

    if union_operands:
        if batch_union_available:
            record = {
                "op": "batch_union",
                "inputs": [operand.operand_id for operand in union_operands],
                "attempted_kernel": kernel.name,
                "actual_kernel": kernel.name,
                "semantic_equivalent_operation_count": max(0, len(union_operands) - 1),
            }
            current = batch_union([operand.handle for operand in union_operands])
            _record_result_probe(record, kernel=kernel, result_handle=current)
            trace_operations.append(record)
            current_id = f"batch_union({','.join(record['inputs'])})"
        else:
            current = union_operands[0].handle
            current_id = union_operands[0].operand_id
            for operand in union_operands[1:]:
                record = _operation_record(op="union", left=current_id, right=operand.operand_id, kernel=kernel)
                previous = current
                current = kernel.union(previous, operand.handle)
                _record_operation_result(record, kernel=kernel, result_handle=current, left_handle=previous)
                trace_operations.append(record)
                current_id = f"union({current_id},{operand.operand_id})"
        remaining_intersections = intersect_operands
    elif intersect_operands:
        current = intersect_operands[0].handle
        current_id = intersect_operands[0].operand_id
        remaining_intersections = intersect_operands[1:]
    else:
        raise ValueError("kernel boolean program requires a union or intersect base operand")

    for operand in remaining_intersections:
        record = _operation_record(op="intersect", left=current_id, right=operand.operand_id, kernel=kernel)
        previous = current
        current = kernel.intersection(previous, operand.handle)
        _record_operation_result(record, kernel=kernel, result_handle=current, left_handle=previous)
        trace_operations.append(record)
        current_id = f"intersect({current_id},{operand.operand_id})"

    for operand in subtract_operands:
        record = _operation_record(op="subtract", left=current_id, right=operand.operand_id, kernel=kernel)
        previous = current
        current = kernel.difference(previous, operand.handle)
        _record_operation_result(record, kernel=kernel, result_handle=current, left_handle=previous)
        trace_operations.append(record)
        current_id = f"subtract({current_id},{operand.operand_id})"

    mesh = _non_empty_mesh(kernel, current)
    operation_records = _semantic_operation_records_from_manifest(manifest)
    fallback_records = [
        dict(record)
        for record in trace_operations
        if isinstance(record.get("kernel_fallback"), dict)
        or bool(record.get("passthrough_fallback_suspected"))
    ]
    runtime_diagnostics = _boolean_fallback_diagnostics(fallback_records)
    manifest = _manifest_with_runtime_diagnostics(manifest, runtime_diagnostics)
    exact_profile_cut_summary = _exact_profile_cut_summary(trace_operations)
    semantic_handoff = _attach_kernel_program_semantic_handoff(
        mesh,
        operands,
        trace_operations,
    )
    operation_names = [
        str(record.get("operation") or "")
        for record in operation_records
        if isinstance(record, dict) and record.get("operation")
    ]
    semantic_operation = (
        operation_names[0]
        if operation_names and len(set(operation_names)) == 1
        else ""
    )
    feature_semantic_operation = _semantic_operation_for_kind(
        operation_records,
        _FEATURE_DETAIL_OPERATION_KINDS,
        fallback=semantic_operation,
    )
    edge_treatment_semantic_operation = _semantic_operation_for_kind(
        operation_records,
        _EDGE_TREATMENT_OPERATION_KINDS,
        fallback=semantic_operation,
    )
    surface_damage_semantic_operation = _semantic_operation_for_kind(
        operation_records,
        _SURFACE_DAMAGE_OPERATION_KINDS,
        fallback=semantic_operation,
    )
    face_semantic_operation = (
        feature_semantic_operation
        or edge_treatment_semantic_operation
        or surface_damage_semantic_operation
        or semantic_operation
    )
    face_operation_record = _final_semantic_operation_record(
        operation_records,
        face_semantic_operation,
    )
    face_operation_ids: list[str] = []
    face_operation_summary: dict[str, Any] = {}
    face_operation_attribution: dict[str, Any] = {
        "schema": "lathe.geometry.kernel_program_face_operation_attribution.v1",
        "source": "kernel_program.boolean",
        "attributed": False,
        "method": "boolean_kernel_face_ranges_unavailable",
        "result_face_count": len(mesh.faces),
        "reason": "boolean_kernel_did_not_preserve_source_face_ranges",
    }
    if face_operation_record:
        face_operation_id = str(face_operation_record.get("operation_id") or "")
        if face_operation_id:
            (
                face_operation_ids,
                face_operation_summary,
                face_operation_attribution,
            ) = _attach_whole_result_face_operation_metadata(
                mesh,
                face_operation_id,
                source="kernel_program.boolean.whole_result_semantic_operation",
                method="whole_result_semantic_operation_range",
                reason="boolean_kernel_did_not_preserve_source_face_ranges",
            )
    else:
        mesh.metadata["lathe_kernel_program_face_operation_attribution"] = dict(
            face_operation_attribution
        )
    kernel_feature_detail = _kernel_feature_detail_metadata(
        kernel,
        mesh,
        current,
        operands,
        semantic_operation=feature_semantic_operation,
        method_suffix="boolean_kernel_program_v1",
        fallback=bool(fallback_records),
        face_operation_attributed=bool(face_operation_ids),
        extra={
            "operand_count": len(operands),
            "boolean_fallback_count": len(fallback_records),
            "kernel_call_count": kernel_call_count,
            "batch_union": bool(batch_union_available),
        },
    )
    if kernel_feature_detail:
        mesh.metadata["lathe_kernel_feature_detail"] = dict(kernel_feature_detail)
    kernel_edge_treatment = _kernel_edge_treatment_metadata(
        kernel,
        mesh,
        current,
        operands,
        semantic_operation=edge_treatment_semantic_operation,
        method_suffix="boolean_kernel_program_v1",
        fallback=bool(fallback_records),
        extra={
            "operand_count": len(operands),
            "boolean_fallback_count": len(fallback_records),
            "kernel_call_count": kernel_call_count,
            "batch_union": bool(batch_union_available),
        },
    )
    if kernel_edge_treatment:
        mesh.metadata["lathe_kernel_edge_treatment"] = dict(kernel_edge_treatment)
    kernel_surface_damage = _kernel_surface_damage_metadata(
        kernel,
        mesh,
        current,
        operands,
        semantic_operation=surface_damage_semantic_operation,
        method_suffix="boolean_kernel_program_v1",
        fallback=bool(fallback_records),
        extra={
            "operand_count": len(operands),
            "boolean_fallback_count": len(fallback_records),
            "kernel_call_count": kernel_call_count,
            "batch_union": bool(batch_union_available),
        },
    )
    if kernel_surface_damage:
        mesh.metadata["lathe_kernel_surface_damage"] = dict(kernel_surface_damage)
    details = {
        "kernel_program_version": KERNEL_PROGRAM_VERSION,
        "kernel_program_route": route,
        "kernel_program_operation_count": operation_count,
        "kernel_program_kernel_call_count": kernel_call_count,
        "kernel_program_operand_count": len(operands),
        "kernel_program_semantic_operation_record_count": len(operation_records),
        "kernel_program_semantic_operation_counts": _operation_counts(operation_records),
        "kernel_program_semantic_operation_records": operation_records,
        "kernel_program_kernel": kernel.name,
        "kernel_program_backend": backend,
        "kernel_program_manifest": manifest,
        "kernel_program_diagnostics": list(manifest.get("diagnostics") or []),
        "kernel_program_capabilities_checked": sorted(required_capabilities),
        "kernel_program_watertight": kernel.is_watertight(current),
        "kernel_program_body_count": kernel.body_count(current),
        "kernel_program_operands": [operand.trace_record() for operand in operands],
        "kernel_program_operations": trace_operations,
        "kernel_program_face_operation_attribution": face_operation_attribution,
        "face_operation_ids": face_operation_ids,
        "face_operation_summary": face_operation_summary,
        "kernel_program_boolean_fallback_count": len(fallback_records),
        "kernel_program_boolean_fallback_records": fallback_records,
        "kernel_feature_detail": kernel_feature_detail,
        "kernel_program_feature_detail": kernel_feature_detail,
        "kernel_edge_treatment": kernel_edge_treatment,
        "kernel_program_edge_treatment": kernel_edge_treatment,
        "kernel_surface_damage": kernel_surface_damage,
        "kernel_program_surface_damage": kernel_surface_damage,
        "kernel_program_semantic_handoff": semantic_handoff,
        **exact_profile_cut_summary,
    }
    return KernelProgramResult(
        mesh=mesh,
        handle=current,
        operation_count=operation_count,
        details=details,
    )


def execute_hull_program(
    kernel: GeometryKernel,
    operands: list[KernelOperand],
    *,
    operation_limit: int | None = None,
    route: str = "convex_hull_program",
    backend: str | None = None,
) -> KernelProgramResult:
    """Execute a convex hull over already-imported kernel operands."""
    _validate_hull_operands(operands)
    operation_count = hull_operation_count(operands)
    if operation_limit is not None and operation_count > operation_limit:
        raise ValueError(
            f"kernel hull operation_count={operation_count} exceeds limit={operation_limit}"
        )
    capabilities = _kernel_capabilities(kernel)
    exact_hull_params = _exact_axis_aligned_box_pair_hull_params(operands)
    if exact_hull_params is None:
        exact_hull_params = _exact_sphere_pair_hull_params(operands)
    if exact_hull_params is None:
        exact_hull_params = _exact_cylinder_pair_hull_params(operands)
    if exact_hull_params is None:
        exact_hull_params = _exact_capsule_pair_hull_params(operands)
    if exact_hull_params is None:
        exact_hull_params = _sampled_mixed_coaxial_profile_hull_params(operands)
    if exact_hull_params is not None:
        required = _exact_rebuild_required_capabilities(exact_hull_params)
        if required and all(capabilities.get(name) is True for name in required):
            hull_exact = bool(exact_hull_params.get("exact", True))
            manifest = build_hull_program_manifest(
                operands,
                route=route,
                backend=backend,
                operation_limit=operation_limit,
            )
            manifest = {
                **manifest,
                "required_capabilities": required,
                "exact_kernel_path": hull_exact,
                **(
                    {"profile_approximation": str(exact_hull_params["profile_approximation"])}
                    if "profile_approximation" in exact_hull_params
                    else {}
                ),
                "exact_hull_method": str(exact_hull_params["method"]),
            }
            primitive_type = str(exact_hull_params["primitive_type"])
            build_kwargs: dict[str, Any] = {
                "center": exact_hull_params["center"],
                "part": "hull",
                "semantic_metadata": {
                    "kernel_program": {
                        "op": "hull",
                        "method": str(exact_hull_params["method"]),
                        "operand_ids": [operand.operand_id for operand in operands],
                    }
                },
            }
            if primitive_type == "box":
                build_kwargs["extents"] = exact_hull_params["extents"]
                build_kwargs["rounding"] = 0.0
            elif primitive_type == "sphere":
                build_kwargs["radius"] = exact_hull_params["radius"]
            elif primitive_type == "capsule":
                build_kwargs["radius"] = exact_hull_params["radius"]
                build_kwargs["length"] = exact_hull_params["length"]
                build_kwargs["axis"] = exact_hull_params["axis"]
            elif primitive_type == "cylinder":
                build_kwargs["radius"] = exact_hull_params["radius"]
                build_kwargs["height"] = exact_hull_params["height"]
                build_kwargs["axis"] = exact_hull_params["axis"]
            elif primitive_type == "revolved_profile":
                build_kwargs["profile_points"] = exact_hull_params["profile_points"]
                build_kwargs["axis"] = exact_hull_params["axis"]
            else:
                build_kwargs = {}
            if build_kwargs:
                current = kernel.build_primitive(primitive_type, **build_kwargs)
                mesh = _non_empty_mesh(kernel, current)
                operation_record: dict[str, Any] = {
                    "op": "hull",
                    "inputs": [operand.operand_id for operand in operands],
                    "attempted_kernel": kernel.name,
                    "actual_kernel": kernel.name,
                    "attempted_backend": f"{kernel.name}.build_primitive",
                    "actual_backend": f"{kernel.name}.build_primitive",
                    "actual_operation": str(exact_hull_params["actual_operation"]),
                    "kernel_hull_method": str(exact_hull_params["method"]),
                    "exact_kernel_path": hull_exact,
                    "fallback": False,
                    "passthrough": False,
                    "result_kind": str(exact_hull_params["result_kind"]),
                    "result_center": list(exact_hull_params["center"]),
                    "result_face_count": len(mesh.faces),
                    "result_vertex_count": len(mesh.vertices),
                    "result_watertight": bool(mesh.is_watertight),
                    "result_body_count": kernel.body_count(current),
                }
                if "radius" in exact_hull_params:
                    operation_record["result_radius"] = float(exact_hull_params["radius"])
                if "extents" in exact_hull_params:
                    operation_record["result_extents"] = [
                        float(value) for value in exact_hull_params["extents"]
                    ]
                if "bounds_min" in exact_hull_params:
                    operation_record["result_bounds_min"] = [
                        float(value) for value in exact_hull_params["bounds_min"]
                    ]
                if "bounds_max" in exact_hull_params:
                    operation_record["result_bounds_max"] = [
                        float(value) for value in exact_hull_params["bounds_max"]
                    ]
                if "length" in exact_hull_params:
                    operation_record["result_length"] = float(exact_hull_params["length"])
                if "height" in exact_hull_params:
                    operation_record["result_height"] = float(exact_hull_params["height"])
                if "axis" in exact_hull_params:
                    operation_record["result_axis"] = str(exact_hull_params["axis"])
                if "profile_point_count" in exact_hull_params:
                    operation_record["result_profile_point_count"] = int(
                        exact_hull_params["profile_point_count"]
                    )
                if "profile_points" in exact_hull_params:
                    operation_record["result_profile_points"] = _json_safe(
                        exact_hull_params["profile_points"]
                    )
                if "profile_approximation" in exact_hull_params:
                    operation_record["profile_approximation"] = str(
                        exact_hull_params["profile_approximation"]
                    )
                if "profile_sample_count" in exact_hull_params:
                    operation_record["profile_sample_count"] = int(
                        exact_hull_params["profile_sample_count"]
                    )
                if "source_spheres" in exact_hull_params:
                    operation_record["source_spheres"] = _json_safe(exact_hull_params["source_spheres"])
                if "source_cylinders" in exact_hull_params:
                    operation_record["source_cylinders"] = _json_safe(exact_hull_params["source_cylinders"])
                if "source_capsules" in exact_hull_params:
                    operation_record["source_capsules"] = _json_safe(exact_hull_params["source_capsules"])
                if "source_boxes" in exact_hull_params:
                    operation_record["source_boxes"] = _json_safe(exact_hull_params["source_boxes"])
                if "source_profile_hull_operands" in exact_hull_params:
                    operation_record["source_profile_hull_operands"] = _json_safe(
                        exact_hull_params["source_profile_hull_operands"]
                    )
                mesh.metadata["lathe_kernel_hull"] = {
                    "schema": "lathe.geometry.kernel_hull.v1",
                    "method": str(exact_hull_params["method"]),
                    "actual_operation": str(exact_hull_params["actual_operation"]),
                    "result_kind": str(exact_hull_params["result_kind"]),
                    "exact_kernel_path": hull_exact,
                    **(
                        {"radius": float(exact_hull_params["radius"])}
                        if "radius" in exact_hull_params
                        else {}
                    ),
                    **(
                        {"extents": [float(value) for value in exact_hull_params["extents"]]}
                        if "extents" in exact_hull_params
                        else {}
                    ),
                    **(
                        {"length": float(exact_hull_params["length"]), "axis": str(exact_hull_params["axis"])}
                        if "length" in exact_hull_params
                        else {}
                    ),
                    **(
                        {"height": float(exact_hull_params["height"]), "axis": str(exact_hull_params["axis"])}
                        if "height" in exact_hull_params
                        else {}
                    ),
                    **(
                        {
                            "profile_point_count": int(exact_hull_params["profile_point_count"]),
                            "profile_points": _json_safe(exact_hull_params["profile_points"]),
                            "axis": str(exact_hull_params["axis"]),
                            **(
                                {"profile_approximation": str(exact_hull_params["profile_approximation"])}
                                if "profile_approximation" in exact_hull_params
                                else {}
                            ),
                            **(
                                {"profile_sample_count": int(exact_hull_params["profile_sample_count"])}
                                if "profile_sample_count" in exact_hull_params
                                else {}
                            ),
                        }
                        if "profile_points" in exact_hull_params
                        else {}
                    ),
                    "fallback": False,
                    "passthrough": False,
                    "result_face_count": len(mesh.faces),
                    "result_vertex_count": len(mesh.vertices),
                    "result_watertight": bool(mesh.is_watertight),
                }
                _record_result_probe(operation_record, kernel=kernel, result_handle=current)
                operation_records = _semantic_operation_records_from_manifest(manifest)
                (
                    final_operation_record,
                    face_operation_ids,
                    face_operation_summary,
                    face_operation_attribution,
                ) = _attach_semantic_whole_result_face_metadata(
                    mesh,
                    operation_records,
                    "op.hull",
                    source="kernel_program.hull.whole_result_semantic_operation",
                    method="whole_result_semantic_operation_range",
                    reason="hull_kernel_rebuilt_result_without_source_face_ranges",
                    extra={
                        "hull_execution_method": str(exact_hull_params["method"]),
                        "exact_kernel_path": hull_exact,
                    },
                )
                if final_operation_record:
                    operation_record["semantic_operation_record"] = dict(final_operation_record)
                kernel_hull = dict(mesh.metadata.get("lathe_kernel_hull") or {})
                kernel_feature_detail = _kernel_feature_detail_metadata(
                    kernel,
                    mesh,
                    current,
                    operands,
                    semantic_operation="op.hull",
                    method_suffix="hull_kernel_program_v1",
                    fallback=False,
                    face_operation_attributed=bool(face_operation_ids),
                    extra={
                        "operand_count": len(operands),
                        "hull_execution_method": str(exact_hull_params["method"]),
                        "exact_kernel_path": hull_exact,
                        "result_kind": str(exact_hull_params["result_kind"]),
                    },
                )
                if kernel_feature_detail:
                    mesh.metadata["lathe_kernel_feature_detail"] = dict(kernel_feature_detail)
                semantic_handoff = _attach_kernel_program_semantic_handoff(
                    mesh,
                    operands,
                    [operation_record],
                )
                return KernelProgramResult(
                    mesh=mesh,
                    handle=current,
                    operation_count=operation_count,
                    details={
                        "kernel_program_version": KERNEL_PROGRAM_VERSION,
                        "kernel_program_route": route,
                        "kernel_program_operation_count": operation_count,
                        "kernel_program_operand_count": len(operands),
                        "kernel_program_semantic_operation_record_count": len(operation_records),
                        "kernel_program_semantic_operation_counts": _operation_counts(operation_records),
                        "kernel_program_semantic_operation_records": operation_records,
                        "kernel_program_kernel": kernel.name,
                        "kernel_program_backend": backend,
                        "kernel_program_manifest": manifest,
                        "kernel_program_capabilities_checked": required,
                        "kernel_program_watertight": bool(mesh.is_watertight),
                        "kernel_program_body_count": kernel.body_count(current),
                        "kernel_program_operands": [operand.trace_record() for operand in operands],
                        "kernel_program_operations": [operation_record],
                        "kernel_program_face_operation_attribution": face_operation_attribution,
                        "face_operation_ids": face_operation_ids,
                        "face_operation_summary": face_operation_summary,
                        "kernel_hull": kernel_hull,
                        "kernel_program_hull": kernel_hull,
                        "kernel_feature_detail": kernel_feature_detail,
                        "kernel_program_feature_detail": kernel_feature_detail,
                        "kernel_program_hull_operand_ids": [operand.operand_id for operand in operands],
                        "kernel_program_semantic_handoff": semantic_handoff,
                        "hull_execution_method": str(exact_hull_params["method"]),
                        "hull_exact": hull_exact,
                        "hull_result_kind": str(exact_hull_params["result_kind"]),
                        "hull_result_center": list(exact_hull_params["center"]),
                        **(
                            {
                                "hull_profile_approximation": str(
                                    exact_hull_params["profile_approximation"]
                                )
                            }
                            if "profile_approximation" in exact_hull_params
                            else {}
                        ),
                        **(
                            {"hull_result_radius": float(exact_hull_params["radius"])}
                            if "radius" in exact_hull_params
                            else {}
                        ),
                        **(
                            {
                                "hull_result_extents": [
                                    float(value) for value in exact_hull_params["extents"]
                                ],
                                "hull_result_bounds_min": [
                                    float(value) for value in exact_hull_params["bounds_min"]
                                ],
                                "hull_result_bounds_max": [
                                    float(value) for value in exact_hull_params["bounds_max"]
                                ],
                            }
                            if "extents" in exact_hull_params
                            else {}
                        ),
                        **(
                            {
                                "hull_result_length": float(exact_hull_params["length"]),
                                "hull_result_axis": str(exact_hull_params["axis"]),
                            }
                            if "length" in exact_hull_params
                            else {}
                        ),
                        **(
                            {
                                "hull_result_height": float(exact_hull_params["height"]),
                                "hull_result_axis": str(exact_hull_params["axis"]),
                            }
                            if "height" in exact_hull_params
                            else {}
                        ),
                        **(
                            {
                                "hull_result_profile_point_count": int(
                                    exact_hull_params["profile_point_count"]
                                ),
                                "hull_result_profile_points": _json_safe(
                                    exact_hull_params["profile_points"]
                                ),
                                "hull_result_axis": str(exact_hull_params["axis"]),
                                **(
                                    {"hull_profile_sample_count": int(exact_hull_params["profile_sample_count"])}
                                    if "profile_sample_count" in exact_hull_params
                                    else {}
                                ),
                            }
                            if "profile_points" in exact_hull_params
                            else {}
                        ),
                    },
                )
    _require_capabilities(kernel, capabilities, {"hull", "to_trimesh"})
    manifest = build_hull_program_manifest(
        operands,
        route=route,
        backend=backend,
        operation_limit=operation_limit,
    )

    operand_ids = [operand.operand_id for operand in operands]
    current = kernel.hull([operand.handle for operand in operands])
    mesh = _non_empty_mesh(kernel, current)
    bounds = np.asarray(mesh.bounds, dtype=np.float64)
    bounds_min = [float(value) for value in bounds[0]]
    bounds_max = [float(value) for value in bounds[1]]
    result_extents = [
        float(bounds_max[index] - bounds_min[index])
        for index in range(3)
    ]
    result_center = [
        float((bounds_min[index] + bounds_max[index]) * 0.5)
        for index in range(3)
    ]
    operation_record: dict[str, Any] = {
        "op": "hull",
        "inputs": operand_ids,
        "attempted_kernel": kernel.name,
        "actual_kernel": kernel.name,
        "result_face_count": len(mesh.faces),
        "result_vertex_count": len(mesh.vertices),
        "result_watertight": bool(mesh.is_watertight),
        "result_body_count": kernel.body_count(current),
        "result_kind": "convex_hull",
        "result_center": result_center,
        "result_bounds_min": bounds_min,
        "result_bounds_max": bounds_max,
        "result_extents": result_extents,
        "exact_kernel_path": True,
        "fallback": False,
        "passthrough": False,
    }
    kernel_hull = _dict_metadata(mesh.metadata.get("lathe_reference_hull"))
    if not kernel_hull:
        kernel_hull = _dict_metadata(mesh.metadata.get("lathe_manifold_hull"))
    if kernel_hull:
        operation_record["kernel_hull"] = dict(kernel_hull)
        operation_record["kernel_hull_method"] = str(kernel_hull.get("method") or "")
        operation_record["attempted_backend"] = str(
            kernel_hull.get("attempted_backend") or ""
        )
        operation_record["actual_backend"] = str(kernel_hull.get("actual_backend") or "")
        operation_record["actual_operation"] = str(
            kernel_hull.get("actual_operation") or ""
        )
    hull_method = str(
        operation_record.get("kernel_hull_method")
        or operation_record.get("actual_operation")
        or "kernel_convex_hull_v1"
    )
    operation_record["kernel_hull_method"] = hull_method
    operation_records = _semantic_operation_records_from_manifest(manifest)
    kernel_hull_payload = {
        "schema": "lathe.geometry.kernel_hull.v1",
        "method": hull_method,
        "source_operand_ids": operand_ids,
        "attempted_backend": str(operation_record.get("attempted_backend") or f"{kernel.name}.hull"),
        "actual_backend": str(operation_record.get("actual_backend") or f"{kernel.name}.hull"),
        "actual_operation": str(operation_record.get("actual_operation") or hull_method),
        "result_kind": "convex_hull",
        "result_center": result_center,
        "result_bounds_min": bounds_min,
        "result_bounds_max": bounds_max,
        "result_extents": result_extents,
        "exact_kernel_path": True,
        "fallback": False,
        "passthrough": False,
        "result_face_count": len(mesh.faces),
        "result_vertex_count": len(mesh.vertices),
        "result_watertight": bool(mesh.is_watertight),
    }
    if kernel_hull:
        kernel_hull_payload["kernel_trace"] = dict(kernel_hull)
    mesh.metadata["lathe_kernel_hull"] = dict(kernel_hull_payload)
    (
        final_operation_record,
        face_operation_ids,
        face_operation_summary,
        face_operation_attribution,
    ) = _attach_semantic_whole_result_face_metadata(
        mesh,
        operation_records,
        "op.hull",
        source="kernel_program.hull.whole_result_semantic_operation",
        method="whole_result_semantic_operation_range",
        reason="hull_kernel_did_not_preserve_source_face_ranges",
        extra={
            "hull_execution_method": hull_method,
            "exact_kernel_path": True,
        },
    )
    if final_operation_record:
        operation_record["semantic_operation_record"] = dict(final_operation_record)
    kernel_feature_detail = _kernel_feature_detail_metadata(
        kernel,
        mesh,
        current,
        operands,
        semantic_operation="op.hull",
        method_suffix="hull_kernel_program_v1",
        fallback=False,
        face_operation_attributed=bool(face_operation_ids),
        extra={
            "operand_count": len(operands),
            "hull_execution_method": hull_method,
            "exact_kernel_path": True,
            "result_kind": "convex_hull",
        },
    )
    if kernel_feature_detail:
        mesh.metadata["lathe_kernel_feature_detail"] = dict(kernel_feature_detail)
    semantic_handoff = _attach_kernel_program_semantic_handoff(
        mesh,
        operands,
        [operation_record],
    )
    details = {
        "kernel_program_version": KERNEL_PROGRAM_VERSION,
        "kernel_program_route": route,
        "kernel_program_operation_count": operation_count,
        "kernel_program_operand_count": len(operands),
        "kernel_program_semantic_operation_record_count": len(operation_records),
        "kernel_program_semantic_operation_counts": _operation_counts(operation_records),
        "kernel_program_semantic_operation_records": operation_records,
        "kernel_program_kernel": kernel.name,
        "kernel_program_backend": backend,
        "kernel_program_manifest": manifest,
        "kernel_program_capabilities_checked": ["hull", "to_trimesh"],
        "kernel_program_watertight": kernel.is_watertight(current),
        "kernel_program_body_count": kernel.body_count(current),
        "kernel_program_operands": [operand.trace_record() for operand in operands],
        "kernel_program_operations": [operation_record],
        "kernel_program_face_operation_attribution": face_operation_attribution,
        "face_operation_ids": face_operation_ids,
        "face_operation_summary": face_operation_summary,
        "kernel_hull": kernel_hull_payload,
        "kernel_program_hull": kernel_hull_payload,
        "kernel_feature_detail": kernel_feature_detail,
        "kernel_program_feature_detail": kernel_feature_detail,
        "kernel_program_hull_operand_ids": operand_ids,
        "kernel_program_semantic_handoff": semantic_handoff,
        "hull_execution_method": hull_method,
        "hull_exact": True,
        "hull_result_kind": "convex_hull",
        "hull_result_center": result_center,
        "hull_result_bounds_min": bounds_min,
        "hull_result_bounds_max": bounds_max,
        "hull_result_extents": result_extents,
    }
    return KernelProgramResult(
        mesh=mesh,
        handle=current,
        operation_count=operation_count,
        details=details,
    )


def execute_minkowski_program(
    kernel: GeometryKernel,
    source: KernelOperand,
    structuring: KernelOperand,
    *,
    structuring_center: tuple[float, float, float] = (0.0, 0.0, 0.0),
    sample_limit: int = 50_000,
    operation_limit: int | None = None,
    route: str = "convex_minkowski_program",
    backend: str | None = None,
) -> KernelProgramResult:
    """Execute a deterministic Minkowski construction.

    Exact axis-aligned box cases lower to native kernel primitives. General
    convex operands still use the vertex-sum convex hull fallback and record
    that approximation explicitly.
    """
    if sample_limit <= 0:
        raise ValueError("kernel minkowski sample_limit must be positive")
    _validate_minkowski_operands(source, structuring)
    operation_count = minkowski_operation_count(source, structuring)
    if operation_limit is not None and operation_count > operation_limit:
        raise ValueError(
            f"kernel minkowski operation_count={operation_count} exceeds limit={operation_limit}"
        )
    capabilities = _kernel_capabilities(kernel)
    _require_capabilities(kernel, capabilities, {"to_trimesh"})

    source_mesh = _non_empty_mesh(kernel, source.handle)
    structuring_mesh = _non_empty_mesh(kernel, structuring.handle)
    source_vertex_count = len(source_mesh.vertices)
    structuring_vertex_count = len(structuring_mesh.vertices)
    pair_count = source_vertex_count * structuring_vertex_count
    if source_vertex_count == 0 or structuring_vertex_count == 0:
        raise ValueError("kernel minkowski requires non-empty source and structuring meshes")

    exact_box_params = _exact_axis_aligned_box_minkowski_params(
        source_mesh,
        structuring_mesh,
        structuring_center=structuring_center,
    )
    exact_round_box_params = None
    if exact_box_params is None:
        exact_round_box_params = _exact_axis_aligned_box_sphere_minkowski_params(
            source_mesh,
            structuring_mesh,
            structuring_center=structuring_center,
        )
    if exact_box_params is None and exact_round_box_params is None:
        exact_box_capsule_params = _exact_axis_aligned_box_capsule_minkowski_params(
            source_mesh,
            structuring_mesh,
            structuring_center=structuring_center,
        )
    else:
        exact_box_capsule_params = None
    if (
        exact_box_params is None
        and exact_round_box_params is None
        and exact_box_capsule_params is None
    ):
        exact_box_cylinder_params = _exact_axis_aligned_box_cylinder_minkowski_params(
            source_mesh,
            structuring_mesh,
            structuring_center=structuring_center,
        )
    else:
        exact_box_cylinder_params = None
    exact_sphere_params = None
    if (
        exact_box_params is None
        and exact_round_box_params is None
        and exact_box_capsule_params is None
    ):
        exact_cylinder_cylinder_params = _exact_cylinder_cylinder_minkowski_params(
            source_mesh,
            structuring_mesh,
            structuring_center=structuring_center,
        )
    else:
        exact_cylinder_cylinder_params = None
    if (
        exact_box_params is None
        and exact_round_box_params is None
        and exact_box_capsule_params is None
        and exact_box_cylinder_params is None
        and exact_cylinder_cylinder_params is None
    ):
        exact_cylinder_capsule_params = _exact_cylinder_capsule_minkowski_params(
            source_mesh,
            structuring_mesh,
            structuring_center=structuring_center,
        )
    else:
        exact_cylinder_capsule_params = None
    if (
        exact_box_params is None
        and exact_round_box_params is None
        and exact_box_capsule_params is None
        and exact_box_cylinder_params is None
        and exact_cylinder_cylinder_params is None
        and exact_cylinder_capsule_params is None
    ):
        exact_capsule_capsule_params = _exact_capsule_capsule_minkowski_params(
            source_mesh,
            structuring_mesh,
            structuring_center=structuring_center,
        )
    else:
        exact_capsule_capsule_params = None
    if (
        exact_box_params is None
        and exact_round_box_params is None
        and exact_box_capsule_params is None
        and exact_box_cylinder_params is None
        and exact_cylinder_cylinder_params is None
        and exact_cylinder_capsule_params is None
        and exact_capsule_capsule_params is None
    ):
        exact_capsule_sphere_params = _exact_capsule_sphere_minkowski_params(
            source_mesh,
            structuring_mesh,
            structuring_center=structuring_center,
        )
    else:
        exact_capsule_sphere_params = None
    if (
        exact_box_params is None
        and exact_round_box_params is None
        and exact_box_capsule_params is None
        and exact_box_cylinder_params is None
        and exact_cylinder_cylinder_params is None
        and exact_cylinder_capsule_params is None
        and exact_capsule_capsule_params is None
        and exact_capsule_sphere_params is None
    ):
        exact_cylinder_sphere_params = _exact_cylinder_sphere_minkowski_params(
            source_mesh,
            structuring_mesh,
            structuring_center=structuring_center,
        )
    else:
        exact_cylinder_sphere_params = None
    if (
        exact_box_params is None
        and exact_round_box_params is None
        and exact_box_cylinder_params is None
        and exact_cylinder_cylinder_params is None
        and exact_cylinder_capsule_params is None
        and exact_capsule_capsule_params is None
        and exact_capsule_sphere_params is None
        and exact_cylinder_sphere_params is None
    ):
        exact_sphere_params = _exact_sphere_sphere_minkowski_params(
            source_mesh,
            structuring_mesh,
            structuring_center=structuring_center,
        )
    else:
        exact_sphere_params = None
    exact_minkowski_params: dict[str, Any] | None = None
    if exact_box_params is not None:
        exact_minkowski_params = {
            **exact_box_params,
            "required_capability": "box",
            "required_capabilities": ["box"],
            "primitive_type": "box",
            "method": "exact_axis_aligned_box_sum_v1",
            "actual_operation": "axis_aligned_box_minkowski_sum",
            "approximation": "none_exact_axis_aligned_box_sum",
            "result_kind": "box",
            "rounding": 0.0,
        }
    elif exact_round_box_params is not None:
        exact_minkowski_params = {
            **exact_round_box_params,
            "required_capability": "box_rounding",
            "required_capabilities": ["box", "box_rounding"],
            "primitive_type": "box",
            "method": "exact_axis_aligned_box_sphere_rounding_v1",
            "actual_operation": "axis_aligned_box_sphere_minkowski_sum",
            "approximation": "none_exact_axis_aligned_box_sphere_rounding",
            "result_kind": "rounded_box",
        }
    elif exact_box_capsule_params is not None:
        exact_minkowski_params = {
            **exact_box_capsule_params,
            "required_capability": "box_rounding",
            "required_capabilities": ["box", "box_rounding"],
            "primitive_type": "box",
            "method": "exact_axis_aligned_box_capsule_rounding_v1",
            "actual_operation": "axis_aligned_box_capsule_minkowski_sum",
            "approximation": "none_exact_axis_aligned_box_capsule_rounding",
            "result_kind": "rounded_box",
        }
    elif exact_box_cylinder_params is not None:
        exact_minkowski_params = {
            **exact_box_cylinder_params,
            "required_capability": "extruded_profile",
            "required_capabilities": ["extruded_profile"],
            "primitive_type": "extruded_profile",
            "method": "exact_axis_aligned_box_cylinder_profile_sum_v1",
            "actual_operation": "axis_aligned_box_cylinder_minkowski_sum",
            "approximation": "none_exact_axis_aligned_box_cylinder_profile_sum",
            "result_kind": "rounded_rectangle_extruded_profile",
            "rounding": 0.0,
        }
    elif exact_cylinder_cylinder_params is not None:
        exact_minkowski_params = {
            **exact_cylinder_cylinder_params,
            "required_capability": "cylinder",
            "required_capabilities": ["cylinder"],
            "primitive_type": "cylinder",
            "method": "exact_coaxial_cylinder_sum_v1",
            "actual_operation": "coaxial_cylinder_minkowski_sum",
            "approximation": "none_exact_coaxial_cylinder_sum",
            "result_kind": "cylinder",
            "rounding": 0.0,
        }
    elif exact_cylinder_capsule_params is not None:
        exact_minkowski_params = {
            **exact_cylinder_capsule_params,
            "required_capability": "capsule",
            "required_capabilities": ["capsule"],
            "primitive_type": "capsule",
            "method": "exact_coaxial_cylinder_capsule_sum_v1",
            "actual_operation": "coaxial_cylinder_capsule_minkowski_sum",
            "approximation": "none_exact_coaxial_cylinder_capsule_sum",
            "result_kind": "capsule",
            "rounding": 0.0,
        }
    elif exact_capsule_capsule_params is not None:
        exact_minkowski_params = {
            **exact_capsule_capsule_params,
            "required_capability": "capsule",
            "required_capabilities": ["capsule"],
            "primitive_type": "capsule",
            "method": "exact_coaxial_capsule_sum_v1",
            "actual_operation": "coaxial_capsule_minkowski_sum",
            "approximation": "none_exact_coaxial_capsule_sum",
            "result_kind": "capsule",
            "rounding": 0.0,
        }
    elif exact_capsule_sphere_params is not None:
        exact_minkowski_params = {
            **exact_capsule_sphere_params,
            "required_capability": "capsule",
            "required_capabilities": ["capsule"],
            "primitive_type": "capsule",
            "method": "exact_capsule_sphere_sum_v1",
            "actual_operation": "capsule_sphere_minkowski_sum",
            "approximation": "none_exact_capsule_sphere_sum",
            "result_kind": "capsule",
            "rounding": 0.0,
        }
    elif exact_cylinder_sphere_params is not None:
        exact_minkowski_params = {
            **exact_cylinder_sphere_params,
            "required_capability": "capsule",
            "required_capabilities": ["capsule"],
            "primitive_type": "capsule",
            "method": "exact_cylinder_sphere_capsule_sum_v1",
            "actual_operation": "cylinder_sphere_minkowski_sum",
            "approximation": "none_exact_cylinder_sphere_capsule_sum",
            "result_kind": "capsule",
            "rounding": 0.0,
        }
    elif exact_sphere_params is not None:
        exact_minkowski_params = {
            **exact_sphere_params,
            "required_capability": "sphere",
            "required_capabilities": ["sphere"],
            "primitive_type": "sphere",
            "method": "exact_sphere_sum_v1",
            "actual_operation": "sphere_minkowski_sum",
            "approximation": "none_exact_sphere_sum",
            "result_kind": "sphere",
            "rounding": 0.0,
        }
    exact_box_failure: str | None = None
    exact_required_capabilities = _exact_rebuild_required_capabilities(
        exact_minkowski_params
    )
    if (
        exact_minkowski_params is not None
        and exact_required_capabilities
        and all(capabilities.get(str(name)) is True for name in exact_required_capabilities)
    ):
        manifest = build_minkowski_program_manifest(
            source,
            structuring,
            route=route,
            backend=backend,
            operation_limit=operation_limit,
            sample_limit=sample_limit,
            pair_count=pair_count,
            sample_stride=0,
            sample_count=0,
            approximation=str(exact_minkowski_params["approximation"]),
            required_capabilities=[str(name) for name in exact_required_capabilities],
        )
        result_extents = exact_minkowski_params.get("extents")
        result_radius = exact_minkowski_params.get("radius")
        result_length = exact_minkowski_params.get("length")
        result_height = exact_minkowski_params.get("height")
        result_extrude_height = exact_minkowski_params.get("extrude_height")
        result_profile_polygon = exact_minkowski_params.get("profile_polygon")
        result_axis = exact_minkowski_params.get("axis")
        operation_record = {
            "op": "minkowski",
            "source": source.operand_id,
            "structuring": structuring.operand_id,
            "attempted_kernel": kernel.name,
            "actual_kernel": kernel.name,
            "attempted_backend": f"{kernel.name}.build_primitive",
            "actual_backend": f"{kernel.name}.build_primitive",
            "actual_operation": str(exact_minkowski_params["actual_operation"]),
            "kernel_minkowski_method": str(exact_minkowski_params["method"]),
            "exact_kernel_path": True,
            "fallback": False,
            "passthrough": False,
            "approximation": "none",
            "result_kind": str(exact_minkowski_params["result_kind"]),
            "source_vertex_count": source_vertex_count,
            "structuring_vertex_count": structuring_vertex_count,
            "pair_count": pair_count,
            "sample_stride": 0,
            "sample_count": 0,
            "structuring_center": list(exact_minkowski_params["structuring_center"]),
            "structuring_center_offset": list(exact_minkowski_params["structuring_center_offset"]),
            "result_center": list(exact_minkowski_params["center"]),
        }
        if result_extents is not None:
            operation_record["result_extents"] = list(result_extents)
        if result_radius is not None:
            operation_record["result_radius"] = float(result_radius)
        if result_length is not None:
            operation_record["result_length"] = float(result_length)
        if result_height is not None:
            operation_record["result_height"] = float(result_height)
        if result_extrude_height is not None:
            operation_record["result_extrude_height"] = float(result_extrude_height)
        if isinstance(result_profile_polygon, list):
            operation_record["result_profile_point_count"] = len(result_profile_polygon)
        if result_axis is not None:
            operation_record["result_axis"] = str(result_axis)
        for metadata_name in (
            "source_box",
            "structuring_box",
            "source_cylinder",
            "structuring_cylinder",
            "source_capsule",
            "structuring_capsule",
            "source_sphere",
            "structuring_sphere",
        ):
            if metadata_name in exact_minkowski_params:
                operation_record[metadata_name] = _json_safe(exact_minkowski_params[metadata_name])
        try:
            part = source.part or "minkowski"
            primitive_type = str(exact_minkowski_params.get("primitive_type") or "box")
            build_kwargs: dict[str, Any] = {
                "center": exact_minkowski_params["center"],
                "part": f"{part}_minkowski",
                "semantic_metadata": {
                    "kernel_program": {
                        "op": "minkowski",
                        "method": str(exact_minkowski_params["method"]),
                        "source_operand_id": source.operand_id,
                        "structuring_operand_id": structuring.operand_id,
                    }
                },
            }
            if primitive_type == "sphere":
                build_kwargs["radius"] = exact_minkowski_params["radius"]
            elif primitive_type == "capsule":
                build_kwargs["radius"] = exact_minkowski_params["radius"]
                build_kwargs["length"] = exact_minkowski_params["length"]
                build_kwargs["axis"] = exact_minkowski_params["axis"]
            elif primitive_type == "cylinder":
                build_kwargs["radius"] = exact_minkowski_params["radius"]
                build_kwargs["height"] = exact_minkowski_params["height"]
                build_kwargs["axis"] = exact_minkowski_params["axis"]
            elif primitive_type == "extruded_profile":
                build_kwargs["profile_polygon"] = exact_minkowski_params["profile_polygon"]
                build_kwargs["extrude_height"] = exact_minkowski_params["extrude_height"]
                build_kwargs["axis"] = exact_minkowski_params["axis"]
            else:
                build_kwargs["extents"] = exact_minkowski_params["extents"]
                build_kwargs["rounding"] = float(exact_minkowski_params.get("rounding") or 0.0)
            current = kernel.build_primitive(primitive_type, **build_kwargs)
            mesh = _non_empty_mesh(kernel, current)
            if primitive_type == "sphere":
                shape_payload = {"radius": float(exact_minkowski_params["radius"])}
            elif primitive_type == "capsule":
                shape_payload = {
                    "radius": float(exact_minkowski_params["radius"]),
                    "length": float(exact_minkowski_params["length"]),
                    "axis": str(exact_minkowski_params["axis"]),
                }
            elif primitive_type == "cylinder":
                shape_payload = {
                    "radius": float(exact_minkowski_params["radius"]),
                    "height": float(exact_minkowski_params["height"]),
                    "axis": str(exact_minkowski_params["axis"]),
                }
            elif primitive_type == "extruded_profile":
                shape_payload = {
                    "axis": str(exact_minkowski_params["axis"]),
                    "extrude_height": float(exact_minkowski_params["extrude_height"]),
                    "profile_point_count": len(exact_minkowski_params.get("profile_polygon") or []),
                    "rounding_radius": float(exact_minkowski_params.get("rounding_radius") or 0.0),
                    "profile_width": float(exact_minkowski_params.get("profile_width") or 0.0),
                    "profile_height": float(exact_minkowski_params.get("profile_height") or 0.0),
                }
            else:
                shape_payload = {"rounding": float(exact_minkowski_params.get("rounding") or 0.0)}
            mesh.metadata["lathe_kernel_minkowski"] = {
                "schema": "lathe.geometry.kernel_minkowski.v1",
                "method": str(exact_minkowski_params["method"]),
                "source_operand_id": source.operand_id,
                "structuring_operand_id": structuring.operand_id,
                "attempted_backend": f"{kernel.name}.build_primitive",
                "actual_backend": f"{kernel.name}.build_primitive",
                "actual_operation": str(exact_minkowski_params["actual_operation"]),
                "result_kind": str(exact_minkowski_params["result_kind"]),
                **shape_payload,
                "fallback": False,
                "passthrough": False,
                "result_face_count": len(mesh.faces),
                "result_vertex_count": len(mesh.vertices),
                "result_watertight": bool(mesh.is_watertight),
            }
            _record_result_probe(operation_record, kernel=kernel, result_handle=current)
            operand_records = _semantic_operation_records_from_manifest(manifest)
            (
                final_operation_record,
                face_operation_ids,
                face_operation_summary,
                face_operation_attribution,
            ) = _attach_semantic_whole_result_face_metadata(
                mesh,
                operand_records,
                "op.minkowski",
                source="kernel_program.minkowski.whole_result_semantic_operation",
                method="whole_result_semantic_operation_range",
                reason="minkowski_kernel_rebuilt_result_without_source_face_ranges",
                extra={
                    "minkowski_execution_method": str(exact_minkowski_params["method"]),
                    "exact_kernel_path": True,
                },
            )
            if final_operation_record:
                operation_record["semantic_operation_record"] = dict(final_operation_record)
            kernel_minkowski = dict(mesh.metadata.get("lathe_kernel_minkowski") or {})
            kernel_feature_detail = _kernel_feature_detail_metadata(
                kernel,
                mesh,
                current,
                [source, structuring],
                semantic_operation="op.minkowski",
                method_suffix="minkowski_kernel_program_v1",
                fallback=False,
                face_operation_attributed=bool(face_operation_ids),
                extra={
                    "minkowski_execution_method": str(exact_minkowski_params["method"]),
                    "exact_kernel_path": True,
                    "approximation": "none",
                    "pair_count": pair_count,
                },
            )
            if kernel_feature_detail:
                mesh.metadata["lathe_kernel_feature_detail"] = dict(kernel_feature_detail)
            details = {
                "kernel_program_version": KERNEL_PROGRAM_VERSION,
                "kernel_program_route": route,
                "kernel_program_operation_count": operation_count,
                "kernel_program_operand_count": 2,
                "kernel_program_semantic_operation_record_count": len(operand_records),
                "kernel_program_semantic_operation_counts": _operation_counts(operand_records),
                "kernel_program_semantic_operation_records": operand_records,
                "kernel_program_kernel": kernel.name,
                "kernel_program_backend": backend,
                "kernel_program_manifest": manifest,
                "kernel_program_capabilities_checked": _required_capability_list(
                    exact_required_capabilities,
                    "to_trimesh",
                ),
                "kernel_program_watertight": bool(mesh.is_watertight),
                "kernel_program_body_count": len(mesh.split(only_watertight=False)),
                "kernel_program_operands": [source.trace_record(), structuring.trace_record()],
                "kernel_program_operations": [operation_record],
                "kernel_program_face_operation_attribution": face_operation_attribution,
                "face_operation_ids": face_operation_ids,
                "face_operation_summary": face_operation_summary,
                "kernel_minkowski": kernel_minkowski,
                "kernel_program_minkowski": kernel_minkowski,
                "kernel_feature_detail": kernel_feature_detail,
                "kernel_program_feature_detail": kernel_feature_detail,
                "kernel_program_minkowski_source_operand_id": source.operand_id,
                "kernel_program_minkowski_structuring_operand_id": structuring.operand_id,
                "minkowski_execution_method": str(exact_minkowski_params["method"]),
                "minkowski_exact": True,
                "minkowski_approximation": "none",
                "minkowski_pair_count": pair_count,
                "minkowski_sample_stride": 0,
                "minkowski_sample_count": 0,
                "minkowski_kernel_import_succeeded": False,
                "minkowski_finalized_by_kernel": True,
                "minkowski_result_kind": str(exact_minkowski_params["result_kind"]),
                "minkowski_result_center": list(exact_minkowski_params["center"]),
            }
            if result_extents is not None:
                details["minkowski_result_extents"] = list(result_extents)
            if result_radius is not None:
                details["minkowski_result_radius"] = float(result_radius)
            if result_length is not None:
                details["minkowski_result_length"] = float(result_length)
            if result_height is not None:
                details["minkowski_result_height"] = float(result_height)
            if result_extrude_height is not None:
                details["minkowski_result_extrude_height"] = float(result_extrude_height)
            if isinstance(result_profile_polygon, list):
                details["minkowski_result_profile_point_count"] = len(result_profile_polygon)
            if result_axis is not None:
                details["minkowski_result_axis"] = str(result_axis)
            if primitive_type not in {"sphere", "capsule", "cylinder", "extruded_profile"}:
                details["minkowski_rounding"] = float(exact_minkowski_params.get("rounding") or 0.0)
            semantic_handoff = _attach_kernel_program_semantic_handoff(
                mesh,
                [source, structuring],
                [operation_record],
            )
            details["kernel_program_semantic_handoff"] = semantic_handoff
            return KernelProgramResult(
                mesh=mesh,
                handle=current,
                operation_count=operation_count,
                details=details,
            )
        except (AttributeError, TypeError, ValueError, RuntimeError, OSError) as exc:
            exact_box_failure = f"{type(exc).__name__}: {exc}"

    _require_capabilities(kernel, capabilities, {"hull", "to_trimesh"})
    offsets = [
        (
            float(vertex[0]) - structuring_center[0],
            float(vertex[1]) - structuring_center[1],
            float(vertex[2]) - structuring_center[2],
        )
        for vertex in structuring_mesh.vertices.tolist()
    ]
    source_vertices = [
        (float(vertex[0]), float(vertex[1]), float(vertex[2]))
        for vertex in source_mesh.vertices.tolist()
    ]

    stride = max(1, math.ceil(pair_count / sample_limit))
    points: list[tuple[float, float, float]] = []
    pair_index = 0
    for vertex in source_vertices:
        for offset in offsets:
            if pair_index % stride == 0:
                points.append(
                    (
                        vertex[0] + offset[0],
                        vertex[1] + offset[1],
                        vertex[2] + offset[2],
                    )
                )
            pair_index += 1

    hull_seed = trimesh.Trimesh(vertices=points, faces=[], process=False).convex_hull
    if not isinstance(hull_seed, trimesh.Trimesh) or len(hull_seed.faces) == 0:
        raise ValueError("kernel minkowski convex hull approximation produced an empty mesh")
    manifest = build_minkowski_program_manifest(
        source,
        structuring,
        route=route,
        backend=backend,
        operation_limit=operation_limit,
        sample_limit=sample_limit,
        pair_count=pair_count,
        sample_stride=stride,
        sample_count=len(points),
    )

    import_succeeded = False
    finalized_by_kernel = False
    kernel_failure: str | None = None
    current: Any = hull_seed
    mesh = hull_seed
    operation_record: dict[str, Any] = {
        "op": "minkowski",
        "source": source.operand_id,
        "structuring": structuring.operand_id,
        "attempted_kernel": kernel.name,
        "attempted_backend": f"{kernel.name}.hull",
        "actual_backend": "trimesh.convex_hull",
        "actual_operation": "convex_vertex_sum_hull",
        "exact_kernel_path": False,
        "actual_kernel": "trimesh.convex_hull",
        "approximation": "convex_vertex_sum_hull",
        "source_vertex_count": len(source_vertices),
        "structuring_vertex_count": len(offsets),
        "pair_count": pair_count,
        "sample_stride": stride,
        "sample_count": len(points),
        "seed_hull_face_count": len(hull_seed.faces),
        "seed_hull_watertight": bool(hull_seed.is_watertight),
    }
    if exact_minkowski_params is not None:
        operation_record["exact_minkowski_path_available"] = True
        operation_record["exact_minkowski_path_method"] = str(
            exact_minkowski_params.get("method") or ""
        )
        if not all(capabilities.get(str(name)) is True for name in exact_required_capabilities):
            operation_record["exact_minkowski_path_skipped"] = (
                "kernel_did_not_advertise_required_capability"
            )
            operation_record["exact_minkowski_required_capabilities"] = [
                str(name)
                for name in exact_required_capabilities
            ]
    if exact_box_failure:
        operation_record["exact_minkowski_path_failed"] = exact_box_failure
        operation_record["exact_kernel_path_fallback"] = True
        operation_record["fallback"] = True
    try:
        imported = kernel.from_trimesh(hull_seed)
        import_succeeded = True
        current = kernel.hull([imported])
        mesh = _non_empty_mesh(kernel, current)
        finalized_by_kernel = True
        operation_record["actual_kernel"] = kernel.name
        _record_result_probe(operation_record, kernel=kernel, result_handle=current)
    except (AttributeError, TypeError, ValueError, RuntimeError, OSError) as exc:
        kernel_failure = f"{type(exc).__name__}: {exc}"
        current = hull_seed
        mesh = hull_seed
        operation_record["kernel_finalize_failed"] = kernel_failure
        operation_record["result_face_count"] = len(mesh.faces)
        operation_record["result_watertight"] = bool(mesh.is_watertight)
        operation_record["result_body_count"] = len(mesh.split(only_watertight=False))

    operand_records = _semantic_operation_records_from_manifest(manifest)
    kernel_minkowski = {
        "schema": "lathe.geometry.kernel_minkowski.v1",
        "method": "convex_vertex_sum_hull",
        "source_operand_id": source.operand_id,
        "structuring_operand_id": structuring.operand_id,
        "attempted_backend": f"{kernel.name}.hull",
        "actual_backend": str(operation_record.get("actual_backend") or "trimesh.convex_hull"),
        "actual_operation": "convex_vertex_sum_hull",
        "result_kind": "convex_hull_approximation",
        "exact_kernel_path": False,
        "approximation": "convex_vertex_sum_hull",
        "fallback": bool(operation_record.get("fallback", False)),
        "passthrough": False,
        "source_vertex_count": len(source_vertices),
        "structuring_vertex_count": len(offsets),
        "pair_count": pair_count,
        "sample_stride": stride,
        "sample_count": len(points),
        "result_face_count": len(mesh.faces),
        "result_vertex_count": len(mesh.vertices),
        "result_watertight": bool(mesh.is_watertight),
    }
    if kernel_failure:
        kernel_minkowski["kernel_finalize_failed"] = kernel_failure
    if exact_box_failure:
        kernel_minkowski["exact_kernel_path_failed"] = exact_box_failure
    mesh.metadata["lathe_kernel_minkowski"] = dict(kernel_minkowski)
    (
        final_operation_record,
        face_operation_ids,
        face_operation_summary,
        face_operation_attribution,
    ) = _attach_semantic_whole_result_face_metadata(
        mesh,
        operand_records,
        "op.minkowski",
        source="kernel_program.minkowski.whole_result_semantic_operation",
        method="whole_result_semantic_operation_range",
        reason="minkowski_kernel_did_not_preserve_source_face_ranges",
        extra={
            "minkowski_execution_method": "convex_vertex_sum_hull",
            "exact_kernel_path": False,
            "approximation": "convex_vertex_sum_hull",
        },
    )
    if final_operation_record:
        operation_record["semantic_operation_record"] = dict(final_operation_record)
    kernel_feature_detail = _kernel_feature_detail_metadata(
        kernel,
        mesh,
        current,
        [source, structuring],
        semantic_operation="op.minkowski",
        method_suffix="minkowski_kernel_program_v1",
        fallback=bool(operation_record.get("fallback", False)),
        face_operation_attributed=bool(face_operation_ids),
        extra={
            "minkowski_execution_method": "convex_vertex_sum_hull",
            "exact_kernel_path": False,
            "approximation": "convex_vertex_sum_hull",
            "pair_count": pair_count,
        },
    )
    if kernel_feature_detail:
        mesh.metadata["lathe_kernel_feature_detail"] = dict(kernel_feature_detail)
    details = {
        "kernel_program_version": KERNEL_PROGRAM_VERSION,
        "kernel_program_route": route,
        "kernel_program_operation_count": operation_count,
        "kernel_program_operand_count": 2,
        "kernel_program_semantic_operation_record_count": len(operand_records),
        "kernel_program_semantic_operation_counts": _operation_counts(operand_records),
        "kernel_program_semantic_operation_records": operand_records,
        "kernel_program_kernel": kernel.name,
        "kernel_program_backend": backend,
        "kernel_program_manifest": manifest,
        "kernel_program_capabilities_checked": ["hull", "to_trimesh"],
        "kernel_program_watertight": bool(mesh.is_watertight),
        "kernel_program_body_count": len(mesh.split(only_watertight=False)),
        "kernel_program_operands": [source.trace_record(), structuring.trace_record()],
        "kernel_program_operations": [operation_record],
        "kernel_program_face_operation_attribution": face_operation_attribution,
        "face_operation_ids": face_operation_ids,
        "face_operation_summary": face_operation_summary,
        "kernel_minkowski": kernel_minkowski,
        "kernel_program_minkowski": kernel_minkowski,
        "kernel_feature_detail": kernel_feature_detail,
        "kernel_program_feature_detail": kernel_feature_detail,
        "kernel_program_minkowski_source_operand_id": source.operand_id,
        "kernel_program_minkowski_structuring_operand_id": structuring.operand_id,
        "minkowski_execution_method": "convex_vertex_sum_hull",
        "minkowski_exact": False,
        "minkowski_approximation": "convex_vertex_sum_hull",
        "minkowski_pair_count": pair_count,
        "minkowski_sample_stride": stride,
        "minkowski_sample_count": len(points),
        "minkowski_kernel_import_succeeded": import_succeeded,
        "minkowski_finalized_by_kernel": finalized_by_kernel,
    }
    if exact_box_failure:
        details["minkowski_exact_path_failure"] = exact_box_failure
    if kernel_failure:
        details["minkowski_kernel_finalize_failure"] = kernel_failure
    semantic_handoff = _attach_kernel_program_semantic_handoff(
        mesh,
        [source, structuring],
        [operation_record],
    )
    details["kernel_program_semantic_handoff"] = semantic_handoff
    return KernelProgramResult(
        mesh=mesh,
        handle=current,
        operation_count=operation_count,
        details=details,
    )


def execute_transform_program(
    kernel: GeometryKernel,
    source: KernelOperand,
    *,
    matrix: list[list[float]],
    operation_limit: int | None = None,
    route: str = "transform_program",
    backend: str | None = None,
) -> KernelProgramResult:
    """Execute a transform against one already-imported kernel operand."""
    transform_matrix = _validated_transform_matrix(matrix)
    _validate_transform_operand(source)
    operation_count = transform_operation_count(source)
    if operation_limit is not None and operation_count > operation_limit:
        raise ValueError(
            f"kernel transform operation_count={operation_count} exceeds limit={operation_limit}"
        )
    capabilities = _kernel_capabilities(kernel)
    _require_capabilities(kernel, capabilities, {"transform", "to_trimesh"})
    manifest = build_transform_program_manifest(
        source,
        matrix=transform_matrix,
        route=route,
        backend=backend,
        operation_limit=operation_limit,
    )

    transform = getattr(kernel, "transform", None)
    if not callable(transform):
        raise ValueError(f"geometry kernel {kernel.name!r} does not implement transform")
    current = transform(source.handle, transform_matrix)
    mesh = _non_empty_mesh(kernel, current)
    operation_records = _semantic_operation_records_from_manifest(manifest)
    operation_record = {
        "op": "transform",
        "source": source.operand_id,
        "attempted_kernel": kernel.name,
        "actual_kernel": kernel.name,
        "matrix": transform_matrix,
        "result_face_count": len(mesh.faces),
        "result_vertex_count": len(mesh.vertices),
        "result_watertight": bool(mesh.is_watertight),
        "result_body_count": kernel.body_count(current),
    }
    _record_result_probe(operation_record, kernel=kernel, result_handle=current)
    face_operation_id, final_operation_record = _final_semantic_operation_face_id(
        operation_records,
        "sop.transform",
        fallback=f"{source.operand_id}.transform",
    )
    if final_operation_record:
        operation_record["semantic_operation_record"] = dict(final_operation_record)
    (
        face_operation_ids,
        face_operation_summary,
        face_operation_attribution,
    ) = _attach_direct_face_operation_metadata(
        mesh,
        face_operation_id,
        source="kernel_program.transform.source_operand",
        method="transformed_source_face_ranges",
    )
    kernel_transform = _dict_metadata(operation_record.get("kernel_transform"))
    if not kernel_transform:
        kernel_transform = _dict_metadata(mesh.metadata.get("lathe_reference_transform"))
    semantic_handoff = _attach_kernel_program_semantic_handoff(
        mesh,
        [source],
        [operation_record],
    )
    details = {
        "kernel_program_version": KERNEL_PROGRAM_VERSION,
        "kernel_program_route": route,
        "kernel_program_operation_count": operation_count,
        "kernel_program_operand_count": 1,
        "kernel_program_semantic_operation_record_count": len(operation_records),
        "kernel_program_semantic_operation_counts": _operation_counts(operation_records),
        "kernel_program_semantic_operation_records": operation_records,
        "kernel_program_kernel": kernel.name,
        "kernel_program_backend": backend,
        "kernel_program_manifest": manifest,
        "kernel_program_capabilities_checked": ["transform", "to_trimesh"],
        "kernel_program_watertight": kernel.is_watertight(current),
        "kernel_program_body_count": kernel.body_count(current),
        "kernel_program_operands": [source.trace_record()],
        "kernel_program_operations": [operation_record],
        "kernel_program_face_operation_attribution": face_operation_attribution,
        "face_operation_ids": face_operation_ids,
        "face_operation_summary": face_operation_summary,
        "kernel_transform": kernel_transform,
        "kernel_program_transform": kernel_transform,
        "kernel_program_transform_source_operand_id": source.operand_id,
        "transform_matrix": transform_matrix,
        "kernel_program_semantic_handoff": semantic_handoff,
    }
    return KernelProgramResult(
        mesh=mesh,
        handle=current,
        operation_count=operation_count,
        details=details,
    )


def execute_deform_program(
    kernel: GeometryKernel,
    source: KernelOperand,
    *,
    deform_operation: str,
    axis: str = "y",
    angle_degrees: float | None = None,
    start_scale: float | None = None,
    end_scale: float | None = None,
    direction_axis: str | None = None,
    origin: list[float] | tuple[float, float, float] | None = None,
    subdivision_levels: int | None = None,
    segments: int | None = None,
    operation_limit: int | None = None,
    route: str = "deform_program",
    backend: str | None = None,
) -> KernelProgramResult:
    """Execute a vertex deformation through the typed KernelProgram seam."""
    operation = _validated_deform_operation(deform_operation)
    axis_name = _validated_deform_axis(axis)
    direction_name = (
        _validated_deform_axis(direction_axis, field="direction_axis")
        if direction_axis is not None
        else None
    )
    origin_cm = _validated_origin(origin)
    _validate_transform_operand(source)
    operation_count = deform_operation_count(source)
    if operation_limit is not None and operation_count > operation_limit:
        raise ValueError(
            f"kernel deform operation_count={operation_count} exceeds limit={operation_limit}"
        )
    capabilities = _kernel_capabilities(kernel)
    required = {"from_trimesh", "to_trimesh"}
    _require_capabilities(kernel, capabilities, required)
    manifest = build_deform_program_manifest(
        source,
        deform_operation=operation,
        axis=axis_name,
        angle_degrees=angle_degrees,
        start_scale=start_scale,
        end_scale=end_scale,
        direction_axis=direction_name,
        origin=origin_cm,
        subdivision_levels=subdivision_levels,
        segments=segments,
        route=route,
        backend=backend,
        operation_limit=operation_limit,
    )

    source_mesh = _non_empty_mesh(kernel, source.handle)
    exact_deform_params = _exact_extruded_profile_deform_params(
        source_mesh,
        operation=operation,
        axis=axis_name,
        angle_degrees=angle_degrees,
        start_scale=start_scale,
        end_scale=end_scale,
        origin=origin_cm,
        segments=segments,
        subdivision_levels=subdivision_levels,
    )
    if exact_deform_params is None:
        exact_deform_params = _round_primitive_deform_params(
            source_mesh,
            operation=operation,
            axis=axis_name,
            angle_degrees=angle_degrees,
            start_scale=start_scale,
            end_scale=end_scale,
            direction_axis=direction_name,
            origin=origin_cm,
            segments=segments,
            subdivision_levels=subdivision_levels,
    )
    exact_deform_failure = ""
    if exact_deform_params is not None:
        exact_required = _exact_rebuild_required_capabilities(exact_deform_params)
        exact_checked_capabilities = _required_capability_list(
            sorted(required),
            exact_required,
        )
        if exact_required and all(capabilities.get(name) is True for name in exact_required):
            try:
                current = kernel.build_primitive(
                    str(exact_deform_params["primitive_type"]),
                    **dict(exact_deform_params["build_params"]),
                )
                mesh = _non_empty_mesh(kernel, current)
                source_profile = dict(exact_deform_params.get("source_profile") or {})
                source_center = source_profile.get("center") or (0.0, 0.0, 0.0)
                source_primitive_type = str(
                    source_profile.get("primitive_type")
                    or exact_deform_params.get("source_primitive_type")
                    or "unknown"
                )
                result_primitive_type = str(
                    exact_deform_params.get("result_primitive_type")
                    or exact_deform_params["primitive_type"]
                )
                deform_exact = bool(exact_deform_params.get("exact", True))
                deform_approximation = exact_deform_params.get("approximation")
                exact_metadata = {
                    "schema": "lathe.geometry.kernel_deform.v1",
                    "method": str(exact_deform_params["method"]),
                    "operation": operation,
                    "axis": axis_name,
                    "origin_cm": [
                        float(value)
                        for value in (
                            origin_cm
                            if origin_cm is not None
                            else source_center
                        )
                    ],
                    "attempted_backend": f"{kernel.name}.build_primitive",
                    "actual_backend": f"{kernel.name}.build_primitive",
                    "attempted_kernel": kernel.name,
                    "actual_kernel": kernel.name,
                    "actual_operation": operation,
                    "kernel_rebuild_path": True,
                    "exact_kernel_path": deform_exact,
                    "deform_exact": deform_exact,
                    "fallback": False,
                    "passthrough": False,
                    "source_primitive_type": source_primitive_type,
                    "result_primitive_type": result_primitive_type,
                    "source_face_count": len(source_mesh.faces),
                    "source_vertex_count": len(source_mesh.vertices),
                    "result_face_count": len(mesh.faces),
                    "result_vertex_count": len(mesh.vertices),
                    "result_watertight": bool(mesh.is_watertight),
                    "result_body_count": kernel.body_count(current),
                }
                for key in ("result_profile_point_count", "result_segments"):
                    if exact_deform_params.get(key) is not None:
                        exact_metadata[key] = int(exact_deform_params[key])
                for key in (
                    "result_radius",
                    "result_start_radius",
                    "result_end_radius",
                    "result_height",
                    "result_length",
                    "result_tube_radius",
                    "result_angle_degrees",
                    "result_start_angle_degrees",
                    "result_start_scale",
                    "result_end_scale",
                    "result_twist_degrees",
                ):
                    if exact_deform_params.get(key) is not None:
                        exact_metadata[key] = float(exact_deform_params[key])
                for key in ("result_axis", "result_direction_axis", "result_plane_axis"):
                    if exact_deform_params.get(key) is not None:
                        exact_metadata[key] = str(exact_deform_params[key])
                if deform_approximation is not None:
                    exact_metadata["deform_approximation"] = str(deform_approximation)
                if angle_degrees is not None:
                    exact_metadata["angle_degrees"] = float(angle_degrees)
                if start_scale is not None:
                    exact_metadata["start_scale"] = float(start_scale)
                if end_scale is not None:
                    exact_metadata["end_scale"] = float(end_scale)
                mesh.metadata["lathe_kernel_deform"] = dict(exact_metadata)
                operation_records = _semantic_operation_records_from_manifest(manifest)
                operation_record = {
                    "op": "deform",
                    "source": source.operand_id,
                    "attempted_kernel": kernel.name,
                    "actual_kernel": kernel.name,
                    "attempted_backend": f"{kernel.name}.build_primitive",
                    "actual_backend": f"{kernel.name}.build_primitive",
                    "semantic_operation": operation,
                    "deform_operation": operation,
                    "axis": axis_name,
                    "direction_axis": direction_name,
                    "angle_degrees": exact_metadata.get("angle_degrees"),
                    "start_scale": exact_metadata.get("start_scale"),
                    "end_scale": exact_metadata.get("end_scale"),
                    "origin_cm": exact_metadata["origin_cm"],
                    "result_face_count": len(mesh.faces),
                    "result_vertex_count": len(mesh.vertices),
                    "result_watertight": bool(mesh.is_watertight),
                    "result_body_count": kernel.body_count(current),
                    "kernel_rebuild_path": True,
                    "exact_kernel_path": deform_exact,
                    "deform_exact": deform_exact,
                    "kernel_deform": dict(exact_metadata),
                }
                if deform_approximation is not None:
                    operation_record["deform_approximation"] = str(deform_approximation)
                for key in (
                    "result_primitive_type",
                    "result_axis",
                    "result_radius",
                    "result_start_radius",
                    "result_end_radius",
                    "result_height",
                    "result_length",
                    "result_tube_radius",
                    "result_angle_degrees",
                    "result_start_angle_degrees",
                    "result_profile_point_count",
                    "result_segments",
                    "result_direction_axis",
                    "result_plane_axis",
                ):
                    if key in exact_metadata:
                        operation_record[key] = exact_metadata[key]
                face_operation_id, final_operation_record = _final_semantic_operation_face_id(
                    operation_records,
                    operation,
                    fallback=f"{source.operand_id}.{_operation_id_fragment(operation)}",
                )
                if final_operation_record:
                    operation_record["semantic_operation_record"] = dict(final_operation_record)
                _record_result_probe(operation_record, kernel=kernel, result_handle=current)
                (
                    face_operation_ids,
                    face_operation_summary,
                    face_operation_attribution,
                ) = _attach_direct_face_operation_metadata(
                    mesh,
                    face_operation_id,
                    source=f"kernel_program.deform.{result_primitive_type}_rebuild",
                    method=f"{exact_deform_params['method']}_face_ranges",
                )
                semantic_handoff = _attach_kernel_program_semantic_handoff(
                    mesh,
                    [source],
                    [operation_record],
                )
                deform_detail_payload: dict[str, Any] = {
                    "deform_exact": deform_exact,
                    "deform_exact_method": str(exact_deform_params["method"]),
                    "deform_result_primitive_type": result_primitive_type,
                }
                if deform_approximation is not None:
                    deform_detail_payload["deform_approximation"] = str(deform_approximation)
                for metadata_key, detail_key in (
                    ("result_axis", "deform_result_axis"),
                    ("result_radius", "deform_result_radius"),
                    ("result_start_radius", "deform_result_start_radius"),
                    ("result_end_radius", "deform_result_end_radius"),
                    ("result_height", "deform_result_height"),
                    ("result_length", "deform_result_length"),
                    ("result_tube_radius", "deform_result_tube_radius"),
                    ("result_angle_degrees", "deform_result_angle_degrees"),
                    ("result_start_angle_degrees", "deform_result_start_angle_degrees"),
                    ("result_direction_axis", "deform_result_direction_axis"),
                    ("result_plane_axis", "deform_result_plane_axis"),
                    ("result_profile_point_count", "deform_result_profile_point_count"),
                    ("result_segments", "deform_result_segments"),
                ):
                    if metadata_key in exact_metadata:
                        deform_detail_payload[detail_key] = exact_metadata[metadata_key]
                return KernelProgramResult(
                    mesh=mesh,
                    handle=current,
                    operation_count=operation_count,
                    details={
                        "kernel_program_version": KERNEL_PROGRAM_VERSION,
                        "kernel_program_route": route,
                        "kernel_program_operation_count": operation_count,
                        "kernel_program_operand_count": 1,
                        "kernel_program_semantic_operation_record_count": len(operation_records),
                        "kernel_program_semantic_operation_counts": _operation_counts(operation_records),
                        "kernel_program_semantic_operation_records": operation_records,
                        "kernel_program_kernel": kernel.name,
                        "kernel_program_backend": backend,
                        "kernel_program_manifest": {
                            **manifest,
                            "required_capabilities": exact_checked_capabilities,
                            "kernel_rebuild_path": True,
                            "exact_kernel_path": deform_exact,
                            "exact_deform_method": str(exact_deform_params["method"]),
                            **(
                                {"deform_approximation": str(deform_approximation)}
                                if deform_approximation is not None
                                else {}
                            ),
                        },
                        "kernel_program_capabilities_checked": exact_checked_capabilities,
                        "kernel_program_watertight": bool(mesh.is_watertight),
                        "kernel_program_body_count": kernel.body_count(current),
                        "kernel_program_operands": [source.trace_record()],
                        "kernel_program_operations": [operation_record],
                        "kernel_program_face_operation_attribution": face_operation_attribution,
                        "face_operation_ids": face_operation_ids,
                        "face_operation_summary": face_operation_summary,
                        "kernel_program_deform_source_operand_id": source.operand_id,
                        "deform_operation": operation,
                        "deform_axis": axis_name,
                        "deform_direction_axis": direction_name,
                        "deform_angle_degrees": exact_metadata.get("angle_degrees"),
                        "deform_start_scale": exact_metadata.get("start_scale"),
                        "deform_end_scale": exact_metadata.get("end_scale"),
                        "deform_origin_cm": exact_metadata["origin_cm"],
                        "deform_source_face_count": len(source_mesh.faces),
                        "deform_source_vertex_count": len(source_mesh.vertices),
                        "deform_result_face_count": len(mesh.faces),
                        "deform_result_vertex_count": len(mesh.vertices),
                        "deform_result_watertight": bool(mesh.is_watertight),
                        **deform_detail_payload,
                        "kernel_deform": exact_metadata,
                        "kernel_program_deform": exact_metadata,
                        "kernel_program_semantic_handoff": semantic_handoff,
                    },
                )
            except (AttributeError, TypeError, ValueError, RuntimeError, OSError) as exc:
                exact_deform_failure = f"{type(exc).__name__}: {exc}"

    working_mesh, subdivision_details = _subdivided_deform_mesh(
        source_mesh,
        axis=axis_name,
        subdivision_levels=subdivision_levels,
        segments=segments,
    )
    origin_vector = _mesh_origin(working_mesh, origin_cm)
    vertices = np.asarray(working_mesh.vertices, dtype=np.float64).copy()
    axis_index = _axis_index(axis_name)
    axis_min, _, span = _axis_span(vertices, axis_index)
    first, second = _perpendicular_axis_indices(axis_name)
    relative = vertices - origin_vector

    operation_payload: dict[str, Any] = {
        "schema": "lathe.geometry.kernel_deform.v1",
        "method": "kernel_program_mesh_deform_v1",
        "operation": operation,
        "axis": axis_name,
        "origin_cm": [float(value) for value in origin_vector.tolist()],
        "span_cm": float(span),
        "attempted_backend": kernel.name,
        "actual_backend": kernel.name,
        "attempted_kernel": kernel.name,
        "actual_kernel": kernel.name,
        "actual_operation": operation,
        "fallback": False,
        "passthrough": False,
        **subdivision_details,
    }
    if exact_deform_params is not None:
        operation_payload["exact_deform_path_available"] = True
        operation_payload["exact_deform_path_method"] = str(exact_deform_params["method"])
        operation_payload["exact_deform_required_capabilities"] = list(exact_required)
        if exact_deform_failure:
            operation_payload["exact_deform_path_failed"] = exact_deform_failure
            operation_payload["exact_kernel_path_fallback"] = True
        elif not all(capabilities.get(str(name)) is True for name in exact_required):
            operation_payload["exact_deform_path_skipped"] = (
                "kernel_did_not_advertise_required_capability"
            )
    if operation == "sop.twist":
        angle = _finite_float(angle_degrees, field="angle_degrees")
        angles = math.radians(angle) * (relative[:, axis_index] / span)
        cos_values = np.cos(angles)
        sin_values = np.sin(angles)
        first_values = relative[:, first].copy()
        second_values = relative[:, second].copy()
        vertices[:, first] = origin_vector[first] + first_values * cos_values - second_values * sin_values
        vertices[:, second] = origin_vector[second] + first_values * sin_values + second_values * cos_values
        operation_payload["angle_degrees"] = float(angle)
    elif operation == "sop.taper":
        start = _finite_float(1.0 if start_scale is None else start_scale, field="start_scale")
        end = _finite_float(end_scale, field="end_scale")
        if start <= 0.0 or end <= 0.0:
            raise ValueError("kernel deform taper scale values must be > 0")
        t = (vertices[:, axis_index] - axis_min) / span
        scale = start + (end - start) * t
        vertices[:, first] = origin_vector[first] + (vertices[:, first] - origin_vector[first]) * scale
        vertices[:, second] = origin_vector[second] + (vertices[:, second] - origin_vector[second]) * scale
        operation_payload["start_scale"] = float(start)
        operation_payload["end_scale"] = float(end)
    elif operation == "sop.bend":
        angle = _finite_float(angle_degrees, field="angle_degrees")
        if direction_name is None:
            direction_name = _axis_name_from_index(first)
        if direction_name == axis_name:
            raise ValueError("kernel deform bend direction_axis must differ from axis")
        direction_index = _axis_index(direction_name)
        angle_radians = math.radians(angle)
        if abs(angle_radians) > 1e-9:
            radius = span / abs(angle_radians)
            relative_axis = vertices[:, axis_index] - origin_vector[axis_index]
            relative_direction = vertices[:, direction_index] - origin_vector[direction_index]
            theta = (relative_axis / span) * angle_radians
            vertices[:, axis_index] = origin_vector[axis_index] + np.sin(theta) * radius
            vertices[:, direction_index] = (
                origin_vector[direction_index]
                + (np.cos(theta) - 1.0) * radius
                + relative_direction * np.cos(theta)
            )
        operation_payload["angle_degrees"] = float(angle)
        operation_payload["direction_axis"] = direction_name

    deformed = _mesh_with_vertices(working_mesh, vertices)
    operation_payload.update(
        {
            "source_face_count": len(source_mesh.faces),
            "source_vertex_count": len(source_mesh.vertices),
            "deform_input_face_count": len(working_mesh.faces),
            "deform_input_vertex_count": len(working_mesh.vertices),
            "result_face_count": len(deformed.faces),
            "result_vertex_count": len(deformed.vertices),
            "result_watertight": bool(deformed.is_watertight),
            "result_body_count": len(deformed.split(only_watertight=False)),
        }
    )
    deformed.metadata["lathe_kernel_deform"] = dict(operation_payload)
    current = kernel.from_trimesh(deformed)
    mesh = _non_empty_mesh(kernel, current)
    mesh.metadata["lathe_kernel_deform"] = dict(operation_payload)
    operation_records = _semantic_operation_records_from_manifest(manifest)
    operation_record = {
        "op": "deform",
        "source": source.operand_id,
        "attempted_kernel": kernel.name,
        "actual_kernel": kernel.name,
        "semantic_operation": operation,
        "deform_operation": operation,
        "axis": axis_name,
        "direction_axis": direction_name,
        "angle_degrees": operation_payload.get("angle_degrees"),
        "start_scale": operation_payload.get("start_scale"),
        "end_scale": operation_payload.get("end_scale"),
        "origin_cm": operation_payload["origin_cm"],
        "span_cm": operation_payload["span_cm"],
        "result_face_count": len(mesh.faces),
        "result_vertex_count": len(mesh.vertices),
        "result_watertight": bool(mesh.is_watertight),
        "result_body_count": kernel.body_count(current),
        "kernel_deform": dict(operation_payload),
    }
    face_operation_id, final_operation_record = _final_semantic_operation_face_id(
        operation_records,
        operation,
        fallback=f"{source.operand_id}.{_operation_id_fragment(operation)}",
    )
    if final_operation_record:
        operation_record["semantic_operation_record"] = dict(final_operation_record)
    _record_result_probe(operation_record, kernel=kernel, result_handle=current)
    (
        face_operation_ids,
        face_operation_summary,
        face_operation_attribution,
    ) = _attach_direct_face_operation_metadata(
        mesh,
        face_operation_id,
        source="kernel_program.deform.source_operand",
        method="deformed_source_face_ranges",
    )
    semantic_handoff = _attach_kernel_program_semantic_handoff(
        mesh,
        [source],
        [operation_record],
    )
    details = {
        "kernel_program_version": KERNEL_PROGRAM_VERSION,
        "kernel_program_route": route,
        "kernel_program_operation_count": operation_count,
        "kernel_program_operand_count": 1,
        "kernel_program_semantic_operation_record_count": len(operation_records),
        "kernel_program_semantic_operation_counts": _operation_counts(operation_records),
        "kernel_program_semantic_operation_records": operation_records,
        "kernel_program_kernel": kernel.name,
        "kernel_program_backend": backend,
        "kernel_program_manifest": manifest,
        "kernel_program_capabilities_checked": sorted(required),
        "kernel_program_watertight": kernel.is_watertight(current),
        "kernel_program_body_count": kernel.body_count(current),
        "kernel_program_operands": [source.trace_record()],
        "kernel_program_operations": [operation_record],
        "kernel_program_face_operation_attribution": face_operation_attribution,
        "face_operation_ids": face_operation_ids,
        "face_operation_summary": face_operation_summary,
        "kernel_program_deform_source_operand_id": source.operand_id,
        "deform_operation": operation,
        "deform_axis": axis_name,
        "deform_direction_axis": direction_name,
        "deform_angle_degrees": operation_payload.get("angle_degrees"),
        "deform_start_scale": operation_payload.get("start_scale"),
        "deform_end_scale": operation_payload.get("end_scale"),
        "deform_origin_cm": operation_payload["origin_cm"],
        "deform_span_cm": operation_payload["span_cm"],
        "deform_source_face_count": len(source_mesh.faces),
        "deform_source_vertex_count": len(source_mesh.vertices),
        "deform_input_face_count": len(working_mesh.faces),
        "deform_input_vertex_count": len(working_mesh.vertices),
        "deform_result_face_count": len(mesh.faces),
        "deform_result_vertex_count": len(mesh.vertices),
        "deform_result_watertight": bool(mesh.is_watertight),
        "kernel_deform": operation_payload,
        "kernel_program_deform": operation_payload,
        **subdivision_details,
        "kernel_program_semantic_handoff": semantic_handoff,
    }
    return KernelProgramResult(
        mesh=mesh,
        handle=current,
        operation_count=operation_count,
        details=details,
    )


def execute_refine_program(
    kernel: GeometryKernel,
    source: KernelOperand,
    *,
    refine_operation: str,
    levels: int | None = None,
    scheme: str | None = None,
    target_edge_length_cm: float | None = None,
    mode: str = "adaptive",
    max_iterations: int = 6,
    operation_limit: int | None = None,
    route: str = "refine_program",
    backend: str | None = None,
) -> KernelProgramResult:
    """Execute subdivision/remesh refinement through the typed KernelProgram seam."""
    operation = _validated_refine_operation(refine_operation)
    _validate_transform_operand(source)
    operation_count = refine_operation_count(source)
    if operation_limit is not None and operation_count > operation_limit:
        raise ValueError(
            f"kernel refine operation_count={operation_count} exceeds limit={operation_limit}"
        )
    capabilities = _kernel_capabilities(kernel)
    required = {"from_trimesh", "to_trimesh"}
    _require_capabilities(kernel, capabilities, required)
    source_mesh = _non_empty_mesh(kernel, source.handle)
    if len(source_mesh.vertices) == 0 or len(source_mesh.faces) == 0:
        raise ValueError("kernel refine source produced an empty mesh")

    if operation == "sop.subdivide":
        refine_levels = 0 if levels is None else int(levels)
        if refine_levels < 0:
            raise ValueError("kernel refine subdivision levels must be >= 0")
        if refine_levels > 5:
            raise ValueError("kernel refine subdivision levels must be <= 5")
        requested_scheme = str(scheme or "catmull_clark")
        if not requested_scheme:
            raise ValueError("kernel refine subdivision scheme must be non-empty")
        actual_method = "trimesh_midpoint_subdivide_v1" if refine_levels > 0 else "identity_noop_v1"
        result_mesh = _subdivide_mesh(source_mesh, levels=refine_levels)
        refine_payload: dict[str, Any] = {
            "levels": refine_levels,
            "requested_scheme": requested_scheme,
            "actual_scheme": "linear_midpoint" if refine_levels > 0 else "identity",
            "method": actual_method,
            "actual_method": actual_method,
            "actual_geometry_backend": (
                "trimesh.remesh.subdivide" if refine_levels > 0 else "identity"
            ),
        }
    else:
        target_edge = _finite_float(target_edge_length_cm, field="target_edge_length_cm")
        if target_edge <= 0.0:
            raise ValueError("kernel refine target_edge_length_cm must be > 0")
        normalized_mode = _normalize_refine_mode(mode)
        iterations = int(max_iterations)
        if iterations < 0:
            raise ValueError("kernel refine max_iterations must be >= 0")
        iterations = min(iterations, 12)
        result_mesh = _remesh_to_edge_length(
            source_mesh,
            target_edge_length_cm=target_edge,
            mode=normalized_mode,
            max_iterations=iterations,
        )
        refine_payload = {
            "target_edge_length_cm": target_edge,
            "requested_mode": normalized_mode,
            "method": "iterative_midpoint_edge_refine_v1",
            "actual_method": "iterative_midpoint_edge_refine_v1",
            "actual_geometry_backend": "trimesh.remesh.subdivide",
            "max_iterations": iterations,
            **({"smoothing": "laplacian_v1"} if normalized_mode == "smooth" else {}),
        }

    manifest = build_refine_program_manifest(
        source,
        refine_operation=operation,
        levels=refine_payload.get("levels"),
        scheme=refine_payload.get("requested_scheme"),
        target_edge_length_cm=refine_payload.get("target_edge_length_cm"),
        mode=refine_payload.get("requested_mode"),
        max_iterations=refine_payload.get("max_iterations"),
        route=route,
        backend=backend,
        operation_limit=operation_limit,
    )
    refine_metadata = {
        "schema": "lathe.geometry.kernel_refine.v1",
        "method": "kernel_program_mesh_refine_v1",
        "operation": operation,
        "attempted_backend": kernel.name,
        "actual_backend": kernel.name,
        "attempted_kernel": kernel.name,
        "actual_kernel": kernel.name,
        "actual_operation": operation,
        "fallback": False,
        "passthrough": False,
        "source_face_count": len(source_mesh.faces),
        "source_vertex_count": len(source_mesh.vertices),
        "result_face_count": len(result_mesh.faces),
        "result_vertex_count": len(result_mesh.vertices),
        "result_watertight": bool(result_mesh.is_watertight),
        "result_body_count": len(result_mesh.split(only_watertight=False)),
        **refine_payload,
    }
    result_mesh.metadata["lathe_kernel_refine"] = dict(refine_metadata)
    current = kernel.from_trimesh(result_mesh)
    mesh = _non_empty_mesh(kernel, current)
    mesh.metadata["lathe_kernel_refine"] = dict(refine_metadata)
    operation_records = _semantic_operation_records_from_manifest(manifest)
    operation_record = {
        "op": "refine",
        "source": source.operand_id,
        "attempted_kernel": kernel.name,
        "actual_kernel": kernel.name,
        "semantic_operation": operation,
        "refine_operation": operation,
        "result_face_count": len(mesh.faces),
        "result_vertex_count": len(mesh.vertices),
        "result_watertight": bool(mesh.is_watertight),
        "result_body_count": kernel.body_count(current),
        "kernel_refine": dict(refine_metadata),
    }
    face_operation_id, final_operation_record = _final_semantic_operation_face_id(
        operation_records,
        operation,
        fallback=f"{source.operand_id}.{_operation_id_fragment(operation)}",
    )
    if final_operation_record:
        operation_record["semantic_operation_record"] = dict(final_operation_record)
    _record_result_probe(operation_record, kernel=kernel, result_handle=current)
    (
        face_operation_ids,
        face_operation_summary,
        face_operation_attribution,
    ) = _attach_direct_face_operation_metadata(
        mesh,
        face_operation_id,
        source="kernel_program.refine.source_operand",
        method="refined_source_face_ranges",
    )
    kernel_feature_detail = _kernel_feature_detail_metadata(
        kernel,
        mesh,
        current,
        [source],
        semantic_operation=operation,
        method_suffix="refine_kernel_program_v1",
        fallback=False,
        face_operation_attributed=bool(face_operation_ids),
        extra={
            "refine_operation": operation,
            "actual_method": str(refine_payload.get("actual_method") or ""),
            "actual_geometry_backend": str(
                refine_payload.get("actual_geometry_backend") or ""
            ),
            "source_face_count": len(source_mesh.faces),
            "source_vertex_count": len(source_mesh.vertices),
            "result_face_count": len(mesh.faces),
            "result_vertex_count": len(mesh.vertices),
        },
    )
    if kernel_feature_detail:
        mesh.metadata["lathe_kernel_feature_detail"] = dict(kernel_feature_detail)
    semantic_handoff = _attach_kernel_program_semantic_handoff(
        mesh,
        [source],
        [operation_record],
    )
    details = {
        "kernel_program_version": KERNEL_PROGRAM_VERSION,
        "kernel_program_route": route,
        "kernel_program_operation_count": operation_count,
        "kernel_program_operand_count": 1,
        "kernel_program_semantic_operation_record_count": len(operation_records),
        "kernel_program_semantic_operation_counts": _operation_counts(operation_records),
        "kernel_program_semantic_operation_records": operation_records,
        "kernel_program_kernel": kernel.name,
        "kernel_program_backend": backend,
        "kernel_program_manifest": manifest,
        "kernel_program_capabilities_checked": sorted(required),
        "kernel_program_watertight": kernel.is_watertight(current),
        "kernel_program_body_count": kernel.body_count(current),
        "kernel_program_operands": [source.trace_record()],
        "kernel_program_operations": [operation_record],
        "kernel_program_face_operation_attribution": face_operation_attribution,
        "face_operation_ids": face_operation_ids,
        "face_operation_summary": face_operation_summary,
        "kernel_feature_detail": kernel_feature_detail,
        "kernel_program_feature_detail": kernel_feature_detail,
        "kernel_program_refine_source_operand_id": source.operand_id,
        "refine_operation": operation,
        "refine_source_face_count": len(source_mesh.faces),
        "refine_source_vertex_count": len(source_mesh.vertices),
        "refine_result_face_count": len(mesh.faces),
        "refine_result_vertex_count": len(mesh.vertices),
        "refine_result_watertight": bool(mesh.is_watertight),
        "kernel_refine": refine_metadata,
        "kernel_program_refine": refine_metadata,
        **refine_payload,
        "kernel_program_semantic_handoff": semantic_handoff,
    }
    return KernelProgramResult(
        mesh=mesh,
        handle=current,
        operation_count=operation_count,
        details=details,
    )


def execute_carve_program(
    kernel: GeometryKernel,
    source: KernelOperand,
    *,
    u_start: float,
    u_end: float,
    axis: str = "z",
    operation_limit: int | None = None,
    route: str = "carve_program",
    backend: str | None = None,
) -> KernelProgramResult:
    """Execute an axis-bounded carve through the typed KernelProgram seam."""
    start = _finite_float(u_start, field="u_start")
    end = _finite_float(u_end, field="u_end")
    if not 0.0 <= start < end <= 1.0:
        raise ValueError("kernel carve u_start/u_end must satisfy 0 <= start < end <= 1")
    axis_name = _validated_deform_axis(axis)
    _validate_transform_operand(source)
    operation_count = carve_operation_count(source)
    if operation_limit is not None and operation_count > operation_limit:
        raise ValueError(
            f"kernel carve operation_count={operation_count} exceeds limit={operation_limit}"
        )
    capabilities = _kernel_capabilities(kernel)
    required = {"from_trimesh", "to_trimesh"}
    _require_capabilities(kernel, capabilities, required)
    manifest = build_carve_program_manifest(
        source,
        u_start=start,
        u_end=end,
        axis=axis_name,
        route=route,
        backend=backend,
        operation_limit=operation_limit,
    )
    source_mesh = _non_empty_mesh(kernel, source.handle)
    exact_carve_params = _exact_primitive_carve_params(
        source_mesh,
        axis=axis_name,
        u_start=start,
        u_end=end,
    )
    exact_carve_failure = ""
    if exact_carve_params is not None:
        exact_required = _exact_rebuild_required_capabilities(exact_carve_params)
        exact_checked_capabilities = _required_capability_list(
            sorted(required),
            exact_required,
        )
        if exact_required and all(capabilities.get(name) is True for name in exact_required):
            try:
                current = kernel.build_primitive(
                    str(exact_carve_params["primitive_type"]),
                    **dict(exact_carve_params["build_params"]),
                )
                mesh = _non_empty_mesh(kernel, current)
                carve_metadata = {
                    "schema": "lathe.geometry.kernel_carve.v1",
                    "operation": "sop.carve",
                    "method": str(exact_carve_params["method"]),
                    "axis": axis_name,
                    "u_start": start,
                    "u_end": end,
                    "attempted_backend": f"{kernel.name}.build_primitive",
                    "actual_backend": f"{kernel.name}.build_primitive",
                    "attempted_kernel": kernel.name,
                    "actual_kernel": kernel.name,
                    "actual_operation": "sop.carve",
                    "exact_kernel_path": True,
                    "fallback": False,
                    "passthrough": False,
                    "source_primitive_type": str(exact_carve_params["source_primitive_type"]),
                    "result_primitive_type": str(exact_carve_params["result_primitive_type"]),
                    "source_face_count": len(source_mesh.faces),
                    "source_vertex_count": len(source_mesh.vertices),
                    "result_face_count": len(mesh.faces),
                    "result_vertex_count": len(mesh.vertices),
                    "result_watertight": bool(mesh.is_watertight),
                    "result_body_count": kernel.body_count(current),
                }
                for key in (
                    "source_min_cm",
                    "source_max_cm",
                    "source_span_cm",
                    "carved_min_cm",
                    "carved_max_cm",
                    "carved_span_cm",
                    "result_radius",
                    "result_height",
                    "result_start_scale",
                    "result_end_scale",
                ):
                    if exact_carve_params.get(key) is not None:
                        carve_metadata[key] = float(exact_carve_params[key])
                if exact_carve_params.get("result_profile_point_count") is not None:
                    carve_metadata["result_profile_point_count"] = int(
                        exact_carve_params["result_profile_point_count"]
                    )
                if exact_carve_params.get("result_axis") is not None:
                    carve_metadata["result_axis"] = str(exact_carve_params["result_axis"])
                if exact_carve_params.get("result_extents") is not None:
                    carve_metadata["result_extents"] = [
                        float(value) for value in exact_carve_params["result_extents"]
                    ]
                mesh.metadata["lathe_kernel_carve"] = dict(carve_metadata)
                operation_records = _semantic_operation_records_from_manifest(manifest)
                operation_record = {
                    "op": "carve",
                    "source": source.operand_id,
                    "attempted_kernel": kernel.name,
                    "actual_kernel": kernel.name,
                    "attempted_backend": f"{kernel.name}.build_primitive",
                    "actual_backend": f"{kernel.name}.build_primitive",
                    "semantic_operation": "sop.carve",
                    "axis": axis_name,
                    "u_start": start,
                    "u_end": end,
                    "result_face_count": len(mesh.faces),
                    "result_vertex_count": len(mesh.vertices),
                    "result_watertight": bool(mesh.is_watertight),
                    "result_body_count": kernel.body_count(current),
                    "exact_kernel_path": True,
                    "kernel_carve": dict(carve_metadata),
                }
                for key in (
                    "result_primitive_type",
                    "result_axis",
                    "result_extents",
                    "result_radius",
                    "result_height",
                    "result_profile_point_count",
                    "result_start_scale",
                    "result_end_scale",
                ):
                    if key in carve_metadata:
                        operation_record[key] = carve_metadata[key]
                face_operation_id, final_operation_record = _final_semantic_operation_face_id(
                    operation_records,
                    "sop.carve",
                    fallback=f"{source.operand_id}.sop_carve",
                )
                if final_operation_record:
                    operation_record["semantic_operation_record"] = dict(final_operation_record)
                _record_result_probe(operation_record, kernel=kernel, result_handle=current)
                (
                    face_operation_ids,
                    face_operation_summary,
                    face_operation_attribution,
                ) = _attach_direct_face_operation_metadata(
                    mesh,
                    face_operation_id,
                    source=f"kernel_program.carve.{carve_metadata['result_primitive_type']}_rebuild",
                    method=f"{exact_carve_params['method']}_face_ranges",
                )
                semantic_handoff = _attach_kernel_program_semantic_handoff(
                    mesh,
                    [source],
                    [operation_record],
                )
                carve_detail_payload: dict[str, Any] = {
                    "carve_exact": True,
                    "carve_exact_method": str(exact_carve_params["method"]),
                    "carve_result_primitive_type": str(carve_metadata["result_primitive_type"]),
                }
                for metadata_key, detail_key in (
                    ("result_axis", "carve_result_axis"),
                    ("result_extents", "carve_result_extents"),
                    ("result_radius", "carve_result_radius"),
                    ("result_height", "carve_result_height"),
                    ("result_profile_point_count", "carve_result_profile_point_count"),
                    ("result_start_scale", "carve_result_start_scale"),
                    ("result_end_scale", "carve_result_end_scale"),
                ):
                    if metadata_key in carve_metadata:
                        carve_detail_payload[detail_key] = carve_metadata[metadata_key]
                return KernelProgramResult(
                    mesh=mesh,
                    handle=current,
                    operation_count=operation_count,
                    details={
                        "kernel_program_version": KERNEL_PROGRAM_VERSION,
                        "kernel_program_route": route,
                        "kernel_program_operation_count": operation_count,
                        "kernel_program_operand_count": 1,
                        "kernel_program_semantic_operation_record_count": len(operation_records),
                        "kernel_program_semantic_operation_counts": _operation_counts(operation_records),
                        "kernel_program_semantic_operation_records": operation_records,
                        "kernel_program_kernel": kernel.name,
                        "kernel_program_backend": backend,
                        "kernel_program_manifest": {
                            **manifest,
                            "required_capabilities": exact_checked_capabilities,
                            "exact_kernel_path": True,
                            "exact_carve_method": str(exact_carve_params["method"]),
                        },
                        "kernel_program_capabilities_checked": exact_checked_capabilities,
                        "kernel_program_watertight": bool(mesh.is_watertight),
                        "kernel_program_body_count": kernel.body_count(current),
                        "kernel_program_operands": [source.trace_record()],
                        "kernel_program_operations": [operation_record],
                        "kernel_program_face_operation_attribution": face_operation_attribution,
                        "face_operation_ids": face_operation_ids,
                        "face_operation_summary": face_operation_summary,
                        "kernel_program_carve_source_operand_id": source.operand_id,
                        "carve_axis": axis_name,
                        "carve_u_start": start,
                        "carve_u_end": end,
                        "carve_source_face_count": len(source_mesh.faces),
                        "carve_source_vertex_count": len(source_mesh.vertices),
                        "carve_result_face_count": len(mesh.faces),
                        "carve_result_vertex_count": len(mesh.vertices),
                        "carve_result_watertight": bool(mesh.is_watertight),
                        "kernel_carve": carve_metadata,
                        "kernel_program_carve": carve_metadata,
                        **{
                            key: carve_metadata[key]
                            for key in (
                                "source_min_cm",
                                "source_max_cm",
                                "source_span_cm",
                                "carved_min_cm",
                                "carved_max_cm",
                                "carved_span_cm",
                            )
                            if key in carve_metadata
                        },
                        **carve_detail_payload,
                        "kernel_program_semantic_handoff": semantic_handoff,
                    },
                )
            except (AttributeError, TypeError, ValueError, RuntimeError, OSError) as exc:
                exact_carve_failure = f"{type(exc).__name__}: {exc}"
    result_mesh, carve_details = _carved_axis_interval_mesh(
        source_mesh,
        axis=axis_name,
        u_start=start,
        u_end=end,
    )
    if exact_carve_params is not None:
        carve_details["exact_carve_path_available"] = True
        carve_details["exact_carve_path_method"] = str(exact_carve_params["method"])
        carve_details["exact_carve_required_capabilities"] = list(exact_required)
        if exact_carve_failure:
            carve_details["exact_carve_path_failed"] = exact_carve_failure
            carve_details["exact_kernel_path_fallback"] = True
        elif not all(capabilities.get(str(name)) is True for name in exact_required):
            carve_details["exact_carve_path_skipped"] = (
                "kernel_did_not_advertise_required_capability"
            )
    carve_metadata = {
        "schema": "lathe.geometry.kernel_carve.v1",
        "operation": "sop.carve",
        "axis": axis_name,
        "u_start": start,
        "u_end": end,
        "attempted_backend": kernel.name,
        "actual_backend": kernel.name,
        "attempted_kernel": kernel.name,
        "actual_kernel": kernel.name,
        "actual_operation": "sop.carve",
        "passthrough": False,
        "source_face_count": len(source_mesh.faces),
        "source_vertex_count": len(source_mesh.vertices),
        "result_face_count": len(result_mesh.faces),
        "result_vertex_count": len(result_mesh.vertices),
        "result_watertight": bool(result_mesh.is_watertight),
        "result_body_count": len(result_mesh.split(only_watertight=False)),
        **carve_details,
    }
    result_mesh.metadata["lathe_kernel_carve"] = dict(carve_metadata)
    current = kernel.from_trimesh(result_mesh)
    mesh = _non_empty_mesh(kernel, current)
    mesh.metadata["lathe_kernel_carve"] = dict(carve_metadata)
    operation_records = _semantic_operation_records_from_manifest(manifest)
    operation_record = {
        "op": "carve",
        "source": source.operand_id,
        "attempted_kernel": kernel.name,
        "actual_kernel": kernel.name,
        "semantic_operation": "sop.carve",
        "axis": axis_name,
        "u_start": start,
        "u_end": end,
        "result_face_count": len(mesh.faces),
        "result_vertex_count": len(mesh.vertices),
        "result_watertight": bool(mesh.is_watertight),
        "result_body_count": kernel.body_count(current),
        "kernel_carve": dict(carve_metadata),
    }
    face_operation_id, final_operation_record = _final_semantic_operation_face_id(
        operation_records,
        "sop.carve",
        fallback=f"{source.operand_id}.sop_carve",
    )
    if final_operation_record:
        operation_record["semantic_operation_record"] = dict(final_operation_record)
    _record_result_probe(operation_record, kernel=kernel, result_handle=current)
    (
        face_operation_ids,
        face_operation_summary,
        face_operation_attribution,
    ) = _attach_direct_face_operation_metadata(
        mesh,
        face_operation_id,
        source="kernel_program.carve.source_operand",
        method="carved_source_face_ranges",
    )
    semantic_handoff = _attach_kernel_program_semantic_handoff(
        mesh,
        [source],
        [operation_record],
    )
    details = {
        "kernel_program_version": KERNEL_PROGRAM_VERSION,
        "kernel_program_route": route,
        "kernel_program_operation_count": operation_count,
        "kernel_program_operand_count": 1,
        "kernel_program_semantic_operation_record_count": len(operation_records),
        "kernel_program_semantic_operation_counts": _operation_counts(operation_records),
        "kernel_program_semantic_operation_records": operation_records,
        "kernel_program_kernel": kernel.name,
        "kernel_program_backend": backend,
        "kernel_program_manifest": manifest,
        "kernel_program_capabilities_checked": sorted(required),
        "kernel_program_watertight": kernel.is_watertight(current),
        "kernel_program_body_count": kernel.body_count(current),
        "kernel_program_operands": [source.trace_record()],
        "kernel_program_operations": [operation_record],
        "kernel_program_face_operation_attribution": face_operation_attribution,
        "face_operation_ids": face_operation_ids,
        "face_operation_summary": face_operation_summary,
        "kernel_program_carve_source_operand_id": source.operand_id,
        "carve_axis": axis_name,
        "carve_u_start": start,
        "carve_u_end": end,
        "carve_source_face_count": len(source_mesh.faces),
        "carve_source_vertex_count": len(source_mesh.vertices),
        "carve_result_face_count": len(mesh.faces),
        "carve_result_vertex_count": len(mesh.vertices),
        "carve_result_watertight": bool(mesh.is_watertight),
        "kernel_carve": carve_metadata,
        "kernel_program_carve": carve_metadata,
        **carve_details,
        "kernel_program_semantic_handoff": semantic_handoff,
    }
    return KernelProgramResult(
        mesh=mesh,
        handle=current,
        operation_count=operation_count,
        details=details,
    )


def execute_polyextrude_program(
    kernel: GeometryKernel,
    source: KernelOperand,
    *,
    axis: str,
    distance_cm: float,
    semantic_operation: str = "sop.polyextrude",
    operation_limit: int | None = None,
    route: str = "polyextrude_program",
    backend: str | None = None,
) -> KernelProgramResult:
    """Execute source polyextrusion through the typed KernelProgram seam."""
    axis_name = _validated_deform_axis(axis)
    distance = _finite_float(distance_cm, field="distance_cm")
    _validate_transform_operand(source)
    operation_count = polyextrude_operation_count(source)
    if operation_limit is not None and operation_count > operation_limit:
        raise ValueError(
            f"kernel polyextrude operation_count={operation_count} exceeds limit={operation_limit}"
        )
    capabilities = _kernel_capabilities(kernel)
    required = {"from_trimesh", "to_trimesh"}
    _require_capabilities(kernel, capabilities, required)
    manifest = build_polyextrude_program_manifest(
        source,
        axis=axis_name,
        distance_cm=distance,
        semantic_operation=semantic_operation,
        route=route,
        backend=backend,
        operation_limit=operation_limit,
    )
    source_mesh = _non_empty_mesh(kernel, source.handle)
    exact_polyextrude_params = _exact_primitive_polyextrude_params(
        source_mesh,
        axis=axis_name,
        distance_cm=distance,
    )
    exact_polyextrude_failure = ""
    if exact_polyextrude_params is not None:
        exact_required = _exact_rebuild_required_capabilities(exact_polyextrude_params)
        exact_checked_capabilities = _required_capability_list(
            sorted(required),
            exact_required,
        )
        if exact_required and all(capabilities.get(name) is True for name in exact_required):
            try:
                current = kernel.build_primitive(
                    str(exact_polyextrude_params["primitive_type"]),
                    **dict(exact_polyextrude_params["build_params"]),
                )
                mesh = _non_empty_mesh(kernel, current)
                polyextrude_metadata = {
                    "schema": "lathe.geometry.kernel_polyextrude.v1",
                    "operation": semantic_operation,
                    "method": str(exact_polyextrude_params["method"]),
                    "axis": axis_name,
                    "distance_cm": distance,
                    "attempted_backend": f"{kernel.name}.build_primitive",
                    "actual_backend": f"{kernel.name}.build_primitive",
                    "attempted_kernel": kernel.name,
                    "actual_kernel": kernel.name,
                    "actual_operation": semantic_operation,
                    "exact_kernel_path": True,
                    "fallback": False,
                    "passthrough": False,
                    "source_primitive_type": str(exact_polyextrude_params["source_primitive_type"]),
                    "result_primitive_type": str(exact_polyextrude_params["result_primitive_type"]),
                    "source_face_count": len(source_mesh.faces),
                    "source_vertex_count": len(source_mesh.vertices),
                    "result_face_count": len(mesh.faces),
                    "result_vertex_count": len(mesh.vertices),
                    "result_watertight": bool(mesh.is_watertight),
                    "result_body_count": kernel.body_count(current),
                }
                for key in (
                    "source_min_cm",
                    "source_max_cm",
                    "source_extent_cm",
                    "result_min_cm",
                    "result_max_cm",
                    "result_extent_cm",
                    "result_radius",
                    "result_height",
                    "result_start_scale",
                    "result_end_scale",
                ):
                    if exact_polyextrude_params.get(key) is not None:
                        polyextrude_metadata[key] = float(exact_polyextrude_params[key])
                if exact_polyextrude_params.get("result_profile_point_count") is not None:
                    polyextrude_metadata["result_profile_point_count"] = int(
                        exact_polyextrude_params["result_profile_point_count"]
                    )
                if exact_polyextrude_params.get("result_axis") is not None:
                    polyextrude_metadata["result_axis"] = str(exact_polyextrude_params["result_axis"])
                if exact_polyextrude_params.get("result_extents") is not None:
                    polyextrude_metadata["result_extents"] = [
                        float(value) for value in exact_polyextrude_params["result_extents"]
                    ]
                if exact_polyextrude_params.get("side") is not None:
                    polyextrude_metadata["side"] = str(exact_polyextrude_params["side"])
                mesh.metadata["lathe_kernel_polyextrude"] = dict(polyextrude_metadata)
                operation_records = _semantic_operation_records_from_manifest(manifest)
                operation_record = {
                    "op": "polyextrude",
                    "source": source.operand_id,
                    "attempted_kernel": kernel.name,
                    "actual_kernel": kernel.name,
                    "attempted_backend": f"{kernel.name}.build_primitive",
                    "actual_backend": f"{kernel.name}.build_primitive",
                    "semantic_operation": semantic_operation,
                    "axis": axis_name,
                    "distance_cm": distance,
                    "result_face_count": len(mesh.faces),
                    "result_vertex_count": len(mesh.vertices),
                    "result_watertight": bool(mesh.is_watertight),
                    "result_body_count": kernel.body_count(current),
                    "exact_kernel_path": True,
                    "kernel_polyextrude": dict(polyextrude_metadata),
                }
                for key in (
                    "result_primitive_type",
                    "result_axis",
                    "result_extents",
                    "result_radius",
                    "result_height",
                    "result_profile_point_count",
                    "result_start_scale",
                    "result_end_scale",
                ):
                    if key in polyextrude_metadata:
                        operation_record[key] = polyextrude_metadata[key]
                _record_result_probe(operation_record, kernel=kernel, result_handle=current)
                final_operation_record = _final_semantic_operation_record(
                    operation_records,
                    semantic_operation,
                )
                face_operation_id = str(
                    final_operation_record.get("operation_id")
                    or f"{source.operand_id}.{_operation_id_fragment(semantic_operation)}"
                )
                (
                    face_operation_ids,
                    face_operation_summary,
                    face_operation_attribution,
                ) = _attach_direct_face_operation_metadata(
                    mesh,
                    face_operation_id,
                    source=f"kernel_program.polyextrude.{polyextrude_metadata['result_primitive_type']}_rebuild",
                    method=f"{exact_polyextrude_params['method']}_face_ranges",
                )
                kernel_feature_detail = _kernel_feature_detail_metadata(
                    kernel,
                    mesh,
                    current,
                    [source],
                    semantic_operation=semantic_operation,
                    method_suffix="polyextrude_kernel_program_v1",
                    fallback=False,
                    face_operation_attributed=bool(face_operation_ids),
                    extra={
                        "exact_kernel_path": True,
                        "polyextrude_axis": axis_name,
                        "polyextrude_distance_cm": distance,
                    },
                )
                if kernel_feature_detail:
                    mesh.metadata["lathe_kernel_feature_detail"] = dict(kernel_feature_detail)
                semantic_handoff = _attach_kernel_program_semantic_handoff(
                    mesh,
                    [source],
                    [operation_record],
                )
                polyextrude_detail_payload: dict[str, Any] = {
                    "polyextrude_exact": True,
                    "polyextrude_exact_method": str(exact_polyextrude_params["method"]),
                    "polyextrude_result_primitive_type": str(polyextrude_metadata["result_primitive_type"]),
                }
                for metadata_key, detail_key in (
                    ("result_axis", "polyextrude_result_axis"),
                    ("result_extents", "polyextrude_result_extents"),
                    ("result_radius", "polyextrude_result_radius"),
                    ("result_height", "polyextrude_result_height"),
                    ("result_profile_point_count", "polyextrude_result_profile_point_count"),
                    ("result_start_scale", "polyextrude_result_start_scale"),
                    ("result_end_scale", "polyextrude_result_end_scale"),
                    ("side", "polyextrude_side"),
                ):
                    if metadata_key in polyextrude_metadata:
                        polyextrude_detail_payload[detail_key] = polyextrude_metadata[metadata_key]
                return KernelProgramResult(
                    mesh=mesh,
                    handle=current,
                    operation_count=operation_count,
                    details={
                        "kernel_program_version": KERNEL_PROGRAM_VERSION,
                        "kernel_program_route": route,
                        "kernel_program_operation_count": operation_count,
                        "kernel_program_operand_count": 1,
                        "kernel_program_semantic_operation_record_count": len(operation_records),
                        "kernel_program_semantic_operation_counts": _operation_counts(operation_records),
                        "kernel_program_semantic_operation_records": operation_records,
                        "kernel_program_kernel": kernel.name,
                        "kernel_program_backend": backend,
                        "kernel_program_manifest": {
                            **manifest,
                            "required_capabilities": exact_checked_capabilities,
                            "exact_kernel_path": True,
                            "exact_polyextrude_method": str(exact_polyextrude_params["method"]),
                        },
                        "kernel_program_capabilities_checked": exact_checked_capabilities,
                        "kernel_program_watertight": bool(mesh.is_watertight),
                        "kernel_program_body_count": kernel.body_count(current),
                        "kernel_program_operands": [source.trace_record()],
                        "kernel_program_operations": [operation_record],
                        "kernel_program_face_operation_attribution": face_operation_attribution,
                        "face_operation_ids": face_operation_ids,
                        "face_operation_summary": face_operation_summary,
                        "kernel_feature_detail": kernel_feature_detail,
                        "kernel_program_feature_detail": kernel_feature_detail,
                        "kernel_program_polyextrude_source_operand_id": source.operand_id,
                        "polyextrude_axis": axis_name,
                        "polyextrude_distance_cm": distance,
                        "polyextrude_source_face_count": len(source_mesh.faces),
                        "polyextrude_source_vertex_count": len(source_mesh.vertices),
                        "polyextrude_result_face_count": len(mesh.faces),
                        "polyextrude_result_vertex_count": len(mesh.vertices),
                        "polyextrude_result_watertight": bool(mesh.is_watertight),
                        "kernel_polyextrude": polyextrude_metadata,
                        **{
                            key: polyextrude_metadata[key]
                            for key in (
                                "source_min_cm",
                                "source_max_cm",
                                "source_extent_cm",
                                "result_min_cm",
                                "result_max_cm",
                                "result_extent_cm",
                            )
                            if key in polyextrude_metadata
                        },
                        **polyextrude_detail_payload,
                        "kernel_program_semantic_handoff": semantic_handoff,
                    },
                )
            except (AttributeError, TypeError, ValueError, RuntimeError, OSError) as exc:
                exact_polyextrude_failure = f"{type(exc).__name__}: {exc}"
    result_mesh, polyextrude_details = _polyextruded_axis_mesh(
        source_mesh,
        axis=axis_name,
        distance_cm=distance,
    )
    if exact_polyextrude_params is not None:
        polyextrude_details["exact_polyextrude_path_available"] = True
        polyextrude_details["exact_polyextrude_path_method"] = str(exact_polyextrude_params["method"])
        polyextrude_details["exact_polyextrude_required_capabilities"] = list(exact_required)
        if exact_polyextrude_failure:
            polyextrude_details["exact_polyextrude_path_failed"] = exact_polyextrude_failure
            polyextrude_details["exact_kernel_path_fallback"] = True
        elif not all(capabilities.get(str(name)) is True for name in exact_required):
            polyextrude_details["exact_polyextrude_path_skipped"] = (
                "kernel_did_not_advertise_required_capability"
            )
    polyextrude_metadata = {
        "schema": "lathe.geometry.kernel_polyextrude.v1",
        "operation": semantic_operation,
        "axis": axis_name,
        "distance_cm": distance,
        "attempted_backend": kernel.name,
        "actual_backend": kernel.name,
        "attempted_kernel": kernel.name,
        "actual_kernel": kernel.name,
        "actual_operation": semantic_operation,
        "passthrough": abs(distance) <= 1e-9,
        "source_face_count": len(source_mesh.faces),
        "source_vertex_count": len(source_mesh.vertices),
        "result_face_count": len(result_mesh.faces),
        "result_vertex_count": len(result_mesh.vertices),
        "result_watertight": bool(result_mesh.is_watertight),
        "result_body_count": len(result_mesh.split(only_watertight=False)),
        **polyextrude_details,
    }
    result_mesh.metadata["lathe_kernel_polyextrude"] = dict(polyextrude_metadata)
    current = source.handle if abs(distance) <= 1e-9 else kernel.from_trimesh(result_mesh)
    mesh = result_mesh if abs(distance) <= 1e-9 else _non_empty_mesh(kernel, current)
    mesh.metadata["lathe_kernel_polyextrude"] = dict(polyextrude_metadata)
    operation_records = _semantic_operation_records_from_manifest(manifest)
    operation_record = {
        "op": "polyextrude",
        "source": source.operand_id,
        "attempted_kernel": kernel.name,
        "actual_kernel": kernel.name,
        "semantic_operation": semantic_operation,
        "axis": axis_name,
        "distance_cm": distance,
        "result_face_count": len(mesh.faces),
        "result_vertex_count": len(mesh.vertices),
        "result_watertight": bool(mesh.is_watertight),
        "result_body_count": kernel.body_count(current),
        "kernel_polyextrude": dict(polyextrude_metadata),
    }
    _record_result_probe(operation_record, kernel=kernel, result_handle=current)
    final_operation_record = _final_semantic_operation_record(
        operation_records,
        semantic_operation,
    )
    face_operation_id = str(
        final_operation_record.get("operation_id")
        or f"{source.operand_id}.{_operation_id_fragment(semantic_operation)}"
    )
    (
        face_operation_ids,
        face_operation_summary,
        face_operation_attribution,
    ) = _attach_direct_face_operation_metadata(
        mesh,
        face_operation_id,
        source="kernel_program.polyextrude.source_operand",
        method="polyextruded_source_face_ranges",
    )
    kernel_feature_detail = _kernel_feature_detail_metadata(
        kernel,
        mesh,
        current,
        [source],
        semantic_operation=semantic_operation,
        method_suffix="polyextrude_kernel_program_v1",
        fallback=bool(polyextrude_details.get("fallback"))
        or bool(polyextrude_details.get("exact_kernel_path_fallback")),
        face_operation_attributed=bool(face_operation_ids),
        extra={
            "exact_kernel_path": bool(polyextrude_details.get("exact_kernel_path", False)),
            "polyextrude_axis": axis_name,
            "polyextrude_distance_cm": distance,
        },
    )
    if kernel_feature_detail:
        mesh.metadata["lathe_kernel_feature_detail"] = dict(kernel_feature_detail)
    semantic_handoff = _attach_kernel_program_semantic_handoff(
        mesh,
        [source],
        [operation_record],
    )
    details = {
        "kernel_program_version": KERNEL_PROGRAM_VERSION,
        "kernel_program_route": route,
        "kernel_program_operation_count": operation_count,
        "kernel_program_operand_count": 1,
        "kernel_program_semantic_operation_record_count": len(operation_records),
        "kernel_program_semantic_operation_counts": _operation_counts(operation_records),
        "kernel_program_semantic_operation_records": operation_records,
        "kernel_program_kernel": kernel.name,
        "kernel_program_backend": backend,
        "kernel_program_manifest": manifest,
        "kernel_program_capabilities_checked": sorted(required),
        "kernel_program_watertight": kernel.is_watertight(current),
        "kernel_program_body_count": kernel.body_count(current),
        "kernel_program_operands": [source.trace_record()],
        "kernel_program_operations": [operation_record],
        "kernel_program_face_operation_attribution": face_operation_attribution,
        "face_operation_ids": face_operation_ids,
        "face_operation_summary": face_operation_summary,
        "kernel_feature_detail": kernel_feature_detail,
        "kernel_program_feature_detail": kernel_feature_detail,
        "kernel_program_polyextrude_source_operand_id": source.operand_id,
        "polyextrude_axis": axis_name,
        "polyextrude_distance_cm": distance,
        "polyextrude_source_face_count": len(source_mesh.faces),
        "polyextrude_source_vertex_count": len(source_mesh.vertices),
        "polyextrude_result_face_count": len(mesh.faces),
        "polyextrude_result_vertex_count": len(mesh.vertices),
        "polyextrude_result_watertight": bool(mesh.is_watertight),
        **polyextrude_details,
        "kernel_program_semantic_handoff": semantic_handoff,
    }
    return KernelProgramResult(
        mesh=mesh,
        handle=current,
        operation_count=operation_count,
        details=details,
    )


def execute_component_assembly_program(
    kernel: GeometryKernel,
    operands: list[KernelOperand],
    *,
    semantic_operation: str = "component_assembly",
    assembly_kind: str = "component_assembly",
    operation_limit: int | None = None,
    route: str = "component_assembly_program",
    backend: str | None = None,
) -> KernelProgramResult:
    """Execute a heterogeneous visible component assembly through the kernel seam."""
    if not operands:
        raise ValueError("kernel component_assembly program requires at least one operand")
    unsupported_blend_modes = sorted(
        {
            str(operand.blend_mode or "union")
            for operand in operands
            if str(operand.blend_mode or "union") != "union"
        }
    )
    missing_handles = [operand.operand_id for operand in operands if operand.handle is None]
    if missing_handles:
        raise ValueError(
            f"kernel component_assembly operands have no handles: {missing_handles!r}"
        )
    if unsupported_blend_modes:
        component_manifest = build_component_assembly_program_manifest(
            operands,
            semantic_operation=semantic_operation,
            assembly_kind=assembly_kind,
            route=route,
            backend=backend,
            operation_limit=operation_limit,
        )
        result = execute_boolean_program(
            kernel,
            operands,
            operation_limit=operation_limit,
            route=f"{route}_ordered_boolean",
            backend=backend,
        )
        mesh = result.mesh
        result_body_count = kernel.body_count(result.handle)
        source_face_counts = [int(operand.source_mesh_face_count) for operand in operands]
        source_vertex_counts = [
            int(len(operand.source_mesh.vertices))
            if isinstance(operand.source_mesh, trimesh.Trimesh)
            else 0
            for operand in operands
        ]
        source_body_counts = [int(operand.source_mesh_body_count) for operand in operands]
        component_parts = _stable_unique_strings([operand.part for operand in operands])
        component_primitive_types = _stable_unique_strings(
            [operand.primitive_type for operand in operands]
        )
        component_blend_modes = {
            mode: sum(1 for operand in operands if str(operand.blend_mode or "union") == mode)
            for mode in sorted({str(operand.blend_mode or "union") for operand in operands})
        }
        component_semantics = _component_operand_semantic_summary(operands)
        fallback_count = int(result.details.get("kernel_program_boolean_fallback_count") or 0)
        component_assembly_metadata = {
            "schema": "lathe.geometry.kernel_component_assembly.v1",
            "operation": semantic_operation,
            "assembly_kind": assembly_kind,
            "method": "ordered_boolean_component_assembly_program_v1",
            "attempted_backend": f"{kernel.name}.ordered_boolean",
            "actual_backend": f"{kernel.name}.ordered_boolean",
            "attempted_kernel": kernel.name,
            "actual_kernel": kernel.name,
            "actual_operation": "ordered_boolean",
            "fallback": bool(fallback_count),
            "passthrough": False,
            "operand_count": len(operands),
            "component_blend_modes": component_blend_modes,
            **component_semantics,
            "unsupported_blend_modes_routed": unsupported_blend_modes,
            "source_parts": component_parts,
            "source_primitive_types": component_primitive_types,
            "source_face_counts": source_face_counts,
            "source_vertex_counts": source_vertex_counts,
            "source_body_counts": source_body_counts,
            "source_face_count": int(sum(source_face_counts)),
            "source_vertex_count": int(sum(source_vertex_counts)),
            "source_body_count": int(sum(source_body_counts)),
            "result_face_count": len(mesh.faces),
            "result_vertex_count": len(mesh.vertices),
            "result_watertight": bool(mesh.is_watertight),
            "result_body_count": int(result_body_count),
            "boolean_operation_count": int(boolean_operation_count(operands)),
            "boolean_fallback_count": fallback_count,
        }
        mesh.metadata["lathe_kernel_component_assembly"] = dict(component_assembly_metadata)
        details = {
            **dict(result.details),
            "kernel_program_component_assembly_boolean_route": True,
            "kernel_program_component_assembly_requested_route": route,
            "kernel_program_component_assembly_actual_route": result.details.get("kernel_program_route"),
            "kernel_program_component_assembly_manifest": component_manifest,
            "component_assembly_semantic_operation": semantic_operation,
            "component_assembly_kind": assembly_kind,
            "component_assembly_method": "ordered_boolean_component_assembly_program_v1",
            "component_assembly_source_operand_count": len(operands),
            "component_assembly_source_parts": component_parts,
            "component_assembly_source_primitive_types": component_primitive_types,
            "component_assembly_component_blend_modes": component_blend_modes,
            **{
                f"component_assembly_{key}": value
                for key, value in component_semantics.items()
            },
            "component_assembly_source_face_count": int(sum(source_face_counts)),
            "component_assembly_source_vertex_count": int(sum(source_vertex_counts)),
            "component_assembly_source_body_count": int(sum(source_body_counts)),
            "component_assembly_result_face_count": len(mesh.faces),
            "component_assembly_result_vertex_count": len(mesh.vertices),
            "component_assembly_result_body_count": int(result_body_count),
            "component_assembly_result_watertight": bool(mesh.is_watertight),
            "kernel_component_assembly": component_assembly_metadata,
        }
        return KernelProgramResult(
            mesh=mesh,
            handle=result.handle,
            operation_count=result.operation_count,
            details=details,
        )
    operation_count = component_assembly_operation_count(operands)
    if operation_limit is not None and operation_count > operation_limit:
        raise ValueError(
            f"kernel component_assembly operation_count={operation_count} exceeds "
            f"limit={operation_limit}"
        )
    capabilities = _kernel_capabilities(kernel)
    required = {"from_trimesh", "to_trimesh"}
    _require_capabilities(kernel, capabilities, required)
    manifest = build_component_assembly_program_manifest(
        operands,
        semantic_operation=semantic_operation,
        assembly_kind=assembly_kind,
        route=route,
        backend=backend,
        operation_limit=operation_limit,
    )

    source_meshes = [_non_empty_mesh(kernel, operand.handle).copy() for operand in operands]
    combined = trimesh.util.concatenate([mesh.copy() for mesh in source_meshes])
    if not isinstance(combined, trimesh.Trimesh) or len(combined.faces) == 0:
        raise ValueError("kernel component_assembly program produced an empty mesh")
    combined.remove_infinite_values()
    combined.remove_unreferenced_vertices()
    try:
        combined.fix_normals()
    except (AttributeError, TypeError, ValueError, RuntimeError):
        pass

    source_body_counts: list[int] = []
    for mesh in source_meshes:
        try:
            source_body_counts.append(int(len(mesh.split(only_watertight=False))))
        except (AttributeError, TypeError, ValueError, RuntimeError):
            source_body_counts.append(0)
    source_face_counts = [len(mesh.faces) for mesh in source_meshes]
    source_vertex_counts = [len(mesh.vertices) for mesh in source_meshes]
    component_primitive_types = _stable_unique_strings(
        [operand.primitive_type for operand in operands]
    )
    component_parts = _stable_unique_strings([operand.part for operand in operands])
    component_semantics = _component_operand_semantic_summary(operands)
    component_assembly_metadata = {
        "schema": "lathe.geometry.kernel_component_assembly.v1",
        "operation": semantic_operation,
        "assembly_kind": assembly_kind,
        "method": "visible_mesh_concatenation_import_v1",
        "attempted_backend": f"{kernel.name}.from_trimesh",
        "actual_backend": f"{kernel.name}.from_trimesh",
        "attempted_kernel": kernel.name,
        "actual_kernel": kernel.name,
        "actual_operation": semantic_operation,
        "fallback": False,
        "passthrough": False,
        "operand_count": len(operands),
        **component_semantics,
        "source_parts": component_parts,
        "source_primitive_types": component_primitive_types,
        "source_face_counts": source_face_counts,
        "source_vertex_counts": source_vertex_counts,
        "source_body_counts": source_body_counts,
        "source_face_count": int(sum(source_face_counts)),
        "source_vertex_count": int(sum(source_vertex_counts)),
        "source_body_count": int(sum(source_body_counts)),
        "result_face_count": len(combined.faces),
        "result_vertex_count": len(combined.vertices),
        "result_watertight": bool(combined.is_watertight),
        "result_body_count": int(len(combined.split(only_watertight=False))),
    }
    combined.metadata["lathe_kernel_component_assembly"] = dict(component_assembly_metadata)
    current = kernel.from_trimesh(combined)
    mesh = _non_empty_mesh(kernel, current)
    mesh.metadata["lathe_kernel_component_assembly"] = dict(component_assembly_metadata)

    operation_records = _semantic_operation_records_from_manifest(manifest)
    operation_record = {
        "op": "component_assembly",
        "semantic_operation": semantic_operation,
        "assembly_kind": assembly_kind,
        "inputs": [operand.operand_id for operand in operands],
        "attempted_kernel": kernel.name,
        "actual_kernel": kernel.name,
        "attempted_backend": f"{kernel.name}.from_trimesh",
        "actual_backend": f"{kernel.name}.from_trimesh",
        "actual_operation": semantic_operation,
        "method": "visible_mesh_concatenation_import_v1",
        "result_face_count": len(mesh.faces),
        "result_vertex_count": len(mesh.vertices),
        "result_watertight": bool(mesh.is_watertight),
        "result_body_count": kernel.body_count(current),
        "kernel_component_assembly": dict(component_assembly_metadata),
    }
    _record_result_probe(operation_record, kernel=kernel, result_handle=current)
    face_operation_ids = _instance_face_operation_ids(
        operands,
        source_meshes,
        mesh,
        assembly_method="visible_mesh_concatenation_import",
    )
    face_operation_summary: dict[str, Any] = {}
    face_operation_attribution = {
        "schema": "lathe.geometry.kernel_program_face_operation_attribution.v1",
        "source": "kernel_program.component_assembly.operands",
        "attributed": bool(face_operation_ids),
        "assembly_method": "visible_mesh_concatenation_import",
        "component_count": len(operands),
        "result_face_count": len(mesh.faces),
    }
    if face_operation_ids:
        face_operation_summary = _kernel_program_face_operation_summary(
            face_operation_ids,
            source="kernel_program.component_assembly.component_operands",
        )
        face_operation_attribution.update(
            {
                "method": "concatenated_component_face_ranges",
                "face_operation_count": len(set(face_operation_ids)),
                "face_operation_attribution_count": len(face_operation_ids),
            }
        )
        mesh.metadata["face_operation_ids"] = list(face_operation_ids)
        mesh.metadata["face_operation_summary"] = dict(face_operation_summary)
    else:
        face_operation_attribution["reason"] = (
            "kernel_result_faces_not_a_direct_component_concatenation"
        )
    mesh.metadata["lathe_kernel_program_face_operation_attribution"] = dict(
        face_operation_attribution
    )
    semantic_handoff = _attach_kernel_program_semantic_handoff(
        mesh,
        operands,
        [operation_record],
    )
    result_body_count = kernel.body_count(current)
    details = {
        "kernel_program_version": KERNEL_PROGRAM_VERSION,
        "kernel_program_route": route,
        "kernel_program_operation_count": operation_count,
        "kernel_program_operand_count": len(operands),
        "kernel_program_semantic_operation_record_count": len(operation_records),
        "kernel_program_semantic_operation_counts": _operation_counts(operation_records),
        "kernel_program_semantic_operation_records": operation_records,
        "kernel_program_kernel": kernel.name,
        "kernel_program_backend": backend,
        "kernel_program_manifest": manifest,
        "kernel_program_capabilities_checked": sorted(required),
        "kernel_program_watertight": kernel.is_watertight(current),
        "kernel_program_body_count": result_body_count,
        "kernel_program_operands": [operand.trace_record() for operand in operands],
        "kernel_program_operations": [operation_record],
        "kernel_program_face_operation_attribution": face_operation_attribution,
        "face_operation_ids": face_operation_ids,
        "face_operation_summary": face_operation_summary,
        "component_assembly_semantic_operation": semantic_operation,
        "component_assembly_kind": assembly_kind,
        "component_assembly_method": "visible_mesh_concatenation_import_v1",
        "component_assembly_source_operand_count": len(operands),
        "component_assembly_source_parts": component_parts,
        "component_assembly_source_primitive_types": component_primitive_types,
        **{
            f"component_assembly_{key}": value
            for key, value in component_semantics.items()
        },
        "component_assembly_source_face_count": int(sum(source_face_counts)),
        "component_assembly_source_vertex_count": int(sum(source_vertex_counts)),
        "component_assembly_source_body_count": int(sum(source_body_counts)),
        "component_assembly_result_face_count": len(mesh.faces),
        "component_assembly_result_vertex_count": len(mesh.vertices),
        "component_assembly_result_body_count": int(result_body_count),
        "component_assembly_result_watertight": bool(mesh.is_watertight),
        "kernel_component_assembly": component_assembly_metadata,
        "kernel_program_semantic_handoff": semantic_handoff,
    }
    return KernelProgramResult(
        mesh=mesh,
        handle=current,
        operation_count=operation_count,
        details=details,
    )


def _sequence_count(value: Any) -> int:
    if isinstance(value, (list, tuple)):
        return len(value)
    return 0


_PROFILE_CURVE_NUMERIC_METADATA_KEYS = (
    "degree",
    "order",
    "input_point_count",
    "sampled_point_count",
    "weight_count",
    "knot_count",
)
_PROFILE_CURVE_BOOL_METADATA_KEYS = ("rational", "periodic", "custom_knots", "closed_polygon", "closed_curve")


def _copy_profile_curve_metadata_stats(
    stats: dict[str, Any],
    *,
    prefix: str,
    payload: Any,
) -> None:
    curve = _dict_metadata(payload)
    if not curve:
        return
    for key in ("curve_kind", "degree_source_parameter"):
        value = curve.get(key)
        if value not in (None, ""):
            stats[f"{prefix}_{key}"] = str(value)
    for key in _PROFILE_CURVE_NUMERIC_METADATA_KEYS:
        value = curve.get(key)
        if isinstance(value, (int, float)) and math.isfinite(float(value)):
            stats[f"{prefix}_{key}"] = int(value)
    for key in _PROFILE_CURVE_BOOL_METADATA_KEYS:
        if key in curve:
            stats[f"{prefix}_{key}"] = bool(curve.get(key))


def _copy_section_curve_metadata_stats(
    stats: dict[str, Any],
    *,
    payload: Any,
) -> None:
    if not isinstance(payload, (list, tuple)):
        return
    kinds: list[str] = []
    degrees: list[int] = []
    orders: list[int] = []
    rational_count = 0
    periodic_count = 0
    for item in payload:
        curve = _dict_metadata(item)
        kind = str(curve.get("curve_kind") or "")
        if kind:
            kinds.append(kind)
        if curve.get("rational"):
            rational_count += 1
        if curve.get("periodic"):
            periodic_count += 1
        for key, out in (("degree", degrees), ("order", orders)):
            value = curve.get(key)
            if isinstance(value, (int, float)) and math.isfinite(float(value)):
                out.append(int(value))
    if kinds:
        unique_kinds = sorted(set(kinds))
        stats["section_curve_kinds"] = unique_kinds
        stats["section_curve_kind_count"] = len(unique_kinds)
    if degrees:
        stats["section_curve_degree_min"] = min(degrees)
        stats["section_curve_degree_max"] = max(degrees)
    if orders:
        stats["section_curve_order_min"] = min(orders)
        stats["section_curve_order_max"] = max(orders)
    if payload:
        stats["section_curve_rational_count"] = rational_count
        stats["section_curve_periodic_count"] = periodic_count


def _profile_path_source_stats(source: KernelOperand) -> dict[str, Any]:
    metadata = _dict_metadata(source.metadata)
    semantic_metadata = _dict_metadata(metadata.get("semantic_metadata"))
    source_shape = _dict_metadata(semantic_metadata.get("source_shape_primitive"))
    v2_metadata = _dict_metadata(semantic_metadata.get("shape_ir_v2"))
    stats: dict[str, Any] = {
        "source_primitive_type": source.primitive_type or str(source_shape.get("primitive_type") or ""),
        "source_part": source.part or str(source_shape.get("part") or ""),
    }
    for key in (
        "cross_section",
        "profile_polygon",
        "profile_points",
        "sweep_path",
        "cross_sections",
        "section_centers",
    ):
        count = _sequence_count(source_shape.get(key))
        if count:
            stats[f"{key}_count"] = count
    if isinstance(source_shape.get("cross_sections"), (list, tuple)):
        section_sizes = [
            _sequence_count(section)
            for section in source_shape["cross_sections"]
            if isinstance(section, (list, tuple))
        ]
        if section_sizes:
            stats["section_profile_point_count_min"] = min(section_sizes)
            stats["section_profile_point_count_max"] = max(section_sizes)
    for numeric_key in (
        "radius",
        "height",
        "tube_radius",
        "turns",
        "segments_per_turn",
        "cross_section_segments",
        "thread_pitch",
        "actual_pitch",
        "thread_depth",
        "thread_start_clearance",
        "thread_end_clearance",
        "angle_degrees",
        "start_angle_degrees",
        "path_segments",
        "extrude_height",
        "extrude_start_scale",
        "extrude_end_scale",
        "extrude_twist_degrees",
        "extrude_segments",
        "revolve_degrees",
        "revolve_start_degrees",
    ):
        value = source_shape.get(numeric_key)
        if isinstance(value, (int, float)) and math.isfinite(float(value)):
            stats[numeric_key] = float(value)
    kernel_import = _dict_metadata(metadata.get("kernel_import"))
    _copy_kernel_import_stats(stats, kernel_import)
    for modifier_name in (
        "v2_sweep_modifier",
        "v2_polywire_modifier",
        "v2_helical_sweep_modifier",
        "v2_loft_modifier",
        "v2_spring_modifier",
        "v2_curved_tube_modifier",
        "v2_threaded_cylinder_modifier",
        "v2_curve_profile_modifier",
        "v2_curve_sweep_modifier",
        "v2_curve_loft_modifier",
    ):
        modifier = _dict_metadata(v2_metadata.get(modifier_name))
        if modifier:
            stats["source_modifier"] = modifier_name
            stats["source_modifier_method"] = str(modifier.get("method") or "")
            for count_key in (
                "cross_section_point_count",
                "sweep_path_point_count",
                "path_point_count",
                "section_count",
                "profile_point_count",
            ):
                if count_key in modifier:
                    with suppress(TypeError, ValueError):
                        stats[count_key] = int(modifier[count_key])
            _copy_profile_curve_metadata_stats(stats, prefix="profile", payload=modifier)
            for nested_key, prefix in (
                ("cross_section_curve", "cross_section"),
                ("sweep_curve", "sweep"),
                ("path_curve", "path"),
                ("section_path_curve", "section_path"),
            ):
                _copy_profile_curve_metadata_stats(
                    stats,
                    prefix=prefix,
                    payload=modifier.get(nested_key),
                )
            _copy_section_curve_metadata_stats(
                stats,
                payload=modifier.get("section_curve_metadata"),
            )
            break
    return stats


def execute_profile_path_program(
    kernel: GeometryKernel,
    source: KernelOperand,
    *,
    semantic_operation: str = "sop.sweep",
    profile_kind: str = "profile_path",
    operation_limit: int | None = None,
    route: str = "profile_path_program",
    backend: str | None = None,
) -> KernelProgramResult:
    """Expose sweep/loft/profile geometry as a typed KernelProgram result."""
    if source.handle is None:
        raise ValueError(f"kernel profile_path source operand {source.operand_id!r} has no handle")
    operation_count = profile_path_operation_count(source)
    if operation_limit is not None and operation_count > operation_limit:
        raise ValueError(
            f"kernel profile_path operation_count={operation_count} exceeds limit={operation_limit}"
        )
    capabilities = _kernel_capabilities(kernel)
    required = {"to_trimesh"}
    _require_capabilities(kernel, capabilities, required)
    manifest = build_profile_path_program_manifest(
        source,
        semantic_operation=semantic_operation,
        profile_kind=profile_kind,
        route=route,
        backend=backend,
        operation_limit=operation_limit,
    )
    mesh = _non_empty_mesh(kernel, source.handle)
    source_stats = _profile_path_source_stats(source)
    method = "profile_path_kernel_build_result_v1"
    if source_stats.get("kernel_import_route") == "exact_mesh.from_trimesh":
        method = "profile_path_exact_mesh_import_result_v1"
    profile_path_metadata = {
        "schema": "lathe.geometry.kernel_profile_path.v1",
        "operation": semantic_operation,
        "profile_kind": profile_kind,
        "method": method,
        "attempted_backend": str(source_stats.get("kernel_import_route") or kernel.name),
        "actual_backend": str(source_stats.get("kernel_import_backend") or kernel.name),
        "attempted_kernel": kernel.name,
        "actual_kernel": kernel.name,
        "actual_operation": semantic_operation,
        "fallback": False,
        "passthrough": False,
        "source_face_count": source.source_mesh_face_count or len(mesh.faces),
        "source_vertex_count": len(source.source_mesh.vertices)
        if isinstance(source.source_mesh, trimesh.Trimesh)
        else len(mesh.vertices),
        "result_face_count": len(mesh.faces),
        "result_vertex_count": len(mesh.vertices),
        "result_watertight": bool(mesh.is_watertight),
        "result_body_count": kernel.body_count(source.handle),
        **source_stats,
    }
    mesh.metadata["lathe_kernel_profile_path"] = dict(profile_path_metadata)
    operation_records = _semantic_operation_records_from_manifest(manifest)
    operation_record = {
        "op": "profile_path",
        "source": source.operand_id,
        "semantic_operation": semantic_operation,
        "profile_kind": profile_kind,
        "attempted_kernel": kernel.name,
        "actual_kernel": kernel.name,
        "method": method,
        "result_face_count": len(mesh.faces),
        "result_vertex_count": len(mesh.vertices),
        "result_watertight": bool(mesh.is_watertight),
        "result_body_count": kernel.body_count(source.handle),
        "kernel_profile_path": dict(profile_path_metadata),
    }
    _record_result_probe(operation_record, kernel=kernel, result_handle=source.handle)
    (
        face_operation_ids,
        face_operation_summary,
        face_operation_attribution,
    ) = _attach_direct_face_operation_metadata(
        mesh,
        f"{source.operand_id}.{_operation_id_fragment(semantic_operation)}",
        source="kernel_program.profile_path.source_operand",
        method="profile_path_source_face_ranges",
    )
    semantic_handoff = _attach_kernel_program_semantic_handoff(
        mesh,
        [source],
        [operation_record],
    )
    details = {
        "kernel_program_version": KERNEL_PROGRAM_VERSION,
        "kernel_program_route": route,
        "kernel_program_operation_count": operation_count,
        "kernel_program_operand_count": 1,
        "kernel_program_semantic_operation_record_count": len(operation_records),
        "kernel_program_semantic_operation_counts": _operation_counts(operation_records),
        "kernel_program_semantic_operation_records": operation_records,
        "kernel_program_kernel": kernel.name,
        "kernel_program_backend": backend,
        "kernel_program_manifest": manifest,
        "kernel_program_capabilities_checked": sorted(required),
        "kernel_program_watertight": kernel.is_watertight(source.handle),
        "kernel_program_body_count": kernel.body_count(source.handle),
        "kernel_program_operands": [source.trace_record()],
        "kernel_program_operations": [operation_record],
        "kernel_program_face_operation_attribution": face_operation_attribution,
        "face_operation_ids": face_operation_ids,
        "face_operation_summary": face_operation_summary,
        "kernel_program_profile_path_source_operand_id": source.operand_id,
        "profile_path_semantic_operation": semantic_operation,
        "profile_path_kind": profile_kind,
        "profile_path_method": method,
        "profile_path_result_face_count": len(mesh.faces),
        "profile_path_result_vertex_count": len(mesh.vertices),
        "profile_path_result_watertight": bool(mesh.is_watertight),
        "kernel_profile_path": profile_path_metadata,
        "kernel_program_semantic_handoff": semantic_handoff,
    }
    return KernelProgramResult(
        mesh=mesh,
        handle=source.handle,
        operation_count=operation_count,
        details=details,
    )


def _sdf_field_source_stats(source: KernelOperand) -> dict[str, Any]:
    metadata = _dict_metadata(source.metadata)
    semantic_metadata = _dict_metadata(metadata.get("semantic_metadata"))
    source_shape = _dict_metadata(semantic_metadata.get("source_shape_primitive"))
    v2_metadata = _dict_metadata(semantic_metadata.get("shape_ir_v2"))
    modifier = _dict_metadata(v2_metadata.get("v2_sdf_metaball_cluster_modifier"))
    stats: dict[str, Any] = {
        "source_primitive_type": source.primitive_type or str(source_shape.get("primitive_type") or ""),
        "source_part": source.part or str(source_shape.get("part") or ""),
    }
    for key in ("mesh_vertices", "mesh_faces"):
        count = _sequence_count(source_shape.get(key))
        if count:
            stats[f"{key}_count"] = count
    kernel_import = _dict_metadata(metadata.get("kernel_import"))
    _copy_kernel_import_stats(stats, kernel_import)
    if modifier:
        stats["source_modifier"] = "v2_sdf_metaball_cluster_modifier"
        stats["source_modifier_method"] = str(modifier.get("method") or "")
        for numeric_key in (
            "blob_count",
            "radius_cm",
            "field_radius_cm",
            "smooth_radius_cm",
            "connection_distance_cm",
            "effective_spread_radius_cm",
            "result_body_count",
            "resolution",
            "bounds_radius_cm",
            "seed",
        ):
            value = modifier.get(numeric_key)
            if isinstance(value, (int, float)) and math.isfinite(float(value)):
                stats[numeric_key] = float(value)
        for text_key in (
            "requested_extraction_backend",
            "actual_extraction_backend",
            "extraction_fallback_reason",
        ):
            if modifier.get(text_key) not in (None, "", (), [], {}):
                stats[text_key] = str(modifier.get(text_key) or "")
        attempts = modifier.get("attempted_extraction_backends")
        if isinstance(attempts, list):
            stats["attempted_extraction_backends"] = [str(item) for item in attempts]
        blob_records = modifier.get("blob_records")
        if isinstance(blob_records, list):
            stats["blob_record_count"] = len(blob_records)
    return stats


def execute_sdf_field_program(
    kernel: GeometryKernel,
    source: KernelOperand,
    *,
    semantic_operation: str = "solid.sdf_metaball_cluster",
    field_kind: str = "sdf_field",
    operation_limit: int | None = None,
    route: str = "sdf_field_program",
    backend: str | None = None,
) -> KernelProgramResult:
    """Expose extracted implicit-field geometry as a typed KernelProgram result."""
    if source.handle is None:
        raise ValueError(f"kernel sdf_field source operand {source.operand_id!r} has no handle")
    operation_count = sdf_field_operation_count(source)
    if operation_limit is not None and operation_count > operation_limit:
        raise ValueError(
            f"kernel sdf_field operation_count={operation_count} exceeds limit={operation_limit}"
        )
    capabilities = _kernel_capabilities(kernel)
    required = {"to_trimesh"}
    _require_capabilities(kernel, capabilities, required)
    manifest = build_sdf_field_program_manifest(
        source,
        semantic_operation=semantic_operation,
        field_kind=field_kind,
        route=route,
        backend=backend,
        operation_limit=operation_limit,
    )
    mesh = _non_empty_mesh(kernel, source.handle)
    source_stats = _sdf_field_source_stats(source)
    method = "sdf_field_kernel_build_result_v1"
    if source_stats.get("kernel_import_route") == "exact_mesh.from_trimesh":
        method = "sdf_field_extracted_mesh_import_result_v1"
    sdf_field_metadata = {
        "schema": "lathe.geometry.kernel_sdf_field.v1",
        "operation": semantic_operation,
        "field_kind": field_kind,
        "method": method,
        "attempted_backend": str(source_stats.get("kernel_import_route") or kernel.name),
        "actual_backend": str(source_stats.get("kernel_import_backend") or kernel.name),
        "attempted_kernel": kernel.name,
        "actual_kernel": kernel.name,
        "actual_operation": semantic_operation,
        "fallback": False,
        "passthrough": False,
        "source_face_count": source.source_mesh_face_count or len(mesh.faces),
        "source_vertex_count": len(source.source_mesh.vertices)
        if isinstance(source.source_mesh, trimesh.Trimesh)
        else len(mesh.vertices),
        "result_face_count": len(mesh.faces),
        "result_vertex_count": len(mesh.vertices),
        "result_watertight": bool(mesh.is_watertight),
        "result_body_count": kernel.body_count(source.handle),
        **source_stats,
    }
    mesh.metadata["lathe_kernel_sdf_field"] = dict(sdf_field_metadata)
    operation_records = _semantic_operation_records_from_manifest(manifest)
    operation_record = {
        "op": "sdf_field",
        "source": source.operand_id,
        "semantic_operation": semantic_operation,
        "field_kind": field_kind,
        "attempted_kernel": kernel.name,
        "actual_kernel": kernel.name,
        "method": method,
        "result_face_count": len(mesh.faces),
        "result_vertex_count": len(mesh.vertices),
        "result_watertight": bool(mesh.is_watertight),
        "result_body_count": kernel.body_count(source.handle),
        "kernel_sdf_field": dict(sdf_field_metadata),
    }
    _record_result_probe(operation_record, kernel=kernel, result_handle=source.handle)
    (
        face_operation_ids,
        face_operation_summary,
        face_operation_attribution,
    ) = _attach_direct_face_operation_metadata(
        mesh,
        f"{source.operand_id}.{_operation_id_fragment(semantic_operation)}",
        source="kernel_program.sdf_field.source_operand",
        method="sdf_field_source_face_ranges",
    )
    semantic_handoff = _attach_kernel_program_semantic_handoff(
        mesh,
        [source],
        [operation_record],
    )
    details = {
        "kernel_program_version": KERNEL_PROGRAM_VERSION,
        "kernel_program_route": route,
        "kernel_program_operation_count": operation_count,
        "kernel_program_operand_count": 1,
        "kernel_program_semantic_operation_record_count": len(operation_records),
        "kernel_program_semantic_operation_counts": _operation_counts(operation_records),
        "kernel_program_semantic_operation_records": operation_records,
        "kernel_program_kernel": kernel.name,
        "kernel_program_backend": backend,
        "kernel_program_manifest": manifest,
        "kernel_program_capabilities_checked": sorted(required),
        "kernel_program_watertight": kernel.is_watertight(source.handle),
        "kernel_program_body_count": kernel.body_count(source.handle),
        "kernel_program_operands": [source.trace_record()],
        "kernel_program_operations": [operation_record],
        "kernel_program_face_operation_attribution": face_operation_attribution,
        "face_operation_ids": face_operation_ids,
        "face_operation_summary": face_operation_summary,
        "kernel_program_sdf_field_source_operand_id": source.operand_id,
        "sdf_field_semantic_operation": semantic_operation,
        "sdf_field_kind": field_kind,
        "sdf_field_method": method,
        "sdf_field_result_face_count": len(mesh.faces),
        "sdf_field_result_vertex_count": len(mesh.vertices),
        "sdf_field_result_watertight": bool(mesh.is_watertight),
        "kernel_sdf_field": sdf_field_metadata,
        "kernel_program_semantic_handoff": semantic_handoff,
    }
    return KernelProgramResult(
        mesh=mesh,
        handle=source.handle,
        operation_count=operation_count,
        details=details,
    )


def _terrain_field_source_stats(source: KernelOperand) -> dict[str, Any]:
    metadata = _dict_metadata(source.metadata)
    semantic_metadata = _dict_metadata(metadata.get("semantic_metadata"))
    source_shape = _dict_metadata(semantic_metadata.get("source_shape_primitive"))
    v2_metadata = _dict_metadata(semantic_metadata.get("shape_ir_v2"))
    modifier = _dict_metadata(v2_metadata.get("v2_terrain_patch_modifier"))
    stats: dict[str, Any] = {
        "source_primitive_type": source.primitive_type or str(source_shape.get("primitive_type") or ""),
        "source_part": source.part or str(source_shape.get("part") or ""),
    }
    resolution = source_shape.get("resolution")
    if isinstance(resolution, (list, tuple)) and len(resolution) >= 2:
        with suppress(TypeError, ValueError):
            stats["heightfield_resolution"] = [int(resolution[0]), int(resolution[1])]
    height_data = source_shape.get("height_data")
    if isinstance(height_data, list) and height_data:
        row_count = len(height_data)
        column_count = max(
            (
                len(row)
                for row in height_data
                if isinstance(row, (list, tuple))
            ),
            default=0,
        )
        stats["height_data_row_count"] = int(row_count)
        stats["height_data_column_count"] = int(column_count)
        heights: list[float] = []
        for row in height_data:
            if not isinstance(row, (list, tuple)):
                continue
            for value in row:
                with suppress(TypeError, ValueError):
                    numeric = float(value)
                    if math.isfinite(numeric):
                        heights.append(numeric)
        if heights:
            stats["height_min"] = min(heights)
            stats["height_max"] = max(heights)
            stats["height_span"] = max(heights) - min(heights)
    bounds_xy = source_shape.get("bounds_xy")
    if isinstance(bounds_xy, (list, tuple)) and len(bounds_xy) == 4:
        with suppress(TypeError, ValueError):
            stats["bounds_xy"] = [float(value) for value in bounds_xy]
    vertical_scale = source_shape.get("vertical_scale")
    if isinstance(vertical_scale, (int, float)) and math.isfinite(float(vertical_scale)):
        stats["vertical_scale_cm"] = float(vertical_scale)
    kernel_import = _dict_metadata(metadata.get("kernel_import"))
    if kernel_import:
        _copy_kernel_import_stats(stats, kernel_import)
        if bool(kernel_import.get("surface_primitive_solidified")):
            stats["surface_primitive_solidified"] = True
            stats["solidification_method"] = str(kernel_import.get("method") or "")
    if modifier:
        stats["source_modifier"] = "v2_terrain_patch_modifier"
        stats["source_modifier_method"] = str(modifier.get("method") or "")
        for numeric_key in (
            "width_cm",
            "depth_cm",
            "height_cm",
            "resolution",
            "seed",
            "roughness",
            "octaves",
            "border_taper",
            "terrace_count",
            "terrace_strength",
            "erosion_strength",
        ):
            value = modifier.get(numeric_key)
            if isinstance(value, (int, float)) and math.isfinite(float(value)):
                stats[numeric_key] = float(value)
        if modifier.get("biome") not in (None, "", (), [], {}):
            stats["biome"] = str(modifier.get("biome") or "")
    return stats


def execute_terrain_field_program(
    kernel: GeometryKernel,
    source: KernelOperand,
    *,
    semantic_operation: str = "solid.terrain_patch",
    terrain_kind: str = "terrain_patch",
    operation_limit: int | None = None,
    route: str = "terrain_field_program",
    backend: str | None = None,
) -> KernelProgramResult:
    """Expose generated heightfield terrain as a typed KernelProgram result."""
    if source.handle is None:
        raise ValueError(f"kernel terrain_field source operand {source.operand_id!r} has no handle")
    operation_count = terrain_field_operation_count(source)
    if operation_limit is not None and operation_count > operation_limit:
        raise ValueError(
            f"kernel terrain_field operation_count={operation_count} exceeds limit={operation_limit}"
        )
    capabilities = _kernel_capabilities(kernel)
    required = {"to_trimesh"}
    _require_capabilities(kernel, capabilities, required)
    manifest = build_terrain_field_program_manifest(
        source,
        semantic_operation=semantic_operation,
        terrain_kind=terrain_kind,
        route=route,
        backend=backend,
        operation_limit=operation_limit,
    )
    mesh = _non_empty_mesh(kernel, source.handle)
    source_stats = _terrain_field_source_stats(source)
    method = "terrain_field_kernel_build_result_v1"
    if bool(source_stats.get("surface_primitive_solidified")):
        method = "terrain_heightfield_solidified_kernel_result_v1"
    elif source_stats.get("kernel_import_route") == "exact_mesh.from_trimesh":
        method = "terrain_heightfield_exact_mesh_import_result_v1"
    terrain_field_metadata = {
        "schema": "lathe.geometry.kernel_terrain_field.v1",
        "operation": semantic_operation,
        "terrain_kind": terrain_kind,
        "method": method,
        "attempted_backend": str(source_stats.get("kernel_import_route") or kernel.name),
        "actual_backend": str(source_stats.get("kernel_import_backend") or kernel.name),
        "attempted_kernel": kernel.name,
        "actual_kernel": kernel.name,
        "actual_operation": semantic_operation,
        "fallback": False,
        "passthrough": False,
        "source_face_count": source.source_mesh_face_count or len(mesh.faces),
        "source_vertex_count": len(source.source_mesh.vertices)
        if isinstance(source.source_mesh, trimesh.Trimesh)
        else len(mesh.vertices),
        "result_face_count": len(mesh.faces),
        "result_vertex_count": len(mesh.vertices),
        "result_watertight": bool(mesh.is_watertight),
        "result_body_count": kernel.body_count(source.handle),
        **source_stats,
    }
    mesh.metadata["lathe_kernel_terrain_field"] = dict(terrain_field_metadata)
    operation_records = _semantic_operation_records_from_manifest(manifest)
    operation_record = {
        "op": "terrain_field",
        "source": source.operand_id,
        "semantic_operation": semantic_operation,
        "terrain_kind": terrain_kind,
        "attempted_kernel": kernel.name,
        "actual_kernel": kernel.name,
        "method": method,
        "result_face_count": len(mesh.faces),
        "result_vertex_count": len(mesh.vertices),
        "result_watertight": bool(mesh.is_watertight),
        "result_body_count": kernel.body_count(source.handle),
        "kernel_terrain_field": dict(terrain_field_metadata),
    }
    _record_result_probe(operation_record, kernel=kernel, result_handle=source.handle)
    (
        face_operation_ids,
        face_operation_summary,
        face_operation_attribution,
    ) = _attach_direct_face_operation_metadata(
        mesh,
        f"{source.operand_id}.{_operation_id_fragment(semantic_operation)}",
        source="kernel_program.terrain_field.source_operand",
        method="terrain_field_source_face_ranges",
    )
    semantic_handoff = _attach_kernel_program_semantic_handoff(
        mesh,
        [source],
        [operation_record],
    )
    details = {
        "kernel_program_version": KERNEL_PROGRAM_VERSION,
        "kernel_program_route": route,
        "kernel_program_operation_count": operation_count,
        "kernel_program_operand_count": 1,
        "kernel_program_semantic_operation_record_count": len(operation_records),
        "kernel_program_semantic_operation_counts": _operation_counts(operation_records),
        "kernel_program_semantic_operation_records": operation_records,
        "kernel_program_kernel": kernel.name,
        "kernel_program_backend": backend,
        "kernel_program_manifest": manifest,
        "kernel_program_capabilities_checked": sorted(required),
        "kernel_program_watertight": kernel.is_watertight(source.handle),
        "kernel_program_body_count": kernel.body_count(source.handle),
        "kernel_program_operands": [source.trace_record()],
        "kernel_program_operations": [operation_record],
        "kernel_program_face_operation_attribution": face_operation_attribution,
        "face_operation_ids": face_operation_ids,
        "face_operation_summary": face_operation_summary,
        "kernel_program_terrain_field_source_operand_id": source.operand_id,
        "terrain_field_semantic_operation": semantic_operation,
        "terrain_field_kind": terrain_kind,
        "terrain_field_method": method,
        "terrain_field_result_face_count": len(mesh.faces),
        "terrain_field_result_vertex_count": len(mesh.vertices),
        "terrain_field_result_watertight": bool(mesh.is_watertight),
        "kernel_terrain_field": terrain_field_metadata,
        "kernel_program_semantic_handoff": semantic_handoff,
    }
    return KernelProgramResult(
        mesh=mesh,
        handle=source.handle,
        operation_count=operation_count,
        details=details,
    )


def _kernel_scatter_source_payload(source: KernelOperand) -> tuple[str, dict[str, Any]]:
    metadata = _dict_metadata(source.metadata)
    semantic_metadata = _dict_metadata(metadata.get("semantic_metadata"))
    point_scatter = _dict_metadata(semantic_metadata.get("point_scatter"))
    if point_scatter:
        return "point_scatter", point_scatter
    surface_scatter = _dict_metadata(semantic_metadata.get("surface_scatter"))
    if surface_scatter:
        return "surface_scatter", surface_scatter
    copy_to_points = _kernel_modifier_payload(metadata, "v2_copy_to_points_modifier")
    if copy_to_points:
        return "point_scatter", copy_to_points
    surface_modifier = _kernel_modifier_payload(metadata, "v2_surface_scatter_modifier")
    if surface_modifier:
        return "surface_scatter", surface_modifier
    return "", {}


def _kernel_modifier_payload_containers(metadata: dict[str, Any]) -> list[dict[str, Any]]:
    semantic_metadata = _dict_metadata(metadata.get("semantic_metadata"))
    containers = [
        metadata,
        _dict_metadata(metadata.get("shape_ir_v2_baked_source_modifiers")),
        semantic_metadata,
        _dict_metadata(semantic_metadata.get("shape_ir_v2")),
        _dict_metadata(semantic_metadata.get("shape_ir_v2_baked_source_modifiers")),
    ]
    source_shapes = [
        _dict_metadata(semantic_metadata.get("source_shape_primitive")),
        *[
            _dict_metadata(item)
            for item in semantic_metadata.get("source_shape_primitives", [])
            if isinstance(item, dict)
        ],
    ]
    for source_shape in source_shapes:
        if not source_shape:
            continue
        source_semantic = _dict_metadata(source_shape.get("semantic_metadata"))
        containers.extend(
            [
                source_shape,
                _dict_metadata(source_shape.get("shape_ir_v2_baked_source_modifiers")),
                source_semantic,
                _dict_metadata(source_semantic.get("shape_ir_v2")),
                _dict_metadata(source_semantic.get("shape_ir_v2_baked_source_modifiers")),
            ]
        )
    return [container for container in containers if container]


def _kernel_modifier_payload(metadata: dict[str, Any], modifier_name: str) -> dict[str, Any]:
    for container in _kernel_modifier_payload_containers(metadata):
        payload = _dict_metadata(container.get(modifier_name))
        if payload:
            return payload
    return {}


def _kernel_pattern_instance_source_payload(source: KernelOperand) -> tuple[str, dict[str, Any]]:
    metadata = _dict_metadata(source.metadata)
    for modifier_name, pattern_kind in _PATTERN_INSTANCE_MODIFIER_KINDS.items():
        payload = _kernel_modifier_payload(metadata, modifier_name)
        if payload:
            return pattern_kind, payload
    return "", {}


def _kernel_edge_control_source_payload(source: KernelOperand) -> tuple[str, dict[str, Any]]:
    metadata = _dict_metadata(source.metadata)
    weighted = _kernel_modifier_payload(metadata, "v2_weighted_normals_modifier")
    if weighted:
        return "weighted_normals", weighted
    hard_edge = _kernel_modifier_payload(metadata, "v2_mark_hard_edge_modifier")
    if hard_edge:
        return "mark_hard_edge", hard_edge
    return "", {}


def _kernel_feature_detail_payloads(operands: list[KernelOperand]) -> list[dict[str, Any]]:
    features: list[dict[str, Any]] = []
    for operand in operands:
        metadata = _dict_metadata(operand.metadata)
        semantic_metadata = _dict_metadata(metadata.get("semantic_metadata"))
        v2_metadata = _dict_metadata(semantic_metadata.get("shape_ir_v2"))
        operation = str(
            v2_metadata.get("v2_op")
            or semantic_metadata.get("operation")
            or ""
        )
        for modifier_name, feature_kind in _FEATURE_DETAIL_MODIFIER_KINDS.items():
            payload = _kernel_modifier_payload(metadata, modifier_name)
            if not payload:
                continue
            payload_operation = _modifier_payload_operation(
                modifier_name,
                payload,
                base_operation=operation,
            )
            features.append(
                {
                    "operand_id": operand.operand_id,
                    "part": operand.part or "",
                    "component": str(metadata.get("component") or ""),
                    "region": str(metadata.get("region") or ""),
                    "primitive_type": operand.primitive_type or "",
                    "operation": payload_operation,
                    "feature_kind": feature_kind,
                    "modifier_name": modifier_name,
                    "feature_payload": _json_safe(payload),
                }
            )
    return features


def _kernel_edge_treatment_payloads(operands: list[KernelOperand]) -> list[dict[str, Any]]:
    treatments: list[dict[str, Any]] = []
    for operand in operands:
        metadata = _dict_metadata(operand.metadata)
        semantic_metadata = _dict_metadata(metadata.get("semantic_metadata"))
        v2_metadata = _dict_metadata(semantic_metadata.get("shape_ir_v2"))
        operation = str(
            v2_metadata.get("v2_op")
            or semantic_metadata.get("operation")
            or ""
        )
        payload = _kernel_modifier_payload(metadata, "v2_polybevel_modifier")
        if not payload:
            continue
        payload_operation = _modifier_payload_operation(
            "v2_polybevel_modifier",
            payload,
            base_operation=operation,
        )
        treatment_kind = _EDGE_TREATMENT_OPERATION_KINDS.get(payload_operation, "polybevel")
        treatments.append(
            {
                "operand_id": operand.operand_id,
                "part": operand.part or "",
                "primitive_type": operand.primitive_type or "",
                "operation": payload_operation,
                "treatment_kind": treatment_kind,
                "modifier_name": "v2_polybevel_modifier",
                "edge_treatment_payload": _json_safe(payload),
            }
        )
    return treatments


def _first_numeric_payload_value(
    payload: dict[str, Any],
    keys: tuple[str, ...],
) -> tuple[float | None, str]:
    for key in keys:
        if key not in payload:
            continue
        value = payload.get(key)
        if isinstance(value, bool):
            continue
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(numeric):
            return numeric, key
    return None, ""


def _first_int_payload_value(
    payload: dict[str, Any],
    keys: tuple[str, ...],
) -> tuple[int | None, str]:
    for key in keys:
        if key not in payload:
            continue
        value = payload.get(key)
        if isinstance(value, bool):
            continue
        try:
            numeric = int(value)
        except (TypeError, ValueError):
            continue
        return numeric, key
    return None, ""


def _edge_treatment_geometry_parameters(
    treatments: list[dict[str, Any]],
) -> tuple[float, int, str, str]:
    width_values: list[tuple[float, str]] = []
    segment_values: list[tuple[int, str]] = []
    for treatment in treatments:
        payload = _dict_metadata(treatment.get("edge_treatment_payload"))
        width, width_key = _first_numeric_payload_value(
            payload,
            (
                "width_cm",
                "bevel_width_cm",
                "polybevel_width_cm",
                "edge_bevel_width_cm",
                "chamfer_width_cm",
            ),
        )
        if width is not None and width > 0.0:
            width_values.append((float(width), width_key))
        segments, segment_key = _first_int_payload_value(
            payload,
            (
                "segments",
                "bevel_segments",
                "polybevel_segments",
                "chamfer_segments",
            ),
        )
        if segments is not None and segments > 0:
            segment_values.append((int(segments), segment_key))
    if not width_values:
        return 0.0, 1, "", ""
    width, width_key = max(width_values, key=lambda item: item[0])
    if segment_values:
        segments, segment_key = max(segment_values, key=lambda item: item[0])
    else:
        segments, segment_key = 1, ""
    return float(width), max(1, int(segments)), width_key, segment_key


def _mesh_vertices_changed(
    source: trimesh.Trimesh,
    candidate: trimesh.Trimesh,
) -> bool:
    if len(source.vertices) != len(candidate.vertices) or len(source.faces) != len(candidate.faces):
        return True
    try:
        if not np.array_equal(np.asarray(source.faces), np.asarray(candidate.faces)):
            return True
        return not bool(
            np.allclose(
                np.asarray(source.vertices, dtype=np.float64),
                np.asarray(candidate.vertices, dtype=np.float64),
                rtol=1e-7,
                atol=1e-8,
            )
        )
    except (TypeError, ValueError):
        return True


def _apply_import_edge_treatment_geometry(
    kernel: GeometryKernel,
    mesh: trimesh.Trimesh,
    result_handle: Any,
    operands: list[KernelOperand],
    *,
    semantic_operation: str,
) -> tuple[trimesh.Trimesh, Any, dict[str, Any]]:
    treatments = _kernel_edge_treatment_payloads(operands)
    treatment_operation = _EDGE_TREATMENT_OPERATION_KINDS.get(semantic_operation)
    if not treatments and not treatment_operation:
        return mesh, result_handle, {}

    width, segments, width_key, segment_key = _edge_treatment_geometry_parameters(treatments)
    details: dict[str, Any] = {
        "edge_treatment_geometry_attempted": bool(width > 0.0),
        "edge_treatment_geometry_applied": False,
        "edge_treatment_geometry_fallback": False,
        "edge_treatment_width_cm": float(width),
        "edge_treatment_segments": int(segments),
        "edge_treatment_width_source_parameter": width_key,
        "edge_treatment_segment_source_parameter": segment_key,
        "edge_treatment_source_face_count": len(mesh.faces),
        "edge_treatment_source_vertex_count": len(mesh.vertices),
        "edge_treatment_source_watertight": bool(mesh.is_watertight),
    }
    if width <= 0.0:
        details["edge_treatment_geometry_skip_reason"] = "missing_positive_width_cm"
        return mesh, result_handle, details
    details["edge_treatment_geometry_required_capabilities"] = ["from_trimesh"]

    source_metadata = dict(mesh.metadata) if isinstance(mesh.metadata, dict) else {}
    pending_polybevel = _dict_metadata(source_metadata.get("lathe_pending_polybevel_mesh"))
    general_bevel = _dict_metadata(source_metadata.get("lathe_general_mesh_bevel"))
    if bool(pending_polybevel.get("geometry_applied")) or general_bevel:
        applied_metadata = pending_polybevel or general_bevel
        details.update(
            {
                "edge_treatment_geometry_applied": True,
                "edge_treatment_geometry_already_applied": True,
                "edge_treatment_geometry_applied_during_import": True,
                "edge_treatment_geometry_skip_reason": "already_applied_during_kernel_import",
                "edge_treatment_geometry_method": str(
                    applied_metadata.get("method") or "imported_edge_treatment_geometry_v1"
                ),
                "edge_treatment_result_face_count": len(mesh.faces),
                "edge_treatment_result_vertex_count": len(mesh.vertices),
                "edge_treatment_result_watertight": bool(mesh.is_watertight),
            }
        )
        try:
            details["edge_treatment_result_body_count"] = int(kernel.body_count(result_handle))
        except (AttributeError, TypeError, ValueError, RuntimeError):
            details["edge_treatment_result_body_count"] = len(mesh.split(only_watertight=False))
        if pending_polybevel:
            details["pending_polybevel_mesh"] = _json_safe(pending_polybevel)
        if general_bevel:
            details["general_mesh_bevel"] = _json_safe(general_bevel)
        return mesh, result_handle, details

    try:
        from ..exact_solids import _general_mesh_bevel
    except (ImportError, AttributeError) as exc:
        details.update(
            {
                "edge_treatment_geometry_fallback": True,
                "edge_treatment_geometry_failure_type": type(exc).__name__,
                "edge_treatment_geometry_failure_reason": str(exc),
            }
        )
        return mesh, result_handle, details

    try:
        candidate = _general_mesh_bevel(mesh.copy(), width=width, segments=segments)
    except (TypeError, ValueError, RuntimeError, AttributeError, IndexError) as exc:
        details.update(
            {
                "edge_treatment_geometry_fallback": True,
                "edge_treatment_geometry_failure_type": type(exc).__name__,
                "edge_treatment_geometry_failure_reason": str(exc),
            }
        )
        return mesh, result_handle, details
    if not isinstance(candidate, trimesh.Trimesh) or len(candidate.faces) == 0:
        details.update(
            {
                "edge_treatment_geometry_fallback": True,
                "edge_treatment_geometry_failure_reason": "empty_or_non_mesh_result",
            }
        )
        return mesh, result_handle, details

    if source_metadata:
        candidate.metadata = {**source_metadata, **dict(candidate.metadata or {})}
    bevel_metadata = _dict_metadata(candidate.metadata.get("lathe_general_mesh_bevel"))
    changed = _mesh_vertices_changed(mesh, candidate)
    if not changed and not bevel_metadata:
        details.update(
            {
                "edge_treatment_geometry_fallback": True,
                "edge_treatment_geometry_failure_reason": "general_mesh_bevel_returned_source_mesh",
            }
        )
        return mesh, result_handle, details

    try:
        treated_handle = kernel.from_trimesh(candidate)
    except (AttributeError, TypeError, ValueError, RuntimeError, OSError) as exc:
        details.update(
            {
                "edge_treatment_geometry_fallback": True,
                "edge_treatment_geometry_failure_type": type(exc).__name__,
                "edge_treatment_geometry_failure_reason": str(exc),
                "edge_treatment_candidate_face_count": len(candidate.faces),
                "edge_treatment_candidate_vertex_count": len(candidate.vertices),
            }
        )
        return mesh, result_handle, details

    try:
        result_body_count = kernel.body_count(treated_handle)
    except (AttributeError, TypeError, ValueError, RuntimeError):
        result_body_count = len(candidate.split(only_watertight=False))
    details.update(
        {
            "edge_treatment_geometry_applied": True,
            "edge_treatment_geometry_method": str(
                bevel_metadata.get("method") or "general_mesh_bevel_changed_mesh_v1"
            ),
            "edge_treatment_result_face_count": len(candidate.faces),
            "edge_treatment_result_vertex_count": len(candidate.vertices),
            "edge_treatment_result_watertight": bool(candidate.is_watertight),
            "edge_treatment_result_body_count": int(result_body_count),
        }
    )
    if bevel_metadata:
        details["general_mesh_bevel"] = _json_safe(bevel_metadata)
    return candidate, treated_handle, details


def _kernel_edge_treatment_metadata(
    kernel: GeometryKernel,
    mesh: trimesh.Trimesh,
    result_handle: Any,
    operands: list[KernelOperand],
    *,
    semantic_operation: str = "",
    method_suffix: str,
    fallback: bool = False,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    treatments = _kernel_edge_treatment_payloads(operands)
    operation_kind = _EDGE_TREATMENT_OPERATION_KINDS.get(semantic_operation)
    if not treatments and operation_kind:
        source = operands[0] if operands else None
        treatments.append(
            {
                "operand_id": source.operand_id if source is not None else "",
                "part": source.part if source is not None and source.part else "",
                "component": str(_dict_metadata(source.metadata).get("component") or "")
                if source is not None
                else "",
                "region": str(_dict_metadata(source.metadata).get("region") or "")
                if source is not None
                else "",
                "primitive_type": (
                    source.primitive_type
                    if source is not None and source.primitive_type
                    else ""
                ),
                "operation": semantic_operation,
                "treatment_kind": operation_kind,
                "modifier_name": "",
                "edge_treatment_payload": {},
            }
        )
    elif treatments and operation_kind:
        treatments = [
            {
                **dict(treatment),
                "operation": semantic_operation,
                "treatment_kind": operation_kind,
            }
            for treatment in treatments
        ]
    if not treatments:
        return {}

    primary = treatments[0]
    treatment_kinds = sorted(
        {str(treatment.get("treatment_kind") or "") for treatment in treatments}
    )
    treatment_kind = (
        str(primary.get("treatment_kind") or "edge_treatment")
        if len(treatment_kinds) == 1
        else "mixed_edge_treatment"
    )
    try:
        result_body_count = kernel.body_count(result_handle)
    except (AttributeError, TypeError, ValueError, RuntimeError):
        result_body_count = len(mesh.split(only_watertight=False))
    operation = semantic_operation or str(primary.get("operation") or "edge.treatment")
    payload: dict[str, Any] = {
        "schema": "lathe.geometry.kernel_edge_treatment.v1",
        "operation": operation,
        "treatment_kind": treatment_kind,
        "treatment_kinds": treatment_kinds,
        "edge_treatment_count": len(treatments),
        "treatments": _json_safe(treatments),
        "method": f"{treatment_kind}_{method_suffix}",
        "attempted_backend": kernel.name,
        "actual_backend": kernel.name,
        "attempted_kernel": kernel.name,
        "actual_kernel": kernel.name,
        "actual_operation": operation,
        "fallback": bool(fallback),
        "passthrough": False,
        "result_face_count": len(mesh.faces),
        "result_vertex_count": len(mesh.vertices),
        "result_body_count": int(result_body_count),
        "result_watertight": bool(mesh.is_watertight),
    }
    if extra:
        payload.update(_json_safe(extra))
    return payload


def _kernel_surface_damage_payloads(operands: list[KernelOperand]) -> list[dict[str, Any]]:
    damages: list[dict[str, Any]] = []
    for operand in operands:
        metadata = _dict_metadata(operand.metadata)
        semantic_metadata = _dict_metadata(metadata.get("semantic_metadata"))
        v2_metadata = _dict_metadata(semantic_metadata.get("shape_ir_v2"))
        operation = str(
            v2_metadata.get("v2_op")
            or semantic_metadata.get("operation")
            or ""
        )
        for modifier_name, damage_kind in _SURFACE_DAMAGE_MODIFIER_KINDS.items():
            payload = _kernel_modifier_payload(metadata, modifier_name)
            if not payload:
                continue
            payload_operation = _modifier_payload_operation(
                modifier_name,
                payload,
                base_operation=operation,
            )
            damages.append(
                {
                    "operand_id": operand.operand_id,
                    "part": operand.part or "",
                    "primitive_type": operand.primitive_type or "",
                    "operation": payload_operation,
                    "damage_kind": damage_kind,
                    "modifier_name": modifier_name,
                    "damage_payload": _json_safe(payload),
                }
            )
    return damages


def _kernel_surface_damage_metadata(
    kernel: GeometryKernel,
    mesh: trimesh.Trimesh,
    result_handle: Any,
    operands: list[KernelOperand],
    *,
    semantic_operation: str = "",
    method_suffix: str,
    fallback: bool = False,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    damages = _kernel_surface_damage_payloads(operands)
    operation_kind = _SURFACE_DAMAGE_OPERATION_KINDS.get(semantic_operation)
    if not damages and operation_kind:
        source = operands[0] if operands else None
        damages.append(
            {
                "operand_id": source.operand_id if source is not None else "",
                "part": source.part if source is not None and source.part else "",
                "primitive_type": (
                    source.primitive_type
                    if source is not None and source.primitive_type
                    else ""
                ),
                "operation": semantic_operation,
                "damage_kind": operation_kind,
                "modifier_name": "",
                "damage_payload": {},
            }
        )
    if not damages:
        return {}

    primary = damages[0]
    damage_kinds = sorted({str(damage.get("damage_kind") or "") for damage in damages})
    damage_kind = (
        str(primary.get("damage_kind") or "surface_damage")
        if len(damage_kinds) == 1
        else "mixed_surface_damage"
    )
    try:
        result_body_count = kernel.body_count(result_handle)
    except (AttributeError, TypeError, ValueError, RuntimeError):
        result_body_count = len(mesh.split(only_watertight=False))
    operation = semantic_operation or str(primary.get("operation") or "surface.damage")
    payload: dict[str, Any] = {
        "schema": "lathe.geometry.kernel_surface_damage.v1",
        "operation": operation,
        "damage_kind": damage_kind,
        "damage_kinds": damage_kinds,
        "damage_count": len(damages),
        "damages": _json_safe(damages),
        "method": f"{damage_kind}_{method_suffix}",
        "attempted_backend": kernel.name,
        "actual_backend": kernel.name,
        "attempted_kernel": kernel.name,
        "actual_kernel": kernel.name,
        "actual_operation": operation,
        "fallback": bool(fallback),
        "passthrough": False,
        "result_face_count": len(mesh.faces),
        "result_vertex_count": len(mesh.vertices),
        "result_body_count": int(result_body_count),
        "result_watertight": bool(mesh.is_watertight),
    }
    if extra:
        payload.update(_json_safe(extra))
    return payload


def _kernel_feature_detail_metadata(
    kernel: GeometryKernel,
    mesh: trimesh.Trimesh,
    result_handle: Any,
    operands: list[KernelOperand],
    *,
    semantic_operation: str = "",
    method_suffix: str,
    fallback: bool = False,
    face_operation_attributed: bool | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    features = _kernel_feature_detail_payloads(operands)
    operation_kind = _FEATURE_DETAIL_OPERATION_KINDS.get(semantic_operation)
    if not features and operation_kind:
        source = operands[0] if operands else None
        features.append(
            {
                "operand_id": source.operand_id if source is not None else "",
                "part": source.part if source is not None and source.part else "",
                "primitive_type": (
                    source.primitive_type
                    if source is not None and source.primitive_type
                    else ""
                ),
                "operation": semantic_operation,
                "feature_kind": operation_kind,
                "modifier_name": "",
                "feature_payload": {},
            }
        )
    if not features:
        return {}

    primary = features[0]
    feature_kinds = sorted({str(feature.get("feature_kind") or "") for feature in features})
    feature_kind = (
        str(primary.get("feature_kind") or "feature_detail")
        if len(feature_kinds) == 1
        else "mixed_feature_detail"
    )
    try:
        result_body_count = kernel.body_count(result_handle)
    except (AttributeError, TypeError, ValueError, RuntimeError):
        result_body_count = len(mesh.split(only_watertight=False))
    operation = semantic_operation or str(primary.get("operation") or "feature.detail")
    feature_payloads = [
        _dict_metadata(feature.get("feature_payload"))
        for feature in features
        if isinstance(feature, dict)
    ]
    feature_methods = sorted(
        {
            str(payload.get("actual_method") or payload.get("method") or "")
            for payload in feature_payloads
            if str(payload.get("actual_method") or payload.get("method") or "")
        }
    )
    feature_geometry_backends = sorted(
        {
            str(
                payload.get("actual_geometry_backend")
                or payload.get("geometry_backend")
                or ""
            )
            for payload in feature_payloads
            if str(
                payload.get("actual_geometry_backend")
                or payload.get("geometry_backend")
                or ""
            )
        }
    )
    payload: dict[str, Any] = {
        "schema": "lathe.geometry.kernel_feature_detail.v1",
        "operation": operation,
        "feature_kind": feature_kind,
        "feature_kinds": feature_kinds,
        "feature_count": len(features),
        "features": _json_safe(features),
        "method": f"{feature_kind}_{method_suffix}",
        "attempted_backend": kernel.name,
        "actual_backend": kernel.name,
        "attempted_kernel": kernel.name,
        "actual_kernel": kernel.name,
        "actual_operation": operation,
        "fallback": bool(fallback),
        "passthrough": False,
        "result_face_count": len(mesh.faces),
        "result_vertex_count": len(mesh.vertices),
        "result_body_count": int(result_body_count),
        "result_watertight": bool(mesh.is_watertight),
    }
    if feature_methods:
        payload["feature_methods"] = feature_methods
        if len(feature_methods) == 1:
            payload["actual_method"] = feature_methods[0]
    if feature_geometry_backends:
        payload["feature_actual_geometry_backends"] = feature_geometry_backends
        if len(feature_geometry_backends) == 1:
            payload["actual_geometry_backend"] = feature_geometry_backends[0]
    if face_operation_attributed is not None:
        payload["face_operation_attributed"] = bool(face_operation_attributed)
    if extra:
        payload.update(_json_safe(extra))
    return payload


def execute_import_program(
    kernel: GeometryKernel,
    source: KernelOperand,
    *,
    semantic_operation: str = "shape.import",
    operation_limit: int | None = None,
    route: str = "import_program",
    backend: str | None = None,
) -> KernelProgramResult:
    """Expose a single imported operand as a traced KernelProgram result."""
    if source.handle is None:
        raise ValueError(f"kernel import source operand {source.operand_id!r} has no handle")
    operation_count = import_operation_count(source)
    if operation_limit is not None and operation_count > operation_limit:
        raise ValueError(
            f"kernel import operation_count={operation_count} exceeds limit={operation_limit}"
        )
    capabilities = _kernel_capabilities(kernel)
    required = set(_import_required_capabilities(source, semantic_operation))
    _require_capabilities(kernel, capabilities, required)
    manifest = build_import_program_manifest(
        source,
        semantic_operation=semantic_operation,
        route=route,
        backend=backend,
        operation_limit=operation_limit,
    )
    result_handle = source.handle
    mesh = _non_empty_mesh(kernel, result_handle)
    mesh, result_handle, edge_treatment_geometry = _apply_import_edge_treatment_geometry(
        kernel,
        mesh,
        result_handle,
        [source],
        semantic_operation=semantic_operation,
    )
    operation_records = _semantic_operation_records_from_manifest(manifest)
    final_operation_record = _final_semantic_operation_record(
        operation_records,
        semantic_operation,
    )
    operation_record = {
        "op": "import",
        "source": source.operand_id,
        "attempted_kernel": kernel.name,
        "actual_kernel": kernel.name,
        "semantic_operation": semantic_operation,
        "primitive_type": source.primitive_type,
        "part": source.part,
        "result_face_count": len(mesh.faces),
        "result_vertex_count": len(mesh.vertices),
        "result_watertight": bool(mesh.is_watertight),
        "result_body_count": kernel.body_count(result_handle),
    }
    if final_operation_record:
        operation_record["semantic_operation_record"] = dict(final_operation_record)
    if edge_treatment_geometry:
        operation_record["kernel_edge_treatment_geometry"] = dict(edge_treatment_geometry)
    kernel_import = _dict_metadata(_dict_metadata(source.metadata).get("kernel_import"))
    if kernel_import:
        kernel_import_stats: dict[str, Any] = {}
        _copy_kernel_import_stats(kernel_import_stats, kernel_import)
        operation_record["import_route"] = str(kernel_import.get("route") or "")
        operation_record["import_primitive_type"] = str(kernel_import.get("primitive_type") or "")
        operation_record["attempted_backend"] = str(kernel_import.get("route") or "")
        operation_record["actual_backend"] = str(kernel_import.get("backend") or "")
        operation_record["actual_operation"] = str(
            kernel_import.get("method")
            or kernel_import.get("route")
            or "kernel_import"
        )
        operation_record.update(kernel_import_stats)
    face_operation_id = source.operand_id
    if final_operation_record:
        face_operation_id = str(final_operation_record.get("operation_id") or face_operation_id)
    elif operation_records:
        face_operation_id = str(operation_records[0].get("operation_id") or face_operation_id)
    (
        face_operation_ids,
        face_operation_summary,
        face_operation_attribution,
    ) = _attach_direct_face_operation_metadata(
        mesh,
        face_operation_id,
        source="kernel_program.import.source_operand",
        method="imported_source_face_ranges",
    )
    edge_control_kind, edge_control_payload = _kernel_edge_control_source_payload(source)
    kernel_edge_control: dict[str, Any] = {}
    if semantic_operation in {"op.weighted_normals", "op.mark_hard_edge"} or edge_control_kind:
        edge_control_kind = edge_control_kind or (
            "weighted_normals"
            if semantic_operation == "op.weighted_normals"
            else "mark_hard_edge"
        )
        kernel_edge_control = {
            "schema": "lathe.geometry.kernel_edge_control.v1",
            "operation": semantic_operation,
            "edge_control_kind": edge_control_kind,
            "method": f"{edge_control_kind}_source_preserving_kernel_program_v1",
            "attempted_backend": kernel.name,
            "actual_backend": kernel.name,
            "attempted_kernel": kernel.name,
            "actual_kernel": kernel.name,
            "actual_operation": semantic_operation,
            "fallback": False,
            "passthrough": False,
            "source_operand_id": source.operand_id,
            "source_part": source.part or "",
            "source_primitive_type": source.primitive_type or "",
            "edge_control_payload": _json_safe(edge_control_payload),
            "result_face_count": len(mesh.faces),
            "result_vertex_count": len(mesh.vertices),
            "result_body_count": kernel.body_count(result_handle),
            "result_watertight": bool(mesh.is_watertight),
            "face_operation_attributed": bool(face_operation_ids),
        }
        mesh.metadata["lathe_kernel_edge_control"] = dict(kernel_edge_control)
    kernel_edge_treatment = _kernel_edge_treatment_metadata(
        kernel,
        mesh,
        result_handle,
        [source],
        semantic_operation=semantic_operation,
        method_suffix="source_preserving_kernel_program_v1",
        fallback=bool(edge_treatment_geometry.get("edge_treatment_geometry_fallback")),
        extra={
            "face_operation_attributed": bool(face_operation_ids),
            **edge_treatment_geometry,
        },
    )
    if kernel_edge_treatment:
        mesh.metadata["lathe_kernel_edge_treatment"] = dict(kernel_edge_treatment)
        operation_record["kernel_edge_treatment"] = dict(kernel_edge_treatment)
    kernel_feature_detail = _kernel_feature_detail_metadata(
        kernel,
        mesh,
        result_handle,
        [source],
        semantic_operation=semantic_operation,
        method_suffix="source_preserving_kernel_program_v1",
        face_operation_attributed=bool(face_operation_ids),
    )
    if kernel_feature_detail:
        mesh.metadata["lathe_kernel_feature_detail"] = dict(kernel_feature_detail)
    kernel_surface_damage = _kernel_surface_damage_metadata(
        kernel,
        mesh,
        result_handle,
        [source],
        semantic_operation=semantic_operation,
        method_suffix="source_preserving_kernel_program_v1",
        extra={"face_operation_attributed": bool(face_operation_ids)},
    )
    if kernel_surface_damage:
        mesh.metadata["lathe_kernel_surface_damage"] = dict(kernel_surface_damage)
    semantic_handoff = _attach_kernel_program_semantic_handoff(
        mesh,
        [source],
        [operation_record],
    )
    details = {
        "kernel_program_version": KERNEL_PROGRAM_VERSION,
        "kernel_program_route": route,
        "kernel_program_operation_count": operation_count,
        "kernel_program_operand_count": 1,
        "kernel_program_semantic_operation_record_count": len(operation_records),
        "kernel_program_semantic_operation_counts": _operation_counts(operation_records),
        "kernel_program_semantic_operation_records": operation_records,
        "kernel_program_kernel": kernel.name,
        "kernel_program_backend": backend,
        "kernel_program_manifest": manifest,
        "kernel_program_capabilities_checked": sorted(required),
        "kernel_program_watertight": kernel.is_watertight(result_handle),
        "kernel_program_body_count": kernel.body_count(result_handle),
        "kernel_program_operands": [source.trace_record()],
        "kernel_program_operations": [operation_record],
        "kernel_program_face_operation_attribution": face_operation_attribution,
        "face_operation_ids": face_operation_ids,
        "face_operation_summary": face_operation_summary,
        "kernel_program_import_source_operand_id": source.operand_id,
        "import_semantic_operation": semantic_operation,
        "kernel_edge_control": kernel_edge_control,
        "kernel_program_edge_control": kernel_edge_control,
        "kernel_edge_treatment": kernel_edge_treatment,
        "kernel_program_edge_treatment": kernel_edge_treatment,
        "kernel_edge_treatment_geometry": edge_treatment_geometry,
        "kernel_program_edge_treatment_geometry": edge_treatment_geometry,
        "kernel_feature_detail": kernel_feature_detail,
        "kernel_program_feature_detail": kernel_feature_detail,
        "kernel_surface_damage": kernel_surface_damage,
        "kernel_program_surface_damage": kernel_surface_damage,
        "kernel_program_semantic_handoff": semantic_handoff,
    }
    return KernelProgramResult(
        mesh=mesh,
        handle=result_handle,
        operation_count=operation_count,
        details=details,
    )


def execute_instances_program(
    kernel: GeometryKernel,
    source: KernelOperand,
    *,
    matrices: list[list[list[float]]],
    semantic_operation: str = "sop.copy_to_points",
    instance_pattern: str | None = None,
    instance_pattern_payload: dict[str, Any] | None = None,
    operation_limit: int | None = None,
    route: str = "instances_program",
    backend: str | None = None,
) -> KernelProgramResult:
    """Execute repeated transformed instances of one source operand."""
    transform_matrices = _validated_transform_matrices(matrices)
    _validate_transform_operand(source)
    operation_count = instances_operation_count(source, transform_matrices)
    if operation_limit is not None and operation_count > operation_limit:
        raise ValueError(
            f"kernel instances operation_count={operation_count} exceeds limit={operation_limit}"
        )
    capabilities = _kernel_capabilities(kernel)
    batch_union = getattr(kernel, "batch_union", None)
    batch_union_available = (
        len(transform_matrices) > 1
        and capabilities.get("batch_union") is True
        and callable(batch_union)
    )
    required = {"transform", "to_trimesh", "from_trimesh"}
    if len(transform_matrices) > 1:
        required.add("batch_union" if batch_union_available else "union")
    _require_capabilities(kernel, capabilities, required)
    transform = getattr(kernel, "transform", None)
    if not callable(transform):
        raise ValueError(f"geometry kernel {kernel.name!r} does not implement transform")
    manifest = build_instances_program_manifest(
        source,
        matrices=transform_matrices,
        semantic_operation=semantic_operation,
        route=route,
        backend=backend,
        operation_limit=operation_limit,
        batch_union_available=batch_union_available,
    )

    trace_operations: list[dict[str, Any]] = []
    transformed_handles: list[Any] = []
    transformed_ids: list[str] = []
    for index, matrix in enumerate(transform_matrices):
        handle = transform(source.handle, matrix)
        record = {
            "op": "transform",
            "source": source.operand_id,
            "instance_id": f"{source.operand_id}.instance_{index:04d}",
            "instance_index": index,
            "attempted_kernel": kernel.name,
            "actual_kernel": kernel.name,
            "matrix": matrix,
        }
        _record_result_probe(record, kernel=kernel, result_handle=handle)
        trace_operations.append(record)
        transformed_handles.append(handle)
        transformed_ids.append(str(record["instance_id"]))

    if not transformed_handles:
        raise ValueError("kernel instances program produced no instance handles")
    if len(transformed_handles) == 1:
        current = transformed_handles[0]
        current_id = transformed_ids[0]
    elif batch_union_available:
        record = {
            "op": "batch_union",
            "inputs": list(transformed_ids),
            "actual_kernel": kernel.name,
            "semantic_equivalent_operation_count": len(transformed_handles) - 1,
        }
        current = batch_union(transformed_handles)
        _record_result_probe(record, kernel=kernel, result_handle=current)
        trace_operations.append(record)
        current_id = f"batch_union({','.join(transformed_ids)})"
    else:
        current = transformed_handles[0]
        current_id = transformed_ids[0]
        for index, handle in enumerate(transformed_handles[1:], start=1):
            record = _operation_record(
                op="union",
                left=current_id,
                right=transformed_ids[index],
                kernel=kernel,
            )
            previous = current
            current = kernel.union(previous, handle)
            _record_operation_result(record, kernel=kernel, result_handle=current, left_handle=previous)
            trace_operations.append(record)
            current_id = f"union({current_id},{transformed_ids[index]})"

    mesh = _non_empty_mesh(kernel, current)
    attempted_result_face_count = len(mesh.faces)
    transformed_meshes = [_non_empty_mesh(kernel, handle) for handle in transformed_handles]
    instance_operands: list[KernelOperand] = []
    source_metadata = _dict_metadata(source.metadata)
    for index, (handle, instance_mesh) in enumerate(zip(transformed_handles, transformed_meshes)):
        try:
            instance_body_count = kernel.body_count(handle)
        except (AttributeError, TypeError, ValueError, RuntimeError):
            instance_body_count = len(instance_mesh.split(only_watertight=False))
        instance_metadata = dict(source_metadata)
        instance_metadata.update(
            {
                "source_operand_id": source.operand_id,
                "instance_index": index,
                "instance_id": transformed_ids[index],
                "instance_matrix": transform_matrices[index],
            }
        )
        instance_operands.append(
            KernelOperand(
                operand_id=transformed_ids[index],
                handle=handle,
                source_mesh=instance_mesh,
                blend_mode=source.blend_mode,
                part=source.part,
                primitive_type=source.primitive_type,
                source_index=source.source_index,
                tags=source.tags,
                source_mesh_face_count=len(instance_mesh.faces),
                source_mesh_watertight=bool(instance_mesh.is_watertight),
                source_mesh_body_count=int(instance_body_count),
                source_mesh_repaired=source.source_mesh_repaired,
                metadata=instance_metadata,
            )
        )
    expected_disjoint_groups = _disjoint_mesh_group_count(transformed_meshes)
    attempted_result_body_count = kernel.body_count(current)
    attempted_batch_union = _dict_metadata(mesh.metadata.get("lathe_reference_batch_union"))
    attempted_batch_union_method = str(attempted_batch_union.get("method") or "")
    disjoint_instances_preserve_face_ranges = (
        len(transformed_meshes) > 1
        and expected_disjoint_groups == len(transformed_meshes)
        and "mesh_concatenation" not in attempted_batch_union_method
    )
    visible_preservation_fallback: dict[str, Any] | None = None
    if (
        len(transformed_meshes) > 1
        and expected_disjoint_groups > 1
        and (
            attempted_result_body_count < expected_disjoint_groups
            or disjoint_instances_preserve_face_ranges
        )
    ):
        if attempted_result_body_count < expected_disjoint_groups:
            preservation_reason = "kernel_instance_union_collapsed_disjoint_instances"
        else:
            preservation_reason = "kernel_instance_union_lacked_direct_disjoint_face_ranges"
        preserved_mesh = trimesh.util.concatenate([mesh.copy() for mesh in transformed_meshes])
        preserved_mesh.remove_unreferenced_vertices()
        preserved_mesh.fix_normals()
        current = kernel.from_trimesh(preserved_mesh)
        mesh = preserved_mesh
        current_id = f"visible_mesh_concatenation({','.join(transformed_ids)})"
        visible_preservation_fallback = {
            "schema": "lathe.geometry.instances_visible_preservation_fallback.v1",
            "reason": preservation_reason,
            "attempted_body_count": int(attempted_result_body_count),
            "expected_disjoint_group_count": int(expected_disjoint_groups),
            "instance_count": len(transformed_meshes),
            "attempted_face_count": attempted_result_face_count,
            "preserved_face_count": len(mesh.faces),
            "preserved_body_count": kernel.body_count(current),
            "actual_method": "visible_mesh_concatenation_import",
            "attempted_batch_union_method": attempted_batch_union_method,
        }
        trace_operations.append(
            {
                "op": "visible_mesh_concatenation_import",
                "inputs": list(transformed_ids),
                "actual_kernel": kernel.name,
                "reason": visible_preservation_fallback["reason"],
                "expected_disjoint_group_count": expected_disjoint_groups,
                "result_face_count": len(mesh.faces),
                "result_watertight": bool(mesh.is_watertight),
                "result_body_count": kernel.body_count(current),
                "kernel_fallback": dict(visible_preservation_fallback),
                "passthrough_fallback_suspected": False,
            }
        )
    operation_records = _semantic_operation_records_from_manifest(manifest)
    final_operation_record = _final_semantic_operation_record(
        operation_records,
        semantic_operation,
    )
    fallback_records = [
        dict(record)
        for record in trace_operations
        if isinstance(record.get("kernel_fallback"), dict)
        or bool(record.get("passthrough_fallback_suspected"))
    ]
    batch_union_record = next(
        (
            record
            for record in reversed(trace_operations)
            if record.get("op") == "batch_union"
        ),
        {},
    )
    batch_union_metadata = _dict_metadata(batch_union_record.get("kernel_batch_union"))
    if visible_preservation_fallback is not None:
        assembly_method = "visible_mesh_concatenation_import"
    elif batch_union_metadata:
        assembly_method = str(batch_union_metadata.get("method") or "batch_union")
    elif len(transformed_handles) == 1:
        assembly_method = "single_transform"
    elif batch_union_available:
        assembly_method = "batch_union"
    else:
        assembly_method = "pairwise_union"
    result_body_count = kernel.body_count(current)
    face_operation_ids = _instance_face_operation_ids(
        instance_operands,
        transformed_meshes,
        mesh,
        assembly_method=assembly_method,
    )
    face_operation_summary: dict[str, Any] = {}
    face_operation_attribution = {
        "schema": "lathe.geometry.kernel_program_face_operation_attribution.v1",
        "source": "kernel_program.instances",
        "attributed": bool(face_operation_ids),
        "assembly_method": assembly_method,
        "instance_count": len(instance_operands),
        "result_face_count": len(mesh.faces),
    }
    if face_operation_ids:
        face_operation_summary = _kernel_program_face_operation_summary(
            face_operation_ids,
            source="kernel_program.instances.instance_operands",
        )
        face_operation_attribution.update(
            {
                "method": "concatenated_instance_face_ranges",
                "face_operation_count": len(set(face_operation_ids)),
                "face_operation_attribution_count": len(face_operation_ids),
            }
        )
        mesh.metadata["face_operation_ids"] = list(face_operation_ids)
        mesh.metadata["face_operation_summary"] = dict(face_operation_summary)
    else:
        face_operation_attribution["reason"] = (
            "kernel_result_faces_not_a_direct_instance_concatenation"
        )
    mesh.metadata["lathe_kernel_program_face_operation_attribution"] = dict(
        face_operation_attribution
    )
    source_face_operation_summary = dict(face_operation_summary)
    source_face_operation_attribution = dict(face_operation_attribution)
    if source_face_operation_summary:
        mesh.metadata["source_face_operation_summary"] = dict(source_face_operation_summary)
        mesh.metadata["lathe_kernel_program_source_face_operation_attribution"] = dict(
            source_face_operation_attribution
        )
    if final_operation_record:
        final_operation_id = str(final_operation_record.get("operation_id") or "")
        if final_operation_id:
            (
                face_operation_ids,
                face_operation_summary,
                face_operation_attribution,
            ) = _attach_whole_result_face_operation_metadata(
                mesh,
                final_operation_id,
                source="kernel_program.instances.whole_result_semantic_operation",
                method="whole_result_instances_semantic_operation_range",
                reason="instances_preserve_source_face_ranges_separately",
                source_face_ranges_preserved=bool(source_face_operation_summary),
                extra={
                    "source_face_operation_summary": source_face_operation_summary,
                    "source_face_operation_attribution": source_face_operation_attribution,
                },
            )
    scatter_kind, scatter_payload = _kernel_scatter_source_payload(source)
    kernel_scatter: dict[str, Any] = {}
    if semantic_operation in {"sop.copy_to_points", "sop.scatter_on_surface"} or scatter_kind:
        scatter_kind = scatter_kind or (
            "surface_scatter"
            if semantic_operation == "sop.scatter_on_surface"
            else "point_scatter"
        )
        kernel_scatter = {
            "schema": "lathe.geometry.kernel_scatter.v1",
            "operation": semantic_operation,
            "scatter_kind": scatter_kind,
            "method": f"{scatter_kind}_instances_kernel_program_v1",
            "attempted_backend": kernel.name,
            "actual_backend": kernel.name,
            "attempted_kernel": kernel.name,
            "actual_kernel": kernel.name,
            "actual_operation": semantic_operation,
            "fallback": visible_preservation_fallback is not None,
            "passthrough": False,
            "instance_count": len(transform_matrices),
            "source_operand_id": source.operand_id,
            "source_part": source.part or "",
            "source_primitive_type": source.primitive_type or "",
            "source_scatter_payload": _json_safe(scatter_payload),
            "batch_union": bool(batch_union_available),
            "actual_assembly_method": assembly_method,
            "expected_disjoint_group_count": int(expected_disjoint_groups),
            "attempted_body_count": int(attempted_result_body_count),
            "result_face_count": len(mesh.faces),
            "result_vertex_count": len(mesh.vertices),
            "result_body_count": int(result_body_count),
            "result_watertight": bool(mesh.is_watertight),
            "face_operation_attributed": bool(face_operation_ids),
        }
        for key in (
            "point_count",
            "emitted_count",
            "density_per_m2",
            "surface_area_m2",
            "seed",
            "jitter_cm",
            "orientation_mode",
            "orientation_applied",
            "align_to_normal",
            "surface_anchor",
            "target",
            "target_part",
            "target_primitive_type",
            "source_context_record_count",
            "source_context_parts",
            "source_context_primitive_types",
            "source_parts",
            "source_primitive_types",
            "template_primitive_type",
            "template_primitive_count",
            "template_part",
        ):
            if key in scatter_payload:
                kernel_scatter[key] = _json_safe(scatter_payload[key])
        mesh.metadata["lathe_kernel_scatter"] = dict(kernel_scatter)
    pattern_kind, pattern_payload = _kernel_pattern_instance_source_payload(source)
    explicit_pattern_payload = (
        dict(instance_pattern_payload)
        if isinstance(instance_pattern_payload, dict)
        else {}
    )
    if explicit_pattern_payload:
        pattern_payload = explicit_pattern_payload
    pattern_kind = str(instance_pattern or pattern_kind or "").strip()
    if not pattern_kind:
        pattern_kind = _PATTERN_INSTANCE_OPERATION_KINDS.get(semantic_operation, "")
    kernel_pattern_instances: dict[str, Any] = {}
    if pattern_kind:
        kernel_pattern_instances = {
            "schema": "lathe.geometry.kernel_pattern_instances.v1",
            "operation": semantic_operation,
            "pattern_kind": pattern_kind,
            "method": f"{pattern_kind}_pattern_instances_kernel_program_v1",
            "attempted_backend": kernel.name,
            "actual_backend": kernel.name,
            "attempted_kernel": kernel.name,
            "actual_kernel": kernel.name,
            "actual_operation": semantic_operation,
            "fallback": visible_preservation_fallback is not None,
            "passthrough": False,
            "instance_count": len(transform_matrices),
            "source_operand_id": source.operand_id,
            "source_part": source.part or "",
            "source_primitive_type": source.primitive_type or "",
            "pattern_payload": _json_safe(pattern_payload),
            "batch_union": bool(batch_union_available),
            "actual_assembly_method": assembly_method,
            "expected_disjoint_group_count": int(expected_disjoint_groups),
            "attempted_body_count": int(attempted_result_body_count),
            "result_face_count": len(mesh.faces),
            "result_vertex_count": len(mesh.vertices),
            "result_body_count": int(result_body_count),
            "result_watertight": bool(mesh.is_watertight),
            "face_operation_attributed": bool(face_operation_ids),
        }
        for key in (
            "axis",
            "count",
            "spacing_cm",
            "pattern",
            "include_source",
            "origin_cm",
            "seed",
            "jitter_cm",
            "snap_to_grid_cm",
            "source_axis",
            "orientation_mode",
            "orientation_applied",
            "instance_transform_count",
            "instance_transform_record_count",
            "source_context_record_count",
            "source_context_parts",
            "source_context_primitive_types",
            "source_parts",
            "source_primitive_types",
            "template_part",
            "template_primitive_type",
            "template_primitive_count",
            "source_record_expansion_count",
            "source_record_expansion_route",
        ):
            if key in pattern_payload:
                kernel_pattern_instances[key] = _json_safe(pattern_payload[key])
        mesh.metadata["lathe_kernel_pattern_instances"] = dict(kernel_pattern_instances)
    kernel_feature_detail = _kernel_feature_detail_metadata(
        kernel,
        mesh,
        current,
        [source],
        semantic_operation=semantic_operation,
        method_suffix="instances_kernel_program_v1",
        fallback=visible_preservation_fallback is not None,
        face_operation_attributed=bool(face_operation_ids),
        extra={
            "instance_count": len(transform_matrices),
            "actual_assembly_method": assembly_method,
            "batch_union": bool(batch_union_available),
            "expected_disjoint_group_count": int(expected_disjoint_groups),
        },
    )
    if kernel_feature_detail:
        mesh.metadata["lathe_kernel_feature_detail"] = dict(kernel_feature_detail)
    runtime_diagnostics = _boolean_fallback_diagnostics(
        fallback_records,
        code="instances_boolean_csg_fallback",
    )
    manifest = _manifest_with_runtime_diagnostics(manifest, runtime_diagnostics)
    handoff_trace_operations = list(trace_operations)
    if final_operation_record:
        handoff_trace_operations.append(
            {
                "op": "instances_semantic_operation",
                "semantic_operation": semantic_operation,
                "semantic_operation_record": dict(final_operation_record),
            }
        )
    semantic_handoff = _attach_kernel_program_semantic_handoff(
        mesh,
        instance_operands,
        handoff_trace_operations,
    )
    details = {
        "kernel_program_version": KERNEL_PROGRAM_VERSION,
        "kernel_program_route": route,
        "kernel_program_operation_count": operation_count,
        "kernel_program_operand_count": 1,
        "kernel_program_semantic_operation_record_count": len(operation_records),
        "kernel_program_semantic_operation_counts": _operation_counts(operation_records),
        "kernel_program_semantic_operation_records": operation_records,
        "kernel_program_kernel": kernel.name,
        "kernel_program_backend": backend,
        "kernel_program_manifest": manifest,
        "kernel_program_diagnostics": list(manifest.get("diagnostics") or []),
        "kernel_program_capabilities_checked": sorted(required),
        "kernel_program_watertight": kernel.is_watertight(current),
        "kernel_program_body_count": result_body_count,
        "kernel_program_operands": [source.trace_record()],
        "kernel_program_instance_operands": [
            operand.trace_record() for operand in instance_operands
        ],
        "kernel_program_operations": trace_operations,
        "kernel_program_face_operation_attribution": face_operation_attribution,
        "face_operation_ids": face_operation_ids,
        "face_operation_summary": face_operation_summary,
        "source_face_operation_summary": source_face_operation_summary,
        "kernel_program_source_face_operation_attribution": source_face_operation_attribution,
        "kernel_program_instances_source_operand_id": source.operand_id,
        "instances_semantic_operation": semantic_operation,
        "instances_count": len(transform_matrices),
        "instances_semantic_operand_count": len(instance_operands),
        "instances_batch_union": bool(batch_union_available),
        "instances_batch_union_method": str(batch_union_metadata.get("method") or ""),
        "instances_batch_union_metadata": dict(batch_union_metadata),
        "instances_actual_assembly_method": assembly_method,
        "instances_expected_disjoint_group_count": int(expected_disjoint_groups),
        "instances_attempted_body_count": int(attempted_result_body_count),
        "instances_result_face_count": len(mesh.faces),
        "instances_result_body_count": int(result_body_count),
        "instances_result_watertight": bool(mesh.is_watertight),
        "instances_visible_preservation_fallback": visible_preservation_fallback,
        "instances_visible_preservation_fallback_applied": visible_preservation_fallback is not None,
        "instances_boolean_fallback_count": len(fallback_records),
        "instances_boolean_fallback_records": fallback_records,
        "kernel_scatter": kernel_scatter,
        "kernel_program_scatter": kernel_scatter,
        "kernel_pattern_instances": kernel_pattern_instances,
        "kernel_program_pattern_instances": kernel_pattern_instances,
        "kernel_feature_detail": kernel_feature_detail,
        "kernel_program_feature_detail": kernel_feature_detail,
        "kernel_program_semantic_handoff": semantic_handoff,
    }
    return KernelProgramResult(
        mesh=mesh,
        handle=current,
        operation_count=operation_count,
        details=details,
    )
