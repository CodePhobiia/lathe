"""``lathe fmt`` subcommand: canonical source formatter.

Modes:

* default — rewrite each file in place; print a summary of files changed
* ``--check`` — don't write; exit non-zero if any file would change
* ``--stdout`` — write formatted output of a single file (or stdin) to stdout
* ``--dry-run`` — print a unified diff of the changes without writing

The heavy lifting lives in :mod:`lathe.formatter`; this module only
wires argument parsing to the formatter API.
"""

from __future__ import annotations

import difflib
import sys
from pathlib import Path

from ..errors import LatheError
from ..formatter import check_formatted, format_source
from ._common import _dump, _expand_files


def run_fmt(args) -> None:
    """Run fmt.

    Args:
        args: args argument.
    """
    mode_stdout = bool(getattr(args, "stdout", False))
    mode_check = bool(getattr(args, "check", False))
    mode_dry_run = bool(getattr(args, "dry_run", False))

    if mode_stdout:
        _run_stdout(args)
        return

    files = _expand_files(args.files) or _expand_files(["examples/*.lth"])
    if not files:
        _dump({"ok": True, "mode": _mode_label(args), "results": []})
        return

    results: list[dict] = []
    any_failed = False
    any_changed = False

    for file_name in files:
        path = Path(file_name)
        try:
            source = path.read_text(encoding="utf-8")
        except OSError as exc:
            any_failed = True
            results.append({"file": file_name, "ok": False, "message": str(exc)})
            continue
        try:
            is_canonical, canonical = check_formatted(source)
        except LatheError as exc:
            any_failed = True
            results.append({"file": file_name, "ok": False, "message": str(exc)})
            continue

        if is_canonical:
            results.append({"file": file_name, "ok": True, "changed": False})
            continue

        any_changed = True
        entry = {"file": file_name, "ok": True, "changed": True}

        if mode_dry_run:
            entry["diff"] = _unified_diff(source, canonical, file_name)
        elif mode_check:
            pass
        else:
            path.write_text(canonical, encoding="utf-8")

        results.append(entry)

    summary = {
        "ok": not any_failed,
        "mode": _mode_label(args),
        "changed": sum(1 for r in results if r.get("changed")),
        "total": len(results),
        "results": results,
    }
    _dump(summary)

    exit_code = 0
    if any_failed or (mode_check and any_changed):
        exit_code = 1
    raise SystemExit(exit_code)


def _run_stdout(args) -> None:
    if args.files:
        if len(args.files) != 1:
            print("fmt --stdout accepts at most one file", file=sys.stderr)
            raise SystemExit(2)
        source = Path(args.files[0]).read_text(encoding="utf-8")
    else:
        source = sys.stdin.read()
    try:
        formatted = format_source(source)
    except LatheError as exc:
        print(f"fmt error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    sys.stdout.write(formatted)


def _unified_diff(source: str, canonical: str, label: str) -> str:
    return "".join(
        difflib.unified_diff(
            source.splitlines(keepends=True),
            canonical.splitlines(keepends=True),
            fromfile=f"a/{label}",
            tofile=f"b/{label}",
        )
    )


def _mode_label(args) -> str:
    if getattr(args, "stdout", False):
        return "stdout"
    if getattr(args, "check", False):
        return "check"
    if getattr(args, "dry_run", False):
        return "dry_run"
    return "write"
