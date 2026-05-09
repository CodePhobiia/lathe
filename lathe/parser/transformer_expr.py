"""Expression-level Lark transformer rules for the Lathe parser.

Mirrors ``fast_parser_expr`` for the formal grammar path, including
units, binary ops and literal folding.
"""

from __future__ import annotations

import ast as py_ast
from collections.abc import Iterable
from typing import Any

from lark import Transformer, v_args

from .grammar import (
    _UNIT_RE,
    LatheParseError,
    _dedupe_keep_first,
    _num,
    _set_nested,
)


@v_args(inline=True)
class _TransformerExprMixin(Transformer):
    def list(self, *items: Any) -> list[Any]:
        """List.

        Args:
            *items: *items argument.

        Returns:
            The result.
        """
        return list(items)

    def call(self, name: str, args: list[Any] | None = None) -> dict[str, Any]:
        """Call.

        Args:
            name: name argument.
            args: args argument.

        Returns:
            The result.
        """
        return {"type": "call", "name": name, "args": args or []}

    def args(self, *items: Any) -> list[Any]:
        """Args.

        Args:
            *items: *items argument.

        Returns:
            The result.
        """
        return list(items)

    def named_arg(self, name: str, value: Any) -> dict[str, Any]:
        """Named arg.

        Args:
            name: name argument.
            value: value argument.

        Returns:
            The result.
        """
        return {"name": name, "value": value}

    def positional_arg(self, value: Any) -> dict[str, Any]:
        """Positional arg.

        Args:
            value: value argument.

        Returns:
            The result.
        """
        return {"name": None, "value": value}

    def qident(self, first: str, *rest: str) -> str:
        """Qident.

        Args:
            first: first argument.
            *rest: *rest argument.

        Returns:
            The result.
        """
        return ".".join([first, *rest])

    def path(self, first: str, *rest: str) -> str:
        """Path.

        Args:
            first: first argument.
            *rest: *rest argument.

        Returns:
            The result.
        """
        return ".".join([first, *rest])

    def ident_expr(self, name: str) -> str:
        """Ident expr.

        Args:
            name: name argument.

        Returns:
            The result.
        """
        return name

    def string_lit(self, token: str) -> str:
        """String lit.

        Args:
            token: token argument.

        Returns:
            The result.
        """
        return py_ast.literal_eval(token)

    def number(self, token: Any) -> int | float:
        """Number.

        Args:
            token: token argument.

        Returns:
            The result.
        """
        return _num(str(token))

    def number_lit(self, value: int | float) -> int | float:
        """Number lit.

        Args:
            value: value argument.

        Returns:
            The result.
        """
        return value

    def unit_lit(self, token: Any) -> dict[str, Any]:
        """Unit lit.

        Args:
            token: token argument.

        Returns:
            The result.
        """
        text = str(token)
        match = _UNIT_RE.match(text)
        if not match:
            raise LatheParseError(f"Invalid unit literal: {text}")
        return {
            "type": "unit",
            "value": _num(match.group("value")),
            "unit": match.group("unit"),
        }

    def true_lit(self) -> bool:
        """True lit.

        Returns:
            The result.
        """
        return True

    def false_lit(self) -> bool:
        """False lit.

        Returns:
            The result.
        """
        return False

    def range_expr(self, left: Any, right: Any) -> dict[str, Any]:
        """Range expr.

        Args:
            left: left argument.
            right: right argument.

        Returns:
            The result.
        """
        return {"type": "range", "from": left, "to": right}

    def not_expr(self, value: Any) -> dict[str, Any]:
        """Not expr.

        Args:
            value: value argument.

        Returns:
            The result.
        """
        return {"type": "unary", "op": "not", "value": value}

    def neg_expr(self, value: Any) -> dict[str, Any]:
        """Neg expr.

        Args:
            value: value argument.

        Returns:
            The result.
        """
        return {"type": "unary", "op": "-", "value": value}

    def _binary(self, op: str, left: Any, right: Any) -> dict[str, Any]:
        return {"type": "binary", "op": op, "left": left, "right": right}

    def or_expr(self, left: Any, right: Any) -> dict[str, Any]:
        """Or expr.

        Args:
            left: left argument.
            right: right argument.

        Returns:
            The result.
        """
        return self._binary("or", left, right)

    def and_expr(self, left: Any, right: Any) -> dict[str, Any]:
        """And expr.

        Args:
            left: left argument.
            right: right argument.

        Returns:
            The result.
        """
        return self._binary("and", left, right)

    def eq_expr(self, left: Any, right: Any) -> dict[str, Any]:
        """Eq expr.

        Args:
            left: left argument.
            right: right argument.

        Returns:
            The result.
        """
        return self._binary("==", left, right)

    def neq_expr(self, left: Any, right: Any) -> dict[str, Any]:
        """Neq expr.

        Args:
            left: left argument.
            right: right argument.

        Returns:
            The result.
        """
        return self._binary("!=", left, right)

    def lt_expr(self, left: Any, right: Any) -> dict[str, Any]:
        """Lt expr.

        Args:
            left: left argument.
            right: right argument.

        Returns:
            The result.
        """
        return self._binary("<", left, right)

    def lte_expr(self, left: Any, right: Any) -> dict[str, Any]:
        """Lte expr.

        Args:
            left: left argument.
            right: right argument.

        Returns:
            The result.
        """
        return self._binary("<=", left, right)

    def gt_expr(self, left: Any, right: Any) -> dict[str, Any]:
        """Gt expr.

        Args:
            left: left argument.
            right: right argument.

        Returns:
            The result.
        """
        return self._binary(">", left, right)

    def gte_expr(self, left: Any, right: Any) -> dict[str, Any]:
        """Gte expr.

        Args:
            left: left argument.
            right: right argument.

        Returns:
            The result.
        """
        return self._binary(">=", left, right)

    def in_expr(self, left: Any, right: Any) -> dict[str, Any]:
        """In expr.

        Args:
            left: left argument.
            right: right argument.

        Returns:
            The result.
        """
        return self._binary("in", left, right)

    def add_expr(self, left: Any, right: Any) -> dict[str, Any]:
        """Add expr.

        Args:
            left: left argument.
            right: right argument.

        Returns:
            The result.
        """
        return self._binary("+", left, right)

    def sub_expr(self, left: Any, right: Any) -> dict[str, Any]:
        """Sub expr.

        Args:
            left: left argument.
            right: right argument.

        Returns:
            The result.
        """
        return self._binary("-", left, right)

    def mul_expr(self, left: Any, right: Any) -> dict[str, Any]:
        """Mul expr.

        Args:
            left: left argument.
            right: right argument.

        Returns:
            The result.
        """
        return self._binary("*", left, right)

    def div_expr(self, left: Any, right: Any) -> dict[str, Any]:
        """Div expr.

        Args:
            left: left argument.
            right: right argument.

        Returns:
            The result.
        """
        return self._binary("/", left, right)

    def IDENT(self, token: Any) -> str:
        """Ident.

        Args:
            token: token argument.

        Returns:
            The result.
        """
        return str(token)

    def _assignments(self, assignments: Iterable[tuple[str, Any]], context: str) -> dict[str, Any]:
        values: dict[str, Any] = {}
        for path, value in assignments:
            _set_nested(values, path, value, context)
        return values

    def _structured_decl(
        self,
        node_type: str,
        name: str,
        *rest: Any,
        kind: str | None = None,
    ) -> dict[str, Any]:
        uses: list[str] = []
        defaults: dict[str, Any] = {}
        params: dict[str, Any] = {}
        geometry: dict[str, Any] = {}
        features: dict[str, Any] = {}
        surface: dict[str, Any] = {}
        assembly: dict[str, Any] = {}
        space: dict[str, Any] = {}
        repair_policy: dict[str, Any] = {}
        rules: list[dict[str, Any]] = []
        assigns: list[tuple[str, Any]] = []
        version: str = ""
        ports: list[dict[str, Any]] = []
        parameters: list[dict[str, Any]] = []
        body: dict[str, Any] | None = None
        for item in rest:
            if item is None:
                continue
            if isinstance(item, list) and item and isinstance(item[0], str):
                uses = item
            elif isinstance(item, dict):
                node = item.get("node_type")
                if node == "defaults":
                    defaults = item["values"]
                elif node == "params":
                    params = item["values"]
                elif node == "geometry":
                    geometry = item["values"]
                elif node == "features":
                    features = item["values"]
                elif node == "source_surface":
                    surface = item["values"]
                elif node == "assembly":
                    assembly = item["values"]
                elif node in {"space_inline", "search_inline"}:
                    space = item
                elif node == "repair_policy_inline":
                    repair_policy = item["values"]
                elif node == "rule":
                    rules.append(item)
                elif node == "version_clause":
                    version = item.get("version", "")
                elif node == "ports":
                    ports = item.get("ports", [])
                elif node == "parameters":
                    parameters = item.get("parameters", [])
                elif node == "body":
                    body = item
                else:
                    raise LatheParseError(f"Unexpected {node_type} item: {item!r}")
            elif isinstance(item, tuple) and len(item) == 2:
                assigns.append(item)
            else:
                raise LatheParseError(f"Unexpected {node_type} item: {item!r}")
        decl = {
            "node_type": node_type,
            "name": name,
            "kind": kind,
            "uses": _dedupe_keep_first(uses),
            "defaults": defaults,
            "params": params,
            "geometry": geometry,
            "features": features,
            "surface": surface,
            "assembly": assembly,
            "space": space,
            "repair_policy": repair_policy,
            "rules": rules,
            "values": self._assignments(assigns, node_type),
        }
        if version or ports or parameters or body is not None:
            decl["version"] = version
            decl["ports"] = ports
            decl["parameters"] = parameters
            decl["body"] = body or {"node_type": "body", "kit_uses": [], "rules": [], "values": {}}
        return decl

    def _mapping_decl(self, node_type: str, name: str, *rest: Any) -> dict[str, Any]:
        uses: list[str] = []
        assigns: list[tuple[str, Any]] = []
        version: str = ""
        ports: list[dict[str, Any]] = []
        parameters: list[dict[str, Any]] = []
        body: dict[str, Any] | None = None
        for item in rest:
            if item is None:
                continue
            if isinstance(item, list) and item and isinstance(item[0], str):
                uses = item
            elif isinstance(item, tuple) and len(item) == 2:
                assigns.append(item)
            elif isinstance(item, dict):
                node = item.get("node_type")
                if node == "version_clause":
                    version = item.get("version", "")
                elif node == "ports":
                    ports = item.get("ports", [])
                elif node == "parameters":
                    parameters = item.get("parameters", [])
                elif node == "body":
                    body = item
                else:
                    raise LatheParseError(f"Unexpected {node_type} item: {item!r}")
            else:
                raise LatheParseError(f"Unexpected {node_type} item: {item!r}")
        decl = {
            "node_type": node_type,
            "name": name,
            "uses": _dedupe_keep_first(uses),
            "values": self._assignments(assigns, node_type),
        }
        if version or ports or parameters or body is not None:
            decl["version"] = version
            decl["ports"] = ports
            decl["parameters"] = parameters
            decl["body"] = body or {"node_type": "body", "kit_uses": [], "rules": [], "values": {}}
        return decl

    def _space_spec(self, node_type: str, name: str | None, *rest: Any) -> dict[str, Any]:
        assigns: list[tuple[str, Any]] = []
        vary: list[dict[str, Any]] = []
        freeze: list[str] = []
        objectives: list[dict[str, Any]] = []
        select: dict[str, Any] = {}
        for item in rest:
            if item is None:
                continue
            if isinstance(item, tuple) and len(item) == 2:
                assigns.append(item)
            elif isinstance(item, dict) and item.get("node_type") == "space_stmt":
                kind = item["kind"]
                if kind == "vary":
                    vary.append({"path": item["path"], "domain": item["domain"]})
                elif kind == "freeze":
                    freeze.append(item["path"])
                elif kind == "objective":
                    objective = {"direction": item["direction"], "metric": item["metric"]}
                    if "weight" in item:
                        objective["weight"] = item["weight"]
                    objectives.append(objective)
                elif kind == "select":
                    select["best_of"] = item["best_of"]
            else:
                raise LatheParseError(f"Unexpected space item: {item!r}")
        payload = {
            "node_type": node_type,
            "values": self._assignments(assigns, "space"),
            "vary": vary,
            "freeze": _dedupe_keep_first(freeze),
            "objectives": objectives,
            "select": select,
        }
        if name is not None:
            payload["name"] = name
        return payload

    def _profile_or_contract(self, node_type: str, name: str, *rest: Any) -> dict[str, Any]:
        uses: list[str] = []
        defaults: dict[str, Any] = {}
        rules: list[dict[str, Any]] = []
        repair: dict[str, Any] = {}
        for item in rest:
            if item is None:
                continue
            if isinstance(item, list) and item and isinstance(item[0], str):
                uses = item
            elif isinstance(item, dict) and item.get("node_type") == "defaults":
                defaults = item["values"]
            elif isinstance(item, dict) and item.get("node_type") == "repair":
                repair = item["values"]
            elif isinstance(item, dict) and item.get("node_type") == "rule":
                rules.append(item)
            else:
                raise LatheParseError(f"Unexpected {node_type} item: {item!r}")
        return {
            "node_type": node_type,
            "name": name,
            "uses": _dedupe_keep_first(uses),
            "defaults": defaults,
            "rules": rules,
            "repair": repair,
        }
