"""Half-edge bevel operator for arbitrary mesh topology.

Per northstar §10 Lane A future-tasks. The current bevel path is
post-boolean polybevel; a half-edge-based bevel operates on any
mesh by selecting edges via a half-edge query (angle, exposure,
material boundary, role tag) and inserting a bevel ring.

This module declares the typed request + result. The actual
geometry pass is delegated to either the existing
``feature_ops/bevel_real.py`` (post-boolean polybevel) or — when an
external half-edge backend is wired — a true half-edge bevel.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

HALF_EDGE_BEVEL_VERSION = "lathe.asset_foundry.half_edge_bevel_v1"


@dataclass(frozen=True)
class HalfEdgeBevelRequest:
    """Inputs for a half-edge bevel plan."""

    asset_id: str
    mesh_uri: str
    edge_selector: Mapping[str, Any]
    """Selector record matching
    ``lathe.asset_quality.edge_group_selector`` predicates: e.g.
    ``{"angle_gt_deg": 35, "exposed": True, "feature_scale_gt": 0.005}``."""

    bevel_radius_cm: float = 0.5
    segments: int = 2
    profile: str = "chunky_industrial"
    """``chunky_industrial`` | ``smooth_2seg`` | ``hard_1seg``."""

    backend: str = "auto"
    """``auto`` chooses the best available; ``polybevel`` forces
    post-boolean polybevel; ``half_edge`` forces a half-edge backend
    when one is wired."""


@dataclass(frozen=True)
class HalfEdgeBevelResult:
    """Output of a half-edge bevel plan."""

    request: HalfEdgeBevelRequest
    status: str
    """``planned`` (ready for execution) | ``unsupported`` |
    ``proxy`` | ``not_started``."""
    status_reason: str
    selected_edge_count: int
    estimated_bevel_ring_face_count: int
    """Heuristic: ``selected_edge_count * segments * 2`` (two triangles per
    bevel ring quad)."""
    backend_actual: str
    """The actual backend that handled the plan."""


def plan_half_edge_bevel(
    request: HalfEdgeBevelRequest,
    *,
    edge_count_hint: int = 0,
) -> HalfEdgeBevelResult:
    """Plan a half-edge bevel.

    Returns a ``planned`` status when the polybevel fallback is
    available. ``unsupported`` when the selector is empty or the
    backend is explicitly forced to ``half_edge`` (which is not yet
    wired in-tree).
    """
    if request.bevel_radius_cm <= 0 or request.segments < 1:
        return HalfEdgeBevelResult(
            request=request,
            status="unsupported",
            status_reason="invalid_radius_or_segment_count",
            selected_edge_count=0,
            estimated_bevel_ring_face_count=0,
            backend_actual=request.backend,
        )
    selector = request.edge_selector or {}
    if not selector:
        return HalfEdgeBevelResult(
            request=request,
            status="unsupported",
            status_reason="empty_edge_selector",
            selected_edge_count=0,
            estimated_bevel_ring_face_count=0,
            backend_actual=request.backend,
        )
    if request.backend == "half_edge":
        return HalfEdgeBevelResult(
            request=request,
            status="not_started",
            status_reason="half_edge_backend_not_wired_in_tree",
            selected_edge_count=edge_count_hint,
            estimated_bevel_ring_face_count=0,
            backend_actual="half_edge",
        )
    estimated_faces = edge_count_hint * request.segments * 2
    backend_actual = "polybevel" if request.backend in {"auto", "polybevel"} else request.backend
    return HalfEdgeBevelResult(
        request=request,
        status="planned",
        status_reason="",
        selected_edge_count=edge_count_hint,
        estimated_bevel_ring_face_count=estimated_faces,
        backend_actual=backend_actual,
    )


__all__ = [
    "HALF_EDGE_BEVEL_VERSION",
    "HalfEdgeBevelRequest",
    "HalfEdgeBevelResult",
    "plan_half_edge_bevel",
]
