"""Operand-to-operation-record helpers consumed by every manifest builder.

Every ``build_*_program_manifest`` function in the package starts by
calling ``_operand_operation_records`` to convert the kernel-operand
list into a list of semantic-operation records that the manifest
inspects (for ``operation`` matching, ``operation_id`` propagation,
modifier-payload extraction). This module groups those helpers
together so per-op modules can import them via a single, narrow
dependency point.

The cluster includes:

  - ``_modifier_operation_default`` — derive the default ``v2_op``
    string for a ``v2_*_modifier`` payload name.
  - ``_modifier_payload_operation`` — pick the right operation field
    out of a payload, with the default as fallback.
  - ``_operand_modifier_payloads`` — walk an operand's metadata and
    return every present ``v2_*_modifier`` payload.
  - ``_kernel_modifier_payload_containers`` — the search graph
    ``_operand_modifier_payloads`` walks.
  - ``_shape_record_v2_metadata`` / ``_shape_record_operation`` —
    inspect a single shape-IR-v2 record for its op/id/repair fields.
  - ``_shape_record_operation_records`` — recursively walk an
    assembly-primitive tree, emitting one record per shape op.
  - ``_operand_operation_records`` — the umbrella builder that
    combines all the above for a list of operands.
  - ``_operand_semantic_records`` — extract per-operand semantic
    metadata for the kernel-program handoff payload.
"""

from __future__ import annotations

from typing import Any

from ._common import _operation_id_fragment
from ._core import KernelOperand
from ._face_operation import _copy_source_context_summary, _metadata_list
from ._serialize import (
    _compact_kernel_handoff_value,
    _compact_semantic_metadata_record,
    _compact_shape_record_summary,
    _compact_source_shape_record,
    _dict_metadata,
    _json_safe,
)

_MODIFIER_OPERATION_DEFAULTS: dict[str, str] = {
    "boolean": "op.boolean",
    "bracket": "op.support_bracket",
    "branching_tree": "op.branching_tree",
    "capsule": "solid.capsule",
    "corner_guard_set": "op.corner_guard_set",
    "countersunk_hole": "op.countersunk_hole",
    "countersunk_hole_set": "op.countersunk_hole_set",
    "carve": "op.carve",
    "cga_facade": "op.cga_facade",
    "component_assembly_transform": "op.component_assembly_transform",
    "context_aggregate": "source_context.aggregate",
    "cut_panel_line": "op.panel_line_cut",
    "curved_tube": "solid.curved_tube",
    "curve_loft": "solid.curve_lofted_solid",
    "curve_profile": "op.curve_profile",
    "curve_sweep": "op.curve_sweep",
    "deform": "sop.deform",
    "extrude": "sop.polyextrude",
    "fastener_grid": "op.fastener_grid",
    "flange": "solid.flange",
    "gear": "solid.gear",
    "handle": "op.handle",
    "helical_sweep": "sop.helical_sweep",
    "hinge": "op.hinge",
    "hull": "op.hull",
    "inset": "op.inset",
    "ladder_frame": "op.ladder_frame",
    "loft": "solid.lofted_solid",
    "louver_panel": "op.louver_panel",
    "minkowski": "op.minkowski",
    "mount_plate": "op.mount_plate",
    "output_materialize": "op.output_materialize",
    "panel_frame": "op.panel_frame",
    "panel": "op.panel",
    "perforated_panel": "op.perforated_panel",
    "polywire": "op.polywire",
    "polyextrude_exact_mesh": "sop.polyextrude_exact_mesh",
    "polyextrude": "sop.polyextrude",
    "prism": "solid.prism",
    "rail": "op.rail",
    "record_materialize": "op.record_materialize",
    "ribbed_panel": "op.ribbed_panel",
    "rounded_slot": "op.rounded_slot",
    "remesh": "sop.remesh",
    "sdf_metaball_cluster": "solid.sdf_metaball_cluster",
    "shell": "op.shell",
    "sop_boolean": "sop.boolean",
    "socket": "op.socket",
    "spring": "solid.spring",
    "structural_beam": "op.structural_beam",
    "subdivision": "sop.subdivide",
    "sweep": "sop.sweep",
    "tessellation": "sop.tessellate",
    "tube": "solid.tube",
    "threaded_cylinder": "solid.threaded_cylinder",
    "trim_band": "op.trim_band",
    "truss_frame": "op.truss_frame",
    "vent_slats": "op.vent_slats",
    "wire": "op.wire",
    "chip_edges": "op.chip_edges",
    "dent_mask": "op.dent_mask",
    "grime_mask": "op.grime_mask",
    "scratch_mask": "op.scratch_mask",
}


def _modifier_operation_default(modifier_name: str) -> str:
    """Map a ``v2_*_modifier`` name to its default ``v2_op`` string."""
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
    """Pick the right ``operation`` string from a modifier payload."""
    return str(
        payload.get("v2_op")
        or payload.get("operation")
        or base_operation
        or _modifier_operation_default(modifier_name)
    )


def _kernel_modifier_payload_containers(metadata: dict[str, Any]) -> list[dict[str, Any]]:
    """Return every metadata sub-dict that may carry ``v2_*_modifier`` payloads.

    The search walks operand metadata, semantic_metadata, shape_ir_v2,
    baked-source-modifier maps, and source_shape_primitive(s). Each
    container is returned only when non-empty.
    """
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


def _operand_modifier_payloads(metadata: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """Return ``(name, payload)`` for every ``v2_*_modifier`` in the metadata graph.

    Walks every container ``_kernel_modifier_payload_containers``
    surfaces and dedupes on ``(name, operation_id, method-or-operation)``.
    """
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


def _shape_record_v2_metadata(record: dict[str, Any]) -> dict[str, Any]:
    """Return the ``semantic_metadata.shape_ir_v2`` blob of a shape record."""
    semantic_metadata = _dict_metadata(record.get("semantic_metadata"))
    return _dict_metadata(semantic_metadata.get("shape_ir_v2"))


def _shape_record_operation(record: dict[str, Any]) -> tuple[str, str, str]:
    """Return ``(operation, operation_id, repair_action)`` for one shape record."""
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


def _shape_record_operation_records(
    records: list[dict[str, Any]],
    operand: KernelOperand,
    operand_index: int,
    *,
    source: str,
    path_prefix: str,
) -> list[dict[str, Any]]:
    """Walk an assembly-primitive tree, emitting one operation record per shape op.

    Recursive: each record's ``assembly_primitives`` child list is
    walked, with the path-fragment encoded into the operation_id for
    deterministic uniqueness across nested trees.
    """
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
    """Build the full semantic-operation record list for a kernel-operand sequence.

    Combines (a) per-operand semantic-metadata records, (b) feature
    component records, (c) every ``v2_*_modifier`` payload, and
    (d) recursive assembly-primitive / source-shape-primitive walks.
    De-duplicates on ``(operation_id, operation, operand_id, source)``
    before returning.
    """
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


def _operand_semantic_records(operand: KernelOperand, index: int) -> dict[str, Any]:
    """Extract per-operand semantic metadata for the kernel-program handoff.

    Returns a record summarizing the operand's component/region/tags,
    boolean/bevel/hard-edge seam groups, instance metadata,
    source-shape-primitive(s), component-assembly metadata, and a
    compacted semantic_metadata blob. Used by the
    ``_kernel_program_semantic_handoff`` builder.
    """
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


__all__ = [
    "_MODIFIER_OPERATION_DEFAULTS",
    "_kernel_modifier_payload_containers",
    "_modifier_operation_default",
    "_modifier_payload_operation",
    "_operand_modifier_payloads",
    "_operand_operation_records",
    "_operand_semantic_records",
    "_shape_record_operation",
    "_shape_record_operation_records",
    "_shape_record_v2_metadata",
]
