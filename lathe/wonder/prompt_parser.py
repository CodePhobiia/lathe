"""Deterministic Wonder prompt parser for the Skyborne capstone."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from ..forge import (
    DEFAULT_SKYBORNE_COUNTS,
    SKYBORNE_KIT_ID,
    SKYBORNE_STYLE_PACK_ID,
    SkyborneIntent,
)
from .prompt_keywords import (
    ARCHETYPE_KEYWORDS,
    DIRECTOR_TERM_KEYWORDS,
    NUMBER_WORDS,
    ROLE_KEYWORDS,
    STYLE_KEYWORDS,
)

PROMPT_PARSER_VERSION = "lathe.wonder.prompt_parser_v1"


@dataclass(frozen=True)
class ParsedWonderPrompt:
    """Typed deterministic prompt extraction for ``wonder build``."""

    prompt: str
    seed: int
    world_kind: str
    kit_id: str
    style_pack_id: str
    asset_counts: Mapping[str, int]
    director_terms: tuple[str, ...]
    keyword_hits: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    parser_version: str = PROMPT_PARSER_VERSION

    def to_skyborne_intent(self) -> SkyborneIntent:
        return SkyborneIntent(
            prompt=self.prompt,
            asset_counts=dict(self.asset_counts),
            style_pack_id=self.style_pack_id,
            kit_id=self.kit_id,
            director_terms=tuple(self.director_terms),
            world_kind=self.world_kind,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.parser_version,
            "prompt": self.prompt,
            "seed": self.seed,
            "world_kind": self.world_kind,
            "kit_id": self.kit_id,
            "style_pack_id": self.style_pack_id,
            "asset_counts": dict(sorted(self.asset_counts.items())),
            "director_terms": list(self.director_terms),
            "keyword_hits": {k: list(v) for k, v in sorted(self.keyword_hits.items())},
        }


def _contains(text: str, phrase: str) -> bool:
    return re.search(rf"\b{re.escape(phrase)}\b", text) is not None


def _keyword_hits(text: str, table: Mapping[str, tuple[str, ...]]) -> dict[str, tuple[str, ...]]:
    hits: dict[str, tuple[str, ...]] = {}
    for key, phrases in table.items():
        matched = tuple(phrase for phrase in phrases if _contains(text, phrase))
        if matched:
            hits[key] = matched
    return hits


def _parse_count_for_role(text: str, role: str) -> int | None:
    phrases = ROLE_KEYWORDS.get(role, ())
    for phrase in sorted(phrases, key=len, reverse=True):
        pattern = rf"\b(?P<count>\d+|{'|'.join(NUMBER_WORDS)})\s+{re.escape(phrase)}\b"
        match = re.search(pattern, text)
        if not match:
            continue
        token = match.group("count")
        if token.isdigit():
            return int(token)
        return NUMBER_WORDS[token]
    return None


def _resolve_world_kind(text: str) -> str:
    hits = _keyword_hits(text, ARCHETYPE_KEYWORDS)
    if "village" in hits:
        return "floating_fantasy_village"
    if "temple" in hits:
        return "floating_fantasy_temple"
    if "outpost" in hits:
        return "floating_fantasy_outpost"
    if "vista" in hits:
        return "floating_fantasy_vista"
    return "floating_fantasy_village"


def _resolve_style_pack(text: str) -> str:
    style_hits = _keyword_hits(text, STYLE_KEYWORDS)
    if "lowpoly_fantasy_sunset_crystal_v1" in style_hits:
        return SKYBORNE_STYLE_PACK_ID
    return SKYBORNE_STYLE_PACK_ID


def _resolve_director_terms(text: str) -> tuple[str, ...]:
    hits = _keyword_hits(text, DIRECTOR_TERM_KEYWORDS)
    terms = [term for term in DIRECTOR_TERM_KEYWORDS if term in hits]
    for required in (
        "stylized_low_poly_fantasy",
        "sunset_crystal_palette",
        "faceted_cliffside",
    ):
        if required not in terms:
            terms.append(required)
    return tuple(terms)


def parse_wonder_prompt(prompt: str, *, seed: int = 0) -> ParsedWonderPrompt:
    """Parse a prompt into the deterministic Skyborne request shape."""

    normalized = " ".join(str(prompt).lower().split())
    counts = dict(DEFAULT_SKYBORNE_COUNTS)
    for role in ROLE_KEYWORDS:
        parsed_count = _parse_count_for_role(normalized, role)
        if parsed_count is not None:
            counts[role] = parsed_count
        elif any(_contains(normalized, phrase) for phrase in ROLE_KEYWORDS[role]):
            counts.setdefault(role, DEFAULT_SKYBORNE_COUNTS.get(role, 1))

    hits: dict[str, tuple[str, ...]] = {}
    hits.update({f"archetype:{k}": v for k, v in _keyword_hits(normalized, ARCHETYPE_KEYWORDS).items()})
    hits.update({f"role:{k}": v for k, v in _keyword_hits(normalized, ROLE_KEYWORDS).items()})
    hits.update({f"style:{k}": v for k, v in _keyword_hits(normalized, STYLE_KEYWORDS).items()})
    hits.update(
        {f"director:{k}": v for k, v in _keyword_hits(normalized, DIRECTOR_TERM_KEYWORDS).items()}
    )
    return ParsedWonderPrompt(
        prompt=str(prompt),
        seed=seed,
        world_kind=_resolve_world_kind(normalized),
        kit_id=SKYBORNE_KIT_ID,
        style_pack_id=_resolve_style_pack(normalized),
        asset_counts=dict(sorted(counts.items())),
        director_terms=_resolve_director_terms(normalized),
        keyword_hits=hits,
    )


__all__ = [
    "PROMPT_PARSER_VERSION",
    "ParsedWonderPrompt",
    "parse_wonder_prompt",
]
