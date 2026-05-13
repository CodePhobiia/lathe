"""``lathe.knowledge.morphology_profile_v1`` — typed morphology pack loader.

Per ``docs/research/newresearch.md`` §2: family-blind ≠ morphology-blind.
A door knows it has a hinge line on a long vertical edge and a handle
at ergonomic height; a crate knows it has corners, panels, and a lid
seam. That knowledge belongs in declarative profiles, not in
per-asset code branches.

A ``MorphologyProfile`` carries:

  - body archetype + expected aspect ratios
  - typed parts ladder (required / optional)
  - anchor emitter declarations (host-side anchor recipes)
  - default relations (which source roles attach to which target roles)

The synthesizer's Stage 1 (resolve_context) looks up the profile via
``FamilyAlias.morphology_profile_id`` and threads it into the
construction context for later stages to consume.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

CONTRACT_VERSION = "lathe.knowledge.morphology_profile_v1"

_KNOWLEDGE_ROOT = Path(__file__).resolve().parents[4] / "std" / "procedural" / "knowledge" / "morphology"


@dataclass(frozen=True)
class BodyArchetype:
    """How the primary volume is shaped.

    - ``shape``: ``rounded_box``, ``vertical_panel``, ``cylinder``, ``revolve``, ``subdivision_box``.
    - ``long_axis``: which axis is the dominant length (``"X"``, ``"Y"``, ``"Z"`` or ``"X_or_Y"``).
    - ``aspect_bounds``: per-axis min/max as fractions of the longest dimension.
    """

    shape: str = "rounded_box"
    long_axis: str = "X"
    aspect_bounds: Mapping[str, tuple[float, float]] = field(
        default_factory=lambda: {"x": (0.5, 1.0), "y": (0.3, 1.0), "z": (0.3, 1.0)}
    )


@dataclass(frozen=True)
class PartLadderEntry:
    """One entry in the typed parts ladder.

    - ``role``: canonical part role (``primary_volume``, ``handle``, ``hinge``, ``panel``, ...).
    - ``required``: whether the class invariant demands this part.
    - ``min_count`` / ``max_count``: cardinality bounds (e.g. 2 handles, 1 lid_seam).
    - ``node_type``: canonical generator NODE_TYPE.
    """

    role: str
    required: bool = False
    min_count: int = 0
    max_count: int = 8
    node_type: str = ""


@dataclass(frozen=True)
class AnchorEmitterDecl:
    """Declarative anchor emission spec attached to the morphology profile.

    The actual emitter implementation lives in
    ``lathe/asset_quality/procedural_synthesizer/anchors/`` —  this
    record names which emitter to invoke and any selector overrides.
    """

    role: str
    selector: str = "exterior_face"  # exterior_face, long_vertical_edge, exterior_corner, etc.
    side_candidates: tuple[str, ...] = ()
    height_range_m: tuple[float, float] | None = None


@dataclass(frozen=True)
class DefaultRelation:
    """Default placement relation: source_role → target_role."""

    source_role: str
    relation: str
    target_role: str


@dataclass(frozen=True)
class MorphologyProfile:
    """A typed morphology pack — declarative + family-blind."""

    profile_id: str
    description: str
    body: BodyArchetype
    parts_ladder: tuple[PartLadderEntry, ...]
    anchor_emitters: tuple[AnchorEmitterDecl, ...]
    default_relations: tuple[DefaultRelation, ...]
    domain: str = "hard_surface"

    def required_roles(self) -> tuple[str, ...]:
        return tuple(p.role for p in self.parts_ladder if p.required)

    def role_min_count(self, role: str) -> int:
        for p in self.parts_ladder:
            if p.role == role:
                return p.min_count
        return 0


def _entry_from_dict(d: Mapping[str, Any]) -> PartLadderEntry:
    return PartLadderEntry(
        role=str(d.get("role") or ""),
        required=bool(d.get("required", False)),
        min_count=int(d.get("min_count") or (1 if d.get("required") else 0)),
        max_count=int(d.get("max_count") or 8),
        node_type=str(d.get("node_type") or d.get("role") or ""),
    )


def _emitter_from_dict(d: Mapping[str, Any]) -> AnchorEmitterDecl:
    raw_height = d.get("height_range_m")
    height_range: tuple[float, float] | None
    if isinstance(raw_height, list) and len(raw_height) == 2:
        try:
            height_range = (float(raw_height[0]), float(raw_height[1]))
        except (TypeError, ValueError):
            height_range = None
    else:
        height_range = None
    return AnchorEmitterDecl(
        role=str(d.get("role") or ""),
        selector=str(d.get("selector") or "exterior_face"),
        side_candidates=tuple(d.get("side_candidates") or ()),
        height_range_m=height_range,
    )


def _relation_from_dict(d: Mapping[str, Any]) -> DefaultRelation:
    return DefaultRelation(
        source_role=str(d.get("source_role") or ""),
        relation=str(d.get("relation") or "attached_to"),
        target_role=str(d.get("target_role") or ""),
    )


def profile_from_dict(payload: Mapping[str, Any]) -> MorphologyProfile:
    body_raw = payload.get("body") or {}
    aspect_raw = body_raw.get("expected_aspect") or {}
    aspect_bounds: dict[str, tuple[float, float]] = {}
    for axis in ("x", "y", "z"):
        bound = aspect_raw.get(axis)
        if isinstance(bound, list) and len(bound) == 2:
            try:
                aspect_bounds[axis] = (float(bound[0]), float(bound[1]))
                continue
            except (TypeError, ValueError):
                pass
        aspect_bounds[axis] = (0.3, 1.0)
    body = BodyArchetype(
        shape=str(body_raw.get("archetype") or "rounded_box"),
        long_axis=str(body_raw.get("long_axis") or "X"),
        aspect_bounds=aspect_bounds,
    )
    parts = tuple(
        _entry_from_dict(p) for p in (payload.get("parts_ladder") or []) if isinstance(p, Mapping)
    )
    emitters = tuple(
        _emitter_from_dict(e) for e in (payload.get("anchor_emitters") or []) if isinstance(e, Mapping)
    )
    relations = tuple(
        _relation_from_dict(r) for r in (payload.get("default_relations") or []) if isinstance(r, Mapping)
    )
    return MorphologyProfile(
        profile_id=str(payload.get("id") or payload.get("profile_id") or ""),
        description=str(payload.get("description") or ""),
        body=body,
        parts_ladder=parts,
        anchor_emitters=emitters,
        default_relations=relations,
        domain=str(payload.get("domain") or "hard_surface"),
    )


_PROFILE_CACHE: dict[str, MorphologyProfile] | None = None


def load_all_morphology_profiles(root: Path | None = None) -> Mapping[str, MorphologyProfile]:
    """Lazy-loaded registry. Mirrors ``load_all_alias_packs`` shape."""
    global _PROFILE_CACHE
    if _PROFILE_CACHE is not None:
        return _PROFILE_CACHE
    knowledge_root = root or _KNOWLEDGE_ROOT
    if not knowledge_root.exists():
        _PROFILE_CACHE = {}
        return _PROFILE_CACHE
    profiles: dict[str, MorphologyProfile] = {}
    for json_path in sorted(knowledge_root.glob("*.json")):
        try:
            payload = json.loads(json_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, Mapping):
            continue
        profile = profile_from_dict(payload)
        if profile.profile_id:
            profiles[profile.profile_id] = profile
    _PROFILE_CACHE = profiles
    return profiles


def reset_morphology_profile_cache() -> None:
    """Test hook — clears the lazy registry."""
    global _PROFILE_CACHE
    _PROFILE_CACHE = None


__all__ = [
    "CONTRACT_VERSION",
    "BodyArchetype",
    "PartLadderEntry",
    "AnchorEmitterDecl",
    "DefaultRelation",
    "MorphologyProfile",
    "profile_from_dict",
    "load_all_morphology_profiles",
    "reset_morphology_profile_cache",
]
