"""``lathe ref`` subcommand dispatcher (Phase-1 slice).

Only ``lathe ref parse <token>`` is wired up in this wave; ``inspect``,
``diff``, ``copy``, and ``planes`` are Phase-2 deliverables (REF-9..12).
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict

from ..ref import RefParseError, parse_ref


def run_ref_parse(args) -> None:
    """Run `lathe ref parse <token>`.

    Exit 0 on success with the parsed :class:`~lathe.ref.RefNode` rendered
    as JSON on stdout. Exit 2 on :class:`~lathe.ref.RefParseError` with a
    structured error payload on stderr.
    """

    token = args.token
    try:
        node = parse_ref(token)
    except RefParseError as exc:
        prefix = f"[{exc.code}] "
        raw = str(exc)
        message = raw[len(prefix):] if raw.startswith(prefix) else raw
        payload = {
            "ok": False,
            "error": {
                "code": exc.code,
                "message": message,
                "token": exc.token,
            },
        }
        print(json.dumps(payload, indent=2, sort_keys=False), file=sys.stderr)
        raise SystemExit(2)

    payload = {
        "ok": True,
        "ref": asdict(node),
    }
    print(json.dumps(payload, indent=2, sort_keys=False))


def run_ref(args) -> None:
    """Dispatcher for the ``ref`` command family."""

    sub = getattr(args, "ref_cmd", None)
    if sub == "parse":
        run_ref_parse(args)
        return
    if sub == "inspect":
        from .ref_inspect_cmd import run_ref_inspect
        run_ref_inspect(args)
        return
    if sub == "planes":
        from .ref_planes_cmd import run_ref_planes
        run_ref_planes(args)
        return
    if sub == "diff":
        from .ref_diff_cmd import run_ref_diff
        run_ref_diff(args)
        return
    if sub == "copy":
        from .ref_copy_cmd import run_ref_copy
        run_ref_copy(args)
        return
    # argparse is configured with required=True on the subparsers, so
    # reaching this branch means a programmer error rather than bad input.
    raise SystemExit(2)
