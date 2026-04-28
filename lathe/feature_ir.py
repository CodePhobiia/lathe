"""Feature IR: lowered feature-grammar expressions.

Intermediate representation for parameterised features emitted by
scaffold compilation and consumed by feature fusion.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class FeatureIR:
    """FeatureIR."""

    geometry: dict[str, Any] = field(default_factory=dict)
    features: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_asset(cls, asset: dict[str, Any]) -> FeatureIR:
        """From asset.

        Args:
            asset: asset argument.

        Returns:
            The result.
        """
        return cls(
            geometry=dict(asset.get("geometry", {})),
            features=dict(asset.get("features", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        """To dict.

        Returns:
            The result.
        """
        return asdict(self)
