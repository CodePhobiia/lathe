"""Golden geometry fixtures (GEO-8).

Five synthetic scenes are built in-test via the Manifold geometry
kernel and then probed for watertightness, body count, and triangle
count. The triangle counts are pinned after the first successful run —
Manifold3d is deterministic under a fixed segment count, so re-runs
must reproduce the pinned values exactly. If Manifold changes its
triangulation strategy, update the pinned values intentionally and
note the change in the commit.

Skips cleanly when ``manifold3d`` is not importable, so CI stays green
on installs that omit the ``geometry`` extra.
"""

from __future__ import annotations

import unittest

import pytest
from lathe.geometry import resolve_geometry_kernel

pytestmark = pytest.mark.golden

try:
    import manifold3d  # type: ignore[import-untyped]  # noqa: F401

    MANIFOLD_AVAILABLE = True
except ImportError:  # pragma: no cover — environment-dependent
    MANIFOLD_AVAILABLE = False


_SEGMENTS = 32


@pytest.mark.skipif(not MANIFOLD_AVAILABLE, reason="manifold3d required")
class GeometryFixtureTests(unittest.TestCase):
    """Deterministic CSG fixture probes under the Manifold kernel.

    Pinned triangle counts come from the first successful run against
    ``manifold3d`` with ``circular_segments=32``; re-pin only on an
    intentional kernel/segment change.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.kernel = resolve_geometry_kernel(
            {"runtime": {"geometry": {"backend": "lathe.geometry.manifold_v1"}}}
        )

    def _probe(self, handle: object) -> tuple[bool, int, int]:
        mesh = self.kernel.to_trimesh(handle)
        watertight = bool(self.kernel.is_watertight(handle))
        body_count = int(self.kernel.body_count(handle))
        tri_count = len(mesh.faces)
        return watertight, body_count, tri_count

    def test_box_scene(self) -> None:
        handle = self.kernel.build_primitive("box", extents=(2.0, 2.0, 2.0))
        watertight, body_count, tri_count = self._probe(handle)
        self.assertTrue(watertight)
        self.assertEqual(body_count, 1)
        # Pinned: manifold3d cube → 12 tris.
        self.assertEqual(tri_count, 12)

    def test_box_with_hole_scene(self) -> None:
        box = self.kernel.build_primitive("box", extents=(2.0, 2.0, 2.0))
        hole = self.kernel.build_primitive("cylinder", radius=0.5, height=3.0, axis="z", segments=_SEGMENTS)
        handle = self.kernel.difference(box, hole)
        watertight, body_count, tri_count = self._probe(handle)
        self.assertTrue(watertight)
        self.assertEqual(body_count, 1)
        # Pinned: box \ z-aligned cylinder at 32 segments -> 140 tris on manifold3d 2.5.
        self.assertEqual(tri_count, 140)

    def test_two_touching_boxes_scene(self) -> None:
        left = self.kernel.build_primitive("box", extents=(1.0, 1.0, 1.0), center=(-0.5, 0.0, 0.0))
        right = self.kernel.build_primitive("box", extents=(1.0, 1.0, 1.0), center=(0.5, 0.0, 0.0))
        handle = self.kernel.union(left, right)
        watertight, body_count, tri_count = self._probe(handle)
        self.assertTrue(watertight)
        self.assertEqual(body_count, 1)
        # Pinned: face-sharing union fuses into a single box → 12 tris.
        self.assertEqual(tri_count, 12)

    def test_sphere_scene(self) -> None:
        handle = self.kernel.build_primitive("sphere", radius=1.0, segments=_SEGMENTS)
        watertight, body_count, tri_count = self._probe(handle)
        self.assertTrue(watertight)
        self.assertEqual(body_count, 1)
        # Pinned: 32-segment manifold sphere → 512 tris.
        self.assertEqual(tri_count, 512)

    def test_torus_scene(self) -> None:
        # A "torus" approximated as (outer cylinder \ inner cylinder) - the
        # manifold kernel has no native torus. The combination is a
        # deterministic fixture with a single body and a hollow core.
        outer = self.kernel.build_primitive("cylinder", radius=1.0, height=0.4, axis="y", segments=_SEGMENTS)
        inner = self.kernel.build_primitive("cylinder", radius=0.5, height=1.0, axis="y", segments=_SEGMENTS)
        handle = self.kernel.difference(outer, inner)
        watertight, body_count, tri_count = self._probe(handle)
        self.assertTrue(watertight)
        self.assertEqual(body_count, 1)
        # Pinned: 32-segment cylinder \ 32-segment cylinder -> 192 tris.
        self.assertEqual(tri_count, 192)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
