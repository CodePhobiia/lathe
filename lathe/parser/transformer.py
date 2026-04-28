"""Lark-tree to raw-AST-JSON transformer.

Visits the formal-grammar parse tree and emits the same mapping/list
shapes the fast parser produces. Delegates block and expression
handling to ``transformer_blocks`` and ``transformer_expr``.
"""

from __future__ import annotations

from typing import Any

from lark import Transformer, v_args

from .grammar import LatheParseError, _dedupe_keep_first, _empty_program
from .transformer_blocks import _TransformerBlocksMixin


@v_args(inline=True)
class _LatheTransformer(_TransformerBlocksMixin, Transformer):
    def program(self, *items: Any) -> dict[str, Any]:
        """Program.

        Args:
            *items: *items argument.

        Returns:
            The result.
        """
        program = _empty_program()
        for item in items:
            if not item:
                continue
            kind = item["node_type"]
            if kind == "module":
                program["module"] = item["name"]
            elif kind == "import":
                program["imports"].append(item["name"])
            elif kind == "profile":
                program["profiles"].append(item)
            elif kind == "contract":
                program["contracts"].append(item)
            elif kind == "critic":
                program["critics"].append(item)
            elif kind == "library":
                program["libraries"].append(item)
            elif kind == "kit":
                program["kits"].append(item)
            elif kind == "pattern":
                program["patterns"].append(item)
            elif kind == "family":
                program["families"].append(item)
            elif kind == "component":
                program["components"].append(item)
            elif kind == "assembly_decl":
                program["assemblies"].append(item)
            elif kind == "trait":
                program["traits"].append(item)
            elif kind == "mechanism":
                program["mechanisms"].append(item)
            elif kind == "material":
                program["materials"].append(item)
            elif kind == "surface_program":
                program["surface_programs"].append(item)
            elif kind == "surface_backend":
                program["surface_backends"].append(item)
            elif kind == "surface_policy":
                program["surface_policies"].append(item)
            elif kind == "decal_library":
                program["decal_libraries"].append(item)
            elif kind == "mask_program":
                program["mask_programs"].append(item)
            elif kind == "trim_sheet":
                program["trim_sheets"].append(item)
            elif kind == "palette":
                program["palettes"].append(item)
            elif kind == "reference_set":
                program["reference_sets"].append(item)
            elif kind == "reconstruct_policy":
                program["reconstruct_policies"].append(item)
            elif kind == "adapt_policy":
                program["adapt_policies"].append(item)
            elif kind == "assembly_policy":
                program["assembly_policies"].append(item)
            elif kind == "fit_profile":
                program["fit_profiles"].append(item)
            elif kind == "transfer_rule":
                program["transfer_rules"].append(item)
            elif kind == "execution_profile":
                program["execution_profiles"].append(item)
            elif kind == "render_fixture":
                program["render_fixtures"].append(item)
            elif kind == "bake_profile":
                program["bake_profiles"].append(item)
            elif kind == "library_binding":
                program["library_bindings"].append(item)
            elif kind == "material_graph":
                program["material_graphs"].append(item)
            elif kind == "inspection_policy":
                program["inspection_policies"].append(item)
            elif kind == "repair_policy":
                program["repair_policies"].append(item)
            elif kind == "fixture":
                program["fixtures"].append(item)
            elif kind == "test":
                program["tests"].append(item)
            elif kind == "benchmark":
                program["benchmarks"].append(item)
            elif kind == "space_decl":
                program["spaces"].append(item)
            elif kind == "asset":
                program["assets"].append(item)
            elif kind == "variant":
                program["variants"].append(item)
            else:
                raise LatheParseError(f"Unknown program item: {kind}")
        program["imports"] = _dedupe_keep_first(program["imports"])
        return program

    def module_decl(self, name: str) -> dict[str, Any]:
        """Module decl.

        Args:
            name: name argument.

        Returns:
            The result.
        """
        return {"node_type": "module", "name": name}

    def import_decl(self, name: str) -> dict[str, Any]:
        """Import decl.

        Args:
            name: name argument.

        Returns:
            The result.
        """
        return {"node_type": "import", "name": name}

    def use_clause(self, first: str, *rest: str) -> list[str]:
        """Use clause.

        Args:
            first: first argument.
            *rest: *rest argument.

        Returns:
            The result.
        """
        return [first, *rest]

    def profile_decl(self, name: str, *rest: Any) -> dict[str, Any]:
        """Profile decl.

        Args:
            name: name argument.
            *rest: *rest argument.

        Returns:
            The result.
        """
        return self._profile_or_contract("profile", name, *rest)

    def contract_decl(self, name: str, *rest: Any) -> dict[str, Any]:
        """Contract decl.

        Args:
            name: name argument.
            *rest: *rest argument.

        Returns:
            The result.
        """
        return self._profile_or_contract("contract", name, *rest)

    def critic_decl(self, name: str, param_name: str, body: Any) -> dict[str, Any]:
        """Critic decl.

        Args:
            name: name argument.
            param_name: param_name argument.
            body: body argument.

        Returns:
            The result.
        """
        return {
            "node_type": "critic",
            "name": name,
            "param": {"name": param_name, "type": "asset"},
            "body": body,
        }

    def weighted_critic(self, *items: Any) -> dict[str, Any]:
        """Weighted critic.

        Args:
            *items: *items argument.

        Returns:
            The result.
        """
        return {"type": "weighted", "items": list(items)}

    def weighted_item(self, metric: Any, weight: int | float) -> dict[str, Any]:
        """Weighted item.

        Args:
            metric: metric argument.
            weight: weight argument.

        Returns:
            The result.
        """
        return {"metric": metric, "weight": float(weight)}

    def family_decl(self, name: str, *rest: Any) -> dict[str, Any]:
        """Family decl.

        Args:
            name: name argument.
            *rest: *rest argument.

        Returns:
            The result.
        """
        decl_kind: str | None = None
        remaining: list[Any] = []
        for item in rest:
            if (
                decl_kind is None
                and isinstance(item, str)
                and item in {"hard_surface_prop", "env_module", "mechanical_assembly"}
            ):
                decl_kind = item
            else:
                remaining.append(item)
        return self._structured_decl("family", name, *remaining, kind=decl_kind)

    def component_decl(self, name: str, *rest: Any) -> dict[str, Any]:
        """Component decl.

        Args:
            name: name argument.
            *rest: *rest argument.

        Returns:
            The result.
        """
        return self._structured_decl("component", name, *rest)

    def assembly_decl(self, name: str, *rest: Any) -> dict[str, Any]:
        """Assembly decl.

        Args:
            name: name argument.
            *rest: *rest argument.

        Returns:
            The result.
        """
        return self._structured_decl("assembly_decl", name, *rest)

    def trait_decl(self, name: str, *rest: Any) -> dict[str, Any]:
        """Trait decl.

        Args:
            name: name argument.
            *rest: *rest argument.

        Returns:
            The result.
        """
        return self._structured_decl("trait", name, *rest)

    def mechanism_decl(self, name: str, *rest: Any) -> dict[str, Any]:
        """Mechanism decl.

        Args:
            name: name argument.
            *rest: *rest argument.

        Returns:
            The result.
        """
        return self._structured_decl("mechanism", name, *rest)

    def library_decl(self, name: str, *rest: Any) -> dict[str, Any]:
        """Library decl.

        Args:
            name: name argument.
            *rest: *rest argument.

        Returns:
            The result.
        """
        return self._mapping_decl("library", name, *rest)

    def kit_decl(self, name: str, *rest: Any) -> dict[str, Any]:
        """Kit decl.

        Args:
            name: name argument.
            *rest: *rest argument.

        Returns:
            The result.
        """
        return self._mapping_decl("kit", name, *rest)

    def pattern_decl(self, name: str, *rest: Any) -> dict[str, Any]:
        """Pattern decl.

        Args:
            name: name argument.
            *rest: *rest argument.

        Returns:
            The result.
        """
        return self._mapping_decl("pattern", name, *rest)

    def material_decl(self, name: str, *rest: Any) -> dict[str, Any]:
        """Material decl.

        Args:
            name: name argument.
            *rest: *rest argument.

        Returns:
            The result.
        """
        return self._mapping_decl("material", name, *rest)

    def surface_program_decl(self, name: str, *rest: Any) -> dict[str, Any]:
        """Surface program decl.

        Args:
            name: name argument.
            *rest: *rest argument.

        Returns:
            The result.
        """
        return self._mapping_decl("surface_program", name, *rest)

    def surface_backend_decl(self, name: str, *rest: Any) -> dict[str, Any]:
        """Surface backend decl.

        Args:
            name: name argument.
            *rest: *rest argument.

        Returns:
            The result.
        """
        return self._mapping_decl("surface_backend", name, *rest)

    def surface_policy_decl(self, name: str, *rest: Any) -> dict[str, Any]:
        """Surface policy decl.

        Args:
            name: name argument.
            *rest: *rest argument.

        Returns:
            The result.
        """
        return self._mapping_decl("surface_policy", name, *rest)

    def decal_library_decl(self, name: str, *rest: Any) -> dict[str, Any]:
        """Decal library decl.

        Args:
            name: name argument.
            *rest: *rest argument.

        Returns:
            The result.
        """
        return self._mapping_decl("decal_library", name, *rest)

    def mask_program_decl(self, name: str, *rest: Any) -> dict[str, Any]:
        """Mask program decl.

        Args:
            name: name argument.
            *rest: *rest argument.

        Returns:
            The result.
        """
        return self._mapping_decl("mask_program", name, *rest)

    def trim_sheet_decl(self, name: str, *rest: Any) -> dict[str, Any]:
        """Trim sheet decl.

        Args:
            name: name argument.
            *rest: *rest argument.

        Returns:
            The result.
        """
        return self._mapping_decl("trim_sheet", name, *rest)

    def palette_decl(self, name: str, *rest: Any) -> dict[str, Any]:
        """Palette decl.

        Args:
            name: name argument.
            *rest: *rest argument.

        Returns:
            The result.
        """
        return self._mapping_decl("palette", name, *rest)

    def reference_set_decl(self, name: str, *rest: Any) -> dict[str, Any]:
        """Reference set decl.

        Args:
            name: name argument.
            *rest: *rest argument.

        Returns:
            The result.
        """
        return self._mapping_decl("reference_set", name, *rest)

    def reconstruct_policy_decl(self, name: str, *rest: Any) -> dict[str, Any]:
        """Reconstruct policy decl.

        Args:
            name: name argument.
            *rest: *rest argument.

        Returns:
            The result.
        """
        return self._mapping_decl("reconstruct_policy", name, *rest)

    def adapt_policy_decl(self, name: str, *rest: Any) -> dict[str, Any]:
        """Adapt policy decl.

        Args:
            name: name argument.
            *rest: *rest argument.

        Returns:
            The result.
        """
        return self._mapping_decl("adapt_policy", name, *rest)

    def assembly_policy_decl(self, name: str, *rest: Any) -> dict[str, Any]:
        """Assembly policy decl.

        Args:
            name: name argument.
            *rest: *rest argument.

        Returns:
            The result.
        """
        return self._mapping_decl("assembly_policy", name, *rest)

    def fit_profile_decl(self, name: str, *rest: Any) -> dict[str, Any]:
        """Fit profile decl.

        Args:
            name: name argument.
            *rest: *rest argument.

        Returns:
            The result.
        """
        return self._mapping_decl("fit_profile", name, *rest)

    def transfer_rule_decl(self, name: str, *rest: Any) -> dict[str, Any]:
        """Transfer rule decl.

        Args:
            name: name argument.
            *rest: *rest argument.

        Returns:
            The result.
        """
        return self._mapping_decl("transfer_rule", name, *rest)

    def execution_profile_decl(self, name: str, *rest: Any) -> dict[str, Any]:
        """Execution profile decl.

        Args:
            name: name argument.
            *rest: *rest argument.

        Returns:
            The result.
        """
        return self._mapping_decl("execution_profile", name, *rest)

    def render_fixture_decl(self, name: str, *rest: Any) -> dict[str, Any]:
        """Render fixture decl.

        Args:
            name: name argument.
            *rest: *rest argument.

        Returns:
            The result.
        """
        return self._mapping_decl("render_fixture", name, *rest)

    def bake_profile_decl(self, name: str, *rest: Any) -> dict[str, Any]:
        """Bake profile decl.

        Args:
            name: name argument.
            *rest: *rest argument.

        Returns:
            The result.
        """
        return self._mapping_decl("bake_profile", name, *rest)

    def library_binding_decl(self, name: str, *rest: Any) -> dict[str, Any]:
        """Library binding decl.

        Args:
            name: name argument.
            *rest: *rest argument.

        Returns:
            The result.
        """
        return self._mapping_decl("library_binding", name, *rest)

    def material_graph_decl(self, name: str, *rest: Any) -> dict[str, Any]:
        """Material graph decl.

        Args:
            name: name argument.
            *rest: *rest argument.

        Returns:
            The result.
        """
        return self._mapping_decl("material_graph", name, *rest)

    def inspection_policy_decl(self, name: str, *rest: Any) -> dict[str, Any]:
        """Inspection policy decl.

        Args:
            name: name argument.
            *rest: *rest argument.

        Returns:
            The result.
        """
        return self._mapping_decl("inspection_policy", name, *rest)

    def repair_policy_decl(self, name: str, *assignments: Any) -> dict[str, Any]:
        """Repair policy decl.

        Args:
            name: name argument.
            *assignments: *assignments argument.

        Returns:
            The result.
        """
        return {
            "node_type": "repair_policy",
            "name": name,
            "values": self._assignments(assignments, "repair_policy"),
        }

    def fixture_decl(self, name: str, *assignments: Any) -> dict[str, Any]:
        """Fixture decl.

        Args:
            name: name argument.
            *assignments: *assignments argument.

        Returns:
            The result.
        """
        return {
            "node_type": "fixture",
            "name": name,
            "values": self._assignments(assignments, "fixture"),
        }

    def test_decl(self, name: str, *rest: Any) -> dict[str, Any]:
        """Test decl.

        Args:
            name: name argument.
            *rest: *rest argument.

        Returns:
            The result.
        """
        values: list[tuple[str, Any]] = []
        asserts: list[dict[str, Any]] = []
        for item in rest:
            if isinstance(item, tuple) and len(item) == 2:
                values.append(item)
            elif isinstance(item, dict) and item.get("node_type") == "assert":
                asserts.append(item)
            else:
                raise LatheParseError(f"Unexpected test item: {item!r}")
        return {
            "node_type": "test",
            "name": name,
            "values": self._assignments(values, "test"),
            "asserts": asserts,
        }

    def benchmark_decl(self, name: str, *rest: Any) -> dict[str, Any]:
        """Benchmark decl.

        Args:
            name: name argument.
            *rest: *rest argument.

        Returns:
            The result.
        """
        values: list[tuple[str, Any]] = []
        asserts: list[dict[str, Any]] = []
        for item in rest:
            if isinstance(item, tuple) and len(item) == 2:
                values.append(item)
            elif isinstance(item, dict) and item.get("node_type") == "assert":
                asserts.append(item)
            else:
                raise LatheParseError(f"Unexpected benchmark item: {item!r}")
        return {
            "node_type": "benchmark",
            "name": name,
            "values": self._assignments(values, "benchmark"),
            "asserts": asserts,
        }

    def space_decl(self, name: str, *rest: Any) -> dict[str, Any]:
        """Space decl.

        Args:
            name: name argument.
            *rest: *rest argument.

        Returns:
            The result.
        """
        return self._space_spec("space_decl", name, *rest)

    def asset_decl(self, name: str, kind: str, *rest: Any) -> dict[str, Any]:
        """Asset decl.

        Args:
            name: name argument.
            kind: kind argument.
            *rest: *rest argument.

        Returns:
            The result.
        """
        from_family = ""
        uses: list[str] = []
        refs: dict[str, Any] = {}
        intent: dict[str, Any] = {}
        geometry: dict[str, Any] = {}
        features: dict[str, Any] = {}
        surface: dict[str, Any] = {}
        assembly: dict[str, Any] = {}
        fit: dict[str, Any] = {}
        transfer: dict[str, Any] = {}
        reuse: dict[str, Any] = {}
        constraints: dict[str, Any] = {}
        ingest: dict[str, Any] = {}
        assembly_rules: dict[str, Any] = {}
        execution: dict[str, Any] = {}
        space: dict[str, Any] = {}
        repair_policy: dict[str, Any] = {}
        build: dict[str, Any] = {}
        validate: dict[str, Any] = {}
        package: dict[str, Any] = {}
        publish: dict[str, Any] = {}
        for item in rest:
            if item is None:
                continue
            if isinstance(item, dict) and item.get("node_type") == "from_clause":
                from_family = item["name"]
                continue
            if isinstance(item, list) and item and isinstance(item[0], str):
                uses = item
            elif isinstance(item, dict) and item.get("node_type") == "refs":
                refs = item["values"]
            elif isinstance(item, dict) and item.get("node_type") == "intent":
                intent = item["values"]
            elif isinstance(item, dict) and item.get("node_type") == "geometry":
                geometry = item["values"]
            elif isinstance(item, dict) and item.get("node_type") == "features":
                features = item["values"]
            elif isinstance(item, dict) and item.get("node_type") == "source_surface":
                surface = item["values"]
            elif isinstance(item, dict) and item.get("node_type") == "assembly":
                assembly = item["values"]
            elif isinstance(item, dict) and item.get("node_type") == "fit":
                fit = item["values"]
            elif isinstance(item, dict) and item.get("node_type") == "transfer":
                transfer = item["values"]
            elif isinstance(item, dict) and item.get("node_type") == "reuse":
                reuse = item["values"]
            elif isinstance(item, dict) and item.get("node_type") == "constraints":
                constraints = item["values"]
            elif isinstance(item, dict) and item.get("node_type") == "ingest":
                ingest = item["values"]
            elif isinstance(item, dict) and item.get("node_type") == "assembly_rules":
                assembly_rules = item["values"]
            elif isinstance(item, dict) and item.get("node_type") == "execution":
                execution = item["values"]
            elif isinstance(item, dict) and item.get("node_type") in {
                "space_inline",
                "search_inline",
            }:
                space = item
            elif isinstance(item, dict) and item.get("node_type") == "repair_policy_inline":
                repair_policy = item["values"]
            elif isinstance(item, dict) and item.get("node_type") == "build":
                build = item["values"]
            elif isinstance(item, dict) and item.get("node_type") == "validate":
                validate = item["values"]
            elif isinstance(item, dict) and item.get("node_type") == "package":
                package = item["values"]
            elif isinstance(item, dict) and item.get("node_type") == "publish":
                publish = item["values"]
            else:
                raise LatheParseError(f"Unexpected asset item: {item!r}")
        return {
            "node_type": "asset",
            "name": name,
            "kind": kind,
            "from": from_family,
            "uses": _dedupe_keep_first(uses),
            "refs": refs,
            "intent": intent,
            "geometry": geometry,
            "features": features,
            "surface": surface,
            "assembly": assembly,
            "fit": fit,
            "transfer": transfer,
            "reuse": reuse,
            "constraints": constraints,
            "ingest": ingest,
            "assembly_rules": assembly_rules,
            "execution": execution,
            "space": space,
            "repair_policy": repair_policy,
            "build": build,
            "validate": validate,
            "package": package,
            "publish": publish,
        }

    def variant_decl(self, name: str, base: str, *patches: Any) -> dict[str, Any]:
        """Variant decl.

        Args:
            name: name argument.
            base: base argument.
            *patches: *patches argument.

        Returns:
            The result.
        """
        return {
            "node_type": "variant",
            "name": name,
            "on": base,
            "patches": list(patches),
        }

    def kind(self, token: Any) -> str:
        """Kind.

        Args:
            token: token argument.

        Returns:
            The result.
        """
        return str(token)
