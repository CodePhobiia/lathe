"""Unit tests for the user-level build-cache helpers (``lathe.cache``)."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import timedelta
from pathlib import Path

import pytest
from lathe import cache as cache_mod
from lathe import cache_paths as cache_paths_mod


@pytest.fixture
def tmp_cache(monkeypatch, tmp_path) -> Path:
    """Redirect LATHE_CACHE_DIR to a pristine ``tmp_path`` for the test."""
    monkeypatch.setenv("LATHE_CACHE_DIR", str(tmp_path))
    return tmp_path


def _write_entry(
    root: Path, key: str, *, asset: str | None, bytes_: int = 64, mtime: float | None = None
) -> Path:
    builds = root / "builds" / key
    builds.mkdir(parents=True, exist_ok=True)
    (builds / "blob.bin").write_bytes(b"x" * bytes_)
    if asset is not None:
        (builds / "manifest.json").write_text(
            json.dumps({"asset": asset, "cache_version": "v10_rc2"}),
            encoding="utf-8",
        )
    if mtime is not None:
        import os

        os.utime(builds, (mtime, mtime))
    return builds


def _write_report_entry(
    root: Path,
    key: str,
    *,
    asset: str,
    bytes_: int = 64,
    backend_stack: str | dict[str, str] = "lathe.stack.reference_v1",
) -> Path:
    builds = root / "builds" / key
    package_dir = builds / "stages" / "package"
    package_dir.mkdir(parents=True, exist_ok=True)
    (builds / "blob.bin").write_bytes(b"x" * bytes_)
    (builds / "build_report.json").write_text(
        json.dumps(
            {
                "asset": asset,
                "kind": "prop",
                "backend_stack": backend_stack,
                "manifest_path": "stages/package/package_manifest.json",
            }
        ),
        encoding="utf-8",
    )
    (package_dir / "package_manifest.json").write_text(
        json.dumps(
            {
                "asset_id": asset,
                "trace_path": "stages/package/trace_manifest.json",
            }
        ),
        encoding="utf-8",
    )
    (package_dir / "trace_manifest.json").write_text(
        json.dumps({"normalized_hash": f"normalized-{asset}"}),
        encoding="utf-8",
    )
    return builds


def test_lathe_cache_dir_respects_env(monkeypatch, tmp_path):
    target = tmp_path / "explicit"
    monkeypatch.setenv("LATHE_CACHE_DIR", str(target))
    resolved = cache_mod.lathe_cache_dir()
    assert resolved == target.resolve()
    assert resolved.is_dir()


def test_lathe_cache_dir_expands_tilde(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("LATHE_CACHE_DIR", "~/lathe_cache_tilde")
    resolved = cache_mod.lathe_cache_dir()
    assert resolved == (tmp_path / "lathe_cache_tilde").resolve()


def test_lathe_cache_dir_linux_fallback(monkeypatch, tmp_path):
    monkeypatch.delenv("LATHE_CACHE_DIR", raising=False)
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(sys, "platform", "linux", raising=False)
    monkeypatch.setattr(cache_paths_mod.Path, "home", staticmethod(lambda: tmp_path))
    # Force the platformdirs branch off so we hit the fallback.
    monkeypatch.setitem(sys.modules, "platformdirs", None)
    resolved = cache_paths_mod._resolve_default_cache_dir()
    assert resolved == (tmp_path / ".cache" / "lathe").resolve()


def test_lathe_cache_dir_windows_fallback(monkeypatch, tmp_path):
    monkeypatch.delenv("LATHE_CACHE_DIR", raising=False)
    local_app = tmp_path / "LocalAppData"
    local_app.mkdir()
    monkeypatch.setenv("LOCALAPPDATA", str(local_app))
    monkeypatch.setattr(sys, "platform", "win32", raising=False)
    monkeypatch.setitem(sys.modules, "platformdirs", None)
    resolved = cache_paths_mod._resolve_default_cache_dir()
    assert resolved == (local_app / "lathe" / "cache").resolve()


def test_list_cache_entries_empty(tmp_cache):
    assert cache_mod.list_cache_entries() == []
    assert cache_mod.cache_total_bytes() == 0


def test_cache_total_bytes_sums_entries(tmp_cache):
    _write_entry(tmp_cache, "aaa", asset="courier_drone", bytes_=100)
    _write_entry(tmp_cache, "bbb", asset="industrial_crate", bytes_=200)
    entries = cache_mod.list_cache_entries()
    assert len(entries) == 2
    assert cache_mod.cache_total_bytes() == sum(e.size_bytes for e in entries)
    # Sanity: each entry reports > 0 bytes.
    assert all(e.size_bytes >= 100 for e in entries)


def test_clean_cache_dry_run_does_not_delete(tmp_cache):
    _write_entry(tmp_cache, "aaa", asset="courier_drone")
    _write_entry(tmp_cache, "bbb", asset="industrial_crate")
    matched = cache_mod.clean_cache(dry_run=True)
    assert len(matched) == 2
    # Nothing actually removed.
    assert len(cache_mod.list_cache_entries()) == 2


def test_clean_cache_filters_by_asset(tmp_cache):
    _write_entry(tmp_cache, "aaa", asset="courier_drone")
    _write_entry(tmp_cache, "bbb", asset="industrial_crate")
    matched = cache_mod.clean_cache(asset="courier_drone")
    assert [e.asset_hint for e in matched] == ["courier_drone"]
    remaining = cache_mod.list_cache_entries()
    assert [e.asset_hint for e in remaining] == ["industrial_crate"]


def test_cache_entry_reads_current_build_report_layout(tmp_cache):
    _write_report_entry(tmp_cache, "aaa", asset="courier_drone")
    entries = cache_mod.list_cache_entries()
    assert len(entries) == 1
    entry = entries[0]
    assert entry.asset_hint == "courier_drone"
    assert entry.backend_stack == "lathe.stack.reference_v1"
    assert entry.source_fingerprint == "normalized-courier_drone"
    assert entry.metadata_source == "build_report.json"


def test_cache_entry_reads_backend_stack_id_from_current_report_object(tmp_cache):
    _write_report_entry(
        tmp_cache,
        "aaa",
        asset="courier_drone",
        backend_stack={"id": "lathe.stack.hard_surface_game_asset_v1", "name": "Hard surface"},
    )
    [entry] = cache_mod.list_cache_entries()
    assert entry.backend_stack == "lathe.stack.hard_surface_game_asset_v1"


def test_clean_cache_asset_filter_uses_current_build_report_layout(tmp_cache):
    _write_report_entry(tmp_cache, "aaa", asset="courier_drone")
    _write_report_entry(tmp_cache, "bbb", asset="industrial_crate")
    matched = cache_mod.clean_cache(asset="courier_drone", dry_run=True)
    assert [e.key for e in matched] == ["aaa"]
    assert {e.key for e in cache_mod.list_cache_entries()} == {"aaa", "bbb"}


def test_corrupt_root_manifest_falls_back_to_build_report(tmp_cache):
    entry = _write_report_entry(tmp_cache, "aaa", asset="courier_drone")
    (entry / "manifest.json").write_text("{not json", encoding="utf-8")
    [cached] = cache_mod.list_cache_entries()
    assert cached.asset_hint == "courier_drone"
    assert cached.metadata_source == "build_report.json"


def test_persist_build_cache_writes_canonical_manifest(tmp_cache, tmp_path):
    from lathe.executor import BUILD_CACHE_VERSION, BuildExecutor
    from lathe.parser import parse_file

    root = Path(__file__).resolve().parents[2]
    program = parse_file(root / "examples" / "courier_drone.lth")
    executor = BuildExecutor(program, "courier_drone", tmp_path / "out" / "courier_drone")
    executor.cache_dir = tmp_cache / "builds" / "new-entry"
    executor.out_dir.mkdir(parents=True)
    (executor.out_dir / "build_report.json").write_text("{}", encoding="utf-8")

    executor._persist_build_cache()

    manifest = json.loads((executor.cache_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema"] == "lathe.cache_manifest.v1"
    assert manifest["cache_version"] == BUILD_CACHE_VERSION
    assert manifest["asset"] == "courier_drone"
    assert manifest["cache_key"] == executor.cache_key
    assert manifest["source_fingerprint"]


def test_build_executor_resolves_cache_root_after_env_override(monkeypatch, tmp_path):
    from lathe.executor import BuildExecutor
    from lathe.parser import parse_file

    root = Path(__file__).resolve().parents[2]
    custom_cache = tmp_path / "custom-cache"
    monkeypatch.setenv("LATHE_CACHE_DIR", str(custom_cache))
    program = parse_file(root / "examples" / "api" / "socket.lth")

    executor = BuildExecutor(program, "api_socket", tmp_path / "out" / "api_socket")

    assert executor.cache_dir.is_relative_to(custom_cache / "builds")


def test_cache_manifest_records_required_identity_fields(tmp_path):
    from lathe.executor import BUILD_CACHE_VERSION, BuildExecutor
    from lathe.parser import parse_file

    root = Path(__file__).resolve().parents[2]
    program = parse_file(root / "examples" / "courier_drone.lth")
    executor = BuildExecutor(program, "courier_drone_mobile", tmp_path / "out" / "courier_drone_mobile")

    manifest = executor._cache_manifest()

    assert manifest["asset"] == "courier_drone_mobile"
    assert manifest["variant"] == "courier_drone_mobile"
    assert manifest["backend_stack"] == executor.backend_stack
    assert manifest["cache_version"] == BUILD_CACHE_VERSION
    assert manifest["source_fingerprint"]
    assert isinstance(manifest["created_time"], float)


def test_list_cache_entries_exposes_required_identity_fields(tmp_cache):
    entry = _write_entry(tmp_cache, "aaa", asset="courier_drone")
    manifest_path = entry / "manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload.update(
        {
            "variant": "courier_drone_mobile",
            "backend_stack": "lathe.stack.hard_surface_game_asset_v1",
            "source_fingerprint": "normalized-hash",
            "created_time": 123.5,
        }
    )
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")

    [cached] = cache_mod.list_cache_entries()

    assert cached.asset_hint == "courier_drone"
    assert cached.variant_hint == "courier_drone_mobile"
    assert cached.backend_stack == "lathe.stack.hard_surface_game_asset_v1"
    assert cached.cache_version == "v10_rc2"
    assert cached.source_fingerprint == "normalized-hash"
    assert cached.created_time == 123.5


def test_migrate_cache_manifests_dry_run_reports_without_writing(tmp_cache):
    entry = _write_report_entry(tmp_cache, "aaa", asset="courier_drone")

    results = cache_mod.migrate_cache_manifests(dry_run=True)

    assert [(result.key, result.status, result.asset_hint) for result in results] == [
        ("aaa", "would_migrate", "courier_drone")
    ]
    assert not (entry / "manifest.json").exists()


def test_migrate_cache_manifests_backfills_inferable_legacy_entry(tmp_cache):
    from lathe.executor import BUILD_CACHE_VERSION

    entry = _write_report_entry(tmp_cache, "aaa", asset="courier_drone")

    results = cache_mod.migrate_cache_manifests()

    assert [(result.key, result.status, result.asset_hint) for result in results] == [
        ("aaa", "migrated", "courier_drone")
    ]
    manifest = json.loads((entry / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema"] == cache_mod.BACKFILLED_CACHE_MANIFEST_SCHEMA
    assert manifest["cache_version"] == BUILD_CACHE_VERSION
    assert manifest["cache_key"] == "aaa"
    assert manifest["asset"] == "courier_drone"
    assert manifest["backend_stack"] == "lathe.stack.reference_v1"
    assert manifest["source_fingerprint"] == "normalized-courier_drone"
    assert manifest["metadata_source"] == "manifest.json"
    assert manifest["migrated_from"] == "build_report.json"

    [cached] = cache_mod.list_cache_entries()
    assert cached.asset_hint == "courier_drone"
    assert cached.cache_version == BUILD_CACHE_VERSION
    assert cached.metadata_source == "manifest.json"


def test_migrate_cache_manifests_skips_complete_manifest(tmp_cache):
    entry = _write_entry(tmp_cache, "aaa", asset="courier_drone")
    payload = json.loads((entry / "manifest.json").read_text(encoding="utf-8"))
    payload.update(
        {
            "schema": cache_mod.CANONICAL_CACHE_MANIFEST_SCHEMA,
            "cache_key": "aaa",
            "backend_stack": "lathe.stack.reference_v1",
            "source_fingerprint": "normalized-courier_drone",
            "created_time": 123.5,
        }
    )
    (entry / "manifest.json").write_text(json.dumps(payload), encoding="utf-8")

    [result] = cache_mod.migrate_cache_manifests()

    assert result.status == "skipped"
    assert result.reason == "manifest already complete"


def test_cli_cache_migrate_backfills_legacy_entry(tmp_cache):
    _write_report_entry(tmp_cache, "aaa", asset="courier_drone")
    result = subprocess.run(
        [sys.executable, "-m", "lathe.cli", "cache", "migrate"],
        capture_output=True,
        text=True,
        env={**__import__("os").environ, "LATHE_CACHE_DIR": str(tmp_cache)},
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["migrated_count"] == 1
    assert payload["results"][0]["status"] == "migrated"
    assert (tmp_cache / "builds" / "aaa" / "manifest.json").is_file()


def test_clean_cache_filters_by_age(tmp_cache):
    now = time.time()
    _write_entry(tmp_cache, "old", asset="courier_drone", mtime=now - 86400 * 10)
    _write_entry(tmp_cache, "new", asset="courier_drone", mtime=now)
    matched = cache_mod.clean_cache(older_than=timedelta(days=7))
    assert [e.key for e in matched] == ["old"]
    remaining = {e.key for e in cache_mod.list_cache_entries()}
    assert remaining == {"new"}


def test_cli_cache_status_smoke(tmp_cache):
    _write_report_entry(tmp_cache, "aaa", asset="courier_drone", bytes_=42)
    result = subprocess.run(
        [sys.executable, "-m", "lathe.cli", "cache", "status", "--json"],
        capture_output=True,
        text=True,
        env={**__import__("os").environ, "LATHE_CACHE_DIR": str(tmp_cache)},
        check=False,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["entry_count"] >= 1
    assert payload["total_bytes"] >= 42
    assert payload["entries"][0]["asset"] == "courier_drone"
    assert payload["entries"][0]["metadata_source"] == "build_report.json"
    assert "courier_drone" in payload["per_asset"]
