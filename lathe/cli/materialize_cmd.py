"""``lathe materialize`` subcommand.

Resolve and apply variant patches to produce a concrete asset shape
without running the downstream pipeline.
"""

from __future__ import annotations

from pathlib import Path

from ._common import _diff_objects, _dump


def run_materialize(args) -> None:
    """Run materialize.

    Args:
        args: args argument.
    """
    from ..parser import parse_file
    from ..resolver import materialize_asset

    program = parse_file(Path(args.file))
    _dump(materialize_asset(program, args.name, execution_profile_override=args.execution_profile))


def run_diff_asset(args) -> None:
    """Run diff asset.

    Args:
        args: args argument.
    """
    from ..parser import parse_file as _parse_file
    from ..resolver import materialize_asset as _materialize_asset

    asset_a = _materialize_asset(_parse_file(Path(args.file_a)), args.name_a)
    asset_b = _materialize_asset(_parse_file(Path(args.file_b)), args.name_b)
    _dump(_diff_objects(asset_a, asset_b))
