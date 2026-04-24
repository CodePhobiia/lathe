"""Canonical per-node defaults used by the normalizer.

Keeps the authoritative list of field defaults in one place so the
normalizer, tests and schema stay in sync.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

PROGRAM_DEFAULTS = {
    "module": None,
    "imports": [],
    "profiles": [],
    "contracts": [],
    "critics": [],
    "libraries": [],
    "kits": [],
    "patterns": [],
    "families": [],
    "components": [],
    "assemblies": [],
    "traits": [],
    "mechanisms": [],
    "materials": [],
    "surface_programs": [],
    "surface_backends": [],
    "surface_policies": [],
    "decal_libraries": [],
    "mask_programs": [],
    "trim_sheets": [],
    "palettes": [],
    "reference_sets": [],
    "reconstruct_policies": [],
    "adapt_policies": [],
    "assembly_policies": [],
    "fit_profiles": [],
    "transfer_rules": [],
    "execution_profiles": [],
    "render_fixtures": [],
    "bake_profiles": [],
    "library_bindings": [],
    "material_graphs": [],
    "inspection_policies": [],
    "repair_policies": [],
    "fixtures": [],
    "tests": [],
    "benchmarks": [],
    "spaces": [],
    "assets": [],
    "variants": [],
}

STRUCTURED_DECL_DEFAULTS = {
    "kind": None,
    "uses": [],
    "defaults": {},
    "params": {},
    "geometry": {},
    "features": {},
    "surface": {},
    "assembly": {},
    "space": {},
    "repair_policy": {},
    "rules": [],
    "values": {},
}

MAPPING_DECL_DEFAULTS = {
    "uses": [],
    "values": {},
}

SPACE_DEFAULTS = {
    "use": "",
    "values": {},
    "vary": [],
    "freeze": [],
    "objectives": [],
    "select": {},
}

TEST_DECL_DEFAULTS = {
    "values": {},
    "asserts": [],
}

TOP_LEVEL_REPAIR_POLICY_DEFAULTS = {
    "mode": "auto_until_pass",
    "max_rounds": 3,
    "allow": [],
    "deny": [],
}

PROFILE_DEFAULTS = {
    "uses": [],
    "defaults": {},
    "rules": [],
    "repair": {},
}

CONTRACT_DEFAULTS = deepcopy(PROFILE_DEFAULTS)

VALIDATE_REPAIR_DEFAULTS = {
    "mode": "auto_until_pass",
    "max_rounds": 3,
    "allow": [],
    "deny": [],
}

ASSET_REFS_DEFAULTS = {
    "images": [],
    "meshes": [],
    "assets": [],
    "materials": [],
    "reference_sets": [],
    "notes": [],
}

ASSET_INTENT_DEFAULTS = {
    "style": [],
    "parts": [],
    "materials": [],
    "negatives": [],
    "interactions": [],
    "notes": [],
}

ASSET_GEOMETRY_DEFAULTS = {}

ASSET_FEATURES_DEFAULTS = {
    "allow": [],
}

ASSET_SOURCE_SURFACE_DEFAULTS = {
    "program": "",
    "material_graph": "",
    "patterns": [],
    "palette": "",
    "material_zones": [],
    "materials": [],
    "decals": [],
    "bake": [],
    "backend": "",
    "policy": "",
    "decal_libraries": [],
    "mask_programs": [],
    "trim_sheets": [],
    "authoring": {},
}

ASSET_ASSEMBLY_DEFAULTS = {
    "family": "",
    "components": [],
    "mechanisms": [],
    "traits": [],
}

ASSET_SPACE_DEFAULTS = deepcopy(SPACE_DEFAULTS)

ASSET_REPAIR_POLICY_DEFAULTS = {
    "use": "",
    "mode": "",
    "max_rounds": None,
    "allow": [],
    "deny": [],
}

ASSET_FIT_DEFAULTS = {}
ASSET_TRANSFER_DEFAULTS = {}
ASSET_REUSE_DEFAULTS = {}
ASSET_CONSTRAINTS_DEFAULTS = {}
ASSET_INGEST_DEFAULTS = {}
ASSET_ASSEMBLY_RULES_DEFAULTS = {}
ASSET_EXECUTION_DEFAULTS = {
    "profile": "",
    "engine": "",
    "mode": "",
    "deterministic": None,
    "preserve_blend": "",
    "geometry_backend": "",
    "uv_backend": "",
    "bake_backend": "",
    "surface_backend": "",
    "render_backend": "",
    "package_backend": "",
    "library_backend": "",
    "library_bindings": [],
    "inspection_policy": "",
}

BUILD_STAGE_DEFAULTS = {
    "shape": {
        "backend": "auto",
        "mode": "generate",
        "candidates": 4,
        "seed": "auto",
        "symmetry": "none",
        "preserve": [],
    },
    "topology": {
        "backend": "auto",
        "retopo": "auto",
        "ngons": "avoid",
        "preserve": [],
    },
    "uv": {
        "backend": "auto",
        "sets": ["base"],
        "unwrap": "auto",
        "tile_mode": "zero_to_one",
        "padding": {"type": "unit", "value": 8, "unit": "px"},
        "pack_rotate": True,
        "udims": [],
    },
    "surface": {
        "backend": "auto",
        "workflow": "pbr_metal_rough",
        "maps": ["basecolor", "normal", "orm"],
        "resolution": {"type": "unit", "value": 2048, "unit": "px"},
        "bakes": [],
        "bake_profile": "",
        "render_fixture": "",
        "decals": [],
        "id_map": False,
    },
    "rig": {
        "backend": "auto",
        "type": "none",
        "joints": [],
        "pivot_policy": "auto",
        "joint_limits": "auto",
    },
    "interfaces": {
        "backend": "auto",
        "sockets": [],
        "anchors": [],
    },
    "physics": {
        "backend": "auto",
        "collision": "none",
        "max_hulls": 10,
        "mass": "auto",
        "center_of_mass": "auto",
    },
    "optimize": {
        "backend": "auto",
        "lods": 1,
        "atlas": False,
        "mesh_compression": False,
        "strip_hidden_faces": False,
        "instance_candidates": False,
    },
}

ASSET_VALIDATE_DEFAULTS = {
    "rules": [],
    "threshold": 0.80,
    "repair": deepcopy(VALIDATE_REPAIR_DEFAULTS),
}

ASSET_PACKAGE_DEFAULTS = {
    "backend": "auto",
    "formats": [],
    "manifest": True,
    "previews": [],
    "embed_textures": False,
    "include_trace": True,
    "naming": "auto",
}

ASSET_PUBLISH_DEFAULTS = {
    "registry": "",
    "version": "auto_patch",
    "tags": [],
    "visibility": "private",
    "approval": "required",
    "channel": "dev",
}

ASSET_DEFAULTS = {
    "from": "",
    "uses": [],
    "refs": deepcopy(ASSET_REFS_DEFAULTS),
    "intent": deepcopy(ASSET_INTENT_DEFAULTS),
    "geometry": deepcopy(ASSET_GEOMETRY_DEFAULTS),
    "features": deepcopy(ASSET_FEATURES_DEFAULTS),
    "surface": deepcopy(ASSET_SOURCE_SURFACE_DEFAULTS),
    "assembly": deepcopy(ASSET_ASSEMBLY_DEFAULTS),
    "fit": deepcopy(ASSET_FIT_DEFAULTS),
    "transfer": deepcopy(ASSET_TRANSFER_DEFAULTS),
    "reuse": deepcopy(ASSET_REUSE_DEFAULTS),
    "constraints": deepcopy(ASSET_CONSTRAINTS_DEFAULTS),
    "ingest": deepcopy(ASSET_INGEST_DEFAULTS),
    "assembly_rules": deepcopy(ASSET_ASSEMBLY_RULES_DEFAULTS),
    "execution": deepcopy(ASSET_EXECUTION_DEFAULTS),
    "space": deepcopy(ASSET_SPACE_DEFAULTS),
    "repair_policy": deepcopy(ASSET_REPAIR_POLICY_DEFAULTS),
    "build": deepcopy(BUILD_STAGE_DEFAULTS),
    "validate": deepcopy(ASSET_VALIDATE_DEFAULTS),
    "package": deepcopy(ASSET_PACKAGE_DEFAULTS),
    "publish": deepcopy(ASSET_PUBLISH_DEFAULTS),
}

VARIANT_DEFAULTS = {
    "patches": [],
}

SET_LIKE_PATHS = {
    "imports",
    "uses",
    "intent.style",
    "intent.parts",
    "intent.materials",
    "intent.negatives",
    "intent.interactions",
    "build.surface.maps",
    "build.surface.bakes",
    "build.rig.joints",
    "build.interfaces.sockets",
    "build.interfaces.anchors",
    "package.formats",
    "package.previews",
    "publish.tags",
    "validate.repair.allow",
    "validate.repair.deny",
    "features.allow",
    "surface.material_zones",
    "surface.materials",
    "surface.patterns",
    "surface.decals",
    "surface.bake",
    "surface.decal_libraries",
    "surface.mask_programs",
    "surface.trim_sheets",
    "assembly.components",
    "assembly.mechanisms",
    "assembly.traits",
    "execution.library_bindings",
    "space.freeze",
    "repair_policy.allow",
    "repair_policy.deny",
}

BUILD_STAGES = [
    "shape",
    "topology",
    "uv",
    "surface",
    "rig",
    "interfaces",
    "physics",
    "optimize",
]


def deep_copy(value: Any) -> Any:
    """Deep copy.

    Args:
        value: value argument.

    Returns:
        The result.
    """
    return deepcopy(value)
