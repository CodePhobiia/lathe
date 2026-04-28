"""``lathe telemetry`` subcommand: manage opt-in build-ping telemetry."""

from __future__ import annotations

import argparse
import sys

from .. import telemetry as _telemetry
from ._common import _dump


def register(sub: argparse._SubParsersAction) -> None:
    """Register the ``telemetry`` subcommand on an existing argparse sub-parsers."""
    p = sub.add_parser(
        "telemetry",
        help="Manage opt-in anonymous build-ping telemetry",
        description=(
            "Manage opt-in anonymous build-ping telemetry (Plan 09 Phase 10b). "
            "Default is disabled. See docs/telemetry.md for the exact payload "
            "and retention policy."
        ),
    )
    tsub = p.add_subparsers(dest="telemetry_cmd", required=True)

    p_enable = tsub.add_parser(
        "enable",
        help="Enable anonymous build-ping telemetry",
    )
    p_enable.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Skip the interactive confirmation prompt",
    )

    tsub.add_parser("disable", help="Disable telemetry (salt is preserved)")
    tsub.add_parser("status", help="Show current telemetry state")
    tsub.add_parser("clear", help="Delete the local telemetry config file")


def _run_enable(args) -> None:
    if not getattr(args, "yes", False):
        sys.stdout.write("This will enable anonymous opt-in telemetry. Proceed? [y/N] ")
        sys.stdout.flush()
        try:
            resp = sys.stdin.readline().strip().lower()
        except (OSError, ValueError):
            resp = ""
        if resp not in {"y", "yes"}:
            _dump({"ok": False, "state": "unchanged", "message": "Cancelled."})
            return

    cfg = _telemetry.enable()
    salt = cfg.get("user_salt") or ""
    _dump(
        {
            "ok": True,
            "state": "enabled",
            "salt_prefix": salt[:4] if salt else None,
            "ingest_url": _telemetry.TELEMETRY_INGEST_URL,
        }
    )


def _run_disable(_args) -> None:
    _telemetry.disable()
    _dump({"ok": True, "state": "disabled"})


def _run_status(_args) -> None:
    _dump(_telemetry.status())


def _run_clear(_args) -> None:
    existed = _telemetry.clear()
    _dump(
        {
            "ok": True,
            "state": "unset",
            "removed": existed,
        }
    )


_TELEMETRY_DISPATCH = {
    "enable": _run_enable,
    "disable": _run_disable,
    "status": _run_status,
    "clear": _run_clear,
}


def run_telemetry(args) -> None:
    """Dispatch ``lathe telemetry <sub>``."""
    sub = getattr(args, "telemetry_cmd", None)
    handler = _TELEMETRY_DISPATCH.get(sub)
    if handler is None:
        raise SystemExit(2)
    handler(args)
