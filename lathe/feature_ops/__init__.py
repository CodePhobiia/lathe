"""Feature primitive builders used by the hard-surface feature grammar."""

from __future__ import annotations

import math
from collections.abc import Iterable

from ..assembly_kernel import BlueprintComponent
from ..instance_pattern import (
    FaceFrame,
    InstanceAttributes,
    bolt_cap_kit,
    distribute_greeble_kits,
    primary_face_frame,
    socket_point_kit,
)
from ..shape_ir import ShapePrimitive
from .bevel_real import (
    box_with_seam_group,
    fillet_edge,
    tag_boolean_seam_group,
)

__all__ = [
    "box_with_seam_group",
    "fillet_edge",
    "tag_boolean_seam_group",
]


def _feature_box(
    component: BlueprintComponent,
    *,
    center: tuple[float, float, float],
    extents: tuple[float, float, float],
    feature_kind: str,
    tags: Iterable[str],
    blend_mode: str = "union",
    rounding: float = 0.0,
) -> ShapePrimitive:
    return ShapePrimitive(
        primitive_type="box",
        part=component.part,
        center=center,
        extents=extents,
        tags=["feature", feature_kind, *list(tags)],
        component=feature_kind,
        region=component.name,
        blend_mode=blend_mode,
        rounding=rounding,
    )


def _feature_cylinder(
    component: BlueprintComponent,
    *,
    center: tuple[float, float, float],
    radius: float,
    height: float,
    axis: str,
    feature_kind: str,
    tags: Iterable[str],
    blend_mode: str = "union",
    rounding: float = 0.0,
) -> ShapePrimitive:
    return ShapePrimitive(
        primitive_type="cylinder",
        part=component.part,
        center=center,
        radius=radius,
        height=height,
        axis=axis,
        tags=["feature", feature_kind, *list(tags)],
        component=feature_kind,
        region=component.name,
        blend_mode=blend_mode,
        rounding=rounding,
    )


def _feature_sphere(
    component: BlueprintComponent,
    *,
    center: tuple[float, float, float],
    radius: float,
    feature_kind: str,
    tags: Iterable[str],
    blend_mode: str = "union",
    rounding: float = 0.0,
) -> ShapePrimitive:
    return ShapePrimitive(
        primitive_type="sphere",
        part=component.part,
        center=center,
        radius=radius,
        tags=["feature", feature_kind, *list(tags), "mesh_op_sphere"],
        component=feature_kind,
        region=component.name,
        blend_mode=blend_mode,
        rounding=rounding,
    )


def _feature_torus(
    component: BlueprintComponent,
    *,
    center: tuple[float, float, float],
    major_radius: float,
    minor_radius: float,
    axis: str,
    feature_kind: str,
    tags: Iterable[str],
    blend_mode: str = "union",
) -> ShapePrimitive:
    return ShapePrimitive(
        primitive_type="torus",
        part=component.part,
        center=center,
        major_radius=major_radius,
        minor_radius=minor_radius,
        axis=axis,
        tags=["feature", feature_kind, *list(tags), "mesh_op_torus"],
        component=feature_kind,
        region=component.name,
        blend_mode=blend_mode,
    )


def _feature_revolved_profile(
    component: BlueprintComponent,
    *,
    center: tuple[float, float, float],
    axis: str,
    profile_points: list[tuple[float, float]],
    feature_kind: str,
    tags: Iterable[str],
    blend_mode: str = "union",
) -> ShapePrimitive:
    return ShapePrimitive(
        primitive_type="revolved_profile",
        part=component.part,
        center=center,
        axis=axis,
        profile_points=profile_points,
        tags=["feature", feature_kind, *list(tags), "mesh_op_revolved_profile"],
        component=feature_kind,
        region=component.name,
        blend_mode=blend_mode,
    )


def _feature_extruded_profile(
    component: BlueprintComponent,
    *,
    center: tuple[float, float, float],
    profile_polygon: list[tuple[float, float]],
    extrude_height: float,
    axis: str,
    feature_kind: str,
    tags: Iterable[str],
    blend_mode: str = "union",
    rounding: float = 0.0,
) -> ShapePrimitive:
    return ShapePrimitive(
        primitive_type="extruded_profile",
        part=component.part,
        center=center,
        axis=axis,
        profile_polygon=profile_polygon,
        extrude_height=extrude_height,
        tags=["feature", feature_kind, *list(tags), "mesh_op_polyextrude"],
        component=feature_kind,
        region=component.name,
        blend_mode=blend_mode,
        rounding=rounding,
    )


def _feature_swept_profile(
    component: BlueprintComponent,
    *,
    center: tuple[float, float, float],
    cross_section: list[tuple[float, float]],
    sweep_path: list[tuple[float, float, float]],
    feature_kind: str,
    tags: Iterable[str],
    blend_mode: str = "union",
) -> ShapePrimitive:
    return ShapePrimitive(
        primitive_type="swept_profile",
        part=component.part,
        center=center,
        cross_section=cross_section,
        sweep_path=sweep_path,
        tags=["feature", feature_kind, *list(tags), "mesh_op_sweep"],
        component=feature_kind,
        region=component.name,
        blend_mode=blend_mode,
    )


def _feature_subdivision_box(
    component: BlueprintComponent,
    *,
    center: tuple[float, float, float],
    extents: tuple[float, float, float],
    corner_radii: tuple[float, float, float, float, float, float, float, float],
    feature_kind: str,
    tags: Iterable[str],
    blend_mode: str = "union",
    corner_segments: int = 4,
) -> ShapePrimitive:
    return ShapePrimitive(
        primitive_type="subdivision_box",
        part=component.part,
        center=center,
        extents=extents,
        corner_radii=corner_radii,
        corner_segments=corner_segments,
        tags=["feature", feature_kind, *list(tags), "mesh_op_subdivide"],
        component=feature_kind,
        region=component.name,
        blend_mode=blend_mode,
    )


def _chamfered_rectangle_polygon(width: float, height: float, chamfer: float) -> list[tuple[float, float]]:
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


def _round_cross_section(radius: float, *, segments: int = 8) -> list[tuple[float, float]]:
    segments = max(6, min(24, segments))
    radius = max(float(radius), 0.001)
    return [
        (
            math.cos(index * 2.0 * math.pi / segments) * radius,
            math.sin(index * 2.0 * math.pi / segments) * radius,
        )
        for index in range(segments)
    ]


def _axis_sweep_path(length: float, axis: str) -> list[tuple[float, float, float]]:
    half = max(float(length), 0.001) * 0.5
    if axis == "x":
        return [(-half, 0.0, 0.0), (half, 0.0, 0.0)]
    if axis == "z":
        return [(0.0, 0.0, -half), (0.0, 0.0, half)]
    return [(0.0, -half, 0.0), (0.0, half, 0.0)]


def _feature_round_bar(
    component: BlueprintComponent,
    *,
    center: tuple[float, float, float],
    radius: float,
    height: float,
    axis: str,
    feature_kind: str,
    tags: Iterable[str],
    blend_mode: str = "union",
) -> ShapePrimitive:
    return _feature_swept_profile(
        component,
        center=center,
        cross_section=_round_cross_section(radius, segments=10),
        sweep_path=_axis_sweep_path(height, axis),
        feature_kind=feature_kind,
        tags=[*list(tags), "mesh_op_round_bar"],
        blend_mode=blend_mode,
    )


def _lathed_cylinder_profile(height: float, radius: float, *, bevel: float = 0.12) -> list[tuple[float, float]]:
    half = max(float(height), 0.001) * 0.5
    shoulder = max(0.0, min(float(bevel), 0.35))
    inner = max(half * (1.0 - shoulder), 0.0)
    radius = max(float(radius), 0.001)
    return [
        (-half, radius * 0.82),
        (-inner, radius),
        (inner, radius),
        (half, radius * 0.82),
    ]


def _soft_corner_radii(extents: tuple[float, float, float], scale: float) -> tuple[float, float, float, float, float, float, float, float]:
    radius = max(min(extents) * scale, 0.001)
    return (
        radius * 0.55,
        radius * 0.75,
        radius * 0.48,
        radius * 0.90,
        radius * 0.72,
        radius,
        radius * 0.58,
        radius * 0.82,
    )


def _domed_profile(radius: float, depth: float) -> list[tuple[float, float]]:
    half_depth = max(depth * 0.5, radius * 0.18, 0.001)
    return [
        (-half_depth, radius * 0.82),
        (-half_depth * 0.18, radius),
        (half_depth * 0.48, radius * 0.74),
        (half_depth, radius * 0.18),
    ]


def _tapered_socket_profile(radius: float, depth: float) -> list[tuple[float, float]]:
    half_depth = max(depth * 0.5, 0.001)
    radius = max(radius, 0.001)
    return [
        (-half_depth, radius * 0.62),
        (-half_depth * 0.18, radius),
        (half_depth * 0.42, radius * 0.88),
        (half_depth, radius * 0.42),
    ]


def _capsule_profile(radius: float, length: float) -> list[tuple[float, float]]:
    half_length = max(length * 0.5, radius * 0.75, 0.001)
    radius = max(radius, 0.001)
    return [
        (-half_length, radius * 0.35),
        (-half_length * 0.86, radius * 0.88),
        (-half_length * 0.62, radius),
        (half_length * 0.62, radius),
        (half_length * 0.86, radius * 0.88),
        (half_length, radius * 0.35),
    ]


def edge_break_features(
    component: BlueprintComponent, *, depth_scale: float, thickness_scale: float
) -> list[ShapePrimitive]:
    """Create shallow edge-break strips around a component silhouette."""
    width, height, depth = component.extents
    tx = max(width * 0.06 * thickness_scale, 0.4)
    ty = max(height * 0.06 * thickness_scale, 0.4)
    tz = max(depth * 0.20 * depth_scale, 0.4)
    cx, cy, cz = component.center
    rounding = max(min(width, height, depth) * 0.03, 0.12)
    return [
        _feature_extruded_profile(
            component,
            center=(cx, cy + height * 0.48, cz + depth * 0.42),
            profile_polygon=_chamfered_rectangle_polygon(width * 0.82, ty, ty * 0.35),
            extrude_height=tz,
            axis="z",
            feature_kind="edge_break",
            tags=["top", "front", "extruded_edge_break"],
            rounding=rounding,
        ),
        _feature_extruded_profile(
            component,
            center=(cx, cy + height * 0.48, cz - depth * 0.42),
            profile_polygon=_chamfered_rectangle_polygon(width * 0.82, ty, ty * 0.35),
            extrude_height=tz,
            axis="z",
            feature_kind="edge_break",
            tags=["top", "rear", "extruded_edge_break"],
            rounding=rounding,
        ),
        _feature_extruded_profile(
            component,
            center=(cx - width * 0.42, cy, cz),
            profile_polygon=_chamfered_rectangle_polygon(tx, height * 0.78, tx * 0.35),
            extrude_height=depth * 0.78,
            axis="z",
            feature_kind="edge_break",
            tags=["left", "extruded_edge_break"],
            rounding=rounding,
        ),
        _feature_extruded_profile(
            component,
            center=(cx + width * 0.42, cy, cz),
            profile_polygon=_chamfered_rectangle_polygon(tx, height * 0.78, tx * 0.35),
            extrude_height=depth * 0.78,
            axis="z",
            feature_kind="edge_break",
            tags=["right", "extruded_edge_break"],
            rounding=rounding,
        ),
    ]


def trim_band_features(
    component: BlueprintComponent, *, depth_scale: float, thickness_scale: float
) -> list[ShapePrimitive]:
    """Create front and rear trim bands for a component."""
    width, height, depth = component.extents
    band_h = max(height * 0.07 * thickness_scale, 0.35)
    band_d = max(depth * 0.16 * depth_scale, 0.35)
    cx, cy, cz = component.center
    return [
        _feature_extruded_profile(
            component,
            center=(cx, cy, cz + depth * 0.40),
            profile_polygon=_chamfered_rectangle_polygon(width * 0.88, band_h, band_h * 0.30),
            extrude_height=band_d,
            axis="z",
            feature_kind="trim_band",
            tags=["front", "extruded_trim_band"],
        ),
        _feature_extruded_profile(
            component,
            center=(cx, cy, cz - depth * 0.40),
            profile_polygon=_chamfered_rectangle_polygon(width * 0.88, band_h, band_h * 0.30),
            extrude_height=band_d,
            axis="z",
            feature_kind="trim_band",
            tags=["rear", "extruded_trim_band"],
        ),
    ]


def panel_frame_features(
    component: BlueprintComponent, *, depth_scale: float, thickness_scale: float
) -> list[ShapePrimitive]:
    """Create a raised rectangular panel frame on the component face."""
    width, height, depth = component.extents
    lip = max(min(width, height) * 0.07 * thickness_scale, 0.35)
    face_depth = max(depth * 0.28 * depth_scale, 0.35)
    cx, cy, cz = component.center
    half_w = width / 2.0
    half_h = height / 2.0
    return [
        _feature_extruded_profile(
            component,
            center=(cx, cy + half_h - lip / 2.0, cz + depth * 0.34),
            profile_polygon=_chamfered_rectangle_polygon(width * 0.86, lip, lip * 0.30),
            extrude_height=face_depth,
            axis="z",
            feature_kind="frame_lip",
            tags=["top", "extruded_frame_lip"],
        ),
        _feature_extruded_profile(
            component,
            center=(cx, cy - half_h + lip / 2.0, cz + depth * 0.34),
            profile_polygon=_chamfered_rectangle_polygon(width * 0.86, lip, lip * 0.30),
            extrude_height=face_depth,
            axis="z",
            feature_kind="frame_lip",
            tags=["bottom", "extruded_frame_lip"],
        ),
        _feature_extruded_profile(
            component,
            center=(cx - half_w + lip / 2.0, cy, cz + depth * 0.34),
            profile_polygon=_chamfered_rectangle_polygon(lip, height * 0.84, lip * 0.30),
            extrude_height=face_depth,
            axis="z",
            feature_kind="frame_lip",
            tags=["left", "extruded_frame_lip"],
        ),
        _feature_extruded_profile(
            component,
            center=(cx + half_w - lip / 2.0, cy, cz + depth * 0.34),
            profile_polygon=_chamfered_rectangle_polygon(lip, height * 0.84, lip * 0.30),
            extrude_height=face_depth,
            axis="z",
            feature_kind="frame_lip",
            tags=["right", "extruded_frame_lip"],
        ),
    ]


def inset_panel_features(
    component: BlueprintComponent, *, depth_scale: float, thickness_scale: float
) -> list[ShapePrimitive]:
    """Create a subtractive inset panel feature."""
    width, height, depth = component.extents
    return [
        _feature_extruded_profile(
            component,
            center=(component.center[0], component.center[1], component.center[2] + depth * 0.18),
            profile_polygon=_chamfered_rectangle_polygon(
                max(width * 0.80, 0.35),
                max(height * 0.72, 0.35),
                max(min(width, height) * 0.035 * thickness_scale, 0.05),
            ),
            extrude_height=max(depth * 0.24 * depth_scale, 0.24),
            axis="z",
            feature_kind="inset_panel",
            tags=["recess", "extruded_inset_panel"],
            blend_mode="subtract",
            rounding=max(min(width, height) * 0.025 * thickness_scale, 0.12),
        )
    ]


def rib_features(
    component: BlueprintComponent, *, count: int, depth_scale: float, thickness_scale: float
) -> list[ShapePrimitive]:
    """Create repeated rib features across the component width."""
    width, height, depth = component.extents
    rib_w = max(width * 0.12 * thickness_scale, 0.35)
    rib_d = max(depth * 0.20 * depth_scale, 0.35)
    spacing = width * 0.62 / max(1, count - 1)
    start_x = component.center[0] - spacing * (count - 1) / 2.0
    primitives: list[ShapePrimitive] = []
    for index in range(count):
        cx = start_x + spacing * index
        primitives.append(
            _feature_extruded_profile(
                component,
                center=(cx, component.center[1], component.center[2] + depth * 0.28),
                profile_polygon=_chamfered_rectangle_polygon(rib_w, height * 0.74, rib_w * 0.30),
                extrude_height=rib_d,
                axis="z",
                feature_kind="rib",
                tags=["extruded_rib", f"rib_{index}"],
            )
        )
    return primitives


def fastener_strip_features(
    component: BlueprintComponent, *, count: int, depth_scale: float, size_scale: float
) -> list[ShapePrimitive]:
    """Create a strip of fastener-like box features."""
    width, height, depth = component.extents
    spacing = width * 0.68 / max(1, count - 1) if count > 1 else 0.0
    start_x = component.center[0] - spacing * (count - 1) / 2.0
    primitives: list[ShapePrimitive] = []
    for index in range(count):
        cx = start_x + spacing * index
        radius = max(min(width * 0.032, height * 0.048) * size_scale, 0.12)
        primitives.append(
            _feature_revolved_profile(
                component,
                center=(cx, component.center[1], component.center[2] + depth * 0.46),
                axis="z",
                profile_points=_domed_profile(radius, max(depth * 0.12 * depth_scale, 0.16)),
                feature_kind="fastener_strip",
                tags=["fastener", "domed_fastener"],
            )
        )
    return primitives


def vent_grille_features(
    component: BlueprintComponent, *, count: int, depth_scale: float
) -> list[ShapePrimitive]:
    """Create subtractive grille slats on a vent-like component."""
    width, height, depth = component.extents
    slot_h = max(height / (count * 2.0), 0.28)
    spacing = height / max(1, count)
    start_y = component.center[1] - spacing * (count - 1) / 2.0
    primitives: list[ShapePrimitive] = []
    for index in range(count):
        cy = start_y + spacing * index
        primitives.append(
            _feature_extruded_profile(
                component,
                center=(component.center[0], cy, component.center[2] + depth * 0.18),
                profile_polygon=_chamfered_rectangle_polygon(width * 0.92, slot_h, slot_h * 0.32),
                extrude_height=max(depth * 0.22 * depth_scale, 0.24),
                axis="z",
                feature_kind="vent_grille",
                tags=["slat", "extruded_vent_grille"],
                blend_mode="subtract",
            )
        )
    return primitives


def support_bracket_features(component: BlueprintComponent, *, depth_scale: float) -> list[ShapePrimitive]:
    """Create brace and pad features for support components."""
    width, height, depth = component.extents
    brace_extents = (
        max(width * 0.64, 0.35),
        max(height * 0.22, 0.35),
        max(depth * 1.10 * depth_scale, 0.35),
    )
    pad_w = max(width * 1.10, 0.35)
    pad_h = max(height * 0.18, 0.35)
    pad_d = max(depth * 0.58, 0.35)
    return [
        _feature_subdivision_box(
            component,
            center=(component.center[0], component.center[1] + height * 0.12, component.center[2]),
            extents=brace_extents,
            corner_radii=_soft_corner_radii(brace_extents, 0.18),
            feature_kind="support_bracket",
            tags=["brace", "subdivision_support_brace"],
            corner_segments=3,
        ),
        _feature_extruded_profile(
            component,
            center=(component.center[0], component.center[1] - height * 0.18, component.center[2]),
            profile_polygon=_chamfered_rectangle_polygon(pad_w, pad_h, pad_h * 0.24),
            extrude_height=pad_d,
            axis="z",
            feature_kind="support_bracket",
            tags=["pad", "extruded_support_pad"],
        ),
    ]


def stair_step_features(component: BlueprintComponent, *, count: int, depth_scale: float) -> list[ShapePrimitive]:
    """Create a stair run with stepped treads across the front depth."""
    width, height, depth = component.extents
    count = max(2, min(12, count))
    cx, cy, cz = component.center
    step_depth = max(depth * 0.72 / count, 0.20)
    step_height = max(height * 0.58 / count, 0.16)
    primitives: list[ShapePrimitive] = []
    for index in range(count):
        y = cy - height * 0.30 + step_height * (index + 0.5)
        z = cz + depth * 0.36 - step_depth * (index + 0.5)
        primitives.append(
            _feature_extruded_profile(
                component,
                center=(cx, y, z),
                profile_polygon=_chamfered_rectangle_polygon(max(width * 0.82, 0.45), step_height, step_height * 0.20),
                extrude_height=step_depth,
                axis="z",
                feature_kind="stair_step",
                tags=["architectural", "stair", "tread", "extruded_stair_tread", f"step_{index}"],
                rounding=0.03,
            )
        )
        primitives.append(
            _feature_extruded_profile(
                component,
                center=(cx, y + step_height * 0.48, z - step_depth * 0.46),
                profile_polygon=_chamfered_rectangle_polygon(max(width * 0.80, 0.42), max(step_height * 0.18, 0.08), max(step_height * 0.05, 0.02)),
                extrude_height=max(step_depth * 0.20 * depth_scale, 0.08),
                axis="z",
                feature_kind="stair_step",
                tags=["architectural", "stair", "nosing", "extruded_stair_nosing", f"nosing_{index}"],
                rounding=0.02,
            )
        )
    return primitives


def arch_opening_features(component: BlueprintComponent, *, depth_scale: float, thickness_scale: float) -> list[ShapePrimitive]:
    """Create an arched portal/frame motif from side piers and crown blocks."""
    width, height, depth = component.extents
    cx, cy, cz = component.center
    pier_w = max(width * 0.14 * thickness_scale, 0.28)
    crown_h = max(height * 0.12 * thickness_scale, 0.20)
    face_d = max(depth * 0.36 * depth_scale, 0.22)
    radius = max(width * 0.19 * thickness_scale, 0.14)
    crown_profile = [(-width * 0.40, -crown_h * 0.50), (width * 0.40, -crown_h * 0.50)]
    crown_profile.extend(
        (
            math.cos(math.pi * step / 10.0) * radius * 1.55,
            math.sin(math.pi * step / 10.0) * radius * 0.92 + crown_h * 0.06,
        )
        for step in range(11)
    )
    return [
        _feature_extruded_profile(
            component,
            center=(cx - width * 0.31, cy - height * 0.08, cz + depth * 0.38),
            profile_polygon=_chamfered_rectangle_polygon(pier_w, max(height * 0.72, 0.40), pier_w * 0.22),
            extrude_height=face_d,
            axis="z",
            feature_kind="arch_frame",
            tags=["architectural", "arch", "left_pier", "extruded_arch_pier"],
            rounding=0.04,
        ),
        _feature_extruded_profile(
            component,
            center=(cx + width * 0.31, cy - height * 0.08, cz + depth * 0.38),
            profile_polygon=_chamfered_rectangle_polygon(pier_w, max(height * 0.72, 0.40), pier_w * 0.22),
            extrude_height=face_d,
            axis="z",
            feature_kind="arch_frame",
            tags=["architectural", "arch", "right_pier", "extruded_arch_pier"],
            rounding=0.04,
        ),
        _feature_extruded_profile(
            component,
            center=(cx, cy + height * 0.29, cz + depth * 0.38),
            profile_polygon=_chamfered_rectangle_polygon(max(width * 0.72, 0.48), crown_h, crown_h * 0.24),
            extrude_height=face_d,
            axis="z",
            feature_kind="arch_frame",
            tags=["architectural", "arch", "lintel", "extruded_arch_lintel"],
            rounding=0.05,
        ),
        _feature_extruded_profile(
            component,
            center=(cx, cy + height * 0.31, cz + depth * 0.38),
            profile_polygon=crown_profile,
            extrude_height=face_d * 1.06,
            axis="z",
            feature_kind="arch_frame",
            tags=["architectural", "arch", "crown", "extruded_arch_crown"],
            rounding=0.05,
        ),
        _feature_extruded_profile(
            component,
            center=(cx, cy + height * 0.04, cz + depth * 0.40),
            profile_polygon=_chamfered_rectangle_polygon(max(width * 0.40, 0.30), max(height * 0.58, 0.32), max(width * 0.04, 0.04)),
            extrude_height=face_d * 1.12,
            axis="z",
            feature_kind="arch_cutout",
            tags=["architectural", "arch", "opening", "extruded_arch_cutout"],
            blend_mode="subtract",
            rounding=0.08,
        ),
    ]


def column_set_features(component: BlueprintComponent, *, count: int, depth_scale: float) -> list[ShapePrimitive]:
    """Create repeated round columns with caps and bases."""
    width, height, depth = component.extents
    count = max(1, min(8, count))
    spacing = width * 0.62 / max(1, count - 1) if count > 1 else 0.0
    start_x = component.center[0] - spacing * (count - 1) / 2.0
    radius = max(min(width / max(count * 3.4, 1.0), depth * 0.11) * depth_scale, 0.12)
    primitives: list[ShapePrimitive] = []
    for index in range(count):
        x = start_x + spacing * index
        primitives.append(
            _feature_revolved_profile(
                component,
                center=(x, component.center[1], component.center[2] + depth * 0.36),
                axis="y",
                profile_points=_lathed_cylinder_profile(max(height * 0.76, 0.38), radius, bevel=0.08),
                feature_kind="column_set",
                tags=["architectural", "column", "shaft", "lathed_column_shaft", f"column_{index}"],
            )
        )
        for cap, sign in (("base", -1.0), ("capital", 1.0)):
            cap_h = max(height * 0.055, 0.10)
            primitives.append(
                _feature_revolved_profile(
                    component,
                    center=(x, component.center[1] + sign * height * 0.40, component.center[2] + depth * 0.36),
                    axis="y",
                    profile_points=[
                        (-cap_h * 0.50, radius * 1.10),
                        (-cap_h * 0.20, radius * 1.42),
                        (cap_h * 0.20, radius * 1.42),
                        (cap_h * 0.50, radius * 1.10),
                    ],
                    feature_kind="column_set",
                    tags=["architectural", "column", cap, f"column_{index}_{cap}", "lathed_column_plate"],
                )
            )
    return primitives


def pipe_run_features(component: BlueprintComponent, *, count: int, depth_scale: float) -> list[ShapePrimitive]:
    """Create routed pipe runs with elbow collars."""
    width, height, depth = component.extents
    count = max(1, min(8, count))
    spacing = height * 0.54 / max(1, count - 1) if count > 1 else 0.0
    start_y = component.center[1] - spacing * (count - 1) / 2.0
    radius = max(min(height, depth) * 0.025 * depth_scale, 0.08)
    primitives: list[ShapePrimitive] = []
    for index in range(count):
        y = start_y + spacing * index
        primitives.append(
            _feature_round_bar(
                component,
                center=(component.center[0], y, component.center[2] + depth * 0.58),
                radius=radius,
                height=max(width * 0.78, 0.44),
                axis="x",
                feature_kind="pipe_run",
                tags=["mechanical", "pipe", "run", "swept_pipe_run", f"pipe_{index}"],
            )
        )
        for side, sign in (("left", -1.0), ("right", 1.0)):
            primitives.append(
                _feature_torus(
                    component,
                    center=(component.center[0] + sign * width * 0.40, y, component.center[2] + depth * 0.58),
                    major_radius=radius * 1.12,
                    minor_radius=max(radius * 0.20, 0.025),
                    axis="x",
                    feature_kind="pipe_run",
                    tags=["mechanical", "pipe", "collar", side, f"pipe_collar_{index}"],
                )
            )
    return primitives


def wheel_pair_features(component: BlueprintComponent, *, count: int, depth_scale: float) -> list[ShapePrimitive]:
    """Create paired wheel/disc assemblies for vehicles, carts, and machinery."""
    width, height, depth = component.extents
    count = max(1, min(4, count))
    spacing = depth * 0.54 / max(1, count - 1) if count > 1 else 0.0
    start_z = component.center[2] - spacing * (count - 1) / 2.0
    radius = max(min(height, depth) * 0.18 * depth_scale, 0.18)
    primitives: list[ShapePrimitive] = []
    for index in range(count):
        z = start_z + spacing * index
        for side, sign in (("left", -1.0), ("right", 1.0)):
            x = component.center[0] + sign * width * 0.48
            primitives.append(
                _feature_torus(
                    component,
                    center=(x, component.center[1] - height * 0.30, z),
                    major_radius=radius * 0.78,
                    minor_radius=max(radius * 0.18, 0.04),
                    axis="x",
                    feature_kind="wheel_pair",
                    tags=["vehicle", "wheel", "tire", side, f"wheel_{index}"],
                )
            )
            primitives.append(
                _feature_revolved_profile(
                    component,
                    center=(x, component.center[1] - height * 0.30, z),
                    axis="x",
                    profile_points=_lathed_cylinder_profile(max(width * 0.070, 0.16), radius * 0.42, bevel=0.16),
                    feature_kind="wheel_pair",
                    tags=["vehicle", "wheel", "hub", "lathed_wheel_hub", side, f"wheel_hub_{index}"],
                    blend_mode="subtract",
                )
            )
    return primitives


def hull_keel_features(component: BlueprintComponent, *, depth_scale: float, thickness_scale: float) -> list[ShapePrimitive]:
    """Create a boat/aircraft-like hull keel and tapered side sponsons."""
    width, height, depth = component.extents
    cx, cy, cz = component.center
    keel_extents = (
        max(width * 0.22 * thickness_scale, 0.22),
        max(height * 0.26, 0.20),
        max(depth * 1.06 * depth_scale, 0.50),
    )
    sponson_extents = (
        max(width * 0.20 * thickness_scale, 0.20),
        max(height * 0.20, 0.18),
        max(depth * 0.84 * depth_scale, 0.42),
    )
    bow_w = max(width * 0.62, 0.36)
    bow_h = max(height * 0.12, 0.12)
    bow_d = max(depth * 0.10 * depth_scale, 0.12)
    return [
        _feature_subdivision_box(
            component,
            center=(cx, cy - height * 0.42, cz),
            extents=keel_extents,
            corner_radii=_soft_corner_radii(keel_extents, 0.22),
            feature_kind="hull_keel",
            tags=["vehicle", "boat", "hull", "keel", "subdivision_hull_keel"],
            corner_segments=3,
        ),
        _feature_subdivision_box(
            component,
            center=(cx - width * 0.34, cy - height * 0.24, cz),
            extents=sponson_extents,
            corner_radii=_soft_corner_radii(sponson_extents, 0.24),
            feature_kind="hull_keel",
            tags=["vehicle", "boat", "hull", "left_sponson", "subdivision_hull_sponson"],
            corner_segments=3,
        ),
        _feature_subdivision_box(
            component,
            center=(cx + width * 0.34, cy - height * 0.24, cz),
            extents=sponson_extents,
            corner_radii=_soft_corner_radii(sponson_extents, 0.24),
            feature_kind="hull_keel",
            tags=["vehicle", "boat", "hull", "right_sponson", "subdivision_hull_sponson"],
            corner_segments=3,
        ),
        _feature_extruded_profile(
            component,
            center=(cx, cy - height * 0.18, cz + depth * 0.50),
            profile_polygon=[
                (-bow_w * 0.50, -bow_h * 0.50),
                (bow_w * 0.50, -bow_h * 0.50),
                (bow_w * 0.36, bow_h * 0.50),
                (-bow_w * 0.36, bow_h * 0.50),
            ],
            extrude_height=bow_d,
            axis="z",
            feature_kind="hull_keel",
            tags=["vehicle", "boat", "hull", "bow_plate", "extruded_bow_plate"],
            rounding=0.05,
        ),
    ]


def structural_frame_features(component: BlueprintComponent, *, depth_scale: float, thickness_scale: float) -> list[ShapePrimitive]:
    """Create an external structural cage/frame around a component."""
    width, height, depth = component.extents
    cx, cy, cz = component.center
    rail = max(min(width, height, depth) * 0.045 * thickness_scale, 0.12)
    section = _round_cross_section(rail * 0.50)
    return [
        _feature_swept_profile(
            component,
            center=(cx, cy + height * 0.46, cz + depth * 0.46),
            cross_section=section,
            sweep_path=[(-max(width * 0.49, 0.20), 0.0, 0.0), (max(width * 0.49, 0.20), 0.0, 0.0)],
            feature_kind="structural_frame",
            tags=["structure", "frame", "top_front", "swept_structural_frame"],
        ),
        _feature_swept_profile(
            component,
            center=(cx, cy - height * 0.46, cz + depth * 0.46),
            cross_section=section,
            sweep_path=[(-max(width * 0.49, 0.20), 0.0, 0.0), (max(width * 0.49, 0.20), 0.0, 0.0)],
            feature_kind="structural_frame",
            tags=["structure", "frame", "bottom_front", "swept_structural_frame"],
        ),
        _feature_swept_profile(
            component,
            center=(cx - width * 0.48, cy, cz + depth * 0.46),
            cross_section=section,
            sweep_path=[(0.0, -max(height * 0.49, 0.20), 0.0), (0.0, max(height * 0.49, 0.20), 0.0)],
            feature_kind="structural_frame",
            tags=["structure", "frame", "left_front", "swept_structural_frame"],
        ),
        _feature_swept_profile(
            component,
            center=(cx + width * 0.48, cy, cz + depth * 0.46),
            cross_section=section,
            sweep_path=[(0.0, -max(height * 0.49, 0.20), 0.0), (0.0, max(height * 0.49, 0.20), 0.0)],
            feature_kind="structural_frame",
            tags=["structure", "frame", "right_front", "swept_structural_frame"],
        ),
    ]


def recessed_handle_features(component: BlueprintComponent, *, depth_scale: float) -> list[ShapePrimitive]:
    """Create a recessed handle pocket with side mounts."""
    width, height, depth = component.extents
    side_w = max(width * 0.18, 0.24)
    mount_d = max(depth * 0.44 * depth_scale, 0.24)
    cx, cy, cz = component.center
    return [
        _feature_extruded_profile(
            component,
            center=(cx, cy, cz),
            profile_polygon=_chamfered_rectangle_polygon(
                max(width * 0.84, 0.28),
                max(height * 0.62, 0.28),
                max(min(width, height) * 0.06, 0.04),
            ),
            extrude_height=max(depth * 0.40 * depth_scale, 0.22),
            axis="z",
            feature_kind="recessed_handle",
            tags=["pocket", "extruded_handle_pocket"],
            blend_mode="subtract",
        ),
        _feature_extruded_profile(
            component,
            center=(cx - width * 0.26, cy, cz),
            profile_polygon=_chamfered_rectangle_polygon(side_w, height * 0.82, side_w * 0.20),
            extrude_height=mount_d,
            axis="z",
            feature_kind="recessed_handle",
            tags=["left_mount", "extruded_handle_mount"],
        ),
        _feature_extruded_profile(
            component,
            center=(cx + width * 0.26, cy, cz),
            profile_polygon=_chamfered_rectangle_polygon(side_w, height * 0.82, side_w * 0.20),
            extrude_height=mount_d,
            axis="z",
            feature_kind="recessed_handle",
            tags=["right_mount", "extruded_handle_mount"],
        ),
    ]


def hinge_set_features(component: BlueprintComponent, *, depth_scale: float) -> list[ShapePrimitive]:
    """Create paired hinge barrel features."""
    _width, height, depth = component.extents
    barrel_r = max(depth * 0.22, 0.22)
    barrel_h = max(height * 0.82, 0.40)
    cx, cy, cz = component.center
    return [
        _feature_revolved_profile(
            component,
            center=(cx, cy + height * 0.18, cz),
            axis=component.axis,
            profile_points=[
                (-barrel_h * 0.50, barrel_r * 0.82),
                (-barrel_h * 0.42, barrel_r),
                (barrel_h * 0.42, barrel_r),
                (barrel_h * 0.50, barrel_r * 0.82),
            ],
            feature_kind="hinge_set",
            tags=["upper", "lathed_hinge_barrel"],
        ),
        _feature_revolved_profile(
            component,
            center=(cx, cy - height * 0.18, cz),
            axis=component.axis,
            profile_points=[
                (-barrel_h * 0.50, barrel_r * 0.82),
                (-barrel_h * 0.42, barrel_r),
                (barrel_h * 0.42, barrel_r),
                (barrel_h * 0.50, barrel_r * 0.82),
            ],
            feature_kind="hinge_set",
            tags=["lower", "lathed_hinge_barrel"],
        ),
    ]


def clasp_set_features(component: BlueprintComponent, *, depth_scale: float) -> list[ShapePrimitive]:
    """Create clasp strap and tongue features."""
    width, height, depth = component.extents
    cx, cy, cz = component.center
    strap_w = max(width * 0.62, 0.28)
    strap_h = max(height * 0.18, 0.28)
    strap_d = max(depth * 0.26 * depth_scale, 0.22)
    tongue_w = max(width * 0.24, 0.24)
    tongue_h = max(height * 0.32, 0.24)
    tongue_d = max(depth * 0.22 * depth_scale, 0.22)
    return [
        _feature_extruded_profile(
            component,
            center=(cx, cy + height * 0.16, cz + depth * 0.12),
            profile_polygon=_chamfered_rectangle_polygon(strap_w, strap_h, strap_h * 0.25),
            extrude_height=strap_d,
            axis="z",
            feature_kind="clasp_set",
            tags=["strap", "extruded_clasp_strap"],
        ),
        _feature_extruded_profile(
            component,
            center=(cx, cy - height * 0.18, cz + depth * 0.18),
            profile_polygon=_chamfered_rectangle_polygon(tongue_w, tongue_h, min(tongue_w, tongue_h) * 0.20),
            extrude_height=tongue_d,
            axis="z",
            feature_kind="clasp_set",
            tags=["tongue", "extruded_clasp_tongue"],
        ),
    ]


def rotor_shroud_features(component: BlueprintComponent, *, scale: float) -> list[ShapePrimitive]:
    """Create a four-sided rotor shroud around a rotor pod."""
    width, _height, depth = component.extents
    radius = max(width, depth) * 0.70 * scale
    bar = max(radius * 0.10, 0.24)
    cx, cy, cz = component.center
    section = _round_cross_section(bar * 0.50)
    span = radius * 0.775
    return [
        _feature_swept_profile(
            component,
            center=(cx, cy, cz + radius),
            cross_section=section,
            sweep_path=[(-span, 0.0, 0.0), (span, 0.0, 0.0)],
            feature_kind="rotor_shroud",
            tags=["front", "swept_rotor_shroud"],
        ),
        _feature_swept_profile(
            component,
            center=(cx, cy, cz - radius),
            cross_section=section,
            sweep_path=[(-span, 0.0, 0.0), (span, 0.0, 0.0)],
            feature_kind="rotor_shroud",
            tags=["rear", "swept_rotor_shroud"],
        ),
        _feature_swept_profile(
            component,
            center=(cx + radius, cy, cz),
            cross_section=section,
            sweep_path=[(0.0, 0.0, -span), (0.0, 0.0, span)],
            feature_kind="rotor_shroud",
            tags=["left", "swept_rotor_shroud"],
        ),
        _feature_swept_profile(
            component,
            center=(cx - radius, cy, cz),
            cross_section=section,
            sweep_path=[(0.0, 0.0, -span), (0.0, 0.0, span)],
            feature_kind="rotor_shroud",
            tags=["right", "swept_rotor_shroud"],
        ),
    ]


def screen_bezel_features(component: BlueprintComponent, *, depth_scale: float) -> list[ShapePrimitive]:
    """Create frame and cutout features for a screen bezel."""
    width, height, depth = component.extents
    return [
        *panel_frame_features(component, depth_scale=depth_scale * 1.1, thickness_scale=1.0),
        _feature_extruded_profile(
            component,
            center=(component.center[0], component.center[1], component.center[2] + depth * 0.12),
            profile_polygon=_chamfered_rectangle_polygon(width * 0.78, height * 0.70, min(width, height) * 0.04),
            extrude_height=max(depth * 0.18 * depth_scale, 0.2),
            axis="z",
            feature_kind="screen_bezel",
            tags=["screen_window", "extruded_screen_window"],
            blend_mode="subtract",
        ),
    ]


def panel_seam_features(component: BlueprintComponent, *, count: int, depth_scale: float) -> list[ShapePrimitive]:
    """Create subtractive panel cut-lines on a component face."""
    width, height, depth = component.extents
    if count <= 0:
        return []
    line_w = max(width * 0.018, 0.16)
    line_h = max(height * 0.018, 0.16)
    line_d = max(depth * 0.26 * depth_scale, 0.18)
    cx, cy, cz = component.center
    primitives: list[ShapePrimitive] = []
    vertical_count = max(1, count // 2)
    horizontal_count = max(0, count - vertical_count)
    vertical_spacing = width * 0.62 / max(1, vertical_count + 1)
    for index in range(vertical_count):
        x = cx - width * 0.31 + vertical_spacing * (index + 1)
        primitives.append(
            _feature_extruded_profile(
                component,
                center=(x, cy, cz + depth * 0.30),
                profile_polygon=_chamfered_rectangle_polygon(line_w, height * 0.74, line_w * 0.45),
                extrude_height=line_d,
                axis="z",
                feature_kind="panel_seam",
                tags=["surface_detail", "cut_line", "vertical", "extruded_panel_seam", f"seam_v_{index}"],
                blend_mode="subtract",
            )
        )
    horizontal_spacing = height * 0.58 / max(1, horizontal_count + 1)
    for index in range(horizontal_count):
        y = cy - height * 0.29 + horizontal_spacing * (index + 1)
        primitives.append(
            _feature_extruded_profile(
                component,
                center=(cx, y, cz + depth * 0.31),
                profile_polygon=_chamfered_rectangle_polygon(width * 0.74, line_h, line_h * 0.45),
                extrude_height=line_d,
                axis="z",
                feature_kind="panel_seam",
                tags=["surface_detail", "cut_line", "horizontal", "extruded_panel_seam", f"seam_h_{index}"],
                blend_mode="subtract",
            )
        )
    return primitives


def groove_channel_features(
    component: BlueprintComponent, *, count: int, depth_scale: float
) -> list[ShapePrimitive]:
    """Create repeated subtractive channels on the primary face."""
    width, height, depth = component.extents
    if count <= 0:
        return []
    groove_w = max(width * 0.030, 0.18)
    groove_d = max(depth * 0.30 * depth_scale, 0.20)
    spacing = width * 0.64 / max(1, count - 1) if count > 1 else 0.0
    start_x = component.center[0] - spacing * (count - 1) / 2.0
    primitives: list[ShapePrimitive] = []
    for index in range(count):
        primitives.append(
            _feature_extruded_profile(
                component,
                center=(start_x + spacing * index, component.center[1], component.center[2] + depth * 0.28),
                profile_polygon=_chamfered_rectangle_polygon(groove_w, height * 0.72, groove_w * 0.45),
                extrude_height=groove_d,
                axis="z",
                feature_kind="groove_channel",
                tags=["surface_detail", "groove", "extruded_groove_channel", f"channel_{index}"],
                blend_mode="subtract",
                rounding=0.06,
            )
        )
    return primitives


def raised_ridge_features(
    component: BlueprintComponent, *, count: int, depth_scale: float, thickness_scale: float
) -> list[ShapePrimitive]:
    """Create raised surface ridges across the primary face."""
    width, height, depth = component.extents
    if count <= 0:
        return []
    ridge_h = max(height * 0.038 * thickness_scale, 0.20)
    ridge_d = max(depth * 0.18 * depth_scale, 0.20)
    spacing = height * 0.62 / max(1, count - 1) if count > 1 else 0.0
    start_y = component.center[1] - spacing * (count - 1) / 2.0
    primitives: list[ShapePrimitive] = []
    for index in range(count):
        primitives.append(
            _feature_extruded_profile(
                component,
                center=(component.center[0], start_y + spacing * index, component.center[2] + depth * 0.43),
                profile_polygon=_chamfered_rectangle_polygon(width * 0.76, ridge_h, ridge_h * 0.45),
                extrude_height=ridge_d,
                axis="z",
                feature_kind="raised_ridge",
                tags=["surface_detail", "ridge", "extruded_ridge", f"ridge_{index}"],
                rounding=0.04,
            )
        )
    return primitives


def layer_plate_features(
    component: BlueprintComponent, *, count: int, depth_scale: float
) -> list[ShapePrimitive]:
    """Create stacked raised plates for layered hard-surface construction."""
    width, height, depth = component.extents
    if count <= 0:
        return []
    primitives: list[ShapePrimitive] = []
    for index in range(count):
        inset = 0.10 + index * 0.08
        plate_w = max(width * (1.0 - inset * 2.0), 0.30)
        plate_h = max(height * (1.0 - inset * 1.6), 0.30)
        plate_d = max(depth * (0.10 + index * 0.035) * depth_scale, 0.18)
        primitives.append(
            _feature_extruded_profile(
                component,
                center=(
                    component.center[0],
                    component.center[1],
                    component.center[2] + depth * (0.36 + index * 0.035),
                ),
                profile_polygon=_chamfered_rectangle_polygon(plate_w, plate_h, min(plate_w, plate_h) * 0.08),
                extrude_height=plate_d,
                axis="z",
                feature_kind="layer_plate",
                tags=["surface_detail", "layered_piece", "extruded_plate", f"layer_{index}"],
                rounding=0.08,
            )
        )
    return primitives


def corner_guard_features(
    component: BlueprintComponent, *, depth_scale: float, thickness_scale: float
) -> list[ShapePrimitive]:
    """Create raised corner guards on box-like component faces."""
    width, height, depth = component.extents
    guard_w = max(width * 0.16 * thickness_scale, 0.28)
    guard_h = max(height * 0.16 * thickness_scale, 0.28)
    guard_d = max(depth * 0.30 * depth_scale, 0.22)
    cx, cy, cz = component.center
    offsets = (
        (-width * 0.39, -height * 0.39, "bottom_left"),
        (width * 0.39, -height * 0.39, "bottom_right"),
        (-width * 0.39, height * 0.39, "top_left"),
        (width * 0.39, height * 0.39, "top_right"),
    )
    return [
        _feature_extruded_profile(
            component,
            center=(cx + ox, cy + oy, cz + depth * 0.42),
            profile_polygon=_chamfered_rectangle_polygon(guard_w, guard_h, min(guard_w, guard_h) * 0.18),
            extrude_height=guard_d,
            axis="z",
            feature_kind="corner_guard",
            tags=["surface_detail", "edge_break", "extruded_corner_guard", corner],
            rounding=0.12,
        )
        for ox, oy, corner in offsets
    ]


def socket_point_features(
    component: BlueprintComponent, *, count: int, depth_scale: float
) -> list[ShapePrimitive]:
    """Create modular socket points as visible circular connection features.

    Promoted from a 2D column/row grid to a Poisson-disk surface-projected
    instancer (see ``lathe.instance_pattern``). Each sample point now
    receives a multi-primitive kit (raised collar ring + recessed cup)
    instead of a single revolved cup.
    """
    width, height, depth = component.extents
    if count <= 0:
        return []
    radius = max(min(width, height) * 0.045, 0.18)
    socket_depth = max(depth * 0.34 * depth_scale, 0.24)
    face = primary_face_frame(
        component,
        normal_axis="z",
        normal_sign=1,
        inset_ratio=0.62,
        offset_ratio=0.42,
    )

    def _factory(
        component: BlueprintComponent,
        face_arg,
        sample_uv: tuple[float, float],
        index: int,
    ) -> list[ShapePrimitive]:
        return socket_point_kit(
            component,
            face_arg,
            sample_uv,
            radius=radius,
            depth=socket_depth,
            index=index,
        )

    return distribute_greeble_kits(
        component,
        face,
        count=count,
        kit_factory=_factory,
        seed_token="socket_point",
        min_spacing=max(radius * 3.4, 0.36),
    )


def bolt_grid_features(component: BlueprintComponent, *, count: int, depth_scale: float) -> list[ShapePrimitive]:
    """Create raised bolt/rivet features over a primary component face.

    Promoted from a 2D column/row grid to a Poisson-disk surface-projected
    instancer (see ``lathe.instance_pattern``). Each sample now emits a
    bolt-cap + washer kit rather than a single domed cylinder, so what
    used to read as flat box-pasting now reads as fastener hardware.
    """
    width, height, depth = component.extents
    if count <= 0:
        return []
    radius = max(min(width, height) * 0.030, 0.14)
    bolt_height = max(depth * 0.12 * depth_scale, 0.16)
    face = primary_face_frame(
        component,
        normal_axis="z",
        normal_sign=1,
        inset_ratio=0.72,
        offset_ratio=0.46,
    )

    def _factory(
        component: BlueprintComponent,
        face_arg,
        sample_uv: tuple[float, float],
        index: int,
    ) -> list[ShapePrimitive]:
        return bolt_cap_kit(
            component,
            face_arg,
            sample_uv,
            radius=radius,
            height=bolt_height,
            index=index,
            head_style="hex",
        )

    return distribute_greeble_kits(
        component,
        face,
        count=count,
        kit_factory=_factory,
        seed_token="bolt_grid",
        min_spacing=max(radius * 2.8, 0.32),
    )


def brass_band_rivets_features(
    component: BlueprintComponent,
    *,
    band_count: int,
    rivets_per_band: int,
    band_z_fractions: list[float] | None = None,
    radius_scale: float = 1.0,
) -> list[ShapePrimitive]:
    """Distribute rivets evenly around a chest body's brass bands.

    The chest body is treated as a roughly cylindrical/box region wrapped
    by ``band_count`` horizontal brass bands at ``band_z_fractions``
    (vertical fractions of the component's height; defaults to evenly
    spaced top/middle/bottom positions). For each band, ``rivets_per_band``
    rivets are placed at evenly-spaced angles around the body's
    perimeter; each rivet is a ``bolt_cap_kit`` (washer + domed cap)
    oriented with its axis pointing radially outward (snapped to the
    nearest cardinal axis of x/z because the kit's FaceFrame requires
    a cardinal normal).

    Determinism: the same component + band layout always produces the
    same rivet positions (the only RNG is per-instance scale/age jitter
    seeded off ``component.name``).
    """
    if band_count <= 0 or rivets_per_band <= 0:
        return []

    width, height, depth = component.extents
    cx, cy, cz = component.center

    # Default band positions: evenly spaced over central 80% of body height.
    if band_z_fractions is None:
        if band_count == 1:
            band_z_fractions = [0.0]
        else:
            top = 0.36
            bottom = -0.36
            band_z_fractions = [
                bottom + (top - bottom) * (i / max(band_count - 1, 1))
                for i in range(band_count)
            ]
    band_z_fractions = list(band_z_fractions)[:band_count]

    rivet_radius = max(min(width, depth) * 0.012 * radius_scale, 0.10)
    rivet_height = max(rivet_radius * 1.05, 0.10)

    # Inset the rivet ring slightly inside the body's bounding hull so
    # the bolt cap sits proud of the band rather than free-floating.
    half_w = width * 0.50
    half_d = depth * 0.50

    primitives: list[ShapePrimitive] = []
    rivet_index = 0
    for band_idx, z_frac in enumerate(band_z_fractions):
        band_y = cy + height * float(z_frac)
        for angle_idx in range(rivets_per_band):
            angle = (angle_idx / rivets_per_band) * 2.0 * math.pi
            # Compute the radial position on the body's cardinal-axis
            # perimeter (treating the box as the inscribed rectangle at
            # this height). The closest cardinal face determines the
            # FaceFrame normal axis.
            ux = math.cos(angle)
            uz = math.sin(angle)
            if abs(ux) >= abs(uz):
                # Rivet sits on +x or -x face.
                normal_axis = "x"
                normal_sign = 1 if ux > 0.0 else -1
                world_x = cx + half_w * normal_sign
                world_z = cz + uz * (half_d * 0.95) * (abs(ux) ** 0.5)
            else:
                # Rivet sits on +z or -z face.
                normal_axis = "z"
                normal_sign = 1 if uz > 0.0 else -1
                world_z = cz + half_d * normal_sign
                world_x = cx + ux * (half_w * 0.95) * (abs(uz) ** 0.5)

            face = FaceFrame(
                origin=(world_x, band_y, world_z),
                half_u=max(rivet_radius * 4.0, 0.20),
                half_v=max(rivet_radius * 4.0, 0.20),
                tangent_axis="z" if normal_axis == "x" else "x",
                bitangent_axis="y",
                normal_axis=normal_axis,
                normal_sign=normal_sign,
            )

            # Per-instance jitter (deterministic from component + index).
            jitter_seed = (hash((component.name, "rivet", rivet_index)) & 0xFFFFFFFF) or 1
            t = (jitter_seed % 1024) / 1024.0
            scale_uniform = 0.92 + (1.08 - 0.92) * t
            age_t = ((jitter_seed >> 10) % 1024) / 1024.0
            age_value = 0.30 * age_t

            attributes = InstanceAttributes(
                scale_uniform=scale_uniform,
                rotation=0.0,
                material_variant_index=rivet_index % 4,
                age=age_value,
            )

            kit = bolt_cap_kit(
                component,
                face,
                sample_uv=(0.0, 0.0),
                radius=rivet_radius,
                height=rivet_height,
                index=rivet_index,
                head_style="dome",
                lod_level=0,
                attributes=attributes,
            )
            for prim in kit:
                prim.tags = [
                    *prim.tags,
                    "brass_band_rivet",
                    f"band_{band_idx}",
                    f"angle_{angle_idx}",
                    "instance_pattern_band",
                ]
            primitives.extend(kit)
            rivet_index += 1

    return primitives


def trim_strip_features(
    component: BlueprintComponent, *, count: int, depth_scale: float, thickness_scale: float
) -> list[ShapePrimitive]:
    """Create repeated narrow trim strips across a primary hard-surface face."""
    width, height, depth = component.extents
    if count <= 0:
        return []
    strip_h = max(height * 0.030 * thickness_scale, 0.18)
    strip_d = max(depth * 0.16 * depth_scale, 0.18)
    spacing = height * 0.66 / max(1, count - 1) if count > 1 else 0.0
    start_y = component.center[1] - spacing * (count - 1) / 2.0
    primitives: list[ShapePrimitive] = []
    for index in range(count):
        primitives.append(
            _feature_extruded_profile(
                component,
                center=(component.center[0], start_y + spacing * index, component.center[2] + depth * 0.47),
                profile_polygon=_chamfered_rectangle_polygon(width * 0.86, strip_h, strip_h * 0.35),
                extrude_height=strip_d,
                axis="z",
                feature_kind="trim_strip",
                tags=["surface_detail", "trim", "linear_repeat", "extruded_trim", f"trim_{index}"],
                rounding=0.04,
            )
        )
    return primitives


def outset_panel_features(component: BlueprintComponent, *, count: int, depth_scale: float) -> list[ShapePrimitive]:
    """Create raised inset/outset plate islands on the primary face."""
    width, height, depth = component.extents
    if count <= 0:
        return []
    columns = min(max(1, count), 3)
    rows = max(1, (count + columns - 1) // columns)
    primitives: list[ShapePrimitive] = []
    for index in range(count):
        col = index % columns
        row = index // columns
        x = component.center[0] + (col - (columns - 1) / 2.0) * width * 0.25
        y = component.center[1] + (row - (rows - 1) / 2.0) * height * 0.23
        panel_w = max(width * 0.20, 0.24)
        panel_h = max(height * 0.18, 0.24)
        primitives.append(
            _feature_extruded_profile(
                component,
                center=(x, y, component.center[2] + depth * 0.50),
                profile_polygon=_chamfered_rectangle_polygon(panel_w, panel_h, min(panel_w, panel_h) * 0.16),
                extrude_height=max(depth * 0.18 * depth_scale, 0.18),
                axis="z",
                feature_kind="outset_panel",
                tags=["surface_detail", "outset", "plate_island", "extruded_outset_panel", f"outset_{index}"],
                rounding=0.06,
            )
        )
    return primitives


def linear_detail_array_features(
    component: BlueprintComponent, *, count: int, axis: str, depth_scale: float
) -> list[ShapePrimitive]:
    """Create a generic line of raised detail blocks along one local axis."""
    width, height, depth = component.extents
    if count <= 0:
        return []
    axis = axis if axis in {"x", "y"} else "x"
    span = width if axis == "x" else height
    spacing = span * 0.66 / max(1, count - 1) if count > 1 else 0.0
    start = -spacing * (count - 1) / 2.0
    primitives: list[ShapePrimitive] = []
    for index in range(count):
        offset = start + spacing * index
        cx = component.center[0] + (offset if axis == "x" else 0.0)
        cy = component.center[1] + (offset if axis == "y" else 0.0)
        detail_w = max(width * (0.060 if axis == "x" else 0.18), 0.16)
        detail_h = max(height * (0.18 if axis == "x" else 0.060), 0.16)
        primitives.append(
            _feature_extruded_profile(
                component,
                center=(cx, cy, component.center[2] + depth * 0.52),
                profile_polygon=_chamfered_rectangle_polygon(detail_w, detail_h, min(detail_w, detail_h) * 0.25),
                extrude_height=max(depth * 0.15 * depth_scale, 0.16),
                axis="z",
                feature_kind="linear_detail_array",
                tags=["surface_detail", "repeated_detail", "linear_array", "extruded_linear_detail", f"array_{index}"],
                rounding=0.05,
            )
        )
    return primitives


def radial_detail_array_features(
    component: BlueprintComponent, *, count: int, depth_scale: float
) -> list[ShapePrimitive]:
    """Create circularly arranged rivet-like details on a component face."""
    width, height, depth = component.extents
    if count <= 0:
        return []
    radius = max(min(width, height) * 0.030, 0.12)
    array_radius_x = width * 0.28
    array_radius_y = height * 0.26
    primitives: list[ShapePrimitive] = []
    for index in range(count):
        angle = (index / max(1, count)) * 6.283185307179586
        x = component.center[0] + math.cos(angle) * array_radius_x
        y = component.center[1] + math.sin(angle) * array_radius_y
        primitives.append(
            _feature_revolved_profile(
                component,
                center=(x, y, component.center[2] + depth * 0.50),
                axis="z",
                profile_points=_domed_profile(radius, max(depth * 0.13 * depth_scale, 0.14)),
                feature_kind="radial_detail_array",
                tags=["surface_detail", "repeated_detail", "radial_array", "domed_radial_detail", f"radial_{index}"],
            )
        )
    return primitives


def rail_attachment_features(
    component: BlueprintComponent, *, count: int, depth_scale: float, thickness_scale: float
) -> list[ShapePrimitive]:
    """Create raised mounting rails that can read as modular slide tracks."""
    width, height, depth = component.extents
    if count <= 0:
        return []
    rail_w = max(width * 0.045 * thickness_scale, 0.20)
    rail_h = max(height * 0.74, 0.36)
    rail_d = max(depth * 0.22 * depth_scale, 0.20)
    spacing = width * 0.56 / max(1, count - 1) if count > 1 else 0.0
    start_x = component.center[0] - spacing * (count - 1) / 2.0
    primitives: list[ShapePrimitive] = []
    for index in range(count):
        rail_x = start_x + spacing * index
        primitives.append(
            _feature_extruded_profile(
                component,
                center=(rail_x, component.center[1], component.center[2] + depth * 0.54),
                profile_polygon=_chamfered_rectangle_polygon(rail_w, rail_h, rail_w * 0.35),
                extrude_height=rail_d,
                axis="z",
                feature_kind="attachment_rail",
                tags=["surface_detail", "attachment_motif", "rail", "module_mount", "extruded_attachment_rail", f"rail_{index}"],
                rounding=0.05,
            )
        )
    return primitives


def fin_attachment_features(
    component: BlueprintComponent, *, count: int, depth_scale: float, thickness_scale: float
) -> list[ShapePrimitive]:
    """Create repeated fin plates that change silhouette and surface rhythm."""
    width, height, depth = component.extents
    if count <= 0:
        return []
    fin_w = max(width * 0.045 * thickness_scale, 0.18)
    fin_h = max(height * 0.54, 0.32)
    fin_d = max(depth * 0.58 * depth_scale, 0.28)
    spacing = width * 0.72 / max(1, count - 1) if count > 1 else 0.0
    start_x = component.center[0] - spacing * (count - 1) / 2.0
    primitives: list[ShapePrimitive] = []
    for index in range(count):
        fin_x = start_x + spacing * index
        primitives.append(
            _feature_extruded_profile(
                component,
                center=(fin_x, component.center[1] + height * 0.05, component.center[2] + depth * 0.62),
                profile_polygon=[
                    (-fin_w * 0.50, -fin_h * 0.50),
                    (fin_w * 0.50, -fin_h * 0.50),
                    (fin_w * 0.42, fin_h * 0.36),
                    (0.0, fin_h * 0.50),
                    (-fin_w * 0.42, fin_h * 0.36),
                ],
                extrude_height=fin_d,
                axis="z",
                feature_kind="attachment_fin",
                tags=["surface_detail", "attachment_motif", "fin", "silhouette_detail", "extruded_fin", f"fin_{index}"],
                rounding=0.03,
            )
        )
    return primitives


def strap_attachment_features(
    component: BlueprintComponent, *, count: int, depth_scale: float, thickness_scale: float
) -> list[ShapePrimitive]:
    """Create broad retaining straps across the face of a component."""
    width, height, depth = component.extents
    if count <= 0:
        return []
    strap_w = max(width * 0.11 * thickness_scale, 0.24)
    strap_d = max(depth * 0.24 * depth_scale, 0.20)
    spacing = width * 0.58 / max(1, count - 1) if count > 1 else 0.0
    start_x = component.center[0] - spacing * (count - 1) / 2.0
    primitives: list[ShapePrimitive] = []
    for index in range(count):
        strap_x = start_x + spacing * index
        primitives.append(
            _feature_extruded_profile(
                component,
                center=(strap_x, component.center[1], component.center[2] + depth * 0.55),
                profile_polygon=_chamfered_rectangle_polygon(strap_w, height * 0.92, strap_w * 0.22),
                extrude_height=strap_d,
                axis="z",
                feature_kind="attachment_strap",
                tags=["surface_detail", "attachment_motif", "strap", "retainer", "extruded_attachment_strap", f"strap_{index}"],
                rounding=0.08,
            )
        )
    return primitives


def cable_attachment_features(
    component: BlueprintComponent, *, count: int, depth_scale: float
) -> list[ShapePrimitive]:
    """Create parallel cable runs on the surface."""
    width, height, depth = component.extents
    if count <= 0:
        return []
    radius = max(min(width, height) * 0.026, 0.12)
    spacing = height * 0.48 / max(1, count - 1) if count > 1 else 0.0
    start_y = component.center[1] - spacing * (count - 1) / 2.0
    primitives: list[ShapePrimitive] = []
    for index in range(count):
        primitives.append(
            _feature_swept_profile(
                component,
                center=(component.center[0], start_y + spacing * index, component.center[2] + depth * 0.58),
                cross_section=_round_cross_section(radius),
                sweep_path=[
                    (-max(width * 0.76, 0.40) * 0.50, 0.0, 0.0),
                    (0.0, 0.0, depth * 0.045 * depth_scale),
                    (max(width * 0.76, 0.40) * 0.50, 0.0, 0.0),
                ],
                feature_kind="attachment_cable",
                tags=["surface_detail", "attachment_motif", "cable", "routing", "swept_cable", f"cable_{index}"],
            )
        )
    return primitives


def vent_stack_attachment_features(
    component: BlueprintComponent, *, count: int, depth_scale: float
) -> list[ShapePrimitive]:
    """Create a stack of subtractive vent cuts with a raised backing plate."""
    width, height, depth = component.extents
    if count <= 0:
        return []
    plate_w = width * 0.70
    plate_h = height * 0.62
    plate_d = max(depth * 0.12 * depth_scale, 0.18)
    plate = _feature_extruded_profile(
        component,
        center=(component.center[0], component.center[1], component.center[2] + depth * 0.48),
        profile_polygon=_chamfered_rectangle_polygon(plate_w, plate_h, min(plate_w, plate_h) * 0.06),
        extrude_height=plate_d,
        axis="z",
        feature_kind="attachment_vent_stack",
        tags=["surface_detail", "attachment_motif", "vent_stack", "backing_plate", "extruded_vent_backing"],
        rounding=0.06,
    )
    slot_h = max(height * 0.035, 0.14)
    spacing = height * 0.44 / max(1, count - 1) if count > 1 else 0.0
    start_y = component.center[1] - spacing * (count - 1) / 2.0
    primitives = [plate]
    for index in range(count):
        primitives.append(
            _feature_extruded_profile(
                component,
                center=(component.center[0], start_y + spacing * index, component.center[2] + depth * 0.56),
                profile_polygon=_chamfered_rectangle_polygon(width * 0.58, slot_h, slot_h * 0.35),
                extrude_height=max(depth * 0.24 * depth_scale, 0.18),
                axis="z",
                feature_kind="attachment_vent_stack",
                tags=["surface_detail", "attachment_motif", "vent_stack", "vent_cut", "extruded_vent_cut", f"vent_{index}"],
                blend_mode="subtract",
                rounding=0.03,
            )
        )
    return primitives


def handle_bar_attachment_features(
    component: BlueprintComponent, *, depth_scale: float, thickness_scale: float
) -> list[ShapePrimitive]:
    """Create a generic grab handle motif with two mounts."""
    width, height, depth = component.extents
    radius = max(min(width, height) * 0.035 * thickness_scale, 0.14)
    bar_width = max(width * 0.58, 0.50)
    mount_w = max(width * 0.09 * thickness_scale, 0.18)
    mount_h = max(height * 0.20, 0.20)
    mount_d = max(depth * 0.30 * depth_scale, 0.20)
    cx, cy, cz = component.center
    return [
        _feature_swept_profile(
            component,
            center=(cx, cy, cz + depth * 0.54),
            cross_section=_round_cross_section(radius),
            sweep_path=[
                (-bar_width * 0.50, 0.0, 0.0),
                (-bar_width * 0.40, 0.0, depth * 0.13),
                (bar_width * 0.40, 0.0, depth * 0.13),
                (bar_width * 0.50, 0.0, 0.0),
            ],
            feature_kind="attachment_handle_bar",
            tags=["surface_detail", "attachment_motif", "handle", "grab_bar", "swept_handle"],
        ),
        _feature_extruded_profile(
            component,
            center=(cx - bar_width * 0.48, cy, cz + depth * 0.54),
            profile_polygon=_chamfered_rectangle_polygon(mount_w, mount_h, mount_w * 0.18),
            extrude_height=mount_d,
            axis="z",
            feature_kind="attachment_handle_bar",
            tags=["surface_detail", "attachment_motif", "handle", "left_mount", "extruded_handle_mount"],
            rounding=0.05,
        ),
        _feature_extruded_profile(
            component,
            center=(cx + bar_width * 0.48, cy, cz + depth * 0.54),
            profile_polygon=_chamfered_rectangle_polygon(mount_w, mount_h, mount_w * 0.18),
            extrude_height=mount_d,
            axis="z",
            feature_kind="attachment_handle_bar",
            tags=["surface_detail", "attachment_motif", "handle", "right_mount", "extruded_handle_mount"],
            rounding=0.05,
        ),
    ]


def guard_bar_attachment_features(
    component: BlueprintComponent, *, depth_scale: float, thickness_scale: float
) -> list[ShapePrimitive]:
    """Create protective guard bars on exposed component edges."""
    width, height, depth = component.extents
    bar = max(min(width, height) * 0.045 * thickness_scale, 0.16)
    cx, cy, cz = component.center
    return [
        _feature_swept_profile(
            component,
            center=(cx - width * 0.43, cy, cz + depth * 0.58),
            cross_section=_round_cross_section(bar * 0.50),
            sweep_path=[(0.0, -height * 0.43, 0.0), (0.0, height * 0.43, 0.0)],
            feature_kind="attachment_guard_bar",
            tags=["surface_detail", "attachment_motif", "guard", "left", "swept_guard_bar"],
        ),
        _feature_swept_profile(
            component,
            center=(cx + width * 0.43, cy, cz + depth * 0.58),
            cross_section=_round_cross_section(bar * 0.50),
            sweep_path=[(0.0, -height * 0.43, 0.0), (0.0, height * 0.43, 0.0)],
            feature_kind="attachment_guard_bar",
            tags=["surface_detail", "attachment_motif", "guard", "right", "swept_guard_bar"],
        ),
        _feature_swept_profile(
            component,
            center=(cx, cy + height * 0.43, cz + depth * 0.58),
            cross_section=_round_cross_section(bar * 0.50),
            sweep_path=[(-width * 0.43, 0.0, 0.0), (width * 0.43, 0.0, 0.0)],
            feature_kind="attachment_guard_bar",
            tags=["surface_detail", "attachment_motif", "guard", "top", "swept_guard_bar"],
        ),
    ]


def ornament_attachment_features(component: BlueprintComponent, *, count: int, depth_scale: float) -> list[ShapePrimitive]:
    """Create small ornamental studs in a readable radial cluster."""
    return [
        _with_feature_kind(primitive, "attachment_ornament", extra_tags=["attachment_motif", "ornament"])
        for primitive in radial_detail_array_features(component, count=count, depth_scale=depth_scale)
    ]


def _with_feature_kind(
    primitive: ShapePrimitive, feature_kind: str, *, extra_tags: Iterable[str]
) -> ShapePrimitive:
    primitive.component = feature_kind
    for tag in extra_tags:
        if tag not in primitive.tags:
            primitive.tags.append(tag)
    if feature_kind not in primitive.tags:
        primitive.tags.append(feature_kind)
    return primitive


def sensor_pod_module_features(
    component: BlueprintComponent, *, count: int, depth_scale: float, thickness_scale: float
) -> list[ShapePrimitive]:
    """Create swappable sensor pod modules with housings and lens caps."""
    width, height, depth = component.extents
    count = max(1, count)
    spacing = width * 0.54 / max(1, count - 1) if count > 1 else 0.0
    start_x = component.center[0] - spacing * (count - 1) / 2.0
    primitives: list[ShapePrimitive] = []
    for index in range(count):
        x = start_x + spacing * index
        pod_extents = (
            max(width * 0.16 * thickness_scale, 0.26),
            max(height * 0.18 * thickness_scale, 0.26),
            max(depth * 0.32 * depth_scale, 0.24),
        )
        primitives.append(
            _feature_subdivision_box(
                component,
                center=(x, component.center[1], component.center[2] + depth * 0.62),
                extents=pod_extents,
                corner_radii=_soft_corner_radii(pod_extents, 0.22),
                feature_kind="module_sensor_pod",
                tags=["surface_detail", "module_category", "sensor_pod", "swappable_module", "subdivision_sensor_pod", f"module_{index}"],
                corner_segments=4,
            )
        )
        primitives.append(
            _feature_revolved_profile(
                component,
                center=(x, component.center[1], component.center[2] + depth * 0.81),
                axis="z",
                profile_points=_domed_profile(max(min(width, height) * 0.045, 0.14), max(depth * 0.14 * depth_scale, 0.12)),
                feature_kind="module_sensor_pod",
                tags=["surface_detail", "module_category", "sensor_pod", "lens", "domed_sensor_lens", f"module_{index}"],
            )
        )
    return primitives


def power_cell_module_features(
    component: BlueprintComponent, *, count: int, depth_scale: float
) -> list[ShapePrimitive]:
    """Create clipped-in power-cell modules."""
    width, height, depth = component.extents
    count = max(1, count)
    spacing = height * 0.50 / max(1, count - 1) if count > 1 else 0.0
    start_y = component.center[1] - spacing * (count - 1) / 2.0
    primitives: list[ShapePrimitive] = []
    for index in range(count):
        y = start_y + spacing * index
        cell_radius = max(min(width, height) * 0.050, 0.16)
        cell_length = max(width * 0.58, 0.42)
        primitives.append(
            _feature_revolved_profile(
                component,
                center=(component.center[0], y, component.center[2] + depth * 0.62),
                axis="x",
                profile_points=_capsule_profile(cell_radius, cell_length),
                feature_kind="module_power_cell",
                tags=["surface_detail", "module_category", "power_cell", "swappable_module", "lathed_power_cell", f"cell_{index}"],
            )
        )
        primitives.append(
            _feature_extruded_profile(
                component,
                center=(component.center[0], y, component.center[2] + depth * 0.45),
                profile_polygon=_chamfered_rectangle_polygon(max(width * 0.66, 0.42), max(height * 0.030, 0.12), max(height * 0.010, 0.02)),
                extrude_height=max(depth * 0.12 * depth_scale, 0.12),
                axis="z",
                feature_kind="module_power_cell",
                tags=["surface_detail", "module_category", "power_cell", "retainer", "extruded_power_cell_clip", f"cell_clip_{index}"],
                rounding=0.03,
            )
        )
    return primitives


def barrel_module_features(component: BlueprintComponent, *, count: int, depth_scale: float) -> list[ShapePrimitive]:
    """Create forward barrel or nozzle modules."""
    width, height, depth = component.extents
    count = max(1, count)
    spacing = width * 0.36 / max(1, count - 1) if count > 1 else 0.0
    start_x = component.center[0] - spacing * (count - 1) / 2.0
    primitives: list[ShapePrimitive] = []
    for index in range(count):
        x = start_x + spacing * index
        barrel_radius = max(min(width, height) * 0.045, 0.15)
        barrel_depth = max(depth * 0.68 * depth_scale, 0.38)
        primitives.append(
            _feature_revolved_profile(
                component,
                center=(x, component.center[1], component.center[2] + depth * 0.82),
                axis="z",
                profile_points=[
                    (-barrel_depth * 0.50, barrel_radius * 0.92),
                    (-barrel_depth * 0.36, barrel_radius),
                    (barrel_depth * 0.24, barrel_radius * 0.82),
                    (barrel_depth * 0.50, barrel_radius * 0.68),
                ],
                feature_kind="module_barrel",
                tags=["surface_detail", "module_category", "barrel", "swappable_module", "lathed_module_barrel", f"barrel_{index}"],
            )
        )
        primitives.append(
            _feature_revolved_profile(
                component,
                center=(x, component.center[1], component.center[2] + depth * 1.14),
                axis="z",
                profile_points=_tapered_socket_profile(
                    max(min(width, height) * 0.030, 0.10),
                    max(depth * 0.22 * depth_scale, 0.16),
                ),
                feature_kind="module_barrel",
                tags=["surface_detail", "module_category", "barrel", "muzzle", "lathed_muzzle_cutout", f"barrel_tip_{index}"],
                blend_mode="subtract",
            )
        )
    return primitives


def blade_module_features(
    component: BlueprintComponent, *, count: int, depth_scale: float, thickness_scale: float
) -> list[ShapePrimitive]:
    """Create swappable blade-like fins or tool heads."""
    width, height, depth = component.extents
    count = max(1, count)
    spacing = width * 0.46 / max(1, count - 1) if count > 1 else 0.0
    start_x = component.center[0] - spacing * (count - 1) / 2.0
    primitives: list[ShapePrimitive] = []
    for index in range(count):
        blade_x = start_x + spacing * index
        blade_w = max(width * 0.10 * thickness_scale, 0.18)
        blade_h = max(height * 0.76, 0.36)
        blade_d = max(depth * 0.52 * depth_scale, 0.28)
        primitives.append(
            _feature_extruded_profile(
                component,
                center=(blade_x, component.center[1] + height * 0.03, component.center[2] + depth * 0.86),
                profile_polygon=[
                    (-blade_w * 0.50, -blade_h * 0.50),
                    (blade_w * 0.50, -blade_h * 0.44),
                    (blade_w * 0.32, blade_h * 0.34),
                    (0.0, blade_h * 0.50),
                    (-blade_w * 0.32, blade_h * 0.34),
                ],
                extrude_height=blade_d,
                axis="z",
                feature_kind="module_blade",
                tags=["surface_detail", "module_category", "blade", "swappable_module", "extruded_module_blade", f"blade_{index}"],
                rounding=0.03,
            )
        )
    return primitives


def wing_module_features(
    component: BlueprintComponent, *, count: int, depth_scale: float, thickness_scale: float
) -> list[ShapePrimitive]:
    """Create paired wing or stabilizer modules that expand the silhouette."""
    width, height, depth = component.extents
    count = max(1, count)
    primitives: list[ShapePrimitive] = []
    for index in range(count):
        y = component.center[1] + (index - (count - 1) / 2.0) * height * 0.18
        for side, sign in (("left", -1.0), ("right", 1.0)):
            wing_w = max(width * 0.42 * thickness_scale, 0.28)
            wing_h = max(height * 0.070, 0.16)
            wing_d = max(depth * 0.46 * depth_scale, 0.24)
            primitives.append(
                _feature_extruded_profile(
                    component,
                    center=(component.center[0] + sign * width * 0.56, y, component.center[2] + depth * 0.30),
                    profile_polygon=[
                        (-wing_w * 0.50, -wing_h * 0.50),
                        (wing_w * 0.42, -wing_h * 0.40),
                        (wing_w * 0.50, 0.0),
                        (wing_w * 0.28, wing_h * 0.50),
                        (-wing_w * 0.50, wing_h * 0.34),
                    ],
                    extrude_height=wing_d,
                    axis="z",
                    feature_kind="module_wing",
                    tags=["surface_detail", "module_category", "wing", "silhouette_module", "extruded_module_wing", side, f"wing_{index}"],
                    rounding=0.04,
                )
            )
    return primitives


def leg_module_features(component: BlueprintComponent, *, count: int, depth_scale: float) -> list[ShapePrimitive]:
    """Create deployable leg/stand modules."""
    width, height, depth = component.extents
    count = max(1, count)
    columns = min(2, count)
    primitives: list[ShapePrimitive] = []
    for index in range(count):
        col = index % columns
        row = index // columns
        x = component.center[0] + (col - (columns - 1) / 2.0) * width * 0.58
        z = component.center[2] + (row - 0.5) * depth * 0.30
        leg_radius = max(min(width, depth) * 0.030, 0.07)
        leg_span = max(height * 0.58, 0.34)
        foot_w = max(width * 0.22, 0.24)
        foot_h = max(height * 0.050, 0.14)
        foot_d = max(depth * 0.22, 0.24)
        primitives.append(
            _feature_swept_profile(
                component,
                center=(x, component.center[1] - height * 0.58, z),
                cross_section=_round_cross_section(leg_radius, segments=8),
                sweep_path=[
                    (0.0, leg_span * 0.50, -depth * 0.04),
                    (width * 0.030 * (1.0 if col else -1.0), 0.0, 0.0),
                    (0.0, -leg_span * 0.50, depth * 0.06 * depth_scale),
                ],
                feature_kind="module_leg",
                tags=["surface_detail", "module_category", "leg", "support_module", "swept_leg_strut", f"leg_{index}"],
            )
        )
        primitives.append(
            _feature_extruded_profile(
                component,
                center=(x, component.center[1] - height * 0.88, z),
                profile_polygon=_chamfered_rectangle_polygon(foot_w, foot_h, min(foot_w, foot_h) * 0.30),
                extrude_height=foot_d,
                axis="z",
                feature_kind="module_leg",
                tags=["surface_detail", "module_category", "leg", "foot_pad", "extruded_leg_foot", f"leg_foot_{index}"],
                rounding=0.05,
            )
        )
    return primitives


def shield_plate_module_features(
    component: BlueprintComponent, *, count: int, depth_scale: float, thickness_scale: float
) -> list[ShapePrimitive]:
    """Create replaceable armor/shield plates."""
    width, height, depth = component.extents
    count = max(1, count)
    spacing = height * 0.50 / max(1, count - 1) if count > 1 else 0.0
    start_y = component.center[1] - spacing * (count - 1) / 2.0
    primitives: list[ShapePrimitive] = []
    for index in range(count):
        shield_w = max(width * 0.72, 0.38)
        shield_h = max(height * 0.18 * thickness_scale, 0.22)
        shield_d = max(depth * 0.28 * depth_scale, 0.20)
        primitives.append(
            _feature_extruded_profile(
                component,
                center=(component.center[0], start_y + spacing * index, component.center[2] + depth * 0.60),
                profile_polygon=[
                    (-shield_w * 0.50, -shield_h * 0.36),
                    (-shield_w * 0.40, -shield_h * 0.50),
                    (shield_w * 0.40, -shield_h * 0.50),
                    (shield_w * 0.50, -shield_h * 0.36),
                    (shield_w * 0.38, shield_h * 0.46),
                    (0.0, shield_h * 0.50),
                    (-shield_w * 0.38, shield_h * 0.46),
                ],
                extrude_height=shield_d,
                axis="z",
                feature_kind="module_shield_plate",
                tags=["surface_detail", "module_category", "shield_plate", "armor_module", "extruded_shield_plate", f"shield_{index}"],
                rounding=0.08,
            )
        )
    return primitives


def antenna_module_features(component: BlueprintComponent, *, count: int, depth_scale: float) -> list[ShapePrimitive]:
    """Create slim antenna or mast modules."""
    width, height, depth = component.extents
    count = max(1, count)
    spacing = width * 0.48 / max(1, count - 1) if count > 1 else 0.0
    start_x = component.center[0] - spacing * (count - 1) / 2.0
    primitives: list[ShapePrimitive] = []
    for index in range(count):
        x = start_x + spacing * index
        primitives.append(
            _feature_swept_profile(
                component,
                center=(x, component.center[1] + height * 0.55, component.center[2] + depth * 0.18),
                cross_section=_round_cross_section(max(min(width, depth) * 0.018, 0.07), segments=7),
                sweep_path=[
                    (0.0, -max(height * 0.36 * depth_scale, 0.18), 0.0),
                    (width * 0.02, 0.0, depth * 0.015),
                    (0.0, max(height * 0.36 * depth_scale, 0.18), 0.0),
                ],
                feature_kind="module_antenna",
                tags=["surface_detail", "module_category", "antenna", "signal_module", "swept_antenna_mast", f"antenna_{index}"],
            )
        )
        primitives.append(
            _feature_sphere(
                component,
                center=(x, component.center[1] + height * 0.92, component.center[2] + depth * 0.18),
                radius=max(min(width, depth) * 0.034, 0.10),
                feature_kind="module_antenna",
                tags=["surface_detail", "module_category", "antenna", "cap", "spherical_antenna_cap", f"antenna_cap_{index}"],
                rounding=0.03,
            )
        )
    return primitives


def silhouette_spine_features(
    component: BlueprintComponent, *, count: int, depth_scale: float, thickness_scale: float
) -> list[ShapePrimitive]:
    """Create large dorsal silhouette spines along the top face."""
    width, height, depth = component.extents
    count = max(1, count)
    spacing = width * 0.54 / max(1, count - 1) if count > 1 else 0.0
    start_x = component.center[0] - spacing * (count - 1) / 2.0
    primitives: list[ShapePrimitive] = []
    for index in range(count):
        spine_w = max(width * 0.08 * thickness_scale, 0.18)
        spine_h = max(height * 0.42 * depth_scale, 0.26)
        spine_d = max(depth * 0.22, 0.22)
        primitives.append(
            _feature_extruded_profile(
                component,
                center=(start_x + spacing * index, component.center[1] + height * 0.58, component.center[2]),
                profile_polygon=[
                    (-spine_w * 0.50, -spine_h * 0.50),
                    (spine_w * 0.50, -spine_h * 0.50),
                    (spine_w * 0.38, spine_h * 0.12),
                    (0.0, spine_h * 0.50),
                    (-spine_w * 0.38, spine_h * 0.12),
                ],
                extrude_height=spine_d,
                axis="z",
                feature_kind="silhouette_spine",
                tags=[
                    "surface_detail",
                    "silhouette_detail",
                    "silhouette_motif",
                    "silhouette_motif_spine",
                    "spine",
                    "extruded_silhouette_spine",
                    f"spine_{index}",
                ],
                rounding=0.04,
            )
        )
    return primitives


def silhouette_wing_features(
    component: BlueprintComponent, *, count: int, depth_scale: float, thickness_scale: float
) -> list[ShapePrimitive]:
    """Create broad side-wing silhouettes for drones, panels, and tools."""
    width, height, depth = component.extents
    count = max(1, count)
    primitives: list[ShapePrimitive] = []
    for index in range(count):
        y = component.center[1] + (index - (count - 1) / 2.0) * height * 0.20
        for side, sign in (("left", -1.0), ("right", 1.0)):
            wing_w = max(width * 0.56 * thickness_scale, 0.34)
            wing_h = max(height * 0.075, 0.14)
            wing_d = max(depth * 0.54 * depth_scale, 0.26)
            primitives.append(
                _feature_extruded_profile(
                    component,
                    center=(component.center[0] + sign * width * 0.68, y, component.center[2] + depth * 0.02),
                    profile_polygon=[
                        (-wing_w * 0.50, -wing_h * 0.50),
                        (wing_w * 0.44, -wing_h * 0.36),
                        (wing_w * 0.50, 0.0),
                        (wing_w * 0.30, wing_h * 0.50),
                        (-wing_w * 0.50, wing_h * 0.30),
                    ],
                    extrude_height=wing_d,
                    axis="z",
                    feature_kind="silhouette_wing",
                    tags=[
                        "surface_detail",
                        "silhouette_detail",
                        "silhouette_motif",
                        "silhouette_motif_wing",
                        "wing",
                        "extruded_silhouette_wing",
                        side,
                        f"wing_{index}",
                    ],
                    rounding=0.04,
                )
            )
    return primitives


def silhouette_tower_features(
    component: BlueprintComponent, *, count: int, depth_scale: float, thickness_scale: float
) -> list[ShapePrimitive]:
    """Create vertical tower/spire silhouettes rising from the top face."""
    width, height, depth = component.extents
    count = max(1, count)
    spacing = width * 0.34 / max(1, count - 1) if count > 1 else 0.0
    start_x = component.center[0] - spacing * (count - 1) / 2.0
    primitives: list[ShapePrimitive] = []
    for index in range(count):
        x = start_x + spacing * index
        tower_extents = (
            max(width * 0.12 * thickness_scale, 0.22),
            max(height * 0.64 * depth_scale, 0.34),
            max(depth * 0.15 * thickness_scale, 0.18),
        )
        primitives.append(
            _feature_subdivision_box(
                component,
                center=(x, component.center[1] + height * 0.70, component.center[2] + depth * 0.08),
                extents=tower_extents,
                corner_radii=_soft_corner_radii(tower_extents, 0.16),
                feature_kind="silhouette_tower",
                tags=[
                    "surface_detail",
                    "silhouette_detail",
                    "silhouette_motif",
                    "silhouette_motif_tower",
                    "tower",
                    "subdivision_silhouette_tower",
                    f"tower_{index}",
                ],
                corner_segments=3,
            )
        )
        primitives.append(
            _feature_revolved_profile(
                component,
                center=(x, component.center[1] + height * 1.06, component.center[2] + depth * 0.08),
                axis="y",
                profile_points=[
                    (-max(height * 0.16 * depth_scale, 0.10), max(min(width, depth) * 0.035 * thickness_scale, 0.09)),
                    (0.0, max(min(width, depth) * 0.028 * thickness_scale, 0.07)),
                    (max(height * 0.16 * depth_scale, 0.10), max(min(width, depth) * 0.012 * thickness_scale, 0.035)),
                ],
                feature_kind="silhouette_tower",
                tags=[
                    "surface_detail",
                    "silhouette_detail",
                    "silhouette_motif",
                    "silhouette_motif_tower",
                    "antenna",
                    "lathed_tower_mast",
                    f"tower_mast_{index}",
                ],
            )
        )
    return primitives


def silhouette_outrigger_features(
    component: BlueprintComponent, *, count: int, depth_scale: float, thickness_scale: float
) -> list[ShapePrimitive]:
    """Create side outriggers and foot pads that widen the readable stance."""
    width, height, depth = component.extents
    count = max(1, count)
    rows = min(2, count)
    primitives: list[ShapePrimitive] = []
    for index in range(rows):
        z = component.center[2] + (index - (rows - 1) / 2.0) * depth * 0.44
        for side, sign in (("left", -1.0), ("right", 1.0)):
            x = component.center[0] + sign * width * 0.66
            outrigger_extents = (
                max(width * 0.36 * thickness_scale, 0.28),
                max(height * 0.16, 0.18),
                max(depth * 0.20 * depth_scale, 0.20),
            )
            primitives.append(
                _feature_subdivision_box(
                    component,
                    center=(x, component.center[1] - height * 0.34, z),
                    extents=outrigger_extents,
                    corner_radii=_soft_corner_radii(outrigger_extents, 0.20),
                    feature_kind="silhouette_outrigger",
                    tags=[
                        "surface_detail",
                        "silhouette_detail",
                        "silhouette_motif",
                        "silhouette_motif_outrigger",
                        "outrigger",
                        "subdivision_silhouette_outrigger",
                        side,
                        f"outrigger_{index}",
                    ],
                    corner_segments=3,
                )
            )
    return primitives


def silhouette_blade_features(
    component: BlueprintComponent, *, count: int, depth_scale: float, thickness_scale: float
) -> list[ShapePrimitive]:
    """Create forward blade/tool-head silhouettes."""
    width, height, depth = component.extents
    count = max(1, count)
    spacing = width * 0.26 / max(1, count - 1) if count > 1 else 0.0
    start_x = component.center[0] - spacing * (count - 1) / 2.0
    primitives: list[ShapePrimitive] = []
    for index in range(count):
        blade_w = max(width * 0.16 * thickness_scale, 0.20)
        blade_h = max(height * 0.74, 0.32)
        blade_d = max(depth * 0.72 * depth_scale, 0.34)
        primitives.append(
            _feature_extruded_profile(
                component,
                center=(start_x + spacing * index, component.center[1], component.center[2] + depth * 0.86),
                profile_polygon=[
                    (-blade_w * 0.50, -blade_h * 0.50),
                    (blade_w * 0.50, -blade_h * 0.42),
                    (blade_w * 0.30, blade_h * 0.34),
                    (0.0, blade_h * 0.50),
                    (-blade_w * 0.30, blade_h * 0.34),
                ],
                extrude_height=blade_d,
                axis="z",
                feature_kind="silhouette_blade",
                tags=[
                    "surface_detail",
                    "silhouette_detail",
                    "silhouette_motif",
                    "silhouette_motif_blade",
                    "blade",
                    "extruded_silhouette_blade",
                    f"blade_{index}",
                ],
                rounding=0.03,
            )
        )
    return primitives


def silhouette_handle_features(
    component: BlueprintComponent, *, depth_scale: float, thickness_scale: float
) -> list[ShapePrimitive]:
    """Create a large silhouette handle with anchored mounts."""
    width, height, depth = component.extents
    radius = max(min(width, height) * 0.045 * thickness_scale, 0.14)
    bar_width = max(width * 0.72, 0.54)
    mount_w = max(width * 0.10 * thickness_scale, 0.18)
    mount_h = max(height * 0.28, 0.22)
    mount_d = max(depth * 0.32 * depth_scale, 0.20)
    cx, cy, cz = component.center
    return [
        _feature_swept_profile(
            component,
            center=(cx, cy + height * 0.45, cz + depth * 0.10),
            cross_section=_round_cross_section(radius),
            sweep_path=[
                (-bar_width * 0.50, 0.0, 0.0),
                (-bar_width * 0.35, height * 0.13, depth * 0.05),
                (bar_width * 0.35, height * 0.13, depth * 0.05),
                (bar_width * 0.50, 0.0, 0.0),
            ],
            feature_kind="silhouette_handle",
            tags=[
                "surface_detail",
                "silhouette_detail",
                "silhouette_motif",
                "silhouette_motif_handle",
                "handle",
                "grab_arc",
                "swept_silhouette_handle",
            ],
        ),
        _feature_extruded_profile(
            component,
            center=(cx - bar_width * 0.46, cy + height * 0.44, cz + depth * 0.14),
            profile_polygon=_chamfered_rectangle_polygon(mount_w, mount_h, mount_w * 0.20),
            extrude_height=mount_d,
            axis="z",
            feature_kind="silhouette_handle",
            tags=[
                "surface_detail",
                "silhouette_detail",
                "silhouette_motif",
                "silhouette_motif_handle",
                "handle",
                "left_mount",
                "extruded_handle_mount",
            ],
            rounding=0.05,
        ),
        _feature_extruded_profile(
            component,
            center=(cx + bar_width * 0.46, cy + height * 0.44, cz + depth * 0.14),
            profile_polygon=_chamfered_rectangle_polygon(mount_w, mount_h, mount_w * 0.20),
            extrude_height=mount_d,
            axis="z",
            feature_kind="silhouette_handle",
            tags=[
                "surface_detail",
                "silhouette_detail",
                "silhouette_motif",
                "silhouette_motif_handle",
                "handle",
                "right_mount",
                "extruded_handle_mount",
            ],
            rounding=0.05,
        ),
    ]


def silhouette_guard_cowl_features(
    component: BlueprintComponent, *, depth_scale: float, thickness_scale: float
) -> list[ShapePrimitive]:
    """Create a protective raised cowl around the upper front silhouette."""
    width, height, depth = component.extents
    cx, cy, cz = component.center
    cowl_h = max(height * 0.13 * thickness_scale, 0.18)
    cowl_d = max(depth * 0.34 * depth_scale, 0.22)
    side_w = max(width * 0.060 * thickness_scale, 0.16)
    side_h = max(height * 0.74, 0.30)
    return [
        _feature_extruded_profile(
            component,
            center=(cx, cy + height * 0.44, cz + depth * 0.58),
            profile_polygon=_chamfered_rectangle_polygon(max(width * 0.82, 0.42), cowl_h, cowl_h * 0.30),
            extrude_height=cowl_d,
            axis="z",
            feature_kind="silhouette_guard_cowl",
            tags=[
                "surface_detail",
                "silhouette_detail",
                "silhouette_motif",
                "silhouette_motif_guard_cowl",
                "guard_cowl",
                "top_front",
                "extruded_guard_cowl",
            ],
            rounding=0.07,
        ),
        _feature_extruded_profile(
            component,
            center=(cx - width * 0.43, cy, cz + depth * 0.58),
            profile_polygon=_chamfered_rectangle_polygon(side_w, side_h, side_w * 0.30),
            extrude_height=cowl_d,
            axis="z",
            feature_kind="silhouette_guard_cowl",
            tags=[
                "surface_detail",
                "silhouette_detail",
                "silhouette_motif",
                "silhouette_motif_guard_cowl",
                "guard_cowl",
                "left",
                "extruded_guard_cowl",
            ],
            rounding=0.06,
        ),
        _feature_extruded_profile(
            component,
            center=(cx + width * 0.43, cy, cz + depth * 0.58),
            profile_polygon=_chamfered_rectangle_polygon(side_w, side_h, side_w * 0.30),
            extrude_height=cowl_d,
            axis="z",
            feature_kind="silhouette_guard_cowl",
            tags=[
                "surface_detail",
                "silhouette_detail",
                "silhouette_motif",
                "silhouette_motif_guard_cowl",
                "guard_cowl",
                "right",
                "extruded_guard_cowl",
            ],
            rounding=0.06,
        ),
    ]
