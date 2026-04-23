from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class FeatureIR:
    geometry: dict[str, Any] = field(default_factory=dict)
    features: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_asset(cls, asset: dict[str, Any]) -> "FeatureIR":
        return cls(
            geometry=dict(asset.get("geometry", {})),
            features=dict(asset.get("features", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
