"""WFC adjacency rules.

Adjacency rules are an explicit set of allowed `(tile_a, direction,
tile_b)` triples. Rules are symmetric by construction: if A is allowed
to face B on +X, then B is allowed to face A on -X.

Rules can be authored explicitly or auto-derived from connector tags on
the underlying tileset. Connector matching uses exact-string equality,
following the simplest WFC variant.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .tileset import DIRECTIONS, OPPOSITE, Direction, Tileset


@dataclass
class AdjacencyRules:
    """Allowed neighbor pairs per direction.

    Internal representation is a dict keyed by direction whose value is
    a set of `(tile_a_id, tile_b_id)` pairs. The pair `(a, d, b)` means
    "tile A may sit directly adjacent to tile B in direction d from A".
    """

    name: str
    allowed: dict[Direction, set[tuple[str, str]]] = field(
        default_factory=lambda: {d: set() for d in DIRECTIONS}
    )

    def allow(self, tile_a: str, direction: Direction, tile_b: str) -> None:
        if direction not in DIRECTIONS:
            raise ValueError(f"unknown direction {direction!r}")
        self.allowed[direction].add((tile_a, tile_b))
        self.allowed[OPPOSITE[direction]].add((tile_b, tile_a))

    def is_allowed(self, tile_a: str, direction: Direction, tile_b: str) -> bool:
        return (tile_a, tile_b) in self.allowed.get(direction, set())

    def neighbors_of(self, tile_a: str, direction: Direction) -> set[str]:
        return {b for (a, b) in self.allowed.get(direction, set()) if a == tile_a}


def from_connectors(tileset: Tileset, *, name: str | None = None) -> AdjacencyRules:
    """Auto-derive adjacency rules from per-face connector tags.

    Two tiles are adjacent on direction `d` iff
    ``tile_a.connector(d) == tile_b.connector(opposite(d))``. The
    ``"void"`` connector still matches itself: this lets you tag the
    "outside" of the grid uniformly.
    """
    rules = AdjacencyRules(name=name or f"{tileset.name}_auto")
    tiles = tileset.tiles
    for direction in DIRECTIONS:
        opp = OPPOSITE[direction]
        for tile_a in tiles:
            tag_a = tile_a.connector(direction)
            for tile_b in tiles:
                tag_b = tile_b.connector(opp)
                if tag_a == tag_b:
                    rules.allowed[direction].add((tile_a.id, tile_b.id))
    return rules
