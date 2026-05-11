"""Typed attribute schema for node_type='vent'.

A vent is a recessed grille / louvered intake. Modeled as a rectangular
recess subdivided into N parallel slats. The slats are the visible
geometry; the recess frame is part of the host surface and not emitted
here (downstream surface stages handle frame trim).

Validated in Stage 4 of the synthesizer pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


_VALID_STYLES: frozenset[str] = frozenset(
    {"horizontal_slat", "vertical_slat", "circular_grille", "honeycomb"}
)

_VALID_AXES: frozenset[str] = frozenset({"x", "y", "z"})


@dataclass(frozen=True)
class VentAttributes:
    """Typed attribute contract for node_type='vent'.

    Fields:
        style: vent family. Must be in ``_VALID_STYLES``.
        width_cm: overall vent width on the host face (positive).
        height_cm: overall vent height on the host face (positive).
        depth_cm: how deep the vent recesses into the host (positive).
        slat_count: number of slats / grille rows (>=1, ignored for
            honeycomb).
        host_face_axis: axis normal to the host face. Must be in
            ``_VALID_AXES``.
        region_id: optional material-zone identifier.
    """

    style: str
    width_cm: float
    height_cm: float
    depth_cm: float
    slat_count: int = 6
    host_face_axis: str = "z"
    region_id: str | None = None

    def __post_init__(self) -> None:
        if self.style not in _VALID_STYLES:
            raise ValueError(
                f"vent.style={self.style!r} not in {sorted(_VALID_STYLES)}"
            )
        for field_name, value in (
            ("width_cm", self.width_cm),
            ("height_cm", self.height_cm),
            ("depth_cm", self.depth_cm),
        ):
            if not isinstance(value, (int, float)) or float(value) <= 0:
                raise ValueError(f"vent.{field_name}={value} must be positive")
        if not isinstance(self.slat_count, int) or self.slat_count < 1:
            raise ValueError(f"vent.slat_count={self.slat_count} must be >= 1")
        if self.host_face_axis not in _VALID_AXES:
            raise ValueError(
                f"vent.host_face_axis={self.host_face_axis!r} not in {sorted(_VALID_AXES)}"
            )

    @classmethod
    def from_dict(cls, attrs: dict[str, Any]) -> "VentAttributes":
        if not isinstance(attrs, dict):
            raise TypeError(
                f"vent attributes must be dict, got {type(attrs).__name__}"
            )
        for required in ("style", "width_cm", "height_cm", "depth_cm"):
            if required not in attrs:
                raise ValueError(
                    f"vent attributes missing required key {required!r}"
                )
        return cls(
            style=str(attrs["style"]),
            width_cm=float(attrs["width_cm"]),
            height_cm=float(attrs["height_cm"]),
            depth_cm=float(attrs["depth_cm"]),
            slat_count=int(attrs.get("slat_count") or 6),
            host_face_axis=str(attrs.get("host_face_axis") or "z"),
            region_id=attrs.get("region_id"),
        )
