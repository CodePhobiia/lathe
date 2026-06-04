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

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

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


@dataclass(frozen=True)
class CategoryAnchorComplianceReport:
    version: str
    asset_id: str
    asset_family: str
    anchor_rule_id: str
    evidence_checked: int
    evidence_passed: int
    compliance_score: float
    missing_evidence: tuple[str, ...]
    repair_recommendations: tuple[str, ...]


_CATEGORY_ANCHOR_RULES: Mapping[str, Mapping[str, Any]] = {
    "industrial_crate": {
        "required_part_tokens": ("body", "panel", "corner", "lid", "latch"),
        "min_material_classes": 2,
    },
    "mechanical_door": {
        "required_part_tokens": ("door", "hinge", "handle", "panel"),
        "min_material_classes": 1,
    },
    "violet_crystal_cluster": {
        "required_part_tokens": ("primary_crystal", "secondary_crystal"),
        "required_payload_kind": "prismatic_cluster",
        "required_material_tokens": ("crystal",),
        "min_material_classes": 2,
    },
}


def _category_anchor_rule_key(
    *,
    asset_id: str,
    asset_family: str,
    geometry_payload_kind: str,
) -> str:
    asset_id_l = asset_id.lower()
    family_l = asset_family.lower()
    payload_l = geometry_payload_kind.lower()
    if payload_l == "prismatic_cluster" or "violet_crystal_cluster" in asset_id_l:
        return "violet_crystal_cluster"
    if "door" in asset_id_l or family_l == "door":
        return "mechanical_door"
    if (
        "crate" in asset_id_l
        or "container" in asset_id_l
        or family_l in {"container", "hard_surface_prop"}
    ):
        return "industrial_crate"
    return family_l


def _has_token(values: Sequence[str], token: str) -> bool:
    token = token.lower()
    return any(token in value.lower() for value in values)


def evaluate_category_anchor_compliance(
    *,
    asset_id: str,
    asset_family: str,
    semantic_parts: Sequence[str],
    material_classes: Sequence[str],
    geometry_payload_kind: str = "",
) -> CategoryAnchorComplianceReport:
    """Check class evidence before aesthetic/topology polish can promote."""
    rule_key = _category_anchor_rule_key(
        asset_id=asset_id,
        asset_family=asset_family,
        geometry_payload_kind=geometry_payload_kind,
    )
    rules = _CATEGORY_ANCHOR_RULES.get(rule_key)
    if rules is None:
        rules = {
            "required_part_tokens": (),
            "min_material_classes": 1,
        }
    missing: list[str] = []
    checked = 0
    passed = 0
    for token in rules.get("required_part_tokens", ()):
        checked += 1
        if _has_token(semantic_parts, str(token)):
            passed += 1
        else:
            missing.append(f"part_token:{token}")
    required_payload_kind = rules.get("required_payload_kind")
    if required_payload_kind:
        checked += 1
        if geometry_payload_kind == required_payload_kind:
            passed += 1
        else:
            missing.append(f"geometry_payload_kind:{required_payload_kind}")
    for token in rules.get("required_material_tokens", ()):
        checked += 1
        if _has_token(material_classes, str(token)):
            passed += 1
        else:
            missing.append(f"material_token:{token}")
    min_material_classes = int(rules.get("min_material_classes", 0))
    if min_material_classes:
        checked += 1
        if len(set(material_classes)) >= min_material_classes:
            passed += 1
        else:
            missing.append(f"material_class_count>={min_material_classes}")
    score = passed / max(1, checked)
    return CategoryAnchorComplianceReport(
        version=TOPOLOGY_CLASS_COMPLIANCE_VERSION,
        asset_id=asset_id,
        asset_family=asset_family,
        anchor_rule_id=f"class_anchor.{rule_key or 'generic'}_v1",
        evidence_checked=checked,
        evidence_passed=passed,
        compliance_score=round(score, 6),
        missing_evidence=tuple(missing),
        repair_recommendations=tuple(
            f"add category anchor evidence: {item}" for item in missing
        ),
    )


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
    "CategoryAnchorComplianceReport",
    "TopologyClassReport",
    "evaluate_category_anchor_compliance",
    "evaluate_topology_class_compliance",
]
