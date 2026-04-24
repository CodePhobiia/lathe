"""Manifold kernel adapter (GEO-1, V0.2 E2 evaluation).

Thin wrapper around manifold3d for CSG ops Lathe's shape stage cares
about: union, difference, intersection, convex hull, plus primitive
construction and trimesh round-trip. This adapter is evaluation-only:
nothing in the executor or `lathe/geometry_kernel.py` depends on it.

See `docs/geometry_kernel_eval.md` for the ADOPT/ADAPT/REJECT decision.
"""

from __future__ import annotations

import math
from typing import Any, Iterable

import numpy as np
import trimesh

try:
    import manifold3d as _m3d
    _MANIFOLD_AVAILABLE = True
    _IMPORT_ERROR: str | None = None
except ImportError as exc:
    _m3d = None
    _MANIFOLD_AVAILABLE = False
    _IMPORT_ERROR = str(exc)


class ManifoldKernelUnavailable(RuntimeError):
    """Raised when manifold3d is not importable."""


class ManifoldMesh:
    """Opaque handle wrapping a `manifold3d.Manifold` object.

    Exposes a minimal interface so call sites don't touch the underlying
    binding directly.
    """

    __slots__ = ("_m",)

    def __init__(self, manifold: Any) -> None:
        self._m = manifold

    @property
    def raw(self) -> Any:
        return self._m

    def is_empty(self) -> bool:
        return bool(self._m.is_empty())

    def num_tri(self) -> int:
        return int(self._m.num_tri())

    def num_vert(self) -> int:
        return int(self._m.num_vert())

    def volume(self) -> float:
        return float(self._m.volume())

    def genus(self) -> int:
        return int(self._m.genus())


class ManifoldKernel:
    """Adapter exposing CSG ops over manifold3d.

    Mirrors only the op surface `scripts/bench_geometry_kernel.py` and
    candidate GEO-2 integration need: primitives, union, difference,
    intersection, convex hull, trimesh conversion, watertight + body
    count probes.
    """

    name = "lathe.geometry.manifold_v1"
    version = "0.1"

    def __init__(self) -> None:
        if not _MANIFOLD_AVAILABLE:
            raise ManifoldKernelUnavailable(
                f"manifold3d unavailable: {_IMPORT_ERROR!r}. "
                "Install with `pip install manifold3d` or the "
                "`geometry` extra."
            )

    def probe(self) -> dict[str, Any]:
        """Availability + capability flags. Safe to call without install."""
        payload: dict[str, Any] = {
            "name": self.name,
            "version": self.version,
            "available": _MANIFOLD_AVAILABLE,
        }
        if _MANIFOLD_AVAILABLE:
            payload["manifold3d_module_dir"] = sorted(
                attr for attr in dir(_m3d) if not attr.startswith("_")
            )
            payload["capabilities"] = {
                "union": True,
                "difference": True,
                "intersection": True,
                "hull": True,
                "convex_hull_points": True,
                "watertight_by_construction": True,
                "body_count": True,
                "to_trimesh": True,
            }
        else:
            payload["import_error"] = _IMPORT_ERROR
        return payload

    def build_primitive(self, kind: str, **params: Any) -> ManifoldMesh:
        """Create a primitive Manifold.

        Supported kinds: `box` (extents + optional center), `cylinder`
        (radius + height + axis + optional center), `sphere` (radius
        + optional center).
        """
        if kind == "box":
            extents = params.get("extents")
            if extents is None:
                raise ValueError("box requires `extents` (3-tuple)")
            center = params.get("center", (0.0, 0.0, 0.0))
            manifold = _m3d.Manifold.cube(list(map(float, extents)), center=True)
            manifold = manifold.translate(list(map(float, center)))
            return ManifoldMesh(manifold)

        if kind == "cylinder":
            radius = params.get("radius")
            height = params.get("height")
            if radius is None or height is None:
                raise ValueError("cylinder requires `radius` and `height`")
            axis = params.get("axis", "y")
            center = params.get("center", (0.0, 0.0, 0.0))
            segments = int(params.get("segments", 32))
            manifold = _m3d.Manifold.cylinder(
                float(height), float(radius), float(radius),
                circular_segments=segments, center=True,
            )
            # Native manifold3d cylinder is z-axis aligned.
            if axis == "x":
                manifold = manifold.rotate([0.0, 90.0, 0.0])
            elif axis == "y":
                manifold = manifold.rotate([90.0, 0.0, 0.0])
            manifold = manifold.translate(list(map(float, center)))
            return ManifoldMesh(manifold)

        if kind == "sphere":
            radius = params.get("radius")
            if radius is None:
                raise ValueError("sphere requires `radius`")
            center = params.get("center", (0.0, 0.0, 0.0))
            segments = int(params.get("segments", 32))
            manifold = _m3d.Manifold.sphere(float(radius), circular_segments=segments)
            manifold = manifold.translate(list(map(float, center)))
            return ManifoldMesh(manifold)

        raise ValueError(f"Unsupported primitive kind: {kind!r}")

    def union(self, a: ManifoldMesh, b: ManifoldMesh) -> ManifoldMesh:
        return ManifoldMesh(a.raw + b.raw)

    def difference(self, a: ManifoldMesh, b: ManifoldMesh) -> ManifoldMesh:
        return ManifoldMesh(a.raw - b.raw)

    def intersection(self, a: ManifoldMesh, b: ManifoldMesh) -> ManifoldMesh:
        return ManifoldMesh(a.raw ^ b.raw)

    def hull(self, meshes: Iterable[ManifoldMesh]) -> ManifoldMesh:
        seq = list(meshes)
        if not seq:
            raise ValueError("hull requires at least one mesh")
        raws = [m.raw for m in seq]
        return ManifoldMesh(_m3d.Manifold.batch_hull(raws))

    def batch_union(self, meshes: Iterable[ManifoldMesh]) -> ManifoldMesh:
        """Reduce a stream of meshes via pairwise union.

        manifold3d exposes `batch_boolean` but the pairwise reduce form
        keeps the adapter surface minimal and matches how Lathe builds
        assemblies primitive-by-primitive.
        """
        it = iter(meshes)
        try:
            acc = next(it).raw
        except StopIteration as exc:
            raise ValueError("batch_union requires at least one mesh") from exc
        for m in it:
            acc = acc + m.raw
        return ManifoldMesh(acc)

    def to_trimesh(self, manifold_mesh: ManifoldMesh) -> trimesh.Trimesh:
        mesh = manifold_mesh.raw.to_mesh()
        verts = np.asarray(mesh.vert_properties, dtype=np.float64)
        # Manifold may emit property columns beyond xyz; take the first 3.
        if verts.shape[1] > 3:
            verts = verts[:, :3]
        tris = np.asarray(mesh.tri_verts, dtype=np.int64)
        return trimesh.Trimesh(vertices=verts, faces=tris, process=False)

    def is_watertight(self, manifold_mesh: ManifoldMesh) -> bool:
        """Manifold is watertight by construction; empty meshes are not."""
        if manifold_mesh.is_empty():
            return False
        return True

    def body_count(self, manifold_mesh: ManifoldMesh) -> int:
        if manifold_mesh.is_empty():
            return 0
        return len(manifold_mesh.raw.decompose())


def manifold_available() -> bool:
    """Module-level probe for test skipping and soft feature-gating."""
    return _MANIFOLD_AVAILABLE
