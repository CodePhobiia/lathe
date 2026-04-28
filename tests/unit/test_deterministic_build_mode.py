from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from lathe.executor import build_asset
from lathe.parser import parse_file

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE = REPO_ROOT / "examples" / "api" / "socket.lth"
ASSET = "api_socket"
OFFLINE_RUNTIME_CONFIG = REPO_ROOT / "examples" / "runtime_configs" / "offline.json"
CANONICAL_GALLERY_BUILDS = (
    ("examples/industrial_crate.lth", "industrial_crate"),
    ("examples/courier_drone.lth", "courier_drone"),
    ("examples/courier_drone.lth", "courier_drone_mobile"),
    ("examples/reconstruct_courier_from_mesh.lth", "reconstruct_courier_from_mesh"),
    ("examples/console_terminal_mobile_adapt.lth", "console_terminal_mobile"),
)


def _selector_manifest(build_dir: Path) -> dict:
    return json.loads((build_dir / "selector_manifest.json").read_text(encoding="utf-8"))


def _package_hashes(build_dir: Path) -> dict[str, str]:
    manifest = json.loads(
        (build_dir / "stages" / "package" / "package_manifest.json").read_text(encoding="utf-8")
    )
    return dict(sorted(manifest["output_hashes"].items()))


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.slow
def test_fresh_builds_have_stable_selector_and_package_hashes(tmp_path: Path) -> None:
    program = parse_file(SOURCE)
    first_dir = tmp_path / "first" / ASSET
    second_dir = tmp_path / "second" / ASSET

    first_report = build_asset(program, ASSET, first_dir)
    second_report = build_asset(program, ASSET, second_dir)

    assert first_report["certified"] is True
    assert second_report["certified"] is True
    first_manifest = _selector_manifest(first_dir)
    second_manifest = _selector_manifest(second_dir)
    assert first_manifest["buildHash"] == second_manifest["buildHash"]
    assert first_manifest["packageHash"] == second_manifest["packageHash"]
    assert _package_hashes(first_dir) == _package_hashes(second_dir)


@pytest.mark.slow
@pytest.mark.parametrize("source,asset", CANONICAL_GALLERY_BUILDS)
def test_canonical_gallery_cli_builds_offline_deterministic(source: str, asset: str, tmp_path: Path) -> None:
    """Every canonical gallery asset should build through the documented CLI.

    This exercises a clean output directory, checked-in refs, the no-network
    reference provider config, and ``--deterministic`` report emission.
    """
    out_root = tmp_path / "dist"
    cmd = [
        sys.executable,
        "-m",
        "lathe.cli",
        "build",
        str(REPO_ROOT / source),
        asset,
        "--out",
        str(out_root),
        "--runtime-config",
        str(OFFLINE_RUNTIME_CONFIG),
        "--report",
        "json",
        "--deterministic",
    ]
    env = os.environ.copy()
    env["LATHE_ALLOW_EXTERNAL_OUT"] = "1"

    result = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=360,
        check=False,
    )
    build_dir = out_root / asset
    if result.returncode != 0:
        pytest.fail(
            f"canonical deterministic build failed for {source}::{asset} with rc={result.returncode}\n"
            f"stdout={result.stdout[-1000:]}\nstderr={result.stderr[-1000:]}"
        )

    report = _read_json(build_dir / "build_report.json")
    selector = _selector_manifest(build_dir)
    package_hashes = _package_hashes(build_dir)

    assert report["certified"] is True
    assert report["asset"] == asset
    assert selector["buildHash"]
    assert selector["packageHash"]
    assert package_hashes
