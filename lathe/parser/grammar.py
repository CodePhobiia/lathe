"""Lark grammar loader and parse driver for the Lathe source language.

Builds (and caches to ``.lathe_lark_cache``) the Lark parser from
``grammar/lathe.lark`` and exposes the formal fallback parse entry
used when the fast parser declines.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

# re-export — authoritative definitions live in lathe/errors.py
from ..errors import DuplicateFieldError, LatheParseError  # noqa: F401


def _find_grammar_path() -> Path:
    here = Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        candidate = parent / "grammar" / "lathe.lark"
        if candidate.exists():
            return candidate
    raise FileNotFoundError("Could not locate grammar/lathe.lark")


GRAMMAR_PATH = _find_grammar_path()
REPO_ROOT = GRAMMAR_PATH.parent.parent


_UNIT_RE = re.compile(
    r"^(?P<value>-?(?:\d+\.\d+|\d+))(?P<unit>mm|cm|m|deg|rad|g|kg|ms|s|kb|mb|gb|px|px_per_m|px_per_cm)$"
)

PROGRAM_ARRAY_KEYS = [
    "profiles",
    "contracts",
    "critics",
    "libraries",
    "kits",
    "patterns",
    "families",
    "components",
    "assemblies",
    "traits",
    "mechanisms",
    "materials",
    "surface_programs",
    "surface_backends",
    "surface_policies",
    "decal_libraries",
    "mask_programs",
    "trim_sheets",
    "palettes",
    "style_packs",
    "style_bridges",
    "reference_sets",
    "reconstruct_policies",
    "adapt_policies",
    "assembly_policies",
    "fit_profiles",
    "transfer_rules",
    "execution_profiles",
    "render_fixtures",
    "bake_profiles",
    "library_bindings",
    "material_graphs",
    "inspection_policies",
    "asset_class_profiles",
    "wfc_tilesets",
    "wfc_adjacencies",
    "terrain_programs",
    "subdivision_finishings",
    "f_rep_programs",
    "repair_policies",
    "fixtures",
    "tests",
    "benchmarks",
    "spaces",
    "worlds",
    "scenes",
    "assets",
    "variants",
]


def _empty_program() -> dict[str, Any]:
    return {
        "module": None,
        "imports": [],
        "profiles": [],
        "contracts": [],
        "critics": [],
        "libraries": [],
        "kits": [],
        "patterns": [],
        "families": [],
        "components": [],
        "assemblies": [],
        "traits": [],
        "mechanisms": [],
        "materials": [],
        "surface_programs": [],
        "surface_backends": [],
        "surface_policies": [],
        "decal_libraries": [],
        "mask_programs": [],
        "trim_sheets": [],
        "palettes": [],
        "style_packs": [],
        "style_bridges": [],
        "reference_sets": [],
        "reconstruct_policies": [],
        "adapt_policies": [],
        "assembly_policies": [],
        "fit_profiles": [],
        "transfer_rules": [],
        "execution_profiles": [],
        "render_fixtures": [],
        "bake_profiles": [],
        "library_bindings": [],
        "material_graphs": [],
        "inspection_policies": [],
        "asset_class_profiles": [],
        "vegetation_species": [],
        "vegetation_kits": [],
        "wind_programs": [],
        "volume_programs": [],
        "wfc_tilesets": [],
        "wfc_adjacencies": [],
        "terrain_programs": [],
        "subdivision_finishings": [],
        "f_rep_programs": [],
        "repair_policies": [],
        "fixtures": [],
        "tests": [],
        "benchmarks": [],
        "spaces": [],
        "worlds": [],
        "scenes": [],
        "assets": [],
        "variants": [],
    }


def _num(text: str) -> int | float:
    if any(c in text for c in ".eE"):
        return float(text)
    return int(text)


def _dedupe_keep_first(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            out.append(value)
    return out


def _set_nested(target: dict[str, Any], path: str, value: Any, context: str) -> None:
    parts = path.split(".")
    cursor = target
    for part in parts[:-1]:
        nxt = cursor.get(part)
        if nxt is None:
            nxt = {}
            cursor[part] = nxt
        elif not isinstance(nxt, dict):
            raise DuplicateFieldError(path, context)
        cursor = nxt
    leaf = parts[-1]
    if leaf in cursor:
        raise DuplicateFieldError(path, context)
    cursor[leaf] = value
