from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest
from lathe.capabilities import probe_blender
from lathe.cli import scene_cmd
from lathe.scene import blender_export
from lathe.scene.artifacts import SceneArtifactError

REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_SCENE = REPO_ROOT / "examples" / "wonder" / "alchemist_observatory" / "scene_graph.json"
OPTIONAL_BLENDER_CI = REPO_ROOT / "scripts" / "ci_wonder_optional_blender.py"
OPTIONAL_BLENDER_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "wonder-optional-blender.yml"


class _FakeBlenderResult:
    ok = True
    exit_code = 0
    duration_s = 0.25
    stdout_tail = "saved blend"
    stderr_tail = ""
    timed_out = False
    stdout_log_path = None
    stderr_log_path = None


def _scene() -> dict:
    return json.loads(EXAMPLE_SCENE.read_text(encoding="utf-8"))


def _summary_from_metadata(metadata: dict) -> dict:
    return {
        "objects": [item["object_id"] for item in metadata["objects"]],
        "collections": [f"LatheScene_{metadata['scene_id']}"]
        + [item["region_id"] for item in metadata["regions"]],
        "materials": [item["material_id"] for item in metadata["materials"]],
        "cameras": [item["camera_id"] for item in metadata["cameras"]],
        "lights": [item["light_id"] for item in metadata["lights"]],
        "custom_properties": {
            "scene": {"lathe_scene_id": metadata["scene_id"]},
            "objects": {
                item["object_id"]: {
                    "lathe_scene_id": metadata["scene_id"],
                    "lathe_object_id": item["object_id"],
                    "lathe_region_id": item["region_id"],
                    "lathe_material_id": item["material_id"],
                    "lathe_provenance_source": item["provenance"]["source"],
                    "lathe_provenance_commercial_use": item["provenance"]["commercial_use"],
                    "lathe_reuse_group_id": item["instancing"]["reuse_group_id"],
                    "lathe_asset_signature": item["instancing"]["asset_signature"],
                    "lathe_shared_asset": item["instancing"]["shared_asset"],
                    "lathe_instance_fingerprint": item["instancing"]["instance_fingerprint"],
                }
                for item in metadata["objects"]
            },
            "collections": {
                item["region_id"]: {
                    "lathe_scene_id": metadata["scene_id"],
                    "lathe_region_id": item["region_id"],
                }
                for item in metadata["regions"]
            },
            "materials": {
                item["material_id"]: {
                    "lathe_scene_id": metadata["scene_id"],
                    "lathe_material_id": item["material_id"],
                }
                for item in metadata["materials"]
            },
        },
        "node_groups": [],
        "linked_libraries": [],
        "overrides": [],
    }


def test_export_scene_blend_uses_sandbox_and_preserves_identity(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    scene_graph = _scene()
    calls: list[dict] = []

    def fake_probe() -> dict:
        return {
            "available": True,
            "path": "C:/Blender/blender.exe",
            "version": "5.0.1",
            "code": "ok",
            "supported_modes": ["background_cli"],
        }

    def fake_run(command, *, cwd, expect_files, log_dir, log_prefix):
        metadata_path = Path(command[command.index("--metadata") + 1])
        output_path = Path(command[command.index("--output") + 1])
        summary_path = Path(command[command.index("--summary") + 1])
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"BLENDER")
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(json.dumps(_summary_from_metadata(metadata)), encoding="utf-8")
        calls.append(
            {
                "command": [str(item) for item in command],
                "cwd": Path(cwd),
                "expect_files": [Path(item) for item in expect_files],
                "log_dir": Path(log_dir),
                "log_prefix": log_prefix,
            }
        )
        return _FakeBlenderResult()

    monkeypatch.setattr(blender_export, "probe_blender", fake_probe)
    monkeypatch.setattr(blender_export, "run_blender_sandboxed", fake_run)

    report = blender_export.export_scene_blend(
        scene_graph,
        tmp_path,
        include_collision_nodes=True,
    )

    assert calls, "Blender sandbox should be invoked"
    command = calls[0]["command"]
    assert command[:4] == ["C:/Blender/blender.exe", "--background", "--factory-startup", "--python"]
    assert command[command.index("--metadata") + 1].endswith("reports\\blender_export_metadata.json") or command[
        command.index("--metadata") + 1
    ].endswith("reports/blender_export_metadata.json")
    assert calls[0]["expect_files"] == [
        tmp_path / "exports" / "alchemist_observatory.blend",
        tmp_path / "reports" / "blender_export_summary.json",
    ]
    assert report["schema_version"] == "lathe.scene_export_artifacts.v1"
    assert report["exporter"] == "lathe.scene.blender_exporter.v1"
    blend_artifact = next(item for item in report["artifacts"] if item["target"] == "blend")
    assert blend_artifact["format"] == "blend"
    assert blend_artifact["identity"]["status"] == "passed"
    assert blend_artifact["collections"]["missing"] == []
    assert blend_artifact["cameras"]["missing"] == []
    assert blend_artifact["lights"]["missing"] == []
    assert blend_artifact["materials"]["missing"] == []
    assert (tmp_path / "exports" / "alchemist_observatory.blend").read_bytes() == b"BLENDER"
    metadata = json.loads((tmp_path / "reports" / "blender_export_metadata.json").read_text(encoding="utf-8"))
    assert metadata["schema_version"] == "lathe.scene_blender_export_metadata.v1"
    assert metadata["objects"][0]["object_id"].startswith("obj_")
    assert metadata["objects"][0]["provenance"]["source"] == "deterministic_lathe"
    assert metadata["objects"][0]["instancing"]["schema_version"] == "lathe.scene_instancing_metadata.v1"
    assert metadata["objects"][0]["instancing"]["reuse_group_id"].startswith("reuse_group_")
    object_props = blend_artifact["identity"]["object_ids_found"]
    assert scene_graph["objects"][0]["object_id"] in object_props
    summary = json.loads((tmp_path / "reports" / "blender_export_summary.json").read_text(encoding="utf-8"))
    first_props = summary["custom_properties"]["objects"][metadata["objects"][0]["object_id"]]
    assert first_props["lathe_reuse_group_id"] == metadata["objects"][0]["instancing"]["reuse_group_id"]
    assert first_props["lathe_shared_asset"] is metadata["objects"][0]["instancing"]["shared_asset"]


def test_export_scene_blend_fails_when_blender_unavailable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        blender_export,
        "probe_blender",
        lambda: {"available": False, "path": None, "code": "not_found"},
    )

    with pytest.raises(SceneArtifactError) as excinfo:
        blender_export.export_scene_blend(_scene(), tmp_path)

    assert excinfo.value.diagnostics[0]["code"] == "SX1201"
    assert not (tmp_path / "exports" / "alchemist_observatory.blend").exists()


def test_scene_export_cli_routes_blender_target(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    def fake_export(scene_graph, package_dir, *, mode, include_collision_nodes):
        assert scene_graph["scene_id"] == "alchemist_observatory"
        assert Path(package_dir) == tmp_path
        assert mode == "preview"
        assert include_collision_nodes is True
        return {
            "schema_version": "lathe.scene_export_artifacts.v1",
            "scene_id": "alchemist_observatory",
            "mode": mode,
            "exporter": "lathe.scene.blender_exporter.v1",
            "artifacts": [],
            "diagnostics": [],
        }

    monkeypatch.setattr(blender_export, "export_scene_blend", fake_export)

    scene_cmd._run_export(
        argparse.Namespace(
            scene=str(EXAMPLE_SCENE),
            out=str(tmp_path),
            target="blender",
            mode="preview",
            include_collision_proxies=True,
            include_id_mask_bundle=False,
        )
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["target"] == "blender"
    assert payload["include_collision_proxies"] is True
    assert payload["report"]["exporter"] == "lathe.scene.blender_exporter.v1"


def test_optional_blender_ci_lane_runs_mocked_bridge_and_documents_render_boundary() -> None:
    script = OPTIONAL_BLENDER_CI.read_text(encoding="utf-8")
    workflow = OPTIONAL_BLENDER_WORKFLOW.read_text(encoding="utf-8")

    assert "tests/unit/test_scene_blender_export.py" in script
    assert "scene_export_blender_smoke" in script
    assert "Blender-backed scene rendering is not available" in script
    assert "python scripts/ci_wonder_optional_blender.py" in workflow
    assert "continue-on-error: true" in workflow


@pytest.mark.skipif(not probe_blender().get("available"), reason="Blender is not available")
def test_export_scene_blend_smoke_when_blender_available(tmp_path: Path) -> None:
    report = blender_export.export_scene_blend(_scene(), tmp_path)

    blend_artifact = next(item for item in report["artifacts"] if item["target"] == "blend")
    assert blend_artifact["identity"]["status"] == "passed"
    assert blend_artifact["collections"]["missing"] == []
    assert blend_artifact["cameras"]["missing"] == []
    assert blend_artifact["lights"]["missing"] == []
    assert blend_artifact["materials"]["missing"] == []
    summary = json.loads((tmp_path / "reports" / "blender_export_summary.json").read_text(encoding="utf-8"))
    objects = summary["custom_properties"]["objects"]
    first_object = _scene()["objects"][0]
    first_props = next(
        item for item in objects.values() if item.get("lathe_object_id") == first_object["object_id"]
    )
    assert first_props["lathe_scene_id"] == "alchemist_observatory"
    assert first_props["lathe_region_id"] == first_object["region"]
    assert first_props["lathe_provenance_source"] == "deterministic_lathe"
