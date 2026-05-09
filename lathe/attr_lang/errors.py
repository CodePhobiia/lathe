"""Error types for the Lathe attribute mini-language.

These errors carry source position so the parser, evaluator, and built-in
implementations can produce messages that point at the offending byte
offset / line / column in the original expression source.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SourceSpan:
    source: str
    start: int
    end: int

    @property
    def line(self) -> int:
        return self.source.count("\n", 0, self.start) + 1

    @property
    def column(self) -> int:
        last_nl = self.source.rfind("\n", 0, self.start)
        return self.start - last_nl

    def snippet(self, context: int = 24) -> str:
        lo = max(0, self.start - context)
        hi = min(len(self.source), self.end + context)
        return self.source[lo:hi].replace("\n", " ")


class AttrLangError(Exception):
    """Base class for attribute-lang errors."""

    def __init__(self, message: str, span: SourceSpan | None = None) -> None:
        if span is not None:
            located = (
                f"{message} (line {span.line}, column {span.column}): "
                f"...{span.snippet()}..."
            )
        else:
            located = message
        super().__init__(located)
        self.span = span
        self.raw_message = message


class ParseError(AttrLangError):
    """Raised by the parser for syntactic problems."""


class ForbiddenConstructError(ParseError):
    """Raised when source uses a forbidden construct (for/while/def/import/...)."""


class EvalError(AttrLangError):
    """Raised by the evaluator at runtime."""


class TypeMismatchError(EvalError):
    """A built-in or operator received an unexpected operand type."""


class UnknownIdentifierError(EvalError):
    """An attribute reference (e.g. ``@foo``) is not present in the context."""


class UnknownBuiltinError(EvalError):
    """A call references a built-in / namespace that is not registered."""
