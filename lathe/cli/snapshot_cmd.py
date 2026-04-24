"""``lathe snapshot`` subcommand: emit a canonical build snapshot (RPT-4)."""

from __future__ import annotations

import argparse
from pathlib import Path

from ..snapshot import SNAPSHOT_FILENAME, write_snapshot
from ._common import _emit_error


def register(sub: argparse._SubParsersAction) -> None:
    """Register ``lathe snapshot`` on an existing argparse sub-parsers."""
    p = sub.add_parser(
        "snapshot",
        help="Emit a canonical hash-based snapshot for a completed build",
        description=(
            "RPT-4 (V0.2 E4): write a small JSON sidecar that hashes each "
            "stage bundle in BUILD_DIR. Deterministic under --deterministic. "
            "Exit codes: 0 = ok; 2 = BUILD_DIR missing or not a directory."
        ),
    )
    p.add_argument("build_dir", help="Completed build directory (e.g. dist/courier_drone)")
    p.add_argument(
        "--out",
        default=None,
        help=f"Snapshot path (default: <build_dir>/{SNAPSHOT_FILENAME})",
    )
    p.add_argument(
        "--deterministic",
        action="store_true",
        help="Zero the emitted timestamp for byte-stable output",
    )


def run_snapshot(args: argparse.Namespace) -> None:
    """Dispatch ``lathe snapshot``."""
    build_dir = Path(args.build_dir)
    if not build_dir.is_dir():
        _emit_error(
            "lathe.cli.snapshot.missing_build_dir",
            f"build directory does not exist: {build_dir}",
            "Run `lathe build` first, or point --out at a real dir.",
            exit_code=2,
        )
        return
    out_path = Path(args.out) if getattr(args, "out", None) else None
    path = write_snapshot(
        build_dir,
        out_path=out_path,
        deterministic=bool(getattr(args, "deterministic", False)),
    )
    print(str(path))
