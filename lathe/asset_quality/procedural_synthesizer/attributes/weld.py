"""Typed attribute schema for node_type='weld'.

A weld is a continuous bead along a host edge connecting two faces.
Modeled as a thin extruded fillet running along an axis. Visual is a
small triangular / quarter-round bead; downstream surface stages can
add cooled-metal slag patterns via decals.

Validated in Stage 4 of the synthesizer pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_VALID_KINDS: frozenset[str] = frozenset(
    {"fillet", "butt", "spot", "seam", "tack"}
)

_VALID_AXES: frozenset[str] = frozenset({"x", "y", "z"})


@dataclass(frozen=True)
class WeldAttributes:
    """Typed attribute contract for node_type='weld'.

    Fields:
        kind: weld family. Must be in ``_VALID_KINDS``.
        bead_radius_cm: bead cross-section radius (positive).
        length_cm: total weld length (positive).
        axis: axis the bead runs along. Must be in ``_VALID_AXES``.
        spot_count: number of discrete weld spots (>=1, only honored
            for spot / tack).
        region_id: optional material-zone identifier.
    """

    kind: str
    bead_radius_cm: float
    length_cm: float
    axis: str = "x"
    spot_count: int = 1
    region_id: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in _VALID_KINDS:
            raise ValueError(
                f"weld.kind={self.kind!r} not in {sorted(_VALID_KINDS)}"
            )
        for field_name, value in (
            ("bead_radius_cm", self.bead_radius_cm),
            ("length_cm", self.length_cm),
        ):
            if not isinstance(value, (int, float)) or float(value) <= 0:
                raise ValueError(f"weld.{field_name}={value} must be positive")
        if self.axis not in _VALID_AXES:
            raise ValueError(
                f"weld.axis={self.axis!r} not in {sorted(_VALID_AXES)}"
            )
        if not isinstance(self.spot_count, int) or self.spot_count < 1:
            raise ValueError(f"weld.spot_count={self.spot_count} must be >= 1")

    @classmethod
    def from_dict(cls, attrs: dict[str, Any]) -> WeldAttributes:
        if not isinstance(attrs, dict):
            raise TypeError(
                f"weld attributes must be dict, got {type(attrs).__name__}"
            )
        for required in ("kind", "bead_radius_cm", "length_cm"):
            if required not in attrs:
                raise ValueError(
                    f"weld attributes missing required key {required!r}"
                )
        return cls(
            kind=str(attrs["kind"]),
            bead_radius_cm=float(attrs["bead_radius_cm"]),
            length_cm=float(attrs["length_cm"]),
            axis=str(attrs.get("axis") or "x"),
            spot_count=int(attrs.get("spot_count") or 1),
            region_id=attrs.get("region_id"),
        )
