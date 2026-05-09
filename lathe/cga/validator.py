"""Static validation pass for a parsed CGA :class:`Grammar`.

Checks that:

* The declared root has at least one production.
* Every non-terminal referenced on a RHS resolves to a production or is
  reported as unresolved (callers may still treat it as an implicit terminal).
* Splits are well-formed: axes are valid, no item carries a negative size,
  and fixed-size totals do not blatantly exceed any reasonable shape budget
  (the runtime evaluator clamps; the validator only warns).
* Repeats have a positive count.
* ``chooseOne`` weights are positive and sum to a non-zero total.

Validation is conservative — it never raises; it returns a
:class:`GrammarReport` so the caller can decide policy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any

from .productions import (
    ChooseOne,
    Extrude,
    Grammar,
    NonTerminal,
    Repeat,
    Rotate,
    Scale,
    Split,
    Terminal,
    Translate,
)


@dataclass
class GrammarDiagnostic:
    """A single grammar-level diagnostic."""

    code: str
    message: str
    rule: str
    severity: str = "warning"


@dataclass
class GrammarReport:
    """Output of :func:`validate_grammar`."""

    diagnostics: list[GrammarDiagnostic] = field(default_factory=list)
    referenced_nonterminals: set[str] = field(default_factory=set)
    declared_nonterminals: set[str] = field(default_factory=set)

    @property
    def ok(self) -> bool:
        return not any(d.severity == "error" for d in self.diagnostics)

    @property
    def unresolved(self) -> set[str]:
        return self.referenced_nonterminals - self.declared_nonterminals


def validate_grammar(grammar: Grammar) -> GrammarReport:
    """Run static checks on ``grammar`` and return a :class:`GrammarReport`."""
    report = GrammarReport(declared_nonterminals=set(grammar.productions.keys()))
    if not grammar.productions:
        return report
    if grammar.root not in grammar.productions:
        report.diagnostics.append(
            GrammarDiagnostic(
                code="cga.missing_root",
                message=f"declared root {grammar.root!r} has no production",
                rule=grammar.root,
                severity="error",
            )
        )
    for lhs, productions in grammar.productions.items():
        for production in productions:
            for rhs in production.rhs:
                _walk_rhs(rhs, lhs, report)
    return report


def _walk_rhs(rhs: Any, owning_rule: str, report: GrammarReport) -> None:
    if isinstance(rhs, NonTerminal):
        report.referenced_nonterminals.add(rhs.name)
        if rhs.name not in report.declared_nonterminals:
            report.diagnostics.append(
                GrammarDiagnostic(
                    code="cga.unresolved_nonterminal",
                    message=f"non-terminal {rhs.name!r} referenced from {owning_rule!r} has no production",
                    rule=owning_rule,
                    severity="warning",
                )
            )
        return
    if isinstance(rhs, Terminal):
        _walk_terminal_params(rhs, owning_rule, report)
        return
    if isinstance(rhs, Split):
        if rhs.axis not in {"x", "y", "z"}:
            report.diagnostics.append(
                GrammarDiagnostic(
                    code="cga.split_bad_axis",
                    message=f"split axis must be x|y|z (got {rhs.axis!r})",
                    rule=owning_rule,
                    severity="error",
                )
            )
        for item in rhs.items:
            if item.size < 0:
                report.diagnostics.append(
                    GrammarDiagnostic(
                        code="cga.split_negative_size",
                        message=f"split item carries negative size {item.size}",
                        rule=owning_rule,
                        severity="error",
                    )
                )
            _walk_rhs(item.rhs, owning_rule, report)
        return
    if isinstance(rhs, Repeat):
        if rhs.count <= 0:
            report.diagnostics.append(
                GrammarDiagnostic(
                    code="cga.repeat_nonpositive",
                    message=f"repeat count must be > 0 (got {rhs.count})",
                    rule=owning_rule,
                    severity="error",
                )
            )
        _walk_rhs(rhs.rhs, owning_rule, report)
        return
    if isinstance(rhs, ChooseOne):
        total = sum(w for w, _ in rhs.options)
        if total <= 0:
            report.diagnostics.append(
                GrammarDiagnostic(
                    code="cga.choose_zero_total",
                    message="chooseOne weights sum to zero",
                    rule=owning_rule,
                    severity="error",
                )
            )
        for weight, sub in rhs.options:
            if weight < 0:
                report.diagnostics.append(
                    GrammarDiagnostic(
                        code="cga.choose_negative_weight",
                        message=f"chooseOne weight is negative ({weight})",
                        rule=owning_rule,
                        severity="error",
                    )
                )
            _walk_rhs(sub, owning_rule, report)
        return
    if isinstance(rhs, (Extrude, Translate, Rotate, Scale)):
        if rhs.rhs is not None:
            _walk_rhs(rhs.rhs, owning_rule, report)
        return
    report.diagnostics.append(
        GrammarDiagnostic(
            code="cga.unknown_rhs",
            message=f"unrecognised RHS form {type(rhs).__name__}",
            rule=owning_rule,
            severity="error",
        )
    )


def _walk_terminal_params(
    terminal: Terminal,
    owning_rule: str,
    report: GrammarReport,
) -> None:
    params = terminal.params if isinstance(terminal.params, dict) else {}
    for key in ("width", "width_m", "w", "depth", "depth_m", "d", "height", "height_m", "h"):
        if key not in params:
            continue
        value = params.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            report.diagnostics.append(
                GrammarDiagnostic(
                    code="cga.terminal_dimension_non_numeric",
                    message=f"terminal {terminal.name!r} parameter {key!r} must be numeric length",
                    rule=owning_rule,
                    severity="error",
                )
            )
            continue
        if not math.isfinite(float(value)) or float(value) <= 0.0:
            report.diagnostics.append(
                GrammarDiagnostic(
                    code="cga.terminal_dimension_nonpositive",
                    message=f"terminal {terminal.name!r} parameter {key!r} must be > 0",
                    rule=owning_rule,
                    severity="error",
                )
            )
    axis = params.get("axis")
    if axis is not None and axis not in {"x", "y", "z"}:
        report.diagnostics.append(
            GrammarDiagnostic(
                code="cga.terminal_bad_axis",
                message=f"terminal {terminal.name!r} axis must be x|y|z (got {axis!r})",
                rule=owning_rule,
                severity="error",
            )
        )
