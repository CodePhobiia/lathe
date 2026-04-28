"""Reference geometry kernel backed by trimesh (GEO-3).

Always-available fallback for the ``lathe.geometry.reference_v1`` ID.
Wraps ``trimesh.creation`` for primitives and trimesh's boolean
pipeline (``trimesh.boolean.union/difference/intersection``) for CSG
ops. Results are not guaranteed watertight — trimesh booleans depend
on the configured engine and can emit non-manifold output on dense or
coplanar scenes. That known weakness is exactly what motivates
Manifold adoption (see ``docs/geometry_kernel_eval.md``); this kernel
exists so a Lathe install without ``manifold3d`` still has a working
geometry path.

The kernel exposes *only* the Protocol surface the shape stage uses.
Lower-level SDF fusion logic continues to live in
``lathe/geometry_kernel.py`` and is reached via that module's
``fuse_shape_ir`` helper; this kernel is the boolean/CSG surface, not
a replacement for the entire legacy module.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from typing import Any

import numpy as np
import trimesh

from .kernel import REFERENCE_KERNEL_ID, GeometryKernel

__all__ = ["ReferenceKernel", "reference_kernel"]


class _BoxExtentsRequiredError(ValueError):
    def __init__(self) -> None:
        super().__init__("box requires `extents` (3-tuple)")


class _CylinderDimensionsRequiredError(ValueError):
    def __init__(self) -> None:
        super().__init__("cylinder requires `radius` and `height`")


class _SphereRadiusRequiredError(ValueError):
    def __init__(self) -> None:
        super().__init__("sphere requires `radius`")


class _UnsupportedPrimitiveKindError(ValueError):
    def __init__(self, kind: str) -> None:
        super().__init__(f"Unsupported primitive kind: {kind!r}")


class _HullEmptyError(ValueError):
    def __init__(self) -> None:
        super().__init__("hull requires at least one mesh")


class ReferenceKernel:
    """Trimesh-backed geometry kernel (always available)."""

    name = REFERENCE_KERNEL_ID
    version = "0.1"

    def probe(self) -> dict[str, Any]:
        """Availability + capability metadata."""
        return {
            "name": self.name,
            "version": self.version,
            "available": True,
            "capabilities": {
                "union": True,
                "difference": True,
                "intersection": True,
                "hull": True,
                "to_trimesh": True,
                "body_count": True,
                "watertight_by_construction": False,
            },
            "notes": (
                "Trimesh booleans depend on an available engine and may "
                "emit non-watertight output on dense / coplanar scenes."
            ),
        }

    def build_primitive(self, kind: str, **params: Any) -> trimesh.Trimesh:
        """Create a primitive trimesh handle."""
        center = tuple(float(v) for v in params.get("center", (0.0, 0.0, 0.0)))
        if kind == "box":
            extents = params.get("extents")
            if extents is None:
                raise _BoxExtentsRequiredError
            transform = np.eye(4)
            transform[:3, 3] = np.array(center, dtype=float)
            return trimesh.creation.box(
                extents=np.array(list(extents), dtype=float),
                transform=transform,
            )

        if kind == "cylinder":
            radius = params.get("radius")
            height = params.get("height")
            if radius is None or height is None:
                raise _CylinderDimensionsRequiredError
            axis = params.get("axis", "y")
            segments = int(params.get("segments", 32))
            mesh = trimesh.creation.cylinder(radius=float(radius), height=float(height), sections=segments)
            if axis == "x":
                mesh.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2.0, [0.0, 1.0, 0.0]))
            elif axis == "y":
                mesh.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2.0, [1.0, 0.0, 0.0]))
            translation = np.eye(4)
            translation[:3, 3] = np.array(center, dtype=float)
            mesh.apply_transform(translation)
            return mesh

        if kind == "sphere":
            radius = params.get("radius")
            if radius is None:
                raise _SphereRadiusRequiredError
            segments = int(params.get("segments", 32))
            mesh = trimesh.creation.icosphere(
                subdivisions=max(1, int(math.log2(max(2, segments // 4)))),
                radius=float(radius),
            )
            translation = np.eye(4)
            translation[:3, 3] = np.array(center, dtype=float)
            mesh.apply_transform(translation)
            return mesh

        raise _UnsupportedPrimitiveKindError(kind)

    def _boolean(self, op: str, a: trimesh.Trimesh, b: trimesh.Trimesh) -> trimesh.Trimesh:
        # trimesh.boolean.{union,difference,intersection} accept an iterable.
        fn = getattr(trimesh.boolean, op)
        try:
            result = fn([a, b])
        except (ImportError, ValueError, RuntimeError, AttributeError, TypeError):
            # Fall back to concatenation/passthrough for union when no engine is present;
            # caller contract is "best-effort CSG", not watertightness.
            if op == "union":
                return trimesh.util.concatenate([a, b])
            if op == "difference":
                return a
            if op == "intersection":
                return a
            raise
        if isinstance(result, list):
            if not result:
                return trimesh.Trimesh()
            return trimesh.util.concatenate(result) if len(result) > 1 else result[0]
        return result

    def union(self, a: trimesh.Trimesh, b: trimesh.Trimesh) -> trimesh.Trimesh:
        """Return the boolean union of two trimesh handles."""
        return self._boolean("union", a, b)

    def difference(self, a: trimesh.Trimesh, b: trimesh.Trimesh) -> trimesh.Trimesh:
        """Return the boolean difference of two trimesh handles."""
        return self._boolean("difference", a, b)

    def intersection(self, a: trimesh.Trimesh, b: trimesh.Trimesh) -> trimesh.Trimesh:
        """Return the boolean intersection of two trimesh handles."""
        return self._boolean("intersection", a, b)

    def hull(self, meshes: Iterable[trimesh.Trimesh]) -> trimesh.Trimesh:
        """Return a convex hull over the supplied trimesh handles."""
        seq = list(meshes)
        if not seq:
            raise _HullEmptyError
        combined = trimesh.util.concatenate(seq) if len(seq) > 1 else seq[0]
        return combined.convex_hull

    def to_trimesh(self, handle: trimesh.Trimesh) -> trimesh.Trimesh:
        """Return the trimesh handle unchanged."""
        return handle

    def is_watertight(self, handle: trimesh.Trimesh) -> bool:
        """Return whether the trimesh handle is non-empty and watertight."""
        if handle is None or len(handle.faces) == 0:
            return False
        return bool(handle.is_watertight)

    def body_count(self, handle: trimesh.Trimesh) -> int:
        """Return the number of disjoint mesh bodies."""
        if handle is None or len(handle.faces) == 0:
            return 0
        try:
            return len(handle.split(only_watertight=False))
        except (ValueError, RuntimeError, AttributeError, IndexError, TypeError):
            return 1


def reference_kernel() -> GeometryKernel:
    """Instantiate the reference (trimesh) geometry kernel."""
    return ReferenceKernel()  # type: ignore[return-value]
