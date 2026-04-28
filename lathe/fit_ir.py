"""Fit IR: V1.1 ``fit`` block lowered into executable form.

Captures reference-to-target fitting rules used by the shape stage
when an asset opts in to learned or provided geometry proposals.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class FitIR:
    """FitIR."""

    values: dict[str, Any] = field(default_factory=dict)
    fit_profile: dict[str, Any] = field(default_factory=dict)
    reconstruct_policy: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_asset(cls, asset: dict[str, Any]) -> FitIR:
        """From asset.

        Args:
            asset: asset argument.

        Returns:
            The result.
        """
        fit = asset.get("fit", {})
        return cls(
            values={k: v for k, v in fit.items() if not str(k).startswith("resolved_")},
            fit_profile=dict(fit.get("resolved_fit_profile", {})),
            reconstruct_policy=dict(fit.get("resolved_reconstruct_policy", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        """To dict.

        Returns:
            The result.
        """
        return asdict(self)
