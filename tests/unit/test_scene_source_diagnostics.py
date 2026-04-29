from __future__ import annotations

import json
from pathlib import Path

from lathe.scene.source import source_to_scene_graph
from lathe.scene.source_diagnostics import source_span_for_json_pointer

REPO_ROOT = Path(__file__).resolve().parents[2]
BAD_OUTPUTS = REPO_ROOT / "docs" / "llm" / "bad_outputs"
BAD_SOURCE = BAD_OUTPUTS / "invalid_scene_source_bad_id.lth"


def _expected(name: str) -> dict:
    return json.loads((BAD_OUTPUTS / name).read_text(encoding="utf-8"))


def test_invalid_scene_source_bad_id_fixture_emits_source_span_and_repair_hint() -> None:
    source_text = BAD_SOURCE.read_text(encoding="utf-8")

    _scene_graph, diagnostics = source_to_scene_graph(
        source_text,
        root=BAD_SOURCE.parent,
        source_path=BAD_SOURCE,
    )

    expected = _expected("invalid_scene_source_bad_id.expected_diagnostics.json")
    expected_codes = {diagnostic["code"] for diagnostic in expected["diagnostics"]}
    assert expected_codes.issubset({diagnostic["code"] for diagnostic in diagnostics})
    invalid_id = next(diagnostic for diagnostic in diagnostics if diagnostic["path"] == "/objects/0/object_id")
    assert invalid_id["code"] == "WONDER_SCHEMA_VALIDATION"
    assert invalid_id["source_span"]["file"].endswith("invalid_scene_source_bad_id.lth")
    assert invalid_id["source_span"]["line"] >= 1
    assert invalid_id["source_span"]["column"] >= 1
    assert "stable ID" in invalid_id["repair_hint"]


def test_source_span_mapper_truthfully_maps_embedded_json_pointer() -> None:
    source_text = BAD_SOURCE.read_text(encoding="utf-8")

    span = source_span_for_json_pointer(
        source_text,
        "/objects/0/object_id",
        source_path=BAD_SOURCE,
    )

    assert span is not None
    source_line = source_text.splitlines()[span["line"] - 1]
    assert '"object_id": "bad object id"' in source_line
    assert span["file"].endswith("invalid_scene_source_bad_id.lth")
