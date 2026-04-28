"""User-level build-cache helpers (PERF-1, PERF-2, DXPOL-1).

Lives separately from ``lathe.executor`` so the cache-dir resolution,
listing, cleaning, and warm-up APIs are reusable from the CLI and from
tests without pulling the full build runtime.

The actual cache layout is owned by ``lathe.executor``: each build
writes into ``lathe_cache_dir() / "builds" / <cache_key>``. This module
only resolves the root and inspects what is already there; it never
writes build payloads itself except indirectly via :func:`warm_cache`,
which delegates to the normal ``build_asset`` code path. The migration
helper only backfills root cache metadata manifests from existing
build/package evidence.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import time
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any

from .cache_paths import (
    BACKFILLED_CACHE_MANIFEST_SCHEMA,
    BUILDS_SUBDIR,
    CACHE_MANIFEST_FILENAME,
    CANONICAL_CACHE_MANIFEST_SCHEMA,
    lathe_cache_dir,
)


@dataclass
class CacheEntry:
    """A single build-cache entry on disk."""

    key: str
    size_bytes: int
    mtime: float
    asset_hint: str | None
    cache_version: str
    path: Path
    variant_hint: str | None = None
    backend_stack: str | None = None
    source_fingerprint: str | None = None
    created_time: float | None = None
    metadata_source: str | None = None


@dataclass
class CacheMigrationResult:
    """A cache entry considered by metadata-manifest migration."""

    key: str
    path: Path
    status: str
    reason: str
    asset_hint: str | None = None


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


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _manifest_from_build_report(path: Path) -> dict[str, Any]:
    report = _read_json(path / "build_report.json")
    if not report:
        return {}
    metadata: dict[str, Any] = {
        "asset": report.get("asset"),
        "kind": report.get("kind"),
        "backend_stack": report.get("backend_stack"),
        "metadata_source": "build_report.json",
    }
    selected_backends = report.get("selected_backends")
    if isinstance(selected_backends, dict):
        metadata["selected_backends"] = selected_backends
    manifest_path = report.get("manifest_path")
    if isinstance(manifest_path, str):
        package_manifest = _read_json(path / manifest_path)
    else:
        package_manifest = _read_json(path / "stages" / "package" / "package_manifest.json")
    if package_manifest:
        if not isinstance(metadata.get("asset"), str):
            metadata["asset"] = package_manifest.get("asset_id")
        metadata["variant"] = package_manifest.get("variant")
    trace_path = package_manifest.get("trace_path") if package_manifest else None
    if isinstance(trace_path, str):
        trace = _read_json(path / trace_path)
        if trace:
            metadata["source_fingerprint"] = trace.get("normalized_hash") or trace.get("source_hash")
    return metadata


def _manifest_from_package_manifest(path: Path) -> dict[str, Any]:
    package_manifest = _read_json(path / "stages" / "package" / "package_manifest.json")
    if not package_manifest:
        return {}
    metadata: dict[str, Any] = {
        "asset": package_manifest.get("asset_id"),
        "variant": package_manifest.get("variant"),
        "metadata_source": "stages/package/package_manifest.json",
    }
    trace_path = package_manifest.get("trace_path")
    if isinstance(trace_path, str):
        trace = _read_json(path / trace_path)
        if trace:
            metadata["source_fingerprint"] = trace.get("normalized_hash") or trace.get("source_hash")
            backend_versions = trace.get("backend_versions")
            if isinstance(backend_versions, dict):
                metadata["backend_stack"] = ",".join(
                    f"{stage}:{backend_versions[stage]}" for stage in sorted(backend_versions)
                )
    return metadata


def _read_manifest(path: Path) -> dict[str, Any]:
    manifest = _read_json(path / CACHE_MANIFEST_FILENAME)
    if manifest:
        manifest.setdefault("metadata_source", CACHE_MANIFEST_FILENAME)
        return manifest
    report_manifest = _manifest_from_build_report(path)
    if report_manifest:
        return report_manifest
    return _manifest_from_package_manifest(path)


def _manifest_is_complete(manifest: dict[str, Any]) -> bool:
    if manifest.get("schema") not in {CANONICAL_CACHE_MANIFEST_SCHEMA, BACKFILLED_CACHE_MANIFEST_SCHEMA}:
        return False
    required = ("cache_key", "asset", "backend_stack", "cache_version", "source_fingerprint", "created_time")
    return all(manifest.get(field) not in (None, "") for field in required)


def _metadata_str(metadata: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = metadata.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _metadata_backend_stack(value: Any) -> str | None:
    if isinstance(value, str) and value:
        return value
    if isinstance(value, list):
        return ",".join(str(item) for item in value if str(item))
    if isinstance(value, dict):
        stack_id = _metadata_str(value, "id", "name")
        if stack_id:
            return stack_id
        return ",".join(f"{key}:{value[key]}" for key in sorted(value))
    return None


def _current_cache_version() -> str:
    from .executor import BUILD_CACHE_VERSION

    return BUILD_CACHE_VERSION


def _migration_manifest(path: Path) -> dict[str, Any] | None:
    metadata = _manifest_from_build_report(path) or _manifest_from_package_manifest(path)
    asset = _metadata_str(metadata, "asset", "asset_name", "asset_id")
    backend_stack = _metadata_backend_stack(metadata.get("backend_stack"))
    source_fingerprint = _metadata_str(metadata, "source_fingerprint", "source_hash", "normalized_hash")
    if not asset or not backend_stack or not source_fingerprint:
        return None
    try:
        created_time = path.stat().st_mtime
    except OSError:
        created_time = time.time()
    return {
        "schema": BACKFILLED_CACHE_MANIFEST_SCHEMA,
        "cache_version": _current_cache_version(),
        "cache_key": path.name,
        "asset": asset,
        "variant": _metadata_str(metadata, "variant", "variant_name"),
        "kind": _metadata_str(metadata, "kind"),
        "backend_stack": backend_stack,
        "source_fingerprint": source_fingerprint,
        "created_time": created_time,
        "migrated_time": time.time(),
        "metadata_source": CACHE_MANIFEST_FILENAME,
        "migrated_from": metadata.get("metadata_source"),
    }


def _entry_from_dir(path: Path) -> CacheEntry:
    manifest = _read_manifest(path)
    asset_hint = _metadata_str(manifest, "asset", "asset_name", "asset_id")
    if not asset_hint:
        build = manifest.get("build") if isinstance(manifest.get("build"), dict) else None
        if build:
            asset_hint = _metadata_str(build, "asset", "asset_name", "asset_id")
    cache_version = str(manifest.get("cache_version") or manifest.get("BUILD_CACHE_VERSION") or "")
    created_value = manifest.get("created_time")
    try:
        created_time = float(created_value) if created_value is not None else None
    except (TypeError, ValueError):
        created_time = None
    backend_stack = _metadata_backend_stack(manifest.get("backend_stack"))
    try:
        mtime = path.stat().st_mtime
    except OSError:
        mtime = 0.0
    return CacheEntry(
        key=path.name,
        size_bytes=_directory_size(path),
        mtime=mtime,
        asset_hint=asset_hint,
        cache_version=cache_version,
        path=path,
        variant_hint=_metadata_str(manifest, "variant", "variant_name"),
        backend_stack=backend_stack,
        source_fingerprint=_metadata_str(manifest, "source_fingerprint", "source_hash", "normalized_hash"),
        created_time=created_time,
        metadata_source=_metadata_str(manifest, "metadata_source"),
    )


def list_cache_entries() -> list[CacheEntry]:
    """Return one :class:`CacheEntry` per immediate subdirectory of the builds root."""
    root = _builds_root()
    entries: list[CacheEntry] = []
    for child in sorted(root.iterdir()):
        if child.is_dir() and not child.is_symlink():
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


def migrate_cache_manifests(*, dry_run: bool = False) -> list[CacheMigrationResult]:
    """Backfill root metadata manifests for cache entries that can be inferred."""
    results: list[CacheMigrationResult] = []
    for child in sorted(_builds_root().iterdir()):
        if not child.is_dir() or child.is_symlink():
            continue
        existing = _read_json(child / CACHE_MANIFEST_FILENAME)
        if existing and _manifest_is_complete(existing):
            results.append(
                CacheMigrationResult(
                    key=child.name,
                    path=child,
                    status="skipped",
                    reason="manifest already complete",
                    asset_hint=_metadata_str(existing, "asset", "asset_name", "asset_id"),
                )
            )
            continue
        manifest = _migration_manifest(child)
        if manifest is None:
            results.append(
                CacheMigrationResult(
                    key=child.name,
                    path=child,
                    status="skipped",
                    reason="metadata could not be inferred",
                )
            )
            continue
        status = "would_migrate" if dry_run else "migrated"
        if not dry_run:
            try:
                (child / CACHE_MANIFEST_FILENAME).write_text(
                    json.dumps(manifest, indent=2) + "\n",
                    encoding="utf-8",
                )
            except OSError as exc:
                results.append(
                    CacheMigrationResult(
                        key=child.name,
                        path=child,
                        status="skipped",
                        reason=f"failed to write manifest: {exc}",
                        asset_hint=_metadata_str(manifest, "asset"),
                    )
                )
                continue
        results.append(
            CacheMigrationResult(
                key=child.name,
                path=child,
                status=status,
                reason="backfilled cache manifest",
                asset_hint=_metadata_str(manifest, "asset"),
            )
        )
    return results


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
    from .executor import build_asset
    from .parser import parse_file

    source_path = Path(source).resolve()
    program = parse_file(str(source_path))
    with tempfile.TemporaryDirectory(prefix=f"warm_{asset}_", dir=source_path.parent) as tmp_out:
        build_asset(program, asset, tmp_out, runtime_config=runtime_config)

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
    "BACKFILLED_CACHE_MANIFEST_SCHEMA",
    "BUILDS_SUBDIR",
    "CACHE_MANIFEST_FILENAME",
    "CANONICAL_CACHE_MANIFEST_SCHEMA",
    "CacheEntry",
    "CacheMigrationResult",
    "cache_total_bytes",
    "clean_cache",
    "lathe_cache_dir",
    "list_cache_entries",
    "migrate_cache_manifests",
    "warm_cache",
]
