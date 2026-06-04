"""AST node types for the Lathe attribute mini-language.

The grammar is intentionally tiny and declarative. Allowed node kinds:

- Literals: int, float, vec2/vec3/vec4 tuples, hex / named colors, strings,
  bool, identifier list literals.
- Identifiers: bare names (function lookup root) and ``@``-prefixed
  attribute references resolved against the per-element context.
- Member access (``palette.shadow``) and call expressions
  (``noise(perlin, octaves=4)``).
- Binary / unary operators (math + boolean / mask logic).
- Conditional via ``mix(a, b, t)`` / ``step`` / ``smoothstep`` built-ins —
  no native ternary, ``if``, ``for``, ``while``, ``def``, ``lambda``, or
  ``import``.
- Top-level statements: bare expressions and assignments
  (``@rough = ...`` or ``mask = ...``).

Every node carries a :class:`SourceSpan` so evaluator errors can point at
the offending text. Nodes are ``frozen=True`` dataclasses; the evaluator
treats them as pure values.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .errors import SourceSpan


@dataclass(frozen=True)
class Node:
    span: SourceSpan = field(repr=False)


@dataclass(frozen=True)
class IntLiteral(Node):
    value: int


@dataclass(frozen=True)
class FloatLiteral(Node):
    value: float


@dataclass(frozen=True)
class BoolLiteral(Node):
    value: bool


@dataclass(frozen=True)
class StringLiteral(Node):
    value: str


@dataclass(frozen=True)
class ColorLiteral(Node):
    """A ``#rrggbb`` / ``#rrggbbaa`` literal expanded to a 4-tuple in 0..1."""

    rgba: tuple[float, float, float, float]


@dataclass(frozen=True)
class VectorLiteral(Node):
    """A parenthesized tuple literal: ``(u, v)``, ``(x, y, z)``, ``(r,g,b,a)``."""

    components: tuple[Expr, ...]


@dataclass(frozen=True)
class ListLiteral(Node):
    """A bracketed list — used for ramp colors, palette swatches, etc."""

    items: tuple[Expr, ...]


@dataclass(frozen=True)
class Identifier(Node):
    """A bare name. Resolves to a built-in callable or a constant."""

    name: str


@dataclass(frozen=True)
class AttrRef(Node):
    """A ``@name`` attribute reference resolved per-element from context."""

    name: str


@dataclass(frozen=True)
class MemberAccess(Node):
    target: Expr
    member: str


@dataclass(frozen=True)
class Index(Node):
    target: Expr
    index: Expr


@dataclass(frozen=True)
class KeywordArg(Node):
    name: str
    value: Expr


@dataclass(frozen=True)
class Call(Node):
    """A call: positional args + keyword args. Callee is any expression."""

    callee: Expr
    positional: tuple[Expr, ...]
    keywords: tuple[KeywordArg, ...]


@dataclass(frozen=True)
class UnaryOp(Node):
    op: str  # one of: '-', '+', '!', '~'
    operand: Expr


@dataclass(frozen=True)
class BinOp(Node):
    op: str  # arithmetic, comparison, logical/mask
    left: Expr
    right: Expr


# ----------------------------------------------------------------------
# Top-level statements
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class Assignment(Node):
    """``target = value`` where target is either ``@name`` or a bare name."""

    target_name: str
    target_is_attr: bool
    value: Expr


@dataclass(frozen=True)
class Program(Node):
    """A parsed source unit — zero or more statements (assignments / exprs)."""

    statements: tuple[Statement, ...]


# Type aliases used throughout the codebase.
Expr = (
    IntLiteral
    | FloatLiteral
    | BoolLiteral
    | StringLiteral
    | ColorLiteral
    | VectorLiteral
    | ListLiteral
    | Identifier
    | AttrRef
    | MemberAccess
    | Index
    | Call
    | UnaryOp
    | BinOp
)

Statement = Assignment | Expr
