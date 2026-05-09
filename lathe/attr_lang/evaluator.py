"""AST evaluator for the Lathe attribute mini-language.

The evaluator is a small visitor that reads
:class:`~lathe.attr_lang.ast.Node` instances and produces values
(``float``, ``int``, ``bool``, ``str``, or fixed-length tuple of floats).

It is **per-element** by design: callers construct an
:class:`EvalContext` populated with the auto-derived signals for a single
element (vertex / face / point / pixel) and evaluate the program for that
element. Vectorized evaluation is the responsibility of the integrator
(call :meth:`evaluate_program` once per element).

This module has zero dependencies outside the standard library.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any, Callable

from . import ast as _ast
from . import builtins as _builtins
from .errors import (
    EvalError,
    TypeMismatchError,
    UnknownBuiltinError,
    UnknownIdentifierError,
)

Value = Any

# A bound callable: a Python callable that takes (context, *args, **kwargs).
BoundCallable = Callable[..., Value]


@dataclass
class EvalContext:
    """Per-element evaluation context.

    ``attrs`` carries the auto-derived signals (``P``, ``N``, ``curvature``,
    ``ao``, ``height``, ``up_dot``, ``id``, ``material_zone``, ``uv``,
    ``world_pos``, ``P_local``, ``face_index``, ``vertex_index``) plus any
    user-defined attributes assigned by previous statements in the same
    program.

    ``palettes`` lets palette / ramp built-ins look up named palettes the
    integrator has registered. Keys are palette names; values are sequences
    of colors (each color is either a 3- or 4-tuple of floats in 0..1).

    ``palette_swatches`` registers individual named swatches reachable via
    ``palette.<swatch_name>`` (e.g. ``palette.shadow``,
    ``palette.midtone``, ``palette.highlight``).

    ``locals_`` carries non-``@`` named bindings created by bare-name
    assignments (e.g. ``mask = curvature_peaks(...) & ao_below(...)``).
    """

    attrs: dict[str, Value] = field(default_factory=dict)
    palettes: Mapping[str, Iterable[Value]] = field(default_factory=dict)
    palette_swatches: Mapping[str, Value] = field(default_factory=dict)
    locals_: dict[str, Value] = field(default_factory=dict)

    # ---- attribute / palette resolution --------------------------------

    def lookup_attr(self, name: str, *, default: Value = None) -> Value:
        if name in self.attrs:
            return self.attrs[name]
        if default is None and name not in self.attrs:
            raise UnknownIdentifierError(f"attribute @{name} is not defined")
        return default

    def resolve_palette(self, name: str) -> list[Value]:
        if name not in self.palettes:
            raise EvalError(f"palette {name!r} is not registered")
        return list(self.palettes[name])

    # ---- output capture ------------------------------------------------

    def assign_attr(self, name: str, value: Value) -> None:
        self.attrs[name] = value

    def assign_local(self, name: str, value: Value) -> None:
        self.locals_[name] = value


# ----------------------------------------------------------------------
# Evaluator
# ----------------------------------------------------------------------


def evaluate(node: _ast.Expr, ctx: EvalContext) -> Value:
    """Evaluate a single expression node against ``ctx``."""

    return _Evaluator(ctx).visit(node)


def evaluate_program(program: _ast.Program, ctx: EvalContext) -> EvalContext:
    """Evaluate a whole :class:`Program` for one element.

    Mutates ``ctx`` in place (assignments are written to ``ctx.attrs`` /
    ``ctx.locals_``) and returns it for convenience. Bare expression
    statements are evaluated for side-effect-free type-checking and their
    result is discarded.
    """

    ev = _Evaluator(ctx)
    for stmt in program.statements:
        if isinstance(stmt, _ast.Assignment):
            value = ev.visit(stmt.value)
            if stmt.target_is_attr:
                ctx.assign_attr(stmt.target_name, value)
            else:
                ctx.assign_local(stmt.target_name, value)
        else:
            ev.visit(stmt)
    return ctx


class _Evaluator:
    def __init__(self, ctx: EvalContext) -> None:
        self.ctx = ctx

    # Dispatch ----------------------------------------------------------

    def visit(self, node: _ast.Expr) -> Value:
        method = getattr(self, f"visit_{type(node).__name__}", None)
        if method is None:
            raise EvalError(f"no evaluator for AST node {type(node).__name__}")
        return method(node)

    # Literals ----------------------------------------------------------

    def visit_IntLiteral(self, n: _ast.IntLiteral) -> Value:
        return n.value

    def visit_FloatLiteral(self, n: _ast.FloatLiteral) -> Value:
        return n.value

    def visit_BoolLiteral(self, n: _ast.BoolLiteral) -> Value:
        return n.value

    def visit_StringLiteral(self, n: _ast.StringLiteral) -> Value:
        return n.value

    def visit_ColorLiteral(self, n: _ast.ColorLiteral) -> Value:
        return n.rgba

    def visit_VectorLiteral(self, n: _ast.VectorLiteral) -> Value:
        return tuple(self.visit(c) for c in n.components)

    def visit_ListLiteral(self, n: _ast.ListLiteral) -> Value:
        return [self.visit(item) for item in n.items]

    # Identifiers / attribute refs --------------------------------------

    def visit_Identifier(self, n: _ast.Identifier) -> Value:
        if n.name in self.ctx.locals_:
            return self.ctx.locals_[n.name]
        try:
            return _builtins.resolve_top_level(n.name)
        except UnknownBuiltinError as exc:
            raise UnknownIdentifierError(str(exc), n.span) from None

    def visit_AttrRef(self, n: _ast.AttrRef) -> Value:
        if n.name in self.ctx.attrs:
            return self.ctx.attrs[n.name]
        raise UnknownIdentifierError(f"attribute @{n.name} is not defined", n.span)

    # Member access / index ---------------------------------------------

    def visit_MemberAccess(self, n: _ast.MemberAccess) -> Value:
        # Special-case ``palette.<swatch>`` so authors can write
        # ``ramp(@height, [palette.shadow, palette.midtone, palette.highlight])``.
        if (
            isinstance(n.target, _ast.Identifier)
            and n.target.name == "palette"
            and n.member in self.ctx.palette_swatches
        ):
            return self.ctx.palette_swatches[n.member]
        target = self.visit(n.target)
        if isinstance(target, dict):
            if n.member in target:
                return target[n.member]
            raise UnknownBuiltinError(
                f"{type(target).__name__} has no member {n.member!r}", n.span
            )
        # If the target is a tuple, allow .x/.y/.z/.w / .r/.g/.b/.a swizzles.
        if isinstance(target, tuple):
            mapping = {
                "x": 0, "y": 1, "z": 2, "w": 3,
                "r": 0, "g": 1, "b": 2, "a": 3,
                "u": 0, "v": 1,
            }
            idx = mapping.get(n.member)
            if idx is not None and idx < len(target):
                return target[idx]
        raise EvalError(
            f"value of type {type(target).__name__} has no member {n.member!r}", n.span
        )

    def visit_Index(self, n: _ast.Index) -> Value:
        target = self.visit(n.target)
        idx = self.visit(n.index)
        if not isinstance(target, (list, tuple)):
            raise TypeMismatchError("indexing requires list / tuple", n.span)
        i = int(idx)
        if not -len(target) <= i < len(target):
            raise EvalError(f"index {i} out of bounds (len={len(target)})", n.span)
        return target[i]

    # Calls -------------------------------------------------------------

    def visit_Call(self, n: _ast.Call) -> Value:
        callee_value = self._resolve_callee(n.callee)
        args = [self.visit(a) for a in n.positional]
        kwargs = {kw.name: self.visit(kw.value) for kw in n.keywords}
        if not callable(callee_value):
            raise TypeMismatchError(
                f"value of type {type(callee_value).__name__} is not callable",
                n.span,
            )
        try:
            return callee_value(self.ctx, *args, **kwargs)
        except EvalError:
            raise
        except TypeError as exc:
            raise EvalError(f"call failed: {exc}", n.span) from None

    def _resolve_callee(self, node: _ast.Expr) -> Value:
        """Resolve a callee expression — handle namespace-as-callable case."""

        if isinstance(node, _ast.Identifier):
            # ``ramp(...)`` — namespace + directly-callable shorthand.
            if node.name in _builtins.DIRECTLY_CALLABLE_NAMESPACES:
                return _builtins.DIRECTLY_CALLABLE_NAMESPACES[node.name]
            return self.visit_Identifier(node)
        if isinstance(node, _ast.MemberAccess):
            target = self.visit(node.target)
            if isinstance(target, dict) and node.member in target:
                return target[node.member]
        return self.visit(node)

    # Operators ---------------------------------------------------------

    def visit_UnaryOp(self, n: _ast.UnaryOp) -> Value:
        v = self.visit(n.operand)
        if n.op == "-":
            return _builtins._unary_vec(v, lambda x: -x)
        if n.op == "+":
            return v
        if n.op == "!":
            return 0.0 if _builtins._to_float(v) >= 0.5 else 1.0
        if n.op == "~":
            return _builtins._unary_vec(v, lambda x: 1.0 - x)
        raise EvalError(f"unknown unary op {n.op!r}", n.span)

    def visit_BinOp(self, n: _ast.BinOp) -> Value:
        if n.op in ("&&", "||"):
            left = self.visit(n.left)
            right = self.visit(n.right)
            l = _builtins._to_float(left)
            r = _builtins._to_float(right)
            if n.op == "&&":
                return 1.0 if (l >= 0.5 and r >= 0.5) else 0.0
            return 1.0 if (l >= 0.5 or r >= 0.5) else 0.0

        left = self.visit(n.left)
        right = self.visit(n.right)

        if n.op in ("+", "-", "*", "/", "%"):
            return _builtins._vec_op(left, right, _ARITH_OPS[n.op])
        if n.op in ("<", ">", "<=", ">=", "==", "!="):
            l = _builtins._to_float(left)
            r = _builtins._to_float(right)
            return 1.0 if _CMP_OPS[n.op](l, r) else 0.0
        if n.op == "&":
            return _builtins._vec_op(left, right, min)
        if n.op == "|":
            return _builtins._vec_op(left, right, max)
        raise EvalError(f"unknown binary op {n.op!r}", n.span)


_ARITH_OPS: dict[str, Callable[[float, float], float]] = {
    "+": lambda a, b: a + b,
    "-": lambda a, b: a - b,
    "*": lambda a, b: a * b,
    "/": lambda a, b: a / b if b != 0 else 0.0,
    "%": lambda a, b: (a % b) if b != 0 else 0.0,
}

_CMP_OPS: dict[str, Callable[[float, float], bool]] = {
    "<": lambda a, b: a < b,
    ">": lambda a, b: a > b,
    "<=": lambda a, b: a <= b,
    ">=": lambda a, b: a >= b,
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
}
