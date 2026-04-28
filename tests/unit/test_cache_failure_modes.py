"""Cache/filesystem failure-mode coverage."""

from __future__ import annotations

import json
import shutil
import threading
from pathlib import Path

import pytest
from lathe import cache as cache_mod
from lathe.executor import BUILD_CACHE_VERSION, BuildExecutor


@pytest.fixture
def tmp_cache(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    root = tmp_path / "cache"
    monkeypatch.setenv("LATHE_CACHE_DIR", str(root))
    return root


def _executor_for_cache(cache_dir: Path, out_dir: Path, *, cache_key: str = "cache-key") -> BuildExecutor:
    executor = object.__new__(BuildExecutor)
    executor.cache_dir = cache_dir
    executor.out_dir = out_dir
    executor.cache_key = cache_key
    return executor


def test_list_cache_entries_skips_symlinked_cache_directories(tmp_cache: Path, tmp_path: Path) -> None:
    outside = tmp_path / "outside-cache-entry"
    outside.mkdir()
    (outside / "manifest.json").write_text(json.dumps({"asset": "outside"}), encoding="utf-8")
    builds = tmp_cache / "builds"
    builds.mkdir(parents=True)
    link = builds / "linked-entry"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except (NotImplementedError, OSError):
        pytest.skip("symlinks are unavailable in this environment")

    assert cache_mod.list_cache_entries() == []
    assert outside.exists()


def test_cache_entry_permission_error_reading_manifest_degrades_to_unknown(
    tmp_cache: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entry = tmp_cache / "builds" / "entry"
    entry.mkdir(parents=True)
    (entry / "manifest.json").write_text(json.dumps({"asset": "courier_drone"}), encoding="utf-8")
    (entry / "blob.bin").write_bytes(b"x")
    original_read_text = Path.read_text

    def deny_manifest(path: Path, *args: object, **kwargs: object) -> str:
        if path == entry / "manifest.json":
            raise PermissionError("denied")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", deny_manifest)

    [cached] = cache_mod.list_cache_entries()
    assert cached.key == "entry"
    assert cached.asset_hint is None
    assert cached.metadata_source is None


def test_restore_cached_build_ignores_entry_missing_report_without_touching_output(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache-entry"
    out_dir = tmp_path / "out"
    cache_dir.mkdir()
    out_dir.mkdir()
    sentinel = out_dir / "keep.txt"
    sentinel.write_text("existing output", encoding="utf-8")
    executor = _executor_for_cache(cache_dir, out_dir)

    assert executor._restore_cached_build() is None
    assert sentinel.read_text(encoding="utf-8") == "existing output"


def test_restore_cached_build_ignores_corrupt_report_without_touching_output(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache-entry"
    out_dir = tmp_path / "out"
    cache_dir.mkdir()
    (cache_dir / "build_report.json").write_text("{not json", encoding="utf-8")
    out_dir.mkdir()
    sentinel = out_dir / "keep.txt"
    sentinel.write_text("existing output", encoding="utf-8")
    executor = _executor_for_cache(cache_dir, out_dir)

    assert executor._restore_cached_build() is None
    assert sentinel.read_text(encoding="utf-8") == "existing output"


def test_restore_cached_build_ignores_version_mismatch_without_touching_output(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache-entry"
    out_dir = tmp_path / "out"
    cache_dir.mkdir()
    (cache_dir / "build_report.json").write_text(json.dumps({"asset": "courier_drone"}), encoding="utf-8")
    (cache_dir / "manifest.json").write_text(
        json.dumps({"cache_version": "old", "cache_key": "cache-key"}),
        encoding="utf-8",
    )
    out_dir.mkdir()
    sentinel = out_dir / "keep.txt"
    sentinel.write_text("existing output", encoding="utf-8")
    executor = _executor_for_cache(cache_dir, out_dir)

    assert executor._restore_cached_build() is None
    assert sentinel.read_text(encoding="utf-8") == "existing output"


def test_restore_cached_build_ignores_cache_key_mismatch_without_touching_output(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache-entry"
    out_dir = tmp_path / "out"
    cache_dir.mkdir()
    (cache_dir / "build_report.json").write_text(json.dumps({"asset": "courier_drone"}), encoding="utf-8")
    (cache_dir / "manifest.json").write_text(
        json.dumps({"cache_version": BUILD_CACHE_VERSION, "cache_key": "other-key"}),
        encoding="utf-8",
    )
    out_dir.mkdir()
    sentinel = out_dir / "keep.txt"
    sentinel.write_text("existing output", encoding="utf-8")
    executor = _executor_for_cache(cache_dir, out_dir)

    assert executor._restore_cached_build() is None
    assert sentinel.read_text(encoding="utf-8") == "existing output"


def test_restore_cached_build_treats_copy_failure_as_cache_miss(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache_dir = tmp_path / "cache-entry"
    out_dir = tmp_path / "out"
    cache_dir.mkdir()
    (cache_dir / "build_report.json").write_text(json.dumps({"asset": "courier_drone"}), encoding="utf-8")
    (cache_dir / "manifest.json").write_text(
        json.dumps({"cache_version": BUILD_CACHE_VERSION, "cache_key": "cache-key"}),
        encoding="utf-8",
    )
    executor = _executor_for_cache(cache_dir, out_dir)

    def fail_copytree(*_args: object, **_kwargs: object) -> None:
        raise PermissionError("cache entry unreadable")

    monkeypatch.setattr(shutil, "copytree", fail_copytree)

    assert executor._restore_cached_build() is None


def test_restore_cached_build_accepts_valid_manifest_and_updates_report_out_dir(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache-entry"
    out_dir = tmp_path / "out"
    cache_dir.mkdir()
    (cache_dir / "build_report.json").write_text(json.dumps({"asset": "courier_drone"}), encoding="utf-8")
    (cache_dir / "manifest.json").write_text(
        json.dumps({"cache_version": BUILD_CACHE_VERSION, "cache_key": "cache-key"}),
        encoding="utf-8",
    )
    executor = _executor_for_cache(cache_dir, out_dir)

    report = executor._restore_cached_build()

    assert report == {"asset": "courier_drone", "out_dir": str(out_dir)}
    persisted = json.loads((out_dir / "build_report.json").read_text(encoding="utf-8"))
    assert persisted["out_dir"] == str(out_dir)


def test_persist_build_cache_tolerates_concurrent_writers_to_same_entry(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache" / "builds" / "same-key"
    errors: list[BaseException] = []

    def worker(index: int) -> None:
        out_dir = tmp_path / f"out-{index}"
        out_dir.mkdir()
        (out_dir / "build_report.json").write_text(json.dumps({"worker": index}), encoding="utf-8")
        (out_dir / f"payload-{index}.bin").write_bytes(b"x" * 8)
        executor = _executor_for_cache(cache_dir, out_dir)
        executor._cache_manifest = lambda: {
            "cache_version": BUILD_CACHE_VERSION,
            "cache_key": "cache-key",
            "worker": index,
        }
        try:
            executor._persist_build_cache()
        except BaseException as exc:  # pragma: no cover - asserted below
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(index,)) for index in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    assert (cache_dir / "build_report.json").exists()
    assert (cache_dir / "manifest.json").exists()
    payload_files = sorted(path.name for path in cache_dir.glob("payload-*.bin"))
    assert len(payload_files) == 1


def test_persist_build_cache_cleans_failed_staging_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache_dir = tmp_path / "cache" / "builds" / "same-key"
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    (out_dir / "build_report.json").write_text("{}", encoding="utf-8")
    executor = _executor_for_cache(cache_dir, out_dir)
    executor._cache_manifest = lambda: {"cache_version": BUILD_CACHE_VERSION}

    def race_copytree(*_args: object, **_kwargs: object) -> None:
        raise FileExistsError("simulated concurrent writer")

    monkeypatch.setattr(shutil, "copytree", race_copytree)

    executor._persist_build_cache()

    assert not cache_dir.exists()
    assert not list(cache_dir.parent.glob(".*.tmp"))
