"""Generic fallback assembly blueprint generation."""

from __future__ import annotations

import numpy as np

from ..assembly_kernel import AssemblyBlueprint
from ..asset_graph import AssetGraph
from .common import _component, _part_name


def _generic_blueprint(
    asset_graph: AssetGraph, rng: np.random.Generator, candidate_index: int
) -> AssemblyBlueprint:
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
    components = [
        _component(
            "generic_shell", "shell", body_part, body_center, (width, height, depth), tags=["body", "generic"]
        )
    ]
    for index, part in enumerate(asset_graph.parts):
        if part.name == body_part:
            continue
        offset_x = ((index % 2) * 2 - 1) * width * 0.32
        offset_y = (
            0.0 if asset_graph.kind != "env_module" else (height * 0.18 if index % 3 == 0 else -height * 0.18)
        )
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
    return AssemblyBlueprint(
        asset_graph.blueprint_id,
        asset_graph.family,
        components,
        notes=["generic hard-surface assembly fallback compiled from shared shell/panel primitives"],
    )
