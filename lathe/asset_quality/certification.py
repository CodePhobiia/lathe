"""Phase 14 asset-quality example certification.

The Phase 14 certifier validates checked-in asset-quality evidence
bundles. It is deliberately filesystem- and JSON-oriented: the golden
and smoke examples are regression fixtures, not live renderer or DCC
jobs. Missing renderer or bake artifacts are allowed in warning mode
only when the fixture says so explicitly; strict mode keeps those gaps
as named blockers.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .art_direction import QUALITY_DIMENSIONS, validate_art_direction_payload
from .semantic_critique import SEMANTIC_CRITIQUE_VERSION
from .universal_quality import universal_quality_results

CERTIFICATE_VERSION = "lathe.asset_quality.certificate.v1"
GENERATED_AT = "2026-04-30T00:00:00Z"

MODE_WARNING = "warning"
MODE_STRICT = "strict"

WARNING_THRESHOLD = 70
STRICT_THRESHOLD = 90
ART_DIRECTION_WARNING_THRESHOLD = 75
ART_DIRECTION_STRICT_THRESHOLD = 90
UNIVERSAL_QUALITY_WARNING_THRESHOLD = 75
UNIVERSAL_QUALITY_STRICT_THRESHOLD = 90

_CATEGORY_ORDER: tuple[str, ...] = (
    "design_brief",
    "family_grammar",
    "construction_graph",
    "shape_detail_hierarchy",
    "high_low_relation",
    "material_wear_graph",
    "preview_evidence",
    "platform_budget",
    "determinism",
    "traceability",
)

_CATEGORY_MAX: dict[str, int] = {
    "design_brief": 10,
    "family_grammar": 15,
    "construction_graph": 15,
    "shape_detail_hierarchy": 10,
    "high_low_relation": 10,
    "material_wear_graph": 15,
    "preview_evidence": 10,
    "platform_budget": 5,
    "determinism": 5,
    "traceability": 5,
}

_ART_DIRECTION_ORDER: tuple[str, ...] = (
    "silhouette_strength",
    "proportion_quality",
    "material_separation",
    "focal_point_readability",
    "ornament_intentionality",
    "procedural_noise_penalty",
    "thumbnail_readability",
)

_ART_DIRECTION_MAX: dict[str, int] = {name: 10 for name in _ART_DIRECTION_ORDER}

_GOLDEN_REQUIRED: tuple[str, ...] = (
    "design_brief.json",
    "family_grammar_coverage.json",
    "construction_graph.json",
    "shape_ir_v2.json",
    "high_low_relation.json",
    "material_wear_graph.json",
    "reference_board.json",
    "preview_evidence.json",
    "quality_certificate.json",
    "quality_report.md",
)

_HERO_REQUIRED: tuple[str, ...] = (
    "design_brief.json",
    "silhouette_plan.json",
    "construction_graph.json",
    "material_wear_graph.json",
    "preview_evidence.json",
    "quality_certificate.json",
    "quality_report.md",
)

_SMOKE_REQUIRED: tuple[str, ...] = (
    "design_brief.json",
    "construction_graph.json",
    "family_grammar_coverage.json",
    "material_wear_graph.json",
    "preview_evidence.json",
    "quality_certificate.json",
)

_QUALITY_ENGINE_REQUIRED: tuple[str, ...] = (
    "design_brief.json",
    "art_direction.json",
    "quality_plan.json",
    "construction_graph.json",
    "family_grammar_coverage.json",
    "high_low_relation.json",
    "material_wear_graph.json",
    "preview_evidence.json",
    "semantic_critique.example.json",
    "quality_certificate.json",
    "quality_report.md",
)

_OPTIONAL_JSON_FILES: tuple[str, ...] = (
    "art_direction.json",
    "silhouette_plan.json",
    "quality_plan.json",
    "semantic_critique.example.json",
    "source_status.json",
    "family_grammar_coverage.json",
    "shape_ir_v2.json",
    "high_low_relation.json",
    "reference_board.json",
    "vision_critique.example.json",
    "patch_result.json",
    "quality_certificate.json",
)

_EXPECTED_PREVIEW_VIEWS: tuple[str, ...] = (
    "final_beauty",
    "material_ids",
    "wireframe",
    "comparison_sheet",
)

_STRICT_PREVIEW_BLOCKERS: dict[str, str] = {
    "final_beauty": "final_preview_missing",
    "material_ids": "material_ids_missing",
    "wireframe": "wireframe_missing",
    "comparison_sheet": "comparison_sheet_missing",
}


def validate_example(example_dir: str | Path, *, mode: str = MODE_WARNING) -> dict[str, Any]:
    """Validate one Phase 14 example fixture.

    Returns a stable JSON payload suitable for the CLI. ``ok`` reflects
    the requested mode: warning mode checks ``gates.warning_pass``;
    strict mode checks ``gates.strict_pass``.
    """
    certificate = certify_example(example_dir, mode=mode)
    gates = certificate["gates"]
    if mode == MODE_STRICT:
        ok = bool(gates["strict_pass"])
    elif mode == MODE_WARNING:
        ok = bool(gates["warning_pass"])
    else:
        raise ValueError(f"unsupported certification mode: {mode!r}")
    return {
        "ok": ok,
        "mode": mode,
        "example_path": str(Path(example_dir)),
        "asset_id": certificate["asset_id"],
        "status": certificate["status"],
        "score": certificate["scores"]["total"],
        "gates": gates,
        "diagnostics": certificate["diagnostics"],
        "certificate": certificate,
    }


def certify_example(example_dir: str | Path, *, mode: str = MODE_WARNING) -> dict[str, Any]:
    """Compute the deterministic Phase 14 certificate for a fixture."""
    if mode not in {MODE_WARNING, MODE_STRICT}:
        raise ValueError(f"unsupported certification mode: {mode!r}")
    path = Path(example_dir)
    bundle = _load_bundle(path)
    scores, score_notes = _score_bundle(bundle)
    diagnostics = _bundle_diagnostics(bundle)
    diagnostics.extend(_claim_diagnostics(bundle))
    universal_quality = _universal_quality_summary(bundle)
    art_direction = _art_direction_summary(bundle)
    if bundle["example_type"] == "hero" and not art_direction["gates"]["warning_pass"]:
        diagnostics.append(
            _diagnostic(
                "AQ14C1",
                "error",
                "hero art-direction score is below the Phase 14C warning threshold",
                path="silhouette_plan.json",
            )
        )
    if (
        bundle["example_type"] == "quality_engine"
        and universal_quality
        and not _as_dict(universal_quality.get("gates")).get("warning_pass")
    ):
        diagnostics.append(
            _diagnostic(
                "AQ14C2",
                "error",
                "universal quality score is below the Phase 14C warning threshold",
                path="quality_plan.json",
            )
        )

    critical_missing_artifact = any(
        diagnostic.get("severity") == "error" for diagnostic in diagnostics
    )
    total = sum(scores[name] for name in _CATEGORY_ORDER)
    warning_pass = total >= WARNING_THRESHOLD and not critical_missing_artifact
    strict_blockers = _strict_blockers(
        bundle,
        scores,
        warning_pass,
        art_direction,
        universal_quality,
    )
    strict_pass = (
        total >= STRICT_THRESHOLD
        and warning_pass
        and not strict_blockers
    )
    status = _status_for(warning_pass, strict_pass, mode)
    evidence = _evidence_map(bundle)
    claims = _claims(bundle, warning_pass, strict_pass)
    notes = _notes(bundle, score_notes)
    profile_phase = (
        "phase14c"
        if bundle["example_type"] in {"hero", "quality_engine"}
        else "phase14"
    )

    certificate = {
        "schema_version": CERTIFICATE_VERSION,
        "asset_id": bundle["asset_id"],
        "example_type": bundle["example_type"],
        "certification_profile": f"{profile_phase}_{mode}",
        "generated_at": GENERATED_AT,
        "status": status,
        "scores": {"total": total, **scores},
        "score_thresholds": {
            "warning": WARNING_THRESHOLD,
            "strict": STRICT_THRESHOLD,
            "categories": dict(_CATEGORY_MAX),
        },
        "gates": {
            "warning_pass": warning_pass,
            "strict_pass": strict_pass,
            "critical_missing_artifact": critical_missing_artifact,
            "strict_blockers": strict_blockers,
        },
        "budget": _budget_summary(bundle),
        "evidence": evidence,
        "claims": claims,
        "diagnostics": diagnostics,
        "notes": notes,
    }
    if universal_quality:
        certificate["universal_quality"] = universal_quality
    if bundle["example_type"] == "hero":
        certificate["art_direction"] = art_direction
    return certificate


def certify_to_directory(
    example_dir: str | Path,
    out_dir: str | Path,
    *,
    mode: str = MODE_WARNING,
) -> dict[str, Any]:
    """Write a certificate and Markdown report for ``example_dir`` to ``out_dir``."""
    certificate = certify_example(example_dir, mode=mode)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    certificate_path = out / "quality_certificate.json"
    report_path = out / "quality_report.md"
    certificate_path.write_text(_canonical_json(certificate), encoding="utf-8")
    report_path.write_text(render_quality_report(certificate), encoding="utf-8")
    return {
        "ok": bool(certificate["gates"]["warning_pass"])
        if mode == MODE_WARNING
        else bool(certificate["gates"]["strict_pass"]),
        "mode": mode,
        "certificate_path": str(certificate_path),
        "report_path": str(report_path),
        "certificate": certificate,
    }


def catalog_examples(root: str | Path) -> dict[str, Any]:
    """Return warning/strict status for every direct example directory."""
    root_path = Path(root)
    examples: list[dict[str, Any]] = []
    for child in sorted(root_path.iterdir() if root_path.exists() else []):
        if not child.is_dir():
            continue
        if not _is_example_fixture_dir(child):
            continue
        warning = validate_example(child, mode=MODE_WARNING)
        strict = validate_example(child, mode=MODE_STRICT)
        examples.append(
            {
                "asset_id": warning["asset_id"],
                "example_path": str(child),
                "example_type": warning["certificate"]["example_type"],
                "warning_pass": bool(warning["gates"]["warning_pass"]),
                "strict_pass": bool(strict["gates"]["strict_pass"]),
                "score": warning["score"],
                "strict_blockers": list(strict["gates"]["strict_blockers"]),
            }
        )
    return {
        "ok": all(entry["warning_pass"] for entry in examples),
        "root": str(root_path),
        "example_count": len(examples),
        "examples": examples,
    }


def write_catalog(root: str | Path, out_path: str | Path) -> dict[str, Any]:
    """Write :func:`catalog_examples` to ``out_path``."""
    catalog = catalog_examples(root)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_canonical_json(catalog), encoding="utf-8")
    return catalog


def render_quality_report(certificate: dict[str, Any]) -> str:
    """Render a deterministic Markdown report from a certificate."""
    gates = certificate["gates"]
    claims = certificate["claims"]
    evidence = certificate["evidence"]
    scores = certificate["scores"]
    strict_blockers = gates["strict_blockers"] or ["none"]
    diagnostics = certificate["diagnostics"] or [
        {"code": "AQ1400", "severity": "info", "message": "no diagnostics"}
    ]

    lines = [
        f"# Quality Report: {certificate['asset_id']}",
        "",
        "## Certification",
        "",
        f"- Profile: {certificate['certification_profile']}",
        f"- Status: {certificate['status']}",
        f"- Score: {scores['total']} / 100",
        f"- Warning pass: {str(gates['warning_pass']).lower()}",
        f"- Strict pass: {str(gates['strict_pass']).lower()}",
        "",
        "## Category Scores",
        "",
    ]
    for name in _CATEGORY_ORDER:
        lines.append(f"- {name}: {scores[name]} / {_CATEGORY_MAX[name]}")
    lines.extend(
        [
            "",
            "## Evidence",
            "",
        ]
    )
    for key, value in evidence.items():
        lines.append(f"- {key}: {value}")
    lines.extend(
        [
            "",
            "## Truthfulness",
            "",
            f"- External renderer verified: {str(claims['external_renderer_verified']).lower()}",
            f"- Real high/low bake verified: {str(claims['real_high_low_bake_verified']).lower()}",
            f"- Production-game certification claimed: {str(claims['certified_for_production_game_use']).lower()}",
            "",
            "## Strict Blockers",
            "",
        ]
    )
    for blocker in strict_blockers:
        lines.append(f"- {blocker}")
    lines.extend(
        [
            "",
            "## Diagnostics",
            "",
        ]
    )
    for diagnostic in diagnostics:
        lines.append(
            f"- {diagnostic['severity']} {diagnostic['code']}: {diagnostic['message']}"
        )
    art_direction = certificate.get("art_direction")
    universal_quality = certificate.get("universal_quality")
    if isinstance(universal_quality, dict):
        lines.extend(
            [
                "",
                "## Universal Quality",
                "",
                f"- Total: {universal_quality['scores']['total']} / 100",
                f"- Warning pass: {str(universal_quality['gates']['warning_pass']).lower()}",
                f"- Strict pass: {str(universal_quality['gates']['strict_pass']).lower()}",
            ]
        )
        for name in QUALITY_DIMENSIONS:
            lines.append(f"- {name}: {universal_quality['scores'][name]} / 10")
    if isinstance(art_direction, dict):
        lines.extend(
            [
                "",
                "## Hero Art Direction",
                "",
                f"- Total: {art_direction['scores']['total']} / 100",
                f"- Warning pass: {str(art_direction['gates']['warning_pass']).lower()}",
                f"- Strict pass: {str(art_direction['gates']['strict_pass']).lower()}",
            ]
        )
        for name in _ART_DIRECTION_ORDER:
            lines.append(f"- {name}: {art_direction['scores'][name]} / {_ART_DIRECTION_MAX[name]}")
    lines.append("")
    return "\n".join(lines)


def snapshot_stability(example_dir: str | Path) -> dict[str, Any]:
    """Return deterministic snapshot comparison details for ``example_dir``."""
    path = Path(example_dir)
    snapshot_dir = path / "snapshots"
    mapping = {
        "art_direction.snapshot.json": "art_direction.json",
        "construction_graph.snapshot.json": "construction_graph.json",
        "high_low_relation.snapshot.json": "high_low_relation.json",
        "material_wear_graph.snapshot.json": "material_wear_graph.json",
        "quality_plan.snapshot.json": "quality_plan.json",
        "semantic_critique.snapshot.json": "semantic_critique.example.json",
        "quality_certificate.snapshot.json": "quality_certificate.json",
    }
    comparisons: list[dict[str, Any]] = []
    for snapshot_name, evidence_name in mapping.items():
        snapshot_path = snapshot_dir / snapshot_name
        evidence_path = path / evidence_name
        if not snapshot_path.exists() and not evidence_path.exists():
            continue
        if not snapshot_path.exists() or not evidence_path.exists():
            comparisons.append(
                {
                    "snapshot": f"snapshots/{snapshot_name}",
                    "evidence": evidence_name,
                    "stable": False,
                    "reason": "missing_snapshot_or_evidence",
                }
            )
            continue
        try:
            snapshot_payload = _read_json(snapshot_path)
            evidence_payload = _read_json(evidence_path)
        except ValueError as exc:
            comparisons.append(
                {
                    "snapshot": f"snapshots/{snapshot_name}",
                    "evidence": evidence_name,
                    "stable": False,
                    "reason": f"malformed_json:{exc}",
                }
            )
            continue
        stable = _snapshot_matches(snapshot_payload, evidence_payload, evidence_name)
        comparisons.append(
            {
                "snapshot": f"snapshots/{snapshot_name}",
                "evidence": evidence_name,
                "stable": stable,
                "reason": None if stable else "json_mismatch",
            }
        )
    return {
        "snapshot_count": len(comparisons),
        "stable_count": sum(1 for entry in comparisons if entry["stable"]),
        "all_stable": bool(comparisons) and all(entry["stable"] for entry in comparisons),
        "comparisons": comparisons,
    }


def refresh_golden_snapshots(example_dir: str | Path) -> None:
    """Copy current golden evidence into the snapshot folder.

    This helper is intentionally tiny and deterministic; tests use it on
    temporary fixtures only. It does not run as part of certification.
    """
    path = Path(example_dir)
    snapshot_dir = path / "snapshots"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    for snapshot_name, evidence_name in {
        "art_direction.snapshot.json": "art_direction.json",
        "construction_graph.snapshot.json": "construction_graph.json",
        "high_low_relation.snapshot.json": "high_low_relation.json",
        "material_wear_graph.snapshot.json": "material_wear_graph.json",
        "quality_plan.snapshot.json": "quality_plan.json",
        "semantic_critique.snapshot.json": "semantic_critique.example.json",
        "quality_certificate.snapshot.json": "quality_certificate.json",
    }.items():
        evidence_path = path / evidence_name
        if evidence_path.exists():
            evidence_payload = _read_json(evidence_path)
            snapshot_payload = _hash_snapshot(evidence_name, evidence_payload)
            (snapshot_dir / snapshot_name).write_text(
                _canonical_json(snapshot_payload),
                encoding="utf-8",
            )


def _load_bundle(path: Path) -> dict[str, Any]:
    design_probe = _read_optional_design_probe(path)
    if path.name.startswith("golden_"):
        example_type = "golden"
        required = _GOLDEN_REQUIRED
    elif path.name.startswith("hero_"):
        example_type = "hero"
        required = _HERO_REQUIRED
    elif path.parent.name == "quality_engine" or _is_quality_engine_design(design_probe):
        example_type = "quality_engine"
        required = _QUALITY_ENGINE_REQUIRED
    else:
        example_type = "smoke"
        required = _SMOKE_REQUIRED
    json_names = tuple(dict.fromkeys((*required, *_OPTIONAL_JSON_FILES)))
    data: dict[str, Any] = {}
    malformed: list[dict[str, str]] = []
    for name in json_names:
        if not name.endswith(".json"):
            continue
        file_path = path / name
        if not file_path.exists():
            continue
        try:
            data[name] = _read_json(file_path)
        except ValueError as exc:
            malformed.append(
                {
                    "file": name,
                    "reason": str(exc),
                }
            )
    design = data.get("design_brief.json") if isinstance(data.get("design_brief.json"), dict) else {}
    asset_id = design.get("asset_id")
    if not isinstance(asset_id, str) or not asset_id:
        asset_id = path.name
    return {
        "path": path,
        "example_type": example_type,
        "asset_id": asset_id,
        "required": required,
        "data": data,
        "malformed": malformed,
        "missing": [name for name in required if not (path / name).exists()],
        "quality_report_present": (path / "quality_report.md").exists(),
        "snapshot_stability": snapshot_stability(path),
    }


def _read_optional_design_probe(path: Path) -> dict[str, Any]:
    design_path = path / "design_brief.json"
    if not design_path.exists():
        return {}
    try:
        return _read_json(design_path)
    except ValueError:
        return {}


def _is_quality_engine_design(design: dict[str, Any]) -> bool:
    asset_id = design.get("asset_id")
    tier = design.get("certification_tier")
    return (
        isinstance(asset_id, str)
        and asset_id.startswith("quality_engine_")
    ) or (
        isinstance(tier, str)
        and "universal_quality" in tier
    )


def _is_example_fixture_dir(path: Path) -> bool:
    return (path / "design_brief.json").is_file()


def _bundle_diagnostics(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    for name in bundle["missing"]:
        diagnostics.append(
            _diagnostic(
                "AQ1401",
                "error",
                f"missing required evidence file: {name}",
                path=name,
            )
        )
    for entry in bundle["malformed"]:
        diagnostics.append(
            _diagnostic(
                "AQ1402",
                "error",
                f"malformed evidence JSON: {entry['file']} ({entry['reason']})",
                path=entry["file"],
            )
        )
    if not _report_claims_trace_to_evidence(bundle):
        diagnostics.append(
            _diagnostic(
                "AQ1403",
                "error",
                "quality report or certificate evidence map is incomplete",
                path="quality_report.md",
            )
        )
    diagnostics.extend(_quality_engine_contract_diagnostics(bundle))
    return diagnostics


def _quality_engine_contract_diagnostics(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    if bundle["example_type"] != "quality_engine":
        return []
    diagnostics: list[dict[str, Any]] = []
    art_direction = _json_obj(bundle, "art_direction.json")
    if art_direction:
        for field in validate_art_direction_payload(art_direction):
            diagnostics.append(
                _diagnostic(
                    "AQ14C3",
                    "error",
                    f"malformed art-direction evidence field: {field}",
                    path=f"art_direction.json.{field}",
                )
            )
    quality_plan = _json_obj(bundle, "quality_plan.json")
    for field in (
        "source_art_direction",
        "source_family_metadata",
        "primary_secondary_tertiary",
        "silhouette_requirements",
        "proportion_requirements",
        "material_requirements",
        "detail_requirements",
        "motif_requirements",
        "surface_story_requirements",
        "certification_targets",
        "likely_failure_modes",
    ):
        if quality_plan and not quality_plan.get(field):
            diagnostics.append(
                _diagnostic(
                    "AQ14C4",
                    "error",
                    f"quality plan is missing canonical Phase 14C field: {field}",
                    path=f"quality_plan.json.{field}",
                )
            )
    critique = _json_obj(bundle, "semantic_critique.example.json")
    if critique and critique.get("schema_version") != SEMANTIC_CRITIQUE_VERSION:
        diagnostics.append(
            _diagnostic(
                "AQ14C5",
                "error",
                "semantic critique evidence has an unsupported schema_version",
                path="semantic_critique.example.json.schema_version",
            )
        )
    if critique and not (
        isinstance(critique.get("issues"), list)
        and isinstance(critique.get("summary"), dict)
    ):
        diagnostics.append(
            _diagnostic(
                "AQ14C6",
                "error",
                "semantic critique evidence must include summary and issues",
                path="semantic_critique.example.json",
            )
        )
    return diagnostics


def _claim_diagnostics(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    existing = _json_obj(bundle, "quality_certificate.json")
    if not existing:
        return []
    diagnostics: list[dict[str, Any]] = []
    claims = _as_dict(existing.get("claims"))
    high_low = _json_obj(bundle, "high_low_relation.json")
    preview = _json_obj(bundle, "preview_evidence.json")
    real_bake = high_low.get("mode") == "real_bake"
    renderer_used = bool(_as_dict(preview.get("truthfulness")).get("external_renderer_used"))
    if claims.get("certified_for_production_game_use") is True:
        diagnostics.append(
            _diagnostic(
                "AQ1404",
                "error",
                "fixture claims production-game certification; Phase 14 may not overstate readiness",
                path="quality_certificate.json.claims.certified_for_production_game_use",
            )
        )
    if claims.get("external_renderer_verified") is True and not renderer_used:
        diagnostics.append(
            _diagnostic(
                "AQ1405",
                "error",
                "external_renderer_verified is true but preview evidence does not show an external renderer",
                path="quality_certificate.json.claims.external_renderer_verified",
            )
        )
    if claims.get("real_high_low_bake_verified") is True and not real_bake:
        diagnostics.append(
            _diagnostic(
                "AQ1406",
                "error",
                "real_high_low_bake_verified is true but high_low_relation.mode is not real_bake",
                path="quality_certificate.json.claims.real_high_low_bake_verified",
            )
        )
    return diagnostics


def _score_bundle(bundle: dict[str, Any]) -> tuple[dict[str, int], list[str]]:
    scores = {
        "design_brief": _score_design_brief(bundle),
        "family_grammar": _score_family_grammar(bundle),
        "construction_graph": _score_construction_graph(bundle),
        "shape_detail_hierarchy": _score_shape_detail(bundle),
        "high_low_relation": _score_high_low(bundle),
        "material_wear_graph": _score_material_wear(bundle),
        "preview_evidence": _score_preview(bundle),
        "platform_budget": _score_platform_budget(bundle),
        "determinism": _score_determinism(bundle),
        "traceability": _score_traceability(bundle),
    }
    notes = _score_notes(bundle, scores)
    return scores, notes


def _score_design_brief(bundle: dict[str, Any]) -> int:
    brief = _json_obj(bundle, "design_brief.json")
    if not brief:
        return 0
    required = (
        "schema_version",
        "asset_id",
        "family",
        "style",
        "platform_profile",
        "required_features",
        "acceptance_goals",
    )
    present = sum(1 for key in required if brief.get(key))
    style = _as_dict(brief.get("style"))
    platform = _as_dict(brief.get("platform_profile"))
    acceptance = _as_dict(brief.get("acceptance_goals"))
    if style.get("theme") and style.get("keywords") and style.get("forbidden"):
        present += 1
    if platform.get("target") and platform.get("triangle_budget_warning"):
        present += 1
    if len(acceptance) >= 3:
        present += 1
    return min(10, present)


def _score_family_grammar(bundle: dict[str, Any]) -> int:
    grammar = _json_obj(bundle, "family_grammar_coverage.json")
    if not grammar:
        return 0
    coverage = _number(grammar.get("coverage"), 0.0)
    return min(15, max(0, round(coverage * 15)))


def _score_construction_graph(bundle: dict[str, Any]) -> int:
    graph = _json_obj(bundle, "construction_graph.json")
    if not graph:
        return 0
    if bundle["example_type"] == "hero":
        required_sets = (
            {"blade"},
            {"fuller"},
            {"tip", "blade_tip"},
            {"guard"},
            {"grip"},
            {"pommel"},
            {"material_zone"},
            {"wear_anchor"},
            {"focal_detail"},
        )
    elif bundle["example_type"] == "quality_engine":
        nodes = _as_list(graph.get("nodes"))
        categories = {
            str(entry.get("category"))
            for entry in nodes
            if isinstance(entry, dict) and entry.get("category")
        }
        score = 5 + min(6, len(categories)) + min(4, len(nodes) // 3)
        summary = _as_dict(graph.get("summary"))
        if _number(summary.get("unclassified_major_primitives"), 0.0) > 0:
            score = min(score, 9)
        return min(15, max(0, score))
    else:
        required_sets = (
            {"shell"},
            {"frame"},
            {"corner_guard"},
            {"panel"},
            {"seam"},
            {"latch", "handle"},
            {"feet", "base_contact"},
            {"material_zone"},
            {"wear_anchor"},
        )
    categories = {
        str(entry.get("category"))
        for entry in _as_list(graph.get("nodes"))
        if isinstance(entry, dict) and entry.get("category")
    }
    satisfied = sum(1 for options in required_sets if categories & options)
    score = round(15 * (satisfied / len(required_sets)))
    summary = _as_dict(graph.get("summary"))
    if _number(summary.get("unclassified_major_primitives"), 0.0) > 0:
        score = min(score, 9)
    return min(15, max(0, score))


def _score_shape_detail(bundle: dict[str, Any]) -> int:
    shape = _json_obj(bundle, "shape_ir_v2.json")
    if not shape:
        return 7 if bundle["example_type"] in {"hero", "smoke", "quality_engine"} else 0
    ops = _as_list(shape.get("ops"))
    hierarchy = _as_dict(shape.get("detail_hierarchy"))
    score = 5 + min(4, len(ops) // 3)
    if hierarchy.get("status") in {"proxy", "semantic"}:
        score += 1
    return min(10, score)


def _score_high_low(bundle: dict[str, Any]) -> int:
    high_low = _json_obj(bundle, "high_low_relation.json")
    if not high_low:
        return 6 if bundle["example_type"] in {"hero", "smoke"} else 0
    mode = high_low.get("mode")
    if mode == "real_bake":
        return 10
    if mode == "proxy_bake":
        return 6
    if mode == "deferred":
        return 3
    return 0


def _score_material_wear(bundle: dict[str, Any]) -> int:
    material = _json_obj(bundle, "material_wear_graph.json")
    if not material:
        return 0
    summary = _as_dict(material.get("graph_summary"))
    binding = _as_dict(material.get("binding_validation"))
    uniform = _as_dict(material.get("uniform_noise"))
    zones = _as_list(material.get("material_zones"))
    score = 0
    if len(zones) >= 3 or _number(summary.get("material_zone_count"), 0.0) >= 1:
        score += 4
    if _number(summary.get("wear_mask_count"), 0.0) >= 4:
        score += 4
    if binding.get("all_node_bindings_resolved") is True:
        score += 3
    if binding.get("all_edge_bindings_resolved", True) is True:
        score += 2
    if uniform.get("is_uniform_noise") is False:
        score += 2
    return min(15, score)


def _score_preview(bundle: dict[str, Any]) -> int:
    preview = _json_obj(bundle, "preview_evidence.json")
    if not preview:
        return 0
    views = _as_dict(preview.get("views"))
    if all(_preview_view_present(bundle, view) for view in _EXPECTED_PREVIEW_VIEWS):
        return 10
    statuses = [
        _as_dict(views.get(view)).get("status")
        for view in _EXPECTED_PREVIEW_VIEWS
    ]
    if all(status in {"present", "proxy", "skipped"} for status in statuses):
        blocking_warning = any(
            _as_dict(views.get(view)).get("blocking_for_warning") is True
            for view in _EXPECTED_PREVIEW_VIEWS
        )
        return 0 if blocking_warning else 7
    return 0


def _score_platform_budget(bundle: dict[str, Any]) -> int:
    brief = _json_obj(bundle, "design_brief.json")
    platform = _as_dict(brief.get("platform_profile"))
    warning_budget = platform.get("triangle_budget_warning")
    strict_budget = platform.get("triangle_budget_strict")
    if not warning_budget:
        return 0
    budget = _budget_summary(bundle)
    if budget.get("strict_within_budget") is True and strict_budget:
        return 5
    return 4 if strict_budget else 3


def _score_determinism(bundle: dict[str, Any]) -> int:
    stability = _as_dict(bundle.get("snapshot_stability"))
    if bundle["example_type"] == "smoke" and stability.get("snapshot_count", 0) == 0:
        return 4
    count = int(stability.get("snapshot_count") or 0)
    if count == 0:
        return 0
    stable = int(stability.get("stable_count") or 0)
    return min(5, round(5 * (stable / count)))


def _score_traceability(bundle: dict[str, Any]) -> int:
    cert = _json_obj(bundle, "quality_certificate.json")
    evidence = _as_dict(cert.get("evidence"))
    required = [
        name.removesuffix(".json")
        for name in bundle["required"]
        if name.endswith(".json") and name != "quality_certificate.json"
    ]
    present = sum(1 for key in required if key in evidence)
    if not required:
        return 0
    score = round(4 * (present / len(required)))
    if bundle.get("quality_report_present") or bundle["example_type"] == "smoke":
        score += 1
    return min(5, score)


def _strict_blockers(
    bundle: dict[str, Any],
    scores: dict[str, int],
    warning_pass: bool,
    art_direction: dict[str, Any] | None = None,
    universal_quality: dict[str, Any] | None = None,
) -> list[str]:
    blockers: list[str] = []
    if not warning_pass:
        blockers.append("warning_mode_not_passing")
    high_low = _json_obj(bundle, "high_low_relation.json")
    if high_low and high_low.get("mode") != "real_bake":
        blockers.append("real_bake_not_executed")
    elif not high_low and bundle["example_type"] == "golden":
        blockers.append("high_low_relation_missing")
    preview = _json_obj(bundle, "preview_evidence.json")
    views = _as_dict(preview.get("views"))
    for view, token in _STRICT_PREVIEW_BLOCKERS.items():
        entry = _as_dict(views.get(view))
        if not _preview_view_present(bundle, view) and entry.get("blocking_for_strict", True):
            blockers.append(token)
    material = _json_obj(bundle, "material_wear_graph.json")
    binding = _as_dict(material.get("binding_validation"))
    if binding and (
        binding.get("all_node_bindings_resolved") is not True
        or binding.get("all_edge_bindings_resolved", True) is not True
    ):
        blockers.append("material_wear_graph_unresolved_bindings")
    if scores["determinism"] < _CATEGORY_MAX["determinism"]:
        blockers.append("unstable_snapshot")
    if (
        bundle["example_type"] == "hero"
        and art_direction
        and not _as_dict(art_direction.get("gates")).get("strict_pass")
    ):
        blockers.append("hero_art_direction_below_strict")
    if (
        bundle["example_type"] == "quality_engine"
        and universal_quality
        and not _as_dict(universal_quality.get("gates")).get("strict_pass")
    ):
        blockers.append("universal_quality_below_strict")
    if bundle["example_type"] == "golden":
        smoke_root = bundle["path"].parent
        for child in sorted(smoke_root.glob("smoke_*")):
            try:
                smoke = certify_example(child, mode=MODE_WARNING)
            except (OSError, ValueError):
                blockers.append(f"smoke_warning_failed:{child.name}")
                continue
            if not smoke["gates"]["warning_pass"]:
                blockers.append(f"smoke_warning_failed:{child.name}")
    return sorted(dict.fromkeys(blockers))


def _claims(
    bundle: dict[str, Any], warning_pass: bool, strict_pass: bool
) -> dict[str, bool]:
    high_low = _json_obj(bundle, "high_low_relation.json")
    preview = _json_obj(bundle, "preview_evidence.json")
    renderer_used = bool(_as_dict(preview.get("truthfulness")).get("external_renderer_used"))
    real_bake = high_low.get("mode") == "real_bake"
    return {
        "certified_for_production_game_use": False,
        "certified_for_phase14_quality_upgrade": bool(warning_pass),
        "external_renderer_verified": renderer_used,
        "real_high_low_bake_verified": real_bake,
        "strict_mode_certified": bool(strict_pass),
    }


def _budget_summary(bundle: dict[str, Any]) -> dict[str, Any]:
    brief = _json_obj(bundle, "design_brief.json")
    platform = _as_dict(brief.get("platform_profile"))
    graph = _json_obj(bundle, "construction_graph.json")
    summary = _as_dict(graph.get("summary"))
    runtime_triangles = summary.get("runtime_proxy_triangle_count")
    warning_budget = platform.get("triangle_budget_warning")
    strict_budget = platform.get("triangle_budget_strict")
    warning_within = (
        isinstance(runtime_triangles, int)
        and isinstance(warning_budget, int)
        and runtime_triangles <= warning_budget
    )
    strict_within = (
        isinstance(runtime_triangles, int)
        and isinstance(strict_budget, int)
        and runtime_triangles <= strict_budget
    )
    return {
        "runtime_proxy_triangle_count": runtime_triangles,
        "triangle_budget_warning": warning_budget,
        "triangle_budget_strict": strict_budget,
        "warning_within_budget": warning_within,
        "strict_within_budget": strict_within,
    }


def _notes(bundle: dict[str, Any], score_notes: list[str]) -> list[str]:
    notes = [
        "Phase 14 warning certification proves deterministic quality-pipeline evidence, not final DCC/game-engine production readiness.",
    ]
    if bundle["example_type"] == "smoke":
        notes.append("Smoke examples validate warning-mode structure only; they are not hero-production certificates.")
    if bundle["example_type"] == "hero":
        notes.append("Hero examples validate art-direction evidence and proxy visuals; they do not claim final game-production certification.")
    if bundle["example_type"] == "quality_engine":
        notes.append("Quality-engine examples validate universal art-direction planning across families; they do not claim final game-production certification.")
    notes.extend(score_notes)
    return notes


def _universal_quality_summary(bundle: dict[str, Any]) -> dict[str, Any]:
    quality_plan = _json_obj(bundle, "quality_plan.json")
    if not quality_plan and bundle["example_type"] != "hero":
        return {}
    if quality_plan:
        results = universal_quality_results(
            quality_plan,
            construction_graph=_json_obj(bundle, "construction_graph.json"),
            material_wear_graph=_json_obj(bundle, "material_wear_graph.json"),
        )
        scores = results["scores"]
        dimensions = results["dimensions"]
        evidence = {
            "art_direction": "art_direction.json",
            "quality_plan": "quality_plan.json",
            "construction_graph": "construction_graph.json",
            "material_wear_graph": "material_wear_graph.json",
            "preview_evidence": "preview_evidence.json",
            "semantic_critique": "semantic_critique.example.json",
        }
    else:
        hero_scores = _art_direction_scores(bundle)
        scores = {
            "silhouette_strength": hero_scores["silhouette_strength"],
            "proportion_intent": hero_scores["proportion_quality"],
            "material_contrast": hero_scores["material_separation"],
            "detail_hierarchy": max(
                hero_scores["focal_point_readability"],
                hero_scores["ornament_intentionality"],
            ),
            "motif_coherence": hero_scores["ornament_intentionality"],
            "surface_storytelling": hero_scores["material_separation"],
            "functional_readability": hero_scores["focal_point_readability"],
            "style_consistency": hero_scores["thumbnail_readability"],
            "procedural_noise_penalty": hero_scores["procedural_noise_penalty"],
        }
        dimensions = {
            name: {
                "score": scores[name],
                "max_score": 10,
                "diagnostics": [],
                "repair_suggestions": [],
            }
            for name in QUALITY_DIMENSIONS
        }
        evidence = {
            "silhouette_plan": "silhouette_plan.json",
            "construction_graph": "construction_graph.json",
            "material_wear_graph": "material_wear_graph.json",
            "preview_evidence": "preview_evidence.json",
        }
    total = round(100 * (sum(scores[name] for name in QUALITY_DIMENSIONS) / (len(QUALITY_DIMENSIONS) * 10)))
    warning_pass = total >= UNIVERSAL_QUALITY_WARNING_THRESHOLD and all(
        scores[name] >= 7 for name in QUALITY_DIMENSIONS
    )
    strict_pass = total >= UNIVERSAL_QUALITY_STRICT_THRESHOLD and all(
        scores[name] >= 8 for name in QUALITY_DIMENSIONS
    )
    blockers: list[str] = []
    if not warning_pass:
        blockers.append("universal_quality_below_warning")
    if not strict_pass:
        blockers.append("universal_quality_below_strict")
    return {
        "schema_version": "lathe.asset_quality.universal_quality.v1",
        "scores": {"total": total, **scores},
        "score_thresholds": {
            "warning": UNIVERSAL_QUALITY_WARNING_THRESHOLD,
            "strict": UNIVERSAL_QUALITY_STRICT_THRESHOLD,
            "dimensions": {name: 10 for name in QUALITY_DIMENSIONS},
        },
        "dimensions": dimensions,
        "gates": {
            "warning_pass": warning_pass,
            "strict_pass": strict_pass,
            "blockers": blockers,
        },
        "evidence": evidence,
    }


def _art_direction_summary(bundle: dict[str, Any]) -> dict[str, Any]:
    if bundle["example_type"] != "hero":
        return {}
    scores = _art_direction_scores(bundle)
    raw_total = sum(scores[name] for name in _ART_DIRECTION_ORDER)
    total = round(100 * (raw_total / max(1, len(_ART_DIRECTION_ORDER) * 10)))
    warning_pass = total >= ART_DIRECTION_WARNING_THRESHOLD and all(
        scores[name] >= 7 for name in _ART_DIRECTION_ORDER
    )
    strict_pass = total >= ART_DIRECTION_STRICT_THRESHOLD and all(
        scores[name] >= 8 for name in _ART_DIRECTION_ORDER
    )
    blockers: list[str] = []
    if not warning_pass:
        blockers.append("hero_art_direction_below_warning")
    if not strict_pass:
        blockers.append("hero_art_direction_below_strict")
    return {
        "schema_version": "lathe.asset_quality.hero_art_direction.v1",
        "scores": {"total": total, **scores},
        "score_thresholds": {
            "warning": ART_DIRECTION_WARNING_THRESHOLD,
            "strict": ART_DIRECTION_STRICT_THRESHOLD,
            "dimensions": dict(_ART_DIRECTION_MAX),
        },
        "gates": {
            "warning_pass": warning_pass,
            "strict_pass": strict_pass,
            "blockers": blockers,
        },
        "evidence": {
            "silhouette_plan": "silhouette_plan.json",
            "construction_graph": "construction_graph.json",
            "material_wear_graph": "material_wear_graph.json",
            "preview_evidence": "preview_evidence.json",
        },
    }


def _art_direction_scores(bundle: dict[str, Any]) -> dict[str, int]:
    plan = _json_obj(bundle, "silhouette_plan.json")
    metrics = _as_dict(plan.get("metrics"))
    material = _json_obj(bundle, "material_wear_graph.json")
    material_summary = _as_dict(material.get("graph_summary"))
    scores = {
        "silhouette_strength": _metric_score(metrics, "silhouette_strength"),
        "proportion_quality": _metric_score(metrics, "proportion_quality"),
        "material_separation": max(
            _metric_score(metrics, "material_separation"),
            _material_separation_score(material_summary),
        ),
        "focal_point_readability": _metric_score(metrics, "focal_point_readability"),
        "ornament_intentionality": _metric_score(metrics, "ornament_intentionality"),
        "procedural_noise_penalty": _metric_score(
            metrics,
            "procedural_noise_penalty",
            invert=True,
        ),
        "thumbnail_readability": _metric_score(metrics, "thumbnail_readability"),
    }
    return {name: max(0, min(10, score)) for name, score in scores.items()}


def _metric_score(metrics: dict[str, Any], key: str, *, invert: bool = False) -> int:
    value = _number(metrics.get(key), -1.0)
    if value < 0.0:
        return 0
    value = max(0.0, min(1.0, value))
    if invert:
        value = 1.0 - value
    return round(value * 10)


def _material_separation_score(summary: dict[str, Any]) -> int:
    zone_count = int(_number(summary.get("material_zone_count"), 0.0))
    if zone_count >= 5:
        return 10
    if zone_count >= 4:
        return 9
    if zone_count >= 3:
        return 8
    return 0


def _score_notes(bundle: dict[str, Any], scores: dict[str, int]) -> list[str]:
    notes: list[str] = []
    if scores["high_low_relation"] < 9:
        notes.append("High/low evidence is proxy or deferred; real DCC baking remains outside this lane.")
    if scores["preview_evidence"] < 10:
        notes.append("Preview evidence is truthful about skipped renderer outputs.")
    if bundle["example_type"] == "golden" and scores["determinism"] == 5:
        notes.append("Golden evidence snapshots are stable against checked-in artifacts.")
    return notes


def _status_for(warning_pass: bool, strict_pass: bool, mode: str) -> str:
    if strict_pass:
        return "strict_pass"
    if warning_pass and mode == MODE_STRICT:
        return "strict_fail_warning_pass"
    if warning_pass:
        return "warning_pass_strict_fail"
    return "warning_fail"


def _evidence_map(bundle: dict[str, Any]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for name in bundle["required"]:
        path = bundle["path"] / name
        if not path.exists():
            continue
        key = name.removesuffix(".json").removesuffix(".md")
        mapping[key] = name
    for name in _OPTIONAL_JSON_FILES:
        path = bundle["path"] / name
        if path.exists():
            key = name.removesuffix(".json")
            mapping.setdefault(key, name)
    preview = _json_obj(bundle, "preview_evidence.json")
    views = _as_dict(preview.get("views"))
    for view in _EXPECTED_PREVIEW_VIEWS:
        entry = _as_dict(views.get(view))
        rel_path = entry.get("path")
        if _preview_view_present(bundle, view) and isinstance(rel_path, str):
            mapping[f"preview_{view}"] = rel_path
    return dict(sorted(mapping.items()))


def _preview_view_present(bundle: dict[str, Any], view: str) -> bool:
    preview = _json_obj(bundle, "preview_evidence.json")
    views = _as_dict(preview.get("views"))
    entry = _as_dict(views.get(view))
    if entry.get("status") != "present":
        return False
    rel_path = entry.get("path")
    if not isinstance(rel_path, str) or not rel_path:
        return False
    candidate = Path(rel_path)
    if candidate.is_absolute() or ".." in candidate.parts:
        return False
    return (bundle["path"] / candidate).is_file()


def _report_claims_trace_to_evidence(bundle: dict[str, Any]) -> bool:
    cert = _json_obj(bundle, "quality_certificate.json")
    if not cert:
        return "quality_certificate.json" in bundle["missing"]
    evidence = _as_dict(cert.get("evidence"))
    required = [
        name.removesuffix(".json").removesuffix(".md")
        for name in bundle["required"]
        if name not in {"quality_certificate.json"}
    ]
    return all(key in evidence for key in required if key != "quality_report")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(str(exc)) from exc
    if not isinstance(payload, dict):
        raise ValueError("top-level JSON value must be an object")
    return payload


def _snapshot_matches(
    snapshot_payload: dict[str, Any],
    evidence_payload: dict[str, Any],
    evidence_name: str,
) -> bool:
    if snapshot_payload == evidence_payload:
        return True
    expected = _hash_snapshot(evidence_name, evidence_payload)
    return snapshot_payload == expected


def _hash_snapshot(evidence_name: str, evidence_payload: dict[str, Any]) -> dict[str, str]:
    digest = hashlib.sha256(_canonical_json(evidence_payload).encode()).hexdigest()
    return {
        "schema_version": "lathe.asset_quality.snapshot.v1",
        "snapshot_of": evidence_name,
        "sha256": digest,
    }


def _json_obj(bundle: dict[str, Any], name: str) -> dict[str, Any]:
    value = bundle["data"].get(name)
    return value if isinstance(value, dict) else {}


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _number(value: Any, default: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    return float(value)


def _diagnostic(
    code: str,
    severity: str,
    message: str,
    *,
    path: str | None = None,
) -> dict[str, Any]:
    diagnostic: dict[str, Any] = {
        "code": code,
        "severity": severity,
        "message": message,
    }
    if path is not None:
        diagnostic["path"] = path
    return diagnostic


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


__all__ = [
    "CERTIFICATE_VERSION",
    "MODE_STRICT",
    "MODE_WARNING",
    "catalog_examples",
    "certify_example",
    "certify_to_directory",
    "refresh_golden_snapshots",
    "render_quality_report",
    "snapshot_stability",
    "validate_example",
    "write_catalog",
]
