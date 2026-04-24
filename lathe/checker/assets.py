from __future__ import annotations

from typing import Any

from ..resolver import ResolutionError
from .cross_stage import check_backend_resolution
from .surface import check_surface_v12_refs
from .utils import diag


def check_assets_and_variants(checker: Any) -> None:
    names = [decl["name"] for decl in checker.program.get("assets", [])] + [decl["name"] for decl in checker.program.get("variants", [])]
    for name in names:
        try:
            asset = checker.resolver.materialize_asset(name)
        except ResolutionError as exc:
            checker.diagnostics.append(diag("L2102", "resolution_error", "error", "resolve", str(exc), asset=name))
            continue
        check_materialized_asset(checker, asset)


def check_materialized_asset(checker: Any, asset: dict[str, Any]) -> None:
    asset_name = asset["name"]
    intent = asset.get("intent", {})
    build = asset.get("build", {})
    validate = asset.get("validate", {})

    if not intent.get("role"):
        checker.diagnostics.append(
            diag("L4101", "missing_role", "error", "typecheck", "Asset intent.role is required", asset=asset_name, path="intent.role")
        )

    if "scale" in intent and "dimensions" in intent:
        checker.diagnostics.append(
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
    if family_name and family_name not in checker.resolver.family_map:
        checker.diagnostics.append(
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
    if from_family and from_family not in checker.resolver.family_map and from_family not in checker.resolver.kit_map:
        checker.diagnostics.append(
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
        if component_name not in checker.resolver.component_map:
            checker.diagnostics.append(
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
        if trait_name not in checker.resolver.trait_map:
            checker.diagnostics.append(
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
        if mechanism_name not in checker.resolver.mechanism_map:
            checker.diagnostics.append(
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
        if ref_name not in checker.resolver.reference_set_map:
            checker.diagnostics.append(
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
    if palette_name and palette_name not in checker.resolver.palette_map:
        checker.diagnostics.append(
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
    if surface_program_name and surface_program_name not in checker.resolver.surface_program_map:
        checker.diagnostics.append(
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
    check_surface_v12_refs(checker, asset.get("surface", {}), "surface", asset_name)
    for pattern_name in asset.get("surface", {}).get("patterns", []):
        if pattern_name not in checker.resolver.pattern_map:
            checker.diagnostics.append(
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
    if space_name and space_name not in checker.resolver.space_map:
        checker.diagnostics.append(
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
    if repair_policy_name and repair_policy_name not in checker.resolver.repair_policy_map:
        checker.diagnostics.append(
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
    if execution_profile_name and execution_profile_name not in checker.resolver.execution_profile_map:
        checker.diagnostics.append(
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
        if binding_name not in checker.resolver.library_binding_map:
            checker.diagnostics.append(
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
    if bake_profile_name and bake_profile_name not in checker.resolver.bake_profile_map:
        checker.diagnostics.append(
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
    if render_fixture_name and render_fixture_name not in checker.resolver.render_fixture_map:
        checker.diagnostics.append(
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
    if material_graph_name and material_graph_name not in checker.resolver.material_graph_map:
        checker.diagnostics.append(
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
    if inspection_policy_name and inspection_policy_name not in checker.resolver.inspection_policy_map:
        checker.diagnostics.append(
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
    if fit_profile_name and fit_profile_name not in checker.resolver.fit_profile_map:
        checker.diagnostics.append(
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
    if reconstruct_policy_name and reconstruct_policy_name not in checker.resolver.reconstruct_policy_map:
        checker.diagnostics.append(
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
    if adapt_policy_name and adapt_policy_name not in checker.resolver.adapt_policy_map:
        checker.diagnostics.append(
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
    if assembly_policy_name and assembly_policy_name not in checker.resolver.assembly_policy_map:
        checker.diagnostics.append(
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
        if rule_name not in checker.resolver.transfer_rule_map:
            checker.diagnostics.append(
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
        checker.diagnostics.append(
            diag("L4102", "missing_reconstruct_input", "error", "build", "reconstruct mode requires refs.images or refs.meshes", asset=asset_name, stage="shape", suggested_repairs=["rebuild_shape"])
        )
    if mode == "adapt" and not (refs.get("meshes") or refs.get("assets")):
        checker.diagnostics.append(
            diag("L4103", "missing_adapt_input", "error", "build", "adapt mode requires refs.meshes or refs.assets", asset=asset_name, stage="shape", suggested_repairs=["rebuild_shape"])
        )
    if mode == "assemble" and not refs.get("assets") and not asset.get("assembly", {}).get("resolved_kit"):
        checker.diagnostics.append(
            diag("L4104", "missing_assemble_input", "error", "build", "assemble mode requires refs.assets", asset=asset_name, stage="shape")
        )

    rig = build.get("rig", {})
    if rig.get("type") == "none" and rig.get("joints"):
        checker.diagnostics.append(
            diag("L4201", "rig_none_with_joints", "error", "typecheck", "rig.type = none requires joints to be empty", asset=asset_name, path="build.rig.joints")
        )
    part_names = set(intent.get("parts", []))
    for joint in rig.get("joints", []):
        if joint not in part_names:
            checker.diagnostics.append(
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
        checker.diagnostics.append(
            diag("L4301", "udims_with_zero_to_one", "error", "typecheck", "uv.udims must be empty when tile_mode = zero_to_one", asset=asset_name, path="build.uv.udims")
        )

    physics = build.get("physics", {})
    if physics.get("collision") == "convex_decomp" and int(physics.get("max_hulls", 0)) < 1:
        checker.diagnostics.append(
            diag("L4401", "invalid_max_hulls", "error", "typecheck", "physics.max_hulls must be >= 1 for convex_decomp", asset=asset_name, path="build.physics.max_hulls")
        )

    threshold = validate.get("threshold", 0.80)
    if not isinstance(threshold, (int, float)) or not (0 <= float(threshold) <= 1):
        checker.diagnostics.append(
            diag("L4501", "invalid_threshold", "error", "typecheck", "validate.threshold must be in [0,1]", asset=asset_name, path="validate.threshold")
        )

    for rule in validate.get("rules", []):
        if rule.get("kind") == "prefer" and "weight" in rule and float(rule["weight"]) <= 0:
            checker.diagnostics.append(
                diag("L4502", "non_positive_prefer_weight", "error", "typecheck", "prefer weights must be positive", asset=asset_name, path="validate.rules")
            )

    check_backend_resolution(checker, asset)
