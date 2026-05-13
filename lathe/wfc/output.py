"""Translate a WFCResult into engine-side or kernel-side artifacts.

Two output adapters are provided:

* :func:`to_scene_objects` — produces a list of plain-dict scene
  objects keyed by tile ID and grid position, suitable for emission
  through the scene IR or the asset_graph layer.
* :func:`to_blueprint_components` — produces a list of
  :class:`lathe.assembly_kernel.BlueprintComponent` instances, so the
  solved grid can drop straight into the assembly_kernel pipeline as
  if it were any other authored blueprint.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .solver import WFCResult
from .tileset import Tileset

if TYPE_CHECKING:  # pragma: no cover - imported only for type hints
    from ..assembly_kernel import BlueprintComponent


def to_scene_objects(result: WFCResult, tileset: Tileset) -> list[dict[str, Any]]:
    """Plain-dict scene-object list for IR-level consumers."""
    objects: list[dict[str, Any]] = []
    for placement in result.placements:
        tile = tileset.by_id(placement.tile_id)
        objects.append(
            {
                "name": f"wfc_{tile.id}_{placement.position[0]}_{placement.position[1]}_{placement.position[2]}",
                "tile_id": tile.id,
                "mesh_ref": tile.mesh_ref,
                "grid_position": list(placement.position),
                "transform": list(placement.transform),
            }
        )
    return objects


def to_blueprint_components(
    result: WFCResult,
    tileset: Tileset,
    *,
    cell_extents: tuple[float, float, float] = (1.0, 1.0, 1.0),
) -> list[BlueprintComponent]:
    """Bridge into the assembly_kernel via :class:`BlueprintComponent`.

    Each placed tile becomes one blueprint component centred at its
    grid transform. The component name is unique per cell, the part
    is taken from the tile id, and the mesh_ref + connector tags are
    smuggled in via tags so downstream stages can read them without
    extending the dataclass.
    """
    from ..assembly_kernel import BlueprintComponent  # local import: avoid cycles

    components: list[BlueprintComponent] = []
    for placement in result.placements:
        tile = tileset.by_id(placement.tile_id)
        connector_tags = [f"connector:{d}={tile.connector(d)}" for d in tile.connectors]
        components.append(
            BlueprintComponent(
                name=f"wfc_{tile.id}_{placement.position[0]}_{placement.position[1]}_{placement.position[2]}",
                component_type="wfc_tile",
                part=tile.id,
                center=placement.transform,
                extents=cell_extents,
                tags=[f"mesh_ref:{tile.mesh_ref}", *connector_tags],
            )
        )
    return components
