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


@pytest.fixture
def tmp_cache(monkeypatch, tmp_path) -> Path:
    """Redirect LATHE_CACHE_DIR to a pristine ``tmp_path`` for the test."""
    monkeypatch.setenv("LATHE_CACHE_DIR", str(tmp_path))
    return tmp_path


def _write_entry(root: Path, key: str, *, asset: str | None, bytes_: int = 64, mtime: float | None = None) -> Path:
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
    monkeypatch.setattr(cache_mod.Path, "home", staticmethod(lambda: tmp_path))
    # Force the platformdirs branch off so we hit the fallback.
    monkeypatch.setitem(sys.modules, "platformdirs", None)
    resolved = cache_mod._resolve_default_cache_dir()
    assert resolved == (tmp_path / ".cache" / "lathe").resolve()


def test_lathe_cache_dir_windows_fallback(monkeypatch, tmp_path):
    monkeypatch.delenv("LATHE_CACHE_DIR", raising=False)
    local_app = tmp_path / "LocalAppData"
    local_app.mkdir()
    monkeypatch.setenv("LOCALAPPDATA", str(local_app))
    monkeypatch.setattr(sys, "platform", "win32", raising=False)
    monkeypatch.setitem(sys.modules, "platformdirs", None)
    resolved = cache_mod._resolve_default_cache_dir()
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


def test_clean_cache_filters_by_age(tmp_cache):
    now = time.time()
    _write_entry(tmp_cache, "old", asset="courier_drone", mtime=now - 86400 * 10)
    _write_entry(tmp_cache, "new", asset="courier_drone", mtime=now)
    matched = cache_mod.clean_cache(older_than=timedelta(days=7))
    assert [e.key for e in matched] == ["old"]
    remaining = {e.key for e in cache_mod.list_cache_entries()}
    assert remaining == {"new"}


def test_cli_cache_status_smoke(tmp_cache):
    _write_entry(tmp_cache, "aaa", asset="courier_drone", bytes_=42)
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
