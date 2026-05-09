"""Worked WFC examples.

Provides a 6-tile dungeon corridor kit and a helper that runs the
solver on a 10x1x10 grid with seed=0. The connector vocabulary is
intentionally simple:

* ``"open"`` — passable corridor opening
* ``"solid"`` — solid wall
* ``"floor"`` — open floor face (used for vertical mating)
* ``"ceil"`` — closed ceiling face
* ``"void"`` — outside the grid (default tag)

Connector matching is exact-string, with one exception: tiles tag
their downward (-Z) face with ``"floor"`` and their upward (+Z) face
with ``"ceil"`` so they sit on a single horizontal slab.
"""

from __future__ import annotations

from .adjacency import from_connectors
from .output import to_blueprint_components, to_scene_objects
from .solver import WFCResult, WFCSolver, solve_wfc
from .tileset import Tile, Tileset


def dungeon_corridor_tileset() -> Tileset:
    """The canonical 6-tile dungeon corridor kit.

    Layout: 10x1x10, single-storey corridor. ``+X/-X`` is east/west,
    ``+Y/-Y`` is north/south, ``+Z/-Z`` is up/down.
    """

    return Tileset(
        name="dungeon_corridor",
        tiles=[
            Tile(
                id="floor_open",
                mesh_ref="kits/dungeon/floor_open.glb",
                connectors={
                    "+X": "open",
                    "-X": "open",
                    "+Y": "open",
                    "-Y": "open",
                    "+Z": "ceil",
                    "-Z": "floor",
                },
                weight=4.0,
            ),
            Tile(
                id="wall_NS",
                mesh_ref="kits/dungeon/wall_ns.glb",
                connectors={
                    "+X": "solid",
                    "-X": "solid",
                    "+Y": "open",
                    "-Y": "open",
                    "+Z": "ceil",
                    "-Z": "floor",
                },
                weight=2.0,
            ),
            Tile(
                id="wall_EW",
                mesh_ref="kits/dungeon/wall_ew.glb",
                connectors={
                    "+X": "open",
                    "-X": "open",
                    "+Y": "solid",
                    "-Y": "solid",
                    "+Z": "ceil",
                    "-Z": "floor",
                },
                weight=2.0,
            ),
            Tile(
                id="corner_NE",
                mesh_ref="kits/dungeon/corner_ne.glb",
                connectors={
                    "+X": "solid",
                    "-X": "open",
                    "+Y": "solid",
                    "-Y": "open",
                    "+Z": "ceil",
                    "-Z": "floor",
                },
                weight=1.0,
            ),
            Tile(
                id="t_junction_N",
                mesh_ref="kits/dungeon/t_junction_n.glb",
                connectors={
                    "+X": "open",
                    "-X": "open",
                    "+Y": "open",
                    "-Y": "solid",
                    "+Z": "ceil",
                    "-Z": "floor",
                },
                weight=1.0,
            ),
            Tile(
                id="cross",
                mesh_ref="kits/dungeon/cross.glb",
                connectors={
                    "+X": "open",
                    "-X": "open",
                    "+Y": "open",
                    "-Y": "open",
                    "+Z": "ceil",
                    "-Z": "floor",
                },
                weight=0.5,
            ),
        ],
    )


def run_dungeon_corridor(
    *,
    grid_shape: tuple[int, int, int] = (10, 10, 1),
    seed: int = 0,
) -> WFCResult:
    """Solve the canonical 10x10x1 dungeon corridor at the given seed.

    Note the grid is laid out in ``(x, y, z)``: 10 east-west, 10
    north-south, 1 high. ``-Z`` connectors are unmatched at the bottom
    layer because there is nothing beneath; the ``"floor"`` tag pairs
    only with itself, so empty space outside the grid is implicitly
    treated as ``"void"``.
    """

    tileset = dungeon_corridor_tileset()
    adjacency = from_connectors(tileset)
    return solve_wfc(tileset, adjacency, grid_shape, seed=seed)


__all__ = [
    "dungeon_corridor_tileset",
    "run_dungeon_corridor",
    "WFCResult",
    "WFCSolver",
    "to_blueprint_components",
    "to_scene_objects",
]
