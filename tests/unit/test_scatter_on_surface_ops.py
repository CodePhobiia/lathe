"""Tests for V1.4 §7.x mesh_program ``scatter_on_surface`` op.

Covers:

* Density scales with target surface area (count = density * area_m2).
* Sampled instance centers lie on (or within numerical tolerance of)
  the target's surface mesh.
* ``align_to_normal=true`` rotates the template so its local +Z axis
  matches the face normal at the sample point.
* ``jitter`` is deterministic given the same seed/inputs.
* Validation rejections (negative density, count > cap, missing args,
  non-primitive bindings, unknown identifiers).
"""

from __future__ import annotations

import numpy as np
import pytest

from lathe.exact_solids import _primitive_mesh
from lathe.mesh_program import MeshProgramError, lower_mesh_program
from lathe.parser.imports import parse_text


def _parse_program(body: str) -> dict:
    src = (
        "module demo.scatter_surface_test\n"
        "asset scatter_surface_test : hard_surface_prop {\n"
        "  intent { role = \"scatter surface test\" }\n"
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


# ---------------------------------------------------------------------------
# Density / count behaviour
# ---------------------------------------------------------------------------


def test_density_scales_count_to_target_surface_area() -> None:
    # 20 m × 20 m = 400 m² × 0.5/m² = 200 (≈ within sampling rounding).
    mp = _parse_program(
        "let ground = terrain_heightfield("
        "extents: [20m, 20m], resolution: 32, scale_z: 2m, seed: 5)\n"
        "        let pebble = solid_cylinder("
        "radius: 8cm, height: 5cm, axis: \"y\")\n"
        "        scatter_on_surface(primitive: pebble, target: ground, "
        "density: 0.5, seed: 7)"
    )
    primitives = lower_mesh_program(mp)
    pebbles = [p for p in primitives if p.primitive_type == "cylinder"]
    # The actual terrain area is slightly larger than 400 m² because the
    # heightfield is undulating — count tracks the real area, not the
    # XY projection. Loose-enough tolerance for that variance.
    assert 195 <= len(pebbles) <= 240


def test_density_scales_proportionally_to_density_value() -> None:
    # 1 m × 1 m × 1 m box has 6 m² of surface area. density=1.0 → 6 copies.
    body_lo = (
        "let ground = box(extents: [1m, 1m, 1m])\n"
        "        let pebble = solid_cylinder("
        "radius: 1cm, height: 1cm, axis: \"y\")\n"
        "        scatter_on_surface(primitive: pebble, target: ground, "
        "density: 1.0, seed: 1)"
    )
    body_hi = body_lo.replace("density: 1.0", "density: 4.0")
    prims_lo = lower_mesh_program(_parse_program(body_lo))
    prims_hi = lower_mesh_program(_parse_program(body_hi))
    n_lo = len([p for p in prims_lo if p.primitive_type == "cylinder"])
    n_hi = len([p for p in prims_hi if p.primitive_type == "cylinder"])
    # Box surface area = 6 m² × density gives the count.
    assert n_lo == 6
    assert n_hi == 24


def test_target_appears_in_primitive_output() -> None:
    # Even when nothing else references the target after scatter, the
    # heightfield must land in the output so the GLB shows the terrain.
    mp = _parse_program(
        "let ground = terrain_heightfield("
        "extents: [10m, 10m], resolution: 16, scale_z: 1m, seed: 3)\n"
        "        let pebble = solid_cylinder("
        "radius: 5cm, height: 3cm, axis: \"y\")\n"
        "        scatter_on_surface(primitive: pebble, target: ground, "
        "density: 0.05, seed: 1)"
    )
    primitives = lower_mesh_program(mp)
    terrains = [p for p in primitives if p.primitive_type == "heightfield"]
    assert len(terrains) == 1


# ---------------------------------------------------------------------------
# Surface coplanarity
# ---------------------------------------------------------------------------


def test_sampled_centers_lie_on_target_surface() -> None:
    # On an axis-aligned box, every surface sample must satisfy at
    # least one of |center[axis] - half_extent| ~ 0 — i.e. it sits on
    # one of the six faces. Verifies the kernel is sampling the actual
    # surface, not the volume.
    mp = _parse_program(
        "let slab = box(extents: [10m, 10m, 10m])\n"
        "        let dot = solid_cylinder("
        "radius: 1cm, height: 1cm, axis: \"y\")\n"
        "        scatter_on_surface(primitive: dot, target: slab, "
        "density: 0.5, seed: 11)"
    )
    primitives = lower_mesh_program(mp)
    slab = next(p for p in primitives if p.primitive_type == "box")
    dots = [p for p in primitives if p.primitive_type == "cylinder"]
    half_x = float(slab.extents[0]) * 0.5
    half_y = float(slab.extents[1]) * 0.5
    half_z = float(slab.extents[2]) * 0.5
    cx, cy, cz = slab.center
    tol = 1e-3
    for inst in dots:
        x, y, z = inst.center
        on_x = (
            abs((x - cx) - half_x) < tol or abs((x - cx) + half_x) < tol
        )
        on_y = (
            abs((y - cy) - half_y) < tol or abs((y - cy) + half_y) < tol
        )
        on_z = (
            abs((z - cz) - half_z) < tol or abs((z - cz) + half_z) < tol
        )
        assert on_x or on_y or on_z, (
            f"center {inst.center} is not on the slab's surface"
        )


# ---------------------------------------------------------------------------
# align_to_normal rotation
# ---------------------------------------------------------------------------


def test_align_to_normal_rotates_template_z_to_face_normal() -> None:
    # Tall slab: top face normal is +Z, side face normal is ±X/±Y.
    # An aligned cylinder template (axis y) gets baked to sdf_mesh
    # vertices such that its local +Z direction matches the face normal
    # at every sample point. Verify the bake by checking that the
    # bounding box of each baked instance is no longer axis-aligned to
    # the world (its long axis has been rotated to follow the face).
    mp = _parse_program(
        "let slab = box(extents: [10m, 1m, 10m])\n"
        "        let pin = solid_cylinder("
        "radius: 5cm, height: 30cm, axis: \"z\")\n"
        "        scatter_on_surface(primitive: pin, target: slab, "
        "density: 1.0, seed: 19, align_to_normal: true)"
    )
    primitives = lower_mesh_program(mp)
    aligned = [
        p for p in primitives
        if p.primitive_type == "sdf_mesh"
        and any("scatter_on_surface_aligned" in t for t in p.tags)
    ]
    assert aligned, "expected align_to_normal=true to bake to sdf_mesh"
    # For each baked instance, the principal direction of the vertex
    # cloud (~the original cylinder Z-axis) should agree with the face
    # normal, not with world +Z. Sample a few and check they are not
    # all aligned to world +Z (which would mean rotation was a no-op).
    world_z = np.array([0.0, 0.0, 1.0], dtype=np.float64)
    n_world_aligned = 0
    for inst in aligned:
        verts = np.array(inst.mesh_vertices, dtype=np.float64)
        verts = verts - verts.mean(axis=0)
        # Principal axis via SVD: largest singular vector ≈ cylinder axis.
        _, _, vh = np.linalg.svd(verts, full_matrices=False)
        principal = vh[0]
        if abs(abs(float(np.dot(principal, world_z))) - 1.0) < 1e-3:
            n_world_aligned += 1
    # On a thin slab almost all faces have non-vertical normals (sides
    # dominate area). At most a small fraction can still be world-Z.
    assert n_world_aligned < 0.5 * len(aligned)


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_jitter_is_deterministic_for_same_seed() -> None:
    body = (
        "let slab = box(extents: [5m, 5m, 5m])\n"
        "        let dot = solid_cylinder("
        "radius: 1cm, height: 1cm, axis: \"y\")\n"
        "        scatter_on_surface(primitive: dot, target: slab, "
        "density: 1.0, seed: 42, jitter: 5cm)"
    )
    centers_a = sorted(
        (p.center for p in lower_mesh_program(_parse_program(body))
         if p.primitive_type == "cylinder")
    )
    centers_b = sorted(
        (p.center for p in lower_mesh_program(_parse_program(body))
         if p.primitive_type == "cylinder")
    )
    assert centers_a == centers_b


def test_different_seeds_produce_different_distributions() -> None:
    body_a = (
        "let slab = box(extents: [5m, 5m, 5m])\n"
        "        let dot = solid_cylinder("
        "radius: 1cm, height: 1cm, axis: \"y\")\n"
        "        scatter_on_surface(primitive: dot, target: slab, "
        "density: 1.0, seed: 1)"
    )
    body_b = body_a.replace("seed: 1", "seed: 999")
    centers_a = sorted(
        (p.center for p in lower_mesh_program(_parse_program(body_a))
         if p.primitive_type == "cylinder")
    )
    centers_b = sorted(
        (p.center for p in lower_mesh_program(_parse_program(body_b))
         if p.primitive_type == "cylinder")
    )
    assert centers_a != centers_b


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_rejects_negative_density() -> None:
    mp = _parse_program(
        "let slab = box(extents: [1m, 1m, 1m])\n"
        "        let dot = solid_cylinder("
        "radius: 1cm, height: 1cm, axis: \"y\")\n"
        "        scatter_on_surface(primitive: dot, target: slab, "
        "density: -1.0)"
    )
    with pytest.raises(MeshProgramError, match="density must be >= 0"):
        lower_mesh_program(mp)


def test_rejects_count_above_cap() -> None:
    # density=10 on a 100 m² box surface → 1000; need bigger to exceed.
    # 100 m × 100 m × 100 m box has 60000 m² surface, density=1 → 60000.
    mp = _parse_program(
        "let slab = box(extents: [100m, 100m, 100m])\n"
        "        let dot = solid_cylinder("
        "radius: 1cm, height: 1cm, axis: \"y\")\n"
        "        scatter_on_surface(primitive: dot, target: slab, "
        "density: 1.0)"
    )
    with pytest.raises(MeshProgramError, match="exceeds the .* cap"):
        lower_mesh_program(mp)


def test_rejects_zero_count() -> None:
    # 1 m² with density 0 yields count=0 — caller should be told.
    mp = _parse_program(
        "let slab = box(extents: [1m, 1m, 1m])\n"
        "        let dot = solid_cylinder("
        "radius: 1cm, height: 1cm, axis: \"y\")\n"
        "        scatter_on_surface(primitive: dot, target: slab, "
        "density: 0.0)"
    )
    with pytest.raises(MeshProgramError, match="nothing to scatter"):
        lower_mesh_program(mp)


def test_rejects_unknown_target_identifier() -> None:
    mp = _parse_program(
        "let dot = solid_cylinder("
        "radius: 1cm, height: 1cm, axis: \"y\")\n"
        "        scatter_on_surface(primitive: dot, target: ghost, "
        "density: 1.0)"
    )
    with pytest.raises(MeshProgramError, match="unknown identifier 'ghost'"):
        lower_mesh_program(mp)


def test_rejects_unknown_primitive_identifier() -> None:
    mp = _parse_program(
        "let slab = box(extents: [1m, 1m, 1m])\n"
        "        scatter_on_surface(primitive: ghost, target: slab, "
        "density: 1.0)"
    )
    with pytest.raises(MeshProgramError, match="unknown identifier 'ghost'"):
        lower_mesh_program(mp)


def test_rejects_non_primitive_target() -> None:
    # A point_set is not a primitive — scatter_on_surface must reject it.
    mp = _parse_program(
        "let dot = solid_cylinder("
        "radius: 1cm, height: 1cm, axis: \"y\")\n"
        "        let pts = points_grid(extents: [4cm, 4cm], rows: 2, cols: 2)\n"
        "        scatter_on_surface(primitive: dot, target: pts, "
        "density: 1.0)"
    )
    with pytest.raises(MeshProgramError, match="'target' must reference a primitive"):
        lower_mesh_program(mp)


def test_rejects_non_primitive_template() -> None:
    mp = _parse_program(
        "let slab = box(extents: [1m, 1m, 1m])\n"
        "        let pts = points_grid(extents: [4cm, 4cm], rows: 2, cols: 2)\n"
        "        scatter_on_surface(primitive: pts, target: slab, "
        "density: 1.0)"
    )
    with pytest.raises(MeshProgramError, match="'primitive' must reference a primitive"):
        lower_mesh_program(mp)


def test_rejects_negative_jitter() -> None:
    mp = _parse_program(
        "let slab = box(extents: [1m, 1m, 1m])\n"
        "        let dot = solid_cylinder("
        "radius: 1cm, height: 1cm, axis: \"y\")\n"
        "        scatter_on_surface(primitive: dot, target: slab, "
        "density: 1.0, jitter: -1mm)"
    )
    with pytest.raises(MeshProgramError, match="jitter must be >= 0"):
        lower_mesh_program(mp)


def test_rejects_missing_required_args() -> None:
    mp = _parse_program(
        "let slab = box(extents: [1m, 1m, 1m])\n"
        "        let dot = solid_cylinder("
        "radius: 1cm, height: 1cm, axis: \"y\")\n"
        "        scatter_on_surface(primitive: dot, target: slab)"
    )
    with pytest.raises(MeshProgramError, match="requires 'density'"):
        lower_mesh_program(mp)


def test_rejects_unknown_arg() -> None:
    mp = _parse_program(
        "let slab = box(extents: [1m, 1m, 1m])\n"
        "        let dot = solid_cylinder("
        "radius: 1cm, height: 1cm, axis: \"y\")\n"
        "        scatter_on_surface(primitive: dot, target: slab, "
        "density: 1.0, mystery: 1.0)"
    )
    with pytest.raises(MeshProgramError, match="unknown scatter_on_surface"):
        lower_mesh_program(mp)


def test_emits_scatter_on_surface_tags() -> None:
    mp = _parse_program(
        "let slab = box(extents: [3m, 3m, 3m])\n"
        "        let dot = solid_cylinder("
        "radius: 1cm, height: 1cm, axis: \"y\")\n"
        "        scatter_on_surface(primitive: dot, target: slab, "
        "density: 1.0, seed: 0)"
    )
    primitives = lower_mesh_program(mp)
    dots = [p for p in primitives if p.primitive_type == "cylinder"]
    assert dots
    for inst in dots:
        assert any(t.startswith("scatter_on_surface:") for t in inst.tags)
        assert "scatter_on_surface" in inst.tags
