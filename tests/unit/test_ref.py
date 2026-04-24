"""Unit tests for `lathe.ref` — Phase-1 semantic references.

Covers REF-1/2/3/4/8/14 acceptance criteria:

* grammar parse/format round-trip for every Phase-1 selector kind,
* path-traversal rejection,
* Phase-2 geometric-selector rejection with the stable
  ``phase_2_feature_not_yet_available`` error code,
* resolution against a real ``dist/courier_drone`` build when available
  (and against a synthesised minimal build dir otherwise),
* stale-ref warning when ``build_report.json`` is missing,
* CLI smoke for ``python -m lathe.cli ref parse``.
"""

from __future__ import annotations

import json
import subprocess
import sys
import warnings
from pathlib import Path

import pytest

from lathe.ref import (
    RefNode,
    RefParseError,
    RefSelector,
    StaleRefWarning,
    format_ref,
    parse_ref,
    resolve_ref,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Happy parse cases
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "token, expected_target, expected_selector",
    [
        ("@lathe[dist/courier_drone]", "dist/courier_drone", None),
        (
            "@lathe[dist/courier_drone#asset.courier_drone]",
            "dist/courier_drone",
            RefSelector(kind="asset", id="courier_drone"),
        ),
        (
            "@lathe[dist/courier_drone#variant.courier_drone_mobile]",
            "dist/courier_drone",
            RefSelector(kind="variant", id="courier_drone_mobile"),
        ),
        (
            "@lathe[dist/courier_drone#stage.shape]",
            "dist/courier_drone",
            RefSelector(kind="stage", id="shape"),
        ),
        (
            "@lathe[dist/courier_drone#diagnostic.bake_missing]",
            "dist/courier_drone",
            RefSelector(kind="diagnostic", id="bake_missing"),
        ),
        (
            "@lathe[dist/courier_drone#part.body]",
            "dist/courier_drone",
            RefSelector(kind="part", id="body"),
        ),
        (
            "@lathe[examples/courier_drone.lth#asset.courier_drone]",
            "examples/courier_drone.lth",
            RefSelector(kind="asset", id="courier_drone"),
        ),
    ],
)
def test_parse_ref_happy(token, expected_target, expected_selector):
    node = parse_ref(token)
    assert node.target == expected_target
    assert node.selector == expected_selector


def test_parse_ref_dotted_diagnostic_id():
    # Diagnostic ids often contain dots (stage.code form). The part-suffix
    # Phase-2 guard should not fire for non-part selectors.
    node = parse_ref("@lathe[dist/x#diagnostic.shape.candidate_score]")
    assert node.selector == RefSelector(kind="diagnostic", id="shape.candidate_score")


# ---------------------------------------------------------------------------
# format_ref round-trip
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "token",
    [
        "@lathe[dist/courier_drone]",
        "@lathe[dist/courier_drone#asset.courier_drone]",
        "@lathe[dist/courier_drone#variant.mobile]",
        "@lathe[dist/courier_drone#stage.package]",
        "@lathe[dist/courier_drone#diagnostic.bake_missing]",
        "@lathe[dist/courier_drone#part.rotor_fl]",
    ],
)
def test_format_ref_roundtrip(token):
    assert format_ref(parse_ref(token)) == token


# ---------------------------------------------------------------------------
# Structural rejections
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "token, expected_code",
    [
        ("dist/courier_drone#asset.foo", "missing_prefix"),
        ("@lathe[dist/courier_drone", "missing_suffix"),
        ("@lathe[]", "empty_ref"),
        ("@lathe[dist/foo#]", "empty_selector"),
        ("@lathe[dist/foo#nope.bar]", "unknown_selector_kind"),
        ("@lathe[dist/foo#asset.]", "invalid_identifier"),
        ("@lathe[dist/foo#asset]", "unknown_selector_kind"),
    ],
)
def test_parse_ref_structural_rejects(token, expected_code):
    with pytest.raises(RefParseError) as exc:
        parse_ref(token)
    assert exc.value.code == expected_code


# ---------------------------------------------------------------------------
# Path-traversal rejection
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "token",
    [
        "@lathe[../../etc/passwd]",
        "@lathe[..\\secret]",
        "@lathe[C:\\Windows\\System32]",
        "@lathe[D:/absolute/path]",
        "@lathe[\\\\?\\share\\x]",
        "@lathe[\\\\server\\share]",
        "@lathe[/etc/shadow]",
    ],
)
def test_parse_ref_rejects_path_traversal(token):
    with pytest.raises(RefParseError) as exc:
        parse_ref(token)
    assert exc.value.code == "path_traversal_rejected"


# ---------------------------------------------------------------------------
# Phase-2 geometric-selector rejection
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "token",
    [
        "@lathe[dist/foo#part.body.face12]",
        "@lathe[dist/foo#part.body.edge7]",
        "@lathe[dist/foo#part.body.vertex0]",
        "@lathe[dist/foo#socket.grip_main]",
        "@lathe[dist/foo#collision.body]",
        "@lathe[dist/foo#pivot.hinge_top]",
        "@lathe[dist/foo#material.steel]",
        "@lathe[dist/foo#lod2.body]",
        "@lathe[dist/foo#lod2]",
    ],
)
def test_phase_2_selectors_rejected_helpfully(token):
    with pytest.raises(RefParseError) as exc:
        parse_ref(token)
    assert exc.value.code == "phase_2_feature_not_yet_available"
    # Error message should point at the public docs and the roadmap.
    msg = str(exc.value)
    assert "docs/refs.md" in msg or "refs.md" in msg


# ---------------------------------------------------------------------------
# Resolution against a minimal synthetic build dir
# ---------------------------------------------------------------------------


@pytest.fixture()
def mini_build(tmp_path: Path) -> Path:
    """A minimal build dir shaped like a real Lathe build."""
    build_dir = tmp_path / "mini_drone"
    (build_dir / "stages" / "shape").mkdir(parents=True)
    build_report = {
        "asset": "mini_drone",
        "kind": "mechanical_assembly",
        "out_dir": str(build_dir),
        "certified": True,
        "backend_stack": {"id": "lathe.stack.hard_surface_game_asset_v1"},
        "stage_bundles": {
            "shape": {"backend_id": "lathe.shape.intent_mesh_handoff_v1"},
            "package": {"backend_id": "lathe.package.openusd_gltf_v1"},
        },
        "diagnostics": [
            {"id": "bake_missing", "severity": "warning", "stage": "surface",
             "message": "bake was not run", "code": "surface.bake_missing"}
        ],
        "outputs": [
            {"format": "glb", "uri": "stages/package/mini_drone.glb",
             "sha256": "a" * 64, "size_bytes": 100}
        ],
    }
    (build_dir / "build_report.json").write_text(json.dumps(build_report))
    shape_bundle = {
        "selected_candidate_id": "c0",
        "candidates": [
            {"candidate_id": "c0", "part_labels": ["body", "rotor_fl", "rotor_fr"]}
        ],
    }
    (build_dir / "stages" / "shape" / "bundle.json").write_text(json.dumps(shape_bundle))
    return tmp_path


def test_resolve_whole_build(mini_build: Path):
    node = parse_ref("@lathe[mini_drone]")
    result = resolve_ref(node, repo_root=mini_build)
    assert result["ok"] is True
    assert result["facts"]["asset"] == "mini_drone"
    assert result["facts"]["certified"] is True
    assert "shape" in result["facts"]["stage_ids"]


def test_resolve_asset_match(mini_build: Path):
    node = parse_ref("@lathe[mini_drone#asset.mini_drone]")
    result = resolve_ref(node, repo_root=mini_build)
    assert result["ok"] is True
    assert result["facts"]["asset"] == "mini_drone"


def test_resolve_asset_mismatch(mini_build: Path):
    node = parse_ref("@lathe[mini_drone#asset.not_the_asset]")
    result = resolve_ref(node, repo_root=mini_build)
    assert result["ok"] is False
    assert result["facts"]["reason"] == "asset_not_in_build"


def test_resolve_stage_known(mini_build: Path):
    node = parse_ref("@lathe[mini_drone#stage.shape]")
    result = resolve_ref(node, repo_root=mini_build)
    assert result["ok"] is True
    assert result["facts"]["stage"] == "shape"


def test_resolve_stage_unknown(mini_build: Path):
    node = parse_ref("@lathe[mini_drone#stage.nope]")
    result = resolve_ref(node, repo_root=mini_build)
    assert result["ok"] is False
    assert "available_stages" in result["facts"]


def test_resolve_diagnostic_found(mini_build: Path):
    node = parse_ref("@lathe[mini_drone#diagnostic.bake_missing]")
    result = resolve_ref(node, repo_root=mini_build)
    assert result["ok"] is True
    assert result["facts"]["severity"] == "warning"
    assert result["facts"]["stage"] == "surface"


def test_resolve_diagnostic_missing(mini_build: Path):
    node = parse_ref("@lathe[mini_drone#diagnostic.no_such_diag]")
    result = resolve_ref(node, repo_root=mini_build)
    assert result["ok"] is False
    assert result["facts"]["reason"] == "diagnostic_not_found"
    assert "available_diagnostic_ids" in result["facts"]


def test_resolve_part_found(mini_build: Path):
    node = parse_ref("@lathe[mini_drone#part.body]")
    result = resolve_ref(node, repo_root=mini_build)
    assert result["ok"] is True
    assert result["facts"]["part_id"] == "body"
    assert "rotor_fl" in result["facts"]["sibling_parts"]


def test_resolve_part_missing(mini_build: Path):
    node = parse_ref("@lathe[mini_drone#part.not_a_part]")
    result = resolve_ref(node, repo_root=mini_build)
    assert result["ok"] is False
    assert result["facts"]["reason"] == "part_not_found"


def test_resolve_missing_target(tmp_path: Path):
    node = parse_ref("@lathe[does_not_exist]")
    result = resolve_ref(node, repo_root=tmp_path)
    assert result["ok"] is False
    assert result["facts"]["reason"] == "target_not_found"


# ---------------------------------------------------------------------------
# Stale-ref warnings
# ---------------------------------------------------------------------------


def test_stale_ref_warning_when_build_report_missing(tmp_path: Path):
    empty_build = tmp_path / "empty_build"
    empty_build.mkdir()
    node = parse_ref("@lathe[empty_build]")
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        result = resolve_ref(node, repo_root=tmp_path)
    assert any(issubclass(w.category, StaleRefWarning) for w in captured)
    assert result["ok"] is False


def test_stale_ref_warning_on_asset_rename(mini_build: Path):
    # Ask for a different asset name than the one recorded in build_report.json.
    node = parse_ref("@lathe[mini_drone#asset.renamed_drone]")
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        resolve_ref(node, repo_root=mini_build)
    assert any(issubclass(w.category, StaleRefWarning) for w in captured)


# ---------------------------------------------------------------------------
# CLI smoke
# ---------------------------------------------------------------------------


def _cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "lathe.cli", "ref", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )


def test_cli_ref_parse_happy():
    result = _cli("parse", "@lathe[foo#asset.bar]")
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["ref"]["target"] == "foo"
    assert payload["ref"]["selector"] == {"kind": "asset", "id": "bar"}


def test_cli_ref_parse_phase_2_exits_2():
    result = _cli("parse", "@lathe[foo#part.body.face12]")
    assert result.returncode == 2
    payload = json.loads(result.stderr)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "phase_2_feature_not_yet_available"


def test_cli_ref_parse_traversal_exits_2():
    result = _cli("parse", "@lathe[../../etc]")
    assert result.returncode == 2
    payload = json.loads(result.stderr)
    assert payload["error"]["code"] == "path_traversal_rejected"
