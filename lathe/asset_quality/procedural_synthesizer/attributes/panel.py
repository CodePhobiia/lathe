"""Typed attribute schema for node_type='panel'.

A panel is a flat or slightly-curved plate authored to attach to a
primary volume or to break up a large face. Examples: front-face
panel on a crate, door panel, service-access panel on a console.

Validated in Stage 4 of the procedural synthesizer pipeline before
the panel generator consumes it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_VALID_PLANES: frozenset[str] = frozenset({"xy", "xz", "yz"})

_VALID_BORDER_POLICIES: frozenset[str] = frozenset(
    {"beveled", "sharp", "rounded", "trim_band"}
)


@dataclass(frozen=True)
class PanelAttributes:
    """Typed attribute contract for node_type='panel'.

    Construction-graph ConstructionNode.attributes is validated against
    this schema. A node missing a required field, or carrying a value
    outside the enumerated set, fails validation.

    Fields:
        plane: which plane the panel's flat face lives in. Must be in
            ``_VALID_PLANES``.
        width_cm: panel width along the plane's first axis (positive).
        height_cm: panel height along the plane's second axis (positive).
        thickness_cm: panel thickness along the plane's normal axis
            (positive).
        inset_depth_cm: how deeply the panel is recessed below its
            attachment surface. Zero means flush; positive means recessed.
        border_policy: how panel edges are finished. Must be in
            ``_VALID_BORDER_POLICIES``.
        region_id: optional identifier linking the panel to a material
            zone / face region. Used by downstream surface stages.
    """

    plane: str
    width_cm: float
    height_cm: float
    thickness_cm: float
    inset_depth_cm: float = 0.0
    border_policy: str = "sharp"
    region_id: str | None = None

    def __post_init__(self) -> None:
        if self.plane not in _VALID_PLANES:
            raise ValueError(
                f"panel.plane={self.plane!r} not in {sorted(_VALID_PLANES)}"
            )
        for field_name, value in (
            ("width_cm", self.width_cm),
            ("height_cm", self.height_cm),
            ("thickness_cm", self.thickness_cm),
        ):
            if not isinstance(value, (int, float)):
                raise TypeError(
                    f"panel.{field_name} must be numeric, got "
                    f"{type(value).__name__}"
                )
            if float(value) <= 0:
                raise ValueError(
                    f"panel.{field_name}={value} must be positive"
                )
        if not isinstance(self.inset_depth_cm, (int, float)):
            raise TypeError(
                f"panel.inset_depth_cm must be numeric, got "
                f"{type(self.inset_depth_cm).__name__}"
            )
        if float(self.inset_depth_cm) < 0:
            raise ValueError(
                f"panel.inset_depth_cm={self.inset_depth_cm} must be >= 0"
            )
        if self.border_policy not in _VALID_BORDER_POLICIES:
            raise ValueError(
                f"panel.border_policy={self.border_policy!r} not in "
                f"{sorted(_VALID_BORDER_POLICIES)}"
            )
        if self.region_id is not None and not isinstance(self.region_id, str):
            raise TypeError(
                f"panel.region_id must be str or None, got "
                f"{type(self.region_id).__name__}"
            )

    @classmethod
    def from_dict(cls, attrs: dict[str, Any]) -> PanelAttributes:
        """Validate a raw attribute dict and produce a typed instance."""
        if not isinstance(attrs, dict):
            raise TypeError(
                f"panel attributes must be dict, got {type(attrs).__name__}"
            )
        # All three core dimensions required
        for required in ("plane", "width_cm", "height_cm", "thickness_cm"):
            if required not in attrs:
                raise ValueError(f"panel attributes missing required key {required!r}")
        return cls(
            plane=str(attrs["plane"]),
            width_cm=float(attrs["width_cm"]),
            height_cm=float(attrs["height_cm"]),
            thickness_cm=float(attrs["thickness_cm"]),
            inset_depth_cm=float(attrs.get("inset_depth_cm") or 0.0),
            border_policy=str(attrs.get("border_policy") or "sharp"),
            region_id=attrs.get("region_id"),
        )
