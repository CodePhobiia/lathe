from __future__ import annotations

import copy
import json
from pathlib import Path

from lathe.scene.validators import run_scene_validators, validate_scene_quality
from lathe.wonder import validate_contract

REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_SCENE = REPO_ROOT / "examples" / "wonder" / "alchemist_observatory" / "scene_graph.json"


def _scene() -> dict:
    return json.loads(EXAMPLE_SCENE.read_text(encoding="utf-8"))


def _codes(diagnostics: list[dict]) -> set[str]:
    return {diagnostic["code"] for diagnostic in diagnostics}


def test_scene_quality_report_accepts_alchemist_observatory() -> None:
    report = run_scene_validators(_scene(), root=EXAMPLE_SCENE.parent)

    assert report["schema_version"] == "lathe.scene_quality_report.v1"
    assert report["scene_id"] == "alchemist_observatory"
    assert report["status"] == "passed"
    assert report["score"] == 100
    assert report["human_summary"] == {
        "headline": "Scene Quality: 100/100 (passed)",
        "strengths": [
            "spatial passed",
            "semantic passed",
            "style passed",
            "composition passed",
            "curiosity passed",
            "continuity passed",
        ],
        "needs_work": ["No blocking scene-quality issues found."],
    }
    assert report["diagnostics"] == []
    assert validate_contract("scene_quality_report", report) == []


def test_scene_quality_reports_spatial_and_composition_problems() -> None:
    scene_graph = _scene()
    scene_graph["objects"][0]["transform"]["position"] = [99, 0, -1]
    scene_graph["layout"]["focal_point"] = "obj_missing_001"
    scene_graph["cameras"] = []

    report = run_scene_validators(scene_graph, root=EXAMPLE_SCENE.parent)

    assert report["status"] == "failed"
    assert {"SV1001", "SV1002", "SV4002", "SV4003"} <= _codes(report["diagnostics"])
    assert report["score"] < 100
    assert report["human_summary"]["headline"] == f"Scene Quality: {report['score']}/100 (failed)"
    assert any(item.startswith("SV1001:") for item in report["human_summary"]["needs_work"])
    assert all(isinstance(item, str) and item for item in report["human_summary"]["strengths"])
    assert validate_contract("scene_quality_report", report) == []


def test_scene_quality_reports_style_and_curiosity_gaps() -> None:
    scene_graph = _scene()
    scene_graph["style_bible"]["palette"] = []
    scene_graph["curiosity_anchors"] = scene_graph["curiosity_anchors"][:1]

    diagnostics = validate_scene_quality(scene_graph, root=EXAMPLE_SCENE.parent)

    assert {"SV3001", "SV5001"} <= _codes(diagnostics)


def test_scene_quality_reports_semantic_avoid_term_overlap() -> None:
    scene_graph = _scene()
    scene_graph["objects"][0]["semantic_tags"].append("modern")

    report = run_scene_validators(scene_graph, root=EXAMPLE_SCENE.parent)

    assert report["status"] == "failed"
    assert "SV2003" in _codes(report["diagnostics"])


def test_scene_quality_reports_unknown_memory_affected_id() -> None:
    scene_graph = _scene()
    scene_graph["memory_events"][0]["affected_ids"] = ["obj_missing_001"]

    diagnostics = validate_scene_quality(scene_graph, root=EXAMPLE_SCENE.parent)

    assert "SV6001" in _codes(diagnostics)


def test_scene_quality_can_require_export_artifacts(tmp_path: Path) -> None:
    scene_graph = copy.deepcopy(_scene())
    scene_graph["exports"][0]["path"] = "exports/missing.glb"
    (tmp_path / "exports").mkdir()

    report = run_scene_validators(scene_graph, root=tmp_path, require_export_artifacts=True)

    assert report["status"] == "failed"
    assert "SV7003" in _codes(report["diagnostics"])


def test_scene_quality_reports_export_missing_material() -> None:
    scene_graph = copy.deepcopy(_scene())
    scene_graph["objects"][0]["material_bindings"][0]["material"] = "mat_missing_export_001"

    report = run_scene_validators(scene_graph, root=EXAMPLE_SCENE.parent, validators=["export"])

    assert report["status"] == "failed"
    assert {"S1012", "SV7004"} <= _codes(report["diagnostics"])
    export_report = next(item for item in report["validators"] if item["validator"] == "export")
    assert "SV7004" in _codes(export_report["diagnostics"])
