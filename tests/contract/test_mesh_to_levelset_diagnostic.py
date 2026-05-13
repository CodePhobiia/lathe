"""Contract test: mesh-to-levelset (voxel) fallback emits a degraded diagnostic.

Per `docs/asset-quality/lathe-northstar-full-implementation-plan.md`
v2 §5.3 Lane A priority task 5:

> Mesh-to-levelset repair as last-resort fallback, **always emits a
> degraded-status diagnostic**.

The reference kernel's ``_voxel_boolean`` last-resort fallback
samples both operand meshes onto a regular grid, performs the
boolean in voxel space, and extracts the result via marching cubes.
This is lossy by construction — surface fidelity, seams, and
topology cannot be guaranteed.

When that fallback fires, the kernel-program diagnostic surface must
emit:

  1. The existing ``boolean_csg_fallback`` diagnostic with severity
     ``warning`` (generic fallback tracking).
  2. An additional ``mesh_to_levelset_repair`` diagnostic with
     severity ``degraded``, ``lossy=True``, and
     ``certification_blocking=True`` so downstream hero-quality
     certification can refuse to stamp the output.

This test calls ``_boolean_fallback_diagnostics`` directly with a
synthetic voxel fallback record (the exact shape ``_record_operation_result``
produces when reading the reference kernel's
``lathe_reference_boolean_fallback`` metadata) and asserts both
diagnostics land in the expected shape. A second test calls it with
a non-voxel fallback (e.g., passthrough concatenate) and asserts the
``mesh_to_levelset_repair`` diagnostic does NOT fire — the degraded
status is reserved for the level-set path specifically.
"""

from __future__ import annotations

from lathe.geometry.kernel_program import _boolean_fallback_diagnostics


def _voxel_fallback_record(
    *,
    op: str = "union",
    operation_index: int = 0,
) -> dict:
    """Synthetic fallback record mimicking what the reference kernel emits."""
    return {
        "op": op,
        "attempted_kernel": "lathe.geometry.reference_v1",
        "actual_kernel": "lathe.geometry.reference_v1",
        "kernel_fallback": {
            "method": "voxel_boolean_fallback_v1",
            "op": op,
            "attempted_backend": "trimesh.boolean",
            "actual_backend": "lathe.reference.voxel_boolean",
            "actual_operation": f"voxel_{op}",
            "fallback": True,
            "passthrough": False,
            "pitch_cm": 0.5,
            "source_voxel_count": 800,
            "cutter_voxel_count": 600,
            "result_voxel_count": 1234,
        },
        "passthrough_fallback_suspected": False,
    }


def _passthrough_fallback_record() -> dict:
    """A passthrough/concatenate fallback record — NOT the voxel path."""
    return {
        "op": "union",
        "attempted_kernel": "lathe.geometry.reference_v1",
        "actual_kernel": "lathe.geometry.reference_v1",
        "kernel_fallback": {
            "method": "additive_mesh_concatenation",
            "op": "union",
            "attempted_backend": "trimesh.boolean",
            "actual_backend": "trimesh.util.concatenate",
            "actual_operation": "additive_mesh_concatenation",
            "fallback": True,
            "passthrough": True,
        },
        "passthrough_fallback_suspected": True,
    }


def test_voxel_fallback_emits_both_diagnostics() -> None:
    """Voxel fallback emits both boolean_csg_fallback AND mesh_to_levelset_repair.

    The pairing is intentional: the generic warning continues to fire
    for backwards compatibility, and the new degraded-status diagnostic
    adds the certification-blocking signal.
    """
    diagnostics = _boolean_fallback_diagnostics([_voxel_fallback_record()])

    assert len(diagnostics) == 2, (
        f"voxel fallback should produce 2 diagnostics, got {len(diagnostics)}"
    )
    codes = [d["code"] for d in diagnostics]
    assert codes == ["boolean_csg_fallback", "mesh_to_levelset_repair"], (
        f"expected ordered diagnostic codes ['boolean_csg_fallback', "
        f"'mesh_to_levelset_repair'], got {codes!r}"
    )


def test_mesh_to_levelset_diagnostic_carries_degraded_status() -> None:
    """The mesh_to_levelset_repair diagnostic must signal degradation explicitly.

    The specific fields are the contract certification logic consumes:
      - severity = ``degraded`` (not just ``warning``)
      - lossy = True
      - certification_blocking = True
      - fallback_method = ``voxel_boolean_fallback_v1``
      - pitch_cm and result_voxel_count carried for audit
    """
    diagnostics = _boolean_fallback_diagnostics([_voxel_fallback_record()])
    levelset_diag = next(
        d for d in diagnostics if d["code"] == "mesh_to_levelset_repair"
    )
    assert levelset_diag["severity"] == "degraded"
    assert levelset_diag["lossy"] is True
    assert levelset_diag["certification_blocking"] is True
    assert levelset_diag["fallback_method"] == "voxel_boolean_fallback_v1"
    assert levelset_diag["attempted_backend"] == "trimesh.boolean"
    assert levelset_diag["actual_backend"] == "lathe.reference.voxel_boolean"
    assert levelset_diag["pitch_cm"] == 0.5
    assert levelset_diag["result_voxel_count"] == 1234


def test_passthrough_fallback_does_not_emit_levelset_diagnostic() -> None:
    """A non-voxel fallback (concatenate, passthrough) emits only the warning.

    The degraded-status diagnostic is reserved for the actual
    mesh-to-levelset path. A passthrough/concatenate fallback is also
    a fallback, but not a level-set repair — emitting a
    ``mesh_to_levelset_repair`` for it would dilute the signal.
    """
    diagnostics = _boolean_fallback_diagnostics([_passthrough_fallback_record()])
    codes = [d["code"] for d in diagnostics]
    assert codes == ["boolean_csg_fallback"], (
        f"passthrough fallback should produce ONLY the boolean_csg_fallback "
        f"warning, got {codes!r}. The mesh_to_levelset_repair diagnostic "
        "must not fire for non-voxel fallbacks."
    )


def test_voxel_fallback_diagnostic_count_one_per_record() -> None:
    """Every voxel fallback record produces its own paired diagnostic set.

    Catches a regression where one record might accidentally suppress
    a paired diagnostic for a sibling record.
    """
    records = [
        _voxel_fallback_record(op="union", operation_index=0),
        _voxel_fallback_record(op="difference", operation_index=1),
        _voxel_fallback_record(op="intersection", operation_index=2),
    ]
    diagnostics = _boolean_fallback_diagnostics(records)

    # 3 records x 2 diagnostics each
    assert len(diagnostics) == 6
    levelset_diags = [
        d for d in diagnostics if d["code"] == "mesh_to_levelset_repair"
    ]
    assert len(levelset_diags) == 3
    # Operation indices preserved and ordered.
    indices = [d["operation_index"] for d in levelset_diags]
    assert indices == [0, 1, 2]
    # Per-operation op preserved.
    ops = [d["operation"] for d in levelset_diags]
    assert ops == ["union", "difference", "intersection"]


def test_mixed_fallback_records_route_to_correct_diagnostics() -> None:
    """One voxel + one passthrough produces 3 diagnostics: 2 + 1.

    Asserts the levelset diagnostic is targeted to the voxel record
    only, even when interleaved with other fallback methods.
    """
    records = [
        _passthrough_fallback_record(),
        _voxel_fallback_record(op="union"),
    ]
    diagnostics = _boolean_fallback_diagnostics(records)

    codes = [d["code"] for d in diagnostics]
    assert codes == [
        "boolean_csg_fallback",  # passthrough record's warning
        "boolean_csg_fallback",  # voxel record's warning
        "mesh_to_levelset_repair",  # voxel record's degraded follow-up
    ]


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
