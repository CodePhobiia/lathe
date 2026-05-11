"""Typed attribute schema for node_type='socket'.

A socket is a cylindrical or rectangular receiving cavity cut into a
host face — power-outlet socket, plug-port socket, axle-bearing seat,
tool-mounting slot. Subtractive geometry.

Validated in Stage 4 of the synthesizer pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


_VALID_AXES: frozenset[str] = frozenset({"x", "y", "z"})

_VALID_PROFILES: frozenset[str] = frozenset(
    {"round", "square", "rounded_square", "keyway"}
)


@dataclass(frozen=True)
class SocketAttributes:
    """Typed attribute contract for node_type='socket'.

    Fields:
        depth_axis: axis along which the socket recesses. Must be in
            ``_VALID_AXES``.
        depth_cm: socket depth (positive).
        radius_cm: socket radius / half-width (positive).
        profile: socket cross-section profile. Must be in ``_VALID_PROFILES``.
        chamfer_cm: chamfer at the socket mouth (>=0).
        region_id: optional material-zone identifier.
    """

    depth_axis: str
    depth_cm: float
    radius_cm: float
    profile: str = "round"
    chamfer_cm: float = 0.0
    region_id: str | None = None

    def __post_init__(self) -> None:
        if self.depth_axis not in _VALID_AXES:
            raise ValueError(
                f"socket.depth_axis={self.depth_axis!r} not in {sorted(_VALID_AXES)}"
            )
        for field_name, value in (("depth_cm", self.depth_cm), ("radius_cm", self.radius_cm)):
            if not isinstance(value, (int, float)) or float(value) <= 0:
                raise ValueError(f"socket.{field_name}={value} must be positive")
        if self.profile not in _VALID_PROFILES:
            raise ValueError(
                f"socket.profile={self.profile!r} not in {sorted(_VALID_PROFILES)}"
            )
        if not isinstance(self.chamfer_cm, (int, float)) or float(self.chamfer_cm) < 0:
            raise ValueError(f"socket.chamfer_cm={self.chamfer_cm} must be >= 0")

    @classmethod
    def from_dict(cls, attrs: dict[str, Any]) -> "SocketAttributes":
        if not isinstance(attrs, dict):
            raise TypeError(
                f"socket attributes must be dict, got {type(attrs).__name__}"
            )
        for required in ("depth_axis", "depth_cm", "radius_cm"):
            if required not in attrs:
                raise ValueError(
                    f"socket attributes missing required key {required!r}"
                )
        return cls(
            depth_axis=str(attrs["depth_axis"]),
            depth_cm=float(attrs["depth_cm"]),
            radius_cm=float(attrs["radius_cm"]),
            profile=str(attrs.get("profile") or "round"),
            chamfer_cm=float(attrs.get("chamfer_cm") or 0.0),
            region_id=attrs.get("region_id"),
        )
