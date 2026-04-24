"""``lathe parse`` subcommand: emit raw parser output for a source file."""

from __future__ import annotations

from pathlib import Path

from ._common import _dump, _expand_files


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


def run_fmt(args) -> None:
    """Run fmt.

    Args:
        args: args argument.
    """
    from jsonschema import Draft202012Validator, ValidationError as JSONSchemaValidationError

    from ..errors import LatheError
    from ..normalizer import normalize_program
    from ..parser import parse_file
    from ..schema import get_schema

    files = _expand_files(args.files) or _expand_files(["examples/*.lth"])
    results = []
    ok = True
    validator = Draft202012Validator(get_schema())
    for file_name in files:
        try:
            normalized = normalize_program(parse_file(Path(file_name)))
            validator.validate(normalized)
            results.append({"file": file_name, "ok": True})
        except (LatheError, JSONSchemaValidationError, OSError) as exc:
            ok = False
            results.append({"file": file_name, "ok": False, "message": str(exc)})
    _dump({"ok": ok, "mode": "check" if args.check else "scaffold", "results": results})
    raise SystemExit(0 if ok else 1)


def run_schema(_args) -> None:
    """Run schema.

    Args:
        _args: _args argument.
    """
    from ..schema import get_schema

    _dump(get_schema())
