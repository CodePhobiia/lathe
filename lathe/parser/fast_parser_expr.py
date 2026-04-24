"""Expression-level productions for the fast parser.

Handles numeric/string/identifier atoms, unit suffixes, composite
mapping/list literals and operator chains used inside Lathe blocks.
"""

from __future__ import annotations

import ast as py_ast
from typing import Any, Iterable

from .grammar import LatheParseError, _UNIT_RE, _dedupe_keep_first, _num, _set_nested
from .tokens import _TokenStream


class _FastParserExprMixin:
    ts: _TokenStream

    def _qident(self) -> str:
        parts = [self.ts.pop_ident()]
        while self.ts.peek("."):
            self.ts.pop(".")
            parts.append(self.ts.pop_ident())
        return ".".join(parts)

    def _path(self) -> str:
        return self._qident()

    def _optional_uses(self) -> list[str]:
        if not self.ts.peek("uses"):
            return []
        self.ts.pop("uses")
        uses = [self._qident()]
        while self.ts.peek(","):
            self.ts.pop(",")
            uses.append(self._qident())
        return uses

    def _assign_block(self, context: str) -> dict[str, Any]:
        assignments: list[tuple[str, Any]] = []
        self.ts.pop("{")
        while not self.ts.peek("}"):
            path = self._path()
            assignments.append((path, self._assign_value()))
        self.ts.pop("}")
        return self._assignments(assignments, context)

    def _assign_value(self) -> Any:
        self.ts.pop("=")
        return self._expr()

    def _expect_in_expr(self) -> Any:
        if self.ts.pop_ident() != "in":
            raise LatheParseError("vary requires 'in'")
        return self._expr()

    def _finish_path(self, first: str) -> str:
        parts = [first]
        while self.ts.peek("."):
            self.ts.pop(".")
            parts.append(self.ts.pop_ident())
        return ".".join(parts)

    def _rule(self, kind: str) -> dict[str, Any]:
        rule = {"node_type": "rule", "kind": kind, "expr": self._expr()}
        if kind == "prefer" and self.ts.peek("weight"):
            self.ts.pop("weight")
            rule["weight"] = float(self._number_value())
        return rule

    def _metric_ref(self) -> Any:
        return self._atom()

    def _expr(self) -> Any:
        return self._or_expr()

    def _or_expr(self) -> Any:
        left = self._and_expr()
        while self.ts.peek("or"):
            self.ts.pop("or")
            left = {"type": "binary", "op": "or", "left": left, "right": self._and_expr()}
        return left

    def _and_expr(self) -> Any:
        left = self._equality()
        while self.ts.peek("and"):
            self.ts.pop("and")
            left = {"type": "binary", "op": "and", "left": left, "right": self._equality()}
        return left

    def _equality(self) -> Any:
        left = self._comparison()
        while self.ts.peek() in {"==", "!="}:
            op = self.ts.pop()
            left = {"type": "binary", "op": op, "left": left, "right": self._comparison()}
        return left

    def _comparison(self) -> Any:
        left = self._sum()
        while self.ts.peek() in {"<", "<=", ">", ">=", "in"}:
            op = self.ts.pop()
            left = {"type": "binary", "op": op, "left": left, "right": self._sum()}
        return left

    def _sum(self) -> Any:
        left = self._term()
        while self.ts.peek() in {"+", "-"}:
            op = self.ts.pop()
            left = {"type": "binary", "op": op, "left": left, "right": self._term()}
        return left

    def _term(self) -> Any:
        left = self._factor()
        while self.ts.peek() in {"*", "/"}:
            op = self.ts.pop()
            left = {"type": "binary", "op": op, "left": left, "right": self._factor()}
        return left

    def _factor(self) -> Any:
        if self.ts.peek("not"):
            self.ts.pop("not")
            return {"type": "unary", "op": "not", "value": self._factor()}
        if self.ts.peek("-") and self.ts.kind() == "op":
            self.ts.pop("-")
            return {"type": "unary", "op": "-", "value": self._factor()}
        return self._range()

    def _range(self) -> Any:
        left = self._atom()
        if self.ts.peek(".."):
            self.ts.pop("..")
            return {"type": "range", "from": left, "to": self._atom()}
        return left

    def _atom(self) -> Any:
        kind = self.ts.kind()
        value = self.ts.peek()
        if value == "(":
            self.ts.pop("(")
            expr = self._expr()
            self.ts.pop(")")
            return expr
        if value == "[":
            return self._list()
        if kind == "string":
            return py_ast.literal_eval(self.ts.pop())
        if kind == "unit":
            return self._unit_value(self.ts.pop())
        if kind == "number":
            return self._number_value()
        if kind == "ident":
            name = self._qident()
            if name == "true":
                return True
            if name == "false":
                return False
            if self.ts.peek("("):
                return self._call_after_name(name)
            return name
        raise LatheParseError(f"Expected expression, got '{value or 'end of file'}'")

    def _list(self) -> list[Any]:
        items: list[Any] = []
        self.ts.pop("[")
        while not self.ts.peek("]"):
            items.append(self._expr())
            if self.ts.peek(","):
                self.ts.pop(",")
                if self.ts.peek("]"):
                    break
            else:
                break
        self.ts.pop("]")
        return items

    def _call_after_name(self, name: str) -> dict[str, Any]:
        args = []
        self.ts.pop("(")
        while not self.ts.peek(")"):
            if self.ts.kind() == "ident" and self.ts.tokens[self.ts.index + 1][1] == ":":
                arg_name = self.ts.pop_ident()
                self.ts.pop(":")
                args.append({"name": arg_name, "value": self._expr()})
            else:
                args.append({"name": None, "value": self._expr()})
            if self.ts.peek(","):
                self.ts.pop(",")
                if self.ts.peek(")"):
                    break
            else:
                break
        self.ts.pop(")")
        return {"type": "call", "name": name, "args": args}

    def _number_value(self) -> int | float:
        if self.ts.kind() != "number":
            raise LatheParseError(f"Expected number, got '{self.ts.peek()}'")
        return _num(self.ts.pop())

    def _unit_value(self, text: str) -> dict[str, Any]:
        match = _UNIT_RE.match(text)
        if not match:
            raise LatheParseError(f"Invalid unit literal: {text}")
        return {"type": "unit", "value": _num(match.group("value")), "unit": match.group("unit")}

    def _assignments(self, assignments: Iterable[tuple[str, Any]], context: str) -> dict[str, Any]:
        values: dict[str, Any] = {}
        for path, value in assignments:
            _set_nested(values, path, value, context)
        return values
