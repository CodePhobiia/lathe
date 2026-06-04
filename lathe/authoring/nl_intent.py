"""Natural-language intent capture (Wave 18 / research §8 layer 3).

Lands the typed contract for "user says 'make a brass steampunk
chest with corner reinforcements and a heavy latch'" → a structured
``NLIntent`` record → a construction_graph + family alias + visual
language assignment the synthesizer can consume.

The actual NL parsing (LLM call, classifier, regex, whatever) is the
upstream layer's choice. This module names the typed intent the
upstream produces + the deterministic translation from intent to
synthesizer payload.

That separation keeps the deterministic substrate deterministic: the
NL layer is allowed to be probabilistic, but the moment it commits
to an ``NLIntent``, every downstream step is deterministic per the
seed hierarchy.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

CONTRACT_VERSION = "lathe.authoring.nl_intent_v1"


@dataclass(frozen=True)
class NLIntent:
    """Structured intent produced by the natural-language layer.

    All fields are optional except ``asset_class``. Unspecified fields
    fall back to the alias / morphology default.
    """

    asset_class: str  # "crate" | "door" | "panel" | "terminal" | "weapon"
    visual_language: str = ""  # e.g. "steampunk_workshop_v1"
    condition: float = 0.3
    scale_m: float = 0.9
    parts_requested: tuple[str, ...] = ()
    features_allow: tuple[str, ...] = ()
    features_forbid: tuple[str, ...] = ()
    style_hints: Mapping[str, Any] = field(default_factory=dict)
    seed: int | None = None
    raw_prompt: str = ""


# Mapping from asset_class → canonical FamilyAlias + MorphologyProfile.
_CLASS_TO_FAMILY: dict[str, dict[str, str]] = {
    "crate": {"family": "industrial_crate", "kind": "hard_surface_prop"},
    "door": {"family": "mechanical_door", "kind": "env_module"},
    "panel": {"family": "service_cabinet", "kind": "mechanical_prop"},
    "terminal": {"family": "console_terminal", "kind": "interactable"},
    "weapon": {"family": "fantasy_weapon", "kind": "weapon_prop"},
}


def parse_nl_intent(
    prompt: str,
    asset_class: str,
    *,
    visual_language: str = "",
    condition: float = 0.3,
    scale_m: float = 0.9,
    parts_requested: tuple[str, ...] = (),
    features_allow: tuple[str, ...] = (),
    features_forbid: tuple[str, ...] = (),
    style_hints: Mapping[str, Any] | None = None,
    seed: int | None = None,
) -> NLIntent:
    """Construct an NLIntent from explicit fields.

    Upstream NL pipelines (LLM extraction, classifier) call this
    after extracting structured fields from a prompt. The function is
    a deterministic shaper, not a parser — it doesn't interpret the
    raw prompt itself.
    """
    return NLIntent(
        asset_class=asset_class,
        visual_language=visual_language,
        condition=max(0.0, min(1.0, float(condition))),
        scale_m=max(0.01, float(scale_m)),
        parts_requested=tuple(parts_requested),
        features_allow=tuple(features_allow),
        features_forbid=tuple(features_forbid),
        style_hints=dict(style_hints or {}),
        seed=seed,
        raw_prompt=str(prompt),
    )


def nl_intent_to_construction_payload(intent: NLIntent) -> dict[str, Any]:
    """Project an NLIntent into the .lth-equivalent construction payload.

    Returns a dict with the keys the synthesizer's runtime_from_asset
    expects: ``kind``, ``from``, ``intent`` (with parts + scale +
    density), ``features.allow``, ``features.forbid``, and a
    ``build.shape.procedural.brief`` block carrying the visual
    language + condition hints.
    """
    family_meta = _CLASS_TO_FAMILY.get(intent.asset_class) or {
        "family": intent.asset_class,
        "kind": "hard_surface_prop",
    }
    payload: dict[str, Any] = {
        "name": f"{intent.asset_class}_nl",
        "kind": family_meta["kind"],
        "from": f"{family_meta['family']}_family",
        "intent": {
            "kind": family_meta["kind"],
            "scale": {"type": "unit", "value": intent.scale_m, "unit": "m"},
            "parts": list(intent.parts_requested),
            "density": 1.0,
        },
        "features": {
            "allow": list(intent.features_allow),
            "forbid": list(intent.features_forbid),
        },
        "build": {
            "shape": {
                "procedural": {
                    "brief": {
                        "family": f"{family_meta['family']}_family",
                        "visual_language": intent.visual_language,
                        "condition": intent.condition,
                        "style_hints": dict(intent.style_hints),
                    }
                }
            }
        },
    }
    if intent.seed is not None:
        payload["build"]["shape"]["procedural"]["brief"]["seed"] = intent.seed
    return payload


__all__ = [
    "CONTRACT_VERSION",
    "NLIntent",
    "parse_nl_intent",
    "nl_intent_to_construction_payload",
]
