"""Typed attribute schema for node_type='fastener'.

A fastener is a small repeating hardware element — bolt head, screw,
rivet, washer-and-bolt set, pop rivet. Fasteners typically appear as
a pattern (grid / line / corner-quad) on a host surface. The
attribute schema describes one fastener's geometry; the pattern that
distributes it is expressed via a separate copy_to_points / distribute
edge or by the composition policy generating one fastener-node per
host corner.

Validated in Stage 4 of the synthesizer pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_VALID_AXES: frozenset[str] = frozenset({"x", "y", "z"})

_VALID_KINDS: frozenset[str] = frozenset(
    {"bolt", "screw", "rivet", "carriage_bolt", "pop_rivet", "washer_bolt"}
)


@dataclass(frozen=True)
class FastenerAttributes:
    """Typed attribute contract for node_type='fastener'.

    Fields:
        kind: fastener style. Must be in ``_VALID_KINDS``.
        head_radius_cm: radius of the head (positive). Set the visual
            scale; downstream surface stages may tighten or loosen
            this against tolerance/material recipes.
        head_height_cm: head protrusion height (positive).
        shaft_radius_cm: shaft radius (positive, < head_radius_cm).
        shaft_length_cm: shaft length below the head (positive).
        axis: which axis the fastener's shaft is oriented along. Must
            be in ``_VALID_AXES``.
        region_id: optional material-zone identifier for the fastener.
    """

    kind: str
    head_radius_cm: float
    head_height_cm: float
    shaft_radius_cm: float
    shaft_length_cm: float
    axis: str = "y"
    region_id: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in _VALID_KINDS:
            raise ValueError(
                f"fastener.kind={self.kind!r} not in {sorted(_VALID_KINDS)}"
            )
        for field_name, value in (
            ("head_radius_cm", self.head_radius_cm),
            ("head_height_cm", self.head_height_cm),
            ("shaft_radius_cm", self.shaft_radius_cm),
            ("shaft_length_cm", self.shaft_length_cm),
        ):
            if not isinstance(value, (int, float)):
                raise TypeError(
                    f"fastener.{field_name} must be numeric, got "
                    f"{type(value).__name__}"
                )
            if float(value) <= 0:
                raise ValueError(
                    f"fastener.{field_name}={value} must be positive"
                )
        if float(self.shaft_radius_cm) >= float(self.head_radius_cm):
            raise ValueError(
                f"fastener.shaft_radius_cm={self.shaft_radius_cm} must be < "
                f"head_radius_cm={self.head_radius_cm}; otherwise the head "
                "is degenerate."
            )
        if self.axis not in _VALID_AXES:
            raise ValueError(
                f"fastener.axis={self.axis!r} not in {sorted(_VALID_AXES)}"
            )
        if self.region_id is not None and not isinstance(self.region_id, str):
            raise TypeError(
                f"fastener.region_id must be str or None, got "
                f"{type(self.region_id).__name__}"
            )

    @classmethod
    def from_dict(cls, attrs: dict[str, Any]) -> FastenerAttributes:
        """Validate a raw attribute dict and produce a typed instance."""
        if not isinstance(attrs, dict):
            raise TypeError(
                f"fastener attributes must be dict, got {type(attrs).__name__}"
            )
        for required in ("kind", "head_radius_cm", "head_height_cm", "shaft_radius_cm", "shaft_length_cm"):
            if required not in attrs:
                raise ValueError(f"fastener attributes missing required key {required!r}")
        return cls(
            kind=str(attrs["kind"]),
            head_radius_cm=float(attrs["head_radius_cm"]),
            head_height_cm=float(attrs["head_height_cm"]),
            shaft_radius_cm=float(attrs["shaft_radius_cm"]),
            shaft_length_cm=float(attrs["shaft_length_cm"]),
            axis=str(attrs.get("axis") or "y"),
            region_id=attrs.get("region_id"),
        )
