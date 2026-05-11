"""Typed attribute schema for node_type='inset'.

An inset is a recessed region cut into a host face — countersunk
panel pocket, label well, finger-pull recess, drawer-front cavity.
Geometrically a box subtracted from the host volume; the synthesizer
emits the subtractive op while the host volume remains the parent
geometry.

Validated in Stage 4 of the synthesizer pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


_VALID_AXES: frozenset[str] = frozenset({"x", "y", "z"})

_VALID_BOTTOM_STYLES: frozenset[str] = frozenset(
    {"flat", "rounded", "beveled"}
)


@dataclass(frozen=True)
class InsetAttributes:
    """Typed attribute contract for node_type='inset'.

    Fields:
        depth_axis: axis along which the inset recesses (perpendicular
            to the host face). Must be in ``_VALID_AXES``.
        depth_cm: recess depth (positive).
        width_cm: in-plane width (positive).
        height_cm: in-plane height (positive).
        bottom_style: how the inset's bottom is finished. Must be in
            ``_VALID_BOTTOM_STYLES``.
        rounding_cm: corner / bottom-edge rounding radius (>=0).
        region_id: optional material-zone identifier for the recess
            interior.
    """

    depth_axis: str
    depth_cm: float
    width_cm: float
    height_cm: float
    bottom_style: str = "flat"
    rounding_cm: float = 0.0
    region_id: str | None = None

    def __post_init__(self) -> None:
        if self.depth_axis not in _VALID_AXES:
            raise ValueError(
                f"inset.depth_axis={self.depth_axis!r} not in {sorted(_VALID_AXES)}"
            )
        for field_name, value in (
            ("depth_cm", self.depth_cm),
            ("width_cm", self.width_cm),
            ("height_cm", self.height_cm),
        ):
            if not isinstance(value, (int, float)):
                raise TypeError(
                    f"inset.{field_name} must be numeric, got "
                    f"{type(value).__name__}"
                )
            if float(value) <= 0:
                raise ValueError(f"inset.{field_name}={value} must be positive")
        if self.bottom_style not in _VALID_BOTTOM_STYLES:
            raise ValueError(
                f"inset.bottom_style={self.bottom_style!r} not in "
                f"{sorted(_VALID_BOTTOM_STYLES)}"
            )
        if not isinstance(self.rounding_cm, (int, float)) or float(self.rounding_cm) < 0:
            raise ValueError(
                f"inset.rounding_cm={self.rounding_cm} must be >= 0"
            )
        if self.region_id is not None and not isinstance(self.region_id, str):
            raise TypeError(
                f"inset.region_id must be str or None, got "
                f"{type(self.region_id).__name__}"
            )

    @classmethod
    def from_dict(cls, attrs: dict[str, Any]) -> "InsetAttributes":
        if not isinstance(attrs, dict):
            raise TypeError(
                f"inset attributes must be dict, got {type(attrs).__name__}"
            )
        for required in ("depth_axis", "depth_cm", "width_cm", "height_cm"):
            if required not in attrs:
                raise ValueError(
                    f"inset attributes missing required key {required!r}"
                )
        return cls(
            depth_axis=str(attrs["depth_axis"]),
            depth_cm=float(attrs["depth_cm"]),
            width_cm=float(attrs["width_cm"]),
            height_cm=float(attrs["height_cm"]),
            bottom_style=str(attrs.get("bottom_style") or "flat"),
            rounding_cm=float(attrs.get("rounding_cm") or 0.0),
            region_id=attrs.get("region_id"),
        )
