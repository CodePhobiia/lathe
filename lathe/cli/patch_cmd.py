"""``lathe patch`` subcommand: apply patch_api operations to sources."""

from __future__ import annotations

from pathlib import Path

from ._common import _dump, _emit_error


def run_patch(args) -> None:
    """Run patch.

    Args:
        args: args argument.
    """
    from ..parser import parse_file
    from ..patch_api import (
        add_benchmark_fixture,
        add_component_to_family,
        change_repair_policy,
        freeze_dimension,
        update_material_palette,
        widen_search_bounds,
    )

    program = parse_file(Path(args.file))
    if args.op == "add_component_to_family":
        payload = add_component_to_family(program, args.target, args.value)
    elif args.op == "change_repair_policy":
        payload = change_repair_policy(program, args.target, args.value)
    elif args.op == "update_material_palette":
        payload = update_material_palette(program, args.target, args.value)
    elif args.op == "widen_search_bounds":
        if args.value2 is None:
            _emit_error(
                "lathe.cli.patch.missing_value2",
                "--value2 is required for widen_search_bounds",
                "Re-run with --value2 LOWER:UPPER, for example --value2 0.8:1.2.",
                exit_code=2,
                source_path=str(args.file),
            )
        if ":" not in args.value2:
            _emit_error(
                "lathe.cli.patch.invalid_value2",
                "--value2 must be LOWER:UPPER for widen_search_bounds",
                "Re-run with --value2 LOWER:UPPER using numeric lower and upper bounds.",
                exit_code=2,
                source_path=str(args.file),
            )
        lower_text, upper_text = args.value2.split(":", 1)
        try:
            lower = float(lower_text)
            upper = float(upper_text)
        except ValueError:
            _emit_error(
                "lathe.cli.patch.invalid_value2",
                "--value2 must contain numeric LOWER:UPPER bounds for widen_search_bounds",
                "Re-run with --value2 LOWER:UPPER, for example --value2 0.8:1.2.",
                exit_code=2,
                source_path=str(args.file),
            )
        payload = widen_search_bounds(program, args.target, args.value, lower, upper)
    elif args.op == "freeze_dimension":
        payload = freeze_dimension(program, args.target, args.value)
    elif args.op == "add_benchmark_fixture":
        payload = add_benchmark_fixture(program, args.target, args.value)
    else:
        _emit_error(
            "lathe.cli.patch.unknown_op",
            f"Unsupported patch op: {args.op}",
            "See lathe patch --help for supported operations.",
            exit_code=2,
            source_path=str(args.file),
        )
    _dump(payload)
