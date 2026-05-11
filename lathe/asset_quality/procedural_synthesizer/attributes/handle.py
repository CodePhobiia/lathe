"""Typed attribute schema for node_type='handle'.

A handle is a graspable element protruding from a host surface — bar
handles, knob handles, recessed-grip handles, latch handles. Common
on doors, drawers, cabinets, crates, weapons.

Validated in Stage 4 of the synthesizer pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


_VALID_AXES: frozenset[str] = frozenset({"x", "y", "z"})

_VALID_STYLES: frozenset[str] = frozenset(
    {"bar", "knob", "recessed_grip", "latch_lever", "pull_ring", "loop"}
)


@dataclass(frozen=True)
class HandleAttributes:
    """Typed attribute contract for node_type='handle'.

    Fields:
        style: handle style. Must be in ``_VALID_STYLES``.
        length_cm: handle major dimension (positive). For bar/loop:
            the bar length. For knob: the knob diameter. For
            recessed_grip: the slot length.
        grip_radius_cm: cross-section radius of the grippable portion
            (positive).
        standoff_cm: distance the handle stands off from the host
            surface (>=0; zero means flush / recessed).
        axis: which axis the handle extends along (the "long" axis of
            a bar handle, or the protrusion axis of a knob handle).
            Must be in ``_VALID_AXES``.
        region_id: optional material-zone identifier.
    """

    style: str
    length_cm: float
    grip_radius_cm: float
    standoff_cm: float = 0.0
    axis: str = "y"
    region_id: str | None = None

    def __post_init__(self) -> None:
        if self.style not in _VALID_STYLES:
            raise ValueError(
                f"handle.style={self.style!r} not in {sorted(_VALID_STYLES)}"
            )
        for field_name, value in (
            ("length_cm", self.length_cm),
            ("grip_radius_cm", self.grip_radius_cm),
        ):
            if not isinstance(value, (int, float)):
                raise TypeError(
                    f"handle.{field_name} must be numeric, got "
                    f"{type(value).__name__}"
                )
            if float(value) <= 0:
                raise ValueError(
                    f"handle.{field_name}={value} must be positive"
                )
        if not isinstance(self.standoff_cm, (int, float)):
            raise TypeError(
                f"handle.standoff_cm must be numeric, got "
                f"{type(self.standoff_cm).__name__}"
            )
        if float(self.standoff_cm) < 0:
            raise ValueError(
                f"handle.standoff_cm={self.standoff_cm} must be >= 0"
            )
        if self.axis not in _VALID_AXES:
            raise ValueError(
                f"handle.axis={self.axis!r} not in {sorted(_VALID_AXES)}"
            )
        if self.region_id is not None and not isinstance(self.region_id, str):
            raise TypeError(
                f"handle.region_id must be str or None, got "
                f"{type(self.region_id).__name__}"
            )

    @classmethod
    def from_dict(cls, attrs: dict[str, Any]) -> "HandleAttributes":
        """Validate a raw attribute dict and produce a typed instance."""
        if not isinstance(attrs, dict):
            raise TypeError(
                f"handle attributes must be dict, got {type(attrs).__name__}"
            )
        for required in ("style", "length_cm", "grip_radius_cm"):
            if required not in attrs:
                raise ValueError(f"handle attributes missing required key {required!r}")
        return cls(
            style=str(attrs["style"]),
            length_cm=float(attrs["length_cm"]),
            grip_radius_cm=float(attrs["grip_radius_cm"]),
            standoff_cm=float(attrs.get("standoff_cm") or 0.0),
            axis=str(attrs.get("axis") or "y"),
            region_id=attrs.get("region_id"),
        )
