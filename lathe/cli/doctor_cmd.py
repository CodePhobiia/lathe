"""``lathe doctor`` subcommand: report environment/provider availability."""

from __future__ import annotations

from ..runtime_config import load_runtime_config
from ._common import _dump


def run_doctor(args) -> None:
    """Run doctor.

    Args:
        args: args argument.
    """
    from . import collect_doctor_report, dump_doctor_json, format_doctor_report

    runtime_config = load_runtime_config(args.runtime_config) if args.runtime_config else load_runtime_config(None)
    report = collect_doctor_report(runtime_config)
    print(dump_doctor_json(report) if args.json else format_doctor_report(report))


def run_backends(_args) -> None:
    """Run backends.

    Args:
        _args: _args argument.
    """
    from ..backends import list_backends, list_stacks

    _dump({"stacks": list_stacks(), "backends": list_backends()})


def run_shape_providers(_args) -> None:
    """Run shape providers.

    Args:
        _args: _args argument.
    """
    from ..shape_providers import list_shape_providers

    _dump({"shape_providers": list_shape_providers()})


def run_probe_providers(args) -> None:
    """Run probe providers.

    Args:
        args: args argument.
    """
    from ..shape_providers import probe_all_shape_providers

    runtime_config = load_runtime_config(args.runtime_config) if args.runtime_config else load_runtime_config(None)
    _dump({"shape_providers": probe_all_shape_providers(runtime_config)})


def run_probe_blender(args) -> None:
    """Run probe blender.

    Args:
        args: args argument.
    """
    from ..capabilities import probe_blender

    runtime_config = load_runtime_config(args.runtime_config) if args.runtime_config else load_runtime_config(None)
    _dump(probe_blender(runtime_config))
