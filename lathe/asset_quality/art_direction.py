"""Universal art-direction IR for Phase 14C quality planning.

This module is intentionally independent of public ``.lth`` syntax. It
normalizes fixture or runtime design-brief evidence into a shared
art-direction shape that downstream quality planning, scoring, and
certification can consume across weapons, crates, machines, furniture,
and environment props.
"""

from __future__ import annotations

from typing import Any

ART_DIRECTION_DOCUMENT_VERSION = "lathe.asset_quality.art_direction.v1"
ART_DIRECTION_IR_VERSION = "lathe.asset_quality.art_direction_ir.v1"

QUALITY_DIMENSIONS: tuple[str, ...] = (
    "silhouette_strength",
    "proportion_intent",
    "material_contrast",
    "detail_hierarchy",
    "motif_coherence",
    "surface_storytelling",
    "functional_readability",
    "style_consistency",
    "procedural_noise_penalty",
)

_OBJECT_FAMILY_TOKENS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("weapon", ("weapon", "sword", "blade", "staff", "dagger", "shield")),
    ("container", ("crate", "chest", "container", "box")),
    ("machine", ("machine", "terminal", "dropper", "conveyor", "tycoon", "dispenser")),
    ("furniture", ("counter", "chair", "table", "cabinet", "shelf", "shop")),
    ("architecture", ("door", "gate", "wall", "room", "architecture")),
    ("environment_piece", ("rock", "tree", "environment", "prop", "altar", "torch")),
)


def build_art_direction_ir(
    design_brief: dict[str, Any],
    *,
    family_metadata: dict[str, Any] | None = None,
    reference_board: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the normalized Phase 14C art-direction IR."""
    brief = _as_dict(design_brief)
    style = _style_from_brief(brief)
    platform = _platform_from_brief(brief)
    required_features = _string_list(brief.get("required_features"))
    forbidden = _string_list(style.get("forbidden"))
    keywords = _string_list(style.get("keywords"))
    family = _family_from_brief(brief)
    asset_id = _string(brief.get("asset_id")) or _string(brief.get("asset_name")) or "unnamed_asset"
    object_family = infer_object_family(
        family=family,
        theme=_string(style.get("theme")),
        keywords=keywords,
        required_features=required_features,
    )
    reference = _as_dict(reference_board)
    reference_summary = _reference_summary(reference)
    family_summary = _family_summary(_as_dict(family_metadata))

    forbidden_failures = sorted(set(forbidden + _universal_failures()))
    return {
        "schema_version": ART_DIRECTION_IR_VERSION,
        "asset_id": asset_id,
        "family": family,
        "object_family": object_family,
        "style_intent": {
            "genre": _genre_from_style(style, keywords),
            "substyle": _string(style.get("theme")) or "general game asset",
            "mood": keywords[:5],
            "audience": _string(platform.get("target")) or "game runtime",
            "quality_bar": _string(brief.get("certification_tier")) or "warning_quality",
        },
        "visual_hierarchy": {
            "primary_read": _primary_read(object_family, required_features),
            "secondary_read": "functional parts and silhouette accents remain readable",
            "tertiary_read": "ornament, decals, wear, and microdetail are bounded by motif or function",
            "noise_policy": "ornament must map to a declared motif, material transition, or functional affordance",
        },
        "silhouette": {
            "target_strength": "high",
            "thumbnail_size_px": 128,
            "required_distinctive_features": required_features[:5],
            "forbidden_shapes": forbidden,
        },
        "proportion_policy": {
            "functional_scale_required": True,
            "exaggeration_allowed_when_style_requires": True,
            "scale_anchors": _scale_anchors(object_family),
        },
        "materials": {
            "required_separation": "high",
            "zones": _material_zone_goals(object_family, required_features),
            "contrast_policy": "primary/secondary/accent/readability",
        },
        "motifs": {
            "allowed": _motifs_from_style(object_family, keywords),
            "forbidden": forbidden,
            "placement_rules": _motif_placement_rules(object_family),
        },
        "surface_story": {
            "wear_logic": _wear_logic(object_family),
            "decals": _decal_logic(object_family),
            "grime_logic": ["recesses", "lower contact points", "handled/touched affordances"],
        },
        "platform": {
            "target": _string(platform.get("target")) or "game_runtime_proxy",
            "triangle_budget_warning": platform.get("triangle_budget_warning"),
            "triangle_budget_strict": platform.get("triangle_budget_strict"),
            "texture_policy": _string(platform.get("texture_budget")) or "proxy_or_deferred",
        },
        "forbidden_failure_modes": forbidden_failures,
        "forbidden_visual_failure_modes": forbidden_failures,
        "reference_summary": reference_summary,
        "family_metadata_summary": family_summary,
    }


def build_art_direction_document(
    design_brief: dict[str, Any],
    *,
    family_metadata: dict[str, Any] | None = None,
    reference_board: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the checked-in ``art_direction.json`` document shape."""
    ir = build_art_direction_ir(
        design_brief,
        family_metadata=family_metadata,
        reference_board=reference_board,
    )
    return _document_from_ir(ir)


def normalize_art_direction(
    art_direction: dict[str, Any] | None,
    *,
    design_brief: dict[str, Any] | None = None,
    family_metadata: dict[str, Any] | None = None,
    reference_board: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Normalize explicit art-direction evidence or derive it from a brief."""
    payload = _as_dict(art_direction)
    if not payload:
        return build_art_direction_ir(
            _as_dict(design_brief),
            family_metadata=family_metadata,
            reference_board=reference_board,
        )

    normalized = dict(payload)
    failures = _string_list(normalized.get("forbidden_failure_modes"))
    visual_failures = _string_list(normalized.get("forbidden_visual_failure_modes"))
    combined_failures = sorted(set(failures + visual_failures + _universal_failures()))
    normalized["schema_version"] = ART_DIRECTION_IR_VERSION
    normalized.setdefault("family", _family_from_brief(_as_dict(design_brief)))
    normalized["forbidden_failure_modes"] = combined_failures
    normalized["forbidden_visual_failure_modes"] = combined_failures
    normalized.setdefault("reference_summary", _reference_summary(_as_dict(reference_board)))
    normalized.setdefault("family_metadata_summary", _family_summary(_as_dict(family_metadata)))
    return normalized


def validate_art_direction_payload(payload: dict[str, Any]) -> list[str]:
    """Return missing/malformed field names for explicit art-direction evidence."""
    data = _as_dict(payload)
    issues: list[str] = []
    version = data.get("schema_version")
    if version not in {ART_DIRECTION_DOCUMENT_VERSION, ART_DIRECTION_IR_VERSION}:
        issues.append("schema_version")
    for key in (
        "asset_id",
        "object_family",
        "style_intent",
        "visual_hierarchy",
        "silhouette",
        "materials",
        "motifs",
        "surface_story",
        "platform",
    ):
        if not data.get(key):
            issues.append(key)
    if not (
        data.get("forbidden_failure_modes")
        or data.get("forbidden_visual_failure_modes")
    ):
        issues.append("forbidden_failure_modes")
    for key in (
        "style_intent",
        "visual_hierarchy",
        "silhouette",
        "materials",
        "motifs",
        "surface_story",
        "platform",
    ):
        if key in data and not isinstance(data.get(key), dict):
            issues.append(key)
    return sorted(dict.fromkeys(issues))


def _document_from_ir(ir: dict[str, Any]) -> dict[str, Any]:
    """Convert normalized IR into the external fixture document version."""
    return {
        "schema_version": ART_DIRECTION_DOCUMENT_VERSION,
        "asset_id": ir.get("asset_id"),
        "object_family": ir.get("object_family"),
        "style_intent": _as_dict(ir.get("style_intent")),
        "visual_hierarchy": _as_dict(ir.get("visual_hierarchy")),
        "silhouette": _as_dict(ir.get("silhouette")),
        "proportion_policy": _as_dict(ir.get("proportion_policy")),
        "materials": _as_dict(ir.get("materials")),
        "motifs": _as_dict(ir.get("motifs")),
        "surface_story": _as_dict(ir.get("surface_story")),
        "platform": _as_dict(ir.get("platform")),
        "forbidden_failure_modes": _string_list(ir.get("forbidden_failure_modes"))
        or _string_list(ir.get("forbidden_visual_failure_modes")),
    }


def infer_object_family(
    *,
    family: str,
    theme: str = "",
    keywords: list[str] | None = None,
    required_features: list[str] | None = None,
) -> str:
    """Infer a broad object family without hardcoding one asset."""
    haystack = " ".join(
        [
            family,
            theme,
            " ".join(keywords or []),
            " ".join(required_features or []),
        ]
    ).lower()
    for object_family, tokens in _OBJECT_FAMILY_TOKENS:
        if any(token in haystack for token in tokens):
            return object_family
    return "prop"


def _style_from_brief(brief: dict[str, Any]) -> dict[str, Any]:
    style = _as_dict(brief.get("style"))
    if style:
        return style
    tags = _string_list(brief.get("style_tags"))
    return {
        "theme": " ".join(tags) if tags else _string(brief.get("shape_language")),
        "keywords": tags,
        "forbidden": _string_list(brief.get("negative_constraints")),
    }


def _platform_from_brief(brief: dict[str, Any]) -> dict[str, Any]:
    platform = _as_dict(brief.get("platform_profile"))
    if platform:
        return platform
    return {"target": "game_runtime_proxy", "texture_budget": "proxy_or_deferred"}


def _family_from_brief(brief: dict[str, Any]) -> str:
    return _string(brief.get("family")) or _string(brief.get("role")) or "generic"


def _genre_from_style(style: dict[str, Any], keywords: list[str]) -> str:
    text = f"{style.get('theme', '')} {' '.join(keywords)}".lower()
    for token in ("fantasy", "sci-fi", "sci_fi", "industrial", "haunted", "roblox"):
        if token in text:
            return token.replace("_", "-")
    return "game"


def _primary_read(object_family: str, required_features: list[str]) -> str:
    if required_features:
        return f"{object_family} identity through {required_features[0]}"
    return f"{object_family} identity at thumbnail distance"


def _scale_anchors(object_family: str) -> list[str]:
    anchors = {
        "weapon": ["handle scale", "blade or striking surface length", "guard/affordance width"],
        "container": ["body volume", "lid/seam scale", "handle and foot clearance"],
        "machine": ["input/output affordance", "service panel scale", "button/readout scale"],
        "furniture": ["human contact surface", "support structure", "usable clearance"],
        "architecture": ["human passage scale", "hinge/frame thickness", "access affordance"],
        "environment_piece": ["world scale", "ground contact", "readable landmark feature"],
    }
    return anchors.get(object_family, ["primary volume", "functional affordance", "contact points"])


def _material_zone_goals(object_family: str, required_features: list[str]) -> list[str]:
    base = ["primary material", "secondary support material", "accent/focal material", "wear overlay"]
    if object_family == "machine":
        return [*base, "signal or emissive material"]
    if object_family == "furniture":
        return [*base, "touch/contact material"]
    if object_family == "weapon":
        return [*base, "edge or focal trim material"]
    if required_features:
        return [*base, f"feature-linked material: {required_features[0]}"]
    return base


def _motifs_from_style(object_family: str, keywords: list[str]) -> list[str]:
    motifs = [item for item in keywords if item not in {"hero", "game", "runtime"}][:4]
    defaults = {
        "weapon": ["edge line", "centerline", "guard transition"],
        "container": ["reinforced corners", "panel seams", "labels"],
        "machine": ["signal strips", "ports", "service panels"],
        "furniture": ["trim bands", "surface edge", "support rhythm"],
        "architecture": ["frame rhythm", "threshold", "hinge-side emphasis"],
        "environment_piece": ["landmark silhouette", "ground wear", "material strata"],
    }
    return list(dict.fromkeys(motifs + defaults.get(object_family, ["functional accents"])))


def _motif_placement_rules(object_family: str) -> list[str]:
    rules = {
        "weapon": ["place motifs on centerlines, guards, grips, and terminations"],
        "container": ["place motifs on panels, corners, latches, and decals"],
        "machine": ["place motifs around input/output affordances and service access"],
        "furniture": ["place motifs on usable edges, supports, and customer-facing faces"],
        "architecture": ["place motifs on frames, thresholds, hinges, and lock areas"],
        "environment_piece": ["place motifs on silhouette landmarks and contact/weathering zones"],
    }
    return rules.get(object_family, ["place motifs where they clarify function or silhouette"])


def _wear_logic(object_family: str) -> list[str]:
    common = ["convex edge wear", "contact polish", "recess grime"]
    if object_family == "weapon":
        return ["edge chips near striking surfaces", "hand polish on grip", *common]
    if object_family == "machine":
        return ["button touch wear", "output port grime", *common]
    if object_family == "furniture":
        return ["countertop rub", "front-edge scuffs", *common]
    return common


def _decal_logic(object_family: str) -> list[str]:
    if object_family == "machine":
        return ["status labels", "direction arrows", "interaction icons"]
    if object_family == "container":
        return ["warning labels", "serial marks", "orientation arrows"]
    if object_family == "furniture":
        return ["shop signage", "trim labels"]
    return ["only when decal improves function or theme read"]


def _reference_summary(reference: dict[str, Any]) -> dict[str, Any]:
    summary = _as_dict(reference.get("summary"))
    if summary:
        return {
            "has_reference_board": True,
            "silhouette_count": summary.get("silhouette_count", 0),
            "material_count": summary.get("material_count", 0),
            "negative_count": summary.get("negative_count", 0),
        }
    return {
        "has_reference_board": False,
        "silhouette_count": 0,
        "material_count": 0,
        "negative_count": 0,
    }


def _family_summary(family_metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        "coverage": family_metadata.get("coverage"),
        "required_rule_count": len(_as_list(family_metadata.get("required_rules"))),
        "missing_required_count": len(_as_list(family_metadata.get("missing_required_rules"))),
    }


def _universal_failures() -> list[str]:
    return [
        "random primitive stack",
        "unbounded procedural noise",
        "material zones without semantic purpose",
        "weak thumbnail read",
        "style mismatch between parts",
    ]


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _string(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _string_list(value: Any) -> list[str]:
    return [item for item in _as_list(value) if isinstance(item, str) and item]


__all__ = [
    "ART_DIRECTION_DOCUMENT_VERSION",
    "ART_DIRECTION_IR_VERSION",
    "QUALITY_DIMENSIONS",
    "build_art_direction_document",
    "build_art_direction_ir",
    "infer_object_family",
    "normalize_art_direction",
    "validate_art_direction_payload",
]
