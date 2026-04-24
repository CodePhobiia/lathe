"""Effective build-plan emitter.

Takes a resolved asset and produces the per-stage build plan
(providers, critics, bake intents, package layout) that ``executor``
drives.
"""

from __future__ import annotations

from typing import Any

from .backends import resolve_selected_backends
from .defaults import BUILD_STAGES
from .resolver import Resolver


STAGE_DAG = {
    "shape": ["topology"],
    "topology": ["uv", "rig", "interfaces", "physics", "optimize"],
    "uv": ["surface", "optimize"],
    "surface": ["optimize"],
    "rig": ["interfaces", "physics", "optimize"],
    "interfaces": ["physics", "optimize"],
    "physics": ["optimize"],
    "optimize": ["validate", "package", "publish"],
}

V13_INTERNAL_BACKENDS = {
    "geometry_backend": {
        "blender_gnodes": "lathe.geometry.blender_gnodes_v1",
        "blender_modstack": "lathe.geometry.blender_modstack_v1",
    },
    "uv_backend": {
        "blender_uv": "lathe.uv.blender_uv_v1",
    },
    "bake_backend": {
        "blender_cycles": "lathe.bake.blender_cycles_v1",
    },
    "surface_backend": {
        "blender_materials": "lathe.surface.blender_materials_v1",
    },
    "render_backend": {
        "blender_eval": "lathe.render.blender_eval_v1",
    },
    "package_backend": {
        "blender_export": "lathe.package.blender_export_v1",
    },
    "library_backend": {
        "blender_assets": "lathe.library.blender_assets_v1",
    },
}

V13_1_BRIDGE_BACKENDS = {
    "bridge_backend": "lathe.bridge.blender_execution_v1",
}


def _v11_flow_summary(asset: dict[str, Any]) -> dict[str, Any]:
    shape = asset.get("build", {}).get("shape", {})
    refs = asset.get("refs", {})
    assembly = asset.get("assembly", {})
    fit = asset.get("fit", {})
    transfer = asset.get("transfer", {})
    constraints = asset.get("constraints", {})
    mode = str(shape.get("mode", "generate"))
    return {
        "mode": mode,
        "reference_sets": list(refs.get("reference_sets", [])),
        "resolved_reference_sets": [item.get("name") for item in refs.get("resolved_reference_sets", [])],
        "fit_profile": shape.get("fit_profile") or fit.get("profile") or "",
        "resolved_fit_profile": fit.get("resolved_fit_profile", {}).get("name", ""),
        "reconstruct_policy": shape.get("reconstruct_policy") or fit.get("reconstruct_policy") or "",
        "resolved_reconstruct_policy": fit.get("resolved_reconstruct_policy", {}).get("name", ""),
        "adapt_policy": shape.get("adapt_policy") or transfer.get("adapt_policy") or "",
        "resolved_adapt_policy": transfer.get("resolved_adapt_policy", {}).get("name", ""),
        "transfer_rules": list(transfer.get("rules", [])),
        "resolved_transfer_rules": [item.get("name") for item in transfer.get("resolved_transfer_rules", [])],
        "assembly_policy": shape.get("assembly_policy") or constraints.get("assembly_policy") or "",
        "resolved_assembly_policy": constraints.get("resolved_assembly_policy", {}).get("name", ""),
        "kit": assembly.get("kit", ""),
        "resolved_kit": assembly.get("resolved_kit", {}).get("name", ""),
    }


def _v12_surface_summary(asset: dict[str, Any]) -> dict[str, Any]:
    surface = asset.get("surface", {})
    build_surface = asset.get("build", {}).get("surface", {})
    authoring = surface.get("authoring", {}) if isinstance(surface.get("authoring"), dict) else {}
    return {
        "surface_program": surface.get("program", ""),
        "surface_policy": surface.get("policy", build_surface.get("surface_policy", "")),
        "resolved_surface_policy": surface.get("resolved_surface_policy", {}).get("name", ""),
        "authoring_backend": authoring.get("backend") or surface.get("backend") or build_surface.get("authoring_backend", ""),
        "resolved_surface_backend": surface.get("resolved_surface_backend", {}).get("name", ""),
        "authoring_mode": authoring.get("mode", surface.get("authoring_mode", "")),
        "decal_libraries": list(surface.get("decal_libraries", [])),
        "mask_programs": list(surface.get("mask_programs", [])),
        "trim_sheets": list(surface.get("trim_sheets", [])),
        "resolved_decal_libraries": [item.get("name") for item in surface.get("resolved_decal_libraries", [])],
        "resolved_mask_programs": [item.get("name") for item in surface.get("resolved_mask_programs", [])],
        "resolved_trim_sheets": [item.get("name") for item in surface.get("resolved_trim_sheets", [])],
    }


def _v13_execution_summary(asset: dict[str, Any]) -> dict[str, Any]:
    execution = asset.get("execution", {})
    surface = asset.get("surface", {})
    build_surface = asset.get("build", {}).get("surface", {})
    resolved_profile = execution.get("resolved_execution_profile", {})
    return {
        "profile": execution.get("profile", ""),
        "resolved_execution_profile": resolved_profile.get("name", ""),
        "engine": execution.get("engine", ""),
        "mode": execution.get("mode", ""),
        "deterministic": execution.get("deterministic"),
        "preserve_blend": execution.get("preserve_blend", ""),
        "material_graph": surface.get("material_graph", ""),
        "resolved_material_graph": surface.get("resolved_material_graph", {}).get("name", ""),
        "bake_profile": build_surface.get("bake_profile", ""),
        "resolved_bake_profile": build_surface.get("resolved_bake_profile", {}).get("name", ""),
        "render_fixture": build_surface.get("render_fixture", ""),
        "resolved_render_fixture": build_surface.get("resolved_render_fixture", {}).get("name", ""),
        "library_bindings": list(execution.get("library_bindings", [])),
        "resolved_library_bindings": [item.get("name") for item in execution.get("resolved_library_bindings", [])],
        "internal_backends": {
            key: V13_INTERNAL_BACKENDS.get(key, {}).get(str(execution.get(key, "") or ""), "")
            for key in ("geometry_backend", "uv_backend", "bake_backend", "surface_backend", "render_backend", "package_backend", "library_backend")
        },
    }


def _v13_1_control_summary(asset: dict[str, Any]) -> dict[str, Any]:
    execution = asset.get("execution", {})
    policy = execution.get("resolved_inspection_policy", {})
    values = policy.get("values", {}) if isinstance(policy, dict) else {}
    required = values.get("require", values.get("required_evidence", values.get("evidence", [])))
    if isinstance(required, str):
        required = [required]
    return {
        "bridge_backend": V13_1_BRIDGE_BACKENDS["bridge_backend"],
        "source_of_truth": "lathe_source",
        "inspection_policy": execution.get("inspection_policy", ""),
        "resolved_inspection_policy": policy.get("name", "") if isinstance(policy, dict) else "",
        "required_evidence": list(required or []),
        "patch_source_allowed": bool(values.get("patch_source_allowed", False)),
        "unsafe_blender_python_allowed": bool(values.get("unsafe_blender_python_allowed", False)),
        "default_recovery_branches": ["reselect_candidate", "repair_candidate", "regenerate_candidate", "patch_source"],
    }


def build_plan(program: dict[str, Any], asset_name: str, execution_profile_override: str | None = None) -> dict[str, Any]:
    """Build plan.

    Args:
        program: program argument.
        asset_name: asset_name argument.
        execution_profile_override: execution_profile_override argument.

    Returns:
        The result.
    """
    resolver = Resolver(program)
    explicit = resolver.derive_explicit_asset(asset_name)
    if execution_profile_override:
        explicit.setdefault("execution", {})
        explicit["execution"]["profile"] = execution_profile_override
    use_chain = [decl["name"] for decl in resolver.resolve_use_chain(explicit.get("uses", []))]
    effective = resolver.materialize_asset(asset_name, execution_profile_override=execution_profile_override)
    backend_resolution = resolve_selected_backends(effective)
    return {
        "asset": asset_name,
        "kind": effective["kind"],
        "resolved_uses": use_chain,
        "stages": BUILD_STAGES,
        "dag": STAGE_DAG,
        "backend_stack": backend_resolution["stack"],
        "selected_backends": backend_resolution["selected"],
        "v1_1_flow": _v11_flow_summary(effective),
        "v1_2_surface": _v12_surface_summary(effective),
        "v1_3_execution": _v13_execution_summary(effective),
        "v1_3_1_control": _v13_1_control_summary(effective),
        "effective_asset": effective,
    }
