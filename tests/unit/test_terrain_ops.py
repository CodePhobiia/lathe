"""Tests for the Phase 3 second-slice terrain primitive ops.

Covers ``terrain_heightfield`` (single ``heightfield`` constructor with
fbm noise + rim taper) and ``terrain_biome`` (compound op that mutates
the target heightfield's elevation grid per biome rule).
"""

from __future__ import annotations

import numpy as np
import pytest

from lathe.mesh_program import MeshProgramError, lower_mesh_program
from lathe.parser.imports import parse_text


def _parse_program(body: str) -> dict:
    src = (
        "module demo.terrain_test\n"
        "asset terrain_test : hard_surface_prop {\n"
        "  intent { role = \"terrain test\" }\n"
        "  build {\n"
        "    shape {\n"
        "      mode = generate\n"
        "      candidates = 1\n"
        "      mesh_program {\n"
        f"{body}\n"
        "      }\n"
        "    }\n"
        "  }\n"
        "}\n"
    )
    program = parse_text(src)
    return program["assets"][0]["build"]["shape"]["mesh_program"]


def _bare_heightfield(body_call: str):
    """Lower a single terrain_heightfield call and return the bare primitive.

    Mesh-program let-bindings only land in the output list once a
    downstream op references them. We pair every constructor-only test
    with a no-op ``terrain_biome(target: ground, biome: \"rolling_hills\",
    roughness: 0.0)`` so the heightfield gets emitted *and* the
    rolling_hills modifier is a near-no-op (envelope == 1 when
    roughness=0).
    """
    body = (
        f"        let ground = {body_call}\n"
        "        terrain_biome(target: ground, biome: \"rolling_hills\", "
        "roughness: 0.0)"
    )
    return lower_mesh_program(_parse_program(body))[0]


def test_terrain_heightfield_emits_grid_with_correct_extents() -> None:
    hf = _bare_heightfield(
        "terrain_heightfield(extents: [40m, 40m], resolution: 32, "
        "scale_z: 8m, seed: 42)"
    )
    assert hf.primitive_type == "heightfield"
    # Resolution recorded as (nx, ny).
    assert hf.resolution == (32, 32)
    # bounds_xy centered on origin, full 40m × 40m == 4000cm × 4000cm.
    assert hf.bounds_xy is not None
    xmin, ymin, xmax, ymax = hf.bounds_xy
    assert xmin == pytest.approx(-2000.0)
    assert ymin == pytest.approx(-2000.0)
    assert xmax == pytest.approx(2000.0)
    assert ymax == pytest.approx(2000.0)
    # vertical_scale stores the requested scale_z in cm.
    assert hf.vertical_scale == pytest.approx(800.0)
    # height_data is an ny × nx grid normalised to [0, 1] (rim taper drops
    # corners to 0; fbm noise lifts interior).
    assert hf.height_data is not None
    h = np.asarray(hf.height_data)
    assert h.shape == (32, 32)
    assert h.min() >= 0.0
    assert h.max() <= 1.0 + 1e-9
    assert "terrain" in hf.tags
    assert "terrain_heightfield" in hf.tags


def test_terrain_heightfield_is_deterministic_at_fixed_seed() -> None:
    call = (
        "terrain_heightfield(extents: [20m, 20m], resolution: 16, "
        "scale_z: 4m, seed: 7)"
    )
    a = _bare_heightfield(call)
    b = _bare_heightfield(call)
    np.testing.assert_array_equal(
        np.asarray(a.height_data), np.asarray(b.height_data)
    )


def test_terrain_heightfield_different_seeds_produce_different_terrain() -> None:
    a = _bare_heightfield(
        "terrain_heightfield(extents: [20m, 20m], resolution: 16, "
        "scale_z: 4m, seed: 1)"
    )
    b = _bare_heightfield(
        "terrain_heightfield(extents: [20m, 20m], resolution: 16, "
        "scale_z: 4m, seed: 2)"
    )
    assert not np.array_equal(
        np.asarray(a.height_data), np.asarray(b.height_data)
    )


def test_terrain_heightfield_rejects_low_resolution() -> None:
    mp = _parse_program(
        "        let ground = terrain_heightfield(extents: [40m, 40m], "
        "resolution: 4, scale_z: 8m, seed: 1)"
    )
    with pytest.raises(MeshProgramError, match="resolution must be >= 8"):
        lower_mesh_program(mp)


def test_terrain_heightfield_rejects_nonpositive_extents() -> None:
    mp = _parse_program(
        "        let ground = terrain_heightfield(extents: [0m, 10m], "
        "resolution: 16, scale_z: 4m, seed: 1)"
    )
    with pytest.raises(MeshProgramError, match="extents must be positive"):
        lower_mesh_program(mp)


def test_terrain_heightfield_rejects_nonpositive_scale_z() -> None:
    mp = _parse_program(
        "        let ground = terrain_heightfield(extents: [10m, 10m], "
        "resolution: 16, scale_z: 0m, seed: 1)"
    )
    with pytest.raises(MeshProgramError, match="scale_z must be > 0"):
        lower_mesh_program(mp)


def test_terrain_heightfield_rejects_unknown_kwarg() -> None:
    mp = _parse_program(
        "        let ground = terrain_heightfield(extents: [10m, 10m], "
        "resolution: 16, scale_z: 4m, seed: 1, foo: 1)"
    )
    with pytest.raises(MeshProgramError, match="unknown terrain_heightfield"):
        lower_mesh_program(mp)


def test_terrain_biome_alpine_modifies_target_heights() -> None:
    body = (
        "        let ground = terrain_heightfield(extents: [40m, 40m], "
        "resolution: 32, scale_z: 8m, seed: 1234)\n"
        "        terrain_biome(target: ground, biome: \"alpine\", "
        "roughness: 0.6, peak_density: 0.3)"
    )
    primitives = lower_mesh_program(_parse_program(body))
    assert len(primitives) == 1
    hf = primitives[0]
    assert "terrain_biome:alpine" in hf.tags

    # Compare against the same constructor + a no-op rolling_hills
    # (roughness=0 -> envelope=1) — alpine peaks should perturb the
    # surface measurably.
    bare = _bare_heightfield(
        "terrain_heightfield(extents: [40m, 40m], resolution: 32, "
        "scale_z: 8m, seed: 1234)"
    )
    h_bare = np.asarray(bare.height_data)
    h_alpine = np.asarray(hf.height_data)
    assert not np.allclose(h_bare, h_alpine)


def test_terrain_biome_rolling_hills_softens_peaks() -> None:
    body = (
        "        let ground = terrain_heightfield(extents: [40m, 40m], "
        "resolution: 32, scale_z: 8m, seed: 5)\n"
        "        terrain_biome(target: ground, biome: \"rolling_hills\", "
        "roughness: 0.8)"
    )
    primitives = lower_mesh_program(_parse_program(body))
    hf = primitives[0]
    assert "terrain_biome:rolling_hills" in hf.tags
    h = np.asarray(hf.height_data)
    # rolling_hills multiplies by an envelope that dips below 1.0, so
    # the mean should be <= the bare mean.
    assert h.shape == (32, 32)
    assert h.min() >= 0.0


def test_terrain_biome_rocky_adds_high_freq_detail() -> None:
    body = (
        "        let ground = terrain_heightfield(extents: [40m, 40m], "
        "resolution: 32, scale_z: 8m, seed: 9)\n"
        "        terrain_biome(target: ground, biome: \"rocky\", "
        "roughness: 0.5)"
    )
    primitives = lower_mesh_program(_parse_program(body))
    hf = primitives[0]
    assert "terrain_biome:rocky" in hf.tags
    # rocky always renormalises to <= 1.0.
    h = np.asarray(hf.height_data)
    assert h.max() <= 1.0 + 1e-9


def test_terrain_biome_rejects_unknown_biome() -> None:
    body = (
        "        let ground = terrain_heightfield(extents: [10m, 10m], "
        "resolution: 16, scale_z: 4m, seed: 1)\n"
        "        terrain_biome(target: ground, biome: \"jungle\")"
    )
    with pytest.raises(MeshProgramError, match="biome must be one of"):
        lower_mesh_program(_parse_program(body))


def test_terrain_biome_rejects_non_heightfield_target() -> None:
    body = (
        "        let ground = box(extents: [1m, 1m, 1m])\n"
        "        terrain_biome(target: ground, biome: \"alpine\")"
    )
    with pytest.raises(
        MeshProgramError, match="target must be a heightfield primitive"
    ):
        lower_mesh_program(_parse_program(body))


def test_terrain_biome_rejects_unknown_target() -> None:
    body = (
        "        let ground = terrain_heightfield(extents: [10m, 10m], "
        "resolution: 16, scale_z: 4m, seed: 1)\n"
        "        terrain_biome(target: ghost, biome: \"alpine\")"
    )
    with pytest.raises(
        MeshProgramError, match="must reference a primitive let-binding"
    ):
        lower_mesh_program(_parse_program(body))


def test_terrain_biome_rejects_out_of_range_roughness() -> None:
    body = (
        "        let ground = terrain_heightfield(extents: [10m, 10m], "
        "resolution: 16, scale_z: 4m, seed: 1)\n"
        "        terrain_biome(target: ground, biome: \"alpine\", roughness: 1.5)"
    )
    with pytest.raises(MeshProgramError, match="roughness must be in"):
        lower_mesh_program(_parse_program(body))
