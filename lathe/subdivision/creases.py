"""Crease tag bookkeeping for subdivision finishing.

Per OpenSubDiv conventions a *crease* is an edge with a non-zero
sharpness; sharpness is normally taken in ``[0, 10]`` (or ``infinity``)
where a value of ``1`` keeps the edge sharp at the first refinement and
attenuates by ``1`` per additional level. We follow that convention; the
authored ``.lth`` surface accepts:

* a number  ``0..10``                  (semi-sharp; attenuated each level)
* the literal ``infinity`` / ``inf``   (perfectly sharp)
* the boolean ``true``                 (treated as ``infinity``)

After each subdivision pass a crease's effective sharpness is ``max(s -
1, 0)`` (Hoppe et al., 'Piecewise Smooth Surface Reconstruction', 1994).
A sharpness of ``0`` is equivalent to a smooth edge.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from math import inf, isfinite

Edge = tuple[int, int]

INFINITE_CREASE = float("inf")


def _canon(a: int, b: int) -> Edge:
    return (a, b) if a <= b else (b, a)


def normalise_crease_sharpness(value: object) -> float:
    """Return a finite sharpness in ``[0, 10]`` or ``+inf`` for "sharp"."""
    if isinstance(value, bool):
        return INFINITE_CREASE if value else 0.0
    if value in (None, ""):
        return 0.0
    if isinstance(value, str):
        token = value.strip().lower()
        if token in {"inf", "infinity", "infinite", "sharp", "hard"}:
            return INFINITE_CREASE
        if token in {"smooth", "soft", "none"}:
            return 0.0
        try:
            return _clamp(float(token))
        except ValueError as exc:
            raise ValueError(f"unparseable crease sharpness: {value!r}") from exc
    try:
        as_float = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise ValueError(f"unparseable crease sharpness: {value!r}") from exc
    if not isfinite(as_float):
        return INFINITE_CREASE if as_float > 0 else 0.0
    return _clamp(as_float)


def _clamp(value: float) -> float:
    if value <= 0:
        return 0.0
    return min(value, 10.0)


@dataclass(frozen=True)
class CreaseTags:
    """Author-declared crease sharpnesses, keyed by canonical edge."""

    edges: dict[Edge, float]
    corners: dict[int, float]

    @classmethod
    def empty(cls) -> CreaseTags:
        """Crease set with no tagged edges or corners."""
        return cls(edges={}, corners={})

    @classmethod
    def from_records(
        cls,
        edge_records: Iterable[Sequence[object]] | None = None,
        corner_records: Iterable[Sequence[object]] | None = None,
    ) -> CreaseTags:
        """Build from ``[(va, vb, sharpness), ...]`` style records.

        Accepts dicts with ``vertices``/``edge``/``sharpness`` keys as
        well as flat tuples; missing sharpness defaults to ``infinity``.
        """
        edges: dict[Edge, float] = {}
        for rec in edge_records or ():
            edge, sharp = _parse_edge_record(rec)
            if sharp <= 0:
                continue
            existing = edges.get(edge, 0.0)
            edges[edge] = max(existing, sharp)
        corners: dict[int, float] = {}
        for rec in corner_records or ():
            vertex, sharp = _parse_corner_record(rec)
            if sharp <= 0:
                continue
            existing = corners.get(vertex, 0.0)
            corners[vertex] = max(existing, sharp)
        return cls(edges=edges, corners=corners)

    def is_empty(self) -> bool:
        """``True`` when no edges or corners are tagged."""
        return not self.edges and not self.corners

    def edge_sharpness(self, a: int, b: int) -> float:
        """Sharpness for the unordered ``(a, b)`` edge, ``0`` if smooth."""
        return self.edges.get(_canon(a, b), 0.0)

    def corner_sharpness(self, v: int) -> float:
        """Sharpness associated with vertex ``v``."""
        return self.corners.get(v, 0.0)

    def attenuate(self) -> CreaseTags:
        """Return creases for the next subdivision level (``s -> s - 1``).

        Infinite sharpness stays infinite. Finite sharpness >= 1 reduces
        by 1; finite sharpness < 1 becomes ``0`` and the entry is dropped.
        """
        new_edges: dict[Edge, float] = {}
        for edge, sharp in self.edges.items():
            if sharp == INFINITE_CREASE:
                new_edges[edge] = INFINITE_CREASE
                continue
            attenuated = sharp - 1.0
            if attenuated > 0:
                new_edges[edge] = attenuated
        new_corners: dict[int, float] = {}
        for vertex, sharp in self.corners.items():
            if sharp == INFINITE_CREASE:
                new_corners[vertex] = INFINITE_CREASE
                continue
            attenuated = sharp - 1.0
            if attenuated > 0:
                new_corners[vertex] = attenuated
        return CreaseTags(edges=new_edges, corners=new_corners)


def _parse_edge_record(rec: object) -> tuple[Edge, float]:
    if isinstance(rec, dict):
        edge_pair = (
            rec.get("edge")
            or rec.get("vertices")
            or rec.get("vertex_pair")
            or rec.get("between")
        )
        sharp_raw = rec.get("sharpness", rec.get("sharp", rec.get("crease", inf)))
    else:
        try:
            seq = list(rec)  # type: ignore[arg-type]
        except TypeError as exc:
            raise ValueError(f"crease record must be sequence/dict: {rec!r}") from exc
        if len(seq) == 2 and isinstance(seq[0], (list, tuple)):
            edge_pair = seq[0]
            sharp_raw = seq[1]
        elif len(seq) == 2:
            edge_pair = (seq[0], seq[1])
            sharp_raw = inf
        elif len(seq) >= 3:
            edge_pair = (seq[0], seq[1])
            sharp_raw = seq[2]
        else:
            raise ValueError(f"crease record needs >= 2 elements: {rec!r}")
    if not edge_pair or len(edge_pair) != 2:
        raise ValueError(f"crease record missing edge pair: {rec!r}")
    a = int(edge_pair[0])
    b = int(edge_pair[1])
    return _canon(a, b), normalise_crease_sharpness(sharp_raw)


def _parse_corner_record(rec: object) -> tuple[int, float]:
    if isinstance(rec, dict):
        vertex = rec.get("vertex", rec.get("index"))
        sharp_raw = rec.get("sharpness", rec.get("sharp", inf))
    else:
        try:
            seq = list(rec)  # type: ignore[arg-type]
        except TypeError as exc:
            raise ValueError(f"corner record must be sequence/dict: {rec!r}") from exc
        if len(seq) == 1:
            vertex = seq[0]
            sharp_raw = inf
        elif len(seq) >= 2:
            vertex = seq[0]
            sharp_raw = seq[1]
        else:
            raise ValueError(f"corner record needs >= 1 element: {rec!r}")
    if vertex is None:
        raise ValueError(f"corner record missing vertex: {rec!r}")
    return int(vertex), normalise_crease_sharpness(sharp_raw)


__all__ = [
    "INFINITE_CREASE",
    "CreaseTags",
    "normalise_crease_sharpness",
]
