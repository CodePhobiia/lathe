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
            else:
                raise LatheParseError(f"Unexpected asset block '{block}'")
        self.ts.pop("}")
        return values

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

    def _scene_decl(self) -> dict[str, Any]:
        name = self.ts.pop_ident()
        values: list[tuple[str, Any]] = []
        styles: list[dict[str, Any]] = []
        regions: list[dict[str, Any]] = []
        objects: list[dict[str, Any]] = []
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
            elif item == "region":
                regions.append(self._scene_typed_assign_block("scene_region", "region", field="type"))
            elif item == "object":
                objects.append(self._scene_object_block())
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
            "node_type": "scene",
            "name": name,
            "values": self._assignments(values, "scene"),
            "styles": styles,
            "regions": regions,
            "objects": objects,
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

    def _scene_typed_assign_block(self, node_type: str, context: str, *, field: str) -> dict[str, Any]:
        name = self.ts.pop_ident()
        type_value = ""
        if self.ts.peek(":"):
            self.ts.pop(":")
            type_value = self.ts.pop_ident()
        values = self._assign_block(context)
        return {"node_type": node_type, "name": name, field: type_value, "values": values}

    def _scene_object_block(self) -> dict[str, Any]:
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
        return {
            "node_type": "scene_object",
            "name": name,
            "role": role,
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
