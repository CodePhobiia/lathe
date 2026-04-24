from __future__ import annotations

from ..assembly_kernel import BlueprintComponent
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
