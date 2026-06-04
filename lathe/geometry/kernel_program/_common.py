"""Common per-op helpers — trace records, mesh probes, ID fragments.

Every per-op executor (``execute_boolean_program``, ``execute_hull_program``,
``execute_transform_program``, …) needs the same handful of shared
primitives:

  - ``_operation_id_fragment`` — operation-id slug builder.
  - ``_non_empty_mesh`` — extract a non-empty trimesh from a kernel handle.
  - ``_operation_record`` — build a per-operation trace record skeleton.
  - ``_record_result_probe`` — read the result mesh's metadata onto a
    record (face counts, kernel backend metadata for every per-op family).
  - ``_record_operation_result`` — wrapper that adds boolean-fallback
    extraction on top of ``_record_result_probe``.
  - ``_attach_kernel_boolean_execution_metadata`` — boolean-specific
    metadata extraction shared between probe paths.

Isolating these into one module keeps the per-op modules thin and
breaks an import cycle: per-op modules import ``_common``; ``_common``
imports only from ``..kernel`` and ``trimesh``.
"""

from __future__ import annotations

import contextlib
import math
from typing import Any

import trimesh

from ..kernel import GeometryKernel
from ._serialize import _dict_metadata


def _operation_id_fragment(value: str) -> str:
    """Slugify a free-form string for use inside an operation_id."""
    return "".join(char if char.isalnum() else "_" for char in value).strip("_") or "operation"


def _sequence_count(value: Any) -> int:
    """Return ``len(value)`` for list/tuple, 0 otherwise."""
    if isinstance(value, (list, tuple)):
        return len(value)
    return 0


def _finite_float(value: Any, *, field: str) -> float:
    """Coerce ``value`` to a finite float or raise ValueError naming ``field``.

    Used by deform / refine / carve to validate numeric kwargs (angle
    degrees, scale factors, u-range bounds, target edge lengths).
    """
    try:
        out = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"kernel deform {field} must be numeric") from exc
    if not math.isfinite(out):
        raise ValueError(f"kernel deform {field} must be finite")
    return out


def _copy_kernel_import_stats(
    stats: dict[str, Any], kernel_import: dict[str, Any]
) -> None:
    """Copy the standard kernel-import audit fields from ``kernel_import`` into ``stats``.

    Reads route, backend, primitive_type, succeeded flag, construction
    backend lists, construction methods/trace, fallback / passthrough /
    geometry-applied booleans, and the build-primitive attempt record.
    """
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


def _non_empty_mesh(kernel: GeometryKernel, handle: Any) -> trimesh.Trimesh:
    """Convert ``handle`` to a non-empty trimesh or raise ValueError.

    Kernel programs must produce non-empty output to be inspectable
    downstream — an empty mesh is treated as a hard failure rather
    than a silent degenerate result.
    """
    mesh = kernel.to_trimesh(handle)
    if not isinstance(mesh, trimesh.Trimesh) or len(mesh.faces) == 0:
        raise ValueError("kernel program produced an empty or non-mesh result")
    return mesh


def _operation_record(
    *,
    op: str,
    left: str,
    right: str,
    kernel: GeometryKernel,
) -> dict[str, Any]:
    """Build a per-op trace record skeleton with attempted/actual kernel populated."""
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
    """Inspect ``mesh.metadata`` for boolean-backend evidence and populate ``record``.

    Reads from the seven boolean-related metadata blobs (manifold,
    reference exact/backend/sdf/batch_union, reference fallback). The
    first source that has a structured payload contributes its
    attempted/actual backend, method, and source-tag onto the record;
    subsequent sources are ignored to keep the trace deterministic.
    """
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
    """Populate ``record`` with face-count + kernel-family metadata from the result.

    Reads the result handle's trimesh and copies every recognized
    ``lathe_*`` metadata blob into ``record["kernel_*"]`` plus a few
    flattened convenience fields (``attempted_backend``,
    ``actual_backend``, ``actual_operation``, per-family ``*_method``).
    The metadata families inspected mirror the per-op modules:
    boolean, hull, transform, deform, refine, carve, polyextrude,
    component_assembly, profile_path, sdf_field, terrain_field,
    scatter, pattern_instances, edge_control, edge_treatment,
    feature_detail, surface_damage, minkowski.
    """
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
    with contextlib.suppress(AttributeError, TypeError, ValueError, RuntimeError):
        record["result_body_count"] = kernel.body_count(result_handle)


def _record_operation_result(
    record: dict[str, Any],
    *,
    kernel: GeometryKernel,
    result_handle: Any,
    left_handle: Any,
) -> None:
    """Add boolean-fallback extraction on top of ``_record_result_probe``.

    Boolean-specific extraction reads decomposition metadata and the
    legacy ``lathe_reference_boolean_fallback`` payload, which together
    cover the fallback-trace cluster that ``_record_result_probe`` does
    not. Also flips ``passthrough_fallback_suspected`` when the
    operation is destructive (subtract/intersect) but the result handle
    is the left operand — a tell-tale sign the kernel skipped the op.
    """
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


__all__ = [
    "_attach_kernel_boolean_execution_metadata",
    "_copy_kernel_import_stats",
    "_finite_float",
    "_non_empty_mesh",
    "_operation_id_fragment",
    "_operation_record",
    "_record_operation_result",
    "_record_result_probe",
    "_sequence_count",
]
