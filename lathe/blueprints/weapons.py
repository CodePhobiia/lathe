"""Weapon-family assembly blueprints."""

from __future__ import annotations

import numpy as np

from ..assembly_kernel import AssemblyBlueprint
from ..asset_graph import AssetGraph
from .common import _component, _part_name


def _sword_blueprint(
    asset_graph: AssetGraph, rng: np.random.Generator, candidate_index: int
) -> AssemblyBlueprint:
    scale = asset_graph.scale_cm
    blade_height = scale * 0.70 * float(1.0 + rng.uniform(-0.015, 0.015))
    blade_width = scale * 0.075 * float(1.0 + rng.uniform(-0.025, 0.025))
    blade_depth = max(scale * 0.018, 1.5)
    guard_width = scale * 0.34 * float(1.0 + rng.uniform(-0.025, 0.025))
    guard_radius = max(scale * 0.018, 1.4)
    grip_height = scale * 0.18
    grip_radius = max(scale * 0.026, 2.1)
    pommel_radius = max(scale * 0.040, 3.5)

    blade_part = _part_name(asset_graph, "blade", fallback="long_tapered_blade")
    fuller_part = _part_name(asset_graph, "fuller", fallback="central_fuller")
    tip_part = _part_name(asset_graph, "tip", fallback="sharp_tip")
    guard_part = _part_name(asset_graph, "guard", "crossguard", fallback="crossguard")
    grip_part = _part_name(asset_graph, "grip", "handle", fallback="leather_wrapped_grip")
    pommel_part = _part_name(asset_graph, "pommel", fallback="round_pommel")

    guard_y = -scale * 0.22
    blade_center_y = guard_y + blade_height * 0.50 + scale * 0.018
    tip_center_y = blade_center_y + blade_height * 0.50 + scale * 0.030
    grip_center_y = guard_y - grip_height * 0.52
    pommel_center_y = grip_center_y - grip_height * 0.58

    components = [
        _component(
            "sword_blade_region",
            "blade",
            blade_part,
            (0.0, blade_center_y, 0.0),
            (blade_width, blade_height, blade_depth),
            tags=["blade", "steel", "centerline"],
            adjacency=[guard_part, fuller_part, tip_part],
        ),
        _component(
            "sword_fuller_region",
            "fuller",
            fuller_part,
            (0.0, blade_center_y - blade_height * 0.06, 0.0),
            (blade_width * 0.24, blade_height * 0.68, blade_depth * 1.08),
            tags=["fuller", "blade", "centerline"],
            adjacency=[blade_part],
        ),
        _component(
            "sword_tip_region",
            "blade_tip",
            tip_part,
            (0.0, tip_center_y, 0.0),
            (blade_width * 0.96, scale * 0.070, blade_depth),
            tags=["tip", "point", "steel"],
            adjacency=[blade_part],
        ),
        _component(
            "sword_crossguard_region",
            "guard",
            guard_part,
            (0.0, guard_y, 0.0),
            (guard_width, guard_radius * 1.8, guard_radius * 1.8),
            tags=["guard", "crossguard", "brass"],
            adjacency=[blade_part, grip_part],
            axis="x",
            radius=guard_radius,
            height=guard_width,
            interface_role="hand_stop",
        ),
        _component(
            "sword_grip_region",
            "grip",
            grip_part,
            (0.0, grip_center_y, 0.0),
            (grip_radius * 2.0, grip_height, grip_radius * 2.0),
            tags=["grip", "leather", "handle"],
            adjacency=[guard_part, pommel_part],
            axis="y",
            radius=grip_radius,
            height=grip_height,
            interface_role="grip",
        ),
        _component(
            "sword_pommel_region",
            "pommel",
            pommel_part,
            (0.0, pommel_center_y, 0.0),
            (pommel_radius * 2.0, scale * 0.060, pommel_radius * 2.0),
            tags=["pommel", "brass", "counterweight"],
            adjacency=[grip_part],
            axis="y",
            radius=pommel_radius,
            height=scale * 0.060,
        ),
    ]
    return AssemblyBlueprint(
        asset_graph.blueprint_id,
        asset_graph.family,
        components,
        notes=["hero sword assembled from blade, fuller, crossguard, grip, and pommel primitives"],
    )
