"""``lathe cache`` subcommand: inspect, clean, and warm the user build cache."""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from datetime import timedelta
from pathlib import Path
from typing import Any

from ..cache import (
    CacheEntry,
    cache_total_bytes,
    clean_cache,
    lathe_cache_dir,
    list_cache_entries,
    warm_cache,
)
from ..runtime_config import load_runtime_config
from ._common import _dump


def register(sub: argparse._SubParsersAction) -> None:
    """Register the ``cache`` subcommand on an existing argparse sub-parsers."""
    p = sub.add_parser(
        "cache",
        help="Inspect, clean, and warm the Lathe build cache",
        description=(
            "Inspect, clean, and warm the user-level Lathe build cache. "
            "The cache lives under ``LATHE_CACHE_DIR`` if set, otherwise "
            "the platform's standard user cache directory (see docs/cache.md)."
        ),
    )
    csub = p.add_subparsers(dest="cache_cmd", required=True)

    p_status = csub.add_parser("status", help="Summarize cache entries and total size")
    p_status.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    p_clean = csub.add_parser("clean", help="Delete cache entries")
    p_clean.add_argument("--asset", default=None, help="Only delete entries whose manifest asset matches")
    p_clean.add_argument("--older-than", dest="older_than", default=None, help="Duration, e.g. 7d, 24h, 30m")
    p_clean.add_argument("--dry-run", dest="dry_run", action="store_true", help="Print matches without deleting")
    p_clean.add_argument("--yes", "-y", action="store_true", help="Required for destructive clean (no --dry-run)")

    p_warm = csub.add_parser("warm", help="Build an asset (no-op if already cached)")
    p_warm.add_argument("file")
    p_warm.add_argument("asset")
    p_warm.add_argument("--runtime-config", default=None, help="Optional runtime config JSON file")


_DURATION_RE = re.compile(r"^\s*(\d+)\s*([smhdw])\s*$", re.IGNORECASE)
_DURATION_UNITS = {
    "s": 1,
    "m": 60,
    "h": 3600,
    "d": 86400,
    "w": 604800,
}


def _parse_duration(text: str) -> timedelta:
    match = _DURATION_RE.match(text)
    if not match:
        raise ValueError(f"invalid duration: {text!r} (expected e.g. 7d, 24h, 30m, 45s)")
    value = int(match.group(1))
    unit = match.group(2).lower()
    return timedelta(seconds=value * _DURATION_UNITS[unit])


def _entry_payload(entry: CacheEntry) -> dict[str, Any]:
    return {
        "key": entry.key,
        "size_bytes": entry.size_bytes,
        "mtime": entry.mtime,
        "asset": entry.asset_hint,
        "cache_version": entry.cache_version,
        "path": str(entry.path),
    }


def _human_bytes(n: int) -> str:
    value = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024.0 or unit == "TB":
            return f"{value:.1f}{unit}" if unit != "B" else f"{int(value)}B"
        value /= 1024.0
    return f"{value:.1f}TB"


def _run_status(args: argparse.Namespace) -> None:
    entries = list_cache_entries()
    total = sum(e.size_bytes for e in entries)
    per_asset: dict[str, dict[str, int]] = defaultdict(lambda: {"count": 0, "size_bytes": 0})
    for entry in entries:
        key = entry.asset_hint or "<unknown>"
        per_asset[key]["count"] += 1
        per_asset[key]["size_bytes"] += entry.size_bytes

    if getattr(args, "json", False):
        _dump(
            {
                "cache_dir": str(lathe_cache_dir()),
                "entry_count": len(entries),
                "total_bytes": total,
                "per_asset": dict(per_asset),
                "entries": [_entry_payload(e) for e in entries],
            }
        )
        return

    print(f"cache_dir: {lathe_cache_dir()}")
    print(f"entries:   {len(entries)}")
    print(f"size:      {_human_bytes(total)}")
    if per_asset:
        print("per-asset:")
        for asset, stats in sorted(per_asset.items()):
            print(f"  {asset:<32} {stats['count']:>4}  {_human_bytes(stats['size_bytes'])}")


def _run_clean(args: argparse.Namespace) -> None:
    asset = args.asset
    older_than = _parse_duration(args.older_than) if args.older_than else None
    dry_run = bool(args.dry_run)

    if not dry_run and not args.yes:
        _dump({"ok": False, "message": "clean requires --dry-run or --yes (safety gate)"})
        raise SystemExit(2)

    matched = clean_cache(asset=asset, older_than=older_than, dry_run=dry_run)
    _dump(
        {
            "ok": True,
            "dry_run": dry_run,
            "deleted" if not dry_run else "would_delete": [_entry_payload(e) for e in matched],
            "count": len(matched),
            "bytes": sum(e.size_bytes for e in matched),
        }
    )


def _run_warm(args: argparse.Namespace) -> None:
    source = Path(args.file)
    if not source.exists():
        _dump({"ok": False, "message": f"source file does not exist: {source}"})
        raise SystemExit(2)
    runtime_config = load_runtime_config(args.runtime_config) if args.runtime_config else None
    before = cache_total_bytes()
    try:
        entry = warm_cache(source, args.asset, runtime_config=runtime_config)
    except (OSError, RuntimeError, ValueError) as exc:
        _dump({"ok": False, "message": str(exc)})
        raise SystemExit(1) from exc
    after = cache_total_bytes()
    _dump(
        {
            "ok": True,
            "entry": _entry_payload(entry),
            "cache_bytes_before": before,
            "cache_bytes_after": after,
        }
    )


_CACHE_DISPATCH = {
    "status": _run_status,
    "clean": _run_clean,
    "warm": _run_warm,
}


def run_cache(args: argparse.Namespace) -> None:
    """Dispatch ``lathe cache <sub>``."""
    sub = getattr(args, "cache_cmd", None)
    handler = _CACHE_DISPATCH.get(sub)
    if handler is None:
        sys.stderr.write("unknown cache subcommand\n")
        raise SystemExit(2)
    handler(args)
