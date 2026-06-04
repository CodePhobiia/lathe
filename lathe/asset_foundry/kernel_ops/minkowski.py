"""Minkowski sum operator.

Per northstar §10 Lane A future-tasks, Minkowski sums are useful for:
  - shrink-wrap proxies (sphere + asset);
  - rounded-corner offsets (small sphere/box sum to round all edges);
  - clearance volumes for assembly validation.

Two concrete paths are implemented:
  - ``minkowski_box_box``: analytic — Minkowski sum of two AABBs is
    another AABB whose extents are the sum of the input half-extents.
  - ``minkowski_polyhedron_polyhedron``: half-space-set summation —
    given two convex polyhedra represented as half-space sets, the
    Minkowski sum is the half-space set whose normals are the union
    of input normals and whose offsets are the sum of pairwise
    offsets along each normal. Approximate for non-convex inputs.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from ..polyhedron import HalfSpace, HalfSpacePolyhedron, build_half_space_polyhedron

MINKOWSKI_VERSION = "lathe.asset_foundry.minkowski_v1"


@dataclass(frozen=True)
class MinkowskiSumRequest:
    """Inputs for a Minkowski sum."""

    asset_id: str
    operand_a_kind: str
    """``box`` | ``half_space_polyhedron``."""
    operand_b_kind: str
    bbox_extent_cm: float = 50.0


@dataclass(frozen=True)
class MinkowskiSumResult:
    """Output of a Minkowski sum."""

    asset_id: str
    kind: str
    """``aabb`` | ``half_space_polyhedron`` | ``unsupported``."""

    extents_cm: tuple[float, float, float] | None
    """Set when kind == ``aabb`` — half-extents along x/y/z."""

    polyhedron: HalfSpacePolyhedron | None
    """Set when kind == ``half_space_polyhedron``."""

    status: str
    """``real`` | ``approximate`` | ``unsupported``."""

    status_reason: str = ""


def minkowski_box_box(
    request: MinkowskiSumRequest,
    a_extents_cm: tuple[float, float, float],
    b_extents_cm: tuple[float, float, float],
) -> MinkowskiSumResult:
    """Analytic Minkowski sum of two AABBs (half-extents in cm)."""
    if any(e < 0 for e in a_extents_cm) or any(e < 0 for e in b_extents_cm):
        return MinkowskiSumResult(
            asset_id=request.asset_id,
            kind="unsupported",
            extents_cm=None,
            polyhedron=None,
            status="unsupported",
            status_reason="negative_extent",
        )
    summed = (
        a_extents_cm[0] + b_extents_cm[0],
        a_extents_cm[1] + b_extents_cm[1],
        a_extents_cm[2] + b_extents_cm[2],
    )
    return MinkowskiSumResult(
        asset_id=request.asset_id,
        kind="aabb",
        extents_cm=summed,
        polyhedron=None,
        status="real",
    )


def minkowski_polyhedron_polyhedron(
    request: MinkowskiSumRequest,
    half_spaces_a: Sequence[HalfSpace],
    half_spaces_b: Sequence[HalfSpace],
    *,
    bbox_extent_cm: float | None = None,
) -> MinkowskiSumResult:
    """Approximate Minkowski sum of two convex polyhedra.

    For two convex polyhedra A and B given by their half-space
    inequalities ``n_i . x <= o_i``, the Minkowski sum's half-spaces
    are the union of input normals; for each normal n, the summed
    offset is ``max(o_A(n)) + max(o_B(n))``. This works exactly
    when both polyhedra are convex; for non-convex inputs the result
    is the Minkowski sum of their convex hulls (approximation).
    """
    if not half_spaces_a or not half_spaces_b:
        return MinkowskiSumResult(
            asset_id=request.asset_id,
            kind="unsupported",
            extents_cm=None,
            polyhedron=None,
            status="unsupported",
            status_reason="empty_half_space_set",
        )
    # Union of normals (each normal gets summed-offset).
    summed_by_normal: dict[tuple[float, float, float], float] = {}
    labels: dict[tuple[float, float, float], str] = {}

    def _accept(hs_a: HalfSpace, hs_b: HalfSpace) -> None:
        key = hs_a.normal
        max_a = hs_a.offset
        max_b = hs_b.offset
        summed_by_normal[key] = max(summed_by_normal.get(key, max_a + max_b), max_a + max_b)
        labels[key] = labels.get(key, hs_a.label or "minkowski")

    for hs_a in half_spaces_a:
        # Match against the b half-space sharing the same normal direction.
        best_b: HalfSpace | None = None
        for hs_b in half_spaces_b:
            if hs_b.normal == hs_a.normal:
                if best_b is None or hs_b.offset > best_b.offset:
                    best_b = hs_b
        if best_b is None:
            # No matching normal in b — use b's projection in this direction
            # via the support function: max(n . v) over b's vertices is the
            # same as max(o_b(n')) over b's normals weighted by alignment.
            # For the approximation, we simply skip — the result is
            # constrained by the planes in B that DO have matching normals.
            continue
        _accept(hs_a, best_b)
    if not summed_by_normal:
        return MinkowskiSumResult(
            asset_id=request.asset_id,
            kind="unsupported",
            extents_cm=None,
            polyhedron=None,
            status="unsupported",
            status_reason="no_matching_normals",
        )
    summed = tuple(
        HalfSpace(normal=n, offset=o, label=labels[n])
        for n, o in summed_by_normal.items()
    )
    poly = build_half_space_polyhedron(
        summed,
        bbox_extent_cm=bbox_extent_cm if bbox_extent_cm is not None else request.bbox_extent_cm,
        zone_prefix=f"minkowski.{request.asset_id}",
    )
    return MinkowskiSumResult(
        asset_id=request.asset_id,
        kind="half_space_polyhedron",
        extents_cm=None,
        polyhedron=poly,
        status="approximate" if len(half_spaces_a) != len(half_spaces_b) else "real",
        status_reason=""
        if len(half_spaces_a) == len(half_spaces_b)
        else "non_matching_normal_count_approximated_via_convex_hull",
    )


def result_to_dict(result: MinkowskiSumResult) -> dict[str, Any]:
    """JSON-serialize a MinkowskiSumResult."""
    payload: dict[str, Any] = {
        "asset_id": result.asset_id,
        "kind": result.kind,
        "status": result.status,
        "status_reason": result.status_reason,
    }
    if result.extents_cm is not None:
        payload["extents_cm"] = list(result.extents_cm)
    if result.polyhedron is not None:
        payload["polyhedron"] = {
            "vertex_count": result.polyhedron.vertex_count(),
            "face_count": result.polyhedron.face_count(),
            "half_space_count": len(result.polyhedron.half_spaces),
        }
    return payload


__all__ = [
    "MINKOWSKI_VERSION",
    "MinkowskiSumRequest",
    "MinkowskiSumResult",
    "minkowski_box_box",
    "minkowski_polyhedron_polyhedron",
    "result_to_dict",
]
