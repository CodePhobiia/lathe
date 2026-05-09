from __future__ import annotations

from dataclasses import asdict, dataclass

from .asset_graph import AssetGraph


@dataclass
class FidelityProfile:
    tier: str
    detail_density: float
    edge_weight: float
    panel_depth: float
    trim_complexity: int
    support_complexity: float
    silhouette_refinement: float
    repair_budget: int

    def to_dict(self) -> dict[str, float | int | str]:
        return asdict(self)


_TIER_MULTIPLIERS: dict[str, dict[str, float | int]] = {
    "blockout": {
        "detail_density": 0.70,
        "edge_weight": 0.75,
        "panel_depth": 0.72,
        "trim_complexity": 1,
        "support_complexity": 0.80,
        "silhouette_refinement": 0.86,
        "repair_budget": 1,
    },
    "game": {
        "detail_density": 1.0,
        "edge_weight": 1.0,
        "panel_depth": 1.0,
        "trim_complexity": 3,
        "support_complexity": 1.0,
        "silhouette_refinement": 1.0,
        "repair_budget": 3,
    },
    "hero": {
        "detail_density": 1.35,
        "edge_weight": 1.25,
        "panel_depth": 1.30,
        "trim_complexity": 5,
        "support_complexity": 1.20,
        "silhouette_refinement": 1.18,
        "repair_budget": 4,
    },
    "cinematic": {
        "detail_density": 2.20,
        "edge_weight": 1.65,
        "panel_depth": 1.80,
        "trim_complexity": 8,
        "support_complexity": 1.45,
        "silhouette_refinement": 1.40,
        "repair_budget": 6,
    },
}


def _tier_multipliers(tier: str) -> dict[str, float | int]:
    """Return the canonical multiplier dict for a fidelity ``tier``.

    Public helper so downstream surface authoring (e.g. ``surface_grammar``)
    can read tier-driven multipliers without re-deriving them.
    """

    if tier not in _TIER_MULTIPLIERS:
        raise KeyError(f"unknown fidelity tier: {tier!r}")
    return dict(_TIER_MULTIPLIERS[tier])


def _profile_from_tier(tier: str) -> FidelityProfile:
    mult = _TIER_MULTIPLIERS[tier]
    return FidelityProfile(
        tier=tier,
        detail_density=float(mult["detail_density"]),
        edge_weight=float(mult["edge_weight"]),
        panel_depth=float(mult["panel_depth"]),
        trim_complexity=int(mult["trim_complexity"]),
        support_complexity=float(mult["support_complexity"]),
        silhouette_refinement=float(mult["silhouette_refinement"]),
        repair_budget=int(mult["repair_budget"]),
    )


def infer_fidelity_profile(asset_graph: AssetGraph) -> FidelityProfile:
    critic_name = str(asset_graph.critic_name or "").lower()
    threshold = float(asset_graph.validation_threshold or 0.80)
    if "cinematic" in critic_name or threshold >= 0.92:
        return _profile_from_tier("cinematic")
    if "hero" in critic_name or threshold >= 0.86:
        return _profile_from_tier("hero")
    if threshold <= 0.78:
        return _profile_from_tier("blockout")
    return _profile_from_tier("game")
