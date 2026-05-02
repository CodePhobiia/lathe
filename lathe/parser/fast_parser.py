"""Fast hand-rolled parser for Lathe source files.

Bypasses the Lark grammar for the common happy path while falling back
to the formal grammar on ambiguous constructs. Produces the same raw
AST JSON shape as the Lark path.
"""

from __future__ import annotations

from typing import Any

from .fast_parser_expr import _FastParserExprMixin
from .grammar import LatheParseError, _dedupe_keep_first, _empty_program
from .tokens import _TokenStream


class _FastParser(_FastParserExprMixin):
    MAPPING_DECLS = {
        "library",
        "kit",
        "pattern",
        "material",
        "surface_program",
        "surface_backend",
        "surface_policy",
        "decal_library",
        "mask_program",
        "trim_sheet",
        "palette",
        "reference_set",
        "reconstruct_policy",
        "adapt_policy",
        "assembly_policy",
        "fit_profile",
        "transfer_rule",
        "execution_profile",
        "render_fixture",
        "bake_profile",
        "library_binding",
        "material_graph",
        "inspection_policy",
    }
    STRUCTURED_DECLS = {"family", "component", "assembly", "trait", "mechanism"}
    SIMPLE_MAPPING_DECLS = {"repair_policy", "fixture"}
    ASSET_BLOCKS = {
        "refs",
        "intent",
        "geometry",
        "features",
        "surface",
        "assembly",
        "fit",
        "transfer",
        "reuse",
        "constraints",
        "ingest",
        "assembly_rules",
        "execution",
        "package",
        "publish",
    }
    BUILD_BLOCKS = {"shape", "topology", "uv", "surface", "rig", "interfaces", "physics", "optimize"}
    EXPERIMENTAL_SUBBLOCKS = {"art_direction", "references", "kit"}
    EXPERIMENTAL_ART_DIRECTION_FIELDS = {"style_tags", "wear", "material_age", "detail_density"}
    DECL_KEYS = {
        "library": "libraries",
        "kit": "kits",
        "pattern": "patterns",
        "material": "materials",
        "surface_program": "surface_programs",
        "surface_backend": "surface_backends",
        "surface_policy": "surface_policies",
        "decal_library": "decal_libraries",
        "mask_program": "mask_programs",
        "trim_sheet": "trim_sheets",
        "palette": "palettes",
        "reference_set": "reference_sets",
        "reconstruct_policy": "reconstruct_policies",
        "adapt_policy": "adapt_policies",
        "assembly_policy": "assembly_policies",
        "fit_profile": "fit_profiles",
        "transfer_rule": "transfer_rules",
        "execution_profile": "execution_profiles",
        "render_fixture": "render_fixtures",
        "bake_profile": "bake_profiles",
        "library_binding": "library_bindings",
        "material_graph": "material_graphs",
        "inspection_policy": "inspection_policies",
    }
    STRUCTURED_KEYS = {
        "family": "families",
        "component": "components",
        "assembly": "assemblies",
        "trait": "traits",
        "mechanism": "mechanisms",
    }

    def __init__(self, source: str) -> None:
        self.ts = _TokenStream(source)

    def parse(self) -> dict[str, Any]:
        """Parse.

        Returns:
            The result.
        """
        program = _empty_program()
        while not self.ts.eof():
            keyword = self.ts.pop_ident()
            if keyword == "module":
                program["module"] = self._qident()
            elif keyword == "import":
                program["imports"].append(self._qident())
            elif keyword in {"profile", "contract"}:
                program[f"{keyword}s"].append(self._profile_or_contract(keyword))
            elif keyword == "critic":
                program["critics"].append(self._critic())
            elif keyword in self.MAPPING_DECLS:
                program[self.DECL_KEYS[keyword]].append(self._mapping_decl(keyword))
            elif keyword == "style_pack":
                program["style_packs"].append(self._style_pack_decl())
            elif keyword in {"faction_pack", "biome_kit", "architecture_grammar", "object_grammar"}:
                program["style_packs"].append(self._style_system_decl(keyword))
            elif keyword in self.STRUCTURED_DECLS:
                node_type = "assembly_decl" if keyword == "assembly" else keyword
                program[self.STRUCTURED_KEYS[keyword]].append(self._structured_decl(node_type, keyword))
            elif keyword in self.SIMPLE_MAPPING_DECLS:
                key = "repair_policies" if keyword == "repair_policy" else "fixtures"
                program[key].append(self._simple_mapping_decl(keyword))
            elif keyword == "test":
                program["tests"].append(self._test_like("test"))
            elif keyword == "benchmark":
                program["benchmarks"].append(self._test_like("benchmark"))
            elif keyword == "space":
                program["spaces"].append(self._space_decl())
            elif keyword == "world":
                program["worlds"].append(self._scene_decl(node_type="world"))
            elif keyword == "scene":
                program["scenes"].append(self._scene_decl())
            elif keyword == "asset":
                program["assets"].append(self._asset_decl())
            elif keyword == "variant":
                program["variants"].append(self._variant_decl())
            else:
                raise LatheParseError(f"Unknown declaration '{keyword}'")
        program["imports"] = _dedupe_keep_first(program["imports"])
        return program

    def _profile_or_contract(self, node_type: str) -> dict[str, Any]:
        name = self.ts.pop_ident()
        uses = self._optional_uses()
        defaults: dict[str, Any] = {}
        repair: dict[str, Any] = {}
        rules: list[dict[str, Any]] = []
        self.ts.pop("{")
        while not self.ts.peek("}"):
            keyword = self.ts.pop_ident()
            if keyword == "defaults":
                defaults = self._assign_block("defaults")
            elif keyword == "repair":
                repair = self._assign_block("repair")
            elif keyword in {"ensure", "prefer"}:
                rules.append(self._rule(keyword))
            else:
                raise LatheParseError(f"Unexpected {node_type} item '{keyword}'")
        self.ts.pop("}")
        return {
            "node_type": node_type,
            "name": name,
            "uses": _dedupe_keep_first(uses),
            "defaults": defaults,
            "rules": rules,
            "repair": repair,
        }

    def _critic(self) -> dict[str, Any]:
        name = self.ts.pop_ident()
        self.ts.pop("(")
        param = self.ts.pop_ident()
        self.ts.pop(":")
        asset_type = self.ts.pop_ident()
        if asset_type != "asset":
            raise LatheParseError("Critic parameter type must be asset")
        self.ts.pop(")")
        self.ts.pop("=")
        if self.ts.peek("weighted"):
            self.ts.pop("weighted")
            self.ts.pop("{")
            items = []
            while not self.ts.peek("}"):
                metric = self._metric_ref()
                weight = self._number_value()
                items.append({"metric": metric, "weight": float(weight)})
            self.ts.pop("}")
            body: Any = {"type": "weighted", "items": items}
        else:
            body = self._expr()
        return {"node_type": "critic", "name": name, "param": {"name": param, "type": "asset"}, "body": body}

    def _mapping_decl(self, node_type: str) -> dict[str, Any]:
        name = self.ts.pop_ident()
        uses = self._optional_uses()
        values = self._assign_block(node_type)
        return {"node_type": node_type, "name": name, "uses": _dedupe_keep_first(uses), "values": values}

    def _style_pack_decl(self) -> dict[str, Any]:
        name = self.ts.pop_ident()
        values = self._assign_block("style_pack")
        return {"node_type": "style_pack", "name": name, "uses": [], "values": values}

    def _style_system_decl(self, keyword: str) -> dict[str, Any]:
        name = self.ts.pop_ident()
        uses = self._optional_uses()
        values = self._assign_block(keyword)
        values["_style_system"] = keyword
        return {"node_type": "style_pack", "name": name, "uses": _dedupe_keep_first(uses), "values": values}

    def _simple_mapping_decl(self, node_type: str) -> dict[str, Any]:
        name = self.ts.pop_ident()
        values = self._assign_block(node_type)
        return {"node_type": node_type, "name": name, "values": values}

    def _structured_decl(self, node_type: str, keyword: str) -> dict[str, Any]:
        name = self.ts.pop_ident()
        decl_kind = None
        if keyword == "family" and self.ts.peek(":"):
            self.ts.pop(":")
            decl_kind = self.ts.pop_ident()
        uses = self._optional_uses()
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
        self.ts.pop("{")
        while not self.ts.peek("}"):
            item = self.ts.pop_ident()
            if item in {"defaults", "params", "geometry", "features", "surface", "assembly"}:
                values = self._assign_block(item)
                if item == "defaults":
                    defaults = values
                elif item == "params":
                    params = values
                elif item == "geometry":
                    geometry = values
                elif item == "features":
                    features = values
                elif item == "surface":
                    surface = values
                elif item == "assembly":
                    assembly = values
            elif item in {"space", "search"}:
                space = self._space_body("space_inline" if item == "space" else "search_inline")
            elif item == "repair_policy":
                repair_policy = self._assign_block("repair_policy")
            elif item in {"ensure", "prefer"}:
                rules.append(self._rule(item))
            else:
                assigns.append((self._finish_path(item), self._assign_value()))
        self.ts.pop("}")
        return {
            "node_type": node_type,
            "name": name,
            "kind": decl_kind,
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

    def _asset_decl(self) -> dict[str, Any]:
        name = self.ts.pop_ident()
        self.ts.pop(":")
        kind = self.ts.pop_ident()
        from_family = ""
        if self.ts.peek("from"):
            self.ts.pop("from")
            from_family = self._qident()
        uses = self._optional_uses()
        values: dict[str, Any] = {
            "node_type": "asset",
            "name": name,
            "kind": kind,
            "from": from_family,
            "uses": _dedupe_keep_first(uses),
            "refs": {},
            "intent": {},
            "geometry": {},
            "features": {},
            "surface": {},
            "assembly": {},
            "fit": {},
            "transfer": {},
            "reuse": {},
            "constraints": {},
            "ingest": {},
            "assembly_rules": {},
            "execution": {},
            "space": {},
            "repair_policy": {},
            "build": {},
            "validate": {},
            "package": {},
            "publish": {},
            "experimental": {},
        }
        self.ts.pop("{")
        while not self.ts.peek("}"):
            block = self.ts.pop_ident()
            if block in self.ASSET_BLOCKS:
                key = "surface" if block == "surface" else block
                values[key] = self._assign_block(block)
            elif block in {"space", "search"}:
                values["space"] = self._space_body("space_inline" if block == "space" else "search_inline")
            elif block == "repair_policy":
                values["repair_policy"] = self._assign_block("repair_policy")
            elif block == "build":
                values["build"] = self._build_block()
            elif block == "validate":
                values["validate"] = self._validate_block()
            elif block == "experimental":
                values["experimental"] = self._experimental_block()
            else:
                raise LatheParseError(f"Unexpected asset block '{block}'")
        self.ts.pop("}")
        return values

    def _experimental_block(self) -> dict[str, Any]:
        """Parse the Phase 13 experimental block.

        All experimental sub-blocks live INSIDE this single wrapper. The
        wrapper itself is OPTIONAL on the asset; absence is the default
        and produces no ``experimental`` key downstream. The sub-block
        names are loose by design — unknown sub-blocks are tolerated at
        the parser level so the checker can emit an actionable
        ``L7100`` diagnostic instead of a hard parse error. Order is
        free; duplicates are taken last-wins.
        """
        out: dict[str, Any] = {}
        self.ts.pop("{")
        while not self.ts.peek("}"):
            sub_block = self.ts.pop_ident()
            if sub_block == "art_direction":
                out["art_direction"] = self._experimental_art_direction_block()
            elif sub_block == "references":
                out["references"] = self._experimental_references_block()
            elif sub_block == "kit":
                out["kit"] = self._experimental_kit_block()
            else:
                # Tolerated by the parser; flagged as L7100 by the
                # checker. Skip the block body so parsing recovers.
                out.setdefault("_unknown_subblocks", []).append(sub_block)
                self._skip_block_body()
        self.ts.pop("}")
        return out

    def _experimental_art_direction_block(self) -> dict[str, Any]:
        """Parse ``art_direction { ... }`` inside the experimental block.

        Field names are NOT enforced at the parser level — every
        recognized assignment lands in ``values``; the checker (L7101,
        L7102) decides which ones are in the MVP whitelist and whether
        their value types are valid.
        """
        return self._assign_block("experimental.art_direction")

    def _experimental_references_block(self) -> dict[str, Any]:
        """Parse ``references { use = "<path>" }`` inside experimental."""
        return self._assign_block("experimental.references")

    def _experimental_kit_block(self) -> dict[str, Any]:
        """Parse ``kit { use = [<part>, ...] }`` inside experimental."""
        return self._assign_block("experimental.kit")

    def _skip_block_body(self) -> None:
        """Skip a balanced ``{ ... }`` block, preserving brace nesting."""
        self.ts.pop("{")
        depth = 1
        while depth > 0:
            if self.ts.eof():
                raise LatheParseError("Unterminated experimental sub-block")
            tok = self.ts.peek()
            if tok == "{":
                self.ts.pop("{")
                depth += 1
                continue
            if tok == "}":
                self.ts.pop("}")
                depth -= 1
                continue
            self.ts.pop()

    def _build_block(self) -> dict[str, Any]:
        values: dict[str, Any] = {}
        self.ts.pop("{")
        while not self.ts.peek("}"):
            block = self.ts.pop_ident()
            if block not in self.BUILD_BLOCKS:
                raise LatheParseError(f"Unexpected build block '{block}'")
            values[block] = self._assign_block(block)
        self.ts.pop("}")
        return values

    def _validate_block(self) -> dict[str, Any]:
        assignments: list[tuple[str, Any]] = []
        rules: list[dict[str, Any]] = []
        repair: dict[str, Any] = {}
        self.ts.pop("{")
        while not self.ts.peek("}"):
            item = self.ts.pop_ident()
            if item in {"ensure", "prefer"}:
                rules.append(self._rule(item))
            elif item == "repair":
                repair = self._assign_block("repair")
            else:
                assignments.append((self._finish_path(item), self._assign_value()))
        self.ts.pop("}")
        values = self._assignments(assignments, "validate")
        values["rules"] = rules
        values["repair"] = repair
        return values

    def _test_like(self, node_type: str) -> dict[str, Any]:
        name = self.ts.pop_ident()
        values: list[tuple[str, Any]] = []
        asserts: list[dict[str, Any]] = []
        self.ts.pop("{")
        while not self.ts.peek("}"):
            item = self.ts.pop_ident()
            if item == "assert":
                asserts.append({"node_type": "assert", "expr": self._expr()})
            else:
                values.append((self._finish_path(item), self._assign_value()))
        self.ts.pop("}")
        return {
            "node_type": node_type,
            "name": name,
            "values": self._assignments(values, node_type),
            "asserts": asserts,
        }

    def _space_decl(self) -> dict[str, Any]:
        name = self.ts.pop_ident()
        payload = self._space_body("space_decl")
        payload["name"] = name
        return payload

    def _space_body(self, node_type: str) -> dict[str, Any]:
        assigns: list[tuple[str, Any]] = []
        vary: list[dict[str, Any]] = []
        freeze: list[str] = []
        objectives: list[dict[str, Any]] = []
        select: dict[str, Any] = {}
        self.ts.pop("{")
        while not self.ts.peek("}"):
            item = self.ts.pop_ident()
            if item == "vary":
                vary.append({"path": self._path(), "domain": self._expect_in_expr()})
            elif item == "freeze":
                freeze.append(self._path())
            elif item == "objective":
                direction = self.ts.pop_ident()
                if direction not in {"maximize", "minimize"}:
                    raise LatheParseError("objective must use maximize or minimize")
                metric = self._metric_ref()
                objective = {"direction": direction, "metric": metric}
                if self.ts.peek("weight"):
                    self.ts.pop("weight")
                    objective["weight"] = float(self._number_value())
                objectives.append(objective)
            elif item == "select":
                if self.ts.pop_ident() != "best_of":
                    raise LatheParseError("select currently supports best_of")
                select["best_of"] = int(self._number_value())
            else:
                assigns.append((self._finish_path(item), self._assign_value()))
        self.ts.pop("}")
        return {
            "node_type": node_type,
            "values": self._assignments(assigns, "space"),
            "vary": vary,
            "freeze": _dedupe_keep_first(freeze),
            "objectives": objectives,
            "select": select,
        }

    def _scene_decl(self, *, node_type: str = "scene") -> dict[str, Any]:
        name = self.ts.pop_ident()
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
        self.ts.pop("{")
        while not self.ts.peek("}"):
            item = self.ts.pop_ident()
            if item == "style":
                styles.append(self._scene_named_assign_block("scene_style", "style"))
            elif item == "style_pack" and self.ts.kind() == "ident":
                style_packs.append(self._scene_named_assign_block("scene_style_pack", "style_pack"))
            elif item in {"faction_pack", "biome_kit", "architecture_grammar", "object_grammar"} and self.ts.kind() == "ident":
                style_packs.append(self._scene_style_system_block(item))
            elif item == "region":
                regions.append(self._scene_typed_assign_block("scene_region", "region", field="type"))
            elif item in {"group", "collection"}:
                groups.append(self._scene_named_assign_block("scene_group", item))
            elif item == "placement_zone":
                placement_zones.append(self._scene_typed_assign_block("scene_placement_zone", "placement_zone", field="type"))
            elif item == "module":
                modules.append(self._scene_object_block(node_type="scene_module", construct="module"))
            elif item == "kit":
                kits.append(self._scene_kit_block())
            elif item == "variant_family":
                variant_families.append(self._scene_variant_family_block())
            elif item == "generator":
                generators.append(self._scene_generator_block())
            elif item == "biome":
                biomes.append(self._scene_biome_block())
            elif item == "scatter":
                scatters.append(self._scene_scatter_block())
            elif item == "environment":
                environments.append(self._scene_environment_block())
            elif item in {"object", "instance"}:
                objects.append(self._scene_object_block(construct=item))
            elif item == "terrain":
                objects.append(self._scene_terrain_block())
            elif item in {
                "road",
                "bridge",
                "building",
                "building_envelope",
                "floor_stack",
                "facade_grid",
                "facade_bay",
                "roof_profile",
                "vertical_core",
                "entrance_plan",
                "site_compound",
                "building_lot",
                "courtyard_plan",
                "pedestrian_path",
                "service_alley",
                "parking_zone",
                "loading_zone",
                "exterior_utility",
                "building_complex",
                "harbor_complex",
                "dockyard",
                "vehicle_yard",
                "hangar_complex",
                "factory_complex",
                "production_line",
                "industrial_district",
                "transport_corridor",
                "supply_network",
                "resource_region",
                "settlement",
                "civilization",
                "culture_system",
                "law_code",
                "policy_rule",
                "economy_model",
                "trade_policy",
                "diplomacy_state",
                "social_graph",
                "social_relation",
                "population_group",
                "labor_system",
                "ritual_calendar",
                "festival",
                "belief_system",
                "cultural_marker",
                "civic_institution",
                "quest",
                "objective",
                "mission",
                "objective_chain",
                "success_condition",
                "failure_condition",
                "reward_table",
                "loot_table",
                "inventory_slot",
                "crafting_station",
                "recipe",
                "shop",
                "vendor",
                "currency",
                "reputation_rule",
                "unlock_rule",
                "progression_track",
                "gameplay_rule",
                "interactable",
                "encounter",
                "director",
                "encounter_director",
                "director_intent",
                "pacing_curve",
                "threat_budget",
                "spawn_wave",
                "spawn_budget",
                "combat_phase",
                "stealth_phase",
                "escalation_rule",
                "adaptive_difficulty",
                "encounter_beat",
                "director_signal",
                "threat_zone",
                "reinforcement_route",
                "simulation_layer",
                "heat_field",
                "noise_field",
                "visibility_field",
                "resource_flow",
                "faction_pressure",
                "territory_influence",
                "alarm_grid",
                "patrol_density",
                "hazard_field",
                "sensor_grid",
                "cover_map",
                "flow_gate",
                "world_metric",
                "simulation_probe",
                "traversal_gate",
                "resource_economy",
                "control_zone",
                "npc",
                "agent",
                "crowd",
                "schedule",
                "patrol_route",
                "dialogue_tree",
                "inventory_loadout",
                "spawn_ecology",
                "biome_system",
                "habitat_zone",
                "species_population",
                "food_web",
                "predator_prey_link",
                "migration_route",
                "nesting_site",
                "resource_patch",
                "resource_regeneration",
                "growth_cycle",
                "weather_ecology_link",
                "ecological_pressure",
                "land_use_plan",
                "farm_plot",
                "hunting_ground",
                "fishing_ground",
                "grazing_range",
                "extraction_site",
                "pollution_source",
                "conservation_zone",
                "restoration_project",
                "scarcity_loop",
                "settlement_pressure",
                "resource_claim",
                "harvest_cycle",
                "carrying_capacity_rule",
                "biome_impact",
                "supply_chain",
                "logistics_hub",
                "storage_depot",
                "stockpile",
                "input_buffer",
                "output_buffer",
                "processing_stage",
                "refinery_stage",
                "workshop_stage",
                "assembly_stage",
                "market_node",
                "demand_sink",
                "supply_route",
                "transport_leg",
                "bottleneck",
                "throughput_rule",
                "failure_mode",
                "production_strategy",
                "production_priority",
                "quota_rule",
                "allocation_rule",
                "rationing_policy",
                "strategic_reserve",
                "trade_embargo",
                "sabotage_target",
                "maintenance_plan",
                "repair_schedule",
                "mobilization_order",
                "production_mode",
                "wartime_production",
                "peacetime_production",
                "procurement_contract",
                "readiness_level",
                "conflict_system",
                "strategic_objective",
                "war_plan",
                "battlefront",
                "escalation_ladder",
                "treaty",
                "ceasefire",
                "alliance",
                "rival_claim",
                "diplomatic_demand",
                "negotiation_channel",
                "sanction",
                "espionage_cell",
                "covert_operation",
                "disaster_response",
                "emergency_order",
                "faction_ai",
                "doctrine_model",
                "goal_stack",
                "threat_model",
                "perception_feed",
                "decision_rule",
                "policy_selector",
                "action_option",
                "response_plan",
                "escalation_choice",
                "deescalation_choice",
                "resource_strategy",
                "logistics_priority",
                "diplomatic_posture",
                "contingency_plan",
                "adaptive_order",
                "operational_plan",
                "order_queue",
                "world_order",
                "patrol_order",
                "convoy_order",
                "construction_order",
                "repair_order",
                "relief_order",
                "mission_order",
                "scheduled_action",
                "task_assignment",
                "crew_roster",
                "convoy_route",
                "construction_queue",
                "repair_crew",
                "relief_team",
                "settlement_evolution",
                "growth_phase",
                "expansion_zone",
                "construction_stage",
                "upgrade_plan",
                "district_upgrade",
                "building_upgrade",
                "infrastructure_upgrade",
                "material_delivery",
                "staffing_plan",
                "occupancy_plan",
                "worksite",
                "build_permit",
                "damage_repair_plan",
                "demolition_plan",
                "renovation_project",
                "city_plan",
                "zoning_rule",
                "zoning_district",
                "parcel_grid",
                "land_parcel",
                "parcel_subdivision",
                "block_plan",
                "street_hierarchy",
                "transit_node",
                "civic_service_plan",
                "service_coverage",
                "utility_corridor",
                "district_site_plan",
                "street_crossing",
                "perimeter_plan",
                "security_gate",
                "landscape_zone",
                "traffic_flow",
                "service_flow",
                "access_sequence",
                "public_entry",
                "service_entry",
                "threshold_transition",
                "entry_lobby",
                "access_checkpoint",
                "loading_path",
                "wayfinding_node",
                "circulation_core",
                "stair_run",
                "elevator_bank",
                "egress_route",
                "emergency_exit",
                "corridor_spine",
                "floor_transition",
                "public_circulation",
                "service_circulation",
                "stair_detail",
                "tread_pattern",
                "landing_platform",
                "handrail_run",
                "corridor_shell",
                "door_rhythm",
                "ceiling_service_grid",
                "egress_surface_plan",
                "room_route_binding",
                "power_grid",
                "substation",
                "transformer_bank",
                "power_line",
                "water_network",
                "pump_station",
                "water_tower",
                "sewer_network",
                "treatment_plant",
                "data_network",
                "data_hub",
                "fiber_line",
                "transit_line",
                "transit_station",
                "service_connection",
                "maintenance_access",
                "building_service_plan",
                "service_core",
                "utility_room",
                "mechanical_room",
                "electrical_panel",
                "meter_bank",
                "plumbing_stack",
                "hvac_system",
                "ventilation_duct",
                "elevator_core",
                "service_elevator",
                "service_shaft",
                "fire_suppression",
                "sprinkler_zone",
                "waste_chute",
                "loading_dock",
                "room_program",
                "bathroom",
                "kitchen",
                "lab_room",
                "med_bay",
                "workshop_room",
                "control_room",
                "storage_room",
                "office_room",
                "bedroom",
                "fixture_cluster",
                "appliance_bank",
                "workstation_cluster",
                "cabinet_wall",
                "counter_run",
                "sanitary_fixture",
                "lab_bench",
                "medical_bed",
                "tool_rack",
                "room_adjacency",
                "room_connection",
                "door_opening",
                "corridor_link",
                "wall_run",
                "room_socket",
                "fixture_socket",
                "socket_binding",
                "fixture_placement",
                "furniture_placement",
                "service_placement",
                "wall_attachment",
                "anchor_rule",
                "placement_constraint",
                "auto_layout",
                "room_layout_plan",
                "fixture_layout",
                "furniture_layout",
                "service_layout",
                "wall_fixture_layout",
                "layout_solver",
                "room_bounds",
                "wall_side_rule",
                "socket_priority",
                "clearance_zone",
                "layout_slot",
                "footprint_packer",
                "placement_footprint",
                "occupancy_grid",
                "fit_profile",
                "collision_rule",
                "service_reach",
                "room_packing_solver",
                "packing_slot",
                "packed_transform",
                "clearance_reservation",
                "service_anchor_map",
                "room_content_plan",
                "content_family_binding",
                "furniture_asset",
                "fixture_asset",
                "packed_child_asset",
                "content_surface_plan",
                "content_material_zone",
                "content_finish_preset",
                "content_wear_profile",
                "content_marking_set",
                "room_pack_preset",
                "footprint_size_preset",
                "packing_policy_preset",
                "clearance_preset",
                "service_reach_preset",
                "role_item_set",
                "public_space_plan",
                "growth_boundary",
                "district_dependency",
                "development_pressure",
                "climate_zone",
                "climate_risk_map",
                "flood_risk",
                "fire_risk",
                "heat_risk",
                "resource_constraint",
                "protected_land",
                "green_infrastructure",
                "stormwater_system",
                "cooling_corridor",
                "evacuation_route",
                "emergency_shelter",
                "resilience_plan",
                "climate_adaptation",
                "transit_oriented_growth",
                "risk_mitigation",
                "faction_behavior",
                "behavior_graph",
                "event",
                "event_emitter",
                "trigger_volume",
                "timer",
                "state_machine",
                "state_transition",
                "conditional_spawn",
                "alert_network",
                "scene_state",
                "scene_mutation",
                "timeline",
                "sequencer",
                "animation_clip",
                "action",
                "action_pose",
                "motion_path",
                "moving_part",
                "door_action",
                "gate_action",
                "machine_cycle",
                "vfx_emitter",
                "sound_cue",
                "physics_body",
                "physics_joint",
                "hinge_joint",
                "physics_constraint",
                "breakable_part",
                "damage_state",
                "debris_field",
                "rope",
                "cable",
                "cloth_flag",
                "force_field",
                "destruction_event",
                "surface_layer",
                "material_zone",
                "decal",
                "wear_pattern",
                "damage_surface",
                "surface_transition",
                "weather_system",
                "atmosphere",
                "wind_zone",
                "liquid_body",
                "puddle_field",
                "fire_source",
                "smoke_emitter",
                "mist_volume",
                "wetness_zone",
                "heat_haze",
                "time_of_day",
                "environment_effect",
                "shot",
                "shot_sequence",
                "camera_rail",
                "look_at_target",
                "focal_zone",
                "cutscene_beat",
                "orbit_camera",
                "inspection_camera",
                "focus_pull",
                "camera_volume",
                "presentation_rig",
                "composition_guide",
                "ambient_bed",
                "sound_zone",
                "reverb_space",
                "acoustic_occluder",
                "sound_propagation",
                "music_state",
                "music_transition",
                "stinger",
                "foley_emitter",
                "audio_bus",
                "listener_zone",
                "acoustic_material",
                "interaction_prompt",
                "interaction_zone",
                "affordance",
                "usable",
                "pickup",
                "inspect_point",
                "terminal",
                "control_panel",
                "switch",
                "lever",
                "button",
                "door_lock",
                "quest_marker",
                "signage",
                "map_marker",
                "diegetic_hud",
                "ui_anchor",
                "interior",
                "city_block",
                "district",
                "room_cluster",
                "street_grid",
                "floorplan",
                "road_intersection",
                "infrastructure",
                "service_network",
                "access",
                "route",
            }:
                objects.append(self._scene_object_block(construct=item))
            elif item == "array":
                arrays.append(self._scene_object_block(node_type="scene_array", construct="array"))
            elif item == "socket" and self.ts.kind() == "ident":
                sockets.append(self._scene_typed_assign_block("scene_socket", "socket", field="type"))
            elif item == "attach" and self.ts.kind() == "ident":
                attachments.append(self._scene_typed_assign_block("scene_attachment", "attach", field="type"))
            elif item == "relationship":
                relationships.append(self._scene_typed_assign_block("scene_relationship", "relationship", field="type"))
            elif item in {"camera", "camera_intent"}:
                cameras.append(self._scene_typed_assign_block("scene_camera", item, field="framing"))
            elif item in {"light", "lighting_plan"}:
                lights.append(self._scene_typed_assign_block("scene_light", item, field="type"))
            elif item == "curiosity_anchor":
                curiosity_anchors.append(self._scene_named_assign_block("scene_curiosity_anchor", item))
            elif item == "hidden_state":
                hidden_state.append(self._scene_named_assign_block("scene_hidden_state", item))
            elif item == "export":
                exports.append(self._scene_named_assign_block("scene_export", "export"))
            else:
                values.append((self._finish_path(item), self._assign_value()))
        self.ts.pop("}")
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

    def _scene_named_assign_block(self, node_type: str, context: str) -> dict[str, Any]:
        name = self.ts.pop_ident()
        values = self._assign_block(context)
        return {"node_type": node_type, "name": name, "values": values}

    def _scene_style_system_block(self, keyword: str) -> dict[str, Any]:
        name = self.ts.pop_ident()
        values = self._assign_block(keyword)
        values["_style_system"] = keyword
        return {"node_type": "scene_style_pack", "name": name, "values": values}

    def _scene_typed_assign_block(self, node_type: str, context: str, *, field: str) -> dict[str, Any]:
        name = self.ts.pop_ident()
        type_value = ""
        if self.ts.peek(":"):
            self.ts.pop(":")
            type_value = self.ts.pop_ident()
        values = self._assign_block(context)
        return {"node_type": node_type, "name": name, field: type_value, "values": values}

    def _scene_object_block(self, *, node_type: str = "scene_object", construct: str = "object") -> dict[str, Any]:
        name = self.ts.pop_ident()
        role = ""
        source = ""
        if self.ts.peek(":"):
            self.ts.pop(":")
            role = self.ts.pop_ident()
        if self.ts.peek("from"):
            self.ts.pop("from")
            source = self._qident()
        assignments: list[tuple[str, Any]] = []
        self.ts.pop("{")
        while not self.ts.peek("}"):
            item = self.ts.pop_ident()
            if item == "gameplay" and self.ts.peek("{"):
                assignments.extend(self._prefixed_assign_block("gameplay", "gameplay"))
            else:
                assignments.append((self._finish_path(item), self._assign_value()))
        self.ts.pop("}")
        values = self._assignments(assignments, "object")
        if construct != "object":
            values.setdefault("_construct", construct)
        return {
            "node_type": node_type,
            "name": name,
            "role": role,
            "from": source,
            "values": values,
        }

    def _scene_kit_block(self) -> dict[str, Any]:
        name = self.ts.pop_ident()
        role = ""
        source = ""
        if self.ts.peek(":"):
            self.ts.pop(":")
            role = self.ts.pop_ident()
        if self.ts.peek("from"):
            self.ts.pop("from")
            source = self._qident()
        assignments: list[tuple[str, Any]] = []
        parts: list[dict[str, Any]] = []
        sockets: list[dict[str, Any]] = []
        attachments: list[dict[str, Any]] = []
        self.ts.pop("{")
        while not self.ts.peek("}"):
            item = self.ts.pop_ident()
            if item == "part":
                parts.append(self._scene_object_block(node_type="scene_kit_part", construct="part"))
            elif item == "socket" and self.ts.kind() == "ident":
                sockets.append(self._scene_typed_assign_block("scene_socket", "socket", field="type"))
            elif item == "attach" and self.ts.kind() == "ident":
                attachments.append(self._scene_typed_assign_block("scene_attachment", "attach", field="type"))
            else:
                assignments.append((self._finish_path(item), self._assign_value()))
        self.ts.pop("}")
        values = self._assignments(assignments, "kit")
        values["_parts"] = parts
        values["_sockets"] = sockets
        values["_attachments"] = attachments
        return {
            "node_type": "scene_kit",
            "name": name,
            "role": role,
            "from": source,
            "values": values,
        }

    def _scene_variant_family_block(self) -> dict[str, Any]:
        name = self.ts.pop_ident()
        assignments: list[tuple[str, Any]] = []
        options: list[dict[str, Any]] = []
        sockets: list[dict[str, Any]] = []
        attachments: list[dict[str, Any]] = []
        constraints: list[dict[str, Any]] = []
        self.ts.pop("{")
        while not self.ts.peek("}"):
            item = self.ts.pop_ident()
            if item == "option":
                options.append(self._scene_object_block(node_type="scene_variant_option", construct="option"))
            elif item == "socket" and self.ts.kind() == "ident":
                sockets.append(self._scene_typed_assign_block("scene_socket", "socket", field="type"))
            elif item == "attach" and self.ts.kind() == "ident":
                attachments.append(self._scene_typed_assign_block("scene_attachment", "attach", field="type"))
            elif item == "constraint" and self.ts.kind() == "ident":
                constraints.append(self._scene_typed_assign_block("scene_constraint", "constraint", field="type"))
            else:
                assignments.append((self._finish_path(item), self._assign_value()))
        self.ts.pop("}")
        values = self._assignments(assignments, "variant_family")
        values["_options"] = options
        values["_sockets"] = sockets
        values["_attachments"] = attachments
        values["_constraints"] = constraints
        return {"node_type": "scene_variant_family", "name": name, "values": values}

    def _scene_generator_block(self) -> dict[str, Any]:
        name = self.ts.pop_ident()
        role = ""
        source = ""
        if self.ts.peek(":"):
            self.ts.pop(":")
            role = self.ts.pop_ident()
        if self.ts.peek("from"):
            self.ts.pop("from")
            source = self._qident()
        assignments: list[tuple[str, Any]] = []
        sockets: list[dict[str, Any]] = []
        attachments: list[dict[str, Any]] = []
        constraints: list[dict[str, Any]] = []
        self.ts.pop("{")
        while not self.ts.peek("}"):
            item = self.ts.pop_ident()
            if item == "socket" and self.ts.kind() == "ident":
                sockets.append(self._scene_typed_assign_block("scene_socket", "socket", field="type"))
            elif item == "attach" and self.ts.kind() == "ident":
                attachments.append(self._scene_typed_assign_block("scene_attachment", "attach", field="type"))
            elif item == "constraint" and self.ts.kind() == "ident":
                constraints.append(self._scene_typed_assign_block("scene_constraint", "constraint", field="type"))
            else:
                assignments.append((self._finish_path(item), self._assign_value()))
        self.ts.pop("}")
        values = self._assignments(assignments, "generator")
        values["_sockets"] = sockets
        values["_attachments"] = attachments
        values["_constraints"] = constraints
        return {
            "node_type": "scene_generator",
            "name": name,
            "role": role,
            "from": source,
            "values": values,
        }

    def _scene_biome_block(self) -> dict[str, Any]:
        name = self.ts.pop_ident()
        assignments: list[tuple[str, Any]] = []
        options: list[dict[str, Any]] = []
        sockets: list[dict[str, Any]] = []
        attachments: list[dict[str, Any]] = []
        constraints: list[dict[str, Any]] = []
        self.ts.pop("{")
        while not self.ts.peek("}"):
            item = self.ts.pop_ident()
            if item == "option":
                options.append(self._scene_object_block(node_type="scene_variant_option", construct="option"))
            elif item == "socket" and self.ts.kind() == "ident":
                sockets.append(self._scene_typed_assign_block("scene_socket", "socket", field="type"))
            elif item == "attach" and self.ts.kind() == "ident":
                attachments.append(self._scene_typed_assign_block("scene_attachment", "attach", field="type"))
            elif item == "constraint" and self.ts.kind() == "ident":
                constraints.append(self._scene_typed_assign_block("scene_constraint", "constraint", field="type"))
            else:
                assignments.append((self._finish_path(item), self._assign_value()))
        self.ts.pop("}")
        values = self._assignments(assignments, "biome")
        values["_options"] = options
        values["_sockets"] = sockets
        values["_attachments"] = attachments
        values["_constraints"] = constraints
        return {"node_type": "scene_biome", "name": name, "values": values}

    def _scene_scatter_block(self) -> dict[str, Any]:
        name = self.ts.pop_ident()
        role = ""
        source = ""
        if self.ts.peek(":"):
            self.ts.pop(":")
            role = self.ts.pop_ident()
        if self.ts.peek("from"):
            self.ts.pop("from")
            source = self._qident()
        assignments: list[tuple[str, Any]] = []
        sockets: list[dict[str, Any]] = []
        attachments: list[dict[str, Any]] = []
        constraints: list[dict[str, Any]] = []
        self.ts.pop("{")
        while not self.ts.peek("}"):
            item = self.ts.pop_ident()
            if item == "socket" and self.ts.kind() == "ident":
                sockets.append(self._scene_typed_assign_block("scene_socket", "socket", field="type"))
            elif item == "attach" and self.ts.kind() == "ident":
                attachments.append(self._scene_typed_assign_block("scene_attachment", "attach", field="type"))
            elif item == "constraint" and self.ts.kind() == "ident":
                constraints.append(self._scene_typed_assign_block("scene_constraint", "constraint", field="type"))
            else:
                assignments.append((self._finish_path(item), self._assign_value()))
        self.ts.pop("}")
        values = self._assignments(assignments, "scatter")
        values["_sockets"] = sockets
        values["_attachments"] = attachments
        values["_constraints"] = constraints
        return {
            "node_type": "scene_scatter",
            "name": name,
            "role": role,
            "from": source,
            "values": values,
        }

    def _scene_environment_block(self) -> dict[str, Any]:
        name = self.ts.pop_ident()
        role = ""
        source = ""
        if self.ts.peek(":"):
            self.ts.pop(":")
            role = self.ts.pop_ident()
        if self.ts.peek("from"):
            self.ts.pop("from")
            source = self._qident()
        assignments: list[tuple[str, Any]] = []
        sockets: list[dict[str, Any]] = []
        attachments: list[dict[str, Any]] = []
        constraints: list[dict[str, Any]] = []
        self.ts.pop("{")
        while not self.ts.peek("}"):
            item = self.ts.pop_ident()
            if item == "socket" and self.ts.kind() == "ident":
                sockets.append(self._scene_typed_assign_block("scene_socket", "socket", field="type"))
            elif item == "attach" and self.ts.kind() == "ident":
                attachments.append(self._scene_typed_assign_block("scene_attachment", "attach", field="type"))
            elif item == "constraint" and self.ts.kind() == "ident":
                constraints.append(self._scene_typed_assign_block("scene_constraint", "constraint", field="type"))
            else:
                assignments.append((self._finish_path(item), self._assign_value()))
        self.ts.pop("}")
        values = self._assignments(assignments, "environment")
        values["_sockets"] = sockets
        values["_attachments"] = attachments
        values["_constraints"] = constraints
        return {
            "node_type": "scene_environment",
            "name": name,
            "role": role,
            "from": source,
            "values": values,
        }

    def _scene_terrain_block(self) -> dict[str, Any]:
        name = self.ts.pop_ident()
        source = ""
        if self.ts.peek("from"):
            self.ts.pop("from")
            source = self._qident()
        assignments: list[tuple[str, Any]] = []
        self.ts.pop("{")
        while not self.ts.peek("}"):
            item = self.ts.pop_ident()
            if item == "gameplay" and self.ts.peek("{"):
                assignments.extend(self._prefixed_assign_block("gameplay", "gameplay"))
            else:
                assignments.append((self._finish_path(item), self._assign_value()))
        self.ts.pop("}")
        values = self._assignments(assignments, "terrain")
        values.setdefault("_construct", "terrain")
        return {
            "node_type": "scene_object",
            "name": name,
            "role": "environment_structure",
            "from": source,
            "values": values,
        }

    def _prefixed_assign_block(self, prefix: str, context: str) -> list[tuple[str, Any]]:
        assignments: list[tuple[str, Any]] = []
        self.ts.pop("{")
        while not self.ts.peek("}"):
            path = self._path()
            assignments.append((f"{prefix}.{path}", self._assign_value()))
        self.ts.pop("}")
        return assignments

    def _variant_decl(self) -> dict[str, Any]:
        name = self.ts.pop_ident()
        if self.ts.pop_ident() != "on":
            raise LatheParseError("variant requires 'on'")
        base = self._qident()
        patches = []
        self.ts.pop("{")
        while not self.ts.peek("}"):
            op = self.ts.pop_ident()
            if op not in {"set", "append", "remove", "unset"}:
                raise LatheParseError(f"Unknown patch op '{op}'")
            path = self._path()
            patch = {"op": op, "path": path}
            if op != "unset":
                patch["value"] = self._assign_value()
            patches.append(patch)
        self.ts.pop("}")
        return {"node_type": "variant", "name": name, "on": base, "patches": patches}
