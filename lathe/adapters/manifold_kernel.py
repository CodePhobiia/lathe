"""Manifold kernel adapter (GEO-1, V0.2 E2 evaluation).

Thin wrapper around manifold3d for CSG ops Lathe's shape stage cares
about: union, difference, intersection, convex hull, plus primitive
construction and trimesh round-trip. This adapter is evaluation-only:
nothing in the executor or `lathe/geometry_kernel.py` depends on it.

See `docs/geometry_kernel_eval.md` for the ADOPT/ADAPT/REJECT decision.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import numpy as np
import trimesh

_XYZ_COLUMN_COUNT = 3

try:
    import manifold3d as _m3d

    _MANIFOLD_AVAILABLE = True
    _IMPORT_ERROR: str | None = None
except ImportError as exc:
    _m3d = None
    _MANIFOLD_AVAILABLE = False
    _IMPORT_ERROR = str(exc)


class ManifoldKernelUnavailableError(RuntimeError):
    """Raised when manifold3d is not importable."""

    def __init__(self, import_error: str | None) -> None:
        """Build the standard unavailable-kernel message."""
        super().__init__(
            f"manifold3d unavailable: {import_error!r}. "
            "Install with `pip install manifold3d` or the `geometry` extra."
        )


ManifoldKernelUnavailable = ManifoldKernelUnavailableError


class _BoxExtentsRequiredError(ValueError):
    def __init__(self) -> None:
        super().__init__("box requires `extents` (3-tuple)")


class _CylinderDimensionsRequiredError(ValueError):
    def __init__(self) -> None:
        super().__init__("cylinder requires `radius` and `height`")


class _SphereRadiusRequiredError(ValueError):
    def __init__(self) -> None:
        super().__init__("sphere requires `radius`")


class _RevolvedProfilePointsRequiredError(ValueError):
    def __init__(self) -> None:
        super().__init__("revolved_profile requires `profile_points` (>= 1 point)")


class _UnsupportedPrimitiveKindError(ValueError):
    def __init__(self, kind: str) -> None:
        super().__init__(f"Unsupported primitive kind: {kind!r}")


class _HullEmptyError(ValueError):
    def __init__(self) -> None:
        super().__init__("hull requires at least one mesh")


class _BatchUnionEmptyError(ValueError):
    def __init__(self) -> None:
        super().__init__("batch_union requires at least one mesh")


class ManifoldMesh:
    """Opaque handle wrapping a `manifold3d.Manifold` object.

    Exposes a minimal interface so call sites don't touch the underlying
    binding directly.
    """

    __slots__ = ("_m",)

    def __init__(self, manifold: Any) -> None:
        """Wrap a raw ``manifold3d.Manifold`` handle."""
        self._m = manifold

    @property
    def raw(self) -> Any:
        """Return the underlying ``manifold3d`` object."""
        return self._m

    def is_empty(self) -> bool:
        """Return whether the wrapped manifold has no volume."""
        return bool(self._m.is_empty())

    def num_tri(self) -> int:
        """Return the triangle count reported by manifold3d."""
        return int(self._m.num_tri())

    def num_vert(self) -> int:
        """Return the vertex count reported by manifold3d."""
        return int(self._m.num_vert())

    def volume(self) -> float:
        """Return the signed volume reported by manifold3d."""
        return float(self._m.volume())

    def genus(self) -> int:
        """Return the manifold genus reported by manifold3d."""
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
        """Validate that the optional manifold3d dependency is importable."""
        if not _MANIFOLD_AVAILABLE:
            raise ManifoldKernelUnavailable(_IMPORT_ERROR)

    def probe(self) -> dict[str, Any]:
        """Availability + capability flags. Safe to call without install."""
        payload: dict[str, Any] = {
            "name": self.name,
            "version": self.version,
            "available": _MANIFOLD_AVAILABLE,
        }
        if _MANIFOLD_AVAILABLE:
            payload["manifold3d_module_dir"] = sorted(attr for attr in dir(_m3d) if not attr.startswith("_"))
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
        + optional center), `revolved_profile` (profile_points +
        optional axis + optional center + optional segments).
        """
        if kind == "revolved_profile":
            profile_points = params.get("profile_points")
            if not profile_points:
                raise _RevolvedProfilePointsRequiredError
            axis = params.get("axis", "y")
            center = params.get("center", (0.0, 0.0, 0.0))
            segments = int(params.get("segments", 48))
            # CrossSection contour: (radial, axial). Close back to the axis
            # at both ends so the revolved manifold is watertight even when
            # the author hands us an open profile.
            axials = [float(a) for a, _ in profile_points]
            first_axial = axials[0]
            last_axial = axials[-1]
            contour: list[tuple[float, float]] = [(0.0, first_axial)]
            for axial, radial in profile_points:
                contour.append((max(0.0, float(radial)), float(axial)))
            contour.append((0.0, last_axial))
            cross_section = _m3d.CrossSection([contour])
            manifold = cross_section.revolve(circular_segments=segments)
            # CrossSection.revolve emits the manifold around the
            # 3D Z-axis. Rotate to the user's chosen axis.
            if axis == "x":
                manifold = manifold.rotate([0.0, 90.0, 0.0])
            elif axis == "y":
                manifold = manifold.rotate([90.0, 0.0, 0.0])
            manifold = manifold.translate(list(map(float, center)))
            return ManifoldMesh(manifold)

        if kind == "box":
            extents = params.get("extents")
            if extents is None:
                raise _BoxExtentsRequiredError
            center = params.get("center", (0.0, 0.0, 0.0))
            manifold = _m3d.Manifold.cube(list(map(float, extents)), center=True)
            manifold = manifold.translate(list(map(float, center)))
            return ManifoldMesh(manifold)

        if kind == "cylinder":
            radius = params.get("radius")
            height = params.get("height")
            if radius is None or height is None:
                raise _CylinderDimensionsRequiredError
            axis = params.get("axis", "y")
            center = params.get("center", (0.0, 0.0, 0.0))
            segments = int(params.get("segments", 32))
            manifold = _m3d.Manifold.cylinder(
                float(height),
                float(radius),
                float(radius),
                circular_segments=segments,
                center=True,
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
                raise _SphereRadiusRequiredError
            center = params.get("center", (0.0, 0.0, 0.0))
            segments = int(params.get("segments", 32))
            manifold = _m3d.Manifold.sphere(float(radius), circular_segments=segments)
            manifold = manifold.translate(list(map(float, center)))
            return ManifoldMesh(manifold)

        raise _UnsupportedPrimitiveKindError(kind)

    def union(self, a: ManifoldMesh, b: ManifoldMesh) -> ManifoldMesh:
        """Return the boolean union of two manifold handles."""
        return ManifoldMesh(a.raw + b.raw)

    def difference(self, a: ManifoldMesh, b: ManifoldMesh) -> ManifoldMesh:
        """Return the boolean difference of two manifold handles."""
        return ManifoldMesh(a.raw - b.raw)

    def intersection(self, a: ManifoldMesh, b: ManifoldMesh) -> ManifoldMesh:
        """Return the boolean intersection of two manifold handles."""
        return ManifoldMesh(a.raw ^ b.raw)

    def hull(self, meshes: Iterable[ManifoldMesh]) -> ManifoldMesh:
        """Return a convex hull over the supplied manifold handles."""
        seq = list(meshes)
        if not seq:
            raise _HullEmptyError
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
            raise _BatchUnionEmptyError from exc
        for m in it:
            acc = acc + m.raw
        return ManifoldMesh(acc)

    def to_trimesh(self, manifold_mesh: ManifoldMesh) -> trimesh.Trimesh:
        """Convert a manifold handle into a ``trimesh.Trimesh``."""
        mesh = manifold_mesh.raw.to_mesh()
        verts = np.asarray(mesh.vert_properties, dtype=np.float64)
        # Manifold may emit property columns beyond xyz; take the first 3.
        if verts.shape[1] > _XYZ_COLUMN_COUNT:
            verts = verts[:, :_XYZ_COLUMN_COUNT]
        tris = np.asarray(mesh.tri_verts, dtype=np.int64)
        return trimesh.Trimesh(vertices=verts, faces=tris, process=False)

    def is_watertight(self, manifold_mesh: ManifoldMesh) -> bool:
        """Manifold is watertight by construction; empty meshes are not."""
        return not manifold_mesh.is_empty()

    def body_count(self, manifold_mesh: ManifoldMesh) -> int:
        """Return the number of disjoint bodies in the manifold handle."""
        if manifold_mesh.is_empty():
            return 0
        return len(manifold_mesh.raw.decompose())


def manifold_available() -> bool:
    """Module-level probe for test skipping and soft feature-gating."""
    return _MANIFOLD_AVAILABLE
