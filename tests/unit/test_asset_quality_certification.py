"""Phase 14 tests for asset-quality certification logic."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from lathe.asset_quality.certification import (
    CERTIFICATE_VERSION,
    MODE_STRICT,
    MODE_WARNING,
    catalog_examples,
    certify_example,
    certify_to_directory,
    snapshot_stability,
    validate_example,
)
from lathe.asset_quality.preview_render import PREVIEW_ROLE_FILENAMES, generate_preview_artifacts

_REPO_ROOT = Path(__file__).resolve().parents[2]
_EXAMPLES_ROOT = _REPO_ROOT / "examples" / "asset_quality"
_GOLDEN = _EXAMPLES_ROOT / "golden_industrial_crate"
_HERO = _EXAMPLES_ROOT / "hero_sword"
_QUALITY_ENGINE = _EXAMPLES_ROOT / "quality_engine"


def _copy_fixture(src: Path, dst: Path) -> Path:
    target = dst / src.name
    shutil.copytree(src, target)
    return target


def test_golden_crate_warning_mode_passes() -> None:
    result = validate_example(_GOLDEN, mode=MODE_WARNING)

    assert result["ok"] is True
    assert result["certificate"]["schema_version"] == CERTIFICATE_VERSION
    assert result["gates"]["warning_pass"] is True
    assert result["gates"]["strict_pass"] is False
    assert result["score"] == 96


def test_golden_crate_strict_mode_only_fails_on_real_bake() -> None:
    result = validate_example(_GOLDEN, mode=MODE_STRICT)

    assert result["ok"] is False
    assert result["gates"]["warning_pass"] is True
    assert result["gates"]["strict_blockers"] == ["real_bake_not_executed"]


def test_hero_sword_warning_mode_scores_art_direction() -> None:
    result = validate_example(_HERO, mode=MODE_WARNING)

    assert result["ok"] is True
    assert result["certificate"]["example_type"] == "hero"
    assert result["score"] == 95
    art_direction = result["certificate"]["art_direction"]
    assert art_direction["scores"]["total"] == 91
    assert art_direction["gates"]["warning_pass"] is True
    assert art_direction["gates"]["strict_pass"] is True
    assert set(art_direction["scores"]) >= {
        "silhouette_strength",
        "proportion_quality",
        "material_separation",
        "focal_point_readability",
        "ornament_intentionality",
        "procedural_noise_penalty",
        "thumbnail_readability",
    }
    universal = result["certificate"]["universal_quality"]
    assert universal["gates"]["warning_pass"] is True
    assert universal["gates"]["strict_pass"] is True


def test_hero_sword_strict_mode_only_fails_on_real_bake() -> None:
    result = validate_example(_HERO, mode=MODE_STRICT)

    assert result["ok"] is False
    assert result["gates"]["warning_pass"] is True
    assert result["gates"]["strict_blockers"] == ["real_bake_not_executed"]


def test_missing_design_brief_is_critical(tmp_path: Path) -> None:
    fixture = _copy_fixture(_GOLDEN, tmp_path)
    (fixture / "design_brief.json").unlink()

    result = validate_example(fixture, mode=MODE_WARNING)

    assert result["ok"] is False
    assert result["gates"]["critical_missing_artifact"] is True
    assert any(diagnostic["path"] == "design_brief.json" for diagnostic in result["diagnostics"])


def test_missing_material_wear_graph_is_critical(tmp_path: Path) -> None:
    fixture = _copy_fixture(_GOLDEN, tmp_path)
    (fixture / "material_wear_graph.json").unlink()

    result = validate_example(fixture, mode=MODE_WARNING)

    assert result["ok"] is False
    assert result["gates"]["critical_missing_artifact"] is True
    assert any(diagnostic["path"] == "material_wear_graph.json" for diagnostic in result["diagnostics"])


def test_missing_hero_silhouette_plan_is_critical(tmp_path: Path) -> None:
    fixture = _copy_fixture(_HERO, tmp_path)
    (fixture / "silhouette_plan.json").unlink()

    result = validate_example(fixture, mode=MODE_WARNING)

    assert result["ok"] is False
    assert result["gates"]["critical_missing_artifact"] is True
    assert any(diagnostic["path"] == "silhouette_plan.json" for diagnostic in result["diagnostics"])


def test_proxy_previews_are_warning_allowed_and_not_renderer_claims() -> None:
    warning = validate_example(_GOLDEN, mode=MODE_WARNING)
    strict = validate_example(_GOLDEN, mode=MODE_STRICT)

    assert warning["ok"] is True
    assert "final_preview_missing" not in strict["gates"]["strict_blockers"]
    assert strict["certificate"]["claims"]["external_renderer_verified"] is False


def test_missing_preview_file_reintroduces_matching_strict_blocker(tmp_path: Path) -> None:
    fixture = _copy_fixture(_GOLDEN, tmp_path)
    (fixture / "previews" / "final_beauty.png").unlink()

    result = validate_example(fixture, mode=MODE_STRICT)

    assert result["ok"] is False
    assert "final_preview_missing" in result["gates"]["strict_blockers"]
    assert "material_ids_missing" not in result["gates"]["strict_blockers"]


def test_preview_generator_outputs_deterministic_proxy_artifacts(tmp_path: Path) -> None:
    fixture = _copy_fixture(_GOLDEN, tmp_path)

    first = generate_preview_artifacts(fixture)
    second = generate_preview_artifacts(fixture)

    assert first["artifacts"] == second["artifacts"]
    assert [entry["role"] for entry in first["artifacts"]] == list(PREVIEW_ROLE_FILENAMES)
    for entry in first["artifacts"]:
        image = fixture / entry["path"]
        assert image.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def test_unsupported_claims_are_rejected(tmp_path: Path) -> None:
    fixture = _copy_fixture(_GOLDEN, tmp_path)
    certificate_path = fixture / "quality_certificate.json"
    certificate = json.loads(certificate_path.read_text(encoding="utf-8"))
    certificate["claims"]["external_renderer_verified"] = True
    certificate_path.write_text(json.dumps(certificate, indent=2, sort_keys=True), encoding="utf-8")

    result = validate_example(fixture, mode=MODE_WARNING)

    assert result["ok"] is False
    assert any(diagnostic["code"] == "AQ1405" for diagnostic in result["diagnostics"])


def test_snapshot_stability_uses_checked_in_hashes() -> None:
    stability = snapshot_stability(_GOLDEN)

    assert stability["snapshot_count"] == 4
    assert stability["all_stable"] is True


def test_certify_to_directory_writes_certificate_and_report(tmp_path: Path) -> None:
    out = tmp_path / "cert"

    payload = certify_to_directory(_GOLDEN, out, mode=MODE_WARNING)

    assert payload["ok"] is True
    assert (out / "quality_certificate.json").exists()
    assert (out / "quality_report.md").exists()
    written = json.loads((out / "quality_certificate.json").read_text(encoding="utf-8"))
    assert written["asset_id"] == "golden_industrial_crate"


def test_existing_certificate_does_not_claim_production_readiness() -> None:
    certificate = certify_example(_GOLDEN, mode=MODE_WARNING)

    assert certificate["claims"]["certified_for_production_game_use"] is False
    assert certificate["claims"]["real_high_low_bake_verified"] is False
    assert certificate["claims"]["external_renderer_verified"] is False


def test_quality_engine_fixtures_pass_warning_and_keep_truthful_strict_blocker() -> None:
    fixture_names = [
        "environment_shop_counter",
        "fantasy_weapon",
        "roblox_tycoon_machine",
        "sci_fi_crate",
    ]

    for fixture_name in fixture_names:
        fixture = _QUALITY_ENGINE / fixture_name
        warning = validate_example(fixture, mode=MODE_WARNING)
        strict = validate_example(fixture, mode=MODE_STRICT)

        assert warning["ok"] is True
        assert warning["certificate"]["example_type"] == "quality_engine"
        assert warning["certificate"]["universal_quality"]["gates"]["strict_pass"] is True
        assert strict["ok"] is False
        assert strict["gates"]["strict_blockers"] == ["real_bake_not_executed"]
        assert strict["certificate"]["claims"]["external_renderer_verified"] is False
        assert strict["certificate"]["claims"]["real_high_low_bake_verified"] is False
        assert strict["certificate"]["claims"]["certified_for_production_game_use"] is False


def test_missing_quality_plan_is_critical_for_quality_engine_fixture(tmp_path: Path) -> None:
    fixture = _copy_fixture(_QUALITY_ENGINE / "fantasy_weapon", tmp_path)
    (fixture / "quality_plan.json").unlink()

    result = validate_example(fixture, mode=MODE_WARNING)

    assert result["ok"] is False
    assert result["gates"]["critical_missing_artifact"] is True
    assert any(diagnostic["path"] == "quality_plan.json" for diagnostic in result["diagnostics"])


def test_missing_art_direction_is_critical_for_quality_engine_fixture(tmp_path: Path) -> None:
    fixture = _copy_fixture(_QUALITY_ENGINE / "fantasy_weapon", tmp_path)
    (fixture / "art_direction.json").unlink()

    result = validate_example(fixture, mode=MODE_WARNING)

    assert result["ok"] is False
    assert result["gates"]["critical_missing_artifact"] is True
    assert any(diagnostic["path"] == "art_direction.json" for diagnostic in result["diagnostics"])


def test_missing_semantic_critique_is_critical_for_quality_engine_fixture(tmp_path: Path) -> None:
    fixture = _copy_fixture(_QUALITY_ENGINE / "fantasy_weapon", tmp_path)
    (fixture / "semantic_critique.example.json").unlink()

    result = validate_example(fixture, mode=MODE_WARNING)

    assert result["ok"] is False
    assert result["gates"]["critical_missing_artifact"] is True
    assert any(
        diagnostic["path"] == "semantic_critique.example.json"
        for diagnostic in result["diagnostics"]
    )


def test_malformed_art_direction_is_critical_for_quality_engine_fixture(tmp_path: Path) -> None:
    fixture = _copy_fixture(_QUALITY_ENGINE / "fantasy_weapon", tmp_path)
    art_direction_path = fixture / "art_direction.json"
    art_direction = json.loads(art_direction_path.read_text(encoding="utf-8"))
    art_direction.pop("style_intent")
    art_direction_path.write_text(json.dumps(art_direction, indent=2, sort_keys=True), encoding="utf-8")

    result = validate_example(fixture, mode=MODE_WARNING)

    assert result["ok"] is False
    assert any(diagnostic["path"] == "art_direction.json.style_intent" for diagnostic in result["diagnostics"])


def test_catalog_examples_reports_all_phase14_fixtures() -> None:
    catalog = catalog_examples(_EXAMPLES_ROOT)

    assert catalog["ok"] is True
    assert catalog["example_count"] == 5
    assert {entry["asset_id"] for entry in catalog["examples"]} == {
        "golden_industrial_crate",
        "hero_sword",
        "smoke_mechanical_door",
        "smoke_service_cabinet",
        "smoke_terminal_or_supply_chest",
    }


def test_catalog_examples_reports_quality_engine_children() -> None:
    catalog = catalog_examples(_QUALITY_ENGINE)

    assert catalog["ok"] is True
    assert catalog["example_count"] == 4
    assert {entry["example_type"] for entry in catalog["examples"]} == {"quality_engine"}
    assert {entry["asset_id"] for entry in catalog["examples"]} == {
        "quality_engine_environment_shop_counter",
        "quality_engine_fantasy_weapon",
        "quality_engine_roblox_tycoon_machine",
        "quality_engine_sci_fi_crate",
    }
