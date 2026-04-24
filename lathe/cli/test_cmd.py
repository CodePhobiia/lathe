"""``lathe test`` / ``lathe bench`` subcommands.

Run the ``test`` and ``benchmark`` declarations embedded in Lathe
source files (distinct from the pytest suite).
"""

from __future__ import annotations

from pathlib import Path

from ._common import _dump, _expand_files


def run_test(args) -> None:
    """Run test.

    Args:
        args: args argument.
    """
    from ..test_runtime import run_lathe_tests

    result = run_lathe_tests(_expand_files(args.files) or None)
    _dump(result)
    raise SystemExit(0 if result["ok"] else 1)


def run_bench(args) -> None:
    """Run bench.

    Args:
        args: args argument.
    """
    from ..bench_runtime import run_lathe_benchmarks

    result = run_lathe_benchmarks(_expand_files(args.files) or None)
    _dump(result)
    raise SystemExit(0 if result["ok"] else 1)


def run_audit(args) -> None:
    """Run audit.

    Args:
        args: args argument.
    """
    from ..eval_harness import run_benchmark_suite

    root = Path(args.root).resolve()
    _dump(run_benchmark_suite(root))
