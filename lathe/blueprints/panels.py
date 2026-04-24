from __future__ import annotations

import numpy as np

from ..assembly_kernel import AssemblyBlueprint, mirrored
from ..asset_graph import AssetGraph
from .common import _component, _pair_parts, _part_name


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
