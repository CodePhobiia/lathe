from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class AssemblyIR:
    family: str
    components: list[str] = field(default_factory=list)
    mechanisms: list[str] = field(default_factory=list)
    traits: list[str] = field(default_factory=list)
    resolved_components: list[dict[str, Any]] = field(default_factory=list)
    resolved_mechanisms: list[dict[str, Any]] = field(default_factory=list)
    resolved_traits: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_asset(cls, asset: dict[str, Any]) -> "AssemblyIR":
        assembly = asset.get("assembly", {})
        return cls(
            family=str(assembly.get("family", "")),
            components=list(assembly.get("components", [])),
            mechanisms=list(assembly.get("mechanisms", [])),
            traits=list(assembly.get("traits", [])),
            resolved_components=list(assembly.get("resolved_components", [])),
            resolved_mechanisms=list(assembly.get("resolved_mechanisms", [])),
            resolved_traits=list(assembly.get("resolved_traits", [])),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
