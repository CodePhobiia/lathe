from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from lathe.scene import check_scene_graph, load_and_check_scene_graph, scene_graph_validation_summary

REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_SCENE = REPO_ROOT / "examples" / "wonder" / "alchemist_observatory" / "scene_graph.json"


def _scene() -> dict:
    return json.loads(EXAMPLE_SCENE.read_text(encoding="utf-8"))


def _cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "lathe.cli", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        check=False,
    )


def _write_scene(tmp_path: Path, scene_graph: dict) -> Path:
    path = tmp_path / "scene_graph.json"
    path.write_text(json.dumps(scene_graph), encoding="utf-8")
    return path


def _codes(diagnostics: list[dict]) -> list[str]:
    return [diagnostic["code"] for diagnostic in diagnostics]


def test_check_scene_graph_accepts_alchemist_observatory() -> None:
    diagnostics = check_scene_graph(_scene(), root=EXAMPLE_SCENE.parent)

    assert diagnostics == []


def test_scene_graph_validation_summary_is_human_readable() -> None:
    scene_graph = _scene()

    summary = scene_graph_validation_summary(scene_graph, [])

    assert summary["status"] == "passed"
    assert summary["counts"]["objects"] == len(scene_graph["objects"])
    assert summary["counts"]["regions"] == len(scene_graph["regions"])
    assert "passed semantic validation" in summary["text"]


def test_check_scene_graph_reports_duplicate_object_ids() -> None:
    scene_graph = _scene()
    scene_graph["objects"][1]["object_id"] = scene_graph["objects"][0]["object_id"]

    diagnostics = check_scene_graph(scene_graph, root=EXAMPLE_SCENE.parent)

    assert "S1001" in _codes(diagnostics)
    duplicate = next(item for item in diagnostics if item["code"] == "S1001")
    assert duplicate["name"] == "duplicate_object_id"
    assert duplicate["path"] == "/objects/1/object_id"
    assert duplicate["details"]["first_path"] == "/objects/0/object_id"


@pytest.mark.parametrize(
    ("collection", "field", "code", "name"),
    [
        ("regions", "region_id", "S1006", "duplicate_region_id"),
        ("cameras", "camera_id", "S1007", "duplicate_camera_id"),
        ("lights", "light_id", "S1008", "duplicate_light_id"),
        ("materials", "material_id", "S1009", "duplicate_material_id"),
        ("curiosity_anchors", "anchor_id", "S1010", "duplicate_curiosity_anchor_id"),
        ("hidden_state", "hidden_id", "S1011", "duplicate_hidden_id"),
    ],
)
def test_check_scene_graph_reports_duplicate_scene_entity_ids(
    collection: str,
    field: str,
    code: str,
    name: str,
) -> None:
    scene_graph = _scene()
    duplicate = json.loads(json.dumps(scene_graph[collection][0]))
    scene_graph[collection].append(duplicate)
    duplicate_index = len(scene_graph[collection]) - 1

    diagnostics = check_scene_graph(scene_graph, root=EXAMPLE_SCENE.parent)

    assert code in _codes(diagnostics)
    duplicate_diagnostic = next(item for item in diagnostics if item["code"] == code)
    assert duplicate_diagnostic["name"] == name
    assert duplicate_diagnostic["path"] == f"/{collection}/{duplicate_index}/{field}"
    assert duplicate_diagnostic["details"]["first_path"] == f"/{collection}/0/{field}"


def test_check_scene_graph_reports_missing_object_region() -> None:
    scene_graph = _scene()
    scene_graph["objects"][0]["region"] = "region_missing_001"

    diagnostics = check_scene_graph(scene_graph, root=EXAMPLE_SCENE.parent)

    assert "S1002" in _codes(diagnostics)
    missing = next(item for item in diagnostics if item["code"] == "S1002")
    assert missing["name"] == "missing_object_region"
    assert missing["path"] == "/objects/0/region"
    assert missing["details"]["region"] == "region_missing_001"


def test_check_scene_graph_reports_missing_object_material() -> None:
    scene_graph = _scene()
    scene_graph["objects"][0]["material_bindings"][0]["material"] = "mat_missing_001"

    diagnostics = check_scene_graph(scene_graph, root=EXAMPLE_SCENE.parent)

    assert "S1012" in _codes(diagnostics)
    missing = next(item for item in diagnostics if item["code"] == "S1012")
    assert missing["name"] == "missing_object_material"
    assert missing["path"] == "/objects/0/material_bindings/0/material"
    assert missing["details"]["material"] == "mat_missing_001"
    assert missing["details"]["slot"] == "metal"


def test_check_scene_graph_reports_invalid_relationship_endpoint() -> None:
    scene_graph = _scene()
    scene_graph["relationships"][0]["to"] = "obj_missing_001"

    diagnostics = check_scene_graph(scene_graph, root=EXAMPLE_SCENE.parent)

    assert "S1003" in _codes(diagnostics)
    invalid = next(item for item in diagnostics if item["code"] == "S1003")
    assert invalid["name"] == "invalid_relationship_endpoint"
    assert invalid["path"] == "/relationships/0/to"
    assert invalid["details"]["endpoint"] == "obj_missing_001"


@pytest.mark.parametrize(
    ("collection", "field", "code", "name"),
    [
        ("cameras", "target", "S1013", "invalid_camera_target"),
        ("lights", "target", "S1014", "invalid_light_target"),
        ("curiosity_anchors", "attached_to", "S1015", "invalid_curiosity_attachment"),
        ("hidden_state", "attached_to", "S1016", "invalid_hidden_attachment"),
    ],
)
def test_check_scene_graph_reports_invalid_scene_ref_fields(
    collection: str,
    field: str,
    code: str,
    name: str,
) -> None:
    scene_graph = _scene()
    scene_graph[collection][0][field] = "obj_missing_001"

    diagnostics = check_scene_graph(scene_graph, root=EXAMPLE_SCENE.parent)

    assert code in _codes(diagnostics)
    invalid = next(item for item in diagnostics if item["code"] == code)
    assert invalid["name"] == name
    assert invalid["path"] == f"/{collection}/0/{field}"
    assert invalid["details"]["target"] == "obj_missing_001"


def test_check_scene_graph_reports_invalid_affordance_reveal() -> None:
    scene_graph = _scene()
    scene_graph["objects"][0]["affordances"][0]["reveals"] = "hidden_missing_001"

    diagnostics = check_scene_graph(scene_graph, root=EXAMPLE_SCENE.parent)

    assert "S1017" in _codes(diagnostics)
    invalid = next(item for item in diagnostics if item["code"] == "S1017")
    assert invalid["name"] == "invalid_affordance_reveal"
    assert invalid["path"] == "/objects/0/affordances/0/reveals"
    assert invalid["details"]["reveals"] == "hidden_missing_001"


@pytest.mark.parametrize(
    ("mutate", "code", "path"),
    [
        (
            lambda scene_graph: scene_graph["layout"].__setitem__("focal_point", "obj_missing_001"),
            "S1018",
            "/layout/focal_point",
        ),
        (
            lambda scene_graph: scene_graph["layout"]["main_path"].__setitem__("to", "obj_missing_001"),
            "S1019",
            "/layout/main_path/to",
        ),
        (
            lambda scene_graph: scene_graph["layout"].__setitem__(
                "modular_walls",
                {"enabled": True, "regions": ["region_missing_001"]},
            ),
            "S1022",
            "/layout/modular_walls/regions/0",
        ),
        (
            lambda scene_graph: scene_graph["curiosity_anchors"][0]["expansion_options"][0].__setitem__(
                "target_scope",
                "obj_missing_001",
            ),
            "S1020",
            "/curiosity_anchors/0/expansion_options/0/target_scope",
        ),
        (
            lambda scene_graph: scene_graph["memory_events"][0]["affected_ids"].append("obj_missing_001"),
            "S1021",
            "/memory_events/0/affected_ids/2",
        ),
    ],
)
def test_check_scene_graph_reports_all_schema_declared_scene_refs(mutate, code: str, path: str) -> None:
    scene_graph = _scene()
    mutate(scene_graph)

    diagnostics = check_scene_graph(scene_graph, root=EXAMPLE_SCENE.parent)

    assert code in _codes(diagnostics)
    diagnostic = next(item for item in diagnostics if item["code"] == code)
    assert diagnostic["path"] == path


@pytest.mark.parametrize(
    ("collection", "code", "bad_path"),
    [
        ("exports", "S1004", "../outside.json"),
        ("build_artifacts", "S1005", "C:/tmp/report.json"),
    ],
)
def test_check_scene_graph_reports_unsafe_artifact_paths(
    collection: str,
    code: str,
    bad_path: str,
) -> None:
    scene_graph = _scene()
    scene_graph[collection][0]["path"] = bad_path

    diagnostics = check_scene_graph(scene_graph, root=EXAMPLE_SCENE.parent)

    assert code in _codes(diagnostics)
    unsafe = next(item for item in diagnostics if item["code"] == code)
    assert unsafe["path"] == f"/{collection}/0/path"
    assert unsafe["details"]["path"] == bad_path


def test_load_and_check_scene_graph_keeps_schema_diagnostics_for_missing_required(tmp_path: Path) -> None:
    scene_graph = _scene()
    scene_graph.pop("objects")

    _payload, diagnostics = load_and_check_scene_graph(_write_scene(tmp_path, scene_graph))

    assert _codes(diagnostics) == ["WONDER_SCHEMA_VALIDATION"]
    assert diagnostics[0]["path"] == "/"
    assert "'objects' is a required property" in diagnostics[0]["message"]


def test_wonder_cli_check_scene_graph_success() -> None:
    result = _cli("wonder", "check-scene-graph", str(EXAMPLE_SCENE))

    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["check"] == "scene_graph_semantics"
    assert payload["summary"]["status"] == "passed"
    assert "passed semantic validation" in payload["summary"]["text"]
    assert payload["diagnostics"] == []


def test_wonder_cli_check_scene_graph_reports_semantic_diagnostics(tmp_path: Path) -> None:
    scene_graph = _scene()
    scene_graph["objects"][1]["object_id"] = scene_graph["objects"][0]["object_id"]

    result = _cli("wonder", "check-scene-graph", str(_write_scene(tmp_path, scene_graph)))

    assert result.returncode == 1
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["contract"] == "scene_graph"
    assert payload["summary"]["status"] == "failed"
    assert "S1001" in payload["summary"]["text"]
    assert "S1001" in _codes(payload["diagnostics"])
