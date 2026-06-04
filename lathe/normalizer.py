"""AST normalizer: apply canonical defaults to the raw parser output.

Runs between ``parser`` and ``resolver`` and is responsible for
injecting the field-level defaults declared in ``lathe.defaults``
so later stages can assume a fully-populated shape.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .defaults import (
    ASSET_DEFAULTS,
    ASSET_REPAIR_POLICY_DEFAULTS,
    ASSET_SOURCE_SURFACE_DEFAULTS,
    ASSET_SPACE_DEFAULTS,
    ASSET_VALIDATE_DEFAULTS,
    CONTRACT_DEFAULTS,
    MAPPING_DECL_DEFAULTS,
    PROFILE_DEFAULTS,
    PROGRAM_DEFAULTS,
    SCENE_DEFAULTS,
    SPACE_DEFAULTS,
    STRUCTURED_DECL_DEFAULTS,
    TEST_DECL_DEFAULTS,
    TOP_LEVEL_REPAIR_POLICY_DEFAULTS,
    VALIDATE_REPAIR_DEFAULTS,
    VARIANT_DEFAULTS,
)
from .errors import NormalizationError
from .style_presets import resolve_style_target

# re-export — authoritative definition lives in lathe/errors.py
from .utils import dedupe_keep_first, deep_fill_missing

CANONICAL_PROFILE_KEYS = ["node_type", "name", "uses", "defaults", "rules", "repair"]
CANONICAL_CRITIC_KEYS = ["node_type", "name", "param", "body"]
CANONICAL_STRUCTURED_DECL_KEYS = [
    "node_type",
    "name",
    "kind",
    "uses",
    "defaults",
    "params",
    "geometry",
    "features",
    "surface",
    "assembly",
    "space",
    "repair_policy",
    "rules",
    "values",
]
CANONICAL_MAPPING_DECL_KEYS = ["node_type", "name", "uses", "values"]
CANONICAL_SPACE_KEYS = ["node_type", "name", "use", "values", "vary", "freeze", "objectives", "select"]
CANONICAL_SCENE_KEYS = [
    "node_type",
    "name",
    "version",
    "brief",
    "prompt",
    "values",
    "styles",
    "regions",
    "groups",
    "placement_zones",
    "modules",
    "kits",
    "variant_families",
    "generators",
    "biomes",
    "scatters",
    "environments",
    "objects",
    "arrays",
    "sockets",
    "attachments",
    "relationships",
    "cameras",
    "lights",
    "curiosity_anchors",
    "hidden_state",
    "exports",
    "wfc",
]
CANONICAL_SCENE_CHILD_KEYS = ["node_type", "name", "type", "role", "framing", "target", "from", "values"]
CANONICAL_REPAIR_POLICY_KEYS = ["node_type", "name", "mode", "max_rounds", "allow", "deny"]
CANONICAL_TEST_KEYS = ["node_type", "name", "values", "asserts"]
CANONICAL_ASSET_KEYS = [
    "node_type",
    "name",
    "kind",
    "from",
    "uses",
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
    "space",
    "repair_policy",
    "build",
    "validate",
    "package",
    "publish",
    "experimental",
]
CANONICAL_VARIANT_KEYS = ["node_type", "name", "on", "patches"]


def _ordered(mapping: dict[str, Any], keys: list[str]) -> dict[str, Any]:
    ordered = {key: mapping[key] for key in keys if key in mapping}
    for key, value in mapping.items():
        if key not in ordered:
            ordered[key] = value
    return ordered


def _normalize_rule(rule: dict[str, Any]) -> dict[str, Any]:
    if "kind" not in rule or "expr" not in rule:
        raise NormalizationError(
            f"rule node is missing required fields ('kind'/'expr'): {rule!r}"
        )
    out = {"kind": rule["kind"], "expr": deepcopy(rule["expr"])}
    if "weight" in rule:
        out["weight"] = rule["weight"]
    out["node_type"] = "rule"
    return out


def _normalize_rules(rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [_normalize_rule(rule) for rule in rules]


def _normalize_validate_repair(repair: dict[str, Any]) -> dict[str, Any]:
    repair = deep_fill_missing(repair or {}, VALIDATE_REPAIR_DEFAULTS)
    if "forbid" in repair and not repair.get("deny"):
        repair["deny"] = repair.pop("forbid")
    for key in ("allow", "deny"):
        repair[key] = dedupe_keep_first(repair.get(key, []))
    return repair


def _normalize_repair_policy_spec(spec: dict[str, Any]) -> dict[str, Any]:
    out = deep_fill_missing(spec or {}, ASSET_REPAIR_POLICY_DEFAULTS)
    if "forbid" in out and not out.get("deny"):
        out["deny"] = out.pop("forbid")
    out["allow"] = dedupe_keep_first(out.get("allow", []))
    out["deny"] = dedupe_keep_first(out.get("deny", []))
    return out


def _normalize_top_level_repair_policy(decl: dict[str, Any]) -> dict[str, Any]:
    values = deep_fill_missing(decl.get("values", {}), TOP_LEVEL_REPAIR_POLICY_DEFAULTS)
    if "forbid" in values and not values.get("deny"):
        values["deny"] = values.pop("forbid")
    values["allow"] = dedupe_keep_first(values.get("allow", []))
    values["deny"] = dedupe_keep_first(values.get("deny", []))
    out = {
        "node_type": "repair_policy",
        "name": decl["name"],
        "mode": values.get("mode"),
        "max_rounds": values.get("max_rounds"),
        "allow": values.get("allow", []),
        "deny": values.get("deny", []),
    }
    return _ordered(out, CANONICAL_REPAIR_POLICY_KEYS)


def _normalize_space_common(space: dict[str, Any], *, with_name: bool) -> dict[str, Any]:
    out = deep_fill_missing(space or {}, SPACE_DEFAULTS)
    out.pop("node_type", None)
    if "values" not in out:
        out["values"] = {}
    out["use"] = str(out["values"].pop("use", out.get("use", "")) or "")
    out["freeze"] = dedupe_keep_first(out.get("freeze", []))
    vary: list[dict[str, Any]] = []
    for item in out.get("vary", []):
        if not isinstance(item, dict):
            continue
        if "path" not in item or "domain" not in item:
            raise NormalizationError(
                f"space.vary entry missing required fields ('path'/'domain'): {item!r}"
            )
        vary.append({"path": item["path"], "domain": deepcopy(item["domain"])})
    objectives: list[dict[str, Any]] = []
    for item in out.get("objectives", []):
        if not isinstance(item, dict):
            continue
        if "direction" not in item or "metric" not in item:
            raise NormalizationError(
                f"space.objectives entry missing required fields "
                f"('direction'/'metric'): {item!r}"
            )
        objective = {"direction": item["direction"], "metric": deepcopy(item["metric"])}
        if "weight" in item:
            objective["weight"] = float(item["weight"])
        objectives.append(objective)
    out["vary"] = vary
    out["objectives"] = objectives
    out["select"] = deepcopy(out.get("select", {}))
    keys = CANONICAL_SPACE_KEYS if with_name else ["use", "values", "vary", "freeze", "objectives", "select"]
    return _ordered(out, keys)


def _normalize_space_decl(decl: dict[str, Any]) -> dict[str, Any]:
    out = _normalize_space_common(decl, with_name=True)
    out["node_type"] = "space"
    out["name"] = decl["name"]
    return _ordered(out, CANONICAL_SPACE_KEYS)


def _normalize_assert(assertion: dict[str, Any]) -> dict[str, Any]:
    if "expr" not in assertion:
        raise NormalizationError(f"assert node is missing required 'expr' field: {assertion!r}")
    return {"node_type": "assert", "expr": deepcopy(assertion["expr"])}


def _normalize_test_like(decl: dict[str, Any], node_type: str) -> dict[str, Any]:
    out = deep_fill_missing(decl, TEST_DECL_DEFAULTS)
    out["node_type"] = node_type
    out["asserts"] = [_normalize_assert(item) for item in out.get("asserts", [])]
    return _ordered(out, CANONICAL_TEST_KEYS)


def _normalize_mapping_decl(decl: dict[str, Any], node_type: str) -> dict[str, Any]:
    out = deep_fill_missing(decl, MAPPING_DECL_DEFAULTS)
    out["node_type"] = node_type
    out["uses"] = dedupe_keep_first(out.get("uses", []))
    if node_type in {"kit", "library"} and _has_hda_fields(decl):
        _normalize_hda_fields(out, decl)
        return _ordered(out, [*CANONICAL_MAPPING_DECL_KEYS, "version", "ports", "parameters", "body"])
    return _ordered(out, CANONICAL_MAPPING_DECL_KEYS)


HDA_PORT_TYPES = {
    "polygon_2d",
    "polygon_3d",
    "face_ref",
    "vertex_ref",
    "edge_ref",
    "socket",
    "mesh",
    "points",
    "volume",
    "heightfield",
    "spline",
    "sdf",
    "image",
    "shape_primitive_set",
    "material_ref",
    "number",
    "int",
    "boolean",
    "string",
    "enum",
    "vec2",
    "vec3",
    "vec4",
    "color",
}

HDA_PARAMETER_TYPES = {
    "number",
    "int",
    "boolean",
    "string",
    "enum",
    "vec2",
    "vec3",
    "vec4",
    "color",
}


def _has_hda_fields(decl: dict[str, Any]) -> bool:
    """Return True when the decl carries HDA-class fields from the parser."""
    return any(key in decl for key in ("version", "ports", "parameters", "body"))


def _normalize_port(port: dict[str, Any]) -> dict[str, Any]:
    return {
        "node_type": "port_decl",
        "direction": str(port.get("direction", "in")),
        "name": str(port.get("name", "")),
        "port_type": str(port.get("port_type", "")),
        "options": deepcopy(port.get("options", {})) or {},
    }


def _normalize_parameter(parameter: dict[str, Any]) -> dict[str, Any]:
    return {
        "node_type": "parameter_decl",
        "name": str(parameter.get("name", "")),
        "param_type": str(parameter.get("param_type", "")),
        "options": deepcopy(parameter.get("options", {})) or {},
    }


def _normalize_kit_use(use: dict[str, Any]) -> dict[str, Any]:
    return {
        "node_type": "kit_use_stmt",
        "kit": str(use.get("kit", "")),
        "version_constraint": str(use.get("version_constraint", "")),
        "bindings": deepcopy(use.get("bindings", {})) or {},
    }


def _normalize_body(body: dict[str, Any] | None) -> dict[str, Any]:
    body = body or {}
    return {
        "node_type": "body",
        "kit_uses": [_normalize_kit_use(u) for u in body.get("kit_uses", []) if isinstance(u, dict)],
        "rules": _normalize_rules(body.get("rules", [])),
        "values": deepcopy(body.get("values", {})) or {},
    }


def _normalize_hda_fields(out: dict[str, Any], decl: dict[str, Any]) -> None:
    out["version"] = str(decl.get("version", "") or "")
    out["ports"] = [_normalize_port(p) for p in decl.get("ports", []) if isinstance(p, dict)]
    out["parameters"] = [
        _normalize_parameter(p) for p in decl.get("parameters", []) if isinstance(p, dict)
    ]
    out["body"] = _normalize_body(decl.get("body"))


def _normalize_structured_decl(decl: dict[str, Any], node_type: str) -> dict[str, Any]:
    out = deep_fill_missing(decl, STRUCTURED_DECL_DEFAULTS)
    out["node_type"] = node_type
    out["uses"] = dedupe_keep_first(out.get("uses", []))
    out["rules"] = _normalize_rules(out.get("rules", []))
    out["space"] = _normalize_space_common(out.get("space", {}), with_name=False)
    out["repair_policy"] = _normalize_repair_policy_spec(out.get("repair_policy", {}))
    if "allow" in out["features"]:
        out["features"]["allow"] = dedupe_keep_first(out["features"]["allow"])
    if "components" in out["assembly"]:
        out["assembly"]["components"] = dedupe_keep_first(out["assembly"]["components"])
    if "mechanisms" in out["assembly"]:
        out["assembly"]["mechanisms"] = dedupe_keep_first(out["assembly"]["mechanisms"])
    if "traits" in out["assembly"]:
        out["assembly"]["traits"] = dedupe_keep_first(out["assembly"]["traits"])
    if "material_zones" in out["surface"]:
        out["surface"]["material_zones"] = dedupe_keep_first(out["surface"]["material_zones"])
    if "materials" in out["surface"]:
        out["surface"]["materials"] = dedupe_keep_first(out["surface"]["materials"])
    if "decals" in out["surface"]:
        out["surface"]["decals"] = dedupe_keep_first(out["surface"]["decals"])
    if "bake" in out["surface"]:
        out["surface"]["bake"] = dedupe_keep_first(out["surface"]["bake"])
    if "patterns" in out["surface"]:
        out["surface"]["patterns"] = dedupe_keep_first(out["surface"]["patterns"])
    if node_type == "mechanism" and _has_hda_fields(decl):
        _normalize_hda_fields(out, decl)
        return _ordered(
            out,
            [*CANONICAL_STRUCTURED_DECL_KEYS, "version", "ports", "parameters", "body"],
        )
    return _ordered(out, CANONICAL_STRUCTURED_DECL_KEYS)


def _normalize_profile_like(decl: dict[str, Any], node_type: str) -> dict[str, Any]:
    defaults = PROFILE_DEFAULTS if node_type == "profile" else CONTRACT_DEFAULTS
    out = deep_fill_missing(decl, defaults)
    out["node_type"] = node_type
    out["uses"] = dedupe_keep_first(out.get("uses", []))
    out["rules"] = _normalize_rules(out.get("rules", []))
    out["repair"] = _normalize_validate_repair(out.get("repair", {}))
    return _ordered(out, CANONICAL_PROFILE_KEYS)


def _normalize_experimental(experimental: Any) -> dict[str, Any]:
    """Normalize the Phase 13 experimental block.

    Defaults to an empty dict when the asset omits ``experimental``. Keeps
    only the three MVP sub-blocks (``art_direction``, ``references``,
    ``kit``) the user wrote — sub-blocks are NOT defaulted. Unknown
    sub-blocks captured by the parser as ``_unknown_subblocks`` are
    forwarded so the checker can surface ``L7100`` diagnostics.
    """
    if not isinstance(experimental, dict):
        return {}
    out: dict[str, Any] = {}
    if "art_direction" in experimental and isinstance(experimental["art_direction"], dict):
        out["art_direction"] = deepcopy(experimental["art_direction"])
    if "references" in experimental and isinstance(experimental["references"], dict):
        out["references"] = deepcopy(experimental["references"])
    if "kit" in experimental and isinstance(experimental["kit"], dict):
        out["kit"] = deepcopy(experimental["kit"])
    if "_unknown_subblocks" in experimental and isinstance(
        experimental["_unknown_subblocks"], list
    ):
        out["_unknown_subblocks"] = list(experimental["_unknown_subblocks"])
    return out


def normalize_asset(asset: dict[str, Any]) -> dict[str, Any]:
    """Normalize asset.

    Args:
        asset: asset argument.

    Returns:
        The result.
    """
    out = deep_fill_missing(asset, ASSET_DEFAULTS)
    out["node_type"] = "asset"
    out["uses"] = dedupe_keep_first(out.get("uses", []))
    out["validate"] = deep_fill_missing(out.get("validate", {}), ASSET_VALIDATE_DEFAULTS)
    out["validate"]["rules"] = _normalize_rules(out["validate"].get("rules", []))
    out["validate"]["repair"] = _normalize_validate_repair(out["validate"].get("repair", {}))
    out["surface"] = deep_fill_missing(out.get("surface", {}), ASSET_SOURCE_SURFACE_DEFAULTS)
    out["assembly"] = deep_fill_missing(out.get("assembly", {}), ASSET_DEFAULTS["assembly"])
    out["fit"] = deepcopy(out.get("fit", {}))
    out["transfer"] = deepcopy(out.get("transfer", {}))
    out["reuse"] = deepcopy(out.get("reuse", {}))
    out["constraints"] = deepcopy(out.get("constraints", {}))
    out["ingest"] = deepcopy(out.get("ingest", {}))
    out["assembly_rules"] = deepcopy(out.get("assembly_rules", {}))
    out["execution"] = deepcopy(out.get("execution", {}))
    out["space"] = _normalize_space_common(
        deep_fill_missing(out.get("space", {}), ASSET_SPACE_DEFAULTS), with_name=False
    )
    out["repair_policy"] = _normalize_repair_policy_spec(out.get("repair_policy", {}))
    out["experimental"] = _normalize_experimental(out.get("experimental", {}))

    for path in [
        (out["intent"], "style"),
        (out["intent"], "parts"),
        (out["intent"], "materials"),
        (out["intent"], "negatives"),
        (out["intent"], "interactions"),
        (out["build"]["surface"], "maps"),
        (out["build"]["surface"], "bakes"),
        (out["build"]["rig"], "joints"),
        (out["build"]["interfaces"], "sockets"),
        (out["build"]["interfaces"], "pivots"),
        (out["build"]["interfaces"], "anchors"),
        (out["build"]["interfaces"], "connections"),
        (out["package"], "formats"),
        (out["package"], "previews"),
        (out["publish"], "tags"),
        (out["validate"]["repair"], "allow"),
        (out["validate"]["repair"], "deny"),
        (out["features"], "allow"),
        (out["surface"], "material_zones"),
        (out["surface"], "materials"),
        (out["surface"], "patterns"),
        (out["surface"], "decals"),
        (out["surface"], "bake"),
        (out["surface"], "decal_libraries"),
        (out["surface"], "mask_programs"),
        (out["surface"], "trim_sheets"),
        (out["assembly"], "components"),
        (out["assembly"], "mechanisms"),
        (out["assembly"], "traits"),
        (out["execution"], "library_bindings"),
        (out["repair_policy"], "allow"),
        (out["repair_policy"], "deny"),
    ]:
        container, key = path
        if key in container:
            container[key] = dedupe_keep_first(container[key])

    if not out["package"].get("formats"):
        out["package"]["formats"] = ["usd", "glb"]

    _expand_style_stack(out)

    return _ordered(out, CANONICAL_ASSET_KEYS)


def _expand_style_stack(out: dict[str, Any]) -> None:
    """Expand ``intent.style_target`` into a fully-populated 8-axis stack.

    Roadmap §6.8: authors may write ``style_target = "stylized_pbr_aaa"``
    for the named-preset shorthand, or supply a dict with per-axis
    overrides. Either way the normalizer materializes
    ``intent.style_stack`` with all 8 axes present so per-stage routing
    code can read a single axis without fallback logic.

    Also normalizes ``intent.style_bridges`` (zero or more author-declared
    bridge records) into a list of dicts so the checker has a stable
    shape to consume.
    """
    intent = out.get("intent")
    if not isinstance(intent, dict):
        return
    target = intent.get("style_target")
    intent["style_stack"] = resolve_style_target(target)
    bridges = intent.get("style_bridges")
    if bridges is None:
        intent["style_bridges"] = []
    elif isinstance(bridges, dict):
        intent["style_bridges"] = [bridges]
    elif isinstance(bridges, list):
        normalized: list[dict[str, Any]] = []
        for entry in bridges:
            if isinstance(entry, dict):
                normalized.append(entry)
            elif isinstance(entry, str):
                normalized.append({"name": entry, "bridges": []})
        intent["style_bridges"] = normalized
    else:
        intent["style_bridges"] = []


def _normalize_variant(variant: dict[str, Any]) -> dict[str, Any]:
    out = deep_fill_missing(variant, VARIANT_DEFAULTS)
    out["node_type"] = "variant"
    return _ordered(out, CANONICAL_VARIANT_KEYS)


def _normalize_scene_child(child: dict[str, Any], node_type: str) -> dict[str, Any]:
    out = {
        "node_type": node_type,
        "name": child["name"],
        "type": child.get("type", ""),
        "role": child.get("role", ""),
        "framing": child.get("framing", ""),
        "target": child.get("target", ""),
        "from": child.get("from", ""),
        "values": deepcopy(child.get("values", {})),
    }
    return _ordered(out, CANONICAL_SCENE_CHILD_KEYS)


def _normalize_scene(scene: dict[str, Any]) -> dict[str, Any]:
    out = deep_fill_missing(scene, SCENE_DEFAULTS)
    values = deepcopy(out.get("values", {}))
    out["node_type"] = "scene"
    out["version"] = values.get("version", out.get("version", 1))
    out["brief"] = str(values.get("brief", out.get("brief", "")) or "")
    out["prompt"] = str(values.get("prompt", out.get("prompt", "")) or "")
    out["values"] = values
    out["styles"] = sorted(
        [_normalize_scene_child(item, "scene_style") for item in out.get("styles", [])],
        key=lambda d: d["name"],
    )
    out["regions"] = sorted(
        [_normalize_scene_child(item, "scene_region") for item in out.get("regions", [])],
        key=lambda d: d["name"],
    )
    out["groups"] = sorted(
        [_normalize_scene_child(item, "scene_group") for item in out.get("groups", [])],
        key=lambda d: d["name"],
    )
    out["placement_zones"] = sorted(
        [_normalize_scene_child(item, "scene_placement_zone") for item in out.get("placement_zones", [])],
        key=lambda d: d["name"],
    )
    out["modules"] = sorted(
        [_normalize_scene_child(item, "scene_module") for item in out.get("modules", [])],
        key=lambda d: d["name"],
    )
    out["kits"] = sorted(
        [_normalize_scene_child(item, "scene_kit") for item in out.get("kits", [])],
        key=lambda d: d["name"],
    )
    out["variant_families"] = sorted(
        [_normalize_scene_child(item, "scene_variant_family") for item in out.get("variant_families", [])],
        key=lambda d: d["name"],
    )
    out["generators"] = sorted(
        [_normalize_scene_child(item, "scene_generator") for item in out.get("generators", [])],
        key=lambda d: d["name"],
    )
    out["biomes"] = sorted(
        [_normalize_scene_child(item, "scene_biome") for item in out.get("biomes", [])],
        key=lambda d: d["name"],
    )
    out["scatters"] = sorted(
        [_normalize_scene_child(item, "scene_scatter") for item in out.get("scatters", [])],
        key=lambda d: d["name"],
    )
    out["environments"] = sorted(
        [_normalize_scene_child(item, "scene_environment") for item in out.get("environments", [])],
        key=lambda d: d["name"],
    )
    out["objects"] = sorted(
        [_normalize_scene_child(item, "scene_object") for item in out.get("objects", [])],
        key=lambda d: d["name"],
    )
    out["arrays"] = sorted(
        [_normalize_scene_child(item, "scene_array") for item in out.get("arrays", [])],
        key=lambda d: d["name"],
    )
    out["sockets"] = sorted(
        [_normalize_scene_child(item, "scene_socket") for item in out.get("sockets", [])],
        key=lambda d: d["name"],
    )
    out["attachments"] = sorted(
        [_normalize_scene_child(item, "scene_attachment") for item in out.get("attachments", [])],
        key=lambda d: d["name"],
    )
    out["relationships"] = sorted(
        [_normalize_scene_child(item, "scene_relationship") for item in out.get("relationships", [])],
        key=lambda d: d["name"],
    )
    out["cameras"] = sorted(
        [_normalize_scene_child(item, "scene_camera") for item in out.get("cameras", [])],
        key=lambda d: d["name"],
    )
    out["lights"] = sorted(
        [_normalize_scene_child(item, "scene_light") for item in out.get("lights", [])],
        key=lambda d: d["name"],
    )
    out["curiosity_anchors"] = sorted(
        [_normalize_scene_child(item, "scene_curiosity_anchor") for item in out.get("curiosity_anchors", [])],
        key=lambda d: d["name"],
    )
    out["hidden_state"] = sorted(
        [_normalize_scene_child(item, "scene_hidden_state") for item in out.get("hidden_state", [])],
        key=lambda d: d["name"],
    )
    out["exports"] = sorted(
        [_normalize_scene_child(item, "scene_export") for item in out.get("exports", [])],
        key=lambda d: d["name"],
    )
    out["wfc"] = sorted(
        [_normalize_scene_child(item, "scene_wfc") for item in out.get("wfc", [])],
        key=lambda d: (d.get("name") or ""),
    )
    return _ordered(out, CANONICAL_SCENE_KEYS)


def normalize_program(program: dict[str, Any]) -> dict[str, Any]:
    """Normalize program.

    Args:
        program: program argument.

    Returns:
        The result.
    """
    out = deep_fill_missing(program, PROGRAM_DEFAULTS)
    out["imports"] = dedupe_keep_first(out.get("imports", []))
    out["profiles"] = sorted(
        [_normalize_profile_like(p, "profile") for p in out.get("profiles", [])], key=lambda d: d["name"]
    )
    out["contracts"] = sorted(
        [_normalize_profile_like(c, "contract") for c in out.get("contracts", [])], key=lambda d: d["name"]
    )
    out["critics"] = sorted(
        [_ordered({**c, "node_type": "critic"}, CANONICAL_CRITIC_KEYS) for c in out.get("critics", [])],
        key=lambda d: d["name"],
    )
    out["families"] = sorted(
        [_normalize_structured_decl(item, "family") for item in out.get("families", [])],
        key=lambda d: d["name"],
    )
    out["components"] = sorted(
        [_normalize_structured_decl(item, "component") for item in out.get("components", [])],
        key=lambda d: d["name"],
    )
    out["assemblies"] = sorted(
        [_normalize_structured_decl(item, "assembly") for item in out.get("assemblies", [])],
        key=lambda d: d["name"],
    )
    out["traits"] = sorted(
        [_normalize_structured_decl(item, "trait") for item in out.get("traits", [])], key=lambda d: d["name"]
    )
    out["mechanisms"] = sorted(
        [_normalize_structured_decl(item, "mechanism") for item in out.get("mechanisms", [])],
        key=lambda d: d["name"],
    )
    out["materials"] = sorted(
        [_normalize_mapping_decl(item, "material") for item in out.get("materials", [])],
        key=lambda d: d["name"],
    )
    out["surface_backends"] = sorted(
        [_normalize_mapping_decl(item, "surface_backend") for item in out.get("surface_backends", [])],
        key=lambda d: d["name"],
    )
    out["surface_policies"] = sorted(
        [_normalize_mapping_decl(item, "surface_policy") for item in out.get("surface_policies", [])],
        key=lambda d: d["name"],
    )
    out["decal_libraries"] = sorted(
        [_normalize_mapping_decl(item, "decal_library") for item in out.get("decal_libraries", [])],
        key=lambda d: d["name"],
    )
    out["mask_programs"] = sorted(
        [_normalize_mapping_decl(item, "mask_program") for item in out.get("mask_programs", [])],
        key=lambda d: d["name"],
    )
    out["trim_sheets"] = sorted(
        [_normalize_mapping_decl(item, "trim_sheet") for item in out.get("trim_sheets", [])],
        key=lambda d: d["name"],
    )
    out["palettes"] = sorted(
        [_normalize_mapping_decl(item, "palette") for item in out.get("palettes", [])],
        key=lambda d: d["name"],
    )
    out["style_packs"] = sorted(
        [_normalize_mapping_decl(item, "style_pack") for item in out.get("style_packs", [])],
        key=lambda d: d["name"],
    )
    out["style_bridges"] = sorted(
        [_normalize_mapping_decl(item, "style_bridge") for item in out.get("style_bridges", [])],
        key=lambda d: d["name"],
    )
    out["execution_profiles"] = sorted(
        [_normalize_mapping_decl(item, "execution_profile") for item in out.get("execution_profiles", [])],
        key=lambda d: d["name"],
    )
    out["render_fixtures"] = sorted(
        [_normalize_mapping_decl(item, "render_fixture") for item in out.get("render_fixtures", [])],
        key=lambda d: d["name"],
    )
    out["bake_profiles"] = sorted(
        [_normalize_mapping_decl(item, "bake_profile") for item in out.get("bake_profiles", [])],
        key=lambda d: d["name"],
    )
    out["library_bindings"] = sorted(
        [_normalize_mapping_decl(item, "library_binding") for item in out.get("library_bindings", [])],
        key=lambda d: d["name"],
    )
    out["material_graphs"] = sorted(
        [_normalize_mapping_decl(item, "material_graph") for item in out.get("material_graphs", [])],
        key=lambda d: d["name"],
    )
    out["inspection_policies"] = sorted(
        [_normalize_mapping_decl(item, "inspection_policy") for item in out.get("inspection_policies", [])],
        key=lambda d: d["name"],
    )
    out["asset_class_profiles"] = sorted(
        [
            _normalize_mapping_decl(item, "asset_class_profile")
            for item in out.get("asset_class_profiles", [])
        ],
        key=lambda d: d["name"],
    )
    out["vegetation_species"] = sorted(
        [
            _normalize_mapping_decl(item, "vegetation_species")
            for item in out.get("vegetation_species", [])
        ],
        key=lambda d: d["name"],
    )
    out["vegetation_kits"] = sorted(
        [
            _normalize_mapping_decl(item, "vegetation_kit")
            for item in out.get("vegetation_kits", [])
        ],
        key=lambda d: d["name"],
    )
    out["wind_programs"] = sorted(
        [
            _normalize_mapping_decl(item, "wind_program")
            for item in out.get("wind_programs", [])
        ],
        key=lambda d: d["name"],
    )
    out["volume_programs"] = sorted(
        [
            _normalize_mapping_decl(item, "volume_program")
            for item in out.get("volume_programs", [])
        ],
        key=lambda d: d["name"],
    )
    out["subdivision_finishings"] = sorted(
        [
            _normalize_mapping_decl(item, "subdivision_finishing")
            for item in out.get("subdivision_finishings", [])
        ],
        key=lambda d: d["name"],
    )
    out["terrain_programs"] = sorted(
        [
            _normalize_mapping_decl(item, "terrain_program")
            for item in out.get("terrain_programs", [])
        ],
        key=lambda d: d["name"],
    )
    out["wfc_tilesets"] = sorted(
        [
            _normalize_mapping_decl(item, "wfc_tileset")
            for item in out.get("wfc_tilesets", [])
        ],
        key=lambda d: d["name"],
    )
    out["wfc_adjacencies"] = sorted(
        [
            _normalize_mapping_decl(item, "wfc_adjacency")
            for item in out.get("wfc_adjacencies", [])
        ],
        key=lambda d: d["name"],
    )
    out["f_rep_programs"] = sorted(
        [
            _normalize_mapping_decl(item, "f_rep_program")
            for item in out.get("f_rep_programs", [])
        ],
        key=lambda d: d["name"],
    )
    out["repair_policies"] = sorted(
        [_normalize_top_level_repair_policy(item) for item in out.get("repair_policies", [])],
        key=lambda d: d["name"],
    )
    out["fixtures"] = sorted(
        [_normalize_mapping_decl(item, "fixture") for item in out.get("fixtures", [])],
        key=lambda d: d["name"],
    )
    out["tests"] = sorted(
        [_normalize_test_like(item, "test") for item in out.get("tests", [])], key=lambda d: d["name"]
    )
    out["benchmarks"] = sorted(
        [_normalize_test_like(item, "benchmark") for item in out.get("benchmarks", [])],
        key=lambda d: d["name"],
    )
    out["spaces"] = sorted(
        [_normalize_space_decl(item) for item in out.get("spaces", [])], key=lambda d: d["name"]
    )
    out["worlds"] = sorted(
        [{**_normalize_scene(item), "node_type": "world"} for item in out.get("worlds", [])],
        key=lambda d: d["name"],
    )
    out["scenes"] = sorted(
        [_normalize_scene(item) for item in out.get("scenes", [])], key=lambda d: d["name"]
    )
    out["assets"] = sorted([normalize_asset(a) for a in out.get("assets", [])], key=lambda d: d["name"])
    out["variants"] = sorted(
        [_normalize_variant(v) for v in out.get("variants", [])], key=lambda d: d["name"]
    )
    return {
        "module": out.get("module"),
        "imports": out["imports"],
        "profiles": out["profiles"],
        "contracts": out["contracts"],
        "critics": out["critics"],
        "libraries": sorted(
            [_normalize_mapping_decl(item, "library") for item in out.get("libraries", [])],
            key=lambda d: d["name"],
        ),
        "kits": sorted(
            [_normalize_mapping_decl(item, "kit") for item in out.get("kits", [])], key=lambda d: d["name"]
        ),
        "patterns": sorted(
            [_normalize_mapping_decl(item, "pattern") for item in out.get("patterns", [])],
            key=lambda d: d["name"],
        ),
        "families": out["families"],
        "components": out["components"],
        "assemblies": out["assemblies"],
        "traits": out["traits"],
        "mechanisms": out["mechanisms"],
        "materials": out["materials"],
        "surface_programs": sorted(
            [_normalize_mapping_decl(item, "surface_program") for item in out.get("surface_programs", [])],
            key=lambda d: d["name"],
        ),
        "surface_backends": out["surface_backends"],
        "surface_policies": out["surface_policies"],
        "decal_libraries": out["decal_libraries"],
        "mask_programs": out["mask_programs"],
        "trim_sheets": out["trim_sheets"],
        "palettes": out["palettes"],
        "style_packs": out["style_packs"],
        "style_bridges": out["style_bridges"],
        "execution_profiles": out["execution_profiles"],
        "render_fixtures": out["render_fixtures"],
        "bake_profiles": out["bake_profiles"],
        "library_bindings": out["library_bindings"],
        "material_graphs": out["material_graphs"],
        "inspection_policies": out["inspection_policies"],
        "asset_class_profiles": out["asset_class_profiles"],
        "vegetation_species": out["vegetation_species"],
        "vegetation_kits": out["vegetation_kits"],
        "wind_programs": out["wind_programs"],
        "volume_programs": out["volume_programs"],
        "subdivision_finishings": out["subdivision_finishings"],
        "terrain_programs": out["terrain_programs"],
        "wfc_tilesets": out["wfc_tilesets"],
        "wfc_adjacencies": out["wfc_adjacencies"],
        "f_rep_programs": out["f_rep_programs"],
        "reference_sets": sorted(
            [_normalize_mapping_decl(item, "reference_set") for item in out.get("reference_sets", [])],
            key=lambda d: d["name"],
        ),
        "reconstruct_policies": sorted(
            [
                _normalize_mapping_decl(item, "reconstruct_policy")
                for item in out.get("reconstruct_policies", [])
            ],
            key=lambda d: d["name"],
        ),
        "adapt_policies": sorted(
            [_normalize_mapping_decl(item, "adapt_policy") for item in out.get("adapt_policies", [])],
            key=lambda d: d["name"],
        ),
        "assembly_policies": sorted(
            [_normalize_mapping_decl(item, "assembly_policy") for item in out.get("assembly_policies", [])],
            key=lambda d: d["name"],
        ),
        "fit_profiles": sorted(
            [_normalize_mapping_decl(item, "fit_profile") for item in out.get("fit_profiles", [])],
            key=lambda d: d["name"],
        ),
        "transfer_rules": sorted(
            [_normalize_mapping_decl(item, "transfer_rule") for item in out.get("transfer_rules", [])],
            key=lambda d: d["name"],
        ),
        "repair_policies": out["repair_policies"],
        "fixtures": out["fixtures"],
        "tests": out["tests"],
        "benchmarks": out["benchmarks"],
        "spaces": out["spaces"],
        "worlds": out["worlds"],
        "scenes": out["scenes"],
        "assets": out["assets"],
        "variants": out["variants"],
    }
