"""Wonder mode CLI planner (Wave 26 / P15).

Takes a one-sentence prompt → structured NLIntent → KitGraph → scene
composition → planned asset builds → planned packaging. Returns a
``WonderResult`` describing the planned execution without actually
running heavyweight builds (which take minutes per asset).

The actual execution layer (running synth + topology + uv + surface +
package per instance) is invoked separately so the planner stays
fast + testable.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..authoring.nl_intent import NLIntent, nl_intent_to_construction_payload, parse_nl_intent
from ..determinism.seeds import derive_hierarchy
from ..scene.kit_graph import ArchetypeReference, KitGraph
from ..scene.scene_compose import SceneComposition, compose_scene_from_kit

CONTRACT_VERSION = "lathe.wonder.cli_v1"


@dataclass(frozen=True)
class WonderRequest:
    """A wonder-mode request — the one prompt + execution metadata."""

    prompt: str
    intents: tuple[NLIntent, ...]
    kit: KitGraph
    world_seed: int = 0
    out_dir: Path | None = None
    target_engines: tuple[str, ...] = ("roblox", "unity", "unreal", "usd", "gltf")


@dataclass(frozen=True)
class WonderResult:
    """Planned wonder-mode build — exercises every contract."""

    request: WonderRequest
    composition: SceneComposition
    seed_hierarchies_by_instance: Mapping[str, Any]
    construction_payloads_by_instance: Mapping[str, Mapping[str, Any]]
    planned_asset_count: int
    planned_engine_manifests: tuple[str, ...]


def plan_wonder_build(request: WonderRequest) -> WonderResult:
    """Plan a wonder-mode build from a request.

    For each intent:
      1. Resolve its archetype reference in the kit.
      2. Compose scene → instance per archetype.
      3. Derive seed hierarchy per instance.
      4. Generate construction payload per instance.
    """
    composition = compose_scene_from_kit(request.kit, request.world_seed)

    seed_hierarchies: dict[str, Any] = {}
    construction_payloads: dict[str, Mapping[str, Any]] = {}
    for instance in composition.instances:
        hierarchy = derive_hierarchy(
            world_seed=request.world_seed,
            kit_id=composition.kit_id,
            asset_id=instance.instance_id,
        )
        seed_hierarchies[instance.instance_id] = hierarchy

        # Match intent for this archetype role, if any.
        matching_intent = next(
            (intent for intent in request.intents if intent.asset_class == instance.archetype_role),
            None,
        )
        if matching_intent is None:
            matching_intent = parse_nl_intent(
                prompt=request.prompt,
                asset_class=instance.archetype_role,
                visual_language=request.kit.visual_language_id,
                condition=instance.condition,
                scale_m=0.9,
                seed=instance.seed,
            )
        construction_payloads[instance.instance_id] = nl_intent_to_construction_payload(
            matching_intent
        )

    return WonderResult(
        request=request,
        composition=composition,
        seed_hierarchies_by_instance=seed_hierarchies,
        construction_payloads_by_instance=construction_payloads,
        planned_asset_count=composition.instance_count(),
        planned_engine_manifests=request.target_engines,
    )


def quick_wonder_request_from_prompt(
    prompt: str,
    asset_classes: Mapping[str, int],
    visual_language: str = "utility_industrial_v1",
    world_seed: int = 0,
) -> WonderRequest:
    """Quick-construct a WonderRequest for testing / demo use.

    ``asset_classes`` maps role → count (e.g., {"crate": 6, "door": 2}).
    """
    archetypes = []
    intents = []
    for role, count in asset_classes.items():
        source_lth = {
            "crate": "examples/industrial_crate.lth",
            "door": "examples/mechanical_door.lth",
            "panel": "examples/service_panel.lth",
            "terminal": "examples/service_terminal.lth",
        }.get(role, f"examples/{role}.lth")
        archetypes.append(
            ArchetypeReference(
                role=role,
                source_lth=source_lth,
                asset_name=role,
                seed_strategy="stratified",
                repetition_limit=count,
                condition_distribution=(0.1, 0.7),
            )
        )
        intents.append(
            parse_nl_intent(
                prompt=prompt,
                asset_class=role,
                visual_language=visual_language,
                condition=0.4,
                scale_m=0.9,
            )
        )

    kit = KitGraph(
        kit_id=f"wonder_kit_seed_{world_seed}",
        visual_language_id=visual_language,
        archetypes=tuple(archetypes),
        variation_seed=world_seed,
    )
    return WonderRequest(
        prompt=prompt,
        intents=tuple(intents),
        kit=kit,
        world_seed=world_seed,
    )


__all__ = [
    "CONTRACT_VERSION",
    "WonderRequest",
    "WonderResult",
    "plan_wonder_build",
    "quick_wonder_request_from_prompt",
]
