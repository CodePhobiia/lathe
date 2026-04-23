from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ShapePrimitive:
    primitive_type: str
    part: str
    center: tuple[float, float, float]
    extents: tuple[float, float, float] | None = None
    radius: float | None = None
    height: float | None = None
    axis: str = "y"
    tags: list[str] = field(default_factory=list)
    component: str | None = None
    region: str | None = None
    blend_mode: str = "union"
    rounding: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ShapeRegion:
    name: str
    part: str
    component: str
    center: tuple[float, float, float]
    extents: tuple[float, float, float]
    tags: list[str] = field(default_factory=list)
    adjacency: list[str] = field(default_factory=list)
    symmetry_mate: str | None = None
    interface_role: str | None = None
    required: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ShapeIR:
    asset_name: str
    family: str
    blueprint_id: str
    symmetry_axis: str | None
    units: str
    primitives: list[ShapePrimitive]
    regions: list[ShapeRegion]
    primitives_used: list[str]
    part_graph: list[dict[str, str]]
    signature: dict[str, Any]
    assessment: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["primitives"] = [primitive.to_dict() for primitive in self.primitives]
        payload["regions"] = [region.to_dict() for region in self.regions]
        return payload
