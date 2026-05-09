"""WFC tileset definitions.

A tileset is a collection of named tiles. Each tile carries a mesh
reference (or kit_call ID), per-face connector tags, and an optional
frequency hint that biases collapse weight without breaking determinism
under a fixed seed.

Connector matching is the default adjacency derivation: two tiles are
adjacent on direction `d` iff the connector tag on the outgoing face of
tile A equals the connector tag on the opposing face of tile B. This is
the simplest WFC variant; more elaborate flip/rotation tag schemes are
out of scope for the foundation slice.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

Direction = str  # one of "+X", "-X", "+Y", "-Y", "+Z", "-Z"

DIRECTIONS: tuple[Direction, ...] = ("+X", "-X", "+Y", "-Y", "+Z", "-Z")

OPPOSITE: dict[Direction, Direction] = {
    "+X": "-X",
    "-X": "+X",
    "+Y": "-Y",
    "-Y": "+Y",
    "+Z": "-Z",
    "-Z": "+Z",
}

DIRECTION_OFFSETS: dict[Direction, tuple[int, int, int]] = {
    "+X": (1, 0, 0),
    "-X": (-1, 0, 0),
    "+Y": (0, 1, 0),
    "-Y": (0, -1, 0),
    "+Z": (0, 0, 1),
    "-Z": (0, 0, -1),
}


@dataclass(frozen=True)
class Tile:
    """A single placeable WFC tile.

    Attributes:
        id: Stable identifier within a tileset (used by adjacency rules
            and the solver output).
        mesh_ref: Reference to a mesh, kit_call ID, or component name.
            Treated as opaque by the solver.
        connectors: Mapping from face direction to connector tag. Faces
            absent from the mapping behave as if tagged ``"void"``.
        weight: Frequency hint. Higher weights bias the deterministic
            collapse pick toward this tile when it is among the
            allowed options for the chosen cell.
    """

    id: str
    mesh_ref: str
    connectors: Mapping[Direction, str] = field(default_factory=dict)
    weight: float = 1.0

    def connector(self, direction: Direction) -> str:
        return self.connectors.get(direction, "void")


@dataclass
class Tileset:
    """A named collection of WFC tiles."""

    name: str
    tiles: list[Tile] = field(default_factory=list)

    def __post_init__(self) -> None:
        seen: set[str] = set()
        for tile in self.tiles:
            if tile.id in seen:
                raise ValueError(f"duplicate tile id {tile.id!r} in tileset {self.name!r}")
            seen.add(tile.id)

    @property
    def tile_ids(self) -> tuple[str, ...]:
        return tuple(tile.id for tile in self.tiles)

    @property
    def tile_weights(self) -> dict[str, float]:
        return {tile.id: tile.weight for tile in self.tiles}

    def by_id(self, tile_id: str) -> Tile:
        for tile in self.tiles:
            if tile.id == tile_id:
                return tile
        raise KeyError(f"tile {tile_id!r} not found in tileset {self.name!r}")
