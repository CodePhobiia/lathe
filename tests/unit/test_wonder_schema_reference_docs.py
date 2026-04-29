from __future__ import annotations

from pathlib import Path

from scripts.generate_wonder_schema_reference import (
    OUTPUT_PATH,
    ROOT,
    render_wonder_schema_reference,
)


def test_wonder_schema_reference_is_generated_from_current_schemas() -> None:
    expected = render_wonder_schema_reference()
    actual = Path(OUTPUT_PATH).read_text(encoding="utf-8")

    assert actual == expected


def test_wonder_schema_reference_uses_repo_relative_schema_paths() -> None:
    expected = render_wonder_schema_reference()

    assert str(ROOT) not in expected
    assert ROOT.as_posix() not in expected
    assert "schema/dream_brief.schema.json" in expected
    assert "schema/scene_graph.schema.json" in expected
    assert "schema/scene_patch.schema.json" in expected
    assert "schema/render_inspection.schema.json" in expected
    assert "schema/world_memory.schema.json" in expected
    assert "schema/scene_manifest.schema.json" in expected
    assert "schema/wonder_report.schema.json" in expected
    assert "schema/scene_package_manifest.schema.json" in expected
    assert "schema/scene_plan.schema.json" in expected
    assert "schema/scene_quality_report.schema.json" in expected
