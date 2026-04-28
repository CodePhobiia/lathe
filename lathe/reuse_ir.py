"""Reuse IR: V1.1 ``reuse`` block.

Captures how an asset borrows components or libraries from a kit,
including renaming and override rules.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ReuseIR:
    """ReuseIR."""

    values: dict[str, Any] = field(default_factory=dict)
    resolved_kit: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_asset(cls, asset: dict[str, Any]) -> ReuseIR:
        """From asset.

        Args:
            asset: asset argument.

        Returns:
            The result.
        """
        reuse = asset.get("reuse", {})
        assembly = asset.get("assembly", {})
        return cls(
            values=dict(reuse),
            resolved_kit=dict(assembly.get("resolved_kit", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        """To dict.

        Returns:
            The result.
        """
        return asdict(self)
