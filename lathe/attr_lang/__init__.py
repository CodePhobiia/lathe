"""Lathe attribute mini-language (``§6.4``).

A tiny VEX-style expression language for declarative-leaning per-element
manipulation in surface_graph nodes, mesh_program ops, feature emitters,
validators, and instance_pattern blocks.

Public API:

- :func:`parse` — parse a multi-statement program.
- :func:`parse_expression` — parse a single expression.
- :func:`evaluate` / :func:`evaluate_program` — run an AST against a context.
- :class:`EvalContext` — per-element evaluation context with auto-derived
  signals (``@P``, ``@N``, ``@curvature``, ``@ao``, ``@height``, ``@up_dot``,
  ``@id``, ``@material_zone``, ``@uv``, ``@world_pos``, ``@P_local``,
  ``@face_index``, ``@vertex_index``).
- :data:`AUTO_DERIVED_SIGNALS` — canonical list of available ``@``-attrs.
- :func:`compile_expression` — convenience that parses once and returns a
  callable bound to a context constructor.

The grammar is intentionally a strict subset: no loops, recursion,
conditionals, I/O, or imports. Forbidden constructs are rejected at parse
time with a clear :class:`ForbiddenConstructError`.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from . import ast
from .ast import (
    Assignment,
    AttrRef,
    BinOp,
    BoolLiteral,
    Call,
    ColorLiteral,
    Expr,
    FloatLiteral,
    Identifier,
    Index,
    IntLiteral,
    KeywordArg,
    ListLiteral,
    MemberAccess,
    Node,
    Program,
    Statement,
    StringLiteral,
    UnaryOp,
    VectorLiteral,
)
from .builtins import (
    CONSTANTS,
    DIRECTLY_CALLABLE_NAMESPACES,
    NAMESPACES,
    TOP_LEVEL_BUILTINS,
)
from .errors import (
    AttrLangError,
    EvalError,
    ForbiddenConstructError,
    ParseError,
    SourceSpan,
    TypeMismatchError,
    UnknownBuiltinError,
    UnknownIdentifierError,
)
from .evaluator import EvalContext, evaluate, evaluate_program
from .parser import parse, parse_expression

AUTO_DERIVED_SIGNALS: tuple[str, ...] = (
    "P",
    "N",
    "curvature",
    "ao",
    "height",
    "up_dot",
    "id",
    "material_zone",
    "uv",
    "world_pos",
    "P_local",
    "face_index",
    "vertex_index",
)


def compile_expression(source: str) -> Callable[[EvalContext], Any]:
    """Parse ``source`` once and return a function ``ctx -> value``.

    Use this when the same expression will be evaluated against many
    contexts (e.g. a mask expression evaluated per surface element).
    """
    parsed = parse_expression(source)

    def _run(ctx: EvalContext) -> Any:
        return evaluate(parsed, ctx)

    return _run


__all__ = [
    "AUTO_DERIVED_SIGNALS",
    "CONSTANTS",
    "DIRECTLY_CALLABLE_NAMESPACES",
    "NAMESPACES",
    "TOP_LEVEL_BUILTINS",
    "Assignment",
    "AttrLangError",
    "AttrRef",
    "BinOp",
    "BoolLiteral",
    "Call",
    "ColorLiteral",
    "EvalContext",
    "EvalError",
    "Expr",
    "FloatLiteral",
    "ForbiddenConstructError",
    "Identifier",
    "Index",
    "IntLiteral",
    "KeywordArg",
    "ListLiteral",
    "MemberAccess",
    "Node",
    "ParseError",
    "Program",
    "SourceSpan",
    "Statement",
    "StringLiteral",
    "TypeMismatchError",
    "UnaryOp",
    "UnknownBuiltinError",
    "UnknownIdentifierError",
    "VectorLiteral",
    "ast",
    "compile_expression",
    "evaluate",
    "evaluate_program",
    "parse",
    "parse_expression",
]
