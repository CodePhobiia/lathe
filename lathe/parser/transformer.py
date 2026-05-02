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
            elif kind == "style_pack":
                program["style_packs"].append(item)
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
            elif kind == "world":
                program["worlds"].append(item)
            elif kind == "scene":
                program["scenes"].append(item)
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

    def style_pack_decl(self, name: str, *rest: Any) -> dict[str, Any]:
        """Style pack decl.

        Args:
            name: name argument.
            *rest: *rest argument.

        Returns:
            The result.
        """
        return self._mapping_decl("style_pack", name, *rest)

    def faction_pack_decl(self, name: str, *rest: Any) -> dict[str, Any]:
        return self._style_system_decl("faction_pack", name, *rest)

    def biome_kit_decl(self, name: str, *rest: Any) -> dict[str, Any]:
        return self._style_system_decl("biome_kit", name, *rest)

    def architecture_grammar_decl(self, name: str, *rest: Any) -> dict[str, Any]:
        return self._style_system_decl("architecture_grammar", name, *rest)

    def object_grammar_decl(self, name: str, *rest: Any) -> dict[str, Any]:
        return self._style_system_decl("object_grammar", name, *rest)

    def _style_system_decl(self, system: str, name: str, *rest: Any) -> dict[str, Any]:
        item = self._mapping_decl("style_pack", name, *rest)
        values = dict(item.get("values", {}))
        values["_style_system"] = system
        item["values"] = values
        return item

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

    def world_decl(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_like_decl("world", name, *items)

    def scene_decl(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_like_decl("scene", name, *items)

    def _scene_like_decl(self, node_type: str, name: str, *items: Any) -> dict[str, Any]:
        values: list[tuple[str, Any]] = []
        styles: list[dict[str, Any]] = []
        style_packs: list[dict[str, Any]] = []
        regions: list[dict[str, Any]] = []
        groups: list[dict[str, Any]] = []
        placement_zones: list[dict[str, Any]] = []
        modules: list[dict[str, Any]] = []
        kits: list[dict[str, Any]] = []
        variant_families: list[dict[str, Any]] = []
        generators: list[dict[str, Any]] = []
        biomes: list[dict[str, Any]] = []
        scatters: list[dict[str, Any]] = []
        environments: list[dict[str, Any]] = []
        objects: list[dict[str, Any]] = []
        arrays: list[dict[str, Any]] = []
        sockets: list[dict[str, Any]] = []
        attachments: list[dict[str, Any]] = []
        relationships: list[dict[str, Any]] = []
        cameras: list[dict[str, Any]] = []
        lights: list[dict[str, Any]] = []
        curiosity_anchors: list[dict[str, Any]] = []
        hidden_state: list[dict[str, Any]] = []
        exports: list[dict[str, Any]] = []
        for item in items:
            if isinstance(item, tuple) and len(item) == 2:
                values.append(item)
            elif isinstance(item, dict) and item.get("node_type") == "scene_style":
                styles.append(item)
            elif isinstance(item, dict) and item.get("node_type") == "scene_style_pack":
                style_packs.append(item)
            elif isinstance(item, dict) and item.get("node_type") == "scene_region":
                regions.append(item)
            elif isinstance(item, dict) and item.get("node_type") == "scene_group":
                groups.append(item)
            elif isinstance(item, dict) and item.get("node_type") == "scene_placement_zone":
                placement_zones.append(item)
            elif isinstance(item, dict) and item.get("node_type") == "scene_module":
                modules.append(item)
            elif isinstance(item, dict) and item.get("node_type") == "scene_kit":
                kits.append(item)
            elif isinstance(item, dict) and item.get("node_type") == "scene_variant_family":
                variant_families.append(item)
            elif isinstance(item, dict) and item.get("node_type") == "scene_generator":
                generators.append(item)
            elif isinstance(item, dict) and item.get("node_type") == "scene_biome":
                biomes.append(item)
            elif isinstance(item, dict) and item.get("node_type") == "scene_scatter":
                scatters.append(item)
            elif isinstance(item, dict) and item.get("node_type") == "scene_environment":
                environments.append(item)
            elif isinstance(item, dict) and item.get("node_type") == "scene_object":
                objects.append(item)
            elif isinstance(item, dict) and item.get("node_type") == "scene_array":
                arrays.append(item)
            elif isinstance(item, dict) and item.get("node_type") == "scene_socket":
                sockets.append(item)
            elif isinstance(item, dict) and item.get("node_type") == "scene_attachment":
                attachments.append(item)
            elif isinstance(item, dict) and item.get("node_type") == "scene_relationship":
                relationships.append(item)
            elif isinstance(item, dict) and item.get("node_type") == "scene_camera":
                cameras.append(item)
            elif isinstance(item, dict) and item.get("node_type") == "scene_light":
                lights.append(item)
            elif isinstance(item, dict) and item.get("node_type") == "scene_curiosity_anchor":
                curiosity_anchors.append(item)
            elif isinstance(item, dict) and item.get("node_type") == "scene_hidden_state":
                hidden_state.append(item)
            elif isinstance(item, dict) and item.get("node_type") == "scene_export":
                exports.append(item)
            else:
                raise LatheParseError(f"Unexpected scene item: {item!r}")
        return {
            "node_type": node_type,
            "name": name,
            "values": self._assignments(values, "scene"),
            "styles": styles,
            "style_packs": style_packs,
            "regions": regions,
            "groups": groups,
            "placement_zones": placement_zones,
            "modules": modules,
            "kits": kits,
            "variant_families": variant_families,
            "generators": generators,
            "biomes": biomes,
            "scatters": scatters,
            "environments": environments,
            "objects": objects,
            "arrays": arrays,
            "sockets": sockets,
            "attachments": attachments,
            "relationships": relationships,
            "cameras": cameras,
            "lights": lights,
            "curiosity_anchors": curiosity_anchors,
            "hidden_state": hidden_state,
            "exports": exports,
        }

    def style_scene_block(self, name: str, *assignments: Any) -> dict[str, Any]:
        return {
            "node_type": "scene_style",
            "name": name,
            "values": self._assignments(assignments, "style"),
        }

    def style_pack_scene_block(self, name: str, *assignments: Any) -> dict[str, Any]:
        return {
            "node_type": "scene_style_pack",
            "name": name,
            "values": self._assignments(assignments, "style_pack"),
        }

    def faction_pack_scene_block(self, name: str, *assignments: Any) -> dict[str, Any]:
        return self._scene_style_system_block("faction_pack", name, *assignments)

    def biome_kit_scene_block(self, name: str, *assignments: Any) -> dict[str, Any]:
        return self._scene_style_system_block("biome_kit", name, *assignments)

    def architecture_grammar_scene_block(self, name: str, *assignments: Any) -> dict[str, Any]:
        return self._scene_style_system_block("architecture_grammar", name, *assignments)

    def object_grammar_scene_block(self, name: str, *assignments: Any) -> dict[str, Any]:
        return self._scene_style_system_block("object_grammar", name, *assignments)

    def _scene_style_system_block(self, system: str, name: str, *assignments: Any) -> dict[str, Any]:
        values = self._assignments(assignments, system)
        values["_style_system"] = system
        return {"node_type": "scene_style_pack", "name": name, "values": values}

    def scene_type_clause(self, value: str) -> dict[str, Any]:
        return {"node_type": "scene_type_clause", "value": value}

    def scene_role_clause(self, value: str) -> dict[str, Any]:
        return {"node_type": "scene_role_clause", "value": value}

    def scene_from_clause(self, value: str) -> dict[str, Any]:
        return {"node_type": "scene_from_clause", "value": value}

    def _scene_qualifier_value(self, items: tuple[Any, ...], qualifier: str) -> str:
        for item in items:
            if isinstance(item, dict) and item.get("node_type") == qualifier:
                return str(item.get("value", "") or "")
        return ""

    def _scene_assignments(self, items: tuple[Any, ...]) -> list[tuple[str, Any]]:
        assignments: list[tuple[str, Any]] = []
        for item in items:
            if isinstance(item, tuple) and len(item) == 2:
                assignments.append(item)
            elif isinstance(item, dict) and item.get("node_type") == "scene_gameplay_block":
                assignments.extend(item["assignments"])
        return assignments

    def _scene_partitioned_items(self, items: tuple[Any, ...]) -> tuple[list[tuple[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        assignments: list[tuple[str, Any]] = []
        parts: list[dict[str, Any]] = []
        options: list[dict[str, Any]] = []
        sockets: list[dict[str, Any]] = []
        attachments: list[dict[str, Any]] = []
        constraints: list[dict[str, Any]] = []
        for item in items:
            if isinstance(item, tuple) and len(item) == 2:
                assignments.append(item)
            elif isinstance(item, dict) and item.get("node_type") == "scene_gameplay_block":
                assignments.extend(item["assignments"])
            elif isinstance(item, dict) and item.get("node_type") == "scene_kit_part":
                parts.append(item)
            elif isinstance(item, dict) and item.get("node_type") == "scene_variant_option":
                options.append(item)
            elif isinstance(item, dict) and item.get("node_type") == "scene_socket":
                sockets.append(item)
            elif isinstance(item, dict) and item.get("node_type") == "scene_attachment":
                attachments.append(item)
            elif isinstance(item, dict) and item.get("node_type") == "scene_constraint":
                constraints.append(item)
        return assignments, parts, options, sockets, attachments, constraints

    def region_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return {
            "node_type": "scene_region",
            "name": name,
            "type": self._scene_qualifier_value(items, "scene_type_clause"),
            "values": self._assignments(self._scene_assignments(items), "region"),
        }

    def group_scene_block(self, name: str, *assignments: Any) -> dict[str, Any]:
        return {
            "node_type": "scene_group",
            "name": name,
            "values": self._assignments(assignments, "group"),
        }

    def collection_scene_block(self, name: str, *assignments: Any) -> dict[str, Any]:
        return {
            "node_type": "scene_group",
            "name": name,
            "values": self._assignments(assignments, "collection"),
        }

    def placement_zone_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return {
            "node_type": "scene_placement_zone",
            "name": name,
            "type": self._scene_qualifier_value(items, "scene_type_clause"),
            "values": self._assignments(self._scene_assignments(items), "placement_zone"),
        }

    def module_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        values = self._assignments(self._scene_assignments(items), "module")
        values.setdefault("_construct", "module")
        return {
            "node_type": "scene_module",
            "name": name,
            "role": self._scene_qualifier_value(items, "scene_role_clause"),
            "from": self._scene_qualifier_value(items, "scene_from_clause"),
            "values": values,
        }

    def kit_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        assignments, parts, _options, sockets, attachments, _constraints = self._scene_partitioned_items(items)
        values = self._assignments(assignments, "kit")
        values["_parts"] = parts
        values["_sockets"] = sockets
        values["_attachments"] = attachments
        return {
            "node_type": "scene_kit",
            "name": name,
            "role": self._scene_qualifier_value(items, "scene_role_clause"),
            "from": self._scene_qualifier_value(items, "scene_from_clause"),
            "values": values,
        }

    def variant_family_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        assignments, _parts, options, sockets, attachments, constraints = self._scene_partitioned_items(items)
        values = self._assignments(assignments, "variant_family")
        values["_options"] = options
        values["_sockets"] = sockets
        values["_attachments"] = attachments
        values["_constraints"] = constraints
        return {"node_type": "scene_variant_family", "name": name, "values": values}

    def option_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        values = self._assignments(self._scene_assignments(items), "option")
        values.setdefault("_construct", "option")
        return {
            "node_type": "scene_variant_option",
            "name": name,
            "role": self._scene_qualifier_value(items, "scene_role_clause"),
            "from": self._scene_qualifier_value(items, "scene_from_clause"),
            "values": values,
        }

    def generator_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        assignments, _parts, _options, sockets, attachments, constraints = self._scene_partitioned_items(items)
        values = self._assignments(assignments, "generator")
        values["_sockets"] = sockets
        values["_attachments"] = attachments
        values["_constraints"] = constraints
        return {
            "node_type": "scene_generator",
            "name": name,
            "role": self._scene_qualifier_value(items, "scene_role_clause"),
            "from": self._scene_qualifier_value(items, "scene_from_clause"),
            "values": values,
        }

    def biome_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        assignments, _parts, options, sockets, attachments, constraints = self._scene_partitioned_items(items)
        values = self._assignments(assignments, "biome")
        values["_options"] = options
        values["_sockets"] = sockets
        values["_attachments"] = attachments
        values["_constraints"] = constraints
        return {"node_type": "scene_biome", "name": name, "values": values}

    def scatter_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        assignments, _parts, _options, sockets, attachments, constraints = self._scene_partitioned_items(items)
        values = self._assignments(assignments, "scatter")
        values["_sockets"] = sockets
        values["_attachments"] = attachments
        values["_constraints"] = constraints
        return {
            "node_type": "scene_scatter",
            "name": name,
            "role": self._scene_qualifier_value(items, "scene_role_clause"),
            "from": self._scene_qualifier_value(items, "scene_from_clause"),
            "values": values,
        }

    def environment_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        assignments, _parts, _options, sockets, attachments, constraints = self._scene_partitioned_items(items)
        values = self._assignments(assignments, "environment")
        values["_sockets"] = sockets
        values["_attachments"] = attachments
        values["_constraints"] = constraints
        return {
            "node_type": "scene_environment",
            "name": name,
            "role": self._scene_qualifier_value(items, "scene_role_clause"),
            "from": self._scene_qualifier_value(items, "scene_from_clause"),
            "values": values,
        }

    def constraint_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return {
            "node_type": "scene_constraint",
            "name": name,
            "type": self._scene_qualifier_value(items, "scene_type_clause"),
            "values": self._assignments(self._scene_assignments(items), "constraint"),
        }

    def part_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        values = self._assignments(self._scene_assignments(items), "part")
        values.setdefault("_construct", "part")
        return {
            "node_type": "scene_kit_part",
            "name": name,
            "role": self._scene_qualifier_value(items, "scene_role_clause"),
            "from": self._scene_qualifier_value(items, "scene_from_clause"),
            "values": values,
        }

    def object_scene_block(
        self,
        name: str,
        *items: Any,
    ) -> dict[str, Any]:
        return {
            "node_type": "scene_object",
            "name": name,
            "role": self._scene_qualifier_value(items, "scene_role_clause"),
            "from": self._scene_qualifier_value(items, "scene_from_clause"),
            "values": self._assignments(self._scene_assignments(items), "object"),
        }

    def instance_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        values = self._assignments(self._scene_assignments(items), "instance")
        values.setdefault("_construct", "instance")
        return {
            "node_type": "scene_object",
            "name": name,
            "role": self._scene_qualifier_value(items, "scene_role_clause"),
            "from": self._scene_qualifier_value(items, "scene_from_clause"),
            "values": values,
        }

    def terrain_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        values = self._assignments(self._scene_assignments(items), "terrain")
        values.setdefault("_construct", "terrain")
        return {
            "node_type": "scene_object",
            "name": name,
            "role": "environment_structure",
            "from": self._scene_qualifier_value(items, "scene_from_clause"),
            "values": values,
        }

    def _scene_construct_block(self, name: str, construct: str, *items: Any) -> dict[str, Any]:
        values = self._assignments(self._scene_assignments(items), construct)
        values.setdefault("_construct", construct)
        return {
            "node_type": "scene_object",
            "name": name,
            "role": self._scene_qualifier_value(items, "scene_role_clause"),
            "from": self._scene_qualifier_value(items, "scene_from_clause"),
            "values": values,
        }

    def road_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "road", *items)

    def bridge_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "bridge", *items)

    def building_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "building", *items)

    def building_envelope_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "building_envelope", *items)

    def floor_stack_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "floor_stack", *items)

    def facade_grid_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "facade_grid", *items)

    def facade_bay_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "facade_bay", *items)

    def roof_profile_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "roof_profile", *items)

    def vertical_core_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "vertical_core", *items)

    def entrance_plan_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "entrance_plan", *items)

    def site_compound_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "site_compound", *items)

    def building_lot_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "building_lot", *items)

    def courtyard_plan_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "courtyard_plan", *items)

    def pedestrian_path_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "pedestrian_path", *items)

    def service_alley_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "service_alley", *items)

    def parking_zone_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "parking_zone", *items)

    def loading_zone_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "loading_zone", *items)

    def exterior_utility_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "exterior_utility", *items)

    def building_complex_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "building_complex", *items)

    def harbor_complex_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "harbor_complex", *items)

    def dockyard_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "dockyard", *items)

    def vehicle_yard_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "vehicle_yard", *items)

    def hangar_complex_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "hangar_complex", *items)

    def factory_complex_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "factory_complex", *items)

    def production_line_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "production_line", *items)

    def industrial_district_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "industrial_district", *items)

    def transport_corridor_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "transport_corridor", *items)

    def supply_network_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "supply_network", *items)

    def resource_region_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "resource_region", *items)

    def settlement_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "settlement", *items)

    def civilization_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "civilization", *items)

    def culture_system_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "culture_system", *items)

    def law_code_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "law_code", *items)

    def policy_rule_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "policy_rule", *items)

    def economy_model_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "economy_model", *items)

    def trade_policy_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "trade_policy", *items)

    def diplomacy_state_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "diplomacy_state", *items)

    def social_graph_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "social_graph", *items)

    def social_relation_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "social_relation", *items)

    def population_group_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "population_group", *items)

    def labor_system_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "labor_system", *items)

    def ritual_calendar_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "ritual_calendar", *items)

    def festival_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "festival", *items)

    def belief_system_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "belief_system", *items)

    def cultural_marker_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "cultural_marker", *items)

    def civic_institution_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "civic_institution", *items)

    def quest_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "quest", *items)

    def objective_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "objective", *items)

    def mission_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "mission", *items)

    def objective_chain_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "objective_chain", *items)

    def success_condition_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "success_condition", *items)

    def failure_condition_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "failure_condition", *items)

    def reward_table_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "reward_table", *items)

    def loot_table_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "loot_table", *items)

    def inventory_slot_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "inventory_slot", *items)

    def crafting_station_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "crafting_station", *items)

    def recipe_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "recipe", *items)

    def shop_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "shop", *items)

    def vendor_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "vendor", *items)

    def currency_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "currency", *items)

    def reputation_rule_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "reputation_rule", *items)

    def unlock_rule_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "unlock_rule", *items)

    def progression_track_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "progression_track", *items)

    def gameplay_rule_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "gameplay_rule", *items)

    def interactable_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "interactable", *items)

    def encounter_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "encounter", *items)

    def director_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "director", *items)

    def encounter_director_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "encounter_director", *items)

    def director_intent_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "director_intent", *items)

    def pacing_curve_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "pacing_curve", *items)

    def threat_budget_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "threat_budget", *items)

    def spawn_wave_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "spawn_wave", *items)

    def spawn_budget_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "spawn_budget", *items)

    def combat_phase_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "combat_phase", *items)

    def stealth_phase_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "stealth_phase", *items)

    def escalation_rule_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "escalation_rule", *items)

    def adaptive_difficulty_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "adaptive_difficulty", *items)

    def encounter_beat_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "encounter_beat", *items)

    def director_signal_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "director_signal", *items)

    def threat_zone_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "threat_zone", *items)

    def reinforcement_route_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "reinforcement_route", *items)

    def simulation_layer_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "simulation_layer", *items)

    def heat_field_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "heat_field", *items)

    def noise_field_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "noise_field", *items)

    def visibility_field_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "visibility_field", *items)

    def resource_flow_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "resource_flow", *items)

    def faction_pressure_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "faction_pressure", *items)

    def territory_influence_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "territory_influence", *items)

    def alarm_grid_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "alarm_grid", *items)

    def patrol_density_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "patrol_density", *items)

    def hazard_field_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "hazard_field", *items)

    def sensor_grid_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "sensor_grid", *items)

    def cover_map_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "cover_map", *items)

    def flow_gate_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "flow_gate", *items)

    def world_metric_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "world_metric", *items)

    def simulation_probe_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "simulation_probe", *items)

    def traversal_gate_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "traversal_gate", *items)

    def resource_economy_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "resource_economy", *items)

    def control_zone_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "control_zone", *items)

    def npc_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "npc", *items)

    def agent_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "agent", *items)

    def crowd_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "crowd", *items)

    def schedule_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "schedule", *items)

    def patrol_route_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "patrol_route", *items)

    def dialogue_tree_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "dialogue_tree", *items)

    def inventory_loadout_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "inventory_loadout", *items)

    def spawn_ecology_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "spawn_ecology", *items)

    def biome_system_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "biome_system", *items)

    def habitat_zone_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "habitat_zone", *items)

    def species_population_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "species_population", *items)

    def food_web_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "food_web", *items)

    def predator_prey_link_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "predator_prey_link", *items)

    def migration_route_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "migration_route", *items)

    def nesting_site_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "nesting_site", *items)

    def resource_patch_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "resource_patch", *items)

    def resource_regeneration_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "resource_regeneration", *items)

    def growth_cycle_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "growth_cycle", *items)

    def weather_ecology_link_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "weather_ecology_link", *items)

    def ecological_pressure_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "ecological_pressure", *items)

    def land_use_plan_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "land_use_plan", *items)

    def farm_plot_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "farm_plot", *items)

    def hunting_ground_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "hunting_ground", *items)

    def fishing_ground_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "fishing_ground", *items)

    def grazing_range_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "grazing_range", *items)

    def extraction_site_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "extraction_site", *items)

    def pollution_source_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "pollution_source", *items)

    def conservation_zone_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "conservation_zone", *items)

    def restoration_project_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "restoration_project", *items)

    def scarcity_loop_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "scarcity_loop", *items)

    def settlement_pressure_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "settlement_pressure", *items)

    def resource_claim_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "resource_claim", *items)

    def harvest_cycle_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "harvest_cycle", *items)

    def carrying_capacity_rule_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "carrying_capacity_rule", *items)

    def biome_impact_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "biome_impact", *items)

    def supply_chain_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "supply_chain", *items)

    def logistics_hub_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "logistics_hub", *items)

    def storage_depot_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "storage_depot", *items)

    def stockpile_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "stockpile", *items)

    def input_buffer_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "input_buffer", *items)

    def output_buffer_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "output_buffer", *items)

    def processing_stage_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "processing_stage", *items)

    def refinery_stage_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "refinery_stage", *items)

    def workshop_stage_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "workshop_stage", *items)

    def assembly_stage_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "assembly_stage", *items)

    def market_node_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "market_node", *items)

    def demand_sink_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "demand_sink", *items)

    def supply_route_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "supply_route", *items)

    def transport_leg_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "transport_leg", *items)

    def bottleneck_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "bottleneck", *items)

    def throughput_rule_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "throughput_rule", *items)

    def failure_mode_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "failure_mode", *items)

    def production_strategy_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "production_strategy", *items)

    def production_priority_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "production_priority", *items)

    def quota_rule_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "quota_rule", *items)

    def allocation_rule_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "allocation_rule", *items)

    def rationing_policy_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "rationing_policy", *items)

    def strategic_reserve_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "strategic_reserve", *items)

    def trade_embargo_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "trade_embargo", *items)

    def sabotage_target_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "sabotage_target", *items)

    def maintenance_plan_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "maintenance_plan", *items)

    def repair_schedule_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "repair_schedule", *items)

    def mobilization_order_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "mobilization_order", *items)

    def production_mode_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "production_mode", *items)

    def wartime_production_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "wartime_production", *items)

    def peacetime_production_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "peacetime_production", *items)

    def procurement_contract_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "procurement_contract", *items)

    def readiness_level_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "readiness_level", *items)

    def conflict_system_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "conflict_system", *items)

    def strategic_objective_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "strategic_objective", *items)

    def war_plan_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "war_plan", *items)

    def battlefront_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "battlefront", *items)

    def escalation_ladder_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "escalation_ladder", *items)

    def treaty_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "treaty", *items)

    def ceasefire_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "ceasefire", *items)

    def alliance_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "alliance", *items)

    def rival_claim_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "rival_claim", *items)

    def diplomatic_demand_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "diplomatic_demand", *items)

    def negotiation_channel_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "negotiation_channel", *items)

    def sanction_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "sanction", *items)

    def espionage_cell_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "espionage_cell", *items)

    def covert_operation_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "covert_operation", *items)

    def disaster_response_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "disaster_response", *items)

    def emergency_order_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "emergency_order", *items)

    def faction_ai_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "faction_ai", *items)

    def doctrine_model_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "doctrine_model", *items)

    def goal_stack_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "goal_stack", *items)

    def threat_model_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "threat_model", *items)

    def perception_feed_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "perception_feed", *items)

    def decision_rule_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "decision_rule", *items)

    def policy_selector_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "policy_selector", *items)

    def action_option_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "action_option", *items)

    def response_plan_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "response_plan", *items)

    def escalation_choice_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "escalation_choice", *items)

    def deescalation_choice_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "deescalation_choice", *items)

    def resource_strategy_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "resource_strategy", *items)

    def logistics_priority_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "logistics_priority", *items)

    def diplomatic_posture_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "diplomatic_posture", *items)

    def contingency_plan_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "contingency_plan", *items)

    def adaptive_order_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "adaptive_order", *items)

    def operational_plan_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "operational_plan", *items)

    def order_queue_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "order_queue", *items)

    def world_order_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "world_order", *items)

    def patrol_order_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "patrol_order", *items)

    def convoy_order_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "convoy_order", *items)

    def construction_order_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "construction_order", *items)

    def repair_order_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "repair_order", *items)

    def relief_order_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "relief_order", *items)

    def mission_order_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "mission_order", *items)

    def scheduled_action_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "scheduled_action", *items)

    def task_assignment_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "task_assignment", *items)

    def crew_roster_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "crew_roster", *items)

    def convoy_route_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "convoy_route", *items)

    def construction_queue_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "construction_queue", *items)

    def repair_crew_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "repair_crew", *items)

    def relief_team_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "relief_team", *items)

    def settlement_evolution_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "settlement_evolution", *items)

    def growth_phase_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "growth_phase", *items)

    def expansion_zone_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "expansion_zone", *items)

    def construction_stage_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "construction_stage", *items)

    def upgrade_plan_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "upgrade_plan", *items)

    def district_upgrade_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "district_upgrade", *items)

    def building_upgrade_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "building_upgrade", *items)

    def infrastructure_upgrade_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "infrastructure_upgrade", *items)

    def material_delivery_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "material_delivery", *items)

    def staffing_plan_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "staffing_plan", *items)

    def occupancy_plan_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "occupancy_plan", *items)

    def worksite_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "worksite", *items)

    def build_permit_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "build_permit", *items)

    def damage_repair_plan_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "damage_repair_plan", *items)

    def demolition_plan_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "demolition_plan", *items)

    def renovation_project_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "renovation_project", *items)

    def city_plan_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "city_plan", *items)

    def zoning_rule_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "zoning_rule", *items)

    def zoning_district_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "zoning_district", *items)

    def parcel_grid_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "parcel_grid", *items)

    def land_parcel_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "land_parcel", *items)

    def parcel_subdivision_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "parcel_subdivision", *items)

    def block_plan_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "block_plan", *items)

    def street_hierarchy_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "street_hierarchy", *items)

    def transit_node_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "transit_node", *items)

    def civic_service_plan_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "civic_service_plan", *items)

    def service_coverage_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "service_coverage", *items)

    def utility_corridor_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "utility_corridor", *items)

    def district_site_plan_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "district_site_plan", *items)

    def street_crossing_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "street_crossing", *items)

    def perimeter_plan_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "perimeter_plan", *items)

    def security_gate_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "security_gate", *items)

    def landscape_zone_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "landscape_zone", *items)

    def traffic_flow_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "traffic_flow", *items)

    def service_flow_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "service_flow", *items)

    def access_sequence_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "access_sequence", *items)

    def public_entry_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "public_entry", *items)

    def service_entry_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "service_entry", *items)

    def threshold_transition_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "threshold_transition", *items)

    def entry_lobby_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "entry_lobby", *items)

    def access_checkpoint_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "access_checkpoint", *items)

    def loading_path_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "loading_path", *items)

    def wayfinding_node_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "wayfinding_node", *items)

    def circulation_core_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "circulation_core", *items)

    def stair_run_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "stair_run", *items)

    def elevator_bank_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "elevator_bank", *items)

    def egress_route_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "egress_route", *items)

    def emergency_exit_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "emergency_exit", *items)

    def corridor_spine_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "corridor_spine", *items)

    def floor_transition_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "floor_transition", *items)

    def public_circulation_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "public_circulation", *items)

    def service_circulation_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "service_circulation", *items)

    def stair_detail_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "stair_detail", *items)

    def tread_pattern_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "tread_pattern", *items)

    def landing_platform_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "landing_platform", *items)

    def handrail_run_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "handrail_run", *items)

    def corridor_shell_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "corridor_shell", *items)

    def door_rhythm_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "door_rhythm", *items)

    def ceiling_service_grid_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "ceiling_service_grid", *items)

    def egress_surface_plan_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "egress_surface_plan", *items)

    def room_route_binding_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "room_route_binding", *items)

    def power_grid_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "power_grid", *items)

    def substation_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "substation", *items)

    def transformer_bank_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "transformer_bank", *items)

    def power_line_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "power_line", *items)

    def water_network_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "water_network", *items)

    def pump_station_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "pump_station", *items)

    def water_tower_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "water_tower", *items)

    def sewer_network_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "sewer_network", *items)

    def treatment_plant_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "treatment_plant", *items)

    def data_network_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "data_network", *items)

    def data_hub_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "data_hub", *items)

    def fiber_line_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "fiber_line", *items)

    def transit_line_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "transit_line", *items)

    def transit_station_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "transit_station", *items)

    def service_connection_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "service_connection", *items)

    def maintenance_access_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "maintenance_access", *items)

    def building_service_plan_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "building_service_plan", *items)

    def service_core_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "service_core", *items)

    def utility_room_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "utility_room", *items)

    def mechanical_room_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "mechanical_room", *items)

    def electrical_panel_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "electrical_panel", *items)

    def meter_bank_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "meter_bank", *items)

    def plumbing_stack_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "plumbing_stack", *items)

    def hvac_system_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "hvac_system", *items)

    def ventilation_duct_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "ventilation_duct", *items)

    def elevator_core_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "elevator_core", *items)

    def service_elevator_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "service_elevator", *items)

    def service_shaft_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "service_shaft", *items)

    def fire_suppression_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "fire_suppression", *items)

    def sprinkler_zone_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "sprinkler_zone", *items)

    def waste_chute_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "waste_chute", *items)

    def loading_dock_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "loading_dock", *items)

    def room_program_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "room_program", *items)

    def bathroom_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "bathroom", *items)

    def kitchen_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "kitchen", *items)

    def lab_room_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "lab_room", *items)

    def med_bay_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "med_bay", *items)

    def workshop_room_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "workshop_room", *items)

    def control_room_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "control_room", *items)

    def storage_room_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "storage_room", *items)

    def office_room_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "office_room", *items)

    def bedroom_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "bedroom", *items)

    def fixture_cluster_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "fixture_cluster", *items)

    def appliance_bank_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "appliance_bank", *items)

    def workstation_cluster_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "workstation_cluster", *items)

    def cabinet_wall_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "cabinet_wall", *items)

    def counter_run_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "counter_run", *items)

    def sanitary_fixture_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "sanitary_fixture", *items)

    def lab_bench_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "lab_bench", *items)

    def medical_bed_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "medical_bed", *items)

    def tool_rack_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "tool_rack", *items)

    def room_adjacency_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "room_adjacency", *items)

    def room_connection_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "room_connection", *items)

    def door_opening_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "door_opening", *items)

    def corridor_link_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "corridor_link", *items)

    def wall_run_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "wall_run", *items)

    def room_socket_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "room_socket", *items)

    def fixture_socket_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "fixture_socket", *items)

    def socket_binding_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "socket_binding", *items)

    def fixture_placement_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "fixture_placement", *items)

    def furniture_placement_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "furniture_placement", *items)

    def service_placement_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "service_placement", *items)

    def wall_attachment_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "wall_attachment", *items)

    def anchor_rule_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "anchor_rule", *items)

    def placement_constraint_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "placement_constraint", *items)

    def auto_layout_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "auto_layout", *items)

    def room_layout_plan_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "room_layout_plan", *items)

    def fixture_layout_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "fixture_layout", *items)

    def furniture_layout_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "furniture_layout", *items)

    def service_layout_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "service_layout", *items)

    def wall_fixture_layout_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "wall_fixture_layout", *items)

    def layout_solver_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "layout_solver", *items)

    def room_bounds_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "room_bounds", *items)

    def wall_side_rule_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "wall_side_rule", *items)

    def socket_priority_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "socket_priority", *items)

    def clearance_zone_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "clearance_zone", *items)

    def layout_slot_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "layout_slot", *items)

    def footprint_packer_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "footprint_packer", *items)

    def placement_footprint_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "placement_footprint", *items)

    def occupancy_grid_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "occupancy_grid", *items)

    def fit_profile_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "fit_profile", *items)

    def collision_rule_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "collision_rule", *items)

    def service_reach_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "service_reach", *items)

    def room_packing_solver_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "room_packing_solver", *items)

    def packing_slot_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "packing_slot", *items)

    def packed_transform_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "packed_transform", *items)

    def clearance_reservation_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "clearance_reservation", *items)

    def service_anchor_map_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "service_anchor_map", *items)

    def room_content_plan_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "room_content_plan", *items)

    def content_family_binding_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "content_family_binding", *items)

    def furniture_asset_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "furniture_asset", *items)

    def fixture_asset_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "fixture_asset", *items)

    def packed_child_asset_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "packed_child_asset", *items)

    def content_surface_plan_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "content_surface_plan", *items)

    def content_material_zone_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "content_material_zone", *items)

    def content_finish_preset_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "content_finish_preset", *items)

    def content_wear_profile_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "content_wear_profile", *items)

    def content_marking_set_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "content_marking_set", *items)

    def room_pack_preset_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "room_pack_preset", *items)

    def footprint_size_preset_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "footprint_size_preset", *items)

    def packing_policy_preset_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "packing_policy_preset", *items)

    def clearance_preset_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "clearance_preset", *items)

    def service_reach_preset_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "service_reach_preset", *items)

    def role_item_set_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "role_item_set", *items)

    def public_space_plan_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "public_space_plan", *items)

    def growth_boundary_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "growth_boundary", *items)

    def district_dependency_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "district_dependency", *items)

    def development_pressure_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "development_pressure", *items)

    def climate_zone_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "climate_zone", *items)

    def climate_risk_map_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "climate_risk_map", *items)

    def flood_risk_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "flood_risk", *items)

    def fire_risk_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "fire_risk", *items)

    def heat_risk_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "heat_risk", *items)

    def resource_constraint_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "resource_constraint", *items)

    def protected_land_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "protected_land", *items)

    def green_infrastructure_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "green_infrastructure", *items)

    def stormwater_system_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "stormwater_system", *items)

    def cooling_corridor_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "cooling_corridor", *items)

    def evacuation_route_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "evacuation_route", *items)

    def emergency_shelter_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "emergency_shelter", *items)

    def resilience_plan_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "resilience_plan", *items)

    def climate_adaptation_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "climate_adaptation", *items)

    def transit_oriented_growth_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "transit_oriented_growth", *items)

    def risk_mitigation_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "risk_mitigation", *items)

    def faction_behavior_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "faction_behavior", *items)

    def behavior_graph_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "behavior_graph", *items)

    def event_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "event", *items)

    def event_emitter_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "event_emitter", *items)

    def trigger_volume_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "trigger_volume", *items)

    def timer_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "timer", *items)

    def state_machine_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "state_machine", *items)

    def state_transition_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "state_transition", *items)

    def conditional_spawn_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "conditional_spawn", *items)

    def alert_network_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "alert_network", *items)

    def scene_state_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "scene_state", *items)

    def scene_mutation_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "scene_mutation", *items)

    def timeline_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "timeline", *items)

    def sequencer_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "sequencer", *items)

    def animation_clip_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "animation_clip", *items)

    def action_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "action", *items)

    def action_pose_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "action_pose", *items)

    def motion_path_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "motion_path", *items)

    def moving_part_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "moving_part", *items)

    def door_action_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "door_action", *items)

    def gate_action_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "gate_action", *items)

    def machine_cycle_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "machine_cycle", *items)

    def vfx_emitter_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "vfx_emitter", *items)

    def sound_cue_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "sound_cue", *items)

    def physics_body_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "physics_body", *items)

    def physics_joint_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "physics_joint", *items)

    def hinge_joint_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "hinge_joint", *items)

    def physics_constraint_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "physics_constraint", *items)

    def breakable_part_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "breakable_part", *items)

    def damage_state_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "damage_state", *items)

    def debris_field_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "debris_field", *items)

    def rope_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "rope", *items)

    def cable_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "cable", *items)

    def cloth_flag_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "cloth_flag", *items)

    def force_field_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "force_field", *items)

    def destruction_event_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "destruction_event", *items)

    def surface_layer_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "surface_layer", *items)

    def material_zone_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "material_zone", *items)

    def decal_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "decal", *items)

    def wear_pattern_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "wear_pattern", *items)

    def damage_surface_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "damage_surface", *items)

    def surface_transition_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "surface_transition", *items)

    def weather_system_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "weather_system", *items)

    def atmosphere_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "atmosphere", *items)

    def wind_zone_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "wind_zone", *items)

    def liquid_body_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "liquid_body", *items)

    def puddle_field_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "puddle_field", *items)

    def fire_source_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "fire_source", *items)

    def smoke_emitter_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "smoke_emitter", *items)

    def mist_volume_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "mist_volume", *items)

    def wetness_zone_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "wetness_zone", *items)

    def heat_haze_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "heat_haze", *items)

    def time_of_day_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "time_of_day", *items)

    def environment_effect_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "environment_effect", *items)

    def shot_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "shot", *items)

    def shot_sequence_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "shot_sequence", *items)

    def camera_rail_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "camera_rail", *items)

    def look_at_target_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "look_at_target", *items)

    def focal_zone_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "focal_zone", *items)

    def cutscene_beat_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "cutscene_beat", *items)

    def orbit_camera_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "orbit_camera", *items)

    def inspection_camera_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "inspection_camera", *items)

    def focus_pull_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "focus_pull", *items)

    def camera_volume_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "camera_volume", *items)

    def presentation_rig_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "presentation_rig", *items)

    def composition_guide_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "composition_guide", *items)

    def ambient_bed_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "ambient_bed", *items)

    def sound_zone_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "sound_zone", *items)

    def reverb_space_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "reverb_space", *items)

    def acoustic_occluder_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "acoustic_occluder", *items)

    def sound_propagation_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "sound_propagation", *items)

    def music_state_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "music_state", *items)

    def music_transition_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "music_transition", *items)

    def stinger_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "stinger", *items)

    def foley_emitter_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "foley_emitter", *items)

    def audio_bus_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "audio_bus", *items)

    def listener_zone_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "listener_zone", *items)

    def acoustic_material_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "acoustic_material", *items)

    def interaction_prompt_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "interaction_prompt", *items)

    def interaction_zone_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "interaction_zone", *items)

    def affordance_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "affordance", *items)

    def usable_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "usable", *items)

    def pickup_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "pickup", *items)

    def inspect_point_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "inspect_point", *items)

    def terminal_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "terminal", *items)

    def control_panel_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "control_panel", *items)

    def switch_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "switch", *items)

    def lever_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "lever", *items)

    def button_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "button", *items)

    def door_lock_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "door_lock", *items)

    def quest_marker_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "quest_marker", *items)

    def signage_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "signage", *items)

    def map_marker_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "map_marker", *items)

    def diegetic_hud_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "diegetic_hud", *items)

    def ui_anchor_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "ui_anchor", *items)

    def interior_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "interior", *items)

    def city_block_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "city_block", *items)

    def district_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "district", *items)

    def room_cluster_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "room_cluster", *items)

    def street_grid_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "street_grid", *items)

    def floorplan_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "floorplan", *items)

    def road_intersection_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "road_intersection", *items)

    def infrastructure_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "infrastructure", *items)

    def service_network_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "service_network", *items)

    def access_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "access", *items)

    def route_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return self._scene_construct_block(name, "route", *items)

    def array_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        values = self._assignments(self._scene_assignments(items), "array")
        values.setdefault("_construct", "array")
        return {
            "node_type": "scene_array",
            "name": name,
            "role": self._scene_qualifier_value(items, "scene_role_clause"),
            "from": self._scene_qualifier_value(items, "scene_from_clause"),
            "values": values,
        }

    def socket_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return {
            "node_type": "scene_socket",
            "name": name,
            "type": self._scene_qualifier_value(items, "scene_type_clause"),
            "values": self._assignments(self._scene_assignments(items), "socket"),
        }

    def attach_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return {
            "node_type": "scene_attachment",
            "name": name,
            "type": self._scene_qualifier_value(items, "scene_type_clause"),
            "values": self._assignments(self._scene_assignments(items), "attach"),
        }

    def gameplay_scene_block(self, *assignments: Any) -> dict[str, Any]:
        return {
            "node_type": "scene_gameplay_block",
            "assignments": [(f"gameplay.{path}", value) for path, value in self._scene_assignments(assignments)],
        }

    def relationship_scene_block(
        self,
        name: str,
        *items: Any,
    ) -> dict[str, Any]:
        return {
            "node_type": "scene_relationship",
            "name": name,
            "type": self._scene_qualifier_value(items, "scene_type_clause"),
            "values": self._assignments(self._scene_assignments(items), "relationship"),
        }

    def camera_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return {
            "node_type": "scene_camera",
            "name": name,
            "framing": self._scene_qualifier_value(items, "scene_type_clause"),
            "values": self._assignments(self._scene_assignments(items), "camera"),
        }

    def camera_intent_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return {
            "node_type": "scene_camera",
            "name": name,
            "framing": self._scene_qualifier_value(items, "scene_type_clause"),
            "values": self._assignments(self._scene_assignments(items), "camera_intent"),
        }

    def light_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return {
            "node_type": "scene_light",
            "name": name,
            "type": self._scene_qualifier_value(items, "scene_type_clause"),
            "values": self._assignments(self._scene_assignments(items), "light"),
        }

    def lighting_plan_scene_block(self, name: str, *items: Any) -> dict[str, Any]:
        return {
            "node_type": "scene_light",
            "name": name,
            "type": self._scene_qualifier_value(items, "scene_type_clause"),
            "values": self._assignments(self._scene_assignments(items), "lighting_plan"),
        }

    def curiosity_anchor_scene_block(self, name: str, *assignments: Any) -> dict[str, Any]:
        return {
            "node_type": "scene_curiosity_anchor",
            "name": name,
            "values": self._assignments(assignments, "curiosity_anchor"),
        }

    def hidden_state_scene_block(self, name: str, *assignments: Any) -> dict[str, Any]:
        return {
            "node_type": "scene_hidden_state",
            "name": name,
            "values": self._assignments(assignments, "hidden_state"),
        }

    def export_scene_block(self, name: str, *assignments: Any) -> dict[str, Any]:
        return {
            "node_type": "scene_export",
            "name": name,
            "values": self._assignments(assignments, "export"),
        }

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
        experimental: dict[str, Any] = {}
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
            elif isinstance(item, dict) and item.get("node_type") == "experimental":
                experimental = item["values"]
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
            "experimental": experimental,
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
