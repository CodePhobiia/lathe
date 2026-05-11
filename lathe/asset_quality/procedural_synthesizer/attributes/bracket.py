"""Typed attribute schema for node_type='bracket'.

A bracket is a structural reinforcement that ties two faces of a
host volume together — corner bracket, L-bracket, T-bracket, angle
plate, gusset. Mounted to a host edge or corner; the geometry forms
an L (two perpendicular plates) or a triangular fillet between two
faces.

Validated in Stage 4 of the synthesizer pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


_VALID_PROFILES: frozenset[str] = frozenset(
    {"l_bracket", "t_bracket", "angle_plate", "gusset", "corner_brace"}
)

_VALID_ORIENTATIONS: frozenset[str] = frozenset(
    {"xy", "xz", "yz"}
)


@dataclass(frozen=True)
class BracketAttributes:
    """Typed attribute contract for node_type='bracket'.

    Fields:
        profile: bracket family. Must be in ``_VALID_PROFILES``.
        leg_length_cm: length of each bracket leg (positive).
        leg_width_cm: width of each leg (positive).
        thickness_cm: plate thickness (positive, < leg_width_cm).
        orientation: plane the two legs lie in. Must be in
            ``_VALID_ORIENTATIONS``.
        fillet_cm: inner-corner fillet radius (>=0). Only honored by
            l_bracket / corner_brace profiles.
        region_id: optional material-zone identifier.
    """

    profile: str
    leg_length_cm: float
    leg_width_cm: float
    thickness_cm: float
    orientation: str = "xy"
    fillet_cm: float = 0.0
    region_id: str | None = None

    def __post_init__(self) -> None:
        if self.profile not in _VALID_PROFILES:
            raise ValueError(
                f"bracket.profile={self.profile!r} not in {sorted(_VALID_PROFILES)}"
            )
        for field_name, value in (
            ("leg_length_cm", self.leg_length_cm),
            ("leg_width_cm", self.leg_width_cm),
            ("thickness_cm", self.thickness_cm),
        ):
            if not isinstance(value, (int, float)) or float(value) <= 0:
                raise ValueError(f"bracket.{field_name}={value} must be positive")
        if float(self.thickness_cm) >= float(self.leg_width_cm):
            raise ValueError(
                f"bracket.thickness_cm={self.thickness_cm} must be < "
                f"leg_width_cm={self.leg_width_cm}; otherwise the bracket is "
                "degenerate."
            )
        if self.orientation not in _VALID_ORIENTATIONS:
            raise ValueError(
                f"bracket.orientation={self.orientation!r} not in {sorted(_VALID_ORIENTATIONS)}"
            )
        if not isinstance(self.fillet_cm, (int, float)) or float(self.fillet_cm) < 0:
            raise ValueError(f"bracket.fillet_cm={self.fillet_cm} must be >= 0")

    @classmethod
    def from_dict(cls, attrs: dict[str, Any]) -> "BracketAttributes":
        if not isinstance(attrs, dict):
            raise TypeError(
                f"bracket attributes must be dict, got {type(attrs).__name__}"
            )
        for required in ("profile", "leg_length_cm", "leg_width_cm", "thickness_cm"):
            if required not in attrs:
                raise ValueError(
                    f"bracket attributes missing required key {required!r}"
                )
        return cls(
            profile=str(attrs["profile"]),
            leg_length_cm=float(attrs["leg_length_cm"]),
            leg_width_cm=float(attrs["leg_width_cm"]),
            thickness_cm=float(attrs["thickness_cm"]),
            orientation=str(attrs.get("orientation") or "xy"),
            fillet_cm=float(attrs.get("fillet_cm") or 0.0),
            region_id=attrs.get("region_id"),
        )
