"""Tests for the Phase 3 first-slice vegetation primitive ops.

Covers ``vegetation_trunk`` (single ``lofted_solid`` constructor with
taper + gentle bend) and ``vegetation_canopy`` (compound op emitting
branch cylinders + leaf spheres anchored on a trunk top).
"""

from __future__ import annotations

import pytest
from lathe.mesh_program import MeshProgramError, lower_mesh_program
from lathe.parser.imports import parse_text


def _parse_program(body: str) -> dict:
    src = (
        "module demo.veg_test\n"
        "asset veg_test : hard_surface_prop {\n"
        "  intent { role = \"veg test\" }\n"
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


def test_vegetation_trunk_emits_lofted_solid_with_taper() -> None:
    mp = _parse_program(
        "        let trunk = vegetation_trunk(height: 4m, base_radius: 25cm, "
        "taper: 0.4, segments: 6)\n"
        "        let cutout = box(extents: [1cm, 1cm, 1cm])\n"
        "        let r = boolean(op: subtract, a: trunk, b: cutout, seam_group: \"s\")"
    )
    primitives = lower_mesh_program(mp)
    trunk = primitives[0]
    assert trunk.primitive_type == "lofted_solid"
    assert trunk.cross_sections is not None
    assert trunk.section_centers is not None
    # 6 segments -> 7 ring sections.
    assert len(trunk.cross_sections) == 7
    assert len(trunk.section_centers) == 7
    # Base radius == 25cm, top radius == 25 * (1 - 0.4) == 15cm.
    base_section = trunk.cross_sections[0]
    top_section = trunk.cross_sections[-1]
    base_r = max(abs(p[0]) for p in base_section)
    top_r = max(abs(p[0]) for p in top_section)
    assert base_r == pytest.approx(25.0, rel=1e-3)
    assert top_r == pytest.approx(15.0, rel=1e-3)
    # Last section should be ~400cm above the first along Y.
    first = trunk.section_centers[0]
    last = trunk.section_centers[-1]
    assert (last[1] - first[1]) == pytest.approx(400.0, rel=0.01)
    assert "vegetation" in trunk.tags
    assert "vegetation_trunk" in trunk.tags


def test_vegetation_trunk_zero_bend_is_perfectly_straight() -> None:
    mp = _parse_program(
        "        let trunk = vegetation_trunk(height: 2m, base_radius: 10cm, "
        "taper: 0.0, segments: 4, bend: 0.0)\n"
        "        let cutout = box(extents: [1cm, 1cm, 1cm])\n"
        "        let r = boolean(op: subtract, a: trunk, b: cutout, seam_group: \"s\")"
    )
    primitives = lower_mesh_program(mp)
    trunk = primitives[0]
    # All section centers should share x=0, z=0 (no bend).
    for center in (trunk.section_centers or []):
        assert center[0] == pytest.approx(0.0, abs=1e-9)
        assert center[2] == pytest.approx(0.0, abs=1e-9)
    # taper=0 -> base_r == top_r.
    base_r = max(abs(p[0]) for p in (trunk.cross_sections or [[]])[0])
    top_r = max(abs(p[0]) for p in (trunk.cross_sections or [[]])[-1])
    assert base_r == pytest.approx(top_r, rel=1e-6)


def test_vegetation_trunk_rejects_invalid_segments() -> None:
    mp = _parse_program(
        "        let trunk = vegetation_trunk(height: 2m, base_radius: 10cm, "
        "taper: 0.3, segments: 1)\n"
        "        let cutout = box(extents: [1cm, 1cm, 1cm])\n"
        "        let r = boolean(op: subtract, a: trunk, b: cutout, seam_group: \"s\")"
    )
    with pytest.raises(MeshProgramError, match="segments must be >= 2"):
        lower_mesh_program(mp)


def test_vegetation_trunk_rejects_invalid_taper() -> None:
    mp = _parse_program(
        "        let trunk = vegetation_trunk(height: 2m, base_radius: 10cm, "
        "taper: 1.5, segments: 4)\n"
        "        let cutout = box(extents: [1cm, 1cm, 1cm])\n"
        "        let r = boolean(op: subtract, a: trunk, b: cutout, seam_group: \"s\")"
    )
    with pytest.raises(MeshProgramError, match="taper must be in"):
        lower_mesh_program(mp)


def test_vegetation_canopy_emits_branches_and_leaves() -> None:
    mp = _parse_program(
        "        let trunk = vegetation_trunk(height: 4m, base_radius: 25cm, "
        "taper: 0.4, segments: 6)\n"
        "        vegetation_canopy(parent: trunk, branch_count: 10, "
        "leaf_density: 60, leaf_size: 6cm, foliage_radius: 140cm)"
    )
    primitives = lower_mesh_program(mp)
    # 1 trunk + 10 branches + 60 leaves == 71.
    assert len(primitives) == 71
    branches = [p for p in primitives if "vegetation_branch" in p.tags]
    leaves = [p for p in primitives if "vegetation_leaf" in p.tags]
    assert len(branches) == 10
    assert len(leaves) == 60
    # Branches are cylinders, leaves are spheres.
    for branch in branches:
        assert branch.primitive_type == "cylinder"
        assert branch.radius is not None and branch.radius > 0.0
        assert branch.height is not None and branch.height > 0.0
    for leaf in leaves:
        assert leaf.primitive_type == "sphere"
        assert leaf.radius == pytest.approx(6.0, rel=1e-6)


def test_vegetation_canopy_skeleton_only() -> None:
    mp = _parse_program(
        "        let trunk = vegetation_trunk(height: 2m, base_radius: 12cm, "
        "taper: 0.3, segments: 4)\n"
        "        vegetation_canopy(parent: trunk, branch_count: 4, "
        "leaf_density: 0, leaf_size: 4cm, foliage_radius: 80cm)"
    )
    primitives = lower_mesh_program(mp)
    # 1 trunk + 4 branches + 0 leaves.
    assert len(primitives) == 5
    leaves = [p for p in primitives if "vegetation_leaf" in p.tags]
    assert leaves == []


def test_vegetation_canopy_rejects_bad_branch_count() -> None:
    mp = _parse_program(
        "        let trunk = vegetation_trunk(height: 2m, base_radius: 10cm, "
        "taper: 0.3, segments: 4)\n"
        "        vegetation_canopy(parent: trunk, branch_count: 0, "
        "leaf_density: 10, leaf_size: 2cm, foliage_radius: 50cm)"
    )
    with pytest.raises(MeshProgramError, match="branch_count must be >= 1"):
        lower_mesh_program(mp)


def test_vegetation_canopy_rejects_unknown_parent() -> None:
    mp = _parse_program(
        "        let trunk = vegetation_trunk(height: 2m, base_radius: 10cm, "
        "taper: 0.3, segments: 4)\n"
        "        vegetation_canopy(parent: ghost, branch_count: 4, "
        "leaf_density: 10, leaf_size: 2cm, foliage_radius: 50cm)"
    )
    with pytest.raises(MeshProgramError, match="must reference a primitive let-binding"):
        lower_mesh_program(mp)


def test_vegetation_canopy_branches_anchored_above_trunk() -> None:
    # Trunk is 4m tall (base at y=0, top ~y=400). Branches should be
    # centered above the trunk top, not below it.
    mp = _parse_program(
        "        let trunk = vegetation_trunk(height: 4m, base_radius: 25cm, "
        "taper: 0.4, segments: 6, bend: 0.0)\n"
        "        vegetation_canopy(parent: trunk, branch_count: 6, "
        "leaf_density: 30, leaf_size: 6cm, foliage_radius: 100cm)"
    )
    primitives = lower_mesh_program(mp)
    branches = [p for p in primitives if "vegetation_branch" in p.tags]
    # Branch midpoint Y should sit above the trunk's top (y=400), since
    # branches lean outward+upward from the top.
    for branch in branches:
        assert branch.center[1] > 380.0
