"""Typed attribute schema for node_type='wear_zone'.

A wear_zone is a non-geometric annotation that tags a region of a
host face for downstream wear-pattern authoring — scratched corners,
rusted feet, chipped edges. Metadata-only; consumed by the surface
stage to bias wear maps / dent masks / chip masks at the right
location and intensity.

Validated in Stage 4 of the synthesizer pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


_VALID_INTENSITY: frozenset[str] = frozenset(
    {"light", "moderate", "heavy", "extreme"}
)


@dataclass(frozen=True)
class WearZoneAttributes:
    """Typed attribute contract for node_type='wear_zone'.

    Fields:
        zone_id: stable identifier the surface stage uses to look up
            this wear zone's mask. Required.
        wear_kind: short tag describing wear type (e.g. "edge_chip" /
            "corner_dent" / "rust" / "scratch" / "grime"). Resolved
            against a style pack's wear library.
        intensity: how heavy the wear is. Must be in ``_VALID_INTENSITY``.
        host_face_axis: optional axis identifier of the host face the
            wear occupies.
        coverage_fraction: fraction of the host face the wear covers
            (0.0 to 1.0). Surface stage scales mask density by this.
        tags: optional descriptors.
    """

    zone_id: str
    wear_kind: str
    intensity: str = "moderate"
    host_face_axis: str | None = None
    coverage_fraction: float = 0.25
    tags: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not isinstance(self.zone_id, str) or not self.zone_id:
            raise ValueError("wear_zone.zone_id must be a non-empty string")
        if not isinstance(self.wear_kind, str) or not self.wear_kind:
            raise ValueError("wear_zone.wear_kind must be a non-empty string")
        if self.intensity not in _VALID_INTENSITY:
            raise ValueError(
                f"wear_zone.intensity={self.intensity!r} not in "
                f"{sorted(_VALID_INTENSITY)}"
            )
        if not isinstance(self.coverage_fraction, (int, float)):
            raise TypeError(
                f"wear_zone.coverage_fraction must be numeric, got "
                f"{type(self.coverage_fraction).__name__}"
            )
        cov = float(self.coverage_fraction)
        if cov < 0.0 or cov > 1.0:
            raise ValueError(
                f"wear_zone.coverage_fraction={cov} must be in [0.0, 1.0]"
            )
        if self.host_face_axis is not None and self.host_face_axis not in {
            "x", "y", "z", "+x", "-x", "+y", "-y", "+z", "-z"
        }:
            raise ValueError(
                f"wear_zone.host_face_axis={self.host_face_axis!r} invalid"
            )

    @classmethod
    def from_dict(cls, attrs: dict[str, Any]) -> "WearZoneAttributes":
        if not isinstance(attrs, dict):
            raise TypeError(
                f"wear_zone attributes must be dict, got "
                f"{type(attrs).__name__}"
            )
        for required in ("zone_id", "wear_kind"):
            if required not in attrs:
                raise ValueError(
                    f"wear_zone attributes missing required key {required!r}"
                )
        return cls(
            zone_id=str(attrs["zone_id"]),
            wear_kind=str(attrs["wear_kind"]),
            intensity=str(attrs.get("intensity") or "moderate"),
            host_face_axis=attrs.get("host_face_axis"),
            coverage_fraction=float(attrs.get("coverage_fraction", 0.25)),
            tags=tuple(str(t) for t in (attrs.get("tags") or ())),
        )
