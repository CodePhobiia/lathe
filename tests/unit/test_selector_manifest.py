"""Unit tests for ``lathe.selector_manifest`` (REF-5) and ``lathe.ref`` (REF-7).

Covers:

* schema-conformant manifest assembly from a minimal runtime,
* full-population manifest with parts/sockets/pivots/collisions/lods/materials/diagnostics,
* writer round-trip (validate → write → re-read → re-validate),
* writer refusal on invalid payload,
* graceful handling of absent optimize / interfaces runtimes,
* variant=None serializes as JSON null,
* invalid explicit build/package hashes fail instead of being rewritten,
* ``resolve_ref`` prefers ``selector_manifest.json`` when present,
* stale-ref warning on buildHash mismatch,
* fallback to ``build_report.json`` when selector manifest absent,
* end-to-end: build_selector_manifest → write → resolve_ref.
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path

import jsonschema
import pytest
from lathe.ref import StaleRefWarning, parse_ref, resolve_ref
from lathe.selector_manifest import (
    SelectorManifestError,
    build_selector_manifest,
    write_selector_manifest,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO_ROOT / "schema" / "lathe.selector.schema.json"


@pytest.fixture(scope="module")
def schema_validator() -> jsonschema.Draft202012Validator:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return jsonschema.Draft202012Validator(schema)


# ---------------------------------------------------------------------------
# build_selector_manifest — minimal runtime
# ---------------------------------------------------------------------------


def test_build_selector_manifest_minimal(schema_validator, tmp_path):
    build_dir = tmp_path / "mini"
    build_dir.mkdir()
    manifest = build_selector_manifest(
        asset_name="mini",
        variant_name=None,
        source_path="examples/mini.lth",
        build_hash="0123abcd" * 4,
        runtime={},
        validate_report=None,
        asset=None,
        build_dir=build_dir,
    )
    schema_validator.validate(manifest)
    assert manifest["schemaVersion"] == 1
    assert manifest["asset"] == "mini"
    assert manifest["variant"] is None
    assert manifest["parts"] == []
    assert manifest["sockets"] == []
    assert manifest["pivots"] == []
    assert manifest["collisions"] == []
    assert manifest["lods"] == []
    assert manifest["materials"] == []
    assert manifest["diagnostics"] == []
    assert manifest["tables"] == {}
    assert manifest["relations"] == {}


# ---------------------------------------------------------------------------
# build_selector_manifest — fully populated runtime
# ---------------------------------------------------------------------------


def _full_runtime() -> dict[str, object]:
    return {
        "topology": {
            "bundle": {
                "part_groups": [
                    {"name": "body", "face_count": 120, "bbox": [-1, -1, -1, 1, 1, 1]},
                    {"name": "rotor_fl", "face_count": 40},
                ],
            },
        },
        "interfaces": {
            "bundle": {
                "sockets": [
                    {
                        "id": "grip_main",
                        "origin": [0.0, 1.0, 0.0],
                        "axis": [0.0, 0.0, 1.0],
                        "kind": "attachment",
                        "parent_part_id": "body",
                    }
                ],
                "pivots": [{"id": "hinge_top", "origin": [0.0, 1.5, 0.0], "axis": [0.0, 1.0, 0.0]}],
            },
        },
        "optimize": {
            "bundle": {
                "collision_manifest": [
                    {"id": "body_hull", "kind": "hull", "parent_part_id": "body", "hull_count": 3}
                ],
                "lod_manifest": [
                    {"level": 0, "part_id": "body", "triangle_count": 120, "screen_size": 1.0},
                    {"level": 1, "part_id": "body", "triangle_count": 60, "screen_size": 0.4},
                ],
            },
        },
        "surface": {
            "bundle": {
                "materials": [
                    {
                        "id": "steel",
                        "display_name": "Brushed Steel",
                        "texture_memory_mb": 4.0,
                        "texture_set": ["basecolor", "normal", "roughness"],
                    }
                ],
            },
        },
        "package": {"bundle": {"package_hash": "deadbeef" * 8}},
    }


def test_build_selector_manifest_full(schema_validator, tmp_path):
    manifest = build_selector_manifest(
        asset_name="courier_drone",
        variant_name=None,
        source_path="examples/courier_drone.lth",
        build_hash="0123abcd" * 4,
        runtime=_full_runtime(),
        validate_report={
            "diagnostics": [
                {
                    "id": "shape.candidate_score",
                    "severity": "info",
                    "stage": "shape",
                    "message": "candidate score above threshold",
                }
            ],
        },
        asset={"space": {"up_axis": "Y", "unit": "cm"}},
        build_dir=tmp_path / "courier_drone",
    )
    schema_validator.validate(manifest)
    part_ids = [p["id"] for p in manifest["parts"]]
    assert "body" in part_ids and "rotor_fl" in part_ids
    # ref tokens are canonical @lathe[...] strings
    assert manifest["parts"][0]["ref"].startswith("@lathe[")
    assert manifest["parts"][0]["ref"].endswith("#part.body]")
    assert manifest["sockets"][0]["id"] == "grip_main"
    assert manifest["sockets"][0]["kind"] == "attachment"
    assert manifest["pivots"][0]["id"] == "hinge_top"
    assert manifest["collisions"][0]["kind"] == "hull"
    assert len(manifest["lods"]) == 2
    assert manifest["lods"][1]["level"] == 1
    assert manifest["materials"][0]["displayName"] == "Brushed Steel"
    assert manifest["diagnostics"][0]["severity"] == "info"


def test_build_selector_manifest_absent_optimize(schema_validator, tmp_path):
    """Missing optimize runtime → collisions + lods stay as empty lists."""
    runtime = {"topology": {"bundle": {"part_groups": [{"name": "body"}]}}}
    manifest = build_selector_manifest(
        asset_name="x",
        variant_name=None,
        source_path="examples/x.lth",
        build_hash="0123abcd" * 4,
        runtime=runtime,
        asset=None,
        build_dir=tmp_path / "x",
    )
    schema_validator.validate(manifest)
    assert manifest["collisions"] == []
    assert manifest["lods"] == []
    # Parts still populated from topology.
    assert manifest["parts"][0]["id"] == "body"


def test_build_selector_manifest_variant_name(tmp_path):
    manifest = build_selector_manifest(
        asset_name="courier_drone_mobile",
        variant_name="courier_drone_mobile",
        source_path="examples/courier_drone.lth",
        build_hash="0123abcd" * 4,
        runtime={},
        build_dir=tmp_path / "build",
    )
    assert manifest["variant"] == "courier_drone_mobile"
    # Round-trip through JSON to confirm variant stays non-null.
    payload = json.loads(json.dumps(manifest))
    assert payload["variant"] == "courier_drone_mobile"


def test_build_selector_manifest_variant_none_serializes_as_null(tmp_path):
    manifest = build_selector_manifest(
        asset_name="x",
        variant_name=None,
        source_path="examples/x.lth",
        build_hash="0123abcd" * 4,
        runtime={},
        build_dir=tmp_path / "x",
    )
    serialized = json.dumps(manifest)
    reloaded = json.loads(serialized)
    assert reloaded["variant"] is None


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"build_hash": "build-not-a-digest"}, "buildHash"),
        ({"build_hash": "0123abcd" * 4, "package_hash": "package-not-a-digest"}, "packageHash"),
    ],
)
def test_build_selector_manifest_rejects_invalid_explicit_hashes(tmp_path, kwargs, message):
    args = {
        "asset_name": "x",
        "variant_name": None,
        "source_path": "examples/x.lth",
        "build_hash": "0123abcd" * 4,
        "runtime": {},
        "build_dir": tmp_path / "x",
    }
    args.update(kwargs)

    with pytest.raises(SelectorManifestError) as exc:
        build_selector_manifest(**args)

    assert message in str(exc.value)
    assert "digest" in str(exc.value)


@pytest.mark.parametrize(
    "runtime",
    [
        {"package": {"bundle": {"package_hash": "invalid-package-hash"}}},
        {"package": {"bundle": {"outputs": [{"format": "glb", "sha256": "invalid-output-hash"}]}}},
    ],
)
def test_build_selector_manifest_rejects_invalid_runtime_package_hashes(tmp_path, runtime):
    with pytest.raises(SelectorManifestError) as exc:
        build_selector_manifest(
            asset_name="x",
            variant_name=None,
            source_path="examples/x.lth",
            build_hash="0123abcd" * 4,
            runtime=runtime,
            build_dir=tmp_path / "x",
        )

    assert "runtime.package.bundle" in str(exc.value)
    assert "digest" in str(exc.value)


# ---------------------------------------------------------------------------
# write_selector_manifest
# ---------------------------------------------------------------------------


def test_write_selector_manifest_round_trip(tmp_path, schema_validator):
    build_dir = tmp_path / "build"
    build_dir.mkdir()
    manifest = build_selector_manifest(
        asset_name="demo",
        variant_name=None,
        source_path="examples/demo.lth",
        build_hash="abcd1234" * 4,
        runtime=_full_runtime(),
        build_dir=build_dir,
    )
    path = write_selector_manifest(manifest, build_dir)
    assert path.exists()
    assert path.name == "selector_manifest.json"
    # Re-read and re-validate.
    reloaded = json.loads(path.read_text(encoding="utf-8"))
    schema_validator.validate(reloaded)
    assert reloaded["asset"] == "demo"


def test_write_selector_manifest_rejects_invalid(tmp_path):
    build_dir = tmp_path / "build"
    build_dir.mkdir()
    broken = {
        "schemaVersion": 1,
        # missing most required keys
    }
    with pytest.raises(SelectorManifestError) as exc:
        write_selector_manifest(broken, build_dir)
    assert "selector_manifest.json failed schema validation" in str(exc.value)
    # File must not have been written.
    assert not (build_dir / "selector_manifest.json").exists()


def test_write_selector_manifest_rejects_unsupported_schema_version_with_code(tmp_path):
    build_dir = tmp_path / "build"
    manifest = build_selector_manifest(
        asset_name="demo",
        variant_name=None,
        source_path="examples/demo.lth",
        build_hash="abcd1234" * 4,
        runtime=_full_runtime(),
        build_dir=build_dir,
    )
    manifest["schemaVersion"] = 2

    with pytest.raises(SelectorManifestError) as exc:
        write_selector_manifest(manifest, build_dir)

    assert exc.value.code == "L7201"
    assert "unsupported_selector_manifest_version" in str(exc.value)
    assert "schemaVersion '2'" in str(exc.value)
    assert "supported: 1" in str(exc.value)
    assert not (build_dir / "selector_manifest.json").exists()


# ---------------------------------------------------------------------------
# resolve_ref — prefers selector_manifest.json
# ---------------------------------------------------------------------------


def _write_build_with_manifest(
    tmp_path: Path,
    *,
    asset_name: str,
    build_hash: str,
    parts: list[dict] | None = None,
) -> Path:
    build_dir = tmp_path / asset_name
    build_dir.mkdir()
    # Minimal build_report so stage resolvers have something to look at.
    build_report = {
        "asset": asset_name,
        "kind": "mechanical_assembly",
        "certified": True,
        "backend_stack": {"id": "lathe.stack.hard_surface_game_asset_v1"},
        "stage_bundles": {
            "shape": {"backend_id": "lathe.shape.intent_mesh_handoff_v1"},
        },
        "diagnostics": [],
        "outputs": [],
    }
    (build_dir / "build_report.json").write_text(json.dumps(build_report))

    runtime = {
        "topology": {
            "bundle": {
                "part_groups": [{"name": p["id"]} for p in (parts or [])],
            }
        },
    }
    manifest = build_selector_manifest(
        asset_name=asset_name,
        variant_name=None,
        source_path=f"examples/{asset_name}.lth",
        build_hash=build_hash,
        runtime=runtime,
        build_dir=build_dir,
    )
    write_selector_manifest(manifest, build_dir)
    return build_dir


def test_resolve_ref_prefers_selector_manifest(tmp_path):
    _write_build_with_manifest(
        tmp_path,
        asset_name="mini",
        build_hash="0123abcd" * 4,
        parts=[{"id": "body"}, {"id": "rotor"}],
    )
    node = parse_ref("@lathe[mini#part.body]")
    result = resolve_ref(node, repo_root=tmp_path)
    assert result["ok"] is True
    assert result["facts"]["source"] == "selector_manifest.json:parts"
    assert result["facts"]["part_id"] == "body"


def test_resolve_ref_asset_via_manifest(tmp_path):
    _write_build_with_manifest(tmp_path, asset_name="mini", build_hash="0123abcd" * 4)
    node = parse_ref("@lathe[mini#asset.mini]")
    result = resolve_ref(node, repo_root=tmp_path)
    assert result["ok"] is True
    assert result["facts"]["source"] == "selector_manifest.json"


def test_resolve_ref_emits_stale_warning_on_build_hash_mismatch(tmp_path):
    _write_build_with_manifest(
        tmp_path,
        asset_name="mini",
        build_hash="0123abcd" * 4,
    )
    node = parse_ref("@lathe[mini]")
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        resolve_ref(node, repo_root=tmp_path, expected_build_hash="ffffffff" * 4)
    assert any(issubclass(w.category, StaleRefWarning) for w in captured)


def test_resolve_ref_falls_back_to_build_report_when_manifest_absent(tmp_path):
    # Phase-1 compatibility: build_report.json only, no selector_manifest.json.
    build_dir = tmp_path / "legacy"
    (build_dir / "stages" / "shape").mkdir(parents=True)
    build_report = {
        "asset": "legacy",
        "kind": "mechanical_assembly",
        "certified": True,
        "backend_stack": {"id": "lathe.stack.hard_surface_game_asset_v1"},
        "stage_bundles": {"shape": {"backend_id": "lathe.shape.intent_mesh_handoff_v1"}},
        "diagnostics": [],
        "outputs": [],
    }
    (build_dir / "build_report.json").write_text(json.dumps(build_report))
    shape_bundle = {
        "selected_candidate_id": "c0",
        "candidates": [{"candidate_id": "c0", "part_labels": ["body"]}],
    }
    (build_dir / "stages" / "shape" / "bundle.json").write_text(json.dumps(shape_bundle))
    node = parse_ref("@lathe[legacy#asset.legacy]")
    result = resolve_ref(node, repo_root=tmp_path)
    assert result["ok"] is True
    # No manifest-provided "source" field → resolution came from build_report.json.
    assert result["facts"].get("source") != "selector_manifest.json"


# ---------------------------------------------------------------------------
# End-to-end: assemble → write → resolve
# ---------------------------------------------------------------------------


def test_end_to_end_manifest_resolves(tmp_path):
    build_dir = tmp_path / "e2e"
    build_dir.mkdir()
    runtime = {
        "topology": {"bundle": {"part_groups": [{"name": "body"}, {"name": "wing"}]}},
        "optimize": {
            "bundle": {
                "lod_manifest": [
                    {"level": 0, "part_id": "body", "triangle_count": 100},
                ],
            }
        },
    }
    manifest = build_selector_manifest(
        asset_name="e2e",
        variant_name=None,
        source_path="examples/e2e.lth",
        build_hash="0123abcd" * 4,
        runtime=runtime,
        build_dir=build_dir,
    )
    write_selector_manifest(manifest, build_dir)
    (build_dir / "build_report.json").write_text(
        json.dumps(
            {
                "asset": "e2e",
                "kind": "mechanical_assembly",
                "certified": True,
                "backend_stack": {"id": "lathe.stack.hard_surface_game_asset_v1"},
                "stage_bundles": {},
                "diagnostics": [],
                "outputs": [],
            }
        )
    )
    node = parse_ref("@lathe[e2e#part.wing]")
    result = resolve_ref(node, repo_root=tmp_path)
    assert result["ok"] is True
    assert result["facts"]["source"] == "selector_manifest.json:parts"
