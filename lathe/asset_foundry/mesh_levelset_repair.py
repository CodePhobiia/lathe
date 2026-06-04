"""Foundry Lane A #7 — mesh-to-levelset repair as last-resort fallback.

Per northstar §10 Lane A priority task #7, the kernel needs a
last-resort fallback that converts a broken mesh to a signed-distance
field (level set), repairs it (close holes, recover manifoldness),
and remeshes to triangles. This recovers something usable when
exact-boolean + Manifold-CSG + cutter-omit all fail.

Strict rule: every levelset-repair output MUST be tagged
``visible_degraded_status`` so consumers cannot pass it off as a
real exact-boolean result. Per masterplan §3, hidden levelset
output is a no-fake-quality violation.

This module is a *typed contract scaffold* — it defines the
RepairRequest / RepairReport / quality-loss bookkeeping and a
deterministic stub repair function. Real OpenVDB / scikit-image
levelset integration is wired by an external builder when the
dependency is available; otherwise the stub records
``status: 'unbuilt', reason: 'levelset_backend_unavailable'``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

MESH_LEVELSET_REPAIR_VERSION = "lathe.asset_foundry.mesh_levelset_repair_v1"


@dataclass(frozen=True)
class LevelsetRepairRequest:
    """Inputs for a last-resort levelset repair pass."""

    asset_id: str
    input_mesh_uri: str
    voxel_size_cm: float = 0.2
    """Smaller -> sharper recovery, larger -> faster. Default 0.2 cm."""

    band_width_voxels: int = 4
    """Narrow-band width for the signed-distance volume."""

    close_holes_radius_cm: float | None = None
    """When set, holes smaller than this radius get closed during
    isosurface extraction."""

    smoothing_iterations: int = 0
    """Light Taubin smoothing applied after meshing. > 0 risks
    softening hard edges; default off for hard-surface fixtures."""

    isovalue: float = 0.0
    """Iso level. 0 = surface. Positive = inflate, negative = deflate."""

    expected_part_count: int | None = None
    """When set, the repair report includes a body-count divergence
    metric (recovered vs expected)."""


@dataclass(frozen=True)
class LevelsetRepairReport:
    """Output of a levelset-repair pass — always degraded-status."""

    version: str
    request: LevelsetRepairRequest
    status: str
    """One of ``real`` (degraded), ``unbuilt``, ``failed``."""

    status_reason: str
    output_mesh_uri: str | None
    """Path of the remeshed result; None when status != ``real``."""

    voxel_dim: tuple[int, int, int]
    """Resolved grid dimensions for diagnostic. ``(0,0,0)`` when
    status != ``real``."""

    triangle_count_in: int
    triangle_count_out: int
    body_count_out: int
    watertight_out: bool
    degraded_status: bool = True
    """Always True — levelset output is never a real exact-boolean
    result. Forbidden to claim hero quality on this output."""

    quality_loss_estimate: float = 1.0
    """``0`` = no detail lost (impossible — levelset always smooths).
    ``1`` = total fallback. The certificate uses this to discount
    the hero score."""

    repair_actions_applied: tuple[str, ...] = ()


def _stub_repair(request: LevelsetRepairRequest) -> LevelsetRepairReport:
    """Stub repair when the levelset backend dependency is missing.

    Always returns ``unbuilt`` so the caller can route to a different
    fallback or surface the blocker honestly.
    """
    return LevelsetRepairReport(
        version=MESH_LEVELSET_REPAIR_VERSION,
        request=request,
        status="unbuilt",
        status_reason="levelset_backend_unavailable",
        output_mesh_uri=None,
        voxel_dim=(0, 0, 0),
        triangle_count_in=0,
        triangle_count_out=0,
        body_count_out=0,
        watertight_out=False,
        degraded_status=True,
        quality_loss_estimate=1.0,
        repair_actions_applied=(),
    )


def perform_levelset_repair(
    request: LevelsetRepairRequest,
    *,
    backend: str = "auto",
) -> LevelsetRepairReport:
    """Last-resort mesh-to-levelset repair.

    Args:
        request: the typed repair request.
        backend: ``"auto"`` selects ``openvdb``, ``scikit-image``, or
            falls back to the stub. ``"stub"`` forces the unbuilt
            response (used to assert wiring without external deps).

    Returns:
        A LevelsetRepairReport. Output is ALWAYS tagged
        ``degraded_status=True`` per the no-fake-quality rule.

    Notes:
        The real backend integration is wired by an external builder
        when the OpenVDB / scikit-image dependency is available; this
        function provides the typed contract so downstream stages can
        consume the report regardless of which backend produced it.
    """
    if backend == "stub":
        return _stub_repair(request)
    # We do not attempt to import OpenVDB / scikit-image here to avoid
    # adding a runtime dependency. An external builder that wraps this
    # function MAY override _stub_repair with a backend-specific
    # implementation.
    return _stub_repair(request)


def levelset_repair_report_to_dict(
    report: LevelsetRepairReport,
) -> dict[str, Any]:
    """JSON-serialize a LevelsetRepairReport."""
    return {
        "version": report.version,
        "request": {
            "asset_id": report.request.asset_id,
            "input_mesh_uri": report.request.input_mesh_uri,
            "voxel_size_cm": report.request.voxel_size_cm,
            "band_width_voxels": report.request.band_width_voxels,
            "close_holes_radius_cm": report.request.close_holes_radius_cm,
            "smoothing_iterations": report.request.smoothing_iterations,
            "isovalue": report.request.isovalue,
            "expected_part_count": report.request.expected_part_count,
        },
        "status": report.status,
        "status_reason": report.status_reason,
        "output_mesh_uri": report.output_mesh_uri,
        "voxel_dim": list(report.voxel_dim),
        "triangle_count_in": report.triangle_count_in,
        "triangle_count_out": report.triangle_count_out,
        "body_count_out": report.body_count_out,
        "watertight_out": report.watertight_out,
        "degraded_status": report.degraded_status,
        "quality_loss_estimate": report.quality_loss_estimate,
        "repair_actions_applied": list(report.repair_actions_applied),
    }


__all__ = [
    "MESH_LEVELSET_REPAIR_VERSION",
    "LevelsetRepairReport",
    "LevelsetRepairRequest",
    "levelset_repair_report_to_dict",
    "perform_levelset_repair",
]
