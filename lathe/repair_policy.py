from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class RepairPolicyIR:
    use: str = ""
    mode: str = ""
    max_rounds: int | None = None
    allow: list[str] = field(default_factory=list)
    deny: list[str] = field(default_factory=list)

    @classmethod
    def from_asset(cls, asset: dict[str, Any]) -> "RepairPolicyIR":
        repair_policy = asset.get("repair_policy", {})
        return cls(
            use=str(repair_policy.get("use", "")),
            mode=str(repair_policy.get("mode", "")),
            max_rounds=repair_policy.get("max_rounds"),
            allow=list(repair_policy.get("allow", [])),
            deny=list(repair_policy.get("deny", [])),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
