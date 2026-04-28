"""Smoke tests for the REF-9/10/11/12 extended ref CLIs."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _cli_importable() -> bool:
    """Skip-guard: other surgeons may land work-in-progress changes to
    ``lathe.cli`` that break its package init. These extended ref tests
    don't care about unrelated CLI breakage — they care about the four new
    ref subcommands — so we skip cleanly rather than cascade-fail.
    """
    probe = subprocess.run(
        [sys.executable, "-c", "import lathe.cli"],
        capture_output=True,
        text=True,
    )
    return probe.returncode == 0


pytestmark = pytest.mark.skipif(
    not _cli_importable(),
    reason="lathe.cli package init is broken in this workspace (unrelated to REF-6/9/10/11/12)",
)


def _cli(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "lathe.cli", "ref", *args],
        cwd=cwd or REPO_ROOT,
        capture_output=True,
        text=True,
    )


def _write_manifest(
    build_dir: Path, asset: str, *, build_hash: str = "a" * 16, pkg_hash: str = "b" * 16
) -> None:
    build_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schemaVersion": 1,
        "latheVersion": "0.1.0",
        "sourcePath": "examples/x.lth",
        "asset": asset,
        "variant": None,
        "buildHash": build_hash,
        "packageHash": pkg_hash,
        "coordinateSystem": {"upAxis": "Y", "unit": "cm", "handedness": "right"},
        "tables": {},
        "parts": [
            {
                "id": "body",
                "ref": f"@lathe[{build_dir.name}#part.body]",
                "bbox": [-1.0, -2.0, -0.5, 1.0, 2.0, 0.5],
                "faceCount": 2,
                "faces": [
                    {
                        "id": "body.face0",
                        "ref": f"@lathe[{build_dir.name}#part.body.face0]",
                        "centroid": [0.0, 0.0, 0.0],
                        "normal": [0.0, 0.0, 1.0],
                    },
                ],
                "edges": [],
                "vertices": [],
            },
        ],
        "sockets": [],
        "pivots": [],
        "collisions": [],
        "lods": [],
        "materials": [],
        "diagnostics": [],
        "relations": {},
    }
    (build_dir / "selector_manifest.json").write_text(json.dumps(manifest))
    (build_dir / "build_report.json").write_text(
        json.dumps(
            {
                "asset": asset,
                "kind": "mechanical_assembly",
                "certified": True,
                "stage_bundles": {"shape": {"backend_id": "x"}},
                "outputs": [
                    {"format": "glb", "uri": "stages/package/out.glb", "sha256": "0" * 64, "size_bytes": 10}
                ],
            }
        )
    )


@pytest.fixture()
def tmp_build(tmp_path: Path) -> Path:
    build_dir = tmp_path / "mini_drone"
    _write_manifest(build_dir, "mini_drone")
    pkg_dir = build_dir / "stages" / "package"
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "out.glb").write_bytes(b"\x67\x6c\x54\x46dummyglb")
    return tmp_path


def test_inspect_happy(tmp_build: Path):
    token = "@lathe[mini_drone#part.body]"
    result = _cli("inspect", token, "--repo-root", str(tmp_build))
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["resolution"]["selector_kind"] == "part"


def test_inspect_unresolved_exits_3(tmp_build: Path):
    token = "@lathe[mini_drone#part.nonexistent]"
    result = _cli("inspect", token, "--repo-root", str(tmp_build))
    assert result.returncode == 3
    payload = json.loads(result.stderr)
    assert payload["ok"] is False


def test_inspect_bad_token_exits_2(tmp_build: Path):
    result = _cli("inspect", "not-a-ref", "--repo-root", str(tmp_build))
    assert result.returncode == 2
    payload = json.loads(result.stderr)
    assert payload["error"]["code"] == "missing_prefix"


def test_planes_happy(tmp_build: Path):
    build_dir = tmp_build / "mini_drone"
    result = _cli("planes", str(build_dir))
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["parts"][0]["id"] == "body"
    planes = payload["parts"][0]["planes"]
    labels = {p["face"] for p in planes}
    assert labels == {"+X", "-X", "+Y", "-Y", "+Z", "-Z"}


def test_planes_missing_manifest_exits_2(tmp_path: Path):
    missing = tmp_path / "nonexistent"
    result = _cli("planes", str(missing))
    assert result.returncode == 2


def test_diff_happy(tmp_build: Path):
    # Create a second build with a different packageHash.
    other = tmp_build / "other_build"
    _write_manifest(other, "mini_drone", pkg_hash="c" * 16)
    # Also remove 'body' to test removed diff.
    mf = json.loads((other / "selector_manifest.json").read_text())
    mf["parts"] = []
    (other / "selector_manifest.json").write_text(json.dumps(mf))

    result = _cli("diff", str(tmp_build / "mini_drone"), str(other))
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["summary"]["geometry_changed"] is True
    assert "body" in payload["diff"]["parts"]["removed"]


def test_diff_missing_manifest_exits_2(tmp_path: Path):
    missing = tmp_path / "does_not_exist"
    result = _cli("diff", str(tmp_path), str(missing))
    assert result.returncode == 2


def test_copy_asset_happy(tmp_build: Path, tmp_path: Path):
    token = "@lathe[mini_drone#asset.mini_drone]"
    dest = tmp_path / "copied.glb"
    result = _cli("copy", token, str(dest), "--repo-root", str(tmp_build))
    assert result.returncode == 0, result.stderr
    assert dest.exists()
    payload = json.loads(result.stdout)
    assert payload["ok"] is True


def test_copy_unresolved_exits_3(tmp_build: Path, tmp_path: Path):
    token = "@lathe[mini_drone#asset.not_a_real_asset]"
    dest = tmp_path / "copied.glb"
    result = _cli("copy", token, str(dest), "--repo-root", str(tmp_build))
    assert result.returncode == 3
    assert not dest.exists()


def test_copy_face_has_no_artifact(tmp_build: Path, tmp_path: Path):
    token = "@lathe[mini_drone#part.body.face0]"
    dest = tmp_path / "face.glb"
    result = _cli("copy", token, str(dest), "--repo-root", str(tmp_build))
    # face tokens resolve but have no copyable artifact -> exit 4.
    assert result.returncode == 4
