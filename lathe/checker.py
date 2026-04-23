from __future__ import annotations

from typing import Any

from .backends import (
    BACKEND_SELECTION_STAGES,
    BACKENDS,
    BackendResolutionError,
    evaluate_backend,
    evaluate_stack,
    list_stacks,
    select_stack,
)
from .resolver import ResolutionError, Resolver


BACKEND_PATHS = {
    "shape": "build.shape.backend",
    "topology": "build.topology.backend",
    "uv": "build.uv.backend",
    "package": "package.backend",
}

V13_1_EVIDENCE_CLASSES = {
    "geometry_evidence",
    "topology_evidence",
    "uv_evidence",
    "bake_evidence",
    "surface_evidence",
    "package_export_evidence",
}


def diag(
    code: str,
    name: str,
    severity: str,
    phase: str,
    message: str,
    *,
    asset: str | None = None,
    stage: str | None = None,
    path: str | None = None,
    details: dict[str, Any] | None = None,
    suggested_repairs: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "code": code,
        "name": name,
        "severity": severity,
        "phase": phase,
        "asset": asset,
        "stage": stage,
        "path": path,
        "message": message,
        "details": details or {},
        "suggested_repairs": suggested_repairs or [],
    }


class Checker:
    def __init__(self, program: dict[str, Any]) -> None:
        self.program = program
        self.resolver = Resolver(program)
        self.diagnostics: list[dict[str, Any]] = []

    def run(self) -> list[dict[str, Any]]:
        self._check_duplicate_names()
        self._check_use_graphs()
        self._check_critics()
        self._check_new_declarations()
        self._check_assets_and_variants()
        self._check_tests_and_benchmarks()
        return self.diagnostics

    def _check_duplicate_names(self) -> None:
        namespaces = [
            ("profiles", "L2001"),
            ("contracts", "L2002"),
            ("critics", "L2003"),
            ("libraries", "L2004"),
            ("kits", "L2005"),
            ("patterns", "L2006"),
            ("families", "L2006"),
            ("components", "L2007"),
            ("assemblies", "L2008"),
            ("traits", "L2009"),
            ("mechanisms", "L2010"),
            ("materials", "L2011"),
            ("surface_programs", "L2011"),
            ("surface_backends", "L2011"),
            ("surface_policies", "L2011"),
            ("decal_libraries", "L2011"),
            ("mask_programs", "L2011"),
            ("trim_sheets", "L2011"),
            ("palettes", "L2012"),
            ("reference_sets", "L2012"),
            ("reconstruct_policies", "L2012"),
            ("adapt_policies", "L2012"),
            ("assembly_policies", "L2012"),
            ("fit_profiles", "L2012"),
            ("transfer_rules", "L2012"),
            ("execution_profiles", "L2012"),
            ("render_fixtures", "L2012"),
            ("bake_profiles", "L2012"),
            ("library_bindings", "L2012"),
            ("material_graphs", "L2012"),
            ("inspection_policies", "L2012"),
            ("repair_policies", "L2013"),
            ("fixtures", "L2014"),
            ("tests", "L2015"),
            ("benchmarks", "L2016"),
            ("spaces", "L2017"),
            ("assets", "L2004"),
            ("variants", "L2005"),
        ]
        for ns_key, code in namespaces:
            seen: set[str] = set()
            for decl in self.program.get(ns_key, []):
                name = decl["name"]
                if name in seen:
                    self.diagnostics.append(
                        diag(code, "duplicate_name", "error", "resolve", f"Duplicate declaration '{name}' in {ns_key[:-1]} namespace")
                    )
                seen.add(name)

    def _check_use_graphs(self) -> None:
        for decl_type, ns_key in [("profile", "profiles"), ("contract", "contracts")]:
            for decl in self.program.get(ns_key, []):
                try:
                    self._walk_decl_uses(decl_type, decl["name"], [])
                except ResolutionError as exc:
                    self.diagnostics.append(
                        diag("L2101", "use_cycle_or_invalid_use", "error", "resolve", str(exc), path=f"{decl_type}.{decl['name']}.uses")
                    )

    def _walk_decl_uses(self, decl_type: str, decl_name: str, stack: list[tuple[str, str]]) -> None:
        decl = self.resolver.profile_map[decl_name] if decl_type == "profile" else self.resolver.contract_map[decl_name]
        key = (decl_type, decl_name)
        if key in stack:
            cycle = " -> ".join(name for _, name in [*stack, key])
            raise ResolutionError(f"Use cycle detected: {cycle}")
        stack.append(key)
        for use_name in decl.get("uses", []):
            child_type, child_decl = self.resolver._resolve_use_decl(use_name, decl_type)
            self._walk_decl_uses(child_type, child_decl["name"], stack)
        stack.pop()

    def _check_critics(self) -> None:
        for critic in self.program.get("critics", []):
            body = critic.get("body")
            if isinstance(body, dict) and body.get("type") == "weighted":
                total = 0.0
                for item in body.get("items", []):
                    weight = float(item.get("weight", 0.0))
                    total += weight
                    if weight < 0:
                        self.diagnostics.append(
                            diag(
                                "L3201",
                                "negative_critic_weight",
                                "error",
                                "typecheck",
                                f"Critic '{critic['name']}' has a negative weight",
                                path=f"critic.{critic['name']}",
                            )
                        )
                if total == 0:
                    self.diagnostics.append(
                        diag(
                            "L3202",
                            "zero_total_critic_weight",
                            "error",
                            "typecheck",
                            f"Critic '{critic['name']}' has zero total weight",
                            path=f"critic.{critic['name']}",
                        )
                    )

    def _check_new_declarations(self) -> None:
        for family in self.program.get("families", []):
            for component_name in family.get("assembly", {}).get("components", []):
                if component_name not in self.resolver.component_map:
                    self.diagnostics.append(
                        diag(
                            "L5201",
                            "unknown_component_reference",
                            "error",
                            "resolve",
                            f"Family '{family['name']}' references unknown component '{component_name}'",
                            path=f"family.{family['name']}.assembly.components",
                        )
                    )
            palette_name = family.get("surface", {}).get("palette")
            if palette_name and palette_name not in self.resolver.palette_map:
                self.diagnostics.append(
                    diag(
                        "L5202",
                        "unknown_palette_reference",
                        "error",
                        "resolve",
                        f"Family '{family['name']}' references unknown palette '{palette_name}'",
                        path=f"family.{family['name']}.surface.palette",
                    )
                )
            surface_program_name = family.get("surface", {}).get("program")
            if surface_program_name and surface_program_name not in self.resolver.surface_program_map:
                self.diagnostics.append(
                    diag(
                        "L5209",
                        "unknown_surface_program_reference",
                        "error",
                        "resolve",
                        f"Family '{family['name']}' references unknown surface_program '{surface_program_name}'",
                        path=f"family.{family['name']}.surface.program",
                    )
                )
            self._check_surface_v12_refs(family.get("surface", {}), f"family.{family['name']}.surface", family["name"])
            for pattern_name in family.get("surface", {}).get("patterns", []):
                if pattern_name not in self.resolver.pattern_map:
                    self.diagnostics.append(
                        diag(
                            "L5210",
                            "unknown_pattern_reference",
                            "error",
                            "resolve",
                            f"Family '{family['name']}' references unknown pattern '{pattern_name}'",
                            path=f"family.{family['name']}.surface.patterns",
                        )
                    )
            repair_policy_name = family.get("repair_policy", {}).get("use")
            if repair_policy_name and repair_policy_name not in self.resolver.repair_policy_map:
                self.diagnostics.append(
                    diag(
                        "L5203",
                        "unknown_repair_policy_reference",
                        "error",
                        "resolve",
                        f"Family '{family['name']}' references unknown repair policy '{repair_policy_name}'",
                        path=f"family.{family['name']}.repair_policy.use",
                    )
                )

        for palette in self.program.get("palettes", []):
            material_names = list(palette.get("values", {}).get("materials", []) or palette.get("values", {}).get("slots", []))
            for material_name in material_names:
                if material_name not in self.resolver.material_map:
                    self.diagnostics.append(
                        diag(
                            "L5204",
                            "unknown_material_reference",
                            "error",
                            "resolve",
                            f"Palette '{palette['name']}' references unknown material '{material_name}'",
                            path=f"palette.{palette['name']}.values",
                        )
                    )

        for profile in self.program.get("execution_profiles", []):
            values = profile.get("values", {})
            engine = values.get("engine")
            mode = values.get("mode")
            inspection_policy_name = values.get("inspection_policy")
            if engine and engine != "blender":
                self.diagnostics.append(
                    diag(
                        "L5230",
                        "unsupported_execution_engine",
                        "error",
                        "typecheck",
                        f"Execution profile '{profile['name']}' uses unsupported engine '{engine}'",
                        path=f"execution_profile.{profile['name']}.engine",
                    )
                )
            if mode and mode not in {"background_cli", "python_module"}:
                self.diagnostics.append(
                    diag(
                        "L5231",
                        "unsupported_execution_mode",
                        "error",
                        "typecheck",
                        f"Execution profile '{profile['name']}' uses unsupported mode '{mode}'",
                        path=f"execution_profile.{profile['name']}.mode",
                    )
                )
            if inspection_policy_name and inspection_policy_name not in self.resolver.inspection_policy_map:
                self.diagnostics.append(
                    diag(
                        "L5238",
                        "unknown_inspection_policy_reference",
                        "error",
                        "resolve",
                        f"Execution profile '{profile['name']}' references unknown inspection policy '{inspection_policy_name}'",
                        path=f"execution_profile.{profile['name']}.inspection_policy",
                    )
                )

        for binding in self.program.get("library_bindings", []):
            target = str(binding.get("values", {}).get("target", "") or "")
            if target and target != "blender_assets":
                self.diagnostics.append(
                    diag(
                        "L5232",
                        "unsupported_library_binding_target",
                        "error",
                        "typecheck",
                        f"Library binding '{binding['name']}' uses unsupported target '{target}'",
                        path=f"library_binding.{binding['name']}.target",
                    )
                )

        for policy in self.program.get("inspection_policies", []):
            values = policy.get("values", {})
            required = values.get("require", values.get("required_evidence", values.get("evidence", [])))
            if isinstance(required, str):
                required = [required]
            for evidence_class in required or []:
                if evidence_class not in V13_1_EVIDENCE_CLASSES:
                    self.diagnostics.append(
                        diag(
                            "L5239",
                            "unknown_inspection_evidence_class",
                            "error",
                            "typecheck",
                            f"Inspection policy '{policy['name']}' requires unknown evidence class '{evidence_class}'",
                            path=f"inspection_policy.{policy['name']}.require",
                        )
                    )

    def _check_assets_and_variants(self) -> None:
        names = [decl["name"] for decl in self.program.get("assets", [])] + [decl["name"] for decl in self.program.get("variants", [])]
        for name in names:
            try:
                asset = self.resolver.materialize_asset(name)
            except ResolutionError as exc:
                self.diagnostics.append(diag("L2102", "resolution_error", "error", "resolve", str(exc), asset=name))
                continue
            self._check_materialized_asset(asset)

    def _check_materialized_asset(self, asset: dict[str, Any]) -> None:
        asset_name = asset["name"]
        intent = asset.get("intent", {})
        build = asset.get("build", {})
        validate = asset.get("validate", {})

        if not intent.get("role"):
            self.diagnostics.append(
                diag("L4101", "missing_role", "error", "typecheck", "Asset intent.role is required", asset=asset_name, path="intent.role")
            )

        if "scale" in intent and "dimensions" in intent:
            self.diagnostics.append(
                diag(
                    "L3203",
                    "scale_dimensions_conflict",
                    "error",
                    "typecheck",
                    "intent.scale and intent.dimensions are mutually exclusive",
                    asset=asset_name,
                    path="intent",
                )
            )

        family_name = asset.get("assembly", {}).get("family")
        if family_name and family_name not in self.resolver.family_map:
            self.diagnostics.append(
                diag(
                    "L5205",
                    "unknown_family_reference",
                    "error",
                    "resolve",
                    f"Asset '{asset_name}' references unknown family '{family_name}'",
                    asset=asset_name,
                    path="assembly.family",
                )
            )

        from_family = asset.get("from")
        if from_family and from_family not in self.resolver.family_map and from_family not in self.resolver.kit_map:
            self.diagnostics.append(
                diag(
                    "L5211",
                    "unknown_from_family_reference",
                    "error",
                    "resolve",
                    f"Asset '{asset_name}' references unknown family '{from_family}' in from clause",
                    asset=asset_name,
                    path="from",
                )
            )
        for component_name in asset.get("assembly", {}).get("components", []):
            if component_name not in self.resolver.component_map:
                self.diagnostics.append(
                    diag(
                        "L5201",
                        "unknown_component_reference",
                        "error",
                        "resolve",
                        f"Asset '{asset_name}' references unknown component '{component_name}'",
                        asset=asset_name,
                        path="assembly.components",
                    )
                )
        for trait_name in asset.get("assembly", {}).get("traits", []):
            if trait_name not in self.resolver.trait_map:
                self.diagnostics.append(
                    diag(
                        "L5206",
                        "unknown_trait_reference",
                        "error",
                        "resolve",
                        f"Asset '{asset_name}' references unknown trait '{trait_name}'",
                        asset=asset_name,
                        path="assembly.traits",
                    )
                )
        for mechanism_name in asset.get("assembly", {}).get("mechanisms", []):
            if mechanism_name not in self.resolver.mechanism_map:
                self.diagnostics.append(
                    diag(
                        "L5207",
                        "unknown_mechanism_reference",
                        "error",
                        "resolve",
                        f"Asset '{asset_name}' references unknown mechanism '{mechanism_name}'",
                        asset=asset_name,
                        path="assembly.mechanisms",
                    )
                )

        for ref_name in asset.get("refs", {}).get("reference_sets", []):
            if ref_name not in self.resolver.reference_set_map:
                self.diagnostics.append(
                    diag(
                        "L5212",
                        "unknown_reference_set_reference",
                        "error",
                        "resolve",
                        f"Asset '{asset_name}' references unknown reference_set '{ref_name}'",
                        asset=asset_name,
                        path="refs.reference_sets",
                    )
                )
        palette_name = asset.get("surface", {}).get("palette")
        if palette_name and palette_name not in self.resolver.palette_map:
            self.diagnostics.append(
                diag(
                    "L5202",
                    "unknown_palette_reference",
                    "error",
                    "resolve",
                    f"Asset '{asset_name}' references unknown palette '{palette_name}'",
                    asset=asset_name,
                    path="surface.palette",
                )
            )
        surface_program_name = asset.get("surface", {}).get("program")
        if surface_program_name and surface_program_name not in self.resolver.surface_program_map:
            self.diagnostics.append(
                diag(
                    "L5209",
                    "unknown_surface_program_reference",
                    "error",
                    "resolve",
                    f"Asset '{asset_name}' references unknown surface_program '{surface_program_name}'",
                    asset=asset_name,
                    path="surface.program",
                )
            )
        self._check_surface_v12_refs(asset.get("surface", {}), "surface", asset_name)
        for pattern_name in asset.get("surface", {}).get("patterns", []):
            if pattern_name not in self.resolver.pattern_map:
                self.diagnostics.append(
                    diag(
                        "L5210",
                        "unknown_pattern_reference",
                        "error",
                        "resolve",
                        f"Asset '{asset_name}' references unknown pattern '{pattern_name}'",
                        asset=asset_name,
                        path="surface.patterns",
                    )
                )
        space_name = asset.get("space", {}).get("use")
        if space_name and space_name not in self.resolver.space_map:
            self.diagnostics.append(
                diag(
                    "L5208",
                    "unknown_space_reference",
                    "error",
                    "resolve",
                    f"Asset '{asset_name}' references unknown search space '{space_name}'",
                    asset=asset_name,
                    path="space.use",
                )
            )
        repair_policy_name = asset.get("repair_policy", {}).get("use")
        if repair_policy_name and repair_policy_name not in self.resolver.repair_policy_map:
            self.diagnostics.append(
                diag(
                    "L5203",
                    "unknown_repair_policy_reference",
                    "error",
                    "resolve",
                    f"Asset '{asset_name}' references unknown repair policy '{repair_policy_name}'",
                    asset=asset_name,
                    path="repair_policy.use",
                )
            )

        execution_profile_name = asset.get("execution", {}).get("profile")
        if execution_profile_name and execution_profile_name not in self.resolver.execution_profile_map:
            self.diagnostics.append(
                diag(
                    "L5233",
                    "unknown_execution_profile_reference",
                    "error",
                    "resolve",
                    f"Asset '{asset_name}' references unknown execution profile '{execution_profile_name}'",
                    asset=asset_name,
                    path="execution.profile",
                )
            )
        for binding_name in asset.get("execution", {}).get("library_bindings", []):
            if binding_name not in self.resolver.library_binding_map:
                self.diagnostics.append(
                    diag(
                        "L5234",
                        "unknown_library_binding_reference",
                        "error",
                        "resolve",
                        f"Asset '{asset_name}' references unknown library binding '{binding_name}'",
                        asset=asset_name,
                        path="execution.library_bindings",
                    )
                )
        bake_profile_name = asset.get("build", {}).get("surface", {}).get("bake_profile")
        if bake_profile_name and bake_profile_name not in self.resolver.bake_profile_map:
            self.diagnostics.append(
                diag(
                    "L5235",
                    "unknown_bake_profile_reference",
                    "error",
                    "resolve",
                    f"Asset '{asset_name}' references unknown bake profile '{bake_profile_name}'",
                    asset=asset_name,
                    path="build.surface.bake_profile",
                )
            )
        render_fixture_name = asset.get("build", {}).get("surface", {}).get("render_fixture")
        if render_fixture_name and render_fixture_name not in self.resolver.render_fixture_map:
            self.diagnostics.append(
                diag(
                    "L5236",
                    "unknown_render_fixture_reference",
                    "error",
                    "resolve",
                    f"Asset '{asset_name}' references unknown render fixture '{render_fixture_name}'",
                    asset=asset_name,
                    path="build.surface.render_fixture",
                )
            )
        material_graph_name = asset.get("surface", {}).get("material_graph")
        if material_graph_name and material_graph_name not in self.resolver.material_graph_map:
            self.diagnostics.append(
                diag(
                    "L5237",
                    "unknown_material_graph_reference",
                    "error",
                    "resolve",
                    f"Asset '{asset_name}' references unknown material graph '{material_graph_name}'",
                    asset=asset_name,
                    path="surface.material_graph",
                )
            )
        inspection_policy_name = asset.get("execution", {}).get("inspection_policy")
        if inspection_policy_name and inspection_policy_name not in self.resolver.inspection_policy_map:
            self.diagnostics.append(
                diag(
                    "L5238",
                    "unknown_inspection_policy_reference",
                    "error",
                    "resolve",
                    f"Asset '{asset_name}' references unknown inspection policy '{inspection_policy_name}'",
                    asset=asset_name,
                    path="execution.inspection_policy",
                )
            )

        fit_profile_name = asset.get("build", {}).get("shape", {}).get("fit_profile") or asset.get("fit", {}).get("profile")
        if fit_profile_name and fit_profile_name not in self.resolver.fit_profile_map:
            self.diagnostics.append(
                diag(
                    "L5213",
                    "unknown_fit_profile_reference",
                    "error",
                    "resolve",
                    f"Asset '{asset_name}' references unknown fit profile '{fit_profile_name}'",
                    asset=asset_name,
                    path="build.shape.fit_profile",
                )
            )
        reconstruct_policy_name = asset.get("build", {}).get("shape", {}).get("reconstruct_policy") or asset.get("fit", {}).get("reconstruct_policy")
        if reconstruct_policy_name and reconstruct_policy_name not in self.resolver.reconstruct_policy_map:
            self.diagnostics.append(
                diag(
                    "L5214",
                    "unknown_reconstruct_policy_reference",
                    "error",
                    "resolve",
                    f"Asset '{asset_name}' references unknown reconstruct policy '{reconstruct_policy_name}'",
                    asset=asset_name,
                    path="build.shape.reconstruct_policy",
                )
            )
        adapt_policy_name = asset.get("build", {}).get("shape", {}).get("adapt_policy") or asset.get("transfer", {}).get("adapt_policy")
        if adapt_policy_name and adapt_policy_name not in self.resolver.adapt_policy_map:
            self.diagnostics.append(
                diag(
                    "L5215",
                    "unknown_adapt_policy_reference",
                    "error",
                    "resolve",
                    f"Asset '{asset_name}' references unknown adapt policy '{adapt_policy_name}'",
                    asset=asset_name,
                    path="build.shape.adapt_policy",
                )
            )
        assembly_policy_name = asset.get("build", {}).get("shape", {}).get("assembly_policy") or asset.get("constraints", {}).get("assembly_policy")
        if assembly_policy_name and assembly_policy_name not in self.resolver.assembly_policy_map:
            self.diagnostics.append(
                diag(
                    "L5216",
                    "unknown_assembly_policy_reference",
                    "error",
                    "resolve",
                    f"Asset '{asset_name}' references unknown assembly policy '{assembly_policy_name}'",
                    asset=asset_name,
                    path="build.shape.assembly_policy",
                )
            )
        for rule_name in asset.get("transfer", {}).get("rules", []):
            if rule_name not in self.resolver.transfer_rule_map:
                self.diagnostics.append(
                    diag(
                        "L5217",
                        "unknown_transfer_rule_reference",
                        "error",
                        "resolve",
                        f"Asset '{asset_name}' references unknown transfer rule '{rule_name}'",
                        asset=asset_name,
                        path="transfer.rules",
                    )
                )
        shape = build.get("shape", {})
        refs = asset.get("refs", {})
        mode = shape.get("mode")
        if mode == "reconstruct" and not (refs.get("images") or refs.get("meshes")):
            self.diagnostics.append(
                diag("L4102", "missing_reconstruct_input", "error", "build", "reconstruct mode requires refs.images or refs.meshes", asset=asset_name, stage="shape", suggested_repairs=["rebuild_shape"])
            )
        if mode == "adapt" and not (refs.get("meshes") or refs.get("assets")):
            self.diagnostics.append(
                diag("L4103", "missing_adapt_input", "error", "build", "adapt mode requires refs.meshes or refs.assets", asset=asset_name, stage="shape", suggested_repairs=["rebuild_shape"])
            )
        if mode == "assemble" and not refs.get("assets") and not asset.get("assembly", {}).get("resolved_kit"):
            self.diagnostics.append(
                diag("L4104", "missing_assemble_input", "error", "build", "assemble mode requires refs.assets", asset=asset_name, stage="shape")
            )

        rig = build.get("rig", {})
        if rig.get("type") == "none" and rig.get("joints"):
            self.diagnostics.append(
                diag("L4201", "rig_none_with_joints", "error", "typecheck", "rig.type = none requires joints to be empty", asset=asset_name, path="build.rig.joints")
            )
        part_names = set(intent.get("parts", []))
        for joint in rig.get("joints", []):
            if joint not in part_names:
                self.diagnostics.append(
                    diag(
                        "L4202",
                        "joint_missing_part",
                        "error",
                        "typecheck",
                        f"Joint '{joint}' is not declared in intent.parts",
                        asset=asset_name,
                        path="build.rig.joints",
                    )
                )

        uv = build.get("uv", {})
        if uv.get("tile_mode") == "zero_to_one" and uv.get("udims"):
            self.diagnostics.append(
                diag("L4301", "udims_with_zero_to_one", "error", "typecheck", "uv.udims must be empty when tile_mode = zero_to_one", asset=asset_name, path="build.uv.udims")
            )

        physics = build.get("physics", {})
        if physics.get("collision") == "convex_decomp" and int(physics.get("max_hulls", 0)) < 1:
            self.diagnostics.append(
                diag("L4401", "invalid_max_hulls", "error", "typecheck", "physics.max_hulls must be >= 1 for convex_decomp", asset=asset_name, path="build.physics.max_hulls")
            )

        threshold = validate.get("threshold", 0.80)
        if not isinstance(threshold, (int, float)) or not (0 <= float(threshold) <= 1):
            self.diagnostics.append(
                diag("L4501", "invalid_threshold", "error", "typecheck", "validate.threshold must be in [0,1]", asset=asset_name, path="validate.threshold")
            )

        for rule in validate.get("rules", []):
            if rule.get("kind") == "prefer" and "weight" in rule and float(rule["weight"]) <= 0:
                self.diagnostics.append(
                    diag("L4502", "non_positive_prefer_weight", "error", "typecheck", "prefer weights must be positive", asset=asset_name, path="validate.rules")
                )

        self._check_backend_resolution(asset)

    def _check_surface_v12_refs(self, surface: dict[str, Any], path_prefix: str, owner_name: str) -> None:
        checks = [
            ("policy", self.resolver.surface_policy_map, "surface_policy", "L5221"),
            ("backend", self.resolver.surface_backend_map, "surface_backend", "L5222"),
        ]
        authoring_backend = surface.get("authoring", {}).get("backend") if isinstance(surface.get("authoring"), dict) else ""
        if authoring_backend and authoring_backend in self.resolver.surface_backend_map:
            surface = {**surface, "backend": authoring_backend}
        for field, namespace, label, code in checks:
            name = surface.get(field)
            if name and name not in namespace and not (field == "backend" and str(name).startswith("lathe.surface.")):
                self.diagnostics.append(
                    diag(
                        code,
                        f"unknown_{label}_reference",
                        "error",
                        "resolve",
                        f"'{owner_name}' references unknown {label} '{name}'",
                        asset=owner_name,
                        path=f"{path_prefix}.{field}",
                    )
                )
        list_checks = [
            ("decal_libraries", self.resolver.decal_library_map, "decal_library", "L5223"),
            ("mask_programs", self.resolver.mask_program_map, "mask_program", "L5224"),
            ("trim_sheets", self.resolver.trim_sheet_map, "trim_sheet", "L5225"),
        ]
        for field, namespace, label, code in list_checks:
            for name in surface.get(field, []):
                if name not in namespace:
                    self.diagnostics.append(
                        diag(
                            code,
                            f"unknown_{label}_reference",
                            "error",
                            "resolve",
                            f"'{owner_name}' references unknown {label} '{name}'",
                            asset=owner_name,
                            path=f"{path_prefix}.{field}",
                        )
                    )

    def _check_tests_and_benchmarks(self) -> None:
        for decl in self.program.get("tests", []):
            asset_name = decl.get("values", {}).get("asset")
            if asset_name and asset_name not in self.resolver.asset_map and asset_name not in self.resolver.variant_map:
                self.diagnostics.append(
                    diag("L5301", "unknown_test_asset", "error", "resolve", f"Test '{decl['name']}' references unknown asset '{asset_name}'", path=f"test.{decl['name']}.values.asset")
                )
        for decl in self.program.get("benchmarks", []):
            values = decl.get("values", {})
            asset_name = values.get("asset")
            if asset_name and asset_name not in self.resolver.asset_map and asset_name not in self.resolver.variant_map:
                self.diagnostics.append(
                    diag("L5302", "unknown_benchmark_asset", "error", "resolve", f"Benchmark '{decl['name']}' references unknown asset '{asset_name}'", path=f"benchmark.{decl['name']}.values.asset")
                )
            for fixture_name in values.get("compare_against", []):
                if fixture_name not in self.resolver.fixture_map:
                    self.diagnostics.append(
                        diag(
                            "L5303",
                            "unknown_fixture_reference",
                            "error",
                            "resolve",
                            f"Benchmark '{decl['name']}' references unknown fixture '{fixture_name}'",
                            path=f"benchmark.{decl['name']}.values.compare_against",
                        )
                    )

    def _check_backend_resolution(self, asset: dict[str, Any]) -> None:
        asset_name = asset["name"]

        for stage in BACKEND_SELECTION_STAGES:
            config = asset.get("package", {}) if stage == "package" else asset.get("build", {}).get(stage, {})
            backend_id = config.get("backend", "auto")
            if backend_id == "auto":
                continue
            if backend_id not in BACKENDS:
                self.diagnostics.append(
                    diag(
                        "L4601",
                        "unknown_backend",
                        "error",
                        "resolve",
                        f"Unknown backend '{backend_id}'",
                        asset=asset_name,
                        stage=stage,
                        path=BACKEND_PATHS[stage],
                    )
                )
                continue
            ok, reasons = evaluate_backend(backend_id, asset, stage)
            if not ok:
                for reason in reasons:
                    self.diagnostics.append(self._backend_diag(asset_name, stage, backend_id, reason))

        try:
            select_stack(asset)
        except BackendResolutionError:
            stack_reasons: dict[str, list[str]] = {}
            for stack in list_stacks():
                ok, reasons = evaluate_stack(stack["id"], asset)
                if not ok:
                    stack_reasons[stack["id"]] = reasons
            self.diagnostics.append(
                diag(
                    "L4604",
                    "no_backend_stack_match",
                    "error",
                    "resolve",
                    "No builtin backend stack can satisfy the current asset configuration",
                    asset=asset_name,
                    details={"candidate_stacks": stack_reasons},
                )
            )

    def _backend_diag(self, asset_name: str, stage: str, backend_id: str, reason: str) -> dict[str, Any]:
        lowered = reason.lower()
        if stage == "uv" and ("tile_mode" in lowered or "unwrap" in lowered or "uv.sets" in lowered):
            code, name = "L4605", "uv_backend_contract_mismatch"
        elif stage == "package" and "package.formats" in lowered:
            code, name = "L4606", "package_backend_format_unsupported"
        elif stage == "shape" and "shape mode" in lowered:
            code, name = "L4607", "shape_backend_mode_unsupported"
        else:
            code, name = "L4602", "backend_contract_mismatch"
        return diag(
            code,
            name,
            "error",
            "resolve",
            f"Backend '{backend_id}' cannot satisfy stage '{stage}': {reason}",
            asset=asset_name,
            stage=stage,
            path=BACKEND_PATHS[stage],
        )


def check_program(program: dict[str, Any]) -> list[dict[str, Any]]:
    return Checker(program).run()
