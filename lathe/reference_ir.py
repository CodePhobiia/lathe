from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ReferenceIR:
    images: list[Any] = field(default_factory=list)
    meshes: list[Any] = field(default_factory=list)
    assets: list[Any] = field(default_factory=list)
    materials: list[Any] = field(default_factory=list)
    reference_sets: list[str] = field(default_factory=list)
    resolved_reference_sets: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_asset(cls, asset: dict[str, Any]) -> "ReferenceIR":
        refs = asset.get("refs", {})
        return cls(
            images=list(refs.get("images", [])),
            meshes=list(refs.get("meshes", [])),
            assets=list(refs.get("assets", [])),
            materials=list(refs.get("materials", [])),
            reference_sets=list(refs.get("reference_sets", [])),
            resolved_reference_sets=list(refs.get("resolved_reference_sets", [])),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
