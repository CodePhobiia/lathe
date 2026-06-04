"""Manifold kernel adapter.

Thin wrapper around manifold3d for CSG ops Lathe's shape stage cares
about: union, difference, intersection, convex hull, plus primitive
construction and trimesh round-trip. The geometry registry exposes this
adapter as ``lathe.geometry.manifold_v1``; keep its metadata explicit so
downstream ShapeIR, topology, UV, surface, and package stages can tell an
authored/exact mesh import from a native Manifold primitive.

See `docs/geometry_kernel_eval.md` for the ADOPT/ADAPT/REJECT decision.
"""

from __future__ import annotations

from collections.abc import Iterable
from copy import deepcopy
from typing import Any

import numpy as np
import trimesh

_XYZ_COLUMN_COUNT = 3
_EXACT_IMPORT_MODIFIER_KEYS = (
    "boolean_seam_groups",
    "bevel_seam_groups",
    "hard_edge_groups",
    "v2_polybevel_modifier",
    "v2_mark_hard_edge_modifier",
    "v2_weighted_normals_modifier",
    "v2_subdivision_modifier",
    "v2_remesh_modifier",
    "v2_tessellation_modifier",
)
_EXACT_IMPORT_PRIMITIVE_KINDS = frozenset(
    {
        "box",
        "cylinder",
        "sphere",
        "capsule",
        "revolved_profile",
        "extruded_profile",
        "rounded_slot",
        "socket",
        "countersunk_hole",
        "countersunk_hole_set",
        "panel",
        "panel_frame",
        "panel_line_cut",
        "inset_cut",
        "perforated_panel",
        "fastener_grid",
        "weld_seam",
        "dent_mask_set",
        "edge_chip_set",
        "surface_patch_set",
        "hinge",
        "handle",
        "corner_guard_set",
        "structural_beam",
        "rail",
        "ribbed_panel",
        "louver_panel",
        "vent_slats",
        "ladder_frame",
        "truss_frame",
        "support_bracket",
        "trim_band",
        "torus",
        "tube",
        "gear",
        "flange",
        "subdivision_box",
        "swept_profile",
        "helical_sweep",
        "spring",
        "threaded_cylinder",
        "curved_tube",
        "lofted_solid",
        "heightfield",
        "terrain_patch",
        "sdf_mesh",
        "sdf_metaball_cluster",
        "terrain_mesh",
        "kernel_primitive_mesh",
        "instance_mesh",
        "polybevel_mesh",
        "profile_mesh",
        "construction_feature_mesh",
        "edge_control_mesh",
        "hull_mesh",
        "minkowski_mesh",
        "subdivision_mesh",
        "remesh_mesh",
        "deform_mesh",
        "boolean_mesh",
        "component_assembly_mesh",
        "component_assembly",
    }
)

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


class _CapsuleDimensionsRequiredError(ValueError):
    def __init__(self) -> None:
        super().__init__("capsule requires `radius` and total `length > 2 * radius`")


class _RevolvedProfilePointsRequiredError(ValueError):
    def __init__(self) -> None:
        super().__init__("revolved_profile requires `profile_points` (>= 1 point)")


class _ExtrudedProfilePolygonRequiredError(ValueError):
    def __init__(self) -> None:
        super().__init__("extruded_profile requires `profile_polygon` (>= 3 CCW points)")


class _ExtrudedProfileHeightRequiredError(ValueError):
    def __init__(self) -> None:
        super().__init__("extruded_profile requires `extrude_height` (> 0)")
class _TorusDimensionsRequiredError(ValueError):
    def __init__(self) -> None:
        super().__init__("torus requires `major_radius` and `minor_radius`")
class _SubdivisionBoxExtentsRequiredError(ValueError):
    def __init__(self) -> None:
        super().__init__("subdivision_box requires `extents` (3-tuple)")


class _SubdivisionBoxCornerRadiiRequiredError(ValueError):
    def __init__(self) -> None:
        super().__init__("subdivision_box requires `corner_radii` (8-tuple)")
class _SweptProfileInputRequiredError(ValueError):
    def __init__(self) -> None:
        super().__init__(
            "swept_profile requires `cross_section` (>= 3 points) and "
            "`sweep_path` (>= 2 points)"
        )


class _UnsupportedPrimitiveKindError(ValueError):
    def __init__(self, kind: str) -> None:
        super().__init__(f"Unsupported primitive kind: {kind!r}")


class _HullEmptyError(ValueError):
    def __init__(self) -> None:
        super().__init__("hull requires at least one mesh")


class _BatchUnionEmptyError(ValueError):
    def __init__(self) -> None:
        super().__init__("batch_union requires at least one mesh")


def _shape_primitive_from_params(kind: str, params: dict[str, Any]):
    from dataclasses import fields

    from ..shape_ir import ShapePrimitive

    field_names = {field.name for field in fields(ShapePrimitive)}
    kwargs = {
        name: params[name]
        for name in field_names
        if name in params
    }
    kwargs["primitive_type"] = kind
    kwargs.setdefault("part", str(params.get("part") or kind))
    kwargs.setdefault(
        "center",
        tuple(float(value) for value in params.get("center", (0.0, 0.0, 0.0))),
    )
    if "v2_tessellation_modifier" in params and "v2_tessellation_modifier" not in kwargs:
        semantic_metadata = kwargs.get("semantic_metadata")
        if isinstance(semantic_metadata, dict):
            semantic_metadata = dict(semantic_metadata)
        else:
            semantic_metadata = {}
        semantic_metadata["v2_tessellation_modifier"] = params["v2_tessellation_modifier"]
        kwargs["semantic_metadata"] = semantic_metadata
    return ShapePrimitive(**kwargs)


def _requires_exact_import(kind: str, params: dict[str, Any]) -> bool:
    return kind in _EXACT_IMPORT_PRIMITIVE_KINDS and any(
        params.get(key) not in (None, {}, [], ())
        for key in _EXACT_IMPORT_MODIFIER_KEYS
    )


def _shape_primitive_metadata_from_params(kind: str, params: dict[str, Any]) -> dict[str, Any]:
    try:
        primitive = _shape_primitive_from_params(kind, params)
        payload = primitive.to_dict()
    except (TypeError, ValueError, KeyError, AttributeError):
        return {}
    payload["schema"] = "lathe.shape_primitive_mesh_metadata.v1"
    return {"lathe_shape_primitive": payload}


def _manifold_body_count(raw: Any) -> int:
    try:
        if bool(raw.is_empty()):
            return 0
        return len(raw.decompose())
    except (AttributeError, TypeError, ValueError, RuntimeError):
        return 0


def _manifold_result_counts(raw: Any) -> dict[str, Any]:
    try:
        face_count = int(raw.num_tri())
    except (AttributeError, TypeError, ValueError, RuntimeError):
        face_count = 0
    try:
        vertex_count = int(raw.num_vert())
    except (AttributeError, TypeError, ValueError, RuntimeError):
        vertex_count = 0
    return {
        "result_face_count": face_count,
        "result_vertex_count": vertex_count,
        "result_body_count": _manifold_body_count(raw),
        "result_watertight": not bool(getattr(raw, "is_empty", lambda: True)()),
    }


def _trimesh_import_metadata(
    *,
    original: trimesh.Trimesh,
    candidate: trimesh.Trimesh,
    manifold: Any,
) -> dict[str, Any]:
    return {
        "schema": "lathe.geometry.manifold_import.v1",
        "method": "manifold3d_mesh_import_v1",
        "requested_backend": "lathe.geometry.manifold_v1.from_trimesh",
        "actual_backend": "manifold3d.Mesh",
        "actual_operation": "mesh_import",
        "fallback": False,
        "passthrough": False,
        "input_face_count": len(original.faces),
        "input_vertex_count": len(original.vertices),
        "input_watertight": bool(original.is_watertight),
        "candidate_face_count": len(candidate.faces),
        "candidate_vertex_count": len(candidate.vertices),
        "candidate_watertight": bool(candidate.is_watertight),
        **_manifold_result_counts(manifold),
    }


class ManifoldMesh:
    """Opaque handle wrapping a `manifold3d.Manifold` object.

    Exposes a minimal interface so call sites don't touch the underlying
    binding directly.
    """

    __slots__ = ("_m", "_metadata")

    def __init__(self, manifold: Any, metadata: dict[str, Any] | None = None) -> None:
        """Wrap a raw ``manifold3d.Manifold`` handle."""
        self._m = manifold
        self._metadata = deepcopy(metadata) if isinstance(metadata, dict) else {}

    @property
    def raw(self) -> Any:
        """Return the underlying ``manifold3d`` object."""
        return self._m

    @property
    def metadata(self) -> dict[str, Any]:
        """Return Lathe metadata carried alongside the opaque handle."""
        return deepcopy(self._metadata)

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
                "transform": True,
                "deform_program": True,
                "refine_program": True,
                "carve_program": True,
                "polyextrude_program": True,
                "component_assembly_program": True,
                "profile_path_program": True,
                "sdf_field_program": True,
                "terrain_field_program": True,
                "scatter_program": True,
                "pattern_instances_program": True,
                "edge_control_program": True,
                "edge_treatment_program": True,
                "feature_detail_program": True,
                "surface_damage_program": True,
                "batch_union": True,
                "convex_hull_points": True,
                "from_trimesh": True,
                "box": True,
                "box_rounding": True,
                "exact_modifier_import": True,
                "cylinder": True,
                "sphere": True,
                "capsule": True,
                "revolved_profile": True,
                "partial_revolved_profile": True,
                "extruded_profile": True,
                "generalized_extruded_profile": True,
                "rounded_slot": True,
                "socket": True,
                "countersunk_hole": True,
                "countersunk_hole_set": True,
                "panel": True,
                "panel_frame": True,
                "panel_line_cut": True,
                "inset_cut": True,
                "perforated_panel": True,
                "fastener_grid": True,
                "weld_seam": True,
                "dent_mask_set": True,
                "edge_chip_set": True,
                "surface_patch_set": True,
                "hinge": True,
                "handle": True,
                "corner_guard_set": True,
                "structural_beam": True,
                "rail": True,
                "ribbed_panel": True,
                "louver_panel": True,
                "vent_slats": True,
                "ladder_frame": True,
                "truss_frame": True,
                "support_bracket": True,
                "trim_band": True,
                "torus": True,
                "tube": True,
                "gear": True,
                "flange": True,
                "subdivision_box": True,
                "swept_profile": True,
                "helical_sweep": True,
                "spring": True,
                "threaded_cylinder": True,
                "curved_tube": True,
                "lofted_solid": True,
                "heightfield": True,
                "heightfield_solid_import": True,
                "terrain_patch": True,
                "terrain_patch_import": True,
                "sdf_mesh": True,
                "sdf_mesh_import": True,
                "sdf_metaball_cluster": True,
                "sdf_metaball_cluster_import": True,
                "terrain_mesh": True,
                "terrain_mesh_import": True,
                "kernel_primitive_mesh": True,
                "kernel_primitive_mesh_import": True,
                "instance_mesh": True,
                "instance_mesh_import": True,
                "polybevel_mesh": True,
                "polybevel_mesh_import": True,
                "profile_mesh": True,
                "profile_mesh_import": True,
                "construction_feature_mesh": True,
                "construction_feature_mesh_import": True,
                "edge_control_mesh": True,
                "edge_control_mesh_import": True,
                "hull_mesh": True,
                "hull_mesh_import": True,
                "minkowski_mesh": True,
                "minkowski_mesh_import": True,
                "subdivision_mesh": True,
                "subdivision_mesh_import": True,
                "remesh_mesh": True,
                "remesh_mesh_import": True,
                "deform_mesh": True,
                "deform_mesh_import": True,
                "boolean_mesh": True,
                "boolean_mesh_import": True,
                "component_assembly_mesh": True,
                "component_assembly_mesh_import": True,
                "component_assembly": True,
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
        + optional center), `capsule` (radius + total length + axis),
        `revolved_profile` (profile_points +
        optional axis + optional center + optional segments +
        optional revolve_degrees / revolve_start_degrees),
        `extruded_profile` (profile_polygon + extrude_height +
        optional axis + optional center + optional scale/twist controls),
        `rounded_slot` (length + width + depth + optional rotation),
        `socket` (semantic round, rectangular, or rounded-slot clearance volume),
        `countersunk_hole` (radius + depth + straight/countersink/counterbore style),
        `countersunk_hole_set` (repeated styled bore cutter pattern),
        `panel` (width + height + thickness + optional corner rounding),
        `panel_frame` (rectangular ring frame with border width),
        `panel_line_cut` (semantic rectangular panel groove/cutter),
        `inset_cut` (semantic shallow face-recess cutter),
        `perforated_panel` (panel plus circular/slot through-hole grid),
        `fastener_grid` (repeated washer/head hardware grid),
        `weld_seam` (path or axis weld bead with semantic seam metadata),
        `dent_mask_set` (repeated spherical face dent cutters),
        `edge_chip_set` (repeated spherical edge/corner chip cutters),
        `surface_patch_set` (repeated rectangular scratch/grime patch fields),
        `hinge` (two-leaf barrel hinge with pin and alternating knuckles),
        `handle` (swept U-pull handle with mount pads),
        `corner_guard_set` (source-envelope corner protector bars),
        `structural_beam` (length + width + height + section profile),
        `rail` (length + profile dimensions + rail profile shape),
        `ribbed_panel` (panel plus repeated raised stiffener ribs),
        `louver_panel` (frame + repeated angled slats),
        `vent_slats` (repeated rectangular slat array),
        `ladder_frame` (side rails + repeated rungs),
        `truss_frame` (chords, posts, braces, optional depth ties),
        `support_bracket` (L bracket plates plus optional gussets),
        `trim_band` (visible rectangular trim strip with semantic axes),
        `torus` (major_radius +
        minor_radius + optional axis + optional center + optional
        segments), `tube` (outer_radius + inner_radius + height),
        `gear` (teeth + pitch_radius + thickness + optional bore/helix),
        `flange` (outer_radius + inner_radius + thickness + optional
        bolt circle),
        `subdivision_box` (extents + corner_radii 8-tuple +
        optional center + optional segments), `swept_profile`
        (cross_section + sweep_path + optional center), `lofted_solid`
        (cross_sections + section_centers), `helical_sweep`
        (radius + height + turns + tube_radius/cross_section),
        `spring` (semantic helical wire coil),
        `threaded_cylinder` (single external-thread cylinder primitive),
        `curved_tube` (radius + tube_radius + angle + optional
        inner_tube_radius),
        `heightfield` / `terrain_patch` solidified as
        a flat-base shell, closed mesh-backed semantic payloads, and
        `component_assembly` / `component_assembly_mesh` compound
        primitives imported from Lathe's exact mesh path.
        """
        if _requires_exact_import(kind, params):
            from ..exact_solids import primitive_mesh

            primitive = _shape_primitive_from_params(kind, params)
            return self.from_trimesh(primitive_mesh(primitive))

        if kind in {
            "tube",
            "gear",
            "flange",
            "rounded_slot",
            "socket",
            "countersunk_hole",
            "countersunk_hole_set",
            "panel",
            "panel_frame",
            "panel_line_cut",
            "inset_cut",
            "perforated_panel",
            "fastener_grid",
            "weld_seam",
            "dent_mask_set",
            "edge_chip_set",
            "surface_patch_set",
            "hinge",
            "handle",
            "corner_guard_set",
            "structural_beam",
            "rail",
            "ribbed_panel",
            "louver_panel",
            "vent_slats",
            "ladder_frame",
            "truss_frame",
            "support_bracket",
            "trim_band",
            "helical_sweep",
            "spring",
            "threaded_cylinder",
            "curved_tube",
            "lofted_solid",
            "heightfield",
            "terrain_patch",
            "sdf_mesh",
            "sdf_metaball_cluster",
            "terrain_mesh",
            "kernel_primitive_mesh",
            "instance_mesh",
            "polybevel_mesh",
            "profile_mesh",
            "construction_feature_mesh",
            "edge_control_mesh",
            "hull_mesh",
            "minkowski_mesh",
            "subdivision_mesh",
            "remesh_mesh",
            "deform_mesh",
            "boolean_mesh",
            "component_assembly_mesh",
            "component_assembly",
        }:
            from ..exact_solids import primitive_mesh

            primitive = _shape_primitive_from_params(kind, params)
            mesh = primitive_mesh(primitive)
            if kind in {"heightfield", "terrain_patch"} and not bool(mesh.is_watertight):
                from ..geometry.shape_ir_lowering import _solidify_heightfield_mesh

                mesh, _ = _solidify_heightfield_mesh(mesh)
            return self.from_trimesh(mesh)

        if kind == "extruded_profile":
            profile_polygon = params.get("profile_polygon")
            if profile_polygon is None or len(tuple(profile_polygon)) < 3:
                raise _ExtrudedProfilePolygonRequiredError
            extrude_height = params.get("extrude_height")
            if extrude_height is None or float(extrude_height) <= 0.0:
                raise _ExtrudedProfileHeightRequiredError
            axis = params.get("axis", "z")
            center = params.get("center", (0.0, 0.0, 0.0))
            generalized_keys = {
                "extrude_start_scale",
                "extrude_end_scale",
                "extrude_twist_degrees",
                "extrude_segments",
            }
            if any(key in params for key in generalized_keys):
                from ..exact_solids import primitive_mesh
                from ..shape_ir import ShapePrimitive

                primitive = ShapePrimitive(
                    primitive_type="extruded_profile",
                    part=str(params.get("part") or "extruded_profile"),
                    center=tuple(float(value) for value in center),
                    axis=str(axis),
                    profile_polygon=[(float(u), float(v)) for u, v in profile_polygon],
                    extrude_height=float(extrude_height),
                    extrude_start_scale=(
                        None
                        if params.get("extrude_start_scale") is None
                        else float(params["extrude_start_scale"])
                    ),
                    extrude_end_scale=(
                        None
                        if params.get("extrude_end_scale") is None
                        else float(params["extrude_end_scale"])
                    ),
                    extrude_twist_degrees=(
                        None
                        if params.get("extrude_twist_degrees") is None
                        else float(params["extrude_twist_degrees"])
                    ),
                    extrude_segments=(
                        None
                        if params.get("extrude_segments") is None
                        else int(params["extrude_segments"])
                    ),
                )
                return self.from_trimesh(primitive_mesh(primitive))
            contour = [(float(u), float(v)) for u, v in profile_polygon]
            cross_section = _m3d.CrossSection([contour])
            manifold = cross_section.extrude(float(extrude_height))
            # ``CrossSection.extrude`` extrudes along +Z starting at
            # z=0, so recenter the prism on z=0 before rotating to the
            # requested axis.
            manifold = manifold.translate([0.0, 0.0, -float(extrude_height) / 2.0])
            if axis == "x":
                manifold = manifold.rotate([0.0, 90.0, 0.0])
            elif axis == "y":
                manifold = manifold.rotate([90.0, 0.0, 0.0])
            manifold = manifold.translate(list(map(float, center)))
            return ManifoldMesh(manifold, _shape_primitive_metadata_from_params(kind, params))

        if kind == "torus":
            major_radius = params.get("major_radius")
            minor_radius = params.get("minor_radius")
            if major_radius is None or minor_radius is None:
                raise _TorusDimensionsRequiredError
            axis = params.get("axis", "y")
            center = params.get("center", (0.0, 0.0, 0.0))
            segments = int(params.get("segments") or params.get("sections") or 48)
            # manifold3d has no native torus, so we revolve a CrossSection
            # circle of `minor_radius` translated by `(major_radius, 0)` in
            # the (X, Y) cross-section plane. Revolve sweeps around the
            # CrossSection's Y-axis and emits a manifold along the result's
            # Z-axis, so we get a torus whose ring axis is Z by default.
            circle = _m3d.CrossSection.circle(float(minor_radius), circular_segments=segments)
            circle = circle.translate((float(major_radius), 0.0))
            manifold = circle.revolve(circular_segments=segments)
            # Rotate to the user's chosen axis, matching the cylinder case.
            if axis == "x":
                manifold = manifold.rotate([0.0, 90.0, 0.0])
            elif axis == "y":
                manifold = manifold.rotate([90.0, 0.0, 0.0])
            manifold = manifold.translate(list(map(float, center)))
            return ManifoldMesh(manifold, _shape_primitive_metadata_from_params(kind, params))

        if kind == "subdivision_box":
            extents = params.get("extents")
            if extents is None:
                raise _SubdivisionBoxExtentsRequiredError
            corner_radii = params.get("corner_radii")
            if corner_radii is None or len(tuple(corner_radii)) != 8:
                raise _SubdivisionBoxCornerRadiiRequiredError
            center = params.get("center", (0.0, 0.0, 0.0))
            segments = max(4, int(params.get("segments", 16)))
            half = [float(extents[0]) / 2.0, float(extents[1]) / 2.0, float(extents[2]) / 2.0]
            cap = min(half) * 0.92
            radii = [min(max(float(r), 0.0), cap) for r in corner_radii]
            # Order: (-x-y-z, +x-y-z, -x+y-z, +x+y-z, -x-y+z, +x-y+z, -x+y+z, +x+y+z).
            corner_signs = [
                (-1.0, -1.0, -1.0),
                (+1.0, -1.0, -1.0),
                (-1.0, +1.0, -1.0),
                (+1.0, +1.0, -1.0),
                (-1.0, -1.0, +1.0),
                (+1.0, -1.0, +1.0),
                (-1.0, +1.0, +1.0),
                (+1.0, +1.0, +1.0),
            ]
            sphere_handles: list[Any] = []
            min_radius = 1e-4
            for (sx, sy, sz), radius in zip(corner_signs, radii, strict=True):
                effective_radius = max(radius, min_radius)
                core_x = max(half[0] - effective_radius, 1e-6)
                core_y = max(half[1] - effective_radius, 1e-6)
                core_z = max(half[2] - effective_radius, 1e-6)
                offset = [sx * core_x, sy * core_y, sz * core_z]
                sphere = _m3d.Manifold.sphere(effective_radius, circular_segments=segments)
                sphere = sphere.translate(offset)
                sphere_handles.append(sphere)
            manifold = _m3d.Manifold.batch_hull(sphere_handles)
            manifold = manifold.translate(list(map(float, center)))
            return ManifoldMesh(manifold, _shape_primitive_metadata_from_params(kind, params))

        if kind == "swept_profile":
            cross_section = params.get("cross_section")
            sweep_path = params.get("sweep_path")
            if (
                not cross_section
                or len(cross_section) < 3
                or not sweep_path
                or len(sweep_path) < 2
            ):
                raise _SweptProfileInputRequiredError
            center = params.get("center", (0.0, 0.0, 0.0))
            # manifold3d has no native sweep operation. Build the mesh
            # via trimesh.creation.sweep_polygon, then import it into
            # manifold via Mesh(vert_properties, tri_verts).
            from trimesh.path.polygons import Polygon

            polygon = Polygon([(float(u), float(v)) for u, v in cross_section])
            path_arr = np.asarray(
                [[float(x), float(y), float(z)] for x, y, z in sweep_path], dtype=np.float64
            )
            tm = trimesh.creation.sweep_polygon(polygon, path=path_arr, cap=True, connect=True)
            verts = np.ascontiguousarray(np.asarray(tm.vertices, dtype=np.float32))
            faces = np.ascontiguousarray(np.asarray(tm.faces, dtype=np.uint32))
            mesh = _m3d.Mesh(vert_properties=verts, tri_verts=faces)
            mesh.merge()
            manifold = _m3d.Manifold(mesh)
            manifold = manifold.translate(list(map(float, center)))
            return ManifoldMesh(manifold, _shape_primitive_metadata_from_params(kind, params))

        if kind == "revolved_profile":
            profile_points = params.get("profile_points")
            if not profile_points:
                raise _RevolvedProfilePointsRequiredError
            axis = params.get("axis", "y")
            center = params.get("center", (0.0, 0.0, 0.0))
            segments = int(params.get("segments") or params.get("sections") or 48)
            revolve_degrees = params.get("revolve_degrees")
            if (
                revolve_degrees is not None
                and abs(float(revolve_degrees) - 360.0) > 1e-6
            ):
                from ..exact_solids import primitive_mesh
                from ..shape_ir import ShapePrimitive

                primitive = ShapePrimitive(
                    primitive_type="revolved_profile",
                    part=str(params.get("part") or "revolved_profile"),
                    center=tuple(float(value) for value in center),
                    axis=str(axis),
                    profile_points=[(float(a), float(r)) for a, r in profile_points],
                    revolve_degrees=float(revolve_degrees),
                    revolve_start_degrees=(
                        None
                        if params.get("revolve_start_degrees") is None
                        else float(params["revolve_start_degrees"])
                    ),
                )
                return self.from_trimesh(primitive_mesh(primitive))
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
            return ManifoldMesh(manifold, _shape_primitive_metadata_from_params(kind, params))

        if kind == "box":
            extents = params.get("extents")
            if extents is None:
                raise _BoxExtentsRequiredError
            rounding = float(params.get("rounding") or params.get("rounding_cm") or 0.0)
            if rounding > 0.0:
                from ..exact_solids import primitive_mesh

                primitive = _shape_primitive_from_params(kind, params)
                mesh = primitive_mesh(primitive)
                mesh.metadata["lathe_manifold_primitive"] = {
                    "schema": "lathe.geometry.manifold_primitive.v1",
                    "method": "rounded_box_exact_mesh_build_primitive_v1",
                    "primitive_type": "box",
                    "rounding_cm": float(rounding),
                    "requested_backend": "lathe.geometry.manifold_v1.build_primitive",
                    "actual_backend": "lathe.exact_solids.rounded_box",
                    "fallback": False,
                    "passthrough": False,
                    "result_face_count": len(mesh.faces),
                    "result_watertight": bool(mesh.is_watertight),
                }
                return self.from_trimesh(mesh)
            center = params.get("center", (0.0, 0.0, 0.0))
            manifold = _m3d.Manifold.cube(list(map(float, extents)), center=True)
            manifold = manifold.translate(list(map(float, center)))
            return ManifoldMesh(manifold, _shape_primitive_metadata_from_params(kind, params))

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
            return ManifoldMesh(manifold, _shape_primitive_metadata_from_params(kind, params))

        if kind == "capsule":
            radius = params.get("radius")
            length = params.get("length")
            if radius is None or length is None:
                raise _CapsuleDimensionsRequiredError
            radius_value = float(radius)
            length_value = float(length)
            if radius_value <= 0.0 or length_value <= radius_value * 2.0:
                raise _CapsuleDimensionsRequiredError
            axis = params.get("axis", "y")
            center = params.get("center", (0.0, 0.0, 0.0))
            segments = max(8, min(128, int(params.get("sections") or params.get("segments") or 32)))
            shaft_length = length_value - radius_value * 2.0
            shaft = _m3d.Manifold.cylinder(
                shaft_length,
                radius_value,
                radius_value,
                circular_segments=segments,
                center=True,
            )
            cap_top = _m3d.Manifold.sphere(radius_value, circular_segments=segments)
            cap_top = cap_top.translate([0.0, 0.0, shaft_length / 2.0])
            cap_bottom = _m3d.Manifold.sphere(radius_value, circular_segments=segments)
            cap_bottom = cap_bottom.translate([0.0, 0.0, -shaft_length / 2.0])
            manifold = shaft + cap_top + cap_bottom
            if axis == "x":
                manifold = manifold.rotate([0.0, 90.0, 0.0])
            elif axis == "y":
                manifold = manifold.rotate([90.0, 0.0, 0.0])
            elif axis != "z":
                raise ValueError("capsule axis must be one of: x, y, z")
            manifold = manifold.translate(list(map(float, center)))
            metadata = _shape_primitive_metadata_from_params(kind, params)
            metadata["lathe_manifold_primitive"] = {
                "schema": "lathe.geometry.manifold_primitive.v1",
                "method": "manifold3d_capsule_union_v1",
                "primitive_type": "capsule",
                "radius_cm": radius_value,
                "length_cm": length_value,
                "shaft_length_cm": shaft_length,
                "axis": str(axis),
                "segments": segments,
                "actual_backend": "manifold3d",
                "fallback": False,
                "passthrough": False,
                **_manifold_result_counts(manifold),
            }
            return ManifoldMesh(manifold, metadata)

        if kind == "sphere":
            radius = params.get("radius")
            if radius is None:
                raise _SphereRadiusRequiredError
            center = params.get("center", (0.0, 0.0, 0.0))
            segments = int(params.get("segments", 32))
            manifold = _m3d.Manifold.sphere(float(radius), circular_segments=segments)
            manifold = manifold.translate(list(map(float, center)))
            return ManifoldMesh(manifold, _shape_primitive_metadata_from_params(kind, params))

        raise _UnsupportedPrimitiveKindError(kind)

    def from_trimesh(self, mesh: trimesh.Trimesh) -> ManifoldMesh:
        """Import an authored/exact mesh into a Manifold handle."""
        original = mesh.copy()
        candidate = mesh.copy()
        candidate.remove_infinite_values()
        candidate.remove_unreferenced_vertices()
        if not bool(candidate.is_watertight):
            candidate.merge_vertices()
        candidate.fix_normals()
        manifold_mesh = _m3d.Mesh(
            np.ascontiguousarray(np.asarray(candidate.vertices, dtype=np.float32)),
            np.ascontiguousarray(np.asarray(candidate.faces, dtype=np.uint32)),
        )
        manifold = _m3d.Manifold(manifold_mesh)
        if manifold.is_empty():
            status = getattr(manifold, "status", lambda: None)()
            raise ValueError(f"manifold3d rejected imported mesh status={status!r}")
        metadata = deepcopy(candidate.metadata)
        metadata["lathe_manifold_import"] = _trimesh_import_metadata(
            original=original,
            candidate=candidate,
            manifold=manifold,
        )
        return ManifoldMesh(manifold, metadata)

    def union(self, a: ManifoldMesh, b: ManifoldMesh) -> ManifoldMesh:
        """Return the boolean union of two manifold handles."""
        result = a.raw + b.raw
        return ManifoldMesh(
            result,
            {
                "lathe_manifold_boolean": {
                    "schema": "lathe.geometry.manifold_boolean.v1",
                    "method": "manifold3d_boolean_v1",
                    "op": "union",
                    "attempted_backend": "manifold3d",
                    "actual_backend": "manifold3d",
                    "actual_operation": "boolean_union",
                    "fallback": False,
                    "passthrough": False,
                    **_manifold_result_counts(result),
                }
            },
        )

    def difference(self, a: ManifoldMesh, b: ManifoldMesh) -> ManifoldMesh:
        """Return the boolean difference of two manifold handles."""
        result = a.raw - b.raw
        return ManifoldMesh(
            result,
            {
                "lathe_manifold_boolean": {
                    "schema": "lathe.geometry.manifold_boolean.v1",
                    "method": "manifold3d_boolean_v1",
                    "op": "difference",
                    "attempted_backend": "manifold3d",
                    "actual_backend": "manifold3d",
                    "actual_operation": "boolean_difference",
                    "fallback": False,
                    "passthrough": False,
                    **_manifold_result_counts(result),
                }
            },
        )

    def intersection(self, a: ManifoldMesh, b: ManifoldMesh) -> ManifoldMesh:
        """Return the boolean intersection of two manifold handles."""
        result = a.raw ^ b.raw
        return ManifoldMesh(
            result,
            {
                "lathe_manifold_boolean": {
                    "schema": "lathe.geometry.manifold_boolean.v1",
                    "method": "manifold3d_boolean_v1",
                    "op": "intersection",
                    "attempted_backend": "manifold3d",
                    "actual_backend": "manifold3d",
                    "actual_operation": "boolean_intersection",
                    "fallback": False,
                    "passthrough": False,
                    **_manifold_result_counts(result),
                }
            },
        )

    def hull(self, meshes: Iterable[ManifoldMesh]) -> ManifoldMesh:
        """Return a convex hull over the supplied manifold handles."""
        seq = list(meshes)
        if not seq:
            raise _HullEmptyError
        raws = [m.raw for m in seq]
        result = _m3d.Manifold.batch_hull(raws)
        return ManifoldMesh(
            result,
            {
                "lathe_manifold_hull": {
                    "schema": "lathe.geometry.manifold_hull.v1",
                    "method": "manifold3d_batch_hull_v1",
                    "attempted_backend": "manifold3d.batch_hull",
                    "actual_backend": "manifold3d.batch_hull",
                    "actual_operation": "convex_hull",
                    "operand_count": len(seq),
                    "fallback": False,
                    "passthrough": False,
                    **_manifold_result_counts(result),
                }
            },
        )

    def batch_union(self, meshes: Iterable[ManifoldMesh]) -> ManifoldMesh:
        """Reduce a stream of meshes via pairwise union.

        manifold3d exposes `batch_boolean` but the pairwise reduce form
        keeps the adapter surface minimal and matches how Lathe builds
        assemblies primitive-by-primitive.
        """
        it = iter(meshes)
        try:
            acc = next(it).raw
            count = 1
        except StopIteration as exc:
            raise _BatchUnionEmptyError from exc
        for m in it:
            acc = acc + m.raw
            count += 1
        return ManifoldMesh(
            acc,
            {
                "lathe_manifold_batch_union": {
                    "schema": "lathe.geometry.manifold_batch_union.v1",
                    "method": "manifold3d_pairwise_batch_union_v1",
                    "attempted_backend": "manifold3d",
                    "actual_backend": "manifold3d",
                    "actual_operation": "pairwise_boolean_union",
                    "operand_count": count,
                    "fallback": False,
                    "passthrough": False,
                    **_manifold_result_counts(acc),
                }
            },
        )

    def transform(self, handle: ManifoldMesh, matrix: list[list[float]]) -> ManifoldMesh:
        """Return a transformed copy of a manifold handle."""
        mesh = self.to_trimesh(handle)
        transform = np.asarray(matrix, dtype=np.float64)
        mesh.apply_transform(transform)
        try:
            from ..geometry.reference_kernel import (
                _transform_box_metadata,
                _transform_cylinder_metadata,
                _transform_shape_primitive_metadata,
            )

            _transform_box_metadata(mesh, transform)
            _transform_cylinder_metadata(mesh, transform)
            _transform_shape_primitive_metadata(mesh, transform)
        except (ImportError, AttributeError, TypeError, ValueError):
            mesh.metadata.pop("lathe_shape_primitive", None)
            mesh.metadata.pop("lathe_reference_primitive", None)
        mesh.remove_unreferenced_vertices()
        mesh.fix_normals()
        mesh.metadata["lathe_manifold_transform"] = {
            "schema": "lathe.geometry.manifold_transform.v1",
            "method": "manifold_mesh_transform_import_v1",
            "attempted_backend": "trimesh_apply_transform_then_manifold_import",
            "actual_backend": "trimesh_apply_transform_then_manifold_import",
            "actual_operation": "matrix_transform",
            "result_face_count": len(mesh.faces),
            "result_vertex_count": len(mesh.vertices),
            "result_watertight": bool(mesh.is_watertight),
            "fallback": False,
            "passthrough": False,
        }
        return self.from_trimesh(mesh)

    def to_trimesh(self, manifold_mesh: ManifoldMesh) -> trimesh.Trimesh:
        """Convert a manifold handle into a ``trimesh.Trimesh``."""
        mesh = manifold_mesh.raw.to_mesh()
        verts = np.asarray(mesh.vert_properties, dtype=np.float64)
        # Manifold may emit property columns beyond xyz; take the first 3.
        if verts.shape[1] > _XYZ_COLUMN_COUNT:
            verts = verts[:, :_XYZ_COLUMN_COUNT]
        tris = np.asarray(mesh.tri_verts, dtype=np.int64)
        result = trimesh.Trimesh(vertices=verts, faces=tris, process=False)
        result.metadata.update(manifold_mesh.metadata)
        return result

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
