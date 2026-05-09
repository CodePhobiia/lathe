"""Lathe checker package.

Runs semantic validation on the resolved AST before planning. This
package re-exports the ``check_*`` entry points; individual rule sets
live in ``assets``, ``cross_stage``, ``declarations``, ``language``,
and ``surface``.
"""

from __future__ import annotations

from typing import Any

from ..resolver import Resolver
from .assets import check_assets_and_variants
from .declarations import check_new_declarations
from .experimental import check_experimental_block
from .language import (
    check_critics,
    check_duplicate_names,
    check_tests_and_benchmarks,
    check_use_graphs,
)
from .surface import check_pbr_material_primitives
from .utils import diag

__all__ = ["Checker", "check_program", "diag"]


class Checker:
    """Checker."""

    def __init__(self, program: dict[str, Any]) -> None:
        self.program = program
        self.resolver = Resolver(program)
        self.diagnostics: list[dict[str, Any]] = []

    def run(self) -> list[dict[str, Any]]:
        """Run.

        Returns:
            The result.
        """
        check_duplicate_names(self)
        check_use_graphs(self)
        check_critics(self)
        check_new_declarations(self)
        check_assets_and_variants(self)
        check_tests_and_benchmarks(self)
        check_experimental_block(self)
        check_pbr_material_primitives(self)
        return self.diagnostics


def check_program(program: dict[str, Any]) -> list[dict[str, Any]]:
    """Check program.

    Args:
        program: program argument.

    Returns:
        The result.
    """
    return Checker(program).run()
