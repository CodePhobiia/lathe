from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class KitIR:
    kit_name: str = ""
    values: dict[str, Any] = field(default_factory=dict)
    assembly_policy: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_asset(cls, asset: dict[str, Any]) -> "KitIR":
        assembly = asset.get("assembly", {})
        constraints = asset.get("constraints", {})
        return cls(
            kit_name=str(assembly.get("kit", "")),
            values=dict(assembly.get("resolved_kit", {}).get("values", {})),
            assembly_policy=dict(constraints.get("resolved_assembly_policy", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
