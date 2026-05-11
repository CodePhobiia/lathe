"""Typed attribute schema for node_type='conduit'.

A conduit is an exposed cable bundle, pipe run, or wire trace running
across or along a host surface. Geometry: one or more cylindrical
spans (straight) plus optional elbow caps (sphere) at bends.

This generator emits straight spans only; bends are decomposed into
separate conduit nodes at composition time. The bend_count attribute
records the intended bend index in a longer routed path so downstream
stages can reconstruct routing intent.

Validated in Stage 4 of the synthesizer pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


_VALID_KINDS: frozenset[str] = frozenset(
    {"cable", "pipe", "wire_loom", "armored_conduit", "hose"}
)

_VALID_AXES: frozenset[str] = frozenset({"x", "y", "z"})


@dataclass(frozen=True)
class ConduitAttributes:
    """Typed attribute contract for node_type='conduit'.

    Fields:
        kind: conduit family. Must be in ``_VALID_KINDS``.
        radius_cm: outer radius (positive).
        length_cm: span length (positive).
        axis: axis the conduit runs along. Must be in ``_VALID_AXES``.
        bend_count: integer hint at how many bends this conduit
            participates in (>=0); affects whether endcap spheres are
            emitted.
        region_id: optional material-zone identifier.
    """

    kind: str
    radius_cm: float
    length_cm: float
    axis: str = "z"
    bend_count: int = 0
    region_id: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in _VALID_KINDS:
            raise ValueError(
                f"conduit.kind={self.kind!r} not in {sorted(_VALID_KINDS)}"
            )
        for field_name, value in (
            ("radius_cm", self.radius_cm),
            ("length_cm", self.length_cm),
        ):
            if not isinstance(value, (int, float)) or float(value) <= 0:
                raise ValueError(f"conduit.{field_name}={value} must be positive")
        if self.axis not in _VALID_AXES:
            raise ValueError(
                f"conduit.axis={self.axis!r} not in {sorted(_VALID_AXES)}"
            )
        if not isinstance(self.bend_count, int) or self.bend_count < 0:
            raise ValueError(f"conduit.bend_count={self.bend_count} must be >= 0")

    @classmethod
    def from_dict(cls, attrs: dict[str, Any]) -> "ConduitAttributes":
        if not isinstance(attrs, dict):
            raise TypeError(
                f"conduit attributes must be dict, got {type(attrs).__name__}"
            )
        for required in ("kind", "radius_cm", "length_cm"):
            if required not in attrs:
                raise ValueError(
                    f"conduit attributes missing required key {required!r}"
                )
        return cls(
            kind=str(attrs["kind"]),
            radius_cm=float(attrs["radius_cm"]),
            length_cm=float(attrs["length_cm"]),
            axis=str(attrs.get("axis") or "z"),
            bend_count=int(attrs.get("bend_count") or 0),
            region_id=attrs.get("region_id"),
        )
