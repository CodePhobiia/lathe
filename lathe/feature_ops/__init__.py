"""Feature primitive builders used by the hard-surface feature grammar."""

from __future__ import annotations

from collections.abc import Iterable

from ..assembly_kernel import BlueprintComponent
from ..shape_ir import ShapePrimitive


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
        _feature_box(
            component,
            center=(cx, cy + height * 0.48, cz + depth * 0.42),
            extents=(width * 0.82, ty, tz),
            feature_kind="edge_break",
            tags=["top", "front"],
            rounding=rounding,
        ),
        _feature_box(
            component,
            center=(cx, cy + height * 0.48, cz - depth * 0.42),
            extents=(width * 0.82, ty, tz),
            feature_kind="edge_break",
            tags=["top", "rear"],
            rounding=rounding,
        ),
        _feature_box(
            component,
            center=(cx - width * 0.42, cy, cz),
            extents=(tx, height * 0.78, depth * 0.78),
            feature_kind="edge_break",
            tags=["left"],
            rounding=rounding,
        ),
        _feature_box(
            component,
            center=(cx + width * 0.42, cy, cz),
            extents=(tx, height * 0.78, depth * 0.78),
            feature_kind="edge_break",
            tags=["right"],
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
        _feature_box(
            component,
            center=(cx, cy, cz + depth * 0.40),
            extents=(width * 0.88, band_h, band_d),
            feature_kind="trim_band",
            tags=["front"],
        ),
        _feature_box(
            component,
            center=(cx, cy, cz - depth * 0.40),
            extents=(width * 0.88, band_h, band_d),
            feature_kind="trim_band",
            tags=["rear"],
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
        _feature_box(
            component,
            center=(cx, cy + half_h - lip / 2.0, cz + depth * 0.34),
            extents=(width * 0.86, lip, face_depth),
            feature_kind="frame_lip",
            tags=["top"],
        ),
        _feature_box(
            component,
            center=(cx, cy - half_h + lip / 2.0, cz + depth * 0.34),
            extents=(width * 0.86, lip, face_depth),
            feature_kind="frame_lip",
            tags=["bottom"],
        ),
        _feature_box(
            component,
            center=(cx - half_w + lip / 2.0, cy, cz + depth * 0.34),
            extents=(lip, height * 0.84, face_depth),
            feature_kind="frame_lip",
            tags=["left"],
        ),
        _feature_box(
            component,
            center=(cx + half_w - lip / 2.0, cy, cz + depth * 0.34),
            extents=(lip, height * 0.84, face_depth),
            feature_kind="frame_lip",
            tags=["right"],
        ),
    ]


def inset_panel_features(
    component: BlueprintComponent, *, depth_scale: float, thickness_scale: float
) -> list[ShapePrimitive]:
    """Create a subtractive inset panel feature."""
    width, height, depth = component.extents
    return [
        _feature_box(
            component,
            center=(component.center[0], component.center[1], component.center[2] + depth * 0.18),
            extents=(
                max(width * 0.80, 0.35),
                max(height * 0.72, 0.35),
                max(depth * 0.24 * depth_scale, 0.24),
            ),
            feature_kind="inset_panel",
            tags=["recess"],
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
            _feature_box(
                component,
                center=(cx, component.center[1], component.center[2] + depth * 0.28),
                extents=(rib_w, height * 0.74, rib_d),
                feature_kind="rib",
                tags=[f"rib_{index}"],
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
        primitives.append(
            _feature_box(
                component,
                center=(cx, component.center[1], component.center[2] + depth * 0.42),
                extents=(
                    max(width * 0.05 * size_scale, 0.28),
                    max(height * 0.08 * size_scale, 0.28),
                    max(depth * 0.10 * depth_scale, 0.28),
                ),
                feature_kind="fastener_strip",
                tags=["fastener"],
                rounding=0.08,
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
            _feature_box(
                component,
                center=(component.center[0], cy, component.center[2] + depth * 0.18),
                extents=(width * 0.92, slot_h, max(depth * 0.22 * depth_scale, 0.24)),
                feature_kind="vent_grille",
                tags=["slat"],
                blend_mode="subtract",
            )
        )
    return primitives


def support_bracket_features(component: BlueprintComponent, *, depth_scale: float) -> list[ShapePrimitive]:
    """Create brace and pad features for support components."""
    width, height, depth = component.extents
    return [
        _feature_box(
            component,
            center=(component.center[0], component.center[1] + height * 0.12, component.center[2]),
            extents=(
                max(width * 0.64, 0.35),
                max(height * 0.22, 0.35),
                max(depth * 1.10 * depth_scale, 0.35),
            ),
            feature_kind="support_bracket",
            tags=["brace"],
        ),
        _feature_box(
            component,
            center=(component.center[0], component.center[1] - height * 0.18, component.center[2]),
            extents=(max(width * 1.10, 0.35), max(height * 0.18, 0.35), max(depth * 0.58, 0.35)),
            feature_kind="support_bracket",
            tags=["pad"],
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
            _feature_box(
                component,
                center=(cx, y, z),
                extents=(max(width * 0.82, 0.45), step_height, step_depth),
                feature_kind="stair_step",
                tags=["architectural", "stair", "tread", f"step_{index}"],
                rounding=0.03,
            )
        )
        primitives.append(
            _feature_box(
                component,
                center=(cx, y + step_height * 0.48, z - step_depth * 0.46),
                extents=(max(width * 0.80, 0.42), max(step_height * 0.18, 0.08), max(step_depth * 0.20 * depth_scale, 0.08)),
                feature_kind="stair_step",
                tags=["architectural", "stair", "nosing", f"nosing_{index}"],
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
    return [
        _feature_box(
            component,
            center=(cx - width * 0.31, cy - height * 0.08, cz + depth * 0.38),
            extents=(pier_w, max(height * 0.72, 0.40), face_d),
            feature_kind="arch_frame",
            tags=["architectural", "arch", "left_pier"],
            rounding=0.04,
        ),
        _feature_box(
            component,
            center=(cx + width * 0.31, cy - height * 0.08, cz + depth * 0.38),
            extents=(pier_w, max(height * 0.72, 0.40), face_d),
            feature_kind="arch_frame",
            tags=["architectural", "arch", "right_pier"],
            rounding=0.04,
        ),
        _feature_box(
            component,
            center=(cx, cy + height * 0.29, cz + depth * 0.38),
            extents=(max(width * 0.72, 0.48), crown_h, face_d),
            feature_kind="arch_frame",
            tags=["architectural", "arch", "lintel"],
            rounding=0.05,
        ),
        _feature_cylinder(
            component,
            center=(cx, cy + height * 0.31, cz + depth * 0.38),
            radius=radius,
            height=face_d * 1.06,
            axis="z",
            feature_kind="arch_frame",
            tags=["architectural", "arch", "crown"],
            rounding=0.05,
        ),
        _feature_box(
            component,
            center=(cx, cy + height * 0.04, cz + depth * 0.40),
            extents=(max(width * 0.40, 0.30), max(height * 0.58, 0.32), face_d * 1.12),
            feature_kind="arch_cutout",
            tags=["architectural", "arch", "opening"],
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
            _feature_cylinder(
                component,
                center=(x, component.center[1], component.center[2] + depth * 0.36),
                radius=radius,
                height=max(height * 0.76, 0.38),
                axis="y",
                feature_kind="column_set",
                tags=["architectural", "column", "shaft", f"column_{index}"],
                rounding=0.06,
            )
        )
        for cap, sign in (("base", -1.0), ("capital", 1.0)):
            primitives.append(
                _feature_box(
                    component,
                    center=(x, component.center[1] + sign * height * 0.40, component.center[2] + depth * 0.36),
                    extents=(radius * 2.8, max(height * 0.055, 0.10), radius * 2.8),
                    feature_kind="column_set",
                    tags=["architectural", "column", cap, f"column_{index}_{cap}"],
                    rounding=0.04,
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
            _feature_cylinder(
                component,
                center=(component.center[0], y, component.center[2] + depth * 0.58),
                radius=radius,
                height=max(width * 0.78, 0.44),
                axis="x",
                feature_kind="pipe_run",
                tags=["mechanical", "pipe", "run", f"pipe_{index}"],
                rounding=0.04,
            )
        )
        for side, sign in (("left", -1.0), ("right", 1.0)):
            primitives.append(
                _feature_cylinder(
                    component,
                    center=(component.center[0] + sign * width * 0.40, y, component.center[2] + depth * 0.58),
                    radius=radius * 1.35,
                    height=max(width * 0.045, 0.10),
                    axis="x",
                    feature_kind="pipe_run",
                    tags=["mechanical", "pipe", "collar", side, f"pipe_collar_{index}"],
                    rounding=0.03,
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
                _feature_cylinder(
                    component,
                    center=(x, component.center[1] - height * 0.30, z),
                    radius=radius,
                    height=max(width * 0.055, 0.14),
                    axis="x",
                    feature_kind="wheel_pair",
                    tags=["vehicle", "wheel", side, f"wheel_{index}"],
                    rounding=0.06,
                )
            )
            primitives.append(
                _feature_cylinder(
                    component,
                    center=(x, component.center[1] - height * 0.30, z),
                    radius=radius * 0.42,
                    height=max(width * 0.070, 0.16),
                    axis="x",
                    feature_kind="wheel_pair",
                    tags=["vehicle", "wheel", "hub", side, f"wheel_hub_{index}"],
                    blend_mode="subtract",
                )
            )
    return primitives


def hull_keel_features(component: BlueprintComponent, *, depth_scale: float, thickness_scale: float) -> list[ShapePrimitive]:
    """Create a boat/aircraft-like hull keel and tapered side sponsons."""
    width, height, depth = component.extents
    cx, cy, cz = component.center
    return [
        _feature_box(
            component,
            center=(cx, cy - height * 0.42, cz),
            extents=(max(width * 0.22 * thickness_scale, 0.22), max(height * 0.26, 0.20), max(depth * 1.06 * depth_scale, 0.50)),
            feature_kind="hull_keel",
            tags=["vehicle", "boat", "hull", "keel"],
            rounding=0.08,
        ),
        _feature_box(
            component,
            center=(cx - width * 0.34, cy - height * 0.24, cz),
            extents=(max(width * 0.20 * thickness_scale, 0.20), max(height * 0.20, 0.18), max(depth * 0.84 * depth_scale, 0.42)),
            feature_kind="hull_keel",
            tags=["vehicle", "boat", "hull", "left_sponson"],
            rounding=0.07,
        ),
        _feature_box(
            component,
            center=(cx + width * 0.34, cy - height * 0.24, cz),
            extents=(max(width * 0.20 * thickness_scale, 0.20), max(height * 0.20, 0.18), max(depth * 0.84 * depth_scale, 0.42)),
            feature_kind="hull_keel",
            tags=["vehicle", "boat", "hull", "right_sponson"],
            rounding=0.07,
        ),
        _feature_box(
            component,
            center=(cx, cy - height * 0.18, cz + depth * 0.50),
            extents=(max(width * 0.62, 0.36), max(height * 0.12, 0.12), max(depth * 0.10 * depth_scale, 0.12)),
            feature_kind="hull_keel",
            tags=["vehicle", "boat", "hull", "bow_plate"],
            rounding=0.05,
        ),
    ]


def structural_frame_features(component: BlueprintComponent, *, depth_scale: float, thickness_scale: float) -> list[ShapePrimitive]:
    """Create an external structural cage/frame around a component."""
    width, height, depth = component.extents
    cx, cy, cz = component.center
    rail = max(min(width, height, depth) * 0.045 * thickness_scale, 0.12)
    return [
        _feature_box(
            component,
            center=(cx, cy + height * 0.46, cz + depth * 0.46),
            extents=(max(width * 0.98, 0.40), rail, rail * depth_scale),
            feature_kind="structural_frame",
            tags=["structure", "frame", "top_front"],
            rounding=0.03,
        ),
        _feature_box(
            component,
            center=(cx, cy - height * 0.46, cz + depth * 0.46),
            extents=(max(width * 0.98, 0.40), rail, rail * depth_scale),
            feature_kind="structural_frame",
            tags=["structure", "frame", "bottom_front"],
            rounding=0.03,
        ),
        _feature_box(
            component,
            center=(cx - width * 0.48, cy, cz + depth * 0.46),
            extents=(rail, max(height * 0.98, 0.40), rail * depth_scale),
            feature_kind="structural_frame",
            tags=["structure", "frame", "left_front"],
            rounding=0.03,
        ),
        _feature_box(
            component,
            center=(cx + width * 0.48, cy, cz + depth * 0.46),
            extents=(rail, max(height * 0.98, 0.40), rail * depth_scale),
            feature_kind="structural_frame",
            tags=["structure", "frame", "right_front"],
            rounding=0.03,
        ),
    ]


def recessed_handle_features(component: BlueprintComponent, *, depth_scale: float) -> list[ShapePrimitive]:
    """Create a recessed handle pocket with side mounts."""
    width, height, depth = component.extents
    side_w = max(width * 0.18, 0.24)
    mount_d = max(depth * 0.44 * depth_scale, 0.24)
    cx, cy, cz = component.center
    return [
        _feature_box(
            component,
            center=(cx, cy, cz),
            extents=(
                max(width * 0.84, 0.28),
                max(height * 0.62, 0.28),
                max(depth * 0.40 * depth_scale, 0.22),
            ),
            feature_kind="recessed_handle",
            tags=["pocket"],
            blend_mode="subtract",
        ),
        _feature_box(
            component,
            center=(cx - width * 0.26, cy, cz),
            extents=(side_w, height * 0.82, mount_d),
            feature_kind="recessed_handle",
            tags=["left_mount"],
        ),
        _feature_box(
            component,
            center=(cx + width * 0.26, cy, cz),
            extents=(side_w, height * 0.82, mount_d),
            feature_kind="recessed_handle",
            tags=["right_mount"],
        ),
    ]


def hinge_set_features(component: BlueprintComponent, *, depth_scale: float) -> list[ShapePrimitive]:
    """Create paired hinge barrel features."""
    _width, height, depth = component.extents
    barrel_r = max(depth * 0.22, 0.22)
    barrel_h = max(height * 0.82, 0.40)
    cx, cy, cz = component.center
    return [
        _feature_cylinder(
            component,
            center=(cx, cy + height * 0.18, cz),
            radius=barrel_r,
            height=barrel_h,
            axis=component.axis,
            feature_kind="hinge_set",
            tags=["upper"],
        ),
        _feature_cylinder(
            component,
            center=(cx, cy - height * 0.18, cz),
            radius=barrel_r,
            height=barrel_h,
            axis=component.axis,
            feature_kind="hinge_set",
            tags=["lower"],
        ),
    ]


def clasp_set_features(component: BlueprintComponent, *, depth_scale: float) -> list[ShapePrimitive]:
    """Create clasp strap and tongue features."""
    width, height, depth = component.extents
    cx, cy, cz = component.center
    return [
        _feature_box(
            component,
            center=(cx, cy + height * 0.16, cz + depth * 0.12),
            extents=(
                max(width * 0.62, 0.28),
                max(height * 0.18, 0.28),
                max(depth * 0.26 * depth_scale, 0.22),
            ),
            feature_kind="clasp_set",
            tags=["strap"],
        ),
        _feature_box(
            component,
            center=(cx, cy - height * 0.18, cz + depth * 0.18),
            extents=(
                max(width * 0.24, 0.24),
                max(height * 0.32, 0.24),
                max(depth * 0.22 * depth_scale, 0.22),
            ),
            feature_kind="clasp_set",
            tags=["tongue"],
        ),
    ]


def rotor_shroud_features(component: BlueprintComponent, *, scale: float) -> list[ShapePrimitive]:
    """Create a four-sided rotor shroud around a rotor pod."""
    width, _height, depth = component.extents
    radius = max(width, depth) * 0.70 * scale
    bar = max(radius * 0.10, 0.24)
    cx, cy, cz = component.center
    return [
        _feature_box(
            component,
            center=(cx, cy, cz + radius),
            extents=(radius * 1.55, bar, bar),
            feature_kind="rotor_shroud",
            tags=["front"],
        ),
        _feature_box(
            component,
            center=(cx, cy, cz - radius),
            extents=(radius * 1.55, bar, bar),
            feature_kind="rotor_shroud",
            tags=["rear"],
        ),
        _feature_box(
            component,
            center=(cx + radius, cy, cz),
            extents=(bar, bar, radius * 1.55),
            feature_kind="rotor_shroud",
            tags=["left"],
        ),
        _feature_box(
            component,
            center=(cx - radius, cy, cz),
            extents=(bar, bar, radius * 1.55),
            feature_kind="rotor_shroud",
            tags=["right"],
        ),
    ]


def screen_bezel_features(component: BlueprintComponent, *, depth_scale: float) -> list[ShapePrimitive]:
    """Create frame and cutout features for a screen bezel."""
    width, height, depth = component.extents
    return [
        *panel_frame_features(component, depth_scale=depth_scale * 1.1, thickness_scale=1.0),
        _feature_box(
            component,
            center=(component.center[0], component.center[1], component.center[2] + depth * 0.12),
            extents=(width * 0.78, height * 0.70, max(depth * 0.18 * depth_scale, 0.2)),
            feature_kind="screen_bezel",
            tags=["screen_window"],
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
            _feature_box(
                component,
                center=(x, cy, cz + depth * 0.30),
                extents=(line_w, height * 0.74, line_d),
                feature_kind="panel_seam",
                tags=["surface_detail", "cut_line", "vertical", f"seam_v_{index}"],
                blend_mode="subtract",
            )
        )
    horizontal_spacing = height * 0.58 / max(1, horizontal_count + 1)
    for index in range(horizontal_count):
        y = cy - height * 0.29 + horizontal_spacing * (index + 1)
        primitives.append(
            _feature_box(
                component,
                center=(cx, y, cz + depth * 0.31),
                extents=(width * 0.74, line_h, line_d),
                feature_kind="panel_seam",
                tags=["surface_detail", "cut_line", "horizontal", f"seam_h_{index}"],
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
            _feature_box(
                component,
                center=(start_x + spacing * index, component.center[1], component.center[2] + depth * 0.28),
                extents=(groove_w, height * 0.72, groove_d),
                feature_kind="groove_channel",
                tags=["surface_detail", "groove", f"channel_{index}"],
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
            _feature_box(
                component,
                center=(component.center[0], start_y + spacing * index, component.center[2] + depth * 0.43),
                extents=(width * 0.76, ridge_h, ridge_d),
                feature_kind="raised_ridge",
                tags=["surface_detail", "ridge", f"ridge_{index}"],
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
            _feature_box(
                component,
                center=(
                    component.center[0],
                    component.center[1],
                    component.center[2] + depth * (0.36 + index * 0.035),
                ),
                extents=(plate_w, plate_h, plate_d),
                feature_kind="layer_plate",
                tags=["surface_detail", "layered_piece", f"layer_{index}"],
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
        _feature_box(
            component,
            center=(cx + ox, cy + oy, cz + depth * 0.42),
            extents=(guard_w, guard_h, guard_d),
            feature_kind="corner_guard",
            tags=["surface_detail", "edge_break", corner],
            rounding=0.12,
        )
        for ox, oy, corner in offsets
    ]


def socket_point_features(
    component: BlueprintComponent, *, count: int, depth_scale: float
) -> list[ShapePrimitive]:
    """Create modular socket points as visible circular connection features."""
    width, height, depth = component.extents
    if count <= 0:
        return []
    radius = max(min(width, height) * 0.045, 0.18)
    socket_depth = max(depth * 0.34 * depth_scale, 0.24)
    columns = min(max(1, count), 4)
    rows = max(1, (count + columns - 1) // columns)
    primitives: list[ShapePrimitive] = []
    for index in range(count):
        col = index % columns
        row = index // columns
        x = component.center[0] + (col - (columns - 1) / 2.0) * width * 0.20
        y = component.center[1] + (row - (rows - 1) / 2.0) * height * 0.20
        primitives.append(
            _feature_cylinder(
                component,
                center=(x, y, component.center[2] + depth * 0.42),
                radius=radius,
                height=socket_depth,
                axis="z",
                feature_kind="socket_point",
                tags=["surface_detail", "socket", "connector", f"socket_{index}"],
                blend_mode="subtract",
            )
        )
    return primitives


def bolt_grid_features(component: BlueprintComponent, *, count: int, depth_scale: float) -> list[ShapePrimitive]:
    """Create raised bolt/rivet features in a compact grid."""
    width, height, depth = component.extents
    if count <= 0:
        return []
    radius = max(min(width, height) * 0.030, 0.14)
    bolt_depth = max(depth * 0.12 * depth_scale, 0.16)
    columns = min(max(1, count), 4)
    rows = max(1, (count + columns - 1) // columns)
    primitives: list[ShapePrimitive] = []
    for index in range(count):
        col = index % columns
        row = index // columns
        x = component.center[0] + (col - (columns - 1) / 2.0) * width * 0.24
        y = component.center[1] + (row - (rows - 1) / 2.0) * height * 0.24
        primitives.append(
            _feature_cylinder(
                component,
                center=(x, y, component.center[2] + depth * 0.46),
                radius=radius,
                height=bolt_depth,
                axis="z",
                feature_kind="bolt_grid",
                tags=["surface_detail", "greeble", "bolt", f"bolt_{index}"],
                rounding=0.04,
            )
        )
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
            _feature_box(
                component,
                center=(component.center[0], start_y + spacing * index, component.center[2] + depth * 0.47),
                extents=(width * 0.86, strip_h, strip_d),
                feature_kind="trim_strip",
                tags=["surface_detail", "trim", "linear_repeat", f"trim_{index}"],
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
        primitives.append(
            _feature_box(
                component,
                center=(x, y, component.center[2] + depth * 0.50),
                extents=(
                    max(width * 0.20, 0.24),
                    max(height * 0.18, 0.24),
                    max(depth * 0.18 * depth_scale, 0.18),
                ),
                feature_kind="outset_panel",
                tags=["surface_detail", "outset", "plate_island", f"outset_{index}"],
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
        primitives.append(
            _feature_box(
                component,
                center=(cx, cy, component.center[2] + depth * 0.52),
                extents=(
                    max(width * (0.060 if axis == "x" else 0.18), 0.16),
                    max(height * (0.18 if axis == "x" else 0.060), 0.16),
                    max(depth * 0.15 * depth_scale, 0.16),
                ),
                feature_kind="linear_detail_array",
                tags=["surface_detail", "repeated_detail", "linear_array", f"array_{index}"],
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
            _feature_cylinder(
                component,
                center=(x, y, component.center[2] + depth * 0.50),
                radius=radius,
                height=max(depth * 0.13 * depth_scale, 0.14),
                axis="z",
                feature_kind="radial_detail_array",
                tags=["surface_detail", "repeated_detail", "radial_array", f"radial_{index}"],
                rounding=0.03,
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
        primitives.append(
            _feature_box(
                component,
                center=(start_x + spacing * index, component.center[1], component.center[2] + depth * 0.54),
                extents=(rail_w, rail_h, rail_d),
                feature_kind="attachment_rail",
                tags=["surface_detail", "attachment_motif", "rail", "module_mount", f"rail_{index}"],
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
        primitives.append(
            _feature_box(
                component,
                center=(start_x + spacing * index, component.center[1] + height * 0.05, component.center[2] + depth * 0.62),
                extents=(fin_w, fin_h, fin_d),
                feature_kind="attachment_fin",
                tags=["surface_detail", "attachment_motif", "fin", "silhouette_detail", f"fin_{index}"],
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
        primitives.append(
            _feature_box(
                component,
                center=(start_x + spacing * index, component.center[1], component.center[2] + depth * 0.55),
                extents=(strap_w, height * 0.92, strap_d),
                feature_kind="attachment_strap",
                tags=["surface_detail", "attachment_motif", "strap", "retainer", f"strap_{index}"],
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
            _feature_cylinder(
                component,
                center=(component.center[0], start_y + spacing * index, component.center[2] + depth * 0.58),
                radius=radius,
                height=max(width * 0.76, 0.40),
                axis="x",
                feature_kind="attachment_cable",
                tags=["surface_detail", "attachment_motif", "cable", "routing", f"cable_{index}"],
                rounding=0.04,
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
    plate = _feature_box(
        component,
        center=(component.center[0], component.center[1], component.center[2] + depth * 0.48),
        extents=(width * 0.70, height * 0.62, max(depth * 0.12 * depth_scale, 0.18)),
        feature_kind="attachment_vent_stack",
        tags=["surface_detail", "attachment_motif", "vent_stack", "backing_plate"],
        rounding=0.06,
    )
    slot_h = max(height * 0.035, 0.14)
    spacing = height * 0.44 / max(1, count - 1) if count > 1 else 0.0
    start_y = component.center[1] - spacing * (count - 1) / 2.0
    primitives = [plate]
    for index in range(count):
        primitives.append(
            _feature_box(
                component,
                center=(component.center[0], start_y + spacing * index, component.center[2] + depth * 0.56),
                extents=(width * 0.58, slot_h, max(depth * 0.24 * depth_scale, 0.18)),
                feature_kind="attachment_vent_stack",
                tags=["surface_detail", "attachment_motif", "vent_stack", "vent_cut", f"vent_{index}"],
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
        _feature_cylinder(
            component,
            center=(cx, cy, cz + depth * 0.64),
            radius=radius,
            height=bar_width,
            axis="x",
            feature_kind="attachment_handle_bar",
            tags=["surface_detail", "attachment_motif", "handle", "grab_bar"],
            rounding=0.06,
        ),
        _feature_box(
            component,
            center=(cx - bar_width * 0.48, cy, cz + depth * 0.54),
            extents=(mount_w, mount_h, mount_d),
            feature_kind="attachment_handle_bar",
            tags=["surface_detail", "attachment_motif", "handle", "left_mount"],
            rounding=0.05,
        ),
        _feature_box(
            component,
            center=(cx + bar_width * 0.48, cy, cz + depth * 0.54),
            extents=(mount_w, mount_h, mount_d),
            feature_kind="attachment_handle_bar",
            tags=["surface_detail", "attachment_motif", "handle", "right_mount"],
            rounding=0.05,
        ),
    ]


def guard_bar_attachment_features(
    component: BlueprintComponent, *, depth_scale: float, thickness_scale: float
) -> list[ShapePrimitive]:
    """Create protective guard bars on exposed component edges."""
    width, height, depth = component.extents
    bar = max(min(width, height) * 0.045 * thickness_scale, 0.16)
    guard_d = max(depth * 0.28 * depth_scale, 0.20)
    cx, cy, cz = component.center
    return [
        _feature_box(
            component,
            center=(cx - width * 0.43, cy, cz + depth * 0.58),
            extents=(bar, height * 0.86, guard_d),
            feature_kind="attachment_guard_bar",
            tags=["surface_detail", "attachment_motif", "guard", "left"],
            rounding=0.05,
        ),
        _feature_box(
            component,
            center=(cx + width * 0.43, cy, cz + depth * 0.58),
            extents=(bar, height * 0.86, guard_d),
            feature_kind="attachment_guard_bar",
            tags=["surface_detail", "attachment_motif", "guard", "right"],
            rounding=0.05,
        ),
        _feature_box(
            component,
            center=(cx, cy + height * 0.43, cz + depth * 0.58),
            extents=(width * 0.86, bar, guard_d),
            feature_kind="attachment_guard_bar",
            tags=["surface_detail", "attachment_motif", "guard", "top"],
            rounding=0.05,
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
        primitives.append(
            _feature_box(
                component,
                center=(x, component.center[1], component.center[2] + depth * 0.62),
                extents=(
                    max(width * 0.16 * thickness_scale, 0.26),
                    max(height * 0.18 * thickness_scale, 0.26),
                    max(depth * 0.32 * depth_scale, 0.24),
                ),
                feature_kind="module_sensor_pod",
                tags=["surface_detail", "module_category", "sensor_pod", "swappable_module", f"module_{index}"],
                rounding=0.12,
            )
        )
        primitives.append(
            _feature_cylinder(
                component,
                center=(x, component.center[1], component.center[2] + depth * 0.81),
                radius=max(min(width, height) * 0.045, 0.14),
                height=max(depth * 0.14 * depth_scale, 0.12),
                axis="z",
                feature_kind="module_sensor_pod",
                tags=["surface_detail", "module_category", "sensor_pod", "lens", f"module_{index}"],
                rounding=0.04,
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
        primitives.append(
            _feature_cylinder(
                component,
                center=(component.center[0], y, component.center[2] + depth * 0.62),
                radius=max(min(width, height) * 0.050, 0.16),
                height=max(width * 0.58, 0.42),
                axis="x",
                feature_kind="module_power_cell",
                tags=["surface_detail", "module_category", "power_cell", "swappable_module", f"cell_{index}"],
                rounding=0.05,
            )
        )
        primitives.append(
            _feature_box(
                component,
                center=(component.center[0], y, component.center[2] + depth * 0.45),
                extents=(
                    max(width * 0.66, 0.42),
                    max(height * 0.030, 0.12),
                    max(depth * 0.12 * depth_scale, 0.12),
                ),
                feature_kind="module_power_cell",
                tags=["surface_detail", "module_category", "power_cell", "retainer", f"cell_clip_{index}"],
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
        primitives.append(
            _feature_cylinder(
                component,
                center=(x, component.center[1], component.center[2] + depth * 0.82),
                radius=max(min(width, height) * 0.045, 0.15),
                height=max(depth * 0.68 * depth_scale, 0.38),
                axis="z",
                feature_kind="module_barrel",
                tags=["surface_detail", "module_category", "barrel", "swappable_module", f"barrel_{index}"],
                rounding=0.04,
            )
        )
        primitives.append(
            _feature_cylinder(
                component,
                center=(x, component.center[1], component.center[2] + depth * 1.14),
                radius=max(min(width, height) * 0.030, 0.10),
                height=max(depth * 0.22 * depth_scale, 0.16),
                axis="z",
                feature_kind="module_barrel",
                tags=["surface_detail", "module_category", "barrel", "muzzle", f"barrel_tip_{index}"],
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
        primitives.append(
            _feature_box(
                component,
                center=(start_x + spacing * index, component.center[1] + height * 0.03, component.center[2] + depth * 0.86),
                extents=(
                    max(width * 0.10 * thickness_scale, 0.18),
                    max(height * 0.76, 0.36),
                    max(depth * 0.52 * depth_scale, 0.28),
                ),
                feature_kind="module_blade",
                tags=["surface_detail", "module_category", "blade", "swappable_module", f"blade_{index}"],
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
            primitives.append(
                _feature_box(
                    component,
                    center=(component.center[0] + sign * width * 0.56, y, component.center[2] + depth * 0.30),
                    extents=(
                        max(width * 0.42 * thickness_scale, 0.28),
                        max(height * 0.070, 0.16),
                        max(depth * 0.46 * depth_scale, 0.24),
                    ),
                    feature_kind="module_wing",
                    tags=["surface_detail", "module_category", "wing", "silhouette_module", side, f"wing_{index}"],
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
        primitives.append(
            _feature_box(
                component,
                center=(x, component.center[1] - height * 0.58, z),
                extents=(
                    max(width * 0.070, 0.16),
                    max(height * 0.58, 0.34),
                    max(depth * 0.070 * depth_scale, 0.16),
                ),
                feature_kind="module_leg",
                tags=["surface_detail", "module_category", "leg", "support_module", f"leg_{index}"],
                rounding=0.05,
            )
        )
        primitives.append(
            _feature_box(
                component,
                center=(x, component.center[1] - height * 0.88, z),
                extents=(max(width * 0.22, 0.24), max(height * 0.050, 0.14), max(depth * 0.22, 0.24)),
                feature_kind="module_leg",
                tags=["surface_detail", "module_category", "leg", "foot_pad", f"leg_foot_{index}"],
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
        primitives.append(
            _feature_box(
                component,
                center=(component.center[0], start_y + spacing * index, component.center[2] + depth * 0.60),
                extents=(
                    max(width * 0.72, 0.38),
                    max(height * 0.18 * thickness_scale, 0.22),
                    max(depth * 0.28 * depth_scale, 0.20),
                ),
                feature_kind="module_shield_plate",
                tags=["surface_detail", "module_category", "shield_plate", "armor_module", f"shield_{index}"],
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
            _feature_cylinder(
                component,
                center=(x, component.center[1] + height * 0.55, component.center[2] + depth * 0.18),
                radius=max(min(width, depth) * 0.018, 0.07),
                height=max(height * 0.72 * depth_scale, 0.36),
                axis="y",
                feature_kind="module_antenna",
                tags=["surface_detail", "module_category", "antenna", "signal_module", f"antenna_{index}"],
                rounding=0.03,
            )
        )
        primitives.append(
            _feature_cylinder(
                component,
                center=(x, component.center[1] + height * 0.92, component.center[2] + depth * 0.18),
                radius=max(min(width, depth) * 0.034, 0.10),
                height=max(height * 0.050, 0.10),
                axis="y",
                feature_kind="module_antenna",
                tags=["surface_detail", "module_category", "antenna", "cap", f"antenna_cap_{index}"],
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
        primitives.append(
            _feature_box(
                component,
                center=(start_x + spacing * index, component.center[1] + height * 0.58, component.center[2]),
                extents=(
                    max(width * 0.08 * thickness_scale, 0.18),
                    max(height * 0.42 * depth_scale, 0.26),
                    max(depth * 0.22, 0.22),
                ),
                feature_kind="silhouette_spine",
                tags=[
                    "surface_detail",
                    "silhouette_detail",
                    "silhouette_motif",
                    "silhouette_motif_spine",
                    "spine",
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
            primitives.append(
                _feature_box(
                    component,
                    center=(component.center[0] + sign * width * 0.68, y, component.center[2] + depth * 0.02),
                    extents=(
                        max(width * 0.56 * thickness_scale, 0.34),
                        max(height * 0.075, 0.14),
                        max(depth * 0.54 * depth_scale, 0.26),
                    ),
                    feature_kind="silhouette_wing",
                    tags=[
                        "surface_detail",
                        "silhouette_detail",
                        "silhouette_motif",
                        "silhouette_motif_wing",
                        "wing",
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
        primitives.append(
            _feature_box(
                component,
                center=(x, component.center[1] + height * 0.70, component.center[2] + depth * 0.08),
                extents=(
                    max(width * 0.12 * thickness_scale, 0.22),
                    max(height * 0.64 * depth_scale, 0.34),
                    max(depth * 0.15 * thickness_scale, 0.18),
                ),
                feature_kind="silhouette_tower",
                tags=[
                    "surface_detail",
                    "silhouette_detail",
                    "silhouette_motif",
                    "silhouette_motif_tower",
                    "tower",
                    f"tower_{index}",
                ],
                rounding=0.05,
            )
        )
        primitives.append(
            _feature_cylinder(
                component,
                center=(x, component.center[1] + height * 1.06, component.center[2] + depth * 0.08),
                radius=max(min(width, depth) * 0.035 * thickness_scale, 0.09),
                height=max(height * 0.32 * depth_scale, 0.20),
                axis="y",
                feature_kind="silhouette_tower",
                tags=[
                    "surface_detail",
                    "silhouette_detail",
                    "silhouette_motif",
                    "silhouette_motif_tower",
                    "antenna",
                    f"tower_mast_{index}",
                ],
                rounding=0.03,
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
            primitives.append(
                _feature_box(
                    component,
                    center=(x, component.center[1] - height * 0.34, z),
                    extents=(
                        max(width * 0.36 * thickness_scale, 0.28),
                        max(height * 0.16, 0.18),
                        max(depth * 0.20 * depth_scale, 0.20),
                    ),
                    feature_kind="silhouette_outrigger",
                    tags=[
                        "surface_detail",
                        "silhouette_detail",
                        "silhouette_motif",
                        "silhouette_motif_outrigger",
                        "outrigger",
                        side,
                        f"outrigger_{index}",
                    ],
                    rounding=0.06,
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
        primitives.append(
            _feature_box(
                component,
                center=(start_x + spacing * index, component.center[1], component.center[2] + depth * 0.86),
                extents=(
                    max(width * 0.16 * thickness_scale, 0.20),
                    max(height * 0.74, 0.32),
                    max(depth * 0.72 * depth_scale, 0.34),
                ),
                feature_kind="silhouette_blade",
                tags=[
                    "surface_detail",
                    "silhouette_detail",
                    "silhouette_motif",
                    "silhouette_motif_blade",
                    "blade",
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
        _feature_cylinder(
            component,
            center=(cx, cy + height * 0.58, cz + depth * 0.14),
            radius=radius,
            height=bar_width,
            axis="x",
            feature_kind="silhouette_handle",
            tags=[
                "surface_detail",
                "silhouette_detail",
                "silhouette_motif",
                "silhouette_motif_handle",
                "handle",
                "grab_arc",
            ],
            rounding=0.06,
        ),
        _feature_box(
            component,
            center=(cx - bar_width * 0.46, cy + height * 0.44, cz + depth * 0.14),
            extents=(mount_w, mount_h, mount_d),
            feature_kind="silhouette_handle",
            tags=[
                "surface_detail",
                "silhouette_detail",
                "silhouette_motif",
                "silhouette_motif_handle",
                "handle",
                "left_mount",
            ],
            rounding=0.05,
        ),
        _feature_box(
            component,
            center=(cx + bar_width * 0.46, cy + height * 0.44, cz + depth * 0.14),
            extents=(mount_w, mount_h, mount_d),
            feature_kind="silhouette_handle",
            tags=[
                "surface_detail",
                "silhouette_detail",
                "silhouette_motif",
                "silhouette_motif_handle",
                "handle",
                "right_mount",
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
    return [
        _feature_box(
            component,
            center=(cx, cy + height * 0.44, cz + depth * 0.58),
            extents=(max(width * 0.82, 0.42), cowl_h, cowl_d),
            feature_kind="silhouette_guard_cowl",
            tags=[
                "surface_detail",
                "silhouette_detail",
                "silhouette_motif",
                "silhouette_motif_guard_cowl",
                "guard_cowl",
                "top_front",
            ],
            rounding=0.07,
        ),
        _feature_box(
            component,
            center=(cx - width * 0.43, cy, cz + depth * 0.58),
            extents=(max(width * 0.060 * thickness_scale, 0.16), max(height * 0.74, 0.30), cowl_d),
            feature_kind="silhouette_guard_cowl",
            tags=[
                "surface_detail",
                "silhouette_detail",
                "silhouette_motif",
                "silhouette_motif_guard_cowl",
                "guard_cowl",
                "left",
            ],
            rounding=0.06,
        ),
        _feature_box(
            component,
            center=(cx + width * 0.43, cy, cz + depth * 0.58),
            extents=(max(width * 0.060 * thickness_scale, 0.16), max(height * 0.74, 0.30), cowl_d),
            feature_kind="silhouette_guard_cowl",
            tags=[
                "surface_detail",
                "silhouette_detail",
                "silhouette_motif",
                "silhouette_motif_guard_cowl",
                "guard_cowl",
                "right",
            ],
            rounding=0.06,
        ),
    ]
