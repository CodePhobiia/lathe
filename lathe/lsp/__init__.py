from __future__ import annotations

from typing import Any


def build_symbol_index(program: dict[str, Any]) -> dict[str, Any]:
    collections = [
        "profiles",
        "contracts",
        "critics",
        "families",
        "components",
        "assemblies",
        "traits",
        "mechanisms",
        "materials",
        "palettes",
        "style_packs",
        "repair_policies",
        "fixtures",
        "tests",
        "benchmarks",
        "spaces",
        "assets",
        "variants",
    ]
    symbols = []
    for collection in collections:
        for item in program.get(collection, []):
            symbols.append({"kind": collection[:-1], "name": item["name"]})
    return {"module": program.get("module"), "symbols": symbols}
