"""CGA-style declarative shape grammar for Lathe assembly_rules.

Implements a CityEngine-class production rule system (V1.1+ compatible).

Production rules are written in a string mini-language that compiles into a
typed :class:`AssemblyTree` of :class:`ProductionNode` records. The evaluator
walks the tree starting from a designated root rule and an initial bounding
shape, expanding non-terminals into RHS forms (split / repeat / chooseOne /
extrude / translate / rotate / scale) until every leaf is a terminal mesh
reference or kit call. Terminals are then handed off to ``assembly_kernel`` as
ShapePrimitives or kit calls.

Public API:

* :func:`compile_assembly_rules` — accept a normalized ``assembly_rules`` dict
  and produce a :class:`Grammar` + diagnostics.
* :func:`evaluate_rule_tree` — expand a :class:`Grammar` against an initial
  shape (deterministic with seed) into an :class:`AssemblyTree`.
* :func:`terminate_to_primitives` — convert an :class:`AssemblyTree` into a
  flat list of terminal records suitable for ``assembly_kernel`` consumption.

Backwards compatibility: when ``assembly_rules`` carries no ``productions``
field the V1.1 dict is returned untouched and :func:`compile_assembly_rules`
returns an empty :class:`Grammar` — downstream code can fall back to the
existing assembly kernel without behavioral change.

Stable contract id: ``lathe.assembly.shape_grammar_v1``.
"""

from __future__ import annotations

from .evaluator import (
    AssemblyTree,
    EvaluationDiagnostic,
    EvaluationReport,
    InitialShape,
    ProductionNode,
    evaluate_rule_tree,
)
from .productions import (
    RHS,
    ChooseOne,
    Extrude,
    Grammar,
    NonTerminal,
    Production,
    Repeat,
    Rotate,
    Scale,
    Split,
    SplitItem,
    Terminal,
    Translate,
    parse_production,
    parse_productions,
)
from .terminals import TerminalRecord, terminate_to_primitives
from .validator import GrammarDiagnostic, GrammarReport, validate_grammar

CGA_CONTRACT_ID = "lathe.assembly.shape_grammar_v1"
DEFAULT_RECURSION_BUDGET = 32


def _parse_productions_with_report(raw_productions: list[object]) -> tuple[Grammar, GrammarReport]:
    grammar = Grammar()
    diagnostics: list[GrammarDiagnostic] = []
    for index, raw in enumerate(raw_productions):
        if not isinstance(raw, str):
            diagnostics.append(
                GrammarDiagnostic(
                    code="cga.production_not_string",
                    message=f"production entry {index} must be a string",
                    rule="productions",
                    severity="error",
                )
            )
            continue
        text = raw.strip()
        if not text or text.startswith("#"):
            continue
        try:
            grammar.add(parse_production(text))
        except ValueError as exc:
            diagnostics.append(
                GrammarDiagnostic(
                    code="cga.production_parse_failed",
                    message=str(exc),
                    rule=f"productions[{index}]",
                    severity="error",
                )
            )
    report = GrammarReport(
        diagnostics=diagnostics,
        declared_nonterminals=set(grammar.productions.keys()),
    )
    return grammar, report


def compile_assembly_rules(
    assembly_rules: dict | None,
    *,
    recursion_budget: int = DEFAULT_RECURSION_BUDGET,
) -> tuple[Grammar, GrammarReport]:
    """Compile a normalized ``assembly_rules`` dict into a :class:`Grammar`.

    The dict may carry a ``productions`` list of CGA-style production
    strings. When absent, an empty grammar and an empty report are returned
    so callers can transparently fall back to the V1.1 assembly path.
    """
    rules = assembly_rules or {}
    raw_productions = rules.get("productions") or []
    if isinstance(raw_productions, str):
        raw_productions = [raw_productions]
    grammar, parse_report = _parse_productions_with_report(list(raw_productions))
    grammar.recursion_budget = int(rules.get("recursion_budget", recursion_budget))
    grammar.root = str(rules.get("root", grammar.root))
    grammar.seed = int(rules.get("seed", grammar.seed))
    report = validate_grammar(grammar)
    if parse_report.diagnostics:
        report.diagnostics = [*parse_report.diagnostics, *report.diagnostics]
    return grammar, report


__all__ = [
    "CGA_CONTRACT_ID",
    "DEFAULT_RECURSION_BUDGET",
    "RHS",
    "AssemblyTree",
    "ChooseOne",
    "EvaluationDiagnostic",
    "EvaluationReport",
    "Extrude",
    "Grammar",
    "GrammarDiagnostic",
    "GrammarReport",
    "InitialShape",
    "NonTerminal",
    "Production",
    "ProductionNode",
    "Repeat",
    "Rotate",
    "Scale",
    "Split",
    "SplitItem",
    "Terminal",
    "TerminalRecord",
    "Translate",
    "compile_assembly_rules",
    "evaluate_rule_tree",
    "parse_production",
    "parse_productions",
    "terminate_to_primitives",
    "validate_grammar",
]
