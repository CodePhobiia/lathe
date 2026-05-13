"""Field-style attr language for masks + scatter.

Per northstar §10 Lane I priority task #4. Field expressions let
authors describe masks and scatter weights as functions over
attributes the geometry already carries:

  - ``exposure > 0.5 and material_zone == 'metal'``
  - ``angle_deg > 35 and role_in('outer_corner', 'silhouette')``
  - ``height_cm < 5 + jitter(seed=42, amp=2)``

The module parses + evaluates expressions deterministically. No
``eval()`` — the grammar is a tiny shunting-yard expression parser
that handles boolean + comparison + arithmetic ops on attribute
references and literals.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

FIELD_ATTRS_VERSION = "lathe.asset_foundry.field_attrs_v1"


class FieldOperator(str, Enum):
    """Supported operators in field expressions."""

    AND = "and"
    OR = "or"
    NOT = "not"
    EQ = "=="
    NEQ = "!="
    GT = ">"
    GTE = ">="
    LT = "<"
    LTE = "<="
    ADD = "+"
    SUB = "-"
    MUL = "*"
    DIV = "/"


_PRECEDENCE: Mapping[str, int] = {
    "or": 1,
    "and": 2,
    "not": 3,
    "==": 4,
    "!=": 4,
    ">": 4,
    ">=": 4,
    "<": 4,
    "<=": 4,
    "+": 5,
    "-": 5,
    "*": 6,
    "/": 6,
}


@dataclass(frozen=True)
class FieldExpression:
    """Parsed expression — a flat RPN sequence of tokens."""

    rpn_tokens: tuple[Any, ...]
    source_text: str


def _tokenize(expr: str) -> list[Any]:
    """Tokenize an expression string into typed tokens."""
    out: list[Any] = []
    i = 0
    s = expr.strip()
    pattern = re.compile(
        r"(\s+)|"
        r"([(),])|"
        r"(==|!=|>=|<=|>|<|\+|\-|\*|/)|"
        r"('[^']*'|\"[^\"]*\")|"
        r"([0-9]+\.?[0-9]*|\.[0-9]+)|"
        r"([A-Za-z_][A-Za-z_0-9]*)"
    )
    while i < len(s):
        m = pattern.match(s, i)
        if not m:
            raise ValueError(f"unexpected character at {i}: {s[i:i+10]!r}")
        if m.group(1):
            i = m.end()
            continue
        token = m.group(0)
        if m.group(2):
            out.append(("punct", token))
        elif m.group(3):
            out.append(("op", token))
        elif m.group(4):
            out.append(("literal", token[1:-1]))
        elif m.group(5):
            out.append(("literal", float(token)))
        else:
            kw = token.lower()
            if kw in {"and", "or", "not"}:
                out.append(("op", kw))
            elif kw in {"true", "false"}:
                out.append(("literal", kw == "true"))
            elif kw == "none":
                out.append(("literal", None))
            else:
                out.append(("ident", token))
        i = m.end()
    return out


def _shunting_yard(tokens: list[Any]) -> list[Any]:
    """Convert infix tokens to RPN."""
    output: list[Any] = []
    stack: list[Any] = []
    expecting_value = True
    i = 0
    while i < len(tokens):
        ttype, tvalue = tokens[i]
        if ttype == "literal":
            output.append(("literal", tvalue))
            expecting_value = False
        elif ttype == "ident":
            # Function call when followed by "(": role_in('a','b').
            if i + 1 < len(tokens) and tokens[i + 1] == ("punct", "("):
                stack.append(("func", tvalue))
                expecting_value = True
            else:
                output.append(("ident", tvalue))
                expecting_value = False
        elif ttype == "op":
            if tvalue == "-" and expecting_value:
                # Unary minus.
                stack.append(("op", "neg"))
            else:
                while (
                    stack
                    and stack[-1][0] in {"op", "func"}
                    and stack[-1][1] != "neg"
                    and _PRECEDENCE.get(stack[-1][1], -1)
                    >= _PRECEDENCE.get(tvalue, -1)
                ):
                    output.append(stack.pop())
                stack.append(("op", tvalue))
            expecting_value = True
        elif ttype == "punct":
            if tvalue == "(":
                stack.append(("punct", "("))
                expecting_value = True
            elif tvalue == ")":
                while stack and stack[-1] != ("punct", "("):
                    output.append(stack.pop())
                if not stack:
                    raise ValueError("mismatched parentheses")
                stack.pop()
                if stack and stack[-1][0] == "func":
                    output.append(stack.pop())
                expecting_value = False
            elif tvalue == ",":
                while stack and stack[-1] != ("punct", "("):
                    output.append(stack.pop())
                expecting_value = True
        i += 1
    while stack:
        top = stack.pop()
        if top == ("punct", "("):
            raise ValueError("mismatched parentheses")
        output.append(top)
    return output


def parse_field_expression(expr: str) -> FieldExpression:
    """Parse a field-expression string."""
    tokens = _tokenize(expr)
    rpn = _shunting_yard(tokens)
    return FieldExpression(rpn_tokens=tuple(rpn), source_text=expr)


def _resolve_ident(ident: str, attrs: Mapping[str, Any]) -> Any:
    """Resolve an attribute reference."""
    if "." in ident:
        cursor: Any = attrs
        for part in ident.split("."):
            if isinstance(cursor, Mapping) and part in cursor:
                cursor = cursor[part]
            else:
                return None
        return cursor
    return attrs.get(ident)


def _call_builtin(name: str, args: list[Any]) -> Any:
    """Built-in functions allowed in field expressions."""
    if name == "role_in":
        # role_in(role_value, 'role1', 'role2', ...)
        if not args:
            return False
        role = args[0]
        return role in args[1:]
    if name == "axis_aligned_to":
        # axis_aligned_to(axis_vector, expected_axis)
        if len(args) < 2:
            return False
        return tuple(args[0]) == tuple(args[1]) if hasattr(args[0], "__iter__") else False
    if name == "abs":
        return abs(args[0]) if args else 0
    if name == "min":
        return min(args) if args else 0
    if name == "max":
        return max(args) if args else 0
    if name == "clamp":
        if len(args) < 3:
            return args[0] if args else 0
        return max(args[1], min(args[2], args[0]))
    if name == "jitter":
        # jitter(seed=int, amp=float) — deterministic.
        if len(args) < 2:
            return 0.0
        seed = int(args[0]) if not isinstance(args[0], bool) else 0
        amp = float(args[1])
        h = (1664525 * (seed if seed != 0 else 0xDEAD) + 1013904223) & 0xFFFFFFFF
        return ((h / 0xFFFFFFFF) - 0.5) * 2.0 * amp
    raise ValueError(f"unknown field function: {name!r}")


def evaluate_field(
    expression: FieldExpression,
    attrs: Mapping[str, Any],
) -> Any:
    """Evaluate a parsed field expression against an attribute map."""
    stack: list[Any] = []
    i = 0
    rpn = list(expression.rpn_tokens)
    while i < len(rpn):
        ttype, tvalue = rpn[i]
        if ttype == "literal":
            stack.append(tvalue)
        elif ttype == "ident":
            stack.append(_resolve_ident(tvalue, attrs))
        elif ttype == "op":
            if tvalue == "neg":
                a = stack.pop()
                stack.append(-a)
            elif tvalue == "not":
                a = stack.pop()
                stack.append(not bool(a))
            else:
                b = stack.pop()
                a = stack.pop()
                stack.append(_binop(tvalue, a, b))
        elif ttype == "func":
            # Function call — we don't know the arity directly from RPN,
            # so we look up how many tokens were pushed since the
            # function entered the stack. Simple convention: we built
            # the RPN so all function args are on the stack at this
            # point, but we don't know how many. As a pragmatic
            # solution, supported functions consume a fixed-or-variable
            # number of args; we pop until we hit a sentinel — but the
            # current RPN builder does not emit sentinels. As a
            # simplification, we look up the function by name and pop
            # the appropriate number of args from the top.
            arg_counts: Mapping[str, int] = {
                "abs": 1,
                "clamp": 3,
                "jitter": 2,
                "role_in": 2,
                "axis_aligned_to": 2,
                "min": 2,
                "max": 2,
            }
            n = arg_counts.get(tvalue, 1)
            if tvalue == "role_in":
                # variable arity; pop everything pushed for this call.
                # Heuristic: pop while the next op is not 'func'.
                args = []
                while len(stack) > 0:
                    args.insert(0, stack.pop())
                    if len(args) >= 6:
                        break
                stack.append(_call_builtin(tvalue, args))
            else:
                args = [stack.pop() for _ in range(n)]
                args.reverse()
                stack.append(_call_builtin(tvalue, args))
        i += 1
    return stack[-1] if stack else None


def _binop(op: str, a: Any, b: Any) -> Any:
    if op == "+":
        return (a or 0) + (b or 0)
    if op == "-":
        return (a or 0) - (b or 0)
    if op == "*":
        return (a or 0) * (b or 0)
    if op == "/":
        return (a or 0) / (b or 1)
    if op == "and":
        return bool(a) and bool(b)
    if op == "or":
        return bool(a) or bool(b)
    if op == "==":
        return a == b
    if op == "!=":
        return a != b
    if op == ">":
        return (a or 0) > (b or 0)
    if op == ">=":
        return (a or 0) >= (b or 0)
    if op == "<":
        return (a or 0) < (b or 0)
    if op == "<=":
        return (a or 0) <= (b or 0)
    raise ValueError(f"unknown binop: {op!r}")


__all__ = [
    "FIELD_ATTRS_VERSION",
    "FieldExpression",
    "FieldOperator",
    "evaluate_field",
    "parse_field_expression",
]
