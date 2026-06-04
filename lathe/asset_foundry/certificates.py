"""Foundry F7 — quality certificates + ladder.

Per docs/asset-quality/lathe-frontier-asset-foundry-masterplan.md §13
(asset quality ladder Level 0..7) + §20.3 (certificate families):

  Level 0 — Valid mesh
  Level 1 — Recognizable object
  Level 2 — Styled object
  Level 3 — Beautiful object
  Level 4 — Variant family
  Level 5 — Game-ready asset
  Level 6 — Scene-ready asset
  Level 7 — Hero-quality asset

This module produces an ``AssetQualityCertificate`` from a
``FoundryAsset`` + its ``RuntimeArtifactManifest``. The certificate
records the achieved ladder level plus per-dimension scores so the
.lthpkg evidence sidecar can surface them to @lathe/three.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any

from .generators._base import FoundryAsset
from .runtime_cook import RuntimeArtifactManifest

CERTIFICATE_VERSION = "lathe.asset_foundry.certificate_v1"


class QualityLadderLevel(IntEnum):
    """Asset quality ladder per masterplan §13."""

    LEVEL_0_VALID_MESH = 0
    LEVEL_1_RECOGNIZABLE = 1
    LEVEL_2_STYLED = 2
    LEVEL_3_BEAUTIFUL = 3
    LEVEL_4_VARIANT_FAMILY = 4
    LEVEL_5_GAME_READY = 5
    LEVEL_6_SCENE_READY = 6
    LEVEL_7_HERO = 7


@dataclass(frozen=True)
class AssetQualityCertificate:
    """A Foundry quality certificate per masterplan §20.3."""

    version: str
    asset_id: str
    style_pack_id: str
    achieved_level: int
    target_level: int
    """``FoundryAsset.quality_ladder_target``."""

    metrics: Mapping[str, float]
    """All in ``[0.0, 1.0]`` (higher = better).
    Dimensions per masterplan §12 + §13:
      - silhouette_readability
      - proportion_style_score
      - facet_intentionality
      - sliver_triangle_penalty (penalty: lower=better, inverted here)
      - material_palette_compliance
      - material_zone_contrast
      - semantic_socket_coverage
      - assembly_quality
      - runtime_readiness_score
      - variant_stability_score
      - style_pack_compliance
      - collision_visual_deviation_score
    """

    overall_score: float
    """Weighted aggregate in ``[0.0, 1.0]``."""

    findings: tuple[str, ...]
    repair_recommendations: tuple[str, ...]


@dataclass(frozen=True)
class CategoryAnchorReport:
    """Category-conditioned evidence that must pass before high polish."""

    rule_id: str
    score: float
    missing_evidence: tuple[str, ...]
    repair_recommendations: tuple[str, ...]


def _semantic_socket_coverage(asset: FoundryAsset) -> float:
    """Score how well the asset's semantic sockets cover its family role.

    Heuristic: families have expected socket roles per the style pack's
    composition policy. For now, score = clamp(socket_count / 2, 0, 1)
    with a bonus when the asset has at least one role matching its
    family's recommended set.
    """
    sockets = asset.spec.sockets
    if not sockets:
        return 0.0
    family = asset.spec.family
    recommended_roles: Mapping[str, frozenset[str]] = {
        "environment_piece": frozenset({"ground_anchor", "scatter_anchor_top", "crystal_glow_source", "path_endpoint", "waterfall_source", "bridge_endpoint", "player_spawn"}),
        "architecture": frozenset({"door_entry", "ground_anchor", "walkable_endpoint"}),
        "prop": frozenset({"ground_anchor", "point_light"}),
        "container": frozenset({"ground_anchor", "lid_hinge"}),
        "machine": frozenset({"ground_anchor", "interaction_point"}),
        "furniture": frozenset({"ground_anchor", "interaction_point"}),
        "weapon": frozenset({"grip_anchor", "blade_pivot"}),
    }
    rec_set = recommended_roles.get(family, frozenset())
    role_match_count = sum(1 for s in sockets if s.role in rec_set)
    coverage = role_match_count / max(1, len(rec_set))
    return min(1.0, max(0.0, coverage))


def _style_pack_compliance(asset: FoundryAsset) -> float:
    """Score how strongly the asset's material slots use style-pack tokens.

    Material classes in style_pack.py's ``material_policy`` value list
    score 1.0; off-style materials score 0.5.
    """
    style_token_whitelist = {
        "wall_plaster",
        "wall_tan",
        "roof_thatch_golden",
        "roof_ochre",
        "wood_warm_brown",
        "wood_reddish_brown",
        "window_emissive_warm",
        "lantern_emissive_warm",
        "crystal_violet_emissive",
        "crystal_magenta",
        "crystal_cyan_dim",
        "tree_teal",
        "tree_deep_green",
        "tree_olive",
        "cliff_purple",
        "cliff_lavender",
        "stone_warm_gray",
        "grass_emerald",
        "water_cyan",
        "metal_warm",
        "metal_bare",
        "rope_fiber",
        "path_dirt_compacted",
    }
    slots = asset.spec.material_slots
    if not slots:
        return 0.0
    matched = sum(1 for s in slots if s.material_class in style_token_whitelist)
    return min(1.0, matched / max(1, len(slots)))


def _material_zone_contrast(asset: FoundryAsset) -> float:
    """Score material-zone contrast (more distinct material slots = better)."""
    slots = asset.spec.material_slots
    if not slots:
        return 0.0
    distinct = len({s.material_class for s in slots})
    # 1.0 at 4+ distinct classes; linear ramp.
    return min(1.0, distinct / 4.0)


def _silhouette_readability(asset: FoundryAsset) -> float:
    """Heuristic silhouette score from bbox aspect ratio.

    A flat-square asset (proportions close to 1:1:1 cube) scores
    medium. Strong vertical or strong horizontal aspect (crystals,
    paths) scores high — those are intentional silhouettes.
    """
    (min_x, min_y, min_z), (max_x, max_y, max_z) = asset.bbox_cm
    dx = max(0.001, max_x - min_x)
    dy = max(0.001, max_y - min_y)
    dz = max(0.001, max_z - min_z)
    sizes = sorted([dx, dy, dz], reverse=True)
    aspect_max_min = sizes[0] / sizes[2]
    if aspect_max_min < 1.3:
        return 0.55  # cube-like = medium
    if aspect_max_min < 2.5:
        return 0.85
    return 1.0


def _proportion_style_score(asset: FoundryAsset) -> float:
    """Score how exaggerated the proportions are vs. naive primitives.

    The style pack favors exaggerated/intentional proportions
    (oversized roofs, tall crystals, dramatic island depth). This is
    a rough proxy via the diagnostics list — fewer proportion-style
    diagnostics fired = higher score.
    """
    diagnostics = asset.spec.diagnostics
    proportion_warnings = sum(
        1
        for d in diagnostics
        if "roof_pitch_too_shallow" in d
        or "window_count_above" in d
        or "crystal_count_below" in d
        or "underside_shard_count_low" in d
    )
    return max(0.0, 1.0 - 0.2 * proportion_warnings)


def _facet_intentionality(asset: FoundryAsset) -> float:
    """Score whether the asset uses faceted style (prism-based generators)."""
    payload = asset.spec.geometry_payload
    kind = payload.get("kind") if isinstance(payload, dict) else ""
    if kind in {"prismatic_cluster", "floating_island_small", "stacked_conical_tree"}:
        return 1.0
    if kind in {"cozy_cottage", "rope_bridge", "stone_path_segment"}:
        return 0.8
    return 0.5


def _sliver_triangle_penalty_score(asset: FoundryAsset) -> float:
    """Penalty inverted — at the spec level we have no triangulation,
    so we score 1.0 unless a generator-specific diagnostic warns."""
    if any("sliver" in d.lower() for d in asset.spec.diagnostics):
        return 0.5
    return 1.0


def _assembly_quality(asset: FoundryAsset) -> float:
    """Score the part-graph richness: a good asset is an assembly."""
    parts = len(asset.spec.semantic_parts)
    if parts <= 1:
        return 0.3
    if parts <= 3:
        return 0.7
    return 1.0


def _runtime_readiness_score(manifest: RuntimeArtifactManifest) -> float:
    """Score the runtime cook readiness."""
    score = 0.0
    if manifest.render_mesh_status == "real":
        score += 0.35
    elif manifest.render_mesh_status == "proxy":
        score += 0.15
    if manifest.lod.lod_status in {"real", "proxy"}:
        score += 0.20
    if manifest.collision.proxy_status in {"real", "unbuilt"} and (
        manifest.collision.strategy != "none"
    ):
        score += 0.15
    if manifest.nav.contributes and manifest.nav.nav_status in {"real", "proxy"}:
        score += 0.10
    if manifest.material_zone_manifest:
        score += 0.10
    if manifest.semantic_sockets:
        score += 0.10
    return min(1.0, score)


def _variant_stability_score(asset: FoundryAsset) -> float:
    """Score the deterministic-by-seed contract.

    All Foundry generators are deterministic-by-construction by
    design. Score 1.0 unless the generator emits an explicit
    nondeterminism diagnostic.
    """
    if any(
        "nondeterministic" in d.lower() or "unstable" in d.lower()
        for d in asset.spec.diagnostics
    ):
        return 0.4
    return 1.0


def _collision_visual_deviation_score(
    asset: FoundryAsset, manifest: RuntimeArtifactManifest
) -> float:
    """Score how closely collision strategy aligns with asset family.

    Compound hulls for buildings + crystals: best. Capsule for trees +
    lanterns: good. Walkable_surface_only for paths + bridges: good.
    None on something that should block: bad.
    """
    strategy = manifest.collision.strategy
    family = asset.spec.family
    expected: Mapping[str, frozenset[str]] = {
        "architecture": frozenset({"compound_hulls", "walkable_surface_only"}),
        "environment_piece": frozenset({"compound_hulls", "walkable_surface_only", "capsule"}),
        "prop": frozenset({"capsule", "box", "hull"}),
    }
    if strategy in expected.get(family, frozenset()):
        return 1.0
    if strategy == "none":
        return 0.2
    return 0.6


def _contains_token(values: tuple[str, ...], *tokens: str) -> bool:
    haystack = " ".join(values).lower()
    return any(token in haystack for token in tokens)


def _category_anchor_report(asset: FoundryAsset) -> CategoryAnchorReport:
    """Score required class evidence before aesthetic metrics can promote."""
    generator_id = asset.spec.generator_id.lower()
    asset_id = asset.asset_id.lower()
    family = asset.spec.family.lower()
    payload = asset.spec.geometry_payload
    payload_kind = str(payload.get("kind") if isinstance(payload, Mapping) else "").lower()
    parts = tuple(str(part).lower() for part in asset.spec.semantic_parts)
    material_classes = tuple(slot.material_class.lower() for slot in asset.spec.material_slots)
    socket_roles = tuple(socket.role.lower() for socket in asset.spec.sockets)

    if "violet_crystal_cluster" in {generator_id, asset_id} or payload_kind == "prismatic_cluster":
        rule_id = "class_anchor.violet_crystal_cluster_v1"
        checks = {
            "prismatic_cluster_payload": payload_kind == "prismatic_cluster",
            "primary_and_secondary_crystals": len(parts) >= 3 and _contains_token(parts, "primary_crystal"),
            "crystal_material_classes": _contains_token(material_classes, "crystal"),
            "glow_or_ground_socket": _contains_token(socket_roles, "crystal_glow_source", "ground_anchor"),
        }
    elif "door" in generator_id or "door" in asset_id or family == "door":
        rule_id = "class_anchor.door_v1"
        checks = {
            "door_or_panel_body": _contains_token(parts, "door", "panel", "body"),
            "hinge_or_access_edge": _contains_token(parts, "hinge"),
            "handle_or_latch": _contains_token(parts, "handle", "latch", "lock"),
            "material_separation": len(set(material_classes)) >= 1,
        }
    elif "crate" in generator_id or "crate" in asset_id or family in {"container", "hard_surface_prop"}:
        rule_id = "class_anchor.crate_v1"
        checks = {
            "bounded_volume": bool(parts) and _contains_token(parts, "body", "shell", "crate", "container"),
            "panel_breakup": _contains_token(parts, "panel", "side", "slat", "rib"),
            "corner_reinforcement": _contains_token(parts, "corner", "guard", "bracket", "reinforcement"),
            "access_seam": _contains_token(parts, "lid", "door", "hinge", "latch", "seam"),
            "material_separation": len(set(material_classes)) >= 2,
        }
    else:
        rule_id = "class_anchor.generic_asset_v1"
        checks = {
            "semantic_parts_present": bool(parts),
            "material_slots_present": bool(material_classes),
            "runtime_family_declared": bool(family),
        }

    missing = tuple(key for key, passed in checks.items() if not passed)
    score = (len(checks) - len(missing)) / max(1, len(checks))
    recommendations = tuple(
        f"add category anchor evidence: {key}" for key in missing
    )
    return CategoryAnchorReport(
        rule_id=rule_id,
        score=round(score, 6),
        missing_evidence=missing,
        repair_recommendations=recommendations,
    )


def _aggregate_score(metrics: Mapping[str, float]) -> float:
    """Weighted aggregate per masterplan §13 with runtime-readiness
    weighted heavily because game-readiness is the immediate target."""
    weights = {
        "silhouette_readability": 0.10,
        "proportion_style_score": 0.08,
        "facet_intentionality": 0.06,
        "sliver_triangle_penalty_score": 0.05,
        "material_palette_compliance": 0.10,
        "material_zone_contrast": 0.08,
        "semantic_socket_coverage": 0.08,
        "assembly_quality": 0.10,
        "runtime_readiness_score": 0.20,
        "variant_stability_score": 0.05,
        "style_pack_compliance": 0.07,
        "collision_visual_deviation_score": 0.03,
        "category_anchor_score": 0.12,
    }
    total_weight = sum(weights.values())
    weighted = 0.0
    for metric_name, weight in weights.items():
        weighted += weight * metrics.get(metric_name, 0.0)
    return weighted / max(1e-9, total_weight)


def quality_ladder_level_for_score(
    score: float,
    manifest: RuntimeArtifactManifest,
    asset: FoundryAsset,
    *,
    category_anchor_score: float = 1.0,
) -> int:
    """Translate an overall score + runtime evidence into a ladder level."""
    if category_anchor_score < 0.5:
        return QualityLadderLevel.LEVEL_1_RECOGNIZABLE.value
    if category_anchor_score < 0.75 and score >= 0.6:
        return QualityLadderLevel.LEVEL_3_BEAUTIFUL.value
    if score < 0.3:
        return QualityLadderLevel.LEVEL_0_VALID_MESH.value
    if score < 0.45:
        return QualityLadderLevel.LEVEL_1_RECOGNIZABLE.value
    if score < 0.6:
        return QualityLadderLevel.LEVEL_2_STYLED.value
    if score < 0.72:
        return QualityLadderLevel.LEVEL_3_BEAUTIFUL.value
    # Level 5 (game-ready) requires runtime artifacts.
    runtime_ready = (
        manifest.render_mesh_status == "real"
        and manifest.lod.lod_status in {"real", "proxy"}
        and (
            manifest.collision.strategy == "none"
            or manifest.collision.proxy_status in {"real", "unbuilt"}
        )
    )
    if score >= 0.85 and runtime_ready and asset.quality_ladder_target >= 7:
        return QualityLadderLevel.LEVEL_7_HERO.value
    if score >= 0.78 and runtime_ready and asset.quality_ladder_target >= 6:
        return QualityLadderLevel.LEVEL_6_SCENE_READY.value
    if score >= 0.72 and runtime_ready:
        return QualityLadderLevel.LEVEL_5_GAME_READY.value
    # No runtime evidence -> max Level 4 even with strong score.
    if score >= 0.72:
        return QualityLadderLevel.LEVEL_4_VARIANT_FAMILY.value
    return QualityLadderLevel.LEVEL_3_BEAUTIFUL.value


def compute_asset_certificate(
    asset: FoundryAsset,
    manifest: RuntimeArtifactManifest,
) -> AssetQualityCertificate:
    """Compute a quality certificate for a Foundry asset.

    Pure function. The metrics are deterministic heuristics; per
    masterplan §3 (no-fake-quality), every metric is grounded in the
    asset spec + runtime evidence, not invented.
    """
    metrics: dict[str, float] = {
        "silhouette_readability": _silhouette_readability(asset),
        "proportion_style_score": _proportion_style_score(asset),
        "facet_intentionality": _facet_intentionality(asset),
        "sliver_triangle_penalty_score": _sliver_triangle_penalty_score(asset),
        "material_palette_compliance": _style_pack_compliance(asset),
        "material_zone_contrast": _material_zone_contrast(asset),
        "semantic_socket_coverage": _semantic_socket_coverage(asset),
        "assembly_quality": _assembly_quality(asset),
        "runtime_readiness_score": _runtime_readiness_score(manifest),
        "variant_stability_score": _variant_stability_score(asset),
        "style_pack_compliance": _style_pack_compliance(asset),
        "collision_visual_deviation_score": _collision_visual_deviation_score(asset, manifest),
    }
    category_anchor = _category_anchor_report(asset)
    metrics["category_anchor_score"] = category_anchor.score

    overall = _aggregate_score(metrics)
    achieved = quality_ladder_level_for_score(
        overall,
        manifest,
        asset,
        category_anchor_score=category_anchor.score,
    )

    findings: list[str] = []
    recommendations: list[str] = []
    if metrics["silhouette_readability"] < 0.7:
        findings.append(
            f"silhouette_readability {metrics['silhouette_readability']:.2f} below 0.7"
        )
        recommendations.append(
            "vary bbox proportions to break the cube-like aspect ratio"
        )
    if metrics["material_zone_contrast"] < 0.5:
        findings.append(
            f"material_zone_contrast {metrics['material_zone_contrast']:.2f} below 0.5"
        )
        recommendations.append(
            "add distinct material slots (e.g. wall + roof + trim + emissive) for stronger zone separation"
        )
    if metrics["runtime_readiness_score"] < 0.5:
        findings.append(
            f"runtime_readiness_score {metrics['runtime_readiness_score']:.2f} below 0.5"
        )
        recommendations.append(
            "build render mesh + LOD chain + collision proxy before claiming game-ready"
        )
    if metrics["assembly_quality"] < 0.5:
        findings.append(
            f"assembly_quality {metrics['assembly_quality']:.2f} below 0.5; asset has too few semantic parts"
        )
        recommendations.append(
            "decompose the asset into more parts (e.g. add trim_band / fastener / decal_zone)"
        )
    if category_anchor.score < 0.75:
        findings.append(
            f"{category_anchor.rule_id} score {category_anchor.score:.2f} below 0.75; missing {list(category_anchor.missing_evidence)}"
        )
        recommendations.extend(category_anchor.repair_recommendations)
    if achieved < asset.quality_ladder_target:
        findings.append(
            f"achieved Level {achieved} below target Level {asset.quality_ladder_target}"
        )

    return AssetQualityCertificate(
        version=CERTIFICATE_VERSION,
        asset_id=asset.asset_id,
        style_pack_id=asset.spec.style_pack_id,
        achieved_level=achieved,
        target_level=asset.quality_ladder_target,
        metrics=metrics,
        overall_score=overall,
        findings=tuple(findings),
        repair_recommendations=tuple(recommendations),
    )


def certificate_to_dict(certificate: AssetQualityCertificate) -> dict[str, Any]:
    """Serialize a certificate to a JSON-compatible dict."""
    return {
        "version": certificate.version,
        "asset_id": certificate.asset_id,
        "style_pack_id": certificate.style_pack_id,
        "achieved_level": certificate.achieved_level,
        "target_level": certificate.target_level,
        "overall_score": certificate.overall_score,
        "metrics": dict(certificate.metrics),
        "findings": list(certificate.findings),
        "repair_recommendations": list(certificate.repair_recommendations),
    }


__all__ = [
    "CERTIFICATE_VERSION",
    "AssetQualityCertificate",
    "CategoryAnchorReport",
    "QualityLadderLevel",
    "certificate_to_dict",
    "compute_asset_certificate",
    "quality_ladder_level_for_score",
]
