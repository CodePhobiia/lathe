"""Typed attribute schema for node_type='rail'.

A rail is a linear structural element with a round or rounded
cross-section — handrail, ladder rung, foot rail, gun rail, towel
bar. Differs from `trim` in that rails are typically free-standing
structural members rather than face-bound decorative bands.

Validated in Stage 4 of the synthesizer pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


_VALID_AXES: frozenset[str] = frozenset({"x", "y", "z"})

_VALID_CROSS_SECTIONS: frozenset[str] = frozenset(
    {"round", "rounded_square", "square", "oval"}
)


@dataclass(frozen=True)
class RailAttributes:
    """Typed attribute contract for node_type='rail'.

    Fields:
        axis: which axis the rail runs along. Must be in ``_VALID_AXES``.
        length_cm: rail length (positive).
        cross_section: cross-section style. Must be in
            ``_VALID_CROSS_SECTIONS``.
        radius_cm: cross-section radius (positive). For non-round
            cross-sections, this is the radius of the bounding circle.
        region_id: optional material-zone identifier.
    """

    axis: str
    length_cm: float
    cross_section: str = "round"
    radius_cm: float = 1.0
    region_id: str | None = None

    def __post_init__(self) -> None:
        if self.axis not in _VALID_AXES:
            raise ValueError(
                f"rail.axis={self.axis!r} not in {sorted(_VALID_AXES)}"
            )
        if not isinstance(self.length_cm, (int, float)) or float(self.length_cm) <= 0:
            raise ValueError(f"rail.length_cm={self.length_cm} must be positive")
        if not isinstance(self.radius_cm, (int, float)) or float(self.radius_cm) <= 0:
            raise ValueError(f"rail.radius_cm={self.radius_cm} must be positive")
        if self.cross_section not in _VALID_CROSS_SECTIONS:
            raise ValueError(
                f"rail.cross_section={self.cross_section!r} not in "
                f"{sorted(_VALID_CROSS_SECTIONS)}"
            )
        if self.region_id is not None and not isinstance(self.region_id, str):
            raise TypeError(
                f"rail.region_id must be str or None, got "
                f"{type(self.region_id).__name__}"
            )

    @classmethod
    def from_dict(cls, attrs: dict[str, Any]) -> "RailAttributes":
        if not isinstance(attrs, dict):
            raise TypeError(
                f"rail attributes must be dict, got {type(attrs).__name__}"
            )
        for required in ("axis", "length_cm"):
            if required not in attrs:
                raise ValueError(
                    f"rail attributes missing required key {required!r}"
                )
        return cls(
            axis=str(attrs["axis"]),
            length_cm=float(attrs["length_cm"]),
            cross_section=str(attrs.get("cross_section") or "round"),
            radius_cm=float(attrs.get("radius_cm") or 1.0),
            region_id=attrs.get("region_id"),
        )
