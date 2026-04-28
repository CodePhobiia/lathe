"""High-poly / low-poly coordination helpers.

Shared state used by the topology and bake stages to thread the
authoritative high-poly mesh through to cage-driven bakes.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass
class HighLowRelation:
    """HighLowRelation."""

    high_mesh_uri: str
    low_mesh_uri: str
    bake_cage_offset_cm: float
    source: str
    high_triangle_count: int = 0
    low_triangle_count: int = 0
    distinction_ratio: float = 0.0
    bake_groups: list[str] | None = None
    authoritative: bool = True

    def to_dict(self) -> dict[str, object]:
        """To dict.

        Returns:
            The result.
        """
        return asdict(self)
