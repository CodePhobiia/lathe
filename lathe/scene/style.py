"""Style pack contracts and helpers for Wonder scene authoring."""

from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

STYLE_PACK_VERSION = "lathe.style_pack.v1"
STYLE_PACK_SCHEMA_FILENAME = "style_pack.schema.json"
STYLE_PACK_CONTRACT = "style_pack"

STYLE_BIBLE_FIELDS = ("mood", "palette", "materials", "forms", "lighting", "avoid")
DEFAULT_REUSE_POLICY: dict[str, Any] = {
    "asset_signature_fields": [
        "source_asset",
        "lathe_asset",
        "source_family",
        "source_kit",
        "variant",
        "material_bindings",
    ],
    "instance_override_fields": [
        "name",
        "role",
        "region",
        "transform",
        "semantic_tags",
        "state",
        "affordances",
        "provenance",
    ],
    "allow_shared_assets": True,
}

BUILTIN_STYLE_PACK_SPECS: dict[str, dict[str, Any]] = {
    "cozy_fantasy_workshop": {
        "display_name": "Cozy Fantasy Workshop",
        "description": "Warm hand-built fantasy interiors with painted wood, soft metals, and practical light.",
        "style_bible": {
            "mood": ["cozy", "handmade", "welcoming"],
            "palette": ["hearth amber", "moss green", "painted cream", "aged brass"],
            "materials": ["painted wood", "aged brass", "soft cloth", "warm plaster"],
            "forms": ["rounded shelves", "chunky joinery", "hand-carved trim"],
            "lighting": ["hearth glow", "warm lanterns"],
            "avoid": ["cold sci fi", "sharp sterile panels"],
        },
        "palette": [
            ("hearth_amber", "hearth amber", "#d98b34", ["primary", "emissive"], ["warm", "lantern"]),
            ("moss_green", "moss green", "#567a4c", ["secondary"], ["paint", "foliage"]),
            ("painted_cream", "painted cream", "#eadbb8", ["primary"], ["plaster", "paint"]),
            ("aged_brass", "aged brass", "#a9793b", ["accent"], ["metal", "hardware"]),
        ],
        "materials": [
            ("mat_painted_wood", "Painted Wood", "architecture", ["painted cream", "moss green"], "#c8a66d", 0.0, 0.62, None, ["wood", "painted"]),
            ("mat_aged_brass", "Aged Brass", "mechanism", ["aged brass"], "#a9793b", 0.8, 0.42, None, ["metal", "warm"]),
            ("mat_warm_plaster", "Warm Plaster", "surface", ["painted cream"], "#eadbb8", 0.0, 0.72, None, ["wall", "soft"]),
        ],
        "lighting": [
            ("lighting_hearth_key", "point", "hearth amber", 1.1, "Warm key light from a hearth or forge.", ["hearth glow"]),
            ("lighting_lantern_fill", "emissive_practical", "aged brass", 0.55, "Small lantern practicals for readable corners.", ["warm lanterns"]),
        ],
    },
    "dark_fantasy_ruin": {
        "display_name": "Dark Fantasy Ruin",
        "description": "Ancient ruined masonry, ritual metals, and cold accent light for ominous fantasy scenes.",
        "style_bible": {
            "mood": ["ancient", "ominous", "weathered"],
            "palette": ["ash stone", "verdigris copper", "blood ember", "cold violet"],
            "materials": ["cracked stone", "oxidized metal", "charred wood", "old bone"],
            "forms": ["broken arches", "ritual circles", "jagged silhouettes"],
            "lighting": ["cold sky", "ember practicals"],
            "avoid": ["clean modern panels", "toy plastic"],
        },
        "palette": [
            ("ash_stone", "ash stone", "#68665f", ["primary"], ["stone", "ruin"]),
            ("verdigris_copper", "verdigris copper", "#4f8f7b", ["secondary"], ["metal", "age"]),
            ("blood_ember", "blood ember", "#9b2f26", ["accent", "emissive"], ["ritual", "fire"]),
            ("cold_violet", "cold violet", "#6b6a9f", ["accent"], ["sky", "magic"]),
        ],
        "materials": [
            ("mat_cracked_stone", "Cracked Stone", "architecture", ["ash stone"], "#68665f", 0.0, 0.88, None, ["stone", "ruined"]),
            ("mat_verdigris_copper", "Verdigris Copper", "mechanism", ["verdigris copper"], "#4f8f7b", 0.65, 0.58, None, ["metal", "oxidized"]),
            ("mat_ember_rune", "Ember Rune", "accent", ["blood ember"], "#9b2f26", 0.0, 0.5, "#9b2f26", ["rune", "emissive"]),
        ],
        "lighting": [
            ("lighting_cold_sky", "directional", "cold violet", 0.75, "Cold sky key for long ruin shadows.", ["cold sky"]),
            ("lighting_ember_practical", "emissive_practical", "blood ember", 0.45, "Low ember practicals near ritual details.", ["ember practicals"]),
        ],
    },
    "dead_god_observatory": {
        "display_name": "Dead God Observatory",
        "description": "Sacred bone architecture, oxidized copper instruments, black glass, and lunar-candle lighting.",
        "style_bible": {
            "mood": ["sacred", "eerie", "antique"],
            "palette": ["bone ivory", "oxidized copper", "black glass", "lunar blue", "candle gold"],
            "materials": ["ribbed bone architecture", "oxidized brass", "black obsidian glass", "dusty enamel"],
            "forms": ["ribbed arches", "circular instruments", "thin spires", "engraved constellations"],
            "lighting": ["cold moonbeam", "warm candle clusters"],
            "avoid": ["modern electronics", "clean sci fi panels"],
        },
        "palette": [
            ("bone_ivory", "bone ivory", "#d8cfb2", ["primary"], ["bone", "architecture"]),
            ("oxidized_copper", "oxidized copper", "#6f7f68", ["secondary"], ["metal", "age"]),
            ("black_glass", "black glass", "#101318", ["secondary"], ["glass", "obsidian"]),
            ("lunar_blue", "lunar blue", "#8fb4d8", ["accent"], ["moonlight", "cold"]),
            ("candle_gold", "candle gold", "#f1b65a", ["emissive", "accent"], ["candle", "warm"]),
        ],
        "materials": [
            ("mat_bone_stone", "Bone Stone", "architecture", ["bone ivory"], "#d8cfb2", 0.0, 0.76, None, ["bone", "ribbed"]),
            ("mat_oxidized_brass", "Oxidized Brass", "mechanism", ["oxidized copper"], "#6f7f68", 0.75, 0.5, None, ["brass", "instrument"]),
            ("mat_black_obsidian_glass", "Black Obsidian Glass", "glass", ["black glass"], "#101318", 0.0, 0.18, None, ["glass", "lens"]),
            ("mat_candle_flame", "Candle Flame", "accent", ["candle gold"], "#f1b65a", 0.0, 0.25, "#f1b65a", ["emissive", "candle"]),
        ],
        "lighting": [
            ("lighting_moonbeam_key", "moonbeam", "lunar blue", 0.8, "Cold moonbeam revealing the hero instrument.", ["cold moonbeam"]),
            ("lighting_candle_fill", "candle_cluster", "candle gold", 0.55, "Warm candle clusters for antique detail readability.", ["warm candle clusters"]),
        ],
    },
    "roblox_horror_lowpoly": {
        "display_name": "Roblox Horror Lowpoly",
        "description": "Mobile-friendly low-poly horror scenes with readable silhouettes and restrained grime.",
        "style_bible": {
            "mood": ["tense", "readable", "lowpoly"],
            "palette": ["fog gray", "sickly green", "warning red", "aged concrete"],
            "materials": ["flat concrete", "painted metal", "lowpoly wood", "subtle grime"],
            "forms": ["chunky silhouettes", "simple bevels", "clear props"],
            "lighting": ["fog fill", "red warning practicals"],
            "avoid": ["photoreal gore", "tiny noisy detail"],
        },
        "palette": [
            ("fog_gray", "fog gray", "#7b827d", ["primary"], ["fog", "neutral"]),
            ("sickly_green", "sickly green", "#8bb35d", ["accent"], ["horror", "light"]),
            ("warning_red", "warning red", "#c74332", ["emissive", "accent"], ["alarm", "danger"]),
            ("aged_concrete", "aged concrete", "#8d877d", ["secondary"], ["wall", "floor"]),
        ],
        "materials": [
            ("mat_lowpoly_concrete", "Lowpoly Concrete", "architecture", ["aged concrete", "fog gray"], "#8d877d", 0.0, 0.8, None, ["roblox", "concrete"]),
            ("mat_warning_emissive", "Warning Emissive", "accent", ["warning red"], "#c74332", 0.0, 0.35, "#c74332", ["roblox", "emissive"]),
            ("mat_painted_metal", "Painted Metal", "mechanism", ["fog gray"], "#7b827d", 0.25, 0.58, None, ["roblox", "metal"]),
        ],
        "lighting": [
            ("lighting_fog_fill", "area", "fog gray", 0.45, "Broad low-contrast fill for readable mobile scenes.", ["fog fill"]),
            ("lighting_warning_red", "emissive_practical", "warning red", 0.7, "Simple red practicals for horror focal points.", ["red warning practicals"]),
        ],
    },
    "roblox_lowpoly_cute": {
        "display_name": "Roblox Lowpoly Cute",
        "description": "Bright simulator-friendly low-poly style with toy materials and mobile-safe contrast.",
        "style_bible": {
            "mood": ["cheerful", "toy like", "readable"],
            "palette": ["sky blue", "grass green", "sunny yellow", "soft pink"],
            "materials": ["smooth plastic", "painted wood", "soft grass", "clean glass"],
            "forms": ["chunky bevels", "rounded corners", "simple icons"],
            "lighting": ["soft daylight", "gentle practicals"],
            "avoid": ["muddy colors", "gritty realism"],
        },
        "palette": [
            ("sky_blue", "sky blue", "#73bdf2", ["primary"], ["bright", "sky"]),
            ("grass_green", "grass green", "#68bd58", ["secondary"], ["nature", "ground"]),
            ("sunny_yellow", "sunny yellow", "#f3cd4e", ["accent"], ["reward", "coin"]),
            ("soft_pink", "soft pink", "#f09ac0", ["accent"], ["cute", "shop"]),
        ],
        "materials": [
            ("mat_smooth_plastic", "Smooth Plastic", "surface", ["sky blue", "sunny yellow"], "#73bdf2", 0.0, 0.42, None, ["roblox", "plastic"]),
            ("mat_soft_grass", "Soft Grass", "terrain", ["grass green"], "#68bd58", 0.0, 0.72, None, ["roblox", "grass"]),
            ("mat_shop_accent", "Shop Accent", "accent", ["soft pink"], "#f09ac0", 0.0, 0.38, None, ["roblox", "cute"]),
        ],
        "lighting": [
            ("lighting_soft_daylight", "directional", "sky blue", 0.85, "Soft daylight for bright simulator spaces.", ["soft daylight"]),
            ("lighting_gentle_practical", "emissive_practical", "sunny yellow", 0.4, "Gentle practical light for reward props.", ["gentle practicals"]),
        ],
    },
    "sci_fi_industrial": {
        "display_name": "Sci Fi Industrial",
        "description": "Functional industrial sci-fi with worn metal, dark panels, and controlled cyan signal light.",
        "style_bible": {
            "mood": ["utilitarian", "worn", "technical"],
            "palette": ["gunmetal", "safety yellow", "signal cyan", "rubber black"],
            "materials": ["brushed metal", "rubber trim", "painted panels", "emissive strips"],
            "forms": ["modular panels", "exposed ribs", "service hatches"],
            "lighting": ["overhead strips", "cyan indicators"],
            "avoid": ["ornate fantasy", "organic bone"],
        },
        "palette": [
            ("gunmetal", "gunmetal", "#454b52", ["primary"], ["metal", "panel"]),
            ("safety_yellow", "safety yellow", "#d0a52b", ["accent"], ["warning", "stripe"]),
            ("signal_cyan", "signal cyan", "#38c8d5", ["emissive", "accent"], ["screen", "indicator"]),
            ("rubber_black", "rubber black", "#15181c", ["secondary"], ["trim", "rubber"]),
        ],
        "materials": [
            ("mat_brushed_gunmetal", "Brushed Gunmetal", "architecture", ["gunmetal"], "#454b52", 0.82, 0.48, None, ["metal", "panel"]),
            ("mat_rubber_black", "Rubber Black", "trim", ["rubber black"], "#15181c", 0.0, 0.68, None, ["rubber", "edge"]),
            ("mat_signal_cyan", "Signal Cyan", "accent", ["signal cyan"], "#38c8d5", 0.0, 0.2, "#38c8d5", ["emissive", "indicator"]),
        ],
        "lighting": [
            ("lighting_overhead_strip", "area", "gunmetal", 0.65, "Functional overhead strip light.", ["overhead strips"]),
            ("lighting_cyan_indicator", "emissive_practical", "signal cyan", 0.5, "Small cyan status indicators.", ["cyan indicators"]),
        ],
    },
}


def _schema_root() -> Path:
    here = Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        candidate = parent / "schema" / STYLE_PACK_SCHEMA_FILENAME
        if candidate.exists():
            return candidate.parent
    raise FileNotFoundError(f"Could not locate schema/{STYLE_PACK_SCHEMA_FILENAME}")


def get_style_pack_schema() -> dict[str, Any]:
    """Return the committed Style Pack JSON Schema."""
    return json.loads((_schema_root() / STYLE_PACK_SCHEMA_FILENAME).read_text(encoding="utf-8"))


def validate_style_pack_payload(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Return schema and semantic diagnostics for a Style Pack payload."""
    diagnostics = _schema_diagnostics(payload)
    diagnostics.extend(_check_material_palette_refs(payload))
    diagnostics.extend(_check_style_pack_fingerprint(payload))
    return diagnostics


def extract_style_pack(
    scene_graph: Mapping[str, Any],
    *,
    style_pack_id: str | None = None,
    display_name: str | None = None,
) -> dict[str, Any]:
    """Build a deterministic Style Pack from a Scene Graph mapping."""
    scene_id = _string_value(scene_graph.get("scene_id")) or "scene"
    style_bible = _style_bible(scene_graph)
    resolved_pack_id = style_pack_id or f"{_slug(scene_id)}_style"
    payload: dict[str, Any] = {
        "schema_version": STYLE_PACK_VERSION,
        "style_pack_id": resolved_pack_id,
        "display_name": display_name or _display_name(resolved_pack_id),
        "source": {
            "kind": "scene_graph",
            "scene_id": scene_id,
            "scene_version": _scene_version(scene_graph),
        },
        "style_bible": style_bible,
        "palette": _palette_tokens(style_bible),
        "materials": _style_materials(scene_graph),
        "lighting": _lighting_presets(scene_graph),
        "form_language": _form_language(style_bible),
        "reuse_policy": copy.deepcopy(DEFAULT_REUSE_POLICY),
        "metadata": {
            "generated_by": "lathe.scene.style",
            "fingerprint": "",
        },
    }
    payload["metadata"]["fingerprint"] = style_pack_fingerprint(payload)
    return payload


def builtin_style_pack_ids() -> tuple[str, ...]:
    """Return sorted identifiers for curated built-in Style Packs."""
    return tuple(sorted(BUILTIN_STYLE_PACK_SPECS))


def get_builtin_style_pack(style_pack_id: str) -> dict[str, Any]:
    """Return a schema-valid curated Style Pack by identifier."""
    spec = BUILTIN_STYLE_PACK_SPECS.get(style_pack_id)
    if spec is None:
        raise KeyError(f"unknown built-in Style Pack: {style_pack_id}")
    payload: dict[str, Any] = {
        "schema_version": STYLE_PACK_VERSION,
        "style_pack_id": style_pack_id,
        "display_name": str(spec["display_name"]),
        "source": {
            "kind": "curated",
            "description": str(spec["description"]),
        },
        "style_bible": _curated_style_bible(spec),
        "palette": _curated_palette(spec),
        "materials": _curated_materials(spec),
        "lighting": _curated_lighting(spec),
        "form_language": _curated_form_language(spec),
        "reuse_policy": copy.deepcopy(DEFAULT_REUSE_POLICY),
        "metadata": {
            "generated_by": "lathe.scene.style.builtin",
            "fingerprint": "",
        },
    }
    payload["metadata"]["fingerprint"] = style_pack_fingerprint(payload)
    return payload


def iter_builtin_style_packs() -> Iterator[dict[str, Any]]:
    """Yield built-in Style Packs in stable identifier order."""
    for style_pack_id in builtin_style_pack_ids():
        yield get_builtin_style_pack(style_pack_id)


def apply_style_pack(scene_graph: Mapping[str, Any], style_pack: Mapping[str, Any]) -> dict[str, Any]:
    """Return a Scene Graph copy with the Style Pack bible and missing materials applied."""
    working = copy.deepcopy(dict(scene_graph))
    style_bible = style_pack.get("style_bible")
    if isinstance(style_bible, Mapping):
        working["style_bible"] = copy.deepcopy(dict(style_bible))

    raw_materials = working.get("materials")
    materials = copy.deepcopy(raw_materials) if isinstance(raw_materials, list) else []
    existing_ids = {
        material.get("material_id")
        for material in materials
        if isinstance(material, Mapping) and isinstance(material.get("material_id"), str)
    }
    for material in _style_pack_materials(style_pack):
        material_id = _string_value(material.get("material_id"))
        if material_id is None or material_id in existing_ids:
            continue
        materials.append(_scene_material(material))
        existing_ids.add(material_id)
    working["materials"] = sorted(
        [material for material in materials if isinstance(material, Mapping)],
        key=lambda item: str(item.get("material_id", "")),
    )
    return working


def validate_scene_style(scene_graph: Mapping[str, Any], style_pack: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Return diagnostics for Style Pack coverage of a Scene Graph."""
    diagnostics = validate_style_pack_payload(style_pack)
    diagnostics.extend(_check_scene_style_terms(scene_graph, style_pack))
    diagnostics.extend(_check_scene_material_bindings(scene_graph, style_pack))
    diagnostics.extend(_check_scene_palette_refs(scene_graph, style_pack))
    return diagnostics


def style_pack_fingerprint(style_pack: Mapping[str, Any]) -> str:
    """Return the deterministic fingerprint string for a Style Pack payload."""
    normalized = _normal_json(style_pack)
    if isinstance(normalized, dict) and isinstance(normalized.get("metadata"), dict):
        normalized["metadata"] = {
            key: value for key, value in normalized["metadata"].items() if key != "fingerprint"
        }
    digest = hashlib.sha256(_canonical_json(normalized).encode("utf-8"), usedforsecurity=False).hexdigest()
    return f"sha256:{digest[:16]}"


def _schema_diagnostics(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    import jsonschema

    validator = jsonschema.Draft202012Validator(get_style_pack_schema())
    diagnostics: list[dict[str, Any]] = []
    for error in sorted(validator.iter_errors(payload), key=lambda item: list(item.absolute_path)):
        diagnostics.append(
            _diagnostic(
                "STYLE_PACK_SCHEMA_VALIDATION",
                "schema_validation",
                _json_pointer(*error.absolute_path),
                error.message,
                phase="style_pack_schema",
            )
        )
    return diagnostics


def _diagnostic(
    code: str,
    name: str,
    path: str,
    message: str,
    *,
    severity: str = "error",
    details: dict[str, Any] | None = None,
    phase: str = "style_pack_semantics",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "code": code,
        "name": name,
        "severity": severity,
        "contract": STYLE_PACK_CONTRACT,
        "phase": phase,
        "path": path,
        "message": message,
    }
    if details:
        payload["details"] = details
    return payload


def _json_pointer(*parts: object) -> str:
    escaped = [str(part).replace("~", "~0").replace("/", "~1") for part in parts]
    return "/" + "/".join(escaped) if escaped else "/"


def _items(payload: Mapping[str, Any], collection: str) -> Iterator[tuple[int, Mapping[str, Any]]]:
    raw = payload.get(collection, [])
    if not isinstance(raw, list):
        return
    for index, item in enumerate(raw):
        if isinstance(item, Mapping):
            yield index, item


def _string_value(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _string_field(item: Mapping[str, Any], field: str) -> str | None:
    return _string_value(item.get(field))


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str) or not item or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def _normal_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _normal_json(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, list):
        return [_normal_json(item) for item in value]
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    return str(value)


def _canonical_json(value: Any) -> str:
    return json.dumps(_normal_json(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _fingerprint(value: Any, *, size: int = 16) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8"), usedforsecurity=False).hexdigest()[:size]


def _slug(value: object, *, max_length: int = 72) -> str:
    raw = str(value).strip().lower().replace("&", " and ")
    slug = "".join(char if "a" <= char <= "z" or "0" <= char <= "9" else "_" for char in raw)
    while "__" in slug:
        slug = slug.replace("__", "_")
    slug = slug.strip("_")
    if not slug:
        slug = "style"
    if not slug[0].isalpha():
        slug = f"style_{slug}"
    if len(slug) < 3:
        slug = f"{slug}_style"
    return slug[:max_length].rstrip("_") or "style"


def _display_name(value: str) -> str:
    return value.replace("_", " ").title()


def _scene_version(scene_graph: Mapping[str, Any]) -> int:
    version = scene_graph.get("version")
    if isinstance(version, int) and not isinstance(version, bool) and version > 0:
        return version
    return 1


def _style_bible(scene_graph: Mapping[str, Any]) -> dict[str, list[str]]:
    raw = scene_graph.get("style_bible")
    source = raw if isinstance(raw, Mapping) else {}
    return {field: _string_list(source.get(field)) for field in STYLE_BIBLE_FIELDS}


def _curated_style_bible(spec: Mapping[str, Any]) -> dict[str, list[str]]:
    raw = spec.get("style_bible")
    source = raw if isinstance(raw, Mapping) else {}
    return {field: _string_list(source.get(field)) for field in STYLE_BIBLE_FIELDS}


def _curated_palette(spec: Mapping[str, Any]) -> list[dict[str, Any]]:
    tokens: list[dict[str, Any]] = []
    palette = spec.get("palette")
    if not isinstance(palette, list):
        return tokens
    for token_id, name, value, roles, tags in palette:
        tokens.append(
            {
                "token_id": str(token_id),
                "name": str(name),
                "value": str(value),
                "roles": _string_list(list(roles)),
                "tags": _string_list(list(tags)),
            }
        )
    return tokens


def _curated_materials(spec: Mapping[str, Any]) -> list[dict[str, Any]]:
    materials: list[dict[str, Any]] = []
    raw_materials = spec.get("materials")
    if not isinstance(raw_materials, list):
        return materials
    for material_id, name, role, palette_refs, basecolor, metallic, roughness, emissive, tags in raw_materials:
        pbr: dict[str, Any] = {
            "basecolor": str(basecolor),
            "metallic": float(metallic),
            "roughness": float(roughness),
        }
        if emissive is not None:
            pbr["emissive"] = str(emissive)
        materials.append(
            {
                "material_id": str(material_id),
                "name": str(name),
                "role": str(role),
                "palette_refs": _string_list(list(palette_refs)),
                "pbr": pbr,
                "tags": _string_list(list(tags)),
            }
        )
    return materials


def _curated_lighting(spec: Mapping[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    raw_lighting = spec.get("lighting")
    if not isinstance(raw_lighting, list):
        return records
    for preset_id, light_type, color, intensity, purpose, style_terms in raw_lighting:
        records.append(
            {
                "preset_id": str(preset_id),
                "light_type": str(light_type),
                "color": str(color),
                "intensity": float(intensity),
                "purpose": str(purpose),
                "style_terms": _string_list(list(style_terms)),
            }
        )
    return records


def _curated_form_language(spec: Mapping[str, Any]) -> list[dict[str, Any]]:
    style_bible = _curated_style_bible(spec)
    return [
        {
            "form_id": _slug(term),
            "term": term,
        }
        for term in _string_list(style_bible.get("forms"))
    ]


def _palette_tokens(style_bible: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "token_id": _slug(term),
            "name": term,
            "roles": [],
            "tags": [term],
        }
        for term in _string_list(style_bible.get("palette"))
    ]


def _style_materials(scene_graph: Mapping[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for _index, material in sorted(_items(scene_graph, "materials"), key=lambda item: _string_field(item[1], "material_id") or ""):
        material_id = _string_field(material, "material_id")
        if material_id is None:
            continue
        records.append(
            {
                "material_id": material_id,
                "name": _string_field(material, "name") or material_id,
                "role": _string_field(material, "role") or "material",
                "palette_refs": _string_list(material.get("palette_refs")),
                "pbr": _normal_json(material.get("pbr", {})),
                "tags": [],
            }
        )
    return records


def _lighting_presets(scene_graph: Mapping[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for _index, light in sorted(_items(scene_graph, "lights"), key=lambda item: _string_field(item[1], "light_id") or ""):
        light_id = _string_field(light, "light_id")
        if light_id is None:
            continue
        records.append(
            {
                "preset_id": _slug(light_id),
                "light_type": _string_field(light, "type") or "point",
                "color": _string_field(light, "color") or "white",
                "intensity": _number_value(light.get("intensity"), default=1.0),
                "purpose": _string_field(light, "purpose") or light_id,
                "style_terms": [],
            }
        )
    return records


def _form_language(style_bible: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "form_id": _slug(term),
            "term": term,
        }
        for term in _string_list(style_bible.get("forms"))
    ]


def _number_value(value: object, *, default: float) -> float:
    if isinstance(value, bool):
        return default
    if isinstance(value, int | float):
        return float(value)
    return default


def _style_pack_materials(style_pack: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    materials = style_pack.get("materials")
    if not isinstance(materials, list):
        return []
    return [material for material in materials if isinstance(material, Mapping)]


def _scene_material(material: Mapping[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "material_id": _string_field(material, "material_id") or "mat_material",
        "name": _string_field(material, "name") or _string_field(material, "material_id") or "Material",
        "role": _string_field(material, "role") or "material",
    }
    palette_refs = _string_list(material.get("palette_refs"))
    if palette_refs:
        payload["palette_refs"] = palette_refs
    pbr = material.get("pbr")
    if isinstance(pbr, Mapping) and pbr:
        payload["pbr"] = _normal_json(pbr)
    return payload


def _palette_terms(style_pack: Mapping[str, Any]) -> set[str]:
    terms: set[str] = set()
    style_bible = style_pack.get("style_bible")
    if isinstance(style_bible, Mapping):
        terms.update(_string_list(style_bible.get("palette")))
    palette = style_pack.get("palette")
    if isinstance(palette, list):
        for token in palette:
            if not isinstance(token, Mapping):
                continue
            token_id = _string_field(token, "token_id")
            name = _string_field(token, "name")
            if token_id is not None:
                terms.add(token_id)
            if name is not None:
                terms.add(name)
    return terms


def _check_material_palette_refs(style_pack: Mapping[str, Any]) -> list[dict[str, Any]]:
    palette_terms = _palette_terms(style_pack)
    diagnostics: list[dict[str, Any]] = []
    for index, material in enumerate(_style_pack_materials(style_pack)):
        material_id = _string_field(material, "material_id")
        for ref_index, ref in enumerate(_string_list(material.get("palette_refs"))):
            if ref in palette_terms:
                continue
            diagnostics.append(
                _diagnostic(
                    "ST2001",
                    "unresolved_style_pack_palette_ref",
                    _json_pointer("materials", index, "palette_refs", ref_index),
                    f"Material palette reference {ref!r} is not declared by the Style Pack palette.",
                    details={"material_id": material_id, "palette_ref": ref},
                )
            )
    return diagnostics


def _check_style_pack_fingerprint(style_pack: Mapping[str, Any]) -> list[dict[str, Any]]:
    metadata = style_pack.get("metadata")
    if not isinstance(metadata, Mapping):
        return []
    actual = _string_field(metadata, "fingerprint")
    if actual is None:
        return []
    expected = style_pack_fingerprint(style_pack)
    if actual == expected:
        return []
    return [
        _diagnostic(
            "ST2002",
            "stale_style_pack_fingerprint",
            "/metadata/fingerprint",
            "Style Pack fingerprint does not match the payload content.",
            details={"expected": expected, "actual": actual},
        )
    ]


def _check_scene_style_terms(scene_graph: Mapping[str, Any], style_pack: Mapping[str, Any]) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    scene_style = _style_bible(scene_graph)
    pack_style = style_pack.get("style_bible")
    pack_source = pack_style if isinstance(pack_style, Mapping) else {}
    for field in STYLE_BIBLE_FIELDS:
        pack_terms = set(_string_list(pack_source.get(field)))
        for term in scene_style[field]:
            if term in pack_terms:
                continue
            diagnostics.append(
                _diagnostic(
                    "ST3001",
                    "scene_style_term_missing_from_pack",
                    _json_pointer("style_bible", field),
                    f"Scene style term {term!r} is not covered by the Style Pack {field} terms.",
                    details={"field": field, "term": term},
                )
            )
    return diagnostics


def _check_scene_material_bindings(scene_graph: Mapping[str, Any], style_pack: Mapping[str, Any]) -> list[dict[str, Any]]:
    scene_material_ids = {
        material_id
        for _index, material in _items(scene_graph, "materials")
        if (material_id := _string_field(material, "material_id")) is not None
    }
    style_material_ids = {
        material_id
        for material in _style_pack_materials(style_pack)
        if (material_id := _string_field(material, "material_id")) is not None
    }
    material_ids = scene_material_ids | style_material_ids
    diagnostics: list[dict[str, Any]] = []
    for object_index, item in _items(scene_graph, "objects"):
        object_id = _string_field(item, "object_id")
        bindings = item.get("material_bindings", [])
        if not isinstance(bindings, list):
            continue
        for binding_index, binding in enumerate(bindings):
            if not isinstance(binding, Mapping):
                continue
            material_id = _string_field(binding, "material")
            if material_id is None or material_id in material_ids:
                continue
            diagnostics.append(
                _diagnostic(
                    "ST3002",
                    "scene_material_binding_missing_from_style",
                    _json_pointer("objects", object_index, "material_bindings", binding_index, "material"),
                    f"Object material binding {material_id!r} is not defined by the scene or Style Pack.",
                    details={"object_id": object_id, "material_id": material_id},
                )
            )
    return diagnostics


def _check_scene_palette_refs(scene_graph: Mapping[str, Any], style_pack: Mapping[str, Any]) -> list[dict[str, Any]]:
    palette_terms = _palette_terms(style_pack)
    diagnostics: list[dict[str, Any]] = []
    for material_index, material in _items(scene_graph, "materials"):
        material_id = _string_field(material, "material_id")
        for ref_index, ref in enumerate(_string_list(material.get("palette_refs"))):
            if ref in palette_terms:
                continue
            diagnostics.append(
                _diagnostic(
                    "ST3003",
                    "scene_palette_ref_missing_from_style",
                    _json_pointer("materials", material_index, "palette_refs", ref_index),
                    f"Scene material palette reference {ref!r} is not declared by the Style Pack palette.",
                    details={"material_id": material_id, "palette_ref": ref},
                )
            )
    return diagnostics


__all__ = [
    "BUILTIN_STYLE_PACK_SPECS",
    "DEFAULT_REUSE_POLICY",
    "STYLE_BIBLE_FIELDS",
    "STYLE_PACK_CONTRACT",
    "STYLE_PACK_SCHEMA_FILENAME",
    "STYLE_PACK_VERSION",
    "apply_style_pack",
    "builtin_style_pack_ids",
    "extract_style_pack",
    "get_builtin_style_pack",
    "get_style_pack_schema",
    "iter_builtin_style_packs",
    "style_pack_fingerprint",
    "validate_scene_style",
    "validate_style_pack_payload",
]
