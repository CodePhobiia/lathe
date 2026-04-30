"""Block-level Lark transformer rules for the Lathe parser.

Handles top-level declarations (``profile``, ``contract``, ``asset``,
``variant``, ``critic`` and friends) and their nested structured
blocks.
"""

from __future__ import annotations

import ast as py_ast
from typing import Any

from lark import Transformer, v_args

from .grammar import LatheParseError
from .transformer_expr import _TransformerExprMixin


@v_args(inline=True)
class _TransformerBlocksMixin(_TransformerExprMixin, Transformer):
    def defaults_block(self, *assignments: Any) -> dict[str, Any]:
        """Defaults block.

        Args:
            *assignments: *assignments argument.

        Returns:
            The result.
        """
        return {"node_type": "defaults", "values": self._assignments(assignments, "defaults")}

    def repair_block(self, *assignments: Any) -> dict[str, Any]:
        """Repair block.

        Args:
            *assignments: *assignments argument.

        Returns:
            The result.
        """
        return {"node_type": "repair", "values": self._assignments(assignments, "repair")}

    def params_block(self, *assignments: Any) -> dict[str, Any]:
        """Params block.

        Args:
            *assignments: *assignments argument.

        Returns:
            The result.
        """
        return {"node_type": "params", "values": self._assignments(assignments, "params")}

    def refs_block(self, *assignments: Any) -> dict[str, Any]:
        """Refs block.

        Args:
            *assignments: *assignments argument.

        Returns:
            The result.
        """
        return {"node_type": "refs", "values": self._assignments(assignments, "refs")}

    def intent_block(self, *assignments: Any) -> dict[str, Any]:
        """Intent block.

        Args:
            *assignments: *assignments argument.

        Returns:
            The result.
        """
        return {"node_type": "intent", "values": self._assignments(assignments, "intent")}

    def geometry_block(self, *assignments: Any) -> dict[str, Any]:
        """Geometry block.

        Args:
            *assignments: *assignments argument.

        Returns:
            The result.
        """
        return {"node_type": "geometry", "values": self._assignments(assignments, "geometry")}

    def features_block(self, *assignments: Any) -> dict[str, Any]:
        """Features block.

        Args:
            *assignments: *assignments argument.

        Returns:
            The result.
        """
        return {"node_type": "features", "values": self._assignments(assignments, "features")}

    def source_surface_block(self, *assignments: Any) -> dict[str, Any]:
        """Source surface block.

        Args:
            *assignments: *assignments argument.

        Returns:
            The result.
        """
        return {"node_type": "source_surface", "values": self._assignments(assignments, "surface")}

    def assembly_block(self, *assignments: Any) -> dict[str, Any]:
        """Assembly block.

        Args:
            *assignments: *assignments argument.

        Returns:
            The result.
        """
        return {"node_type": "assembly", "values": self._assignments(assignments, "assembly")}

    def fit_block(self, *assignments: Any) -> dict[str, Any]:
        """Fit block.

        Args:
            *assignments: *assignments argument.

        Returns:
            The result.
        """
        return {"node_type": "fit", "values": self._assignments(assignments, "fit")}

    def transfer_block(self, *assignments: Any) -> dict[str, Any]:
        """Transfer block.

        Args:
            *assignments: *assignments argument.

        Returns:
            The result.
        """
        return {"node_type": "transfer", "values": self._assignments(assignments, "transfer")}

    def reuse_block(self, *assignments: Any) -> dict[str, Any]:
        """Reuse block.

        Args:
            *assignments: *assignments argument.

        Returns:
            The result.
        """
        return {"node_type": "reuse", "values": self._assignments(assignments, "reuse")}

    def constraints_block(self, *assignments: Any) -> dict[str, Any]:
        """Constraints block.

        Args:
            *assignments: *assignments argument.

        Returns:
            The result.
        """
        return {"node_type": "constraints", "values": self._assignments(assignments, "constraints")}

    def ingest_block(self, *assignments: Any) -> dict[str, Any]:
        """Ingest block.

        Args:
            *assignments: *assignments argument.

        Returns:
            The result.
        """
        return {"node_type": "ingest", "values": self._assignments(assignments, "ingest")}

    def assembly_rules_block(self, *assignments: Any) -> dict[str, Any]:
        """Assembly rules block.

        Args:
            *assignments: *assignments argument.

        Returns:
            The result.
        """
        return {"node_type": "assembly_rules", "values": self._assignments(assignments, "assembly_rules")}

    def execution_block(self, *assignments: Any) -> dict[str, Any]:
        """Execution block.

        Args:
            *assignments: *assignments argument.

        Returns:
            The result.
        """
        return {"node_type": "execution", "values": self._assignments(assignments, "execution")}

    def space_inline_block(self, *rest: Any) -> dict[str, Any]:
        """Space inline block.

        Args:
            *rest: *rest argument.

        Returns:
            The result.
        """
        return self._space_spec("space_inline", None, *rest)

    def search_inline_block(self, *rest: Any) -> dict[str, Any]:
        """Search inline block.

        Args:
            *rest: *rest argument.

        Returns:
            The result.
        """
        return self._space_spec("search_inline", None, *rest)

    def repair_policy_inline_block(self, *assignments: Any) -> dict[str, Any]:
        """Repair policy inline block.

        Args:
            *assignments: *assignments argument.

        Returns:
            The result.
        """
        return {
            "node_type": "repair_policy_inline",
            "values": self._assignments(assignments, "repair_policy"),
        }

    def from_clause(self, name: str) -> dict[str, Any]:
        """From clause.

        Args:
            name: name argument.

        Returns:
            The result.
        """
        return {"node_type": "from_clause", "name": name}

    def shape_block(self, *assignments: Any) -> dict[str, Any]:
        """Shape block.

        Args:
            *assignments: *assignments argument.

        Returns:
            The result.
        """
        return {"node_type": "shape", "values": self._assignments(assignments, "shape")}

    def topology_block(self, *assignments: Any) -> dict[str, Any]:
        """Topology block.

        Args:
            *assignments: *assignments argument.

        Returns:
            The result.
        """
        return {"node_type": "topology", "values": self._assignments(assignments, "topology")}

    def uv_block(self, *assignments: Any) -> dict[str, Any]:
        """Uv block.

        Args:
            *assignments: *assignments argument.

        Returns:
            The result.
        """
        return {"node_type": "uv", "values": self._assignments(assignments, "uv")}

    def build_surface_block(self, *assignments: Any) -> dict[str, Any]:
        """Build surface block.

        Args:
            *assignments: *assignments argument.

        Returns:
            The result.
        """
        return {"node_type": "surface", "values": self._assignments(assignments, "build.surface")}

    def rig_block(self, *assignments: Any) -> dict[str, Any]:
        """Rig block.

        Args:
            *assignments: *assignments argument.

        Returns:
            The result.
        """
        return {"node_type": "rig", "values": self._assignments(assignments, "rig")}

    def interfaces_block(self, *assignments: Any) -> dict[str, Any]:
        """Interfaces block.

        Args:
            *assignments: *assignments argument.

        Returns:
            The result.
        """
        return {"node_type": "interfaces", "values": self._assignments(assignments, "interfaces")}

    def physics_block(self, *assignments: Any) -> dict[str, Any]:
        """Physics block.

        Args:
            *assignments: *assignments argument.

        Returns:
            The result.
        """
        return {"node_type": "physics", "values": self._assignments(assignments, "physics")}

    def optimize_block(self, *assignments: Any) -> dict[str, Any]:
        """Optimize block.

        Args:
            *assignments: *assignments argument.

        Returns:
            The result.
        """
        return {"node_type": "optimize", "values": self._assignments(assignments, "optimize")}

    def build_block(self, *stage_blocks: Any) -> dict[str, Any]:
        """Build block.

        Args:
            *stage_blocks: *stage_blocks argument.

        Returns:
            The result.
        """
        values: dict[str, Any] = {}
        for item in stage_blocks:
            if item is None:
                continue
            values[item["node_type"]] = item["values"]
        return {"node_type": "build", "values": values}

    def validate_block(self, *items: Any) -> dict[str, Any]:
        """Validate block.

        Args:
            *items: *items argument.

        Returns:
            The result.
        """
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
        """Package block.

        Args:
            *assignments: *assignments argument.

        Returns:
            The result.
        """
        return {"node_type": "package", "values": self._assignments(assignments, "package")}

    def publish_block(self, *assignments: Any) -> dict[str, Any]:
        """Publish block.

        Args:
            *assignments: *assignments argument.

        Returns:
            The result.
        """
        return {"node_type": "publish", "values": self._assignments(assignments, "publish")}

    def experimental_block(self, *entries: Any) -> dict[str, Any]:
        """Phase 13 experimental wrapper.

        Args:
            *entries: experimental sub-block entries.

        Returns:
            The merged values dict for the experimental wrapper.
        """
        values: dict[str, Any] = {}
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            kind = entry.get("node_type")
            if kind == "experimental_art_direction":
                values["art_direction"] = entry["values"]
            elif kind == "experimental_references":
                values["references"] = entry["values"]
            elif kind == "experimental_kit":
                values["kit"] = entry["values"]
        return {"node_type": "experimental", "values": values}

    def experimental_art_direction_block(self, *fields: Any) -> dict[str, Any]:
        """Phase 13 ``experimental.art_direction`` block."""
        out: dict[str, Any] = {}
        for field in fields:
            if isinstance(field, tuple) and len(field) == 2:
                out[field[0]] = field[1]
        return {"node_type": "experimental_art_direction", "values": out}

    def experimental_art_direction_style_tags(self, value: Any) -> tuple[str, Any]:
        return ("style_tags", list(value) if isinstance(value, list) else value)

    def experimental_art_direction_wear(self, value: Any) -> tuple[str, Any]:
        return ("wear", py_ast.literal_eval(value) if isinstance(value, str) else value)

    def experimental_art_direction_material_age(self, value: Any) -> tuple[str, Any]:
        return ("material_age", py_ast.literal_eval(value) if isinstance(value, str) else value)

    def experimental_art_direction_detail_density(self, value: Any) -> tuple[str, Any]:
        return ("detail_density", py_ast.literal_eval(value) if isinstance(value, str) else value)

    def experimental_references_block(self, value: Any) -> dict[str, Any]:
        """Phase 13 ``experimental.references`` block."""
        path = py_ast.literal_eval(value) if isinstance(value, str) else value
        return {"node_type": "experimental_references", "values": {"use": path}}

    def experimental_kit_block(self, value: Any) -> dict[str, Any]:
        """Phase 13 ``experimental.kit`` block."""
        items = list(value) if isinstance(value, list) else value
        return {"node_type": "experimental_kit", "values": {"use": items}}

    def ensure_rule(self, expr: Any) -> dict[str, Any]:
        """Ensure rule.

        Args:
            expr: expr argument.

        Returns:
            The result.
        """
        return {"node_type": "rule", "kind": "ensure", "expr": expr}

    def prefer_rule(self, expr: Any, weight: Any = None) -> dict[str, Any]:
        """Prefer rule.

        Args:
            expr: expr argument.
            weight: weight argument.

        Returns:
            The result.
        """
        rule = {"node_type": "rule", "kind": "prefer", "expr": expr}
        if weight is not None:
            rule["weight"] = float(weight)
        return rule

    def vary_stmt(self, path: str, domain: Any) -> dict[str, Any]:
        """Vary stmt.

        Args:
            path: path argument.
            domain: domain argument.

        Returns:
            The result.
        """
        return {"node_type": "space_stmt", "kind": "vary", "path": path, "domain": domain}

    def freeze_stmt(self, path: str) -> dict[str, Any]:
        """Freeze stmt.

        Args:
            path: path argument.

        Returns:
            The result.
        """
        return {"node_type": "space_stmt", "kind": "freeze", "path": path}

    def objective_stmt(self, direction: str, metric: Any, weight: Any = None) -> dict[str, Any]:
        """Objective stmt.

        Args:
            direction: direction argument.
            metric: metric argument.
            weight: weight argument.

        Returns:
            The result.
        """
        item = {"node_type": "space_stmt", "kind": "objective", "direction": direction, "metric": metric}
        if weight is not None:
            item["weight"] = float(weight)
        return item

    def maximize_dir(self) -> str:
        """Maximize dir.

        Returns:
            The result.
        """
        return "maximize"

    def minimize_dir(self) -> str:
        """Minimize dir.

        Returns:
            The result.
        """
        return "minimize"

    def select_best_of_stmt(self, value: int | float) -> dict[str, Any]:
        """Select best of stmt.

        Args:
            value: value argument.

        Returns:
            The result.
        """
        return {"node_type": "space_stmt", "kind": "select", "best_of": int(value)}

    def space_stmt(self, item: Any) -> Any:
        """Space stmt.

        Args:
            item: item argument.

        Returns:
            The result.
        """
        return item

    def assert_stmt(self, expr: Any) -> dict[str, Any]:
        """Assert stmt.

        Args:
            expr: expr argument.

        Returns:
            The result.
        """
        return {"node_type": "assert", "expr": expr}

    def assign_stmt(self, path: str, value: Any) -> tuple[str, Any]:
        """Assign stmt.

        Args:
            path: path argument.
            value: value argument.

        Returns:
            The result.
        """
        return (path, value)

    def set_patch(self, path: str, value: Any) -> dict[str, Any]:
        """Set patch.

        Args:
            path: path argument.
            value: value argument.

        Returns:
            The result.
        """
        return {"op": "set", "path": path, "value": value}

    def append_patch(self, path: str, value: Any) -> dict[str, Any]:
        """Append patch.

        Args:
            path: path argument.
            value: value argument.

        Returns:
            The result.
        """
        return {"op": "append", "path": path, "value": value}

    def remove_patch(self, path: str, value: Any) -> dict[str, Any]:
        """Remove patch.

        Args:
            path: path argument.
            value: value argument.

        Returns:
            The result.
        """
        return {"op": "remove", "path": path, "value": value}

    def unset_patch(self, path: str) -> dict[str, Any]:
        """Unset patch.

        Args:
            path: path argument.

        Returns:
            The result.
        """
        return {"op": "unset", "path": path}
