"""``lathe parse`` subcommand: emit raw parser output for a source file."""

from __future__ import annotations

from pathlib import Path

from ._common import _dump


def run_parse(args) -> None:
    """Run parse.

    Args:
        args: args argument.
    """
    from ..parser import parse_file

    _dump(parse_file(Path(args.file)))


def run_normalize(args) -> None:
    """Run normalize.

    Args:
        args: args argument.
    """
    from ..normalizer import normalize_program
    from ..parser import parse_file

    _dump(normalize_program(parse_file(Path(args.file))))


def run_schema(_args) -> None:
    """Run schema.

    Args:
        _args: _args argument.
    """
    from ..schema import get_schema

    _dump(get_schema())
