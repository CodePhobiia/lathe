"""Container-family assembly blueprints."""

from __future__ import annotations

import numpy as np

from ..assembly_kernel import AssemblyBlueprint, mirrored
from ..asset_graph import AssetGraph
from .common import _component, _pair_parts, _part_name


def _chest_blueprint(
    asset_graph: AssetGraph, rng: np.random.Generator, candidate_index: int
) -> AssemblyBlueprint:
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
        _component(
            "body_shell",
            "shell",
            body_part,
            (0.0, -height * 0.10, 0.0),
            (width, base_height, depth),
            tags=["body", "container", "chest", "plank_displacement", "oak_planks"],
        ),
        _component(
            "body_frame_front",
            "frame",
            body_part,
            (0.0, -height * 0.10, depth * 0.39),
            (width * 0.92, base_height * 0.34, depth * 0.08),
            tags=["frame", "front", "container", "chest"],
            adjacency=[door_part],
        ),
        _component(
            "body_frame_rear",
            "frame",
            body_part,
            (0.0, -height * 0.10, -depth * 0.39),
            (width * 0.92, base_height * 0.28, depth * 0.08),
            tags=["frame", "rear", "container", "chest"],
        ),
        _component(
            "lid_region",
            "lid",
            lid_part,
            (0.0, height * 0.19, 0.0),
            (width * 0.96, lid_height, depth * 0.92),
            tags=["lid", "container", "chest"],
            adjacency=[body_part, lock_part],
        ),
        _component(
            "front_hatch_region",
            "door",
            door_part,
            (0.0, -height * 0.03, depth * 0.48),
            (width * 0.78, base_height * 0.26, depth * 0.10),
            tags=["door", "front", "container", "chest"],
            adjacency=[body_part, lock_part],
        ),
        _component(
            "lock_region",
            "lock_plate",
            lock_part,
            (0.0, height * 0.03, depth * 0.53),
            (width * 0.16, height * 0.18, depth * 0.08),
            tags=["lock", "front", "container", "chest"],
            adjacency=[lid_part, door_part],
        ),
    ]
    if handle_l:
        components.append(
            _component(
                "handle_left_region",
                "handle",
                handle_l,
                (-width * 0.53, -height * 0.02, 0.0),
                (width * 0.10, height * 0.18, depth * 0.14),
                tags=["handle", "left", "container", "chest"],
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
                tags=["handle", "right", "container", "chest"],
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
                tags=["foot", "left", "container", "chest"],
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
                tags=["foot", "right", "container", "chest"],
                symmetry_mate=foot_l,
                interface_role="support",
            )
        )
    return AssemblyBlueprint(
        asset_graph.blueprint_id,
        asset_graph.family,
        components,
        notes=["container shell + lid + front hatch compiled from shared hard-surface primitives"],
    )


def _crate_blueprint(
    asset_graph: AssetGraph, rng: np.random.Generator, candidate_index: int
) -> AssemblyBlueprint:
    scale = asset_graph.scale_cm
    width = scale * 0.72 * float(1.0 + rng.uniform(-0.03, 0.03))
    height = scale * 0.52 * float(1.0 + rng.uniform(-0.03, 0.03))
    depth = scale * 0.60 * float(1.0 + rng.uniform(-0.03, 0.03))
    body_part = _part_name(asset_graph, "body")
    latch_part = _part_name(
        asset_graph, "latch", fallback=_part_name(asset_graph, "plate", fallback=body_part)
    )
    handle_l, handle_r = _pair_parts(asset_graph, "handle")
    foot_l, foot_r = _pair_parts(asset_graph, "foot")
    components = [
        _component(
            "crate_shell", "shell", body_part, (0.0, 0.0, 0.0), (width, height, depth), tags=["body", "crate"]
        ),
        _component(
            "crate_frame_front",
            "frame",
            body_part,
            (0.0, 0.0, depth * 0.39),
            (width * 0.96, height * 0.72, depth * 0.08),
            tags=["frame", "front"],
        ),
        _component(
            "crate_frame_back",
            "frame",
            body_part,
            (0.0, 0.0, -depth * 0.39),
            (width * 0.96, height * 0.72, depth * 0.08),
            tags=["frame", "rear"],
        ),
        _component(
            "crate_latch_region",
            "latch",
            latch_part,
            (0.0, height * 0.08, depth * 0.46),
            (width * 0.22, height * 0.16, depth * 0.08),
            tags=["latch", "front"],
        ),
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
    return AssemblyBlueprint(
        asset_graph.blueprint_id,
        asset_graph.family,
        components,
        notes=["industrial crate assembled from shared shell, frame, latch, handle, and foot primitives"],
    )


def _supply_container_blueprint(
    asset_graph: AssetGraph, rng: np.random.Generator, candidate_index: int
) -> AssemblyBlueprint:
    scale = asset_graph.scale_cm
    width = scale * 0.76 * float(1.0 + rng.uniform(-0.03, 0.03))
    height = scale * 0.50 * float(1.0 + rng.uniform(-0.03, 0.03))
    depth = scale * 0.60 * float(1.0 + rng.uniform(-0.03, 0.03))
    body_part = _part_name(asset_graph, "body")
    lid_part = _part_name(asset_graph, "lid", fallback=body_part)
    band_part = _part_name(asset_graph, "band", fallback=_part_name(asset_graph, "frame", fallback=body_part))
    latch_part = _part_name(
        asset_graph,
        "lock",
        fallback=_part_name(
            asset_graph, "latch", fallback=_part_name(asset_graph, "plate", fallback=body_part)
        ),
    )
    handle_l, handle_r = _pair_parts(asset_graph, "handle")
    foot_l, foot_r = _pair_parts(asset_graph, "foot")
    components = [
        _component(
            "supply_shell",
            "shell",
            body_part,
            (0.0, -height * 0.08, 0.0),
            (width, height * 0.62, depth),
            tags=["body", "container"],
        ),
        _component(
            "supply_lid_region",
            "lid",
            lid_part,
            (0.0, height * 0.18, 0.0),
            (width * 0.94, height * 0.24, depth * 0.92),
            tags=["lid"],
            adjacency=[body_part, latch_part],
        ),
        _component(
            "supply_band_region",
            "frame",
            band_part,
            (0.0, 0.0, depth * 0.36),
            (width * 0.92, height * 0.18, depth * 0.08),
            tags=["band", "front"],
            adjacency=[body_part, lid_part],
        ),
        _component(
            "supply_latch_region",
            "lock_plate",
            latch_part,
            (0.0, height * 0.02, depth * 0.48),
            (width * 0.18, height * 0.14, depth * 0.08),
            tags=["lock", "plate"],
            adjacency=[lid_part, body_part],
        ),
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
    return AssemblyBlueprint(
        asset_graph.blueprint_id,
        asset_graph.family,
        components,
        notes=["supply container compiled from shared shell, lid, strap, latch, handle, and foot primitives"],
    )
