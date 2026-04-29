"""Deterministic Dream Brief decomposition helpers."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any

from .brief import (
    ROLE_SOURCE_FAMILIES,
    SCALE_LAYOUTS,
    _brief_prompt,
    _choose_focal_index,
    _materials,
    _prefixed_id,
    _safe_list,
    _snake_id,
    _style_bible,
    _unique_prefixed_id,
    _unique_tags,
)
from .contracts import WonderContractError, validate_contract

DECOMPOSITION_SCHEMA_VERSION = "lathe.dream_brief_decomposition.v1"


@dataclass(frozen=True)
class DecomposedBriefElement:
    """Stable planning identity for one Dream Brief required element."""

    element_id: str
    object_id: str
    role: str
    priority: str
    asset_id: str
    source_family: str
    represented_as: str
    is_focal: bool
    description: str


@dataclass(frozen=True)
class DecomposedBrief:
    """Deterministic, JSON-ready brief decomposition used by Wonder CLI."""

    schema_version: str
    brief_id: str
    scene_id: str
    prompt: str
    scale: str
    layout_profile: dict[str, Any]
    primary_region: dict[str, Any]
    focal_object_id: str
    elements: list[DecomposedBriefElement]
    style_bible: dict[str, Any]
    material_plan: list[dict[str, Any]]
    camera_plan: list[dict[str, str]]
    curiosity_plan: list[dict[str, Any]]
    export_targets: list[str]

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable decomposition payload."""
        return asdict(self)


def _camera_plan(brief: Mapping[str, Any]) -> list[dict[str, str]]:
    camera_intents = [intent for intent in _safe_list(brief.get("camera_intents")) if isinstance(intent, Mapping)]
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
    plan: list[dict[str, str]] = []
    for intent in camera_intents:
        camera_id = _unique_prefixed_id("camera", str(intent.get("id", "camera")), used_ids)
        plan.append(
            {
                "camera_id": camera_id,
                "intent_id": str(intent.get("id", "camera")),
                "framing": str(intent.get("framing") or "cinematic_wide"),
                "purpose": str(intent.get("purpose") or "View the lowered scene."),
            }
        )
    return plan


def _curiosity_plan(brief: Mapping[str, Any], *, focal_object_id: str) -> list[dict[str, Any]]:
    goals = _unique_tags(_safe_list(brief.get("curiosity_goals")))
    plan: list[dict[str, Any]] = []
    used_curiosity_ids: set[str] = set()
    used_hidden_ids: set[str] = set()
    for index, goal in enumerate(goals, start=1):
        plan.append(
            {
                "goal": goal,
                "anchor_id": _unique_prefixed_id("curiosity", goal, used_curiosity_ids, suffix=index),
                "hidden_id": _unique_prefixed_id("hidden", goal, used_hidden_ids, suffix=index),
                "attached_to": focal_object_id,
            }
        )
    return plan


def decompose_dream_brief(brief: Mapping[str, Any]) -> DecomposedBrief:
    """Return the deterministic planning decomposition for a Dream Brief."""
    diagnostics = validate_contract("dream_brief", dict(brief))
    if diagnostics:
        first = diagnostics[0]
        raise WonderContractError(
            f"Dream Brief cannot be decomposed: {first['path']}: {first['message']}"
        )

    brief_id = str(brief["brief_id"])
    scene_id = _snake_id(brief_id, fallback="scene")
    elements = [element for element in _safe_list(brief.get("required_elements")) if isinstance(element, Mapping)]
    if not elements:
        raise WonderContractError("Dream Brief cannot be decomposed without required_elements.")

    used_object_ids: set[str] = set()
    object_ids = [
        _unique_prefixed_id("obj", str(element["id"]), used_object_ids, suffix=index)
        for index, element in enumerate(elements, start=1)
    ]
    focal_index = _choose_focal_index(elements)
    focal_object_id = object_ids[focal_index]
    region_id = _prefixed_id("region", f"{scene_id}_main")
    room_size, region_type, density, path_width = SCALE_LAYOUTS.get(
        str(brief.get("scale", "single_room")),
        SCALE_LAYOUTS["single_room"],
    )

    decomposed_elements: list[DecomposedBriefElement] = []
    for index, element in enumerate(elements):
        role = str(element["role"])
        decomposed_elements.append(
            DecomposedBriefElement(
                element_id=str(element["id"]),
                object_id=object_ids[index],
                role=role,
                priority=str(element["priority"]),
                asset_id=_snake_id(str(element["id"]), fallback="asset"),
                source_family=ROLE_SOURCE_FAMILIES.get(role, "scene_object"),
                represented_as="scene_light" if role == "light_fixture" else "scene_object",
                is_focal=index == focal_index,
                description=str(element["description"]),
            )
        )

    export_targets = _unique_tags(["scene_graph", *[str(target) for target in _safe_list(brief.get("export_targets"))]])
    return DecomposedBrief(
        schema_version=DECOMPOSITION_SCHEMA_VERSION,
        brief_id=brief_id,
        scene_id=scene_id,
        prompt=_brief_prompt(brief),
        scale=str(brief.get("scale", "single_room")),
        layout_profile={
            "kind": str(brief.get("scale", "single_room")),
            "room_size": room_size,
            "density": density,
            "main_path_width": path_width,
        },
        primary_region={
            "region_id": region_id,
            "type": region_type,
        },
        focal_object_id=focal_object_id,
        elements=decomposed_elements,
        style_bible=_style_bible(brief),
        material_plan=_materials(brief),
        camera_plan=_camera_plan(brief),
        curiosity_plan=_curiosity_plan(brief, focal_object_id=focal_object_id),
        export_targets=export_targets,
    )


__all__ = [
    "DECOMPOSITION_SCHEMA_VERSION",
    "DecomposedBrief",
    "DecomposedBriefElement",
    "decompose_dream_brief",
]
