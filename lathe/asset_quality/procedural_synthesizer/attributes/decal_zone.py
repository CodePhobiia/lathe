"""Typed attribute schema for node_type='decal_zone'.

A decal_zone is a non-geometric annotation that tags a region of a
host face for downstream decal placement — warning labels, logos,
serial numbers, hazard stripes. Metadata-only; consumed by the
surface stage to place decals at authoring time.

Validated in Stage 4 of the synthesizer pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class DecalZoneAttributes:
    """Typed attribute contract for node_type='decal_zone'.

    Fields:
        zone_id: stable identifier the surface stage uses to look up
            this decal zone's content. Required.
        decal_intent: short tag describing the decal purpose (e.g.
            "warning_stripe" / "serial_number" / "logo" /
            "fragile_label"). The surface stage resolves this against
            a style pack's decal library.
        host_face_axis: optional axis identifier of the host face the
            decal occupies. None means the surface stage picks.
        size_cm: bounding-box dimensions of the decal in cm (width,
            height). Both positive.
        priority: when multiple decal zones overlap, higher priority
            wins. Defaults to 0.
        tags: optional descriptors (e.g. "safety_critical",
            "weatherable", "factory_default").
    """

    zone_id: str
    decal_intent: str
    size_cm: tuple[float, float]
    host_face_axis: str | None = None
    priority: int = 0
    tags: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not isinstance(self.zone_id, str) or not self.zone_id:
            raise ValueError("decal_zone.zone_id must be a non-empty string")
        if not isinstance(self.decal_intent, str) or not self.decal_intent:
            raise ValueError("decal_zone.decal_intent must be a non-empty string")
        if not isinstance(self.size_cm, (tuple, list)) or len(self.size_cm) != 2:
            raise ValueError(
                "decal_zone.size_cm must be a (width_cm, height_cm) pair"
            )
        for label, value in zip(("width", "height"), self.size_cm, strict=False):
            if not isinstance(value, (int, float)) or float(value) <= 0:
                raise ValueError(
                    f"decal_zone.size_cm {label} must be a positive number"
                )
        if self.host_face_axis is not None and self.host_face_axis not in {
            "x", "y", "z", "+x", "-x", "+y", "-y", "+z", "-z"
        }:
            raise ValueError(
                f"decal_zone.host_face_axis={self.host_face_axis!r} invalid"
            )
        if not isinstance(self.priority, int):
            raise TypeError(
                f"decal_zone.priority must be int, got "
                f"{type(self.priority).__name__}"
            )

    @classmethod
    def from_dict(cls, attrs: dict[str, Any]) -> DecalZoneAttributes:
        if not isinstance(attrs, dict):
            raise TypeError(
                f"decal_zone attributes must be dict, got "
                f"{type(attrs).__name__}"
            )
        for required in ("zone_id", "decal_intent", "size_cm"):
            if required not in attrs:
                raise ValueError(
                    f"decal_zone attributes missing required key {required!r}"
                )
        raw_size = attrs["size_cm"]
        if not isinstance(raw_size, (tuple, list)):
            raise ValueError("decal_zone.size_cm must be a 2-tuple/list")
        return cls(
            zone_id=str(attrs["zone_id"]),
            decal_intent=str(attrs["decal_intent"]),
            size_cm=(float(raw_size[0]), float(raw_size[1])),
            host_face_axis=attrs.get("host_face_axis"),
            priority=int(attrs.get("priority") or 0),
            tags=tuple(str(t) for t in (attrs.get("tags") or ())),
        )
