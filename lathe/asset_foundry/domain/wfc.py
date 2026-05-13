"""Wave Function Collapse — modular grid assembly.

Per northstar §11 Phase 3. WFC is the canonical solver for placing
modular tiles on a grid subject to per-edge adjacency constraints.
Output is a fully-populated grid where every cell holds one tile,
or a failure record naming the contradiction.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

WFC_VERSION = "lathe.asset_foundry.wfc_v1"


@dataclass(frozen=True)
class WfcTile:
    """One modular tile."""

    tile_id: str
    """Stable identifier."""

    edge_codes: Mapping[str, str]
    """Per-edge code: ``{"north": "wall_grey", "east": "wall_grey",
    "south": "floor", "west": "wall_grey"}``. Two tiles can be
    adjacent on a shared edge iff the edge_codes match."""

    rotations: int = 1
    """1 = unique; 2 = 180-flip; 4 = full 90-degree rotations."""

    weight: float = 1.0


@dataclass(frozen=True)
class WfcConstraintSet:
    """Tile set + grid dimensions + extra constraints."""

    tiles: tuple[WfcTile, ...]
    grid_width: int
    grid_height: int
    seed: int = 0
    fixed_cells: Mapping[tuple[int, int], str] = field(default_factory=dict)
    """``(x, y) -> tile_id`` for pre-placed tiles."""


@dataclass(frozen=True)
class WfcSolverResult:
    status: str
    """``solved`` | ``contradiction`` | ``incomplete``."""

    grid: tuple[tuple[str, ...], ...]
    """Solved grid; empty cells are represented by ``""``."""

    failure_cell: tuple[int, int] | None
    iterations: int
    diagnostics: tuple[str, ...]


def _edges_match(a: WfcTile, b: WfcTile, direction: str) -> bool:
    """Check if tile a's edge matches tile b's opposite edge."""
    opposite = {"north": "south", "south": "north", "east": "west", "west": "east"}
    code_a = a.edge_codes.get(direction)
    code_b = b.edge_codes.get(opposite[direction])
    return code_a is not None and code_b is not None and code_a == code_b


def solve_wfc_grid(constraints: WfcConstraintSet) -> WfcSolverResult:
    """Solve a WFC grid deterministically.

    Uses observation + propagation + backtracking-free pick of
    lowest-entropy cell. Determinism via the seed-derived choice
    when entropies tie.
    """
    if not constraints.tiles:
        return WfcSolverResult(
            status="contradiction",
            grid=(),
            failure_cell=None,
            iterations=0,
            diagnostics=("no_tiles_in_set",),
        )
    w = constraints.grid_width
    h = constraints.grid_height
    tile_by_id = {t.tile_id: t for t in constraints.tiles}
    # Cell -> set of allowed tile_ids.
    cells: list[list[set[str]]] = [
        [set(tile_by_id) for _ in range(w)] for _ in range(h)
    ]
    for (fx, fy), tid in constraints.fixed_cells.items():
        if 0 <= fx < w and 0 <= fy < h and tid in tile_by_id:
            cells[fy][fx] = {tid}

    rng_state = constraints.seed if constraints.seed != 0 else 0xC0FFEE

    def lcg() -> float:
        nonlocal rng_state
        rng_state = (1664525 * rng_state + 1013904223) & 0xFFFFFFFF
        return rng_state / 0xFFFFFFFF

    def propagate() -> tuple[int, int] | None:
        """Propagate constraints; return failure cell or None."""
        changed = True
        while changed:
            changed = False
            for y in range(h):
                for x in range(w):
                    options = cells[y][x]
                    if not options:
                        return (x, y)
                    if len(options) == 1:
                        continue
                    for dx, dy, direction in (
                        (0, -1, "north"),
                        (1, 0, "east"),
                        (0, 1, "south"),
                        (-1, 0, "west"),
                    ):
                        nx, ny = x + dx, y + dy
                        if not (0 <= nx < w and 0 <= ny < h):
                            continue
                        neighbor_options = cells[ny][nx]
                        if not neighbor_options:
                            continue
                        # An option survives iff some neighbor option is
                        # compatible with it along the shared edge.
                        new_options: set[str] = set()
                        for opt_id in options:
                            opt = tile_by_id[opt_id]
                            for n_id in neighbor_options:
                                n_tile = tile_by_id[n_id]
                                if _edges_match(opt, n_tile, direction):
                                    new_options.add(opt_id)
                                    break
                        if new_options != options:
                            cells[y][x] = new_options
                            changed = True
        return None

    iterations = 0
    max_iter = w * h * len(tile_by_id) * 4
    while iterations < max_iter:
        iterations += 1
        # Find lowest-entropy cell (more than 1 option).
        best_cell: tuple[int, int] | None = None
        best_entropy = len(tile_by_id) + 1
        for y in range(h):
            for x in range(w):
                opts = cells[y][x]
                if 1 < len(opts) < best_entropy:
                    best_entropy = len(opts)
                    best_cell = (x, y)
        if best_cell is None:
            # All cells decided.
            grid_out = tuple(
                tuple(next(iter(cells[y][x])) if cells[y][x] else "" for x in range(w))
                for y in range(h)
            )
            return WfcSolverResult(
                status="solved",
                grid=grid_out,
                failure_cell=None,
                iterations=iterations,
                diagnostics=(),
            )
        x, y = best_cell
        candidates = sorted(cells[y][x])
        # Weight-aware deterministic pick.
        weights = [tile_by_id[t].weight for t in candidates]
        total_w = sum(weights) or 1.0
        r = lcg() * total_w
        cum = 0.0
        chosen = candidates[0]
        for c, wgt in zip(candidates, weights):
            cum += wgt
            if r <= cum:
                chosen = c
                break
        cells[y][x] = {chosen}
        failure = propagate()
        if failure is not None:
            grid_partial = tuple(
                tuple(
                    next(iter(cells[yy][xx])) if len(cells[yy][xx]) == 1 else ""
                    for xx in range(w)
                )
                for yy in range(h)
            )
            return WfcSolverResult(
                status="contradiction",
                grid=grid_partial,
                failure_cell=failure,
                iterations=iterations,
                diagnostics=(
                    f"contradiction_at_cell_{failure[0]}_{failure[1]}",
                ),
            )
    return WfcSolverResult(
        status="incomplete",
        grid=tuple(
            tuple(
                next(iter(cells[y][x])) if len(cells[y][x]) == 1 else ""
                for x in range(w)
            )
            for y in range(h)
        ),
        failure_cell=None,
        iterations=iterations,
        diagnostics=("iteration_budget_exceeded",),
    )


__all__ = [
    "WFC_VERSION",
    "WfcConstraintSet",
    "WfcSolverResult",
    "WfcTile",
    "solve_wfc_grid",
]
