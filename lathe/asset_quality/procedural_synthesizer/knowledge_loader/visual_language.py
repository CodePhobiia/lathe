"""VisualLanguage knowledge pack — cross-class art direction.

Per ``docs/research/newresearch.md`` §14: separating style/visual
language from class morphology lets us produce industrial-crate,
fantasy-crate, sci-fi-crate, abandoned-crate — same class rules,
different style overlays.

A VisualLanguage carries:

  - silhouette_bias: which forms the language prefers vs avoids
  - motifs: feature types that mark the language (preferred / rare / forbidden)
  - palette: body / accent color groups
  - materials: material_class → archetype pinning
  - wear: condition-axis defaults
  - feature_weight_overrides: density multipliers per feature_role

Aliases reference a VisualLanguage via ``visual_language_id``. Stage 1's
context resolver loads it alongside style/policies/morphology.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

CONTRACT_VERSION = "lathe.knowledge.visual_language_v1"

_KNOWLEDGE_ROOT = Path(__file__).resolve().parents[4] / "std" / "procedural" / "knowledge" / "visual_language"


@dataclass(frozen=True)
class SilhouetteBias:
    forms_preferred: tuple[str, ...] = ()
    forms_avoid: tuple[str, ...] = ()


@dataclass(frozen=True)
class MotifSet:
    preferred: tuple[str, ...] = ()
    rare: tuple[str, ...] = ()
    forbidden: tuple[str, ...] = ()


@dataclass(frozen=True)
class PaletteSet:
    body: tuple[str, ...] = ()
    accent: tuple[str, ...] = ()
    emissive: tuple[str, ...] = ()


@dataclass(frozen=True)
class WearDefaults:
    edge_polish: float = 0.3
    dust_in_seams: float = 0.4
    paint_chipping: float = 0.2
    oil_staining: float = 0.2
    rust_probability: float = 0.2


@dataclass(frozen=True)
class VisualLanguage:
    """A complete visual-language pack."""

    visual_language_id: str
    description: str
    silhouette_bias: SilhouetteBias
    motifs: MotifSet
    palette: PaletteSet
    materials: Mapping[str, str] = field(default_factory=dict)
    wear: WearDefaults = field(default_factory=WearDefaults)
    feature_weight_overrides: Mapping[str, float] = field(default_factory=dict)

    def weight_for_feature(self, feature_role: str, default: float = 1.0) -> float:
        if not isinstance(self.feature_weight_overrides, Mapping):
            return default
        return float(self.feature_weight_overrides.get(feature_role, default))


def visual_language_from_dict(payload: Mapping[str, Any]) -> VisualLanguage:
    sil_raw = payload.get("silhouette_bias") or {}
    sil = SilhouetteBias(
        forms_preferred=tuple(sil_raw.get("forms") or sil_raw.get("preferred") or ()),
        forms_avoid=tuple(sil_raw.get("avoid") or ()),
    )
    motifs_raw = payload.get("motifs") or {}
    motifs = MotifSet(
        preferred=tuple(motifs_raw.get("preferred") or ()),
        rare=tuple(motifs_raw.get("rare") or ()),
        forbidden=tuple(motifs_raw.get("forbidden") or ()),
    )
    palette_raw = payload.get("palette") or {}
    palette = PaletteSet(
        body=tuple(palette_raw.get("body") or ()),
        accent=tuple(palette_raw.get("accent") or ()),
        emissive=tuple(palette_raw.get("emissive") or ()),
    )
    wear_raw = payload.get("wear") or {}
    wear = WearDefaults(
        edge_polish=float(wear_raw.get("edge_polish", 0.3)),
        dust_in_seams=float(wear_raw.get("dust_in_seams", 0.4)),
        paint_chipping=float(wear_raw.get("paint_chipping", 0.2)),
        oil_staining=float(wear_raw.get("oil_staining", 0.2)),
        rust_probability=float(wear_raw.get("rust_probability", 0.2)),
    )
    materials_raw = payload.get("materials") or {}
    materials = {str(k): str(v) for k, v in materials_raw.items()} if isinstance(materials_raw, Mapping) else {}
    weights_raw = payload.get("feature_weight_overrides") or {}
    weights = (
        {str(k): float(v) for k, v in weights_raw.items()}
        if isinstance(weights_raw, Mapping)
        else {}
    )
    return VisualLanguage(
        visual_language_id=str(payload.get("id") or payload.get("visual_language_id") or ""),
        description=str(payload.get("description") or ""),
        silhouette_bias=sil,
        motifs=motifs,
        palette=palette,
        materials=materials,
        wear=wear,
        feature_weight_overrides=weights,
    )


_LANGUAGE_CACHE: dict[str, VisualLanguage] | None = None


def load_all_visual_languages(root: Path | None = None) -> Mapping[str, VisualLanguage]:
    global _LANGUAGE_CACHE
    if _LANGUAGE_CACHE is not None:
        return _LANGUAGE_CACHE
    knowledge_root = root or _KNOWLEDGE_ROOT
    if not knowledge_root.exists():
        _LANGUAGE_CACHE = {}
        return _LANGUAGE_CACHE
    packs: dict[str, VisualLanguage] = {}
    for json_path in sorted(knowledge_root.glob("*.json")):
        try:
            payload = json.loads(json_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, Mapping):
            continue
        language = visual_language_from_dict(payload)
        if language.visual_language_id:
            packs[language.visual_language_id] = language
    _LANGUAGE_CACHE = packs
    return packs


def reset_visual_language_cache() -> None:
    global _LANGUAGE_CACHE
    _LANGUAGE_CACHE = None


__all__ = [
    "CONTRACT_VERSION",
    "SilhouetteBias",
    "MotifSet",
    "PaletteSet",
    "WearDefaults",
    "VisualLanguage",
    "visual_language_from_dict",
    "load_all_visual_languages",
    "reset_visual_language_cache",
]
