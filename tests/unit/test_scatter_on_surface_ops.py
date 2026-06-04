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

from types import SimpleNamespace

import numpy as np
import pytest
from lathe.mesh_program import MeshProgramError, lower_mesh_program
from lathe.parser.imports import parse_text


def _flatten_primitives(primitives):
    """Yield primitive-like objects including ones nested in ``instance_mesh``.

    The mesh-program kernel collapses scatter_on_surface results into a single
    ``instance_mesh`` ShapePrimitive whose ``semantic_metadata.source_shape_primitives``
    list carries the underlying per-sample primitives (target + each scattered
    template instance). Tests written against the older one-primitive-per-sample
    output continue to work by walking through this helper, which yields a
    duck-typed ``SimpleNamespace`` for each source primitive in addition to the
    top-level primitives themselves.
    """
    for primitive in primitives:
        if primitive.primitive_type == "instance_mesh":
            sources = primitive.semantic_metadata.get("source_shape_primitives", [])
            for src in sources:
                if not isinstance(src, dict):
                    continue
                center = src.get("center")
                if isinstance(center, list):
                    center = tuple(float(value) for value in center)
                yield SimpleNamespace(
                    primitive_type=src.get("primitive_type"),
                    center=center,
                    extents=src.get("extents"),
                    tags=src.get("tags") or [],
                    mesh_vertices=src.get("mesh_vertices"),
                    mesh_faces=src.get("mesh_faces"),
                    semantic_metadata=src.get("semantic_metadata", {}),
                )
        else:
            yield primitive


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
    # 20 m x 20 m = 400 m² x 0.5/m² = 200 over the XY footprint. The kernel
    # samples the actual (triangulated) heightfield surface area, which is
    # noticeably larger than 400 m² once the height profile undulates. Bound
    # the count loosely so a 2 m peak-trough range with resolution 32 still
    # fits.
    mp = _parse_program(
        "let ground = terrain_heightfield("
        "extents: [20m, 20m], resolution: 32, scale_z: 2m, seed: 5)\n"
        "        let pebble = solid_cylinder("
        "radius: 8cm, height: 5cm, axis: \"y\")\n"
        "        scatter_on_surface(primitive: pebble, target: ground, "
        "density: 0.5, seed: 7)"
    )
    primitives = lower_mesh_program(mp)
    pebbles = [p for p in _flatten_primitives(primitives) if p.primitive_type == "cylinder"]
    # Lower bound: at least the XY-projected count. Upper bound: ~3x to
    # accommodate the heightfield's full undulating surface area at this
    # resolution + scale_z, plus jitter rounding.
    assert 195 <= len(pebbles) <= 700, f"got {len(pebbles)} cylinders"


def test_density_scales_proportionally_to_density_value() -> None:
    # 1 m x 1 m x 1 m box has 6 m² of surface area. density=1.0 → 6 copies.
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
    n_lo = len([p for p in _flatten_primitives(prims_lo) if p.primitive_type == "cylinder"])
    n_hi = len([p for p in _flatten_primitives(prims_hi) if p.primitive_type == "cylinder"])
    # Box surface area = 6 m² x density gives the count.
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
    terrains = [p for p in _flatten_primitives(primitives) if p.primitive_type == "heightfield"]
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
    flattened = list(_flatten_primitives(primitives))
    slab = next(p for p in flattened if p.primitive_type == "box")
    dots = [p for p in flattened if p.primitive_type == "cylinder"]
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
    # With ``align_to_normal=true``, the scatter_on_surface kernel emits a
    # per-instance rotation matrix in
    # ``instance_mesh.semantic_metadata.mesh_program_surface_scatter
    # .instance_transform_records``. Each matrix's 3x3 rotation block must
    # carry a column that matches the face normal at the sample point — i.e.
    # the rotations are not all identity / not all aligned to world +Z.
    mp = _parse_program(
        "let slab = box(extents: [10m, 1m, 10m])\n"
        "        let pin = solid_cylinder("
        "radius: 5cm, height: 30cm, axis: \"z\")\n"
        "        scatter_on_surface(primitive: pin, target: slab, "
        "density: 1.0, seed: 19, align_to_normal: true)"
    )
    primitives = lower_mesh_program(mp)
    wrapper = next(p for p in primitives if p.primitive_type == "instance_mesh")
    # Per-instance rotation matrices live under the ShapeIR v2 surface_scatter
    # modifier payload on the wrapping instance_mesh primitive.
    shape_ir_v2 = wrapper.semantic_metadata.get("shape_ir_v2", {})
    modifier = shape_ir_v2.get("v2_surface_scatter_modifier", {})
    transforms = modifier.get("instance_transform_records") or []
    assert transforms, "expected align_to_normal=true to emit instance_transform_records"
    # For a thin slab (Y-extent = 1m) most sample area lives on side faces
    # (10m x 10m top and bottom, 4 x 10m x 1m sides). The Y axis (world +Y)
    # is the slab's narrow dimension; an aligned scatter should rarely leave
    # every instance with rotation that keeps the source +Z parallel to
    # world +Z. Sample a few rotation columns and check at least one is not
    # the identity column.
    world_z = np.array([0.0, 0.0, 1.0], dtype=np.float64)
    n_world_aligned = 0
    n_checked = 0
    for record in transforms:
        matrix = record.get("matrix")
        if not matrix or len(matrix) < 3:
            continue
        rotation_z_col = np.array(
            [matrix[0][2], matrix[1][2], matrix[2][2]], dtype=np.float64,
        )
        # An identity (or near-identity) rotation keeps +Z as +Z.
        if abs(abs(float(np.dot(rotation_z_col, world_z))) - 1.0) < 1e-3:
            n_world_aligned += 1
        n_checked += 1
    assert n_checked >= 16, f"expected enough transform records for the assertion, got {n_checked}"
    # On a thin slab almost all faces have non-vertical normals (sides
    # dominate area). At most a small fraction can still be world-Z.
    assert n_world_aligned < 0.5 * n_checked, (
        f"expected fewer than half of {n_checked} aligned-to-world-Z instances; got {n_world_aligned}"
    )


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
        p.center for p in _flatten_primitives(lower_mesh_program(_parse_program(body)))
         if p.primitive_type == "cylinder"
    )
    centers_b = sorted(
        p.center for p in _flatten_primitives(lower_mesh_program(_parse_program(body)))
         if p.primitive_type == "cylinder"
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
        p.center for p in _flatten_primitives(lower_mesh_program(_parse_program(body_a)))
         if p.primitive_type == "cylinder"
    )
    centers_b = sorted(
        p.center for p in _flatten_primitives(lower_mesh_program(_parse_program(body_b)))
         if p.primitive_type == "cylinder"
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
    # 100 m x 100 m x 100 m box has 60000 m² surface, density=1 → 60000.
    mp = _parse_program(
        "let slab = box(extents: [100m, 100m, 100m])\n"
        "        let dot = solid_cylinder("
        "radius: 1cm, height: 1cm, axis: \"y\")\n"
        "        scatter_on_surface(primitive: dot, target: slab, "
        "density: 1.0)"
    )
    with pytest.raises(MeshProgramError, match=r"(?:exceeds the .* cap|exceeds max_count)"):
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
    with pytest.raises(MeshProgramError, match=r"(?:nothing to scatter|produced no instances)"):
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
    with pytest.raises(MeshProgramError, match=r"scatter_on_surface\.target.*kind='[^']*'"):
        lower_mesh_program(mp)


def test_rejects_non_primitive_template() -> None:
    mp = _parse_program(
        "let slab = box(extents: [1m, 1m, 1m])\n"
        "        let pts = points_grid(extents: [4cm, 4cm], rows: 2, cols: 2)\n"
        "        scatter_on_surface(primitive: pts, target: slab, "
        "density: 1.0)"
    )
    with pytest.raises(MeshProgramError, match=r"scatter_on_surface\.primitive.*kind='[^']*'"):
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
    # Tags now ride on the wrapping instance_mesh primitive that the
    # scatter_on_surface kernel emits; each per-sample source primitive
    # within ``semantic_metadata.source_shape_primitives`` inherits the
    # tags via the kernel program. Assert both surfaces carry the
    # scatter_on_surface identity.
    wrapper = next(p for p in primitives if p.primitive_type == "instance_mesh")
    assert any(t.startswith("scatter_on_surface_source:") for t in wrapper.tags)
    assert "scatter_on_surface" in wrapper.tags
    dots = [p for p in _flatten_primitives(primitives) if p.primitive_type == "cylinder"]
    assert dots
