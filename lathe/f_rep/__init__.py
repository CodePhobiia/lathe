"""F-Rep / SDF authoring module for Lathe (roadmap §7.6).

Implements an Inigo Quilez-style signed distance field algebra in pure
Python, with a deterministic vectorized evaluator and marching-cubes
mesh extraction. Dual contouring is provided as a feature-aware scaffold
that can be elaborated as a follow-up.

Public surface:

* Primitives:
  ``Sphere``, ``Box``, ``Plane``, ``Cylinder``, ``Torus``, ``Capsule``,
  ``SegmentCapsule``, ``SegmentBox``, ``TaperedSegmentCapsule``, ``Frustum``, ``Cone``,
  ``HexPrism``, ``Ellipsoid``, ``RoundedSlot``, ``ExtrudedPolygon``,
  ``RevolvedProfile``.
* Boolean: ``Union``, ``Intersect``, ``Subtract``.
* Chamfer boolean: ``ChamferUnion``, ``ChamferIntersect``,
  ``ChamferSubtract``.
* Smooth boolean: ``SmoothUnion``, ``SmoothIntersect``, ``SmoothSubtract``.
* Intent wrappers: ``ConnectedIntent`` for authored one-body compositions.
* Modifiers: ``Translate``, ``Rotate``, ``Scale``, ``Scale3``, ``Twist``,
  ``Bend``, ``Taper``, ``Mirror``, ``Repeat``, ``Offset``, ``Shell``,
  ``Displace``, ``Warp``.
* Compilation: :func:`compile_program` — turn a Lathe ``f_rep_program``
  AST dict into an :class:`SDFExpr` tree.
* Evaluation: :func:`evaluate_sdf` — vectorized SDF over a point cloud.
* Extraction: :func:`extract_mesh` — marching cubes (default) or dual
  contouring (scaffold) into a triangle mesh.

Reference: Inigo Quilez, "Distance Functions" — https://iquilezles.org/
"""

from __future__ import annotations

from .bounds import estimate_bounds
from .dual_contouring import extract_dual_contouring
from .evaluator import evaluate_program, evaluate_sdf, sample_grid
from .expressions import (
    Bend,
    Box,
    Capsule,
    ChamferIntersect,
    ChamferSubtract,
    ChamferUnion,
    Cone,
    ConnectedIntent,
    Cylinder,
    Displace,
    Ellipsoid,
    ExtrudedPolygon,
    Frustum,
    HexPrism,
    Intersect,
    Mirror,
    Offset,
    Plane,
    Repeat,
    RevolvedProfile,
    Rotate,
    RoundedSlot,
    Scale,
    Scale3,
    SDFExpr,
    SegmentBox,
    SegmentCapsule,
    SegmentExtrudedProfile,
    SegmentLoftedProfile,
    Shell,
    SmoothIntersect,
    SmoothSubtract,
    SmoothUnion,
    Sphere,
    Subtract,
    Taper,
    TaperedSegmentCapsule,
    Torus,
    Translate,
    Twist,
    Union,
    Warp,
)
from .marching_cubes import extract_marching_cubes
from .parser import compile_program, parse_f_rep_program
from .validator import ValidationDiagnostic, ValidationReport, validate_program

F_REP_CONTRACT_ID = "lathe.shape.f_rep_v1"
F_REP_COMPOSITION_IR_ID = "lathe.f_rep_sdf_composition_ir.v1"


def resolve_extraction_backend(backend: str = "marching_cubes") -> dict[str, object]:
    """Return requested-vs-actual extractor metadata for an SDF extraction."""
    requested = str(backend or "marching_cubes")
    if requested == "marching_cubes":
        from .marching_cubes import _have_skimage

        if _have_skimage():
            return {
                "requested_backend": "marching_cubes",
                "actual_backend": "skimage_marching_cubes",
                "fallback": False,
            }
        return {
            "requested_backend": "marching_cubes",
            "actual_backend": "dual_contouring_fallback",
            "fallback": True,
            "fallback_reason": "skimage_unavailable",
        }
    if requested == "dual_contouring":
        return {
            "requested_backend": "dual_contouring",
            "actual_backend": "dual_contouring",
            "fallback": False,
        }
    raise ValueError(f"Unknown extraction backend: {backend!r}")


def extract_mesh(
    expr: SDFExpr,
    *,
    bounds: tuple[tuple[float, float, float], tuple[float, float, float]],
    resolution: int | tuple[int, int, int] = 64,
    backend: str = "marching_cubes",
    iso: float = 0.0,
):
    """Extract a triangle mesh from an SDF expression.

    Args:
        expr: the root :class:`SDFExpr`.
        bounds: ``((xmin, ymin, zmin), (xmax, ymax, zmax))`` evaluation box.
        resolution: scalar grid resolution per axis or a 3-tuple.
        backend: ``"marching_cubes"`` (default) or ``"dual_contouring"``.
        iso: iso-value to extract; default 0 (the SDF surface).

    Returns:
        ``(vertices, faces)`` where ``vertices`` is an ``(N, 3)`` numpy
        array and ``faces`` is an ``(M, 3)`` int array of triangle
        indices.
    """
    backend_info = resolve_extraction_backend(backend)
    actual = str(backend_info["actual_backend"])
    if actual == "skimage_marching_cubes":
        return extract_marching_cubes(expr, bounds=bounds, resolution=resolution, iso=iso)
    if actual in {"dual_contouring", "dual_contouring_fallback"}:
        return extract_dual_contouring(expr, bounds=bounds, resolution=resolution, iso=iso)
    raise ValueError(f"Unknown extraction backend: {backend!r}")


__all__ = [
    "F_REP_COMPOSITION_IR_ID",
    "F_REP_CONTRACT_ID",
    "Bend",
    "Box",
    "Capsule",
    "ChamferIntersect",
    "ChamferSubtract",
    "ChamferUnion",
    "Cone",
    "ConnectedIntent",
    "Cylinder",
    "Displace",
    "Ellipsoid",
    "ExtrudedPolygon",
    "Frustum",
    "HexPrism",
    "Intersect",
    "Mirror",
    "Offset",
    "Plane",
    "Repeat",
    "RevolvedProfile",
    "Rotate",
    "RoundedSlot",
    "SDFExpr",
    "Scale",
    "Scale3",
    "SegmentBox",
    "SegmentCapsule",
    "SegmentExtrudedProfile",
    "SegmentLoftedProfile",
    "Shell",
    "SmoothIntersect",
    "SmoothSubtract",
    "SmoothUnion",
    "Sphere",
    "Subtract",
    "Taper",
    "TaperedSegmentCapsule",
    "Torus",
    "Translate",
    "Twist",
    "Union",
    "ValidationDiagnostic",
    "ValidationReport",
    "Warp",
    "compile_program",
    "estimate_bounds",
    "evaluate_program",
    "evaluate_sdf",
    "extract_dual_contouring",
    "extract_marching_cubes",
    "extract_mesh",
    "parse_f_rep_program",
    "resolve_extraction_backend",
    "sample_grid",
    "validate_program",
]
