"""OpenSubDiv finishing — typed contract.

Per northstar §11 Phase 3. OpenSubDiv is Pixar's industry-standard
subdivision-surface library. The Foundry declares the typed
request/response contract here; the real refinement pass is wired
when the OpenSubDiv binding is present.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

OPENSUBDIV_VERSION = "lathe.asset_foundry.opensubdiv_v1"


@dataclass(frozen=True)
class SubdivisionRequest:
    asset_id: str
    input_mesh_uri: str
    scheme: str = "catmull_clark"
    """``catmull_clark`` | ``loop`` | ``bilinear``."""

    target_level: int = 2
    boundary_interpolation: str = "edge_and_corner"
    """``none`` | ``edge_only`` | ``edge_and_corner``."""

    crease_tag_uri: str | None = None
    """Path to crease/sharpness metadata sidecar."""


@dataclass(frozen=True)
class SubdivisionResult:
    request: SubdivisionRequest
    status: str
    """``planned`` | ``unsupported`` | ``proxy``."""
    status_reason: str
    output_mesh_uri: str | None
    expected_face_count_multiplier: float
    """Catmull-Clark multiplies face count by ~4 per level."""
    backend_actual: str


def plan_opensubdiv_refinement(
    request: SubdivisionRequest,
    *,
    backend: str = "auto",
) -> SubdivisionResult:
    """Plan an OpenSubDiv refinement pass.

    Always returns a typed plan record. When the OpenSubDiv backend
    is not wired in-tree, status is ``unsupported`` with a clear
    reason rather than ``real``.
    """
    if request.target_level < 0 or request.target_level > 6:
        return SubdivisionResult(
            request=request,
            status="unsupported",
            status_reason=f"target_level_{request.target_level}_out_of_range",
            output_mesh_uri=None,
            expected_face_count_multiplier=1.0,
            backend_actual=backend,
        )
    expected_multiplier = (
        4 ** request.target_level if request.scheme == "catmull_clark" else 4 ** request.target_level
    )
    return SubdivisionResult(
        request=request,
        status="planned",
        status_reason="contract_only_no_in_tree_backend",
        output_mesh_uri=None,
        expected_face_count_multiplier=float(expected_multiplier),
        backend_actual=backend,
    )


__all__ = [
    "OPENSUBDIV_VERSION",
    "SubdivisionRequest",
    "SubdivisionResult",
    "plan_opensubdiv_refinement",
]
