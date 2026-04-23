from __future__ import annotations

from typing import Any

import numpy as np

from ..assembly_kernel import AssemblyBlueprint, BlueprintComponent, mirrored, polar_offset
from ..asset_graph import AssetGraph


def _part_name(asset_graph: AssetGraph, *tags: str, fallback: str = "body") -> str:
    tag_set = set(tags)
    for part in asset_graph.parts:
        if tag_set <= set(part.tags):
            return part.name
    for part in asset_graph.parts:
        if any(tag in part.tags for tag in tags):
            return part.name
    return next((part.name for part in asset_graph.parts if part.name == fallback), asset_graph.parts[0].name if asset_graph.parts else fallback)


def _pair_parts(asset_graph: AssetGraph, role: str) -> tuple[str | None, str | None]:
    left = next((part.name for part in asset_graph.parts if role in part.tags and "left" in part.tags), None)
    right = next((part.name for part in asset_graph.parts if role in part.tags and "right" in part.tags), None)
    return left, right


def _component(
    name: str,
    component_type: str,
    part: str,
    center: tuple[float, float, float],
    extents: tuple[float, float, float],
    *,
    tags: list[str] | None = None,
    adjacency: list[str] | None = None,
    axis: str = "y",
    radius: float | None = None,
    height: float | None = None,
    symmetry_mate: str | None = None,
    interface_role: str | None = None,
) -> BlueprintComponent:
    return BlueprintComponent(
        name=name,
        component_type=component_type,
        part=part,
        center=center,
        extents=extents,
        tags=tags or [],
        adjacency=adjacency or [],
        axis=axis,
        radius=radius,
        height=height,
        symmetry_mate=symmetry_mate,
        interface_role=interface_role,
    )


def _chest_blueprint(asset_graph: AssetGraph, rng: np.random.Generator, candidate_index: int) -> AssemblyBlueprint:
    scale = asset_graph.scale_cm
    width = scale * 0.78 * float(1.0 + rng.uniform(-0.03, 0.03))
    height = scale * 0.52 * float(1.0 + rng.uniform(-0.02, 0.02))
    depth = scale * 0.56 * float(1.0 + rng.uniform(-0.03, 0.03))
    body_part = _part_name(asset_graph, "body")
    lid_part = _part_name(asset_graph, "lid", fallback=body_part)
    door_part = _part_name(asset_graph, "hatch", fallback=_part_name(asset_graph, "door", fallback=body_part))
    lock_part = _part_name(asset_graph, "lock", fallback=_part_name(asset_graph, "plate", fallback=body_part))
    handle_l, handle_r = _pair_parts(asset_graph, "handle")
    foot_l, foot_r = _pair_parts(asset_graph, "foot")
    base_height = height * 0.58
    lid_height = height * 0.28
    components = [
        _component("body_shell", "shell", body_part, (0.0, -height * 0.10, 0.0), (width, base_height, depth), tags=["body", "container"]),
        _component("body_frame_front", "frame", body_part, (0.0, -height * 0.10, depth * 0.39), (width * 0.92, base_height * 0.34, depth * 0.08), tags=["frame", "front"], adjacency=[door_part]),
        _component("body_frame_rear", "frame", body_part, (0.0, -height * 0.10, -depth * 0.39), (width * 0.92, base_height * 0.28, depth * 0.08), tags=["frame", "rear"]),
        _component("lid_region", "lid", lid_part, (0.0, height * 0.19, 0.0), (width * 0.96, lid_height, depth * 0.92), tags=["lid"], adjacency=[body_part, lock_part]),
        _component("front_hatch_region", "door", door_part, (0.0, -height * 0.03, depth * 0.48), (width * 0.78, base_height * 0.26, depth * 0.10), tags=["door", "front"], adjacency=[body_part, lock_part]),
        _component("lock_region", "lock_plate", lock_part, (0.0, height * 0.03, depth * 0.53), (width * 0.16, height * 0.18, depth * 0.08), tags=["lock", "front"], adjacency=[lid_part, door_part]),
    ]
    if handle_l:
        components.append(
            _component(
                "handle_left_region",
                "handle",
                handle_l,
                (-width * 0.53, -height * 0.02, 0.0),
                (width * 0.10, height * 0.18, depth * 0.14),
                tags=["handle", "left"],
                axis="x",
                radius=height * 0.08,
                height=width * 0.09,
                symmetry_mate=handle_r,
                interface_role="grip",
            )
        )
    if handle_r:
        components.append(
            _component(
                "handle_right_region",
                "handle",
                handle_r,
                mirrored((-width * 0.53, -height * 0.02, 0.0)),
                (width * 0.10, height * 0.18, depth * 0.14),
                tags=["handle", "right"],
                axis="x",
                radius=height * 0.08,
                height=width * 0.09,
                symmetry_mate=handle_l,
                interface_role="grip",
            )
        )
    if foot_l:
        components.append(
            _component(
                "foot_left_region",
                "foot",
                foot_l,
                (-width * 0.28, -height * 0.48, depth * 0.20),
                (width * 0.12, height * 0.10, depth * 0.16),
                tags=["foot", "left"],
                symmetry_mate=foot_r,
                interface_role="support",
            )
        )
    if foot_r:
        components.append(
            _component(
                "foot_right_region",
                "foot",
                foot_r,
                mirrored((-width * 0.28, -height * 0.48, depth * 0.20)),
                (width * 0.12, height * 0.10, depth * 0.16),
                tags=["foot", "right"],
                symmetry_mate=foot_l,
                interface_role="support",
            )
        )
    return AssemblyBlueprint(asset_graph.blueprint_id, asset_graph.family, components, notes=["container shell + lid + front hatch compiled from shared hard-surface primitives"])


def _drone_blueprint(asset_graph: AssetGraph, rng: np.random.Generator, candidate_index: int) -> AssemblyBlueprint:
    scale = asset_graph.scale_cm
    width = scale * 0.60 * float(1.0 + rng.uniform(-0.03, 0.03))
    height = scale * 0.26 * float(1.0 + rng.uniform(-0.02, 0.02))
    depth = scale * 0.68 * float(1.0 + rng.uniform(-0.03, 0.03))
    body_part = _part_name(asset_graph, "body")
    cargo_part = _part_name(asset_graph, "cargo", fallback=_part_name(asset_graph, "door", fallback=body_part))
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
        _component("body_shell", "shell", body_part, (0.0, 0.0, 0.0), (width, height, depth), tags=["body", "airframe"]),
        _component("canopy_bezel", "bezel", body_part, (0.0, height * 0.28, 0.0), (width * 0.68, height * 0.34, depth * 0.50), tags=["bezel", "canopy"]),
        _component("cargo_door_region", "door", cargo_part, (0.0, -height * 0.42, depth * 0.34), (width * 0.70, height * 0.18, depth * 0.18), tags=["door", "cargo"], adjacency=[body_part]),
        _component("keel_spine", "bracket", body_part, (0.0, -height * 0.24, 0.0), (width * 0.38, height * 0.64, depth * 0.42), tags=["brace", "keel"], adjacency=rotor_names),
        _component("fairing_front_left", "bracket", body_part, (width * 0.54, height * 0.28, depth * 0.52), (width * 0.44, height * 0.18, depth * 0.28), tags=["fairing", "front", "left"], adjacency=rotor_names),
        _component("fairing_front_right", "bracket", body_part, (-width * 0.54, height * 0.28, depth * 0.52), (width * 0.44, height * 0.18, depth * 0.28), tags=["fairing", "front", "right"], adjacency=rotor_names),
        _component("fairing_rear_left", "bracket", body_part, (width * 0.54, height * 0.28, -depth * 0.52), (width * 0.44, height * 0.18, depth * 0.28), tags=["fairing", "rear", "left"], adjacency=rotor_names),
        _component("fairing_rear_right", "bracket", body_part, (-width * 0.54, height * 0.28, -depth * 0.52), (width * 0.44, height * 0.18, depth * 0.28), tags=["fairing", "rear", "right"], adjacency=rotor_names),
    ]
    for name, center, extents in arm_positions:
        components.append(_component(name, "rotor_arm", body_part, center, extents, tags=["arm"], adjacency=rotor_names))
    for rotor_name in rotor_names:
        center = rotor_centers.get(rotor_name, polar_offset(arm_radius, 45.0 * len(components), height * 0.78, depth_scale=1.2))
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
    return AssemblyBlueprint(asset_graph.blueprint_id, asset_graph.family, components, notes=["airframe shell + shared rotor arm/pod primitives define the authoritative drone scaffold"])


def _wall_panel_blueprint(asset_graph: AssetGraph, rng: np.random.Generator, candidate_index: int) -> AssemblyBlueprint:
    scale = asset_graph.scale_cm
    width = scale * 1.10 * float(1.0 + rng.uniform(-0.03, 0.03))
    height = scale * 1.48 * float(1.0 + rng.uniform(-0.03, 0.03))
    depth = scale * 0.18 * float(1.0 + rng.uniform(-0.02, 0.02))
    body_part = _part_name(asset_graph, "body")
    screen_part = _part_name(asset_graph, "screen", fallback=body_part)
    frame_part = _part_name(asset_graph, "frame", fallback=body_part)
    vent_l, vent_r = _pair_parts(asset_graph, "vent")
    console_part = _part_name(asset_graph, "console", fallback=_part_name(asset_graph, "panel", fallback=body_part))
    top_mount = next((part.name for part in asset_graph.parts if "top" in part.tags), body_part)
    bottom_mount = next((part.name for part in asset_graph.parts if "bottom" in part.tags), body_part)
    components = [
        _component("panel_shell", "shell", body_part, (0.0, 0.0, 0.0), (width, height, depth), tags=["body", "panel"]),
        _component("screen_bezel", "bezel", frame_part, (0.0, height * 0.10, depth * 0.14), (width * 0.64, height * 0.52, depth * 0.08), tags=["bezel", "screen"], adjacency=[screen_part]),
        _component("screen_region", "panel", screen_part, (0.0, height * 0.10, depth * 0.16), (width * 0.52, height * 0.42, depth * 0.08), tags=["screen", "panel"], adjacency=[frame_part]),
        _component("console_strip_region", "panel", console_part, (0.0, -height * 0.36, depth * 0.14), (width * 0.60, height * 0.13, depth * 0.08), tags=["console", "panel"], adjacency=[body_part]),
        _component("mount_top_region", "bracket", top_mount, (0.0, height * 0.56, -depth * 0.08), (width * 0.28, height * 0.10, depth * 0.34), tags=["mount", "top"], adjacency=[body_part]),
        _component("mount_bottom_region", "bracket", bottom_mount, (0.0, -height * 0.56, -depth * 0.08), (width * 0.28, height * 0.10, depth * 0.34), tags=["mount", "bottom"], adjacency=[body_part]),
    ]
    if vent_l:
        components.append(
            _component(
                "vent_left_region",
                "vent",
                vent_l,
                (-width * 0.26, -height * 0.18, depth * 0.14),
                (width * 0.18, height * 0.28, depth * 0.08),
                tags=["vent", "left"],
                symmetry_mate=vent_r,
            )
        )
    if vent_r:
        components.append(
            _component(
                "vent_right_region",
                "vent",
                vent_r,
                mirrored((-width * 0.26, -height * 0.18, depth * 0.14)),
                (width * 0.18, height * 0.28, depth * 0.08),
                tags=["vent", "right"],
                symmetry_mate=vent_l,
            )
        )
    return AssemblyBlueprint(asset_graph.blueprint_id, asset_graph.family, components, notes=["env module panel compiled from shared shell, bezel, vent, and bracket primitives"])


def _crate_blueprint(asset_graph: AssetGraph, rng: np.random.Generator, candidate_index: int) -> AssemblyBlueprint:
    scale = asset_graph.scale_cm
    width = scale * 0.72 * float(1.0 + rng.uniform(-0.03, 0.03))
    height = scale * 0.52 * float(1.0 + rng.uniform(-0.03, 0.03))
    depth = scale * 0.60 * float(1.0 + rng.uniform(-0.03, 0.03))
    body_part = _part_name(asset_graph, "body")
    latch_part = _part_name(asset_graph, "latch", fallback=_part_name(asset_graph, "plate", fallback=body_part))
    handle_l, handle_r = _pair_parts(asset_graph, "handle")
    foot_l, foot_r = _pair_parts(asset_graph, "foot")
    components = [
        _component("crate_shell", "shell", body_part, (0.0, 0.0, 0.0), (width, height, depth), tags=["body", "crate"]),
        _component("crate_frame_front", "frame", body_part, (0.0, 0.0, depth * 0.39), (width * 0.96, height * 0.72, depth * 0.08), tags=["frame", "front"]),
        _component("crate_frame_back", "frame", body_part, (0.0, 0.0, -depth * 0.39), (width * 0.96, height * 0.72, depth * 0.08), tags=["frame", "rear"]),
        _component("crate_latch_region", "latch", latch_part, (0.0, height * 0.08, depth * 0.46), (width * 0.22, height * 0.16, depth * 0.08), tags=["latch", "front"]),
    ]
    if handle_l:
        components.append(
            _component(
                "crate_handle_left_region",
                "handle",
                handle_l,
                (-width * 0.52, 0.0, 0.0),
                (width * 0.10, height * 0.18, depth * 0.18),
                tags=["handle", "left"],
                axis="x",
                radius=height * 0.08,
                height=width * 0.10,
                symmetry_mate=handle_r,
                interface_role="grip",
            )
        )
    if handle_r:
        components.append(
            _component(
                "crate_handle_right_region",
                "handle",
                handle_r,
                mirrored((-width * 0.52, 0.0, 0.0)),
                (width * 0.10, height * 0.18, depth * 0.18),
                tags=["handle", "right"],
                axis="x",
                radius=height * 0.08,
                height=width * 0.10,
                symmetry_mate=handle_l,
                interface_role="grip",
            )
        )
    if foot_l:
        components.append(
            _component(
                "crate_foot_left_region",
                "foot",
                foot_l,
                (-width * 0.28, -height * 0.52, depth * 0.22),
                (width * 0.14, height * 0.10, depth * 0.16),
                tags=["foot", "left"],
                symmetry_mate=foot_r,
                interface_role="support",
            )
        )
    if foot_r:
        components.append(
            _component(
                "crate_foot_right_region",
                "foot",
                foot_r,
                mirrored((-width * 0.28, -height * 0.52, depth * 0.22)),
                (width * 0.14, height * 0.10, depth * 0.16),
                tags=["foot", "right"],
                symmetry_mate=foot_l,
                interface_role="support",
            )
        )
    return AssemblyBlueprint(asset_graph.blueprint_id, asset_graph.family, components, notes=["industrial crate assembled from shared shell, frame, latch, handle, and foot primitives"])


def _door_blueprint(asset_graph: AssetGraph, rng: np.random.Generator, candidate_index: int) -> AssemblyBlueprint:
    scale = asset_graph.scale_cm
    width = scale * 0.82 * float(1.0 + rng.uniform(-0.02, 0.02))
    height = scale * 1.70 * float(1.0 + rng.uniform(-0.02, 0.02))
    depth = scale * 0.22 * float(1.0 + rng.uniform(-0.02, 0.02))
    body_part = _part_name(asset_graph, "body")
    door_part = _part_name(asset_graph, "door", fallback=body_part)
    hinge_top = next((part.name for part in asset_graph.parts if "hinge" in part.tags and "top" in part.tags), _part_name(asset_graph, "hinge", fallback=body_part))
    hinge_bottom = next((part.name for part in asset_graph.parts if "hinge" in part.tags and "bottom" in part.tags), hinge_top)
    handle_part = _part_name(asset_graph, "handle", fallback=door_part)
    lock_part = _part_name(asset_graph, "lock", fallback=_part_name(asset_graph, "plate", fallback=door_part))
    threshold_part = _part_name(asset_graph, "threshold", fallback=body_part)
    components = [
        _component("door_frame", "frame", body_part, (0.0, 0.0, 0.0), (width, height, depth), tags=["frame", "door"], adjacency=[door_part]),
        _component("door_leaf_region", "door", door_part, (0.0, 0.0, depth * 0.10), (width * 0.80, height * 0.92, depth * 0.18), tags=["door"], adjacency=[body_part, handle_part, lock_part]),
        _component("hinge_top_region", "hinge", hinge_top, (-width * 0.44, height * 0.28, depth * 0.10), (width * 0.08, height * 0.12, depth * 0.10), tags=["hinge", "top"], axis="z", radius=depth * 0.32, height=height * 0.14, adjacency=[door_part]),
        _component("hinge_bottom_region", "hinge", hinge_bottom, (-width * 0.44, -height * 0.28, depth * 0.10), (width * 0.08, height * 0.12, depth * 0.10), tags=["hinge", "bottom"], axis="z", radius=depth * 0.32, height=height * 0.14, adjacency=[door_part]),
        _component("door_handle_region", "handle", handle_part, (width * 0.32, 0.0, depth * 0.18), (width * 0.08, height * 0.10, depth * 0.10), tags=["handle"], axis="y", radius=depth * 0.22, height=height * 0.18, interface_role="grip", adjacency=[door_part]),
        _component("door_lock_region", "lock_plate", lock_part, (width * 0.24, 0.0, depth * 0.18), (width * 0.12, height * 0.14, depth * 0.06), tags=["lock", "plate"], adjacency=[door_part]),
        _component("threshold_region", "socket_plate", threshold_part, (0.0, -height * 0.50, 0.0), (width * 0.72, height * 0.05, depth * 0.34), tags=["threshold"], adjacency=[body_part, door_part]),
    ]
    return AssemblyBlueprint(asset_graph.blueprint_id, asset_graph.family, components, notes=["mechanical door compiled from shared frame, door, hinge, handle, and threshold primitives"])


def _console_blueprint(asset_graph: AssetGraph, rng: np.random.Generator, candidate_index: int) -> AssemblyBlueprint:
    scale = asset_graph.scale_cm
    width = scale * 0.72 * float(1.0 + rng.uniform(-0.03, 0.03))
    height = scale * 1.04 * float(1.0 + rng.uniform(-0.03, 0.03))
    depth = scale * 0.52 * float(1.0 + rng.uniform(-0.03, 0.03))
    body_part = _part_name(asset_graph, "body")
    bezel_part = _part_name(asset_graph, "bezel", fallback=_part_name(asset_graph, "frame", fallback=body_part))
    screen_part = _part_name(asset_graph, "screen", fallback=_part_name(asset_graph, "panel", fallback=body_part))
    control_part = _part_name(asset_graph, "console", fallback=_part_name(asset_graph, "panel", fallback=screen_part))
    vent_l, vent_r = _pair_parts(asset_graph, "vent")
    stand_part = _part_name(asset_graph, "stand", fallback=body_part)
    socket_part = _part_name(asset_graph, "socket", fallback=_part_name(asset_graph, "plate", fallback=body_part))
    components = [
        _component("console_shell", "shell", body_part, (0.0, 0.0, 0.0), (width, height, depth), tags=["body", "console"]),
        _component("screen_bezel_region", "bezel", bezel_part, (0.0, height * 0.18, depth * 0.36), (width * 0.72, height * 0.40, depth * 0.12), tags=["bezel", "screen"], adjacency=[screen_part]),
        _component("screen_panel_region", "panel", screen_part, (0.0, height * 0.18, depth * 0.41), (width * 0.58, height * 0.28, depth * 0.08), tags=["screen", "panel"], adjacency=[bezel_part]),
        _component("control_panel_region", "panel", control_part, (0.0, -height * 0.14, depth * 0.34), (width * 0.62, height * 0.18, depth * 0.12), tags=["panel", "controls"], adjacency=[body_part]),
        _component("console_stand_region", "stand", stand_part, (0.0, -height * 0.82, 0.0), (width * 0.30, height * 0.86, depth * 0.30), tags=["stand"], interface_role="support", adjacency=[body_part, socket_part]),
        _component("socket_plate_region", "socket_plate", socket_part, (0.0, -height * 0.34, -depth * 0.28), (width * 0.38, height * 0.12, depth * 0.18), tags=["socket", "plate"], adjacency=[body_part, stand_part]),
    ]
    if vent_l:
        components.append(
            _component(
                "console_vent_left_region",
                "vent",
                vent_l,
                (-width * 0.26, -height * 0.04, depth * 0.36),
                (width * 0.14, height * 0.20, depth * 0.10),
                tags=["vent", "left"],
                adjacency=[body_part, control_part],
                symmetry_mate=vent_r,
            )
        )
    if vent_r:
        components.append(
            _component(
                "console_vent_right_region",
                "vent",
                vent_r,
                mirrored((-width * 0.26, -height * 0.04, depth * 0.36)),
                (width * 0.14, height * 0.20, depth * 0.10),
                tags=["vent", "right"],
                adjacency=[body_part, control_part],
                symmetry_mate=vent_l,
            )
        )
    return AssemblyBlueprint(asset_graph.blueprint_id, asset_graph.family, components, notes=["console terminal assembled from shared shell, bezel, panel, stand, vent, and socket-plate primitives"])


def _service_cabinet_blueprint(asset_graph: AssetGraph, rng: np.random.Generator, candidate_index: int) -> AssemblyBlueprint:
    scale = asset_graph.scale_cm
    width = scale * 0.94 * float(1.0 + rng.uniform(-0.03, 0.03))
    height = scale * 1.34 * float(1.0 + rng.uniform(-0.03, 0.03))
    depth = scale * 0.56 * float(1.0 + rng.uniform(-0.03, 0.03))
    body_part = _part_name(asset_graph, "body")
    door_l, door_r = _pair_parts(asset_graph, "door")
    handle_l, handle_r = _pair_parts(asset_graph, "handle")
    foot_l, foot_r = _pair_parts(asset_graph, "foot")
    vent_part = _part_name(asset_graph, "vent", fallback=body_part)
    shelf_parts = [part.name for part in asset_graph.parts if "shelf" in part.tags]
    components = [
        _component("cabinet_shell", "shell", body_part, (0.0, 0.0, 0.0), (width, height, depth), tags=["body", "cabinet"]),
        _component("cabinet_frame_front", "frame", body_part, (0.0, 0.0, depth * 0.40), (width * 0.96, height * 0.92, depth * 0.08), tags=["frame", "front"]),
        _component("cabinet_vent_region", "vent", vent_part, (0.0, height * 0.20, depth * 0.38), (width * 0.34, height * 0.22, depth * 0.08), tags=["vent", "panel"]),
    ]
    if door_l:
        components.append(
            _component(
                "cabinet_door_left_region",
                "door",
                door_l,
                (-width * 0.22, 0.0, depth * 0.42),
                (width * 0.40, height * 0.78, depth * 0.06),
                tags=["door", "left"],
                adjacency=[body_part],
                symmetry_mate=door_r,
            )
        )
    if door_r:
        components.append(
            _component(
                "cabinet_door_right_region",
                "door",
                door_r,
                mirrored((-width * 0.22, 0.0, depth * 0.42)),
                (width * 0.40, height * 0.78, depth * 0.06),
                tags=["door", "right"],
                adjacency=[body_part],
                symmetry_mate=door_l,
            )
        )
    if handle_l:
        components.append(
            _component(
                "cabinet_handle_left_region",
                "handle",
                handle_l,
                (-width * 0.05, 0.0, depth * 0.48),
                (width * 0.06, height * 0.16, depth * 0.08),
                tags=["handle", "left"],
                axis="y",
                radius=depth * 0.18,
                height=height * 0.18,
                interface_role="grip",
                symmetry_mate=handle_r,
            )
        )
    if handle_r:
        components.append(
            _component(
                "cabinet_handle_right_region",
                "handle",
                handle_r,
                mirrored((-width * 0.05, 0.0, depth * 0.48)),
                (width * 0.06, height * 0.16, depth * 0.08),
                tags=["handle", "right"],
                axis="y",
                radius=depth * 0.18,
                height=height * 0.18,
                interface_role="grip",
                symmetry_mate=handle_l,
            )
        )
    for index, shelf_part in enumerate(shelf_parts[:2]):
        y_offset = height * (0.16 - index * 0.28)
        components.append(
            _component(
                f"cabinet_shelf_{index}_region",
                "panel",
                shelf_part,
                (0.0, y_offset, 0.0),
                (width * 0.82, height * 0.05, depth * 0.76),
                tags=["panel", "shelf"],
                adjacency=[body_part],
            )
        )
    if foot_l:
        components.append(
            _component(
                "cabinet_foot_left_region",
                "foot",
                foot_l,
                (-width * 0.28, -height * 0.54, depth * 0.18),
                (width * 0.10, height * 0.08, depth * 0.12),
                tags=["foot", "left"],
                symmetry_mate=foot_r,
                interface_role="support",
            )
        )
    if foot_r:
        components.append(
            _component(
                "cabinet_foot_right_region",
                "foot",
                foot_r,
                mirrored((-width * 0.28, -height * 0.54, depth * 0.18)),
                (width * 0.10, height * 0.08, depth * 0.12),
                tags=["foot", "right"],
                symmetry_mate=foot_l,
                interface_role="support",
            )
        )
    return AssemblyBlueprint(asset_graph.blueprint_id, asset_graph.family, components, notes=["service cabinet compiled from shared shell, frame, door, vent, shelf, handle, and foot primitives"])


def _control_pedestal_blueprint(asset_graph: AssetGraph, rng: np.random.Generator, candidate_index: int) -> AssemblyBlueprint:
    scale = asset_graph.scale_cm
    width = scale * 0.56 * float(1.0 + rng.uniform(-0.03, 0.03))
    height = scale * 1.20 * float(1.0 + rng.uniform(-0.03, 0.03))
    depth = scale * 0.50 * float(1.0 + rng.uniform(-0.03, 0.03))
    body_part = _part_name(asset_graph, "body")
    bezel_part = _part_name(asset_graph, "bezel", fallback=_part_name(asset_graph, "frame", fallback=body_part))
    screen_part = _part_name(asset_graph, "screen", fallback=_part_name(asset_graph, "panel", fallback=body_part))
    control_part = _part_name(asset_graph, "console", fallback=_part_name(asset_graph, "panel", fallback=screen_part))
    column_part = _part_name(asset_graph, "column", fallback=_part_name(asset_graph, "stand", fallback=body_part))
    base_part = _part_name(asset_graph, "base", fallback=_part_name(asset_graph, "plate", fallback=body_part))
    hatch_part = _part_name(asset_graph, "hatch", fallback=_part_name(asset_graph, "door", fallback=body_part))
    socket_part = _part_name(asset_graph, "socket", fallback=_part_name(asset_graph, "plate", fallback=body_part))
    components = [
        _component("pedestal_shell", "shell", body_part, (0.0, 0.0, 0.0), (width, height * 0.36, depth), tags=["body", "pedestal"]),
        _component("pedestal_bezel_region", "bezel", bezel_part, (0.0, height * 0.18, depth * 0.34), (width * 0.72, height * 0.30, depth * 0.12), tags=["bezel", "screen"], adjacency=[screen_part]),
        _component("pedestal_screen_region", "panel", screen_part, (0.0, height * 0.18, depth * 0.38), (width * 0.58, height * 0.22, depth * 0.08), tags=["screen", "panel"], adjacency=[bezel_part]),
        _component("pedestal_control_region", "panel", control_part, (0.0, -height * 0.04, depth * 0.32), (width * 0.62, height * 0.16, depth * 0.10), tags=["panel", "controls"], adjacency=[body_part]),
        _component("pedestal_column_region", "stand", column_part, (0.0, -height * 0.42, 0.0), (width * 0.28, height * 0.58, depth * 0.24), tags=["stand", "column"], interface_role="support", adjacency=[body_part, base_part]),
        _component("pedestal_base_region", "panel", base_part, (0.0, -height * 0.76, 0.0), (width * 0.62, height * 0.08, depth * 0.54), tags=["plate", "base"], interface_role="support", adjacency=[column_part]),
        _component("pedestal_hatch_region", "door", hatch_part, (0.0, -height * 0.18, -depth * 0.26), (width * 0.34, height * 0.18, depth * 0.06), tags=["door", "hatch"], adjacency=[body_part]),
        _component("pedestal_socket_region", "socket_plate", socket_part, (0.0, -height * 0.32, -depth * 0.28), (width * 0.30, height * 0.08, depth * 0.14), tags=["socket", "plate"], adjacency=[column_part]),
    ]
    return AssemblyBlueprint(asset_graph.blueprint_id, asset_graph.family, components, notes=["control pedestal compiled from shared shell, bezel, screen, control panel, column, base, hatch, and socket primitives"])


def _supply_container_blueprint(asset_graph: AssetGraph, rng: np.random.Generator, candidate_index: int) -> AssemblyBlueprint:
    scale = asset_graph.scale_cm
    width = scale * 0.76 * float(1.0 + rng.uniform(-0.03, 0.03))
    height = scale * 0.50 * float(1.0 + rng.uniform(-0.03, 0.03))
    depth = scale * 0.60 * float(1.0 + rng.uniform(-0.03, 0.03))
    body_part = _part_name(asset_graph, "body")
    lid_part = _part_name(asset_graph, "lid", fallback=body_part)
    band_part = _part_name(asset_graph, "band", fallback=_part_name(asset_graph, "frame", fallback=body_part))
    latch_part = _part_name(asset_graph, "lock", fallback=_part_name(asset_graph, "latch", fallback=_part_name(asset_graph, "plate", fallback=body_part)))
    handle_l, handle_r = _pair_parts(asset_graph, "handle")
    foot_l, foot_r = _pair_parts(asset_graph, "foot")
    components = [
        _component("supply_shell", "shell", body_part, (0.0, -height * 0.08, 0.0), (width, height * 0.62, depth), tags=["body", "container"]),
        _component("supply_lid_region", "lid", lid_part, (0.0, height * 0.18, 0.0), (width * 0.94, height * 0.24, depth * 0.92), tags=["lid"], adjacency=[body_part, latch_part]),
        _component("supply_band_region", "frame", band_part, (0.0, 0.0, depth * 0.36), (width * 0.92, height * 0.18, depth * 0.08), tags=["band", "front"], adjacency=[body_part, lid_part]),
        _component("supply_latch_region", "lock_plate", latch_part, (0.0, height * 0.02, depth * 0.48), (width * 0.18, height * 0.14, depth * 0.08), tags=["lock", "plate"], adjacency=[lid_part, body_part]),
    ]
    if handle_l:
        components.append(
            _component(
                "supply_handle_left_region",
                "handle",
                handle_l,
                (-width * 0.52, 0.0, 0.0),
                (width * 0.10, height * 0.16, depth * 0.14),
                tags=["handle", "left"],
                axis="x",
                radius=height * 0.08,
                height=width * 0.10,
                interface_role="grip",
                symmetry_mate=handle_r,
            )
        )
    if handle_r:
        components.append(
            _component(
                "supply_handle_right_region",
                "handle",
                handle_r,
                mirrored((-width * 0.52, 0.0, 0.0)),
                (width * 0.10, height * 0.16, depth * 0.14),
                tags=["handle", "right"],
                axis="x",
                radius=height * 0.08,
                height=width * 0.10,
                interface_role="grip",
                symmetry_mate=handle_l,
            )
        )
    if foot_l:
        components.append(
            _component(
                "supply_foot_left_region",
                "foot",
                foot_l,
                (-width * 0.30, -height * 0.44, depth * 0.18),
                (width * 0.12, height * 0.08, depth * 0.14),
                tags=["foot", "left"],
                symmetry_mate=foot_r,
                interface_role="support",
            )
        )
    if foot_r:
        components.append(
            _component(
                "supply_foot_right_region",
                "foot",
                foot_r,
                mirrored((-width * 0.30, -height * 0.44, depth * 0.18)),
                (width * 0.12, height * 0.08, depth * 0.14),
                tags=["foot", "right"],
                symmetry_mate=foot_l,
                interface_role="support",
            )
        )
    return AssemblyBlueprint(asset_graph.blueprint_id, asset_graph.family, components, notes=["supply container compiled from shared shell, lid, strap, latch, handle, and foot primitives"])


def _generic_blueprint(asset_graph: AssetGraph, rng: np.random.Generator, candidate_index: int) -> AssemblyBlueprint:
    scale = asset_graph.scale_cm
    if asset_graph.kind == "env_module":
        width = scale * 1.18
        height = scale * 1.36
        depth = scale * 0.22
        body_center = (0.0, 0.0, 0.0)
    else:
        width = scale * 0.64
        height = scale * 0.38
        depth = scale * 0.56
        body_center = (0.0, 0.0, 0.0)
    body_part = _part_name(asset_graph, "body")
    components = [_component("generic_shell", "shell", body_part, body_center, (width, height, depth), tags=["body", "generic"])]
    for index, part in enumerate(asset_graph.parts):
        if part.name == body_part:
            continue
        offset_x = ((index % 2) * 2 - 1) * width * 0.32
        offset_y = 0.0 if asset_graph.kind != "env_module" else (height * 0.18 if index % 3 == 0 else -height * 0.18)
        offset_z = (index // 2 - max(0, len(asset_graph.parts) - 2) / 4.0) * depth * 0.18
        component_type = "panel"
        if part.assembly_role in {"handle"}:
            component_type = "handle"
        elif part.assembly_role in {"foot", "stand", "leg"}:
            component_type = "foot"
        elif part.assembly_role in {"door"}:
            component_type = "door"
        elif part.assembly_role in {"screen", "panel"}:
            component_type = "panel"
        components.append(
            _component(
                f"{part.name}_generic_region",
                component_type,
                part.name,
                (offset_x, offset_y, offset_z),
                (width * 0.18, height * 0.18, depth * 0.18),
                tags=list(part.tags),
                symmetry_mate=part.symmetry_mate,
                interface_role=part.interface_role,
            )
        )
    return AssemblyBlueprint(asset_graph.blueprint_id, asset_graph.family, components, notes=["generic hard-surface assembly fallback compiled from shared shell/panel primitives"])


def resolve_blueprint(
    asset_graph: AssetGraph,
    conditioning: dict[str, Any],
    rng: np.random.Generator,
    candidate_index: int,
) -> AssemblyBlueprint:
    family = asset_graph.family
    if family == "brassbound_chest":
        return _chest_blueprint(asset_graph, rng, candidate_index)
    if family == "courier_drone":
        return _drone_blueprint(asset_graph, rng, candidate_index)
    if family == "sci_fi_wall_panel":
        return _wall_panel_blueprint(asset_graph, rng, candidate_index)
    if family == "industrial_crate":
        return _crate_blueprint(asset_graph, rng, candidate_index)
    if family == "mechanical_door":
        return _door_blueprint(asset_graph, rng, candidate_index)
    if family == "console_terminal":
        return _console_blueprint(asset_graph, rng, candidate_index)
    if family == "service_cabinet":
        return _service_cabinet_blueprint(asset_graph, rng, candidate_index)
    if family == "control_pedestal":
        return _control_pedestal_blueprint(asset_graph, rng, candidate_index)
    if family == "supply_container":
        return _supply_container_blueprint(asset_graph, rng, candidate_index)
    return _generic_blueprint(asset_graph, rng, candidate_index)
