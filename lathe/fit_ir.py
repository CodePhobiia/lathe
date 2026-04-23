from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class FitIR:
    values: dict[str, Any] = field(default_factory=dict)
    fit_profile: dict[str, Any] = field(default_factory=dict)
    reconstruct_policy: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_asset(cls, asset: dict[str, Any]) -> "FitIR":
        fit = asset.get("fit", {})
        return cls(
            values={k: v for k, v in fit.items() if not str(k).startswith("resolved_")},
            fit_profile=dict(fit.get("resolved_fit_profile", {})),
            reconstruct_policy=dict(fit.get("resolved_reconstruct_policy", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
