"""Typed attribute schema for node_type='mount'.

A mount is an attachment / anchor pad — feet, base plate, wall-mount
flange. Mounted to a host face; provides a thicker contact patch with
optional anchor holes.

Validated in Stage 4 of the synthesizer pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


_VALID_STYLES: frozenset[str] = frozenset(
    {"flat_pad", "raised_pad", "flange", "foot", "wall_anchor"}
)

_VALID_AXES: frozenset[str] = frozenset({"x", "y", "z"})


@dataclass(frozen=True)
class MountAttributes:
    """Typed attribute contract for node_type='mount'.

    Fields:
        style: mount family. Must be in ``_VALID_STYLES``.
        width_cm: pad width (positive).
        depth_cm: pad depth (positive).
        height_cm: pad height (positive).
        anchor_hole_count: number of anchor through-holes (>=0).
        anchor_hole_radius_cm: anchor hole radius (positive when count>0).
        host_face_axis: axis normal to the host face. Must be in
            ``_VALID_AXES``.
        region_id: optional material-zone identifier.
    """

    style: str
    width_cm: float
    depth_cm: float
    height_cm: float
    anchor_hole_count: int = 0
    anchor_hole_radius_cm: float = 0.3
    host_face_axis: str = "z"
    region_id: str | None = None

    def __post_init__(self) -> None:
        if self.style not in _VALID_STYLES:
            raise ValueError(
                f"mount.style={self.style!r} not in {sorted(_VALID_STYLES)}"
            )
        for field_name, value in (
            ("width_cm", self.width_cm),
            ("depth_cm", self.depth_cm),
            ("height_cm", self.height_cm),
        ):
            if not isinstance(value, (int, float)) or float(value) <= 0:
                raise ValueError(f"mount.{field_name}={value} must be positive")
        if not isinstance(self.anchor_hole_count, int) or self.anchor_hole_count < 0:
            raise ValueError(
                f"mount.anchor_hole_count={self.anchor_hole_count} must be >= 0"
            )
        if self.anchor_hole_count > 0:
            if (
                not isinstance(self.anchor_hole_radius_cm, (int, float))
                or float(self.anchor_hole_radius_cm) <= 0
            ):
                raise ValueError(
                    f"mount.anchor_hole_radius_cm={self.anchor_hole_radius_cm} "
                    "must be positive when anchor_hole_count>0"
                )
        if self.host_face_axis not in _VALID_AXES:
            raise ValueError(
                f"mount.host_face_axis={self.host_face_axis!r} not in {sorted(_VALID_AXES)}"
            )

    @classmethod
    def from_dict(cls, attrs: dict[str, Any]) -> "MountAttributes":
        if not isinstance(attrs, dict):
            raise TypeError(
                f"mount attributes must be dict, got {type(attrs).__name__}"
            )
        for required in ("style", "width_cm", "depth_cm", "height_cm"):
            if required not in attrs:
                raise ValueError(
                    f"mount attributes missing required key {required!r}"
                )
        return cls(
            style=str(attrs["style"]),
            width_cm=float(attrs["width_cm"]),
            depth_cm=float(attrs["depth_cm"]),
            height_cm=float(attrs["height_cm"]),
            anchor_hole_count=int(attrs.get("anchor_hole_count") or 0),
            anchor_hole_radius_cm=float(attrs.get("anchor_hole_radius_cm") or 0.3),
            host_face_axis=str(attrs.get("host_face_axis") or "z"),
            region_id=attrs.get("region_id"),
        )
