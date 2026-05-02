"""Phase 14 fixture-level tests for golden and smoke examples."""

from __future__ import annotations

from pathlib import Path

from lathe.asset_quality.certification import MODE_WARNING, certify_example, validate_example

_REPO_ROOT = Path(__file__).resolve().parents[2]
_EXAMPLES_ROOT = _REPO_ROOT / "examples" / "asset_quality"
_QUALITY_ENGINE = _EXAMPLES_ROOT / "quality_engine"


def test_golden_fixture_contains_required_evidence_artifacts() -> None:
    golden = _EXAMPLES_ROOT / "golden_industrial_crate"

    for name in (
        "design_brief.json",
        "construction_graph.json",
        "family_grammar_coverage.json",
        "shape_ir_v2.json",
        "high_low_relation.json",
        "material_wear_graph.json",
        "reference_board.json",
        "preview_evidence.json",
        "vision_critique.example.json",
        "quality_certificate.json",
        "quality_report.md",
        "previews/final_beauty.png",
        "previews/material_ids.png",
        "previews/wireframe.png",
        "previews/comparison_sheet.png",
        "snapshots/construction_graph.snapshot.json",
        "snapshots/high_low_relation.snapshot.json",
        "snapshots/material_wear_graph.snapshot.json",
        "snapshots/quality_certificate.snapshot.json",
    ):
        assert (golden / name).exists(), name


def test_golden_highlow_and_preview_truthfulness() -> None:
    certificate = certify_example(_EXAMPLES_ROOT / "golden_industrial_crate")

    assert certificate["gates"]["warning_pass"] is True
    assert certificate["claims"]["real_high_low_bake_verified"] is False
    assert certificate["claims"]["external_renderer_verified"] is False
    assert certificate["gates"]["strict_blockers"] == ["real_bake_not_executed"]


def test_hero_sword_fixture_contains_art_direction_evidence() -> None:
    hero = _EXAMPLES_ROOT / "hero_sword"

    for name in (
        "design_brief.json",
        "silhouette_plan.json",
        "construction_graph.json",
        "family_grammar_coverage.json",
        "shape_ir_v2.json",
        "high_low_relation.json",
        "material_wear_graph.json",
        "preview_evidence.json",
        "quality_certificate.json",
        "quality_report.md",
        "previews/final_beauty.png",
        "previews/material_ids.png",
        "previews/wireframe.png",
        "previews/comparison_sheet.png",
        "snapshots/construction_graph.snapshot.json",
        "snapshots/high_low_relation.snapshot.json",
        "snapshots/material_wear_graph.snapshot.json",
        "snapshots/quality_certificate.snapshot.json",
    ):
        assert (hero / name).exists(), name


def test_hero_sword_art_direction_truthfulness() -> None:
    certificate = certify_example(_EXAMPLES_ROOT / "hero_sword")

    assert certificate["gates"]["warning_pass"] is True
    assert certificate["claims"]["real_high_low_bake_verified"] is False
    assert certificate["claims"]["external_renderer_verified"] is False
    assert certificate["art_direction"]["gates"]["strict_pass"] is True
    assert certificate["gates"]["strict_blockers"] == ["real_bake_not_executed"]


def test_quality_engine_fixtures_contain_universal_quality_evidence() -> None:
    for fixture in sorted(_QUALITY_ENGINE.iterdir()):
        if not fixture.is_dir():
            continue
        for name in (
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
            "previews/final_beauty.png",
            "previews/material_ids.png",
            "previews/wireframe.png",
            "previews/comparison_sheet.png",
            "snapshots/art_direction.snapshot.json",
            "snapshots/construction_graph.snapshot.json",
            "snapshots/high_low_relation.snapshot.json",
            "snapshots/material_wear_graph.snapshot.json",
            "snapshots/quality_plan.snapshot.json",
            "snapshots/semantic_critique.snapshot.json",
            "snapshots/quality_certificate.snapshot.json",
        ):
            assert (fixture / name).exists(), f"{fixture.name}/{name}"

        certificate = certify_example(fixture)
        assert certificate["example_type"] == "quality_engine"
        assert certificate["gates"]["warning_pass"] is True
        assert certificate["universal_quality"]["gates"]["strict_pass"] is True
        assert certificate["claims"]["external_renderer_verified"] is False
        assert certificate["claims"]["real_high_low_bake_verified"] is False
        assert certificate["claims"]["certified_for_production_game_use"] is False


def test_all_smoke_examples_pass_warning_mode() -> None:
    smoke_dirs = sorted(_EXAMPLES_ROOT.glob("smoke_*"))

    assert [path.name for path in smoke_dirs] == [
        "smoke_mechanical_door",
        "smoke_service_cabinet",
        "smoke_terminal_or_supply_chest",
    ]
    for path in smoke_dirs:
        result = validate_example(path, mode=MODE_WARNING)
        assert result["ok"] is True, path
        assert result["gates"]["warning_pass"] is True
        assert result["certificate"]["example_type"] == "smoke"


def test_phase14_certificate_is_deterministic() -> None:
    golden = _EXAMPLES_ROOT / "golden_industrial_crate"
    hero = _EXAMPLES_ROOT / "hero_sword"

    first = certify_example(golden)
    second = certify_example(golden)
    hero_first = certify_example(hero)
    hero_second = certify_example(hero)

    assert first == second
    assert hero_first == hero_second
