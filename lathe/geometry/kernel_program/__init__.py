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
    _json_safe,
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
from ._common import (
    _attach_kernel_boolean_execution_metadata,
    _copy_kernel_import_stats,
    _finite_float,
    _non_empty_mesh,
    _operation_id_fragment,
    _operation_record,
    _record_operation_result,
    _record_result_probe,
    _sequence_count,
)
from ._face_operation import (
    _attach_direct_face_operation_metadata,
    _attach_semantic_whole_result_face_metadata,
    _attach_whole_result_face_operation_metadata,
    _copy_source_context_summary,
    _instance_face_operation_ids,
    _kernel_program_face_operation_summary,
    _metadata_list,
)
from ._primitive_metadata import (
    _axis_aligned_box_metadata,
    _axis_extruded_center_and_span,
    _axis_index,
    _axis_interval_center_and_span,
    _axis_name_from_index,
    _axis_span,
    _box_metadata_from_bounds,
    _capsule_metadata,
    _cylinder_metadata,
    _extruded_profile_metadata,
    _mesh_with_vertices,
    _numeric_pair,
    _numeric_triplet,
    _perpendicular_axis_indices,
    _positive_triplet,
    _profile_polygon_2d,
    _rotate_profile_polygon_2d,
    _sphere_metadata,
    _validated_deform_axis,
    _validated_origin,
)
from ._feature_detail import (
    _EDGE_TREATMENT_OPERATION_KINDS,
    _FEATURE_DETAIL_MODIFIER_KINDS,
    _FEATURE_DETAIL_OPERATION_KINDS,
    _PATTERN_INSTANCE_MODIFIER_KINDS,
    _PATTERN_INSTANCE_OPERATION_KINDS,
    _SURFACE_DAMAGE_MODIFIER_KINDS,
    _SURFACE_DAMAGE_OPERATION_KINDS,
    _apply_import_edge_treatment_geometry,
    _edge_treatment_geometry_parameters,
    _import_edge_treatment_requires_reimport,
    _kernel_edge_control_source_payload,
    _kernel_edge_treatment_metadata,
    _kernel_edge_treatment_payloads,
    _kernel_feature_detail_metadata,
    _kernel_feature_detail_payloads,
    _kernel_modifier_payload,
    _kernel_surface_damage_metadata,
    _kernel_surface_damage_payloads,
)
from ._records import (
    _MODIFIER_OPERATION_DEFAULTS,
    _kernel_modifier_payload_containers,
    _modifier_operation_default,
    _modifier_payload_operation,
    _operand_modifier_payloads,
    _operand_operation_records,
    _operand_semantic_records,
    _shape_record_operation,
    _shape_record_operation_records,
    _shape_record_v2_metadata,
)
from ._semantic import (
    _dedupe_operation_records,
    _final_semantic_operation_face_id,
    _final_semantic_operation_record,
    _operation_counts,
    _semantic_operation_for_kind,
    _semantic_operation_records_from_manifest,
    _trace_semantic_operation_records,
)
from ._semantic_handoff import (
    _attach_kernel_program_semantic_handoff,
    _kernel_program_semantic_handoff,
    _sdf_lineage_stats,
)
from .boolean import (
    _MESH_TO_LEVELSET_METHODS,
    _boolean_fallback_diagnostics,
    _exact_profile_cut_record,
    _exact_profile_cut_records,
    _exact_profile_cut_summary,
    _manifest_with_runtime_diagnostics,
    build_boolean_program_manifest,
    execute_boolean_program,
)
from .carve import (
    build_carve_program_manifest,
    execute_carve_program,
)
from .component_assembly import (
    _compact_component_assembly_record,
    _component_assembly_records_from_primitive,
    _component_assembly_summary_from_records,
    _component_operand_semantic_summary,
    _flattened_assembly_record_count,
    _record_dict,
    build_component_assembly_program_manifest,
    execute_component_assembly_program,
)
from .deform import (
    build_deform_program_manifest,
    execute_deform_program,
)
from .hull import (
    build_hull_program_manifest,
    execute_hull_program,
)
from .import_op import (
    build_import_program_manifest,
    execute_import_program,
)
from .instances import (
    build_instances_program_manifest,
    execute_instances_program,
)
from .minkowski import (
    build_minkowski_program_manifest,
    execute_minkowski_program,
)
from .polyextrude import (
    build_polyextrude_program_manifest,
    execute_polyextrude_program,
)
from .profile_path import (
    build_profile_path_program_manifest,
    execute_profile_path_program,
)
from .refine import (
    build_refine_program_manifest,
    execute_refine_program,
)
from .sdf_field import (
    build_sdf_field_program_manifest,
    execute_sdf_field_program,
)
from .terrain_field import (
    build_terrain_field_program_manifest,
    execute_terrain_field_program,
)
from .transform import (
    build_transform_program_manifest,
    execute_transform_program,
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



