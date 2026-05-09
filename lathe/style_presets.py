"""Style stack: 8-axis style target, named presets, and refusal table.

Closes roadmap §6.8. Per stylization_atlas §S.6, style is a STACK, not a tag —
authors compose visual identity along eight orthogonal axes. This module is the
single source of truth for axis names, allowed values, named presets, and the
incompatibility refusal table consumed by the checker.

The eight axes:

* ``material_model`` — pbr_realistic | pbr_stylized | npr_cel | npr_painterly | npr_toy
* ``shading_model`` — lambert_ambient | ramp_outline | brushstroke_composite | flat_shaded
* ``texture_authoring`` — procedural_designer | procedural_painted_feel | hand_painted | flat_vertex_color
* ``outline_mode`` — none | inverted_hull | sobel_post | hybrid
* ``lighting_strategy`` — baked_lightmap | dynamic_global_illumination | per_asset_rig | hybrid
* ``detail_layer_compose`` — multi_band_pbr | flat_single_layer | painterly_pass
* ``animation_rate`` — fluid | on_twos | on_threes | variable
* ``construction_grammar`` — free_form | snap_grid | brick_snap | modular_kit

Per-stage dispatch is fanned out via :func:`stage_axis` accessors so each
compiler stage reads only the axis it cares about and ignores the rest.

Default preset is ``stylized_pbr_aaa`` — this matches the conservative
behavior of the existing hero examples and does not break assets that do not
declare ``style_target``.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

STYLE_AXES: tuple[str, ...] = (
    "material_model",
    "shading_model",
    "texture_authoring",
    "outline_mode",
    "lighting_strategy",
    "detail_layer_compose",
    "animation_rate",
    "construction_grammar",
)

# Allowed values per axis. Validation is permissive at the normalizer (we
# accept unknown values and let downstream stages route on them) but the
# checker uses these sets to flag obvious typos.
AXIS_VALUES: dict[str, frozenset[str]] = {
    "material_model": frozenset(
        {"pbr_realistic", "pbr_stylized", "npr_cel", "npr_painterly", "npr_toy"}
    ),
    "shading_model": frozenset(
        {"lambert_ambient", "ramp_outline", "brushstroke_composite", "flat_shaded"}
    ),
    "texture_authoring": frozenset(
        {"procedural_designer", "procedural_painted_feel", "hand_painted", "flat_vertex_color"}
    ),
    "outline_mode": frozenset({"none", "inverted_hull", "sobel_post", "hybrid"}),
    "lighting_strategy": frozenset(
        {"baked_lightmap", "dynamic_global_illumination", "per_asset_rig", "hybrid"}
    ),
    "detail_layer_compose": frozenset(
        {"multi_band_pbr", "flat_single_layer", "painterly_pass"}
    ),
    "animation_rate": frozenset({"fluid", "on_twos", "on_threes", "variable"}),
    "construction_grammar": frozenset(
        {"free_form", "snap_grid", "brick_snap", "modular_kit"}
    ),
}


# Seven built-in presets covering Bands A through G of stylization_atlas.
# ``stylized_pbr_aaa`` is the implicit default for assets that omit
# ``style_target`` so existing examples keep their current routing behavior.
STYLE_PRESETS: dict[str, dict[str, str]] = {
    "lowpoly_chunky": {
        "material_model": "npr_toy",
        "shading_model": "flat_shaded",
        "texture_authoring": "flat_vertex_color",
        "outline_mode": "none",
        "lighting_strategy": "baked_lightmap",
        "detail_layer_compose": "flat_single_layer",
        "animation_rate": "fluid",
        "construction_grammar": "snap_grid",
    },
    "anime_cel": {
        "material_model": "npr_cel",
        "shading_model": "ramp_outline",
        "texture_authoring": "hand_painted",
        "outline_mode": "inverted_hull",
        "lighting_strategy": "per_asset_rig",
        "detail_layer_compose": "multi_band_pbr",
        "animation_rate": "fluid",
        "construction_grammar": "free_form",
    },
    "painterly": {
        "material_model": "npr_painterly",
        "shading_model": "brushstroke_composite",
        "texture_authoring": "hand_painted",
        "outline_mode": "hybrid",
        "lighting_strategy": "dynamic_global_illumination",
        "detail_layer_compose": "painterly_pass",
        "animation_rate": "on_twos",
        "construction_grammar": "free_form",
    },
    "stylized_pbr_aaa": {
        "material_model": "pbr_stylized",
        "shading_model": "lambert_ambient",
        "texture_authoring": "procedural_designer",
        "outline_mode": "none",
        "lighting_strategy": "dynamic_global_illumination",
        "detail_layer_compose": "multi_band_pbr",
        "animation_rate": "fluid",
        "construction_grammar": "free_form",
    },
    "aaa_realistic": {
        "material_model": "pbr_realistic",
        "shading_model": "lambert_ambient",
        "texture_authoring": "procedural_designer",
        "outline_mode": "none",
        "lighting_strategy": "dynamic_global_illumination",
        "detail_layer_compose": "multi_band_pbr",
        "animation_rate": "fluid",
        "construction_grammar": "free_form",
    },
    "toy_handcrafted": {
        "material_model": "npr_toy",
        "shading_model": "lambert_ambient",
        "texture_authoring": "hand_painted",
        "outline_mode": "none",
        "lighting_strategy": "baked_lightmap",
        "detail_layer_compose": "multi_band_pbr",
        "animation_rate": "fluid",
        "construction_grammar": "brick_snap",
    },
    "astro_bot_clean": {
        "material_model": "pbr_stylized",
        "shading_model": "lambert_ambient",
        "texture_authoring": "procedural_designer",
        "outline_mode": "none",
        "lighting_strategy": "dynamic_global_illumination",
        "detail_layer_compose": "multi_band_pbr",
        "animation_rate": "fluid",
        "construction_grammar": "free_form",
    },
}

DEFAULT_PRESET = "stylized_pbr_aaa"


# Refusal table from stylization_atlas §S.4 red flags.
# Entry shape: (axis_a, value_a, axis_b, value_b, severity, code, message)
# severity: "error" rejects unless a matching style_bridge is declared,
# "warn" emits an L-code warning but does not block.
RefusalRule = tuple[str, str, str, str, str, str, str]

REFUSAL_RULES: tuple[RefusalRule, ...] = (
    (
        "material_model", "pbr_realistic",
        "shading_model", "ramp_outline",
        "error", "L6810",
        "PBR materials with cel ramp produces an uncanny plasticky look. "
        "Declare a style_bridge if intentional.",
    ),
    (
        "material_model", "npr_cel",
        "shading_model", "lambert_ambient",
        "error", "L6811",
        "Cel-shaded geometry needs ramp shading; lambert_ambient produces "
        "an underwhelming flat result.",
    ),
    (
        "material_model", "npr_cel",
        "shading_model", "brushstroke_composite",
        "error", "L6812",
        "Cel and brushstroke shading conflict — pick one painterly mode "
        "or declare a style_bridge.",
    ),
    (
        "material_model", "npr_painterly",
        "shading_model", "ramp_outline",
        "error", "L6813",
        "Painterly material expects brushstroke compositing, not crisp cel "
        "ramps. Declare a style_bridge if intentional.",
    ),
    (
        "material_model", "pbr_realistic",
        "texture_authoring", "flat_vertex_color",
        "error", "L6814",
        "PBR-realistic materials require multi-channel textures; flat vertex "
        "color erases roughness/metallic detail.",
    ),
    (
        "material_model", "npr_toy",
        "detail_layer_compose", "painterly_pass",
        "error", "L6815",
        "Toy/lowpoly look conflicts with painterly multi-pass compose. "
        "Declare a style_bridge or pick flat_single_layer.",
    ),
    (
        "shading_model", "flat_shaded",
        "outline_mode", "sobel_post",
        "error", "L6816",
        "Sobel post on flat shading produces noisy outlines because there "
        "is no shading gradient to detect.",
    ),
    (
        "construction_grammar", "modular_kit",
        "texture_authoring", "flat_vertex_color",
        "error", "L6817",
        "Modular kits expect tileable textures across module seams; flat "
        "vertex color cannot match across kit pieces.",
    ),
    (
        "material_model", "pbr_stylized",
        "shading_model", "brushstroke_composite",
        "warn", "L6850",
        "pbr_stylized + brushstroke_composite is unusual but may work; "
        "verify the surface program supports painterly compose.",
    ),
    (
        "material_model", "pbr_realistic",
        "outline_mode", "inverted_hull",
        "warn", "L6851",
        "Inverted-hull outlines on PBR-realistic look stylized — confirm "
        "this is the intended hybrid (e.g. Borderlands style) or declare "
        "a style_bridge.",
    ),
)


def resolve_style_target(target: Any) -> dict[str, str]:
    """Resolve an authored ``style_target`` into a full 8-axis stack.

    Accepts:
      * ``str`` — name of a preset; missing axes filled from preset.
      * ``dict`` — partial axis overrides; ``preset`` key (if present)
        provides the base, otherwise :data:`DEFAULT_PRESET` is used and
        the dict's other keys override it.
      * falsy — returns a copy of the default preset.

    Always returns a fresh dict with all 8 axes present so downstream
    routing code never has to fall back to ``.get``.
    """
    if not target:
        return deepcopy(STYLE_PRESETS[DEFAULT_PRESET])
    if isinstance(target, str):
        preset = STYLE_PRESETS.get(target.strip())
        if preset is None:
            stack = deepcopy(STYLE_PRESETS[DEFAULT_PRESET])
            stack["_unknown_preset"] = target  # type: ignore[assignment]
            return stack
        return deepcopy(preset)
    if isinstance(target, dict):
        preset_name = str(target.get("preset") or DEFAULT_PRESET).strip()
        base_preset = STYLE_PRESETS.get(preset_name, STYLE_PRESETS[DEFAULT_PRESET])
        stack = deepcopy(base_preset)
        for axis in STYLE_AXES:
            if axis in target and target[axis]:
                stack[axis] = str(target[axis])
        return stack
    return deepcopy(STYLE_PRESETS[DEFAULT_PRESET])


def stage_axis(asset: dict[str, Any], axis: str) -> str:
    """Read a single style-stack axis from a materialized asset.

    Used by per-stage compilers to route on one axis without fishing
    through nested dicts. Returns the default-preset value if the asset
    declares no style stack at all.
    """
    intent = asset.get("intent") if isinstance(asset, dict) else None
    if not isinstance(intent, dict):
        return STYLE_PRESETS[DEFAULT_PRESET].get(axis, "")
    stack = intent.get("style_stack")
    if isinstance(stack, dict) and axis in stack:
        return str(stack[axis])
    return STYLE_PRESETS[DEFAULT_PRESET].get(axis, "")


def style_bridges(asset: dict[str, Any]) -> list[dict[str, Any]]:
    """Return any author-declared ``style_bridge`` records on the asset.

    Looks at both ``intent.style_bridges`` (per-asset) and the resolver's
    program-level ``style_bridges`` namespace if attached. Returns a
    list of dicts with at least ``name`` and ``bridges`` keys.
    """
    intent = asset.get("intent") if isinstance(asset, dict) else None
    if not isinstance(intent, dict):
        return []
    bridges = intent.get("style_bridges") or []
    if not isinstance(bridges, list):
        return []
    out: list[dict[str, Any]] = []
    for entry in bridges:
        if isinstance(entry, dict):
            out.append(entry)
        elif isinstance(entry, str):
            out.append({"name": entry, "bridges": []})
    return out


def bridge_covers(
    bridges: list[dict[str, Any]],
    axis_a: str,
    value_a: str,
    axis_b: str,
    value_b: str,
) -> bool:
    """Return True iff a declared ``style_bridge`` sanctions the pair.

    A bridge ``bridges = [foo, bar]`` sanctions the conflicting pair when:

    * Both pair values appear directly in the bridge list, OR
    * Each pair value is reachable from the bridge list — either as a
      direct match, or via a preset whose name appears in the bridge
      and whose axis value matches the pair value.

    The second case lets authors write ``bridges = [pbr_realistic, npr_cel]``
    to sanction the Borderlands hybrid (pbr_realistic material + the
    ramp_outline shading that belongs to the npr_cel preset) without
    having to enumerate every shading/outline value that comes along.
    """
    for bridge in bridges:
        bridged = bridge.get("bridges") or []
        if not isinstance(bridged, list):
            continue
        bridged_str = {str(item).strip() for item in bridged if item}
        if not bridged_str:
            continue
        a_covered = _value_reachable_from_bridge(axis_a, value_a, bridged_str)
        b_covered = _value_reachable_from_bridge(axis_b, value_b, bridged_str)
        if a_covered and b_covered:
            return True
    return False


def _value_reachable_from_bridge(
    axis: str, value: str, bridged_values: set[str]
) -> bool:
    """Return True iff ``value`` on ``axis`` is reachable from the bridge.

    Direct match wins; otherwise, walk every preset whose name appears in
    ``bridged_values`` and check whether that preset's value for ``axis``
    equals ``value``. Also walk every value in ``bridged_values`` that
    happens to be a known material_model token (e.g. ``npr_cel``) and
    check the preset whose default material_model is that token.
    """
    if value in bridged_values:
        return True
    for token in bridged_values:
        preset = STYLE_PRESETS.get(token)
        if preset is not None and preset.get(axis) == value:
            return True
        # token may be a material_model value (pbr_realistic, npr_cel, …)
        # rather than a preset name; map it to the canonical preset that
        # uses it as material_model and pull through that preset's axes.
        for preset_def in STYLE_PRESETS.values():
            if preset_def.get("material_model") == token and preset_def.get(axis) == value:
                return True
    return False


__all__ = [
    "AXIS_VALUES",
    "DEFAULT_PRESET",
    "REFUSAL_RULES",
    "STYLE_AXES",
    "STYLE_PRESETS",
    "bridge_covers",
    "resolve_style_target",
    "stage_axis",
    "style_bridges",
]
