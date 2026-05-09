"""WFC modular assembly: tilesets, adjacency rules, and solver.

This is the foundation slice for roadmap §7.3. It implements Maxim
Gumin's Wave Function Collapse algorithm as a pure-Python (numpy-only)
solver over a 3D grid of tile superpositions, with deterministic
collapse driven by `numpy.random.default_rng(seed)`.

Public API:

* :class:`Tile`, :class:`Tileset` — define placeable tiles plus their
  per-face connector tags.
* :class:`AdjacencyRules`, :func:`from_tileset` — author or auto-derive
  the directional adjacency relation.
* :class:`WFCSolver`, :func:`solve_wfc` — run the algorithm.
* :class:`WFCResult`, :class:`PlacedTile` — the solved grid output.
* :class:`WFCContradiction` — raised on unsolvable adjacency, carrying
  a deterministic seed-search hint.
* :func:`to_scene_objects`, :func:`to_blueprint_components` — bridge
  results into scene IR or `assembly_kernel.BlueprintComponent`.
"""

from __future__ import annotations

from .adjacency import AdjacencyRules, from_connectors
from .adjacency import from_connectors as from_tileset
from .mesh_program_ops import (
    WFCModuleRef,
    WFCRuleRef,
    build_solver_inputs,
    expand_solved_grid,
    solve_modular,
)
from .output import to_blueprint_components, to_scene_objects
from .solver import (
    GridPos,
    GridShape,
    PlacedTile,
    WFCContradiction,
    WFCResult,
    WFCSolver,
    solve_wfc,
)
from .tileset import DIRECTIONS, OPPOSITE, Direction, Tile, Tileset

__all__ = [
    "AdjacencyRules",
    "DIRECTIONS",
    "Direction",
    "GridPos",
    "GridShape",
    "OPPOSITE",
    "PlacedTile",
    "Tile",
    "Tileset",
    "WFCModuleRef",
    "WFCContradiction",
    "WFCRuleRef",
    "WFCResult",
    "WFCSolver",
    "build_solver_inputs",
    "expand_solved_grid",
    "from_connectors",
    "from_tileset",
    "solve_modular",
    "solve_wfc",
    "to_blueprint_components",
    "to_scene_objects",
]
