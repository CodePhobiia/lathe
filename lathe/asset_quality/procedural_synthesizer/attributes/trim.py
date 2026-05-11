"""Typed attribute schema for node_type='trim'.

Trim is a decorative or protective edge band that runs along an axis-
aligned edge of a host volume. Common uses: rubberized edge guard on
a crate, decorative banding around a console, weather seal on a
cabinet door. Trim differs from frame in that frame composes a closed
rectangular perimeter while trim is a single linear band along one
edge.

Validated in Stage 4 of the synthesizer pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


_VALID_AXES: frozenset[str] = frozenset({"x", "y", "z"})

_VALID_PROFILES: frozenset[str] = frozenset(
    {"flat_band", "rounded_band", "rabbet", "ogee", "bullnose"}
)


@dataclass(frozen=True)
class TrimAttributes:
    """Typed attribute contract for node_type='trim'.

    Fields:
        edge_axis: along which axis the trim runs. Must be in ``_VALID_AXES``.
        length_cm: trim length along ``edge_axis`` (positive).
        cross_section_width_cm: trim cross-section width (positive).
        cross_section_height_cm: trim cross-section height (positive).
        profile: cross-section profile style. Must be in ``_VALID_PROFILES``.
        region_id: optional material-zone identifier consumed by
            downstream surface stages.
    """

    edge_axis: str
    length_cm: float
    cross_section_width_cm: float
    cross_section_height_cm: float
    profile: str = "flat_band"
    region_id: str | None = None

    def __post_init__(self) -> None:
        if self.edge_axis not in _VALID_AXES:
            raise ValueError(
                f"trim.edge_axis={self.edge_axis!r} not in {sorted(_VALID_AXES)}"
            )
        for field_name, value in (
            ("length_cm", self.length_cm),
            ("cross_section_width_cm", self.cross_section_width_cm),
            ("cross_section_height_cm", self.cross_section_height_cm),
        ):
            if not isinstance(value, (int, float)):
                raise TypeError(
                    f"trim.{field_name} must be numeric, got {type(value).__name__}"
                )
            if float(value) <= 0:
                raise ValueError(f"trim.{field_name}={value} must be positive")
        if self.profile not in _VALID_PROFILES:
            raise ValueError(
                f"trim.profile={self.profile!r} not in {sorted(_VALID_PROFILES)}"
            )
        if self.region_id is not None and not isinstance(self.region_id, str):
            raise TypeError(
                f"trim.region_id must be str or None, got "
                f"{type(self.region_id).__name__}"
            )

    @classmethod
    def from_dict(cls, attrs: dict[str, Any]) -> "TrimAttributes":
        """Validate a raw attribute dict and produce a typed instance."""
        if not isinstance(attrs, dict):
            raise TypeError(
                f"trim attributes must be dict, got {type(attrs).__name__}"
            )
        for required in ("edge_axis", "length_cm", "cross_section_width_cm", "cross_section_height_cm"):
            if required not in attrs:
                raise ValueError(f"trim attributes missing required key {required!r}")
        return cls(
            edge_axis=str(attrs["edge_axis"]),
            length_cm=float(attrs["length_cm"]),
            cross_section_width_cm=float(attrs["cross_section_width_cm"]),
            cross_section_height_cm=float(attrs["cross_section_height_cm"]),
            profile=str(attrs.get("profile") or "flat_band"),
            region_id=attrs.get("region_id"),
        )
