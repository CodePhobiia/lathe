"""Typed attribute schema for node_type='frame'.

A frame is a rectangular perimeter of structural members (top/bottom +
left/right) wrapping a host face. Common uses: steel band wrapping a
crate, trim frame around a service-cabinet door, structural perimeter
of a panel-line cutout. The frame's plane is identified by the
``plane`` field (xy / xz / yz) matching panel.plane semantics; the
frame's *thickness axis* is perpendicular to that plane.

Validated in Stage 4 of the synthesizer pipeline before the frame
generator consumes it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


_VALID_PLANES: frozenset[str] = frozenset({"xy", "xz", "yz"})

_VALID_CORNER_STYLES: frozenset[str] = frozenset(
    {"sharp", "mitered", "beveled"}
)


@dataclass(frozen=True)
class FrameAttributes:
    """Typed attribute contract for node_type='frame'.

    Fields:
        plane: which plane the frame's face lives in. Must be in
            ``_VALID_PLANES``. Matches panel.plane semantics: the
            frame perimeter is in this plane; the frame's protrusion
            depth is along the plane's normal axis.
        outer_width_cm: outer-rectangle width along the plane's first
            axis (positive).
        outer_height_cm: outer-rectangle height along the plane's
            second axis (positive).
        member_thickness_cm: cross-section thickness of each frame
            member (positive). Smaller than half of outer_width /
            outer_height so the frame has a non-degenerate opening.
        protrusion_cm: how far the frame stands proud of its host
            surface along the plane's normal axis (>=0; zero means
            flush).
        corner_style: how rail corners are finished. Must be in
            ``_VALID_CORNER_STYLES``.
        region_id: optional material-zone identifier consumed by
            downstream surface stages.
    """

    plane: str
    outer_width_cm: float
    outer_height_cm: float
    member_thickness_cm: float
    protrusion_cm: float = 0.0
    corner_style: str = "sharp"
    region_id: str | None = None

    def __post_init__(self) -> None:
        if self.plane not in _VALID_PLANES:
            raise ValueError(
                f"frame.plane={self.plane!r} not in {sorted(_VALID_PLANES)}"
            )
        for field_name, value in (
            ("outer_width_cm", self.outer_width_cm),
            ("outer_height_cm", self.outer_height_cm),
            ("member_thickness_cm", self.member_thickness_cm),
        ):
            if not isinstance(value, (int, float)):
                raise TypeError(
                    f"frame.{field_name} must be numeric, got "
                    f"{type(value).__name__}"
                )
            if float(value) <= 0:
                raise ValueError(
                    f"frame.{field_name}={value} must be positive"
                )
        if float(self.member_thickness_cm) >= float(self.outer_width_cm) * 0.5:
            raise ValueError(
                f"frame.member_thickness_cm={self.member_thickness_cm} must be "
                f"< outer_width_cm/2 ({self.outer_width_cm * 0.5}); otherwise "
                "the frame's opening is degenerate."
            )
        if float(self.member_thickness_cm) >= float(self.outer_height_cm) * 0.5:
            raise ValueError(
                f"frame.member_thickness_cm={self.member_thickness_cm} must be "
                f"< outer_height_cm/2 ({self.outer_height_cm * 0.5})."
            )
        if not isinstance(self.protrusion_cm, (int, float)):
            raise TypeError(
                f"frame.protrusion_cm must be numeric, got "
                f"{type(self.protrusion_cm).__name__}"
            )
        if float(self.protrusion_cm) < 0:
            raise ValueError(
                f"frame.protrusion_cm={self.protrusion_cm} must be >= 0"
            )
        if self.corner_style not in _VALID_CORNER_STYLES:
            raise ValueError(
                f"frame.corner_style={self.corner_style!r} not in "
                f"{sorted(_VALID_CORNER_STYLES)}"
            )
        if self.region_id is not None and not isinstance(self.region_id, str):
            raise TypeError(
                f"frame.region_id must be str or None, got "
                f"{type(self.region_id).__name__}"
            )

    @classmethod
    def from_dict(cls, attrs: dict[str, Any]) -> "FrameAttributes":
        """Validate a raw attribute dict and produce a typed instance."""
        if not isinstance(attrs, dict):
            raise TypeError(
                f"frame attributes must be dict, got {type(attrs).__name__}"
            )
        for required in ("plane", "outer_width_cm", "outer_height_cm", "member_thickness_cm"):
            if required not in attrs:
                raise ValueError(f"frame attributes missing required key {required!r}")
        return cls(
            plane=str(attrs["plane"]),
            outer_width_cm=float(attrs["outer_width_cm"]),
            outer_height_cm=float(attrs["outer_height_cm"]),
            member_thickness_cm=float(attrs["member_thickness_cm"]),
            protrusion_cm=float(attrs.get("protrusion_cm") or 0.0),
            corner_style=str(attrs.get("corner_style") or "sharp"),
            region_id=attrs.get("region_id"),
        )
