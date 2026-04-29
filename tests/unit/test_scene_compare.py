from __future__ import annotations

from pathlib import Path

from lathe.scene.compare import compare_renders
from PIL import Image


def _png(path: Path, pixels: list[tuple[int, int, int]]) -> None:
    image = Image.new("RGB", (len(pixels), 1))
    image.putdata(pixels)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def test_identical_pngs_produce_zero_changed_pixels_and_passed_status(tmp_path: Path) -> None:
    before = tmp_path / "before.png"
    after = tmp_path / "after.png"
    pixels = [(10, 20, 30), (40, 50, 60)]
    _png(before, pixels)
    _png(after, pixels)

    comparison, diagnostics = compare_renders(before, after)

    assert diagnostics == []
    assert comparison is not None
    assert comparison["status"] == "passed"
    assert comparison["pixel_delta"]["changed_pixels"] == 0
    assert comparison["pixel_delta"]["changed_ratio"] == 0.0
    assert comparison["semantic_delta"]["status"] == "not_evaluated"


def test_one_pixel_changed_counts_one_changed_pixel(tmp_path: Path) -> None:
    before = tmp_path / "before.png"
    after = tmp_path / "after.png"
    _png(before, [(10, 20, 30), (40, 50, 60)])
    _png(after, [(10, 20, 30), (41, 50, 60)])

    comparison, diagnostics = compare_renders(before, after)

    assert diagnostics == []
    assert comparison is not None
    assert comparison["pixel_delta"]["changed_pixels"] == 1
    assert comparison["pixel_delta"]["changed_ratio"] == 0.5


def test_dimension_mismatch_fails_clearly(tmp_path: Path) -> None:
    before = tmp_path / "before.png"
    after = tmp_path / "after.png"
    _png(before, [(10, 20, 30), (40, 50, 60)])
    _png(after, [(10, 20, 30)])

    comparison, diagnostics = compare_renders(before, after)

    assert comparison is None
    assert diagnostics
    assert diagnostics[0]["code"] == "RC1003"
    assert "dimensions must match" in diagnostics[0]["message"]


def test_comparison_includes_camera_lock_hash_when_provided(tmp_path: Path) -> None:
    before = tmp_path / "before.png"
    after = tmp_path / "after.png"
    _png(before, [(10, 20, 30)])
    _png(after, [(10, 20, 30)])
    camera_lock = {"camera_hash": "sha256:" + "a" * 64}

    comparison, diagnostics = compare_renders(before, after, camera_lock=camera_lock)

    assert diagnostics == []
    assert comparison is not None
    assert comparison["camera_lock_status"] == "passed"
    assert comparison["camera_hash"] == camera_lock["camera_hash"]
