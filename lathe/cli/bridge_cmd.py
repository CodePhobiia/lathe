"""``lathe bridge`` subcommand: operate the Codex/Blender bridge."""

from __future__ import annotations

from pathlib import Path

from ..runtime_config import load_runtime_config
from ._common import _dump


def run_bridge(args) -> None:
    """Run bridge.

    Args:
        args: args argument.
    """
    from ..bridge.blender_plan import build_bridge_doctor, build_bridge_plan

    runtime_config = load_runtime_config(args.runtime_config) if getattr(args, "runtime_config", None) else load_runtime_config(None)
    if args.bridge_cmd == "doctor":
        _dump(build_bridge_doctor(runtime_config))
        return
    if args.bridge_cmd == "plan":
        from ..parser import parse_file as _parse_file
        from ..resolver import materialize_asset as _materialize_asset

        program = _parse_file(Path(args.file))
        asset = _materialize_asset(program, args.name, execution_profile_override=args.execution_profile)
        _dump(build_bridge_plan(asset, runtime_config))
        return
    raise SystemExit(2)
