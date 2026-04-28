"""Patch API: apply structured patches to Lathe sources.

Used by the ``lathe patch`` CLI and by tests to mutate assets in a
well-defined, reviewable way.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

# re-export — authoritative definition lives in lathe/errors.py
from .errors import PatchAPIError
from .normalizer import normalize_program


def _decl(program: dict[str, Any], collection: str, name: str) -> dict[str, Any]:
    for item in program.get(collection, []):
        if item["name"] == name:
            return item
    raise PatchAPIError(f"Unknown {collection[:-1]} '{name}'")


def add_component_to_family(program: dict[str, Any], family_name: str, component_name: str) -> dict[str, Any]:
    """Add component to family.

    Args:
        program: program argument.
        family_name: family_name argument.
        component_name: component_name argument.

    Returns:
        The result.
    """
    updated = deepcopy(program)
    family = _decl(updated, "families", family_name)
    components = list(family.setdefault("assembly", {}).get("components", []))
    if component_name not in components:
        components.append(component_name)
    family["assembly"]["components"] = components
    return normalize_program(updated)


def change_repair_policy(program: dict[str, Any], asset_name: str, repair_policy_name: str) -> dict[str, Any]:
    """Change repair policy.

    Args:
        program: program argument.
        asset_name: asset_name argument.
        repair_policy_name: repair_policy_name argument.

    Returns:
        The result.
    """
    updated = deepcopy(program)
    asset = _decl(updated, "assets", asset_name)
    asset.setdefault("repair_policy", {})["use"] = repair_policy_name
    return normalize_program(updated)


def update_material_palette(program: dict[str, Any], asset_name: str, palette_name: str) -> dict[str, Any]:
    """Update material palette.

    Args:
        program: program argument.
        asset_name: asset_name argument.
        palette_name: palette_name argument.

    Returns:
        The result.
    """
    updated = deepcopy(program)
    asset = _decl(updated, "assets", asset_name)
    asset.setdefault("surface", {})["palette"] = palette_name
    return normalize_program(updated)


def widen_search_bounds(
    program: dict[str, Any], space_name: str, variable_name: str, lower: Any, upper: Any
) -> dict[str, Any]:
    """Widen search bounds.

    Args:
        program: program argument.
        space_name: space_name argument.
        variable_name: variable_name argument.
        lower: lower argument.
        upper: upper argument.

    Returns:
        The result.
    """
    updated = deepcopy(program)
    space = _decl(updated, "spaces", space_name)
    vary = list(space.get("vary", []))
    for item in vary:
        if item.get("path") == variable_name:
            item["domain"] = {"type": "range", "from": lower, "to": upper}
            break
    else:
        vary.append({"path": variable_name, "domain": {"type": "range", "from": lower, "to": upper}})
    space["vary"] = vary
    return normalize_program(updated)


def freeze_dimension(program: dict[str, Any], space_name: str, variable_name: str) -> dict[str, Any]:
    """Freeze dimension.

    Args:
        program: program argument.
        space_name: space_name argument.
        variable_name: variable_name argument.

    Returns:
        The result.
    """
    updated = deepcopy(program)
    space = _decl(updated, "spaces", space_name)
    frozen = list(space.get("freeze", []))
    if variable_name not in frozen:
        frozen.append(variable_name)
    space["freeze"] = frozen
    return normalize_program(updated)


def add_benchmark_fixture(program: dict[str, Any], benchmark_name: str, fixture_name: str) -> dict[str, Any]:
    """Add benchmark fixture.

    Args:
        program: program argument.
        benchmark_name: benchmark_name argument.
        fixture_name: fixture_name argument.

    Returns:
        The result.
    """
    updated = deepcopy(program)
    benchmark = _decl(updated, "benchmarks", benchmark_name)
    fixtures = list(benchmark.setdefault("values", {}).get("compare_against", []))
    if fixture_name not in fixtures:
        fixtures.append(fixture_name)
    benchmark["values"]["compare_against"] = fixtures
    return normalize_program(updated)
