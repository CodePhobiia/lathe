from __future__ import annotations

from typing import Any

from ..resolver import Resolver
from .assets import check_assets_and_variants
from .declarations import check_new_declarations
from .language import (
    check_critics,
    check_duplicate_names,
    check_tests_and_benchmarks,
    check_use_graphs,
)
from .utils import diag


__all__ = ["Checker", "check_program", "diag"]


class Checker:
    def __init__(self, program: dict[str, Any]) -> None:
        self.program = program
        self.resolver = Resolver(program)
        self.diagnostics: list[dict[str, Any]] = []

    def run(self) -> list[dict[str, Any]]:
        check_duplicate_names(self)
        check_use_graphs(self)
        check_critics(self)
        check_new_declarations(self)
        check_assets_and_variants(self)
        check_tests_and_benchmarks(self)
        return self.diagnostics


def check_program(program: dict[str, Any]) -> list[dict[str, Any]]:
    return Checker(program).run()
