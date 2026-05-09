"""Assembly kernel: turn an asset graph into an assembly blueprint.

Produces the deterministic blueprint of components, joins and
boundary constraints that seeds scaffold compilation and the shape
IR.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from typing import Any

from .asset_graph import AssetGraph
from .errors import ContractViolation
from .geometry_detail import geometry_detail_controls_from_authoring
from .nested_assets import nested_asset_manifest_for_signature
from .primitive_selector import primitive_selection_summary, select_component_primitives
from .shape_ir import ShapeIR, ShapePrimitive, ShapeRegion

NUMERIC_EPSILON = 1e-6


@dataclass
class BlueprintComponent:
    """BlueprintComponent."""

    name: str
    component_type: str
    part: str
    center: tuple[float, float, float]
    extents: tuple[float, float, float]
    tags: list[str] = field(default_factory=list)
    adjacency: list[str] = field(default_factory=list)
    axis: str = "y"
    radius: float | None = None
    height: float | None = None
    symmetry_mate: str | None = None
    interface_role: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """To dict.

        Returns:
            The result.
        """
        return asdict(self)


@dataclass
class AssemblyBlueprint:
    """AssemblyBlueprint."""

    blueprint_id: str
    family: str
    components: list[BlueprintComponent]
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """To dict.

        Returns:
            The result.
        """
        payload = asdict(self)
        payload["components"] = [component.to_dict() for component in self.components]
        return payload


def _box(
    part: str,
    component: BlueprintComponent,
    *,
    center: tuple[float, float, float] | None = None,
    extents: tuple[float, float, float] | None = None,
    tags: list[str] | None = None,
) -> ShapePrimitive:
    return ShapePrimitive(
        primitive_type="box",
        part=part,
        center=center or component.center,
        extents=extents or component.extents,
        tags=tags or list(component.tags),
        component=component.component_type,
        region=component.name,
    )


def _cylinder(
    part: str,
    component: BlueprintComponent,
    *,
    center: tuple[float, float, float] | None = None,
    radius: float | None = None,
    height: float | None = None,
    axis: str | None = None,
    tags: list[str] | None = None,
) -> ShapePrimitive:
    return ShapePrimitive(
        primitive_type="cylinder",
        part=part,
        center=center or component.center,
        radius=radius if radius is not None else component.radius,
        height=height if height is not None else component.height,
        axis=axis or component.axis,
        tags=tags or list(component.tags),
        component=component.component_type,
        region=component.name,
    )


def _sphere(
    part: str,
    component: BlueprintComponent,
    *,
    center: tuple[float, float, float] | None = None,
    radius: float | None = None,
    tags: list[str] | None = None,
) -> ShapePrimitive:
    return ShapePrimitive(
        primitive_type="sphere",
        part=part,
        center=center or component.center,
        radius=radius if radius is not None else component.radius,
        tags=tags or list(component.tags),
        component=component.component_type,
        region=component.name,
    )


def _torus(
    part: str,
    component: BlueprintComponent,
    *,
    center: tuple[float, float, float] | None = None,
    major_radius: float,
    minor_radius: float,
    axis: str | None = None,
    tags: list[str] | None = None,
) -> ShapePrimitive:
    return ShapePrimitive(
        primitive_type="torus",
        part=part,
        center=center or component.center,
        major_radius=major_radius,
        minor_radius=minor_radius,
        axis=axis or component.axis,
        tags=tags or list(component.tags),
        component=component.component_type,
        region=component.name,
    )


def _revolved_profile(
    part: str,
    component: BlueprintComponent,
    *,
    center: tuple[float, float, float] | None = None,
    profile_points: list[tuple[float, float]],
    axis: str | None = None,
    tags: list[str] | None = None,
) -> ShapePrimitive:
    return ShapePrimitive(
        primitive_type="revolved_profile",
        part=part,
        center=center or component.center,
        profile_points=profile_points,
        axis=axis or component.axis,
        tags=tags or list(component.tags),
        component=component.component_type,
        region=component.name,
    )


def _extruded_profile(
    part: str,
    component: BlueprintComponent,
    *,
    center: tuple[float, float, float] | None = None,
    profile_polygon: list[tuple[float, float]],
    extrude_height: float,
    axis: str | None = None,
    tags: list[str] | None = None,
    blend_mode: str = "union",
    rounding: float = 0.0,
) -> ShapePrimitive:
    return ShapePrimitive(
        primitive_type="extruded_profile",
        part=part,
        center=center or component.center,
        profile_polygon=profile_polygon,
        extrude_height=extrude_height,
        axis=axis or component.axis,
        tags=tags or list(component.tags),
        component=component.component_type,
        region=component.name,
        blend_mode=blend_mode,
        rounding=rounding,
    )


def _subdivision_box(
    part: str,
    component: BlueprintComponent,
    *,
    center: tuple[float, float, float] | None = None,
    extents: tuple[float, float, float] | None = None,
    corner_radii: tuple[float, float, float, float, float, float, float, float] | None = None,
    corner_segments: int = 4,
    tags: list[str] | None = None,
) -> ShapePrimitive:
    box_extents = extents or component.extents
    radius = max(min(box_extents) * 0.14, 0.001)
    return ShapePrimitive(
        primitive_type="subdivision_box",
        part=part,
        center=center or component.center,
        extents=box_extents,
        corner_radii=corner_radii or (radius,) * 8,
        corner_segments=corner_segments,
        tags=tags or list(component.tags),
        component=component.component_type,
        region=component.name,
    )


def _swept_profile(
    part: str,
    component: BlueprintComponent,
    *,
    center: tuple[float, float, float] | None = None,
    cross_section: list[tuple[float, float]],
    sweep_path: list[tuple[float, float, float]],
    tags: list[str] | None = None,
    blend_mode: str = "union",
) -> ShapePrimitive:
    return ShapePrimitive(
        primitive_type="swept_profile",
        part=part,
        center=center or component.center,
        cross_section=cross_section,
        sweep_path=sweep_path,
        tags=tags or list(component.tags),
        component=component.component_type,
        region=component.name,
        blend_mode=blend_mode,
    )


def _chamfered_rect_profile(width: float, height: float, chamfer: float) -> list[tuple[float, float]]:
    half_w = max(width * 0.5, 0.001)
    half_h = max(height * 0.5, 0.001)
    cut = max(0.0, min(chamfer, half_w * 0.72, half_h * 0.72))
    if cut <= 0.0:
        return [(-half_w, -half_h), (half_w, -half_h), (half_w, half_h), (-half_w, half_h)]
    return [
        (-half_w + cut, -half_h),
        (half_w - cut, -half_h),
        (half_w, -half_h + cut),
        (half_w, half_h - cut),
        (half_w - cut, half_h),
        (-half_w + cut, half_h),
        (-half_w, half_h - cut),
        (-half_w, -half_h + cut),
    ]


def _round_cross_section(radius: float, segments: int = 8) -> list[tuple[float, float]]:
    return [
        (math.cos(math.tau * index / segments) * radius, math.sin(math.tau * index / segments) * radius)
        for index in range(segments)
    ]


def _axis_sweep_path(length: float, axis: str) -> list[tuple[float, float, float]]:
    half = max(length, 0.001) * 0.5
    if axis == "x":
        return [(-half, 0.0, 0.0), (half, 0.0, 0.0)]
    if axis == "z":
        return [(0.0, 0.0, -half), (0.0, 0.0, half)]
    return [(0.0, -half, 0.0), (0.0, half, 0.0)]


def _round_bar(
    part: str,
    component: BlueprintComponent,
    *,
    center: tuple[float, float, float] | None = None,
    radius: float,
    height: float,
    axis: str | None = None,
    tags: list[str] | None = None,
) -> ShapePrimitive:
    bar_axis = axis or component.axis
    return _swept_profile(
        part,
        component,
        center=center,
        cross_section=_round_cross_section(radius, 10),
        sweep_path=_axis_sweep_path(height, bar_axis),
        tags=tags or list(component.tags),
    )


def _lathed_cylinder_profile(height: float, radius: float, *, bevel: float = 0.08) -> list[tuple[float, float]]:
    half = max(height, 0.001) * 0.5
    shoulder = max(0.0, min(bevel, 0.35))
    inner = max(half * (1.0 - shoulder), 0.0)
    return [
        (-half, radius * 0.82),
        (-inner, radius),
        (inner, radius),
        (half, radius * 0.82),
    ]


def _lofted_solid(
    part: str,
    component: BlueprintComponent,
    *,
    center: tuple[float, float, float] | None = None,
    cross_sections: list[list[tuple[float, float]]],
    section_centers: list[tuple[float, float, float]],
    tags: list[str] | None = None,
    blend_mode: str = "union",
) -> ShapePrimitive:
    return ShapePrimitive(
        primitive_type="lofted_solid",
        part=part,
        center=center or component.center,
        cross_sections=cross_sections,
        section_centers=section_centers,
        tags=tags or list(component.tags),
        component=component.component_type,
        region=component.name,
        blend_mode=blend_mode,
    )


_CHEST_CONTAINER_TAGS = {"container", "chest", "brassbound", "loot", "wood_and_brass", "crate"}
_BRASS_BAND_AUTHORING_TOKENS = {
    "aged_brass",
    "band",
    "banded",
    "brass",
    "brass_band",
    "brassbound",
    "container",
    "plank",
    "plank_displacement",
    "stave",
    "stave_built",
    "trim_band",
}


def _is_container_component(component: BlueprintComponent) -> bool:
    """Detect chest/crate-like containers from component tags.

    The synthesis-architect recipe (lofted_solid stave shells, lathed feet,
    revolved-profile hinge barrels, U-arc handles) is keyed off this; other
    asset families fall through to the legacy primitive recipe.
    """
    tag_set = {str(tag).lower() for tag in component.tags}
    if tag_set & _CHEST_CONTAINER_TAGS:
        return True
    for tag in tag_set:
        if "chest" in tag or "brassbound" in tag or "loot_chest" in tag:
            return True
    return False


def _asset_graph_authoring_tokens(asset_graph: AssetGraph) -> set[str]:
    authoring = asset_graph.authoring if isinstance(asset_graph.authoring, dict) else {}
    values: list[object] = [
        asset_graph.family,
        asset_graph.kind,
        asset_graph.role,
        authoring.get("asset_class"),
        authoring.get("style_target"),
        authoring.get("family_ref"),
        authoring.get("from_family"),
    ]
    values.extend(asset_graph.styles)
    values.extend(asset_graph.materials)
    tokens: set[str] = set()
    for value in values:
        tokens.update(_edge_class_tokens(str(value).lower()))
    return {token for token in tokens if token}


def _should_emit_brass_band_primitives(asset_graph: AssetGraph, blueprint: AssemblyBlueprint) -> bool:
    component_tokens: set[str] = set()
    for component in blueprint.components:
        for tag in component.tags:
            component_tokens.update(_edge_class_tokens(str(tag).lower()))
        component_tokens.update(_edge_class_tokens(component.name.lower()))
        component_tokens.update(_edge_class_tokens(component.part.lower()))
        component_tokens.update(_edge_class_tokens(component.component_type.lower()))
    if component_tokens & _BRASS_BAND_AUTHORING_TOKENS:
        return True
    asset_tokens = _asset_graph_authoring_tokens(asset_graph)
    if not (asset_tokens & _BRASS_BAND_AUTHORING_TOKENS):
        return False
    return any(_is_container_component(component) for component in blueprint.components)


def _rounded_rect_section(width: float, depth: float, *, corner_radius: float, points_per_corner: int = 3) -> list[tuple[float, float]]:
    """Generate a CCW rounded-rectangle polygon in (u, v) suitable for lofted cross-sections.

    Always returns ``4 * (points_per_corner + 1)`` points. The corner radius
    is clamped to a small non-zero floor so vertex count is constant across
    calls (lofted_solid requires every section to share vertex count).
    """
    half_w = max(width * 0.5, 0.001)
    half_d = max(depth * 0.5, 0.001)
    r_max = min(half_w * 0.5, half_d * 0.5)
    r = max(min(corner_radius, r_max), r_max * 0.001)
    points: list[tuple[float, float]] = []
    corners = [
        (half_w - r, -half_d + r, -math.tau / 4.0),  # bottom-right (start at 270°)
        (half_w - r, half_d - r, 0.0),               # top-right (start at 0°)
        (-half_w + r, half_d - r, math.tau / 4.0),   # top-left (start at 90°)
        (-half_w + r, -half_d + r, math.tau / 2.0),  # bottom-left (start at 180°)
    ]
    for cx, cz, start_angle in corners:
        for i in range(points_per_corner + 1):
            t = i / max(points_per_corner, 1)
            angle = start_angle + (math.tau / 4.0) * t
            points.append((cx + r * math.cos(angle), cz + r * math.sin(angle)))
    return points


def _arched_section(width: float, depth: float, *, corner_radius: float, points_per_corner: int = 3) -> list[tuple[float, float]]:
    """A rounded rectangle alias for arched lid sections (separate name for clarity)."""
    return _rounded_rect_section(width, depth, corner_radius=corner_radius, points_per_corner=points_per_corner)


def _shield_outline(width: float, height: float) -> list[tuple[float, float]]:
    """Victorian shield/oval polygon (CCW) for the chest lock plate outer outline.

    Returns a 12-point polygon: rectangular shoulders top, narrowing waist mid,
    rounded point bottom — like a heraldic escutcheon.
    """
    half_w = max(width * 0.5, 0.001)
    half_h = max(height * 0.5, 0.001)
    return [
        (-half_w * 0.55, -half_h),             # bottom-left of point
        (0.0, -half_h * 1.05),                  # bottom point
        (half_w * 0.55, -half_h),              # bottom-right of point
        (half_w, -half_h * 0.55),              # right waist-low
        (half_w * 0.92, -half_h * 0.10),       # right waist
        (half_w, half_h * 0.55),               # right shoulder
        (half_w * 0.78, half_h * 0.92),        # upper-right curve
        (half_w * 0.30, half_h),               # top-right
        (-half_w * 0.30, half_h),              # top-left
        (-half_w * 0.78, half_h * 0.92),       # upper-left curve
        (-half_w, half_h * 0.55),              # left shoulder
        (-half_w * 0.92, -half_h * 0.10),      # left waist
        (-half_w, -half_h * 0.55),             # left waist-low
    ]


def _rounded_rect_outline_2d(width: float, height: float, corner_radius: float) -> list[tuple[float, float]]:
    """CCW rounded-rectangle outline for plate extrudes (8 points, simple)."""
    half_w = max(width * 0.5, 0.001)
    half_h = max(height * 0.5, 0.001)
    r = max(0.0, min(corner_radius, half_w * 0.45, half_h * 0.45))
    if r <= 1e-4:
        return [(-half_w, -half_h), (half_w, -half_h), (half_w, half_h), (-half_w, half_h)]
    return [
        (-half_w + r, -half_h),
        (half_w - r, -half_h),
        (half_w, -half_h + r),
        (half_w, half_h - r),
        (half_w - r, half_h),
        (-half_w + r, half_h),
        (-half_w, half_h - r),
        (-half_w, -half_h + r),
    ]


def _shell_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    if not _is_container_component(component):
        return [
            _subdivision_box(component.part, component, tags=[*list(component.tags), "outer_shell", "subdivision_shell"], corner_segments=4),
            _subdivision_box(
                component.part,
                component,
                center=(component.center[0], component.center[1] + height * 0.06, component.center[2]),
                extents=(width * 0.88, height * 0.78, depth * 0.88),
                tags=[*list(component.tags), "liner", "subdivision_shell_liner"],
                corner_segments=3,
            ),
        ]

    cx, cy, cz = component.center
    half_h = height * 0.5
    # Tapered stave-built body: wider at the bottom (5%), narrower at the
    # top, with a slight outward bow at mid-height — like a hand-built old
    # chest. 4 sections, rounded rectangle profile.
    base_corner = min(width, depth) * 0.085
    section_z = [-half_h, -half_h * 0.34, half_h * 0.34, half_h]
    width_ratios = [1.05, 1.02, 0.98, 0.94]
    depth_ratios = [1.05, 1.02, 0.98, 0.94]
    radius_jitter = [1.00, 1.06, 1.04, 0.98]
    cross_sections: list[list[tuple[float, float]]] = []
    section_centers: list[tuple[float, float, float]] = []
    for w_ratio, d_ratio, r_jitter, z in zip(width_ratios, depth_ratios, radius_jitter, section_z, strict=False):
        sec_w = width * w_ratio
        sec_d = depth * d_ratio
        sec_r = base_corner * r_jitter
        cross_sections.append(_rounded_rect_section(sec_w, sec_d, corner_radius=sec_r, points_per_corner=3))
        section_centers.append((cx, cy + z, cz))

    primitives: list[ShapePrimitive] = [
        _lofted_solid(
            component.part,
            component,
            center=(cx, cy, cz),
            cross_sections=cross_sections,
            section_centers=section_centers,
            tags=[
                *list(component.tags),
                "outer_shell",
                "lofted_shell_body",
                "stave_built",
                "panel_seam",
            ],
        ),
    ]

    # Inset inner liner: smaller lofted_solid offset slightly upward; not a
    # subtract (downstream prefers union for shape coverage), but tagged as
    # liner so optimization can collapse it if needed.
    inner_w = width * 0.86
    inner_d = depth * 0.86
    inner_h = height * 0.78
    inner_half_h = inner_h * 0.5
    inner_section_z = [-inner_half_h, -inner_half_h * 0.34, inner_half_h * 0.34, inner_half_h]
    inner_w_ratios = [1.02, 1.00, 0.97, 0.94]
    inner_d_ratios = [1.02, 1.00, 0.97, 0.94]
    inner_cross_sections: list[list[tuple[float, float]]] = []
    inner_section_centers: list[tuple[float, float, float]] = []
    inner_corner = min(inner_w, inner_d) * 0.075
    for w_ratio, d_ratio, z in zip(inner_w_ratios, inner_d_ratios, inner_section_z, strict=False):
        inner_cross_sections.append(
            _rounded_rect_section(inner_w * w_ratio, inner_d * d_ratio, corner_radius=inner_corner, points_per_corner=3)
        )
        inner_section_centers.append((cx, cy + height * 0.06 + z, cz))
    primitives.append(
        _lofted_solid(
            component.part,
            component,
            center=(cx, cy + height * 0.06, cz),
            cross_sections=inner_cross_sections,
            section_centers=inner_section_centers,
            tags=[*list(component.tags), "liner", "lofted_shell_liner"],
        )
    )
    return primitives


def _panel_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    return [
        _extruded_profile(
            component.part,
            component,
            profile_polygon=_chamfered_rect_profile(width, height, min(width, height) * 0.04),
            extrude_height=depth,
            axis="z",
            tags=[*list(component.tags), "panel", "extruded_panel"],
            rounding=0.02,
        )
    ]


def _frame_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    thickness = max(min(width, height) * 0.10, depth * 0.9)
    half_w = width / 2.0
    half_h = height / 2.0
    cz = component.center[2]
    return [
        _extruded_profile(
            component.part,
            component,
            center=(component.center[0], component.center[1] + half_h - thickness / 2.0, cz),
            profile_polygon=_chamfered_rect_profile(width, thickness, thickness * 0.22),
            extrude_height=depth,
            axis="z",
            tags=[*list(component.tags), "top_frame_rail", "extruded_frame_rail"],
            rounding=0.02,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(component.center[0], component.center[1] - half_h + thickness / 2.0, cz),
            profile_polygon=_chamfered_rect_profile(width, thickness, thickness * 0.22),
            extrude_height=depth,
            axis="z",
            tags=[*list(component.tags), "bottom_frame_rail", "extruded_frame_rail"],
            rounding=0.02,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(component.center[0] - half_w + thickness / 2.0, component.center[1], cz),
            profile_polygon=_chamfered_rect_profile(thickness, max(thickness, height - 2.0 * thickness), thickness * 0.22),
            extrude_height=depth,
            axis="z",
            tags=[*list(component.tags), "left_frame_stile", "extruded_frame_stile"],
            rounding=0.02,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(component.center[0] + half_w - thickness / 2.0, component.center[1], cz),
            profile_polygon=_chamfered_rect_profile(thickness, max(thickness, height - 2.0 * thickness), thickness * 0.22),
            extrude_height=depth,
            axis="z",
            tags=[*list(component.tags), "right_frame_stile", "extruded_frame_stile"],
            rounding=0.02,
        ),
    ]


def _lid_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    if not _is_container_component(component):
        return [
            _subdivision_box(component.part, component, tags=[*list(component.tags), "lid_slab", "subdivision_lid_slab"], corner_segments=4),
            _extruded_profile(
                component.part,
                component,
                center=(component.center[0], component.center[1] + height * 0.18, component.center[2]),
                profile_polygon=_chamfered_rect_profile(width * 0.74, height * 0.52, min(width, height) * 0.05),
                extrude_height=depth * 0.84,
                axis="z",
                tags=[*list(component.tags), "crest", "extruded_lid_crest"],
                rounding=0.02,
            ),
        ]

    cx, cy, cz = component.center
    half_h = height * 0.5
    # Arched dome lid: 5 sections going from the wide base lip up to a much
    # narrower top, curving inward. The lid lips slightly past the body.
    base_corner = min(width, depth) * 0.10
    # Dome curvature: width factor follows a quarter-cosine from 1.0 at base
    # to ~0.55 at top to give a true arch (not a frustum).
    dome_t = [0.0, 0.30, 0.55, 0.78, 1.0]
    section_z = [-half_h * 0.92, -half_h * 0.30, half_h * 0.20, half_h * 0.62, half_h]
    cross_sections: list[list[tuple[float, float]]] = []
    section_centers: list[tuple[float, float, float]] = []
    for t, z in zip(dome_t, section_z, strict=False):
        # Width factor follows cos(t * pi/2) so the dome is full at base
        # (1.0) and ~0.55 at the apex with a smooth arch in between. The
        # lid lips slightly past the body extents at the base (1.06).
        if t == 0.0:
            w_factor = 1.06
            d_factor = 1.06
        else:
            arch = math.cos(t * math.pi * 0.5)
            w_factor = 0.55 + 0.45 * arch
            d_factor = 0.60 + 0.40 * arch
        sec_w = width * w_factor
        sec_d = depth * d_factor
        sec_r = base_corner * (1.0 - t * 0.4)
        cross_sections.append(_arched_section(sec_w, sec_d, corner_radius=sec_r, points_per_corner=3))
        section_centers.append((cx, cy + z, cz))

    primitives: list[ShapePrimitive] = [
        _lofted_solid(
            component.part,
            component,
            center=(cx, cy, cz),
            cross_sections=cross_sections,
            section_centers=section_centers,
            tags=[
                *list(component.tags),
                "lid_slab",
                "lofted_lid_dome",
                "lid_break",
                "panel_seam",
            ],
        ),
    ]

    # Decorative revolved-profile crest centered atop the lid dome.
    crest_radius = min(width, depth) * 0.25 * 0.5
    crest_height = height * 0.15
    crest_cy = cy + half_h + crest_height * 0.45
    primitives.append(
        _revolved_profile(
            component.part,
            component,
            center=(cx, crest_cy, cz),
            profile_points=[
                (-crest_height * 0.5, crest_radius * 0.95),
                (-crest_height * 0.30, crest_radius * 1.05),
                (-crest_height * 0.10, crest_radius * 0.88),
                (crest_height * 0.05, crest_radius * 0.72),
                (crest_height * 0.25, crest_radius * 0.55),
                (crest_height * 0.45, crest_radius * 0.30),
                (crest_height * 0.50, crest_radius * 0.05),
            ],
            axis="y",
            tags=[
                *list(component.tags),
                "crest",
                "revolved_lid_crest",
                "lid_break",
            ],
        )
    )
    return primitives


def _door_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    return [
        _subdivision_box(component.part, component, tags=[*list(component.tags), "door_slab", "subdivision_door_slab"], corner_segments=4),
        _extruded_profile(
            component.part,
            component,
            center=(component.center[0], component.center[1], component.center[2] + depth * 0.18),
            profile_polygon=_chamfered_rect_profile(width * 0.88, height * 0.90, min(width, height) * 0.04),
            extrude_height=depth * 0.30,
            axis="z",
            tags=[*list(component.tags), "face", "extruded_door_face"],
            rounding=0.02,
        ),
    ]


def _hinge_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    radius = component.radius if component.radius is not None else max(width, depth) * 0.42
    barrel_height = component.height if component.height is not None else max(width, height, depth)
    cx, cy, cz = component.center

    if not _is_container_component(component):
        return [
            _revolved_profile(
                component.part,
                component,
                profile_points=_lathed_cylinder_profile(barrel_height, radius, bevel=0.12),
                axis=component.axis,
                tags=[*list(component.tags), "barrel", "lathed_hinge_barrel"],
            ),
            _extruded_profile(
                component.part,
                component,
                center=(cx, cy, cz - depth * 0.20),
                profile_polygon=_chamfered_rect_profile(width, height * 0.45, height * 0.06),
                extrude_height=depth * 0.55,
                axis="z",
                tags=[*list(component.tags), "mount", "extruded_hinge_mount"],
                rounding=0.02,
            ),
        ]

    # Detailed brass-knuckle barrel: end cap, mid band ring, end cap.
    # profile_points are (axial, radial) along ``component.axis``.
    half_b = max(barrel_height, 0.001) * 0.5
    end_cap_axial = half_b * 0.92
    end_band_axial = half_b * 0.78
    mid_band_axial = half_b * 0.18
    barrel_profile = [
        (-half_b, radius * 0.55),
        (-end_cap_axial, radius * 1.05),
        (-end_band_axial, radius * 1.00),
        (-mid_band_axial, radius * 0.92),
        (-mid_band_axial * 0.4, radius * 1.04),
        (mid_band_axial * 0.4, radius * 1.04),
        (mid_band_axial, radius * 0.92),
        (end_band_axial, radius * 1.00),
        (end_cap_axial, radius * 1.05),
        (half_b, radius * 0.55),
    ]
    primitives: list[ShapePrimitive] = [
        _revolved_profile(
            component.part,
            component,
            profile_points=barrel_profile,
            axis=component.axis,
            tags=[
                *list(component.tags),
                "barrel",
                "revolved_hinge_barrel",
                "brass_band",
                "panel_seam",
            ],
        ),
    ]

    # Two flat mount plates: one attached to body, one to lid. They live on
    # opposite sides of the barrel, normal to the lid_break seam.
    plate_w = width
    plate_h = max(height * 0.50, radius * 1.4)
    plate_d = max(depth * 0.18, 0.05)
    plate_corner = min(plate_w, plate_h) * 0.12
    plate_polygon = _rounded_rect_outline_2d(plate_w, plate_h, plate_corner)

    # Body-side mount plate (below the barrel, attaches to body shell).
    primitives.append(
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy - radius * 0.6, cz - depth * 0.18),
            profile_polygon=plate_polygon,
            extrude_height=plate_d,
            axis="z",
            tags=[
                *list(component.tags),
                "mount",
                "body_side",
                "extruded_hinge_mount",
                "panel_seam",
            ],
            rounding=0.02,
        )
    )
    # Lid-side mount plate (above the barrel, attaches to lid).
    primitives.append(
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + radius * 0.6, cz - depth * 0.18),
            profile_polygon=plate_polygon,
            extrude_height=plate_d,
            axis="z",
            tags=[
                *list(component.tags),
                "mount",
                "lid_side",
                "extruded_hinge_mount",
                "panel_seam",
            ],
            rounding=0.02,
        )
    )
    return primitives


def _latch_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    return [
        _extruded_profile(
            component.part,
            component,
            profile_polygon=_chamfered_rect_profile(width, height, min(width, height) * 0.08),
            extrude_height=depth,
            axis="z",
            tags=[*list(component.tags), "latch_plate", "extruded_latch_plate"],
            rounding=0.02,
        )
    ]


def _lock_plate_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    if not _is_container_component(component):
        return [
            _extruded_profile(
                component.part,
                component,
                profile_polygon=_chamfered_rect_profile(width, height, min(width, height) * 0.08),
                extrude_height=depth,
                axis="z",
                tags=[*list(component.tags), "lock_plate", "extruded_lock_plate"],
                rounding=0.02,
            ),
            _revolved_profile(
                component.part,
                component,
                center=(cx, cy - height * 0.18, cz + depth * 0.08),
                profile_points=[
                    (-depth * 0.20, width * 0.12),
                    (0.0, width * 0.18),
                    (depth * 0.20, width * 0.12),
                ],
                axis="z",
                tags=[*list(component.tags), "latch_body", "lathed_latch_body"],
            ),
        ]

    primitives: list[ShapePrimitive] = []
    # Outer ornate Victorian shield plate.
    primitives.append(
        _extruded_profile(
            component.part,
            component,
            profile_polygon=_shield_outline(width, height),
            extrude_height=depth,
            axis="z",
            tags=[
                *list(component.tags),
                "lock_plate",
                "extruded_lock_plate",
                "ornate_shield",
                "clasp_cut",
                "panel_seam",
            ],
            rounding=0.02,
        )
    )
    # Decorative latch knob (revolved profile centered, slightly raised
    # off the plate face).
    primitives.append(
        _revolved_profile(
            component.part,
            component,
            center=(cx, cy - height * 0.20, cz + depth * 0.55),
            profile_points=[
                (-depth * 0.20, width * 0.10),
                (-depth * 0.10, width * 0.16),
                (0.0, width * 0.20),
                (depth * 0.10, width * 0.16),
                (depth * 0.22, width * 0.08),
            ],
            axis="z",
            tags=[
                *list(component.tags),
                "latch_body",
                "lathed_latch_body",
                "clasp_cut",
            ],
        )
    )
    # Keyhole boolean-subtract: small circle (round head) above a tiny
    # rectangular slot (key shaft). Two extruded_profiles in subtract mode
    # carve into the plate face.
    keyhole_radius = min(width, height) * 0.07
    keyhole_circle = [
        (
            keyhole_radius * math.cos(math.tau * i / 14.0),
            keyhole_radius * math.sin(math.tau * i / 14.0),
        )
        for i in range(14)
    ]
    primitives.append(
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.05, cz + depth * 0.10),
            profile_polygon=keyhole_circle,
            extrude_height=depth * 1.10,
            axis="z",
            tags=[
                *list(component.tags),
                "keyhole_circle",
                "extruded_keyhole",
                "clasp_cut",
            ],
            blend_mode="subtract",
        )
    )
    shaft_w = keyhole_radius * 0.6
    shaft_h = min(width, height) * 0.16
    shaft_polygon = [
        (-shaft_w, -shaft_h),
        (shaft_w, -shaft_h),
        (shaft_w, shaft_h * 0.2),
        (-shaft_w, shaft_h * 0.2),
    ]
    primitives.append(
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy - height * 0.04, cz + depth * 0.10),
            profile_polygon=shaft_polygon,
            extrude_height=depth * 1.10,
            axis="z",
            tags=[
                *list(component.tags),
                "keyhole_shaft",
                "extruded_keyhole",
                "clasp_cut",
            ],
            blend_mode="subtract",
        )
    )
    return primitives


def _handle_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    radius = component.radius if component.radius is not None else max(height, depth) * 0.36
    handle_height = component.height if component.height is not None else max(width, height, depth) * 0.85
    if not _is_container_component(component):
        path_span = handle_height * 0.50
        if component.axis == "x":
            sweep_path = [(-path_span, 0.0, 0.0), (0.0, height * 0.18, 0.0), (path_span, 0.0, 0.0)]
        elif component.axis == "z":
            sweep_path = [(0.0, 0.0, -path_span), (0.0, height * 0.18, 0.0), (0.0, 0.0, path_span)]
        else:
            sweep_path = [(0.0, -path_span, 0.0), (width * 0.10, 0.0, 0.0), (0.0, path_span, 0.0)]
        return [
            _swept_profile(
                component.part,
                component,
                cross_section=_round_cross_section(radius, 8),
                sweep_path=sweep_path,
                tags=[*list(component.tags), "grip", "swept_handle_grip"],
            )
        ]

    # True U-arc handle: 10 path points sweeping from one mount up-and-over
    # to the other. The arc rises off the body face along the local normal
    # (component axis defines mount-line direction, perpendicular = arc).
    arc_segments = 10
    arc_span = handle_height * 0.55
    arc_rise = max(handle_height * 0.45, radius * 2.0)
    sweep_path: list[tuple[float, float, float]] = []
    for i in range(arc_segments):
        t = i / (arc_segments - 1)
        # ``s`` walks from -1 to +1 along the mount span; arc lifts off
        # the mount face following sin(pi*t) for a smooth U-shape.
        s = -1.0 + 2.0 * t
        rise = math.sin(math.pi * t) * arc_rise
        if component.axis == "x":
            sweep_path.append((s * arc_span, rise, 0.0))
        elif component.axis == "z":
            sweep_path.append((0.0, rise, s * arc_span))
        else:
            sweep_path.append((rise, s * arc_span, 0.0))

    cx, cy, cz = component.center
    primitives: list[ShapePrimitive] = [
        _swept_profile(
            component.part,
            component,
            cross_section=_round_cross_section(radius, 12),
            sweep_path=sweep_path,
            tags=[
                *list(component.tags),
                "grip",
                "swept_handle_grip",
                "u_arc",
                "panel_seam",
            ],
        ),
    ]

    # Two end-cap mounts where the handle attaches to the body — small
    # revolved spheroids grounding each terminus.
    cap_radius = radius * 1.35
    cap_height = radius * 1.6
    cap_profile = [
        (-cap_height * 0.5, cap_radius * 0.15),
        (-cap_height * 0.30, cap_radius * 0.85),
        (-cap_height * 0.10, cap_radius * 1.00),
        (cap_height * 0.10, cap_radius * 0.92),
        (cap_height * 0.30, cap_radius * 0.55),
        (cap_height * 0.50, cap_radius * 0.10),
    ]
    end0 = sweep_path[0]
    end1 = sweep_path[-1]
    cap_axis = "y"
    if component.axis in {"x", "z", "y"}:
        cap_axis = component.axis
    primitives.append(
        _revolved_profile(
            component.part,
            component,
            center=(cx + end0[0], cy + end0[1], cz + end0[2]),
            profile_points=cap_profile,
            axis=cap_axis,
            tags=[
                *list(component.tags),
                "grip_end_cap",
                "left_terminus",
                "revolved_handle_cap",
                "panel_seam",
            ],
        )
    )
    primitives.append(
        _revolved_profile(
            component.part,
            component,
            center=(cx + end1[0], cy + end1[1], cz + end1[2]),
            profile_points=cap_profile,
            axis=cap_axis,
            tags=[
                *list(component.tags),
                "grip_end_cap",
                "right_terminus",
                "revolved_handle_cap",
                "panel_seam",
            ],
        )
    )
    return primitives


def _foot_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    if not _is_container_component(component):
        return [
            _subdivision_box(component.part, component, tags=[*list(component.tags), "foot_body", "subdivision_foot_body"], corner_segments=4),
            _extruded_profile(
                component.part,
                component,
                center=(component.center[0], component.center[1] - height * 0.20, component.center[2]),
                profile_polygon=_chamfered_rect_profile(width * 1.14, height * 0.35, height * 0.06),
                extrude_height=depth * 1.08,
                axis="z",
                tags=[*list(component.tags), "pad", "extruded_foot_pad"],
                rounding=0.02,
            ),
        ]

    # Lathed (turned) chest leg: top wide attachment block, narrow waist,
    # widening foot pad, flat termination at floor. profile_points are
    # (axial, radial), axis = vertical "y".
    half_h = max(height, 0.001) * 0.5
    base_radius = max(min(width, depth) * 0.5, 0.05)
    waist_radius = base_radius * 0.55
    pad_radius = base_radius * 0.92
    top_radius = base_radius * 0.96
    lathed_profile = [
        (-half_h, base_radius * 0.05),               # bottom centerline
        (-half_h * 0.97, pad_radius * 1.05),          # foot pad outer
        (-half_h * 0.82, pad_radius * 0.95),
        (-half_h * 0.65, pad_radius * 0.78),          # foot pad inner shoulder
        (-half_h * 0.45, waist_radius * 1.20),
        (-half_h * 0.20, waist_radius),               # narrow waist
        (half_h * 0.10, waist_radius * 1.05),
        (half_h * 0.40, top_radius * 0.85),
        (half_h * 0.70, top_radius * 1.00),
        (half_h * 0.92, top_radius * 1.05),           # top attachment block
        (half_h, top_radius * 0.30),
    ]
    return [
        _revolved_profile(
            component.part,
            component,
            profile_points=lathed_profile,
            axis="y",
            tags=[
                *list(component.tags),
                "foot_body",
                "revolved_lathed_foot",
                "turned_leg",
                "panel_seam",
            ],
        ),
    ]


def _stand_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    return [
        _subdivision_box(component.part, component, tags=[*list(component.tags), "stand_body", "subdivision_stand_body"], corner_segments=4),
        _extruded_profile(
            component.part,
            component,
            center=(component.center[0], component.center[1] - height * 0.42, component.center[2]),
            profile_polygon=_chamfered_rect_profile(width * 1.28, height * 0.22, height * 0.05),
            extrude_height=depth * 1.18,
            axis="z",
            tags=[*list(component.tags), "base", "extruded_stand_base"],
            rounding=0.02,
        ),
    ]


def _bracket_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    return [
        _extruded_profile(
            component.part,
            component,
            center=(component.center[0], component.center[1], component.center[2] - depth * 0.16),
            profile_polygon=_chamfered_rect_profile(width, height * 0.35, height * 0.05),
            extrude_height=depth,
            axis="z",
            tags=[*list(component.tags), "horizontal_bracket_leaf", "extruded_bracket_leaf"],
            rounding=0.02,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(component.center[0], component.center[1] - height * 0.18, component.center[2]),
            profile_polygon=_chamfered_rect_profile(width * 0.35, height, width * 0.05),
            extrude_height=depth,
            axis="z",
            tags=[*list(component.tags), "vertical_bracket_leaf", "extruded_bracket_leaf"],
            rounding=0.02,
        ),
    ]


def _bezel_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    bezel_component = BlueprintComponent(
        name=component.name,
        component_type="bezel",
        part=component.part,
        center=component.center,
        extents=(width, height, max(depth * 0.55, 0.5)),
        tags=list(component.tags),
        adjacency=list(component.adjacency),
        symmetry_mate=component.symmetry_mate,
        interface_role=component.interface_role,
    )
    return _frame_primitives(bezel_component)


def _vent_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    slats = 4
    slat_height = height / (slats * 1.8)
    spacing = height / max(1, slats - 1)
    primitives: list[ShapePrimitive] = []
    start = component.center[1] - spacing * (slats - 1) / 2.0
    for index in range(slats):
        cy = start + spacing * index
        primitives.append(
            _extruded_profile(
                component.part,
                component,
                center=(component.center[0], cy, component.center[2]),
                profile_polygon=_chamfered_rect_profile(width, slat_height, slat_height * 0.25),
                extrude_height=depth,
                axis="z",
                tags=[*list(component.tags), "slat", "extruded_vent_slat"],
                rounding=0.01,
            )
        )
    return primitives


def _rotor_arm_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    radius = max(min(height, depth) * 0.26, 0.025)
    return [
        _swept_profile(
            component.part,
            component,
            cross_section=_round_cross_section(radius, 8),
            sweep_path=[(-width * 0.50, 0.0, 0.0), (0.0, height * 0.04, 0.0), (width * 0.50, 0.0, 0.0)],
            tags=[*list(component.tags), "rotor_arm", "swept_rotor_arm"],
        )
    ]


def _rotor_pod_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    radius = component.radius if component.radius is not None else max(width, depth) * 0.45
    disc_height = component.height if component.height is not None else max(height * 0.40, 1.0)
    return [
        _revolved_profile(
            component.part,
            component,
            profile_points=_lathed_cylinder_profile(disc_height, radius, bevel=0.16),
            axis=component.axis,
            tags=[*list(component.tags), "disc", "lathed_rotor_disc"],
        ),
        _revolved_profile(
            component.part,
            component,
            center=(component.center[0], component.center[1] - height * 0.26, component.center[2]),
            profile_points=_lathed_cylinder_profile(max(height, disc_height * 2.4), radius * 0.34, bevel=0.10),
            axis=component.axis,
            tags=[*list(component.tags), "hub", "lathed_rotor_hub"],
        ),
    ]


def _blade_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    primitives: list[ShapePrimitive] = []
    segment_count = 5
    segment_height = height / segment_count
    for index in range(segment_count):
        t = index / max(1, segment_count - 1)
        segment_width = width * (1.0 - 0.34 * t)
        segment_center_y = cy - height * 0.50 + segment_height * (index + 0.5)
        primitives.append(
            _extruded_profile(
                component.part,
                component,
                center=(cx, segment_center_y, cz),
                profile_polygon=[
                    (-segment_width * 0.50, -segment_height * 0.54),
                    (segment_width * 0.50, -segment_height * 0.48),
                    (segment_width * 0.42, segment_height * 0.54),
                    (-segment_width * 0.42, segment_height * 0.46),
                ],
                extrude_height=depth * 0.88,
                axis="z",
                tags=[*list(component.tags), "blade_face", "extruded_blade_face", f"blade_segment_{index}"],
                rounding=0.01,
            )
        )
    primitives.extend(
        [
            _extruded_profile(
                component.part,
                component,
                center=(cx, cy, cz + depth * 0.50),
                profile_polygon=[
                    (-width * 0.07, -height * 0.46),
                    (width * 0.07, -height * 0.40),
                    (0.0, height * 0.46),
                ],
                extrude_height=depth * 0.20,
                axis="z",
                tags=[*list(component.tags), "feature", "edge_break", "central_ridge", "front", "extruded_blade_ridge"],
                rounding=0.01,
            ),
            _extruded_profile(
                component.part,
                component,
                center=(cx, cy, cz - depth * 0.50),
                profile_polygon=[
                    (-width * 0.07, -height * 0.40),
                    (width * 0.07, -height * 0.46),
                    (0.0, height * 0.46),
                ],
                extrude_height=depth * 0.20,
                axis="z",
                tags=[*list(component.tags), "feature", "edge_break", "central_ridge", "rear", "extruded_blade_ridge"],
                rounding=0.01,
            ),
            _extruded_profile(
                component.part,
                component,
                center=(cx - width * 0.42, cy - height * 0.02, cz),
                profile_polygon=_chamfered_rect_profile(width * 0.08, height * 0.92, width * 0.015),
                extrude_height=depth * 1.04,
                axis="z",
                tags=[*list(component.tags), "feature", "edge_break", "blade_edge", "left", "extruded_blade_edge"],
                rounding=0.01,
            ),
            _extruded_profile(
                component.part,
                component,
                center=(cx + width * 0.42, cy - height * 0.02, cz),
                profile_polygon=_chamfered_rect_profile(width * 0.08, height * 0.92, width * 0.015),
                extrude_height=depth * 1.04,
                axis="z",
                tags=[*list(component.tags), "feature", "edge_break", "blade_edge", "right", "extruded_blade_edge"],
                rounding=0.01,
            ),
            _extruded_profile(
                component.part,
                component,
                center=(cx, cy - height * 0.50, cz),
                profile_polygon=_chamfered_rect_profile(width * 0.92, max(height * 0.035, 0.75), height * 0.02),
                extrude_height=depth * 1.12,
                axis="z",
                tags=[*list(component.tags), "feature", "edge_break", "blade_base_shoulder", "extruded_blade_base_shoulder"],
                rounding=0.01,
            ),
        ]
    )
    return primitives


def _blade_tip_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    primitives: list[ShapePrimitive] = []
    segment_count = 4
    segment_height = height / segment_count
    for index in range(segment_count):
        t = index / max(1, segment_count - 1)
        tip_width = width * (0.76 - 0.60 * t)
        segment_center_y = cy - height * 0.46 + segment_height * (index + 0.5)
        primitives.append(
            _extruded_profile(
                component.part,
                component,
                center=(cx, segment_center_y, cz),
                profile_polygon=[
                    (-max(tip_width, width * 0.10) * 0.50, -segment_height * 0.55),
                    (max(tip_width, width * 0.10) * 0.50, -segment_height * 0.48),
                    (max(tip_width, width * 0.10) * 0.36, segment_height * 0.55),
                    (-max(tip_width, width * 0.10) * 0.36, segment_height * 0.48),
                ],
                extrude_height=depth * (1.0 - 0.16 * t),
                axis="z",
                tags=[*list(component.tags), "feature", "edge_break", "extruded_blade_tip_facet", f"tip_facet_{index}"],
                rounding=0.01,
            )
        )
    primitives.extend(
        [
            _extruded_profile(
                component.part,
                component,
                center=(cx, cy + height * 0.48, cz),
                profile_polygon=[
                    (-width * 0.05, -max(height * 0.05, 0.18)),
                    (width * 0.05, -max(height * 0.05, 0.18)),
                    (0.0, max(height * 0.05, 0.18)),
                ],
                extrude_height=depth * 0.70,
                axis="z",
                tags=[*list(component.tags), "feature", "edge_break", "point", "extruded_blade_point"],
                rounding=0.01,
            ),
            _extruded_profile(
                component.part,
                component,
                center=(cx, cy - height * 0.44, cz),
                profile_polygon=_chamfered_rect_profile(width * 0.72, max(height * 0.11, 0.35), height * 0.02),
                extrude_height=depth * 1.06,
                axis="z",
                tags=[*list(component.tags), "feature", "edge_break", "tip_shoulder", "extruded_tip_shoulder"],
                rounding=0.01,
            ),
        ]
    )
    return primitives


def _fuller_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    cap_height = max(height * 0.030, 0.45)
    return [
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy, cz + depth * 0.34),
            profile_polygon=_chamfered_rect_profile(width * 0.46, height * 0.94, width * 0.06),
            extrude_height=depth * 0.22,
            axis="z",
            tags=[*list(component.tags), "feature", "front", "fuller_channel", "extruded_fuller_channel"],
            blend_mode="subtract",
            rounding=0.02,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy, cz - depth * 0.34),
            profile_polygon=_chamfered_rect_profile(width * 0.46, height * 0.94, width * 0.06),
            extrude_height=depth * 0.22,
            axis="z",
            tags=[*list(component.tags), "feature", "rear", "fuller_channel", "extruded_fuller_channel"],
            blend_mode="subtract",
            rounding=0.02,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.50, cz),
            profile_polygon=_chamfered_rect_profile(width * 0.52, cap_height, cap_height * 0.25),
            extrude_height=depth * 0.34,
            axis="z",
            tags=[*list(component.tags), "feature", "edge_break", "fuller_cap", "extruded_fuller_cap"],
            rounding=0.01,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy - height * 0.50, cz),
            profile_polygon=_chamfered_rect_profile(width * 0.52, cap_height, cap_height * 0.25),
            extrude_height=depth * 0.34,
            axis="z",
            tags=[*list(component.tags), "feature", "edge_break", "fuller_base", "extruded_fuller_cap"],
            rounding=0.01,
        ),
    ]


def _guard_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    radius = component.radius if component.radius is not None else max(height, depth) * 0.42
    guard_height = component.height if component.height is not None else width
    cx, cy, cz = component.center
    return [
        _swept_profile(
            component.part,
            component,
            cross_section=_round_cross_section(radius, 8),
            sweep_path=[(-guard_height * 0.50, 0.0, 0.0), (0.0, height * 0.08, depth * 0.04), (guard_height * 0.50, 0.0, 0.0)],
            tags=[*list(component.tags), "crossbar", "swept_guard_crossbar"],
        ),
        _revolved_profile(
            component.part,
            component,
            center=(cx - guard_height * 0.50, cy, cz),
            profile_points=[
                (-height * 0.44, radius * 0.88),
                (0.0, radius * 1.18),
                (height * 0.44, radius * 0.88),
            ],
            axis="y",
            tags=[*list(component.tags), "feature", "edge_break", "guard_cap", "left", "lathed_guard_cap"],
        ),
        _revolved_profile(
            component.part,
            component,
            center=(cx + guard_height * 0.50, cy, cz),
            profile_points=[
                (-height * 0.44, radius * 0.88),
                (0.0, radius * 1.18),
                (height * 0.44, radius * 0.88),
            ],
            axis="y",
            tags=[*list(component.tags), "feature", "edge_break", "guard_cap", "right", "lathed_guard_cap"],
        ),
        _subdivision_box(
            component.part,
            component,
            extents=(width * 0.18, height * 1.35, depth * 1.10),
            tags=[*list(component.tags), "feature", "edge_break", "center_block", "subdivision_guard_center_block"],
            corner_segments=4,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.70, cz),
            profile_polygon=_chamfered_rect_profile(width * 0.24, height * 0.18, height * 0.04),
            extrude_height=depth * 1.18,
            axis="z",
            tags=[*list(component.tags), "feature", "edge_break", "upper_collar", "extruded_guard_collar"],
            rounding=0.02,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy - height * 0.70, cz),
            profile_polygon=_chamfered_rect_profile(width * 0.24, height * 0.18, height * 0.04),
            extrude_height=depth * 1.18,
            axis="z",
            tags=[*list(component.tags), "feature", "edge_break", "lower_collar", "extruded_guard_collar"],
            rounding=0.02,
        ),
    ]


def _grip_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    radius = component.radius if component.radius is not None else max(width, depth) * 0.44
    grip_height = component.height if component.height is not None else height
    cx, cy, cz = component.center
    primitives = [
        _revolved_profile(
            component.part,
            component,
            profile_points=[
                (-grip_height * 0.50, radius * 0.86),
                (-grip_height * 0.38, radius),
                (0.0, radius * 0.94),
                (grip_height * 0.38, radius),
                (grip_height * 0.50, radius * 0.86),
            ],
            axis="y",
            tags=[*list(component.tags), "leather_core", "lathed_grip_core"],
        )
    ]
    for index, offset in enumerate((-0.42, -0.30, -0.18, -0.06, 0.06, 0.18, 0.30, 0.42)):
        primitives.append(
            _revolved_profile(
                component.part,
                component,
                center=(cx, cy + grip_height * offset, cz),
                profile_points=_lathed_cylinder_profile(
                    max(grip_height * 0.028, 0.50),
                    radius * (1.10 if index % 2 == 0 else 1.04),
                    bevel=0.20,
                ),
                axis="y",
                tags=[*list(component.tags), "feature", "wrap_ridge", "lathed_grip_wrap_ridge", f"wrap_{index}"],
            )
        )
    primitives.extend(
        [
            _revolved_profile(
                component.part,
                component,
                center=(cx, cy + grip_height * 0.50, cz),
                profile_points=_lathed_cylinder_profile(max(grip_height * 0.060, 0.75), radius * 1.16, bevel=0.18),
                axis="y",
                tags=[*list(component.tags), "feature", "edge_break", "upper_grip_collar", "lathed_grip_collar"],
            ),
            _revolved_profile(
                component.part,
                component,
                center=(cx, cy - grip_height * 0.50, cz),
                profile_points=_lathed_cylinder_profile(max(grip_height * 0.060, 0.75), radius * 1.16, bevel=0.18),
                axis="y",
                tags=[*list(component.tags), "feature", "edge_break", "lower_grip_collar", "lathed_grip_collar"],
            ),
        ]
    )
    return primitives


def _pommel_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    radius = component.radius if component.radius is not None else max(width, depth) * 0.50
    pommel_height = component.height if component.height is not None else height
    profile = [
        (-pommel_height * 0.50, radius * 0.36),
        (-pommel_height * 0.38, radius * 0.82),
        (-pommel_height * 0.14, radius),
        (pommel_height * 0.14, radius * 0.86),
        (pommel_height * 0.38, radius * 0.70),
        (pommel_height * 0.50, radius * 0.42),
    ]
    return [
        _revolved_profile(
            component.part,
            component,
            profile_points=profile,
            axis="y",
            tags=[*list(component.tags), "counterweight", "lathed_pommel"],
        ),
    ]


def _weapon_body_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    return [
        _subdivision_box(
            component.part,
            component,
            tags=[*list(component.tags), "receiver_core", "subdivision_receiver_core"],
            corner_segments=4,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.34, cz + depth * 0.12),
            profile_polygon=_chamfered_rect_profile(width * 0.82, height * 0.22, height * 0.05),
            extrude_height=depth * 0.72,
            axis="z",
            tags=[*list(component.tags), "top_rail", "extruded_receiver_top_rail"],
            rounding=0.03,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy - height * 0.34, cz - depth * 0.10),
            profile_polygon=_chamfered_rect_profile(width * 0.62, height * 0.26, height * 0.05),
            extrude_height=depth * 0.38,
            axis="z",
            tags=[*list(component.tags), "lower_receiver", "extruded_lower_receiver"],
            rounding=0.03,
        ),
    ]


def _barrel_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    radius = component.radius if component.radius is not None else max(min(component.extents[0], component.extents[1]) * 0.45, 0.08)
    height = component.height if component.height is not None else max(component.extents)
    cx, cy, cz = component.center
    return [
        _round_bar(component.part, component, radius=radius, height=height, axis=component.axis, tags=[*list(component.tags), "barrel_tube", "swept_barrel_tube"]),
        _torus(
            component.part,
            component,
            major_radius=radius * 1.10,
            minor_radius=max(radius * 0.18, 0.018),
            axis=component.axis,
            center=(
                cx + height * 0.48 if component.axis == "x" else cx,
                cy + height * 0.48 if component.axis == "y" else cy,
                cz + height * 0.48 if component.axis == "z" else cz,
            ),
            tags=[*list(component.tags), "muzzle_ring", "torus_barrel_muzzle_ring"],
        ),
        _extruded_profile(
            component.part,
            component,
            center=(
                cx,
                cy - radius * 1.20,
                cz - height * 0.10 if component.axis == "z" else cz,
            ),
            profile_polygon=_chamfered_rect_profile(radius * 1.0, radius * 0.55, radius * 0.10),
            extrude_height=height * 0.58 if component.axis == "z" else radius * 1.8,
            axis="z" if component.axis == "z" else "x",
            tags=[*list(component.tags), "underbarrel_rail", "extruded_underbarrel_rail"],
            rounding=0.02,
        ),
    ]


def _stock_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    return [
        _subdivision_box(
            component.part,
            component,
            tags=[*list(component.tags), "stock_body", "subdivision_stock_body"],
            corner_segments=4,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy - height * 0.18, cz - depth * 0.42),
            profile_polygon=_chamfered_rect_profile(width * 1.18, height * 0.64, min(width, height) * 0.06),
            extrude_height=depth * 0.22,
            axis="z",
            tags=[*list(component.tags), "butt_pad", "extruded_butt_pad"],
            rounding=0.04,
        ),
    ]


def _magazine_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    return [
        _subdivision_box(
            component.part,
            component,
            tags=[*list(component.tags), "magazine_body", "subdivision_magazine_body"],
            corner_segments=4,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(component.center[0], component.center[1] - height * 0.48, component.center[2]),
            profile_polygon=_chamfered_rect_profile(width * 1.08, max(height * 0.10, 0.06), min(width, height) * 0.04),
            extrude_height=depth * 1.08,
            axis="z",
            tags=[*list(component.tags), "magazine_floorplate", "extruded_magazine_floorplate"],
            rounding=0.03,
        ),
    ]


def _sight_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    """Emit a scope/optic as: rail mount + revolved scope body + adjustment turret.

    The scope body uses ``primitive_type="revolved_profile"`` so the
    objective-bell → tube → ocular-bell silhouette is real geometry rather
    than a stack of axis-aligned boxes. The mount stays a box because it
    bolts onto a flat picatinny-style rail.
    """
    width, height, depth = component.extents
    cx, cy, cz = component.center
    optic_cy = cy + height * 0.60
    # Scope geometry derived from the component's (height, depth) envelope.
    tube_radius = max(min(height * 0.24, width * 0.30), 0.04)
    objective_radius = max(tube_radius * 1.45, 0.05)
    ocular_radius = max(tube_radius * 1.30, 0.045)
    half_length = max(depth * 0.42, 0.10)
    # Profile points are (axial, radial) along the local axis (axial = z here
    # because we revolve around z so the scope tube runs muzzle-to-shooter).
    profile_points = [
        (-half_length, objective_radius * 0.68),         # objective rim (front)
        (-half_length * 0.82, objective_radius),          # objective bell apex
        (-half_length * 0.62, objective_radius * 0.92),   # bell shoulder
        (-half_length * 0.40, tube_radius),               # bell -> tube
        (-half_length * 0.10, tube_radius),               # tube
        (0.0, tube_radius * 1.18),                        # turret hub bulge
        (half_length * 0.18, tube_radius),                # tube
        (half_length * 0.55, tube_radius),                # tube
        (half_length * 0.72, ocular_radius * 0.95),       # ocular flare
        (half_length * 0.92, ocular_radius),              # ocular cap
        (half_length, ocular_radius * 0.78),              # rear cap chamfer
    ]
    primitives: list[ShapePrimitive] = [
        _extruded_profile(
            component.part,
            component,
            profile_polygon=_chamfered_rect_profile(width, max(height * 0.22, 0.045), min(width, height) * 0.04),
            extrude_height=depth * 0.62,
            axis="z",
            tags=[*list(component.tags), "sight_mount", "extruded_sight_mount"],
            rounding=0.02,
        ),
        ShapePrimitive(
            primitive_type="revolved_profile",
            part=component.part,
            center=(cx, optic_cy, cz),
            axis="z",
            tags=[*list(component.tags), "scope_tube"],
            component=component.component_type,
            region=component.name,
            blend_mode="union",
            profile_points=profile_points,
        ),
        # Elevation/windage turret hub on top of the tube.
        ShapePrimitive(
            primitive_type="cylinder",
            part=component.part,
            center=(cx, optic_cy + tube_radius * 1.05, cz),
            radius=max(tube_radius * 0.70, 0.04),
            height=max(tube_radius * 1.10, 0.05),
            axis="y",
            tags=[*list(component.tags), "elevation_turret"],
            component=component.component_type,
            region=component.name,
            blend_mode="union",
            rounding=0.005,
        ),
    ]
    return primitives


def _trigger_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    return [
        _swept_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.22, cz),
            cross_section=_round_cross_section(max(min(height, depth) * 0.055, 0.025), 8),
            sweep_path=[(-width * 0.68, 0.0, 0.0), (0.0, height * 0.14, depth * 0.02), (width * 0.68, 0.0, 0.0)],
            tags=[*list(component.tags), "trigger_guard", "swept_trigger_guard"],
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy - height * 0.20, cz),
            profile_polygon=[
                (-width * 0.12, height * 0.36),
                (width * 0.14, height * 0.26),
                (width * 0.08, -height * 0.32),
                (-width * 0.08, -height * 0.36),
                (-width * 0.14, height * 0.20),
            ],
            extrude_height=depth * 0.58,
            axis="z",
            tags=[*list(component.tags), "trigger_hook", "extruded_trigger_hook"],
            rounding=0.01,
        ),
    ]


def _tool_head_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    return [
        _subdivision_box(component.part, component, tags=[*list(component.tags), "tool_head_mass", "subdivision_tool_head_mass"], corner_segments=4),
        _extruded_profile(
            component.part,
            component,
            center=(cx - width * 0.38, cy, cz),
            profile_polygon=[
                (-width * 0.15, -height * 0.54),
                (width * 0.15, -height * 0.40),
                (width * 0.09, height * 0.54),
                (-width * 0.15, height * 0.46),
            ],
            extrude_height=depth * 0.78,
            axis="z",
            tags=[*list(component.tags), "left_edge", "extruded_tool_head_edge"],
            rounding=0.02,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx + width * 0.38, cy, cz),
            profile_polygon=[
                (-width * 0.15, -height * 0.40),
                (width * 0.15, -height * 0.54),
                (width * 0.15, height * 0.46),
                (-width * 0.09, height * 0.54),
            ],
            extrude_height=depth * 0.78,
            axis="z",
            tags=[*list(component.tags), "right_edge", "extruded_tool_head_edge"],
            rounding=0.02,
        ),
    ]


def _plate_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    return [
        _extruded_profile(
            component.part,
            component,
            profile_polygon=_chamfered_rect_profile(width, height, min(width, height) * 0.04),
            extrude_height=depth,
            axis="z",
            tags=[*list(component.tags), "plate", "extruded_plate"],
            rounding=0.02,
        )
    ]


def _hardpoint_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    pad_h = max(height * 0.34, 0.035)
    lug_w = max(width * 0.18, 0.035)
    rail_w = max(width * 0.12, 0.03)
    return [
        _subdivision_box(component.part, component, tags=[*list(component.tags), "hardpoint_pad", "subdivision_hardpoint_pad"], corner_segments=4),
        _extruded_profile(
            component.part,
            component,
            center=(cx - width * 0.34, cy + pad_h * 0.84, cz),
            profile_polygon=_chamfered_rect_profile(lug_w, max(height * 0.72, 0.055), lug_w * 0.18),
            extrude_height=depth * 0.72,
            axis="z",
            tags=[*list(component.tags), "left_lock_lug", "extruded_hardpoint_lock_lug"],
            rounding=0.02,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx + width * 0.34, cy + pad_h * 0.84, cz),
            profile_polygon=_chamfered_rect_profile(lug_w, max(height * 0.72, 0.055), lug_w * 0.18),
            extrude_height=depth * 0.72,
            axis="z",
            tags=[*list(component.tags), "right_lock_lug", "extruded_hardpoint_lock_lug"],
            rounding=0.02,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.58, cz),
            profile_polygon=_chamfered_rect_profile(rail_w, max(height * 0.40, 0.04), rail_w * 0.20),
            extrude_height=depth * 0.94,
            axis="z",
            tags=[*list(component.tags), "center_alignment_rail", "extruded_hardpoint_alignment_rail"],
            rounding=0.01,
        ),
    ]


def _crew_bay_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    rim = max(min(width, depth) * 0.08, 0.04)
    return [
        _subdivision_box(component.part, component, tags=[*list(component.tags), "crew_bay_volume", "subdivision_crew_bay_volume"], corner_segments=4),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.45, cz + depth * 0.36),
            profile_polygon=_chamfered_rect_profile(width * 0.72, max(height * 0.18, 0.045), height * 0.03),
            extrude_height=depth * 0.16,
            axis="z",
            tags=[*list(component.tags), "forward_canopy", "extruded_crew_bay_canopy"],
            rounding=0.02,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.50, cz - depth * 0.30),
            profile_polygon=_chamfered_rect_profile(width * 0.62, max(height * 0.16, 0.04), height * 0.03),
            extrude_height=depth * 0.14,
            axis="z",
            tags=[*list(component.tags), "rear_canopy", "extruded_crew_bay_canopy"],
            rounding=0.02,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx - width * 0.50 + rim * 0.50, cy + height * 0.14, cz),
            profile_polygon=_chamfered_rect_profile(rim, height * 0.72, rim * 0.20),
            extrude_height=depth,
            axis="z",
            tags=[*list(component.tags), "left_bay_frame", "extruded_crew_bay_frame"],
            rounding=0.02,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx + width * 0.50 - rim * 0.50, cy + height * 0.14, cz),
            profile_polygon=_chamfered_rect_profile(rim, height * 0.72, rim * 0.20),
            extrude_height=depth,
            axis="z",
            tags=[*list(component.tags), "right_bay_frame", "extruded_crew_bay_frame"],
            rounding=0.02,
        ),
    ]


def _cargo_bay_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    door_t = max(height * 0.12, 0.04)
    return [
        _subdivision_box(component.part, component, tags=[*list(component.tags), "cargo_bay_volume", "subdivision_cargo_bay_volume"], corner_segments=4),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.44, cz + depth * 0.46),
            profile_polygon=_chamfered_rect_profile(width * 0.82, door_t, door_t * 0.22),
            extrude_height=depth * 0.10,
            axis="z",
            tags=[*list(component.tags), "forward_bay_door", "extruded_cargo_bay_door"],
            rounding=0.01,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy - height * 0.44, cz),
            profile_polygon=_chamfered_rect_profile(width * 0.76, door_t, door_t * 0.22),
            extrude_height=depth * 0.82,
            axis="z",
            tags=[*list(component.tags), "underside_access_hatch", "extruded_cargo_hatch"],
            rounding=0.01,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx - width * 0.38, cy, cz),
            profile_polygon=_chamfered_rect_profile(width * 0.07, height * 0.82, width * 0.015),
            extrude_height=depth * 0.86,
            axis="z",
            tags=[*list(component.tags), "left_cargo_rail", "extruded_cargo_rail"],
            rounding=0.01,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx + width * 0.38, cy, cz),
            profile_polygon=_chamfered_rect_profile(width * 0.07, height * 0.82, width * 0.015),
            extrude_height=depth * 0.86,
            axis="z",
            tags=[*list(component.tags), "right_cargo_rail", "extruded_cargo_rail"],
            rounding=0.01,
        ),
    ]


def _thruster_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    radius = component.radius if component.radius is not None else max(min(width, height) * 0.34, 0.045)
    nozzle_depth = component.height if component.height is not None else max(depth, 0.08)
    return [
        _revolved_profile(
            component.part,
            component,
            profile_points=[
                (-nozzle_depth * 0.50, radius * 0.76),
                (-nozzle_depth * 0.22, radius),
                (nozzle_depth * 0.24, radius * 0.88),
                (nozzle_depth * 0.50, radius * 0.58),
            ],
            axis=component.axis,
            tags=[*list(component.tags), "thruster_nozzle", "lathed_thruster_nozzle"],
        ),
        _torus(
            component.part,
            component,
            center=(cx, cy, cz - depth * 0.32 if component.axis == "z" else cz),
            major_radius=radius * 1.04,
            minor_radius=max(radius * 0.16, 0.015),
            axis=component.axis,
            tags=[*list(component.tags), "thrust_ring", "torus_thruster_ring"],
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.38, cz),
            profile_polygon=_chamfered_rect_profile(width * 0.82, max(height * 0.24, 0.04), height * 0.04),
            extrude_height=depth * 0.46,
            axis="z",
            tags=[*list(component.tags), "thruster_mount", "extruded_thruster_mount"],
            rounding=0.02,
        ),
    ]


def _antenna_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    radius = component.radius if component.radius is not None else max(min(width, depth) * 0.18, 0.025)
    mast_height = component.height if component.height is not None else max(height, 0.10)
    return [
        _swept_profile(
            component.part,
            component,
            cross_section=_round_cross_section(radius, 8),
            sweep_path=[(0.0, -mast_height * 0.50, 0.0), (width * 0.02, 0.0, depth * 0.02), (0.0, mast_height * 0.50, 0.0)],
            tags=[*list(component.tags), "antenna_mast", "swept_antenna_mast"],
        ),
        _round_bar(
            component.part,
            component,
            center=(cx, cy + mast_height * 0.48, cz),
            radius=max(radius * 0.38, 0.01),
            height=width,
            axis="x",
            tags=[*list(component.tags), "antenna_crossbar", "swept_antenna_crossbar"],
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy - mast_height * 0.48, cz),
            profile_polygon=_chamfered_rect_profile(width * 0.56, max(radius * 1.20, 0.025), radius * 0.18),
            extrude_height=depth * 0.56,
            axis="z",
            tags=[*list(component.tags), "antenna_base_plate", "extruded_antenna_base_plate"],
            rounding=0.02,
        ),
    ]


def _stabilizer_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    return [
        _extruded_profile(
            component.part,
            component,
            profile_polygon=[
                (-width * 0.50, -height * 0.42),
                (width * 0.46, -height * 0.34),
                (width * 0.50, 0.0),
                (width * 0.28, height * 0.42),
                (-width * 0.48, height * 0.24),
            ],
            extrude_height=depth,
            axis="z",
            tags=[*list(component.tags), "stabilizer_plane", "extruded_stabilizer_plane"],
            rounding=0.03,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.30, cz - depth * 0.24),
            profile_polygon=[
                (-width * 0.14, -height * 0.88),
                (width * 0.14, -height * 0.80),
                (width * 0.06, height * 0.88),
                (-width * 0.10, height * 0.70),
            ],
            extrude_height=depth * 0.22,
            axis="z",
            tags=[*list(component.tags), "vertical_fin", "extruded_vertical_fin"],
            rounding=0.02,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy - height * 0.34, cz),
            profile_polygon=_chamfered_rect_profile(width * 0.82, max(height * 0.18, 0.035), height * 0.04),
            extrude_height=depth * 0.64,
            axis="z",
            tags=[*list(component.tags), "stabilizer_root", "extruded_stabilizer_root"],
            rounding=0.02,
        ),
    ]


def _roof_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    return [
        _extruded_profile(
            component.part,
            component,
            profile_polygon=[
                (-width * 0.50, -height * 0.44),
                (width * 0.50, -height * 0.44),
                (width * 0.36, height * 0.34),
                (0.0, height * 0.52),
                (-width * 0.36, height * 0.34),
            ],
            extrude_height=depth,
            axis="z",
            tags=[*list(component.tags), "roof_mass", "extruded_roof_mass"],
            rounding=0.04,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.42, cz),
            profile_polygon=_chamfered_rect_profile(width * 0.82, height * 0.18, height * 0.04),
            extrude_height=depth * 1.12,
            axis="z",
            tags=[*list(component.tags), "ridge_cap", "extruded_ridge_cap"],
            rounding=0.03,
        ),
    ]


def _roof_ridge_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    return [
        _extruded_profile(
            component.part,
            component,
            profile_polygon=[
                (-width * 0.50, -height * 0.42),
                (width * 0.50, -height * 0.42),
                (0.0, height * 0.52),
            ],
            extrude_height=depth,
            axis="z",
            tags=[*list(component.tags), "ridge_mass", "extruded_ridge_mass"],
            rounding=0.03,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.34, cz),
            profile_polygon=[
                (-width * 0.09, -height * 0.18),
                (width * 0.09, -height * 0.18),
                (0.0, height * 0.20),
            ],
            extrude_height=depth * 1.04,
            axis="z",
            tags=[*list(component.tags), "roof_peak", "extruded_roof_peak"],
            rounding=0.02,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx - width * 0.24, cy + height * 0.10, cz),
            profile_polygon=[
                (-width * 0.24, -height * 0.09),
                (width * 0.24, -height * 0.04),
                (width * 0.18, height * 0.09),
                (-width * 0.24, height * 0.05),
            ],
            extrude_height=depth * 1.08,
            axis="z",
            tags=[*list(component.tags), "left_roof_plane", "extruded_left_roof_plane"],
            rounding=0.02,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx + width * 0.24, cy + height * 0.10, cz),
            profile_polygon=[
                (-width * 0.24, -height * 0.04),
                (width * 0.24, -height * 0.09),
                (width * 0.24, height * 0.05),
                (-width * 0.18, height * 0.09),
            ],
            extrude_height=depth * 1.08,
            axis="z",
            tags=[*list(component.tags), "right_roof_plane", "extruded_right_roof_plane"],
            rounding=0.02,
        ),
    ]


def _dome_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    radius = component.radius if component.radius is not None else min(width, depth) * 0.50
    return [
        _revolved_profile(
            component.part,
            component,
            profile_points=_lathed_cylinder_profile(max(height * 0.32, 0.12), radius, bevel=0.18),
            axis="y",
            center=(component.center[0], component.center[1] - height * 0.22, component.center[2]),
            tags=[*list(component.tags), "dome_base", "lathed_dome_base"],
        ),
        _sphere(
            component.part,
            component,
            radius=radius * 0.72,
            center=(component.center[0], component.center[1] + height * 0.06, component.center[2]),
            tags=[*list(component.tags), "dome_crown"],
        ),
        _sphere(
            component.part,
            component,
            radius=radius * 0.22,
            center=(component.center[0], component.center[1] + height * 0.42, component.center[2]),
            tags=[*list(component.tags), "cupola_cap"],
        ),
    ]


def _window_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    lip = max(min(width, height) * 0.12, 0.18)
    face_depth = max(depth, 0.18)
    return [
        _extruded_profile(
            component.part,
            component,
            profile_polygon=_chamfered_rect_profile(width, height, min(width, height) * 0.04),
            extrude_height=face_depth,
            axis="z",
            tags=[*list(component.tags), "window_frame", "extruded_window_frame"],
            rounding=0.02,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy, cz + depth * 0.08),
            profile_polygon=_chamfered_rect_profile(max(width - lip * 2.0, 0.20), max(height - lip * 2.0, 0.20), lip * 0.18),
            extrude_height=face_depth * 1.08,
            axis="z",
            tags=[*list(component.tags), "feature", "glass_cutout", "extruded_window_glass_cutout"],
            blend_mode="subtract",
            rounding=0.02,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy, cz + depth * 0.20),
            profile_polygon=_chamfered_rect_profile(max(lip * 0.45, 0.10), height * 0.86, lip * 0.08),
            extrude_height=face_depth * 1.12,
            axis="z",
            tags=[*list(component.tags), "feature", "mullion", "extruded_window_mullion"],
            rounding=0.01,
        ),
    ]


def _arch_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    pier_w = max(width * 0.16, 0.10)
    crown_h = max(height * 0.26, 0.12)
    opening_w = max(width - pier_w * 2.0, pier_w)
    crown_radius = opening_w * 0.34
    crown_points = [(-width * 0.50, -crown_h * 0.50), (width * 0.50, -crown_h * 0.50)]
    crown_points.extend(
        (
            math.cos(math.pi * step / 8.0) * crown_radius,
            math.sin(math.pi * step / 8.0) * crown_radius + crown_h * 0.02,
        )
        for step in range(9)
    )
    return [
        _subdivision_box(
            component.part,
            component,
            center=(cx - width * 0.50 + pier_w * 0.50, cy - height * 0.06, cz),
            extents=(pier_w, height * 0.88, depth),
            tags=[*list(component.tags), "left_pier", "subdivision_arch_pier"],
            corner_segments=3,
        ),
        _subdivision_box(
            component.part,
            component,
            center=(cx + width * 0.50 - pier_w * 0.50, cy - height * 0.06, cz),
            extents=(pier_w, height * 0.88, depth),
            tags=[*list(component.tags), "right_pier", "subdivision_arch_pier"],
            corner_segments=3,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.38, cz),
            profile_polygon=crown_points,
            extrude_height=depth,
            axis="z",
            tags=[*list(component.tags), "arch_lintel", "extruded_arch_crown"],
            rounding=0.02,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.25, cz),
            profile_polygon=[
                (math.cos(math.pi * step / 10.0) * opening_w * 0.30, math.sin(math.pi * step / 10.0) * opening_w * 0.30)
                for step in range(11)
            ],
            extrude_height=max(depth * 1.04, 0.08),
            axis="z",
            tags=[*list(component.tags), "rounded_arch_crown", "extruded_arch_opening_cut"],
            blend_mode="subtract",
            rounding=0.01,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy - height * 0.50, cz),
            profile_polygon=_chamfered_rect_profile(width * 1.04, max(height * 0.08, 0.05), height * 0.02),
            extrude_height=depth * 1.08,
            axis="z",
            tags=[*list(component.tags), "arch_threshold", "extruded_arch_threshold"],
            rounding=0.01,
        ),
    ]


def _balcony_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    rail_h = max(height * 1.80, 0.18)
    rail_t = max(min(width, depth) * 0.08, 0.06)
    return [
        _subdivision_box(component.part, component, tags=[*list(component.tags), "balcony_slab", "subdivision_balcony_slab"], corner_segments=4),
        _round_bar(
            component.part,
            component,
            center=(cx, cy + rail_h * 0.52, cz + depth * 0.44),
            radius=rail_t * 0.50,
            height=width,
            axis="x",
            tags=[*list(component.tags), "front_rail", "swept_balcony_rail"],
        ),
        _round_bar(
            component.part,
            component,
            center=(cx - width * 0.46, cy + rail_h * 0.45, cz),
            radius=rail_t * 0.50,
            height=rail_h * 0.86,
            axis="y",
            tags=[*list(component.tags), "left_rail", "swept_balcony_side_rail"],
        ),
        _round_bar(
            component.part,
            component,
            center=(cx + width * 0.46, cy + rail_h * 0.45, cz),
            radius=rail_t * 0.50,
            height=rail_h * 0.86,
            axis="y",
            tags=[*list(component.tags), "right_rail", "swept_balcony_side_rail"],
        ),
    ]


def _awning_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    return [
        _extruded_profile(
            component.part,
            component,
            profile_polygon=[
                (-width * 0.54, -height * 0.22),
                (width * 0.54, -height * 0.22),
                (width * 0.48, height * 0.20),
                (-width * 0.48, height * 0.20),
            ],
            extrude_height=depth,
            axis="z",
            tags=[*list(component.tags), "canopy_slab", "extruded_awning_canopy"],
            rounding=0.02,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy - height * 0.18, cz + depth * 0.34),
            profile_polygon=_chamfered_rect_profile(width * 0.96, max(height * 0.18, 0.06), height * 0.03),
            extrude_height=depth * 0.18,
            axis="z",
            tags=[*list(component.tags), "front_lip", "extruded_awning_lip"],
            rounding=0.02,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.12, cz - depth * 0.38),
            profile_polygon=_chamfered_rect_profile(width * 0.90, max(height * 0.14, 0.05), height * 0.025),
            extrude_height=depth * 0.12,
            axis="z",
            tags=[*list(component.tags), "wall_mount", "extruded_awning_wall_mount"],
            rounding=0.02,
        ),
    ]


def _cornice_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    return [
        _extruded_profile(
            component.part,
            component,
            profile_polygon=_chamfered_rect_profile(width, height, min(height, depth) * 0.12),
            extrude_height=depth,
            axis="z",
            tags=[*list(component.tags), "cornice_band", "extruded_cornice_band"],
            rounding=0.02,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.36, cz + depth * 0.12),
            profile_polygon=_chamfered_rect_profile(width * 1.03, max(height * 0.34, 0.06), height * 0.04),
            extrude_height=depth * 0.72,
            axis="z",
            tags=[*list(component.tags), "upper_lip", "extruded_cornice_lip"],
            rounding=0.02,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy - height * 0.34, cz + depth * 0.18),
            profile_polygon=_chamfered_rect_profile(width * 0.96, max(height * 0.20, 0.05), height * 0.03),
            extrude_height=depth * 0.50,
            axis="z",
            tags=[*list(component.tags), "lower_shadow_line", "extruded_cornice_shadow_line"],
            rounding=0.01,
        ),
    ]


def _parapet_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    wall_t = max(min(width, depth) * 0.055, 0.06)
    cap_h = max(height * 0.22, 0.045)
    return [
        _subdivision_box(
            component.part,
            component,
            center=(cx, cy, cz + depth * 0.50 - wall_t * 0.50),
            extents=(width, height, wall_t),
            tags=[*list(component.tags), "front_parapet_wall", "subdivision_parapet_wall"],
            corner_segments=3,
        ),
        _subdivision_box(
            component.part,
            component,
            center=(cx, cy, cz - depth * 0.50 + wall_t * 0.50),
            extents=(width, height, wall_t),
            tags=[*list(component.tags), "rear_parapet_wall", "subdivision_parapet_wall"],
            corner_segments=3,
        ),
        _subdivision_box(
            component.part,
            component,
            center=(cx - width * 0.50 + wall_t * 0.50, cy, cz),
            extents=(wall_t, height, depth),
            tags=[*list(component.tags), "left_parapet_wall", "subdivision_parapet_wall"],
            corner_segments=3,
        ),
        _subdivision_box(
            component.part,
            component,
            center=(cx + width * 0.50 - wall_t * 0.50, cy, cz),
            extents=(wall_t, height, depth),
            tags=[*list(component.tags), "right_parapet_wall", "subdivision_parapet_wall"],
            corner_segments=3,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.50 + cap_h * 0.50, cz),
            profile_polygon=_chamfered_rect_profile(width * 1.04, cap_h, cap_h * 0.25),
            extrude_height=depth * 1.04,
            axis="z",
            tags=[*list(component.tags), "parapet_cap", "extruded_parapet_cap"],
            rounding=0.02,
        ),
    ]


def _dormer_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    return [
        _subdivision_box(component.part, component, tags=[*list(component.tags), "dormer_body", "subdivision_dormer_body"], corner_segments=4),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.42, cz),
            profile_polygon=[
                (-width * 0.56, -height * 0.10),
                (width * 0.56, -height * 0.10),
                (0.0, height * 0.16),
            ],
            extrude_height=depth * 1.16,
            axis="z",
            tags=[*list(component.tags), "dormer_roof", "extruded_dormer_roof"],
            rounding=0.02,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy - height * 0.04, cz + depth * 0.44),
            profile_polygon=_chamfered_rect_profile(width * 0.52, height * 0.46, min(width, height) * 0.04),
            extrude_height=depth * 0.16,
            axis="z",
            tags=[*list(component.tags), "dormer_window", "extruded_dormer_window"],
            rounding=0.01,
        ),
    ]


def _chimney_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    return [
        _subdivision_box(component.part, component, tags=[*list(component.tags), "chimney_stack", "subdivision_chimney_stack"], corner_segments=3),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.48, cz),
            profile_polygon=_chamfered_rect_profile(width * 1.35, max(height * 0.12, 0.06), height * 0.03),
            extrude_height=depth * 1.35,
            axis="z",
            tags=[*list(component.tags), "chimney_cap", "extruded_chimney_cap"],
            rounding=0.02,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.58, cz),
            profile_polygon=_chamfered_rect_profile(width * 0.52, max(height * 0.08, 0.04), height * 0.02),
            extrude_height=depth * 0.52,
            axis="z",
            tags=[*list(component.tags), "flue_opening", "extruded_flue_opening"],
            rounding=0.01,
        ),
    ]


def _column_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    radius = component.radius if component.radius is not None else max(min(width, depth) * 0.42, 0.18)
    cx, cy, cz = component.center
    return [
        _revolved_profile(
            component.part,
            component,
            profile_points=[
                (-height * 0.50, radius * 0.92),
                (-height * 0.44, radius),
                (height * 0.44, radius * 0.96),
                (height * 0.50, radius * 0.90),
            ],
            axis="y",
            tags=[*list(component.tags), "shaft", "lathed_column_shaft"],
        ),
        _revolved_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.48, cz),
            profile_points=[
                (-max(height * 0.04, 0.08), radius * 0.92),
                (0.0, radius * 1.30),
                (max(height * 0.04, 0.08), radius * 1.05),
            ],
            axis="y",
            tags=[*list(component.tags), "capital", "lathed_column_capital"],
        ),
        _revolved_profile(
            component.part,
            component,
            center=(cx, cy - height * 0.48, cz),
            profile_points=[
                (-max(height * 0.04, 0.08), radius * 1.18),
                (0.0, radius * 1.40),
                (max(height * 0.04, 0.08), radius),
            ],
            axis="y",
            tags=[*list(component.tags), "base", "lathed_column_base"],
        ),
    ]


def _tower_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    cap_h = max(height * 0.09, 0.16)
    return [
        _subdivision_box(component.part, component, tags=[*list(component.tags), "tower_shaft", "subdivision_tower_shaft"], corner_segments=4),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.50 + cap_h * 0.35, cz),
            profile_polygon=_chamfered_rect_profile(width * 1.18, cap_h, cap_h * 0.25),
            extrude_height=depth * 1.18,
            axis="z",
            tags=[*list(component.tags), "tower_cap", "extruded_tower_cap"],
            rounding=0.02,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.28, cz + depth * 0.52),
            profile_polygon=_chamfered_rect_profile(width * 0.42, height * 0.22, min(width, height) * 0.03),
            extrude_height=max(depth * 0.08, 0.06),
            axis="z",
            tags=[*list(component.tags), "tower_window", "extruded_tower_window"],
            rounding=0.01,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy - height * 0.48, cz),
            profile_polygon=_chamfered_rect_profile(width * 1.22, max(height * 0.06, 0.10), height * 0.03),
            extrude_height=depth * 1.22,
            axis="z",
            tags=[*list(component.tags), "tower_base", "extruded_tower_base"],
            rounding=0.02,
        ),
    ]


def _stair_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    count = 6
    step_h = max(height * 0.70 / count, 0.14)
    step_d = max(depth * 0.82 / count, 0.18)
    primitives: list[ShapePrimitive] = []
    for index in range(count):
        primitives.append(
            _extruded_profile(
                component.part,
                component,
                center=(
                    component.center[0],
                    component.center[1] - height * 0.35 + step_h * (index + 0.5),
                    component.center[2] + depth * 0.40 - step_d * (index + 0.5),
                ),
                profile_polygon=_chamfered_rect_profile(width, step_h, step_h * 0.20),
                extrude_height=step_d,
                axis="z",
                tags=[*list(component.tags), "step", "extruded_stair_step", f"step_{index}"],
                rounding=0.02,
            )
        )
    return primitives


def _stair_core_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    primitives = _stair_primitives(component)
    primitives.extend(
        [
            _subdivision_box(
                component.part,
                component,
                center=(component.center[0] - width * 0.46, component.center[1], component.center[2]),
                extents=(max(width * 0.08, 0.06), height * 0.92, depth),
                tags=[*list(component.tags), "left_core_wall", "subdivision_stair_core_wall"],
                corner_segments=3,
            ),
            _subdivision_box(
                component.part,
                component,
                center=(component.center[0] + width * 0.46, component.center[1], component.center[2]),
                extents=(max(width * 0.08, 0.06), height * 0.92, depth),
                tags=[*list(component.tags), "right_core_wall", "subdivision_stair_core_wall"],
                corner_segments=3,
            ),
            _extruded_profile(
                component.part,
                component,
                center=(component.center[0], component.center[1] + height * 0.44, component.center[2]),
                profile_polygon=_chamfered_rect_profile(width, max(height * 0.10, 0.08), height * 0.03),
                extrude_height=depth * 0.92,
                axis="z",
                tags=[*list(component.tags), "landing", "extruded_stair_landing"],
                rounding=0.02,
            ),
        ]
    )
    return primitives


def _chassis_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    return [
        _subdivision_box(
            component.part,
            component,
            tags=[*list(component.tags), "chassis_body", "subdivision_vehicle_body"],
            corner_segments=4,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(component.center[0], component.center[1] - height * 0.35, component.center[2]),
            profile_polygon=_chamfered_rect_profile(width * 0.88, height * 0.30, height * 0.05),
            extrude_height=depth * 1.08,
            axis="z",
            tags=[*list(component.tags), "underframe", "extruded_underframe"],
            rounding=0.03,
        ),
    ]


def _cabin_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    return [
        _subdivision_box(
            component.part,
            component,
            tags=[*list(component.tags), "cabin_body", "subdivision_cabin_body"],
            corner_segments=4,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(component.center[0], component.center[1] + height * 0.08, component.center[2] + depth * 0.46),
            profile_polygon=_chamfered_rect_profile(width * 0.68, height * 0.42, height * 0.06),
            extrude_height=depth * 0.16,
            axis="z",
            tags=[*list(component.tags), "feature", "windshield", "extruded_windshield_panel"],
            rounding=0.02,
        ),
    ]


def _wheel_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    radius = component.radius if component.radius is not None else max(min(height, depth) * 0.48, 0.20)
    wheel_height = component.height if component.height is not None else max(width, 0.20)
    return [
        _torus(
            component.part,
            component,
            major_radius=radius * 0.70,
            minor_radius=max(radius * 0.30, wheel_height * 0.18),
            axis="x",
            tags=[*list(component.tags), "tire", "wheel_rim_torus"],
        ),
        _revolved_profile(
            component.part,
            component,
            profile_points=_lathed_cylinder_profile(wheel_height * 1.12, radius * 0.45, bevel=0.16),
            axis="x",
            tags=[*list(component.tags), "hub", "lathed_wheel_hub"],
        ),
    ]


def _hull_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    return [
        _subdivision_box(
            component.part,
            component,
            corner_radii=(
                max(min(width, height, depth) * 0.08, 0.001),
                max(min(width, height, depth) * 0.18, 0.001),
                max(min(width, height, depth) * 0.12, 0.001),
                max(min(width, height, depth) * 0.22, 0.001),
                max(min(width, height, depth) * 0.10, 0.001),
                max(min(width, height, depth) * 0.20, 0.001),
                max(min(width, height, depth) * 0.14, 0.001),
                max(min(width, height, depth) * 0.24, 0.001),
            ),
            tags=[*list(component.tags), "hull_mass", "subdivision_hull_mass"],
            corner_segments=4,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy - height * 0.34, cz),
            profile_polygon=[
                (-width * 0.26, -height * 0.17),
                (width * 0.26, -height * 0.17),
                (width * 0.18, height * 0.12),
                (0.0, height * 0.17),
                (-width * 0.18, height * 0.12),
            ],
            extrude_height=depth * 1.08,
            axis="z",
            tags=[*list(component.tags), "keel", "extruded_keel"],
            rounding=0.03,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.12, cz + depth * 0.48),
            profile_polygon=[
                (-width * 0.38, -height * 0.10),
                (width * 0.30, -height * 0.08),
                (width * 0.38, 0.0),
                (width * 0.22, height * 0.10),
                (-width * 0.34, height * 0.08),
            ],
            extrude_height=depth * 0.18,
            axis="z",
            tags=[*list(component.tags), "bow", "extruded_bow_plate"],
            rounding=0.02,
        ),
    ]


def _deck_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    return [
        _subdivision_box(
            component.part,
            component,
            tags=[*list(component.tags), "deck_mass", "subdivision_deck_mass"],
            corner_segments=3,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(component.center[0], component.center[1] + height * 0.32, component.center[2]),
            profile_polygon=_chamfered_rect_profile(width * 0.82, height * 0.16, height * 0.04),
            extrude_height=depth * 0.82,
            axis="z",
            tags=[*list(component.tags), "raised_deck", "extruded_raised_deck"],
            rounding=0.03,
        ),
    ]


def _mast_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    radius = component.radius if component.radius is not None else max(min(component.extents[0], component.extents[2]) * 0.24, 0.12)
    height = component.height if component.height is not None else component.extents[1]
    width, _, depth = component.extents
    return [
        _swept_profile(
            component.part,
            component,
            cross_section=_round_cross_section(radius, 10),
            sweep_path=[(0.0, -height * 0.50, 0.0), (radius * 0.10, 0.0, 0.0), (0.0, height * 0.50, 0.0)],
            tags=[*list(component.tags), "mast", "swept_mast"],
        ),
        _round_bar(
            component.part,
            component,
            center=(component.center[0], component.center[1] + height * 0.16, component.center[2]),
            radius=max(radius * 0.38, 0.02),
            height=max(width, radius * 7.0),
            axis="x",
            tags=[*list(component.tags), "crossbar", "swept_mast_crossbar"],
        ),
    ]


def _engine_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    radius = component.radius if component.radius is not None else max(min(width, height) * 0.32, 0.18)
    return [
        _revolved_profile(
            component.part,
            component,
            profile_points=[
                (-depth * 0.50, radius * 0.82),
                (-depth * 0.32, radius),
                (depth * 0.22, radius * 0.92),
                (depth * 0.50, radius * 0.70),
            ],
            axis="z",
            tags=[*list(component.tags), "engine_core", "lathed_engine_core"],
        ),
        _extruded_profile(
            component.part,
            component,
            center=(component.center[0], component.center[1], component.center[2] - depth * 0.48),
            profile_polygon=_chamfered_rect_profile(radius * 2.4, radius * 1.5, radius * 0.20),
            extrude_height=max(depth * 0.18, 0.20),
            axis="z",
            tags=[*list(component.tags), "mount", "extruded_engine_mount"],
            rounding=0.02,
        ),
    ]


def _pontoon_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    radius = component.radius if component.radius is not None else max(min(width, height) * 0.48, 0.08)
    pontoon_length = component.height if component.height is not None else depth
    return [
        _swept_profile(
            component.part,
            component,
            cross_section=_round_cross_section(radius, 10),
            sweep_path=[(0.0, 0.0, -pontoon_length * 0.50), (0.0, height * 0.03, 0.0), (0.0, 0.0, pontoon_length * 0.50)],
            tags=[*list(component.tags), "float_body", "swept_pontoon_float"],
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.34, cz),
            profile_polygon=_chamfered_rect_profile(width * 0.82, max(height * 0.16, 0.05), height * 0.03),
            extrude_height=depth * 0.86,
            axis="z",
            tags=[*list(component.tags), "top_sponson", "extruded_pontoon_sponson"],
            rounding=0.02,
        ),
        _revolved_profile(
            component.part,
            component,
            center=(cx, cy, cz + depth * 0.50),
            profile_points=[(-max(depth * 0.04, 0.03), radius * 0.40), (0.0, radius * 0.68), (max(depth * 0.04, 0.03), radius * 0.12)],
            axis="z",
            tags=[*list(component.tags), "bow_cap", "lathed_pontoon_cap"],
        ),
        _revolved_profile(
            component.part,
            component,
            center=(cx, cy, cz - depth * 0.50),
            profile_points=[(-max(depth * 0.04, 0.03), radius * 0.12), (0.0, radius * 0.68), (max(depth * 0.04, 0.03), radius * 0.40)],
            axis="z",
            tags=[*list(component.tags), "stern_cap", "lathed_pontoon_cap"],
        ),
    ]


def _outrigger_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    side_sign = -1.0 if "port" in component.tags or "left" in component.tags else 1.0
    radius = component.radius if component.radius is not None else max(height * 0.52, 0.05)
    float_length = component.height if component.height is not None else depth * 0.92
    return [
        _round_bar(
            component.part,
            component,
            center=(cx - side_sign * width * 0.28, cy + height * 0.22, cz),
            radius=max(min(height, depth) * 0.055, 0.025),
            height=width * 0.72,
            axis="x",
            tags=[*list(component.tags), "crossbeam", "swept_outrigger_crossbeam"],
        ),
        _swept_profile(
            component.part,
            component,
            center=(cx + side_sign * width * 0.18, cy - height * 0.22, cz),
            cross_section=_round_cross_section(radius, 10),
            sweep_path=[(0.0, 0.0, -float_length * 0.50), (side_sign * width * 0.02, height * 0.02, 0.0), (0.0, 0.0, float_length * 0.50)],
            tags=[*list(component.tags), "outrigger_float", "swept_outrigger_float"],
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx + side_sign * width * 0.18, cy + height * 0.08, cz),
            profile_polygon=_chamfered_rect_profile(width * 0.18, max(height * 0.18, 0.04), height * 0.025),
            extrude_height=depth * 0.78,
            axis="z",
            tags=[*list(component.tags), "float_strake", "extruded_outrigger_strake"],
            rounding=0.01,
        ),
    ]


def _sail_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    batten_height = max(height * 0.035, 0.04)
    return [
        _extruded_profile(
            component.part,
            component,
            profile_polygon=[
                (-width * 0.48, -height * 0.50),
                (width * 0.42, -height * 0.36),
                (width * 0.32, height * 0.50),
                (-width * 0.44, height * 0.42),
            ],
            extrude_height=max(depth * 0.18, 0.035),
            axis="z",
            tags=[*list(component.tags), "cloth_panel", "extruded_sail_cloth_panel"],
            rounding=0.01,
        ),
        _round_bar(
            component.part,
            component,
            center=(cx - width * 0.46, cy, cz),
            radius=max(width * 0.025, 0.02),
            height=height * 1.04,
            axis="y",
            tags=[*list(component.tags), "luff_sleeve", "swept_sail_luff_sleeve"],
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.22, cz),
            profile_polygon=_chamfered_rect_profile(width * 0.88, batten_height, batten_height * 0.22),
            extrude_height=max(depth * 0.22, 0.04),
            axis="z",
            tags=[*list(component.tags), "upper_batten", "extruded_sail_batten"],
            rounding=0.01,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy - height * 0.22, cz),
            profile_polygon=_chamfered_rect_profile(width * 0.82, batten_height, batten_height * 0.22),
            extrude_height=max(depth * 0.22, 0.04),
            axis="z",
            tags=[*list(component.tags), "lower_batten", "extruded_sail_batten"],
            rounding=0.01,
        ),
    ]


def _rigging_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    wire = max(min(width, depth) * 0.42, 0.025)
    return [
        _swept_profile(
            component.part,
            component,
            cross_section=_round_cross_section(wire * 0.50, 7),
            sweep_path=[(0.0, -height * 0.50, 0.0), (width * 0.03, 0.0, depth * 0.02), (0.0, height * 0.50, 0.0)],
            tags=[*list(component.tags), "standing_line", "swept_rigging_line"],
        ),
        _round_bar(
            component.part,
            component,
            center=(cx, cy - height * 0.40, cz),
            radius=wire * 0.50,
            height=width * 2.2,
            axis="x",
            tags=[*list(component.tags), "deck_tie", "swept_rigging_deck_tie"],
        ),
        _swept_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.12, cz),
            cross_section=_round_cross_section(wire * 0.50, 7),
            sweep_path=[(0.0, -max(height * 0.27, wire), -depth * 0.50), (0.0, 0.0, 0.0), (0.0, max(height * 0.27, wire), depth * 0.50)],
            tags=[*list(component.tags), "fore_aft_stay", "swept_rigging_stay"],
        ),
    ]


def _cargo_hold_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    rim = max(min(width, depth) * 0.09, 0.04)
    return [
        _subdivision_box(
            component.part,
            component,
            center=(cx, cy - height * 0.12, cz),
            extents=(width * 0.88, max(height * 0.36, 0.05), depth * 0.82),
            tags=[*list(component.tags), "recessed_hold", "subdivision_cargo_hold_recess"],
            corner_segments=3,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx - width * 0.50 + rim * 0.50, cy + height * 0.32, cz),
            profile_polygon=_chamfered_rect_profile(rim, max(height * 0.18, 0.04), rim * 0.20),
            extrude_height=depth,
            axis="z",
            tags=[*list(component.tags), "port_rim", "extruded_cargo_hold_rim"],
            rounding=0.01,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx + width * 0.50 - rim * 0.50, cy + height * 0.32, cz),
            profile_polygon=_chamfered_rect_profile(rim, max(height * 0.18, 0.04), rim * 0.20),
            extrude_height=depth,
            axis="z",
            tags=[*list(component.tags), "starboard_rim", "extruded_cargo_hold_rim"],
            rounding=0.01,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.34, cz - depth * 0.50 + rim * 0.50),
            profile_polygon=_chamfered_rect_profile(width, max(height * 0.18, 0.04), height * 0.03),
            extrude_height=rim,
            axis="z",
            tags=[*list(component.tags), "aft_rim", "extruded_cargo_hold_rim"],
            rounding=0.01,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.34, cz + depth * 0.50 - rim * 0.50),
            profile_polygon=_chamfered_rect_profile(width, max(height * 0.18, 0.04), height * 0.03),
            extrude_height=rim,
            axis="z",
            tags=[*list(component.tags), "fore_rim", "extruded_cargo_hold_rim"],
            rounding=0.01,
        ),
    ]


def _rudder_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    radius = component.radius if component.radius is not None else max(width * 0.16, 0.04)
    shaft_height = component.height if component.height is not None else height
    return [
        _round_bar(
            component.part,
            component,
            center=(cx, cy + height * 0.10, cz - depth * 0.26),
            radius=radius,
            height=shaft_height,
            axis="y",
            tags=[*list(component.tags), "rudder_post", "swept_rudder_post"],
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy - height * 0.14, cz + depth * 0.12),
            profile_polygon=[
                (-width * 0.42, -height * 0.38),
                (width * 0.46, -height * 0.28),
                (width * 0.34, height * 0.38),
                (-width * 0.36, height * 0.30),
            ],
            extrude_height=max(depth * 0.36, 0.05),
            axis="z",
            tags=[*list(component.tags), "rudder_blade", "extruded_rudder_blade"],
            rounding=0.02,
        ),
    ]


def _propeller_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    radius = component.radius if component.radius is not None else max(min(component.extents[0], component.extents[1]) * 0.45, 0.06)
    height = component.height if component.height is not None else max(component.extents[2], 0.04)
    cx, cy, cz = component.center
    blade_thickness = max(radius * 0.20, 0.025)
    return [
        _revolved_profile(
            component.part,
            component,
            profile_points=[
                (-height * 0.50, radius * 0.22),
                (0.0, radius * 0.34),
                (height * 0.50, radius * 0.22),
            ],
            axis="z",
            tags=[*list(component.tags), "prop_hub", "lathed_prop_hub"],
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy, cz),
            profile_polygon=[
                (-radius * 1.05, -blade_thickness * 0.42),
                (0.0, -blade_thickness * 0.24),
                (radius * 1.05, blade_thickness * 0.42),
                (0.0, blade_thickness * 0.24),
            ],
            extrude_height=height * 0.54,
            axis="z",
            tags=[*list(component.tags), "horizontal_blades", "extruded_prop_blade"],
            rounding=0.01,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy, cz),
            profile_polygon=[
                (-blade_thickness * 0.42, -radius * 1.05),
                (blade_thickness * 0.42, 0.0),
                (blade_thickness * 0.24, radius * 1.05),
                (-blade_thickness * 0.24, 0.0),
            ],
            extrude_height=height * 0.54,
            axis="z",
            tags=[*list(component.tags), "vertical_blades", "extruded_prop_blade"],
            rounding=0.01,
        ),
        _subdivision_box(
            component.part,
            component,
            center=(cx, cy, cz + height * 0.04),
            extents=(radius * 1.15, radius * 1.15, max(height * 0.30, 0.025)),
            tags=[*list(component.tags), "skewed_blade_mass", "subdivision_prop_blade_mass"],
            corner_segments=3,
        ),
    ]


def _anchor_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    ring_radius = component.radius if component.radius is not None else max(width * 0.18, 0.04)
    return [
        _torus(
            component.part,
            component,
            center=(cx, cy + height * 0.44, cz),
            major_radius=ring_radius,
            minor_radius=max(depth * 0.10, 0.012),
            axis="z",
            tags=[*list(component.tags), "anchor_ring", "torus_anchor_ring"],
        ),
        _round_bar(
            component.part,
            component,
            center=(cx, cy, cz),
            radius=max(min(width, depth) * 0.08, 0.018),
            height=height,
            axis="y",
            tags=[*list(component.tags), "anchor_shank", "swept_anchor_shank"],
        ),
        _round_bar(
            component.part,
            component,
            center=(cx, cy - height * 0.38, cz),
            radius=max(height * 0.055, 0.018),
            height=width,
            axis="x",
            tags=[*list(component.tags), "anchor_stock", "swept_anchor_stock"],
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx - width * 0.36, cy - height * 0.48, cz),
            profile_polygon=[
                (-width * 0.15, -height * 0.10),
                (width * 0.12, -height * 0.08),
                (width * 0.15, height * 0.12),
                (-width * 0.05, height * 0.10),
            ],
            extrude_height=max(depth * 0.54, 0.04),
            axis="z",
            tags=[*list(component.tags), "port_fluke", "extruded_anchor_fluke"],
            rounding=0.01,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx + width * 0.36, cy - height * 0.48, cz),
            profile_polygon=[
                (-width * 0.12, -height * 0.08),
                (width * 0.15, -height * 0.10),
                (width * 0.05, height * 0.10),
                (-width * 0.15, height * 0.12),
            ],
            extrude_height=max(depth * 0.54, 0.04),
            axis="z",
            tags=[*list(component.tags), "starboard_fluke", "extruded_anchor_fluke"],
            rounding=0.01,
        ),
    ]


def _track_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    shoe_count = 6
    spacing = depth / max(1, shoe_count)
    start_z = cz - depth * 0.50 + spacing * 0.50
    primitives = [
        _subdivision_box(
            component.part,
            component,
            tags=[*list(component.tags), "track_belt", "subdivision_track_belt"],
            corner_segments=4,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.34, cz),
            profile_polygon=_chamfered_rect_profile(width * 0.72, max(height * 0.16, 0.06), height * 0.04),
            extrude_height=depth * 0.92,
            axis="z",
            tags=[*list(component.tags), "upper_run", "extruded_track_upper_run"],
            rounding=0.02,
        ),
    ]
    for index in range(shoe_count):
        primitives.append(
            _extruded_profile(
                component.part,
                component,
                center=(cx, cy - height * 0.34, start_z + spacing * index),
                profile_polygon=_chamfered_rect_profile(width * 1.08, max(height * 0.18, 0.06), height * 0.04),
                extrude_height=spacing * 0.62,
                axis="z",
                tags=[*list(component.tags), "track_shoe", "extruded_track_shoe", f"shoe_{index}"],
                rounding=0.02,
            )
        )
    return primitives


def _suspension_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    radius = max(min(height, depth) * 0.34, 0.04)
    return [
        _round_bar(component.part, component, radius=radius, height=width, axis="x", tags=[*list(component.tags), "axle_bar", "swept_suspension_axle"]),
        _swept_profile(
            component.part,
            component,
            center=(cx - width * 0.36, cy + height * 0.20, cz),
            cross_section=_round_cross_section(max(min(width, depth) * 0.045, 0.018), 8),
            sweep_path=[(0.0, -height * 0.70, 0.0), (width * 0.04, 0.0, depth * 0.06), (0.0, height * 0.70, 0.0)],
            tags=[*list(component.tags), "left_strut", "swept_suspension_strut"],
        ),
        _swept_profile(
            component.part,
            component,
            center=(cx + width * 0.36, cy + height * 0.20, cz),
            cross_section=_round_cross_section(max(min(width, depth) * 0.045, 0.018), 8),
            sweep_path=[(0.0, -height * 0.70, 0.0), (-width * 0.04, 0.0, depth * 0.06), (0.0, height * 0.70, 0.0)],
            tags=[*list(component.tags), "right_strut", "swept_suspension_strut"],
        ),
    ]


def _cargo_module_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    return [
        _subdivision_box(component.part, component, tags=[*list(component.tags), "cargo_shell", "subdivision_cargo_shell"], corner_segments=4),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.42, cz),
            profile_polygon=_chamfered_rect_profile(width * 0.88, max(height * 0.14, 0.06), height * 0.03),
            extrude_height=depth * 0.88,
            axis="z",
            tags=[*list(component.tags), "cargo_lid", "extruded_cargo_lid"],
            rounding=0.02,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy, cz + depth * 0.50),
            profile_polygon=_chamfered_rect_profile(width * 0.64, height * 0.42, min(width, height) * 0.04),
            extrude_height=max(depth * 0.08, 0.06),
            axis="z",
            tags=[*list(component.tags), "cargo_hatch", "extruded_cargo_hatch"],
            rounding=0.02,
        ),
    ]


def _turret_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    radius = component.radius if component.radius is not None else min(width, depth) * 0.48
    return [
        _torus(
            component.part,
            component,
            major_radius=radius * 0.72,
            minor_radius=max(radius * 0.18, height * 0.035, 0.018),
            axis="y",
            tags=[*list(component.tags), "turret_ring", "torus_turret_ring"],
        ),
        _subdivision_box(
            component.part,
            component,
            center=(component.center[0], component.center[1] + height * 0.30, component.center[2]),
            extents=(width, max(height * 0.42, 0.12), depth),
            tags=[*list(component.tags), "turret_housing", "subdivision_turret_housing"],
            corner_segments=4,
        ),
        _round_bar(
            component.part,
            component,
            radius=max(min(width, depth) * 0.12, 0.05),
            height=max(depth * 1.25, 0.18),
            axis="z",
            center=(component.center[0], component.center[1] + height * 0.36, component.center[2] + depth * 0.66),
            tags=[*list(component.tags), "turret_barrel", "swept_turret_barrel"],
        ),
    ]


def _wing_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    return [
        _extruded_profile(
            component.part,
            component,
            profile_polygon=[
                (-width * 0.50, -height * 0.42),
                (width * 0.46, -height * 0.28),
                (width * 0.50, 0.0),
                (width * 0.28, height * 0.42),
                (-width * 0.48, height * 0.24),
            ],
            extrude_height=depth,
            axis="z",
            tags=[*list(component.tags), "wing_plane", "extruded_wing_plane"],
            rounding=0.03,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(component.center[0], component.center[1] + height * 0.34, component.center[2] - depth * 0.30),
            profile_polygon=_chamfered_rect_profile(width * 0.82, max(height * 0.24, 0.05), height * 0.04),
            extrude_height=depth * 0.18,
            axis="z",
            tags=[*list(component.tags), "leading_edge", "extruded_wing_leading_edge"],
            rounding=0.02,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(component.center[0], component.center[1] - height * 0.18, component.center[2] + depth * 0.36),
            profile_polygon=_chamfered_rect_profile(width * 0.66, max(height * 0.18, 0.04), height * 0.03),
            extrude_height=depth * 0.12,
            axis="z",
            tags=[*list(component.tags), "control_surface", "extruded_wing_control_surface"],
            rounding=0.02,
        ),
    ]


def _manipulator_arm_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    return [
        _subdivision_box(component.part, component, tags=[*list(component.tags), "upper_arm", "subdivision_manipulator_arm"], corner_segments=4),
        _revolved_profile(
            component.part,
            component,
            center=(cx, cy - height * 0.46, cz - depth * 0.36),
            profile_points=[
                (-depth * 0.09, height * 0.28),
                (0.0, height * 0.36),
                (depth * 0.09, height * 0.28),
            ],
            axis="z",
            tags=[*list(component.tags), "shoulder_joint", "lathed_manipulator_shoulder_joint"],
        ),
        _revolved_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.22, cz + depth * 0.40),
            profile_points=[
                (-depth * 0.09, height * 0.24),
                (0.0, height * 0.40),
                (depth * 0.09, height * 0.24),
            ],
            axis="z",
            tags=[*list(component.tags), "wrist_joint", "lathed_manipulator_wrist_joint"],
        ),
    ]


def _machine_base_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    return [
        _subdivision_box(component.part, component, tags=[*list(component.tags), "machine_plinth", "subdivision_machine_plinth"], corner_segments=4),
        _extruded_profile(
            component.part,
            component,
            center=(component.center[0], component.center[1] + height * 0.42, component.center[2]),
            profile_polygon=_chamfered_rect_profile(width * 0.84, max(height * 0.18, 0.08), height * 0.04),
            extrude_height=depth * 0.84,
            axis="z",
            tags=[*list(component.tags), "mounting_plate", "extruded_machine_mounting_plate"],
            rounding=0.02,
        ),
    ]


def _machine_column_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    radius = max(min(width, depth) * 0.42, 0.08)
    return [
        _revolved_profile(
            component.part,
            component,
            profile_points=[
                (-height * 0.50, radius * 0.86),
                (-height * 0.42, radius),
                (height * 0.36, radius * 0.92),
                (height * 0.50, radius * 0.72),
            ],
            axis="y",
            tags=[*list(component.tags), "column_core", "lathed_machine_column_core"],
        ),
        _extruded_profile(
            component.part,
            component,
            center=(component.center[0], component.center[1] - height * 0.46, component.center[2]),
            profile_polygon=_chamfered_rect_profile(width * 1.50, max(height * 0.10, 0.08), height * 0.04),
            extrude_height=depth * 1.50,
            axis="z",
            tags=[*list(component.tags), "column_foot", "extruded_machine_column_foot"],
            rounding=0.02,
        ),
    ]


def _hydraulic_piston_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    radius = component.radius if component.radius is not None else max(min(component.extents[0], component.extents[2]) * 0.36, 0.05)
    height = component.height if component.height is not None else component.extents[1]
    return [
        _revolved_profile(
            component.part,
            component,
            profile_points=[
                (-height * 0.50, radius * 0.92),
                (-height * 0.42, radius),
                (height * 0.42, radius),
                (height * 0.50, radius * 0.92),
            ],
            axis=component.axis,
            tags=[*list(component.tags), "piston_body", "lathed_piston_body"],
        ),
        _revolved_profile(
            component.part,
            component,
            profile_points=[
                (-height * 0.59, radius * 0.40),
                (0.0, radius * 0.48),
                (height * 0.59, radius * 0.40),
            ],
            axis=component.axis,
            tags=[*list(component.tags), "chrome_rod", "lathed_chrome_rod"],
        ),
    ]


def _conveyor_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    roller_count = 4
    spacing = width / max(1, roller_count - 1)
    start_x = cx - width * 0.50
    primitives = [
        _subdivision_box(component.part, component, tags=[*list(component.tags), "belt", "subdivision_conveyor_belt"], corner_segments=4)
    ]
    for index in range(roller_count):
        primitives.append(
            _revolved_profile(
                component.part,
                component,
                center=(start_x + spacing * index, cy + height * 0.18, cz),
                profile_points=[
                    (-depth * 0.52, max(height * 0.20, 0.04)),
                    (-depth * 0.44, max(height * 0.24, 0.05)),
                    (depth * 0.44, max(height * 0.24, 0.05)),
                    (depth * 0.52, max(height * 0.20, 0.04)),
                ],
                axis="z",
                tags=[*list(component.tags), "roller", "lathed_conveyor_roller", f"roller_{index}"],
            )
        )
    return primitives


def _gear_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    radius = component.radius if component.radius is not None else max(min(component.extents[0], component.extents[1]) * 0.48, 0.08)
    height = component.height if component.height is not None else max(component.extents[2], 0.06)
    primitives = [
        _revolved_profile(
            component.part,
            component,
            profile_points=[
                (-height * 0.50, radius * 0.82),
                (-height * 0.38, radius),
                (height * 0.38, radius),
                (height * 0.50, radius * 0.82),
            ],
            axis=component.axis,
            tags=[*list(component.tags), "gear_disc", "lathed_gear_disc"],
        ),
        _revolved_profile(
            component.part,
            component,
            profile_points=[
                (-height * 0.58, radius * 0.26),
                (0.0, radius * 0.34),
                (height * 0.58, radius * 0.26),
            ],
            axis=component.axis,
            tags=[*list(component.tags), "gear_hub", "lathed_gear_hub"],
        ),
    ]
    for index in range(8):
        angle = math.tau * index / 8.0
        primitives.append(
            _extruded_profile(
                component.part,
                component,
                center=(
                    component.center[0],
                    component.center[1] + math.sin(angle) * radius * 0.86,
                    component.center[2] + math.cos(angle) * radius * 0.86,
                ),
                profile_polygon=[
                    (-height * 0.54, -radius * 0.10),
                    (height * 0.54, -radius * 0.08),
                    (height * 0.42, radius * 0.11),
                    (-height * 0.42, radius * 0.08),
                ],
                extrude_height=radius * 0.16,
                axis="z",
                tags=[*list(component.tags), "gear_tooth", "extruded_gear_tooth", f"tooth_{index}"],
                rounding=0.01,
            )
        )
    return primitives


def _tank_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    radius = component.radius if component.radius is not None else max(min(component.extents[0], component.extents[2]) * 0.45, 0.10)
    height = component.height if component.height is not None else component.extents[1]
    return [
        _revolved_profile(
            component.part,
            component,
            profile_points=[
                (-height * 0.50, radius * 0.78),
                (-height * 0.38, radius),
                (height * 0.38, radius),
                (height * 0.50, radius * 0.78),
            ],
            axis=component.axis,
            tags=[*list(component.tags), "tank_body", "lathed_tank_body"],
        ),
        _revolved_profile(
            component.part,
            component,
            center=(component.center[0], component.center[1] + height * 0.48, component.center[2]),
            profile_points=[
                (-max(height * 0.04, 0.03), radius * 0.48),
                (0.0, radius * 0.62),
                (max(height * 0.04, 0.03), radius * 0.50),
            ],
            axis=component.axis,
            tags=[*list(component.tags), "access_hatch", "lathed_tank_access_hatch"],
        ),
    ]


def _crane_boom_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    beam_radius = max(min(height, depth) * 0.055, 0.025)
    return [
        _subdivision_box(component.part, component, tags=[*list(component.tags), "boom_beam", "subdivision_crane_boom"], corner_segments=3),
        _swept_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.18, cz),
            cross_section=_round_cross_section(beam_radius, 7),
            sweep_path=[(-width * 0.48, 0.0, -depth * 0.34), (0.0, height * 0.16, 0.0), (width * 0.48, 0.0, depth * 0.34)],
            tags=[*list(component.tags), "diagonal_truss_a", "swept_crane_truss"],
        ),
        _swept_profile(
            component.part,
            component,
            center=(cx, cy - height * 0.02, cz),
            cross_section=_round_cross_section(beam_radius, 7),
            sweep_path=[(-width * 0.48, 0.0, depth * 0.34), (0.0, height * 0.16, 0.0), (width * 0.48, 0.0, -depth * 0.34)],
            tags=[*list(component.tags), "diagonal_truss_b", "swept_crane_truss"],
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy - height * 0.48, cz + depth * 0.46),
            profile_polygon=_chamfered_rect_profile(width * 0.70, height * 0.42, height * 0.05),
            extrude_height=depth * 0.10,
            axis="z",
            tags=[*list(component.tags), "hook_mount", "extruded_crane_hook_mount"],
            rounding=0.02,
        ),
    ]


def _road_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    shoulder = max(width * 0.09, 0.20)
    marker_width = max(width * 0.018, 0.08)
    return [
        _subdivision_box(component.part, component, tags=[*list(component.tags), "road_surface", "subdivision_road_surface"], corner_segments=3),
        _extruded_profile(
            component.part,
            component,
            center=(cx - width * 0.50 + shoulder * 0.50, cy + height * 0.36, cz),
            profile_polygon=_chamfered_rect_profile(shoulder, height * 0.42, height * 0.05),
            extrude_height=depth * 1.02,
            axis="z",
            tags=[*list(component.tags), "shoulder", "left", "extruded_road_shoulder"],
            rounding=0.02,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx + width * 0.50 - shoulder * 0.50, cy + height * 0.36, cz),
            profile_polygon=_chamfered_rect_profile(shoulder, height * 0.42, height * 0.05),
            extrude_height=depth * 1.02,
            axis="z",
            tags=[*list(component.tags), "shoulder", "right", "extruded_road_shoulder"],
            rounding=0.02,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.56, cz),
            profile_polygon=_chamfered_rect_profile(marker_width, max(height * 0.10, 0.05), marker_width * 0.25),
            extrude_height=depth * 0.92,
            axis="z",
            tags=[*list(component.tags), "lane_marker", "center", "extruded_lane_marker"],
            rounding=0.01,
        ),
    ]


def _road_junction_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    marker_h = max(height * 0.12, 0.04)
    return [
        _subdivision_box(component.part, component, tags=[*list(component.tags), "junction_plate", "subdivision_road_junction"], corner_segments=3),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.44, cz),
            profile_polygon=_chamfered_rect_profile(width * 0.18, marker_h, marker_h * 0.25),
            extrude_height=depth * 0.84,
            axis="z",
            tags=[*list(component.tags), "junction_lane_marker", "north_south", "extruded_junction_marker"],
            rounding=0.01,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.45, cz),
            profile_polygon=_chamfered_rect_profile(width * 0.84, marker_h, marker_h * 0.25),
            extrude_height=depth * 0.18,
            axis="z",
            tags=[*list(component.tags), "junction_lane_marker", "east_west", "extruded_junction_marker"],
            rounding=0.01,
        ),
        _subdivision_box(
            component.part,
            component,
            center=(cx - width * 0.40, cy + height * 0.30, cz - depth * 0.40),
            extents=(width * 0.18, height * 0.28, depth * 0.18),
            tags=[*list(component.tags), "corner_apron", "southwest", "subdivision_corner_apron"],
            corner_segments=3,
        ),
        _subdivision_box(
            component.part,
            component,
            center=(cx + width * 0.40, cy + height * 0.30, cz + depth * 0.40),
            extents=(width * 0.18, height * 0.28, depth * 0.18),
            tags=[*list(component.tags), "corner_apron", "northeast", "subdivision_corner_apron"],
            corner_segments=3,
        ),
    ]


def _crosswalk_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    stripe_count = 5
    stripe_w = width / (stripe_count * 2.0 - 1.0)
    start_x = cx - width * 0.50 + stripe_w * 0.50
    primitives = [
        _subdivision_box(
            component.part,
            component,
            extents=(width, max(height * 0.30, 0.025), depth),
            tags=[*list(component.tags), "crosswalk_base", "subdivision_crosswalk_base"],
            corner_segments=3,
        )
    ]
    for index in range(stripe_count):
        primitives.append(
            _extruded_profile(
                component.part,
                component,
                center=(start_x + index * stripe_w * 2.0, cy + height * 0.42, cz),
                profile_polygon=_chamfered_rect_profile(stripe_w, max(height, 0.035), stripe_w * 0.08),
                extrude_height=depth,
                axis="z",
                tags=[*list(component.tags), "crosswalk_stripe", "extruded_crosswalk_stripe", f"stripe_{index}"],
                rounding=0.01,
            )
        )
    return primitives


def _turnout_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    return [
        _subdivision_box(component.part, component, tags=[*list(component.tags), "turnout_pad", "subdivision_turnout_pad"], corner_segments=4),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.44, cz - depth * 0.36),
            profile_polygon=_chamfered_rect_profile(width * 0.80, max(height * 0.12, 0.035), height * 0.02),
            extrude_height=depth * 0.08,
            axis="z",
            tags=[*list(component.tags), "turnout_entry_mark", "extruded_turnout_mark"],
            rounding=0.01,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.44, cz + depth * 0.36),
            profile_polygon=_chamfered_rect_profile(width * 0.80, max(height * 0.12, 0.035), height * 0.02),
            extrude_height=depth * 0.08,
            axis="z",
            tags=[*list(component.tags), "turnout_exit_mark", "extruded_turnout_mark"],
            rounding=0.01,
        ),
    ]


def _roundabout_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    radius = component.radius if component.radius is not None else min(width, depth) * 0.32
    return [
        _subdivision_box(component.part, component, tags=[*list(component.tags), "roundabout_pad", "subdivision_roundabout_pad"], corner_segments=5),
        _revolved_profile(
            component.part,
            component,
            profile_points=_lathed_cylinder_profile(component.height if component.height is not None else height, radius, bevel=0.18),
            axis="y",
            tags=[*list(component.tags), "traffic_island", "lathed_traffic_island"],
        ),
        _torus(
            component.part,
            component,
            major_radius=radius * 1.28,
            minor_radius=max(height * 0.10, 0.018),
            center=(component.center[0], component.center[1] + height * 0.48, component.center[2]),
            axis="y",
            tags=[*list(component.tags), "painted_ring", "torus_roundabout_painted_ring"],
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.52, cz),
            profile_polygon=_chamfered_rect_profile(radius * 1.20, max(height * 0.08, 0.025), height * 0.015),
            extrude_height=radius * 0.16,
            axis="z",
            tags=[*list(component.tags), "entry_yield_mark", "extruded_roundabout_yield_mark"],
            rounding=0.01,
        ),
    ]


def _median_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    cap_h = max(height * 0.20, 0.035)
    return [
        _subdivision_box(component.part, component, tags=[*list(component.tags), "raised_median", "subdivision_raised_median"], corner_segments=4),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.54, cz - depth * 0.34),
            profile_polygon=[
                (-width * 0.50, -cap_h * 0.50),
                (width * 0.50, -cap_h * 0.50),
                (width * 0.59, cap_h * 0.50),
                (-width * 0.40, cap_h * 0.50),
            ],
            extrude_height=depth * 0.10,
            axis="z",
            tags=[*list(component.tags), "median_nose_a", "extruded_median_nose"],
            rounding=0.02,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.54, cz + depth * 0.34),
            profile_polygon=[
                (-width * 0.59, -cap_h * 0.50),
                (width * 0.40, -cap_h * 0.50),
                (width * 0.50, cap_h * 0.50),
                (-width * 0.50, cap_h * 0.50),
            ],
            extrude_height=depth * 0.10,
            axis="z",
            tags=[*list(component.tags), "median_nose_b", "extruded_median_nose"],
            rounding=0.02,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.58, cz),
            profile_polygon=_chamfered_rect_profile(width * 0.46, cap_h, cap_h * 0.20),
            extrude_height=depth * 0.82,
            axis="z",
            tags=[*list(component.tags), "median_painted_spine", "extruded_median_spine"],
            rounding=0.01,
        ),
    ]


def _curb_ramp_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    cheek_w = max(width * 0.12, 0.05)
    return [
        _subdivision_box(component.part, component, tags=[*list(component.tags), "ramp_slab", "subdivision_curb_ramp"], corner_segments=3),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.42, cz + depth * 0.36),
            profile_polygon=_chamfered_rect_profile(width * 0.88, max(height * 0.18, 0.025), height * 0.03),
            extrude_height=depth * 0.12,
            axis="z",
            tags=[*list(component.tags), "tactile_strip", "extruded_tactile_strip"],
            rounding=0.01,
        ),
        _subdivision_box(
            component.part,
            component,
            center=(cx - width * 0.50 + cheek_w * 0.50, cy + height * 0.24, cz),
            extents=(cheek_w, height * 0.68, depth),
            tags=[*list(component.tags), "left_ramp_cheek", "subdivision_ramp_cheek"],
            corner_segments=3,
        ),
        _subdivision_box(
            component.part,
            component,
            center=(cx + width * 0.50 - cheek_w * 0.50, cy + height * 0.24, cz),
            extents=(cheek_w, height * 0.68, depth),
            tags=[*list(component.tags), "right_ramp_cheek", "subdivision_ramp_cheek"],
            corner_segments=3,
        ),
    ]


def _lane_arrow_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    stripe_h = max(height, 0.025)
    return [
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy, cz - depth * 0.10),
            profile_polygon=_chamfered_rect_profile(width * 0.20, stripe_h, stripe_h * 0.25),
            extrude_height=depth * 0.70,
            axis="z",
            tags=[*list(component.tags), "arrow_shaft", "extruded_lane_arrow"],
            rounding=0.01,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy, cz + depth * 0.34),
            profile_polygon=[
                (-width * 0.34, -stripe_h * 0.50),
                (width * 0.34, -stripe_h * 0.50),
                (0.0, stripe_h * 0.50),
            ],
            extrude_height=depth * 0.18,
            axis="z",
            tags=[*list(component.tags), "arrow_head_bar", "extruded_lane_arrow_head"],
            rounding=0.01,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx - width * 0.18, cy, cz + depth * 0.24),
            profile_polygon=_chamfered_rect_profile(width * 0.18, stripe_h, stripe_h * 0.20),
            extrude_height=depth * 0.26,
            axis="z",
            tags=[*list(component.tags), "arrow_head_left", "extruded_lane_arrow_head"],
            rounding=0.01,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx + width * 0.18, cy, cz + depth * 0.24),
            profile_polygon=_chamfered_rect_profile(width * 0.18, stripe_h, stripe_h * 0.20),
            extrude_height=depth * 0.26,
            axis="z",
            tags=[*list(component.tags), "arrow_head_right", "extruded_lane_arrow_head"],
            rounding=0.01,
        ),
    ]


def _stop_line_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    stripe_h = max(height, 0.025)
    return [
        _extruded_profile(
            component.part,
            component,
            profile_polygon=_chamfered_rect_profile(width, stripe_h, stripe_h * 0.15),
            extrude_height=depth,
            axis="z",
            tags=[*list(component.tags), "stop_bar_primary", "extruded_stop_bar"],
            rounding=0.01,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + stripe_h * 0.20, cz + depth * 0.34),
            profile_polygon=_chamfered_rect_profile(width, stripe_h, stripe_h * 0.15),
            extrude_height=max(depth * 0.18, 0.035),
            axis="z",
            tags=[*list(component.tags), "advance_stop_bar", "extruded_stop_bar"],
            rounding=0.01,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + stripe_h * 0.22, cz - depth * 0.34),
            profile_polygon=_chamfered_rect_profile(width * 0.82, stripe_h, stripe_h * 0.15),
            extrude_height=max(depth * 0.12, 0.03),
            axis="z",
            tags=[*list(component.tags), "yield_bar", "extruded_yield_bar"],
            rounding=0.01,
        ),
    ]


def _bridge_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    girder_h = max(height * 0.28, 0.20)
    return [
        _subdivision_box(component.part, component, tags=[*list(component.tags), "bridge_deck", "subdivision_bridge_deck"], corner_segments=3),
        _extruded_profile(
            component.part,
            component,
            center=(cx - width * 0.34, cy - height * 0.46, cz),
            profile_polygon=_chamfered_rect_profile(width * 0.10, girder_h, width * 0.02),
            extrude_height=depth * 1.04,
            axis="z",
            tags=[*list(component.tags), "underside_girder", "left", "extruded_bridge_girder"],
            rounding=0.02,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx + width * 0.34, cy - height * 0.46, cz),
            profile_polygon=_chamfered_rect_profile(width * 0.10, girder_h, width * 0.02),
            extrude_height=depth * 1.04,
            axis="z",
            tags=[*list(component.tags), "underside_girder", "right", "extruded_bridge_girder"],
            rounding=0.02,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy - height * 0.36, cz),
            profile_polygon=_chamfered_rect_profile(width * 0.52, max(height * 0.14, 0.12), height * 0.03),
            extrude_height=depth * 0.90,
            axis="z",
            tags=[*list(component.tags), "spine", "extruded_bridge_spine"],
            rounding=0.02,
        ),
    ]


def _railing_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    post_count = 4
    spacing = depth / max(1, post_count - 1)
    start_z = cz - depth * 0.50
    primitives = [
        _round_bar(
            component.part,
            component,
            center=(cx, cy + height * 0.42, cz),
            radius=max(height * 0.06, 0.035),
            height=depth,
            axis="z",
            tags=[*list(component.tags), "top_rail", "swept_railing_top_rail"],
        )
    ]
    for index in range(post_count):
        primitives.append(
            _round_bar(
                component.part,
                component,
                center=(cx, cy, start_z + spacing * index),
                radius=max(width * 0.10, 0.035),
                height=height,
                axis="y",
                tags=[*list(component.tags), "post", "swept_railing_post", f"post_{index}"],
            )
        )
    return primitives


def _terrain_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    return [
        _subdivision_box(component.part, component, tags=[*list(component.tags), "terrain_mass", "subdivision_terrain_mass"], corner_segments=3),
        _subdivision_box(
            component.part,
            component,
            center=(cx - width * 0.18, cy + height * 0.35, cz - depth * 0.16),
            extents=(width * 0.52, height * 0.38, depth * 0.48),
            tags=[*list(component.tags), "plateau", "subdivision_plateau"],
            corner_segments=3,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx + width * 0.24, cy + height * 0.22, cz + depth * 0.20),
            profile_polygon=[
                (-width * 0.16, -height * 0.12),
                (width * 0.16, -height * 0.08),
                (width * 0.02, height * 0.12),
                (-width * 0.14, height * 0.06),
            ],
            extrude_height=depth * 0.58,
            axis="z",
            tags=[*list(component.tags), "ridge", "extruded_terrain_ridge"],
            rounding=0.02,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy - height * 0.20, cz + depth * 0.42),
            profile_polygon=[
                (-width * 0.35, -height * 0.10),
                (width * 0.35, -height * 0.12),
                (width * 0.30, height * 0.12),
                (-width * 0.28, height * 0.08),
            ],
            extrude_height=depth * 0.16,
            axis="z",
            tags=[*list(component.tags), "cliff_face", "extruded_cliff_face"],
            rounding=0.02,
        ),
    ]


def _terrain_ridge_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    cap = max(width * 0.28, 0.12)
    return [
        _subdivision_box(component.part, component, tags=[*list(component.tags), "feature", "ridge_mass", "subdivision_ridge_mass"], corner_segments=3),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.36, cz),
            profile_polygon=[
                (-width * 0.31, -height * 0.14),
                (width * 0.31, -height * 0.14),
                (width * 0.12, height * 0.17),
                (-width * 0.16, height * 0.16),
            ],
            extrude_height=depth * 1.04,
            axis="z",
            tags=[*list(component.tags), "feature", "ridge_spine", "raised_ridge", "extruded_ridge_spine"],
            rounding=0.02,
        ),
        _subdivision_box(
            component.part,
            component,
            center=(cx - width * 0.42, cy - height * 0.10, cz),
            extents=(cap, height * 0.42, depth * 0.94),
            tags=[*list(component.tags), "feature", "ridge_slope", "left", "subdivision_ridge_slope"],
            corner_segments=3,
        ),
        _subdivision_box(
            component.part,
            component,
            center=(cx + width * 0.42, cy - height * 0.10, cz),
            extents=(cap, height * 0.42, depth * 0.94),
            tags=[*list(component.tags), "feature", "ridge_slope", "right", "subdivision_ridge_slope"],
            corner_segments=3,
        ),
    ]


def _terrain_cliff_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    shelf_h = max(height * 0.10, 0.08)
    return [
        _subdivision_box(component.part, component, tags=[*list(component.tags), "feature", "cliff_mass", "subdivision_cliff_mass"], corner_segments=3),
        _extruded_profile(
            component.part,
            component,
            center=(cx - width * 0.18, cy + height * 0.28, cz),
            profile_polygon=_chamfered_rect_profile(width * 0.40, shelf_h, shelf_h * 0.25),
            extrude_height=depth * 0.92,
            axis="z",
            tags=[*list(component.tags), "feature", "cliff_shelf", "upper", "extruded_cliff_shelf"],
            rounding=0.02,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx + width * 0.20, cy - height * 0.08, cz - depth * 0.12),
            profile_polygon=_chamfered_rect_profile(width * 0.36, shelf_h, shelf_h * 0.25),
            extrude_height=depth * 0.74,
            axis="z",
            tags=[*list(component.tags), "feature", "cliff_shelf", "middle", "extruded_cliff_shelf"],
            rounding=0.02,
        ),
        _subdivision_box(
            component.part,
            component,
            center=(cx, cy - height * 0.46, cz + depth * 0.34),
            extents=(width * 0.74, height * 0.14, depth * 0.24),
            tags=[*list(component.tags), "feature", "talus_foot", "subdivision_talus_foot"],
            corner_segments=3,
        ),
    ]


def _terrain_clearing_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    rim_w = max(min(width, depth) * 0.08, 0.08)
    return [
        _subdivision_box(component.part, component, tags=[*list(component.tags), "feature", "clearing_floor", "subdivision_clearing_floor"], corner_segments=3),
        _subdivision_box(
            component.part,
            component,
            center=(cx - width * 0.50 + rim_w * 0.50, cy + height * 0.60, cz),
            extents=(rim_w, height * 0.70, depth),
            tags=[*list(component.tags), "feature", "clearing_rim", "left", "subdivision_clearing_rim"],
            corner_segments=3,
        ),
        _subdivision_box(
            component.part,
            component,
            center=(cx + width * 0.50 - rim_w * 0.50, cy + height * 0.60, cz),
            extents=(rim_w, height * 0.70, depth),
            tags=[*list(component.tags), "feature", "clearing_rim", "right", "subdivision_clearing_rim"],
            corner_segments=3,
        ),
        _subdivision_box(
            component.part,
            component,
            center=(cx, cy + height * 0.58, cz - depth * 0.50 + rim_w * 0.50),
            extents=(width, height * 0.60, rim_w),
            tags=[*list(component.tags), "feature", "clearing_rim", "near", "subdivision_clearing_rim"],
            corner_segments=3,
        ),
        _subdivision_box(
            component.part,
            component,
            center=(cx, cy + height * 0.58, cz + depth * 0.50 - rim_w * 0.50),
            extents=(width, height * 0.60, rim_w),
            tags=[*list(component.tags), "feature", "clearing_rim", "far", "subdivision_clearing_rim"],
            corner_segments=3,
        ),
    ]


def _terrain_platform_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    skirt_h = max(height * 0.28, 0.10)
    return [
        _subdivision_box(component.part, component, tags=[*list(component.tags), "feature", "platform_mass", "subdivision_terrain_platform"], corner_segments=4),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.46, cz),
            profile_polygon=_chamfered_rect_profile(width * 0.86, height * 0.18, height * 0.04),
            extrude_height=depth * 0.86,
            axis="z",
            tags=[*list(component.tags), "feature", "platform_cap", "extruded_platform_cap"],
            rounding=0.02,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy - height * 0.44, cz - depth * 0.46),
            profile_polygon=_chamfered_rect_profile(width * 0.72, skirt_h, skirt_h * 0.18),
            extrude_height=depth * 0.12,
            axis="z",
            tags=[*list(component.tags), "feature", "platform_skirt", "front", "extruded_platform_skirt"],
            rounding=0.02,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy - height * 0.44, cz + depth * 0.46),
            profile_polygon=_chamfered_rect_profile(width * 0.72, skirt_h, skirt_h * 0.18),
            extrude_height=depth * 0.12,
            axis="z",
            tags=[*list(component.tags), "feature", "platform_skirt", "rear", "extruded_platform_skirt"],
            rounding=0.02,
        ),
    ]


def _terrain_water_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    rim = max(min(width, depth) * 0.08, 0.08)
    return [
        _subdivision_box(
            component.part,
            component,
            center=(cx, cy - height * 0.18, cz),
            extents=(width, max(height * 0.35, 0.05), depth),
            tags=[*list(component.tags), "feature", "water_basin", "subdivision_water_basin"],
            corner_segments=4,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.30, cz),
            profile_polygon=_chamfered_rect_profile(width * 0.82, max(height * 0.16, 0.04), height * 0.03),
            extrude_height=depth * 0.82,
            axis="z",
            tags=[*list(component.tags), "feature", "water_surface", "extruded_water_surface"],
            rounding=0.02,
        ),
        _subdivision_box(
            component.part,
            component,
            center=(cx - width * 0.50 + rim * 0.50, cy + height * 0.12, cz),
            extents=(rim, height * 0.42, depth),
            tags=[*list(component.tags), "feature", "water_rim", "left", "subdivision_water_rim"],
            corner_segments=3,
        ),
        _subdivision_box(
            component.part,
            component,
            center=(cx + width * 0.50 - rim * 0.50, cy + height * 0.12, cz),
            extents=(rim, height * 0.42, depth),
            tags=[*list(component.tags), "feature", "water_rim", "right", "subdivision_water_rim"],
            corner_segments=3,
        ),
    ]


def _room_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    wall_t = max(min(width, depth) * 0.045, 0.18)
    floor_h = max(height * 0.06, 0.12)
    return [
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy - height * 0.50 + floor_h * 0.50, cz),
            profile_polygon=_chamfered_rect_profile(width, floor_h, floor_h * 0.20),
            extrude_height=depth,
            axis="z",
            tags=[*list(component.tags), "floor", "extruded_room_floor"],
            rounding=0.02,
        ),
        _subdivision_box(
            component.part,
            component,
            center=(cx, cy, cz - depth * 0.50 + wall_t * 0.50),
            extents=(width, height, wall_t),
            tags=[*list(component.tags), "back_wall", "subdivision_room_wall"],
            corner_segments=3,
        ),
        _subdivision_box(
            component.part,
            component,
            center=(cx - width * 0.50 + wall_t * 0.50, cy, cz),
            extents=(wall_t, height, depth),
            tags=[*list(component.tags), "left_wall", "subdivision_room_wall"],
            corner_segments=3,
        ),
        _subdivision_box(
            component.part,
            component,
            center=(cx + width * 0.50 - wall_t * 0.50, cy, cz),
            extents=(wall_t, height, depth),
            tags=[*list(component.tags), "right_wall", "subdivision_room_wall"],
            corner_segments=3,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.50 - floor_h * 0.50, cz),
            profile_polygon=_chamfered_rect_profile(width, floor_h, floor_h * 0.20),
            extrude_height=depth,
            axis="z",
            tags=[*list(component.tags), "ceiling_trim", "extruded_ceiling_trim"],
            rounding=0.02,
        ),
    ]


def _room_cell_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    return [
        _subdivision_box(component.part, component, tags=[*list(component.tags), "room_floor_zone", "subdivision_room_cell"], corner_segments=3),
        _extruded_profile(
            component.part,
            component,
            center=(component.center[0], component.center[1] + height * 0.42, component.center[2]),
            profile_polygon=_chamfered_rect_profile(width * 0.94, max(height * 0.10, 0.05), height * 0.03),
            extrude_height=depth * 0.94,
            axis="z",
            tags=[*list(component.tags), "room_zone_trim", "extruded_room_zone_trim"],
            rounding=0.02,
        ),
    ]


def _corridor_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    horizontal = width >= depth
    rail_t = max(min(width, depth) * 0.05, 0.05)
    edge_a_center = (cx, cy + height * 0.34, cz - depth * 0.48) if horizontal else (cx - width * 0.48, cy + height * 0.34, cz)
    edge_b_center = (cx, cy + height * 0.34, cz + depth * 0.48) if horizontal else (cx + width * 0.48, cy + height * 0.34, cz)
    edge_extents = (width, max(height * 0.12, 0.05), rail_t) if horizontal else (rail_t, max(height * 0.12, 0.05), depth)
    return [
        _subdivision_box(component.part, component, tags=[*list(component.tags), "corridor_floor", "subdivision_corridor_floor"], corner_segments=3),
        _extruded_profile(
            component.part,
            component,
            center=edge_a_center,
            profile_polygon=_chamfered_rect_profile(edge_extents[0], edge_extents[1], edge_extents[1] * 0.25),
            extrude_height=edge_extents[2],
            axis="z",
            tags=[*list(component.tags), "corridor_edge_a", "extruded_corridor_edge"],
            rounding=0.02,
        ),
        _extruded_profile(
            component.part,
            component,
            center=edge_b_center,
            profile_polygon=_chamfered_rect_profile(edge_extents[0], edge_extents[1], edge_extents[1] * 0.25),
            extrude_height=edge_extents[2],
            axis="z",
            tags=[*list(component.tags), "corridor_edge_b", "extruded_corridor_edge"],
            rounding=0.02,
        ),
    ]


def _partition_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    return [
        _subdivision_box(component.part, component, tags=[*list(component.tags), "partition_wall", "subdivision_partition_wall"], corner_segments=3),
        _extruded_profile(
            component.part,
            component,
            center=(component.center[0], component.center[1] + height * 0.42, component.center[2]),
            profile_polygon=_chamfered_rect_profile(width, max(height * 0.10, 0.07), height * 0.03),
            extrude_height=depth,
            axis="z",
            tags=[*list(component.tags), "partition_lintel", "extruded_partition_lintel"],
            rounding=0.02,
        ),
    ]


def _ceiling_light_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    radius = min(width, depth) * 0.42
    return [
        _revolved_profile(
            component.part,
            component,
            profile_points=_lathed_cylinder_profile(max(height, 0.05), radius, bevel=0.20),
            axis="y",
            tags=[*list(component.tags), "light_disc", "emissive", "lathed_ceiling_light_disc"],
        ),
        _revolved_profile(
            component.part,
            component,
            profile_points=_lathed_cylinder_profile(max(height * 1.20, 0.06), radius * 0.62, bevel=0.16),
            axis="y",
            center=(component.center[0], component.center[1] - height * 0.40, component.center[2]),
            tags=[*list(component.tags), "glow_core", "emissive", "lathed_ceiling_light_core"],
        ),
    ]


def _alcove_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    side_t = max(width * 0.12, 0.06)
    return [
        _subdivision_box(component.part, component, tags=[*list(component.tags), "alcove_back", "subdivision_alcove_back"], corner_segments=3),
        _subdivision_box(
            component.part,
            component,
            center=(cx - width * 0.46, cy, cz),
            extents=(side_t, height, depth),
            tags=[*list(component.tags), "alcove_left_return", "subdivision_alcove_return"],
            corner_segments=3,
        ),
        _subdivision_box(
            component.part,
            component,
            center=(cx + width * 0.46, cy, cz),
            extents=(side_t, height, depth),
            tags=[*list(component.tags), "alcove_right_return", "subdivision_alcove_return"],
            corner_segments=3,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy - height * 0.42, cz + depth * 0.18),
            profile_polygon=_chamfered_rect_profile(width, max(height * 0.10, 0.06), height * 0.03),
            extrude_height=depth * 0.70,
            axis="z",
            tags=[*list(component.tags), "alcove_sill", "extruded_alcove_sill"],
            rounding=0.02,
        ),
    ]


def _furniture_base_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    return [
        _subdivision_box(
            component.part,
            component,
            tags=[*list(component.tags), "floor_footprint", "subdivision_furniture_base"],
            corner_segments=4,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(component.center[0], component.center[1] + height * 0.34, component.center[2]),
            profile_polygon=_chamfered_rect_profile(width * 0.94, max(height * 0.18, 0.04), height * 0.04),
            extrude_height=depth * 0.94,
            axis="z",
            tags=[*list(component.tags), "layout_trim", "extruded_furniture_trim"],
            rounding=0.03,
        ),
    ]


def _chair_seat_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    cushion_h = max(height * 0.38, 0.05)
    return [
        _subdivision_box(component.part, component, tags=[*list(component.tags), "seat_board", "subdivision_chair_seat"], corner_segments=4),
        _subdivision_box(
            component.part,
            component,
            center=(cx, cy + height * 0.38, cz),
            extents=(width * 0.92, cushion_h, depth * 0.88),
            tags=[*list(component.tags), "seat_cushion", "subdivision_seat_cushion"],
            corner_segments=5,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy - height * 0.38, cz),
            profile_polygon=_chamfered_rect_profile(width * 0.80, max(height * 0.18, 0.04), height * 0.04),
            extrude_height=depth * 0.78,
            axis="z",
            tags=[*list(component.tags), "underseat_frame", "extruded_underseat_frame"],
            rounding=0.02,
        ),
    ]


def _chair_back_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    rail_h = max(height * 0.08, 0.05)
    side_w = max(width * 0.08, 0.04)
    return [
        _subdivision_box(component.part, component, tags=[*list(component.tags), "back_panel", "subdivision_chair_back"], corner_segments=4),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.44, cz),
            profile_polygon=_chamfered_rect_profile(width * 1.04, rail_h, rail_h * 0.25),
            extrude_height=depth * 1.18,
            axis="z",
            tags=[*list(component.tags), "top_rail", "extruded_chair_top_rail"],
            rounding=0.02,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx - width * 0.45, cy, cz),
            profile_polygon=_chamfered_rect_profile(side_w, height * 1.02, side_w * 0.25),
            extrude_height=depth * 1.12,
            axis="z",
            tags=[*list(component.tags), "left_stile", "extruded_chair_stile"],
            rounding=0.02,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx + width * 0.45, cy, cz),
            profile_polygon=_chamfered_rect_profile(side_w, height * 1.02, side_w * 0.25),
            extrude_height=depth * 1.12,
            axis="z",
            tags=[*list(component.tags), "right_stile", "extruded_chair_stile"],
            rounding=0.02,
        ),
    ]


def _furniture_leg_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    radius = component.radius if component.radius is not None else max(min(component.extents[0], component.extents[2]) * 0.45, 0.035)
    height = component.height if component.height is not None else component.extents[1]
    return [
        _revolved_profile(
            component.part,
            component,
            profile_points=[
                (-height * 0.50, radius * 1.05),
                (-height * 0.30, radius * 0.76),
                (height * 0.30, radius * 0.68),
                (height * 0.50, radius * 0.96),
            ],
            axis="y",
            tags=[*list(component.tags), "leg_post", "lathed_furniture_leg"],
        ),
        _extruded_profile(
            component.part,
            component,
            center=(component.center[0], component.center[1] - height * 0.50, component.center[2]),
            profile_polygon=_chamfered_rect_profile(radius * 2.6, max(height * 0.06, 0.035), radius * 0.35),
            extrude_height=radius * 2.6,
            axis="z",
            tags=[*list(component.tags), "floor_pad", "extruded_leg_floor_pad"],
            rounding=0.02,
        ),
    ]


def _table_top_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    return [
        _subdivision_box(component.part, component, tags=[*list(component.tags), "top_slab", "subdivision_table_top"], corner_segments=4),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy - height * 0.46, cz),
            profile_polygon=_chamfered_rect_profile(width * 0.86, max(height * 0.24, 0.05), height * 0.05),
            extrude_height=depth * 0.86,
            axis="z",
            tags=[*list(component.tags), "apron_frame", "extruded_table_apron"],
            rounding=0.02,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.54, cz),
            profile_polygon=_chamfered_rect_profile(width * 0.94, max(height * 0.12, 0.04), height * 0.04),
            extrude_height=depth * 0.94,
            axis="z",
            tags=[*list(component.tags), "surface_inset", "extruded_table_surface_inset"],
            rounding=0.02,
        ),
    ]


def _bed_frame_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    rail = max(min(width, depth) * 0.08, 0.05)
    return [
        _subdivision_box(component.part, component, tags=[*list(component.tags), "bed_platform", "subdivision_bed_platform"], corner_segments=4),
        _extruded_profile(
            component.part,
            component,
            center=(cx - width * 0.50 + rail * 0.50, cy + height * 0.22, cz),
            profile_polygon=_chamfered_rect_profile(rail, height * 0.52, rail * 0.25),
            extrude_height=depth,
            axis="z",
            tags=[*list(component.tags), "left_side_rail", "extruded_bed_side_rail"],
            rounding=0.02,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx + width * 0.50 - rail * 0.50, cy + height * 0.22, cz),
            profile_polygon=_chamfered_rect_profile(rail, height * 0.52, rail * 0.25),
            extrude_height=depth,
            axis="z",
            tags=[*list(component.tags), "right_side_rail", "extruded_bed_side_rail"],
            rounding=0.02,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.22, cz - depth * 0.50 + rail * 0.50),
            profile_polygon=_chamfered_rect_profile(width, height * 0.52, rail * 0.25),
            extrude_height=rail,
            axis="z",
            tags=[*list(component.tags), "head_rail", "extruded_bed_head_rail"],
            rounding=0.02,
        ),
    ]


def _shelf_unit_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    side_w = max(width * 0.08, 0.04)
    shelf_h = max(height * 0.055, 0.04)
    primitives = [
        _extruded_profile(
            component.part,
            component,
            center=(cx - width * 0.50 + side_w * 0.50, cy, cz),
            profile_polygon=_chamfered_rect_profile(side_w, height, side_w * 0.25),
            extrude_height=depth,
            axis="z",
            tags=[*list(component.tags), "left_side", "extruded_shelf_side"],
            rounding=0.02,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx + width * 0.50 - side_w * 0.50, cy, cz),
            profile_polygon=_chamfered_rect_profile(side_w, height, side_w * 0.25),
            extrude_height=depth,
            axis="z",
            tags=[*list(component.tags), "right_side", "extruded_shelf_side"],
            rounding=0.02,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.50 - shelf_h * 0.50, cz),
            profile_polygon=_chamfered_rect_profile(width, shelf_h, shelf_h * 0.25),
            extrude_height=depth,
            axis="z",
            tags=[*list(component.tags), "top_cap", "extruded_shelf_cap"],
            rounding=0.02,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy - height * 0.50 + shelf_h * 0.50, cz),
            profile_polygon=_chamfered_rect_profile(width, shelf_h, shelf_h * 0.25),
            extrude_height=depth,
            axis="z",
            tags=[*list(component.tags), "bottom_cap", "extruded_shelf_cap"],
            rounding=0.02,
        ),
    ]
    for index, offset in enumerate((-0.25, 0.0, 0.25)):
        primitives.append(
            _extruded_profile(
                component.part,
                component,
                center=(cx, cy + height * offset, cz),
                profile_polygon=_chamfered_rect_profile(width * 0.90, shelf_h, shelf_h * 0.25),
                extrude_height=depth * 0.94,
                axis="z",
                tags=[*list(component.tags), "shelf_board", "extruded_shelf_board", f"shelf_{index}"],
                rounding=0.02,
            )
        )
    return primitives


def _cabinet_body_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    return [
        _subdivision_box(component.part, component, tags=[*list(component.tags), "cabinet_case", "subdivision_cabinet_case"], corner_segments=4),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy, cz + depth * 0.50),
            profile_polygon=_chamfered_rect_profile(width * 0.88, height * 0.84, min(width, height) * 0.04),
            extrude_height=max(depth * 0.08, 0.05),
            axis="z",
            tags=[*list(component.tags), "front_face", "extruded_cabinet_front"],
            rounding=0.02,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx - width * 0.12, cy, cz + depth * 0.54),
            profile_polygon=_chamfered_rect_profile(max(width * 0.04, 0.035), height * 0.78, width * 0.01),
            extrude_height=max(depth * 0.05, 0.035),
            axis="z",
            tags=[*list(component.tags), "left_door", "extruded_cabinet_door"],
            rounding=0.01,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx + width * 0.12, cy, cz + depth * 0.54),
            profile_polygon=_chamfered_rect_profile(max(width * 0.04, 0.035), height * 0.78, width * 0.01),
            extrude_height=max(depth * 0.05, 0.035),
            axis="z",
            tags=[*list(component.tags), "right_door", "extruded_cabinet_door"],
            rounding=0.01,
        ),
    ]


def _drawer_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    return [
        _extruded_profile(
            component.part,
            component,
            profile_polygon=_chamfered_rect_profile(width, height, min(width, height) * 0.04),
            extrude_height=depth,
            axis="z",
            tags=[*list(component.tags), "drawer_front", "extruded_drawer_front"],
            rounding=0.02,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy, cz + depth * 0.26),
            profile_polygon=_chamfered_rect_profile(width * 0.34, max(height * 0.26, 0.035), height * 0.05),
            extrude_height=max(depth * 0.35, 0.035),
            axis="z",
            tags=[*list(component.tags), "drawer_pull", "extruded_drawer_pull"],
            rounding=0.02,
        ),
    ]


def _cushion_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    seam_h = max(height * 0.14, 0.035)
    return [
        _subdivision_box(component.part, component, tags=[*list(component.tags), "soft_volume", "subdivision_cushion_volume"], corner_segments=5),
        _subdivision_box(
            component.part,
            component,
            center=(cx, cy + height * 0.42, cz),
            extents=(width * 0.88, seam_h, depth * 0.88),
            tags=[*list(component.tags), "puffed_top", "subdivision_puffed_cushion_top"],
            corner_segments=5,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy, cz + depth * 0.48),
            profile_polygon=_chamfered_rect_profile(width * 0.92, height * 0.24, height * 0.04),
            extrude_height=seam_h,
            axis="z",
            tags=[*list(component.tags), "front_seam", "extruded_cushion_seam"],
            rounding=0.02,
        ),
    ]


def _counter_top_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    return [
        _subdivision_box(component.part, component, tags=[*list(component.tags), "counter_slab", "subdivision_counter_top"], corner_segments=4),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.34, cz + depth * 0.28),
            profile_polygon=_chamfered_rect_profile(width * 0.72, max(height * 0.16, 0.04), height * 0.04),
            extrude_height=depth * 0.18,
            axis="z",
            tags=[*list(component.tags), "work_surface_inset", "extruded_counter_inset"],
            rounding=0.02,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.32, cz - depth * 0.38),
            profile_polygon=_chamfered_rect_profile(width, max(height * 0.18, 0.05), height * 0.04),
            extrude_height=max(depth * 0.08, 0.04),
            axis="z",
            tags=[*list(component.tags), "backsplash", "extruded_backsplash"],
            rounding=0.02,
        ),
    ]


def _appliance_body_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    return [
        _subdivision_box(component.part, component, tags=[*list(component.tags), "appliance_case", "subdivision_appliance_case"], corner_segments=4),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.12, cz + depth * 0.52),
            profile_polygon=_chamfered_rect_profile(width * 0.78, height * 0.34, min(width, height) * 0.04),
            extrude_height=max(depth * 0.08, 0.04),
            axis="z",
            tags=[*list(component.tags), "front_door", "extruded_appliance_front_door"],
            rounding=0.02,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.40, cz + depth * 0.56),
            profile_polygon=_chamfered_rect_profile(width * 0.52, height * 0.12, height * 0.03),
            extrude_height=max(depth * 0.06, 0.035),
            axis="z",
            tags=[*list(component.tags), "control_panel", "extruded_appliance_control_panel"],
            rounding=0.01,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx + width * 0.42, cy + height * 0.08, cz),
            profile_polygon=_chamfered_rect_profile(max(width * 0.06, 0.04), height * 0.70, width * 0.01),
            extrude_height=depth * 0.82,
            axis="z",
            tags=[*list(component.tags), "side_vent", "extruded_appliance_side_vent"],
            rounding=0.01,
        ),
    ]


def _lamp_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    radius = component.radius if component.radius is not None else max(min(width, depth) * 0.28, 0.05)
    lamp_h = component.height if component.height is not None else height
    return [
        _revolved_profile(
            component.part,
            component,
            center=(cx, cy - lamp_h * 0.42, cz),
            profile_points=[
                (-max(lamp_h * 0.04, 0.025), radius * 0.84),
                (0.0, radius * 1.25),
                (max(lamp_h * 0.04, 0.025), radius * 0.92),
            ],
            axis="y",
            tags=[*list(component.tags), "lamp_base", "lathed_lamp_base"],
        ),
        _round_bar(
            component.part,
            component,
            center=(cx, cy - lamp_h * 0.10, cz),
            radius=radius * 0.30,
            height=lamp_h * 0.60,
            axis="y",
            tags=[*list(component.tags), "lamp_stem", "swept_lamp_stem"],
        ),
        _revolved_profile(
            component.part,
            component,
            center=(cx, cy + lamp_h * 0.28, cz),
            profile_points=[
                (-max(lamp_h * 0.11, 0.04), radius * 1.55),
                (-max(lamp_h * 0.05, 0.02), radius * 1.42),
                (max(lamp_h * 0.07, 0.03), radius * 1.06),
                (max(lamp_h * 0.11, 0.04), radius * 0.92),
            ],
            axis="y",
            tags=[*list(component.tags), "shade", "emissive", "lathed_lamp_shade"],
        ),
        _revolved_profile(
            component.part,
            component,
            center=(cx, cy + lamp_h * 0.22, cz),
            profile_points=_lathed_cylinder_profile(max(lamp_h * 0.08, 0.05), radius * 0.68, bevel=0.18),
            axis="y",
            tags=[*list(component.tags), "glow_core", "emissive", "lathed_lamp_glow_core"],
        ),
    ]


def _foliage_ground_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    return [
        _subdivision_box(component.part, component, tags=[*list(component.tags), "soil_patch", "subdivision_soil_patch"], corner_segments=4),
        _subdivision_box(
            component.part,
            component,
            center=(cx - width * 0.18, cy + height * 0.36, cz + depth * 0.16),
            extents=(width * 0.30, max(height * 0.28, 0.035), depth * 0.22),
            tags=[*list(component.tags), "raised_moss_patch", "subdivision_moss_patch"],
            corner_segments=4,
        ),
        _subdivision_box(
            component.part,
            component,
            center=(cx + width * 0.24, cy + height * 0.30, cz - depth * 0.14),
            extents=(width * 0.24, max(height * 0.20, 0.03), depth * 0.18),
            tags=[*list(component.tags), "leaf_litter_patch", "subdivision_leaf_litter_patch"],
            corner_segments=4,
        ),
    ]


def _tree_trunk_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    radius = component.radius if component.radius is not None else max(min(width, depth) * 0.45, 0.06)
    trunk_height = component.height if component.height is not None else height
    primitives = [
        _swept_profile(
            component.part,
            component,
            cross_section=_round_cross_section(radius, 10),
            sweep_path=[(0.0, -trunk_height * 0.50, 0.0), (radius * 0.08, 0.0, -radius * 0.04), (0.0, trunk_height * 0.50, 0.0)],
            tags=[*list(component.tags), "trunk_core", "swept_tree_trunk_core"],
        ),
        _revolved_profile(
            component.part,
            component,
            center=(cx, cy - trunk_height * 0.42, cz),
            profile_points=[
                (-max(trunk_height * 0.06, 0.04), radius * 0.88),
                (0.0, radius * 1.20),
                (max(trunk_height * 0.06, 0.04), radius * 0.96),
            ],
            axis="y",
            tags=[*list(component.tags), "trunk_flare", "lathed_trunk_flare"],
        ),
    ]
    for index, angle in enumerate((0.0, math.tau / 3.0, math.tau * 2.0 / 3.0)):
        primitives.append(
            _swept_profile(
                component.part,
                component,
                center=(cx + math.cos(angle) * radius * 0.72, cy, cz + math.sin(angle) * radius * 0.72),
                cross_section=_round_cross_section(radius * 0.10, 6),
                sweep_path=[(0.0, -trunk_height * 0.46, 0.0), (radius * 0.06, 0.0, radius * 0.03), (0.0, trunk_height * 0.46, 0.0)],
                tags=[*list(component.tags), "bark_ridge", "swept_bark_ridge", f"ridge_{index}"],
            )
        )
    return primitives


def _root_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    radius = component.radius if component.radius is not None else max(min(height, depth) * 0.42, 0.035)
    root_length = component.height if component.height is not None else max(width, depth)
    axis = "x" if width >= depth else "z"
    sweep_path = [
        (-root_length * 0.50, -height * 0.04, 0.0),
        (-root_length * 0.18, height * 0.07, depth * 0.05),
        (root_length * 0.18, height * 0.02, -depth * 0.04),
        (root_length * 0.50, -height * 0.05, 0.0),
    ]
    if axis == "z":
        sweep_path = [(z, y, x) for x, y, z in sweep_path]
    return [
        _swept_profile(
            component.part,
            component,
            cross_section=_round_cross_section(radius, 8),
            sweep_path=sweep_path,
            tags=[*list(component.tags), "root_runner", "swept_root_runner"],
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.28, cz),
            profile_polygon=_chamfered_rect_profile(width * 0.84, max(height * 0.18, 0.035), height * 0.025),
            extrude_height=depth * 0.84,
            axis="z",
            tags=[*list(component.tags), "surface_root_ridge", "extruded_surface_root_ridge"],
            rounding=0.02,
        ),
    ]


def _tree_branch_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    radius = component.radius if component.radius is not None else max(min(height, depth) * 0.42, 0.035)
    branch_length = component.height if component.height is not None else max(width, depth)
    axis = component.axis if component.axis in {"x", "y", "z"} else "x"
    sweep_path = [(-branch_length * 0.50, 0.0, 0.0), (-branch_length * 0.12, height * 0.08, depth * 0.04), (branch_length * 0.50, height * 0.02, 0.0)]
    if axis == "z":
        sweep_path = [(z, y, x) for x, y, z in sweep_path]
    elif axis == "y":
        sweep_path = [(z, x, y) for x, y, z in sweep_path]
    return [
        _swept_profile(
            component.part,
            component,
            cross_section=_round_cross_section(radius, 8),
            sweep_path=sweep_path,
            tags=[*list(component.tags), "branch_core", "swept_branch_core"],
        ),
        _swept_profile(
            component.part,
            component,
            center=(component.center[0], component.center[1] + height * 0.22, component.center[2]),
            cross_section=_round_cross_section(radius * 0.42, 7),
            sweep_path=[(-width * 0.20, 0.0, 0.0), (0.0, height * 0.10, depth * 0.26), (width * 0.20, height * 0.02, depth * 0.52)],
            tags=[*list(component.tags), "twig_fork", "swept_twig_fork"],
        ),
    ]


def _leaf_cluster_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    radius = component.radius if component.radius is not None else max(min(width, depth) * 0.48, 0.08)
    return [
        _sphere(component.part, component, radius=radius, tags=[*list(component.tags), "leaf_mass"]),
        _sphere(
            component.part,
            component,
            center=(cx - width * 0.20, cy + height * 0.08, cz),
            radius=max(min(width * 0.31, height * 0.22, depth * 0.37), 0.04),
            tags=[*list(component.tags), "left_leaf_lobe"],
        ),
        _sphere(
            component.part,
            component,
            center=(cx + width * 0.20, cy - height * 0.04, cz),
            radius=max(min(width * 0.31, height * 0.20, depth * 0.34), 0.04),
            tags=[*list(component.tags), "right_leaf_lobe"],
        ),
        _sphere(
            component.part,
            component,
            center=(cx, cy + height * 0.26, cz + depth * 0.16),
            radius=max(min(width * 0.27, height * 0.17, depth * 0.23), 0.035),
            tags=[*list(component.tags), "crown_leaf_lobe"],
        ),
    ]


def _bush_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    return [
        _sphere(component.part, component, radius=max(min(width, depth) * 0.46, 0.08), tags=[*list(component.tags), "shrub_core"]),
        _sphere(component.part, component, center=(cx - width * 0.18, cy, cz), radius=max(min(width * 0.31, height * 0.31, depth * 0.26), 0.05), tags=[*list(component.tags), "left_shrub_mass"]),
        _sphere(component.part, component, center=(cx + width * 0.18, cy + height * 0.08, cz + depth * 0.08), radius=max(min(width * 0.29, height * 0.29, depth * 0.28), 0.05), tags=[*list(component.tags), "right_shrub_mass"]),
    ]


def _grass_clump_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    primitives: list[ShapePrimitive] = []
    blade_count = 5
    for index in range(blade_count):
        t = (index - (blade_count - 1) / 2.0) / max(1.0, (blade_count - 1) / 2.0)
        primitives.append(
            _extruded_profile(
                component.part,
                component,
                center=(cx + t * width * 0.30, cy + height * (0.05 * (index % 2)), cz + t * depth * 0.12),
                profile_polygon=[
                    (-max(width * 0.05, 0.012), -height * 0.35),
                    (max(width * 0.05, 0.012), -height * 0.35),
                    (max(width * 0.02, 0.006), height * 0.18),
                    (0.0, height * (0.35 + 0.03 * (index % 3))),
                    (-max(width * 0.02, 0.006), height * 0.18),
                ],
                extrude_height=max(depth * 0.12, 0.025),
                axis="z",
                tags=[*list(component.tags), "grass_blade", "extruded_grass_blade", f"blade_{index}"],
                rounding=0.005,
            )
        )
    return primitives


def _natural_rock_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    return [
        _subdivision_box(component.part, component, tags=[*list(component.tags), "rock_core", "subdivision_rock_core"], corner_segments=5),
        _subdivision_box(
            component.part,
            component,
            center=(cx - width * 0.18, cy + height * 0.22, cz + depth * 0.08),
            extents=(width * 0.52, height * 0.58, depth * 0.64),
            tags=[*list(component.tags), "upper_facet", "subdivision_rock_facet"],
            corner_segments=3,
        ),
        _subdivision_box(
            component.part,
            component,
            center=(cx + width * 0.24, cy - height * 0.12, cz - depth * 0.14),
            extents=(width * 0.48, height * 0.42, depth * 0.52),
            tags=[*list(component.tags), "lower_facet", "subdivision_rock_facet"],
            corner_segments=3,
        ),
    ]


def _mushroom_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    radius = component.radius if component.radius is not None else max(min(width, depth) * 0.24, 0.035)
    mushroom_height = component.height if component.height is not None else height
    return [
        _revolved_profile(
            component.part,
            component,
            center=(component.center[0], component.center[1] - mushroom_height * 0.16, component.center[2]),
            profile_points=[
                (-mushroom_height * 0.31, radius * 0.36),
                (-mushroom_height * 0.10, radius * 0.48),
                (mushroom_height * 0.22, radius * 0.40),
                (mushroom_height * 0.31, radius * 0.58),
            ],
            axis="y",
            tags=[*list(component.tags), "stem", "lathed_mushroom_stem"],
        ),
        _sphere(
            component.part,
            component,
            center=(component.center[0], component.center[1] + mushroom_height * 0.24, component.center[2]),
            radius=radius * 1.18,
            tags=[*list(component.tags), "cap", "rounded_cap"],
        ),
        _extruded_profile(
            component.part,
            component,
            center=(component.center[0], component.center[1] + mushroom_height * 0.12, component.center[2]),
            profile_polygon=[
                (-radius * 1.10, 0.0),
                (-radius * 0.20, max(mushroom_height * 0.025, 0.014)),
                (radius * 1.10, 0.0),
                (radius * 0.20, -max(mushroom_height * 0.025, 0.014)),
            ],
            extrude_height=radius * 1.6,
            axis="z",
            tags=[*list(component.tags), "gills", "extruded_mushroom_gills"],
            rounding=0.01,
        ),
    ]


def _fallen_log_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    radius = component.radius if component.radius is not None else max(min(component.extents[1], component.extents[2]) * 0.42, 0.06)
    log_length = component.height if component.height is not None else component.extents[0]
    width, height, depth = component.extents
    sweep_path = [(-log_length * 0.50, 0.0, 0.0), (-log_length * 0.12, -height * 0.03, depth * 0.04), (log_length * 0.50, height * 0.02, 0.0)]
    if component.axis == "z":
        sweep_path = [(z, y, x) for x, y, z in sweep_path]
    elif component.axis == "y":
        sweep_path = [(z, x, y) for x, y, z in sweep_path]
    return [
        _swept_profile(
            component.part,
            component,
            cross_section=_round_cross_section(radius, 10),
            sweep_path=sweep_path,
            tags=[*list(component.tags), "log_body", "swept_fallen_log_body"],
        ),
        _revolved_profile(
            component.part,
            component,
            center=(component.center[0] - log_length * 0.48 if component.axis == "x" else component.center[0], component.center[1], component.center[2]),
            profile_points=_lathed_cylinder_profile(max(log_length * 0.05, 0.04), radius * 0.92, bevel=0.12),
            axis=component.axis,
            tags=[*list(component.tags), "cut_end_a", "lathed_log_cut_end"],
        ),
        _revolved_profile(
            component.part,
            component,
            center=(component.center[0] + log_length * 0.48 if component.axis == "x" else component.center[0], component.center[1], component.center[2]),
            profile_points=_lathed_cylinder_profile(max(log_length * 0.05, 0.04), radius * 0.92, bevel=0.12),
            axis=component.axis,
            tags=[*list(component.tags), "cut_end_b", "lathed_log_cut_end"],
        ),
    ]


def _vine_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    radius = component.radius if component.radius is not None else max(min(component.extents[0], component.extents[2]) * 0.34, 0.018)
    vine_height = component.height if component.height is not None else component.extents[1]
    width, _, depth = component.extents
    return [
        _swept_profile(
            component.part,
            component,
            cross_section=_round_cross_section(radius, 7),
            sweep_path=[
                (0.0, -vine_height * 0.50, 0.0),
                (width * 0.12, -vine_height * 0.18, depth * 0.04),
                (-width * 0.08, vine_height * 0.16, -depth * 0.03),
                (0.0, vine_height * 0.50, 0.0),
            ],
            tags=[*list(component.tags), "vine_line", "swept_vine_line"],
        ),
        _extruded_profile(
            component.part,
            component,
            center=(component.center[0] + width * 0.26, component.center[1] + vine_height * 0.10, component.center[2]),
            profile_polygon=[
                (-width * 0.35, 0.0),
                (-width * 0.06, max(vine_height * 0.05, 0.025)),
                (width * 0.35, 0.0),
                (-width * 0.06, -max(vine_height * 0.05, 0.025)),
            ],
            extrude_height=depth * 0.80,
            axis="z",
            tags=[*list(component.tags), "leaf_sprig", "extruded_vine_leaf_sprig"],
            rounding=0.01,
        ),
    ]


def _flower_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    radius = component.radius if component.radius is not None else max(min(width, depth) * 0.28, 0.025)
    stem_h = component.height if component.height is not None else height * 0.72
    primitives = [
        _round_bar(component.part, component, center=(cx, cy - stem_h * 0.18, cz), radius=radius * 0.32, height=stem_h, axis="y", tags=[*list(component.tags), "stem", "swept_flower_stem"]),
        _sphere(component.part, component, center=(cx, cy + stem_h * 0.34, cz), radius=radius * 0.55, tags=[*list(component.tags), "flower_center"]),
    ]
    for index, angle in enumerate((0.0, math.tau / 3.0, math.tau * 2.0 / 3.0)):
        primitives.append(
            _extruded_profile(
                component.part,
                component,
                center=(cx + math.cos(angle) * radius * 0.9, cy + stem_h * 0.34, cz + math.sin(angle) * radius * 0.9),
                profile_polygon=[
                    (-radius * 0.40, 0.0),
                    (0.0, max(height * 0.05, 0.025)),
                    (radius * 0.40, 0.0),
                    (0.0, -max(height * 0.035, 0.018)),
                ],
                extrude_height=radius * 0.55,
                axis="z",
                tags=[*list(component.tags), "petal", "extruded_flower_petal", f"petal_{index}"],
                rounding=0.01,
            )
        )
    return primitives


def _planter_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    return [
        _subdivision_box(component.part, component, tags=[*list(component.tags), "planter_box", "subdivision_planter_box"], corner_segments=4),
        _subdivision_box(
            component.part,
            component,
            center=(cx, cy + height * 0.40, cz),
            extents=(width * 0.82, max(height * 0.18, 0.05), depth * 0.82),
            tags=[*list(component.tags), "soil_insert", "subdivision_planter_soil"],
            corner_segments=4,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.52, cz),
            profile_polygon=_chamfered_rect_profile(width * 1.08, max(height * 0.12, 0.04), height * 0.025),
            extrude_height=depth * 1.08,
            axis="z",
            tags=[*list(component.tags), "rim", "extruded_planter_rim"],
            rounding=0.02,
        ),
    ]


def _urban_base_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    curb_h = max(height * 0.55, 0.04)
    curb_w = max(width * 0.045, 0.06)
    return [
        _subdivision_box(component.part, component, tags=[*list(component.tags), "sidewalk_slab", "subdivision_urban_sidewalk_slab"], corner_segments=3),
        _extruded_profile(
            component.part,
            component,
            center=(cx - width * 0.46, cy + curb_h * 0.42, cz),
            profile_polygon=_chamfered_rect_profile(curb_w, curb_h, curb_w * 0.20),
            extrude_height=depth,
            axis="z",
            tags=[*list(component.tags), "left_curb", "extruded_urban_curb"],
            rounding=0.01,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx + width * 0.46, cy + curb_h * 0.42, cz),
            profile_polygon=_chamfered_rect_profile(curb_w, curb_h, curb_w * 0.20),
            extrude_height=depth,
            axis="z",
            tags=[*list(component.tags), "right_curb", "extruded_urban_curb"],
            rounding=0.01,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + curb_h * 0.35, cz + depth * 0.46),
            profile_polygon=_chamfered_rect_profile(width, curb_h * 0.72, curb_h * 0.12),
            extrude_height=max(depth * 0.045, 0.06),
            axis="z",
            tags=[*list(component.tags), "front_lip", "extruded_urban_front_lip"],
            rounding=0.01,
        ),
    ]


def _fence_segment_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    post_w = max(width * 0.08, 0.05)
    rail_h = max(height * 0.08, 0.035)
    return [
        _round_bar(
            component.part,
            component,
            center=(cx - width * 0.44, cy, cz),
            radius=post_w * 0.50,
            height=height,
            axis="y",
            tags=[*list(component.tags), "left_post", "swept_fence_post"],
        ),
        _round_bar(
            component.part,
            component,
            center=(cx + width * 0.44, cy, cz),
            radius=post_w * 0.50,
            height=height,
            axis="y",
            tags=[*list(component.tags), "right_post", "swept_fence_post"],
        ),
        _round_bar(
            component.part,
            component,
            center=(cx, cy + height * 0.28, cz),
            radius=rail_h * 0.50,
            height=width,
            axis="x",
            tags=[*list(component.tags), "top_rail", "swept_fence_rail"],
        ),
        _round_bar(
            component.part,
            component,
            center=(cx, cy - height * 0.18, cz),
            radius=rail_h * 0.50,
            height=width,
            axis="x",
            tags=[*list(component.tags), "lower_rail", "swept_fence_rail"],
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.02, cz),
            profile_polygon=_chamfered_rect_profile(post_w * 0.70, height * 0.76, post_w * 0.14),
            extrude_height=depth * 0.80,
            axis="z",
            tags=[*list(component.tags), "center_picket", "extruded_fence_picket"],
            rounding=0.01,
        ),
    ]


def _gate_panel_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    frame_w = max(width * 0.10, 0.05)
    frame_h = max(height * 0.08, 0.04)
    primitives = [
        _subdivision_box(component.part, component, tags=[*list(component.tags), "gate_slab", "subdivision_gate_slab"], corner_segments=3),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.43, cz + depth * 0.08),
            profile_polygon=_chamfered_rect_profile(width, frame_h, frame_h * 0.25),
            extrude_height=depth * 1.20,
            axis="z",
            tags=[*list(component.tags), "top_frame", "extruded_gate_frame"],
            rounding=0.02,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy - height * 0.43, cz + depth * 0.08),
            profile_polygon=_chamfered_rect_profile(width, frame_h, frame_h * 0.25),
            extrude_height=depth * 1.20,
            axis="z",
            tags=[*list(component.tags), "bottom_frame", "extruded_gate_frame"],
            rounding=0.02,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx - width * 0.44, cy, cz + depth * 0.08),
            profile_polygon=_chamfered_rect_profile(frame_w, height, frame_w * 0.20),
            extrude_height=depth * 1.20,
            axis="z",
            tags=[*list(component.tags), "hinge_side_frame", "extruded_gate_frame"],
            rounding=0.02,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx + width * 0.44, cy, cz + depth * 0.08),
            profile_polygon=_chamfered_rect_profile(frame_w, height, frame_w * 0.20),
            extrude_height=depth * 1.20,
            axis="z",
            tags=[*list(component.tags), "latch_side_frame", "extruded_gate_frame"],
            rounding=0.02,
        ),
    ]
    for index, offset in enumerate((-0.20, 0.0, 0.20)):
        primitives.append(
            _round_bar(
                component.part,
                component,
                center=(cx + width * offset, cy, cz + depth * 0.12),
                radius=frame_w * 0.26,
                height=height * 0.78,
                axis="y",
                tags=[*list(component.tags), "vertical_bar", "swept_gate_bar", f"bar_{index}"],
            )
        )
    return primitives


def _sign_post_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    radius = component.radius if component.radius is not None else max(width * 0.12, 0.035)
    post_h = component.height if component.height is not None else height * 0.78
    board_w = width * 1.60
    board_h = height * 0.30
    return [
        _round_bar(
            component.part,
            component,
            center=(cx, cy - height * 0.08, cz),
            radius=radius,
            height=post_h,
            axis="y",
            tags=[*list(component.tags), "post", "swept_sign_post"],
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.26, cz + depth * 0.05),
            profile_polygon=_chamfered_rect_profile(board_w, board_h, min(board_w, board_h) * 0.08),
            extrude_height=max(depth * 0.75, 0.05),
            axis="z",
            tags=[*list(component.tags), "sign_board", "label_zone", "extruded_sign_board"],
            rounding=0.02,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.26, cz + depth * 0.42),
            profile_polygon=_chamfered_rect_profile(board_w * 0.78, board_h * 0.18, board_h * 0.04),
            extrude_height=max(depth * 0.18, 0.035),
            axis="z",
            tags=[*list(component.tags), "painted_label_strip", "extruded_sign_label_strip"],
            rounding=0.01,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy - post_h * 0.52, cz),
            profile_polygon=_chamfered_rect_profile(width * 0.62, max(height * 0.045, 0.035), height * 0.02),
            extrude_height=width * 0.62,
            axis="z",
            tags=[*list(component.tags), "mount_plate", "extruded_sign_mount_plate"],
            rounding=0.02,
        ),
    ]


def _streetlight_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    radius = component.radius if component.radius is not None else max(width * 0.11, 0.035)
    pole_h = component.height if component.height is not None else height * 0.94
    return [
        _round_bar(
            component.part,
            component,
            center=(cx, cy - height * 0.03, cz),
            radius=radius,
            height=pole_h,
            axis="y",
            tags=[*list(component.tags), "lamp_pole", "swept_streetlight_pole"],
        ),
        _round_bar(
            component.part,
            component,
            center=(cx + width * 0.42, cy + height * 0.33, cz),
            radius=max(min(height, depth) * 0.035, 0.02),
            height=width * 0.92,
            axis="x",
            tags=[*list(component.tags), "curved_arm", "swept_streetlight_arm"],
        ),
        _subdivision_box(
            component.part,
            component,
            center=(cx + width * 0.86, cy + height * 0.22, cz),
            extents=(width * 0.48, height * 0.13, depth * 0.62),
            tags=[*list(component.tags), "lamp_head", "subdivision_streetlight_head"],
            corner_segments=4,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx + width * 0.86, cy + height * 0.14, cz),
            profile_polygon=_chamfered_rect_profile(width * 0.36, height * 0.055, height * 0.015),
            extrude_height=depth * 0.45,
            axis="z",
            tags=[*list(component.tags), "glow_panel", "emissive", "extruded_streetlight_glow_panel"],
            rounding=0.01,
        ),
        _revolved_profile(
            component.part,
            component,
            center=(cx, cy - pole_h * 0.50, cz),
            profile_points=_lathed_cylinder_profile(max(height * 0.06, 0.04), radius * 2.2, bevel=0.18),
            axis="y",
            tags=[*list(component.tags), "base_flange", "lathed_streetlight_base_flange"],
        ),
    ]


def _street_bench_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    slat_h = max(height * 0.12, 0.035)
    leg_r = max(width * 0.035, 0.025)
    return [
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.08, cz),
            profile_polygon=_chamfered_rect_profile(width, slat_h, slat_h * 0.22),
            extrude_height=depth * 0.70,
            axis="z",
            tags=[*list(component.tags), "seat_plank", "extruded_bench_seat_plank"],
            rounding=0.02,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.38, cz - depth * 0.34),
            profile_polygon=_chamfered_rect_profile(width, slat_h, slat_h * 0.22),
            extrude_height=depth * 0.30,
            axis="z",
            tags=[*list(component.tags), "back_plank", "extruded_bench_back_plank"],
            rounding=0.02,
        ),
        _revolved_profile(
            component.part,
            component,
            center=(cx - width * 0.34, cy - height * 0.18, cz),
            profile_points=[
                (-height * 0.24, leg_r * 0.55),
                (-height * 0.18, leg_r),
                (height * 0.20, leg_r * 0.78),
                (height * 0.24, leg_r * 0.48),
            ],
            axis="y",
            tags=[*list(component.tags), "left_leg", "lathed_bench_leg"],
        ),
        _revolved_profile(
            component.part,
            component,
            center=(cx + width * 0.34, cy - height * 0.18, cz),
            profile_points=[
                (-height * 0.24, leg_r * 0.55),
                (-height * 0.18, leg_r),
                (height * 0.20, leg_r * 0.78),
                (height * 0.24, leg_r * 0.48),
            ],
            axis="y",
            tags=[*list(component.tags), "right_leg", "lathed_bench_leg"],
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.18, cz - depth * 0.10),
            profile_polygon=_chamfered_rect_profile(width * 0.92, max(height * 0.055, 0.03), height * 0.012),
            extrude_height=depth * 0.12,
            axis="z",
            tags=[*list(component.tags), "middle_slat", "extruded_bench_middle_slat"],
            rounding=0.01,
        ),
    ]


def _trash_bin_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    radius = component.radius if component.radius is not None else max(min(width, depth) * 0.42, 0.05)
    bin_h = component.height if component.height is not None else height
    return [
        _revolved_profile(
            component.part,
            component,
            profile_points=[
                (-bin_h * 0.50, radius * 0.84),
                (-bin_h * 0.34, radius),
                (bin_h * 0.38, radius * 0.94),
                (bin_h * 0.50, radius * 0.82),
            ],
            axis="y",
            tags=[*list(component.tags), "bin_body", "lathed_trash_bin_body"],
        ),
        _revolved_profile(
            component.part,
            component,
            center=(cx, cy + bin_h * 0.46, cz),
            profile_points=[
                (-max(height * 0.06, 0.035), radius * 0.72),
                (-max(height * 0.035, 0.025), radius * 1.08),
                (max(height * 0.04, 0.025), radius * 1.02),
                (max(height * 0.06, 0.035), radius * 0.62),
            ],
            axis="y",
            tags=[*list(component.tags), "lid", "lathed_trash_bin_lid"],
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.18, cz + radius * 0.88),
            profile_polygon=_chamfered_rect_profile(width * 0.58, height * 0.11, height * 0.025),
            extrude_height=max(depth * 0.08, 0.035),
            axis="z",
            tags=[*list(component.tags), "front_slot", "extruded_trash_bin_front_slot"],
            rounding=0.01,
        ),
    ]


def _utility_pole_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    radius = component.radius if component.radius is not None else max(width * 0.18, 0.04)
    pole_h = component.height if component.height is not None else height
    return [
        _round_bar(component.part, component, radius=radius, height=pole_h, axis="y", tags=[*list(component.tags), "pole", "swept_utility_pole"]),
        _round_bar(
            component.part,
            component,
            center=(cx, cy + height * 0.28, cz),
            radius=max(min(height, depth) * 0.04, 0.02),
            height=width * 2.30,
            axis="x",
            tags=[*list(component.tags), "crossbar", "swept_utility_crossbar"],
        ),
        _revolved_profile(
            component.part,
            component,
            center=(cx - width * 0.70, cy + height * 0.32, cz),
            profile_points=_lathed_cylinder_profile(max(height * 0.09, 0.05), radius * 0.42, bevel=0.18),
            axis="y",
            tags=[*list(component.tags), "left_insulator", "lathed_utility_insulator"],
        ),
        _revolved_profile(
            component.part,
            component,
            center=(cx + width * 0.70, cy + height * 0.32, cz),
            profile_points=_lathed_cylinder_profile(max(height * 0.09, 0.05), radius * 0.42, bevel=0.18),
            axis="y",
            tags=[*list(component.tags), "right_insulator", "lathed_utility_insulator"],
        ),
    ]


def _cable_span_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    radius = component.radius if component.radius is not None else max(min(height, depth) * 0.38, 0.018)
    span = component.height if component.height is not None else width
    return [
        _round_bar(
            component.part,
            component,
            radius=radius,
            height=span,
            axis=component.axis,
            tags=[*list(component.tags), "main_wire", "swept_cable_span"],
        ),
        _extruded_profile(
            component.part,
            component,
            center=(component.center[0], component.center[1] - max(height * 0.50, 0.035), component.center[2]),
            profile_polygon=[
                (-width * 0.42, -max(height * 0.05, 0.012)),
                (width * 0.42, -max(height * 0.05, 0.012)),
                (width * 0.32, max(height * 0.06, 0.012)),
                (0.0, max(height * 0.09, 0.018)),
                (-width * 0.32, max(height * 0.06, 0.012)),
            ],
            extrude_height=depth * 0.70,
            axis="z",
            tags=[*list(component.tags), "sag_shadow", "extruded_cable_sag_shadow"],
            rounding=0.01,
        ),
    ]


def _kiosk_body_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    return [
        _subdivision_box(component.part, component, tags=[*list(component.tags), "kiosk_shell", "subdivision_kiosk_shell"], corner_segments=4),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.08, cz + depth * 0.52),
            profile_polygon=_chamfered_rect_profile(width * 0.62, height * 0.28, min(width, height) * 0.04),
            extrude_height=max(depth * 0.07, 0.04),
            axis="z",
            tags=[*list(component.tags), "service_window", "glass", "extruded_kiosk_service_window"],
            rounding=0.01,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.52, cz + depth * 0.10),
            profile_polygon=[
                (-width * 0.56, -height * 0.05),
                (width * 0.56, -height * 0.05),
                (width * 0.40, height * 0.06),
                (-width * 0.40, height * 0.06),
            ],
            extrude_height=depth * 1.16,
            axis="z",
            tags=[*list(component.tags), "roof_cap", "extruded_kiosk_roof_cap"],
            rounding=0.02,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.28, cz + depth * 0.63),
            profile_polygon=_chamfered_rect_profile(width * 0.92, height * 0.08, height * 0.02),
            extrude_height=depth * 0.20,
            axis="z",
            tags=[*list(component.tags), "awning", "canopy", "extruded_kiosk_awning"],
            rounding=0.02,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy - height * 0.12, cz + depth * 0.56),
            profile_polygon=_chamfered_rect_profile(width * 0.82, height * 0.12, height * 0.03),
            extrude_height=depth * 0.22,
            axis="z",
            tags=[*list(component.tags), "counter", "extruded_kiosk_counter"],
            rounding=0.02,
        ),
    ]


def _market_stall_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    post_w = max(width * 0.055, 0.035)
    return [
        _subdivision_box(
            component.part,
            component,
            center=(cx, cy - height * 0.18, cz),
            extents=(width, height * 0.18, depth * 0.82),
            tags=[*list(component.tags), "display_table", "subdivision_market_display_table"],
            corner_segments=4,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.35, cz),
            profile_polygon=[
                (-width * 0.54, -height * 0.04),
                (width * 0.54, -height * 0.04),
                (width * 0.44, height * 0.06),
                (-width * 0.44, height * 0.06),
            ],
            extrude_height=depth * 1.08,
            axis="z",
            tags=[*list(component.tags), "fabric_canopy", "canopy", "extruded_market_canopy"],
            rounding=0.02,
        ),
        _round_bar(component.part, component, center=(cx - width * 0.44, cy + height * 0.04, cz - depth * 0.34), radius=post_w * 0.50, height=height * 0.82, axis="y", tags=[*list(component.tags), "front_left_post", "swept_market_post"]),
        _round_bar(component.part, component, center=(cx + width * 0.44, cy + height * 0.04, cz - depth * 0.34), radius=post_w * 0.50, height=height * 0.82, axis="y", tags=[*list(component.tags), "front_right_post", "swept_market_post"]),
        _round_bar(component.part, component, center=(cx - width * 0.44, cy + height * 0.04, cz + depth * 0.34), radius=post_w * 0.50, height=height * 0.82, axis="y", tags=[*list(component.tags), "rear_left_post", "swept_market_post"]),
        _round_bar(component.part, component, center=(cx + width * 0.44, cy + height * 0.04, cz + depth * 0.34), radius=post_w * 0.50, height=height * 0.82, axis="y", tags=[*list(component.tags), "rear_right_post", "swept_market_post"]),
        _subdivision_box(
            component.part,
            component,
            center=(cx - width * 0.18, cy - height * 0.02, cz + depth * 0.10),
            extents=(width * 0.22, height * 0.12, depth * 0.20),
            tags=[*list(component.tags), "goods_bin_a", "subdivision_market_goods_bin"],
            corner_segments=3,
        ),
        _subdivision_box(
            component.part,
            component,
            center=(cx + width * 0.18, cy - height * 0.02, cz - depth * 0.08),
            extents=(width * 0.22, height * 0.12, depth * 0.20),
            tags=[*list(component.tags), "goods_bin_b", "subdivision_market_goods_bin"],
            corner_segments=3,
        ),
    ]


def _street_barrier_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    return [
        _subdivision_box(component.part, component, tags=[*list(component.tags), "barrier_body", "subdivision_street_barrier"], corner_segments=4),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.18, cz + depth * 0.52),
            profile_polygon=_chamfered_rect_profile(width * 0.82, height * 0.13, height * 0.03),
            extrude_height=max(depth * 0.12, 0.035),
            axis="z",
            tags=[*list(component.tags), "warning_stripe", "extruded_warning_stripe"],
            rounding=0.01,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx - width * 0.34, cy - height * 0.48, cz),
            profile_polygon=_chamfered_rect_profile(width * 0.16, height * 0.20, height * 0.04),
            extrude_height=depth * 1.12,
            axis="z",
            tags=[*list(component.tags), "left_foot", "extruded_barrier_foot"],
            rounding=0.02,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx + width * 0.34, cy - height * 0.48, cz),
            profile_polygon=_chamfered_rect_profile(width * 0.16, height * 0.20, height * 0.04),
            extrude_height=depth * 1.12,
            axis="z",
            tags=[*list(component.tags), "right_foot", "extruded_barrier_foot"],
            rounding=0.02,
        ),
    ]


def _street_crate_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    return [
        _subdivision_box(component.part, component, tags=[*list(component.tags), "crate_body", "subdivision_crate_body"], corner_segments=4),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.44, cz),
            profile_polygon=_chamfered_rect_profile(width * 1.04, max(height * 0.12, 0.035), height * 0.03),
            extrude_height=depth * 1.04,
            axis="z",
            tags=[*list(component.tags), "lid_slats", "extruded_crate_lid_slats"],
            rounding=0.02,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx - width * 0.42, cy, cz + depth * 0.50),
            profile_polygon=_chamfered_rect_profile(max(width * 0.08, 0.035), height * 0.92, width * 0.02),
            extrude_height=max(depth * 0.08, 0.035),
            axis="z",
            tags=[*list(component.tags), "front_left_slat", "extruded_crate_slat"],
            rounding=0.01,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx + width * 0.42, cy, cz + depth * 0.50),
            profile_polygon=_chamfered_rect_profile(max(width * 0.08, 0.035), height * 0.92, width * 0.02),
            extrude_height=max(depth * 0.08, 0.035),
            axis="z",
            tags=[*list(component.tags), "front_right_slat", "extruded_crate_slat"],
            rounding=0.01,
        ),
    ]


def _bollard_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    radius = component.radius if component.radius is not None else max(min(width, depth) * 0.36, 0.04)
    bollard_h = component.height if component.height is not None else height
    return [
        _round_bar(component.part, component, radius=radius, height=bollard_h, axis="y", tags=[*list(component.tags), "post", "swept_bollard_post"]),
        _revolved_profile(
            component.part,
            component,
            center=(cx, cy + bollard_h * 0.48, cz),
            profile_points=_lathed_cylinder_profile(max(height * 0.07, 0.035), radius * 1.08, bevel=0.16),
            axis="y",
            tags=[*list(component.tags), "cap", "lathed_bollard_cap"],
        ),
        _revolved_profile(
            component.part,
            component,
            center=(cx, cy - bollard_h * 0.48, cz),
            profile_points=_lathed_cylinder_profile(max(height * 0.08, 0.035), radius * 1.45, bevel=0.16),
            axis="y",
            tags=[*list(component.tags), "base_plate", "lathed_bollard_base_plate"],
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.10, cz + radius * 0.70),
            profile_polygon=_chamfered_rect_profile(radius * 1.20, max(height * 0.08, 0.03), radius * 0.08),
            extrude_height=max(depth * 0.08, 0.025),
            axis="z",
            tags=[*list(component.tags), "reflective_band", "warning", "extruded_bollard_reflective_band"],
            rounding=0.01,
        ),
    ]


def _infrastructure_base_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    trench_w = max(width * 0.72, 0.10)
    curb_h = max(height * 0.50, 0.035)
    return [
        _subdivision_box(component.part, component, tags=[*list(component.tags), "service_slab", "subdivision_service_slab"], corner_segments=3),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.38, cz),
            profile_polygon=_chamfered_rect_profile(trench_w, max(height * 0.28, 0.035), height * 0.03),
            extrude_height=depth * 0.36,
            axis="z",
            tags=[*list(component.tags), "service_trench", "extruded_service_trench"],
            blend_mode="subtract",
            rounding=0.01,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx - width * 0.46, cy + curb_h * 0.34, cz),
            profile_polygon=_chamfered_rect_profile(max(width * 0.04, 0.05), curb_h, width * 0.01),
            extrude_height=depth,
            axis="z",
            tags=[*list(component.tags), "left_service_edge", "extruded_service_edge"],
            rounding=0.01,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx + width * 0.46, cy + curb_h * 0.34, cz),
            profile_polygon=_chamfered_rect_profile(max(width * 0.04, 0.05), curb_h, width * 0.01),
            extrude_height=depth,
            axis="z",
            tags=[*list(component.tags), "right_service_edge", "extruded_service_edge"],
            rounding=0.01,
        ),
    ]


def _pipe_run_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    radius = component.radius if component.radius is not None else max(min(height, depth) * 0.42, 0.045)
    pipe_length = component.height if component.height is not None else max(width, depth)
    if component.axis == "x":
        pipe_path = [(-pipe_length * 0.50, 0.0, 0.0), (0.0, radius * 0.06, 0.0), (pipe_length * 0.50, 0.0, 0.0)]
    elif component.axis == "z":
        pipe_path = [(0.0, 0.0, -pipe_length * 0.50), (0.0, radius * 0.06, 0.0), (0.0, 0.0, pipe_length * 0.50)]
    else:
        pipe_path = [(0.0, -pipe_length * 0.50, 0.0), (radius * 0.05, 0.0, 0.0), (0.0, pipe_length * 0.50, 0.0)]
    return [
        _swept_profile(component.part, component, cross_section=_round_cross_section(radius, 10), sweep_path=pipe_path, tags=[*list(component.tags), "pipe_body", "swept_pipe_body"]),
        _torus(
            component.part,
            component,
            center=(cx - pipe_length * 0.36 if component.axis == "x" else cx, cy, cz),
            major_radius=radius * 1.06,
            minor_radius=max(radius * 0.16, 0.012),
            axis=component.axis,
            tags=[*list(component.tags), "left_coupler", "torus_pipe_coupler"],
        ),
        _torus(
            component.part,
            component,
            center=(cx + pipe_length * 0.36 if component.axis == "x" else cx, cy, cz),
            major_radius=radius * 1.06,
            minor_radius=max(radius * 0.16, 0.012),
            axis=component.axis,
            tags=[*list(component.tags), "right_coupler", "torus_pipe_coupler"],
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy - radius * 0.92, cz),
            profile_polygon=_chamfered_rect_profile(pipe_length * 0.76 if component.axis == "x" else width, max(radius * 0.32, 0.025), radius * 0.05),
            extrude_height=depth * 0.72,
            axis="z",
            tags=[*list(component.tags), "pipe_shadow_pad", "extruded_pipe_shadow_pad"],
            rounding=0.01,
        ),
    ]


def _duct_run_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    seam = max(height * 0.10, 0.035)
    return [
        _subdivision_box(component.part, component, tags=[*list(component.tags), "duct_body", "subdivision_duct_body"], corner_segments=4),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.42, cz),
            profile_polygon=_chamfered_rect_profile(width * 0.94, seam, seam * 0.30),
            extrude_height=depth * 1.06,
            axis="z",
            tags=[*list(component.tags), "top_flange", "extruded_duct_flange"],
            rounding=0.02,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx - width * 0.28, cy, cz + depth * 0.52),
            profile_polygon=_chamfered_rect_profile(width * 0.08, height * 0.58, width * 0.02),
            extrude_height=max(depth * 0.08, 0.035),
            axis="z",
            tags=[*list(component.tags), "inspection_seam_a", "extruded_duct_inspection_seam"],
            rounding=0.01,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx + width * 0.28, cy, cz + depth * 0.52),
            profile_polygon=_chamfered_rect_profile(width * 0.08, height * 0.58, width * 0.02),
            extrude_height=max(depth * 0.08, 0.035),
            axis="z",
            tags=[*list(component.tags), "inspection_seam_b", "extruded_duct_inspection_seam"],
            rounding=0.01,
        ),
    ]


def _overhead_conduit_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    radius = component.radius if component.radius is not None else max(min(height, depth) * 0.40, 0.035)
    conduit_length = component.height if component.height is not None else width
    return [
        _round_bar(component.part, component, radius=radius, height=conduit_length, axis=component.axis, tags=[*list(component.tags), "conduit_body", "swept_conduit_body"]),
        _extruded_profile(
            component.part,
            component,
            center=(cx - conduit_length * 0.28 if component.axis == "x" else cx, cy - radius * 1.2, cz),
            profile_polygon=_chamfered_rect_profile(max(conduit_length * 0.05, 0.04), radius * 0.60, radius * 0.10),
            extrude_height=radius * 2.4,
            axis="z",
            tags=[*list(component.tags), "hanger_clamp_a", "extruded_conduit_hanger_clamp"],
            rounding=0.01,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx + conduit_length * 0.28 if component.axis == "x" else cx, cy - radius * 1.2, cz),
            profile_polygon=_chamfered_rect_profile(max(conduit_length * 0.05, 0.04), radius * 0.60, radius * 0.10),
            extrude_height=radius * 2.4,
            axis="z",
            tags=[*list(component.tags), "hanger_clamp_b", "extruded_conduit_hanger_clamp"],
            rounding=0.01,
        ),
    ]


def _drain_channel_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    primitives = [
        _subdivision_box(component.part, component, tags=[*list(component.tags), "drain_trough", "subdivision_drain_trough"], corner_segments=4),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.46, cz),
            profile_polygon=_chamfered_rect_profile(width * 1.04, max(height * 0.12, 0.035), height * 0.03),
            extrude_height=depth * 1.05,
            axis="z",
            tags=[*list(component.tags), "drain_frame", "extruded_drain_frame"],
            rounding=0.02,
        ),
    ]
    grate_count = 5
    for index in range(grate_count):
        x = cx - width * 0.40 + width * 0.80 * (index / max(1, grate_count - 1))
        primitives.append(
            _extruded_profile(
                component.part,
                component,
                center=(x, cy + height * 0.52, cz),
                profile_polygon=_chamfered_rect_profile(max(width * 0.055, 0.03), max(height * 0.10, 0.03), width * 0.01),
                extrude_height=depth * 0.92,
                axis="z",
                tags=[*list(component.tags), "grate_bar", "extruded_drain_grate_bar", f"bar_{index}"],
                rounding=0.01,
            )
        )
    return primitives


def _fire_hydrant_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    radius = component.radius if component.radius is not None else max(min(width, depth) * 0.32, 0.04)
    hydrant_h = component.height if component.height is not None else height
    return [
        _revolved_profile(
            component.part,
            component,
            center=(cx, cy, cz),
            profile_points=[
                (-hydrant_h * 0.50, radius * 0.82),
                (-hydrant_h * 0.36, radius),
                (hydrant_h * 0.32, radius * 0.94),
                (hydrant_h * 0.50, radius * 0.78),
            ],
            axis="y",
            tags=[*list(component.tags), "hydrant_body", "lathed_hydrant_body"],
        ),
        _revolved_profile(
            component.part,
            component,
            center=(cx, cy + hydrant_h * 0.44, cz),
            profile_points=[
                (-max(hydrant_h * 0.06, 0.025), radius * 0.76),
                (0.0, radius * 1.05),
                (max(hydrant_h * 0.06, 0.025), radius * 0.46),
            ],
            axis="y",
            tags=[*list(component.tags), "cap", "lathed_hydrant_cap"],
        ),
        _revolved_profile(
            component.part,
            component,
            center=(cx - radius * 1.40, cy + hydrant_h * 0.10, cz),
            profile_points=[
                (-radius * 0.75, radius * 0.30),
                (0.0, radius * 0.42),
                (radius * 0.75, radius * 0.28),
            ],
            axis="x",
            tags=[*list(component.tags), "left_nozzle", "lathed_hydrant_nozzle"],
        ),
        _revolved_profile(
            component.part,
            component,
            center=(cx + radius * 1.40, cy + hydrant_h * 0.10, cz),
            profile_points=[
                (-radius * 0.75, radius * 0.28),
                (0.0, radius * 0.42),
                (radius * 0.75, radius * 0.30),
            ],
            axis="x",
            tags=[*list(component.tags), "right_nozzle", "lathed_hydrant_nozzle"],
        ),
        _revolved_profile(
            component.part,
            component,
            center=(cx, cy - hydrant_h * 0.48, cz),
            profile_points=[
                (-max(hydrant_h * 0.045, 0.02), radius),
                (0.0, radius * 1.30),
                (max(hydrant_h * 0.045, 0.02), radius),
            ],
            axis="y",
            tags=[*list(component.tags), "base_flange", "lathed_hydrant_base_flange"],
        ),
    ]


def _transformer_box_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    return [
        _subdivision_box(component.part, component, tags=[*list(component.tags), "transformer_cabinet", "subdivision_transformer_cabinet"], corner_segments=4),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.08, cz + depth * 0.52),
            profile_polygon=_chamfered_rect_profile(width * 0.78, height * 0.52, min(width, height) * 0.04),
            extrude_height=max(depth * 0.08, 0.04),
            axis="z",
            tags=[*list(component.tags), "front_access_panel", "extruded_transformer_access_panel"],
            rounding=0.02,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx - width * 0.42, cy + height * 0.08, cz),
            profile_polygon=_chamfered_rect_profile(max(width * 0.08, 0.04), height * 0.56, width * 0.015),
            extrude_height=depth * 0.76,
            axis="z",
            tags=[*list(component.tags), "side_vents", "extruded_transformer_side_vents"],
            rounding=0.01,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.18, cz + depth * 0.58),
            profile_polygon=_chamfered_rect_profile(width * 0.42, height * 0.10, height * 0.02),
            extrude_height=max(depth * 0.07, 0.035),
            axis="z",
            tags=[*list(component.tags), "warning_label", "extruded_transformer_warning_label"],
            rounding=0.01,
        ),
        _subdivision_box(
            component.part,
            component,
            center=(cx, cy - height * 0.46, cz),
            extents=(width * 1.08, max(height * 0.10, 0.05), depth * 1.05),
            tags=[*list(component.tags), "concrete_pad", "subdivision_transformer_pad"],
            corner_segments=3,
        ),
    ]


def _junction_box_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    return [
        _subdivision_box(component.part, component, tags=[*list(component.tags), "junction_body", "subdivision_junction_body"], corner_segments=4),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy, cz + depth * 0.52),
            profile_polygon=_chamfered_rect_profile(width * 0.82, height * 0.72, min(width, height) * 0.04),
            extrude_height=max(depth * 0.08, 0.035),
            axis="z",
            tags=[*list(component.tags), "removable_lid", "extruded_junction_lid"],
            rounding=0.02,
        ),
        _revolved_profile(
            component.part,
            component,
            center=(cx - width * 0.52, cy, cz),
            profile_points=[
                (-max(width * 0.05, 0.02), height * 0.12),
                (0.0, height * 0.16),
                (max(width * 0.05, 0.02), height * 0.12),
            ],
            axis="x",
            tags=[*list(component.tags), "left_port", "lathed_junction_port"],
        ),
        _revolved_profile(
            component.part,
            component,
            center=(cx + width * 0.52, cy, cz),
            profile_points=[
                (-max(width * 0.05, 0.02), height * 0.12),
                (0.0, height * 0.16),
                (max(width * 0.05, 0.02), height * 0.12),
            ],
            axis="x",
            tags=[*list(component.tags), "right_port", "lathed_junction_port"],
        ),
    ]


def _valve_wheel_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    radius = component.radius if component.radius is not None else max(min(width, depth) * 0.36, 0.05)
    wheel_h = component.height if component.height is not None else max(height * 0.10, 0.035)
    return [
        _torus(
            component.part,
            component,
            major_radius=radius * 0.82,
            minor_radius=max(radius * 0.14, wheel_h * 0.50),
            axis=component.axis,
            tags=[*list(component.tags), "wheel_rim", "handwheel_torus"],
        ),
        _revolved_profile(
            component.part,
            component,
            center=(cx, cy, cz),
            profile_points=[
                (-wheel_h * 0.68, radius * 0.18),
                (0.0, radius * 0.26),
                (wheel_h * 0.68, radius * 0.18),
            ],
            axis=component.axis,
            tags=[*list(component.tags), "center_hub", "lathed_valve_hub"],
        ),
        _round_bar(
            component.part,
            component,
            center=(cx, cy, cz),
            radius=max(min(height, depth) * 0.045, 0.012),
            height=radius * 1.70,
            axis="x",
            tags=[*list(component.tags), "horizontal_spoke", "swept_valve_spoke"],
        ),
        _round_bar(
            component.part,
            component,
            center=(cx, cy, cz),
            radius=max(min(width, height) * 0.045, 0.012),
            height=radius * 1.70,
            axis="z",
            tags=[*list(component.tags), "vertical_spoke", "swept_valve_spoke"],
        ),
        _revolved_profile(
            component.part,
            component,
            center=(cx, cy - height * 0.46, cz),
            profile_points=[
                (-max(height * 0.36, 0.04), radius * 0.18),
                (0.0, radius * 0.22),
                (max(height * 0.36, 0.04), radius * 0.18),
            ],
            axis="y",
            tags=[*list(component.tags), "valve_stem", "lathed_valve_stem"],
        ),
    ]


def _manhole_cover_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    radius = component.radius if component.radius is not None else max(min(component.extents[0], component.extents[2]) * 0.45, 0.06)
    cover_h = component.height if component.height is not None else max(component.extents[1], 0.035)
    cx, cy, cz = component.center
    return [
        _revolved_profile(
            component.part,
            component,
            profile_points=[
                (-cover_h * 0.50, radius * 0.92),
                (0.0, radius),
                (cover_h * 0.50, radius * 0.92),
            ],
            axis="y",
            tags=[*list(component.tags), "cover_disc", "lathed_manhole_cover_disc"],
        ),
        _torus(
            component.part,
            component,
            center=(cx, cy + cover_h * 0.40, cz),
            major_radius=radius * 1.00,
            minor_radius=max(cover_h * 0.18, 0.012),
            axis="y",
            tags=[*list(component.tags), "outer_rim", "torus_manhole_outer_rim"],
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + cover_h * 0.70, cz),
            profile_polygon=_chamfered_rect_profile(radius * 1.35, max(cover_h * 0.28, 0.02), cover_h * 0.04),
            extrude_height=radius * 0.16,
            axis="z",
            tags=[*list(component.tags), "access_groove_a", "extruded_manhole_access_groove"],
            blend_mode="subtract",
            rounding=0.01,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + cover_h * 0.70, cz),
            profile_polygon=_chamfered_rect_profile(radius * 0.16, max(cover_h * 0.28, 0.02), cover_h * 0.04),
            extrude_height=radius * 1.35,
            axis="z",
            tags=[*list(component.tags), "access_groove_b", "extruded_manhole_access_groove"],
            blend_mode="subtract",
            rounding=0.01,
        ),
    ]


def _service_rail_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    return [
        _subdivision_box(component.part, component, tags=[*list(component.tags), "rail_body", "subdivision_service_rail"], corner_segments=4),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.38, cz),
            profile_polygon=_chamfered_rect_profile(width, max(height * 0.18, 0.035), height * 0.03),
            extrude_height=depth * 0.42,
            axis="z",
            tags=[*list(component.tags), "top_lip", "extruded_service_rail_lip"],
            rounding=0.02,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy - height * 0.38, cz),
            profile_polygon=_chamfered_rect_profile(width, max(height * 0.18, 0.035), height * 0.03),
            extrude_height=depth * 0.42,
            axis="z",
            tags=[*list(component.tags), "bottom_lip", "extruded_service_rail_lip"],
            rounding=0.02,
        ),
    ]


def _support_bracket_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    return [
        _subdivision_box(component.part, component, tags=[*list(component.tags), "vertical_support", "subdivision_support_vertical"], corner_segments=3),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.35, cz),
            profile_polygon=_chamfered_rect_profile(width * 2.0, max(height * 0.14, 0.035), height * 0.03),
            extrude_height=depth * 1.2,
            axis="z",
            tags=[*list(component.tags), "saddle", "extruded_support_saddle"],
            rounding=0.02,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy - height * 0.48, cz),
            profile_polygon=_chamfered_rect_profile(width * 1.70, max(height * 0.12, 0.035), height * 0.03),
            extrude_height=depth * 1.45,
            axis="z",
            tags=[*list(component.tags), "mount_foot", "extruded_support_mount_foot"],
            rounding=0.02,
        ),
    ]


def _cable_tray_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    primitives = [
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy - height * 0.22, cz),
            profile_polygon=_chamfered_rect_profile(width, max(height * 0.18, 0.035), height * 0.03),
            extrude_height=depth,
            axis="z",
            tags=[*list(component.tags), "tray_floor", "extruded_cable_tray_floor"],
            rounding=0.02,
        ),
        _subdivision_box(
            component.part,
            component,
            center=(cx, cy + height * 0.10, cz - depth * 0.46),
            extents=(width, height * 0.62, max(depth * 0.10, 0.035)),
            tags=[*list(component.tags), "left_sidewall", "subdivision_cable_tray_sidewall"],
            corner_segments=3,
        ),
        _subdivision_box(
            component.part,
            component,
            center=(cx, cy + height * 0.10, cz + depth * 0.46),
            extents=(width, height * 0.62, max(depth * 0.10, 0.035)),
            tags=[*list(component.tags), "right_sidewall", "subdivision_cable_tray_sidewall"],
            corner_segments=3,
        ),
    ]
    for index, z_offset in enumerate((-0.20, 0.0, 0.20)):
        primitives.append(
            _round_bar(
                component.part,
                component,
                center=(cx, cy + height * 0.04, cz + depth * z_offset),
                radius=max(height * 0.08, 0.025),
                height=width * 0.92,
                axis="x",
                tags=[*list(component.tags), "bundled_cable", "swept_cable_bundle", f"cable_{index}"],
            )
        )
    return primitives


def _access_base_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    return [
        _subdivision_box(component.part, component, tags=[*list(component.tags), "access_floor_slab", "subdivision_access_base"], corner_segments=4),
        _extruded_profile(
            component.part,
            component,
            center=(cx - width * 0.36, cy + height * 0.44, cz - depth * 0.32),
            profile_polygon=_chamfered_rect_profile(width * 0.18, max(height * 0.24, 0.035), height * 0.04),
            extrude_height=depth * 0.18,
            axis="z",
            tags=[*list(component.tags), "anchor_pad_a", "extruded_access_anchor_pad"],
            rounding=0.02,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx + width * 0.36, cy + height * 0.44, cz + depth * 0.32),
            profile_polygon=_chamfered_rect_profile(width * 0.18, max(height * 0.24, 0.035), height * 0.04),
            extrude_height=depth * 0.18,
            axis="z",
            tags=[*list(component.tags), "anchor_pad_b", "extruded_access_anchor_pad"],
            rounding=0.02,
        ),
    ]


def _catwalk_deck_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    primitives = [
        _subdivision_box(component.part, component, tags=[*list(component.tags), "deck_frame", "subdivision_catwalk_deck"], corner_segments=4),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy - height * 0.44, cz),
            profile_polygon=_chamfered_rect_profile(width, max(height * 0.22, 0.035), height * 0.03),
            extrude_height=depth * 0.18,
            axis="z",
            tags=[*list(component.tags), "center_spine", "extruded_catwalk_center_spine"],
            rounding=0.02,
        ),
    ]
    grate_count = 7
    for index in range(grate_count):
        x = cx - width * 0.42 + width * 0.84 * (index / max(1, grate_count - 1))
        primitives.append(
            _extruded_profile(
                component.part,
                component,
                center=(x, cy + height * 0.24, cz),
                profile_polygon=_chamfered_rect_profile(max(width * 0.045, 0.03), max(height * 0.12, 0.025), width * 0.01),
                extrude_height=depth * 0.92,
                axis="z",
                tags=[*list(component.tags), "grate_bar", "extruded_catwalk_grate_bar", f"grate_{index}"],
                rounding=0.01,
            )
        )
    return primitives


def _walkway_span_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    return [
        _subdivision_box(component.part, component, tags=[*list(component.tags), "walkway_deck", "subdivision_walkway_deck"], corner_segments=3),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy - height * 0.42, cz - depth * 0.42),
            profile_polygon=_chamfered_rect_profile(width, max(height * 0.22, 0.035), height * 0.03),
            extrude_height=depth * 0.18,
            axis="z",
            tags=[*list(component.tags), "left_side_beam", "extruded_walkway_side_beam"],
            rounding=0.02,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy - height * 0.42, cz + depth * 0.42),
            profile_polygon=_chamfered_rect_profile(width, max(height * 0.22, 0.035), height * 0.03),
            extrude_height=depth * 0.18,
            axis="z",
            tags=[*list(component.tags), "right_side_beam", "extruded_walkway_side_beam"],
            rounding=0.02,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx - width * 0.24, cy - height * 0.14, cz),
            profile_polygon=_chamfered_rect_profile(width * 0.06, height * 0.42, width * 0.01),
            extrude_height=depth * 1.04,
            axis="z",
            tags=[*list(component.tags), "cross_tie_a", "extruded_walkway_cross_tie"],
            rounding=0.01,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx + width * 0.24, cy - height * 0.14, cz),
            profile_polygon=_chamfered_rect_profile(width * 0.06, height * 0.42, width * 0.01),
            extrude_height=depth * 1.04,
            axis="z",
            tags=[*list(component.tags), "cross_tie_b", "extruded_walkway_cross_tie"],
            rounding=0.01,
        ),
    ]


def _guardrail_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    post_w = max(width * 0.07, 0.035)
    rail_h = max(height * 0.08, 0.025)
    return [
        _round_bar(
            component.part,
            component,
            center=(cx - width * 0.44, cy, cz),
            radius=post_w * 0.50,
            height=height,
            axis="y",
            tags=[*list(component.tags), "left_post", "swept_guardrail_post"],
        ),
        _round_bar(
            component.part,
            component,
            center=(cx + width * 0.44, cy, cz),
            radius=post_w * 0.50,
            height=height,
            axis="y",
            tags=[*list(component.tags), "right_post", "swept_guardrail_post"],
        ),
        _round_bar(
            component.part,
            component,
            center=(cx, cy + height * 0.38, cz),
            radius=rail_h * 0.50,
            height=width,
            axis="x",
            tags=[*list(component.tags), "top_rail", "swept_guardrail_rail"],
        ),
        _round_bar(
            component.part,
            component,
            center=(cx, cy + height * 0.02, cz),
            radius=rail_h * 0.50,
            height=width,
            axis="x",
            tags=[*list(component.tags), "mid_rail", "swept_guardrail_rail"],
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy - height * 0.32, cz),
            profile_polygon=_chamfered_rect_profile(width * 0.96, rail_h, rail_h * 0.22),
            extrude_height=depth,
            axis="z",
            tags=[*list(component.tags), "kick_plate", "extruded_guardrail_kick_plate"],
            rounding=0.01,
        ),
    ]


def _access_ladder_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    rail_w = max(width * 0.16, 0.035)
    primitives = [
        _round_bar(
            component.part,
            component,
            center=(cx - width * 0.36, cy, cz),
            radius=rail_w * 0.50,
            height=height,
            axis="y",
            tags=[*list(component.tags), "left_side_rail", "swept_ladder_side_rail"],
        ),
        _round_bar(
            component.part,
            component,
            center=(cx + width * 0.36, cy, cz),
            radius=rail_w * 0.50,
            height=height,
            axis="y",
            tags=[*list(component.tags), "right_side_rail", "swept_ladder_side_rail"],
        ),
    ]
    rung_count = 6
    for index in range(rung_count):
        y = cy - height * 0.38 + height * 0.76 * (index / max(1, rung_count - 1))
        primitives.append(
            _round_bar(
                component.part,
                component,
                center=(cx, y, cz),
                radius=max(height * 0.018, 0.018),
                height=width * 0.82,
                axis="x",
                tags=[*list(component.tags), "rung", "swept_ladder_rung", f"rung_{index}"],
            )
        )
    return primitives


def _access_ramp_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    primitives = [
        _subdivision_box(component.part, component, tags=[*list(component.tags), "ramp_slab", "subdivision_access_ramp"], corner_segments=3),
        _extruded_profile(component.part, component, center=(cx, cy + height * 0.42, cz - depth * 0.45), profile_polygon=_chamfered_rect_profile(width, max(height * 0.12, 0.035), height * 0.03), extrude_height=depth * 0.12, axis="z", tags=[*list(component.tags), "left_lip", "extruded_access_ramp_lip"], rounding=0.02),
        _extruded_profile(component.part, component, center=(cx, cy + height * 0.42, cz + depth * 0.45), profile_polygon=_chamfered_rect_profile(width, max(height * 0.12, 0.035), height * 0.03), extrude_height=depth * 0.12, axis="z", tags=[*list(component.tags), "right_lip", "extruded_access_ramp_lip"], rounding=0.02),
    ]
    tread_count = 5
    for index in range(tread_count):
        x = cx - width * 0.36 + width * 0.72 * (index / max(1, tread_count - 1))
        primitives.append(
            _extruded_profile(
                component.part,
                component,
                center=(x, cy + height * 0.48, cz),
                profile_polygon=_chamfered_rect_profile(max(width * 0.055, 0.03), max(height * 0.08, 0.025), width * 0.01),
                extrude_height=depth * 0.82,
                axis="z",
                tags=[*list(component.tags), "anti_slip_tread", "extruded_access_ramp_tread", f"tread_{index}"],
                rounding=0.01,
            )
        )
    return primitives


def _gantry_frame_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    post = max(min(width, depth) * 0.10, 0.04)
    return [
        _round_bar(component.part, component, center=(cx - width * 0.44, cy, cz - depth * 0.38), radius=post * 0.50, height=height, axis="y", tags=[*list(component.tags), "front_left_upright", "swept_gantry_upright"]),
        _round_bar(component.part, component, center=(cx + width * 0.44, cy, cz - depth * 0.38), radius=post * 0.50, height=height, axis="y", tags=[*list(component.tags), "front_right_upright", "swept_gantry_upright"]),
        _round_bar(component.part, component, center=(cx - width * 0.44, cy, cz + depth * 0.38), radius=post * 0.50, height=height, axis="y", tags=[*list(component.tags), "rear_left_upright", "swept_gantry_upright"]),
        _round_bar(component.part, component, center=(cx + width * 0.44, cy, cz + depth * 0.38), radius=post * 0.50, height=height, axis="y", tags=[*list(component.tags), "rear_right_upright", "swept_gantry_upright"]),
        _round_bar(component.part, component, center=(cx, cy + height * 0.46, cz - depth * 0.38), radius=max(height * 0.04, 0.018), height=width, axis="x", tags=[*list(component.tags), "front_crossbeam", "swept_gantry_crossbeam"]),
        _round_bar(component.part, component, center=(cx, cy + height * 0.46, cz + depth * 0.38), radius=max(height * 0.04, 0.018), height=width, axis="x", tags=[*list(component.tags), "rear_crossbeam", "swept_gantry_crossbeam"]),
        _extruded_profile(component.part, component, center=(cx, cy, cz), profile_polygon=_chamfered_rect_profile(width * 0.92, max(height * 0.055, 0.03), height * 0.01), extrude_height=depth * 0.08, axis="z", tags=[*list(component.tags), "diagonal_brace", "extruded_gantry_diagonal_brace"], rounding=0.01),
    ]


def _elevator_shaft_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    frame = max(width * 0.10, 0.04)
    return [
        _subdivision_box(component.part, component, tags=[*list(component.tags), "shaft_volume", "subdivision_elevator_shaft"], corner_segments=3),
        _extruded_profile(component.part, component, center=(cx, cy, cz + depth * 0.52), profile_polygon=_chamfered_rect_profile(width * 0.66, height * 0.72, min(width, height) * 0.03), extrude_height=max(depth * 0.08, 0.04), axis="z", tags=[*list(component.tags), "landing_door", "extruded_elevator_landing_door"], rounding=0.01),
        _extruded_profile(component.part, component, center=(cx - width * 0.38, cy, cz + depth * 0.56), profile_polygon=_chamfered_rect_profile(frame, height * 0.92, frame * 0.20), extrude_height=max(depth * 0.06, 0.035), axis="z", tags=[*list(component.tags), "left_guide_rail", "extruded_elevator_guide_rail"], rounding=0.01),
        _extruded_profile(component.part, component, center=(cx + width * 0.38, cy, cz + depth * 0.56), profile_polygon=_chamfered_rect_profile(frame, height * 0.92, frame * 0.20), extrude_height=max(depth * 0.06, 0.035), axis="z", tags=[*list(component.tags), "right_guide_rail", "extruded_elevator_guide_rail"], rounding=0.01),
        _subdivision_box(component.part, component, center=(cx, cy - height * 0.12, cz), extents=(width * 0.72, height * 0.30, depth * 0.64), tags=[*list(component.tags), "lift_cabin", "subdivision_lift_cabin"], corner_segments=4),
    ]


def _access_platform_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    return [
        _subdivision_box(component.part, component, tags=[*list(component.tags), "platform_deck", "subdivision_access_platform"], corner_segments=4),
        _extruded_profile(component.part, component, center=(cx, cy - height * 0.42, cz), profile_polygon=_chamfered_rect_profile(width * 1.05, max(height * 0.22, 0.035), height * 0.03), extrude_height=depth * 0.14, axis="z", tags=[*list(component.tags), "front_truss", "extruded_access_platform_truss"], rounding=0.02),
        _extruded_profile(component.part, component, center=(cx, cy - height * 0.42, cz), profile_polygon=_chamfered_rect_profile(width * 0.14, max(height * 0.22, 0.035), width * 0.03), extrude_height=depth * 1.05, axis="z", tags=[*list(component.tags), "side_truss", "extruded_access_platform_truss"], rounding=0.02),
        _extruded_profile(component.part, component, center=(cx + width * 0.34, cy + height * 0.42, cz + depth * 0.34), profile_polygon=_chamfered_rect_profile(width * 0.16, max(height * 0.20, 0.035), width * 0.03), extrude_height=depth * 0.16, axis="z", tags=[*list(component.tags), "mount_pad", "extruded_access_platform_mount_pad"], rounding=0.02),
    ]


def _tunnel_segment_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    wall = max(width * 0.08, 0.05)
    return [
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy - height * 0.42, cz),
            profile_polygon=_chamfered_rect_profile(width, max(height * 0.16, 0.05), height * 0.03),
            extrude_height=depth,
            axis="z",
            tags=[*list(component.tags), "floor_plate", "extruded_tunnel_floor"],
            rounding=0.02,
        ),
        _subdivision_box(
            component.part,
            component,
            center=(cx - width * 0.46, cy, cz),
            extents=(wall, height, depth),
            tags=[*list(component.tags), "left_wall", "subdivision_tunnel_wall"],
            corner_segments=3,
        ),
        _subdivision_box(
            component.part,
            component,
            center=(cx + width * 0.46, cy, cz),
            extents=(wall, height, depth),
            tags=[*list(component.tags), "right_wall", "subdivision_tunnel_wall"],
            corner_segments=3,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.46, cz),
            profile_polygon=[
                (-width * 0.50, -height * 0.06),
                (width * 0.50, -height * 0.06),
                (width * 0.36, height * 0.10),
                (-width * 0.36, height * 0.10),
            ],
            extrude_height=depth,
            axis="z",
            tags=[*list(component.tags), "roof_plate", "extruded_tunnel_roof"],
            rounding=0.02,
        ),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.22, cz + depth * 0.48),
            profile_polygon=_chamfered_rect_profile(width * 0.62, height * 0.10, height * 0.02),
            extrude_height=max(depth * 0.10, 0.035),
            axis="z",
            tags=[*list(component.tags), "light_strip", "extruded_tunnel_light_strip"],
            rounding=0.01,
        ),
    ]


def _scaffold_frame_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    post = max(min(width, depth) * 0.10, 0.035)
    return [
        _round_bar(component.part, component, center=(cx - width * 0.42, cy, cz - depth * 0.38), radius=post * 0.50, height=height, axis="y", tags=[*list(component.tags), "front_left_pole", "swept_scaffold_pole"]),
        _round_bar(component.part, component, center=(cx + width * 0.42, cy, cz - depth * 0.38), radius=post * 0.50, height=height, axis="y", tags=[*list(component.tags), "front_right_pole", "swept_scaffold_pole"]),
        _round_bar(component.part, component, center=(cx - width * 0.42, cy, cz + depth * 0.38), radius=post * 0.50, height=height, axis="y", tags=[*list(component.tags), "rear_left_pole", "swept_scaffold_pole"]),
        _round_bar(component.part, component, center=(cx + width * 0.42, cy, cz + depth * 0.38), radius=post * 0.50, height=height, axis="y", tags=[*list(component.tags), "rear_right_pole", "swept_scaffold_pole"]),
        _round_bar(component.part, component, center=(cx, cy + height * 0.24, cz), radius=max(height * 0.03, 0.015), height=width, axis="x", tags=[*list(component.tags), "upper_crossbar", "swept_scaffold_crossbar"]),
        _round_bar(component.part, component, center=(cx, cy - height * 0.18, cz), radius=max(height * 0.03, 0.015), height=width, axis="x", tags=[*list(component.tags), "lower_crossbar", "swept_scaffold_crossbar"]),
        _extruded_profile(component.part, component, center=(cx, cy, cz), profile_polygon=_chamfered_rect_profile(width * 0.86, max(height * 0.05, 0.03), height * 0.01), extrude_height=depth * 0.08, axis="z", tags=[*list(component.tags), "diagonal_brace", "extruded_scaffold_diagonal_brace"], rounding=0.01),
    ]


def _safety_gate_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    frame_w = max(width * 0.10, 0.04)
    return [
        _subdivision_box(component.part, component, tags=[*list(component.tags), "gate_panel", "subdivision_safety_gate_panel"], corner_segments=3),
        _round_bar(component.part, component, center=(cx - width * 0.44, cy, cz), radius=frame_w * 0.50, height=height, axis="y", tags=[*list(component.tags), "hinge_post", "swept_safety_gate_post"]),
        _round_bar(component.part, component, center=(cx + width * 0.44, cy, cz), radius=frame_w * 0.50, height=height, axis="y", tags=[*list(component.tags), "latch_post", "swept_safety_gate_post"]),
        _round_bar(component.part, component, center=(cx, cy + height * 0.36, cz + depth * 0.14), radius=max(height * 0.04, 0.018), height=width, axis="x", tags=[*list(component.tags), "top_bar", "swept_safety_gate_bar"]),
        _round_bar(component.part, component, center=(cx, cy, cz + depth * 0.18), radius=max(height * 0.03, 0.014), height=width * 0.78, axis="x", tags=[*list(component.tags), "middle_bar", "swept_safety_gate_bar"]),
        _round_bar(component.part, component, center=(cx + width * 0.30, cy - height * 0.02, cz + depth * 0.48), radius=max(min(width, height) * 0.035, 0.012), height=width * 0.14, axis="x", tags=[*list(component.tags), "latch_handle", "swept_safety_gate_latch_handle"]),
    ]


def _access_support_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    radius = component.radius if component.radius is not None else max(min(width, depth) * 0.38, 0.04)
    support_h = component.height if component.height is not None else height
    cx, cy, cz = component.center
    return [
        _revolved_profile(
            component.part,
            component,
            profile_points=[
                (-support_h * 0.50, radius * 0.88),
                (-support_h * 0.38, radius),
                (support_h * 0.38, radius * 0.92),
                (support_h * 0.50, radius * 0.78),
            ],
            axis="y",
            tags=[*list(component.tags), "support_column", "lathed_access_support_column"],
        ),
        _revolved_profile(
            component.part,
            component,
            center=(cx, cy - support_h * 0.48, cz),
            profile_points=[
                (-max(height * 0.04, 0.02), radius * 1.18),
                (0.0, radius * 1.65),
                (max(height * 0.04, 0.02), radius * 1.22),
            ],
            axis="y",
            tags=[*list(component.tags), "base_plate", "lathed_access_support_base_plate"],
        ),
        _revolved_profile(
            component.part,
            component,
            center=(cx, cy + support_h * 0.48, cz),
            profile_points=[
                (-max(height * 0.04, 0.02), radius),
                (0.0, radius * 1.38),
                (max(height * 0.04, 0.02), radius * 1.02),
            ],
            axis="y",
            tags=[*list(component.tags), "top_plate", "lathed_access_support_top_plate"],
        ),
    ]


def _lot_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    return [
        _subdivision_box(component.part, component, tags=[*list(component.tags), "lot_footprint", "subdivision_lot_footprint"], corner_segments=3),
        _extruded_profile(
            component.part,
            component,
            center=(cx, cy + height * 0.42, cz),
            profile_polygon=_chamfered_rect_profile(width * 0.76, max(height * 0.18, 0.10), height * 0.04),
            extrude_height=depth * 0.76,
            axis="z",
            tags=[*list(component.tags), "buildable_pad", "extruded_lot_buildable_pad"],
            rounding=0.02,
        ),
    ]


_COMPONENT_BUILDERS: dict[str, Callable[[BlueprintComponent], list[ShapePrimitive]]] = {
    "shell": _shell_primitives,
    "body": _shell_primitives,
    "panel": _panel_primitives,
    "frame": _frame_primitives,
    "lid": _lid_primitives,
    "door": _door_primitives,
    "hinge": _hinge_primitives,
    "latch": _latch_primitives,
    "lock_plate": _lock_plate_primitives,
    "handle": _handle_primitives,
    "foot": _foot_primitives,
    "stand": _stand_primitives,
    "bracket": _bracket_primitives,
    "bezel": _bezel_primitives,
    "vent": _vent_primitives,
    "grille": _vent_primitives,
    "rotor_arm": _rotor_arm_primitives,
    "rotor_pod": _rotor_pod_primitives,
    "blade": _blade_primitives,
    "blade_tip": _blade_tip_primitives,
    "fuller": _fuller_primitives,
    "guard": _guard_primitives,
    "grip": _grip_primitives,
    "pommel": _pommel_primitives,
    "weapon_body": _weapon_body_primitives,
    "barrel": _barrel_primitives,
    "stock": _stock_primitives,
    "magazine": _magazine_primitives,
    "sight": _sight_primitives,
    "trigger": _trigger_primitives,
    "tool_head": _tool_head_primitives,
    "socket_plate": _plate_primitives,
    "anchor_plate": _plate_primitives,
    "hardpoint": _hardpoint_primitives,
    "module_socket": _hardpoint_primitives,
    "crew_bay": _crew_bay_primitives,
    "cargo_bay": _cargo_bay_primitives,
    "thruster": _thruster_primitives,
    "antenna": _antenna_primitives,
    "stabilizer": _stabilizer_primitives,
    "roof": _roof_primitives,
    "roof_ridge": _roof_ridge_primitives,
    "dome": _dome_primitives,
    "window": _window_primitives,
    "arch": _arch_primitives,
    "balcony": _balcony_primitives,
    "awning": _awning_primitives,
    "cornice": _cornice_primitives,
    "parapet": _parapet_primitives,
    "dormer": _dormer_primitives,
    "chimney": _chimney_primitives,
    "column": _column_primitives,
    "tower": _tower_primitives,
    "stair": _stair_primitives,
    "stair_core": _stair_core_primitives,
    "chassis": _chassis_primitives,
    "cabin": _cabin_primitives,
    "wheel": _wheel_primitives,
    "hull": _hull_primitives,
    "deck": _deck_primitives,
    "mast": _mast_primitives,
    "engine": _engine_primitives,
    "pontoon": _pontoon_primitives,
    "outrigger": _outrigger_primitives,
    "sail": _sail_primitives,
    "rigging": _rigging_primitives,
    "cargo_hold": _cargo_hold_primitives,
    "rudder": _rudder_primitives,
    "propeller": _propeller_primitives,
    "anchor": _anchor_primitives,
    "track": _track_primitives,
    "suspension": _suspension_primitives,
    "cargo_module": _cargo_module_primitives,
    "turret": _turret_primitives,
    "wing": _wing_primitives,
    "manipulator_arm": _manipulator_arm_primitives,
    "machine_base": _machine_base_primitives,
    "machine_column": _machine_column_primitives,
    "hydraulic_piston": _hydraulic_piston_primitives,
    "conveyor": _conveyor_primitives,
    "gear": _gear_primitives,
    "tank": _tank_primitives,
    "crane_boom": _crane_boom_primitives,
    "road": _road_primitives,
    "street": _road_primitives,
    "path": _road_primitives,
    "road_branch": _road_primitives,
    "road_junction": _road_junction_primitives,
    "crosswalk": _crosswalk_primitives,
    "turnout": _turnout_primitives,
    "roundabout": _roundabout_primitives,
    "median": _median_primitives,
    "curb_ramp": _curb_ramp_primitives,
    "lane_arrow": _lane_arrow_primitives,
    "stop_line": _stop_line_primitives,
    "bridge": _bridge_primitives,
    "railing": _railing_primitives,
    "terrain": _terrain_primitives,
    "ground": _terrain_primitives,
    "ridge": _terrain_ridge_primitives,
    "cliff": _terrain_cliff_primitives,
    "clearing": _terrain_clearing_primitives,
    "terrain_platform": _terrain_platform_primitives,
    "water": _terrain_water_primitives,
    "room": _room_primitives,
    "interior": _room_primitives,
    "room_cell": _room_cell_primitives,
    "corridor": _corridor_primitives,
    "partition": _partition_primitives,
    "ceiling_light": _ceiling_light_primitives,
    "alcove": _alcove_primitives,
    "furniture_base": _furniture_base_primitives,
    "chair_seat": _chair_seat_primitives,
    "chair_back": _chair_back_primitives,
    "furniture_leg": _furniture_leg_primitives,
    "table_top": _table_top_primitives,
    "bed_frame": _bed_frame_primitives,
    "shelf_unit": _shelf_unit_primitives,
    "cabinet_body": _cabinet_body_primitives,
    "drawer": _drawer_primitives,
    "cushion": _cushion_primitives,
    "counter_top": _counter_top_primitives,
    "appliance_body": _appliance_body_primitives,
    "lamp": _lamp_primitives,
    "foliage_ground": _foliage_ground_primitives,
    "tree_trunk": _tree_trunk_primitives,
    "root": _root_primitives,
    "tree_branch": _tree_branch_primitives,
    "leaf_cluster": _leaf_cluster_primitives,
    "bush": _bush_primitives,
    "grass_clump": _grass_clump_primitives,
    "natural_rock": _natural_rock_primitives,
    "mushroom": _mushroom_primitives,
    "fallen_log": _fallen_log_primitives,
    "vine": _vine_primitives,
    "flower": _flower_primitives,
    "planter": _planter_primitives,
    "urban_base": _urban_base_primitives,
    "fence_segment": _fence_segment_primitives,
    "gate_panel": _gate_panel_primitives,
    "sign_post": _sign_post_primitives,
    "streetlight": _streetlight_primitives,
    "street_bench": _street_bench_primitives,
    "trash_bin": _trash_bin_primitives,
    "utility_pole": _utility_pole_primitives,
    "cable_span": _cable_span_primitives,
    "kiosk_body": _kiosk_body_primitives,
    "market_stall": _market_stall_primitives,
    "street_barrier": _street_barrier_primitives,
    "street_crate": _street_crate_primitives,
    "bollard": _bollard_primitives,
    "infrastructure_base": _infrastructure_base_primitives,
    "pipe_run": _pipe_run_primitives,
    "duct_run": _duct_run_primitives,
    "overhead_conduit": _overhead_conduit_primitives,
    "drain_channel": _drain_channel_primitives,
    "fire_hydrant": _fire_hydrant_primitives,
    "transformer_box": _transformer_box_primitives,
    "junction_box": _junction_box_primitives,
    "valve_wheel": _valve_wheel_primitives,
    "manhole_cover": _manhole_cover_primitives,
    "service_rail": _service_rail_primitives,
    "support_bracket": _support_bracket_primitives,
    "cable_tray": _cable_tray_primitives,
    "access_base": _access_base_primitives,
    "catwalk_deck": _catwalk_deck_primitives,
    "walkway_span": _walkway_span_primitives,
    "guardrail": _guardrail_primitives,
    "access_ladder": _access_ladder_primitives,
    "access_ramp": _access_ramp_primitives,
    "gantry_frame": _gantry_frame_primitives,
    "elevator_shaft": _elevator_shaft_primitives,
    "access_platform": _access_platform_primitives,
    "tunnel_segment": _tunnel_segment_primitives,
    "scaffold_frame": _scaffold_frame_primitives,
    "safety_gate": _safety_gate_primitives,
    "access_support": _access_support_primitives,
    "lot": _lot_primitives,
    "city_block": _lot_primitives,
}


def _unsupported_component_error(component_type: str) -> ValueError:
    return ValueError(f"Unsupported assembly component '{component_type}'")


def _missing_box_extents_error(primitive: ShapePrimitive) -> ContractViolation:
    return ContractViolation(
        f"invariant violation: box ShapePrimitive requires extents, got None (part={primitive.part!r})"
    )


def _missing_non_box_dimensions_error(primitive: ShapePrimitive) -> ContractViolation:
    return ContractViolation(
        "invariant violation: non-box ShapePrimitive requires radius and height, "
        f"got radius={primitive.radius!r}, height={primitive.height!r} "
        f"(part={primitive.part!r})"
    )


def _unsupported_mirror_axis_error(axis: str) -> ValueError:
    return ValueError(f"Unsupported mirror axis '{axis}'")


def _component_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    if component.component_type not in _COMPONENT_BUILDERS:
        raise _unsupported_component_error(component.component_type)
    primitives = _COMPONENT_BUILDERS[component.component_type](component)
    return _attach_component_metadata(primitives, component)


def _attach_component_metadata(
    primitives: list[ShapePrimitive],
    component: BlueprintComponent,
) -> list[ShapePrimitive]:
    base_payload: dict[str, Any] = {
        "name": component.name,
        "component_type": component.component_type,
        "part": component.part,
        "tags": list(component.tags),
    }
    if component.interface_role:
        base_payload["interface_role"] = component.interface_role
    if component.metadata:
        base_payload.update(dict(component.metadata))
    for primitive in primitives:
        metadata = dict(primitive.semantic_metadata) if isinstance(primitive.semantic_metadata, dict) else {}
        metadata["assembly_component"] = {
            **dict(metadata.get("assembly_component") or {}),
            **base_payload,
        }
        if component.metadata.get("source"):
            metadata["component_source"] = str(component.metadata.get("source"))
        if component.metadata.get("cga"):
            metadata["cga_rule_component"] = dict(component.metadata.get("cga") or {})
        primitive.semantic_metadata = metadata
    return primitives


_MAX_AUTHORED_COMPONENTS = 24
_ASSEMBLY_RULE_COMPONENT_KEYS = {
    "anchors",
    "connectors",
    "inserts",
    "modules",
    "mounts",
    "output_ports",
    "repeat_modules",
    "slots",
    "variant_slots",
}


def _slug_fragment(value: str) -> str:
    lowered = value.lower()
    chars: list[str] = []
    previous_was_separator = False
    for char in lowered:
        if char.isalnum():
            chars.append(char)
            previous_was_separator = False
            continue
        if not previous_was_separator:
            chars.append("_")
            previous_was_separator = True
    slug = "".join(chars).strip("_")
    return slug[:48] if slug else "component"


def _iter_text_fragments(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        fragment = value.strip()
        return (fragment,) if fragment else ()
    if isinstance(value, list):
        fragments: list[str] = []
        for entry in value:
            fragments.extend(_iter_text_fragments(entry))
        return tuple(fragments)
    if isinstance(value, dict):
        # Walk values only. Dict keys here are structural field names
        # (e.g. "repair_policy", "interface_role", "node_type") from resolved
        # component records — they are not authoring fragments and must not
        # be matched against the world-template token vocabulary.
        fragments: list[str] = []
        for key in sorted(value.keys(), key=str):
            fragments.extend(_iter_text_fragments(value[key]))
        return tuple(fragments)
    return ()


def _component_type_from_source(fragment: str) -> str | None:
    token = _slug_fragment(fragment)
    if token in _COMPONENT_BUILDERS:
        return token
    aliases: tuple[tuple[tuple[str, ...], str], ...] = (
        (("roof", "gable"), "roof"),
        (("roof_ridge", "roofline", "ridge_cap"), "roof_ridge"),
        (("window", "glass"), "window"),
        (("door", "hatch"), "door"),
        (("arch", "archway"), "arch"),
        (("column", "pillar"), "column"),
        (("tower",), "tower"),
        (("stair", "step"), "stair"),
        (("road", "street", "path"), "road"),
        (("junction", "intersection"), "road_junction"),
        (("bridge", "span"), "bridge"),
        (("rail", "railing"), "railing"),
        (("terrain", "ground"), "terrain"),
        (("ridge",), "ridge"),
        (("cliff",), "cliff"),
        (("water", "pond", "river"), "water"),
        (("chassis",), "chassis"),
        (("cabin",), "cabin"),
        (("wheel", "tire"), "wheel"),
        (("hull",), "hull"),
        (("deck",), "deck"),
        (("mast",), "mast"),
        (("sail",), "sail"),
        (("engine", "motor"), "engine"),
        (("propeller", "prop"), "propeller"),
        (("barrel", "muzzle"), "barrel"),
        (("blade",), "blade"),
        (("spine", "fin"), "stabilizer"),
        (("sensor_pod", "pod"), "rotor_pod"),
        (("power_cell", "power_core"), "module_socket"),
        (("shield_plate", "armor_plate"), "socket_plate"),
        (("guard_bar", "guardrail"), "guardrail"),
        (("guard_cowl", "cowl"), "guard"),
        (("guard",), "guard"),
        (("grip", "handle"), "grip"),
        (("stock",), "stock"),
        (("magazine",), "magazine"),
        (("tree_trunk", "trunk"), "tree_trunk"),
        (("branch",), "tree_branch"),
        (("leaf", "canopy"), "leaf_cluster"),
        (("bush",), "bush"),
        (("grass",), "grass_clump"),
        (("rock", "boulder"), "natural_rock"),
        (("mushroom",), "mushroom"),
        (("vine",), "vine"),
        (("flower",), "flower"),
        (("pipe",), "pipe_run"),
        (("duct",), "duct_run"),
        (("conduit",), "overhead_conduit"),
        (("cable",), "cable_span"),
        (("hydrant",), "fire_hydrant"),
        (("transformer",), "transformer_box"),
        (("junction_box",), "junction_box"),
        (("ladder",), "access_ladder"),
        (("ramp",), "access_ramp"),
        (("gantry",), "gantry_frame"),
        (("scaffold",), "scaffold_frame"),
        (("gate",), "gate_panel"),
        (("fence",), "fence_segment"),
        (("streetlight", "lamp_post"), "streetlight"),
        (("bench",), "street_bench"),
        (("trash", "bin"), "trash_bin"),
        (("kiosk",), "kiosk_body"),
        (("market", "stall"), "market_stall"),
    )
    for tokens, component_type in aliases:
        if any(part in token for part in tokens):
            return component_type
    return None


def _component_types_from_source(fragment: str) -> tuple[str, ...]:
    token = _slug_fragment(fragment)
    tokens = set(token.split("_"))
    if token in _COMPONENT_BUILDERS:
        return (token,)
    explicit_components: list[str] = []
    explicit_aliases: tuple[tuple[tuple[str, ...], str], ...] = (
        (("shell", "body"), "shell"),
        (("panel", "plate"), "panel"),
        (("frame",), "frame"),
        (("bezel", "screen"), "bezel"),
        (("vent", "grille", "louver"), "vent"),
        (("mount", "hardpoint"), "hardpoint"),
        (("socket", "module"), "module_socket"),
        (("rail",), "railing"),
        (("guard",), "guard"),
    )
    for alias_tokens, component_type in explicit_aliases:
        if tokens & set(alias_tokens) and component_type not in explicit_components:
            explicit_components.append(component_type)
    if explicit_components:
        return tuple(explicit_components)
    if (
        {"district", "neighborhood", "settlement", "village", "town", "city", "plaza", "square"} & tokens
        or {"city", "block"} <= tokens
        or {"market", "district"} <= tokens
    ):
        return ("city_block", "road", "road_junction", "streetlight", "market_stall", "kiosk_body")
    if (
        {"world", "biome", "landscape", "terrain", "environment", "wilderness"} & tokens
        or {"open", "world"} <= tokens
    ):
        return ("terrain", "ridge", "cliff", "clearing", "water", "tree_trunk", "leaf_cluster")
    if (
        {"harbor", "harbour", "dock", "dockyard", "marina", "waterfront", "pier"} & tokens
        or {"boat", "dock"} <= tokens
        or {"water", "vehicle"} <= tokens
    ):
        return ("water", "terrain_platform", "bridge", "hull", "deck", "mast", "market_stall")
    if (
        {"utility", "infrastructure", "industrial", "service", "network"} & tokens
        or {"utility", "network"} <= tokens
        or {"service", "network"} <= tokens
    ):
        return ("infrastructure_base", "pipe_run", "duct_run", "overhead_conduit", "transformer_box", "junction_box")
    if (
        {"access", "traversal", "maintenance"} & tokens
        or {"service", "walkway"} <= tokens
        or {"access", "platform"} <= tokens
    ):
        return ("access_base", "walkway_span", "catwalk_deck", "guardrail", "access_ladder", "access_ramp")
    if (
        {"navigation", "navmesh", "pathfinding", "route", "waypoint", "roadmap"} & tokens
        or {"route", "network"} <= tokens
        or {"navigation", "mesh"} <= tokens
        or {"world", "map"} <= tokens
        or {"level", "layout"} <= tokens
    ):
        return ("road", "road_junction", "lane_arrow", "stop_line", "crosswalk", "curb_ramp", "sign_post", "streetlight")
    if (
        {"airport", "spaceport", "runway", "hangar"} & tokens
        or {"landing", "pad"} <= tokens
        or {"flight", "deck"} <= tokens
    ):
        return ("terrain_platform", "road", "lane_arrow", "stop_line", "cabin", "wing", "thruster", "antenna", "streetlight")
    if (
        {"railway", "railroad", "train", "tram", "subway", "metro", "transit"} & tokens
        or {"rail", "network"} <= tokens
        or {"train", "station"} <= tokens
        or {"transit", "station"} <= tokens
    ):
        return ("service_rail", "cable_span", "utility_pole", "cabin", "wheel", "cargo_module", "kiosk_body", "streetlight")
    if (
        {"logistics", "warehouse", "supply", "shipping", "delivery", "convoy", "freight"} & tokens
        or {"supply", "chain"} <= tokens
        or {"cargo", "route"} <= tokens
        or {"delivery", "hub"} <= tokens
    ):
        return ("road", "cargo_module", "cargo_bay", "cargo_hold", "conveyor", "street_crate", "shelf_unit", "kiosk_body")
    if (
        {"vehicle", "car", "truck", "rover", "tank", "speeder", "transport"} & tokens
        or {"ground", "vehicle"} <= tokens
    ):
        return ("chassis", "cabin", "wheel", "engine", "suspension", "cargo_module")
    if (
        {"aircraft", "airplane", "plane", "jet", "drone", "spacecraft", "starship", "airship"} & tokens
        or {"flying", "vehicle"} <= tokens
        or {"space", "vehicle"} <= tokens
    ):
        return ("chassis", "cabin", "wing", "engine", "thruster", "stabilizer", "antenna", "hardpoint")
    if (
        {"boat", "ship", "skiff", "barge", "sailboat", "vessel"} & tokens
        or {"water", "vehicle"} <= tokens
    ):
        return ("hull", "deck", "mast", "sail", "rigging", "rudder", "propeller", "anchor")
    if (
        {"weapon", "rifle", "gun", "sword", "blade", "tool"} & tokens
        or {"melee", "weapon"} <= tokens
        or {"ranged", "weapon"} <= tokens
    ):
        return ("weapon_body", "barrel", "stock", "magazine", "sight", "trigger", "guard", "grip", "blade")
    if (
        {"machine", "factory", "workshop", "mechanism", "console", "generator"} & tokens
        or {"machine", "room"} <= tokens
    ):
        return ("machine_base", "machine_column", "hydraulic_piston", "conveyor", "gear", "tank", "crane_boom")
    if (
        {"crafting", "recipe", "forge", "smelter", "fabricator", "workbench", "tooling"} & tokens
        or {"crafting", "station"} <= tokens
        or {"assembly", "bench"} <= tokens
        or {"material", "processing"} <= tokens
    ):
        return ("machine_base", "table_top", "tool_head", "gear", "tank", "pipe_run", "cabinet_body", "drawer", "hardpoint")
    if (
        {"power", "energy", "electric", "electrical", "grid", "reactor", "battery", "fuel"} & tokens
        or {"power", "grid"} <= tokens
        or {"energy", "network"} <= tokens
    ):
        return ("machine_base", "tank", "pipe_run", "transformer_box", "junction_box", "utility_pole", "cable_span", "valve_wheel")
    if (
        {"robot", "mech", "android", "automaton", "character", "creature", "humanoid", "avatar", "companion", "monster"} & tokens
        or {"robot", "arm"} <= tokens
        or {"creature", "appendage"} <= tokens
    ):
        return ("machine_column", "hydraulic_piston", "manipulator_arm", "hardpoint", "guard", "grip", "root", "tree_branch")
    if (
        {"portal", "relic", "shrine", "altar", "obelisk", "artifact", "monument", "rune"} & tokens
        or {"portal", "gate"} <= tokens
        or {"ritual", "site"} <= tokens
    ):
        return ("tower", "dome", "arch", "column", "gate_panel", "sign_post", "lamp", "hardpoint")
    if (
        {"social", "community", "faction", "civilization", "guild", "tavern", "camp", "campfire"} & tokens
        or {"meeting", "place"} <= tokens
        or {"social", "hub"} <= tokens
        or {"npc", "hub"} <= tokens
    ):
        return ("city_block", "room_cell", "street_bench", "market_stall", "kiosk_body", "sign_post", "lamp", "gate_panel")
    if (
        {"security", "defense", "defence", "fortress", "bunker", "outpost", "watchtower", "safehouse"} & tokens
        or {"guard", "post"} <= tokens
        or {"defense", "line"} <= tokens
        or {"security", "checkpoint"} <= tokens
    ):
        return ("tower", "gate_panel", "safety_gate", "street_barrier", "bollard", "streetlight", "sign_post", "hardpoint")
    if (
        {"research", "education", "laboratory", "lab", "library", "school", "classroom", "academy"} & tokens
        or {"research", "station"} <= tokens
        or {"training", "room"} <= tokens
        or {"learning", "space"} <= tokens
    ):
        return ("room_cell", "table_top", "shelf_unit", "cabinet_body", "machine_base", "machine_column", "sign_post", "lamp", "hardpoint")
    if (
        {"medical", "healthcare", "hospital", "clinic", "infirmary", "medbay", "triage", "pharmacy"} & tokens
        or {"healing", "station"} <= tokens
        or {"medical", "bay"} <= tokens
        or {"first", "aid"} <= tokens
    ):
        return ("room_cell", "table_top", "cabinet_body", "shelf_unit", "lamp", "sign_post", "hardpoint", "street_crate")
    if (
        {"communication", "communications", "comms", "radio", "broadcast", "transmitter", "receiver", "beacon"} & tokens
        or {"signal", "tower"} <= tokens
        or {"message", "hub"} <= tokens
        or {"broadcast", "station"} <= tokens
    ):
        return ("utility_pole", "cable_span", "junction_box", "streetlight", "sign_post", "module_socket", "hardpoint")
    if (
        {"fashion", "garment", "wardrobe", "costume", "outfit", "tailor", "textile"} & tokens
        or {"fashion", "studio"} <= tokens
        or {"costume", "shop"} <= tokens
        or {"textile", "workshop"} <= tokens
    ):
        return ("room_cell", "cabinet_body", "drawer", "shelf_unit", "cushion", "awning", "sail", "hardpoint")
    if (
        {"media", "studio", "film", "photography", "podcast", "press", "news", "cinema", "recording"} & tokens
        or {"media", "room"} <= tokens
        or {"film", "set"} <= tokens
        or {"recording", "studio"} <= tokens
    ):
        return ("room_cell", "service_rail", "streetlight", "ceiling_light", "sign_post", "kiosk_body", "module_socket", "hardpoint")
    if (
        {"domestic", "household", "bedroom", "bathroom", "laundry", "nursery", "kitchenette"} & tokens
        or {"family", "home"} <= tokens
        or {"living", "space"} <= tokens
        or {"home", "interior"} <= tokens
    ):
        return ("room_cell", "bed_frame", "cabinet_body", "drawer", "appliance_body", "table_top", "lamp", "cushion")
    if (
        {"room", "interior", "house", "home", "furniture", "apartment"} & tokens
        or {"living", "room"} <= tokens
    ):
        return ("room", "room_cell", "corridor", "partition", "furniture_base", "chair_seat", "chair_back", "table_top", "shelf_unit", "lamp")
    if (
        {"forest", "garden", "grove", "vegetation", "jungle", "foliage"} & tokens
        or {"natural", "scene"} <= tokens
    ):
        return ("foliage_ground", "tree_trunk", "tree_branch", "leaf_cluster", "bush", "grass_clump", "natural_rock", "fallen_log")
    if (
        {"ecosystem", "wildlife", "habitat", "nest", "lair", "den"} & tokens
        or {"food", "chain"} <= tokens
        or {"animal", "habitat"} <= tokens
        or {"creature", "habitat"} <= tokens
    ):
        return ("terrain", "clearing", "water", "foliage_ground", "tree_trunk", "root", "bush", "natural_rock", "mushroom")
    if (
        {"farm", "agriculture", "orchard", "vineyard", "crop", "ranch"} & tokens
        or {"crop", "field"} <= tokens
        or {"farm", "field"} <= tokens
        or {"food", "garden"} <= tokens
    ):
        return ("terrain", "clearing", "planter", "grass_clump", "fence_segment", "water", "market_stall", "kiosk_body")
    if (
        {"kitchen", "restaurant", "cafe", "cafeteria", "bakery", "cooking", "meal", "feast"} & tokens
        or {"food", "market"} <= tokens
        or {"food", "stall"} <= tokens
        or {"cooking", "station"} <= tokens
    ):
        return ("room_cell", "counter_top", "appliance_body", "table_top", "shelf_unit", "market_stall", "kiosk_body", "lamp")
    if (
        {"culture", "museum", "theater", "theatre", "gallery", "festival", "stage", "performance", "exhibit"} & tokens
        or {"art", "gallery"} <= tokens
        or {"public", "square"} <= tokens
        or {"performance", "space"} <= tokens
    ):
        return ("city_block", "room_cell", "arch", "column", "street_bench", "sign_post", "lamp", "market_stall")
    if (
        {"ritual", "ceremony", "temple", "sanctuary", "memorial", "offering", "pilgrimage"} & tokens
        or {"ritual", "space"} <= tokens
        or {"ceremony", "site"} <= tokens
        or {"sacred", "place"} <= tokens
    ):
        return ("tower", "dome", "arch", "column", "sign_post", "lamp", "hardpoint", "natural_rock")
    if (
        {"governance", "government", "civic", "council", "courthouse", "townhall", "embassy"} & tokens
        or {"town", "hall"} <= tokens
        or {"civic", "center"} <= tokens
        or {"council", "chamber"} <= tokens
    ):
        return ("city_block", "room_cell", "column", "gate_panel", "sign_post", "street_bench", "lamp", "hardpoint")
    if (
        {"legal", "law", "courtroom", "tribunal", "permit", "license", "registry"} & tokens
        or {"law", "office"} <= tokens
        or {"law", "court"} <= tokens
        or {"legal", "archive"} <= tokens
        or {"record", "hall"} <= tokens
    ):
        return ("room_cell", "shelf_unit", "cabinet_body", "drawer", "table_top", "sign_post", "gate_panel", "lamp")
    if (
        {"finance", "bank", "treasury", "vault", "exchange", "broker", "accounting"} & tokens
        or {"market", "exchange"} <= tokens
        or {"trading", "post"} <= tokens
        or {"bank", "vault"} <= tokens
    ):
        return ("kiosk_body", "cabinet_body", "drawer", "street_crate", "shelf_unit", "gate_panel", "sign_post", "hardpoint")
    if (
        {"sports", "sport", "stadium", "gym", "court", "race", "tournament"} & tokens
        or {"sports", "arena"} <= tokens
        or {"training", "ground"} <= tokens
        or {"race", "track"} <= tokens
    ):
        return ("terrain_platform", "street_barrier", "street_bench", "sign_post", "streetlight", "gate_panel", "road", "lane_arrow")
    if (
        {"disaster", "emergency", "rescue", "evacuation", "shelter", "firefighting", "recovery"} & tokens
        or {"rescue", "zone"} <= tokens
        or {"emergency", "shelter"} <= tokens
        or {"evacuation", "route"} <= tokens
    ):
        return ("terrain_platform", "access_ramp", "safety_gate", "street_barrier", "street_crate", "streetlight", "sign_post", "hardpoint")
    if (
        {"mining", "mineshaft", "quarry", "ore", "excavation", "drilling", "shaft"} & tokens
        or {"mine", "site"} <= tokens
        or {"ore", "vein"} <= tokens
        or {"mining", "tunnel"} <= tokens
    ):
        return ("terrain", "cliff", "tunnel_segment", "conveyor", "pipe_run", "natural_rock", "street_crate", "cargo_module")
    if (
        {"ocean", "sea", "coastal", "underwater", "reef", "salvage", "submarine"} & tokens
        or {"ocean", "floor"} <= tokens
        or {"underwater", "base"} <= tokens
        or {"salvage", "site"} <= tokens
    ):
        return ("water", "terrain_platform", "hull", "deck", "pontoon", "anchor", "propeller", "natural_rock")
    if (
        {"orbital", "orbit", "astronomy", "observatory", "satellite", "telescope", "cosmos"} & tokens
        or {"space", "station"} <= tokens
        or {"orbital", "platform"} <= tokens
        or {"star", "map"} <= tokens
    ):
        return ("tower", "dome", "antenna", "utility_pole", "cable_span", "thruster", "module_socket", "hardpoint")
    if (
        {"seasonal", "calendar", "clock", "solstice", "equinox", "daynight"} & tokens
        or {"time", "system"} <= tokens
        or {"season", "cycle"} <= tokens
        or {"day", "night"} <= tokens
    ):
        return ("sign_post", "lamp", "streetlight", "tree_trunk", "leaf_cluster", "flower", "natural_rock", "hardpoint")
    if {"lighting", "light", "lamp", "lantern", "streetlamp"} & tokens:
        return ("lamp", "streetlight", "ceiling_light")
    if (
        {"encounter", "arena", "combat", "spawn", "patrol", "cover"} & tokens
        or {"cover", "zone"} <= tokens
        or {"spawn", "point"} <= tokens
    ):
        return ("terrain_platform", "street_barrier", "street_crate", "gate_panel", "streetlight", "natural_rock")
    if (
        {"inventory", "loot", "pickup", "container", "vendor", "economy"} & tokens
        or {"loot", "table"} <= tokens
        or {"pickup", "handle"} <= tokens
    ):
        return ("street_crate", "cabinet_body", "drawer", "shelf_unit", "market_stall", "kiosk_body", "hardpoint")
    if (
        {"quest", "dialogue", "objective", "checkpoint", "npc", "story"} & tokens
        or {"quest", "giver"} <= tokens
    ):
        return ("sign_post", "street_bench", "kiosk_body", "gate_panel", "lamp", "room_cell")
    if (
        {"rig", "animation", "retarget", "skeleton", "pose", "joint"} & tokens
        or {"animation", "proxy"} <= tokens
        or {"rig", "proxy"} <= tokens
    ):
        return ("machine_column", "hydraulic_piston", "hardpoint", "module_socket", "guardrail", "wheel")
    if (
        {"destructible", "destruction", "breakable", "damage", "fracture", "repair"} & tokens
        or {"damage", "state"} <= tokens
        or {"weak", "point"} <= tokens
    ):
        return ("street_crate", "door", "gate_panel", "safety_gate", "natural_rock", "pipe_run", "hardpoint")
    if (
        {"cloth", "fabric", "banner", "flag", "canopy", "attachment"} & tokens
        or {"cloth", "attachment"} <= tokens
        or {"fabric", "panel"} <= tokens
    ):
        return ("sail", "rigging", "awning", "cushion", "hardpoint", "module_socket")
    if (
        {"simulation", "weather", "wind", "fluid", "particle", "volume", "effect", "effects", "erosion"} & tokens
        or {"flow", "field"} <= tokens
        or {"particle", "system"} <= tokens
    ):
        return ("terrain", "water", "pipe_run", "overhead_conduit", "valve_wheel", "natural_rock", "streetlight")
    if (
        {"camera", "cinematic", "cutscene", "shot", "sequence", "rail", "bookmark"} & tokens
        or {"camera", "rig"} <= tokens
        or {"shot", "sequence"} <= tokens
    ):
        return ("machine_column", "service_rail", "hardpoint", "sign_post", "streetlight", "room_cell")
    if (
        {"audio", "sound", "music", "foley", "ambience", "voiceover", "speaker"} & tokens
        or {"audio", "cue"} <= tokens
    ):
        return ("streetlight", "ceiling_light", "kiosk_body", "sign_post", "room_cell", "hardpoint")
    if (
        {"localization", "text", "subtitle", "caption", "accessibility", "ux", "interface"} & tokens
        or {"text", "table"} <= tokens
        or {"input", "map"} <= tokens
        or {"focus", "navigation"} <= tokens
    ):
        return ("sign_post", "street_bench", "access_ramp", "guardrail", "lamp", "room_cell")
    if (
        {"save", "checkpoint", "persistence", "snapshot", "restore", "unlock"} & tokens
        or {"save", "state"} <= tokens
        or {"checkpoint", "state"} <= tokens
    ):
        return ("sign_post", "kiosk_body", "street_crate", "hardpoint", "gate_panel", "lamp")
    if (
        {"multiplayer", "session", "network", "replication", "telemetry", "rpc", "authority"} & tokens
        or {"sync", "tick"} <= tokens
        or {"matchmaking", "rule"} <= tokens
    ):
        return ("utility_pole", "cable_span", "junction_box", "transformer_box", "module_socket", "streetlight")
    if (
        {"kit", "bundle", "prefab", "module", "domain", "style", "crossdomain", "live"} & tokens
        or {"domain", "kit"} <= tokens
        or {"style", "stack"} <= tokens
        or {"visual", "band"} <= tokens
        or {"live", "runtime"} <= tokens
    ):
        return ("city_block", "terrain", "room", "module_socket", "hardpoint", "sign_post", "street_crate")
    component_type = _component_type_from_source(fragment)
    return (component_type,) if component_type is not None else ()


def _geometry_detail_component_fragments(values: tuple[str, ...]) -> tuple[str, ...]:
    fragments: list[str] = []
    for value in values:
        slug = _slug_fragment(value)
        fragments.append(_GEOMETRY_DETAIL_COMPONENT_FRAGMENT_ALIASES.get(slug, value))
    return tuple(fragments)


def _component_part_for_type(component_type: str, fallback: str) -> str:
    if component_type in {"roof", "roof_ridge", "dormer", "chimney"}:
        return "roof"
    if component_type in {"window", "door", "arch", "balcony", "awning", "cornice", "parapet", "column", "tower", "dome"}:
        return "facade"
    if component_type in {"road", "road_junction", "crosswalk", "turnout", "roundabout", "median", "curb_ramp", "lane_arrow", "stop_line"}:
        return "road"
    if component_type in {"lot", "city_block", "urban_base", "streetlight", "street_bench", "trash_bin", "kiosk_body", "market_stall", "street_barrier", "street_crate", "bollard", "fence_segment", "railing"}:
        return "street_scene"
    if component_type in {"sign_post", "gate_panel", "safety_gate"}:
        return "scene_anchor"
    if component_type in {"hardpoint", "module_socket", "socket_plate", "anchor_plate"}:
        return "interface"
    if component_type in {"terrain", "ridge", "cliff", "clearing", "terrain_platform", "water"}:
        return "terrain"
    if component_type in {"wheel", "track", "suspension"}:
        return "wheel"
    if component_type in {"chassis", "cabin", "engine", "crew_bay", "cargo_bay", "cargo_module", "thruster", "stabilizer", "wing", "rotor_arm", "rotor_pod", "antenna"}:
        return "vehicle"
    if component_type in {"hull", "deck", "mast", "sail", "rigging", "pontoon", "outrigger", "cargo_hold", "rudder", "propeller", "anchor"}:
        return "hull"
    if component_type in {"weapon_body", "barrel", "blade", "guard", "grip", "stock", "magazine", "sight", "trigger", "tool_head"}:
        return "weapon"
    if component_type in {"machine_base", "machine_column", "hydraulic_piston", "conveyor", "gear", "tank", "crane_boom", "manipulator_arm"}:
        return "machine"
    if component_type in {"room", "interior", "room_cell", "corridor", "partition", "alcove"}:
        return "interior"
    if component_type in {"furniture_base", "chair_seat", "chair_back", "furniture_leg", "table_top", "bed_frame", "shelf_unit", "cabinet_body", "drawer", "cushion", "counter_top", "appliance_body"}:
        return "furniture"
    if component_type in {"lamp", "streetlight", "ceiling_light"}:
        return "lighting"
    if component_type in {"tree_trunk", "root", "tree_branch", "leaf_cluster", "bush", "grass_clump", "natural_rock", "mushroom", "vine", "flower", "planter"}:
        return "foliage"
    if component_type in {"pipe_run", "duct_run", "overhead_conduit", "drain_channel", "fire_hydrant", "transformer_box", "junction_box", "valve_wheel", "manhole_cover", "infrastructure_base", "utility_pole", "cable_span", "support_bracket", "cable_tray"}:
        return "infrastructure"
    if component_type in {"access_base", "catwalk_deck", "walkway_span", "guardrail", "access_ladder", "access_ramp", "gantry_frame", "elevator_shaft", "access_platform", "tunnel_segment", "scaffold_frame", "safety_gate", "access_support", "service_rail"}:
        return "access"
    return fallback


def _authored_component_extents(asset_graph: AssetGraph, component_type: str, index: int) -> tuple[float, float, float]:
    scale = max(float(asset_graph.scale_cm), 1.0)
    width = max(scale * 0.32, 6.0)
    height = max(scale * 0.18, 4.0)
    depth = max(scale * 0.24, 6.0)
    if component_type in {"tower", "tree_trunk", "column", "mast", "utility_pole", "antenna"}:
        return (width * 0.28, height * 2.8, depth * 0.28)
    if component_type in {"lot", "city_block", "urban_base"}:
        return (width * 1.8, height * 0.34, depth * 1.5)
    if component_type in {"road", "bridge", "hull", "deck", "barrel", "pipe_run", "duct_run", "overhead_conduit", "walkway_span", "catwalk_deck", "cable_span", "service_rail", "fence_segment", "railing", "cable_tray", "drain_channel", "tunnel_segment"}:
        return (width * 1.4, height * 0.32, depth * 0.54)
    if component_type in {"chassis", "cabin", "cargo_bay", "cargo_hold", "cargo_module", "machine_base", "conveyor", "room", "corridor"}:
        return (width * 1.25, height * 0.72, depth * 0.82)
    if component_type in {"wheel", "valve_wheel", "manhole_cover"}:
        return (width * 0.34, width * 0.34, width * 0.18)
    if component_type in {"engine", "gear", "tank", "hydraulic_piston", "sight", "trigger"}:
        return (width * 0.42, height * 0.62, depth * 0.42)
    if component_type in {"roof", "sail", "wing", "blade"}:
        return (width, height * 0.46, depth * 0.42)
    if component_type in {"water", "terrain", "clearing", "terrain_platform"}:
        return (width * 1.2, height * 0.24, depth * 1.0)
    if component_type in {"market_stall", "kiosk_body", "transformer_box", "junction_box", "access_base", "infrastructure_base"}:
        return (width * 0.72, height * 0.82, depth * 0.72)
    if component_type in {"room_cell", "partition", "furniture_base", "chair_seat", "chair_back", "table_top", "shelf_unit", "counter_top", "appliance_body", "lamp", "ceiling_light"}:
        return (width * 0.58, height * 0.62, depth * 0.58)
    if component_type in {"street_crate", "cabinet_body", "drawer", "hardpoint", "module_socket", "sign_post", "gate_panel", "safety_gate", "cushion", "awning"}:
        return (width * 0.50, height * 0.58, depth * 0.50)
    return (width, height, depth)


def _authored_component_center(index: int, extents: tuple[float, float, float]) -> tuple[float, float, float]:
    column = index % 4
    row = index // 4
    spacing_x = max(extents[0] * 0.62, 10.0)
    spacing_z = max(extents[2] * 0.62, 10.0)
    return (
        round((column - 1.5) * spacing_x, 6),
        round(extents[1] * 0.5, 6),
        round(row * spacing_z, 6),
    )


def _float_tuple3(value: Any) -> tuple[float, float, float] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        return None
    try:
        parsed = tuple(float(item) for item in value)
    except (TypeError, ValueError):
        return None
    if any(not math.isfinite(item) for item in parsed):
        return None
    return (parsed[0], parsed[1], parsed[2])


def _authored_component_decl_extents(
    component: dict[str, Any],
    asset_graph: AssetGraph,
    component_type: str,
    index: int,
) -> tuple[float, float, float]:
    geometry = component.get("geometry") if isinstance(component.get("geometry"), dict) else {}
    values = component.get("values") if isinstance(component.get("values"), dict) else {}
    for container in (geometry, values, component):
        extents = _float_tuple3(
            container.get("extents_cm")
            or container.get("extents")
            or container.get("size_cm")
            or container.get("size")
        )
        if extents is not None and all(item > NUMERIC_EPSILON for item in extents):
            return extents
        width = container.get("width_cm", container.get("width"))
        height = container.get("height_cm", container.get("height"))
        depth = container.get("depth_cm", container.get("depth"))
        try:
            dims = (float(width), float(height), float(depth))
        except (TypeError, ValueError):
            continue
        if all(math.isfinite(item) and item > NUMERIC_EPSILON for item in dims):
            return dims
    return _authored_component_extents(asset_graph, component_type, index)


def _authored_component_decl_center(
    component: dict[str, Any],
    index: int,
    extents: tuple[float, float, float],
) -> tuple[float, float, float]:
    geometry = component.get("geometry") if isinstance(component.get("geometry"), dict) else {}
    values = component.get("values") if isinstance(component.get("values"), dict) else {}
    for container in (geometry, values, component):
        center = _float_tuple3(
            container.get("center_cm")
            or container.get("center")
            or container.get("position_cm")
            or container.get("position")
            or container.get("offset_cm")
            or container.get("offset")
        )
        if center is not None:
            return center
    return _authored_component_center(index, extents)


def _resolved_component_blueprint_components(
    asset_graph: AssetGraph,
    *,
    existing_names: set[str],
    existing_parts: set[str],
) -> list[BlueprintComponent]:
    authoring = asset_graph.authoring if isinstance(asset_graph.authoring, dict) else {}
    raw_components = authoring.get("components")
    if not isinstance(raw_components, list):
        return []
    components: list[BlueprintComponent] = []
    seen_names = set(existing_names)
    seen_parts = set(existing_parts)
    fallback_part = asset_graph.parts[0].name if asset_graph.parts else "body"
    for component in raw_components:
        if len(components) >= _MAX_AUTHORED_COMPONENTS:
            break
        if not isinstance(component, dict):
            continue
        name = _slug_fragment(str(component.get("name") or "resolved_component"))
        values = component.get("values") if isinstance(component.get("values"), dict) else {}
        geometry = component.get("geometry") if isinstance(component.get("geometry"), dict) else {}
        component_type = str(
            geometry.get("component_type")
            or values.get("component_type")
            or _component_type_from_source(name)
            or ""
        ).strip()
        component_type = _component_type_from_source(component_type) or component_type
        if component_type not in _COMPONENT_BUILDERS:
            continue
        part = str(values.get("part") or component.get("part") or name).strip() or fallback_part
        if name in seen_names or part in seen_parts:
            continue
        extents = _authored_component_decl_extents(
            component,
            asset_graph,
            component_type,
            len(components),
        )
        center = _authored_component_decl_center(component, len(components), extents)
        raw_tags = list(values.get("tags") or []) if isinstance(values.get("tags"), list) else []
        material_zone = values.get("material_zone") or geometry.get("material_zone")
        tags = [
            "resolved_assembly_component",
            component_type,
            name,
            *[str(tag) for tag in raw_tags if str(tag)],
            *([str(material_zone)] if material_zone else []),
        ]
        interface_role = values.get("interface_role") or component.get("interface_role")
        components.append(
            BlueprintComponent(
                name=name,
                component_type=component_type,
                part=part,
                center=center,
                extents=extents,
                tags=list(dict.fromkeys(tags)),
                adjacency=[],
                axis=str(geometry.get("axis") or values.get("axis") or "y"),
                radius=max(min(extents) * 0.45, 0.001),
                height=extents[1],
                interface_role=str(interface_role) if interface_role else None,
            )
        )
        seen_names.add(name)
        seen_parts.add(part)
    return components


def _assembly_rule_component_fragments(authoring: dict[str, Any]) -> tuple[str, ...]:
    assembly_rules = authoring.get("assembly_rules")
    if not isinstance(assembly_rules, dict):
        return ()
    fragments: list[str] = []
    for key in sorted(_ASSEMBLY_RULE_COMPONENT_KEYS):
        fragments.extend(_iter_text_fragments(assembly_rules.get(key)))
    return tuple(fragments)


def _assembly_rule_length_m(value: Any, default: float) -> float:
    if isinstance(value, dict) and value.get("type") == "unit":
        try:
            numeric = float(value.get("value"))
        except (TypeError, ValueError):
            return default
        unit = str(value.get("unit") or "m")
        if unit == "mm":
            return numeric / 1000.0
        if unit == "cm":
            return numeric / 100.0
        if unit == "m":
            return numeric
        return default
    if isinstance(value, str):
        text = value.strip().lower()
        try:
            if text.endswith("mm"):
                return float(text[:-2].strip()) / 1000.0
            if text.endswith("cm"):
                return float(text[:-2].strip()) / 100.0
            if text.endswith("m"):
                return float(text[:-1].strip())
            return float(text)
        except ValueError:
            return default
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        numeric = float(value)
        return numeric if math.isfinite(numeric) and numeric > 0.0 else default
    return default


def _assembly_rule_initial_shape(asset_graph: AssetGraph, rules: dict[str, Any]) -> Any:
    from .cga import InitialShape

    scale_m = max(float(asset_graph.scale_cm) / 100.0, 0.01)
    width = _assembly_rule_length_m(
        rules.get("width_m", rules.get("width", rules.get("initial_width"))),
        scale_m,
    )
    depth = _assembly_rule_length_m(
        rules.get("depth_m", rules.get("depth", rules.get("initial_depth"))),
        max(scale_m * 0.5, 0.01),
    )
    height = _assembly_rule_length_m(
        rules.get("height_m", rules.get("height", rules.get("initial_height"))),
        max(scale_m * 0.75, 0.01),
    )
    return InitialShape(
        width=width,
        depth=depth,
        height=height,
        position=(-width * 0.5, -depth * 0.5, -height * 0.5),
    )


def _cga_terminal_params(record: Any) -> dict[str, Any]:
    params = getattr(record, "params", None)
    return dict(params) if isinstance(params, dict) else {}


def _cga_terminal_component_type(
    name: str,
    kind: str,
    params: dict[str, Any] | None = None,
) -> str:
    terminal_params = params or {}
    requested_type = (
        terminal_params.get("component_type")
        or terminal_params.get("component")
        or terminal_params.get("type")
    )
    if isinstance(requested_type, str) and requested_type.strip():
        component_type = _component_type_from_source(requested_type) or _slug_fragment(requested_type)
        if component_type in _COMPONENT_BUILDERS:
            return component_type
    component_type = _component_type_from_source(name)
    if component_type in _COMPONENT_BUILDERS:
        return component_type
    if kind in {"kit", "mesh_ref"}:
        return "module_socket"
    return "panel"


def _cga_param_length_m(params: dict[str, Any], keys: tuple[str, ...], default: float) -> float:
    for key in keys:
        if key not in params:
            continue
        value = params.get(key)
        length = _assembly_rule_length_m(value, default)
        if math.isfinite(length) and length > 0.0:
            return length
    return default


def _cga_terminal_center_cm(record: Any) -> tuple[float, float, float]:
    width_m, depth_m, height_m = record.extents
    x_m, y_m, z_m = record.position
    return (
        (float(x_m) + float(width_m) * 0.5) * 100.0,
        (float(z_m) + float(height_m) * 0.5) * 100.0,
        (float(y_m) + float(depth_m) * 0.5) * 100.0,
    )


def _cga_terminal_extents_cm(record: Any, component_type: str) -> tuple[float, float, float]:
    params = _cga_terminal_params(record)
    width_m, depth_m, height_m = record.extents
    width_m = _cga_param_length_m(params, ("width_m", "width", "w"), float(width_m))
    depth_m = _cga_param_length_m(params, ("depth_m", "depth", "d"), float(depth_m))
    height_m = _cga_param_length_m(params, ("height_m", "height", "h"), float(height_m))
    width = max(width_m * 100.0, NUMERIC_EPSILON)
    height = max(height_m * 100.0, NUMERIC_EPSILON)
    depth = max(depth_m * 100.0, NUMERIC_EPSILON)
    if component_type in {"window", "door", "arch", "balcony", "awning", "cornice"}:
        depth = min(depth, max(min(width, height) * 0.16, 8.0))
    return (width, height, depth)


def _cga_terminal_tags(record: Any, component_type: str) -> list[str]:
    terminal_slug = _slug_fragment(str(record.name))
    metadata = record.metadata if isinstance(record.metadata, dict) else {}
    params = _cga_terminal_params(record)
    tags = [
        "cga_rule_component",
        f"cga_terminal:{terminal_slug}",
        f"cga_kind:{_slug_fragment(str(record.kind))}",
        component_type,
        *[
            f"cga_path:{_slug_fragment(str(path_item))}"
            for path_item in list(record.path)[-4:]
            if str(path_item)
        ],
    ]
    if params:
        tags.append("cga_parametric_terminal")
    if str(record.kind) == "mesh_ref":
        tags.append(f"cga_mesh_ref:{terminal_slug}")
    if metadata.get("split_axis") not in (None, ""):
        tags.append(f"cga_split_axis:{_slug_fragment(str(metadata.get('split_axis')))}")
    if metadata.get("repeat_index") is not None:
        tags.append(f"cga_repeat_index:{_slug_fragment(str(metadata.get('repeat_index')))}")
    if metadata.get("mirrored"):
        tags.append("cga_mirrored")
    if metadata.get("rotate_deg") not in (None, "", 0, 0.0):
        tags.append("cga_rotated")
    alternative_count = metadata.get("production_alternative_count")
    try:
        if int(alternative_count) > 1:
            tags.append(
                f"cga_production_alt:{_slug_fragment(str(metadata.get('selected_production_index')))}"
            )
    except (TypeError, ValueError):
        pass
    if metadata.get("selected_option_index") is not None:
        tags.append(f"cga_choice:{_slug_fragment(str(metadata.get('selected_option_index')))}")
    return list(dict.fromkeys(tags))


def _cga_terminal_metadata(record: Any, component_type: str) -> dict[str, Any]:
    metadata = record.metadata if isinstance(record.metadata, dict) else {}
    params = _cga_terminal_params(record)
    payload: dict[str, Any] = {
        "source": "assembly_rules.productions",
        "cga": {
            "terminal": str(record.name),
            "terminal_kind": str(record.kind),
            "component_type": component_type,
            "path": [str(path_item) for path_item in list(record.path) if str(path_item)],
        },
    }
    cga_payload = payload["cga"]
    if params:
        cga_payload["terminal_params"] = dict(params)
    for key in (
        "split_axis",
        "split_offset",
        "split_size",
        "repeat_index",
        "mirrored",
        "rotate_deg",
        "selected_production_index",
        "production_alternative_count",
        "selected_production_source",
        "selected_option_index",
        "weights",
    ):
        if key in metadata:
            cga_payload[key] = metadata[key]
    steps = metadata.get("derivation_steps")
    if isinstance(steps, list) and steps:
        cga_payload["derivation_steps"] = [
            dict(step)
            for step in steps[-8:]
            if isinstance(step, dict)
        ]
    return payload


def _cga_rule_blueprint_components(
    asset_graph: AssetGraph,
    *,
    existing_names: set[str],
    existing_parts: set[str],
    start_index: int,
    max_count: int,
) -> list[BlueprintComponent]:
    authoring = asset_graph.authoring if isinstance(asset_graph.authoring, dict) else {}
    rules = authoring.get("assembly_rules")
    if not isinstance(rules, dict) or not rules.get("productions"):
        return []
    from .cga import compile_assembly_rules, evaluate_rule_tree, terminate_to_primitives

    grammar, report = compile_assembly_rules(rules)
    if any(getattr(diagnostic, "severity", "") == "error" for diagnostic in report.diagnostics):
        return []
    tree = evaluate_rule_tree(
        grammar,
        _assembly_rule_initial_shape(asset_graph, rules),
        seed=grammar.seed,
    )
    records = terminate_to_primitives(tree)
    components: list[BlueprintComponent] = []
    seen_names = set(existing_names)
    seen_parts = set(existing_parts)
    fallback_part = asset_graph.parts[0].name if asset_graph.parts else "body"
    for record in records:
        if len(components) >= max_count:
            break
        terminal_params = _cga_terminal_params(record)
        component_type = _cga_terminal_component_type(
            record.name,
            record.kind,
            terminal_params,
        )
        terminal_slug = _slug_fragment(str(record.name))
        name = f"cga_{terminal_slug}_{start_index + len(components):02d}"
        requested_part = terminal_params.get("part")
        part = (
            _slug_fragment(requested_part)
            if isinstance(requested_part, str) and requested_part.strip()
            else _component_part_for_type(component_type, fallback_part)
        )
        if name in seen_names:
            continue
        if part in seen_parts and component_type in {"shell", "body"}:
            continue
        axis_param = terminal_params.get("axis")
        axis = (
            str(axis_param)
            if isinstance(axis_param, str) and axis_param in {"x", "y", "z"}
            else str(record.rotation[0] or "z")
        )
        component = BlueprintComponent(
            name=name,
            component_type=component_type,
            part=part,
            center=_cga_terminal_center_cm(record),
            extents=_cga_terminal_extents_cm(record, component_type),
            tags=_cga_terminal_tags(record, component_type),
            adjacency=[],
            axis=axis,
            metadata=_cga_terminal_metadata(record, component_type),
        )
        components.append(component)
        seen_names.add(name)
        seen_parts.add(part)
    return components


def _authored_source_components(
    asset_graph: AssetGraph,
    existing_names: set[str],
    existing_parts: set[str] | None = None,
) -> list[BlueprintComponent]:
    authoring = asset_graph.authoring if isinstance(asset_graph.authoring, dict) else {}
    # Only iterate explicit free-text authoring fields. The resolved
    # components, traits, and mechanisms are full dict structures that are
    # already represented as real BlueprintComponents upstream; pulling
    # text fragments from their internal field values causes part-label
    # bleed. ``features.allow`` declares which feature-ops are permitted
    # on existing parts, not new standalone components — feeding it here
    # surfaced labels like ``"weapon"`` (from ``recessed_handle`` →
    # ``grip``) on a chest.
    raw_fragments = [
        *_iter_text_fragments(authoring.get("source_components")),
        *_iter_text_fragments(authoring.get("source_traits")),
        *_iter_text_fragments(authoring.get("source_mechanisms")),
        *_assembly_rule_component_fragments(authoring),
    ]
    detail_controls = geometry_detail_controls_from_authoring(authoring)
    if detail_controls.active:
        raw_fragments.extend(_geometry_detail_component_fragments(detail_controls.silhouette_motifs))
        raw_fragments.extend(_geometry_detail_component_fragments(detail_controls.module_categories))
        raw_fragments.extend(_geometry_detail_component_fragments(detail_controls.module_sockets))
        for zone in detail_controls.zones:
            raw_fragments.extend(_geometry_detail_component_fragments(zone.module_categories))
            raw_fragments.extend(_geometry_detail_component_fragments(zone.motifs))
            raw_fragments.extend(_geometry_detail_component_fragments(zone.attachment_motifs))
    components: list[BlueprintComponent] = _resolved_component_blueprint_components(
        asset_graph,
        existing_names=existing_names,
        existing_parts=set(existing_parts or set()),
    )
    if len(components) < _MAX_AUTHORED_COMPONENTS:
        components.extend(
            _cga_rule_blueprint_components(
                asset_graph,
                existing_names=set(existing_names) | {component.name for component in components},
                existing_parts=set(existing_parts or set()) | {component.part for component in components},
                start_index=len(components),
                max_count=_MAX_AUTHORED_COMPONENTS - len(components),
            )
        )
    generated_names = set(existing_names) | {component.name for component in components}
    seen_types: set[str] = set()
    fallback_part = asset_graph.parts[0].name if asset_graph.parts else "body"
    for fragment in raw_fragments:
        if len(components) >= _MAX_AUTHORED_COMPONENTS:
            break
        fragment_slug = _slug_fragment(fragment)
        for component_type in _component_types_from_source(fragment):
            if len(components) >= _MAX_AUTHORED_COMPONENTS or component_type in seen_types:
                continue
            seen_types.add(component_type)
            name = f"authored_{fragment_slug}_{component_type}"
            if name in generated_names:
                continue
            extents = _authored_component_extents(asset_graph, component_type, len(components))
            components.append(
                BlueprintComponent(
                    name=name,
                    component_type=component_type,
                    part=_component_part_for_type(component_type, fallback_part),
                    center=_authored_component_center(len(components), extents),
                    extents=extents,
                    tags=["authored_source_component", "authored_source_bundle", component_type, fragment_slug],
                    adjacency=[],
                    axis="y",
                    radius=max(min(extents) * 0.45, 0.001),
                    height=extents[1],
                )
            )
            generated_names.add(name)
    return components


def _primitive_bounds(primitive: ShapePrimitive) -> tuple[list[float], list[float]]:
    if primitive.primitive_type == "box":
        if primitive.extents is None:
            raise _missing_box_extents_error(primitive)
        half = [value / 2.0 for value in primitive.extents]
    elif primitive.primitive_type == "subdivision_box":
        # Per-corner radii are clamped within ``extents``; the bounding
        # box is identical to the un-rounded cuboid AABB.
        if primitive.extents is None:
            raise _missing_box_extents_error(primitive)
        half = [value / 2.0 for value in primitive.extents]
    elif primitive.primitive_type == "revolved_profile":
        # Bounding-cylinder approximation around the swept profile.
        from .exact_solids import _revolved_profile_extents

        radius, height = _revolved_profile_extents(primitive)
        if primitive.axis == "x":
            half = [height / 2.0, radius, radius]
        elif primitive.axis == "z":
            half = [radius, radius, height / 2.0]
        else:
            half = [radius, height / 2.0, radius]
    elif primitive.primitive_type == "extruded_profile":
        # Bounding-box approximation: polygon's 2D bbox swept by
        # ``extrude_height`` along ``axis``.
        from .exact_solids import _extruded_profile_polygon_bbox

        umin, umax, vmin, vmax = _extruded_profile_polygon_bbox(primitive)
        half_u = (umax - umin) / 2.0
        half_v = (vmax - vmin) / 2.0
        half_h = float(primitive.extrude_height or 0.0) / 2.0
        if primitive.axis == "x":
            half = [half_h, half_u, half_v]
        elif primitive.axis == "z":
            half = [half_u, half_v, half_h]
        else:
            half = [half_u, half_h, half_v]
    elif primitive.primitive_type == "torus":
        # Bounding cylinder of the ring: outer radius major+minor,
        # height 2*minor along the ring axis.
        if primitive.major_radius is None or primitive.minor_radius is None:
            raise _missing_non_box_dimensions_error(primitive)
        major = float(primitive.major_radius)
        minor = float(primitive.minor_radius)
        radius = major + minor
        height = 2.0 * minor
        if primitive.axis == "x":
            half = [height / 2.0, radius, radius]
        elif primitive.axis == "z":
            half = [radius, radius, height / 2.0]
        else:
            half = [radius, height / 2.0, radius]
    elif primitive.primitive_type == "sphere":
        if primitive.radius is None:
            raise _missing_non_box_dimensions_error(primitive)
        radius = float(primitive.radius)
        half = [radius, radius, radius]
    elif primitive.primitive_type == "swept_profile":
        # AABB of the sweep path expanded by the cross-section
        # circumradius. The path is anchored to ``primitive.center``;
        # bounds are recomputed from the path itself rather than treating
        # ``center`` as the AABB center.
        from .exact_solids import _swept_profile_extents

        path_min, path_max, circumradius = _swept_profile_extents(primitive)
        path_center = [float(0.5 * (path_max[idx] + path_min[idx])) for idx in range(3)]
        half = [float(0.5 * (path_max[idx] - path_min[idx]) + circumradius) for idx in range(3)]
        bounds_min = [primitive.center[idx] + path_center[idx] - half[idx] for idx in range(3)]
        bounds_max = [primitive.center[idx] + path_center[idx] + half[idx] for idx in range(3)]
        return bounds_min, bounds_max
    elif primitive.primitive_type == "lofted_solid":
        # Same envelope strategy as swept_profile: AABB of the
        # section_centers path expanded by the worst-case cross-section
        # reach across all rings.
        from .exact_solids import _lofted_solid_extents

        path_min, path_max, circumradius = _lofted_solid_extents(primitive)
        path_center = [float(0.5 * (path_max[idx] + path_min[idx])) for idx in range(3)]
        half = [float(0.5 * (path_max[idx] - path_min[idx]) + circumradius) for idx in range(3)]
        bounds_min = [primitive.center[idx] + path_center[idx] - half[idx] for idx in range(3)]
        bounds_max = [primitive.center[idx] + path_center[idx] + half[idx] for idx in range(3)]
        return bounds_min, bounds_max
    elif primitive.primitive_type == "sdf_mesh":
        # AABB derived directly from the extracted vertices (already in
        # mesh-local cm); ``primitive.center`` shifts the whole mesh.
        if not primitive.mesh_vertices or not primitive.mesh_faces:
            raise _missing_non_box_dimensions_error(primitive)
        verts = primitive.mesh_vertices
        xs = [float(v[0]) for v in verts]
        ys = [float(v[1]) for v in verts]
        zs = [float(v[2]) for v in verts]
        path_min = [min(xs), min(ys), min(zs)]
        path_max = [max(xs), max(ys), max(zs)]
        bounds_min = [primitive.center[idx] + path_min[idx] for idx in range(3)]
        bounds_max = [primitive.center[idx] + path_max[idx] for idx in range(3)]
        return bounds_min, bounds_max
    else:
        if primitive.radius is None or primitive.height is None:
            raise _missing_non_box_dimensions_error(primitive)
        if primitive.axis == "x":
            half = [primitive.height / 2.0, primitive.radius, primitive.radius]
        elif primitive.axis == "z":
            half = [primitive.radius, primitive.radius, primitive.height / 2.0]
        else:
            half = [primitive.radius, primitive.height / 2.0, primitive.radius]
    bounds_min = [primitive.center[idx] - half[idx] for idx in range(3)]
    bounds_max = [primitive.center[idx] + half[idx] for idx in range(3)]
    return bounds_min, bounds_max


def _expected_extents(primitives: list[ShapePrimitive]) -> list[float]:
    bounds_min = [float("inf"), float("inf"), float("inf")]
    bounds_max = [float("-inf"), float("-inf"), float("-inf")]
    for primitive in primitives:
        pmin, pmax = _primitive_bounds(primitive)
        for idx in range(3):
            bounds_min[idx] = min(bounds_min[idx], pmin[idx])
            bounds_max[idx] = max(bounds_max[idx], pmax[idx])
    return [round(bounds_max[idx] - bounds_min[idx], 6) for idx in range(3)]


def _ratio_signature(extents: list[float]) -> list[float]:
    largest = max(NUMERIC_EPSILON, *extents)
    return [round(float(value) / largest, 6) for value in extents]


def _profile_bins(values: list[float], span: float) -> list[float]:
    if not values or span <= NUMERIC_EPSILON:
        return [0.0, 0.0, 0.0]
    bins = [0.0, 0.0, 0.0]
    for value in values:
        normalized = (value / span) + 0.5
        index = max(0, min(2, int(normalized * 3.0)))
        bins[index] += 1.0
    total = max(1.0, sum(bins))
    return [round(item / total, 6) for item in bins]


def _shape_assessment(
    asset_graph: AssetGraph, regions: list[ShapeRegion], primitives: list[ShapePrimitive]
) -> dict[str, Any]:
    expected_parts = {part.name for part in asset_graph.parts}
    realized_parts = {region.part for region in regions}
    required_pairs = [
        (part.name, part.symmetry_mate)
        for part in asset_graph.parts
        if part.symmetry_mate and part.name < part.symmetry_mate
    ]
    symmetry_score = (
        1.0
        if not required_pairs
        else round(
            sum(1.0 for left, right in required_pairs if left in realized_parts and right in realized_parts)
            / len(required_pairs),
            6,
        )
    )
    feature_primitives = [primitive for primitive in primitives if "feature" in primitive.tags]
    feature_components = {primitive.component for primitive in feature_primitives if primitive.component}
    edge_treatment_count = sum(
        1
        for primitive in feature_primitives
        if any(tag in primitive.tags for tag in ("edge_break", "bevel", "chamfer", "fillet"))
    )
    panel_feature_count = sum(
        1
        for primitive in feature_primitives
        if any(
            tag in primitive.tags
            for tag in (
                "frame_lip",
                "trim_band",
                "vent_grille",
                "panel_frame",
                "panel_seam",
                "cut_line",
                "groove_channel",
                "layered_piece",
                "raised_ridge",
            )
        )
    )
    support_feature_count = sum(
        1
        for primitive in feature_primitives
        if any(
            tag in primitive.tags
            for tag in (
                "support_bracket",
                "recessed_handle",
                "rotor_shroud",
                "corner_guard",
                "socket",
                "connector",
            )
        )
    )
    geometry_detail_primitives = [
        primitive for primitive in feature_primitives if "surface_detail" in primitive.tags
    ]
    mesh_grammar_primitives = [
        primitive for primitive in feature_primitives if "mesh_grammar" in primitive.tags
    ]
    surface_detail_feature_count = len(geometry_detail_primitives)
    geometry_detail_feature_types = sorted(
        {primitive.component or "feature" for primitive in geometry_detail_primitives}
    )
    geometry_detail_operator_counts: dict[str, int] = {}
    geometry_detail_zones = sorted(
        {
            tag.removeprefix("zone_")
            for primitive in geometry_detail_primitives
            for tag in primitive.tags
            if tag.startswith("zone_")
        }
    )
    geometry_detail_edge_metadata = sorted(
        {
            tag
            for primitive in geometry_detail_primitives
            for tag in primitive.tags
            if tag.startswith("edge_treatment_")
            or tag.startswith("edge_hardness_")
            or tag in {"bevel_width_authored", "chamfer_width_authored"}
        }
    )
    geometry_detail_style_modifiers = sorted(
        {
            tag.removeprefix("style_")
            for primitive in geometry_detail_primitives
            for tag in primitive.tags
            if tag.startswith("style_") and not tag.startswith("style_pack_")
        }
    )
    geometry_detail_style_packs = sorted(
        {
            tag.removeprefix("style_pack_")
            for primitive in geometry_detail_primitives
            for tag in primitive.tags
            if tag.startswith("style_pack_")
        }
    )
    geometry_detail_module_sockets = sorted(
        {
            tag.removeprefix("module_socket_")
            for primitive in geometry_detail_primitives
            for tag in primitive.tags
            if tag.startswith("module_socket_")
        }
    )
    geometry_detail_attachment_motifs = sorted(
        {
            tag
            for primitive in geometry_detail_primitives
            for tag in primitive.tags
            if tag
            in {
                "rail",
                "fin",
                "strap",
                "cable",
                "vent_stack",
                "handle",
                "guard",
                "ornament",
            }
        }
    )
    geometry_detail_module_categories = sorted(
        {
            tag
            for primitive in geometry_detail_primitives
            for tag in primitive.tags
            if tag
            in {
                "sensor_pod",
                "power_cell",
                "barrel",
                "blade",
                "wing",
                "leg",
                "shield_plate",
                "antenna",
            }
        }
    )
    geometry_detail_silhouette_profiles = sorted(
        {
            tag.removeprefix("silhouette_profile_")
            for primitive in geometry_detail_primitives
            for tag in primitive.tags
            if tag.startswith("silhouette_profile_")
        }
    )
    geometry_detail_silhouette_motifs = sorted(
        {
            tag.removeprefix("silhouette_motif_")
            for primitive in geometry_detail_primitives
            for tag in primitive.tags
            if tag.startswith("silhouette_motif_")
        }
    )
    for primitive in geometry_detail_primitives:
        key = primitive.component or "feature"
        geometry_detail_operator_counts[key] = geometry_detail_operator_counts.get(key, 0) + 1
    mesh_grammar_operator_counts: dict[str, int] = {}
    for primitive in mesh_grammar_primitives:
        op_tags = [tag.removeprefix("mesh_op_") for tag in primitive.tags if tag.startswith("mesh_op_")]
        if op_tags:
            for op_tag in op_tags:
                mesh_grammar_operator_counts[op_tag] = mesh_grammar_operator_counts.get(op_tag, 0) + 1
        for modifier_tag in ("bevel", "chamfer"):
            if modifier_tag in primitive.tags:
                mesh_grammar_operator_counts[modifier_tag] = mesh_grammar_operator_counts.get(modifier_tag, 0) + 1
    attachment_region_count = sum(
        1
        for region in regions
        if region.component
        in {
            "handle",
            "hinge",
            "lock_plate",
            "latch",
            "rotor_pod",
            "socket_plate",
            "anchor_plate",
            "bracket",
            "bezel",
            "frame",
            "guard",
            "grip",
            "pommel",
        }
    )
    feature_density = round(len(feature_primitives) / max(1.0, len(asset_graph.parts) * 2.0), 6)
    silhouette_complexity = round(
        min(
            1.0, (len(regions) * 0.04) + (len(feature_primitives) * 0.015) + (attachment_region_count * 0.03)
        ),
        6,
    )
    feature_coherence = round(
        min(
            1.0,
            (0.45 * feature_density)
            + (0.25 * min(1.0, len(feature_components) / max(1, len(asset_graph.parts))))
            + (0.30 * min(1.0, attachment_region_count / max(1, len(asset_graph.parts) / 2.0))),
        ),
        6,
    )
    assessment = {
        "required_part_coverage": round(
            len(expected_parts & realized_parts) / max(1, len(expected_parts)), 6
        ),
        "primitive_count": len(primitives),
        "region_count": len(regions),
        "primitive_diversity": round(
            len({primitive.component or primitive.primitive_type for primitive in primitives})
            / max(1, len(primitives)),
            6,
        ),
        "symmetry_region_score": symmetry_score,
        "richness_floor": round(min(1.0, len(primitives) / max(4.0, len(expected_parts) * 1.6)), 6),
        "feature_count": len(feature_primitives),
        "feature_types": sorted(str(item) for item in feature_components),
        "feature_density": feature_density,
        "edge_treatment_count": edge_treatment_count,
        "panel_feature_count": panel_feature_count,
        "support_feature_count": support_feature_count,
        "attachment_region_count": attachment_region_count,
        "silhouette_complexity": silhouette_complexity,
        "feature_coherence": feature_coherence,
    }
    if surface_detail_feature_count:
        assessment["surface_detail_feature_count"] = surface_detail_feature_count
        assessment["geometry_detail_feature_count"] = surface_detail_feature_count
        assessment["geometry_detail_feature_types"] = geometry_detail_feature_types
        assessment["geometry_detail_operator_counts"] = dict(sorted(geometry_detail_operator_counts.items()))
        if geometry_detail_zones:
            assessment["geometry_detail_zone_count"] = len(geometry_detail_zones)
            assessment["geometry_detail_zones"] = geometry_detail_zones
        if geometry_detail_edge_metadata:
            assessment["geometry_detail_edge_metadata"] = geometry_detail_edge_metadata
        if geometry_detail_style_modifiers:
            assessment["geometry_detail_style_modifiers"] = geometry_detail_style_modifiers
        if geometry_detail_style_packs:
            assessment["geometry_detail_style_packs"] = geometry_detail_style_packs
        if geometry_detail_module_sockets:
            assessment["geometry_detail_module_sockets"] = geometry_detail_module_sockets
        if geometry_detail_attachment_motifs:
            assessment["geometry_detail_attachment_motifs"] = geometry_detail_attachment_motifs
        if geometry_detail_module_categories:
            assessment["geometry_detail_module_categories"] = geometry_detail_module_categories
        if geometry_detail_silhouette_profiles:
            assessment["geometry_detail_silhouette_profiles"] = geometry_detail_silhouette_profiles
        if geometry_detail_silhouette_motifs:
            assessment["geometry_detail_silhouette_motifs"] = geometry_detail_silhouette_motifs
    if mesh_grammar_primitives:
        assessment["mesh_grammar_operator_counts"] = dict(sorted(mesh_grammar_operator_counts.items()))
        assessment["mesh_grammar_generated_primitive_count"] = sum(
            1
            for primitive in mesh_grammar_primitives
            if primitive.component in {"mesh_extrude", "mesh_sweep", "mesh_loft"}
        )
        assessment["mesh_grammar_modified_primitive_count"] = sum(
            1
            for primitive in mesh_grammar_primitives
            if any(tag in primitive.tags for tag in {"bevel", "chamfer"})
        )
    return assessment


def _build_shape_ir(
    asset_graph: AssetGraph,
    *,
    blueprint_id: str,
    primitives: list[ShapePrimitive],
    regions: list[ShapeRegion],
    notes: list[str] | None = None,
    primitive_selection: list[dict[str, Any]] | None = None,
) -> ShapeIR:
    extents = _expected_extents(primitives)
    largest = max(NUMERIC_EPSILON, *extents)
    region_x = [region.center[0] / largest for region in regions]
    region_y = [region.center[1] / largest for region in regions]
    region_z = [region.center[2] / largest for region in regions]
    part_targets = {
        region.name: {
            "part": region.part,
            "center": [round(value, 6) for value in region.center],
            "extents": [round(value, 6) for value in region.extents],
            "component": region.component,
        }
        for region in regions
    }
    primitives_used = sorted({primitive.component or primitive.primitive_type for primitive in primitives})
    assessment = _shape_assessment(asset_graph, regions, primitives)
    geometry_detail_controls = geometry_detail_controls_from_authoring(asset_graph.authoring)
    geometry_authoring = _source_geometry_authoring(asset_graph)
    surface_authoring = _source_surface_authoring(asset_graph)
    signature = {
        "expected_extents": extents,
        "projected_ratio": _ratio_signature(extents),
        "minimum_triangle_density": round(
            min(0.88, 0.42 + 0.05 * len(primitives_used) + 0.03 * len(regions)), 6
        ),
        "expected_part_names": [part.name for part in asset_graph.parts],
        "asset_kind": asset_graph.kind,
        "asset_class": str(asset_graph.authoring.get("asset_class") or ""),
        "part_targets": part_targets,
        "adjacency_pairs": list(asset_graph.part_graph),
        "region_spread": [
            round(max(region_x) - min(region_x), 6) if region_x else 0.0,
            round(max(region_y) - min(region_y), 6) if region_y else 0.0,
            round(max(region_z) - min(region_z), 6) if region_z else 0.0,
        ],
        "vertical_profile": _profile_bins(
            region_y, max(NUMERIC_EPSILON, max(region_y) - min(region_y) if region_y else 1.0)
        ),
        "depth_profile": _profile_bins(
            region_z, max(NUMERIC_EPSILON, max(region_z) - min(region_z) if region_z else 1.0)
        ),
        "width_profile": _profile_bins(
            region_x, max(NUMERIC_EPSILON, max(region_x) - min(region_x) if region_x else 1.0)
        ),
        "expected_region_count": len(regions),
        "fragmentation_ceiling": max(4, len(regions) * 3),
        "primitives_used": primitives_used,
        "blueprint_notes": list(notes or []),
    }
    if asset_graph.sockets:
        signature["interface_sockets"] = list(asset_graph.sockets)
    if asset_graph.anchors:
        signature["interface_anchors"] = list(asset_graph.anchors)
    if asset_graph.connections:
        signature["interface_connections"] = [dict(connection) for connection in asset_graph.connections]
    if asset_graph.connection_layout.get("summary", {}).get("connection_count"):
        signature["connection_layout"] = dict(asset_graph.connection_layout)
    creative_grammar = asset_graph.authoring.get("creative_grammar", {})
    if isinstance(creative_grammar, dict) and creative_grammar.get("summary", {}).get("matched_presets"):
        signature["creative_grammar"] = dict(creative_grammar.get("summary", {}))
    object_grammar = asset_graph.authoring.get("object_grammar", {})
    if isinstance(object_grammar, dict) and object_grammar.get("summary", {}).get("matched_archetypes"):
        signature["object_grammar"] = dict(object_grammar.get("summary", {}))
    child_module_layout = asset_graph.authoring.get("child_module_layout", {})
    if isinstance(child_module_layout, dict) and child_module_layout.get("summary", {}).get("slot_count"):
        signature["child_module_layout"] = {
            **dict(child_module_layout.get("summary", {})),
            "slots": [
                {
                    "id": slot.get("id"),
                    "kind": slot.get("kind"),
                    "socket": slot.get("socket"),
                    "anchor": slot.get("anchor"),
                    "mount": slot.get("mount"),
                    "supports": list(slot.get("supports") or []),
                    "normalized_position": list(slot.get("normalized_position") or []),
                    "facing_degrees": slot.get("facing_degrees"),
                    "module": {
                        "instance_id": slot.get("module", {}).get("instance_id"),
                        "template": slot.get("module", {}).get("template"),
                        "family": slot.get("module", {}).get("family"),
                        "archetype": slot.get("module", {}).get("archetype"),
                        "blueprint_id": slot.get("module", {}).get("blueprint_id"),
                        "controls": dict(slot.get("module", {}).get("controls") or {}),
                        "components": list(slot.get("module", {}).get("components") or []),
                    }
                    if isinstance(slot.get("module"), dict)
                    else {},
                }
                for slot in child_module_layout.get("slots", [])
                if isinstance(slot, dict)
            ],
            "instances": [
                {
                    "instance_id": instance.get("instance_id"),
                    "slot_id": instance.get("slot_id"),
                    "kind": instance.get("kind"),
                    "template": instance.get("template"),
                    "family": instance.get("family"),
                    "archetype": instance.get("archetype"),
                    "blueprint_id": instance.get("blueprint_id"),
                    "controls": dict(instance.get("controls") or {}),
                    "components": list(instance.get("components") or []),
                }
                for instance in child_module_layout.get("instances", [])
                if isinstance(instance, dict)
            ],
        }
    nested_assets = nested_asset_manifest_for_signature(asset_graph.authoring.get("nested_assets", {}))
    if nested_assets.get("summary", {}).get("nested_asset_count"):
        signature["nested_assets"] = nested_assets
    if geometry_detail_controls.explicit_fields:
        signature["geometry_detail_controls"] = geometry_detail_controls.to_dict()
    geometry_authoring_signature: dict[str, Any] = {}
    if geometry_authoring:
        for key in ("mode", "meshing_strategy", "seam_classes", "edge_classes", "integration_rules"):
            value = geometry_authoring.get(key)
            if isinstance(value, list):
                cleaned = [str(item) for item in value if str(item)]
                if cleaned:
                    geometry_authoring_signature[key] = cleaned
            elif isinstance(value, str) and value.strip():
                geometry_authoring_signature[key] = value.strip()
    preservation_intents = _preservation_intents_from_authoring(asset_graph)
    if preservation_intents:
        geometry_authoring_signature["preservation_intents"] = list(preservation_intents)
    if geometry_authoring_signature:
        signature["geometry_authoring"] = geometry_authoring_signature
    repair_policy_authoring = _source_repair_policy_authoring(asset_graph)
    if repair_policy_authoring:
        repair_policy_signature: dict[str, Any] = {}
        for key in ("use", "mode"):
            value = repair_policy_authoring.get(key)
            if isinstance(value, str) and value.strip():
                repair_policy_signature[key] = value.strip()
        for key in ("allow", "deny"):
            value = repair_policy_authoring.get(key)
            if isinstance(value, list):
                cleaned = [str(item) for item in value if str(item)]
                if cleaned:
                    repair_policy_signature[key] = cleaned
        if repair_policy_signature:
            signature["repair_policy_authoring"] = repair_policy_signature
    surface_authoring_signature: dict[str, Any] = {}
    for key in ("materials", "material_zones", "patterns", "program", "palette", "style_target"):
        value = surface_authoring.get(key)
        if isinstance(value, list):
            cleaned = [str(item) for item in value if str(item)]
            if cleaned:
                surface_authoring_signature[key] = cleaned
        elif isinstance(value, str) and value.strip():
            surface_authoring_signature[key] = value.strip()
    if asset_graph.materials:
        surface_authoring_signature["intent_materials"] = list(asset_graph.materials)
    style_target = _source_style_target(asset_graph)
    if style_target:
        surface_authoring_signature["intent_style_target"] = style_target
    if surface_authoring_signature:
        signature["surface_authoring"] = surface_authoring_signature
    if assessment.get("mesh_grammar_operator_counts"):
        signature["mesh_grammar"] = {
            "operator_counts": dict(assessment["mesh_grammar_operator_counts"]),
            "generated_primitive_count": int(assessment.get("mesh_grammar_generated_primitive_count", 0) or 0),
            "modified_primitive_count": int(assessment.get("mesh_grammar_modified_primitive_count", 0) or 0),
        }
    summary = primitive_selection_summary(list(primitive_selection or []))
    signature["primitive_selector"] = summary
    assessment["primitive_selector_applied_count"] = summary["applied_count"]
    assessment["primitive_selector_by_component"] = dict(summary["by_component"])
    assessment["primitive_selector_by_target"] = dict(summary["by_target"])
    meshing_strategy = asset_graph.authoring.get("meshing_strategy")
    if isinstance(meshing_strategy, str) and meshing_strategy:
        signature["meshing_strategy"] = meshing_strategy
    return ShapeIR(
        asset_name=asset_graph.name,
        family=asset_graph.family,
        blueprint_id=blueprint_id,
        symmetry_axis=asset_graph.symmetry_axis,
        units="cm",
        primitives=primitives,
        regions=regions,
        primitives_used=primitives_used,
        part_graph=list(asset_graph.part_graph),
        signature=signature,
        assessment=assessment,
    )


# Per-edge-class polybevel mapping for authored ``geometry.edge_classes``.
# The chest-specific wrapper below keeps the old helper import-compatible, but
# the production path is no longer chest-gated: crates, doors, terminals,
# weapons, and new stdlib families can all turn declared edge classes into
# concrete PolyBevel modifiers.
_EDGE_CLASS_BEVEL_DEFAULTS: dict[str, dict[str, Any]] = {
    "hero_bevel": {"width_cm": 0.30, "segments": 3, "role": "hero"},
    "support_bevel": {"width_cm": 0.15, "segments": 2, "role": "support"},
    "trim_edge": {"width_cm": 0.05, "segments": 1, "role": "trim"},
    "cargo_bevel": {"width_cm": 0.22, "segments": 2, "role": "hero"},
    "frame_bevel": {"width_cm": 0.24, "segments": 2, "role": "hero"},
    "screen_bevel": {"width_cm": 0.10, "segments": 2, "role": "trim"},
    "pod_bevel": {"width_cm": 0.18, "segments": 2, "role": "trim"},
    "guard_bevel": {"width_cm": 0.14, "segments": 2, "role": "trim"},
    "pommel_bevel": {"width_cm": 0.10, "segments": 2, "role": "trim"},
    "grip_ridge": {"width_cm": 0.04, "segments": 1, "role": "trim"},
    "sharp_blade_edge": {"width_cm": 0.035, "segments": 1, "role": "hero"},
    "crystal_inlay_edge": {"width_cm": 0.035, "segments": 1, "role": "trim"},
}
_GENERIC_EDGE_CLASS_NAMES = {"hero_bevel", "support_bevel", "trim_edge"}

# Historical chest declarations keep their exact seam targeting.
_CHEST_EDGE_CLASS_BEVELS: dict[str, dict[str, Any]] = {
    "hero_bevel": {
        "width_cm": 0.30,
        "segments": 3,
        "role": "hero",
        "target_seam_groups": ("lid_break", "panel_seam"),
    },
    "support_bevel": {
        "width_cm": 0.15,
        "segments": 2,
        "role": "support",
        "target_seam_groups": ("panel_seam",),
    },
    "trim_edge": {
        "width_cm": 0.05,
        "segments": 1,
        "role": "trim",
        "target_seam_groups": ("clasp_cut",),
    },
}

# Components that wear hero edges versus trim edges. The chest's lid + body
# carry the silhouette-defining bevels; lock/clasp/handle edges get the
# narrower trim chamfer; feet get a support bevel for floor contact.
_EDGE_CLASS_HERO_COMPONENTS = {
    "body",
    "shell",
    "lid",
    "door",
    "panel",
    "frame",
    "bezel",
    "blade",
    "guard",
    "pommel",
    "receiver",
    "housing",
}
_EDGE_CLASS_SUPPORT_COMPONENTS = {
    "foot",
    "feet",
    "stand",
    "base",
    "bracket",
    "support",
    "threshold",
    "hinge",
}
_EDGE_CLASS_TRIM_COMPONENTS = {
    "lock",
    "lock_plate",
    "latch",
    "handle",
    "hinge",
    "clasp",
    "grip",
    "screen",
    "socket",
    "rail",
    "trim",
}

# Backwards-compatible aliases for callers/tests that still import the old
# chest vocabulary.
_CHEST_HERO_COMPONENTS = _EDGE_CLASS_HERO_COMPONENTS
_CHEST_SUPPORT_COMPONENTS = _EDGE_CLASS_SUPPORT_COMPONENTS
_CHEST_TRIM_COMPONENTS = _EDGE_CLASS_TRIM_COMPONENTS


_FEATURE_ALLOW_ALIASES: dict[str, str] = {
    "bolt_grid": "fastener_grid",
    "bolted_grid": "fastener_grid",
    "cargo_fastener_grid": "fastener_grid",
    "clasp_set": "fastener_grid",
    "fastener_grid": "fastener_grid",
    "fastener_strip": "fastener_grid",
    "linear_detail_array": "fastener_grid",
    "radial_detail_array": "fastener_grid",
    "rivet_row": "fastener_grid",
    "rivet_row_hero": "fastener_grid",
    "rivet_grid": "fastener_grid",
    "rivet_strip": "fastener_grid",
    "blade_fuller_line": "panel_line",
    "blade_star_channel": "panel_line",
    "corner_guard": "corner_guard",
    "corner_guard_set": "corner_guard",
    "corner_protection": "corner_guard",
    "edge_break": "edge_break",
    "bevel": "edge_break",
    "chamfer": "edge_break",
    "frame_lip": "panel_frame",
    "panel_frame": "panel_frame",
    "screen_bezel": "panel_frame",
    "bezel": "panel_frame",
    "handle": "handle",
    "handle_pull": "handle",
    "pull_handle": "handle",
    "recessed_handle": "handle",
    "grab_handle": "handle",
    "hinge": "hinge",
    "hinge_set": "hinge",
    "groove": "panel_line",
    "groove_channel": "panel_line",
    "panel_groove": "panel_line",
    "panel_line": "panel_line",
    "panel_seam": "panel_line",
    "plank_spacing": "panel_line",
    "plank_spacing_hero": "panel_line",
    "cutline": "panel_line",
    "inset": "inset_panel",
    "inset_panel": "inset_panel",
    "recessed_panel": "inset_panel",
    "leather_wrap_ridges": "trim_band",
    "layer_plate": "trim_band",
    "midnight_wrap_ridges": "trim_band",
    "moon_guard_trim": "trim_band",
    "outset_panel": "trim_band",
    "raised_ridge": "trim_band",
    "ridge": "trim_band",
    "strap": "trim_band",
    "shelf_edge_wear": "trim_band",
    "fin": "trim_band",
    "trim_band": "trim_band",
    "trim_strip": "trim_band",
    "vertical_oak_grain": "trim_band",
    "warning_stripe_band": "trim_band",
    "support_bracket": "support_bracket",
    "bracket": "support_bracket",
    "guard_bar": "support_bracket",
    "mount_plate": "mount_plate",
    "mounting_plate": "mount_plate",
    "latch_plate": "latch_plate",
    "lock_plate": "latch_plate",
    "rotor_shroud": "tube_shroud",
    "shroud": "tube_shroud",
    "tube_shroud": "tube_shroud",
    "cable": "tube_shroud",
    "conduit_run": "conduit_run",
    "cable_run": "conduit_run",
    "wire_run": "conduit_run",
    "rail": "rail",
    "guide_rail": "rail",
    "support_rail": "rail",
    "structural_beam": "structural_beam",
    "beam": "structural_beam",
    "i_beam": "structural_beam",
    "truss": "truss_frame",
    "truss_frame": "truss_frame",
    "ladder": "ladder_frame",
    "ladder_frame": "ladder_frame",
    "capsule": "capsule_strut",
    "capsule_strut": "capsule_strut",
    "rounded_strut": "capsule_strut",
    "socket": "socket_point",
    "socket_point": "socket_point",
    "mount_socket": "socket_point",
    "vent_grille": "vent_slats",
    "vent_grid": "vent_slats",
    "vent_stack": "vent_slats",
    "vent_slats": "vent_slats",
    "louver": "vent_slats",
    "louver_panel": "vent_slats",
    "edge_wear": "edge_wear",
    "chip_edges": "edge_wear",
    "worn_edge": "edge_wear",
    "grime_mask": "grime_mask",
    "surface_grime": "grime_mask",
    "weld_seam": "weld_seam",
    "weld_bead": "weld_seam",
    "mirror_instances": "mirror_instances",
    "mirrored_instances": "mirror_instances",
    "symmetry_instances": "mirror_instances",
}

_FEATURE_ALLOW_APPLICATION_ORDER = (
    "inset_panel",
    "panel_line",
    "socket_point",
    "panel_frame",
    "trim_band",
    "fastener_grid",
    "vent_slats",
    "mount_plate",
    "latch_plate",
    "handle",
    "hinge",
    "conduit_run",
    "tube_shroud",
    "rail",
    "structural_beam",
    "truss_frame",
    "ladder_frame",
    "capsule_strut",
    "support_bracket",
    "corner_guard",
    "weld_seam",
    "edge_wear",
    "grime_mask",
    "mirror_instances",
    "edge_break",
)

_FEATURE_ALLOW_MODIFIER_KEYS = {
    "inset_panel": "v2_inset_modifier",
    "panel_line": "v2_cut_panel_line_modifier",
    "socket_point": "v2_socket_modifier",
    "panel_frame": "v2_panel_frame_modifier",
    "trim_band": "v2_trim_band_modifier",
    "fastener_grid": "v2_fastener_grid_modifier",
    "vent_slats": "v2_vent_slats_modifier",
    "mount_plate": "v2_mount_plate_modifier",
    "latch_plate": "v2_mount_plate_modifier",
    "handle": "v2_handle_modifier",
    "hinge": "v2_hinge_modifier",
    "conduit_run": "v2_tube_modifier",
    "tube_shroud": "v2_tube_modifier",
    "rail": "v2_rail_modifier",
    "structural_beam": "v2_structural_beam_modifier",
    "truss_frame": "v2_truss_frame_modifier",
    "ladder_frame": "v2_ladder_frame_modifier",
    "capsule_strut": "v2_capsule_modifier",
    "support_bracket": "v2_bracket_modifier",
    "corner_guard": "v2_corner_guard_set_modifier",
    "weld_seam": "v2_weld_seam_modifier",
    "edge_wear": "v2_chip_edges_modifier",
    "grime_mask": "v2_grime_mask_modifier",
    "mirror_instances": "v2_mirror_modifier",
}

_FEATURE_ALLOW_SOURCE_REPLACERS = {
    "v2_inset_modifier",
    "v2_cut_panel_line_modifier",
    "v2_socket_modifier",
}

_FEATURE_ALLOW_MAX_TARGETS = {
    "edge_break": 12,
    "inset_panel": 2,
    "panel_line": 2,
    "socket_point": 1,
    "panel_frame": 1,
    "trim_band": 2,
    "fastener_grid": 1,
    "vent_slats": 1,
    "mount_plate": 1,
    "latch_plate": 1,
    "handle": 1,
    "hinge": 1,
    "conduit_run": 1,
    "tube_shroud": 1,
    "rail": 2,
    "structural_beam": 1,
    "truss_frame": 1,
    "ladder_frame": 1,
    "capsule_strut": 2,
    "support_bracket": 1,
    "corner_guard": 1,
    "weld_seam": 2,
    "edge_wear": 1,
    "grime_mask": 1,
    "mirror_instances": 1,
}

_FEATURE_ALLOW_TARGET_HINTS = {
    "inset_panel": {"body", "shell", "door", "panel", "lid", "cabinet", "crate", "container"},
    "panel_line": {"body", "shell", "door", "panel", "floor", "wall", "module", "case"},
    "socket_point": {"socket", "plate", "panel", "door", "adapter", "cabinet", "module"},
    "panel_frame": {"screen", "bezel", "frame", "door", "panel", "terminal", "cabinet"},
    "trim_band": {"body", "shell", "lid", "trim", "frame", "guard", "blade", "panel", "cabinet"},
    "fastener_grid": {"body", "shell", "panel", "plate", "lid", "door", "bracket", "case"},
    "vent_slats": {"vent", "screen", "bezel", "panel", "door", "terminal", "cabinet", "drone"},
    "mount_plate": {"mount", "plate", "socket", "bracket", "module", "panel", "door", "cabinet"},
    "latch_plate": {"latch", "lock", "clasp", "door", "lid", "panel", "cabinet"},
    "handle": {"handle", "door", "lid", "drawer", "cabinet", "crate", "case"},
    "hinge": {"hinge", "door", "lid", "cabinet", "case", "frame"},
    "conduit_run": {"conduit", "cable", "pipe", "wire", "route", "duct", "module", "panel"},
    "tube_shroud": {"rotor", "shroud", "pod", "engine", "drone", "fan", "vent"},
    "rail": {"rail", "runner", "guide", "track", "frame", "support", "panel", "door"},
    "structural_beam": {"beam", "girder", "support", "frame", "chassis", "strut", "bridge", "truss"},
    "truss_frame": {"truss", "frame", "bridge", "support", "brace", "lattice", "girder"},
    "ladder_frame": {"ladder", "rung", "rail", "frame", "support", "access"},
    "capsule_strut": {"strut", "bar", "rod", "capsule", "rounded", "support", "brace"},
    "support_bracket": {"bracket", "support", "base", "stand", "frame", "body", "shell"},
    "corner_guard": {"body", "shell", "crate", "case", "container", "panel", "cabinet"},
    "weld_seam": {"weld", "seam", "joint", "edge", "panel", "body", "shell"},
    "edge_wear": {"edge", "wear", "chip", "chipped", "damage", "body", "panel"},
    "grime_mask": {"grime", "dirty", "dirt", "stain", "oil", "surface", "panel", "body"},
    "mirror_instances": {"mirror", "mirrored", "symmetric", "symmetry", "instance", "paired", "panel"},
    "edge_break": set(),
}

_REPAIR_POLICY_HARDSURFACE_DEFAULT_FEATURES = (
    "edge_break",
    "trim_band",
    "rail",
    "fastener_grid",
    "panel_frame",
    "support_bracket",
)

_REPAIR_POLICY_ACTION_FEATURES: dict[str, tuple[str, ...]] = {
    "add_secondary_features": ("trim_band", "rail", "capsule_strut", "fastener_grid", "vent_slats", "weld_seam"),
    "restore_edge_treatment": ("edge_break", "weld_seam", "edge_wear"),
    "increase_panel_depth": ("panel_frame", "trim_band", "inset_panel"),
    "improve_attachment_integration": (
        "socket_point",
        "support_bracket",
        "mount_plate",
        "latch_plate",
        "handle",
        "rail",
        "capsule_strut",
    ),
    "refine_support_layout": ("support_bracket", "mount_plate", "rail", "structural_beam", "truss_frame"),
    "restore_hinge_alignment": ("hinge", "support_bracket"),
    "reauthor_surface_layer": ("edge_wear", "grime_mask"),
    "shroud_exposed_frame": ("tube_shroud",),
}

_GEOMETRY_DETAIL_COMPONENT_FRAGMENT_ALIASES: dict[str, str] = {
    "cable": "cable_span",
    "fin": "stabilizer",
    "guard_bar": "guardrail",
    "guard_cowl": "guard",
    "power_cell": "module_socket",
    "power_core": "module_socket",
    "sensor_mast": "mast",
    "sensor_pod": "rotor_pod",
    "shield_plate": "socket_plate",
    "spine": "stabilizer",
}

_BOOLEAN_INTEGRATION_RULES = {
    "boolean_union",
    "boolean_difference",
    "boolean_intersection",
    "component_assembly",
    "modular_assembly",
}

_INTEGRATION_TOKEN_ALIASES = {
    "bezels": "bezel",
    "columns": "column",
    "doors": "door",
    "frames": "frame",
    "guards": "guard",
    "mounts": "mount",
    "panels": "panel",
    "rotors": "rotor",
    "seams": "seam",
    "shelves": "shelf",
    "slats": "slat",
    "splits": "split",
    "straps": "strap",
    "thresholds": "threshold",
}

_INTEGRATION_STOP_TOKENS = {
    "constraint",
    "geometry",
    "keep",
    "maintain",
    "preserve",
    "protect",
    "rule",
}

_INTEGRATION_BREAK_TOKENS = {
    "break",
    "cut",
    "line",
    "seam",
    "spacing",
    "split",
    "threshold",
}

_INTEGRATION_BODY_FALLBACK_TOKENS = {
    "body",
    "cabinet",
    "case",
    "container",
    "crate",
    "door",
    "frame",
    "lid",
    "panel",
    "shell",
}

_INTEGRATION_GLOBAL_PRESERVE_TOKENS = {
    "border",
    "borders",
    "boundary",
    "edge",
    "edges",
    "graph",
    "hard",
    "interface",
    "interfaces",
    "part",
    "proportion",
    "proportions",
    "shape",
    "silhouette",
    "symmetry",
}

_INTEGRATION_FEATURE_MAX_TARGETS = {
    "corner_guard": 1,
    "handle": 1,
    "hinge": 1,
    "panel_frame": 1,
    "panel_line": 2,
    "socket_point": 2,
    "support_bracket": 2,
    "trim_band": 2,
    "vent_slats": 1,
}

_MATERIAL_ZONE_TOKEN_ALIASES = {
    "aluminium": "aluminum",
    "bodywork": "body",
    "carbonfiber": "carbon",
    "colours": "color",
    "colors": "color",
    "emissives": "emissive",
    "glasses": "glass",
    "metals": "metal",
    "paints": "paint",
    "screens": "screen",
    "steels": "steel",
    "trims": "trim",
}

_MATERIAL_BODY_HINTS = {
    "aluminum",
    "body",
    "ceramic",
    "composite",
    "concrete",
    "core",
    "enamel",
    "metal",
    "oak",
    "paint",
    "painted",
    "panel",
    "plastic",
    "steel",
    "stone",
    "wood",
}

_MATERIAL_TRIM_HINTS = {
    "brass",
    "carbon",
    "dark",
    "edge",
    "guard",
    "leather",
    "metal",
    "rubber",
    "seal",
    "strap",
    "trim",
}

_MATERIAL_GLASS_HINTS = {
    "amber",
    "crystal",
    "emissive",
    "glass",
    "lens",
    "screen",
    "signal",
    "smoked",
}

_MATERIAL_WARNING_HINTS = {
    "hazard",
    "mark",
    "marking",
    "paint",
    "stripe",
    "warning",
}

_SURFACE_DAMAGE_ALIASES = {
    "battle_worn": ("v2_chip_edges_modifier", "chip_edges"),
    "chip": ("v2_chip_edges_modifier", "chip_edges"),
    "chipped": ("v2_chip_edges_modifier", "chip_edges"),
    "chipped_paint": ("v2_chip_edges_modifier", "chip_edges"),
    "edge_wear": ("v2_chip_edges_modifier", "chip_edges"),
    "worn_edge": ("v2_chip_edges_modifier", "chip_edges"),
    "scratch": ("v2_scratch_mask_modifier", "scratch_mask"),
    "scratches": ("v2_scratch_mask_modifier", "scratch_mask"),
    "scuff": ("v2_scratch_mask_modifier", "scratch_mask"),
    "scuffed": ("v2_scratch_mask_modifier", "scratch_mask"),
    "dent": ("v2_dent_mask_modifier", "dent_mask"),
    "dented": ("v2_dent_mask_modifier", "dent_mask"),
    "impact": ("v2_dent_mask_modifier", "dent_mask"),
    "grime": ("v2_grime_mask_modifier", "grime_mask"),
    "dirt": ("v2_grime_mask_modifier", "grime_mask"),
    "moss": ("v2_grime_mask_modifier", "grime_mask"),
    "oil": ("v2_grime_mask_modifier", "grime_mask"),
    "patina": ("v2_grime_mask_modifier", "grime_mask"),
    "weathered": ("v2_grime_mask_modifier", "grime_mask"),
}


def _edge_class_polybevel_modifier(spec: dict[str, Any], existing_targets: set[str]) -> dict[str, Any]:
    target_groups = list(spec.get("target_seam_groups") or [])
    edge_class = str(spec.get("name") or "edge_class")
    return {
        "width_cm": float(spec["width_cm"]),
        "segments": int(spec["segments"]),
        "target_seam_groups": target_groups,
        "edge_class": edge_class,
        "v2_op": str(spec.get("v2_op") or "sop.polybevel"),
        "operation_id": str(
            spec.get("operation_id") or f"edge_class:{edge_class}:polybevel"
        ),
        "source_boolean_seam_group_count": len(existing_targets),
    }


def _chest_polybevel_modifier(spec: dict[str, Any], existing_targets: set[str]) -> dict[str, Any]:
    return _edge_class_polybevel_modifier(spec, existing_targets)


def _source_geometry_authoring(asset_graph: AssetGraph) -> dict[str, Any]:
    authoring = asset_graph.authoring if isinstance(asset_graph.authoring, dict) else {}
    geometry: dict[str, Any] = {}
    resolved_family = authoring.get("resolved_family")
    if isinstance(resolved_family, dict):
        family_geometry = resolved_family.get("geometry")
        if isinstance(family_geometry, dict):
            geometry.update(family_geometry)
    for key in ("geometry", "source_geometry"):
        value = authoring.get(key)
        if isinstance(value, dict):
            geometry.update(value)
    return geometry


def _edge_class_tokens(value: str) -> set[str]:
    tokens = {
        token
        for token in str(value).replace("-", "_").replace(":", "_").split("_")
        if token
    }
    return tokens - {"edge", "bevel", "curve", "class", "soft"}


def _edge_class_text_values(value: Any) -> list[str]:
    if isinstance(value, str):
        stripped = value.strip()
        return [stripped] if stripped else []
    if isinstance(value, dict):
        return [str(key) for key in value.keys() if str(key)]
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if str(item)]
    return []


def _edge_class_declarations(geometry_authoring: dict[str, Any]) -> list[Any]:
    declarations: list[Any] = []
    raw_edge_classes = geometry_authoring.get("edge_classes")
    if isinstance(raw_edge_classes, dict):
        for name, value in raw_edge_classes.items():
            if isinstance(value, dict):
                declared = dict(value)
                declared.setdefault("name", str(name))
                declarations.append(declared)
            elif value:
                declarations.append(str(name))
    elif isinstance(raw_edge_classes, (list, tuple, set)):
        declarations.extend(raw_edge_classes)
    elif isinstance(raw_edge_classes, str):
        declarations.append(raw_edge_classes)

    raw_specs = geometry_authoring.get("edge_class_specs")
    if isinstance(raw_specs, dict):
        for name, value in raw_specs.items():
            if isinstance(value, dict):
                declared = dict(value)
                declared.setdefault("name", str(name))
                declarations.append(declared)
    elif isinstance(raw_specs, (list, tuple)):
        declarations.extend(item for item in raw_specs if isinstance(item, dict))
    return declarations


def _feature_allow_kinds(asset_graph: AssetGraph) -> dict[str, tuple[str, str]]:
    authoring = asset_graph.authoring if isinstance(asset_graph.authoring, dict) else {}
    kinds: dict[str, tuple[str, str]] = {}

    def add_fragment(fragment: str, source: str) -> None:
        slug = _slug_fragment(fragment)
        kind = _FEATURE_ALLOW_ALIASES.get(slug)
        if kind is None:
            tokens = set(slug.split("_"))
            if {"bolt", "grid"} <= tokens or {"fastener", "strip"} <= tokens:
                kind = "fastener_grid"
            elif {"panel", "seam"} <= tokens or "groove" in tokens:
                kind = "panel_line"
            elif {"vent", "grille"} <= tokens or "louver" in tokens:
                kind = "vent_slats"
            elif "trim" in tokens or "ridge" in tokens:
                kind = "trim_band"
            elif "bracket" in tokens:
                kind = "support_bracket"
            elif {"corner", "guard"} <= tokens:
                kind = "corner_guard"
            elif "socket" in tokens:
                kind = "socket_point"
            elif "handle" in tokens:
                kind = "handle"
            elif "hinge" in tokens:
                kind = "hinge"
            elif "shroud" in tokens:
                kind = "tube_shroud"
        if kind and kind not in kinds:
            kinds[kind] = (slug, source)

    for fragment in _iter_text_fragments(authoring.get("feature_allow")):
        add_fragment(fragment, "feature_allow_authoring")
    for fragment in _iter_text_fragments(authoring.get("surface_patterns")):
        add_fragment(fragment, "surface_pattern_authoring")
    source_surface = authoring.get("source_surface")
    if isinstance(source_surface, dict):
        for fragment in _iter_text_fragments(source_surface.get("patterns")):
            add_fragment(fragment, "source_surface_pattern_authoring")

    detail_controls = geometry_detail_controls_from_authoring(authoring)
    if detail_controls.active:
        for fragment in detail_controls.detail_motifs:
            add_fragment(fragment, "geometry_detail_motif_authoring")
        for fragment in detail_controls.attachment_motifs:
            add_fragment(fragment, "geometry_detail_attachment_authoring")
        for fragment in detail_controls.module_sockets:
            add_fragment(fragment, "geometry_detail_socket_authoring")
        for zone in detail_controls.zones:
            for fragment in zone.motifs:
                add_fragment(fragment, f"geometry_detail_zone:{zone.name}:motifs")
            for fragment in zone.attachment_motifs:
                add_fragment(fragment, f"geometry_detail_zone:{zone.name}:attachments")
        if detail_controls.panelization > 0.0:
            add_fragment("panel_seam", "geometry_detail_panelization")
        if detail_controls.groove_density > 0.0:
            add_fragment("groove_channel", "geometry_detail_groove_density")
        if detail_controls.ridge_density > 0.0:
            add_fragment("raised_ridge", "geometry_detail_ridge_density")
        if detail_controls.trim_density > 0.0:
            add_fragment("trim_band", "geometry_detail_trim_density")
        if detail_controls.inset_depth > 0.0:
            add_fragment("inset_panel", "geometry_detail_inset_depth")
        if detail_controls.outset_depth > 0.0:
            add_fragment("outset_panel", "geometry_detail_outset_depth")
        if detail_controls.modular_attachment_points > 0:
            add_fragment("socket_point", "geometry_detail_modular_attachment_points")
        if (
            detail_controls.edge_complexity > 1.0
            or detail_controls.bevel_width > 0.0
            or detail_controls.chamfer_width > 0.0
        ):
            add_fragment("edge_break", "geometry_detail_edge_treatment")
    return kinds


def _feature_box_extents(primitive: ShapePrimitive) -> tuple[float, float, float] | None:
    if primitive.primitive_type in {"box", "subdivision_box"} and primitive.extents is not None:
        try:
            extents = tuple(float(value) for value in primitive.extents)
        except (TypeError, ValueError):
            return None
    else:
        try:
            bounds_min, bounds_max = _primitive_bounds(primitive)
        except (ContractViolation, ValueError, TypeError, AttributeError):
            return None
        extents = tuple(
            max(float(bounds_max[index]) - float(bounds_min[index]), 0.0)
            for index in range(3)
        )
    if len(extents) != 3 or any(value <= NUMERIC_EPSILON for value in extents):
        return None
    return (extents[0], extents[1], extents[2])


def _feature_axis_index(axis: str) -> int:
    return {"x": 0, "y": 1, "z": 2}.get(str(axis), 2)


def _feature_tangent_axes(normal_axis: str) -> tuple[str, str]:
    if normal_axis == "x":
        return ("y", "z")
    if normal_axis == "y":
        return ("x", "z")
    return ("x", "y")


def _feature_face_axes(extents: tuple[float, float, float]) -> tuple[str, str, str]:
    axes = ("x", "y", "z")
    min_index = min(range(3), key=lambda index: extents[index])
    normal_axis = axes[min_index] if extents[min_index] <= max(extents) * 0.42 else "z"
    tangent_a, tangent_b = _feature_tangent_axes(normal_axis)
    if extents[_feature_axis_index(tangent_b)] > extents[_feature_axis_index(tangent_a)]:
        return normal_axis, tangent_b, tangent_a
    return normal_axis, tangent_a, tangent_b


def _feature_extent(extents: tuple[float, float, float], axis: str) -> float:
    return max(float(extents[_feature_axis_index(axis)]), NUMERIC_EPSILON)


def _feature_clamp(value: float, lower: float, upper: float) -> float:
    upper = max(float(lower), float(upper))
    return max(float(lower), min(float(value), upper))


def _feature_shifted_center(
    primitive: ShapePrimitive,
    *,
    axis: str,
    offset: float,
) -> tuple[float, float, float]:
    center = [float(value) for value in primitive.center]
    center[_feature_axis_index(axis)] += float(offset)
    return (round(center[0], 6), round(center[1], 6), round(center[2], 6))


def _feature_target_tokens(primitive: ShapePrimitive) -> set[str]:
    raw = "_".join(
        [
            str(primitive.component or ""),
            str(primitive.part or ""),
            str(primitive.region or ""),
            *[str(tag) for tag in primitive.tags],
        ]
    )
    return _edge_class_tokens(_slug_fragment(raw))


def _feature_allow_target_score(
    primitive: ShapePrimitive,
    *,
    kind: str,
    index: int,
) -> tuple[float, int] | None:
    extents = _feature_box_extents(primitive)
    if extents is None:
        return None
    role = _primitive_edge_role(primitive)
    score = {"hero": 50.0, "support": 28.0, "trim": 20.0}.get(role, 10.0)
    tokens = _feature_target_tokens(primitive)
    hints = _FEATURE_ALLOW_TARGET_HINTS.get(kind, set())
    if hints and tokens & hints:
        score += 32.0
    if tokens & {"body", "shell", "lid", "door", "panel", "frame", "case", "crate", "cabinet"}:
        score += 16.0
    if kind in {"support_bracket", "corner_guard", "mount_plate", "latch_plate"} and role == "support":
        score += 12.0
    if kind == "vent_slats" and tokens & {"vent", "screen", "terminal"}:
        score += 24.0
    if kind == "socket_point" and tokens & {"socket", "adapter", "plate"}:
        score += 24.0
    if kind in {"mount_plate", "latch_plate"} and tokens & {"mount", "plate", "latch", "lock", "door", "lid"}:
        score += 24.0
    if kind in {"handle", "hinge"} and tokens & {"handle", "hinge", "door", "lid"}:
        score += 24.0
    if kind == "conduit_run" and tokens & {"conduit", "cable", "wire", "route", "module"}:
        score += 24.0
    if kind == "tube_shroud" and tokens & {"rotor", "pod", "engine", "drone"}:
        score += 24.0
    if kind in {"rail", "structural_beam", "truss_frame", "ladder_frame", "capsule_strut"} and tokens & {
        "rail",
        "beam",
        "truss",
        "ladder",
        "strut",
        "support",
        "frame",
        "track",
        "brace",
    }:
        score += 24.0
    if kind in {"weld_seam", "edge_wear", "grime_mask"} and tokens & {"edge", "seam", "panel", "body", "shell"}:
        score += 18.0
    if kind == "mirror_instances" and tokens & {"mirror", "symmetry", "symmetric", "instance", "paired", "panel"}:
        score += 18.0
    face_area = sorted(extents)[-1] * sorted(extents)[-2]
    score += min(face_area, 10000.0) * 0.0001
    return score, index


def _feature_allow_targets(
    primitives: list[ShapePrimitive],
    *,
    kind: str,
) -> list[ShapePrimitive]:
    scored: list[tuple[float, int, ShapePrimitive]] = []
    for index, primitive in enumerate(primitives):
        score = _feature_allow_target_score(primitive, kind=kind, index=index)
        if score is None:
            continue
        scored.append((score[0], score[1], primitive))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [primitive for _, _, primitive in scored]


def _feature_modifier_common(
    primitive: ShapePrimitive,
    *,
    kind: str,
    source_token: str,
    source_name: str,
) -> dict[str, Any]:
    source_slug = _slug_fragment(source_name)
    operation_prefix = "feature_allow" if source_slug.startswith("feature_allow") else source_slug
    target = _slug_fragment(
        "_".join(
            [
                str(primitive.part or "body"),
                str(primitive.component or primitive.primitive_type),
                str(primitive.region or ""),
            ]
        )
    )
    return {
        "source": source_name,
        "feature_allow": source_token,
        "feature_token": source_token,
        "target": target,
        "operation_id": f"{operation_prefix}:{kind}:{target}",
    }


def _feature_density_multiplier(asset_graph: AssetGraph) -> float:
    authoring = asset_graph.authoring if isinstance(asset_graph.authoring, dict) else {}
    raw = str(authoring.get("feature_density") or "").strip().lower()
    if raw in {"cinematic", "ultra", "very_high", "dense_hero"}:
        return 1.55
    if raw in {"hero", "high", "dense"}:
        return 1.35
    if raw in {"medium", "standard", "default"}:
        return 1.0
    if raw in {"low", "sparse", "mobile"}:
        return 0.75
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return 1.0
    return _feature_clamp(value, 0.5, 2.0)


def _feature_density_count(value: int, multiplier: float, *, lower: int, upper: int) -> int:
    scaled = int(round(float(value) * max(0.5, float(multiplier))))
    return max(lower, min(upper, scaled))


def _feature_density_adjusted_modifier(
    modifier: dict[str, Any],
    *,
    kind: str,
    density_multiplier: float,
) -> dict[str, Any]:
    if abs(density_multiplier - 1.0) <= NUMERIC_EPSILON:
        return modifier
    adjusted = dict(modifier)
    adjusted["feature_density_multiplier"] = round(float(density_multiplier), 6)
    if kind == "fastener_grid":
        adjusted["rows"] = _feature_density_count(int(adjusted.get("rows") or 1), density_multiplier, lower=1, upper=5)
        adjusted["columns"] = _feature_density_count(
            int(adjusted.get("columns") or 1),
            density_multiplier,
            lower=2,
            upper=10,
        )
    elif kind == "vent_slats":
        adjusted["count"] = _feature_density_count(int(adjusted.get("count") or 1), density_multiplier, lower=2, upper=12)
    elif kind == "trim_band":
        adjusted["width_cm"] = round(float(adjusted.get("width_cm") or 0.0) * _feature_clamp(density_multiplier, 0.75, 1.25), 6)
    elif kind in {"panel_frame", "support_bracket", "corner_guard", "mount_plate", "latch_plate"}:
        if "thickness_cm" in adjusted:
            adjusted["thickness_cm"] = round(
                float(adjusted.get("thickness_cm") or 0.0) * _feature_clamp(density_multiplier, 0.8, 1.25),
                6,
            )
    elif kind == "rail":
        adjusted["profile_cm"] = round(float(adjusted.get("profile_cm") or 0.0) * _feature_clamp(density_multiplier, 0.8, 1.25), 6)
    elif kind == "structural_beam":
        for key in ("width_cm", "height_cm", "web_thickness_cm", "flange_thickness_cm"):
            if key in adjusted:
                adjusted[key] = round(float(adjusted.get(key) or 0.0) * _feature_clamp(density_multiplier, 0.85, 1.2), 6)
    elif kind == "truss_frame":
        adjusted["bay_count"] = _feature_density_count(int(adjusted.get("bay_count") or 1), density_multiplier, lower=2, upper=12)
        adjusted["member_radius_cm"] = round(
            float(adjusted.get("member_radius_cm") or 0.0) * _feature_clamp(density_multiplier, 0.8, 1.2),
            6,
        )
    elif kind == "ladder_frame":
        adjusted["rung_count"] = _feature_density_count(int(adjusted.get("rung_count") or 1), density_multiplier, lower=2, upper=16)
        adjusted["rail_radius_cm"] = round(
            float(adjusted.get("rail_radius_cm") or 0.0) * _feature_clamp(density_multiplier, 0.8, 1.2),
            6,
        )
    elif kind == "capsule_strut":
        adjusted["radius_cm"] = round(float(adjusted.get("radius_cm") or 0.0) * _feature_clamp(density_multiplier, 0.8, 1.25), 6)
    elif kind in {"edge_wear", "grime_mask"}:
        adjusted["count"] = _feature_density_count(int(adjusted.get("count") or 1), density_multiplier, lower=1, upper=8)
    elif kind == "weld_seam":
        adjusted["width_cm"] = round(float(adjusted.get("width_cm") or 0.0) * _feature_clamp(density_multiplier, 0.8, 1.25), 6)
    elif kind == "mirror_instances":
        adjusted["mirror_offset_scale"] = round(_feature_clamp(density_multiplier, 0.75, 1.35), 6)
    return adjusted


def _feature_allow_modifier_payload(
    primitive: ShapePrimitive,
    *,
    kind: str,
    source_token: str,
    source_name: str,
) -> tuple[str, dict[str, Any]] | None:
    extents = _feature_box_extents(primitive)
    if extents is None:
        return None
    normal_axis, length_axis, width_axis = _feature_face_axes(extents)
    normal_extent = _feature_extent(extents, normal_axis)
    length_extent = _feature_extent(extents, length_axis)
    width_extent = _feature_extent(extents, width_axis)
    face_minor = min(length_extent, width_extent)
    common = _feature_modifier_common(
        primitive,
        kind=kind,
        source_token=source_token,
        source_name=source_name,
    )
    if primitive.primitive_type != "box":
        fallback_common = {
            **common,
            "normal_axis": normal_axis,
            "side": "positive",
            "fallback_from": _FEATURE_ALLOW_MODIFIER_KEYS.get(kind, kind),
            "fallback_reason": (
                "source primitive preserves non-box silhouette; using raised attachment "
                "instead of a source-replacing cut"
            ),
        }
        if kind in {"inset_panel", "socket_point"}:
            return (
                "v2_panel_frame_modifier",
                {
                    **fallback_common,
                    "width_axis": length_axis,
                    "height_axis": width_axis,
                    "width_cm": max(length_extent * (0.72 if kind == "inset_panel" else 0.28), NUMERIC_EPSILON),
                    "height_cm": max(width_extent * (0.56 if kind == "inset_panel" else 0.24), NUMERIC_EPSILON),
                    "border_width_cm": _feature_clamp(face_minor * 0.05, 0.14, 1.1),
                    "thickness_cm": _feature_clamp(normal_extent * 0.045, 0.08, 0.45),
                },
            )
        if kind == "panel_line":
            return (
                "v2_trim_band_modifier",
                {
                    **fallback_common,
                    "length_axis": length_axis,
                    "width_axis": width_axis,
                    "length_cm": max(length_extent * 0.78, NUMERIC_EPSILON),
                    "width_cm": _feature_clamp(face_minor * 0.026, 0.08, 0.55),
                    "thickness_cm": _feature_clamp(normal_extent * 0.04, 0.06, 0.35),
                    "pattern": "strip",
                },
            )
    if kind == "inset_panel":
        return (
            "v2_inset_modifier",
            {
                **common,
                "normal_axis": normal_axis,
                "side": "positive",
                "depth_cm": _feature_clamp(normal_extent * 0.08, 0.12, 1.2),
                "margin_cm": _feature_clamp(face_minor * 0.12, 0.35, face_minor * 0.32),
                "bevel_width_cm": _feature_clamp(face_minor * 0.012, 0.025, 0.16),
            },
        )
    if kind == "panel_line":
        return (
            "v2_cut_panel_line_modifier",
            {
                **common,
                "normal_axis": normal_axis,
                "side": "positive",
                "line_axis": length_axis,
                "length_cm": max(length_extent * 0.78, NUMERIC_EPSILON),
                "width_cm": _feature_clamp(face_minor * 0.026, 0.08, 0.55),
                "depth_cm": _feature_clamp(normal_extent * 0.055, 0.08, 0.8),
                "bevel_width_cm": _feature_clamp(face_minor * 0.008, 0.0, 0.12),
            },
        )
    if kind == "socket_point":
        socket_width = _feature_clamp(length_extent * 0.18, 0.45, max(length_extent * 0.45, 0.45))
        socket_height = _feature_clamp(width_extent * 0.18, 0.35, max(width_extent * 0.45, 0.35))
        return (
            "v2_socket_modifier",
            {
                **common,
                "normal_axis": normal_axis,
                "side": "positive",
                "center": primitive.center,
                "width_cm": socket_width,
                "height_cm": socket_height,
                "depth_cm": _feature_clamp(normal_extent * 0.10, 0.10, 0.9),
                "socket_shape": "rounded_slot" if socket_width > socket_height * 1.35 else "box",
                "bevel_width_cm": _feature_clamp(face_minor * 0.012, 0.0, 0.14),
            },
        )
    if kind == "panel_frame":
        return (
            "v2_panel_frame_modifier",
            {
                **common,
                "normal_axis": normal_axis,
                "side": "positive",
                "width_axis": length_axis,
                "height_axis": width_axis,
                "width_cm": max(length_extent * 0.78, NUMERIC_EPSILON),
                "height_cm": max(width_extent * 0.62, NUMERIC_EPSILON),
                "border_width_cm": _feature_clamp(face_minor * 0.055, 0.18, 1.4),
                "thickness_cm": _feature_clamp(normal_extent * 0.065, 0.10, 0.7),
            },
        )
    if kind == "trim_band":
        return (
            "v2_trim_band_modifier",
            {
                **common,
                "normal_axis": normal_axis,
                "side": "positive",
                "length_axis": length_axis,
                "width_axis": width_axis,
                "length_cm": max(length_extent * 0.88, NUMERIC_EPSILON),
                "width_cm": _feature_clamp(face_minor * 0.07, 0.16, 1.6),
                "thickness_cm": _feature_clamp(normal_extent * 0.06, 0.10, 0.65),
                "pattern": "strip",
            },
        )
    if kind == "fastener_grid":
        columns = 4 if length_extent >= 10.0 else 3
        rows = 2 if width_extent >= 3.5 else 1
        spacing = min(
            length_extent / float(columns + 1),
            width_extent / float(rows + 1) if rows > 1 else length_extent / float(columns + 1),
        )
        if spacing <= NUMERIC_EPSILON:
            return None
        return (
            "v2_fastener_grid_modifier",
            {
                **common,
                "normal_axis": normal_axis,
                "side": "positive",
                "row_axis": width_axis,
                "column_axis": length_axis,
                "rows": rows,
                "columns": columns,
                "spacing_cm": _feature_clamp(spacing, 0.6, 4.5),
                "radius_cm": _feature_clamp(spacing * 0.14, 0.07, 0.45),
                "head_height_cm": _feature_clamp(normal_extent * 0.055, 0.08, 0.35),
                "include_washer": True,
            },
        )
    if kind == "vent_slats":
        count = 5 if width_extent >= 8.0 else 4
        spacing = width_extent / float(count + 1)
        return (
            "v2_vent_slats_modifier",
            {
                **common,
                "normal_axis": normal_axis,
                "side": "positive",
                "row_axis": width_axis,
                "length_axis": length_axis,
                "count": count,
                "spacing_cm": _feature_clamp(spacing, 0.55, 3.0),
                "length_cm": max(length_extent * 0.56, NUMERIC_EPSILON),
                "height_cm": _feature_clamp(spacing * 0.34, 0.14, 0.75),
                "thickness_cm": _feature_clamp(normal_extent * 0.055, 0.10, 0.45),
                "slat_depth_cm": _feature_clamp(normal_extent * 0.10, 0.12, 0.75),
            },
        )
    if kind in {"mount_plate", "latch_plate"}:
        plate_common = dict(common)
        plate_common["source_authoring"] = plate_common.pop("source", source_name)
        is_latch = kind == "latch_plate"
        plate_width = _feature_clamp(
            length_extent * (0.22 if is_latch else 0.34),
            0.9,
            max(length_extent * 0.62, 0.9),
        )
        plate_height = _feature_clamp(
            width_extent * (0.16 if is_latch else 0.24),
            0.55,
            max(width_extent * 0.46, 0.55),
        )
        thickness = _feature_clamp(normal_extent * 0.055, 0.08, 0.42)
        return (
            "v2_mount_plate_modifier",
            {
                **plate_common,
                "center": _feature_shifted_center(
                    primitive,
                    axis=normal_axis,
                    offset=normal_extent * 0.5 + thickness * 0.5,
                ),
                "axis": normal_axis,
                "column_axis": length_axis,
                "row_axis": width_axis,
                "width_cm": plate_width,
                "height_cm": plate_height,
                "thickness_cm": thickness,
                "hole_rows": 1 if is_latch else 2,
                "hole_columns": 2 if is_latch else 4,
                "hole_radius_cm": _feature_clamp(face_minor * 0.018, 0.05, 0.24),
                "bevel_width_cm": _feature_clamp(thickness * 0.22, 0.02, 0.12),
                "bevel_segments": 1,
                "blend_mode": "union",
                "component": "latch_plate" if is_latch else "mount_plate",
            },
        )
    if kind == "handle":
        pad_thickness = _feature_clamp(normal_extent * 0.06, 0.10, 0.45)
        grip_radius = _feature_clamp(face_minor * 0.018, 0.08, 0.32)
        standoff = max(pad_thickness + grip_radius + 0.12, _feature_clamp(normal_extent * 0.24, 0.35, 1.8))
        return (
            "v2_handle_modifier",
            {
                **common,
                "center": _feature_shifted_center(
                    primitive,
                    axis=normal_axis,
                    offset=normal_extent * 0.5,
                ),
                "span_axis": length_axis,
                "normal_axis": normal_axis,
                "cross_axis": width_axis,
                "span_cm": _feature_clamp(length_extent * 0.34, 1.2, max(length_extent * 0.72, 1.2)),
                "standoff_cm": standoff,
                "grip_radius_cm": grip_radius,
                "pad_radius_cm": _feature_clamp(grip_radius * 1.9, 0.14, 0.75),
                "pad_thickness_cm": pad_thickness,
                "preserve_component_parts": True,
            },
        )
    if kind == "hinge":
        hinge_length = _feature_clamp(length_extent * 0.34, 1.4, max(length_extent * 0.78, 1.4))
        barrel_radius = _feature_clamp(face_minor * 0.035, 0.12, 0.55)
        return (
            "v2_hinge_modifier",
            {
                **common,
                "center": _feature_shifted_center(
                    primitive,
                    axis=normal_axis,
                    offset=normal_extent * 0.5 + barrel_radius,
                ),
                "hinge_axis": length_axis,
                "leaf_axis": width_axis,
                "height_axis": normal_axis,
                "length_cm": hinge_length,
                "leaf_width_cm": _feature_clamp(face_minor * 0.12, 0.35, 1.5),
                "leaf_thickness_cm": _feature_clamp(normal_extent * 0.035, 0.08, 0.32),
                "barrel_radius_cm": barrel_radius,
                "pin_radius_cm": _feature_clamp(barrel_radius * 0.42, 0.05, barrel_radius * 0.75),
                "knuckle_count": 5,
                "preserve_component_parts": True,
            },
        )
    if kind == "conduit_run":
        tube_radius = _feature_clamp(face_minor * 0.018, 0.08, 0.32)
        conduit_common = dict(common)
        conduit_common["source_authoring"] = conduit_common.pop("source", source_name)
        return (
            "v2_tube_modifier",
            {
                **conduit_common,
                "center": _feature_shifted_center(
                    primitive,
                    axis=normal_axis,
                    offset=normal_extent * 0.5 + tube_radius,
                ),
                "axis": length_axis,
                "outer_radius_cm": tube_radius,
                "inner_radius_cm": max(tube_radius * 0.48, NUMERIC_EPSILON),
                "height_cm": _feature_clamp(length_extent * 0.68, 1.4, max(length_extent * 0.94, 1.4)),
                "rim_bevel_cm": _feature_clamp(tube_radius * 0.16, 0.0, 0.08),
                "blend_mode": "union",
            },
        )
    if kind == "tube_shroud":
        outer_radius = _feature_clamp(face_minor * 0.22, 0.6, max(face_minor * 0.48, 0.6))
        wall = _feature_clamp(outer_radius * 0.22, 0.08, outer_radius * 0.45)
        height = _feature_clamp(normal_extent * 0.16, 0.18, 1.2)
        return (
            "v2_tube_modifier",
            {
                **common,
                "center": _feature_shifted_center(
                    primitive,
                    axis=normal_axis,
                    offset=normal_extent * 0.5 + height * 0.5,
                ),
                "axis": normal_axis,
                "outer_radius_cm": outer_radius,
                "inner_radius_cm": max(outer_radius - wall, NUMERIC_EPSILON),
                "height_cm": height,
                "rim_bevel_cm": _feature_clamp(wall * 0.18, 0.0, 0.12),
            },
        )
    if kind == "rail":
        profile = _feature_clamp(face_minor * 0.045, 0.08, 0.55)
        rail_common = dict(common)
        rail_common["source_authoring"] = rail_common.pop("source", source_name)
        return (
            "v2_rail_modifier",
            {
                **rail_common,
                "center": _feature_shifted_center(
                    primitive,
                    axis=normal_axis,
                    offset=normal_extent * 0.5 + profile * 0.5,
                ),
                "axis": length_axis,
                "length_cm": _feature_clamp(length_extent * 0.78, 1.2, max(length_extent * 0.98, 1.2)),
                "profile_cm": profile,
                "profile_height_cm": _feature_clamp(profile * 0.75, 0.06, profile * 1.35),
                "profile_shape": "rectangular",
                "blend_mode": "union",
            },
        )
    if kind == "structural_beam":
        beam_width = _feature_clamp(face_minor * 0.12, 0.18, 1.2)
        beam_height = _feature_clamp(face_minor * 0.18, 0.22, 1.8)
        beam_common = dict(common)
        beam_common["source_authoring"] = beam_common.pop("source", source_name)
        return (
            "v2_structural_beam_modifier",
            {
                **beam_common,
                "center": _feature_shifted_center(
                    primitive,
                    axis=normal_axis,
                    offset=normal_extent * 0.5 + beam_height * 0.5,
                ),
                "axis": length_axis,
                "length_cm": _feature_clamp(length_extent * 0.72, 1.6, max(length_extent * 0.96, 1.6)),
                "width_cm": beam_width,
                "height_cm": beam_height,
                "profile_shape": "i_beam",
                "web_thickness_cm": _feature_clamp(beam_width * 0.18, 0.05, beam_width * 0.45),
                "flange_thickness_cm": _feature_clamp(beam_height * 0.16, 0.05, beam_height * 0.42),
                "bevel_width_cm": _feature_clamp(min(beam_width, beam_height) * 0.03, 0.0, 0.08),
                "blend_mode": "union",
            },
        )
    if kind == "truss_frame":
        member_radius = _feature_clamp(face_minor * 0.030, 0.06, 0.32)
        depth = _feature_clamp(normal_extent * 0.14, member_radius * 2.5, max(normal_extent * 0.5, member_radius * 2.5))
        truss_common = dict(common)
        truss_common["source_authoring"] = truss_common.pop("source", source_name)
        return (
            "v2_truss_frame_modifier",
            {
                **truss_common,
                "center": _feature_shifted_center(
                    primitive,
                    axis=normal_axis,
                    offset=normal_extent * 0.5 + depth * 0.5,
                ),
                "length_axis": length_axis,
                "height_axis": width_axis,
                "depth_axis": normal_axis,
                "length_cm": _feature_clamp(length_extent * 0.76, 1.8, max(length_extent * 0.98, 1.8)),
                "height_cm": _feature_clamp(width_extent * 0.42, 0.7, max(width_extent * 0.86, 0.7)),
                "depth_cm": depth,
                "member_radius_cm": member_radius,
                "bay_count": 4 if length_extent >= 8.0 else 3,
                "bracing_pattern": "warren",
                "blend_mode": "union",
            },
        )
    if kind == "ladder_frame":
        rail_radius = _feature_clamp(face_minor * 0.028, 0.06, 0.28)
        ladder_common = dict(common)
        ladder_common["source_authoring"] = ladder_common.pop("source", source_name)
        return (
            "v2_ladder_frame_modifier",
            {
                **ladder_common,
                "center": _feature_shifted_center(
                    primitive,
                    axis=normal_axis,
                    offset=normal_extent * 0.5 + rail_radius,
                ),
                "length_axis": length_axis,
                "width_axis": width_axis,
                "length_cm": _feature_clamp(length_extent * 0.70, 1.4, max(length_extent * 0.94, 1.4)),
                "width_cm": _feature_clamp(width_extent * 0.45, 0.5, max(width_extent * 0.82, 0.5)),
                "rail_radius_cm": rail_radius,
                "rung_radius_cm": _feature_clamp(rail_radius * 0.72, 0.04, rail_radius),
                "rung_count": 4 if length_extent >= 7.0 else 3,
                "blend_mode": "union",
            },
        )
    if kind == "capsule_strut":
        radius = _feature_clamp(face_minor * 0.035, 0.07, 0.36)
        length = _feature_clamp(length_extent * 0.62, radius * 2.4, max(length_extent * 0.94, radius * 2.4))
        capsule_common = dict(common)
        capsule_common["source_authoring"] = capsule_common.pop("source", source_name)
        return (
            "v2_capsule_modifier",
            {
                **capsule_common,
                "center": _feature_shifted_center(
                    primitive,
                    axis=normal_axis,
                    offset=normal_extent * 0.5 + radius,
                ),
                "axis": length_axis,
                "radius_cm": radius,
                "length_cm": max(length, radius * 2.2),
                "sections": 24,
                "rings": 12,
                "blend_mode": "union",
            },
        )
    if kind == "support_bracket":
        depth = _feature_clamp(normal_extent * 0.32, 0.6, 3.2)
        return (
            "v2_bracket_modifier",
            {
                **common,
                "center": _feature_shifted_center(
                    primitive,
                    axis=normal_axis,
                    offset=normal_extent * 0.5 + depth * 0.18,
                ),
                "normal_axis": normal_axis,
                "width_axis": length_axis,
                "height_axis": width_axis,
                "width_cm": _feature_clamp(length_extent * 0.22, 0.8, 5.0),
                "height_cm": _feature_clamp(width_extent * 0.28, 0.8, 5.0),
                "depth_cm": depth,
                "thickness_cm": _feature_clamp(face_minor * 0.035, 0.12, 0.7),
                "include_gussets": True,
                "gusset_count": 2,
                "preserve_component_parts": True,
            },
        )
    if kind == "corner_guard":
        normal_index = _feature_axis_index(normal_axis)
        length_index = _feature_axis_index(length_axis)
        width_index = _feature_axis_index(width_axis)
        corner_signs: list[tuple[float, float, float]] = []
        for length_sign in (-1.0, 1.0):
            for width_sign in (-1.0, 1.0):
                signs = [1.0, 1.0, 1.0]
                signs[normal_index] = 1.0
                signs[length_index] = length_sign
                signs[width_index] = width_sign
                corner_signs.append((signs[0], signs[1], signs[2]))
        guard_size = _feature_clamp(face_minor * 0.18, 0.5, 3.0)
        return (
            "v2_corner_guard_set_modifier",
            {
                **common,
                "center": primitive.center,
                "source_extents": extents,
                "guard_axes": [length_axis, width_axis],
                "corner_signs": corner_signs,
                "guard_size_cm": guard_size,
                "thickness_cm": _feature_clamp(guard_size * 0.24, 0.10, 0.6),
                "seat_depth_cm": _feature_clamp(guard_size * 0.05, 0.0, 0.18),
                "preserve_component_parts": True,
            },
        )
    if kind == "weld_seam":
        weld_width = _feature_clamp(face_minor * 0.030, 0.08, 0.42)
        weld_common = dict(common)
        weld_common["source_authoring"] = weld_common.pop("source", source_name)
        return (
            "v2_weld_seam_modifier",
            {
                **weld_common,
                "center": _feature_shifted_center(
                    primitive,
                    axis=normal_axis,
                    offset=normal_extent * 0.5 + weld_width * 0.5,
                ),
                "axis": length_axis,
                "normal_axis": normal_axis,
                "width_cm": weld_width,
                "radius_cm": weld_width * 0.5,
                "length_cm": _feature_clamp(length_extent * 0.76, 1.2, max(length_extent * 0.96, 1.2)),
                "segments": 12,
                "blend_mode": "union",
                "weld_mode": "axis",
            },
        )
    if kind in {"edge_wear", "grime_mask"}:
        modifier_key = _FEATURE_ALLOW_MODIFIER_KEYS[kind]
        payload = _surface_damage_modifier_payload(
            primitive,
            modifier_key=modifier_key,
            source_token=source_token,
            source_name=source_name,
            amount=0.42 if kind == "edge_wear" else 0.30,
        )
        if payload is None:
            return None
        payload = dict(payload)
        payload["source_authoring"] = payload.pop("source", source_name)
        payload["feature_allow"] = source_token
        payload["feature_token"] = source_token
        payload["repair_policy_feature_kind"] = kind
        return modifier_key, payload
    if kind == "mirror_instances":
        mirror_common = dict(common)
        mirror_common["source_authoring"] = mirror_common.pop("source", source_name)
        origin = float(primitive.center[_feature_axis_index(length_axis)]) + length_extent * 0.36
        return (
            "v2_mirror_modifier",
            {
                **mirror_common,
                "axis": length_axis,
                "origin_cm": round(origin, 6),
                "include_source": True,
                "mirror_offset_scale": 1.0,
                "blend_mode": "union",
            },
        )
    return None


def _primitive_has_feature_modifier(primitive: ShapePrimitive, modifier_key: str) -> bool:
    if modifier_key == "v2_polybevel_modifier":
        return primitive.v2_polybevel_modifier is not None
    metadata = primitive.semantic_metadata if isinstance(primitive.semantic_metadata, dict) else {}
    if modifier_key in metadata:
        return True
    return bool(getattr(primitive, modifier_key, None))


def _primitive_has_feature_source_replacer(primitive: ShapePrimitive) -> bool:
    metadata = primitive.semantic_metadata if isinstance(primitive.semantic_metadata, dict) else {}
    return any(key in metadata for key in _FEATURE_ALLOW_SOURCE_REPLACERS)


def _apply_feature_allow_edge_break(
    primitive: ShapePrimitive,
    *,
    source_token: str,
    source_name: str,
    density_multiplier: float = 1.0,
) -> bool:
    source_slug = _slug_fragment(source_name)
    operation_prefix = "feature_allow" if source_slug.startswith("feature_allow") else source_slug
    if primitive.v2_polybevel_modifier is not None:
        return False
    extents = _feature_box_extents(primitive)
    if extents is None:
        return False
    role = _primitive_edge_role(primitive)
    width = _feature_clamp(
        min(extents) * 0.025 * _feature_clamp(density_multiplier, 0.75, 1.25),
        0.035,
        0.28 if role == "hero" else 0.18,
    )
    base_segments = 2 if role in {"hero", "support"} else 1
    segments = _feature_density_count(base_segments, density_multiplier, lower=1, upper=4)
    seam_name = "feature_allow_edge_break"
    primitive.v2_polybevel_modifier = {
        "width_cm": width,
        "segments": segments,
        "target_seam_groups": [seam_name],
        "edge_class": seam_name,
        "v2_op": "sop.polybevel",
        "operation_id": f"{operation_prefix}:edge_break:{_slug_fragment(str(primitive.part or primitive.component or 'body'))}",
        "source": source_name,
        "feature_allow": source_token,
        "feature_token": source_token,
        "feature_density_multiplier": round(float(density_multiplier), 6),
        "source_boolean_seam_group_count": len(primitive.boolean_seam_groups),
    }
    primitive.bevel_seam_groups = [
        *list(primitive.bevel_seam_groups),
        {
            "name": seam_name,
            "width_cm": width,
                "segments": segments,
                "target_seam_groups": [seam_name],
                "source": source_name,
            },
        ]
    primitive.boolean_seam_groups = [
        *list(primitive.boolean_seam_groups),
        {"name": seam_name, "source": source_name},
    ]
    primitive.tags = [*list(primitive.tags), f"{operation_prefix}:edge_break"]
    return True


def _apply_feature_allow_modifier(
    primitive: ShapePrimitive,
    *,
    kind: str,
    source_token: str,
    source_name: str,
    density_multiplier: float = 1.0,
) -> bool:
    if kind == "edge_break":
        return _apply_feature_allow_edge_break(
            primitive,
            source_token=source_token,
            source_name=source_name,
            density_multiplier=density_multiplier,
        )
    payload = _feature_allow_modifier_payload(
        primitive,
        kind=kind,
        source_token=source_token,
        source_name=source_name,
    )
    if payload is None:
        return False
    modifier_key, modifier = payload
    if _primitive_has_feature_modifier(primitive, modifier_key):
        return False
    if modifier_key in _FEATURE_ALLOW_SOURCE_REPLACERS and _primitive_has_feature_source_replacer(primitive):
        return False
    modifier = _feature_density_adjusted_modifier(
        modifier,
        kind=kind,
        density_multiplier=density_multiplier,
    )
    metadata = dict(primitive.semantic_metadata) if isinstance(primitive.semantic_metadata, dict) else {}
    metadata[modifier_key] = modifier
    primitive.semantic_metadata = metadata
    source_slug = _slug_fragment(source_name)
    operation_prefix = "feature_allow" if source_slug.startswith("feature_allow") else source_slug
    primitive.tags = [*list(primitive.tags), f"{operation_prefix}:{kind}"]
    return True


def _apply_feature_allow_modifiers(
    primitives: list[ShapePrimitive],
    *,
    asset_graph: AssetGraph,
) -> int:
    kinds = _feature_allow_kinds(asset_graph)
    if not kinds:
        return 0
    density_multiplier = _feature_density_multiplier(asset_graph)
    applied = 0
    for kind in _FEATURE_ALLOW_APPLICATION_ORDER:
        source_entry = kinds.get(kind)
        if not source_entry:
            continue
        source_token, source_name = source_entry
        limit = _FEATURE_ALLOW_MAX_TARGETS.get(kind, 1)
        applied_for_kind = 0
        for primitive in _feature_allow_targets(primitives, kind=kind):
            if applied_for_kind >= limit:
                break
            if _apply_feature_allow_modifier(
                primitive,
                kind=kind,
                source_token=source_token,
                source_name=source_name,
                density_multiplier=density_multiplier,
            ):
                applied += 1
                applied_for_kind += 1
    return applied


def _source_repair_policy_authoring(asset_graph: AssetGraph) -> dict[str, Any]:
    authoring = asset_graph.authoring if isinstance(asset_graph.authoring, dict) else {}
    policy: dict[str, Any] = {}
    resolved_family = authoring.get("resolved_family")
    if isinstance(resolved_family, dict):
        family_policy = resolved_family.get("repair_policy")
        if isinstance(family_policy, dict):
            policy.update(family_policy)
    asset_policy = authoring.get("repair_policy")
    if isinstance(asset_policy, dict):
        policy.update(asset_policy)
    return policy


def _repair_policy_tokens(value: Any) -> set[str]:
    tokens: set[str] = set()
    for fragment in _iter_text_fragments(value):
        slug = _slug_fragment(fragment)
        tokens.add(slug)
        tokens.update(token for token in slug.split("_") if token)
    return tokens


def _repair_policy_source_token(policy: dict[str, Any]) -> str:
    use = str(policy.get("use") or "").strip()
    mode = str(policy.get("mode") or "").strip()
    if use:
        return _slug_fragment(use)
    if mode:
        return _slug_fragment(mode)
    return "repair_policy"


def _repair_policy_denies_kind(deny_tokens: set[str], *, kind: str, action: str = "") -> bool:
    kind_tokens = set(_slug_fragment(kind).split("_"))
    action_slug = _slug_fragment(action)
    return (
        kind in deny_tokens
        or action_slug in deny_tokens
        or bool(kind_tokens & deny_tokens)
    )


def _repair_policy_feature_kinds(asset_graph: AssetGraph) -> dict[str, tuple[str, str]]:
    policy = _source_repair_policy_authoring(asset_graph)
    if not policy:
        return {}
    source_token = _repair_policy_source_token(policy)
    source_name = "repair_policy"
    allow = policy.get("allow")
    deny_tokens = _repair_policy_tokens(policy.get("deny"))
    use_tokens = _repair_policy_tokens(policy.get("use"))
    mode_tokens = _repair_policy_tokens(policy.get("mode"))
    selected: dict[str, tuple[str, str]] = {}

    def add_kind(kind: str, action: str = "") -> None:
        if kind not in _FEATURE_ALLOW_APPLICATION_ORDER:
            return
        if _repair_policy_denies_kind(deny_tokens, kind=kind, action=action):
            return
        selected.setdefault(kind, (source_token or _slug_fragment(action or kind), source_name))

    if {
        "hard",
        "hardsurface",
        "hard_surface",
        "hero",
        "hero_hardsurface_repair",
    } & (use_tokens | mode_tokens):
        for kind in _REPAIR_POLICY_HARDSURFACE_DEFAULT_FEATURES:
            add_kind(kind, "hero_hardsurface_repair")

    if isinstance(allow, (list, tuple, set)):
        for action in _iter_text_fragments(allow):
            action_slug = _slug_fragment(action)
            for kind in _REPAIR_POLICY_ACTION_FEATURES.get(action_slug, ()):
                add_kind(kind, action_slug)
            if action_slug in _FEATURE_ALLOW_ALIASES:
                add_kind(_FEATURE_ALLOW_ALIASES[action_slug], action_slug)
            elif action_slug in _FEATURE_ALLOW_APPLICATION_ORDER:
                add_kind(action_slug, action_slug)

    return selected


def _apply_repair_policy_preflight_modifiers(
    primitives: list[ShapePrimitive],
    *,
    asset_graph: AssetGraph,
) -> int:
    kinds = _repair_policy_feature_kinds(asset_graph)
    if not kinds:
        return 0
    density_multiplier = max(1.0, _feature_density_multiplier(asset_graph))
    applied = 0
    for kind in _FEATURE_ALLOW_APPLICATION_ORDER:
        source_entry = kinds.get(kind)
        if not source_entry:
            continue
        source_token, source_name = source_entry
        limit = _FEATURE_ALLOW_MAX_TARGETS.get(kind, 1)
        applied_for_kind = 0
        for primitive in _feature_allow_targets(primitives, kind=kind):
            if applied_for_kind >= limit:
                break
            if _apply_feature_allow_modifier(
                primitive,
                kind=kind,
                source_token=source_token,
                source_name=source_name,
                density_multiplier=density_multiplier,
            ):
                applied += 1
                applied_for_kind += 1
    return applied


def _integration_rule_slug(rule: Any) -> str:
    return _slug_fragment(str(rule or ""))


def _integration_rule_tokens(rule: Any) -> set[str]:
    tokens = _edge_class_tokens(_integration_rule_slug(rule))
    normalized: set[str] = set()
    for token in tokens:
        normalized.add(_INTEGRATION_TOKEN_ALIASES.get(token, token))
    return normalized - _INTEGRATION_STOP_TOKENS


def _preservation_rule_slug(value: Any, *, force_preserve: bool = False) -> str:
    slug = _integration_rule_slug(value)
    if force_preserve and slug and "preserve" not in _edge_class_tokens(slug):
        slug = f"preserve_{slug}"
    return slug


def _append_preservation_rule_entries(
    entries: list[tuple[str, str]],
    value: Any,
    *,
    source_name: str,
    force_preserve: bool = False,
) -> None:
    existing = {rule for rule, _ in entries}
    for rule in _iter_text_fragments(value):
        slug = _preservation_rule_slug(rule, force_preserve=force_preserve)
        if not slug or slug in _BOOLEAN_INTEGRATION_RULES:
            continue
        tokens = _integration_rule_tokens(slug)
        if ("preserve" in _edge_class_tokens(slug) or tokens) and slug not in existing:
            entries.append((slug, source_name))
            existing.add(slug)


def _integration_preserve_rule_entries(
    geometry_authoring: dict[str, Any],
    *,
    asset_graph: AssetGraph | None = None,
) -> tuple[tuple[str, str], ...]:
    entries: list[tuple[str, str]] = []
    _append_preservation_rule_entries(
        entries,
        geometry_authoring.get("integration_rules"),
        source_name="geometry.integration_rules",
    )
    if asset_graph is not None:
        authoring = asset_graph.authoring if isinstance(asset_graph.authoring, dict) else {}
        constraints = authoring.get("constraints")
        if isinstance(constraints, dict):
            _append_preservation_rule_entries(
                entries,
                constraints.get("preserve"),
                source_name="constraints.preserve",
                force_preserve=True,
            )
        shape_controls = authoring.get("shape_controls")
        if isinstance(shape_controls, dict):
            _append_preservation_rule_entries(
                entries,
                shape_controls.get("preserve"),
                source_name="build.shape.preserve",
                force_preserve=True,
            )
    return tuple(entries)


def _preservation_intents_from_authoring(asset_graph: AssetGraph) -> tuple[str, ...]:
    authoring = asset_graph.authoring if isinstance(asset_graph.authoring, dict) else {}
    values: list[str] = []
    for source in ("constraints", "shape_controls"):
        value = authoring.get(source)
        if isinstance(value, dict):
            values.extend(_iter_text_fragments(value.get("preserve")))
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        slug = _slug_fragment(value)
        if not slug or slug in seen:
            continue
        seen.add(slug)
        out.append(slug)
    return tuple(out)


def _integration_rule_feature_kind(rule_tokens: set[str]) -> str | None:
    if {"corner", "guard"} <= rule_tokens:
        return "corner_guard"
    if rule_tokens & _INTEGRATION_BREAK_TOKENS:
        return "panel_line"
    if rule_tokens & {"bezel", "frame"}:
        return "panel_frame"
    if "vent" in rule_tokens:
        return "vent_slats"
    if rule_tokens & {"mount", "socket"}:
        return "socket_point"
    if rule_tokens & {"strap", "trim", "ridge"}:
        return "trim_band"
    if "hinge" in rule_tokens:
        return "hinge"
    if "handle" in rule_tokens:
        return "handle"
    if "bracket" in rule_tokens:
        return "support_bracket"
    return None


def _integration_rule_target_score(
    primitive: ShapePrimitive,
    *,
    rule_tokens: set[str],
    feature_kind: str | None,
    index: int,
) -> tuple[float, int] | None:
    primitive_tokens = _feature_target_tokens(primitive)
    matches = primitive_tokens & rule_tokens
    role = _primitive_edge_role(primitive)
    score = {"hero": 42.0, "support": 26.0, "trim": 16.0}.get(role, 8.0)
    if matches:
        score += 60.0 + 12.0 * len(matches)
    elif feature_kind == "corner_guard" and (
        primitive_tokens & {"body", "shell", "case", "crate", "container", "cabinet", "panel"}
    ):
        score += 38.0
    elif feature_kind == "panel_line" and (
        primitive_tokens & {"body", "shell", "lid", "door", "panel", "frame"}
    ):
        score += 30.0
    elif feature_kind == "panel_frame" and (
        primitive_tokens & {"screen", "bezel", "frame", "door", "panel", "terminal", "cabinet"}
    ):
        score += 30.0
    elif feature_kind == "socket_point" and (
        primitive_tokens & {"rotor", "mount", "pod", "socket", "hardpoint", "plate", "module"}
    ):
        score += 28.0
    elif feature_kind == "trim_band" and (
        primitive_tokens & {"strap", "body", "shell", "lid", "blade", "guard", "rail"}
    ):
        score += 24.0
    elif (rule_tokens & _INTEGRATION_GLOBAL_PRESERVE_TOKENS) and (
        primitive_tokens & _INTEGRATION_BODY_FALLBACK_TOKENS
    ):
        score += 22.0
    else:
        return None
    extents = _feature_box_extents(primitive)
    if extents is not None:
        face_area = sorted(extents)[-1] * sorted(extents)[-2]
        score += min(face_area, 10000.0) * 0.0001
    return score, index


def _integration_rule_targets(
    primitives: list[ShapePrimitive],
    *,
    rule_tokens: set[str],
    feature_kind: str | None,
    limit: int,
) -> list[ShapePrimitive]:
    scored: list[tuple[float, int, ShapePrimitive]] = []
    for index, primitive in enumerate(primitives):
        score = _integration_rule_target_score(
            primitive,
            rule_tokens=rule_tokens,
            feature_kind=feature_kind,
            index=index,
        )
        if score is None:
            continue
        scored.append((score[0], score[1], primitive))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [primitive for _, _, primitive in scored[:limit]]


def _integration_rule_target_name(primitive: ShapePrimitive) -> str:
    return _slug_fragment(
        "_".join(
            [
                str(primitive.part or "body"),
                str(primitive.component or primitive.primitive_type),
                str(primitive.region or ""),
            ]
        )
    )


def _append_integration_preservation_metadata(
    primitive: ShapePrimitive,
    *,
    rule: str,
    rule_tokens: set[str],
    feature_kind: str | None,
    source_name: str,
) -> bool:
    metadata = dict(primitive.semantic_metadata) if isinstance(primitive.semantic_metadata, dict) else {}
    records = [
        dict(record)
        for record in metadata.get("integration_preservation_rules", [])
        if isinstance(record, dict)
    ]
    target = _integration_rule_target_name(primitive)
    if any(record.get("rule") == rule and record.get("target") == target for record in records):
        return False
    records.append(
        {
            "schema": "lathe.geometry.integration_preservation_rule.v1",
            "source": source_name,
            "rule": rule,
            "tokens": sorted(rule_tokens),
            "target": target,
            "feature_kind": feature_kind or "",
            "preserve_component_parts": True,
        }
    )
    metadata["integration_preservation_rules"] = records
    metadata["integration_preservation_rule_count"] = len(records)
    metadata["preserve_component_parts"] = True
    metadata["part_preserving_fusion"] = True
    primitive.semantic_metadata = metadata
    tag = f"integration_preserve:{rule}"
    if tag not in primitive.tags:
        primitive.tags = [*list(primitive.tags), tag]
    return True


def _apply_integration_edge_control(
    primitive: ShapePrimitive,
    *,
    rule: str,
    rule_tokens: set[str],
    source_name: str,
) -> int:
    target = _integration_rule_target_name(primitive)
    source_slug = _slug_fragment(source_name)
    group = {
        "name": f"integration_{rule}",
        "part": primitive.part or "body",
        "edge_class": "integration_preserve",
        "source": source_name,
        "rule": rule,
        "tokens": sorted(rule_tokens),
    }
    applied = 0
    existing_group_names = {
        str(item.get("name") or "")
        for item in primitive.hard_edge_groups
        if isinstance(item, dict)
    }
    if group["name"] not in existing_group_names:
        primitive.hard_edge_groups = [*list(primitive.hard_edge_groups), group]
        applied += 1
    if primitive.v2_mark_hard_edge_modifier is None:
        primitive.v2_mark_hard_edge_modifier = {
            "groups": [group],
            "angle_threshold_deg": 35.0,
            "edge_class": "integration_preserve",
            "source": source_name,
            "integration_rule": rule,
            "target": target,
            "v2_op": "op.mark_hard_edge",
            "operation_id": f"{source_slug}:mark_hard_edge:{rule}:{target}",
        }
        applied += 1
    else:
        modifier = dict(primitive.v2_mark_hard_edge_modifier)
        groups = [
            dict(item)
            for item in modifier.get("groups", [])
            if isinstance(item, dict)
        ]
        if not any(item.get("name") == group["name"] for item in groups):
            modifier["groups"] = [*groups, group]
            modifier.setdefault("angle_threshold_deg", 35.0)
            modifier.setdefault("edge_class", "integration_preserve")
            modifier.setdefault("source", source_name)
            primitive.v2_mark_hard_edge_modifier = modifier
            applied += 1
    if primitive.v2_weighted_normals_modifier is None:
        primitive.v2_weighted_normals_modifier = {
            "mode": "area_angle",
            "strength": 1.0,
            "source": source_name,
            "integration_rule": rule,
            "target": target,
            "v2_op": "op.weighted_normals",
            "operation_id": f"{source_slug}:weighted_normals:{rule}:{target}",
        }
        applied += 1
    return applied


def _apply_integration_feature_modifier(
    primitive: ShapePrimitive,
    *,
    rule: str,
    feature_kind: str | None,
    source_name: str,
) -> bool:
    if feature_kind is None:
        return False
    payload = _feature_allow_modifier_payload(
        primitive,
        kind=feature_kind,
        source_token=rule,
        source_name=source_name,
    )
    if payload is None:
        return False
    modifier_key, modifier = payload
    if _primitive_has_feature_modifier(primitive, modifier_key):
        return False
    if modifier_key in _FEATURE_ALLOW_SOURCE_REPLACERS and _primitive_has_feature_source_replacer(primitive):
        return False
    target = _integration_rule_target_name(primitive)
    source_slug = _slug_fragment(source_name)
    modifier = {
        **modifier,
        "source": source_name,
        "integration_rule": rule,
        "feature_kind": feature_kind,
        "operation_id": f"{source_slug}:{feature_kind}:{rule}:{target}",
    }
    metadata = dict(primitive.semantic_metadata) if isinstance(primitive.semantic_metadata, dict) else {}
    metadata[modifier_key] = modifier
    primitive.semantic_metadata = metadata
    tag = f"integration_feature:{feature_kind}"
    if tag not in primitive.tags:
        primitive.tags = [*list(primitive.tags), tag]
    return True


def _apply_integration_rule_preservation(
    primitives: list[ShapePrimitive],
    *,
    asset_graph: AssetGraph,
    geometry_authoring: dict[str, Any],
) -> int:
    rule_entries = _integration_preserve_rule_entries(
        geometry_authoring,
        asset_graph=asset_graph,
    )
    if not rule_entries:
        return 0
    applied = 0
    for rule, source_name in rule_entries:
        rule_tokens = _integration_rule_tokens(rule)
        feature_kind = _integration_rule_feature_kind(rule_tokens)
        limit = _INTEGRATION_FEATURE_MAX_TARGETS.get(feature_kind or "", 2)
        targets = _integration_rule_targets(
            primitives,
            rule_tokens=rule_tokens,
            feature_kind=feature_kind,
            limit=limit,
        )
        for primitive in targets:
            if _append_integration_preservation_metadata(
                primitive,
                rule=rule,
                rule_tokens=rule_tokens,
                feature_kind=feature_kind,
                source_name=source_name,
            ):
                applied += 1
            applied += _apply_integration_edge_control(
                primitive,
                rule=rule,
                rule_tokens=rule_tokens,
                source_name=source_name,
            )
            if _apply_integration_feature_modifier(
                primitive,
                rule=rule,
                feature_kind=feature_kind,
                source_name=source_name,
            ):
                applied += 1
    return applied


def _source_surface_authoring(asset_graph: AssetGraph) -> dict[str, Any]:
    authoring = asset_graph.authoring if isinstance(asset_graph.authoring, dict) else {}
    surface: dict[str, Any] = {}
    resolved_family = authoring.get("resolved_family")
    if isinstance(resolved_family, dict):
        family_surface = resolved_family.get("surface")
        if isinstance(family_surface, dict):
            surface.update(family_surface)
    source_surface = authoring.get("source_surface")
    if isinstance(source_surface, dict):
        surface.update(source_surface)
    return surface


def _material_zone_entries(asset_graph: AssetGraph) -> tuple[str, ...]:
    surface = _source_surface_authoring(asset_graph)
    entries: list[str] = []
    for value in (
        surface.get("material_zones"),
        surface.get("materials"),
        asset_graph.materials,
    ):
        entries.extend(_iter_text_fragments(value))
    return tuple(dict.fromkeys(_slug_fragment(entry) for entry in entries if str(entry).strip()))


def _material_zone_tokens(value: str) -> set[str]:
    tokens = _edge_class_tokens(_slug_fragment(value))
    return {_MATERIAL_ZONE_TOKEN_ALIASES.get(token, token) for token in tokens}


def _material_zone_score(
    material: str,
    primitive: ShapePrimitive,
    *,
    index: int,
) -> float:
    material_tokens = _material_zone_tokens(material)
    primitive_tokens = _feature_target_tokens(primitive)
    role = _primitive_edge_role(primitive)
    score = -float(index) * 0.01
    matches = material_tokens & primitive_tokens
    if matches:
        score += 48.0 + 8.0 * len(matches)
    if primitive_tokens & {"body", "shell", "case", "crate", "container", "panel", "door", "lid"}:
        score += 18.0 if material_tokens & _MATERIAL_BODY_HINTS else 0.0
    if primitive_tokens & {"trim", "rail", "strap", "guard", "hinge", "handle", "foot", "seal", "grip"}:
        score += 22.0 if material_tokens & _MATERIAL_TRIM_HINTS else 0.0
    if primitive_tokens & {"screen", "glass", "lens", "emissive", "bezel", "window", "light"}:
        score += 28.0 if material_tokens & _MATERIAL_GLASS_HINTS else 0.0
    if primitive_tokens & {"warning", "stripe", "marking", "hazard", "paint"}:
        score += 26.0 if material_tokens & _MATERIAL_WARNING_HINTS else 0.0
    if primitive_tokens & {"blade", "barrel", "tool", "weapon"} and material_tokens & {"steel", "metal", "blade"}:
        score += 24.0
    if primitive_tokens & {"grip", "wrap", "handle"} and material_tokens & {"leather", "rubber", "grip"}:
        score += 24.0
    if score <= 0.0 and role == "hero" and index == 0:
        score += 8.0
    if score <= 0.0 and role in {"support", "trim"} and index == min(1, index):
        score += 4.0
    return score


def _best_material_zone_for_primitive(
    entries: tuple[str, ...],
    primitive: ShapePrimitive,
) -> str | None:
    if not entries:
        return None
    scored = [
        (_material_zone_score(material, primitive, index=index), index, material)
        for index, material in enumerate(entries)
    ]
    scored.sort(key=lambda item: (-item[0], item[1]))
    if scored and scored[0][0] > 0.0:
        return scored[0][2]
    role = _primitive_edge_role(primitive)
    if role in {"support", "trim"} and len(entries) > 1:
        return entries[1]
    return entries[0]


def _source_style_target(asset_graph: AssetGraph) -> str:
    authoring = asset_graph.authoring if isinstance(asset_graph.authoring, dict) else {}
    style_target = str(authoring.get("style_target") or "").strip()
    if style_target:
        return _slug_fragment(style_target)
    surface = _source_surface_authoring(asset_graph)
    surface_style = str(surface.get("style_target") or surface.get("style_pack") or "").strip()
    return _slug_fragment(surface_style) if surface_style else ""


def _apply_material_zone_authoring(
    primitives: list[ShapePrimitive],
    *,
    asset_graph: AssetGraph,
) -> int:
    entries = _material_zone_entries(asset_graph)
    style_target = _source_style_target(asset_graph)
    if not entries and not style_target:
        return 0
    applied = 0
    for primitive in primitives:
        metadata = dict(primitive.semantic_metadata) if isinstance(primitive.semantic_metadata, dict) else {}
        changed = False
        material = _best_material_zone_for_primitive(entries, primitive)
        if material:
            metadata.setdefault("material_hint", material)
            metadata.setdefault("material_zone", material)
            metadata["source_material_zones"] = list(entries)
            metadata["material_zone_source"] = "source_surface.material_zones"
            if "material_zone" not in primitive.tags:
                primitive.tags = [*list(primitive.tags), "material_zone"]
            changed = True
        if style_target:
            metadata["style_target"] = style_target
            metadata["style_target_source"] = "intent.style_target"
            tag = f"style_target:{style_target}"
            if tag not in primitive.tags:
                primitive.tags = [*list(primitive.tags), tag]
            changed = True
        if changed:
            primitive.semantic_metadata = metadata
            applied += 1
    return applied


def _surface_damage_requests(asset_graph: AssetGraph) -> dict[str, tuple[str, str, float]]:
    surface = _source_surface_authoring(asset_graph)
    fragments: list[tuple[str, str]] = []
    for key in (
        "patterns",
        "damage_patterns",
        "wear_patterns",
        "story_decals",
        "damage_decals",
        "weather_decals",
        "material_layers",
        "layers",
    ):
        fragments.extend((fragment, f"source_surface.{key}") for fragment in _iter_text_fragments(surface.get(key)))
    for key in ("wear_story", "usage_history", "story", "wear_level", "damage_level", "edge_wear"):
        value = surface.get(key)
        if value not in (None, "", (), [], {}):
            fragments.extend((fragment, f"source_surface.{key}") for fragment in _iter_text_fragments(value))
            if not isinstance(value, (list, dict)):
                fragments.append((str(value), f"source_surface.{key}"))
    requests: dict[str, tuple[str, str, float]] = {}
    for fragment, source_name in fragments:
        slug = _slug_fragment(fragment)
        tokens = set(slug.split("_"))
        matched: tuple[str, str] | None = _SURFACE_DAMAGE_ALIASES.get(slug)
        if matched is None:
            for token in tokens:
                matched = _SURFACE_DAMAGE_ALIASES.get(token)
                if matched is not None:
                    break
        if matched is None:
            continue
        modifier_key, kind = matched
        amount = 0.38
        if tokens & {"heavy", "battle", "worn", "salvaged", "weathered"}:
            amount = 0.55
        elif tokens & {"light", "subtle", "soft"}:
            amount = 0.24
        if modifier_key not in requests:
            requests[modifier_key] = (slug, source_name, amount)
    return requests


def _surface_damage_targets(primitives: list[ShapePrimitive], *, limit: int) -> list[ShapePrimitive]:
    scored: list[tuple[float, int, ShapePrimitive]] = []
    for index, primitive in enumerate(primitives):
        extents = _feature_box_extents(primitive)
        if extents is None:
            continue
        role = _primitive_edge_role(primitive)
        tokens = _feature_target_tokens(primitive)
        score = {"hero": 50.0, "support": 24.0, "trim": 16.0}.get(role, 8.0)
        if tokens & {"body", "shell", "panel", "door", "lid", "case", "crate", "blade", "barrel"}:
            score += 24.0
        face_area = sorted(extents)[-1] * sorted(extents)[-2]
        score += min(face_area, 10000.0) * 0.0001
        scored.append((score, index, primitive))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [primitive for _, _, primitive in scored[:limit]]


def _surface_damage_modifier_payload(
    primitive: ShapePrimitive,
    *,
    modifier_key: str,
    source_token: str,
    source_name: str,
    amount: float,
) -> dict[str, Any] | None:
    extents = _feature_box_extents(primitive)
    if extents is None:
        return None
    normal_axis, length_axis, width_axis = _feature_face_axes(extents)
    length_extent = _feature_extent(extents, length_axis)
    width_extent = _feature_extent(extents, width_axis)
    normal_extent = _feature_extent(extents, normal_axis)
    target = _integration_rule_target_name(primitive)
    common = {
        "source": source_name,
        "surface_pattern": source_token,
        "target": target,
        "amount": _feature_clamp(amount, 0.05, 0.85),
        "normal_axis": normal_axis,
        "side": "positive",
        "operation_id": f"surface_damage:{modifier_key}:{source_token}:{target}",
    }
    if modifier_key == "v2_scratch_mask_modifier":
        return {
            **common,
            "line_axis": length_axis,
            "row_axis": width_axis,
            "count": 4,
            "length_cm": max(length_extent * 0.35, NUMERIC_EPSILON),
            "width_cm": _feature_clamp(width_extent * 0.012, 0.035, 0.18),
            "depth_cm": _feature_clamp(normal_extent * 0.025, 0.035, 0.22),
        }
    if modifier_key == "v2_dent_mask_modifier":
        radius = _feature_clamp(min(length_extent, width_extent) * 0.045, 0.14, 0.75)
        return {
            **common,
            "count": 3,
            "radius_cm": radius,
            "depth_cm": _feature_clamp(radius * 0.55, 0.06, 0.45),
        }
    if modifier_key == "v2_chip_edges_modifier":
        return {
            **common,
            "count": 4,
            "radius_cm": _feature_clamp(min(length_extent, width_extent, normal_extent) * 0.055, 0.10, 0.65),
        }
    if modifier_key == "v2_grime_mask_modifier":
        return {
            **common,
            "line_axis": length_axis,
            "row_axis": width_axis,
            "count": 3,
            "length_cm": max(length_extent * 0.30, NUMERIC_EPSILON),
            "width_cm": _feature_clamp(width_extent * 0.08, 0.25, 1.8),
            "thickness_cm": _feature_clamp(normal_extent * 0.012, 0.02, 0.08),
            "blend_mode": "union",
        }
    return None


def _apply_surface_damage_authoring(
    primitives: list[ShapePrimitive],
    *,
    asset_graph: AssetGraph,
) -> int:
    requests = _surface_damage_requests(asset_graph)
    if not requests:
        return 0
    targets = _surface_damage_targets(primitives, limit=2)
    if not targets:
        return 0
    applied = 0
    for modifier_key, (source_token, source_name, amount) in requests.items():
        for primitive in targets:
            metadata = dict(primitive.semantic_metadata) if isinstance(primitive.semantic_metadata, dict) else {}
            if modifier_key in metadata or getattr(primitive, modifier_key, None):
                continue
            payload = _surface_damage_modifier_payload(
                primitive,
                modifier_key=modifier_key,
                source_token=source_token,
                source_name=source_name,
                amount=amount,
            )
            if payload is None:
                continue
            metadata[modifier_key] = payload
            primitive.semantic_metadata = metadata
            tag = f"surface_damage_authoring:{modifier_key}"
            if tag not in primitive.tags:
                primitive.tags = [*list(primitive.tags), tag]
            applied += 1
            break
    return applied


def _edge_class_fallback_spec(edge_class: str) -> dict[str, Any] | None:
    name = str(edge_class)
    lowered = name.lower()
    if "soft" in lowered:
        return None
    if "bevel" not in lowered and "edge" not in lowered and "ridge" not in lowered:
        return None
    role = "support" if "support" in lowered or "base" in lowered else "trim"
    if "hero" in lowered or "primary" in lowered or "sharp" in lowered:
        role = "hero"
    width = 0.24 if role == "hero" else 0.12 if role == "support" else 0.06
    segments = 2 if role in {"hero", "support"} else 1
    return {"width_cm": width, "segments": segments, "role": role}


def _edge_class_declaration_name(declaration: Any) -> str | None:
    if isinstance(declaration, dict):
        for key in ("name", "id", "edge_class", "edgeClass", "class"):
            value = declaration.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None
    value = str(declaration).strip()
    return value or None


def _edge_class_declared_targets(spec: dict[str, Any]) -> list[str]:
    for key in (
        "target_seam_groups",
        "target_seams",
        "seam_groups",
        "seams",
        "seam_classes",
    ):
        targets = _edge_class_text_values(spec.get(key))
        if targets:
            return targets
    return []


def _edge_class_float(spec: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = spec.get(key)
        if value is None:
            continue
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return None
        if math.isfinite(parsed) and parsed > 0.0:
            return parsed
        return None
    return None


def _edge_class_int(spec: dict[str, Any], *keys: str) -> int | None:
    for key in keys:
        value = spec.get(key)
        if value is None:
            continue
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return None
        return parsed if parsed > 0 else None
    return None


def _edge_class_base_spec(
    declaration: Any,
    registry: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    name = _edge_class_declaration_name(declaration)
    if not name:
        return None
    base = registry.get(name) or _edge_class_fallback_spec(name)
    if not base and not isinstance(declaration, dict):
        return None
    spec = dict(base or {})
    if isinstance(declaration, dict):
        spec.update(declaration)
    spec["name"] = name
    targets = _edge_class_declared_targets(spec)
    if targets:
        spec["target_seam_groups"] = targets
    width = _edge_class_float(
        spec,
        "width_cm",
        "bevel_width_cm",
        "radius_cm",
        "width",
        "bevel_width",
        "radius",
    )
    segments = _edge_class_int(spec, "segments", "segment_count", "bevel_segments")
    if width is None or segments is None:
        return None
    role = str(spec.get("role") or "trim").strip().lower()
    if role not in {"hero", "support", "trim"}:
        role = "trim"
    spec["width_cm"] = width
    spec["segments"] = segments
    spec["role"] = role
    return spec


def _edge_class_target_groups(
    edge_class: str,
    spec: dict[str, Any],
    seam_classes: list[str],
) -> list[str]:
    seam_class_set = {str(name) for name in seam_classes if str(name)}
    explicit_targets = [str(name) for name in spec.get("target_seam_groups") or [] if str(name)]
    if explicit_targets:
        return [
            name for name in explicit_targets if not seam_class_set or name in seam_class_set
        ]
    if not seam_classes:
        return []

    tokens = _edge_class_tokens(edge_class)
    role = str(spec.get("role") or "")
    generic_edge_class = str(edge_class) in _GENERIC_EDGE_CLASS_NAMES
    if role == "hero" and generic_edge_class:
        tokens |= {"break", "seam", "split", "panel", "lid", "frame", "blade"}
    elif role == "support" and generic_edge_class:
        tokens |= {"support", "foot", "base", "stand", "threshold", "split", "panel"}
    elif generic_edge_class:
        tokens |= {"trim", "cut", "clasp", "latch", "lock", "service", "join", "panel"}

    targets = [
        seam
        for seam in seam_classes
        if any(token and token in str(seam).lower() for token in tokens)
    ]
    if targets:
        return targets
    # If the author named a generic edge class such as ``hero_bevel`` and
    # supplied custom seam classes, the declared seams are still the useful
    # semantic edge set. Use them rather than silently dropping the bevel.
    return list(seam_classes)


def _declared_edge_class_specs(
    *,
    edge_classes: list[Any],
    seam_classes: list[str],
    registry: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    for declaration in edge_classes:
        spec = _edge_class_base_spec(declaration, registry)
        if not spec:
            continue
        name = str(spec["name"])
        targets = _edge_class_target_groups(name, spec, seam_classes)
        if not targets:
            continue
        normalized = {
            "name": name,
            "role": str(spec.get("role") or "trim"),
            "width_cm": float(spec["width_cm"]),
            "segments": int(spec["segments"]),
            "target_seam_groups": list(targets),
        }
        if spec.get("source"):
            normalized["source"] = str(spec["source"])
        specs.append(normalized)
    return specs


def _primitive_edge_role(primitive: ShapePrimitive) -> str:
    text = " ".join(
        [
            str(primitive.component or ""),
            str(primitive.part or ""),
            " ".join(str(tag) for tag in primitive.tags),
        ]
    ).lower()
    tokens = _edge_class_tokens(text.replace(" ", "_"))
    if tokens & _EDGE_CLASS_SUPPORT_COMPONENTS:
        return "support"
    if tokens & _EDGE_CLASS_TRIM_COMPONENTS:
        return "trim"
    if tokens & _EDGE_CLASS_HERO_COMPONENTS:
        return "hero"
    return "hero" if primitive.primitive_type in {"box", "subdivision_box"} else "trim"


def _pick_edge_class_spec(
    primitive: ShapePrimitive,
    specs: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if not specs:
        return None
    role = _primitive_edge_role(primitive)
    text_tokens = _edge_class_tokens(
        "_".join(
            [
                str(primitive.component or ""),
                str(primitive.part or ""),
                *[str(tag) for tag in primitive.tags],
            ]
        )
    )
    direct = [
        spec
        for spec in specs
        if _edge_class_tokens(str(spec.get("name") or "")) & text_tokens
    ]
    if direct:
        return direct[0]
    for prefer_generic in (False, True):
        for spec in specs:
            if spec.get("role") != role:
                continue
            is_generic = str(spec.get("name") or "") in _GENERIC_EDGE_CLASS_NAMES
            if is_generic == prefer_generic:
                return spec
    for fallback_role in ("hero", "support", "trim"):
        for spec in specs:
            if (
                spec.get("role") == fallback_role
                and str(spec.get("name") or "") not in _GENERIC_EDGE_CLASS_NAMES
            ):
                return spec
        for spec in specs:
            if spec.get("role") == fallback_role:
                return spec
    return specs[0]


def _apply_declared_edge_class_bevels(
    primitives: list[ShapePrimitive],
    *,
    edge_classes: list[Any],
    seam_classes: list[str],
    registry: dict[str, dict[str, Any]] | None = None,
    source: str = "edge_class_authoring",
) -> int:
    if not edge_classes:
        return 0
    specs = _declared_edge_class_specs(
        edge_classes=edge_classes,
        seam_classes=seam_classes,
        registry=registry or _EDGE_CLASS_BEVEL_DEFAULTS,
    )
    if not specs:
        return 0

    tagged = 0
    for primitive in primitives:
        if primitive.v2_polybevel_modifier is not None:
            continue
        spec = _pick_edge_class_spec(primitive, specs)
        if spec is None:
            continue
        modifier = _edge_class_polybevel_modifier(
            spec, set(spec["target_seam_groups"])
        )
        modifier["source"] = str(spec.get("source") or source)
        primitive.v2_polybevel_modifier = modifier
        primitive.bevel_seam_groups = [
            *list(primitive.bevel_seam_groups),
            {
                "name": spec["name"],
                "width_cm": spec["width_cm"],
                "segments": spec["segments"],
                "target_seam_groups": list(spec["target_seam_groups"]),
                "source": modifier["source"],
            },
        ]
        existing_boolean_names = {
            str(group.get("name")) for group in primitive.boolean_seam_groups if isinstance(group, dict)
        }
        for seam_name in spec["target_seam_groups"]:
            if seam_name in existing_boolean_names:
                continue
            primitive.boolean_seam_groups = [
                *list(primitive.boolean_seam_groups),
                {"name": seam_name, "source": modifier["source"]},
            ]
            existing_boolean_names.add(seam_name)
        primitive.tags = [*list(primitive.tags), f"edge_class:{spec['name']}"]
        tagged += 1
    return tagged


def _apply_chest_edge_class_bevels(
    primitives: list[ShapePrimitive],
    *,
    edge_classes: list[str],
    seam_classes: list[str],
) -> int:
    """Tag chest primitives with PolyBevel modifiers driven by edge_classes.

    Returns the number of primitives that had a bevel modifier attached.
    """
    return _apply_declared_edge_class_bevels(
        primitives,
        edge_classes=edge_classes,
        seam_classes=seam_classes,
        registry=_CHEST_EDGE_CLASS_BEVELS,
        source="chest_edge_class",
    )


def _chest_brass_band_primitives(
    blueprint: AssemblyBlueprint,
) -> tuple[list[ShapePrimitive], list[ShapeRegion]]:
    """Emit 3 horizontal brass bands wrapping the chest body.

    Each band is a torus primitive (a true ring with a circular cross
    section) sized so that its outer edge protrudes from the chest body.
    Bands sit at deterministic heights along the body's vertical (Y)
    axis (top / middle / bottom).

    Torus is preferred over revolved_profile here because revolved_profile
    auto-snaps endpoints back to the rotation axis, which would fill the
    band into a solid disk. Torus produces a hollow ring directly.

    Returns ``(primitives, regions)``. Empty if no chest_body / shell
    component is present in the blueprint.
    """
    body: BlueprintComponent | None = None
    for component in blueprint.components:
        if component.component_type in {"shell", "body"}:
            body = component
            break
    if body is None:
        return [], []

    width, height, depth = body.extents
    cx, cy, cz = body.center
    half_h = max(height * 0.5, 0.001)
    # Bands wrap horizontally; minor radius gives the strap protrusion and
    # cross-section thickness. Major radius is slightly inside the body
    # so the band reads as a strap on the cuboid body's flat faces.
    body_radius = max(width, depth) * 0.5
    minor_radius = max(min(height * 0.04, 1.2), 0.4)  # ~4% of height, 0.4-1.2 cm
    major_radius = body_radius + minor_radius * 0.6

    band_offsets = (-0.78, 0.0, 0.78)

    primitives: list[ShapePrimitive] = []
    regions: list[ShapeRegion] = []
    for index, offset_factor in enumerate(band_offsets):
        band_y = cy + offset_factor * (half_h * 0.85)
        band_part = "body"
        band_name = f"brass_band_{index}"
        primitive = ShapePrimitive(
            primitive_type="torus",
            part=band_part,
            center=(cx, band_y, cz),
            major_radius=major_radius,
            minor_radius=minor_radius,
            axis="y",
            tags=[
                "brass_band",
                "instanced_band",
                "aged_brass_trim",
                f"brass_band_index:{index}",
            ],
            component="band",
            region=band_name,
        )
        # Tag bands with a thin chamfer so silhouette catches highlight.
        primitive.v2_polybevel_modifier = {
            "width_cm": 0.04,
            "segments": 1,
            "target_seam_groups": ["brass_band_edge"],
            "source_boolean_seam_group_count": 0,
        }
        primitive.bevel_seam_groups = [
            {
                "name": "brass_band_chamfer",
                "width_cm": 0.04,
                "segments": 1,
                "target_seam_groups": ["brass_band_edge"],
            }
        ]
        primitives.append(primitive)
        regions.append(
            ShapeRegion(
                name=band_name,
                part=band_part,
                component="band",
                center=(cx, band_y, cz),
                extents=(
                    (major_radius + minor_radius) * 2.0,
                    minor_radius * 2.0,
                    (major_radius + minor_radius) * 2.0,
                ),
                tags=["brass_band", "aged_brass_trim", f"index:{index}"],
                adjacency=[body.name],
                required=False,
            )
        )
    return primitives, regions


def compile_assembly_blueprint(asset_graph: AssetGraph, blueprint: AssemblyBlueprint) -> ShapeIR:
    """Compile assembly blueprint.

    Args:
        asset_graph: asset_graph argument.
        blueprint: blueprint argument.

    Returns:
        The result.
    """
    primitives: list[ShapePrimitive] = []
    regions: list[ShapeRegion] = []
    primitive_selection: list[dict[str, Any]] = []
    creative_grammar = asset_graph.authoring.get("creative_grammar", {})
    if not isinstance(creative_grammar, dict):
        creative_grammar = {}
    existing_component_names = {component.name for component in blueprint.components}
    existing_component_parts = {component.part for component in blueprint.components}
    source_components = _authored_source_components(
        asset_graph,
        existing_component_names,
        existing_parts=existing_component_parts,
    )
    for component in [*blueprint.components, *source_components]:
        component_primitives = _component_primitives(component)
        selected = select_component_primitives(
            component,
            component_primitives,
            creative_grammar=creative_grammar,
            family=asset_graph.family,
        )
        primitives.extend(selected.primitives)
        primitive_selection.extend(selected.applied)
        regions.append(
            ShapeRegion(
                name=component.name,
                part=component.part,
                component=component.component_type,
                center=component.center,
                extents=component.extents,
                tags=list(component.tags),
                adjacency=list(component.adjacency),
                symmetry_mate=component.symmetry_mate,
                interface_role=component.interface_role,
                required=True,
            )
        )

    extra_notes: list[str] = []
    if _should_emit_brass_band_primitives(asset_graph, blueprint):
        band_primitives, band_regions = _chest_brass_band_primitives(blueprint)
        if band_primitives:
            primitives.extend(band_primitives)
            regions.extend(band_regions)
            extra_notes.append(f"brass_band_primitives:{len(band_primitives)}")

    geometry_authoring = _source_geometry_authoring(asset_graph)
    edge_classes = _edge_class_declarations(geometry_authoring)
    seam_classes = _edge_class_text_values(geometry_authoring.get("seam_classes"))
    tagged = _apply_declared_edge_class_bevels(
        primitives,
        edge_classes=edge_classes,
        seam_classes=seam_classes,
    )
    if tagged:
        extra_notes.append(f"edge_class_bevels:{tagged}")
    feature_allow_applied = _apply_feature_allow_modifiers(
        primitives,
        asset_graph=asset_graph,
    )
    if feature_allow_applied:
        extra_notes.append(f"feature_allow_modifiers:{feature_allow_applied}")
    repair_policy_applied = _apply_repair_policy_preflight_modifiers(
        primitives,
        asset_graph=asset_graph,
    )
    if repair_policy_applied:
        extra_notes.append(f"repair_policy_preflight_modifiers:{repair_policy_applied}")
    integration_preservation_applied = _apply_integration_rule_preservation(
        primitives,
        asset_graph=asset_graph,
        geometry_authoring=geometry_authoring,
    )
    if integration_preservation_applied:
        extra_notes.append(f"integration_rule_preservation:{integration_preservation_applied}")
    material_zone_applied = _apply_material_zone_authoring(
        primitives,
        asset_graph=asset_graph,
    )
    if material_zone_applied:
        extra_notes.append(f"material_zone_authoring:{material_zone_applied}")
    surface_damage_applied = _apply_surface_damage_authoring(
        primitives,
        asset_graph=asset_graph,
    )
    if surface_damage_applied:
        extra_notes.append(f"surface_damage_authoring:{surface_damage_applied}")

    return _build_shape_ir(
        asset_graph,
        blueprint_id=blueprint.blueprint_id,
        primitives=primitives,
        regions=regions,
        notes=[
            *blueprint.notes,
            *(
                [f"authored_source_components:{len(source_components)}"]
                if source_components
                else []
            ),
            *extra_notes,
        ],
        primitive_selection=primitive_selection,
    )


def refresh_shape_ir(
    asset_graph: AssetGraph, shape_ir: ShapeIR, *, notes: list[str] | None = None
) -> ShapeIR:
    """Refresh shape ir.

    Args:
        asset_graph: asset_graph argument.
        shape_ir: shape_ir argument.
        notes: notes argument.

    Returns:
        The result.
    """
    prior_selector = shape_ir.signature.get("primitive_selector") if isinstance(shape_ir.signature, dict) else None
    prior_records = (
        list(prior_selector.get("records") or [])
        if isinstance(prior_selector, dict)
        else []
    )
    return _build_shape_ir(
        asset_graph,
        blueprint_id=shape_ir.blueprint_id,
        primitives=list(shape_ir.primitives),
        regions=list(shape_ir.regions),
        notes=notes or list(shape_ir.signature.get("blueprint_notes", [])),
        primitive_selection=prior_records,
    )


def mirrored(center: tuple[float, float, float], *, axis: str = "x") -> tuple[float, float, float]:
    """Mirrored.

    Args:
        center: center argument.
        axis: axis argument.

    Returns:
        The result.
    """
    if axis == "x":
        return (-center[0], center[1], center[2])
    if axis == "z":
        return (center[0], center[1], -center[2])
    raise _unsupported_mirror_axis_error(axis)


def polar_offset(
    radius: float, angle_deg: float, y: float, *, depth_scale: float = 1.0
) -> tuple[float, float, float]:
    """Polar offset.

    Args:
        radius: radius argument.
        angle_deg: angle_deg argument.
        y: y argument.
        depth_scale: depth_scale argument.

    Returns:
        The result.
    """
    angle = math.radians(angle_deg)
    return (round(math.cos(angle) * radius, 6), y, round(math.sin(angle) * radius * depth_scale, 6))
