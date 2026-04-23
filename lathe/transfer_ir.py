from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class TransferIR:
    values: dict[str, Any] = field(default_factory=dict)
    adapt_policy: dict[str, Any] = field(default_factory=dict)
    transfer_rules: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_asset(cls, asset: dict[str, Any]) -> "TransferIR":
        transfer = asset.get("transfer", {})
        return cls(
            values={k: v for k, v in transfer.items() if not str(k).startswith("resolved_")},
            adapt_policy=dict(transfer.get("resolved_adapt_policy", {})),
            transfer_rules=list(transfer.get("resolved_transfer_rules", [])),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
