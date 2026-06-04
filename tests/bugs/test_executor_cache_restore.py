"""Regression tests for the cache-restore atomicity fix (C1).

Before the fix, ``BuildExecutor._restore_cached_build`` called
``shutil.rmtree(out_dir)`` *before* ``shutil.copytree(cache_dir, out_dir)``.
A copytree failure in the middle of that sequence destroyed the user's
existing ``out_dir`` with no rollback. After the fix the restore stages
into a sibling temp dir and atomically renames; if copytree fails, the
original ``out_dir`` survives.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from lathe.cache_paths import CACHE_MANIFEST_FILENAME
from lathe.executor import BUILD_CACHE_VERSION, BuildExecutor


def _make_executor(out_dir: Path, cache_dir: Path, cache_key: str) -> BuildExecutor:
    """Build a minimal stub BuildExecutor without going through __init__.

    We only exercise ``_restore_cached_build`` here, which depends on
    ``self.cache_dir``, ``self.out_dir``, and ``self.cache_key`` only.
    """
    executor = BuildExecutor.__new__(BuildExecutor)
    executor.out_dir = out_dir
    executor.cache_dir = cache_dir
    executor.cache_key = cache_key
    return executor


def _seed_cache(cache_dir: Path, cache_key: str) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / "build_report.json").write_text(
        json.dumps({"asset": "demo", "ok": True}), encoding="utf-8"
    )
    (cache_dir / CACHE_MANIFEST_FILENAME).write_text(
        json.dumps({"cache_version": BUILD_CACHE_VERSION, "cache_key": cache_key}),
        encoding="utf-8",
    )
    (cache_dir / "stages").mkdir()
    (cache_dir / "stages" / "marker.txt").write_text("from-cache", encoding="utf-8")


def test_restore_cached_build_succeeds(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache" / "abc"
    out_dir = tmp_path / "out"
    cache_key = "abc"
    _seed_cache(cache_dir, cache_key)

    executor = _make_executor(out_dir, cache_dir, cache_key)
    report = executor._restore_cached_build()

    assert report is not None
    assert report["out_dir"] == str(out_dir)
    assert (out_dir / "build_report.json").is_file()
    assert (out_dir / "stages" / "marker.txt").read_text(encoding="utf-8") == "from-cache"


def test_restore_cached_build_preserves_out_dir_on_copy_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache_dir = tmp_path / "cache" / "abc"
    out_dir = tmp_path / "out"
    cache_key = "abc"
    _seed_cache(cache_dir, cache_key)

    out_dir.mkdir(parents=True)
    (out_dir / "user_artifact.bin").write_bytes(b"do-not-lose-me")
    (out_dir / "nested").mkdir()
    (out_dir / "nested" / "data.txt").write_text("important", encoding="utf-8")

    real_copytree = shutil.copytree

    def failing_copytree(src: Any, dst: Any, *args: Any, **kwargs: Any) -> Any:
        # Simulate a partial copy then a failure midway.
        Path(dst).mkdir(parents=True, exist_ok=True)
        (Path(dst) / "partial.bin").write_bytes(b"partial")
        raise OSError("disk full")

    monkeypatch.setattr(shutil, "copytree", failing_copytree)

    executor = _make_executor(out_dir, cache_dir, cache_key)
    report = executor._restore_cached_build()

    # Restore must report failure and leave the original out_dir intact.
    assert report is None
    assert out_dir.exists()
    assert (out_dir / "user_artifact.bin").read_bytes() == b"do-not-lose-me"
    assert (out_dir / "nested" / "data.txt").read_text(encoding="utf-8") == "important"

    # No half-restored cache contents leaked into the original tree.
    assert not (out_dir / "build_report.json").exists()
    assert not (out_dir / "stages").exists()

    # And no orphaned staging/displaced sibling directories left behind.
    siblings = [
        child
        for child in out_dir.parent.iterdir()
        if child != out_dir and child.name.startswith((".restore.", ".displaced."))
    ]
    assert siblings == []

    # Sanity: the real shutil.copytree still works after monkeypatch teardown.
    monkeypatch.setattr(shutil, "copytree", real_copytree)
