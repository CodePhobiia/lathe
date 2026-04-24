"""Assembly kernel: turn an asset graph into an assembly blueprint.

Produces the deterministic blueprint of components, joins and
boundary constraints that seeds scaffold compilation and the shape
IR.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any, Callable

from .asset_graph import AssetGraph
from .errors import ContractViolation
from .shape_ir import ShapeIR, ShapePrimitive, ShapeRegion


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


def _box(part: str, component: BlueprintComponent, *, center: tuple[float, float, float] | None = None, extents: tuple[float, float, float] | None = None, tags: list[str] | None = None) -> ShapePrimitive:
    return ShapePrimitive(
        primitive_type="box",
        part=part,
        center=center or component.center,
        extents=extents or component.extents,
        tags=tags or list(component.tags),
        component=component.component_type,
        region=component.name,
    )


def _cylinder(part: str, component: BlueprintComponent, *, center: tuple[float, float, float] | None = None, radius: float | None = None, height: float | None = None, axis: str | None = None, tags: list[str] | None = None) -> ShapePrimitive:
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
            tags=list(component.tags) + ["liner"],
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
        _box(component.part, component, center=(component.center[0], component.center[1] + half_h - thickness / 2.0, cz), extents=(width, thickness, depth)),
        _box(component.part, component, center=(component.center[0], component.center[1] - half_h + thickness / 2.0, cz), extents=(width, thickness, depth)),
        _box(component.part, component, center=(component.center[0] - half_w + thickness / 2.0, component.center[1], cz), extents=(thickness, max(thickness, height - 2.0 * thickness), depth)),
        _box(component.part, component, center=(component.center[0] + half_w - thickness / 2.0, component.center[1], cz), extents=(thickness, max(thickness, height - 2.0 * thickness), depth)),
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
            tags=list(component.tags) + ["crest"],
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
            tags=list(component.tags) + ["face"],
        ),
    ]


def _hinge_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    radius = component.radius if component.radius is not None else max(width, depth) * 0.42
    barrel_height = component.height if component.height is not None else max(width, height, depth)
    return [
        _cylinder(component.part, component, radius=radius, height=barrel_height, axis=component.axis, tags=list(component.tags) + ["barrel"]),
        _box(
            component.part,
            component,
            center=(component.center[0], component.center[1], component.center[2] - depth * 0.20),
            extents=(width, height * 0.45, depth * 0.55),
            tags=list(component.tags) + ["mount"],
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
            center=(component.center[0], component.center[1] - height * 0.18, component.center[2] + depth * 0.08),
            extents=(width * 0.36, height * 0.55, depth * 0.40),
            tags=list(component.tags) + ["latch_body"],
        ),
    ]


def _handle_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    radius = component.radius if component.radius is not None else max(height, depth) * 0.36
    handle_height = component.height if component.height is not None else max(width, height, depth) * 0.85
    return [_cylinder(component.part, component, radius=radius, height=handle_height, axis=component.axis, tags=list(component.tags) + ["grip"])]


def _foot_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    return [
        _box(component.part, component),
        _box(
            component.part,
            component,
            center=(component.center[0], component.center[1] - height * 0.20, component.center[2]),
            extents=(width * 1.14, height * 0.35, depth * 1.08),
            tags=list(component.tags) + ["pad"],
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
            tags=list(component.tags) + ["base"],
        ),
    ]


def _bracket_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    width, height, depth = component.extents
    return [
        _box(component.part, component, center=(component.center[0], component.center[1], component.center[2] - depth * 0.16), extents=(width, height * 0.35, depth)),
        _box(component.part, component, center=(component.center[0], component.center[1] - height * 0.18, component.center[2]), extents=(width * 0.35, height, depth)),
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
                tags=list(component.tags) + ["slat"],
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
        _cylinder(component.part, component, radius=radius, height=disc_height, axis=component.axis, tags=list(component.tags) + ["disc"]),
        _cylinder(
            component.part,
            component,
            center=(component.center[0], component.center[1] - height * 0.26, component.center[2]),
            radius=radius * 0.34,
            height=max(height, disc_height * 2.4),
            axis=component.axis,
            tags=list(component.tags) + ["hub"],
        ),
    ]


def _plate_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    return [_box(component.part, component)]


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
    "socket_plate": _plate_primitives,
    "anchor_plate": _plate_primitives,
}


def _component_primitives(component: BlueprintComponent) -> list[ShapePrimitive]:
    if component.component_type not in _COMPONENT_BUILDERS:
        raise ValueError(f"Unsupported assembly component '{component.component_type}'")
    return _COMPONENT_BUILDERS[component.component_type](component)


def _primitive_bounds(primitive: ShapePrimitive) -> tuple[list[float], list[float]]:
    if primitive.primitive_type == "box":
        if primitive.extents is None:
            raise ContractViolation(
                f"invariant violation: box ShapePrimitive requires extents, got None (part={primitive.part!r})"
            )
        half = [value / 2.0 for value in primitive.extents]
    else:
        if primitive.radius is None or primitive.height is None:
            raise ContractViolation(
                f"invariant violation: non-box ShapePrimitive requires radius and height, "
                f"got radius={primitive.radius!r}, height={primitive.height!r} (part={primitive.part!r})"
            )
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
    largest = max(1e-6, max(extents))
    return [round(float(value) / largest, 6) for value in extents]


def _profile_bins(values: list[float], span: float) -> list[float]:
    if not values or span <= 1e-6:
        return [0.0, 0.0, 0.0]
    bins = [0.0, 0.0, 0.0]
    for value in values:
        normalized = (value / span) + 0.5
        index = max(0, min(2, int(normalized * 3.0)))
        bins[index] += 1.0
    total = max(1.0, sum(bins))
    return [round(item / total, 6) for item in bins]


def _shape_assessment(asset_graph: AssetGraph, regions: list[ShapeRegion], primitives: list[ShapePrimitive]) -> dict[str, Any]:
    expected_parts = {part.name for part in asset_graph.parts}
    realized_parts = {region.part for region in regions}
    required_pairs = [(part.name, part.symmetry_mate) for part in asset_graph.parts if part.symmetry_mate and part.name < part.symmetry_mate]
    symmetry_score = 1.0 if not required_pairs else round(sum(1.0 for left, right in required_pairs if left in realized_parts and right in realized_parts) / len(required_pairs), 6)
    feature_primitives = [primitive for primitive in primitives if "feature" in primitive.tags]
    feature_components = {primitive.component for primitive in feature_primitives if primitive.component}
    edge_treatment_count = sum(1 for primitive in feature_primitives if any(tag in primitive.tags for tag in ("edge_break", "bevel", "chamfer", "fillet")))
    panel_feature_count = sum(1 for primitive in feature_primitives if any(tag in primitive.tags for tag in ("frame_lip", "trim_band", "vent_grille", "panel_frame")))
    support_feature_count = sum(1 for primitive in feature_primitives if any(tag in primitive.tags for tag in ("support_bracket", "recessed_handle", "rotor_shroud")))
    attachment_region_count = sum(1 for region in regions if region.component in {"handle", "hinge", "lock_plate", "latch", "rotor_pod", "socket_plate", "anchor_plate", "bracket", "bezel", "frame"})
    feature_density = round(len(feature_primitives) / max(1.0, len(asset_graph.parts) * 2.0), 6)
    silhouette_complexity = round(min(1.0, (len(regions) * 0.04) + (len(feature_primitives) * 0.015) + (attachment_region_count * 0.03)), 6)
    feature_coherence = round(min(1.0, (0.45 * feature_density) + (0.25 * min(1.0, len(feature_components) / max(1, len(asset_graph.parts)))) + (0.30 * min(1.0, attachment_region_count / max(1, len(asset_graph.parts) / 2.0)))), 6)
    return {
        "required_part_coverage": round(len(expected_parts & realized_parts) / max(1, len(expected_parts)), 6),
        "primitive_count": len(primitives),
        "region_count": len(regions),
        "primitive_diversity": round(len({primitive.component or primitive.primitive_type for primitive in primitives}) / max(1, len(primitives)), 6),
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


def _build_shape_ir(
    asset_graph: AssetGraph,
    *,
    blueprint_id: str,
    primitives: list[ShapePrimitive],
    regions: list[ShapeRegion],
    notes: list[str] | None = None,
) -> ShapeIR:
    extents = _expected_extents(primitives)
    largest = max(1e-6, max(extents))
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
    signature = {
        "expected_extents": extents,
        "projected_ratio": _ratio_signature(extents),
        "minimum_triangle_density": round(min(0.88, 0.42 + 0.05 * len(primitives_used) + 0.03 * len(regions)), 6),
        "expected_part_names": [part.name for part in asset_graph.parts],
        "part_targets": part_targets,
        "adjacency_pairs": list(asset_graph.part_graph),
        "region_spread": [
            round(max(region_x) - min(region_x), 6) if region_x else 0.0,
            round(max(region_y) - min(region_y), 6) if region_y else 0.0,
            round(max(region_z) - min(region_z), 6) if region_z else 0.0,
        ],
        "vertical_profile": _profile_bins(region_y, max(1e-6, max(region_y) - min(region_y) if region_y else 1.0)),
        "depth_profile": _profile_bins(region_z, max(1e-6, max(region_z) - min(region_z) if region_z else 1.0)),
        "width_profile": _profile_bins(region_x, max(1e-6, max(region_x) - min(region_x) if region_x else 1.0)),
        "expected_region_count": len(regions),
        "fragmentation_ceiling": max(4, len(regions) * 3),
        "primitives_used": primitives_used,
        "blueprint_notes": list(notes or []),
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
    return _build_shape_ir(asset_graph, blueprint_id=blueprint.blueprint_id, primitives=primitives, regions=regions, notes=blueprint.notes)


def refresh_shape_ir(asset_graph: AssetGraph, shape_ir: ShapeIR, *, notes: list[str] | None = None) -> ShapeIR:
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
    raise ValueError(f"Unsupported mirror axis '{axis}'")


def polar_offset(radius: float, angle_deg: float, y: float, *, depth_scale: float = 1.0) -> tuple[float, float, float]:
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
