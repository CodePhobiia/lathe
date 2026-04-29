from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_DIR = REPO_ROOT / "examples" / "wonder" / "alchemist_observatory"
EXAMPLE_SCENE = EXAMPLE_DIR / "scene_graph.json"


def _cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "lathe.cli", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        check=False,
    )


def _png(path: Path, color: tuple[int, int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (2, 1), color).save(path)


def test_wonder_lock_camera_writes_expected_json(tmp_path: Path) -> None:
    out_path = tmp_path / "camera_lock.json"

    result = _cli(
        "wonder",
        "lock-camera",
        str(EXAMPLE_SCENE),
        "--camera-id",
        "camera_reveal",
        "--out",
        str(out_path),
    )

    assert result.returncode == 0, result.stderr
    assert out_path.exists()
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "lathe.camera_lock.v1"
    assert payload["camera_id"] == "camera_reveal"
    assert payload["camera_hash"].startswith("sha256:")


def test_wonder_compare_renders_writes_expected_json(tmp_path: Path) -> None:
    camera_lock = tmp_path / "camera_lock.json"
    before = tmp_path / "before.png"
    after = tmp_path / "after.png"
    out_path = tmp_path / "comparison.json"
    _png(before, (10, 20, 30))
    _png(after, (10, 20, 30))
    lock_result = _cli(
        "wonder",
        "lock-camera",
        str(EXAMPLE_SCENE),
        "--camera-id",
        "camera_reveal",
        "--out",
        str(camera_lock),
    )
    assert lock_result.returncode == 0, lock_result.stderr

    result = _cli(
        "wonder",
        "compare-renders",
        "--before",
        str(before),
        "--after",
        str(after),
        "--camera-lock",
        str(camera_lock),
        "--out",
        str(out_path),
    )

    assert result.returncode == 0, result.stderr
    assert out_path.exists()
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "lathe.render_comparison.v1"
    assert payload["camera_lock_status"] == "passed"
    assert payload["pixel_delta"]["changed_pixels"] == 0


def test_wonder_demo_before_after_writes_core_proxy_structure(tmp_path: Path) -> None:
    out_dir = tmp_path / "wonder_before_after"

    result = _cli(
        "wonder",
        "demo-before-after",
        str(EXAMPLE_DIR),
        "--out",
        str(out_dir),
    )

    assert result.returncode == 0, result.stderr
    assert (out_dir / "before" / "scene_graph.json").exists()
    assert (out_dir / "after" / "scene_graph.json").exists()
    assert (out_dir / "before" / "renders" / "camera_reveal" / "beauty.png").exists()
    assert (out_dir / "after" / "renders" / "camera_reveal" / "beauty.png").exists()
    assert (out_dir / "comparisons" / "camera_lock.json").exists()
    assert (out_dir / "comparisons" / "render_comparison.json").exists()
    assert (out_dir / "history" / "scene_history.json").exists()
    assert (out_dir / "reports" / "before_after_report.json").exists()
    assert (out_dir / "reports" / "before_after_report.md").exists()

    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["optional_lanes"]["blender"]["status"] == "skipped"
    assert payload["optional_lanes"]["blender"]["blocking"] is False
    assert payload["optional_lanes"]["roblox"]["status"] == "skipped"
    comparison = json.loads((out_dir / "comparisons" / "render_comparison.json").read_text(encoding="utf-8"))
    assert comparison["semantic_delta"]["status"] == "not_evaluated"
