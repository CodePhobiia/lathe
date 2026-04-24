"""Transfer IR: V1.1 ``transfer`` block.

Describes how properties (materials, rigs, features) are transferred
between assets or between reference and target geometry.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class TransferIR:
    """TransferIR."""
    values: dict[str, Any] = field(default_factory=dict)
    adapt_policy: dict[str, Any] = field(default_factory=dict)
    transfer_rules: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_asset(cls, asset: dict[str, Any]) -> "TransferIR":
        """From asset.

        Args:
            asset: asset argument.

        Returns:
            The result.
        """
        transfer = asset.get("transfer", {})
        return cls(
            values={k: v for k, v in transfer.items() if not str(k).startswith("resolved_")},
            adapt_policy=dict(transfer.get("resolved_adapt_policy", {})),
            transfer_rules=list(transfer.get("resolved_transfer_rules", [])),
        )

    def to_dict(self) -> dict[str, Any]:
        """To dict.

        Returns:
            The result.
        """
        return asdict(self)
