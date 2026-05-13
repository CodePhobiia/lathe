"""F-Rep / SDF sharper extraction.

Per northstar §11 Phase 3. Marching-cubes-like mesh extraction
softens hard surfaces by design. Sharper extractors (Dual Contouring,
Dual Marching Cubes with QEF, Manifold Dual Contouring) preserve
sharp features when they're tagged via Hermite data on grid edges.

This module declares the typed request/result contract. The real
extractor is wired by an external backend when available.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

SDF_EXTRACTION_VERSION = "lathe.asset_foundry.sdf_extraction_v1"


@dataclass(frozen=True)
class SdfExtractionRequest:
    asset_id: str
    grid_dim: tuple[int, int, int]
    voxel_size_cm: float
    isovalue: float = 0.0
    method: str = "dual_contouring"
    """``marching_cubes`` | ``dual_contouring`` | ``dual_marching_cubes`` |
    ``manifold_dual_contouring``."""
    preserve_sharp_features: bool = True
    qef_lambda: float = 0.1
    """QEF regularization. Lower = sharper but more risk of dual-cell artifacts."""


@dataclass(frozen=True)
class SdfExtractionResult:
    request: SdfExtractionRequest
    status: str
    """``planned`` | ``proxy`` | ``unsupported``."""
    status_reason: str
    output_mesh_uri: str | None
    expected_face_count: int
    """Estimate: ``grid_dim_x * grid_dim_y * grid_dim_z * 0.6`` for
    DC-class extractors."""
    backend_actual: str


def plan_sdf_extraction(
    request: SdfExtractionRequest,
    *,
    backend: str = "auto",
) -> SdfExtractionResult:
    if request.method not in {
        "marching_cubes",
        "dual_contouring",
        "dual_marching_cubes",
        "manifold_dual_contouring",
    }:
        return SdfExtractionResult(
            request=request,
            status="unsupported",
            status_reason=f"unknown_method_{request.method!r}",
            output_mesh_uri=None,
            expected_face_count=0,
            backend_actual=backend,
        )
    dx, dy, dz = request.grid_dim
    expected = int(dx * dy * dz * 0.6)
    return SdfExtractionResult(
        request=request,
        status="planned",
        status_reason="contract_only_no_in_tree_backend",
        output_mesh_uri=None,
        expected_face_count=expected,
        backend_actual=backend,
    )


__all__ = [
    "SDF_EXTRACTION_VERSION",
    "SdfExtractionRequest",
    "SdfExtractionResult",
    "plan_sdf_extraction",
]
