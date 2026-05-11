"""Typed attribute schema for node_type='hinge'.

A hinge is a pivoting joint with two leaves and a barrel pin. Modeled
as: two flat leaves (plates) joined by a central cylindrical barrel.
The pin axis is the hinge axis.

Validated in Stage 4 of the synthesizer pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


_VALID_STYLES: frozenset[str] = frozenset(
    {"butt", "barrel", "piano", "strap", "concealed"}
)

_VALID_AXES: frozenset[str] = frozenset({"x", "y", "z"})


@dataclass(frozen=True)
class HingeAttributes:
    """Typed attribute contract for node_type='hinge'.

    Fields:
        style: hinge family. Must be in ``_VALID_STYLES``.
        leaf_width_cm: width of each leaf plate (positive).
        leaf_height_cm: hinge length along the pin axis (positive).
        leaf_thickness_cm: plate thickness (positive).
        barrel_radius_cm: hinge barrel radius (positive).
        pin_axis: axis the pin runs along. Must be in ``_VALID_AXES``.
        region_id: optional material-zone identifier.
    """

    style: str
    leaf_width_cm: float
    leaf_height_cm: float
    leaf_thickness_cm: float
    barrel_radius_cm: float
    pin_axis: str = "y"
    region_id: str | None = None

    def __post_init__(self) -> None:
        if self.style not in _VALID_STYLES:
            raise ValueError(
                f"hinge.style={self.style!r} not in {sorted(_VALID_STYLES)}"
            )
        for field_name, value in (
            ("leaf_width_cm", self.leaf_width_cm),
            ("leaf_height_cm", self.leaf_height_cm),
            ("leaf_thickness_cm", self.leaf_thickness_cm),
            ("barrel_radius_cm", self.barrel_radius_cm),
        ):
            if not isinstance(value, (int, float)) or float(value) <= 0:
                raise ValueError(f"hinge.{field_name}={value} must be positive")
        if self.pin_axis not in _VALID_AXES:
            raise ValueError(
                f"hinge.pin_axis={self.pin_axis!r} not in {sorted(_VALID_AXES)}"
            )

    @classmethod
    def from_dict(cls, attrs: dict[str, Any]) -> "HingeAttributes":
        if not isinstance(attrs, dict):
            raise TypeError(
                f"hinge attributes must be dict, got {type(attrs).__name__}"
            )
        for required in (
            "style",
            "leaf_width_cm",
            "leaf_height_cm",
            "leaf_thickness_cm",
            "barrel_radius_cm",
        ):
            if required not in attrs:
                raise ValueError(
                    f"hinge attributes missing required key {required!r}"
                )
        return cls(
            style=str(attrs["style"]),
            leaf_width_cm=float(attrs["leaf_width_cm"]),
            leaf_height_cm=float(attrs["leaf_height_cm"]),
            leaf_thickness_cm=float(attrs["leaf_thickness_cm"]),
            barrel_radius_cm=float(attrs["barrel_radius_cm"]),
            pin_axis=str(attrs.get("pin_axis") or "y"),
            region_id=attrs.get("region_id"),
        )
