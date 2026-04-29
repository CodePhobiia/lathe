"""Deterministic Dream Brief to Scene Graph lowering."""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from .contracts import WonderContractError, load_and_validate_contract, validate_contract

MAX_ID_BODY = 80

SCALE_LAYOUTS: dict[str, tuple[list[float], str, str, float]] = {
    "single_room": ([12.0, 8.0, 5.5], "interior", "medium", 1.4),
    "small_courtyard": ([18.0, 14.0, 5.0], "exterior", "medium", 1.8),
    "street_corner": ([20.0, 16.0, 7.0], "exterior", "medium", 2.0),
    "multi_room_seed": ([24.0, 18.0, 6.0], "interior", "dense", 1.5),
    "modular_kit": ([16.0, 12.0, 5.0], "debug", "sparse", 1.5),
}

ROLE_SOURCE_FAMILIES: dict[str, str] = {
    "architecture": "environment_architecture",
    "hero_prop": "hero_prop",
    "environment_structure": "environment_structure",
    "dressing_prop": "dressing_prop",
    "light_fixture": "practical_light",
    "navigation": "navigation_marker",
    "interactive": "interactive_mechanism",
    "narrative_clue": "narrative_clue",
}

EXPORT_FORMATS: dict[str, str] = {
    "lathe_source": "lth",
    "scene_graph": "json",
    "scene_package": "lathepkg",
    "blend": "blend",
    "glb": "glb",
    "usd": "usd",
    "fbx": "fbx",
    "roblox_manifest": "json",
    "godot_manifest": "json",
    "unity_manifest": "json",
    "unreal_manifest": "json",
}

DEFERRED_EXPORT_TARGETS = {"lathe_source"}

_SIGNAL_STOPWORDS = frozenset(
    {
        "and",
        "are",
        "for",
        "from",
        "into",
        "main",
        "scene",
        "that",
        "the",
        "this",
        "with",
    }
)

_ROLE_SIGNAL_WORDS = frozenset(
    {
        "architecture",
        "dressing",
        "environment",
        "fixture",
        "hero",
        "interactive",
        "light",
        "navigation",
        "narrative",
        "prop",
        "structure",
    }
)


def _digest(value: str, length: int = 8) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def _slugify(value: object, *, fallback: str = "item") -> str:
    raw = str(value).strip().lower()
    raw = raw.replace("&", " and ")
    slug = re.sub(r"[^a-z0-9]+", "_", raw)
    slug = re.sub(r"_+", "_", slug).strip("_")
    if not slug:
        slug = fallback
    if not slug[0].isalpha():
        slug = f"{fallback}_{slug}"
    if len(slug) < 3:
        slug = f"{slug}_{fallback}"
    return slug


def _limit_slug(slug: str, *, max_body: int = MAX_ID_BODY) -> str:
    if len(slug) <= max_body:
        return slug
    suffix = _digest(slug)
    trim_length = max_body - len(suffix) - 1
    trimmed = slug[:trim_length].rstrip("_")
    if len(trimmed) < 3:
        trimmed = "id"
    return f"{trimmed}_{suffix}"


def _snake_id(value: object, *, fallback: str = "item") -> str:
    return _limit_slug(_slugify(value, fallback=fallback))


def _prefixed_id(prefix: str, value: object, *, suffix: int | None = None) -> str:
    body = _slugify(value, fallback=prefix)
    if suffix is not None:
        body = f"{body}_{suffix:03d}"
    return f"{prefix}_{_limit_slug(body)}"


def _unique_prefixed_id(prefix: str, value: object, used: set[str], *, suffix: int | None = None) -> str:
    candidate = _prefixed_id(prefix, value, suffix=suffix)
    if candidate not in used:
        used.add(candidate)
        return candidate
    base = f"{value}_{suffix or 1}"
    counter = 2
    while True:
        candidate = _prefixed_id(prefix, f"{base}_{counter}")
        if candidate not in used:
            used.add(candidate)
            return candidate
        counter += 1


def _short_tag(value: object) -> str:
    text = re.sub(r"\s+", " ", str(value).strip())
    if len(text) <= 80:
        return text
    return f"{text[:71].rstrip()} {_digest(text)}"


def _unique_tags(values: Iterable[object] | None, *, fallback: object | None = None) -> list[str]:
    tags: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        tag = _short_tag(value)
        if not tag or tag in seen:
            continue
        seen.add(tag)
        tags.append(tag)
    if not tags and fallback is not None:
        tag = _short_tag(fallback)
        if tag:
            tags.append(tag)
    return tags


def _split_text_tags(value: object, *, fallback: str) -> list[str]:
    text = str(value).strip()
    parts = re.split(r"[.;,]+|\band\b|\bwhile\b|\bwith\b", text)
    return _unique_tags(parts, fallback=fallback)


def _title_from_id(value: str) -> str:
    return value.replace("_", " ").title()


def _safe_mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _safe_list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _brief_prompt(brief: Mapping[str, Any]) -> str:
    for field in ("source_prompt", "one_sentence", "title", "brief_id"):
        value = brief.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "Untitled Wonder scene."


def _style_bible(brief: Mapping[str, Any]) -> dict[str, Any]:
    style = _safe_mapping(brief.get("style"))
    intent = _safe_mapping(brief.get("intent"))
    avoid = [*_safe_list(style.get("avoid_styles")), *_safe_list(brief.get("avoid"))]
    return {
        "mood": _unique_tags(_safe_list(brief.get("mood")), fallback=intent.get("emotional_goal", "neutral")),
        "palette": _unique_tags(_safe_list(style.get("palette")), fallback="neutral palette"),
        "materials": _unique_tags(_safe_list(style.get("materials")), fallback="painted surface"),
        "forms": _unique_tags(_safe_list(style.get("form_language")), fallback="simple forms"),
        "lighting": _split_text_tags(style.get("lighting", ""), fallback="ambient light"),
        "avoid": _unique_tags(avoid),
    }


def _layout(scale: str, region_id: str, focal_object_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    room_size, region_type, density, path_width = SCALE_LAYOUTS.get(scale, SCALE_LAYOUTS["single_room"])
    room_z = room_size[2]
    layout = {
        "room_size": room_size,
        "main_path": {
            "from": region_id,
            "to": focal_object_id,
            "width": path_width,
        },
        "focal_point": focal_object_id,
        "density": density,
        "avoid_intersections": True,
    }
    bounds = {
        "center": [0.0, 0.0, round(room_z / 2.0, 3)],
        "size": room_size,
    }
    region = {
        "region_id": region_id,
        "type": region_type,
        "bounds": bounds,
    }
    return layout, region


def _region(brief: Mapping[str, Any], region_seed: dict[str, Any]) -> dict[str, Any]:
    intent = _safe_mapping(brief.get("intent"))
    mood = _unique_tags(_safe_list(brief.get("mood")), fallback=intent.get("emotional_goal", "neutral"))
    semantic_tags = _unique_tags(
        [
            brief.get("scale", "single_room"),
            *_safe_list(brief.get("genre")),
            *_safe_list(brief.get("mood")),
        ],
        fallback="wonder scene",
    )
    return {
        "region_id": region_seed["region_id"],
        "name": str(brief.get("title") or _title_from_id(str(brief.get("brief_id", "scene")))),
        "type": region_seed["type"],
        "purpose": str(intent.get("setting") or brief.get("one_sentence") or "Primary Wonder scene region."),
        "mood": " and ".join(mood[:3]),
        "bounds": region_seed["bounds"],
        "semantic_tags": semantic_tags,
    }


def _choose_focal_index(elements: list[Mapping[str, Any]]) -> int:
    role_order = ("hero_prop", "interactive", "narrative_clue", "architecture")
    for role in role_order:
        for index, element in enumerate(elements):
            if element.get("role") == role and element.get("priority") == "must":
                return index
    for index, element in enumerate(elements):
        if element.get("priority") == "must":
            return index
    return 0


def _position_for_object(
    *,
    rank: int,
    count: int,
    role: str,
    room_size: list[float],
    is_focal: bool,
) -> tuple[list[float], list[float], list[float]]:
    if is_focal:
        return [0.0, 0.0, 0.75], [0.0, 0.0, 0.0], [1.2, 1.2, 1.0]

    radius_x = max(room_size[0] * 0.32, 1.0)
    radius_y = max(room_size[1] * 0.32, 1.0)
    angle = -math.pi / 2.0 + (2.0 * math.pi * rank / max(count, 1))
    z_by_role = {
        "architecture": room_size[2] * 0.45,
        "environment_structure": room_size[2] * 0.35,
        "light_fixture": room_size[2] * 0.62,
        "navigation": 0.05,
    }
    scale_by_role = {
        "architecture": [1.4, 1.4, 1.2],
        "environment_structure": [1.2, 1.2, 1.0],
        "dressing_prop": [0.75, 0.75, 0.75],
        "light_fixture": [0.8, 0.8, 0.8],
        "navigation": [0.7, 0.7, 0.7],
        "interactive": [1.0, 1.0, 1.0],
        "narrative_clue": [0.8, 0.8, 0.8],
    }
    return (
        [round(math.cos(angle) * radius_x, 3), round(math.sin(angle) * radius_y, 3), round(z_by_role.get(role, 0.75), 3)],
        [0.0, 0.0, round(math.degrees(angle), 3)],
        scale_by_role.get(role, [1.0, 1.0, 1.0]),
    )


def _hex_from_text(value: str) -> str:
    return f"#{_digest(value, 6)}"


def _materials(brief: Mapping[str, Any]) -> list[dict[str, Any]]:
    style = _safe_mapping(brief.get("style"))
    palette = _unique_tags(_safe_list(style.get("palette")))
    material_tags = _unique_tags(_safe_list(style.get("materials")))
    seeds = palette or material_tags or ["neutral material"]
    used_ids: set[str] = set()
    materials: list[dict[str, Any]] = []
    for index, seed in enumerate(seeds, start=1):
        role_seed = material_tags[(index - 1) % len(material_tags)] if material_tags else "surface"
        material_id = _unique_prefixed_id("mat", seed, used_ids, suffix=index)
        materials.append(
            {
                "material_id": material_id,
                "name": _title_from_id(_slugify(seed, fallback="material")),
                "role": _snake_id(role_seed, fallback="surface"),
                "palette_refs": [seed],
                "pbr": {
                    "basecolor": _hex_from_text(seed),
                    "metallic": 0.0,
                    "roughness": 0.65,
                },
            }
        )
    return materials


def _action_from_intent(brief: Mapping[str, Any]) -> str:
    intent = _safe_mapping(brief.get("intent"))
    action = str(intent.get("primary_interaction") or "inspect").strip()
    return action or "inspect"


def _curiosity_and_hidden(
    brief: Mapping[str, Any],
    *,
    focal_object_id: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    goals = _unique_tags(_safe_list(brief.get("curiosity_goals")))
    action = _short_tag(_action_from_intent(brief))
    used_curiosity_ids: set[str] = set()
    used_hidden_ids: set[str] = set()
    anchors: list[dict[str, Any]] = []
    hidden_state: list[dict[str, Any]] = []
    for index, goal in enumerate(goals, start=1):
        anchor_id = _unique_prefixed_id("curiosity", goal, used_curiosity_ids, suffix=index)
        hidden_id = _unique_prefixed_id("hidden", goal, used_hidden_ids, suffix=index)
        expansion_id = _snake_id(f"expand_{goal}", fallback="expansion")
        anchors.append(
            {
                "anchor_id": anchor_id,
                "visible_clue": f"A scene detail invites investigation: {goal}",
                "hidden_fact": f"Unresolved Wonder question: {goal}",
                "attached_to": focal_object_id,
                "suggested_user_actions": _unique_tags([action], fallback="inspect"),
                "expansion_options": [
                    {
                        "id": expansion_id,
                        "label": f"Expand on {goal}",
                        "target_scope": focal_object_id,
                        "required_assets": [_snake_id(focal_object_id.removeprefix("obj_"), fallback="asset")],
                        "continuity_constraints": _unique_tags(
                            [
                                f"preserve {focal_object_id}",
                                "preserve primary layout",
                            ]
                        ),
                    }
                ],
            }
        )
        hidden_state.append(
            {
                "hidden_id": hidden_id,
                "attached_to": focal_object_id,
                "fact": f"Unresolved Wonder question: {goal}",
                "reveal_condition": action,
                "visible": False,
            }
        )
    return anchors, hidden_state


def _objects(
    brief: Mapping[str, Any],
    *,
    elements: list[Mapping[str, Any]],
    object_ids: list[str],
    focal_index: int,
    region_id: str,
    materials: list[dict[str, Any]],
    hidden_state: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    room_size = SCALE_LAYOUTS.get(str(brief.get("scale")), SCALE_LAYOUTS["single_room"])[0]
    non_focal_count = max(len(elements) - 1, 1)
    action = _action_from_intent(brief)
    material_id = materials[0]["material_id"] if materials else None
    objects: list[dict[str, Any]] = []
    non_focal_rank = 0
    for index, element in enumerate(elements):
        element_id = str(element["id"])
        role = str(element["role"])
        is_focal = index == focal_index
        if is_focal:
            rank = 0
        else:
            rank = non_focal_rank
            non_focal_rank += 1
        position, rotation, scale = _position_for_object(
            rank=rank,
            count=non_focal_count,
            role=role,
            room_size=room_size,
            is_focal=is_focal,
        )
        affordances: list[dict[str, Any]] = []
        if is_focal and hidden_state:
            affordances.append(
                {
                    "id": _snake_id(f"inspect_{element_id}", fallback="affordance"),
                    "action": action,
                    "reveals": hidden_state[0]["hidden_id"],
                }
            )
        elif role == "interactive":
            affordances.append(
                {
                    "id": _snake_id(f"use_{element_id}", fallback="affordance"),
                    "action": action,
                }
            )

        scene_object: dict[str, Any] = {
            "object_id": object_ids[index],
            "name": _title_from_id(element_id),
            "role": role,
            "region": region_id,
            "lathe_asset": _snake_id(element_id, fallback="asset"),
            "source_family": ROLE_SOURCE_FAMILIES.get(role, "scene_object"),
            "transform": {
                "position": position,
                "rotation": rotation,
                "scale": scale,
            },
            "semantic_tags": _unique_tags([role, element.get("priority"), element_id]),
            "state": {
                "description": str(element.get("description", "")),
                "priority": str(element.get("priority", "should")),
                "lowered_from": "dream_brief",
            },
            "affordances": affordances,
            "provenance": {
                "source": "deterministic_lathe",
                "commercial_use": True,
            },
        }
        if material_id is not None:
            scene_object["material_bindings"] = [
                {
                    "slot": "primary",
                    "material": material_id,
                }
            ]
        objects.append(scene_object)
    return objects


def _light_type(seed: str) -> str:
    lowered = seed.lower()
    if "moon" in lowered:
        return "moonbeam"
    if "candle" in lowered or "torch" in lowered or "flame" in lowered:
        return "candle_cluster"
    if "spot" in lowered:
        return "spot"
    if "sun" in lowered or "directional" in lowered:
        return "directional"
    if "emissive" in lowered or "glow" in lowered:
        return "emissive_practical"
    return "area"


def _lights(
    brief: Mapping[str, Any],
    *,
    elements: list[Mapping[str, Any]],
    focal_object_id: str,
) -> list[dict[str, Any]]:
    style = _safe_mapping(brief.get("style"))
    palette = _unique_tags(_safe_list(style.get("palette")), fallback="warm white")
    light_elements = [element for element in elements if element.get("role") == "light_fixture"]
    used_ids: set[str] = set()
    lights: list[dict[str, Any]] = []
    if not light_elements:
        seed = style.get("lighting", "key light")
        lights.append(
            {
                "light_id": _unique_prefixed_id("light", "key_001", used_ids),
                "type": _light_type(str(seed)),
                "target": focal_object_id,
                "color": palette[0],
                "intensity": 0.75,
                "purpose": str(seed) or "Primary scene lighting.",
            }
        )
        return lights

    for index, element in enumerate(light_elements, start=1):
        seed = str(element.get("description") or element.get("id") or "light")
        lights.append(
            {
                "light_id": _unique_prefixed_id("light", str(element.get("id", "light")), used_ids, suffix=index),
                "type": _light_type(seed),
                "target": focal_object_id,
                "color": palette[(index - 1) % len(palette)],
                "intensity": 0.72,
                "purpose": seed,
            }
        )
    return lights


def _camera_transform(framing: str, room_size: list[float]) -> tuple[list[float], list[float], float]:
    transforms = {
        "inspection": ([-1.8, -1.4, 1.4], [62.0, 0.0, -36.0], 36.0),
        "topdown": ([0.0, 0.0, room_size[2] + 4.0], [90.0, 0.0, 0.0], 55.0),
        "debug": ([room_size[0] * 0.45, -room_size[1] * 0.45, room_size[2] * 0.7], [60.0, 0.0, 42.0], 60.0),
        "contact_sheet": ([0.0, -room_size[1] * 0.7, room_size[2] * 0.55], [65.0, 0.0, 0.0], 50.0),
        "before_after": ([-room_size[0] * 0.35, -room_size[1] * 0.45, room_size[2] * 0.45], [62.0, 0.0, -30.0], 48.0),
    }
    position, rotation, fov = transforms.get(
        framing,
        ([-room_size[0] * 0.45, -room_size[1] * 0.55, room_size[2] * 0.45], [64.0, 0.0, -38.0], 48.0),
    )
    return (
        [round(value, 3) for value in position],
        [round(value, 3) for value in rotation],
        fov,
    )


def _cameras(brief: Mapping[str, Any], *, focal_object_id: str) -> list[dict[str, Any]]:
    room_size = SCALE_LAYOUTS.get(str(brief.get("scale")), SCALE_LAYOUTS["single_room"])[0]
    camera_intents = [
        intent for intent in _safe_list(brief.get("camera_intents")) if isinstance(intent, Mapping)
    ]
    if not camera_intents:
        camera_intents = [
            {
                "id": "reveal",
                "purpose": "Initial reveal of the lowered scene.",
                "framing": "cinematic_wide",
            },
            {
                "id": "debug_topdown",
                "purpose": "Deterministic topdown layout inspection.",
                "framing": "topdown",
            },
        ]
    elif not any(intent.get("framing") in {"debug", "topdown"} for intent in camera_intents):
        camera_intents.append(
            {
                "id": "debug_topdown",
                "purpose": "Deterministic topdown layout inspection.",
                "framing": "topdown",
            }
        )

    used_ids: set[str] = set()
    cameras: list[dict[str, Any]] = []
    for intent in camera_intents:
        framing = str(intent.get("framing") or "cinematic_wide")
        position, rotation, fov = _camera_transform(framing, room_size)
        cameras.append(
            {
                "camera_id": _unique_prefixed_id("camera", str(intent.get("id", "camera")), used_ids, suffix=None),
                "target": focal_object_id,
                "framing": framing,
                "purpose": str(intent.get("purpose") or "View the lowered scene."),
                "transform": {
                    "position": position,
                    "rotation": rotation,
                    "scale": [1.0, 1.0, 1.0],
                },
                "fov_degrees": fov,
            }
        )
    return cameras


def _relationships(
    *,
    object_ids: list[str],
    elements: list[Mapping[str, Any]],
    focal_index: int,
    region_id: str,
    lights: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    relationships: list[dict[str, Any]] = []
    used_ids: set[str] = set()
    focal_object_id = object_ids[focal_index]
    for index, (object_id, element) in enumerate(zip(object_ids, elements, strict=True), start=1):
        if index - 1 == focal_index:
            continue
        role = str(element.get("role"))
        if role in {"architecture", "environment_structure"}:
            rel_type = "contains"
            to_ref = region_id
        elif role == "navigation":
            rel_type = "points_toward"
            to_ref = focal_object_id
        else:
            rel_type = "adjacent_to"
            to_ref = focal_object_id
        relationships.append(
            {
                "relationship_id": _unique_prefixed_id(
                    "rel",
                    f"{_slugify(object_id.removeprefix('obj_'))}_{rel_type}",
                    used_ids,
                    suffix=index,
                ),
                "from": object_id,
                "to": to_ref,
                "type": rel_type,
                "description": f"{object_id} is lowered from the Dream Brief as {rel_type} {to_ref}.",
            }
        )

    for index, light in enumerate(lights, start=1):
        relationships.append(
            {
                "relationship_id": _unique_prefixed_id(
                    "rel",
                    f"{light['light_id']}_lights_focal",
                    used_ids,
                    suffix=index,
                ),
                "from": light["light_id"],
                "to": focal_object_id,
                "type": "lit_by",
                "description": "Generated scene light targets the focal object.",
            }
        )
    return relationships


def _export_path(scene_id: str, target: str, export_format: str) -> str:
    if target == "scene_graph":
        return "scene_graph.json"
    if target == "lathe_source":
        return f"generated/{scene_id}.lth"
    if target == "scene_package":
        return f"dist/{scene_id}.lathepkg"
    if target.endswith("_manifest"):
        return f"dist/exports/{scene_id}.{target}.json"
    return f"dist/exports/{scene_id}.{export_format}"


def _exports(brief: Mapping[str, Any], *, scene_id: str) -> list[dict[str, Any]]:
    targets = ["scene_graph", *[str(target) for target in _safe_list(brief.get("export_targets"))]]
    ordered_targets = _unique_tags(targets)
    exports: list[dict[str, Any]] = []
    for target in ordered_targets:
        export_format = EXPORT_FORMATS.get(target, "json")
        exports.append(
            {
                "target": target,
                "format": export_format,
                "path": _export_path(scene_id, target, export_format),
                "metadata": {
                    "planned_only": True,
                    "lowered_from": "dream_brief",
                },
            }
        )
    return exports


def _brief_scene_diagnostic(
    code: str,
    name: str,
    path: str,
    message: str,
    *,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "code": code,
        "name": name,
        "severity": "error",
        "contract": "brief_scene",
        "phase": "brief_scene_consistency",
        "path": path,
        "message": message,
    }
    if details:
        payload["details"] = details
    return payload


def _signal_tokens(value: object) -> list[str]:
    return re.findall(r"[a-z0-9]+", str(value).lower())


def _compact_signal(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).lower())


def _collect_signal_text(value: object) -> list[str]:
    if isinstance(value, Mapping):
        collected: list[str] = []
        for child in value.values():
            collected.extend(_collect_signal_text(child))
        return collected
    if isinstance(value, list):
        collected = []
        for child in value:
            collected.extend(_collect_signal_text(child))
        return collected
    if isinstance(value, str):
        return [value]
    if value is None:
        return []
    if isinstance(value, (bool, int, float)):
        return [str(value)]
    return []


def _signal_values(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value]
    return []


def _keywords(
    values: Iterable[object],
    *,
    min_length: int,
    include_role_words: bool = True,
) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        for token in _signal_tokens(value):
            if len(token) < min_length or token in _SIGNAL_STOPWORDS:
                continue
            if not include_role_words and token in _ROLE_SIGNAL_WORDS:
                continue
            if token in seen:
                continue
            seen.add(token)
            result.append(token)
    return result


def _required_element_keywords(element: Mapping[str, Any]) -> list[str]:
    element_id = str(element.get("id", ""))
    description = str(element.get("description", ""))
    keywords = [
        *_keywords([element_id], min_length=3, include_role_words=False),
        *_keywords([description], min_length=4, include_role_words=False),
    ]
    if not keywords:
        keywords = _keywords([element_id, description], min_length=3)
    return keywords


def _scene_entity_text(entity: object) -> str:
    return " ".join(_collect_signal_text(entity)).lower()


def _has_keyword_signal(keywords: Iterable[str], candidates: Iterable[str]) -> bool:
    for candidate in candidates:
        candidate_tokens = set(_signal_tokens(candidate))
        compact_candidate = _compact_signal(candidate)
        for keyword in keywords:
            if keyword in candidate_tokens or keyword in compact_candidate:
                return True
    return False


def _candidate_entities_for_role(scene_graph: Mapping[str, Any], role: str) -> list[Mapping[str, Any]]:
    objects = [item for _index, item in _scene_items(scene_graph, "objects")]
    candidates: list[Mapping[str, Any]] = []
    role_matches = {
        "architecture": {"architecture", "environment_structure"},
        "environment_structure": {"architecture", "environment_structure"},
    }.get(role, {role})
    candidates.extend(item for item in objects if item.get("role") in role_matches)
    if role == "light_fixture":
        candidates.extend(item for _index, item in _scene_items(scene_graph, "lights"))
    if role in {"architecture", "environment_structure"}:
        candidates.extend(item for _index, item in _scene_items(scene_graph, "regions"))
    return candidates


def _scene_items(scene_graph: Mapping[str, Any], collection: str) -> Iterable[tuple[int, Mapping[str, Any]]]:
    raw = scene_graph.get(collection, [])
    if not isinstance(raw, list):
        return []
    return [(index, item) for index, item in enumerate(raw) if isinstance(item, Mapping)]


def _check_brief_id_linkage(brief: Mapping[str, Any], scene_graph: Mapping[str, Any]) -> list[dict[str, Any]]:
    brief_id = brief.get("brief_id")
    scene_brief_id = scene_graph.get("brief_id")
    if scene_brief_id == brief_id:
        return []
    return [
        _brief_scene_diagnostic(
            "W2001",
            "brief_id_mismatch",
            "/brief_id",
            f"Scene Graph brief_id {scene_brief_id!r} does not match Dream Brief brief_id {brief_id!r}.",
            details={"brief_id": brief_id, "scene_brief_id": scene_brief_id},
        )
    ]


def _check_required_element_representation(
    brief: Mapping[str, Any],
    scene_graph: Mapping[str, Any],
) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    for index, element in enumerate(_safe_list(brief.get("required_elements"))):
        if not isinstance(element, Mapping):
            continue
        keywords = _required_element_keywords(element)
        role = str(element.get("role", ""))
        candidates = [_scene_entity_text(entity) for entity in _candidate_entities_for_role(scene_graph, role)]
        if keywords and _has_keyword_signal(keywords, candidates):
            continue
        diagnostics.append(
            _brief_scene_diagnostic(
                "W2002",
                "missing_required_element",
                f"/required_elements/{index}",
                f"Required brief element {element.get('id')!r} is not represented by matching Scene Graph entities.",
                details={
                    "element_id": element.get("id"),
                    "role": role,
                    "keywords": keywords,
                },
            )
        )
    return diagnostics


def _check_export_targets(brief: Mapping[str, Any], scene_graph: Mapping[str, Any]) -> list[dict[str, Any]]:
    scene_targets = {
        str(item.get("target"))
        for _index, item in _scene_items(scene_graph, "exports")
        if isinstance(item.get("target"), str)
    }
    scene_formats = {
        str(item.get("format"))
        for _index, item in _scene_items(scene_graph, "exports")
        if isinstance(item.get("format"), str)
    }
    targets: list[tuple[str, str]] = [
        (str(target), f"/export_targets/{index}")
        for index, target in enumerate(_safe_list(brief.get("export_targets")))
    ]
    platform = _safe_mapping(brief.get("constraints")).get("platform")
    if isinstance(platform, str) and platform != "generic":
        targets.append((platform, "/constraints/platform"))

    diagnostics: list[dict[str, Any]] = []
    seen: set[str] = set()
    for target, path in targets:
        if target in seen:
            continue
        seen.add(target)
        if target in DEFERRED_EXPORT_TARGETS:
            continue
        if target in scene_targets or target in scene_formats:
            continue
        diagnostics.append(
            _brief_scene_diagnostic(
                "W2003",
                "missing_export_target",
                path,
                f"Dream Brief export target {target!r} is not represented in Scene Graph exports.",
                details={
                    "target": target,
                    "scene_targets": sorted(scene_targets),
                },
            )
        )
    return diagnostics


def _style_signal_present(brief_values: list[str], scene_values: list[str]) -> bool:
    if not brief_values:
        return True
    keywords = _keywords(brief_values, min_length=4)
    if not keywords:
        keywords = _keywords(brief_values, min_length=3)
    return bool(keywords and _has_keyword_signal(keywords, [_scene_entity_text(scene_values)]))


def _check_style_signals(brief: Mapping[str, Any], scene_graph: Mapping[str, Any]) -> list[dict[str, Any]]:
    style = _safe_mapping(brief.get("style"))
    scene_style = _safe_mapping(scene_graph.get("style_bible"))
    checks = [
        ("W2010", "missing_mood_signal", "/mood", _signal_values(brief.get("mood")), scene_style.get("mood")),
        (
            "W2011",
            "missing_palette_signal",
            "/style/palette",
            _signal_values(style.get("palette")),
            scene_style.get("palette"),
        ),
        (
            "W2012",
            "missing_material_signal",
            "/style/materials",
            _signal_values(style.get("materials")),
            scene_style.get("materials"),
        ),
        (
            "W2013",
            "missing_form_signal",
            "/style/form_language",
            _signal_values(style.get("form_language")),
            scene_style.get("forms"),
        ),
        (
            "W2014",
            "missing_lighting_signal",
            "/style/lighting",
            _signal_values(style.get("lighting")),
            scene_style.get("lighting"),
        ),
        (
            "W2015",
            "missing_avoid_signal",
            "/style/avoid_styles",
            [*_signal_values(style.get("avoid_styles")), *_signal_values(brief.get("avoid"))],
            scene_style.get("avoid"),
        ),
    ]
    diagnostics: list[dict[str, Any]] = []
    for code, name, path, brief_values, raw_scene_values in checks:
        scene_values = _signal_values(raw_scene_values)
        if _style_signal_present(brief_values, scene_values):
            continue
        diagnostics.append(
            _brief_scene_diagnostic(
                code,
                name,
                path,
                f"Scene Graph style_bible does not preserve a recognizable {name.removeprefix('missing_').removesuffix('_signal')} signal.",
                details={
                    "brief_values": brief_values,
                    "scene_values": scene_values,
                },
            )
        )
    return diagnostics


def check_brief_scene_consistency(
    brief: Mapping[str, Any],
    scene_graph: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Return obvious Dream Brief to Scene Graph consistency diagnostics."""
    diagnostics: list[dict[str, Any]] = []
    diagnostics.extend(_check_brief_id_linkage(brief, scene_graph))
    diagnostics.extend(_check_required_element_representation(brief, scene_graph))
    diagnostics.extend(_check_export_targets(brief, scene_graph))
    diagnostics.extend(_check_style_signals(brief, scene_graph))
    return diagnostics


def load_and_check_brief_scene(
    brief_path: str | Path,
    scene_graph_path: str | Path,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    """Load, schema-check, and consistency-check a Dream Brief/Scene Graph pair."""
    from lathe.scene import check_scene_graph

    brief_file = Path(brief_path)
    scene_file = Path(scene_graph_path)
    brief, brief_diagnostics = load_and_validate_contract("dream_brief", brief_file)
    scene_graph, scene_diagnostics = load_and_validate_contract("scene_graph", scene_file)
    diagnostics = [*brief_diagnostics, *scene_diagnostics]
    if brief_diagnostics or scene_diagnostics:
        return brief, scene_graph, diagnostics
    diagnostics.extend(check_scene_graph(scene_graph, root=scene_file.parent))
    diagnostics.extend(check_brief_scene_consistency(brief, scene_graph))
    return brief, scene_graph, diagnostics


def lower_dream_brief_to_scene_graph(brief: Mapping[str, Any]) -> dict[str, Any]:
    """Lower a schema-valid Dream Brief into a deterministic initial Scene Graph."""
    diagnostics = validate_contract("dream_brief", dict(brief))
    if diagnostics:
        first = diagnostics[0]
        raise WonderContractError(
            f"Dream Brief cannot be lowered: {first['path']}: {first['message']}"
        )

    brief_id = str(brief["brief_id"])
    scene_id = _snake_id(brief_id, fallback="scene")
    raw_elements = _safe_list(brief.get("required_elements"))
    elements = [element for element in raw_elements if isinstance(element, Mapping)]
    if not elements:
        raise WonderContractError("Dream Brief cannot be lowered without required_elements.")

    used_object_ids: set[str] = set()
    object_ids = [
        _unique_prefixed_id("obj", str(element["id"]), used_object_ids, suffix=index)
        for index, element in enumerate(elements, start=1)
    ]
    focal_index = _choose_focal_index(elements)
    focal_object_id = object_ids[focal_index]
    region_id = _prefixed_id("region", f"{scene_id}_main")
    layout, region_seed = _layout(str(brief.get("scale", "single_room")), region_id, focal_object_id)
    materials = _materials(brief)
    curiosity_anchors, hidden_state = _curiosity_and_hidden(brief, focal_object_id=focal_object_id)
    objects = _objects(
        brief,
        elements=elements,
        object_ids=object_ids,
        focal_index=focal_index,
        region_id=region_id,
        materials=materials,
        hidden_state=hidden_state,
    )
    lights = _lights(brief, elements=elements, focal_object_id=focal_object_id)
    cameras = _cameras(brief, focal_object_id=focal_object_id)

    return {
        "schema_version": "lathe.scene_graph.v1",
        "scene_id": scene_id,
        "version": 1,
        "brief_id": brief_id,
        "prompt": _brief_prompt(brief),
        "style_bible": _style_bible(brief),
        "layout": layout,
        "regions": [_region(brief, region_seed)],
        "objects": objects,
        "relationships": _relationships(
            object_ids=object_ids,
            elements=elements,
            focal_index=focal_index,
            region_id=region_id,
            lights=lights,
        ),
        "materials": materials,
        "lights": lights,
        "cameras": cameras,
        "curiosity_anchors": curiosity_anchors,
        "hidden_state": hidden_state,
        "exports": _exports(brief, scene_id=scene_id),
        "build_artifacts": [
            {
                "kind": "scene_graph",
                "path": "scene_graph.json",
                "status": "planned",
                "produced_by": "lathe.wonder.brief",
            }
        ],
        "memory_events": [],
    }


__all__ = [
    "check_brief_scene_consistency",
    "load_and_check_brief_scene",
    "lower_dream_brief_to_scene_graph",
]
