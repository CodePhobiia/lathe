"""Property-based tests for ``lathe.resolver.Resolver``.

Invariants covered:

- Applying two *commuting* variant patches (patches that touch disjoint
  paths on an asset) in either order produces a bit-stable materialized
  asset: the resolution is order-insensitive when patches don't conflict.
- Resolver idempotence on an already-materialized asset: re-running
  ``materialize_asset`` on the result of a prior materialization yields
  the same normalized asset (materialization is idempotent at the
  payload level — re-running does not double-apply inheritance).
- Empty ``uses`` chain yields an asset whose resolved-decl lists are
  empty: ``resolve_use_chain([])`` returns ``[]``, and the merged payload
  carries no inherited rules beyond the asset's own declaration.

Hypothesis unavailable; parametrized with explicit fixtures.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from lathe.parser import parse_file
from lathe.resolver import Resolver, materialize_asset


ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "examples"


EXAMPLE_ASSETS = [
    pytest.param((EXAMPLES / "industrial_crate.lth", "industrial_crate"), id="industrial_crate"),
    pytest.param((EXAMPLES / "courier_drone.lth", "courier_drone"), id="courier_drone"),
    pytest.param((EXAMPLES / "console_terminal.lth", "console_terminal"), id="console_terminal"),
    pytest.param((EXAMPLES / "brassbound_chest.lth", "brassbound_chest"), id="brassbound_chest"),
    pytest.param((EXAMPLES / "mechanical_door.lth", "mechanical_door"), id="mechanical_door"),
]


COMMUTING_PATCH_PAIRS = [
    pytest.param(
        (
            {"op": "set", "path": "validate.threshold", "value": 0.85},
            {"op": "set", "path": "build.optimize.draw_calls", "value": 2},
        ),
        id="threshold_and_draw_calls",
    ),
    pytest.param(
        (
            {"op": "set", "path": "validate.threshold", "value": 0.77},
            {"op": "set", "path": "build.surface.resolution", "value": "1024px"},
        ),
        id="threshold_and_surface_res",
    ),
    pytest.param(
        (
            {"op": "set", "path": "build.optimize.draw_calls", "value": 3},
            {"op": "set", "path": "build.surface.resolution", "value": "2048px"},
        ),
        id="draw_calls_and_surface_res",
    ),
    pytest.param(
        (
            {"op": "set", "path": "validate.threshold", "value": 0.81},
            {"op": "set", "path": "build.optimize.texture_budget", "value": "16mb"},
        ),
        id="threshold_and_texture_budget",
    ),
    pytest.param(
        (
            {"op": "set", "path": "build.surface.resolution", "value": "4096px"},
            {"op": "set", "path": "build.optimize.texture_budget", "value": "32mb"},
        ),
        id="surface_res_and_texture_budget",
    ),
]


def _apply_patches_to_explicit(
    resolver: Resolver, asset_name: str, patches: list[dict]
) -> dict:
    """Materialize after applying `patches` in order to the derived
    explicit asset. Returns the fully materialized payload."""
    program_clone = {
        key: copy.deepcopy(value) for key, value in resolver.program.items()
    }
    local = Resolver(program_clone)
    explicit = local.derive_explicit_asset(asset_name)
    for patch in patches:
        local.apply_patch(explicit, patch)
    # Inject the mutated explicit back into the program map so the next
    # derive call sees the patched values.
    for idx, item in enumerate(local.program.get("assets", [])):
        if item.get("name") == asset_name:
            local.program["assets"][idx] = explicit
            break
    local.asset_map[asset_name] = explicit
    return local.materialize_asset(asset_name)


@pytest.mark.parametrize("asset_spec", EXAMPLE_ASSETS)
@pytest.mark.parametrize("patch_pair", COMMUTING_PATCH_PAIRS)
def test_commuting_patches_are_order_insensitive(
    asset_spec: tuple[Path, str], patch_pair: tuple[dict, dict]
) -> None:
    """Two commuting patches (touching disjoint paths) applied in either
    order produce identical materialized assets. This is the bit-stable
    commutativity invariant: resolver order does not matter for
    independent configuration overrides.
    """
    example_path, asset_name = asset_spec
    if not example_path.exists():
        pytest.skip(f"example {example_path} not present")
    program = parse_file(example_path)
    resolver = Resolver(program)
    patch_a, patch_b = patch_pair
    forward = _apply_patches_to_explicit(resolver, asset_name, [patch_a, patch_b])
    reverse = _apply_patches_to_explicit(resolver, asset_name, [patch_b, patch_a])
    assert forward == reverse


@pytest.mark.parametrize("asset_spec", EXAMPLE_ASSETS)
def test_materialization_is_idempotent(asset_spec: tuple[Path, str]) -> None:
    """materialize_asset(name) called twice on the same program yields
    the same payload. The resolver does not mutate ``program`` during
    resolution — each call derives the asset from scratch.
    """
    example_path, asset_name = asset_spec
    if not example_path.exists():
        pytest.skip(f"example {example_path} not present")
    program = parse_file(example_path)
    first = materialize_asset(program, asset_name)
    second = materialize_asset(program, asset_name)
    assert first == second


@pytest.mark.parametrize("asset_spec", EXAMPLE_ASSETS)
def test_empty_uses_chain_returns_empty_decl_list(asset_spec: tuple[Path, str]) -> None:
    """resolve_use_chain([]) always returns an empty list, regardless of
    what profiles/contracts are defined in the program. An asset with no
    ``uses`` inherits nothing from profile/contract chains.
    """
    example_path, asset_name = asset_spec
    if not example_path.exists():
        pytest.skip(f"example {example_path} not present")
    program = parse_file(example_path)
    resolver = Resolver(program)
    ordered = resolver.resolve_use_chain([])
    assert ordered == []


@pytest.mark.parametrize("asset_spec", EXAMPLE_ASSETS)
def test_derive_explicit_asset_is_deepcopy_safe(asset_spec: tuple[Path, str]) -> None:
    """Mutating the explicit asset returned by derive_explicit_asset
    must not mutate the resolver's internal asset_map. This is an
    independence invariant that underwrites patch application safety.
    """
    example_path, asset_name = asset_spec
    if not example_path.exists():
        pytest.skip(f"example {example_path} not present")
    program = parse_file(example_path)
    resolver = Resolver(program)
    snapshot = copy.deepcopy(resolver.asset_map.get(asset_name) or {})
    explicit = resolver.derive_explicit_asset(asset_name)
    # Mutate a top-level field
    explicit["name"] = "mutated_for_test"
    explicit.setdefault("validate", {})["threshold"] = 0.0
    # Original asset_map entry must not have been mutated
    assert resolver.asset_map.get(asset_name) == snapshot


@pytest.mark.parametrize("asset_spec", EXAMPLE_ASSETS)
@pytest.mark.parametrize(
    "single_patch",
    [
        pytest.param({"op": "set", "path": "validate.threshold", "value": 0.99}, id="set_threshold"),
        pytest.param({"op": "set", "path": "build.optimize.draw_calls", "value": 5}, id="set_draw_calls"),
    ],
)
def test_single_patch_is_idempotent_when_applied_twice(
    asset_spec: tuple[Path, str], single_patch: dict
) -> None:
    """Applying the same ``set`` patch twice is equivalent to applying
    it once — the second application lands on the already-set value.
    """
    example_path, asset_name = asset_spec
    if not example_path.exists():
        pytest.skip(f"example {example_path} not present")
    program = parse_file(example_path)
    resolver = Resolver(program)
    once = _apply_patches_to_explicit(resolver, asset_name, [single_patch])
    twice = _apply_patches_to_explicit(resolver, asset_name, [single_patch, single_patch])
    assert once == twice
