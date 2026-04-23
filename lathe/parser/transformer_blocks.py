from __future__ import annotations

from typing import Any

from lark import Transformer, v_args

from .grammar import LatheParseError
from .transformer_expr import _TransformerExprMixin


@v_args(inline=True)
class _TransformerBlocksMixin(_TransformerExprMixin, Transformer):
    def defaults_block(self, *assignments: Any) -> dict[str, Any]:
        return {"node_type": "defaults", "values": self._assignments(assignments, "defaults")}

    def repair_block(self, *assignments: Any) -> dict[str, Any]:
        return {"node_type": "repair", "values": self._assignments(assignments, "repair")}

    def params_block(self, *assignments: Any) -> dict[str, Any]:
        return {"node_type": "params", "values": self._assignments(assignments, "params")}

    def refs_block(self, *assignments: Any) -> dict[str, Any]:
        return {"node_type": "refs", "values": self._assignments(assignments, "refs")}

    def intent_block(self, *assignments: Any) -> dict[str, Any]:
        return {"node_type": "intent", "values": self._assignments(assignments, "intent")}

    def geometry_block(self, *assignments: Any) -> dict[str, Any]:
        return {"node_type": "geometry", "values": self._assignments(assignments, "geometry")}

    def features_block(self, *assignments: Any) -> dict[str, Any]:
        return {"node_type": "features", "values": self._assignments(assignments, "features")}

    def source_surface_block(self, *assignments: Any) -> dict[str, Any]:
        return {"node_type": "source_surface", "values": self._assignments(assignments, "surface")}

    def assembly_block(self, *assignments: Any) -> dict[str, Any]:
        return {"node_type": "assembly", "values": self._assignments(assignments, "assembly")}

    def fit_block(self, *assignments: Any) -> dict[str, Any]:
        return {"node_type": "fit", "values": self._assignments(assignments, "fit")}

    def transfer_block(self, *assignments: Any) -> dict[str, Any]:
        return {"node_type": "transfer", "values": self._assignments(assignments, "transfer")}

    def reuse_block(self, *assignments: Any) -> dict[str, Any]:
        return {"node_type": "reuse", "values": self._assignments(assignments, "reuse")}

    def constraints_block(self, *assignments: Any) -> dict[str, Any]:
        return {"node_type": "constraints", "values": self._assignments(assignments, "constraints")}

    def ingest_block(self, *assignments: Any) -> dict[str, Any]:
        return {"node_type": "ingest", "values": self._assignments(assignments, "ingest")}

    def assembly_rules_block(self, *assignments: Any) -> dict[str, Any]:
        return {"node_type": "assembly_rules", "values": self._assignments(assignments, "assembly_rules")}

    def execution_block(self, *assignments: Any) -> dict[str, Any]:
        return {"node_type": "execution", "values": self._assignments(assignments, "execution")}

    def space_inline_block(self, *rest: Any) -> dict[str, Any]:
        return self._space_spec("space_inline", None, *rest)

    def search_inline_block(self, *rest: Any) -> dict[str, Any]:
        return self._space_spec("search_inline", None, *rest)

    def repair_policy_inline_block(self, *assignments: Any) -> dict[str, Any]:
        return {"node_type": "repair_policy_inline", "values": self._assignments(assignments, "repair_policy")}

    def from_clause(self, name: str) -> dict[str, Any]:
        return {"node_type": "from_clause", "name": name}

    def shape_block(self, *assignments: Any) -> dict[str, Any]:
        return {"node_type": "shape", "values": self._assignments(assignments, "shape")}

    def topology_block(self, *assignments: Any) -> dict[str, Any]:
        return {"node_type": "topology", "values": self._assignments(assignments, "topology")}

    def uv_block(self, *assignments: Any) -> dict[str, Any]:
        return {"node_type": "uv", "values": self._assignments(assignments, "uv")}

    def build_surface_block(self, *assignments: Any) -> dict[str, Any]:
        return {"node_type": "surface", "values": self._assignments(assignments, "build.surface")}

    def rig_block(self, *assignments: Any) -> dict[str, Any]:
        return {"node_type": "rig", "values": self._assignments(assignments, "rig")}

    def interfaces_block(self, *assignments: Any) -> dict[str, Any]:
        return {"node_type": "interfaces", "values": self._assignments(assignments, "interfaces")}

    def physics_block(self, *assignments: Any) -> dict[str, Any]:
        return {"node_type": "physics", "values": self._assignments(assignments, "physics")}

    def optimize_block(self, *assignments: Any) -> dict[str, Any]:
        return {"node_type": "optimize", "values": self._assignments(assignments, "optimize")}

    def build_block(self, *stage_blocks: Any) -> dict[str, Any]:
        values: dict[str, Any] = {}
        for item in stage_blocks:
            if item is None:
                continue
            values[item["node_type"]] = item["values"]
        return {"node_type": "build", "values": values}

    def validate_block(self, *items: Any) -> dict[str, Any]:
        rules: list[dict[str, Any]] = []
        values: dict[str, Any] = {}
        repair: dict[str, Any] = {}
        assignments: list[tuple[str, Any]] = []
        for item in items:
            if item is None:
                continue
            if isinstance(item, dict) and item.get("node_type") == "rule":
                rules.append(item)
            elif isinstance(item, dict) and item.get("node_type") == "repair":
                repair = item["values"]
            elif isinstance(item, tuple) and len(item) == 2:
                assignments.append(item)
            else:
                raise LatheParseError(f"Unexpected validate item: {item!r}")
        values.update(self._assignments(assignments, "validate"))
        values["rules"] = rules
        values["repair"] = repair
        return {"node_type": "validate", "values": values}

    def package_block(self, *assignments: Any) -> dict[str, Any]:
        return {"node_type": "package", "values": self._assignments(assignments, "package")}

    def publish_block(self, *assignments: Any) -> dict[str, Any]:
        return {"node_type": "publish", "values": self._assignments(assignments, "publish")}

    def ensure_rule(self, expr: Any) -> dict[str, Any]:
        return {"node_type": "rule", "kind": "ensure", "expr": expr}

    def prefer_rule(self, expr: Any, weight: Any = None) -> dict[str, Any]:
        rule = {"node_type": "rule", "kind": "prefer", "expr": expr}
        if weight is not None:
            rule["weight"] = float(weight)
        return rule

    def vary_stmt(self, path: str, domain: Any) -> dict[str, Any]:
        return {"node_type": "space_stmt", "kind": "vary", "path": path, "domain": domain}

    def freeze_stmt(self, path: str) -> dict[str, Any]:
        return {"node_type": "space_stmt", "kind": "freeze", "path": path}

    def objective_stmt(self, direction: str, metric: Any, weight: Any = None) -> dict[str, Any]:
        item = {"node_type": "space_stmt", "kind": "objective", "direction": direction, "metric": metric}
        if weight is not None:
            item["weight"] = float(weight)
        return item

    def maximize_dir(self) -> str:
        return "maximize"

    def minimize_dir(self) -> str:
        return "minimize"

    def select_best_of_stmt(self, value: int | float) -> dict[str, Any]:
        return {"node_type": "space_stmt", "kind": "select", "best_of": int(value)}

    def space_stmt(self, item: Any) -> Any:
        return item

    def assert_stmt(self, expr: Any) -> dict[str, Any]:
        return {"node_type": "assert", "expr": expr}

    def assign_stmt(self, path: str, value: Any) -> tuple[str, Any]:
        return (path, value)

    def set_patch(self, path: str, value: Any) -> dict[str, Any]:
        return {"op": "set", "path": path, "value": value}

    def append_patch(self, path: str, value: Any) -> dict[str, Any]:
        return {"op": "append", "path": path, "value": value}

    def remove_patch(self, path: str, value: Any) -> dict[str, Any]:
        return {"op": "remove", "path": path, "value": value}

    def unset_patch(self, path: str) -> dict[str, Any]:
        return {"op": "unset", "path": path}
