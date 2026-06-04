"""Refine program — subdivision / remesh refinement through the kernel seam.

Per the §5.3 decomposition, this module hosts the ``refine`` family:
``sop.subdivide`` (midpoint catmull-clark-style subdivision) and
``sop.remesh`` (iterative-midpoint edge-length retargeting with
optional laplacian smoothing).

The executor takes a single source operand, imports its trimesh,
runs the requested refinement on the trimesh, then re-imports the
refined mesh back into the kernel for downstream composition.
"""

from __future__ import annotations

import contextlib
from typing import Any

import numpy as np
import trimesh

from ..kernel import GeometryKernel
from ._capabilities import (
    _kernel_capabilities,
    _require_capabilities,
    _validate_transform_operand,
)
from ._common import (
    _finite_float,
    _non_empty_mesh,
    _operation_id_fragment,
    _record_result_probe,
)
from ._core import KernelOperand, KernelProgramResult, refine_operation_count
from ._face_operation import _attach_direct_face_operation_metadata
from ._feature_detail import _kernel_feature_detail_metadata
from ._records import _operand_operation_records
from ._semantic import (
    _final_semantic_operation_face_id,
    _operation_counts,
    _semantic_operation_records_from_manifest,
)
from ._semantic_handoff import _attach_kernel_program_semantic_handoff
from ._serialize import _json_safe

KERNEL_PROGRAM_VERSION = "lathe.geometry.kernel_program_v1"


def _validated_refine_operation(operation: str) -> str:
    """Normalize a refine operation alias to its canonical sop.* form."""
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
    """Normalize a refine mode string to one of: adaptive, uniform, smooth, feature_preserving."""
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
    """Apply N levels of midpoint subdivision to ``mesh``; ``levels<=0`` is a no-op."""
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
    with contextlib.suppress(ValueError, RuntimeError, AttributeError, IndexError, TypeError):
        refined.fix_normals()
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
    """Iteratively subdivide ``mesh`` until max-edge-length <= target.

    Each iteration applies one midpoint subdivision pass and re-checks
    the maximum edge length; loops up to ``max_iterations`` times.
    Smooth mode additionally runs one laplacian smoothing pass at the
    end with volume preservation.
    """
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
        with contextlib.suppress(ValueError, RuntimeError, AttributeError, IndexError, TypeError):
            trimesh.smoothing.filter_laplacian(
                remeshed,
                lamb=0.35,
                iterations=1,
                volume_constraint=True,
            )
    remeshed.remove_unreferenced_vertices()
    remeshed.merge_vertices()
    with contextlib.suppress(ValueError, RuntimeError, AttributeError, IndexError, TypeError):
        remeshed.fix_normals()
    if len(remeshed.vertices) == 0 or len(remeshed.faces) == 0:
        raise ValueError("kernel refine remesh produced an empty mesh")
    return remeshed


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


__all__ = [
    "build_refine_program_manifest",
    "execute_refine_program",
]
