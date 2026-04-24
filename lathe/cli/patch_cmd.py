"""``lathe patch`` subcommand: apply patch_api operations to sources."""

from __future__ import annotations

from pathlib import Path

from ._common import _dump


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
            raise SystemExit("--value2 is required for widen_search_bounds")
        if ":" not in args.value2:
            raise SystemExit("--value2 must be LOWER:UPPER for widen_search_bounds")
        lower_text, upper_text = args.value2.split(":", 1)
        payload = widen_search_bounds(program, args.target, args.value, float(lower_text), float(upper_text))
    elif args.op == "freeze_dimension":
        payload = freeze_dimension(program, args.target, args.value)
    elif args.op == "add_benchmark_fixture":
        payload = add_benchmark_fixture(program, args.target, args.value)
    else:
        raise SystemExit(2)
    _dump(payload)
