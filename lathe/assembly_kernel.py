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


def _shell_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    return [
        _box(component.part, component),
        _box(
            component.part,
            component,
            center=(component.center[0], component.center[1] + height * 0.06, component.center[2]),
            extents=(width * 0.88, height * 0.78, depth * 0.88),
            tags=[*list(component.tags), "liner"],
        ),
    ]


def _panel_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    return [_box(component.part, component)]


def _frame_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    thickness = max(min(width, height) * 0.10, depth * 0.9)
    half_w = width / 2.0
    half_h = height / 2.0
    cz = component.center[2]
    return [
        _box(
            component.part,
            component,
            center=(component.center[0], component.center[1] + half_h - thickness / 2.0, cz),
            extents=(width, thickness, depth),
        ),
        _box(
            component.part,
            component,
            center=(component.center[0], component.center[1] - half_h + thickness / 2.0, cz),
            extents=(width, thickness, depth),
        ),
        _box(
            component.part,
            component,
            center=(component.center[0] - half_w + thickness / 2.0, component.center[1], cz),
            extents=(thickness, max(thickness, height - 2.0 * thickness), depth),
        ),
        _box(
            component.part,
            component,
            center=(component.center[0] + half_w - thickness / 2.0, component.center[1], cz),
            extents=(thickness, max(thickness, height - 2.0 * thickness), depth),
        ),
    ]


def _lid_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    return [
        _box(component.part, component),
        _box(
            component.part,
            component,
            center=(component.center[0], component.center[1] + height * 0.18, component.center[2]),
            extents=(width * 0.74, height * 0.52, depth * 0.84),
            tags=[*list(component.tags), "crest"],
        ),
    ]


def _door_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    return [
        _box(component.part, component),
        _box(
            component.part,
            component,
            center=(component.center[0], component.center[1], component.center[2] + depth * 0.18),
            extents=(width * 0.88, height * 0.90, depth * 0.30),
            tags=[*list(component.tags), "face"],
        ),
    ]


def _hinge_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    radius = component.radius if component.radius is not None else max(width, depth) * 0.42
    barrel_height = component.height if component.height is not None else max(width, height, depth)
    return [
        _cylinder(
            component.part,
            component,
            radius=radius,
            height=barrel_height,
            axis=component.axis,
            tags=[*list(component.tags), "barrel"],
        ),
        _box(
            component.part,
            component,
            center=(component.center[0], component.center[1], component.center[2] - depth * 0.20),
            extents=(width, height * 0.45, depth * 0.55),
            tags=[*list(component.tags), "mount"],
        ),
    ]


def _latch_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    return [_box(component.part, component)]


def _lock_plate_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    return [
        _box(component.part, component),
        _box(
            component.part,
            component,
            center=(
                component.center[0],
                component.center[1] - height * 0.18,
                component.center[2] + depth * 0.08,
            ),
            extents=(width * 0.36, height * 0.55, depth * 0.40),
            tags=[*list(component.tags), "latch_body"],
        ),
    ]


def _handle_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    radius = component.radius if component.radius is not None else max(height, depth) * 0.36
    handle_height = component.height if component.height is not None else max(width, height, depth) * 0.85
    return [
        _cylinder(
            component.part,
            component,
            radius=radius,
            height=handle_height,
            axis=component.axis,
            tags=[*list(component.tags), "grip"],
        )
    ]


def _foot_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    return [
        _box(component.part, component),
        _box(
            component.part,
            component,
            center=(component.center[0], component.center[1] - height * 0.20, component.center[2]),
            extents=(width * 1.14, height * 0.35, depth * 1.08),
            tags=[*list(component.tags), "pad"],
        ),
    ]


def _stand_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    return [
        _box(component.part, component),
        _box(
            component.part,
            component,
            center=(component.center[0], component.center[1] - height * 0.42, component.center[2]),
            extents=(width * 1.28, height * 0.22, depth * 1.18),
            tags=[*list(component.tags), "base"],
        ),
    ]


def _bracket_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    return [
        _box(
            component.part,
            component,
            center=(component.center[0], component.center[1], component.center[2] - depth * 0.16),
            extents=(width, height * 0.35, depth),
        ),
        _box(
            component.part,
            component,
            center=(component.center[0], component.center[1] - height * 0.18, component.center[2]),
            extents=(width * 0.35, height, depth),
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
            _box(
                component.part,
                component,
                center=(component.center[0], cy, component.center[2]),
                extents=(width, slat_height, depth),
                tags=[*list(component.tags), "slat"],
            )
        )
    return primitives


def _rotor_arm_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    return [_box(component.part, component)]


def _rotor_pod_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    radius = component.radius if component.radius is not None else max(width, depth) * 0.45
    disc_height = component.height if component.height is not None else max(height * 0.40, 1.0)
    return [
        _cylinder(
            component.part,
            component,
            radius=radius,
            height=disc_height,
            axis=component.axis,
            tags=[*list(component.tags), "disc"],
        ),
        _cylinder(
            component.part,
            component,
            center=(component.center[0], component.center[1] - height * 0.26, component.center[2]),
            radius=radius * 0.34,
            height=max(height, disc_height * 2.4),
            axis=component.axis,
            tags=[*list(component.tags), "hub"],
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
            _box(
                component.part,
                component,
                center=(cx, segment_center_y, cz),
                extents=(segment_width, segment_height * 1.08, depth * 0.88),
                tags=[*list(component.tags), "blade_face", f"blade_segment_{index}"],
            )
        )
    primitives.extend(
        [
            _box(
                component.part,
                component,
                center=(cx, cy, cz + depth * 0.50),
                extents=(width * 0.15, height * 0.92, depth * 0.20),
                tags=[*list(component.tags), "feature", "edge_break", "central_ridge", "front"],
            ),
            _box(
                component.part,
                component,
                center=(cx, cy, cz - depth * 0.50),
                extents=(width * 0.15, height * 0.92, depth * 0.20),
                tags=[*list(component.tags), "feature", "edge_break", "central_ridge", "rear"],
            ),
            _box(
                component.part,
                component,
                center=(cx - width * 0.42, cy - height * 0.02, cz),
                extents=(width * 0.08, height * 0.92, depth * 1.04),
                tags=[*list(component.tags), "feature", "edge_break", "blade_edge", "left"],
            ),
            _box(
                component.part,
                component,
                center=(cx + width * 0.42, cy - height * 0.02, cz),
                extents=(width * 0.08, height * 0.92, depth * 1.04),
                tags=[*list(component.tags), "feature", "edge_break", "blade_edge", "right"],
            ),
            _box(
                component.part,
                component,
                center=(cx, cy - height * 0.50, cz),
                extents=(width * 0.92, max(height * 0.035, 0.75), depth * 1.12),
                tags=[*list(component.tags), "feature", "edge_break", "blade_base_shoulder"],
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
            _box(
                component.part,
                component,
                center=(cx, segment_center_y, cz),
                extents=(max(tip_width, width * 0.10), segment_height * 1.10, depth * (1.0 - 0.16 * t)),
                tags=[*list(component.tags), "feature", "edge_break", f"tip_facet_{index}"],
            )
        )
    primitives.extend(
        [
            _box(
                component.part,
                component,
                center=(cx, cy + height * 0.48, cz),
                extents=(width * 0.10, max(height * 0.10, 0.35), depth * 0.70),
                tags=[*list(component.tags), "feature", "edge_break", "point"],
            ),
            _box(
                component.part,
                component,
                center=(cx, cy - height * 0.44, cz),
                extents=(width * 0.72, max(height * 0.11, 0.35), depth * 1.06),
                tags=[*list(component.tags), "feature", "edge_break", "tip_shoulder"],
            ),
        ]
    )
    return primitives


def _fuller_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    cap_height = max(height * 0.030, 0.45)
    return [
        _box(
            component.part,
            component,
            center=(cx, cy, cz + depth * 0.34),
            extents=(width * 0.46, height * 0.94, depth * 0.22),
            tags=[*list(component.tags), "feature", "front", "fuller_channel"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy, cz - depth * 0.34),
            extents=(width * 0.46, height * 0.94, depth * 0.22),
            tags=[*list(component.tags), "feature", "rear", "fuller_channel"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.50, cz),
            extents=(width * 0.52, cap_height, depth * 0.34),
            tags=[*list(component.tags), "feature", "edge_break", "fuller_cap"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy - height * 0.50, cz),
            extents=(width * 0.52, cap_height, depth * 0.34),
            tags=[*list(component.tags), "feature", "edge_break", "fuller_base"],
        ),
    ]


def _guard_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    radius = component.radius if component.radius is not None else max(height, depth) * 0.42
    guard_height = component.height if component.height is not None else width
    cx, cy, cz = component.center
    return [
        _cylinder(
            component.part,
            component,
            radius=radius,
            height=guard_height,
            axis="x",
            tags=[*list(component.tags), "crossbar"],
        ),
        _cylinder(
            component.part,
            component,
            center=(cx - guard_height * 0.50, cy, cz),
            radius=radius * 1.18,
            height=height * 0.88,
            axis="y",
            tags=[*list(component.tags), "feature", "edge_break", "guard_cap", "left"],
        ),
        _cylinder(
            component.part,
            component,
            center=(cx + guard_height * 0.50, cy, cz),
            radius=radius * 1.18,
            height=height * 0.88,
            axis="y",
            tags=[*list(component.tags), "feature", "edge_break", "guard_cap", "right"],
        ),
        _box(
            component.part,
            component,
            extents=(width * 0.18, height * 1.35, depth * 1.10),
            tags=[*list(component.tags), "feature", "edge_break", "center_block"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.70, cz),
            extents=(width * 0.24, height * 0.18, depth * 1.18),
            tags=[*list(component.tags), "feature", "edge_break", "upper_collar"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy - height * 0.70, cz),
            extents=(width * 0.24, height * 0.18, depth * 1.18),
            tags=[*list(component.tags), "feature", "edge_break", "lower_collar"],
        ),
    ]


def _grip_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    radius = component.radius if component.radius is not None else max(width, depth) * 0.44
    grip_height = component.height if component.height is not None else height
    cx, cy, cz = component.center
    primitives = [
        _cylinder(
            component.part,
            component,
            radius=radius,
            height=grip_height,
            axis="y",
            tags=[*list(component.tags), "leather_core"],
        )
    ]
    for index, offset in enumerate((-0.42, -0.30, -0.18, -0.06, 0.06, 0.18, 0.30, 0.42)):
        primitives.append(
            _cylinder(
                component.part,
                component,
                center=(cx, cy + grip_height * offset, cz),
                radius=radius * (1.10 if index % 2 == 0 else 1.04),
                height=max(grip_height * 0.028, 0.50),
                axis="y",
                tags=[*list(component.tags), "feature", "wrap_ridge", f"wrap_{index}"],
            )
        )
    primitives.extend(
        [
            _cylinder(
                component.part,
                component,
                center=(cx, cy + grip_height * 0.50, cz),
                radius=radius * 1.16,
                height=max(grip_height * 0.060, 0.75),
                axis="y",
                tags=[*list(component.tags), "feature", "edge_break", "upper_grip_collar"],
            ),
            _cylinder(
                component.part,
                component,
                center=(cx, cy - grip_height * 0.50, cz),
                radius=radius * 1.16,
                height=max(grip_height * 0.060, 0.75),
                axis="y",
                tags=[*list(component.tags), "feature", "edge_break", "lower_grip_collar"],
            ),
        ]
    )
    return primitives


def _pommel_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    radius = component.radius if component.radius is not None else max(width, depth) * 0.50
    pommel_height = component.height if component.height is not None else height
    cx, cy, cz = component.center
    return [
        _cylinder(
            component.part,
            component,
            radius=radius,
            height=pommel_height,
            axis="y",
            tags=[*list(component.tags), "counterweight"],
        ),
        _cylinder(
            component.part,
            component,
            radius=radius * 0.68,
            height=max(pommel_height * 1.28, 0.8),
            axis="y",
            tags=[*list(component.tags), "feature", "edge_break", "pommel_cap"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy + pommel_height * 0.42, cz),
            extents=(radius * 1.55, max(pommel_height * 0.16, 0.5), radius * 1.55),
            tags=[*list(component.tags), "feature", "edge_break", "upper_pommel_bevel"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy - pommel_height * 0.42, cz),
            extents=(radius * 1.55, max(pommel_height * 0.16, 0.5), radius * 1.55),
            tags=[*list(component.tags), "feature", "edge_break", "lower_pommel_bevel"],
        ),
    ]


def _weapon_body_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    return [
        _box(component.part, component, tags=[*list(component.tags), "receiver_core"]),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.34, cz + depth * 0.12),
            extents=(width * 0.82, height * 0.22, depth * 0.72),
            tags=[*list(component.tags), "top_rail"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy - height * 0.34, cz - depth * 0.10),
            extents=(width * 0.62, height * 0.26, depth * 0.38),
            tags=[*list(component.tags), "lower_receiver"],
        ),
    ]


def _barrel_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    radius = component.radius if component.radius is not None else max(min(component.extents[0], component.extents[1]) * 0.45, 0.08)
    height = component.height if component.height is not None else max(component.extents)
    return [
        _cylinder(component.part, component, radius=radius, height=height, axis=component.axis, tags=[*list(component.tags), "barrel_tube"]),
        _cylinder(
            component.part,
            component,
            radius=radius * 1.30,
            height=max(height * 0.10, 0.08),
            axis=component.axis,
            center=(
                component.center[0],
                component.center[1],
                component.center[2] + height * 0.48 if component.axis == "z" else component.center[2],
            ),
            tags=[*list(component.tags), "muzzle_ring"],
        ),
        _box(
            component.part,
            component,
            center=(
                component.center[0],
                component.center[1] - radius * 1.20,
                component.center[2] - height * 0.10 if component.axis == "z" else component.center[2],
            ),
            extents=(radius * 1.0, radius * 0.55, height * 0.58 if component.axis == "z" else radius * 1.8),
            tags=[*list(component.tags), "underbarrel_rail"],
        ),
    ]


def _stock_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    return [
        _box(component.part, component, tags=[*list(component.tags), "stock_body"]),
        _box(
            component.part,
            component,
            center=(cx, cy - height * 0.18, cz - depth * 0.42),
            extents=(width * 1.18, height * 0.64, depth * 0.22),
            tags=[*list(component.tags), "butt_pad"],
        ),
    ]


def _magazine_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    return [
        _box(component.part, component, tags=[*list(component.tags), "magazine_body"]),
        _box(
            component.part,
            component,
            center=(component.center[0], component.center[1] - height * 0.48, component.center[2]),
            extents=(width * 1.08, max(height * 0.10, 0.06), depth * 1.08),
            tags=[*list(component.tags), "magazine_floorplate"],
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
        _box(component.part, component, tags=[*list(component.tags), "sight_mount"]),
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
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.22, cz),
            extents=(width * 1.36, max(height * 0.18, 0.06), depth),
            tags=[*list(component.tags), "trigger_guard"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy - height * 0.20, cz),
            extents=(width * 0.28, height * 0.72, depth * 0.58),
            tags=[*list(component.tags), "trigger_hook"],
        ),
    ]


def _tool_head_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    return [
        _box(component.part, component, tags=[*list(component.tags), "tool_head_mass"]),
        _box(
            component.part,
            component,
            center=(cx - width * 0.38, cy, cz),
            extents=(width * 0.30, height * 1.08, depth * 0.78),
            tags=[*list(component.tags), "left_edge"],
        ),
        _box(
            component.part,
            component,
            center=(cx + width * 0.38, cy, cz),
            extents=(width * 0.30, height * 1.08, depth * 0.78),
            tags=[*list(component.tags), "right_edge"],
        ),
    ]


def _plate_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    return [_box(component.part, component)]


def _hardpoint_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    pad_h = max(height * 0.34, 0.035)
    lug_w = max(width * 0.18, 0.035)
    rail_w = max(width * 0.12, 0.03)
    return [
        _box(component.part, component, tags=[*list(component.tags), "hardpoint_pad"]),
        _box(
            component.part,
            component,
            center=(cx - width * 0.34, cy + pad_h * 0.84, cz),
            extents=(lug_w, max(height * 0.72, 0.055), depth * 0.72),
            tags=[*list(component.tags), "left_lock_lug"],
        ),
        _box(
            component.part,
            component,
            center=(cx + width * 0.34, cy + pad_h * 0.84, cz),
            extents=(lug_w, max(height * 0.72, 0.055), depth * 0.72),
            tags=[*list(component.tags), "right_lock_lug"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.58, cz),
            extents=(rail_w, max(height * 0.40, 0.04), depth * 0.94),
            tags=[*list(component.tags), "center_alignment_rail"],
        ),
    ]


def _crew_bay_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    rim = max(min(width, depth) * 0.08, 0.04)
    return [
        _box(component.part, component, tags=[*list(component.tags), "crew_bay_volume"]),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.45, cz + depth * 0.36),
            extents=(width * 0.72, max(height * 0.18, 0.045), depth * 0.16),
            tags=[*list(component.tags), "forward_canopy"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.50, cz - depth * 0.30),
            extents=(width * 0.62, max(height * 0.16, 0.04), depth * 0.14),
            tags=[*list(component.tags), "rear_canopy"],
        ),
        _box(
            component.part,
            component,
            center=(cx - width * 0.50 + rim * 0.50, cy + height * 0.14, cz),
            extents=(rim, height * 0.72, depth),
            tags=[*list(component.tags), "left_bay_frame"],
        ),
        _box(
            component.part,
            component,
            center=(cx + width * 0.50 - rim * 0.50, cy + height * 0.14, cz),
            extents=(rim, height * 0.72, depth),
            tags=[*list(component.tags), "right_bay_frame"],
        ),
    ]


def _cargo_bay_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    door_t = max(height * 0.12, 0.04)
    return [
        _box(component.part, component, tags=[*list(component.tags), "cargo_bay_volume"]),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.44, cz + depth * 0.46),
            extents=(width * 0.82, door_t, depth * 0.10),
            tags=[*list(component.tags), "forward_bay_door"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy - height * 0.44, cz),
            extents=(width * 0.76, door_t, depth * 0.82),
            tags=[*list(component.tags), "underside_access_hatch"],
        ),
        _box(
            component.part,
            component,
            center=(cx - width * 0.38, cy, cz),
            extents=(width * 0.07, height * 0.82, depth * 0.86),
            tags=[*list(component.tags), "left_cargo_rail"],
        ),
        _box(
            component.part,
            component,
            center=(cx + width * 0.38, cy, cz),
            extents=(width * 0.07, height * 0.82, depth * 0.86),
            tags=[*list(component.tags), "right_cargo_rail"],
        ),
    ]


def _thruster_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    radius = component.radius if component.radius is not None else max(min(width, height) * 0.34, 0.045)
    nozzle_depth = component.height if component.height is not None else max(depth, 0.08)
    return [
        _cylinder(
            component.part,
            component,
            radius=radius,
            height=nozzle_depth,
            axis=component.axis,
            tags=[*list(component.tags), "thruster_nozzle"],
        ),
        _cylinder(
            component.part,
            component,
            center=(cx, cy, cz - depth * 0.32 if component.axis == "z" else cz),
            radius=radius * 1.30,
            height=max(nozzle_depth * 0.24, 0.04),
            axis=component.axis,
            tags=[*list(component.tags), "thrust_ring"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.38, cz),
            extents=(width * 0.82, max(height * 0.24, 0.04), depth * 0.46),
            tags=[*list(component.tags), "thruster_mount"],
        ),
    ]


def _antenna_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    radius = component.radius if component.radius is not None else max(min(width, depth) * 0.18, 0.025)
    mast_height = component.height if component.height is not None else max(height, 0.10)
    return [
        _cylinder(
            component.part,
            component,
            radius=radius,
            height=mast_height,
            axis="y",
            tags=[*list(component.tags), "antenna_mast"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy + mast_height * 0.48, cz),
            extents=(width, max(radius * 0.80, 0.02), depth * 0.38),
            tags=[*list(component.tags), "antenna_crossbar"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy - mast_height * 0.48, cz),
            extents=(width * 0.56, max(radius * 1.20, 0.025), depth * 0.56),
            tags=[*list(component.tags), "antenna_base_plate"],
        ),
    ]


def _stabilizer_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    return [
        _box(component.part, component, tags=[*list(component.tags), "stabilizer_plane"]),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.30, cz - depth * 0.24),
            extents=(width * 0.28, height * 1.80, depth * 0.22),
            tags=[*list(component.tags), "vertical_fin"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy - height * 0.34, cz),
            extents=(width * 0.82, max(height * 0.18, 0.035), depth * 0.64),
            tags=[*list(component.tags), "stabilizer_root"],
        ),
    ]


def _roof_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    return [
        _box(component.part, component),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.42, cz),
            extents=(width * 0.82, height * 0.18, depth * 1.12),
            tags=[*list(component.tags), "ridge_cap"],
        ),
    ]


def _roof_ridge_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    return [
        _box(component.part, component, tags=[*list(component.tags), "ridge_mass"]),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.34, cz),
            extents=(width * 0.18, height * 0.38, depth * 1.04),
            tags=[*list(component.tags), "roof_peak"],
        ),
        _box(
            component.part,
            component,
            center=(cx - width * 0.24, cy + height * 0.10, cz),
            extents=(width * 0.48, height * 0.18, depth * 1.08),
            tags=[*list(component.tags), "left_roof_plane"],
        ),
        _box(
            component.part,
            component,
            center=(cx + width * 0.24, cy + height * 0.10, cz),
            extents=(width * 0.48, height * 0.18, depth * 1.08),
            tags=[*list(component.tags), "right_roof_plane"],
        ),
    ]


def _dome_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    radius = component.radius if component.radius is not None else min(width, depth) * 0.50
    return [
        _cylinder(
            component.part,
            component,
            radius=radius,
            height=max(height * 0.32, 0.12),
            axis="y",
            center=(component.center[0], component.center[1] - height * 0.22, component.center[2]),
            tags=[*list(component.tags), "dome_base"],
        ),
        _cylinder(
            component.part,
            component,
            radius=radius * 0.72,
            height=max(height * 0.42, 0.18),
            axis="y",
            center=(component.center[0], component.center[1] + height * 0.06, component.center[2]),
            tags=[*list(component.tags), "dome_crown"],
        ),
        _cylinder(
            component.part,
            component,
            radius=radius * 0.22,
            height=max(height * 0.35, 0.16),
            axis="y",
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
        _box(component.part, component),
        _box(
            component.part,
            component,
            center=(cx, cy, cz + depth * 0.08),
            extents=(max(width - lip * 2.0, 0.20), max(height - lip * 2.0, 0.20), face_depth * 1.08),
            tags=[*list(component.tags), "feature", "glass_cutout"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy, cz + depth * 0.20),
            extents=(max(lip * 0.45, 0.10), height * 0.86, face_depth * 1.12),
            tags=[*list(component.tags), "feature", "mullion"],
        ),
    ]


def _arch_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    pier_w = max(width * 0.16, 0.10)
    crown_h = max(height * 0.26, 0.12)
    opening_w = max(width - pier_w * 2.0, pier_w)
    return [
        _box(
            component.part,
            component,
            center=(cx - width * 0.50 + pier_w * 0.50, cy - height * 0.06, cz),
            extents=(pier_w, height * 0.88, depth),
            tags=[*list(component.tags), "left_pier"],
        ),
        _box(
            component.part,
            component,
            center=(cx + width * 0.50 - pier_w * 0.50, cy - height * 0.06, cz),
            extents=(pier_w, height * 0.88, depth),
            tags=[*list(component.tags), "right_pier"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.38, cz),
            extents=(width, crown_h, depth),
            tags=[*list(component.tags), "arch_lintel"],
        ),
        _cylinder(
            component.part,
            component,
            center=(cx, cy + height * 0.25, cz),
            radius=opening_w * 0.30,
            height=max(depth * 1.04, 0.08),
            axis="z",
            tags=[*list(component.tags), "rounded_arch_crown"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy - height * 0.50, cz),
            extents=(width * 1.04, max(height * 0.08, 0.05), depth * 1.08),
            tags=[*list(component.tags), "arch_threshold"],
        ),
    ]


def _balcony_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    rail_h = max(height * 1.80, 0.18)
    rail_t = max(min(width, depth) * 0.08, 0.06)
    return [
        _box(component.part, component, tags=[*list(component.tags), "balcony_slab"]),
        _box(
            component.part,
            component,
            center=(cx, cy + rail_h * 0.52, cz + depth * 0.44),
            extents=(width, rail_h, rail_t),
            tags=[*list(component.tags), "front_rail"],
        ),
        _box(
            component.part,
            component,
            center=(cx - width * 0.46, cy + rail_h * 0.45, cz),
            extents=(rail_t, rail_h * 0.86, depth),
            tags=[*list(component.tags), "left_rail"],
        ),
        _box(
            component.part,
            component,
            center=(cx + width * 0.46, cy + rail_h * 0.45, cz),
            extents=(rail_t, rail_h * 0.86, depth),
            tags=[*list(component.tags), "right_rail"],
        ),
    ]


def _awning_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    return [
        _box(component.part, component, tags=[*list(component.tags), "canopy_slab"]),
        _box(
            component.part,
            component,
            center=(cx, cy - height * 0.18, cz + depth * 0.34),
            extents=(width * 0.96, max(height * 0.18, 0.06), depth * 0.18),
            tags=[*list(component.tags), "front_lip"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.12, cz - depth * 0.38),
            extents=(width * 0.90, max(height * 0.14, 0.05), depth * 0.12),
            tags=[*list(component.tags), "wall_mount"],
        ),
    ]


def _cornice_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    return [
        _box(component.part, component, tags=[*list(component.tags), "cornice_band"]),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.36, cz + depth * 0.12),
            extents=(width * 1.03, max(height * 0.34, 0.06), depth * 0.72),
            tags=[*list(component.tags), "upper_lip"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy - height * 0.34, cz + depth * 0.18),
            extents=(width * 0.96, max(height * 0.20, 0.05), depth * 0.50),
            tags=[*list(component.tags), "lower_shadow_line"],
        ),
    ]


def _parapet_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    wall_t = max(min(width, depth) * 0.055, 0.06)
    cap_h = max(height * 0.22, 0.045)
    return [
        _box(
            component.part,
            component,
            center=(cx, cy, cz + depth * 0.50 - wall_t * 0.50),
            extents=(width, height, wall_t),
            tags=[*list(component.tags), "front_parapet_wall"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy, cz - depth * 0.50 + wall_t * 0.50),
            extents=(width, height, wall_t),
            tags=[*list(component.tags), "rear_parapet_wall"],
        ),
        _box(
            component.part,
            component,
            center=(cx - width * 0.50 + wall_t * 0.50, cy, cz),
            extents=(wall_t, height, depth),
            tags=[*list(component.tags), "left_parapet_wall"],
        ),
        _box(
            component.part,
            component,
            center=(cx + width * 0.50 - wall_t * 0.50, cy, cz),
            extents=(wall_t, height, depth),
            tags=[*list(component.tags), "right_parapet_wall"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.50 + cap_h * 0.50, cz),
            extents=(width * 1.04, cap_h, depth * 1.04),
            tags=[*list(component.tags), "parapet_cap"],
        ),
    ]


def _dormer_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    return [
        _box(component.part, component, tags=[*list(component.tags), "dormer_body"]),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.42, cz),
            extents=(width * 1.12, height * 0.26, depth * 1.16),
            tags=[*list(component.tags), "dormer_roof"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy - height * 0.04, cz + depth * 0.44),
            extents=(width * 0.52, height * 0.46, depth * 0.16),
            tags=[*list(component.tags), "dormer_window"],
        ),
    ]


def _chimney_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    return [
        _box(component.part, component, tags=[*list(component.tags), "chimney_stack"]),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.48, cz),
            extents=(width * 1.35, max(height * 0.12, 0.06), depth * 1.35),
            tags=[*list(component.tags), "chimney_cap"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.58, cz),
            extents=(width * 0.52, max(height * 0.08, 0.04), depth * 0.52),
            tags=[*list(component.tags), "flue_opening"],
        ),
    ]


def _column_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    radius = component.radius if component.radius is not None else max(min(width, depth) * 0.42, 0.18)
    cx, cy, cz = component.center
    return [
        _cylinder(
            component.part,
            component,
            radius=radius,
            height=component.height if component.height is not None else height,
            axis="y",
            tags=[*list(component.tags), "shaft"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.48, cz),
            extents=(radius * 2.6, max(height * 0.08, 0.16), radius * 2.6),
            tags=[*list(component.tags), "capital"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy - height * 0.48, cz),
            extents=(radius * 2.8, max(height * 0.08, 0.16), radius * 2.8),
            tags=[*list(component.tags), "base"],
        ),
    ]


def _tower_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    cap_h = max(height * 0.09, 0.16)
    return [
        _box(component.part, component, tags=[*list(component.tags), "tower_shaft"]),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.50 + cap_h * 0.35, cz),
            extents=(width * 1.18, cap_h, depth * 1.18),
            tags=[*list(component.tags), "tower_cap"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.28, cz + depth * 0.52),
            extents=(width * 0.42, height * 0.22, max(depth * 0.08, 0.06)),
            tags=[*list(component.tags), "tower_window"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy - height * 0.48, cz),
            extents=(width * 1.22, max(height * 0.06, 0.10), depth * 1.22),
            tags=[*list(component.tags), "tower_base"],
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
            _box(
                component.part,
                component,
                center=(
                    component.center[0],
                    component.center[1] - height * 0.35 + step_h * (index + 0.5),
                    component.center[2] + depth * 0.40 - step_d * (index + 0.5),
                ),
                extents=(width, step_h, step_d),
                tags=[*list(component.tags), "step", f"step_{index}"],
            )
        )
    return primitives


def _stair_core_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    primitives = _stair_primitives(component)
    primitives.extend(
        [
            _box(
                component.part,
                component,
                center=(component.center[0] - width * 0.46, component.center[1], component.center[2]),
                extents=(max(width * 0.08, 0.06), height * 0.92, depth),
                tags=[*list(component.tags), "left_core_wall"],
            ),
            _box(
                component.part,
                component,
                center=(component.center[0] + width * 0.46, component.center[1], component.center[2]),
                extents=(max(width * 0.08, 0.06), height * 0.92, depth),
                tags=[*list(component.tags), "right_core_wall"],
            ),
            _box(
                component.part,
                component,
                center=(component.center[0], component.center[1] + height * 0.44, component.center[2]),
                extents=(width, max(height * 0.10, 0.08), depth * 0.92),
                tags=[*list(component.tags), "landing"],
            ),
        ]
    )
    return primitives


def _chassis_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    return [
        _box(component.part, component),
        _box(
            component.part,
            component,
            center=(component.center[0], component.center[1] - height * 0.35, component.center[2]),
            extents=(width * 0.88, height * 0.30, depth * 1.08),
            tags=[*list(component.tags), "underframe"],
        ),
    ]


def _cabin_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    return [
        _box(component.part, component),
        _box(
            component.part,
            component,
            center=(component.center[0], component.center[1] + height * 0.08, component.center[2] + depth * 0.46),
            extents=(width * 0.68, height * 0.42, depth * 0.16),
            tags=[*list(component.tags), "feature", "windshield"],
        ),
    ]


def _wheel_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    radius = component.radius if component.radius is not None else max(min(height, depth) * 0.48, 0.20)
    wheel_height = component.height if component.height is not None else max(width, 0.20)
    return [
        _cylinder(component.part, component, radius=radius, height=wheel_height, axis="x", tags=[*list(component.tags), "tire"]),
        _cylinder(
            component.part,
            component,
            radius=radius * 0.45,
            height=wheel_height * 1.12,
            axis="x",
            tags=[*list(component.tags), "hub"],
        ),
    ]


def _hull_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    return [
        _box(component.part, component),
        _box(
            component.part,
            component,
            center=(cx, cy - height * 0.34, cz),
            extents=(width * 0.52, height * 0.34, depth * 1.08),
            tags=[*list(component.tags), "keel"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.12, cz + depth * 0.48),
            extents=(width * 0.76, height * 0.20, depth * 0.18),
            tags=[*list(component.tags), "bow"],
        ),
    ]


def _deck_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    return [
        _box(component.part, component),
        _box(
            component.part,
            component,
            center=(component.center[0], component.center[1] + height * 0.32, component.center[2]),
            extents=(width * 0.82, height * 0.16, depth * 0.82),
            tags=[*list(component.tags), "raised_deck"],
        ),
    ]


def _mast_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    radius = component.radius if component.radius is not None else max(min(component.extents[0], component.extents[2]) * 0.24, 0.12)
    height = component.height if component.height is not None else component.extents[1]
    return [
        _cylinder(component.part, component, radius=radius, height=height, axis="y", tags=[*list(component.tags), "mast"]),
        _box(
            component.part,
            component,
            center=(component.center[0], component.center[1] + height * 0.16, component.center[2]),
            extents=(radius * 7.0, radius * 0.8, radius * 1.2),
            tags=[*list(component.tags), "crossbar"],
        ),
    ]


def _engine_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    radius = component.radius if component.radius is not None else max(min(width, height) * 0.32, 0.18)
    return [
        _cylinder(
            component.part,
            component,
            radius=radius,
            height=component.height if component.height is not None else depth,
            axis="z",
            tags=[*list(component.tags), "engine_core"],
        ),
        _box(
            component.part,
            component,
            center=(component.center[0], component.center[1], component.center[2] - depth * 0.48),
            extents=(radius * 2.4, radius * 1.5, max(depth * 0.18, 0.20)),
            tags=[*list(component.tags), "mount"],
        ),
    ]


def _pontoon_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    radius = component.radius if component.radius is not None else max(min(width, height) * 0.48, 0.08)
    pontoon_length = component.height if component.height is not None else depth
    return [
        _cylinder(
            component.part,
            component,
            radius=radius,
            height=pontoon_length,
            axis="z",
            tags=[*list(component.tags), "float_body"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.34, cz),
            extents=(width * 0.82, max(height * 0.16, 0.05), depth * 0.86),
            tags=[*list(component.tags), "top_sponson"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy, cz + depth * 0.50),
            extents=(width * 0.62, height * 0.42, max(depth * 0.08, 0.06)),
            tags=[*list(component.tags), "bow_cap"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy, cz - depth * 0.50),
            extents=(width * 0.62, height * 0.42, max(depth * 0.08, 0.06)),
            tags=[*list(component.tags), "stern_cap"],
        ),
    ]


def _outrigger_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    side_sign = -1.0 if "port" in component.tags or "left" in component.tags else 1.0
    radius = component.radius if component.radius is not None else max(height * 0.52, 0.05)
    float_length = component.height if component.height is not None else depth * 0.92
    return [
        _box(
            component.part,
            component,
            center=(cx - side_sign * width * 0.28, cy + height * 0.22, cz),
            extents=(width * 0.72, max(height * 0.24, 0.04), max(depth * 0.10, 0.05)),
            tags=[*list(component.tags), "crossbeam"],
        ),
        _cylinder(
            component.part,
            component,
            center=(cx + side_sign * width * 0.18, cy - height * 0.22, cz),
            radius=radius,
            height=float_length,
            axis="z",
            tags=[*list(component.tags), "outrigger_float"],
        ),
        _box(
            component.part,
            component,
            center=(cx + side_sign * width * 0.18, cy + height * 0.08, cz),
            extents=(width * 0.18, max(height * 0.18, 0.04), depth * 0.78),
            tags=[*list(component.tags), "float_strake"],
        ),
    ]


def _sail_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    batten_height = max(height * 0.035, 0.04)
    return [
        _box(
            component.part,
            component,
            extents=(width, height, max(depth * 0.18, 0.035)),
            tags=[*list(component.tags), "cloth_panel"],
        ),
        _box(
            component.part,
            component,
            center=(cx - width * 0.46, cy, cz),
            extents=(max(width * 0.05, 0.04), height * 1.04, max(depth * 0.24, 0.04)),
            tags=[*list(component.tags), "luff_sleeve"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.22, cz),
            extents=(width * 0.88, batten_height, max(depth * 0.22, 0.04)),
            tags=[*list(component.tags), "upper_batten"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy - height * 0.22, cz),
            extents=(width * 0.82, batten_height, max(depth * 0.22, 0.04)),
            tags=[*list(component.tags), "lower_batten"],
        ),
    ]


def _rigging_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    wire = max(min(width, depth) * 0.42, 0.025)
    return [
        _box(
            component.part,
            component,
            extents=(wire, height, wire),
            tags=[*list(component.tags), "standing_line"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy - height * 0.40, cz),
            extents=(width * 2.2, wire, max(depth * 0.10, wire)),
            tags=[*list(component.tags), "deck_tie"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.12, cz),
            extents=(wire, max(height * 0.54, wire), depth),
            tags=[*list(component.tags), "fore_aft_stay"],
        ),
    ]


def _cargo_hold_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    rim = max(min(width, depth) * 0.09, 0.04)
    return [
        _box(
            component.part,
            component,
            center=(cx, cy - height * 0.12, cz),
            extents=(width * 0.88, max(height * 0.36, 0.05), depth * 0.82),
            tags=[*list(component.tags), "recessed_hold"],
        ),
        _box(
            component.part,
            component,
            center=(cx - width * 0.50 + rim * 0.50, cy + height * 0.32, cz),
            extents=(rim, max(height * 0.18, 0.04), depth),
            tags=[*list(component.tags), "port_rim"],
        ),
        _box(
            component.part,
            component,
            center=(cx + width * 0.50 - rim * 0.50, cy + height * 0.32, cz),
            extents=(rim, max(height * 0.18, 0.04), depth),
            tags=[*list(component.tags), "starboard_rim"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.34, cz - depth * 0.50 + rim * 0.50),
            extents=(width, max(height * 0.18, 0.04), rim),
            tags=[*list(component.tags), "aft_rim"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.34, cz + depth * 0.50 - rim * 0.50),
            extents=(width, max(height * 0.18, 0.04), rim),
            tags=[*list(component.tags), "fore_rim"],
        ),
    ]


def _rudder_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    radius = component.radius if component.radius is not None else max(width * 0.16, 0.04)
    shaft_height = component.height if component.height is not None else height
    return [
        _cylinder(
            component.part,
            component,
            center=(cx, cy + height * 0.10, cz - depth * 0.26),
            radius=radius,
            height=shaft_height,
            axis="y",
            tags=[*list(component.tags), "rudder_post"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy - height * 0.14, cz + depth * 0.12),
            extents=(width, height * 0.78, max(depth * 0.36, 0.05)),
            tags=[*list(component.tags), "rudder_blade"],
        ),
    ]


def _propeller_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    radius = component.radius if component.radius is not None else max(min(component.extents[0], component.extents[1]) * 0.45, 0.06)
    height = component.height if component.height is not None else max(component.extents[2], 0.04)
    cx, cy, cz = component.center
    blade_thickness = max(radius * 0.20, 0.025)
    return [
        _cylinder(
            component.part,
            component,
            radius=radius * 0.34,
            height=height,
            axis="z",
            tags=[*list(component.tags), "prop_hub"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy, cz),
            extents=(radius * 2.10, blade_thickness, height * 0.54),
            tags=[*list(component.tags), "horizontal_blades"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy, cz),
            extents=(blade_thickness, radius * 2.10, height * 0.54),
            tags=[*list(component.tags), "vertical_blades"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy, cz + height * 0.04),
            extents=(radius * 1.15, radius * 1.15, max(height * 0.30, 0.025)),
            tags=[*list(component.tags), "skewed_blade_mass"],
        ),
    ]


def _anchor_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    ring_radius = component.radius if component.radius is not None else max(width * 0.18, 0.04)
    return [
        _cylinder(
            component.part,
            component,
            center=(cx, cy + height * 0.44, cz),
            radius=ring_radius,
            height=max(depth * 0.35, 0.035),
            axis="z",
            tags=[*list(component.tags), "anchor_ring"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy, cz),
            extents=(max(width * 0.20, 0.04), height, max(depth * 0.34, 0.04)),
            tags=[*list(component.tags), "anchor_shank"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy - height * 0.38, cz),
            extents=(width, max(height * 0.16, 0.04), max(depth * 0.42, 0.04)),
            tags=[*list(component.tags), "anchor_stock"],
        ),
        _box(
            component.part,
            component,
            center=(cx - width * 0.36, cy - height * 0.48, cz),
            extents=(width * 0.30, height * 0.24, max(depth * 0.54, 0.04)),
            tags=[*list(component.tags), "port_fluke"],
        ),
        _box(
            component.part,
            component,
            center=(cx + width * 0.36, cy - height * 0.48, cz),
            extents=(width * 0.30, height * 0.24, max(depth * 0.54, 0.04)),
            tags=[*list(component.tags), "starboard_fluke"],
        ),
    ]


def _track_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    shoe_count = 6
    spacing = depth / max(1, shoe_count)
    start_z = cz - depth * 0.50 + spacing * 0.50
    primitives = [
        _box(component.part, component, tags=[*list(component.tags), "track_belt"]),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.34, cz),
            extents=(width * 0.72, max(height * 0.16, 0.06), depth * 0.92),
            tags=[*list(component.tags), "upper_run"],
        ),
    ]
    for index in range(shoe_count):
        primitives.append(
            _box(
                component.part,
                component,
                center=(cx, cy - height * 0.34, start_z + spacing * index),
                extents=(width * 1.08, max(height * 0.18, 0.06), spacing * 0.62),
                tags=[*list(component.tags), "track_shoe", f"shoe_{index}"],
            )
        )
    return primitives


def _suspension_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    radius = max(min(height, depth) * 0.34, 0.04)
    return [
        _cylinder(component.part, component, radius=radius, height=width, axis="x", tags=[*list(component.tags), "axle_bar"]),
        _box(
            component.part,
            component,
            center=(cx - width * 0.36, cy + height * 0.20, cz),
            extents=(width * 0.16, height * 1.40, max(depth * 1.4, 0.08)),
            tags=[*list(component.tags), "left_strut"],
        ),
        _box(
            component.part,
            component,
            center=(cx + width * 0.36, cy + height * 0.20, cz),
            extents=(width * 0.16, height * 1.40, max(depth * 1.4, 0.08)),
            tags=[*list(component.tags), "right_strut"],
        ),
    ]


def _cargo_module_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    return [
        _box(component.part, component, tags=[*list(component.tags), "cargo_shell"]),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.42, cz),
            extents=(width * 0.88, max(height * 0.14, 0.06), depth * 0.88),
            tags=[*list(component.tags), "cargo_lid"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy, cz + depth * 0.50),
            extents=(width * 0.64, height * 0.42, max(depth * 0.08, 0.06)),
            tags=[*list(component.tags), "cargo_hatch"],
        ),
    ]


def _turret_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    radius = component.radius if component.radius is not None else min(width, depth) * 0.48
    return [
        _cylinder(component.part, component, radius=radius, height=max(height * 0.52, 0.10), axis="y", tags=[*list(component.tags), "turret_ring"]),
        _box(
            component.part,
            component,
            center=(component.center[0], component.center[1] + height * 0.30, component.center[2]),
            extents=(width, max(height * 0.42, 0.12), depth),
            tags=[*list(component.tags), "turret_housing"],
        ),
        _cylinder(
            component.part,
            component,
            radius=max(min(width, depth) * 0.12, 0.05),
            height=max(depth * 1.25, 0.18),
            axis="z",
            center=(component.center[0], component.center[1] + height * 0.36, component.center[2] + depth * 0.66),
            tags=[*list(component.tags), "turret_barrel"],
        ),
    ]


def _wing_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    return [
        _box(component.part, component, tags=[*list(component.tags), "wing_plane"]),
        _box(
            component.part,
            component,
            center=(component.center[0], component.center[1] + height * 0.34, component.center[2] - depth * 0.30),
            extents=(width * 0.82, max(height * 0.24, 0.05), depth * 0.18),
            tags=[*list(component.tags), "leading_edge"],
        ),
        _box(
            component.part,
            component,
            center=(component.center[0], component.center[1] - height * 0.18, component.center[2] + depth * 0.36),
            extents=(width * 0.66, max(height * 0.18, 0.04), depth * 0.12),
            tags=[*list(component.tags), "control_surface"],
        ),
    ]


def _manipulator_arm_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    return [
        _box(component.part, component, tags=[*list(component.tags), "upper_arm"]),
        _box(
            component.part,
            component,
            center=(cx, cy - height * 0.46, cz - depth * 0.36),
            extents=(width * 1.35, height * 0.72, depth * 0.18),
            tags=[*list(component.tags), "shoulder_joint"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.22, cz + depth * 0.40),
            extents=(width * 1.10, height * 0.80, depth * 0.18),
            tags=[*list(component.tags), "wrist_joint"],
        ),
    ]


def _machine_base_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    return [
        _box(component.part, component, tags=[*list(component.tags), "machine_plinth"]),
        _box(
            component.part,
            component,
            center=(component.center[0], component.center[1] + height * 0.42, component.center[2]),
            extents=(width * 0.84, max(height * 0.18, 0.08), depth * 0.84),
            tags=[*list(component.tags), "mounting_plate"],
        ),
    ]


def _machine_column_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    radius = max(min(width, depth) * 0.42, 0.08)
    return [
        _cylinder(component.part, component, radius=radius, height=height, axis="y", tags=[*list(component.tags), "column_core"]),
        _box(
            component.part,
            component,
            center=(component.center[0], component.center[1] - height * 0.46, component.center[2]),
            extents=(width * 1.50, max(height * 0.10, 0.08), depth * 1.50),
            tags=[*list(component.tags), "column_foot"],
        ),
    ]


def _hydraulic_piston_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    radius = component.radius if component.radius is not None else max(min(component.extents[0], component.extents[2]) * 0.36, 0.05)
    height = component.height if component.height is not None else component.extents[1]
    return [
        _cylinder(component.part, component, radius=radius, height=height, axis=component.axis, tags=[*list(component.tags), "piston_body"]),
        _cylinder(
            component.part,
            component,
            radius=radius * 0.48,
            height=height * 1.18,
            axis=component.axis,
            tags=[*list(component.tags), "chrome_rod"],
        ),
    ]


def _conveyor_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    roller_count = 4
    spacing = width / max(1, roller_count - 1)
    start_x = cx - width * 0.50
    primitives = [_box(component.part, component, tags=[*list(component.tags), "belt"])]
    for index in range(roller_count):
        primitives.append(
            _cylinder(
                component.part,
                component,
                center=(start_x + spacing * index, cy + height * 0.18, cz),
                radius=max(height * 0.24, 0.05),
                height=depth * 1.04,
                axis="z",
                tags=[*list(component.tags), "roller", f"roller_{index}"],
            )
        )
    return primitives


def _gear_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    radius = component.radius if component.radius is not None else max(min(component.extents[0], component.extents[1]) * 0.48, 0.08)
    height = component.height if component.height is not None else max(component.extents[2], 0.06)
    primitives = [
        _cylinder(component.part, component, radius=radius, height=height, axis=component.axis, tags=[*list(component.tags), "gear_disc"]),
        _cylinder(component.part, component, radius=radius * 0.34, height=height * 1.15, axis=component.axis, tags=[*list(component.tags), "gear_hub"]),
    ]
    for index in range(8):
        angle = math.tau * index / 8.0
        primitives.append(
            _box(
                component.part,
                component,
                center=(
                    component.center[0],
                    component.center[1] + math.sin(angle) * radius * 0.86,
                    component.center[2] + math.cos(angle) * radius * 0.86,
                ),
                extents=(height * 1.08, radius * 0.22, radius * 0.16),
                tags=[*list(component.tags), "gear_tooth", f"tooth_{index}"],
            )
        )
    return primitives


def _tank_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    radius = component.radius if component.radius is not None else max(min(component.extents[0], component.extents[2]) * 0.45, 0.10)
    height = component.height if component.height is not None else component.extents[1]
    return [
        _cylinder(component.part, component, radius=radius, height=height, axis=component.axis, tags=[*list(component.tags), "tank_body"]),
        _box(
            component.part,
            component,
            center=(component.center[0], component.center[1] + height * 0.48, component.center[2]),
            extents=(radius * 1.25, max(height * 0.08, 0.06), radius * 1.25),
            tags=[*list(component.tags), "access_hatch"],
        ),
    ]


def _crane_boom_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    return [
        _box(component.part, component, tags=[*list(component.tags), "boom_beam"]),
        _box(
            component.part,
            component,
            center=(cx, cy - height * 0.48, cz + depth * 0.46),
            extents=(width * 0.70, height * 0.42, depth * 0.10),
            tags=[*list(component.tags), "hook_mount"],
        ),
    ]


def _road_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    shoulder = max(width * 0.09, 0.20)
    marker_width = max(width * 0.018, 0.08)
    return [
        _box(component.part, component),
        _box(
            component.part,
            component,
            center=(cx - width * 0.50 + shoulder * 0.50, cy + height * 0.36, cz),
            extents=(shoulder, height * 0.42, depth * 1.02),
            tags=[*list(component.tags), "shoulder", "left"],
        ),
        _box(
            component.part,
            component,
            center=(cx + width * 0.50 - shoulder * 0.50, cy + height * 0.36, cz),
            extents=(shoulder, height * 0.42, depth * 1.02),
            tags=[*list(component.tags), "shoulder", "right"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.56, cz),
            extents=(marker_width, max(height * 0.10, 0.05), depth * 0.92),
            tags=[*list(component.tags), "lane_marker", "center"],
        ),
    ]


def _road_junction_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    marker_h = max(height * 0.12, 0.04)
    return [
        _box(component.part, component, tags=[*list(component.tags), "junction_plate"]),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.44, cz),
            extents=(width * 0.18, marker_h, depth * 0.84),
            tags=[*list(component.tags), "junction_lane_marker", "north_south"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.45, cz),
            extents=(width * 0.84, marker_h, depth * 0.18),
            tags=[*list(component.tags), "junction_lane_marker", "east_west"],
        ),
        _box(
            component.part,
            component,
            center=(cx - width * 0.40, cy + height * 0.30, cz - depth * 0.40),
            extents=(width * 0.18, height * 0.28, depth * 0.18),
            tags=[*list(component.tags), "corner_apron", "southwest"],
        ),
        _box(
            component.part,
            component,
            center=(cx + width * 0.40, cy + height * 0.30, cz + depth * 0.40),
            extents=(width * 0.18, height * 0.28, depth * 0.18),
            tags=[*list(component.tags), "corner_apron", "northeast"],
        ),
    ]


def _crosswalk_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    stripe_count = 5
    stripe_w = width / (stripe_count * 2.0 - 1.0)
    start_x = cx - width * 0.50 + stripe_w * 0.50
    primitives = [
        _box(
            component.part,
            component,
            extents=(width, max(height * 0.30, 0.025), depth),
            tags=[*list(component.tags), "crosswalk_base"],
        )
    ]
    for index in range(stripe_count):
        primitives.append(
            _box(
                component.part,
                component,
                center=(start_x + index * stripe_w * 2.0, cy + height * 0.42, cz),
                extents=(stripe_w, max(height, 0.035), depth),
                tags=[*list(component.tags), "crosswalk_stripe", f"stripe_{index}"],
            )
        )
    return primitives


def _turnout_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    return [
        _box(component.part, component, tags=[*list(component.tags), "turnout_pad"]),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.44, cz - depth * 0.36),
            extents=(width * 0.80, max(height * 0.12, 0.035), depth * 0.08),
            tags=[*list(component.tags), "turnout_entry_mark"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.44, cz + depth * 0.36),
            extents=(width * 0.80, max(height * 0.12, 0.035), depth * 0.08),
            tags=[*list(component.tags), "turnout_exit_mark"],
        ),
    ]


def _roundabout_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    radius = component.radius if component.radius is not None else min(width, depth) * 0.32
    return [
        _box(component.part, component, tags=[*list(component.tags), "roundabout_pad"]),
        _cylinder(
            component.part,
            component,
            radius=radius,
            height=component.height if component.height is not None else height,
            axis="y",
            tags=[*list(component.tags), "traffic_island"],
        ),
        _cylinder(
            component.part,
            component,
            radius=radius * 1.28,
            height=max(height * 0.22, 0.035),
            axis="y",
            center=(component.center[0], component.center[1] + height * 0.48, component.center[2]),
            tags=[*list(component.tags), "painted_ring"],
        ),
    ]


def _median_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    cap_h = max(height * 0.20, 0.035)
    return [
        _box(component.part, component, tags=[*list(component.tags), "raised_median"]),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.54, cz - depth * 0.34),
            extents=(width * 1.18, cap_h, depth * 0.10),
            tags=[*list(component.tags), "median_nose_a"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.54, cz + depth * 0.34),
            extents=(width * 1.18, cap_h, depth * 0.10),
            tags=[*list(component.tags), "median_nose_b"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.58, cz),
            extents=(width * 0.46, cap_h, depth * 0.82),
            tags=[*list(component.tags), "median_painted_spine"],
        ),
    ]


def _curb_ramp_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    cheek_w = max(width * 0.12, 0.05)
    return [
        _box(component.part, component, tags=[*list(component.tags), "ramp_slab"]),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.42, cz + depth * 0.36),
            extents=(width * 0.88, max(height * 0.18, 0.025), depth * 0.12),
            tags=[*list(component.tags), "tactile_strip"],
        ),
        _box(
            component.part,
            component,
            center=(cx - width * 0.50 + cheek_w * 0.50, cy + height * 0.24, cz),
            extents=(cheek_w, height * 0.68, depth),
            tags=[*list(component.tags), "left_ramp_cheek"],
        ),
        _box(
            component.part,
            component,
            center=(cx + width * 0.50 - cheek_w * 0.50, cy + height * 0.24, cz),
            extents=(cheek_w, height * 0.68, depth),
            tags=[*list(component.tags), "right_ramp_cheek"],
        ),
    ]


def _lane_arrow_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    stripe_h = max(height, 0.025)
    return [
        _box(
            component.part,
            component,
            center=(cx, cy, cz - depth * 0.10),
            extents=(width * 0.20, stripe_h, depth * 0.70),
            tags=[*list(component.tags), "arrow_shaft"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy, cz + depth * 0.34),
            extents=(width * 0.68, stripe_h, depth * 0.18),
            tags=[*list(component.tags), "arrow_head_bar"],
        ),
        _box(
            component.part,
            component,
            center=(cx - width * 0.18, cy, cz + depth * 0.24),
            extents=(width * 0.18, stripe_h, depth * 0.26),
            tags=[*list(component.tags), "arrow_head_left"],
        ),
        _box(
            component.part,
            component,
            center=(cx + width * 0.18, cy, cz + depth * 0.24),
            extents=(width * 0.18, stripe_h, depth * 0.26),
            tags=[*list(component.tags), "arrow_head_right"],
        ),
    ]


def _stop_line_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    stripe_h = max(height, 0.025)
    return [
        _box(component.part, component, tags=[*list(component.tags), "stop_bar_primary"]),
        _box(
            component.part,
            component,
            center=(cx, cy + stripe_h * 0.20, cz + depth * 0.34),
            extents=(width, stripe_h, max(depth * 0.18, 0.035)),
            tags=[*list(component.tags), "advance_stop_bar"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy + stripe_h * 0.22, cz - depth * 0.34),
            extents=(width * 0.82, stripe_h, max(depth * 0.12, 0.03)),
            tags=[*list(component.tags), "yield_bar"],
        ),
    ]


def _bridge_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    girder_h = max(height * 0.28, 0.20)
    return [
        _box(component.part, component),
        _box(
            component.part,
            component,
            center=(cx - width * 0.34, cy - height * 0.46, cz),
            extents=(width * 0.10, girder_h, depth * 1.04),
            tags=[*list(component.tags), "underside_girder", "left"],
        ),
        _box(
            component.part,
            component,
            center=(cx + width * 0.34, cy - height * 0.46, cz),
            extents=(width * 0.10, girder_h, depth * 1.04),
            tags=[*list(component.tags), "underside_girder", "right"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy - height * 0.36, cz),
            extents=(width * 0.52, max(height * 0.14, 0.12), depth * 0.90),
            tags=[*list(component.tags), "spine"],
        ),
    ]


def _railing_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    post_count = 4
    spacing = depth / max(1, post_count - 1)
    start_z = cz - depth * 0.50
    primitives = [
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.42, cz),
            extents=(width, max(height * 0.12, 0.10), depth),
            tags=[*list(component.tags), "top_rail"],
        )
    ]
    for index in range(post_count):
        primitives.append(
            _box(
                component.part,
                component,
                center=(cx, cy, start_z + spacing * index),
                extents=(width * 0.78, height, max(depth * 0.035, 0.10)),
                tags=[*list(component.tags), "post", f"post_{index}"],
            )
        )
    return primitives


def _terrain_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    return [
        _box(component.part, component),
        _box(
            component.part,
            component,
            center=(cx - width * 0.18, cy + height * 0.35, cz - depth * 0.16),
            extents=(width * 0.52, height * 0.38, depth * 0.48),
            tags=[*list(component.tags), "plateau"],
        ),
        _box(
            component.part,
            component,
            center=(cx + width * 0.24, cy + height * 0.22, cz + depth * 0.20),
            extents=(width * 0.32, height * 0.24, depth * 0.58),
            tags=[*list(component.tags), "ridge"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy - height * 0.20, cz + depth * 0.42),
            extents=(width * 0.70, height * 0.24, depth * 0.16),
            tags=[*list(component.tags), "cliff_face"],
        ),
    ]


def _terrain_ridge_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    cap = max(width * 0.28, 0.12)
    return [
        _box(component.part, component, tags=[*list(component.tags), "feature", "ridge_mass"]),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.36, cz),
            extents=(width * 0.62, height * 0.34, depth * 1.04),
            tags=[*list(component.tags), "feature", "ridge_spine", "raised_ridge"],
        ),
        _box(
            component.part,
            component,
            center=(cx - width * 0.42, cy - height * 0.10, cz),
            extents=(cap, height * 0.42, depth * 0.94),
            tags=[*list(component.tags), "feature", "ridge_slope", "left"],
        ),
        _box(
            component.part,
            component,
            center=(cx + width * 0.42, cy - height * 0.10, cz),
            extents=(cap, height * 0.42, depth * 0.94),
            tags=[*list(component.tags), "feature", "ridge_slope", "right"],
        ),
    ]


def _terrain_cliff_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    shelf_h = max(height * 0.10, 0.08)
    return [
        _box(component.part, component, tags=[*list(component.tags), "feature", "cliff_mass"]),
        _box(
            component.part,
            component,
            center=(cx - width * 0.18, cy + height * 0.28, cz),
            extents=(width * 0.40, shelf_h, depth * 0.92),
            tags=[*list(component.tags), "feature", "cliff_shelf", "upper"],
        ),
        _box(
            component.part,
            component,
            center=(cx + width * 0.20, cy - height * 0.08, cz - depth * 0.12),
            extents=(width * 0.36, shelf_h, depth * 0.74),
            tags=[*list(component.tags), "feature", "cliff_shelf", "middle"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy - height * 0.46, cz + depth * 0.34),
            extents=(width * 0.74, height * 0.14, depth * 0.24),
            tags=[*list(component.tags), "feature", "talus_foot"],
        ),
    ]


def _terrain_clearing_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    rim_w = max(min(width, depth) * 0.08, 0.08)
    return [
        _box(component.part, component, tags=[*list(component.tags), "feature", "clearing_floor"]),
        _box(
            component.part,
            component,
            center=(cx - width * 0.50 + rim_w * 0.50, cy + height * 0.60, cz),
            extents=(rim_w, height * 0.70, depth),
            tags=[*list(component.tags), "feature", "clearing_rim", "left"],
        ),
        _box(
            component.part,
            component,
            center=(cx + width * 0.50 - rim_w * 0.50, cy + height * 0.60, cz),
            extents=(rim_w, height * 0.70, depth),
            tags=[*list(component.tags), "feature", "clearing_rim", "right"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.58, cz - depth * 0.50 + rim_w * 0.50),
            extents=(width, height * 0.60, rim_w),
            tags=[*list(component.tags), "feature", "clearing_rim", "near"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.58, cz + depth * 0.50 - rim_w * 0.50),
            extents=(width, height * 0.60, rim_w),
            tags=[*list(component.tags), "feature", "clearing_rim", "far"],
        ),
    ]


def _terrain_platform_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    skirt_h = max(height * 0.28, 0.10)
    return [
        _box(component.part, component, tags=[*list(component.tags), "feature", "platform_mass"]),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.46, cz),
            extents=(width * 0.86, height * 0.18, depth * 0.86),
            tags=[*list(component.tags), "feature", "platform_cap"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy - height * 0.44, cz - depth * 0.46),
            extents=(width * 0.72, skirt_h, depth * 0.12),
            tags=[*list(component.tags), "feature", "platform_skirt", "front"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy - height * 0.44, cz + depth * 0.46),
            extents=(width * 0.72, skirt_h, depth * 0.12),
            tags=[*list(component.tags), "feature", "platform_skirt", "rear"],
        ),
    ]


def _terrain_water_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    rim = max(min(width, depth) * 0.08, 0.08)
    return [
        _box(
            component.part,
            component,
            center=(cx, cy - height * 0.18, cz),
            extents=(width, max(height * 0.35, 0.05), depth),
            tags=[*list(component.tags), "feature", "water_basin"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.30, cz),
            extents=(width * 0.82, max(height * 0.16, 0.04), depth * 0.82),
            tags=[*list(component.tags), "feature", "water_surface"],
        ),
        _box(
            component.part,
            component,
            center=(cx - width * 0.50 + rim * 0.50, cy + height * 0.12, cz),
            extents=(rim, height * 0.42, depth),
            tags=[*list(component.tags), "feature", "water_rim", "left"],
        ),
        _box(
            component.part,
            component,
            center=(cx + width * 0.50 - rim * 0.50, cy + height * 0.12, cz),
            extents=(rim, height * 0.42, depth),
            tags=[*list(component.tags), "feature", "water_rim", "right"],
        ),
    ]


def _room_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    wall_t = max(min(width, depth) * 0.045, 0.18)
    floor_h = max(height * 0.06, 0.12)
    return [
        _box(
            component.part,
            component,
            center=(cx, cy - height * 0.50 + floor_h * 0.50, cz),
            extents=(width, floor_h, depth),
            tags=[*list(component.tags), "floor"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy, cz - depth * 0.50 + wall_t * 0.50),
            extents=(width, height, wall_t),
            tags=[*list(component.tags), "back_wall"],
        ),
        _box(
            component.part,
            component,
            center=(cx - width * 0.50 + wall_t * 0.50, cy, cz),
            extents=(wall_t, height, depth),
            tags=[*list(component.tags), "left_wall"],
        ),
        _box(
            component.part,
            component,
            center=(cx + width * 0.50 - wall_t * 0.50, cy, cz),
            extents=(wall_t, height, depth),
            tags=[*list(component.tags), "right_wall"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.50 - floor_h * 0.50, cz),
            extents=(width, floor_h, depth),
            tags=[*list(component.tags), "ceiling_trim"],
        ),
    ]


def _room_cell_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    return [
        _box(component.part, component, tags=[*list(component.tags), "room_floor_zone"]),
        _box(
            component.part,
            component,
            center=(component.center[0], component.center[1] + height * 0.42, component.center[2]),
            extents=(width * 0.94, max(height * 0.10, 0.05), depth * 0.94),
            tags=[*list(component.tags), "room_zone_trim"],
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
        _box(component.part, component, tags=[*list(component.tags), "corridor_floor"]),
        _box(
            component.part,
            component,
            center=edge_a_center,
            extents=edge_extents,
            tags=[*list(component.tags), "corridor_edge_a"],
        ),
        _box(
            component.part,
            component,
            center=edge_b_center,
            extents=edge_extents,
            tags=[*list(component.tags), "corridor_edge_b"],
        ),
    ]


def _partition_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    return [
        _box(component.part, component, tags=[*list(component.tags), "partition_wall"]),
        _box(
            component.part,
            component,
            center=(component.center[0], component.center[1] + height * 0.42, component.center[2]),
            extents=(width, max(height * 0.10, 0.07), depth),
            tags=[*list(component.tags), "partition_lintel"],
        ),
    ]


def _ceiling_light_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    radius = min(width, depth) * 0.42
    return [
        _cylinder(
            component.part,
            component,
            radius=radius,
            height=max(height, 0.05),
            axis="y",
            tags=[*list(component.tags), "light_disc", "emissive"],
        ),
        _cylinder(
            component.part,
            component,
            radius=radius * 0.62,
            height=max(height * 1.20, 0.06),
            axis="y",
            center=(component.center[0], component.center[1] - height * 0.40, component.center[2]),
            tags=[*list(component.tags), "glow_core", "emissive"],
        ),
    ]


def _alcove_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    side_t = max(width * 0.12, 0.06)
    return [
        _box(component.part, component, tags=[*list(component.tags), "alcove_back"]),
        _box(
            component.part,
            component,
            center=(cx - width * 0.46, cy, cz),
            extents=(side_t, height, depth),
            tags=[*list(component.tags), "alcove_left_return"],
        ),
        _box(
            component.part,
            component,
            center=(cx + width * 0.46, cy, cz),
            extents=(side_t, height, depth),
            tags=[*list(component.tags), "alcove_right_return"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy - height * 0.42, cz + depth * 0.18),
            extents=(width, max(height * 0.10, 0.06), depth * 0.70),
            tags=[*list(component.tags), "alcove_sill"],
        ),
    ]


def _furniture_base_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    return [
        _box(component.part, component, tags=[*list(component.tags), "floor_footprint"]),
        _box(
            component.part,
            component,
            center=(component.center[0], component.center[1] + height * 0.34, component.center[2]),
            extents=(width * 0.94, max(height * 0.18, 0.04), depth * 0.94),
            tags=[*list(component.tags), "layout_trim"],
        ),
    ]


def _chair_seat_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    cushion_h = max(height * 0.38, 0.05)
    return [
        _box(component.part, component, tags=[*list(component.tags), "seat_board"]),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.38, cz),
            extents=(width * 0.92, cushion_h, depth * 0.88),
            tags=[*list(component.tags), "seat_cushion"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy - height * 0.38, cz),
            extents=(width * 0.80, max(height * 0.18, 0.04), depth * 0.78),
            tags=[*list(component.tags), "underseat_frame"],
        ),
    ]


def _chair_back_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    rail_h = max(height * 0.08, 0.05)
    side_w = max(width * 0.08, 0.04)
    return [
        _box(component.part, component, tags=[*list(component.tags), "back_panel"]),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.44, cz),
            extents=(width * 1.04, rail_h, depth * 1.18),
            tags=[*list(component.tags), "top_rail"],
        ),
        _box(
            component.part,
            component,
            center=(cx - width * 0.45, cy, cz),
            extents=(side_w, height * 1.02, depth * 1.12),
            tags=[*list(component.tags), "left_stile"],
        ),
        _box(
            component.part,
            component,
            center=(cx + width * 0.45, cy, cz),
            extents=(side_w, height * 1.02, depth * 1.12),
            tags=[*list(component.tags), "right_stile"],
        ),
    ]


def _furniture_leg_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    radius = component.radius if component.radius is not None else max(min(component.extents[0], component.extents[2]) * 0.45, 0.035)
    height = component.height if component.height is not None else component.extents[1]
    return [
        _cylinder(component.part, component, radius=radius, height=height, axis="y", tags=[*list(component.tags), "leg_post"]),
        _box(
            component.part,
            component,
            center=(component.center[0], component.center[1] - height * 0.50, component.center[2]),
            extents=(radius * 2.6, max(height * 0.06, 0.035), radius * 2.6),
            tags=[*list(component.tags), "floor_pad"],
        ),
    ]


def _table_top_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    return [
        _box(component.part, component, tags=[*list(component.tags), "top_slab"]),
        _box(
            component.part,
            component,
            center=(cx, cy - height * 0.46, cz),
            extents=(width * 0.86, max(height * 0.24, 0.05), depth * 0.86),
            tags=[*list(component.tags), "apron_frame"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.54, cz),
            extents=(width * 0.94, max(height * 0.12, 0.04), depth * 0.94),
            tags=[*list(component.tags), "surface_inset"],
        ),
    ]


def _bed_frame_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    rail = max(min(width, depth) * 0.08, 0.05)
    return [
        _box(component.part, component, tags=[*list(component.tags), "bed_platform"]),
        _box(
            component.part,
            component,
            center=(cx - width * 0.50 + rail * 0.50, cy + height * 0.22, cz),
            extents=(rail, height * 0.52, depth),
            tags=[*list(component.tags), "left_side_rail"],
        ),
        _box(
            component.part,
            component,
            center=(cx + width * 0.50 - rail * 0.50, cy + height * 0.22, cz),
            extents=(rail, height * 0.52, depth),
            tags=[*list(component.tags), "right_side_rail"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.22, cz - depth * 0.50 + rail * 0.50),
            extents=(width, height * 0.52, rail),
            tags=[*list(component.tags), "head_rail"],
        ),
    ]


def _shelf_unit_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    side_w = max(width * 0.08, 0.04)
    shelf_h = max(height * 0.055, 0.04)
    primitives = [
        _box(
            component.part,
            component,
            center=(cx - width * 0.50 + side_w * 0.50, cy, cz),
            extents=(side_w, height, depth),
            tags=[*list(component.tags), "left_side"],
        ),
        _box(
            component.part,
            component,
            center=(cx + width * 0.50 - side_w * 0.50, cy, cz),
            extents=(side_w, height, depth),
            tags=[*list(component.tags), "right_side"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.50 - shelf_h * 0.50, cz),
            extents=(width, shelf_h, depth),
            tags=[*list(component.tags), "top_cap"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy - height * 0.50 + shelf_h * 0.50, cz),
            extents=(width, shelf_h, depth),
            tags=[*list(component.tags), "bottom_cap"],
        ),
    ]
    for index, offset in enumerate((-0.25, 0.0, 0.25)):
        primitives.append(
            _box(
                component.part,
                component,
                center=(cx, cy + height * offset, cz),
                extents=(width * 0.90, shelf_h, depth * 0.94),
                tags=[*list(component.tags), "shelf_board", f"shelf_{index}"],
            )
        )
    return primitives


def _cabinet_body_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    return [
        _box(component.part, component, tags=[*list(component.tags), "cabinet_case"]),
        _box(
            component.part,
            component,
            center=(cx, cy, cz + depth * 0.50),
            extents=(width * 0.88, height * 0.84, max(depth * 0.08, 0.05)),
            tags=[*list(component.tags), "front_face"],
        ),
        _box(
            component.part,
            component,
            center=(cx - width * 0.12, cy, cz + depth * 0.54),
            extents=(max(width * 0.04, 0.035), height * 0.78, max(depth * 0.05, 0.035)),
            tags=[*list(component.tags), "left_door"],
        ),
        _box(
            component.part,
            component,
            center=(cx + width * 0.12, cy, cz + depth * 0.54),
            extents=(max(width * 0.04, 0.035), height * 0.78, max(depth * 0.05, 0.035)),
            tags=[*list(component.tags), "right_door"],
        ),
    ]


def _drawer_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    return [
        _box(component.part, component, tags=[*list(component.tags), "drawer_front"]),
        _box(
            component.part,
            component,
            center=(cx, cy, cz + depth * 0.26),
            extents=(width * 0.34, max(height * 0.26, 0.035), max(depth * 0.35, 0.035)),
            tags=[*list(component.tags), "drawer_pull"],
        ),
    ]


def _cushion_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    seam_h = max(height * 0.14, 0.035)
    return [
        _box(component.part, component, tags=[*list(component.tags), "soft_volume"]),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.42, cz),
            extents=(width * 0.88, seam_h, depth * 0.88),
            tags=[*list(component.tags), "puffed_top"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy, cz + depth * 0.48),
            extents=(width * 0.92, height * 0.24, seam_h),
            tags=[*list(component.tags), "front_seam"],
        ),
    ]


def _counter_top_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    return [
        _box(component.part, component, tags=[*list(component.tags), "counter_slab"]),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.34, cz + depth * 0.28),
            extents=(width * 0.72, max(height * 0.16, 0.04), depth * 0.18),
            tags=[*list(component.tags), "work_surface_inset"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.32, cz - depth * 0.38),
            extents=(width, max(height * 0.18, 0.05), max(depth * 0.08, 0.04)),
            tags=[*list(component.tags), "backsplash"],
        ),
    ]


def _appliance_body_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    return [
        _box(component.part, component, tags=[*list(component.tags), "appliance_case"]),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.12, cz + depth * 0.52),
            extents=(width * 0.78, height * 0.34, max(depth * 0.08, 0.04)),
            tags=[*list(component.tags), "front_door"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.40, cz + depth * 0.56),
            extents=(width * 0.52, height * 0.12, max(depth * 0.06, 0.035)),
            tags=[*list(component.tags), "control_panel"],
        ),
        _box(
            component.part,
            component,
            center=(cx + width * 0.42, cy + height * 0.08, cz),
            extents=(max(width * 0.06, 0.04), height * 0.70, depth * 0.82),
            tags=[*list(component.tags), "side_vent"],
        ),
    ]


def _lamp_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    radius = component.radius if component.radius is not None else max(min(width, depth) * 0.28, 0.05)
    lamp_h = component.height if component.height is not None else height
    return [
        _cylinder(
            component.part,
            component,
            center=(cx, cy - lamp_h * 0.42, cz),
            radius=radius * 1.25,
            height=max(lamp_h * 0.08, 0.05),
            axis="y",
            tags=[*list(component.tags), "lamp_base"],
        ),
        _cylinder(
            component.part,
            component,
            center=(cx, cy - lamp_h * 0.10, cz),
            radius=radius * 0.30,
            height=lamp_h * 0.60,
            axis="y",
            tags=[*list(component.tags), "lamp_stem"],
        ),
        _cylinder(
            component.part,
            component,
            center=(cx, cy + lamp_h * 0.28, cz),
            radius=radius * 1.55,
            height=max(lamp_h * 0.22, 0.08),
            axis="y",
            tags=[*list(component.tags), "shade", "emissive"],
        ),
        _cylinder(
            component.part,
            component,
            center=(cx, cy + lamp_h * 0.22, cz),
            radius=radius * 0.68,
            height=max(lamp_h * 0.08, 0.05),
            axis="y",
            tags=[*list(component.tags), "glow_core", "emissive"],
        ),
    ]


def _foliage_ground_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    return [
        _box(component.part, component, tags=[*list(component.tags), "soil_patch"]),
        _box(
            component.part,
            component,
            center=(cx - width * 0.18, cy + height * 0.36, cz + depth * 0.16),
            extents=(width * 0.30, max(height * 0.28, 0.035), depth * 0.22),
            tags=[*list(component.tags), "raised_moss_patch"],
        ),
        _box(
            component.part,
            component,
            center=(cx + width * 0.24, cy + height * 0.30, cz - depth * 0.14),
            extents=(width * 0.24, max(height * 0.20, 0.03), depth * 0.18),
            tags=[*list(component.tags), "leaf_litter_patch"],
        ),
    ]


def _tree_trunk_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    radius = component.radius if component.radius is not None else max(min(width, depth) * 0.45, 0.06)
    trunk_height = component.height if component.height is not None else height
    primitives = [
        _cylinder(component.part, component, radius=radius, height=trunk_height, axis="y", tags=[*list(component.tags), "trunk_core"]),
        _cylinder(
            component.part,
            component,
            center=(cx, cy - trunk_height * 0.42, cz),
            radius=radius * 1.20,
            height=max(trunk_height * 0.12, 0.08),
            axis="y",
            tags=[*list(component.tags), "trunk_flare"],
        ),
    ]
    for index, angle in enumerate((0.0, math.tau / 3.0, math.tau * 2.0 / 3.0)):
        primitives.append(
            _box(
                component.part,
                component,
                center=(cx + math.cos(angle) * radius * 0.72, cy, cz + math.sin(angle) * radius * 0.72),
                extents=(radius * 0.24, trunk_height * 0.92, radius * 0.22),
                tags=[*list(component.tags), "bark_ridge", f"ridge_{index}"],
            )
        )
    return primitives


def _root_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    radius = component.radius if component.radius is not None else max(min(height, depth) * 0.42, 0.035)
    root_length = component.height if component.height is not None else max(width, depth)
    axis = "x" if width >= depth else "z"
    return [
        _cylinder(component.part, component, radius=radius, height=root_length, axis=axis, tags=[*list(component.tags), "root_runner"]),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.28, cz),
            extents=(width * 0.84, max(height * 0.18, 0.035), depth * 0.84),
            tags=[*list(component.tags), "surface_root_ridge"],
        ),
    ]


def _tree_branch_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    radius = component.radius if component.radius is not None else max(min(height, depth) * 0.42, 0.035)
    branch_length = component.height if component.height is not None else max(width, depth)
    axis = component.axis if component.axis in {"x", "y", "z"} else "x"
    return [
        _cylinder(component.part, component, radius=radius, height=branch_length, axis=axis, tags=[*list(component.tags), "branch_core"]),
        _box(
            component.part,
            component,
            center=(component.center[0], component.center[1] + height * 0.22, component.center[2]),
            extents=(width * 0.44, max(height * 0.18, 0.035), depth * 1.40),
            tags=[*list(component.tags), "twig_fork"],
        ),
    ]


def _leaf_cluster_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    radius = component.radius if component.radius is not None else max(min(width, depth) * 0.48, 0.08)
    return [
        _cylinder(component.part, component, radius=radius, height=max(height * 0.62, 0.08), axis="y", tags=[*list(component.tags), "leaf_mass"]),
        _box(
            component.part,
            component,
            center=(cx - width * 0.20, cy + height * 0.08, cz),
            extents=(width * 0.62, height * 0.44, depth * 0.74),
            tags=[*list(component.tags), "left_leaf_lobe"],
        ),
        _box(
            component.part,
            component,
            center=(cx + width * 0.20, cy - height * 0.04, cz),
            extents=(width * 0.62, height * 0.40, depth * 0.68),
            tags=[*list(component.tags), "right_leaf_lobe"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.26, cz + depth * 0.16),
            extents=(width * 0.54, height * 0.34, depth * 0.46),
            tags=[*list(component.tags), "crown_leaf_lobe"],
        ),
    ]


def _bush_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    return [
        _cylinder(component.part, component, radius=max(min(width, depth) * 0.46, 0.08), height=max(height * 0.70, 0.08), axis="y", tags=[*list(component.tags), "shrub_core"]),
        _box(component.part, component, center=(cx - width * 0.18, cy, cz), extents=(width * 0.62, height * 0.62, depth * 0.52), tags=[*list(component.tags), "left_shrub_mass"]),
        _box(component.part, component, center=(cx + width * 0.18, cy + height * 0.08, cz + depth * 0.08), extents=(width * 0.58, height * 0.58, depth * 0.56), tags=[*list(component.tags), "right_shrub_mass"]),
    ]


def _grass_clump_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    primitives: list[ShapePrimitive] = []
    blade_count = 5
    for index in range(blade_count):
        t = (index - (blade_count - 1) / 2.0) / max(1.0, (blade_count - 1) / 2.0)
        primitives.append(
            _box(
                component.part,
                component,
                center=(cx + t * width * 0.30, cy + height * (0.05 * (index % 2)), cz + t * depth * 0.12),
                extents=(max(width * 0.10, 0.025), height * (0.70 + 0.06 * (index % 3)), max(depth * 0.12, 0.025)),
                tags=[*list(component.tags), "grass_blade", f"blade_{index}"],
            )
        )
    return primitives


def _natural_rock_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    return [
        _box(component.part, component, tags=[*list(component.tags), "rock_core"]),
        _box(
            component.part,
            component,
            center=(cx - width * 0.18, cy + height * 0.22, cz + depth * 0.08),
            extents=(width * 0.52, height * 0.58, depth * 0.64),
            tags=[*list(component.tags), "upper_facet"],
        ),
        _box(
            component.part,
            component,
            center=(cx + width * 0.24, cy - height * 0.12, cz - depth * 0.14),
            extents=(width * 0.48, height * 0.42, depth * 0.52),
            tags=[*list(component.tags), "lower_facet"],
        ),
    ]


def _mushroom_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    radius = component.radius if component.radius is not None else max(min(width, depth) * 0.24, 0.035)
    mushroom_height = component.height if component.height is not None else height
    return [
        _cylinder(
            component.part,
            component,
            center=(component.center[0], component.center[1] - mushroom_height * 0.16, component.center[2]),
            radius=radius * 0.48,
            height=mushroom_height * 0.62,
            axis="y",
            tags=[*list(component.tags), "stem"],
        ),
        _cylinder(
            component.part,
            component,
            center=(component.center[0], component.center[1] + mushroom_height * 0.24, component.center[2]),
            radius=radius * 1.55,
            height=max(mushroom_height * 0.26, 0.06),
            axis="y",
            tags=[*list(component.tags), "cap"],
        ),
        _box(
            component.part,
            component,
            center=(component.center[0], component.center[1] + mushroom_height * 0.12, component.center[2]),
            extents=(radius * 2.2, max(mushroom_height * 0.05, 0.035), radius * 1.6),
            tags=[*list(component.tags), "gills"],
        ),
    ]


def _fallen_log_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    radius = component.radius if component.radius is not None else max(min(component.extents[1], component.extents[2]) * 0.42, 0.06)
    log_length = component.height if component.height is not None else component.extents[0]
    return [
        _cylinder(component.part, component, radius=radius, height=log_length, axis=component.axis, tags=[*list(component.tags), "log_body"]),
        _cylinder(
            component.part,
            component,
            center=(component.center[0] - log_length * 0.48 if component.axis == "x" else component.center[0], component.center[1], component.center[2]),
            radius=radius * 0.92,
            height=max(log_length * 0.05, 0.04),
            axis=component.axis,
            tags=[*list(component.tags), "cut_end_a"],
        ),
        _cylinder(
            component.part,
            component,
            center=(component.center[0] + log_length * 0.48 if component.axis == "x" else component.center[0], component.center[1], component.center[2]),
            radius=radius * 0.92,
            height=max(log_length * 0.05, 0.04),
            axis=component.axis,
            tags=[*list(component.tags), "cut_end_b"],
        ),
    ]


def _vine_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    radius = component.radius if component.radius is not None else max(min(component.extents[0], component.extents[2]) * 0.34, 0.018)
    vine_height = component.height if component.height is not None else component.extents[1]
    return [
        _cylinder(component.part, component, radius=radius, height=vine_height, axis="y", tags=[*list(component.tags), "vine_line"]),
        _box(
            component.part,
            component,
            center=(component.center[0] + component.extents[0] * 0.26, component.center[1] + vine_height * 0.10, component.center[2]),
            extents=(component.extents[0] * 0.70, max(vine_height * 0.04, 0.035), component.extents[2] * 0.80),
            tags=[*list(component.tags), "leaf_sprig"],
        ),
    ]


def _flower_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    radius = component.radius if component.radius is not None else max(min(width, depth) * 0.28, 0.025)
    stem_h = component.height if component.height is not None else height * 0.72
    primitives = [
        _cylinder(component.part, component, center=(cx, cy - stem_h * 0.18, cz), radius=radius * 0.32, height=stem_h, axis="y", tags=[*list(component.tags), "stem"]),
        _cylinder(component.part, component, center=(cx, cy + stem_h * 0.34, cz), radius=radius, height=max(height * 0.05, 0.03), axis="y", tags=[*list(component.tags), "flower_center"]),
    ]
    for index, angle in enumerate((0.0, math.tau / 3.0, math.tau * 2.0 / 3.0)):
        primitives.append(
            _box(
                component.part,
                component,
                center=(cx + math.cos(angle) * radius * 0.9, cy + stem_h * 0.34, cz + math.sin(angle) * radius * 0.9),
                extents=(radius * 0.85, max(height * 0.035, 0.025), radius * 0.55),
                tags=[*list(component.tags), "petal", f"petal_{index}"],
            )
        )
    return primitives


def _planter_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    return [
        _box(component.part, component, tags=[*list(component.tags), "planter_box"]),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.40, cz),
            extents=(width * 0.82, max(height * 0.18, 0.05), depth * 0.82),
            tags=[*list(component.tags), "soil_insert"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.52, cz),
            extents=(width * 1.08, max(height * 0.12, 0.04), depth * 1.08),
            tags=[*list(component.tags), "rim"],
        ),
    ]


def _urban_base_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    curb_h = max(height * 0.55, 0.04)
    curb_w = max(width * 0.045, 0.06)
    return [
        _box(component.part, component, tags=[*list(component.tags), "sidewalk_slab"]),
        _box(
            component.part,
            component,
            center=(cx - width * 0.46, cy + curb_h * 0.42, cz),
            extents=(curb_w, curb_h, depth),
            tags=[*list(component.tags), "left_curb"],
        ),
        _box(
            component.part,
            component,
            center=(cx + width * 0.46, cy + curb_h * 0.42, cz),
            extents=(curb_w, curb_h, depth),
            tags=[*list(component.tags), "right_curb"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy + curb_h * 0.35, cz + depth * 0.46),
            extents=(width, curb_h * 0.72, max(depth * 0.045, 0.06)),
            tags=[*list(component.tags), "front_lip"],
        ),
    ]


def _fence_segment_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    post_w = max(width * 0.08, 0.05)
    rail_h = max(height * 0.08, 0.035)
    return [
        _box(
            component.part,
            component,
            center=(cx - width * 0.44, cy, cz),
            extents=(post_w, height, depth * 1.25),
            tags=[*list(component.tags), "left_post"],
        ),
        _box(
            component.part,
            component,
            center=(cx + width * 0.44, cy, cz),
            extents=(post_w, height, depth * 1.25),
            tags=[*list(component.tags), "right_post"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.28, cz),
            extents=(width, rail_h, depth),
            tags=[*list(component.tags), "top_rail"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy - height * 0.18, cz),
            extents=(width, rail_h, depth),
            tags=[*list(component.tags), "lower_rail"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.02, cz),
            extents=(post_w * 0.70, height * 0.76, depth * 0.80),
            tags=[*list(component.tags), "center_picket"],
        ),
    ]


def _gate_panel_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    frame_w = max(width * 0.10, 0.05)
    frame_h = max(height * 0.08, 0.04)
    primitives = [
        _box(component.part, component, tags=[*list(component.tags), "gate_slab"]),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.43, cz + depth * 0.08),
            extents=(width, frame_h, depth * 1.20),
            tags=[*list(component.tags), "top_frame"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy - height * 0.43, cz + depth * 0.08),
            extents=(width, frame_h, depth * 1.20),
            tags=[*list(component.tags), "bottom_frame"],
        ),
        _box(
            component.part,
            component,
            center=(cx - width * 0.44, cy, cz + depth * 0.08),
            extents=(frame_w, height, depth * 1.20),
            tags=[*list(component.tags), "hinge_side_frame"],
        ),
        _box(
            component.part,
            component,
            center=(cx + width * 0.44, cy, cz + depth * 0.08),
            extents=(frame_w, height, depth * 1.20),
            tags=[*list(component.tags), "latch_side_frame"],
        ),
    ]
    for index, offset in enumerate((-0.20, 0.0, 0.20)):
        primitives.append(
            _box(
                component.part,
                component,
                center=(cx + width * offset, cy, cz + depth * 0.12),
                extents=(frame_w * 0.52, height * 0.78, depth * 0.82),
                tags=[*list(component.tags), "vertical_bar", f"bar_{index}"],
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
        _cylinder(
            component.part,
            component,
            center=(cx, cy - height * 0.08, cz),
            radius=radius,
            height=post_h,
            axis="y",
            tags=[*list(component.tags), "post"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.26, cz + depth * 0.05),
            extents=(board_w, board_h, max(depth * 0.75, 0.05)),
            tags=[*list(component.tags), "sign_board", "label_zone"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.26, cz + depth * 0.42),
            extents=(board_w * 0.78, board_h * 0.18, max(depth * 0.18, 0.035)),
            tags=[*list(component.tags), "painted_label_strip"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy - post_h * 0.52, cz),
            extents=(width * 0.62, max(height * 0.045, 0.035), width * 0.62),
            tags=[*list(component.tags), "mount_plate"],
        ),
    ]


def _streetlight_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    radius = component.radius if component.radius is not None else max(width * 0.11, 0.035)
    pole_h = component.height if component.height is not None else height * 0.94
    return [
        _cylinder(
            component.part,
            component,
            center=(cx, cy - height * 0.03, cz),
            radius=radius,
            height=pole_h,
            axis="y",
            tags=[*list(component.tags), "lamp_pole"],
        ),
        _box(
            component.part,
            component,
            center=(cx + width * 0.42, cy + height * 0.33, cz),
            extents=(width * 0.92, max(height * 0.045, 0.04), max(depth * 0.42, 0.04)),
            tags=[*list(component.tags), "curved_arm"],
        ),
        _box(
            component.part,
            component,
            center=(cx + width * 0.86, cy + height * 0.22, cz),
            extents=(width * 0.48, height * 0.13, depth * 0.62),
            tags=[*list(component.tags), "lamp_head"],
        ),
        _box(
            component.part,
            component,
            center=(cx + width * 0.86, cy + height * 0.14, cz),
            extents=(width * 0.36, height * 0.055, depth * 0.45),
            tags=[*list(component.tags), "glow_panel", "emissive"],
        ),
        _cylinder(
            component.part,
            component,
            center=(cx, cy - pole_h * 0.50, cz),
            radius=radius * 2.2,
            height=max(height * 0.06, 0.04),
            axis="y",
            tags=[*list(component.tags), "base_flange"],
        ),
    ]


def _street_bench_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    slat_h = max(height * 0.12, 0.035)
    return [
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.08, cz),
            extents=(width, slat_h, depth * 0.70),
            tags=[*list(component.tags), "seat_plank"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.38, cz - depth * 0.34),
            extents=(width, slat_h, depth * 0.30),
            tags=[*list(component.tags), "back_plank"],
        ),
        _box(
            component.part,
            component,
            center=(cx - width * 0.34, cy - height * 0.18, cz),
            extents=(width * 0.08, height * 0.44, depth * 0.16),
            tags=[*list(component.tags), "left_leg"],
        ),
        _box(
            component.part,
            component,
            center=(cx + width * 0.34, cy - height * 0.18, cz),
            extents=(width * 0.08, height * 0.44, depth * 0.16),
            tags=[*list(component.tags), "right_leg"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.18, cz - depth * 0.10),
            extents=(width * 0.92, max(height * 0.055, 0.03), depth * 0.12),
            tags=[*list(component.tags), "middle_slat"],
        ),
    ]


def _trash_bin_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    radius = component.radius if component.radius is not None else max(min(width, depth) * 0.42, 0.05)
    bin_h = component.height if component.height is not None else height
    return [
        _cylinder(
            component.part,
            component,
            radius=radius,
            height=bin_h,
            axis="y",
            tags=[*list(component.tags), "bin_body"],
        ),
        _cylinder(
            component.part,
            component,
            center=(cx, cy + bin_h * 0.46, cz),
            radius=radius * 1.08,
            height=max(height * 0.08, 0.045),
            axis="y",
            tags=[*list(component.tags), "lid"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.18, cz + radius * 0.88),
            extents=(width * 0.58, height * 0.11, max(depth * 0.08, 0.035)),
            tags=[*list(component.tags), "front_slot"],
        ),
    ]


def _utility_pole_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    radius = component.radius if component.radius is not None else max(width * 0.18, 0.04)
    pole_h = component.height if component.height is not None else height
    return [
        _cylinder(component.part, component, radius=radius, height=pole_h, axis="y", tags=[*list(component.tags), "pole"]),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.28, cz),
            extents=(width * 2.30, max(height * 0.055, 0.04), depth * 0.42),
            tags=[*list(component.tags), "crossbar"],
        ),
        _cylinder(
            component.part,
            component,
            center=(cx - width * 0.70, cy + height * 0.32, cz),
            radius=radius * 0.42,
            height=max(height * 0.09, 0.05),
            axis="y",
            tags=[*list(component.tags), "left_insulator"],
        ),
        _cylinder(
            component.part,
            component,
            center=(cx + width * 0.70, cy + height * 0.32, cz),
            radius=radius * 0.42,
            height=max(height * 0.09, 0.05),
            axis="y",
            tags=[*list(component.tags), "right_insulator"],
        ),
    ]


def _cable_span_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    radius = component.radius if component.radius is not None else max(min(height, depth) * 0.38, 0.018)
    span = component.height if component.height is not None else width
    return [
        _cylinder(
            component.part,
            component,
            radius=radius,
            height=span,
            axis=component.axis,
            tags=[*list(component.tags), "main_wire"],
        ),
        _box(
            component.part,
            component,
            center=(component.center[0], component.center[1] - max(height * 0.50, 0.035), component.center[2]),
            extents=(width * 0.84, max(height * 0.12, 0.025), depth * 0.70),
            tags=[*list(component.tags), "sag_shadow"],
        ),
    ]


def _kiosk_body_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    return [
        _box(component.part, component, tags=[*list(component.tags), "kiosk_shell"]),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.08, cz + depth * 0.52),
            extents=(width * 0.62, height * 0.28, max(depth * 0.07, 0.04)),
            tags=[*list(component.tags), "service_window", "glass"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.52, cz + depth * 0.10),
            extents=(width * 1.12, height * 0.12, depth * 1.16),
            tags=[*list(component.tags), "roof_cap"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.28, cz + depth * 0.63),
            extents=(width * 0.92, height * 0.08, depth * 0.20),
            tags=[*list(component.tags), "awning", "canopy"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy - height * 0.12, cz + depth * 0.56),
            extents=(width * 0.82, height * 0.12, depth * 0.22),
            tags=[*list(component.tags), "counter"],
        ),
    ]


def _market_stall_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    post_w = max(width * 0.055, 0.035)
    return [
        _box(
            component.part,
            component,
            center=(cx, cy - height * 0.18, cz),
            extents=(width, height * 0.18, depth * 0.82),
            tags=[*list(component.tags), "display_table"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.35, cz),
            extents=(width * 1.08, height * 0.12, depth * 1.08),
            tags=[*list(component.tags), "fabric_canopy", "canopy"],
        ),
        _box(component.part, component, center=(cx - width * 0.44, cy + height * 0.04, cz - depth * 0.34), extents=(post_w, height * 0.82, post_w), tags=[*list(component.tags), "front_left_post"]),
        _box(component.part, component, center=(cx + width * 0.44, cy + height * 0.04, cz - depth * 0.34), extents=(post_w, height * 0.82, post_w), tags=[*list(component.tags), "front_right_post"]),
        _box(component.part, component, center=(cx - width * 0.44, cy + height * 0.04, cz + depth * 0.34), extents=(post_w, height * 0.82, post_w), tags=[*list(component.tags), "rear_left_post"]),
        _box(component.part, component, center=(cx + width * 0.44, cy + height * 0.04, cz + depth * 0.34), extents=(post_w, height * 0.82, post_w), tags=[*list(component.tags), "rear_right_post"]),
        _box(
            component.part,
            component,
            center=(cx - width * 0.18, cy - height * 0.02, cz + depth * 0.10),
            extents=(width * 0.22, height * 0.12, depth * 0.20),
            tags=[*list(component.tags), "goods_bin_a"],
        ),
        _box(
            component.part,
            component,
            center=(cx + width * 0.18, cy - height * 0.02, cz - depth * 0.08),
            extents=(width * 0.22, height * 0.12, depth * 0.20),
            tags=[*list(component.tags), "goods_bin_b"],
        ),
    ]


def _street_barrier_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    return [
        _box(component.part, component, tags=[*list(component.tags), "barrier_body"]),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.18, cz + depth * 0.52),
            extents=(width * 0.82, height * 0.13, max(depth * 0.12, 0.035)),
            tags=[*list(component.tags), "warning_stripe"],
        ),
        _box(
            component.part,
            component,
            center=(cx - width * 0.34, cy - height * 0.48, cz),
            extents=(width * 0.16, height * 0.20, depth * 1.12),
            tags=[*list(component.tags), "left_foot"],
        ),
        _box(
            component.part,
            component,
            center=(cx + width * 0.34, cy - height * 0.48, cz),
            extents=(width * 0.16, height * 0.20, depth * 1.12),
            tags=[*list(component.tags), "right_foot"],
        ),
    ]


def _street_crate_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    return [
        _box(component.part, component, tags=[*list(component.tags), "crate_body"]),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.44, cz),
            extents=(width * 1.04, max(height * 0.12, 0.035), depth * 1.04),
            tags=[*list(component.tags), "lid_slats"],
        ),
        _box(
            component.part,
            component,
            center=(cx - width * 0.42, cy, cz + depth * 0.50),
            extents=(max(width * 0.08, 0.035), height * 0.92, max(depth * 0.08, 0.035)),
            tags=[*list(component.tags), "front_left_slat"],
        ),
        _box(
            component.part,
            component,
            center=(cx + width * 0.42, cy, cz + depth * 0.50),
            extents=(max(width * 0.08, 0.035), height * 0.92, max(depth * 0.08, 0.035)),
            tags=[*list(component.tags), "front_right_slat"],
        ),
    ]


def _bollard_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    radius = component.radius if component.radius is not None else max(min(width, depth) * 0.36, 0.04)
    bollard_h = component.height if component.height is not None else height
    return [
        _cylinder(component.part, component, radius=radius, height=bollard_h, axis="y", tags=[*list(component.tags), "post"]),
        _cylinder(
            component.part,
            component,
            center=(cx, cy + bollard_h * 0.48, cz),
            radius=radius * 1.08,
            height=max(height * 0.07, 0.035),
            axis="y",
            tags=[*list(component.tags), "cap"],
        ),
        _cylinder(
            component.part,
            component,
            center=(cx, cy - bollard_h * 0.48, cz),
            radius=radius * 1.45,
            height=max(height * 0.08, 0.035),
            axis="y",
            tags=[*list(component.tags), "base_plate"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.10, cz + radius * 0.70),
            extents=(radius * 1.20, max(height * 0.08, 0.03), max(depth * 0.08, 0.025)),
            tags=[*list(component.tags), "reflective_band", "warning"],
        ),
    ]


def _infrastructure_base_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    trench_w = max(width * 0.72, 0.10)
    curb_h = max(height * 0.50, 0.035)
    return [
        _box(component.part, component, tags=[*list(component.tags), "service_slab"]),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.38, cz),
            extents=(trench_w, max(height * 0.28, 0.035), depth * 0.36),
            tags=[*list(component.tags), "service_trench"],
        ),
        _box(
            component.part,
            component,
            center=(cx - width * 0.46, cy + curb_h * 0.34, cz),
            extents=(max(width * 0.04, 0.05), curb_h, depth),
            tags=[*list(component.tags), "left_service_edge"],
        ),
        _box(
            component.part,
            component,
            center=(cx + width * 0.46, cy + curb_h * 0.34, cz),
            extents=(max(width * 0.04, 0.05), curb_h, depth),
            tags=[*list(component.tags), "right_service_edge"],
        ),
    ]


def _pipe_run_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    radius = component.radius if component.radius is not None else max(min(height, depth) * 0.42, 0.045)
    pipe_length = component.height if component.height is not None else max(width, depth)
    return [
        _cylinder(component.part, component, radius=radius, height=pipe_length, axis=component.axis, tags=[*list(component.tags), "pipe_body"]),
        _cylinder(
            component.part,
            component,
            center=(cx - pipe_length * 0.36 if component.axis == "x" else cx, cy, cz),
            radius=radius * 1.24,
            height=max(pipe_length * 0.045, 0.05),
            axis=component.axis,
            tags=[*list(component.tags), "left_coupler"],
        ),
        _cylinder(
            component.part,
            component,
            center=(cx + pipe_length * 0.36 if component.axis == "x" else cx, cy, cz),
            radius=radius * 1.24,
            height=max(pipe_length * 0.045, 0.05),
            axis=component.axis,
            tags=[*list(component.tags), "right_coupler"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy - radius * 0.92, cz),
            extents=(pipe_length * 0.76 if component.axis == "x" else width, max(radius * 0.32, 0.025), depth * 0.72),
            tags=[*list(component.tags), "pipe_shadow_pad"],
        ),
    ]


def _duct_run_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    seam = max(height * 0.10, 0.035)
    return [
        _box(component.part, component, tags=[*list(component.tags), "duct_body"]),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.42, cz),
            extents=(width * 0.94, seam, depth * 1.06),
            tags=[*list(component.tags), "top_flange"],
        ),
        _box(
            component.part,
            component,
            center=(cx - width * 0.28, cy, cz + depth * 0.52),
            extents=(width * 0.08, height * 0.58, max(depth * 0.08, 0.035)),
            tags=[*list(component.tags), "inspection_seam_a"],
        ),
        _box(
            component.part,
            component,
            center=(cx + width * 0.28, cy, cz + depth * 0.52),
            extents=(width * 0.08, height * 0.58, max(depth * 0.08, 0.035)),
            tags=[*list(component.tags), "inspection_seam_b"],
        ),
    ]


def _overhead_conduit_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    radius = component.radius if component.radius is not None else max(min(height, depth) * 0.40, 0.035)
    conduit_length = component.height if component.height is not None else width
    return [
        _cylinder(component.part, component, radius=radius, height=conduit_length, axis=component.axis, tags=[*list(component.tags), "conduit_body"]),
        _box(
            component.part,
            component,
            center=(cx - conduit_length * 0.28 if component.axis == "x" else cx, cy - radius * 1.2, cz),
            extents=(max(conduit_length * 0.05, 0.04), radius * 0.60, radius * 2.4),
            tags=[*list(component.tags), "hanger_clamp_a"],
        ),
        _box(
            component.part,
            component,
            center=(cx + conduit_length * 0.28 if component.axis == "x" else cx, cy - radius * 1.2, cz),
            extents=(max(conduit_length * 0.05, 0.04), radius * 0.60, radius * 2.4),
            tags=[*list(component.tags), "hanger_clamp_b"],
        ),
    ]


def _drain_channel_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    primitives = [
        _box(component.part, component, tags=[*list(component.tags), "drain_trough"]),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.46, cz),
            extents=(width * 1.04, max(height * 0.12, 0.035), depth * 1.05),
            tags=[*list(component.tags), "drain_frame"],
        ),
    ]
    grate_count = 5
    for index in range(grate_count):
        x = cx - width * 0.40 + width * 0.80 * (index / max(1, grate_count - 1))
        primitives.append(
            _box(
                component.part,
                component,
                center=(x, cy + height * 0.52, cz),
                extents=(max(width * 0.055, 0.03), max(height * 0.10, 0.03), depth * 0.92),
                tags=[*list(component.tags), "grate_bar", f"bar_{index}"],
            )
        )
    return primitives


def _fire_hydrant_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    radius = component.radius if component.radius is not None else max(min(width, depth) * 0.32, 0.04)
    hydrant_h = component.height if component.height is not None else height
    return [
        _cylinder(
            component.part,
            component,
            center=(cx, cy, cz),
            radius=radius,
            height=hydrant_h,
            axis="y",
            tags=[*list(component.tags), "hydrant_body"],
        ),
        _cylinder(
            component.part,
            component,
            center=(cx, cy + hydrant_h * 0.44, cz),
            radius=radius * 1.05,
            height=max(hydrant_h * 0.12, 0.05),
            axis="y",
            tags=[*list(component.tags), "cap"],
        ),
        _cylinder(
            component.part,
            component,
            center=(cx - radius * 1.40, cy + hydrant_h * 0.10, cz),
            radius=radius * 0.42,
            height=radius * 1.50,
            axis="x",
            tags=[*list(component.tags), "left_nozzle"],
        ),
        _cylinder(
            component.part,
            component,
            center=(cx + radius * 1.40, cy + hydrant_h * 0.10, cz),
            radius=radius * 0.42,
            height=radius * 1.50,
            axis="x",
            tags=[*list(component.tags), "right_nozzle"],
        ),
        _cylinder(
            component.part,
            component,
            center=(cx, cy - hydrant_h * 0.48, cz),
            radius=radius * 1.30,
            height=max(hydrant_h * 0.09, 0.04),
            axis="y",
            tags=[*list(component.tags), "base_flange"],
        ),
    ]


def _transformer_box_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    return [
        _box(component.part, component, tags=[*list(component.tags), "transformer_cabinet"]),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.08, cz + depth * 0.52),
            extents=(width * 0.78, height * 0.52, max(depth * 0.08, 0.04)),
            tags=[*list(component.tags), "front_access_panel"],
        ),
        _box(
            component.part,
            component,
            center=(cx - width * 0.42, cy + height * 0.08, cz),
            extents=(max(width * 0.08, 0.04), height * 0.56, depth * 0.76),
            tags=[*list(component.tags), "side_vents"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.18, cz + depth * 0.58),
            extents=(width * 0.42, height * 0.10, max(depth * 0.07, 0.035)),
            tags=[*list(component.tags), "warning_label"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy - height * 0.46, cz),
            extents=(width * 1.08, max(height * 0.10, 0.05), depth * 1.05),
            tags=[*list(component.tags), "concrete_pad"],
        ),
    ]


def _junction_box_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    return [
        _box(component.part, component, tags=[*list(component.tags), "junction_body"]),
        _box(
            component.part,
            component,
            center=(cx, cy, cz + depth * 0.52),
            extents=(width * 0.82, height * 0.72, max(depth * 0.08, 0.035)),
            tags=[*list(component.tags), "removable_lid"],
        ),
        _box(
            component.part,
            component,
            center=(cx - width * 0.52, cy, cz),
            extents=(max(width * 0.10, 0.035), height * 0.22, depth * 0.42),
            tags=[*list(component.tags), "left_port"],
        ),
        _box(
            component.part,
            component,
            center=(cx + width * 0.52, cy, cz),
            extents=(max(width * 0.10, 0.035), height * 0.22, depth * 0.42),
            tags=[*list(component.tags), "right_port"],
        ),
    ]


def _valve_wheel_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    radius = component.radius if component.radius is not None else max(min(width, depth) * 0.36, 0.05)
    wheel_h = component.height if component.height is not None else max(height * 0.10, 0.035)
    return [
        _cylinder(component.part, component, radius=radius, height=wheel_h, axis=component.axis, tags=[*list(component.tags), "wheel_rim"]),
        _cylinder(
            component.part,
            component,
            center=(cx, cy, cz),
            radius=radius * 0.26,
            height=wheel_h * 1.35,
            axis=component.axis,
            tags=[*list(component.tags), "center_hub"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy, cz),
            extents=(radius * 1.70, max(height * 0.08, 0.025), max(depth * 0.12, 0.025)),
            tags=[*list(component.tags), "horizontal_spoke"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy, cz),
            extents=(max(width * 0.12, 0.025), max(height * 0.08, 0.025), radius * 1.70),
            tags=[*list(component.tags), "vertical_spoke"],
        ),
        _cylinder(
            component.part,
            component,
            center=(cx, cy - height * 0.46, cz),
            radius=radius * 0.22,
            height=max(height * 0.72, 0.08),
            axis="y",
            tags=[*list(component.tags), "valve_stem"],
        ),
    ]


def _manhole_cover_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    radius = component.radius if component.radius is not None else max(min(component.extents[0], component.extents[2]) * 0.45, 0.06)
    cover_h = component.height if component.height is not None else max(component.extents[1], 0.035)
    cx, cy, cz = component.center
    return [
        _cylinder(component.part, component, radius=radius, height=cover_h, axis="y", tags=[*list(component.tags), "cover_disc"]),
        _cylinder(
            component.part,
            component,
            center=(cx, cy + cover_h * 0.40, cz),
            radius=radius * 1.08,
            height=max(cover_h * 0.42, 0.025),
            axis="y",
            tags=[*list(component.tags), "outer_rim"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy + cover_h * 0.70, cz),
            extents=(radius * 1.35, max(cover_h * 0.28, 0.02), radius * 0.16),
            tags=[*list(component.tags), "access_groove_a"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy + cover_h * 0.70, cz),
            extents=(radius * 0.16, max(cover_h * 0.28, 0.02), radius * 1.35),
            tags=[*list(component.tags), "access_groove_b"],
        ),
    ]


def _service_rail_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    return [
        _box(component.part, component, tags=[*list(component.tags), "rail_body"]),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.38, cz),
            extents=(width, max(height * 0.18, 0.035), depth * 0.42),
            tags=[*list(component.tags), "top_lip"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy - height * 0.38, cz),
            extents=(width, max(height * 0.18, 0.035), depth * 0.42),
            tags=[*list(component.tags), "bottom_lip"],
        ),
    ]


def _support_bracket_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    return [
        _box(component.part, component, tags=[*list(component.tags), "vertical_support"]),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.35, cz),
            extents=(width * 2.0, max(height * 0.14, 0.035), depth * 1.2),
            tags=[*list(component.tags), "saddle"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy - height * 0.48, cz),
            extents=(width * 1.70, max(height * 0.12, 0.035), depth * 1.45),
            tags=[*list(component.tags), "mount_foot"],
        ),
    ]


def _cable_tray_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    primitives = [
        _box(
            component.part,
            component,
            center=(cx, cy - height * 0.22, cz),
            extents=(width, max(height * 0.18, 0.035), depth),
            tags=[*list(component.tags), "tray_floor"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.10, cz - depth * 0.46),
            extents=(width, height * 0.62, max(depth * 0.10, 0.035)),
            tags=[*list(component.tags), "left_sidewall"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.10, cz + depth * 0.46),
            extents=(width, height * 0.62, max(depth * 0.10, 0.035)),
            tags=[*list(component.tags), "right_sidewall"],
        ),
    ]
    for index, z_offset in enumerate((-0.20, 0.0, 0.20)):
        primitives.append(
            _cylinder(
                component.part,
                component,
                center=(cx, cy + height * 0.04, cz + depth * z_offset),
                radius=max(height * 0.08, 0.025),
                height=width * 0.92,
                axis="x",
                tags=[*list(component.tags), "bundled_cable", f"cable_{index}"],
            )
        )
    return primitives


def _access_base_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    return [
        _box(component.part, component, tags=[*list(component.tags), "access_floor_slab"]),
        _box(
            component.part,
            component,
            center=(cx - width * 0.36, cy + height * 0.44, cz - depth * 0.32),
            extents=(width * 0.18, max(height * 0.24, 0.035), depth * 0.18),
            tags=[*list(component.tags), "anchor_pad_a"],
        ),
        _box(
            component.part,
            component,
            center=(cx + width * 0.36, cy + height * 0.44, cz + depth * 0.32),
            extents=(width * 0.18, max(height * 0.24, 0.035), depth * 0.18),
            tags=[*list(component.tags), "anchor_pad_b"],
        ),
    ]


def _catwalk_deck_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    primitives = [
        _box(component.part, component, tags=[*list(component.tags), "deck_frame"]),
        _box(
            component.part,
            component,
            center=(cx, cy - height * 0.44, cz),
            extents=(width, max(height * 0.22, 0.035), depth * 0.18),
            tags=[*list(component.tags), "center_spine"],
        ),
    ]
    grate_count = 7
    for index in range(grate_count):
        x = cx - width * 0.42 + width * 0.84 * (index / max(1, grate_count - 1))
        primitives.append(
            _box(
                component.part,
                component,
                center=(x, cy + height * 0.24, cz),
                extents=(max(width * 0.045, 0.03), max(height * 0.12, 0.025), depth * 0.92),
                tags=[*list(component.tags), "grate_bar", f"grate_{index}"],
            )
        )
    return primitives


def _walkway_span_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    return [
        _box(component.part, component, tags=[*list(component.tags), "walkway_deck"]),
        _box(
            component.part,
            component,
            center=(cx, cy - height * 0.42, cz - depth * 0.42),
            extents=(width, max(height * 0.22, 0.035), depth * 0.18),
            tags=[*list(component.tags), "left_side_beam"],
        ),
        _box(
            component.part,
            component,
            center=(cx, cy - height * 0.42, cz + depth * 0.42),
            extents=(width, max(height * 0.22, 0.035), depth * 0.18),
            tags=[*list(component.tags), "right_side_beam"],
        ),
        _box(
            component.part,
            component,
            center=(cx - width * 0.24, cy - height * 0.14, cz),
            extents=(width * 0.06, height * 0.42, depth * 1.04),
            tags=[*list(component.tags), "cross_tie_a"],
        ),
        _box(
            component.part,
            component,
            center=(cx + width * 0.24, cy - height * 0.14, cz),
            extents=(width * 0.06, height * 0.42, depth * 1.04),
            tags=[*list(component.tags), "cross_tie_b"],
        ),
    ]


def _guardrail_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    post_w = max(width * 0.07, 0.035)
    rail_h = max(height * 0.08, 0.025)
    return [
        _box(component.part, component, center=(cx - width * 0.44, cy, cz), extents=(post_w, height, depth * 1.35), tags=[*list(component.tags), "left_post"]),
        _box(component.part, component, center=(cx + width * 0.44, cy, cz), extents=(post_w, height, depth * 1.35), tags=[*list(component.tags), "right_post"]),
        _box(component.part, component, center=(cx, cy + height * 0.38, cz), extents=(width, rail_h, depth), tags=[*list(component.tags), "top_rail"]),
        _box(component.part, component, center=(cx, cy + height * 0.02, cz), extents=(width, rail_h, depth), tags=[*list(component.tags), "mid_rail"]),
        _box(component.part, component, center=(cx, cy - height * 0.32, cz), extents=(width * 0.96, rail_h, depth), tags=[*list(component.tags), "kick_plate"]),
    ]


def _access_ladder_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    rail_w = max(width * 0.16, 0.035)
    primitives = [
        _box(component.part, component, center=(cx - width * 0.36, cy, cz), extents=(rail_w, height, depth), tags=[*list(component.tags), "left_side_rail"]),
        _box(component.part, component, center=(cx + width * 0.36, cy, cz), extents=(rail_w, height, depth), tags=[*list(component.tags), "right_side_rail"]),
    ]
    rung_count = 6
    for index in range(rung_count):
        y = cy - height * 0.38 + height * 0.76 * (index / max(1, rung_count - 1))
        primitives.append(
            _box(
                component.part,
                component,
                center=(cx, y, cz),
                extents=(width * 0.82, max(height * 0.035, 0.025), depth * 1.08),
                tags=[*list(component.tags), "rung", f"rung_{index}"],
            )
        )
    return primitives


def _access_ramp_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    primitives = [
        _box(component.part, component, tags=[*list(component.tags), "ramp_slab"]),
        _box(component.part, component, center=(cx, cy + height * 0.42, cz - depth * 0.45), extents=(width, max(height * 0.12, 0.035), depth * 0.12), tags=[*list(component.tags), "left_lip"]),
        _box(component.part, component, center=(cx, cy + height * 0.42, cz + depth * 0.45), extents=(width, max(height * 0.12, 0.035), depth * 0.12), tags=[*list(component.tags), "right_lip"]),
    ]
    tread_count = 5
    for index in range(tread_count):
        x = cx - width * 0.36 + width * 0.72 * (index / max(1, tread_count - 1))
        primitives.append(
            _box(
                component.part,
                component,
                center=(x, cy + height * 0.48, cz),
                extents=(max(width * 0.055, 0.03), max(height * 0.08, 0.025), depth * 0.82),
                tags=[*list(component.tags), "anti_slip_tread", f"tread_{index}"],
            )
        )
    return primitives


def _gantry_frame_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    post = max(min(width, depth) * 0.10, 0.04)
    return [
        _box(component.part, component, center=(cx - width * 0.44, cy, cz - depth * 0.38), extents=(post, height, post), tags=[*list(component.tags), "front_left_upright"]),
        _box(component.part, component, center=(cx + width * 0.44, cy, cz - depth * 0.38), extents=(post, height, post), tags=[*list(component.tags), "front_right_upright"]),
        _box(component.part, component, center=(cx - width * 0.44, cy, cz + depth * 0.38), extents=(post, height, post), tags=[*list(component.tags), "rear_left_upright"]),
        _box(component.part, component, center=(cx + width * 0.44, cy, cz + depth * 0.38), extents=(post, height, post), tags=[*list(component.tags), "rear_right_upright"]),
        _box(component.part, component, center=(cx, cy + height * 0.46, cz - depth * 0.38), extents=(width, max(height * 0.08, 0.035), post), tags=[*list(component.tags), "front_crossbeam"]),
        _box(component.part, component, center=(cx, cy + height * 0.46, cz + depth * 0.38), extents=(width, max(height * 0.08, 0.035), post), tags=[*list(component.tags), "rear_crossbeam"]),
        _box(component.part, component, center=(cx, cy, cz), extents=(width * 0.92, max(height * 0.055, 0.03), depth * 0.08), tags=[*list(component.tags), "diagonal_brace"]),
    ]


def _elevator_shaft_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    frame = max(width * 0.10, 0.04)
    return [
        _box(component.part, component, tags=[*list(component.tags), "shaft_volume"]),
        _box(component.part, component, center=(cx, cy, cz + depth * 0.52), extents=(width * 0.66, height * 0.72, max(depth * 0.08, 0.04)), tags=[*list(component.tags), "landing_door"]),
        _box(component.part, component, center=(cx - width * 0.38, cy, cz + depth * 0.56), extents=(frame, height * 0.92, max(depth * 0.06, 0.035)), tags=[*list(component.tags), "left_guide_rail"]),
        _box(component.part, component, center=(cx + width * 0.38, cy, cz + depth * 0.56), extents=(frame, height * 0.92, max(depth * 0.06, 0.035)), tags=[*list(component.tags), "right_guide_rail"]),
        _box(component.part, component, center=(cx, cy - height * 0.12, cz), extents=(width * 0.72, height * 0.30, depth * 0.64), tags=[*list(component.tags), "lift_cabin"]),
    ]


def _access_platform_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    return [
        _box(component.part, component, tags=[*list(component.tags), "platform_deck"]),
        _box(component.part, component, center=(cx, cy - height * 0.42, cz), extents=(width * 1.05, max(height * 0.22, 0.035), depth * 0.14), tags=[*list(component.tags), "front_truss"]),
        _box(component.part, component, center=(cx, cy - height * 0.42, cz), extents=(width * 0.14, max(height * 0.22, 0.035), depth * 1.05), tags=[*list(component.tags), "side_truss"]),
        _box(component.part, component, center=(cx + width * 0.34, cy + height * 0.42, cz + depth * 0.34), extents=(width * 0.16, max(height * 0.20, 0.035), depth * 0.16), tags=[*list(component.tags), "mount_pad"]),
    ]


def _tunnel_segment_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    wall = max(width * 0.08, 0.05)
    return [
        _box(component.part, component, center=(cx, cy - height * 0.42, cz), extents=(width, max(height * 0.16, 0.05), depth), tags=[*list(component.tags), "floor_plate"]),
        _box(component.part, component, center=(cx - width * 0.46, cy, cz), extents=(wall, height, depth), tags=[*list(component.tags), "left_wall"]),
        _box(component.part, component, center=(cx + width * 0.46, cy, cz), extents=(wall, height, depth), tags=[*list(component.tags), "right_wall"]),
        _box(component.part, component, center=(cx, cy + height * 0.46, cz), extents=(width, max(height * 0.16, 0.05), depth), tags=[*list(component.tags), "roof_plate"]),
        _box(component.part, component, center=(cx, cy + height * 0.22, cz + depth * 0.48), extents=(width * 0.62, height * 0.10, max(depth * 0.10, 0.035)), tags=[*list(component.tags), "light_strip"]),
    ]


def _scaffold_frame_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    post = max(min(width, depth) * 0.10, 0.035)
    return [
        _box(component.part, component, center=(cx - width * 0.42, cy, cz - depth * 0.38), extents=(post, height, post), tags=[*list(component.tags), "front_left_pole"]),
        _box(component.part, component, center=(cx + width * 0.42, cy, cz - depth * 0.38), extents=(post, height, post), tags=[*list(component.tags), "front_right_pole"]),
        _box(component.part, component, center=(cx - width * 0.42, cy, cz + depth * 0.38), extents=(post, height, post), tags=[*list(component.tags), "rear_left_pole"]),
        _box(component.part, component, center=(cx + width * 0.42, cy, cz + depth * 0.38), extents=(post, height, post), tags=[*list(component.tags), "rear_right_pole"]),
        _box(component.part, component, center=(cx, cy + height * 0.24, cz), extents=(width, max(height * 0.06, 0.03), depth * 0.10), tags=[*list(component.tags), "upper_crossbar"]),
        _box(component.part, component, center=(cx, cy - height * 0.18, cz), extents=(width, max(height * 0.06, 0.03), depth * 0.10), tags=[*list(component.tags), "lower_crossbar"]),
        _box(component.part, component, center=(cx, cy, cz), extents=(width * 0.86, max(height * 0.05, 0.03), depth * 0.08), tags=[*list(component.tags), "diagonal_brace"]),
    ]


def _safety_gate_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    frame_w = max(width * 0.10, 0.04)
    return [
        _box(component.part, component, tags=[*list(component.tags), "gate_panel"]),
        _box(component.part, component, center=(cx - width * 0.44, cy, cz), extents=(frame_w, height, depth * 1.20), tags=[*list(component.tags), "hinge_post"]),
        _box(component.part, component, center=(cx + width * 0.44, cy, cz), extents=(frame_w, height, depth * 1.20), tags=[*list(component.tags), "latch_post"]),
        _box(component.part, component, center=(cx, cy + height * 0.36, cz + depth * 0.14), extents=(width, max(height * 0.08, 0.035), depth * 1.24), tags=[*list(component.tags), "top_bar"]),
        _box(component.part, component, center=(cx, cy, cz + depth * 0.18), extents=(width * 0.78, max(height * 0.06, 0.025), depth * 1.12), tags=[*list(component.tags), "middle_bar"]),
        _box(component.part, component, center=(cx + width * 0.30, cy - height * 0.02, cz + depth * 0.48), extents=(width * 0.14, height * 0.16, max(depth * 0.10, 0.03)), tags=[*list(component.tags), "latch_handle"]),
    ]


def _access_support_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    radius = component.radius if component.radius is not None else max(min(width, depth) * 0.38, 0.04)
    support_h = component.height if component.height is not None else height
    cx, cy, cz = component.center
    return [
        _cylinder(component.part, component, radius=radius, height=support_h, axis="y", tags=[*list(component.tags), "support_column"]),
        _cylinder(component.part, component, center=(cx, cy - support_h * 0.48, cz), radius=radius * 1.65, height=max(height * 0.08, 0.04), axis="y", tags=[*list(component.tags), "base_plate"]),
        _cylinder(component.part, component, center=(cx, cy + support_h * 0.48, cz), radius=radius * 1.38, height=max(height * 0.08, 0.04), axis="y", tags=[*list(component.tags), "top_plate"]),
    ]


def _lot_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    cx, cy, cz = component.center
    return [
        _box(component.part, component),
        _box(
            component.part,
            component,
            center=(cx, cy + height * 0.42, cz),
            extents=(width * 0.76, max(height * 0.18, 0.10), depth * 0.76),
            tags=[*list(component.tags), "buildable_pad"],
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
    return _COMPONENT_BUILDERS[component.component_type](component)


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
    signature = {
        "expected_extents": extents,
        "projected_ratio": _ratio_signature(extents),
        "minimum_triangle_density": round(
            min(0.88, 0.42 + 0.05 * len(primitives_used) + 0.03 * len(regions)), 6
        ),
        "expected_part_names": [part.name for part in asset_graph.parts],
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
    if assessment.get("mesh_grammar_operator_counts"):
        signature["mesh_grammar"] = {
            "operator_counts": dict(assessment["mesh_grammar_operator_counts"]),
            "generated_primitive_count": int(assessment.get("mesh_grammar_generated_primitive_count", 0) or 0),
            "modified_primitive_count": int(assessment.get("mesh_grammar_modified_primitive_count", 0) or 0),
        }
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
    for component in blueprint.components:
        primitives.extend(_component_primitives(component))
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
    return _build_shape_ir(
        asset_graph,
        blueprint_id=blueprint.blueprint_id,
        primitives=primitives,
        regions=regions,
        notes=blueprint.notes,
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
    return _build_shape_ir(
        asset_graph,
        blueprint_id=shape_ir.blueprint_id,
        primitives=list(shape_ir.primitives),
        regions=list(shape_ir.regions),
        notes=notes or list(shape_ir.signature.get("blueprint_notes", [])),
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
