"""Broadphase spatial clustering for batched boolean evaluation (Wave 12).

Per research §1 invariant 3: most ops do not interact. A crate body,
four corner guards, handles, hinges, and decal plates can be clustered
by bounding boxes — only overlapping clusters need expensive boolean
arrangements.

Algorithm: bbox-overlap union-find. Each primitive has an AABB; two
primitives that AABB-overlap are merged into the same cluster. Result
is a list of disjoint clusters the batched-boolean compiler treats
as independent variadic problems.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AABB:
    """Axis-aligned bounding box in cm."""

    min_cm: tuple[float, float, float]
    max_cm: tuple[float, float, float]

    def overlaps(self, other: AABB, margin_cm: float = 0.5) -> bool:
        return (
            self.min_cm[0] - margin_cm <= other.max_cm[0]
            and other.min_cm[0] - margin_cm <= self.max_cm[0]
            and self.min_cm[1] - margin_cm <= other.max_cm[1]
            and other.min_cm[1] - margin_cm <= self.max_cm[1]
            and self.min_cm[2] - margin_cm <= other.max_cm[2]
            and other.min_cm[2] - margin_cm <= self.max_cm[2]
        )


@dataclass(frozen=True)
class ClusterEntry:
    """A primitive's identity + bbox going into clustering."""

    primitive_id: str
    aabb: AABB
    role: str = ""


class _UnionFind:
    def __init__(self, n: int) -> None:
        self._parent = list(range(n))

    def find(self, x: int) -> int:
        while self._parent[x] != x:
            self._parent[x] = self._parent[self._parent[x]]
            x = self._parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self._parent[ra] = rb


def cluster_by_bbox_overlap(
    entries: Iterable[ClusterEntry], margin_cm: float = 0.5
) -> list[list[ClusterEntry]]:
    """Return a list of disjoint clusters.

    Each cluster is a list of ``ClusterEntry`` whose AABBs touch
    (within ``margin_cm``). Singletons are returned as 1-element lists.
    """
    items = list(entries)
    n = len(items)
    uf = _UnionFind(n)
    for i in range(n):
        for j in range(i + 1, n):
            if items[i].aabb.overlaps(items[j].aabb, margin_cm):
                uf.union(i, j)
    groups: dict[int, list[ClusterEntry]] = {}
    for idx, item in enumerate(items):
        root = uf.find(idx)
        groups.setdefault(root, []).append(item)
    return list(groups.values())


__all__ = ["AABB", "ClusterEntry", "cluster_by_bbox_overlap"]
