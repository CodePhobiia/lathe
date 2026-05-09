"""Built-in ``asset_class_profile`` definitions and cascade logic.

Closes roadmap §5.10. ``intent.asset_class`` on an asset names either
a built-in profile (``aaa_hero``, ``hero``, ``mid_ground``,
``background``, ``mobile``, ``web``, ``roblox``) or a user-declared
``asset_class_profile`` from the program. The named profile cascades
its budgets, LOD count and validator threshold into the asset's
``build.topology.target_quads`` / ``build.surface.resolution`` /
``build.optimize.lods`` / ``validate.threshold`` slots, but only when
the author left those slots unfilled — explicit author values always
win.

Numeric defaults are sourced from the quality_framework §6 budgets
referenced by the Phase 1 roadmap. ``generic`` is the no-op default
applied when an asset omits ``intent.asset_class``: it triggers no
cascade and no hero-class diagnostic gates.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

GENERIC_ASSET_CLASS = "generic"

BUILTIN_ASSET_CLASS_PROFILES: dict[str, dict[str, Any]] = {
    "aaa_hero": {
        "poly_budget": {"tris_max": 150000, "quads_target": 30000},
        "texture_budget": {
            "basecolor": {"type": "unit", "value": 4096, "unit": "px"},
            "normal": {"type": "unit", "value": 4096, "unit": "px"},
            "orm": {"type": "unit", "value": 2048, "unit": "px"},
            "emissive": {"type": "unit", "value": 2048, "unit": "px"},
        },
        "lod_count": 4,
        "validator_threshold": 0.92,
    },
    "hero": {
        "poly_budget": {"tris_max": 80000, "quads_target": 20000},
        "texture_budget": {
            "basecolor": {"type": "unit", "value": 2048, "unit": "px"},
            "normal": {"type": "unit", "value": 4096, "unit": "px"},
            "orm": {"type": "unit", "value": 2048, "unit": "px"},
            "emissive": {"type": "unit", "value": 1024, "unit": "px"},
        },
        "lod_count": 3,
        "validator_threshold": 0.88,
    },
    "mid_ground": {
        "poly_budget": {"tris_max": 20000, "quads_target": 6000},
        "texture_budget": {
            "basecolor": {"type": "unit", "value": 1024, "unit": "px"},
            "normal": {"type": "unit", "value": 2048, "unit": "px"},
            "orm": {"type": "unit", "value": 1024, "unit": "px"},
            "emissive": {"type": "unit", "value": 512, "unit": "px"},
        },
        "lod_count": 3,
        "validator_threshold": 0.84,
    },
    "background": {
        "poly_budget": {"tris_max": 3000, "quads_target": 1000},
        "texture_budget": {
            "basecolor": {"type": "unit", "value": 512, "unit": "px"},
            "normal": {"type": "unit", "value": 1024, "unit": "px"},
            "orm": {"type": "unit", "value": 512, "unit": "px"},
            "emissive": {"type": "unit", "value": 256, "unit": "px"},
        },
        "lod_count": 2,
        "validator_threshold": 0.78,
    },
    "mobile": {
        "poly_budget": {"tris_max": 5000, "quads_target": 1500},
        "texture_budget": {
            "basecolor": {"type": "unit", "value": 1024, "unit": "px"},
            "normal": {"type": "unit", "value": 1024, "unit": "px"},
            "orm": {"type": "unit", "value": 512, "unit": "px"},
            "emissive": {"type": "unit", "value": 512, "unit": "px"},
        },
        "lod_count": 3,
        "validator_threshold": 0.78,
    },
    "web": {
        "poly_budget": {"tris_max": 15000, "quads_target": 4000},
        "texture_budget": {
            "basecolor": {"type": "unit", "value": 1024, "unit": "px"},
            "normal": {"type": "unit", "value": 1024, "unit": "px"},
            "orm": {"type": "unit", "value": 512, "unit": "px"},
            "emissive": {"type": "unit", "value": 512, "unit": "px"},
        },
        "lod_count": 2,
        "validator_threshold": 0.78,
    },
    "roblox": {
        "poly_budget": {"tris_max": 10000, "quads_target": 3000},
        "texture_budget": {
            "basecolor": {"type": "unit", "value": 1024, "unit": "px"},
            "normal": {"type": "unit", "value": 1024, "unit": "px"},
        },
        "lod_count": 1,
        "validator_threshold": 0.70,
    },
}

ALL_BUILTIN_NAMES: tuple[str, ...] = (GENERIC_ASSET_CLASS, *BUILTIN_ASSET_CLASS_PROFILES)


def get_builtin_profile(name: str) -> dict[str, Any] | None:
    """Return a deep copy of a built-in profile body, or ``None``.

    ``generic`` resolves to ``None`` because it intentionally has no
    cascade payload — assets without ``intent.asset_class`` should
    behave exactly as legacy assets.
    """
    if name == GENERIC_ASSET_CLASS:
        return None
    body = BUILTIN_ASSET_CLASS_PROFILES.get(name)
    return deepcopy(body) if body is not None else None


def _profile_body(decl: dict[str, Any]) -> dict[str, Any]:
    """Extract the cascade body from a parsed/normalized profile decl."""
    values = decl.get("values") or {}
    body = {
        "poly_budget": dict(values.get("poly_budget") or {}),
        "texture_budget": dict(values.get("texture_budget") or {}),
    }
    if "lod_count" in values:
        body["lod_count"] = values["lod_count"]
    if "validator_threshold" in values:
        body["validator_threshold"] = values["validator_threshold"]
    if "lod_count" in decl:
        body.setdefault("lod_count", decl["lod_count"])
    if "validator_threshold" in decl:
        body.setdefault("validator_threshold", decl["validator_threshold"])
    return body


def resolve_asset_class_profile(
    name: str, user_profiles: dict[str, dict[str, Any]] | None = None
) -> dict[str, Any] | None:
    """Look up a profile body by name.

    User-declared profiles take precedence over built-ins (they may
    intentionally shadow ``hero``/``mobile``/etc. for project-specific
    overrides). Returns ``None`` for ``generic`` and unknown names so
    callers can no-op cleanly.
    """
    if not name or name == GENERIC_ASSET_CLASS:
        return None
    if user_profiles and name in user_profiles:
        return _profile_body(user_profiles[name])
    return get_builtin_profile(name)


def is_known_asset_class(
    name: str, user_profiles: dict[str, dict[str, Any]] | None = None
) -> bool:
    """Return True for ``generic``, any built-in, or any user profile."""
    if not name:
        return True
    if name == GENERIC_ASSET_CLASS:
        return True
    if name in BUILTIN_ASSET_CLASS_PROFILES:
        return True
    return bool(user_profiles and name in user_profiles)


def _max_texture_budget(texture_budget: dict[str, Any]) -> dict[str, Any] | int | None:
    """Pick the largest declared texture size as a representative resolution.

    The cascade target is ``build.surface.resolution``, a single value
    rather than a per-map map. We mirror the highest declared map size
    so the chosen resolution is at least sufficient for every map the
    profile budgets.
    """
    best_value = -1
    best_entry: Any = None
    for entry in texture_budget.values():
        value = _resolution_value(entry)
        if value > best_value:
            best_value = value
            best_entry = entry
    if best_entry is None:
        return None
    return deepcopy(best_entry)


def _resolution_value(entry: Any) -> int:
    if isinstance(entry, dict) and entry.get("type") == "unit":
        try:
            return int(entry.get("value", 0))
        except (TypeError, ValueError):
            return 0
    if isinstance(entry, (int, float)):
        return int(entry)
    return 0


def cascade_into_asset(
    asset: dict[str, Any], body: dict[str, Any]
) -> dict[str, Any]:
    """Fill missing build/validate slots from a profile body.

    Mutates and returns ``asset``. Author-declared values are never
    overwritten — the cascade runs ``setdefault``-style on each leaf.
    The cascade targets are:

    * ``build.topology.target_quads`` ← ``poly_budget.quads_target`` (or
      ``poly_budget.tris_max`` halved as a fallback)
    * ``build.surface.resolution`` ← max declared map in
      ``texture_budget``
    * ``build.optimize.lods`` ← ``lod_count``
    * ``validate.threshold`` ← ``validator_threshold``
    """
    build = asset.setdefault("build", {})
    topology = build.setdefault("topology", {})
    surface = build.setdefault("surface", {})
    optimize = build.setdefault("optimize", {})
    validate = asset.setdefault("validate", {})

    poly_budget = body.get("poly_budget") or {}
    quads_target = poly_budget.get("quads_target")
    tris_max = poly_budget.get("tris_max")
    if quads_target is None and tris_max is not None:
        try:
            quads_target = max(1, int(tris_max) // 2)
        except (TypeError, ValueError):
            quads_target = None
    if quads_target is not None and "target_quads" not in topology:
        topology["target_quads"] = int(quads_target)
    if tris_max is not None and "tris_max" not in topology:
        topology["tris_max"] = int(tris_max)

    texture_budget = body.get("texture_budget") or {}
    if texture_budget:
        max_res = _max_texture_budget(texture_budget)
        if max_res is not None and "resolution" not in surface:
            surface["resolution"] = max_res
        budget_slot = surface.setdefault("texture_budget", {})
        for map_name, entry in texture_budget.items():
            budget_slot.setdefault(map_name, deepcopy(entry))

    if "lod_count" in body and "lods" not in optimize:
        try:
            optimize["lods"] = int(body["lod_count"])
        except (TypeError, ValueError):
            pass

    if "validator_threshold" in body and "threshold" not in validate:
        try:
            validate["threshold"] = float(body["validator_threshold"])
        except (TypeError, ValueError):
            pass

    return asset
