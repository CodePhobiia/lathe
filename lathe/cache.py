"""User-level build-cache helpers (PERF-1, PERF-2, DXPOL-1).

Lives separately from ``lathe.executor`` so the cache-dir resolution,
listing, cleaning, and warm-up APIs are reusable from the CLI and from
tests without pulling the full build runtime.

The actual cache layout is owned by ``lathe.executor``: each build
writes into ``lathe_cache_dir() / "builds" / <cache_key>``. This module
only resolves the root and inspects what is already there; it never
writes a cache entry itself except indirectly via :func:`warm_cache`,
which delegates to the normal ``build_asset`` code path.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import time
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any


BUILDS_SUBDIR = "builds"


def lathe_cache_dir() -> Path:
    """Resolve the user-level cache directory for Lathe.

    Precedence:
      1. ``LATHE_CACHE_DIR`` environment variable (tilde-expanded).
      2. ``platformdirs.user_cache_dir("lathe")`` if ``platformdirs`` is
         importable.
      3. Platform fallback:
           * Linux / macOS: ``$XDG_CACHE_HOME/lathe`` or ``~/.cache/lathe``.
           * Windows:       ``%LOCALAPPDATA%\\lathe\\cache`` or
                            ``%USERPROFILE%\\.lathe\\cache``.

    Creates the directory if it does not exist and returns an absolute
    :class:`Path`.
    """
    override = os.environ.get("LATHE_CACHE_DIR")
    if override:
        root = Path(os.path.expanduser(override)).resolve()
    else:
        root = _resolve_default_cache_dir()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _resolve_default_cache_dir() -> Path:
    try:
        import platformdirs  # type: ignore

        return Path(platformdirs.user_cache_dir("lathe")).resolve()
    except ImportError:
        pass

    if sys.platform.startswith("win"):
        local_app = os.environ.get("LOCALAPPDATA")
        if local_app:
            return (Path(local_app) / "lathe" / "cache").resolve()
        user_profile = os.environ.get("USERPROFILE") or str(Path.home())
        return (Path(user_profile) / ".lathe" / "cache").resolve()

    xdg = os.environ.get("XDG_CACHE_HOME")
    if xdg:
        return (Path(os.path.expanduser(xdg)) / "lathe").resolve()
    return (Path.home() / ".cache" / "lathe").resolve()


@dataclass
class CacheEntry:
    """A single build-cache entry on disk."""

    key: str
    size_bytes: int
    mtime: float
    asset_hint: str | None
    cache_version: str
    path: Path


def _builds_root() -> Path:
    root = lathe_cache_dir() / BUILDS_SUBDIR
    root.mkdir(parents=True, exist_ok=True)
    return root


def _directory_size(path: Path) -> int:
    total = 0
    for sub in path.rglob("*"):
        try:
            if sub.is_file():
                total += sub.stat().st_size
        except OSError:
            continue
    return total


def _read_manifest(path: Path) -> dict[str, Any]:
    manifest = path / "manifest.json"
    if not manifest.is_file():
        return {}
    try:
        return json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _entry_from_dir(path: Path) -> CacheEntry:
    manifest = _read_manifest(path)
    asset_hint = None
    if isinstance(manifest, dict):
        asset_hint = manifest.get("asset") or manifest.get("asset_name")
        if not asset_hint:
            build = manifest.get("build") if isinstance(manifest.get("build"), dict) else None
            if build:
                asset_hint = build.get("asset") or build.get("asset_name")
    cache_version = ""
    if isinstance(manifest, dict):
        cache_version = str(manifest.get("cache_version") or manifest.get("BUILD_CACHE_VERSION") or "")
    try:
        mtime = path.stat().st_mtime
    except OSError:
        mtime = 0.0
    return CacheEntry(
        key=path.name,
        size_bytes=_directory_size(path),
        mtime=mtime,
        asset_hint=asset_hint if isinstance(asset_hint, str) else None,
        cache_version=cache_version,
        path=path,
    )


def list_cache_entries() -> list[CacheEntry]:
    """Return one :class:`CacheEntry` per immediate subdirectory of the builds root."""
    root = _builds_root()
    entries: list[CacheEntry] = []
    for child in sorted(root.iterdir()):
        if child.is_dir():
            entries.append(_entry_from_dir(child))
    return entries


def cache_total_bytes() -> int:
    """Sum of ``size_bytes`` across every cache entry."""
    return sum(entry.size_bytes for entry in list_cache_entries())


def clean_cache(
    *,
    asset: str | None = None,
    older_than: timedelta | None = None,
    dry_run: bool = False,
) -> list[CacheEntry]:
    """Delete cache entries matching the given filter.

    With no filter, every entry is eligible. Entries are only removed
    when ``dry_run`` is ``False``; in either mode the matched entries
    are returned so callers can report what was (or would be) deleted.
    """
    now = time.time()
    matched: list[CacheEntry] = []
    for entry in list_cache_entries():
        if asset is not None and entry.asset_hint != asset:
            continue
        if older_than is not None:
            age_seconds = now - entry.mtime
            if age_seconds < older_than.total_seconds():
                continue
        matched.append(entry)
    if not dry_run:
        for entry in matched:
            shutil.rmtree(entry.path, ignore_errors=True)
    return matched


def warm_cache(
    source: Path,
    asset: str,
    *,
    runtime_config: dict[str, Any] | None = None,
) -> CacheEntry:
    """Run a full build for ``asset`` if it is not already cached.

    Returns the :class:`CacheEntry` for the resulting (or pre-existing)
    cache directory. The build output is written under a temporary
    ``warm_*`` directory next to the source file and is removed after
    the build completes — only the cache entry survives.
    """
    from .parser import parse_file
    from .executor import build_asset

    source_path = Path(source).resolve()
    program = parse_file(str(source_path))
    tmp_out = source_path.parent / f"warm_{asset}_{int(time.time())}"
    try:
        build_asset(program, asset, str(tmp_out), runtime_config=runtime_config)
    finally:
        shutil.rmtree(tmp_out, ignore_errors=True)

    builds = _builds_root()
    latest: CacheEntry | None = None
    for entry in list_cache_entries():
        if entry.asset_hint and entry.asset_hint != asset:
            continue
        if latest is None or entry.mtime > latest.mtime:
            latest = entry
    if latest is None:
        raise RuntimeError(f"warm_cache: no cache entry produced for asset={asset!r} under {builds}")
    return latest


__all__ = [
    "BUILDS_SUBDIR",
    "CacheEntry",
    "cache_total_bytes",
    "clean_cache",
    "lathe_cache_dir",
    "list_cache_entries",
    "warm_cache",
]
