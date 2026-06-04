"""World-level certificate aggregation for `.lthworld` packages."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from ..forge import WorldComposition
from .validators.style_stack_compatibility import evaluate_style_stack_compatibility

WORLD_CERTIFICATE_VERSION = "lathe.asset_foundry.world_certificate_v1"


@dataclass(frozen=True)
class WorldCertificate:
    version: str
    world_id: str
    target_level: int
    achieved_level: int
    certified: bool
    metrics: Mapping[str, float]
    findings: tuple[Mapping[str, Any], ...]
    repair_recommendations: tuple[str, ...]
    style_compatibility: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "world_id": self.world_id,
            "target_level": self.target_level,
            "achieved_level": self.achieved_level,
            "certified": self.certified,
            "metrics": dict(self.metrics),
            "findings": [dict(f) for f in self.findings],
            "repair_recommendations": list(self.repair_recommendations),
            "style_compatibility": dict(self.style_compatibility),
        }


def evaluate_world_style_compatibility(composition: WorldComposition) -> dict[str, Any]:
    report = evaluate_style_stack_compatibility(
        asset_id=composition.world_id,
        declared_style_packs=composition.style_pack_ids(),
    )
    per_asset = [
        {
            "world_asset_id": asset.world_asset_id,
            "style_pack_id": asset.style_pack_id,
            "compatible": asset.style_pack_id == composition.style.style_pack_id,
        }
        for asset in composition.assets
    ]
    return {
        "version": report.version,
        "world_id": composition.world_id,
        "compatible": report.compatible and all(item["compatible"] for item in per_asset),
        "declared_style_packs": list(report.declared_style_packs),
        "declared_bands": list(report.declared_bands),
        "incompatible_pairs": [list(pair) for pair in report.incompatible_pairs],
        "diagnostics": list(report.diagnostics),
        "per_asset": per_asset,
    }


def compute_world_certificate(
    composition: WorldComposition,
    *,
    asset_links: Mapping[str, Mapping[str, str]],
    traversal_evidence: Mapping[str, Any],
    minimap_evidence: Mapping[str, Any],
    engine_import_status: str,
    hero_render_status: str,
    wonder_critique_status: str = "not_verified",
) -> WorldCertificate:
    """Aggregate current world readiness without overstating final quality."""

    style_report = evaluate_world_style_compatibility(composition)
    linked_count = sum(1 for link in asset_links.values() if link.get("status") == "linked")
    real_render_mesh_count = sum(
        1
        for link in asset_links.values()
        if link.get("status") == "linked" and link.get("render_mesh_status") == "real"
    )
    asset_package_score = linked_count / max(1, composition.asset_count())
    render_mesh_score = real_render_mesh_count / max(1, composition.asset_count())
    style_score = 1.0 if style_report["compatible"] else 0.0
    traversal_score = 1.0 if traversal_evidence.get("nav_status") == "real" else 0.0
    collision_score = 1.0 if traversal_evidence.get("collision_status") == "real" else 0.0
    minimap_score = 1.0 if minimap_evidence.get("status") == "real" else 0.0
    import_score = 1.0 if engine_import_status in {"imported", "validated", "validated_proxy"} else 0.0
    hero_score = 1.0 if hero_render_status == "real" else 0.0
    wonder_score = 1.0 if wonder_critique_status == "real" else 0.0
    metrics = {
        "inventory_completeness": 1.0 if composition.asset_count() > 0 else 0.0,
        "asset_package_completeness": round(asset_package_score, 4),
        "member_render_mesh_evidence": round(render_mesh_score, 4),
        "style_compatibility": style_score,
        "traversal_readiness": traversal_score,
        "collision_readiness": collision_score,
        "minimap_evidence": minimap_score,
        "hero_render_evidence": hero_score,
        "wonder_repair_evidence": wonder_score,
        "engine_import_evidence": import_score,
        "signature_evidence": 1.0,
    }

    findings: list[Mapping[str, Any]] = []
    recommendations: list[str] = []
    if asset_package_score < 1.0:
        findings.append(
            {
                "code": "SV5001",
                "severity": "blocking",
                "claim_level": "not_verified",
                "message": "not every world member has a linked .lthpkg package",
            }
        )
        recommendations.append("package_each_world_member")
    if render_mesh_score < 1.0:
        findings.append(
            {
                "code": "SV5007",
                "severity": "blocking",
                "claim_level": "not_verified",
                "message": "not every linked world member has real render mesh evidence",
            }
        )
        recommendations.append("build_visible_mesh_glb_for_each_world_member")
    if not style_report["compatible"]:
        findings.append(
            {
                "code": "SV5002",
                "severity": "blocking",
                "claim_level": "unsupported",
                "message": "world contains incompatible style packs",
            }
        )
        recommendations.append("replace_or_restyle_incompatible_members")
    if traversal_score < 1.0 or collision_score < 1.0:
        findings.append(
            {
                "code": "SV5003",
                "severity": "blocking",
                "claim_level": "not_verified",
                "message": "traversal or collision evidence is missing",
            }
        )
        recommendations.append("extract_world_traversal_and_collision_evidence")
    if hero_score < 1.0:
        findings.append(
            {
                "code": "SV5004",
                "severity": "blocking",
                "claim_level": "not_verified",
                "message": "hero_sunset.png has not been generated",
            }
        )
        recommendations.append("render_hero_sunset_png")
    if import_score < 1.0:
        findings.append(
            {
                "code": "SV5005",
                "severity": "blocking",
                "claim_level": "not_verified",
                "message": "no real engine import or validator evidence exists",
            }
        )
        recommendations.append("capture_engine_or_validator_import_evidence")
    if wonder_score < 1.0:
        findings.append(
            {
                "code": "SV5006",
                "severity": "blocking",
                "claim_level": "not_verified",
                "message": "no rendered-pixel Wonder critique and repair evidence exists",
            }
        )
        recommendations.append("run_wonder_pixel_critique_repair_round")

    if not findings and all(value >= 1.0 for value in metrics.values()):
        achieved = 6
    elif (
        asset_package_score >= 1.0
        and render_mesh_score >= 1.0
        and style_score >= 1.0
        and traversal_score >= 1.0
        and minimap_score >= 1.0
        and wonder_score >= 1.0
    ):
        achieved = 5
    elif asset_package_score >= 1.0 and style_score >= 1.0:
        achieved = 4
    elif composition.asset_count() > 0:
        achieved = 2
    else:
        achieved = 0

    return WorldCertificate(
        version=WORLD_CERTIFICATE_VERSION,
        world_id=composition.world_id,
        target_level=6,
        achieved_level=achieved,
        certified=achieved >= 6 and not findings,
        metrics=metrics,
        findings=tuple(findings),
        repair_recommendations=tuple(recommendations),
        style_compatibility=style_report,
    )


__all__ = [
    "WORLD_CERTIFICATE_VERSION",
    "WorldCertificate",
    "compute_world_certificate",
    "evaluate_world_style_compatibility",
]
