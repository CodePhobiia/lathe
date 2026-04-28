"""Dependency-light cache path helpers.

Kept separate from :mod:`lathe.cache` so runtime orchestration can locate the
build cache without importing cache commands that warm builds through parser
and executor entry points.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

BUILDS_SUBDIR = "builds"
CACHE_MANIFEST_FILENAME = "manifest.json"
BACKFILLED_CACHE_MANIFEST_SCHEMA = "lathe.cache_manifest.backfill.v1"
CANONICAL_CACHE_MANIFEST_SCHEMA = "lathe.cache_manifest.v1"


def lathe_cache_dir() -> Path:
    """Resolve the user-level cache directory for Lathe."""
    override = os.environ.get("LATHE_CACHE_DIR")
    if override:
        root = Path(override).expanduser().resolve()
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
        return (Path(xdg).expanduser() / "lathe").resolve()
    return (Path.home() / ".cache" / "lathe").resolve()


__all__ = [
    "BACKFILLED_CACHE_MANIFEST_SCHEMA",
    "BUILDS_SUBDIR",
    "CACHE_MANIFEST_FILENAME",
    "CANONICAL_CACHE_MANIFEST_SCHEMA",
    "lathe_cache_dir",
]
