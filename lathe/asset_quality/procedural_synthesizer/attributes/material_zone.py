"""Typed attribute schema for node_type='material_zone'.

A material_zone is a non-geometric annotation that tags a region of a
host volume for downstream surface authoring — basecolor, normal,
roughness, metallic / wear / dirt overlays. It does not emit geometry
ops; it emits a metadata-bearing op the surface stage consumes.

Validated in Stage 4 of the synthesizer pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class MaterialZoneAttributes:
    """Typed attribute contract for node_type='material_zone'.

    Fields:
        zone_id: stable identifier the surface stage uses to look up
            this zone's material assignment. Required.
        material_hint: short human-readable hint (e.g.
            "weathered_steel" / "rubber_grip" / "decal_zone"). The
            surface stage may resolve this against a style pack's
            material library.
        priority: when multiple material zones overlap on the same
            face, the higher priority wins. Defaults to 0.
        host_face_axis: optional axis identifier of the host face this
            zone covers. None means the zone applies to the host
            volume as a whole (used for full-asset reskins).
        tags: optional set of additional descriptors (e.g.
            "wear_prone", "decal_safe", "metallic_paint").
    """

    zone_id: str
    material_hint: str
    priority: int = 0
    host_face_axis: str | None = None
    tags: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not isinstance(self.zone_id, str) or not self.zone_id:
            raise ValueError(
                f"material_zone.zone_id must be a non-empty string"
            )
        if not isinstance(self.material_hint, str) or not self.material_hint:
            raise ValueError(
                f"material_zone.material_hint must be a non-empty string"
            )
        if not isinstance(self.priority, int):
            raise TypeError(
                f"material_zone.priority must be int, got "
                f"{type(self.priority).__name__}"
            )
        if self.host_face_axis is not None and self.host_face_axis not in {"x", "y", "z", "+x", "-x", "+y", "-y", "+z", "-z"}:
            raise ValueError(
                f"material_zone.host_face_axis={self.host_face_axis!r} not "
                "in valid axis identifiers (x/y/z optionally signed)"
            )
        for tag in self.tags:
            if not isinstance(tag, str) or not tag:
                raise ValueError(
                    f"material_zone.tags entries must be non-empty strings"
                )

    @classmethod
    def from_dict(cls, attrs: dict[str, Any]) -> "MaterialZoneAttributes":
        """Validate a raw attribute dict and produce a typed instance."""
        if not isinstance(attrs, dict):
            raise TypeError(
                f"material_zone attributes must be dict, got "
                f"{type(attrs).__name__}"
            )
        for required in ("zone_id", "material_hint"):
            if required not in attrs:
                raise ValueError(
                    f"material_zone attributes missing required key {required!r}"
                )
        tags = attrs.get("tags") or ()
        return cls(
            zone_id=str(attrs["zone_id"]),
            material_hint=str(attrs["material_hint"]),
            priority=int(attrs.get("priority") or 0),
            host_face_axis=attrs.get("host_face_axis"),
            tags=tuple(str(t) for t in tags),
        )
