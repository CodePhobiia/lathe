"""Contract test: partial revolved_profile produces a watertight mesh.

Per `docs/asset-quality/lathe-northstar-full-implementation-plan.md`
v2 §5.3 Lane A priority task 2 (sixth coverage path: "partial rotate
extrude"). Before this fix, ``trimesh.creation.revolve(angle=...,
cap=True)`` produced a non-watertight mesh with mismatched cap-seam
topology and negative volume — Manifold rejected the result and the
primitive failed to import.

The fix routes partial sweeps through ``manifold3d.CrossSection(...)
.revolve(circular_segments, revolve_degrees)`` which produces a
watertight result by construction. This test pins:

  1. Partial sweeps (90°, 180°, 270°, 359°) are watertight.
  2. The volume scales monotonically with the sweep angle.
  3. The full 360° sweep continues to work (unchanged path).
  4. The result executes through Manifold without falling back.
"""

from __future__ import annotations

import pytest
from lathe.adapters.manifold_kernel import manifold_available
from lathe.geometry import resolve_geometry_kernel
from lathe.geometry.kernel import MANIFOLD_KERNEL_ID
from lathe.geometry.shape_ir_lowering import execute_shape_ir_boolean_program
from lathe.shape_ir import ShapeIR, ShapePrimitive


def _partial_revolve_ir(sweep_degrees: float) -> ShapeIR:
    """ShapeIR with a single revolved_profile at ``sweep_degrees``.

    Profile defines an L-shaped (axial, radial) cross-section that
    forms a hollow ring when fully revolved — exercises both axis-
    touching and off-axis vertices.
    """
    return ShapeIR(
        asset_name=f"partial_revolve_{int(sweep_degrees)}",
        family="partial_revolve_probe",
        blueprint_id=f"partial_revolve_{int(sweep_degrees)}",
        symmetry_axis=None,
        units="cm",
        primitives=[
            ShapePrimitive(
                primitive_type="revolved_profile",
                part="arc",
                center=(0.0, 0.0, 0.0),
                axis="z",
                profile_points=[
                    (0.0, 2.0),
                    (4.0, 2.0),
                    (4.0, 4.0),
                    (0.0, 4.0),
                ],
                revolve_degrees=sweep_degrees,
                sections=32,
            ),
        ],
        regions=[],
        primitives_used=["revolved_profile"],
        part_graph=[],
        signature={},
    )


_PARTIAL_SWEEP_ANGLES: tuple[float, ...] = (90.0, 180.0, 270.0, 359.0)


@pytest.mark.skipif(
    not manifold_available(),
    reason="manifold3d not importable; partial revolve fix uses manifold3d native API",
)
@pytest.mark.parametrize("sweep_degrees", _PARTIAL_SWEEP_ANGLES)
def test_partial_revolve_is_watertight(sweep_degrees: float) -> None:
    """A revolved_profile with revolve_degrees < 360 is watertight via Manifold."""
    kernel = resolve_geometry_kernel()
    assert kernel.name == MANIFOLD_KERNEL_ID

    result = execute_shape_ir_boolean_program(kernel, _partial_revolve_ir(sweep_degrees))

    assert result.details.get("kernel_program_kernel") == MANIFOLD_KERNEL_ID, (
        f"sweep {sweep_degrees}° did not route through Manifold; "
        f"actual kernel={result.details.get('kernel_program_kernel')!r}"
    )
    assert result.details.get("kernel_program_emitted_watertight") is True, (
        f"sweep {sweep_degrees}° produced a non-watertight mesh "
        f"(face_count={len(result.mesh.faces)}). The manifold3d "
        "native revolve fix must yield watertight output for all "
        "partial sweep angles."
    )
    assert result.mesh.volume > 0.0, (
        f"sweep {sweep_degrees}° produced non-positive volume "
        f"({result.mesh.volume}); winding/normal orientation must "
        "be correct for downstream CSG."
    )


@pytest.mark.skipif(
    not manifold_available(),
    reason="manifold3d not importable",
)
def test_partial_revolve_volume_scales_with_sweep() -> None:
    """Volume grows monotonically with sweep angle from 90° → 359°.

    Catches a regression where the cap topology could swallow volume
    or where one sweep angle silently produces a degenerate result.
    """
    kernel = resolve_geometry_kernel()
    volumes: list[float] = []
    for sweep in _PARTIAL_SWEEP_ANGLES:
        result = execute_shape_ir_boolean_program(kernel, _partial_revolve_ir(sweep))
        volumes.append(float(result.mesh.volume))

    for i in range(1, len(volumes)):
        assert volumes[i] > volumes[i - 1], (
            f"volume non-monotonic between "
            f"{_PARTIAL_SWEEP_ANGLES[i - 1]}° (vol={volumes[i - 1]:.3f}) and "
            f"{_PARTIAL_SWEEP_ANGLES[i]}° (vol={volumes[i]:.3f})"
        )


@pytest.mark.skipif(
    not manifold_available(),
    reason="manifold3d not importable",
)
def test_full_revolve_still_works() -> None:
    """The 360° path (unchanged trimesh-based revolve) still produces a watertight mesh."""
    kernel = resolve_geometry_kernel()
    result = execute_shape_ir_boolean_program(kernel, _partial_revolve_ir(360.0))

    assert result.details.get("kernel_program_emitted_watertight") is True
    assert result.mesh.volume > 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
