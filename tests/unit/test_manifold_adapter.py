"""Unit tests for the Manifold kernel adapter (GEO-1).

All tests skip cleanly when manifold3d is not installed; the adapter is
an optional dependency under `[project.optional-dependencies].geometry`.
"""

from __future__ import annotations

import pytest

from lathe.adapters import manifold_kernel as mk

manifold3d_available = mk.manifold_available()

pytestmark = pytest.mark.skipif(
    not manifold3d_available,
    reason="manifold3d is not installed; install via `pip install manifold3d`",
)


@pytest.fixture()
def kernel() -> mk.ManifoldKernel:
    return mk.ManifoldKernel()


def test_probe_reports_available(kernel: mk.ManifoldKernel) -> None:
    payload = kernel.probe()
    assert payload["available"] is True
    assert payload["name"] == "lathe.geometry.manifold_v1"
    assert "capabilities" in payload
    for cap in ("union", "difference", "intersection", "hull", "body_count"):
        assert payload["capabilities"][cap] is True


def test_box_primitive_is_watertight_single_body(kernel: mk.ManifoldKernel) -> None:
    box = kernel.build_primitive("box", extents=(1.0, 1.0, 1.0))
    assert kernel.is_watertight(box) is True
    assert kernel.body_count(box) == 1
    assert box.num_tri() == 12
    assert box.num_vert() == 8
    assert box.volume() == pytest.approx(1.0, rel=1e-9)


def test_union_overlapping_boxes_single_body(kernel: mk.ManifoldKernel) -> None:
    a = kernel.build_primitive("box", extents=(1.0, 1.0, 1.0))
    b = kernel.build_primitive("box", extents=(1.0, 1.0, 1.0), center=(0.5, 0.0, 0.0))
    u = kernel.union(a, b)
    assert kernel.is_watertight(u) is True
    assert kernel.body_count(u) == 1
    assert u.volume() == pytest.approx(1.5, rel=1e-6)


def test_difference_cuts_hole(kernel: mk.ManifoldKernel) -> None:
    outer = kernel.build_primitive("box", extents=(2.0, 2.0, 2.0))
    cutter = kernel.build_primitive("box", extents=(1.0, 1.0, 3.0))
    carved = kernel.difference(outer, cutter)
    assert kernel.is_watertight(carved) is True
    # 8 - 1 (through-cut removes a 1x1x2 column from the 2x2x2 outer)
    assert carved.volume() == pytest.approx(8.0 - 2.0, rel=1e-6)
    assert kernel.body_count(carved) == 1


def test_intersection_offset_cubes_watertight(kernel: mk.ManifoldKernel) -> None:
    a = kernel.build_primitive("box", extents=(1.0, 1.0, 1.0))
    b = kernel.build_primitive("box", extents=(1.0, 1.0, 1.0), center=(0.3, 0.2, 0.1))
    inter = kernel.intersection(a, b)
    assert kernel.is_watertight(inter) is True
    assert kernel.body_count(inter) == 1
    assert inter.volume() == pytest.approx(0.7 * 0.8 * 0.9, rel=1e-6)


def test_empty_hull_input_raises(kernel: mk.ManifoldKernel) -> None:
    with pytest.raises(ValueError):
        kernel.hull([])
    with pytest.raises(ValueError):
        kernel.batch_union([])


def test_unsupported_primitive_raises(kernel: mk.ManifoldKernel) -> None:
    with pytest.raises(ValueError):
        kernel.build_primitive("torus", radius=1.0)
    with pytest.raises(ValueError):
        kernel.build_primitive("box")  # missing extents


def test_round_trip_to_trimesh(kernel: mk.ManifoldKernel) -> None:
    box = kernel.build_primitive("box", extents=(1.0, 1.0, 1.0))
    tri = kernel.to_trimesh(box)
    assert len(tri.vertices) == 8
    assert len(tri.faces) == 12
    assert tri.is_watertight is True
    assert tri.volume == pytest.approx(1.0, rel=1e-6)
