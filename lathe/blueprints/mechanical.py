"""Mechanical-family assembly blueprints."""

from __future__ import annotations

import numpy as np

from ..assembly_kernel import AssemblyBlueprint, mirrored, polar_offset
from ..asset_graph import AssetGraph
from .common import _component, _pair_parts, _part_name


def _drone_blueprint(
    asset_graph: AssetGraph, rng: np.random.Generator, candidate_index: int
) -> AssemblyBlueprint:
    scale = asset_graph.scale_cm
    width = scale * 0.60 * float(1.0 + rng.uniform(-0.03, 0.03))
    height = scale * 0.26 * float(1.0 + rng.uniform(-0.02, 0.02))
    depth = scale * 0.68 * float(1.0 + rng.uniform(-0.03, 0.03))
    body_part = _part_name(asset_graph, "body")
    cargo_part = _part_name(
        asset_graph, "cargo", fallback=_part_name(asset_graph, "door", fallback=body_part)
    )
    leg_l, leg_r = _pair_parts(asset_graph, "leg")
    rotor_names = [part.name for part in asset_graph.parts if "rotor" in part.tags]
    arm_radius = width * 1.04
    arm_positions = [
        ("arm_front_bar", (0.0, height * 0.28, depth * 0.56), (width * 2.18, height * 0.18, width * 0.12)),
        ("arm_rear_bar", (0.0, height * 0.28, -depth * 0.56), (width * 2.18, height * 0.18, width * 0.12)),
        ("arm_left_bar", (width * 1.02, height * 0.28, 0.0), (width * 0.12, height * 0.18, depth * 1.74)),
        ("arm_right_bar", (-width * 1.02, height * 0.28, 0.0), (width * 0.12, height * 0.18, depth * 1.74)),
    ]
    rotor_centers = {
        "rotor_fl": (width * 1.02, height * 0.66, depth * 0.98),
        "rotor_fr": (-width * 1.02, height * 0.66, depth * 0.98),
        "rotor_rl": (width * 1.02, height * 0.66, -depth * 0.98),
        "rotor_rr": (-width * 1.02, height * 0.66, -depth * 0.98),
    }
    components = [
        _component(
            "body_shell",
            "shell",
            body_part,
            (0.0, 0.0, 0.0),
            (width, height, depth),
            tags=["body", "airframe"],
        ),
        _component(
            "canopy_bezel",
            "bezel",
            body_part,
            (0.0, height * 0.28, 0.0),
            (width * 0.68, height * 0.34, depth * 0.50),
            tags=["bezel", "canopy"],
        ),
        _component(
            "cargo_door_region",
            "door",
            cargo_part,
            (0.0, -height * 0.42, depth * 0.34),
            (width * 0.70, height * 0.18, depth * 0.18),
            tags=["door", "cargo"],
            adjacency=[body_part],
        ),
        _component(
            "keel_spine",
            "bracket",
            body_part,
            (0.0, -height * 0.24, 0.0),
            (width * 0.38, height * 0.64, depth * 0.42),
            tags=["brace", "keel"],
            adjacency=rotor_names,
        ),
        _component(
            "fairing_front_left",
            "bracket",
            body_part,
            (width * 0.54, height * 0.28, depth * 0.52),
            (width * 0.44, height * 0.18, depth * 0.28),
            tags=["fairing", "front", "left"],
            adjacency=rotor_names,
        ),
        _component(
            "fairing_front_right",
            "bracket",
            body_part,
            (-width * 0.54, height * 0.28, depth * 0.52),
            (width * 0.44, height * 0.18, depth * 0.28),
            tags=["fairing", "front", "right"],
            adjacency=rotor_names,
        ),
        _component(
            "fairing_rear_left",
            "bracket",
            body_part,
            (width * 0.54, height * 0.28, -depth * 0.52),
            (width * 0.44, height * 0.18, depth * 0.28),
            tags=["fairing", "rear", "left"],
            adjacency=rotor_names,
        ),
        _component(
            "fairing_rear_right",
            "bracket",
            body_part,
            (-width * 0.54, height * 0.28, -depth * 0.52),
            (width * 0.44, height * 0.18, depth * 0.28),
            tags=["fairing", "rear", "right"],
            adjacency=rotor_names,
        ),
    ]
    for name, center, extents in arm_positions:
        components.append(
            _component(name, "rotor_arm", body_part, center, extents, tags=["arm"], adjacency=rotor_names)
        )
    for rotor_name in rotor_names:
        center = rotor_centers.get(
            rotor_name, polar_offset(arm_radius, 45.0 * len(components), height * 0.78, depth_scale=1.2)
        )
        mate = next((part.symmetry_mate for part in asset_graph.parts if part.name == rotor_name), None)
        components.append(
            _component(
                f"{rotor_name}_mount",
                "bracket",
                body_part,
                (center[0], height * 0.44, center[2]),
                (width * 0.14, height * 0.72, width * 0.14),
                tags=["brace", "rotor", "mount"],
                adjacency=[body_part, rotor_name],
            )
        )
        components.append(
            _component(
                f"{rotor_name}_pod",
                "rotor_pod",
                rotor_name,
                center,
                (scale * 0.10, scale * 0.10, scale * 0.10),
                tags=["rotor"],
                axis="y",
                radius=scale * 0.11,
                height=scale * 0.025,
                symmetry_mate=mate,
            )
        )
    if leg_l:
        components.append(
            _component(
                "leg_left_region",
                "stand",
                leg_l,
                (width * 0.52, -height * 0.92, depth * 0.22),
                (width * 0.08, height * 0.70, width * 0.08),
                tags=["leg", "left"],
                symmetry_mate=leg_r,
                interface_role="support",
            )
        )
    if leg_r:
        components.append(
            _component(
                "leg_right_region",
                "stand",
                leg_r,
                mirrored((width * 0.52, -height * 0.92, depth * 0.22)),
                (width * 0.08, height * 0.70, width * 0.08),
                tags=["leg", "right"],
                symmetry_mate=leg_l,
                interface_role="support",
            )
        )
    return AssemblyBlueprint(
        asset_graph.blueprint_id,
        asset_graph.family,
        components,
        notes=["airframe shell + shared rotor arm/pod primitives define the authoritative drone scaffold"],
    )


def _door_blueprint(
    asset_graph: AssetGraph, rng: np.random.Generator, candidate_index: int
) -> AssemblyBlueprint:
    scale = asset_graph.scale_cm
    width = scale * 0.82 * float(1.0 + rng.uniform(-0.02, 0.02))
    height = scale * 1.70 * float(1.0 + rng.uniform(-0.02, 0.02))
    depth = scale * 0.22 * float(1.0 + rng.uniform(-0.02, 0.02))
    body_part = _part_name(asset_graph, "body")
    door_part = _part_name(asset_graph, "door", fallback=body_part)
    hinge_top = next(
        (part.name for part in asset_graph.parts if "hinge" in part.tags and "top" in part.tags),
        _part_name(asset_graph, "hinge", fallback=body_part),
    )
    hinge_bottom = next(
        (part.name for part in asset_graph.parts if "hinge" in part.tags and "bottom" in part.tags), hinge_top
    )
    handle_part = _part_name(asset_graph, "handle", fallback=door_part)
    lock_part = _part_name(asset_graph, "lock", fallback=_part_name(asset_graph, "plate", fallback=door_part))
    threshold_part = _part_name(asset_graph, "threshold", fallback=body_part)
    components = [
        _component(
            "door_frame",
            "frame",
            body_part,
            (0.0, 0.0, 0.0),
            (width, height, depth),
            tags=["frame", "door"],
            adjacency=[door_part],
        ),
        _component(
            "door_leaf_region",
            "door",
            door_part,
            (0.0, 0.0, depth * 0.10),
            (width * 0.80, height * 0.92, depth * 0.18),
            tags=["door"],
            adjacency=[body_part, handle_part, lock_part],
        ),
        _component(
            "hinge_top_region",
            "hinge",
            hinge_top,
            (-width * 0.44, height * 0.28, depth * 0.10),
            (width * 0.08, height * 0.12, depth * 0.10),
            tags=["hinge", "top"],
            axis="z",
            radius=depth * 0.32,
            height=height * 0.14,
            adjacency=[door_part],
        ),
        _component(
            "hinge_bottom_region",
            "hinge",
            hinge_bottom,
            (-width * 0.44, -height * 0.28, depth * 0.10),
            (width * 0.08, height * 0.12, depth * 0.10),
            tags=["hinge", "bottom"],
            axis="z",
            radius=depth * 0.32,
            height=height * 0.14,
            adjacency=[door_part],
        ),
        _component(
            "door_handle_region",
            "handle",
            handle_part,
            (width * 0.32, 0.0, depth * 0.18),
            (width * 0.08, height * 0.10, depth * 0.10),
            tags=["handle"],
            axis="y",
            radius=depth * 0.22,
            height=height * 0.18,
            interface_role="grip",
            adjacency=[door_part],
        ),
        _component(
            "door_lock_region",
            "lock_plate",
            lock_part,
            (width * 0.24, 0.0, depth * 0.18),
            (width * 0.12, height * 0.14, depth * 0.06),
            tags=["lock", "plate"],
            adjacency=[door_part],
        ),
        _component(
            "threshold_region",
            "socket_plate",
            threshold_part,
            (0.0, -height * 0.50, 0.0),
            (width * 0.72, height * 0.05, depth * 0.34),
            tags=["threshold"],
            adjacency=[body_part, door_part],
        ),
    ]
    return AssemblyBlueprint(
        asset_graph.blueprint_id,
        asset_graph.family,
        components,
        notes=["mechanical door compiled from shared frame, door, hinge, handle, and threshold primitives"],
    )
