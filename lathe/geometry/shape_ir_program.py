"""Execute stable ShapeIR primitives through a geometry KernelProgram."""

from __future__ import annotations

from typing import Any

import numpy as np
import trimesh

from ..shape_ir import ShapeIR
from ..shape_ir import ShapePrimitive
from .kernel import GeometryKernel
from .program import (
    KernelOperand,
    KernelProgramResult,
    _capability_names,
    execute_boolean_program,
    execute_carve_program,
    execute_component_assembly_program,
    execute_deform_program,
    execute_hull_program,
    execute_import_program,
    execute_instances_program,
    execute_minkowski_program,
    execute_polyextrude_program,
    execute_profile_path_program,
    execute_refine_program,
    execute_sdf_field_program,
    execute_terrain_field_program,
    execute_transform_program,
    semantic_metadata_from_primitive,
)


_KERNEL_BUILD_PRIMITIVE_KINDS = frozenset(
    {
        "box",
        "cylinder",
        "sphere",
        "capsule",
        "revolved_profile",
        "extruded_profile",
        "rounded_slot",
        "socket",
        "countersunk_hole",
        "countersunk_hole_set",
        "panel",
        "panel_frame",
        "panel_line_cut",
        "inset_cut",
        "perforated_panel",
        "fastener_grid",
        "weld_seam",
        "dent_mask_set",
        "edge_chip_set",
        "surface_patch_set",
        "hinge",
        "handle",
        "corner_guard_set",
        "structural_beam",
        "rail",
        "ribbed_panel",
        "louver_panel",
        "vent_slats",
        "ladder_frame",
        "truss_frame",
        "support_bracket",
        "trim_band",
        "torus",
        "tube",
        "gear",
        "flange",
        "subdivision_box",
        "swept_profile",
        "helical_sweep",
        "spring",
        "threaded_cylinder",
        "curved_tube",
        "lofted_solid",
        "heightfield",
        "terrain_patch",
        "sdf_mesh",
        "sdf_metaball_cluster",
        "terrain_mesh",
        "kernel_primitive_mesh",
        "instance_mesh",
        "polybevel_mesh",
        "profile_mesh",
        "construction_feature_mesh",
        "edge_control_mesh",
        "hull_mesh",
        "minkowski_mesh",
        "subdivision_mesh",
        "remesh_mesh",
        "deform_mesh",
        "boolean_mesh",
        "component_assembly_mesh",
        "component_assembly",
    }
)

_INSTANCE_PROGRAM_KIND_DEFAULT_OPERATION = {
    "instances": "sop.copy_to_points",
    "copy_to_points": "sop.copy_to_points",
    "sop.copy_to_points": "sop.copy_to_points",
    "scatter_on_surface": "sop.scatter_on_surface",
    "surface_scatter": "sop.scatter_on_surface",
    "sop.scatter_on_surface": "sop.scatter_on_surface",
    "distribute": "op.distribute",
    "op.distribute": "op.distribute",
    "repeat": "op.repeat",
    "op.repeat": "op.repeat",
    "mirror": "op.mirror",
    "op.mirror": "op.mirror",
}


class ShapeIRKernelProgramError(ValueError):
    """Structured ShapeIR -> KernelProgram import failure."""

    def __init__(self, message: str, *, details: dict[str, object]) -> None:
        super().__init__(message)
        self.details = dict(details)
        self.code = str(details.get("code") or "shape_ir_kernel_program_error")


def _kernel_name(kernel: GeometryKernel) -> str:
    return str(getattr(kernel, "name", "") or "")


def _mesh_body_count(mesh: trimesh.Trimesh) -> int:
    try:
        return len(mesh.split(only_watertight=False)) if len(mesh.faces) > 0 else 0
    except (AttributeError, TypeError, ValueError):
        return 0


def _operation_id_fragment(value: str) -> str:
    return "".join(char if char.isalnum() else "_" for char in value).strip("_") or "operation"


def _shape_operand_face_operation_summary(
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


def _shape_operand_operation_id(
    primitive: ShapePrimitive,
    source_index: int,
    metadata: dict[str, Any],
) -> str:
    semantic_metadata = metadata.get("semantic_metadata")
    semantic_metadata = semantic_metadata if isinstance(semantic_metadata, dict) else {}
    v2_metadata = semantic_metadata.get("shape_ir_v2")
    v2_metadata = v2_metadata if isinstance(v2_metadata, dict) else {}
    repair_metadata = semantic_metadata.get("semantic_repair")
    repair_metadata = repair_metadata if isinstance(repair_metadata, dict) else {}
    operation = (
        v2_metadata.get("v2_op")
        or repair_metadata.get("lowered_operation")
        or semantic_metadata.get("operation")
        or primitive.component
        or primitive.primitive_type
    )
    return str(
        v2_metadata.get("operation_id")
        or repair_metadata.get("operation_id")
        or semantic_metadata.get("operation_id")
        or f"primitive:{source_index:04d}:{_operation_id_fragment(str(operation))}"
    )


def _attach_shape_operand_face_operation_metadata(
    mesh: trimesh.Trimesh,
    primitive: ShapePrimitive,
    *,
    source_index: int,
    metadata: dict[str, Any],
) -> None:
    mesh_metadata = getattr(mesh, "metadata", None)
    if not isinstance(mesh_metadata, dict):
        mesh_metadata = {}
        mesh.metadata = mesh_metadata
    existing = mesh_metadata.get("face_operation_ids")
    if isinstance(existing, list) and len(existing) == len(mesh.faces):
        return
    operation_id = _shape_operand_operation_id(primitive, source_index, metadata)
    face_operation_ids = [operation_id] * len(mesh.faces)
    mesh_metadata["face_operation_ids"] = face_operation_ids
    mesh_metadata["face_operation_summary"] = _shape_operand_face_operation_summary(
        face_operation_ids,
        source="shape_ir_kernel_operand_import",
    )


def _mesh_diagonal(mesh: trimesh.Trimesh) -> float:
    try:
        extents = np.asarray(mesh.bounds[1] - mesh.bounds[0], dtype=np.float64)
    except (AttributeError, TypeError, ValueError, IndexError):
        return 0.0
    return float(np.linalg.norm(extents))


def _solidify_heightfield_mesh(mesh: trimesh.Trimesh) -> tuple[trimesh.Trimesh, dict[str, object]]:
    """Return a closed shell for an open heightfield surface."""
    vertices = np.asarray(mesh.vertices, dtype=np.float64)
    faces = np.asarray(mesh.faces, dtype=np.int64)
    if len(vertices) == 0 or len(faces) == 0:
        return mesh, {"solidified": False, "reason": "empty_mesh"}
    base_z = float(np.min(vertices[:, 2]) - max(_mesh_diagonal(mesh) * 0.02, 0.1))
    bottom_vertices = vertices.copy()
    bottom_vertices[:, 2] = base_z
    vertex_count = len(vertices)
    bottom_faces = np.flip(faces, axis=1) + vertex_count

    edge_counts: dict[tuple[int, int], int] = {}
    oriented_edges: dict[tuple[int, int], tuple[int, int]] = {}
    for face in faces:
        triples = (
            (int(face[0]), int(face[1])),
            (int(face[1]), int(face[2])),
            (int(face[2]), int(face[0])),
        )
        for a, b in triples:
            key = (a, b) if a < b else (b, a)
            edge_counts[key] = edge_counts.get(key, 0) + 1
            oriented_edges.setdefault(key, (a, b))

    side_faces: list[list[int]] = []
    for key, count in sorted(edge_counts.items()):
        if count != 1:
            continue
        a, b = oriented_edges[key]
        side_faces.append([a, b, b + vertex_count])
        side_faces.append([a, b + vertex_count, a + vertex_count])

    solid = trimesh.Trimesh(
        vertices=np.vstack([vertices, bottom_vertices]),
        faces=np.vstack([faces, bottom_faces, np.asarray(side_faces, dtype=np.int64)]),
        process=False,
    )
    solid.remove_unreferenced_vertices()
    solid.fix_normals()
    if isinstance(mesh.metadata, dict):
        solid.metadata = dict(mesh.metadata)
    terrain_metadata = solid.metadata.get("lathe_terrain_patch")
    if isinstance(terrain_metadata, dict):
        solid.metadata["lathe_terrain_patch"] = {
            **terrain_metadata,
            "solidification_method": "heightfield_flat_base_shell_v1",
            "open_surface_face_count": int(len(faces)),
            "result_face_count": int(len(solid.faces)),
            "result_watertight": bool(solid.is_watertight),
        }
    return solid, {
        "solidified": bool(solid.is_watertight),
        "method": "heightfield_flat_base_shell_v1",
        "source_face_count": len(faces),
        "result_face_count": len(solid.faces),
        "base_z": base_z,
    }


def _primitive_build_params(primitive: ShapePrimitive) -> dict[str, object]:
    payload = primitive.to_dict()
    payload.pop("primitive_type", None)
    return payload


_CONSTRUCTION_TRACE_SUMMARY_KEYS = (
    "schema",
    "method",
    "primitive_type",
    "kind",
    "requested_backend",
    "actual_backend",
    "actual_geometry_backend",
    "actual_operation",
    "actual_method",
    "fallback",
    "passthrough",
    "input_face_count",
    "input_vertex_count",
    "input_watertight",
    "candidate_face_count",
    "candidate_vertex_count",
    "candidate_watertight",
    "geometry_applied",
    "width_cm",
    "segments",
    "result_face_count",
    "result_vertex_count",
    "result_watertight",
    "result_body_count",
    "source_body_count",
    "candidate_body_count",
    "profiled_slats",
    "slat_depth_cm",
    "slat_angle_degrees",
    "slotted_drive_attempted",
    "slotted_drive_success_count",
    "slotted_drive_fallback_count",
    "polybeveled_sections",
    "section_count",
    "section_point_count",
    "path_segment_count",
    "source_section_count",
    "source_section_point_count",
    "result_section_point_count",
    "beveled_corner_count",
)


def _json_safe_metadata_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe_metadata_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe_metadata_value(item) for item in value]
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _kernel_build_construction_trace(mesh: trimesh.Trimesh) -> list[dict[str, object]]:
    """Return compact construction facts attached by exact primitive builders."""
    raw_metadata = mesh.metadata if isinstance(mesh.metadata, dict) else {}
    trace: list[dict[str, object]] = []
    for key in sorted(raw_metadata):
        if key == "lathe_shape_primitive" or not str(key).startswith("lathe_"):
            continue
        value = raw_metadata.get(key)
        if not isinstance(value, dict):
            continue
        entry: dict[str, object] = {"metadata_key": str(key)}
        for summary_key in _CONSTRUCTION_TRACE_SUMMARY_KEYS:
            if summary_key in value:
                entry[summary_key] = _json_safe_metadata_value(value[summary_key])
        if len(entry) > 1:
            trace.append(entry)
    return trace


def _shape_primitive_build_required_capabilities(primitive: ShapePrimitive) -> list[str]:
    required = [primitive.primitive_type, "to_trimesh"]
    if primitive.primitive_type == "box" and float(primitive.rounding or 0.0) > 0.0:
        required.append("box_rounding")
    if (
        primitive.v2_polybevel_modifier is not None
        or primitive.bevel_seam_groups
        or primitive.subdivision_levels > 0
        or primitive.v2_subdivision_modifier is not None
        or primitive.remesh_target_edge_length_cm is not None
        or primitive.v2_remesh_modifier is not None
    ):
        required.append("exact_modifier_import")
    ordered: list[str] = []
    for capability in required:
        text = str(capability or "").strip()
        if text and text not in ordered:
            ordered.append(text)
    return ordered


def _exact_mesh_import_required_capabilities(_primitive: ShapePrimitive) -> list[str]:
    return ["from_trimesh"]


def _kernel_import_trace_fields(mesh: trimesh.Trimesh, *, default_backend: str) -> dict[str, object]:
    trace = _kernel_build_construction_trace(mesh)
    if not trace:
        return {
            "internal_build_route": "kernel_native_mesh",
            "actual_construction_backend": default_backend,
            "construction_trace_count": 0,
        }
    methods = sorted(
        {
            str(entry.get("method") or "")
            for entry in trace
            if str(entry.get("method") or "")
        }
    )
    kernel_assisted_backends = sorted(
        {
            str(entry.get("actual_backend") or "")
            for entry in trace
            if str(entry.get("actual_backend") or "")
        }
    )
    construction_backends = sorted({"lathe.exact_solids", *kernel_assisted_backends})
    return {
        "internal_build_route": "exact_solids.primitive_mesh",
        "actual_construction_backend": "lathe.exact_solids",
        "construction_backends": construction_backends,
        "kernel_assisted_backends": kernel_assisted_backends,
        "construction_methods": methods,
        "construction_trace": trace,
        "construction_trace_count": len(trace),
        "construction_fallback": any(bool(entry.get("fallback")) for entry in trace),
        "construction_passthrough": any(bool(entry.get("passthrough")) for entry in trace),
        "construction_geometry_applied": any(bool(entry.get("geometry_applied")) for entry in trace),
    }


def _kernel_capability_map(kernel: GeometryKernel) -> dict[str, bool]:
    try:
        probe = kernel.probe()
    except (AttributeError, TypeError, ValueError, RuntimeError):
        return {}
    if not isinstance(probe, dict):
        return {}
    capabilities = probe.get("capabilities")
    if isinstance(capabilities, dict):
        return {
            str(name): bool(value)
            for name, value in capabilities.items()
            if isinstance(name, str)
        }
    return {name: True for name in _capability_names(capabilities)}


def _capability_gaps(
    capabilities: dict[str, bool],
    required: list[str],
) -> tuple[list[str], list[str]]:
    missing = sorted(name for name in required if name not in capabilities)
    unsupported = sorted(name for name in required if capabilities.get(name) is False)
    return missing, unsupported


def _try_build_kernel_primitive(
    kernel: GeometryKernel,
    primitive: ShapePrimitive,
) -> tuple[Any, trimesh.Trimesh, bool, dict[str, object]] | None:
    if primitive.primitive_type not in _KERNEL_BUILD_PRIMITIVE_KINDS:
        return None
    required_capabilities = _shape_primitive_build_required_capabilities(primitive)
    capabilities = _kernel_capability_map(kernel)
    missing, unsupported = _capability_gaps(capabilities, required_capabilities)
    if missing or unsupported:
        return (
            None,
            trimesh.Trimesh(),
            False,
            {
                "route": "kernel.build_primitive",
                "backend": _kernel_name(kernel),
                "primitive_type": primitive.primitive_type,
                "succeeded": False,
                "skipped": True,
                "reason": "kernel_did_not_advertise_required_capability",
                "required_capabilities": required_capabilities,
                "missing_capabilities": missing,
                "unsupported_capabilities": unsupported,
            },
        )
    try:
        handle = kernel.build_primitive(
            primitive.primitive_type,
            **_primitive_build_params(primitive),
        )
        mesh = kernel.to_trimesh(handle)
    except (AttributeError, TypeError, ValueError, RuntimeError, OSError) as exc:
        return (
            None,
            trimesh.Trimesh(),
            False,
            {
                "route": "kernel.build_primitive",
                "backend": _kernel_name(kernel),
                "primitive_type": primitive.primitive_type,
                "succeeded": False,
                "required_capabilities": required_capabilities,
                "exception_type": type(exc).__name__,
                "exception": str(exc),
            },
        )
    if not isinstance(mesh, trimesh.Trimesh) or len(mesh.faces) == 0:
        return (
            None,
            trimesh.Trimesh(),
            False,
            {
                "route": "kernel.build_primitive",
                "backend": _kernel_name(kernel),
                "primitive_type": primitive.primitive_type,
                "succeeded": False,
                "required_capabilities": required_capabilities,
                "reason": "empty_or_non_mesh_result",
            },
        )
    repaired = False
    if not bool(mesh.is_watertight):
        if primitive.primitive_type not in {"heightfield", "terrain_patch"}:
            return (
                None,
                mesh,
                False,
                {
                    "route": "kernel.build_primitive",
                    "backend": _kernel_name(kernel),
                    "primitive_type": primitive.primitive_type,
                    "succeeded": False,
                    "required_capabilities": required_capabilities,
                    "reason": "non_watertight_result",
                    "face_count": len(mesh.faces),
                    "body_count": _mesh_body_count(mesh),
                },
            )
        mesh, solidify_details = _solidify_heightfield_mesh(mesh)
        try:
            handle = kernel.from_trimesh(mesh)
        except (AttributeError, TypeError, ValueError, RuntimeError, OSError) as exc:
            return (
                None,
                mesh,
                False,
                {
                    "route": "kernel.build_primitive",
                    "backend": _kernel_name(kernel),
                    "primitive_type": primitive.primitive_type,
                    "succeeded": False,
                    "required_capabilities": required_capabilities,
                    "reason": "heightfield_solid_import_failed",
                    "exception_type": type(exc).__name__,
                    "exception": str(exc),
                    "solidify_details": solidify_details,
                },
            )
        repaired = True
    return (
        handle,
        mesh,
        repaired,
        {
            "route": "kernel.build_primitive",
            "backend": _kernel_name(kernel),
            "primitive_type": primitive.primitive_type,
            "succeeded": True,
            "required_capabilities": required_capabilities,
            "result_face_count": len(mesh.faces),
            "result_watertight": bool(mesh.is_watertight),
            "result_body_count": _mesh_body_count(mesh),
            **_kernel_import_trace_fields(mesh, default_backend=_kernel_name(kernel)),
            **(
                {
                    "surface_primitive_solidified": True,
                    "source_primitive_type": primitive.primitive_type,
                    "method": "heightfield_flat_base_shell_v1",
                }
                if primitive.primitive_type in {"heightfield", "terrain_patch"}
                else {}
            ),
        },
    )


def _solid_kernel_mesh_for_primitive(
    mesh: trimesh.Trimesh,
    *,
    primitive_type: str,
    part: str,
    source_index: int,
) -> tuple[trimesh.Trimesh, bool]:
    if len(mesh.faces) == 0:
        raise ShapeIRKernelProgramError(
            "kernel program primitive import failed: "
            f"primitive_type={primitive_type!r} part={part!r} produced empty mesh",
            details={
                "code": "kernel_program_primitive_empty_mesh",
                "primitive_type": primitive_type,
                "part": part,
                "source_index": source_index,
                "face_count": 0,
                "body_count": 0,
            },
        )
    if bool(mesh.is_watertight):
        return mesh, False
    if primitive_type in {"heightfield", "terrain_patch"}:
        solid, details = _solidify_heightfield_mesh(mesh)
        if bool(solid.is_watertight):
            solid.metadata["lathe_kernel_import"] = details
            return solid, True
    repaired = mesh.copy()
    repaired.remove_infinite_values()
    repaired.remove_unreferenced_vertices()
    repaired.merge_vertices()
    repaired.fix_normals()
    try:
        trimesh.repair.fill_holes(repaired)
    except (AttributeError, ImportError, TypeError, ValueError):
        pass
    if bool(repaired.is_watertight):
        return repaired, True
    raise ShapeIRKernelProgramError(
        "kernel program primitive import requires watertight solid mesh; "
        f"primitive_type={primitive_type!r} part={part!r} "
        f"faces={len(mesh.faces)} body_count={_mesh_body_count(mesh)}",
        details={
            "code": "kernel_program_primitive_non_watertight",
            "primitive_type": primitive_type,
            "part": part,
            "source_index": source_index,
            "face_count": len(mesh.faces),
            "body_count": _mesh_body_count(mesh),
            "repaired": False,
        },
    )


def _kernel_supports_capability(kernel: GeometryKernel, capability: str) -> bool:
    return _kernel_capability_map(kernel).get(capability) is True


def _exact_mesh_import_reason(
    primitive: ShapePrimitive,
    *,
    kernel: GeometryKernel | None = None,
) -> str:
    """Return why direct kernel primitive build would lose source geometry."""
    if (
        primitive.primitive_type in {
            "sdf_mesh",
            "terrain_mesh",
            "kernel_primitive_mesh",
            "instance_mesh",
            "polybevel_mesh",
            "profile_mesh",
            "construction_feature_mesh",
            "edge_control_mesh",
            "hull_mesh",
            "minkowski_mesh",
            "subdivision_mesh",
            "remesh_mesh",
            "deform_mesh",
            "boolean_mesh",
            "component_assembly_mesh",
        }
        and primitive.mesh_vertices
        and primitive.mesh_faces
    ):
        semantic_metadata = primitive.semantic_metadata if isinstance(primitive.semantic_metadata, dict) else {}
        v2_metadata = semantic_metadata.get("shape_ir_v2")
        v2_metadata = v2_metadata if isinstance(v2_metadata, dict) else {}
        for value in v2_metadata.values():
            if isinstance(value, dict) and bool(value.get("exact_mesh_import")):
                return "baked_exact_mesh_requires_exact_import"
        if bool(v2_metadata.get("exact_mesh_import")):
            return "baked_exact_mesh_requires_exact_import"
    exact_modifier_import = (
        kernel is not None
        and _kernel_supports_capability(kernel, "exact_modifier_import")
    )
    if (
        primitive.v2_polybevel_modifier is not None
        or primitive.bevel_seam_groups
    ) and not exact_modifier_import:
        return "polybevel_modifier_requires_exact_mesh"
    if (
        primitive.primitive_type == "box"
        and float(primitive.rounding or 0.0) > 0.0
        and not (
            kernel is not None
            and _kernel_supports_capability(kernel, "box_rounding")
        )
    ):
        return "box_rounding_requires_exact_mesh"
    if (
        primitive.subdivision_levels > 0
        or primitive.v2_subdivision_modifier is not None
        or primitive.remesh_target_edge_length_cm is not None
        or primitive.v2_remesh_modifier is not None
    ) and not exact_modifier_import:
        return "topology_modifier_requires_exact_mesh"
    return ""


def operands_from_shape_ir(kernel: GeometryKernel, shape_ir: ShapeIR) -> list[KernelOperand]:
    """Import ShapeIR primitives into ``kernel`` as traced program operands."""
    from ..exact_solids import primitive_mesh

    operands: list[KernelOperand] = []
    for index, primitive in enumerate(shape_ir.primitives):
        metadata = semantic_metadata_from_primitive(primitive)
        exact_import_reason = _exact_mesh_import_reason(primitive, kernel=kernel)
        build_result = None if exact_import_reason else _try_build_kernel_primitive(kernel, primitive)
        if build_result is not None and build_result[0] is not None:
            handle, mesh, repaired, import_metadata = build_result
            metadata["kernel_import"] = import_metadata
            _attach_shape_operand_face_operation_metadata(
                mesh,
                primitive,
                source_index=index,
                metadata=metadata,
            )
            try:
                handle = kernel.from_trimesh(mesh)
            except (AttributeError, TypeError, ValueError, RuntimeError, OSError):
                pass
        else:
            build_attempt = build_result[3] if build_result is not None else {}
            if exact_import_reason:
                required_capabilities = _exact_mesh_import_required_capabilities(primitive)
                capabilities = _kernel_capability_map(kernel)
                missing, unsupported = _capability_gaps(capabilities, required_capabilities)
                build_attempt = {
                    "route": "exact_mesh.from_trimesh",
                    "backend": _kernel_name(kernel),
                    "primitive_type": primitive.primitive_type,
                    "succeeded": False,
                    "skipped": True,
                    "reason": exact_import_reason,
                    "required_capabilities": required_capabilities,
                    "skipped_build_required_capabilities": _shape_primitive_build_required_capabilities(
                        primitive
                    ),
                    "missing_capabilities": missing,
                    "unsupported_capabilities": unsupported,
                }
                if missing or unsupported:
                    raise ShapeIRKernelProgramError(
                        "kernel program primitive import requires exact mesh import "
                        f"capability: primitive_type={primitive.primitive_type!r} "
                        f"part={primitive.part!r}",
                        details={
                            "code": "kernel_program_exact_import_missing_capability",
                            "primitive_type": primitive.primitive_type,
                            "part": primitive.part,
                            "source_index": index,
                            "required_capabilities": required_capabilities,
                            "missing_capabilities": missing,
                            "unsupported_capabilities": unsupported,
                            "build_primitive_attempt": build_attempt,
                        },
                    )
            try:
                raw_mesh = primitive_mesh(primitive)
            except ShapeIRKernelProgramError:
                raise
            except Exception as exc:
                raise ShapeIRKernelProgramError(
                    "kernel program primitive import failed: "
                    f"primitive_type={primitive.primitive_type!r} part={primitive.part!r}",
                    details={
                        "code": "kernel_program_primitive_import_failed",
                        "primitive_type": primitive.primitive_type,
                        "part": primitive.part,
                        "source_index": index,
                        "exception_type": type(exc).__name__,
                        "exception": str(exc),
                        **({"build_primitive_attempt": build_attempt} if build_attempt else {}),
                    },
                ) from exc
            mesh, repaired = _solid_kernel_mesh_for_primitive(
                raw_mesh,
                primitive_type=primitive.primitive_type,
                part=primitive.part,
                source_index=index,
            )
            _attach_shape_operand_face_operation_metadata(
                mesh,
                primitive,
                source_index=index,
                metadata=metadata,
            )
            try:
                handle = kernel.from_trimesh(mesh)
            except Exception as exc:
                raise ShapeIRKernelProgramError(
                    "kernel program primitive import failed during backend import: "
                    f"primitive_type={primitive.primitive_type!r} part={primitive.part!r}",
                    details={
                        "code": "kernel_program_backend_import_failed",
                        "primitive_type": primitive.primitive_type,
                        "part": primitive.part,
                        "source_index": index,
                        "face_count": len(mesh.faces),
                        "body_count": _mesh_body_count(mesh),
                        "exception_type": type(exc).__name__,
                        "exception": str(exc),
                        **({"build_primitive_attempt": build_attempt} if build_attempt else {}),
                    },
                ) from exc
            metadata["kernel_import"] = {
                "route": "exact_mesh.from_trimesh",
                "backend": _kernel_name(kernel),
                "primitive_type": primitive.primitive_type,
                "succeeded": True,
                "result_face_count": len(mesh.faces),
                "result_watertight": bool(mesh.is_watertight),
                "result_body_count": _mesh_body_count(mesh),
                **_kernel_import_trace_fields(mesh, default_backend=_kernel_name(kernel)),
                **({"build_primitive_attempt": build_attempt} if build_attempt else {}),
            }
            if repaired and primitive.primitive_type in {"heightfield", "terrain_patch"}:
                metadata["kernel_import"].update(
                    {
                        "surface_primitive_solidified": True,
                        "source_primitive_type": primitive.primitive_type,
                        "method": "heightfield_flat_base_shell_v1",
                    }
                )
        operands.append(
            KernelOperand(
                operand_id=f"{primitive.part}_{index:04d}",
                handle=handle,
                source_mesh=mesh,
                blend_mode=primitive.blend_mode or "union",
                part=primitive.part,
                primitive_type=primitive.primitive_type,
                source_index=index,
                tags=tuple(str(tag) for tag in primitive.tags),
                source_mesh_face_count=len(mesh.faces),
                source_mesh_watertight=bool(mesh.is_watertight),
                source_mesh_body_count=_mesh_body_count(mesh),
                source_mesh_repaired=repaired,
                metadata=metadata,
            )
        )
    return operands


def _details_show_exact_profile_bevel(details: dict[str, Any]) -> bool:
    final = details.get("kernel_program_exact_profile_cut_final")
    if isinstance(final, dict):
        for key in ("bevel_face_count", "chamfer_face_count", "rim_face_count"):
            try:
                if int(final.get(key) or 0) > 0:
                    return True
            except (TypeError, ValueError):
                continue
    for operation in details.get("kernel_program_operations", []):
        if not isinstance(operation, dict):
            continue
        backend = operation.get("kernel_boolean_backend")
        if isinstance(backend, dict) and bool(backend.get("profile_cut_bevel_applied")):
            return True
        nested_backend = operation.get("kernel_nested_backend_booleans")
        if isinstance(nested_backend, list):
            for item in nested_backend:
                if isinstance(item, dict) and bool(item.get("profile_cut_bevel_applied")):
                    return True
        exact = operation.get("kernel_exact_boolean")
        if not isinstance(exact, dict):
            continue
        if bool(exact.get("bevel_applied")):
            return True
        for key in ("bevel_face_count", "chamfer_face_count", "rim_face_count"):
            try:
                if int(exact.get(key) or 0) > 0:
                    return True
            except (TypeError, ValueError):
                continue
    return False


def _details_show_exact_boolean_noop_passthrough(details: dict[str, Any]) -> bool:
    for operation in details.get("kernel_program_operations", []):
        if not isinstance(operation, dict):
            continue
        exact = operation.get("kernel_exact_boolean")
        if not isinstance(exact, dict):
            continue
        if bool(exact.get("noop_existing_void")):
            return True
        method = str(exact.get("method") or "")
        if method.endswith("_existing_void_passthrough_v1"):
            return True
    return False


def _details_show_sdf_smooth_boolean(details: dict[str, Any]) -> bool:
    for operation in details.get("kernel_program_operations", []):
        if not isinstance(operation, dict):
            continue
        sdf = operation.get("kernel_sdf_boolean")
        if not isinstance(sdf, dict):
            continue
        if bool(sdf.get("smooth_boolean")):
            return True
        try:
            if float(sdf.get("blend_width_cm") or 0.0) > 0.0:
                return True
        except (TypeError, ValueError):
            continue
    return False


def _mesh_body_count(mesh: trimesh.Trimesh) -> int:
    if len(mesh.faces) == 0:
        return 0
    try:
        return int(len(mesh.split(only_watertight=False)))
    except (AttributeError, TypeError, ValueError, RuntimeError):
        return 1


def _sync_detail_payload_result_counts(
    payload: dict[str, Any],
    *,
    face_count: int,
    vertex_count: int,
    watertight: bool,
    body_count: int,
) -> dict[str, Any]:
    updated = dict(payload)
    replacements = {
        "result_face_count": int(face_count),
        "result_vertex_count": int(vertex_count),
        "result_watertight": bool(watertight),
        "result_body_count": int(body_count),
    }
    changed = False
    for key, value in replacements.items():
        previous = updated.get(key)
        if previous not in (None, value):
            updated[f"pre_postprocess_{key}"] = previous
            changed = True
        updated[key] = value
    if changed:
        updated["postprocess_result_counts_synced"] = True
    return updated


def _sync_postprocessed_boolean_details(
    details: dict[str, Any],
    *,
    mesh: trimesh.Trimesh,
    body_count: int,
) -> dict[str, Any]:
    face_count = len(mesh.faces)
    vertex_count = len(mesh.vertices)
    watertight = bool(mesh.is_watertight)
    synced = {
        **details,
        "kernel_program_watertight": watertight,
        "kernel_program_body_count": int(body_count),
        "kernel_program_emitted_face_count": int(face_count),
        "kernel_program_emitted_vertex_count": int(vertex_count),
        "kernel_program_emitted_watertight": watertight,
        "kernel_program_emitted_body_count": int(body_count),
    }
    attribution = synced.get("kernel_program_face_operation_attribution")
    if isinstance(attribution, dict):
        synced["kernel_program_face_operation_attribution"] = {
            **dict(attribution),
            "result_face_count": int(face_count),
            "postprocess_result_counts_synced": True,
        }
    for key in (
        "kernel_feature_detail",
        "kernel_program_feature_detail",
        "kernel_edge_treatment",
        "kernel_program_edge_treatment",
        "kernel_surface_damage",
        "kernel_program_surface_damage",
    ):
        payload = synced.get(key)
        if isinstance(payload, dict):
            synced[key] = _sync_detail_payload_result_counts(
                payload,
                face_count=face_count,
                vertex_count=vertex_count,
                watertight=watertight,
                body_count=body_count,
            )
    edge_fallback = bool(synced.get("post_boolean_polybevel_visible_fallback_applied"))
    if edge_fallback:
        actual_method = str(
            synced.get("post_boolean_polybevel_actual_method")
            or synced.get("post_boolean_polybevel_fallback_method")
            or synced.get("post_boolean_polybevel_method")
            or "post_boolean_polybevel_fallback"
        )
        failure_reason = str(
            synced.get("post_boolean_polybevel_visible_seam_strip_boolean_union_failure_reason")
            or synced.get("post_boolean_polybevel_edge_loop_cutback_rejected_reason")
            or ""
        )
        for key in ("kernel_edge_treatment", "kernel_program_edge_treatment"):
            payload = synced.get(key)
            if isinstance(payload, dict):
                updated = {
                    **dict(payload),
                    "fallback": True,
                    "edge_treatment_geometry_fallback": True,
                    "edge_treatment_actual_method": actual_method,
                    "post_boolean_polybevel_visible_fallback_applied": True,
                }
                if failure_reason:
                    updated["edge_treatment_fallback_reason"] = failure_reason
                synced[key] = updated
    return synced


def execute_shape_ir_boolean_program(
    kernel: GeometryKernel,
    shape_ir: ShapeIR,
    *,
    operation_limit: int | None = None,
    route: str = "shape_ir_kernel_program",
    backend: str | None = None,
    postprocess_boolean_seams: bool = True,
) -> KernelProgramResult:
    """Execute all ShapeIR primitive blend modes through ``kernel``."""
    operands = operands_from_shape_ir(kernel, shape_ir)
    result = execute_boolean_program(
        kernel,
        operands,
        operation_limit=operation_limit,
        route=route,
        backend=backend,
    )
    details = dict(result.details)
    mesh = result.mesh
    result_handle = result.handle
    if postprocess_boolean_seams:
        original_face_count = len(mesh.faces)
        original_vertex_count = len(mesh.vertices)
        blend_modes = [operand.blend_mode for operand in operands]
        destructive = any(mode in {"subtract", "intersect"} for mode in blend_modes)
        source_meshes = [
            operand.source_mesh
            for operand in operands
            if operand.source_mesh is not None
        ]
        if destructive and _details_show_exact_boolean_noop_passthrough(details):
            details["kernel_program_postprocess_skipped"] = True
            details["kernel_program_postprocess_skip_reason"] = (
                "exact_boolean_noop_existing_void"
            )
            details["post_boolean_polybevel_method"] = (
                "skipped_exact_boolean_noop_existing_void"
            )
            details["post_boolean_polybevel_accepted"] = False
            details["kernel_program_postprocess_final_watertight"] = bool(mesh.is_watertight)
            details["kernel_program_postprocess_final_body_count"] = _mesh_body_count(mesh)
        elif destructive and _details_show_exact_profile_bevel(details):
            details["kernel_program_postprocess_skipped"] = True
            details["kernel_program_postprocess_skip_reason"] = (
                "exact_profile_cut_bevel_already_applied"
            )
            details["post_boolean_polybevel_method"] = (
                "skipped_exact_profile_cut_bevel_already_applied"
            )
            details["post_boolean_polybevel_accepted"] = False
            details["kernel_program_postprocess_final_watertight"] = bool(mesh.is_watertight)
            details["kernel_program_postprocess_final_body_count"] = _mesh_body_count(mesh)
        elif destructive and _details_show_sdf_smooth_boolean(details):
            details["kernel_program_postprocess_skipped"] = True
            details["kernel_program_postprocess_skip_reason"] = (
                "sdf_smooth_boolean_bevel_already_applied"
            )
            details["post_boolean_polybevel_method"] = (
                "skipped_sdf_smooth_boolean_bevel_already_applied"
            )
            details["post_boolean_polybevel_accepted"] = False
            details["kernel_program_postprocess_final_watertight"] = bool(mesh.is_watertight)
            details["kernel_program_postprocess_final_body_count"] = _mesh_body_count(mesh)
        elif destructive and len(source_meshes) == len(operands):
            from ..exact_solids import apply_post_boolean_seam_finishing

            mesh, finish_details = apply_post_boolean_seam_finishing(
                mesh,
                primitives=list(shape_ir.primitives),
                meshes=source_meshes,
                blend_modes=blend_modes,
            )
            details.update(finish_details)
            details["kernel_program_postprocess_final_watertight"] = bool(mesh.is_watertight)
            details["kernel_program_postprocess_final_body_count"] = _mesh_body_count(mesh)
        else:
            details["kernel_program_postprocess_skipped"] = True
            details["kernel_program_postprocess_skip_reason"] = (
                "additive_program_no_boolean_seams"
                if not destructive
                else "missing_source_meshes_for_boolean_seams"
            )
        mesh_changed = (
            len(mesh.faces) != original_face_count
            or len(mesh.vertices) != original_vertex_count
        )
        if mesh_changed:
            try:
                result_handle = kernel.from_trimesh(mesh)
                details["kernel_program_postprocess_handle_refreshed"] = True
            except (AttributeError, TypeError, ValueError, RuntimeError, OSError) as exc:
                details["kernel_program_postprocess_handle_refreshed"] = False
                details["kernel_program_postprocess_handle_refresh_failure_type"] = type(exc).__name__
                details["kernel_program_postprocess_handle_refresh_failure_reason"] = str(exc)
        body_count = (
            kernel.body_count(result_handle)
            if details.get("kernel_program_postprocess_handle_refreshed")
            else _mesh_body_count(mesh)
        )
        details = _sync_postprocessed_boolean_details(
            details,
            mesh=mesh,
            body_count=body_count,
        )

    details.update(
        {
            "shape_ir_asset_name": shape_ir.asset_name,
            "shape_ir_family": shape_ir.family,
            "shape_ir_blueprint_id": shape_ir.blueprint_id,
            "shape_ir_primitive_count": len(shape_ir.primitives),
            "shape_ir_region_count": len(shape_ir.regions),
        }
    )
    semantic_handoff = details.get("kernel_program_semantic_handoff")
    if isinstance(semantic_handoff, dict):
        semantic_handoff = {
            **semantic_handoff,
            "result_face_count": len(mesh.faces),
        }
        details["kernel_program_semantic_handoff"] = semantic_handoff
        mesh.metadata["lathe_kernel_program_semantic_handoff"] = semantic_handoff
    return KernelProgramResult(
        mesh=mesh,
        handle=result_handle,
        operation_count=result.operation_count,
        details=details,
    )


def execute_shape_ir_kernel_program(
    kernel: GeometryKernel,
    shape_ir: ShapeIR,
    *,
    program_kind: str = "boolean",
    operation_limit: int | None = None,
    route: str | None = None,
    backend: str | None = None,
    postprocess_boolean_seams: bool = True,
    source_index: int = 0,
    structuring_index: int = 1,
    structuring_center: tuple[float, float, float] | None = None,
    sample_limit: int = 50_000,
    transform_matrix: list[list[float]] | None = None,
    instance_matrices: list[list[list[float]]] | None = None,
    instance_pattern: str | None = None,
    instance_pattern_payload: dict[str, Any] | None = None,
    semantic_operation: str = "sop.copy_to_points",
    deform_operation: str | None = None,
    deform_axis: str = "y",
    deform_angle_degrees: float | None = None,
    deform_start_scale: float | None = None,
    deform_end_scale: float | None = None,
    deform_direction_axis: str | None = None,
    deform_origin: list[float] | tuple[float, float, float] | None = None,
    deform_subdivision_levels: int | None = None,
    deform_segments: int | None = None,
    refine_operation: str | None = None,
    refine_levels: int | None = None,
    refine_scheme: str | None = None,
    refine_target_edge_length_cm: float | None = None,
    refine_mode: str = "adaptive",
    refine_max_iterations: int = 6,
    carve_u_start: float | None = None,
    carve_u_end: float | None = None,
    carve_axis: str = "z",
    polyextrude_axis: str = "z",
    polyextrude_distance_cm: float | None = None,
    assembly_kind: str | None = None,
    profile_kind: str | None = None,
    field_kind: str | None = None,
    terrain_kind: str | None = None,
) -> KernelProgramResult:
    """Execute a ShapeIR as a typed KernelProgram.

    ``execute_shape_ir_boolean_program`` remains the compatibility wrapper for
    existing callers. This dispatcher exposes the same stable ShapeIR primitive
    importer to hull and Minkowski programs so new construction paths do not
    need to flatten back to ad hoc raw mesh imports.
    """
    kind = str(program_kind or "boolean").strip().lower()
    if kind in {"boolean", "ordered_boolean", "csg"}:
        return execute_shape_ir_boolean_program(
            kernel,
            shape_ir,
            operation_limit=operation_limit,
            route=route or "shape_ir_kernel_program",
            backend=backend,
            postprocess_boolean_seams=postprocess_boolean_seams,
        )

    operands = operands_from_shape_ir(kernel, shape_ir)
    if kind in {"hull", "convex_hull"}:
        result = execute_hull_program(
            kernel,
            operands,
            operation_limit=operation_limit,
            route=route or "shape_ir_hull_kernel_program",
            backend=backend,
        )
        return _with_shape_ir_details(result, shape_ir)

    if kind in {"minkowski", "convex_minkowski"}:
        if not (0 <= source_index < len(operands)):
            raise ShapeIRKernelProgramError(
                "shape_ir minkowski source_index is out of range",
                details={
                    "code": "shape_ir_minkowski_source_index_out_of_range",
                    "source_index": source_index,
                    "operand_count": len(operands),
                },
            )
        if not (0 <= structuring_index < len(operands)):
            raise ShapeIRKernelProgramError(
                "shape_ir minkowski structuring_index is out of range",
                details={
                    "code": "shape_ir_minkowski_structuring_index_out_of_range",
                    "structuring_index": structuring_index,
                    "operand_count": len(operands),
                },
            )
        structuring_operand = operands[structuring_index]
        center = structuring_center
        if center is None:
            primitive = shape_ir.primitives[structuring_index]
            center = tuple(float(value) for value in primitive.center)
        result = execute_minkowski_program(
            kernel,
            operands[source_index],
            structuring_operand,
            structuring_center=center,
            sample_limit=sample_limit,
            operation_limit=operation_limit,
            route=route or "shape_ir_minkowski_kernel_program",
            backend=backend,
        )
        details = dict(result.details)
        details["shape_ir_minkowski_source_index"] = int(source_index)
        details["shape_ir_minkowski_structuring_index"] = int(structuring_index)
        return _with_shape_ir_details(
            KernelProgramResult(
                mesh=result.mesh,
                handle=result.handle,
                operation_count=result.operation_count,
                details=details,
            ),
            shape_ir,
        )

    if kind in {"transform", "sop.transform"}:
        if not (0 <= source_index < len(operands)):
            raise ShapeIRKernelProgramError(
                "shape_ir transform source_index is out of range",
                details={
                    "code": "shape_ir_transform_source_index_out_of_range",
                    "source_index": source_index,
                    "operand_count": len(operands),
                },
            )
        if transform_matrix is None:
            raise ShapeIRKernelProgramError(
                "shape_ir transform requires transform_matrix",
                details={
                    "code": "shape_ir_transform_matrix_required",
                    "program_kind": program_kind,
                },
            )
        result = execute_transform_program(
            kernel,
            operands[source_index],
            matrix=transform_matrix,
            operation_limit=operation_limit,
            route=route or "shape_ir_transform_kernel_program",
            backend=backend,
        )
        details = dict(result.details)
        details["shape_ir_transform_source_index"] = int(source_index)
        return _with_shape_ir_details(
            KernelProgramResult(
                mesh=result.mesh,
                handle=result.handle,
                operation_count=result.operation_count,
                details=details,
            ),
            shape_ir,
        )

    if kind in {"deform", "twist", "sop.twist", "taper", "sop.taper", "bend", "sop.bend"}:
        if not (0 <= source_index < len(operands)):
            raise ShapeIRKernelProgramError(
                "shape_ir deform source_index is out of range",
                details={
                    "code": "shape_ir_deform_source_index_out_of_range",
                    "source_index": source_index,
                    "operand_count": len(operands),
                },
            )
        operation = deform_operation or kind
        if str(operation).strip().lower() == "deform":
            raise ShapeIRKernelProgramError(
                "shape_ir deform requires deform_operation",
                details={
                    "code": "shape_ir_deform_operation_required",
                    "program_kind": program_kind,
                },
            )
        result = execute_deform_program(
            kernel,
            operands[source_index],
            deform_operation=operation,
            axis=deform_axis,
            angle_degrees=deform_angle_degrees,
            start_scale=deform_start_scale,
            end_scale=deform_end_scale,
            direction_axis=deform_direction_axis,
            origin=deform_origin,
            subdivision_levels=deform_subdivision_levels,
            segments=deform_segments,
            operation_limit=operation_limit,
            route=route or "shape_ir_deform_kernel_program",
            backend=backend,
        )
        details = dict(result.details)
        details["shape_ir_deform_source_index"] = int(source_index)
        return _with_shape_ir_details(
            KernelProgramResult(
                mesh=result.mesh,
                handle=result.handle,
                operation_count=result.operation_count,
                details=details,
            ),
            shape_ir,
        )

    if kind in {"refine", "subdivide", "sop.subdivide", "remesh", "sop.remesh"}:
        if not (0 <= source_index < len(operands)):
            raise ShapeIRKernelProgramError(
                "shape_ir refine source_index is out of range",
                details={
                    "code": "shape_ir_refine_source_index_out_of_range",
                    "source_index": source_index,
                    "operand_count": len(operands),
                },
            )
        operation = refine_operation or kind
        if str(operation).strip().lower() == "refine":
            raise ShapeIRKernelProgramError(
                "shape_ir refine requires refine_operation",
                details={
                    "code": "shape_ir_refine_operation_required",
                    "program_kind": program_kind,
                },
            )
        result = execute_refine_program(
            kernel,
            operands[source_index],
            refine_operation=operation,
            levels=refine_levels,
            scheme=refine_scheme,
            target_edge_length_cm=refine_target_edge_length_cm,
            mode=refine_mode,
            max_iterations=refine_max_iterations,
            operation_limit=operation_limit,
            route=route or "shape_ir_refine_kernel_program",
            backend=backend,
        )
        details = dict(result.details)
        details["shape_ir_refine_source_index"] = int(source_index)
        return _with_shape_ir_details(
            KernelProgramResult(
                mesh=result.mesh,
                handle=result.handle,
                operation_count=result.operation_count,
                details=details,
            ),
            shape_ir,
        )

    if kind in {"carve", "sop.carve"}:
        if not (0 <= source_index < len(operands)):
            raise ShapeIRKernelProgramError(
                "shape_ir carve source_index is out of range",
                details={
                    "code": "shape_ir_carve_source_index_out_of_range",
                    "source_index": source_index,
                    "operand_count": len(operands),
                },
            )
        if carve_u_start is None or carve_u_end is None:
            raise ShapeIRKernelProgramError(
                "shape_ir carve requires carve_u_start and carve_u_end",
                details={
                    "code": "shape_ir_carve_range_required",
                    "program_kind": program_kind,
                },
            )
        result = execute_carve_program(
            kernel,
            operands[source_index],
            u_start=carve_u_start,
            u_end=carve_u_end,
            axis=carve_axis,
            operation_limit=operation_limit,
            route=route or "shape_ir_carve_kernel_program",
            backend=backend,
        )
        details = dict(result.details)
        details["shape_ir_carve_source_index"] = int(source_index)
        return _with_shape_ir_details(
            KernelProgramResult(
                mesh=result.mesh,
                handle=result.handle,
                operation_count=result.operation_count,
                details=details,
            ),
            shape_ir,
        )

    if kind in {"polyextrude", "sop.polyextrude", "extrude", "op.extrude"}:
        if not (0 <= source_index < len(operands)):
            raise ShapeIRKernelProgramError(
                "shape_ir polyextrude source_index is out of range",
                details={
                    "code": "shape_ir_polyextrude_source_index_out_of_range",
                    "source_index": source_index,
                    "operand_count": len(operands),
                },
            )
        if polyextrude_distance_cm is None:
            raise ShapeIRKernelProgramError(
                "shape_ir polyextrude requires polyextrude_distance_cm",
                details={
                    "code": "shape_ir_polyextrude_distance_required",
                    "program_kind": program_kind,
                },
            )
        result = execute_polyextrude_program(
            kernel,
            operands[source_index],
            axis=polyextrude_axis,
            distance_cm=polyextrude_distance_cm,
            semantic_operation=(
                "op.extrude"
                if kind in {"extrude", "op.extrude"}
                else "sop.polyextrude"
            ),
            operation_limit=operation_limit,
            route=route or "shape_ir_polyextrude_kernel_program",
            backend=backend,
        )
        details = dict(result.details)
        details["shape_ir_polyextrude_source_index"] = int(source_index)
        return _with_shape_ir_details(
            KernelProgramResult(
                mesh=result.mesh,
                handle=result.handle,
                operation_count=result.operation_count,
                details=details,
            ),
            shape_ir,
        )

    if kind in {"component_assembly", "assembly"}:
        result = execute_component_assembly_program(
            kernel,
            operands,
            semantic_operation=semantic_operation,
            assembly_kind=assembly_kind or shape_ir.blueprint_id or shape_ir.asset_name,
            operation_limit=operation_limit,
            route=route or "shape_ir_component_assembly_kernel_program",
            backend=backend,
        )
        details = dict(result.details)
        details["shape_ir_component_assembly_operand_count"] = len(operands)
        details["shape_ir_component_assembly_kind"] = (
            assembly_kind or shape_ir.blueprint_id or shape_ir.asset_name
        )
        return _with_shape_ir_details(
            KernelProgramResult(
                mesh=result.mesh,
                handle=result.handle,
                operation_count=result.operation_count,
                details=details,
            ),
            shape_ir,
        )

    if kind in {
        "profile",
        "profile_path",
        "curve_profile",
        "sweep",
        "sop.sweep",
        "loft",
        "sop.loft",
        "polywire",
        "sop.polywire",
        "helical_sweep",
        "sop.helical_sweep",
    }:
        if not (0 <= source_index < len(operands)):
            raise ShapeIRKernelProgramError(
                "shape_ir profile_path source_index is out of range",
                details={
                    "code": "shape_ir_profile_path_source_index_out_of_range",
                    "source_index": source_index,
                    "operand_count": len(operands),
                },
            )
        operation = semantic_operation
        if operation == "sop.copy_to_points":
            operation = kind if kind.startswith("sop.") else f"sop.{kind}"
        result = execute_profile_path_program(
            kernel,
            operands[source_index],
            semantic_operation=operation,
            profile_kind=profile_kind or kind,
            operation_limit=operation_limit,
            route=route or "shape_ir_profile_path_kernel_program",
            backend=backend,
        )
        details = dict(result.details)
        details["shape_ir_profile_path_source_index"] = int(source_index)
        details["shape_ir_profile_path_kind"] = profile_kind or kind
        return _with_shape_ir_details(
            KernelProgramResult(
                mesh=result.mesh,
                handle=result.handle,
                operation_count=result.operation_count,
                details=details,
            ),
            shape_ir,
        )

    if kind in {"sdf_field", "implicit_field", "sdf", "solid.sdf_metaball_cluster"}:
        if not (0 <= source_index < len(operands)):
            raise ShapeIRKernelProgramError(
                "shape_ir sdf_field source_index is out of range",
                details={
                    "code": "shape_ir_sdf_field_source_index_out_of_range",
                    "source_index": source_index,
                    "operand_count": len(operands),
                },
            )
        result = execute_sdf_field_program(
            kernel,
            operands[source_index],
            semantic_operation=semantic_operation,
            field_kind=field_kind or kind,
            operation_limit=operation_limit,
            route=route or "shape_ir_sdf_field_kernel_program",
            backend=backend,
        )
        details = dict(result.details)
        details["shape_ir_sdf_field_source_index"] = int(source_index)
        details["shape_ir_sdf_field_kind"] = field_kind or kind
        return _with_shape_ir_details(
            KernelProgramResult(
                mesh=result.mesh,
                handle=result.handle,
                operation_count=result.operation_count,
                details=details,
            ),
            shape_ir,
        )

    if kind in {"terrain", "terrain_field", "heightfield", "solid.terrain_patch"}:
        if not (0 <= source_index < len(operands)):
            raise ShapeIRKernelProgramError(
                "shape_ir terrain_field source_index is out of range",
                details={
                    "code": "shape_ir_terrain_field_source_index_out_of_range",
                    "source_index": source_index,
                    "operand_count": len(operands),
                },
            )
        result = execute_terrain_field_program(
            kernel,
            operands[source_index],
            semantic_operation=semantic_operation,
            terrain_kind=terrain_kind or kind,
            operation_limit=operation_limit,
            route=route or "shape_ir_terrain_field_kernel_program",
            backend=backend,
        )
        details = dict(result.details)
        details["shape_ir_terrain_field_source_index"] = int(source_index)
        details["shape_ir_terrain_field_kind"] = terrain_kind or kind
        return _with_shape_ir_details(
            KernelProgramResult(
                mesh=result.mesh,
                handle=result.handle,
                operation_count=result.operation_count,
                details=details,
            ),
            shape_ir,
        )

    if kind in {"import", "primitive", "source"}:
        if not (0 <= source_index < len(operands)):
            raise ShapeIRKernelProgramError(
                "shape_ir import source_index is out of range",
                details={
                    "code": "shape_ir_import_source_index_out_of_range",
                    "source_index": source_index,
                    "operand_count": len(operands),
                },
            )
        result = execute_import_program(
            kernel,
            operands[source_index],
            semantic_operation=semantic_operation,
            operation_limit=operation_limit,
            route=route or "shape_ir_import_kernel_program",
            backend=backend,
        )
        details = dict(result.details)
        details["shape_ir_import_source_index"] = int(source_index)
        return _with_shape_ir_details(
            KernelProgramResult(
                mesh=result.mesh,
                handle=result.handle,
                operation_count=result.operation_count,
                details=details,
            ),
            shape_ir,
        )

    if kind in _INSTANCE_PROGRAM_KIND_DEFAULT_OPERATION:
        if not (0 <= source_index < len(operands)):
            raise ShapeIRKernelProgramError(
                "shape_ir instances source_index is out of range",
                details={
                    "code": "shape_ir_instances_source_index_out_of_range",
                    "source_index": source_index,
                    "operand_count": len(operands),
                },
            )
        if instance_matrices is None:
            raise ShapeIRKernelProgramError(
                "shape_ir instances requires instance_matrices",
                details={
                    "code": "shape_ir_instances_matrices_required",
                    "program_kind": program_kind,
                },
            )
        resolved_semantic_operation = str(semantic_operation or "").strip()
        default_operation = _INSTANCE_PROGRAM_KIND_DEFAULT_OPERATION[kind]
        if not resolved_semantic_operation or (
            resolved_semantic_operation == "sop.copy_to_points"
            and default_operation != "sop.copy_to_points"
        ):
            resolved_semantic_operation = default_operation
        result = execute_instances_program(
            kernel,
            operands[source_index],
            matrices=instance_matrices,
            semantic_operation=resolved_semantic_operation,
            instance_pattern=instance_pattern,
            instance_pattern_payload=instance_pattern_payload,
            operation_limit=operation_limit,
            route=route or f"shape_ir_{_operation_id_fragment(resolved_semantic_operation)}_kernel_program",
            backend=backend,
        )
        details = dict(result.details)
        details["shape_ir_instances_source_index"] = int(source_index)
        details["shape_ir_instances_program_kind"] = kind
        details["shape_ir_instances_semantic_operation"] = resolved_semantic_operation
        return _with_shape_ir_details(
            KernelProgramResult(
                mesh=result.mesh,
                handle=result.handle,
                operation_count=result.operation_count,
                details=details,
            ),
            shape_ir,
        )

    raise ShapeIRKernelProgramError(
        f"unsupported shape_ir kernel program kind: {program_kind!r}",
        details={
            "code": "unsupported_shape_ir_kernel_program_kind",
            "program_kind": program_kind,
            "supported_program_kinds": [
                "boolean",
                "hull",
                "minkowski",
                "transform",
                "deform",
                "refine",
                "carve",
                "polyextrude",
                "component_assembly",
                "profile_path",
                "sdf_field",
                "terrain_field",
                "import",
                "instances",
                "copy_to_points",
                "sop.copy_to_points",
                "surface_scatter",
                "sop.scatter_on_surface",
                "op.distribute",
                "op.repeat",
                "op.mirror",
            ],
        },
    )


def _with_shape_ir_details(
    result: KernelProgramResult,
    shape_ir: ShapeIR,
) -> KernelProgramResult:
    details = dict(result.details)
    details.update(
        {
            "shape_ir_asset_name": shape_ir.asset_name,
            "shape_ir_family": shape_ir.family,
            "shape_ir_blueprint_id": shape_ir.blueprint_id,
            "shape_ir_primitive_count": len(shape_ir.primitives),
            "shape_ir_region_count": len(shape_ir.regions),
        }
    )
    return KernelProgramResult(
        mesh=result.mesh,
        handle=result.handle,
        operation_count=result.operation_count,
        details=details,
    )
