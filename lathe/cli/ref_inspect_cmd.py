"""``lathe ref inspect <token>`` — parse, resolve, and print JSON facts (REF-9).

Exit 0 on success, 2 on bad token (parse error), 3 on unresolved ref.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

from ..ref import RefParseError, parse_ref, resolve_ref


def run_ref_inspect(args) -> None:
    """Parse and resolve a Lathe ref token."""
    token = args.token
    try:
        node = parse_ref(token)
    except RefParseError as exc:
        prefix = f"[{exc.code}] "
        raw = str(exc)
        message = raw[len(prefix) :] if raw.startswith(prefix) else raw
        payload = {
            "ok": False,
            "stage": "parse",
            "error": {"code": exc.code, "message": message, "token": exc.token},
        }
        print(json.dumps(payload, indent=2), file=sys.stderr)
        raise SystemExit(2) from exc

    repo_root = Path(getattr(args, "repo_root", None) or Path.cwd())
    result = resolve_ref(node, repo_root=repo_root)
    payload = {
        "ok": bool(result.get("ok")),
        "ref": asdict(node),
        "resolution": result,
    }
    if not payload["ok"]:
        print(json.dumps(payload, indent=2), file=sys.stderr)
        raise SystemExit(3)
    print(json.dumps(payload, indent=2))
