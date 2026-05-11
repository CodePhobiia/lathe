"""Typed attribute schema for node_type='guard'.

A guard is a protective shroud over a host volume — fan guard, blade
guard, light cage, perimeter rail. Modeled as an open box-frame or
cylindrical cage made of N parallel bars.

Validated in Stage 4 of the synthesizer pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


_VALID_STYLES: frozenset[str] = frozenset(
    {"box_cage", "cylindrical_cage", "perimeter_rail", "blade_shroud", "fan_grille"}
)

_VALID_AXES: frozenset[str] = frozenset({"x", "y", "z"})


@dataclass(frozen=True)
class GuardAttributes:
    """Typed attribute contract for node_type='guard'.

    Fields:
        style: guard family. Must be in ``_VALID_STYLES``.
        width_cm: overall guard width (positive).
        height_cm: overall guard height (positive).
        depth_cm: overall guard depth (positive).
        bar_radius_cm: radius of each cage bar (positive).
        bar_count: number of cage bars (>=2).
        axis: primary axis the bars run along. Must be in ``_VALID_AXES``.
        region_id: optional material-zone identifier.
    """

    style: str
    width_cm: float
    height_cm: float
    depth_cm: float
    bar_radius_cm: float
    bar_count: int = 4
    axis: str = "y"
    region_id: str | None = None

    def __post_init__(self) -> None:
        if self.style not in _VALID_STYLES:
            raise ValueError(
                f"guard.style={self.style!r} not in {sorted(_VALID_STYLES)}"
            )
        for field_name, value in (
            ("width_cm", self.width_cm),
            ("height_cm", self.height_cm),
            ("depth_cm", self.depth_cm),
            ("bar_radius_cm", self.bar_radius_cm),
        ):
            if not isinstance(value, (int, float)) or float(value) <= 0:
                raise ValueError(f"guard.{field_name}={value} must be positive")
        if not isinstance(self.bar_count, int) or self.bar_count < 2:
            raise ValueError(f"guard.bar_count={self.bar_count} must be >= 2")
        if self.axis not in _VALID_AXES:
            raise ValueError(
                f"guard.axis={self.axis!r} not in {sorted(_VALID_AXES)}"
            )

    @classmethod
    def from_dict(cls, attrs: dict[str, Any]) -> "GuardAttributes":
        if not isinstance(attrs, dict):
            raise TypeError(
                f"guard attributes must be dict, got {type(attrs).__name__}"
            )
        for required in (
            "style",
            "width_cm",
            "height_cm",
            "depth_cm",
            "bar_radius_cm",
        ):
            if required not in attrs:
                raise ValueError(
                    f"guard attributes missing required key {required!r}"
                )
        return cls(
            style=str(attrs["style"]),
            width_cm=float(attrs["width_cm"]),
            height_cm=float(attrs["height_cm"]),
            depth_cm=float(attrs["depth_cm"]),
            bar_radius_cm=float(attrs["bar_radius_cm"]),
            bar_count=int(attrs.get("bar_count") or 4),
            axis=str(attrs.get("axis") or "y"),
            region_id=attrs.get("region_id"),
        )
