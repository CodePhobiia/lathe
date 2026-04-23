from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ReuseIR:
    values: dict[str, Any] = field(default_factory=dict)
    resolved_kit: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_asset(cls, asset: dict[str, Any]) -> "ReuseIR":
        reuse = asset.get("reuse", {})
        assembly = asset.get("assembly", {})
        return cls(
            values=dict(reuse),
            resolved_kit=dict(assembly.get("resolved_kit", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
