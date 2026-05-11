"""Kernel feature/edge/surface-damage payload + metadata builders.

This module groups the shared cluster of "modifier payload → trace
metadata" builders used by every per-op executor that touches feature
detail (hull, polyextrude, deform, refine, carve, instances, import).

Per the §5.3 decomposition, isolating these helpers keeps the per-op
modules thin and breaks an import cycle. Per-op modules import from
``_feature_detail``; ``_feature_detail`` imports from ``_records``,
``_serialize``, and ``..kernel``.

The exported surface:

  - Modifier-kind constants (``_FEATURE_DETAIL_MODIFIER_KINDS``,
    ``_FEATURE_DETAIL_OPERATION_KINDS``,
    ``_SURFACE_DAMAGE_MODIFIER_KINDS``,
    ``_SURFACE_DAMAGE_OPERATION_KINDS``,
    ``_EDGE_TREATMENT_OPERATION_KINDS``,
    ``_PATTERN_INSTANCE_MODIFIER_KINDS``,
    ``_PATTERN_INSTANCE_OPERATION_KINDS``).
  - ``_kernel_modifier_payload`` — fetch a single modifier payload.
  - ``_kernel_feature_detail_payloads`` — list every feature-detail
    payload an operand carries.
  - ``_kernel_edge_treatment_payloads`` — same for edge treatments.
  - ``_kernel_surface_damage_payloads`` — same for surface damage.
  - ``_kernel_edge_control_source_payload`` — single edge-control
    payload (weighted_normals or mark_hard_edge).
  - ``_kernel_feature_detail_metadata`` — build the
    ``lathe_kernel_feature_detail`` trace blob.
  - ``_kernel_edge_treatment_metadata`` — build the
    ``lathe_kernel_edge_treatment`` trace blob.
  - ``_kernel_surface_damage_metadata`` — build the
    ``lathe_kernel_surface_damage`` trace blob.
  - ``_edge_treatment_geometry_parameters`` — read width/segments
    from a list of edge-treatment payloads.
  - ``_apply_import_edge_treatment_geometry`` — apply edge-treatment
    geometry during an import-program execution.
  - ``_import_edge_treatment_requires_reimport`` — capability probe.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import trimesh

from ..kernel import GeometryKernel
from ._core import KernelOperand
from ._records import (
    _kernel_modifier_payload_containers,
    _modifier_payload_operation,
)
from ._serialize import _dict_metadata, _json_safe


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


def _kernel_modifier_payload(metadata: dict[str, Any], modifier_name: str) -> dict[str, Any]:
    """Return the first non-empty payload for ``modifier_name`` across all containers."""
    for container in _kernel_modifier_payload_containers(metadata):
        payload = _dict_metadata(container.get(modifier_name))
        if payload:
            return payload
    return {}


def _kernel_edge_control_source_payload(source: KernelOperand) -> tuple[str, dict[str, Any]]:
    """Return ``(kind, payload)`` for a single edge-control op (weighted_normals / mark_hard_edge)."""
    metadata = _dict_metadata(source.metadata)
    weighted = _kernel_modifier_payload(metadata, "v2_weighted_normals_modifier")
    if weighted:
        return "weighted_normals", weighted
    hard_edge = _kernel_modifier_payload(metadata, "v2_mark_hard_edge_modifier")
    if hard_edge:
        return "mark_hard_edge", hard_edge
    return "", {}


def _kernel_feature_detail_payloads(operands: list[KernelOperand]) -> list[dict[str, Any]]:
    """Return every feature-detail modifier payload across the operand list."""
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
    """Return every polybevel/edge-treatment modifier payload across the operand list."""
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


def _kernel_surface_damage_payloads(operands: list[KernelOperand]) -> list[dict[str, Any]]:
    """Return every surface-damage modifier payload across the operand list."""
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


def _first_numeric_payload_value(
    payload: dict[str, Any],
    keys: tuple[str, ...],
) -> tuple[float | None, str]:
    """Return the first finite-numeric payload value among ``keys``, plus its key name."""
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
    """Return the first integer payload value among ``keys``, plus its key name."""
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
    """Pick the largest width + segments across a list of edge-treatment payloads."""
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
    """Return True when the candidate's vertices / faces differ from the source's."""
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
    """Apply general_mesh_bevel for an import-program when edge treatment is requested.

    When the operands carry polybevel modifiers or the
    ``semantic_operation`` itself is an edge-treatment op, this helper
    runs the bevel geometry on the result mesh and returns the new
    handle plus diagnostic details. The original mesh/handle pass
    through unchanged when no edge treatment applies, when the bevel
    has zero width, or when the bevel was already applied during
    import.
    """
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
        from ...exact_solids import _general_mesh_bevel
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
    """Build the ``lathe_kernel_edge_treatment`` trace blob for a per-op result."""
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
    """Build the ``lathe_kernel_surface_damage`` trace blob for a per-op result."""
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
    """Build the ``lathe_kernel_feature_detail`` trace blob for a per-op result."""
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


def _import_edge_treatment_requires_reimport(
    source: KernelOperand,
    semantic_operation: str,
) -> bool:
    """Probe whether an import program needs the from_trimesh capability for edge treatment."""
    treatments = _kernel_edge_treatment_payloads([source])
    treatment_operation = _EDGE_TREATMENT_OPERATION_KINDS.get(semantic_operation)
    if not treatments and not treatment_operation:
        return False
    width, _, _, _ = _edge_treatment_geometry_parameters(treatments)
    return width > 0.0


__all__ = [
    "_EDGE_TREATMENT_OPERATION_KINDS",
    "_FEATURE_DETAIL_MODIFIER_KINDS",
    "_FEATURE_DETAIL_OPERATION_KINDS",
    "_PATTERN_INSTANCE_MODIFIER_KINDS",
    "_PATTERN_INSTANCE_OPERATION_KINDS",
    "_SURFACE_DAMAGE_MODIFIER_KINDS",
    "_SURFACE_DAMAGE_OPERATION_KINDS",
    "_apply_import_edge_treatment_geometry",
    "_edge_treatment_geometry_parameters",
    "_import_edge_treatment_requires_reimport",
    "_kernel_edge_control_source_payload",
    "_kernel_edge_treatment_metadata",
    "_kernel_edge_treatment_payloads",
    "_kernel_feature_detail_metadata",
    "_kernel_feature_detail_payloads",
    "_kernel_modifier_payload",
    "_kernel_surface_damage_metadata",
    "_kernel_surface_damage_payloads",
]
