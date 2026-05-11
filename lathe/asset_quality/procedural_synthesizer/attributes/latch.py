"""Typed attribute schema for node_type='latch'.

A latch is a clasp / lock mechanism. Geometry: a base plate mounted
to the host face + a movable arm or lever that visually closes. The
attribute schema captures both. Mechanisms (kinematics, hinge motion)
are out of scope here; this generator emits only the closed-state
visible geometry.

Validated in Stage 4 of the synthesizer pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


_VALID_STYLES: frozenset[str] = frozenset(
    {"hasp", "barrel_lock", "draw_latch", "cam_lock", "padlock_eye"}
)

_VALID_AXES: frozenset[str] = frozenset({"x", "y", "z"})


@dataclass(frozen=True)
class LatchAttributes:
    """Typed attribute contract for node_type='latch'.

    Fields:
        style: latch family. Must be in ``_VALID_STYLES``.
        plate_width_cm: width of the mounting plate (positive).
        plate_height_cm: height of the mounting plate (positive).
        plate_thickness_cm: thickness of the mounting plate (positive).
        arm_length_cm: length of the lever / arm / shackle (positive).
        arm_radius_cm: radius (for cylindrical arms) (positive).
        host_face_axis: axis normal to the host face. Must be in
            ``_VALID_AXES``.
        region_id: optional material-zone identifier.
    """

    style: str
    plate_width_cm: float
    plate_height_cm: float
    plate_thickness_cm: float
    arm_length_cm: float
    arm_radius_cm: float
    host_face_axis: str = "z"
    region_id: str | None = None

    def __post_init__(self) -> None:
        if self.style not in _VALID_STYLES:
            raise ValueError(
                f"latch.style={self.style!r} not in {sorted(_VALID_STYLES)}"
            )
        for field_name, value in (
            ("plate_width_cm", self.plate_width_cm),
            ("plate_height_cm", self.plate_height_cm),
            ("plate_thickness_cm", self.plate_thickness_cm),
            ("arm_length_cm", self.arm_length_cm),
            ("arm_radius_cm", self.arm_radius_cm),
        ):
            if not isinstance(value, (int, float)) or float(value) <= 0:
                raise ValueError(f"latch.{field_name}={value} must be positive")
        if self.host_face_axis not in _VALID_AXES:
            raise ValueError(
                f"latch.host_face_axis={self.host_face_axis!r} not in {sorted(_VALID_AXES)}"
            )

    @classmethod
    def from_dict(cls, attrs: dict[str, Any]) -> "LatchAttributes":
        if not isinstance(attrs, dict):
            raise TypeError(
                f"latch attributes must be dict, got {type(attrs).__name__}"
            )
        for required in (
            "style",
            "plate_width_cm",
            "plate_height_cm",
            "plate_thickness_cm",
            "arm_length_cm",
            "arm_radius_cm",
        ):
            if required not in attrs:
                raise ValueError(
                    f"latch attributes missing required key {required!r}"
                )
        return cls(
            style=str(attrs["style"]),
            plate_width_cm=float(attrs["plate_width_cm"]),
            plate_height_cm=float(attrs["plate_height_cm"]),
            plate_thickness_cm=float(attrs["plate_thickness_cm"]),
            arm_length_cm=float(attrs["arm_length_cm"]),
            arm_radius_cm=float(attrs["arm_radius_cm"]),
            host_face_axis=str(attrs.get("host_face_axis") or "z"),
            region_id=attrs.get("region_id"),
        )
