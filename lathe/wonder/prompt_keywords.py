"""Deterministic keyword tables for Wonder prompt parsing."""

from __future__ import annotations

NUMBER_WORDS: dict[str, int] = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "twelve": 12,
}

ARCHETYPE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "village": ("village", "hamlet", "settlement"),
    "vista": ("vista", "overlook", "panorama"),
    "outpost": ("outpost", "camp"),
    "temple": ("temple", "shrine"),
}

ROLE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "floating_island": ("floating island", "island"),
    "cottage": ("cottage", "cottages"),
    "elder_house": ("hero inn", "elder house", "hero house", "inn"),
    "pine_tree": ("pine", "pines", "tree", "trees"),
    "crystal_cluster": ("crystal", "crystals", "crystal cluster"),
    "rope_bridge": ("rope bridge", "bridge"),
    "waterfall_ribbon": ("waterfall", "waterfall ribbon"),
    "stone_path_segment": ("stone path", "path", "paths"),
    "lantern": ("lantern", "lanterns"),
    "fence_segment": ("fence", "fences"),
}

STYLE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "lowpoly_fantasy_sunset_crystal_v1": (
        "fantasy",
        "sunset",
        "low poly",
        "low-poly",
        "crystal",
    )
}

DIRECTOR_TERM_KEYWORDS: dict[str, tuple[str, ...]] = {
    "stylized_low_poly_fantasy": ("fantasy", "low poly", "low-poly", "stylized"),
    "sunset_crystal_palette": ("sunset", "crystal", "violet"),
    "faceted_cliffside": ("floating island", "cliff", "cliffside", "island"),
}

__all__ = [
    "ARCHETYPE_KEYWORDS",
    "DIRECTOR_TERM_KEYWORDS",
    "NUMBER_WORDS",
    "ROLE_KEYWORDS",
    "STYLE_KEYWORDS",
]
