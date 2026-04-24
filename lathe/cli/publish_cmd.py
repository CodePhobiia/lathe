"""``lathe publish`` subcommand (BL-31, Plan 08 Phase 1).

Runs the publish runner against a completed build directory. Intended for
callers who want to publish a previously-built asset without re-running the
full pipeline.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from ..publish import get_driver
from ..runtime_config import load_runtime_config
from ._common import _dump


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``publish`` subcommand onto ``subparsers``."""
    p = subparsers.add_parser(
        "publish",
        help="Publish a completed build to a configured target",
        description=(
            "Publish artifacts + signed manifest from a completed build directory. "
            "Drivers: local_fs, s3, supabase, git_lfs. Target configuration comes "
            "from --runtime-config (runtime_config.publish.*) with --target overriding."
        ),
    )
    p.add_argument("build_dir", help="Directory produced by `lathe build --out`")
    p.add_argument("--target", default=None, help="Publish target id (e.g. local_fs, s3)")
    p.add_argument("--runtime-config", default=None, help="Optional runtime config JSON file")
    p.add_argument("--signing-key", default=None, help="ed25519 private key path (overrides runtime_config)")
    p.add_argument("--target-dir", default=None, help="LocalFSDriver destination directory")
    p.add_argument("--bucket", default=None, help="S3 / Supabase bucket override")
    p.add_argument("--asset", default=None, help="Asset name override")
    p.add_argument("--version", default=None, help="Asset version override")


def run_publish(args: argparse.Namespace) -> None:
    """Run the ``publish`` CLI subcommand."""
    build_dir = Path(args.build_dir)
    if not build_dir.exists():
        _dump({"ok": False, "message": f"build_dir does not exist: {build_dir}"})
        raise SystemExit(1)

    runtime_config = (
        load_runtime_config(args.runtime_config) if args.runtime_config else load_runtime_config(None)
    )
    publish_cfg = dict(runtime_config.get("publish") or {})

    target = args.target or publish_cfg.get("target")
    if not target:
        _dump({"ok": False, "message": "no publish target configured; pass --target or runtime_config.publish.target"})
        raise SystemExit(2)

    target_config: dict[str, Any] = dict(publish_cfg)
    target_config["target"] = target
    if args.signing_key:
        target_config["signing_key"] = args.signing_key
    if args.target_dir:
        target_config["target_dir"] = args.target_dir
    if args.bucket:
        target_config["bucket"] = args.bucket
    if args.asset:
        target_config["asset"] = args.asset
    if args.version:
        target_config["version"] = args.version

    try:
        driver = get_driver(str(target))
    except ValueError as exc:
        _dump({"ok": False, "message": str(exc)})
        raise SystemExit(1) from exc

    try:
        result = driver.publish(build_dir, target_config)
    except (ValueError, RuntimeError) as exc:
        _dump({"ok": False, "driver": str(target), "message": str(exc)})
        raise SystemExit(1) from exc

    _dump(
        {
            "ok": True,
            "driver": result.get("driver", str(target)),
            "manifest_uri": result.get("manifest_uri"),
            "signature_uri": result.get("signature_uri"),
            "published_files": result.get("published_files", []),
        }
    )
