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


def infer_fidelity_profile(asset_graph: AssetGraph) -> FidelityProfile:
    critic_name = str(asset_graph.critic_name or "").lower()
    threshold = float(asset_graph.validation_threshold or 0.80)
    if "hero" in critic_name or threshold >= 0.86:
        return FidelityProfile(
            tier="hero",
            detail_density=1.35,
            edge_weight=1.25,
            panel_depth=1.30,
            trim_complexity=5,
            support_complexity=1.20,
            silhouette_refinement=1.18,
            repair_budget=4,
        )
    if threshold <= 0.78:
        return FidelityProfile(
            tier="blockout",
            detail_density=0.70,
            edge_weight=0.75,
            panel_depth=0.72,
            trim_complexity=1,
            support_complexity=0.80,
            silhouette_refinement=0.86,
            repair_budget=1,
        )
    return FidelityProfile(
        tier="game",
        detail_density=1.0,
        edge_weight=1.0,
        panel_depth=1.0,
        trim_complexity=3,
        support_complexity=1.0,
        silhouette_refinement=1.0,
        repair_budget=3,
    )
