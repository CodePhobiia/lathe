"""Feature fusion: combine scaffold primitives into search geometry.

Runs the boolean/chamfer/bevel cascade that turns feature-grammar
output into the fused mesh used for conformance fitting.
"""

from __future__ import annotations

from typing import Any

from .fidelity import FidelityProfile
from .shape_ir import ShapePrimitive

# Legacy hero families predate explicit authoring/context routing. They remain
# exact by default for compatibility, but new exact selection below is driven by
# primitive capability and authored semantic operations rather than this set.
_LEGACY_EXACT_FAMILIES: frozenset[str] = frozenset(
    {
        "brassbound_chest",
        "industrial_crate",
        "mechanical_door",
        "console_terminal",
        "service_cabinet",
        "control_pedestal",
        "supply_container",
        "hero_sword",
    }
)
VALID_MESHING_STRATEGIES: frozenset[str] = frozenset({"auto", "exact", "sdf"})
_HIGH_FIDELITY_ASSET_CLASSES: frozenset[str] = frozenset({"hero", "aaa_hero"})
_EXACT_BASIC_PRIMITIVES: frozenset[str] = frozenset({"box", "cylinder", "sphere"})
_BOOLEAN_INTEGRATION_RULES: frozenset[str] = frozenset(
    {
        "boolean",
        "boolean_union",
        "boolean_add",
        "boolean_difference",
        "boolean_subtract",
        "boolean_intersection",
        "boolean_intersect",
        "csg",
        "csg_union",
        "csg_difference",
        "csg_subtract",
        "csg_intersection",
        "csg_intersect",
    }
)
_KERNEL_SEMANTIC_MODIFIER_ATTRS = (
    "v2_subdivision_modifier",
    "v2_remesh_modifier",
    "v2_polybevel_modifier",
    "v2_mark_hard_edge_modifier",
    "v2_inset_modifier",
    "v2_weighted_normals_modifier",
    "v2_hull_modifier",
    "v2_minkowski_modifier",
)
_KERNEL_SEMANTIC_METADATA_CONTAINERS = (
    "shape_ir_v2",
    "shape_ir_v2_baked_source_modifiers",
    "semantic_metadata",
    "source_shape_primitive",
    "source_shape_primitives",
)


_EXACT_NATIVE_PRIMITIVES: frozenset[str] = frozenset(
    {
        "capsule",
        "component_assembly",
        "corner_guard_set",
        "countersunk_hole",
        "countersunk_hole_set",
        "curved_tube",
        "dent_mask_set",
        "edge_chip_set",
        "revolved_profile",
        "extruded_profile",
        "fastener_grid",
        "flange",
        "gear",
        "handle",
        "helical_sweep",
        "hinge",
        "inset_cut",
        "ladder_frame",
        "louver_panel",
        "panel",
        "panel_frame",
        "panel_line_cut",
        "perforated_panel",
        "rail",
        "ribbed_panel",
        "rounded_slot",
        "socket",
        "spring",
        "structural_beam",
        "support_bracket",
        "surface_patch_set",
        "threaded_cylinder",
        "torus",
        "trim_band",
        "truss_frame",
        "tube",
        "vent_slats",
        "weld_seam",
        "subdivision_box",
        "swept_profile",
        "lofted_solid",
        "heightfield",
        "terrain_patch",
        "sdf_mesh",
        "sdf_metaball_cluster",
        "terrain_mesh",
        "kernel_primitive_mesh",
        "instance_mesh",
        "polybevel_mesh",
        "profile_mesh",
        "construction_feature_mesh",
        "edge_control_mesh",
        "hull_mesh",
        "minkowski_mesh",
        "subdivision_mesh",
        "remesh_mesh",
        "deform_mesh",
        "boolean_mesh",
        "component_assembly_mesh",
    }
)


def _dict_metadata(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _has_v2_modifier_metadata(value: Any, *, depth: int = 0) -> bool:
    if isinstance(value, list):
        return depth <= 4 and any(
            _has_v2_modifier_metadata(item, depth=depth + 1)
            for item in value
            if isinstance(item, dict)
        )
    metadata = _dict_metadata(value)
    if not metadata or depth > 4:
        return False
    for key, item in metadata.items():
        text_key = str(key)
        if item in (None, "", (), [], {}):
            continue
        if text_key in _KERNEL_SEMANTIC_MODIFIER_ATTRS:
            return True
        if text_key.startswith("v2_") and text_key.endswith("_modifier"):
            return True
    return any(
        _has_v2_modifier_metadata(metadata.get(container), depth=depth + 1)
        for container in _KERNEL_SEMANTIC_METADATA_CONTAINERS
    )


def _has_direct_v2_modifier_attr(primitive: ShapePrimitive) -> bool:
    return any(
        isinstance(name, str)
        and name.startswith("v2_")
        and name.endswith("_modifier")
        and value not in (None, "", (), [], {})
        for name, value in vars(primitive).items()
    )


def _primitive_has_kernel_semantics(primitive: ShapePrimitive) -> bool:
    if (primitive.blend_mode or "union") in {"subtract", "intersect"}:
        return True
    if primitive.primitive_type in _EXACT_NATIVE_PRIMITIVES:
        return True
    if primitive.boolean_seam_groups or primitive.bevel_seam_groups or primitive.hard_edge_groups:
        return True
    if _has_direct_v2_modifier_attr(primitive):
        return True
    if _has_v2_modifier_metadata(getattr(primitive, "semantic_metadata", None)):
        return True
    if int(getattr(primitive, "subdivision_levels", 0) or 0) > 0:
        return True
    if getattr(primitive, "remesh_target_edge_length_cm", None) is not None:
        return True
    return any(
        getattr(primitive, attr, None) is not None
        for attr in _KERNEL_SEMANTIC_MODIFIER_ATTRS
    )


def _primitive_is_exact_capable(primitive: ShapePrimitive) -> bool:
    if primitive.primitive_type in _EXACT_BASIC_PRIMITIVES:
        return True
    return _primitive_has_kernel_semantics(primitive)


def _shape_authoring_requests_exact(
    primitives: list[ShapePrimitive] | None,
    shape_signature: dict[str, Any] | None,
    shape_assessment: dict[str, Any] | None,
) -> tuple[bool, str]:
    primitive_list = list(primitives or [])
    if any((primitive.blend_mode or "union") in {"subtract", "intersect"} for primitive in primitive_list):
        return True, "boolean_blend_mode"
    if any(_primitive_has_kernel_semantics(primitive) for primitive in primitive_list):
        return True, "kernel_semantic_primitive"

    signature = shape_signature if isinstance(shape_signature, dict) else {}
    assessment = shape_assessment if isinstance(shape_assessment, dict) else {}
    asset_class = str(signature.get("asset_class") or "").strip().lower()
    if (
        asset_class in _HIGH_FIDELITY_ASSET_CLASSES
        and primitive_list
        and all(_primitive_is_exact_capable(primitive) for primitive in primitive_list)
    ):
        return True, "asset_class_high_fidelity_exact"
    if signature.get("mesh_grammar"):
        return True, "mesh_grammar_authoring"
    if signature.get("geometry_detail_controls"):
        return True, "geometry_detail_authoring"
    geometry_authoring = signature.get("geometry_authoring")
    if isinstance(geometry_authoring, dict):
        integration_rules = {
            str(rule)
            for rule in geometry_authoring.get("integration_rules", [])
            if str(rule)
        }
        if integration_rules & _BOOLEAN_INTEGRATION_RULES:
            return True, "geometry_integration_rules"
        if geometry_authoring.get("edge_classes") or geometry_authoring.get("seam_classes"):
            return True, "geometry_edge_or_seam_class_authoring"
    primitive_selector = signature.get("primitive_selector")
    if isinstance(primitive_selector, dict) and int(primitive_selector.get("applied_count", 0) or 0) > 0:
        return True, "primitive_selector_authoring"
    if int(assessment.get("geometry_detail_feature_count", 0) or 0) > 0:
        return True, "geometry_detail_features"
    if int(assessment.get("mesh_grammar_generated_primitive_count", 0) or 0) > 0:
        return True, "mesh_grammar_generated_primitives"
    return False, ""


def _shape_authoring_requests_component_assembly_mode(
    primitives: list[ShapePrimitive] | None,
    shape_signature: dict[str, Any] | None,
) -> bool:
    primitive_list = list(primitives or [])
    if any(primitive.primitive_type == "component_assembly" for primitive in primitive_list):
        return True
    signature = shape_signature if isinstance(shape_signature, dict) else {}
    geometry_authoring = signature.get("geometry_authoring")
    if not isinstance(geometry_authoring, dict):
        return False
    mode = str(geometry_authoring.get("mode") or "").strip().lower()
    if mode in {"component_assembly", "assembly", "modular_assembly"}:
        return True
    integration_rules = {
        str(rule).strip().lower()
        for rule in geometry_authoring.get("integration_rules", [])
        if str(rule).strip()
    }
    return bool(integration_rules & {"component_assembly", "modular_assembly"})


def integration_config_for_family(
    family: str,
    fidelity: FidelityProfile,
    *,
    meshing_strategy: str | None = None,
    primitives: list[ShapePrimitive] | None = None,
    shape_signature: dict[str, Any] | None = None,
    shape_assessment: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Integration config for family.

    Args:
        family: family argument.
        fidelity: fidelity argument.
        meshing_strategy: optional per-asset opt-in declared on the
            family ``geometry`` block. ``"exact"`` forces the
            explicit-mesh boolean path even for non-hero families
            (with a built-in concatenate fallback if booleans fail).
            ``"sdf"`` forces the voxel/marching-cubes path. ``"auto"``
            (or ``None``) preserves legacy hero defaults, then promotes
            authored kernel-ready primitives and semantic operations to
            exact.

    Returns:
        The result.
    """
    strategy = (meshing_strategy or "auto").lower()
    if strategy not in VALID_MESHING_STRATEGIES:
        strategy = "auto"

    legacy_hero = family in _LEGACY_EXACT_FAMILIES
    authoring_exact, authoring_exact_reason = _shape_authoring_requests_exact(
        primitives,
        shape_signature,
        shape_assessment,
    )
    component_assembly_mode = _shape_authoring_requests_component_assembly_mode(
        primitives,
        shape_signature,
    )
    if strategy == "exact":
        use_exact = True
        exact_reason = "meshing_strategy_exact"
    elif strategy == "sdf":
        use_exact = False
        exact_reason = "meshing_strategy_sdf"
    elif component_assembly_mode:
        use_exact = True
        exact_reason = "component_assembly_authoring"
    elif authoring_exact:
        use_exact = True
        exact_reason = authoring_exact_reason
    else:
        use_exact = legacy_hero
        exact_reason = "legacy_exact_family" if legacy_hero else "auto_sdf_default"

    if fidelity.tier == "cinematic":
        pitch = 1.7
        blur_sigma = 0.62
    elif fidelity.tier == "hero":
        pitch = 2.1
        blur_sigma = 0.42
    elif fidelity.tier == "game":
        pitch = 2.35
        blur_sigma = 0.28
    else:
        pitch = 2.6
        blur_sigma = 0.16
    if family == "courier_drone":
        pitch *= 1.05
    if use_exact:
        if component_assembly_mode:
            exact_mode = "component_assembly"
        else:
            exact_mode = "explicit_mesh"
    else:
        exact_mode = "sdf_voxel_fusion"
    return {
        "enabled": use_exact,
        "pitch": round(pitch, 4),
        "blur_sigma": round(blur_sigma, 4),
        # ``hero_family`` retains the V0.1 contract: it identifies the
        # eight legacy families above. New non-hero families opting
        # into exact via ``meshing_strategy`` are not promoted to
        # hero — only their meshing path changes.
        "hero_family": legacy_hero,
        "intent_driven_exact": bool((authoring_exact or component_assembly_mode) and strategy == "auto"),
        "exact_reason": exact_reason,
        "exact_finalize": use_exact,
        "exact_mode": exact_mode,
        "component_assembly_mode": bool(component_assembly_mode and use_exact),
        "meshing_strategy": strategy,
    }


def primitive_rounding(primitive: ShapePrimitive, fidelity: FidelityProfile) -> float:
    """Primitive rounding.

    Args:
        primitive: primitive argument.
        fidelity: fidelity argument.

    Returns:
        The result.
    """
    base = float(getattr(primitive, "rounding", 0.0) or 0.0)
    if base > 0:
        return base
    high_tier = fidelity.tier in {"hero", "cinematic"}
    if primitive.component in {"shell", "body", "lid", "door", "bezel", "frame"}:
        return 0.7 if high_tier else 0.45
    if primitive.component in {"rotor_pod", "hinge", "handle", "clasp_set"}:
        return 0.4 if high_tier else 0.25
    return 0.0


def primitive_blend_mode(primitive: ShapePrimitive) -> str:
    """Primitive blend mode.

    Args:
        primitive: primitive argument.

    Returns:
        The result.
    """
    return getattr(primitive, "blend_mode", "union") or "union"
