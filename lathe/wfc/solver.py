"""Wave Function Collapse solver.

Implements the standard WFC algorithm (Maxim Gumin, 2016):

1. Initialize each cell with a superposition of all tile IDs.
2. Find the lowest-entropy cell (fewest remaining options). Break ties
   by lexicographic grid position so the result is fully deterministic
   under a fixed seed.
3. Collapse the chosen cell to one tile, weighted by tile frequency.
4. Propagate the collapse: for every neighbor of every changed cell,
   discard tile options that have no allowed neighbor in the current
   superposition. Repeat until the queue is empty.
5. Repeat from step 2 until all cells are collapsed, or a contradiction
   (empty superposition) is detected.

Determinism is guaranteed by `numpy.random.default_rng(seed)`. On
contradiction the solver raises :class:`WFCContradiction` with a hint
listing nearby seed values for the caller to retry — this is the
"deterministic seed-search hint" called for by the roadmap.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

import numpy as np

from .adjacency import AdjacencyRules
from .tileset import DIRECTION_OFFSETS, DIRECTIONS, Direction, Tileset

GridShape = tuple[int, int, int]
GridPos = tuple[int, int, int]


class WFCContradiction(RuntimeError):
    """Raised when the solver runs out of options for some cell.

    The exception carries the failing cell, the seed used for this
    attempt, and a small range of nearby seeds the caller can retry
    deterministically.
    """

    def __init__(
        self,
        cell: GridPos,
        seed: int,
        seed_hints: tuple[int, ...],
        message: str | None = None,
    ) -> None:
        self.cell = cell
        self.seed = seed
        self.seed_hints = seed_hints
        super().__init__(
            message
            or f"WFC contradiction at cell {cell} with seed={seed}; "
            f"try seeds {list(seed_hints)} for a deterministic retry"
        )


@dataclass(frozen=True)
class PlacedTile:
    """One collapsed cell of the solved grid."""

    tile_id: str
    position: GridPos
    transform: tuple[float, float, float] = (0.0, 0.0, 0.0)


@dataclass
class WFCResult:
    """Output of a successful WFC solve."""

    seed: int
    grid_shape: GridShape
    placements: list[PlacedTile] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "seed": self.seed,
            "grid_shape": list(self.grid_shape),
            "placements": [
                {
                    "tile_id": p.tile_id,
                    "position": list(p.position),
                    "transform": list(p.transform),
                }
                for p in self.placements
            ],
        }


class WFCSolver:
    """Stateful, deterministic WFC solver."""

    def __init__(
        self,
        tileset: Tileset,
        adjacency: AdjacencyRules,
        grid_shape: GridShape,
        *,
        seed: int = 0,
        cell_size: tuple[float, float, float] = (1.0, 1.0, 1.0),
    ) -> None:
        if any(d <= 0 for d in grid_shape):
            raise ValueError(f"grid_shape must be positive in all dims, got {grid_shape}")
        self.tileset = tileset
        self.adjacency = adjacency
        self.grid_shape = grid_shape
        self.seed = int(seed)
        self.cell_size = cell_size
        self._rng = np.random.default_rng(self.seed)
        self._tile_ids: tuple[str, ...] = tileset.tile_ids
        if not self._tile_ids:
            raise ValueError(f"tileset {tileset.name!r} is empty")
        self._weights = tileset.tile_weights
        # Each cell holds the set of still-possible tile IDs.
        self._cells: dict[GridPos, set[str]] = {
            pos: set(self._tile_ids) for pos in self._iter_positions()
        }

    # ------------------------------------------------------------------ helpers

    def _iter_positions(self) -> Iterable[GridPos]:
        sx, sy, sz = self.grid_shape
        for x in range(sx):
            for y in range(sy):
                for z in range(sz):
                    yield (x, y, z)

    def _in_bounds(self, pos: GridPos) -> bool:
        sx, sy, sz = self.grid_shape
        x, y, z = pos
        return 0 <= x < sx and 0 <= y < sy and 0 <= z < sz

    def _neighbor(self, pos: GridPos, direction: Direction) -> GridPos | None:
        dx, dy, dz = DIRECTION_OFFSETS[direction]
        x, y, z = pos
        nb = (x + dx, y + dy, z + dz)
        return nb if self._in_bounds(nb) else None

    # ------------------------------------------------------------------ status

    @property
    def is_collapsed(self) -> bool:
        return all(len(opts) == 1 for opts in self._cells.values())

    def _lowest_entropy_cell(self) -> GridPos | None:
        best: GridPos | None = None
        best_count = 1 << 30
        for pos in self._iter_positions():
            n = len(self._cells[pos])
            if n > 1 and n < best_count:
                best_count = n
                best = pos
        return best

    # ------------------------------------------------------------------ steps

    def step(self) -> GridPos | None:
        """Collapse the lowest-entropy cell. Returns the cell or None."""

        cell = self._lowest_entropy_cell()
        if cell is None:
            return None
        options = sorted(self._cells[cell])  # deterministic order
        weights = np.array([self._weights.get(t, 1.0) for t in options], dtype=float)
        total = float(weights.sum())
        if total <= 0.0:
            weights = np.ones_like(weights)
            total = float(weights.sum())
        probs = weights / total
        idx = int(self._rng.choice(len(options), p=probs))
        chosen = options[idx]
        self._cells[cell] = {chosen}
        self._propagate({cell})
        return cell

    def _propagate(self, seeds: set[GridPos]) -> None:
        queue: list[GridPos] = list(seeds)
        while queue:
            pos = queue.pop()
            current_opts = self._cells[pos]
            if not current_opts:
                hints = self._seed_hints()
                raise WFCContradiction(pos, self.seed, hints)
            for direction in DIRECTIONS:
                nb = self._neighbor(pos, direction)
                if nb is None:
                    continue
                nb_opts = self._cells[nb]
                # Compute the set of neighbor tiles compatible with at least
                # one option still alive in the current cell.
                allowed: set[str] = set()
                for t in current_opts:
                    allowed |= self.adjacency.neighbors_of(t, direction)
                pruned = nb_opts & allowed
                if pruned != nb_opts:
                    if not pruned:
                        hints = self._seed_hints()
                        raise WFCContradiction(nb, self.seed, hints)
                    self._cells[nb] = pruned
                    queue.append(nb)

    def _seed_hints(self) -> tuple[int, ...]:
        # Offer the next four seed values after this one as deterministic
        # retry candidates. Caller can iterate as far as they want.
        return tuple(self.seed + offset for offset in (1, 2, 3, 4))

    # ------------------------------------------------------------------ solve

    def solve(self, *, max_steps: int | None = None) -> WFCResult:
        """Run step+propagate until done or contradiction."""

        # Initial pass to prune any pre-impossible options (e.g. a tile
        # whose only allowed neighbor doesn't exist in the tileset).
        self._propagate(set(self._cells.keys()))
        steps = 0
        while not self.is_collapsed:
            cell = self.step()
            if cell is None:
                break
            steps += 1
            if max_steps is not None and steps >= max_steps:
                break
        return self._build_result()

    def _build_result(self) -> WFCResult:
        cx, cy, cz = self.cell_size
        placements: list[PlacedTile] = []
        for pos in self._iter_positions():
            opts = self._cells[pos]
            if len(opts) != 1:
                continue
            (tile_id,) = tuple(opts)
            x, y, z = pos
            transform = (x * cx, y * cy, z * cz)
            placements.append(PlacedTile(tile_id=tile_id, position=pos, transform=transform))
        return WFCResult(seed=self.seed, grid_shape=self.grid_shape, placements=placements)


def solve_wfc(
    tileset: Tileset,
    adjacency: AdjacencyRules,
    grid_shape: GridShape,
    *,
    seed: int = 0,
    cell_size: tuple[float, float, float] = (1.0, 1.0, 1.0),
) -> WFCResult:
    """One-shot convenience wrapper around :class:`WFCSolver`."""

    solver = WFCSolver(
        tileset, adjacency, grid_shape, seed=seed, cell_size=cell_size
    )
    return solver.solve()
