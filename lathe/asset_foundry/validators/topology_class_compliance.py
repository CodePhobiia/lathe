"""Topology class compliance validator.

Per northstar §10 Lane G later-tasks. Different asset classes
demand different topology characteristics:

  - hard-surface props: bool-clean quads + bevel rings + hard-edge marks
  - cottages: clean grid topology on flat walls
  - crystals: pure-facet flat-normal triangulation
  - trees: flat-shaded conical foliage; trunk = capsule topology
  - paths: thin walkable ribbon + decorative tiles
  - bridges: planks + posts + rope-segments
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

TOPOLOGY_CLASS_COMPLIANCE_VERSION = "lathe.asset_foundry.topology_class_compliance_v1"


_CLASS_TOPOLOGY_RULES: Mapping[str, Mapping[str, Any]] = {
    "industrial_crate": {
        "expects_quads_fraction_gt": 0.4,
        "expects_bevel_ring_face_count_gt": 100,
        "max_random_diagonals_fraction": 0.25,
        "min_distinct_parts": 5,
    },
    "mechanical_door": {
        "expects_quads_fraction_gt": 0.4,
        "expects_bevel_ring_face_count_gt": 80,
        "max_random_diagonals_fraction": 0.25,
        "min_distinct_parts": 4,
    },
    "violet_crystal_cluster": {
        "expects_quads_fraction_gt": 0.6,
        "expects_flat_normal_fraction_gt": 0.9,
        "max_random_diagonals_fraction": 0.05,
        "min_distinct_parts": 3,
    },
    "alpine_pine": {
        "expects_quads_fraction_gt": 0.5,
        "expects_flat_normal_fraction_gt": 0.85,
        "min_distinct_parts": 3,
    },
    "cozy_cottage": {
        "expects_quads_fraction_gt": 0.6,
        "expects_bevel_ring_face_count_gt": 20,
        "min_distinct_parts": 5,
    },
    "stone_path_segment": {
        "expects_walkable_zones_gt": 0,
        "min_distinct_parts": 2,
    },
    "rope_bridge": {
        "expects_quads_fraction_gt": 0.5,
        "expects_walkable_zones_gt": 0,
        "min_distinct_parts": 3,
    },
    "lantern_post": {
        "expects_quads_fraction_gt": 0.5,
        "min_distinct_parts": 4,
    },
    "floating_island_small": {
        "expects_flat_normal_fraction_gt": 0.85,
        "expects_walkable_zones_gt": 0,
        "min_distinct_parts": 3,
    },
}


@dataclass(frozen=True)
class TopologyClassReport:
    version: str
    asset_id: str
    asset_family: str
    rules_checked: int
    rules_passed: int
    compliance_score: float
    """rules_passed / rules_checked."""
    diagnostics: tuple[str, ...]


def evaluate_topology_class_compliance(
    *,
    asset_id: str,
    asset_family: str,
    topology_stats: Mapping[str, Any],
) -> TopologyClassReport:
    """Check the topology stats against the family's rule set."""
    rules = _CLASS_TOPOLOGY_RULES.get(asset_family)
    if rules is None:
        return TopologyClassReport(
            version=TOPOLOGY_CLASS_COMPLIANCE_VERSION,
            asset_id=asset_id,
            asset_family=asset_family,
            rules_checked=0,
            rules_passed=0,
            compliance_score=1.0,
            diagnostics=(f"no_rules_for_family: {asset_family!r}",),
        )
    diagnostics: list[str] = []
    passed = 0
    checked = 0
    for rule_name, threshold in rules.items():
        checked += 1
        if rule_name.startswith("expects_") and rule_name.endswith("_gt"):
            stat_name = rule_name.removeprefix("expects_").removesuffix("_gt")
            actual = topology_stats.get(stat_name)
            if isinstance(actual, (int, float)) and actual > float(threshold):
                passed += 1
            else:
                diagnostics.append(
                    f"topology_compliance_{stat_name}: actual {actual} <= threshold {threshold}"
                )
        elif rule_name.startswith("max_") and rule_name.endswith("_fraction"):
            stat_name = rule_name.removeprefix("max_")
            actual = topology_stats.get(stat_name)
            if isinstance(actual, (int, float)) and actual <= float(threshold):
                passed += 1
            else:
                diagnostics.append(
                    f"topology_compliance_{stat_name}: actual {actual} > threshold {threshold}"
                )
        elif rule_name.startswith("min_"):
            stat_name = rule_name.removeprefix("min_")
            actual = topology_stats.get(stat_name)
            if isinstance(actual, (int, float)) and actual >= float(threshold):
                passed += 1
            else:
                diagnostics.append(
                    f"topology_compliance_{stat_name}: actual {actual} < threshold {threshold}"
                )
    score = passed / max(1, checked)
    return TopologyClassReport(
        version=TOPOLOGY_CLASS_COMPLIANCE_VERSION,
        asset_id=asset_id,
        asset_family=asset_family,
        rules_checked=checked,
        rules_passed=passed,
        compliance_score=score,
        diagnostics=tuple(diagnostics),
    )


__all__ = [
    "TOPOLOGY_CLASS_COMPLIANCE_VERSION",
    "TopologyClassReport",
    "evaluate_topology_class_compliance",
]
