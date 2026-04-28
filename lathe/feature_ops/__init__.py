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
