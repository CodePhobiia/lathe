"""Normalizer property tests (BL-38, Plan 08 Phase 9 — Stability).

Property: ``normalize_program`` is **idempotent** — applying it twice
yields the same dict as applying it once. This is the contract the
resolver and checker depend on: once a program is normalized, further
normalization is a no-op.

We also assert idempotence of ``normalize_asset`` over hand-shaped
asset dicts.

Stand-in for the BL-24 golden replay test (which already lives at
``tests/golden/test_hero_bundles.py``). Hypothesis builds normalized-
AST-shaped dicts directly rather than going through ``parse_text``,
giving the normalizer a wider input distribution than any source-text
strategy could.
"""

from __future__ import annotations

import os
from copy import deepcopy
from typing import Any

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from lathe.normalizer import normalize_asset, normalize_program
from lathe.parser import parse_text

pytestmark = pytest.mark.fuzz


# Scale knob (BL-42): default 200 (fast, PR CI / local smoke);
# nightly cron sets LATHE_FUZZ_EXTENDED=1 for the full 10k sweep.
_EXTENDED = os.environ.get("LATHE_FUZZ_EXTENDED") == "1"
MAX_EXAMPLES = 10000 if _EXTENDED else 200


# -- helpers -------------------------------------------------------------


_IDENT = st.from_regex(r"[a-z][a-z0-9_]{0,8}", fullmatch=True)


def _assert_idempotent_program(program: dict) -> None:
    once = normalize_program(deepcopy(program))
    twice = normalize_program(deepcopy(once))
    assert once == twice, "normalize_program not idempotent: differs on second pass."


def _assert_idempotent_asset(asset: dict) -> None:
    once = normalize_asset(deepcopy(asset))
    twice = normalize_asset(deepcopy(once))
    assert once == twice, "normalize_asset not idempotent."


# -- strategies ----------------------------------------------------------


@st.composite
def _random_asset_node(draw: Any) -> dict:
    """Build a parser-emitted asset node dict with random fields."""
    node: dict[str, Any] = {
        "node_type": "asset",
        "name": draw(_IDENT),
        "kind": draw(st.sampled_from(["prop", "vehicle", "container", "architecture", "creature", "weapon"])),
        "from": "",
        "uses": [],
        "refs": {},
        "intent": {},
        "geometry": {},
        "features": {},
        "surface": {},
        "assembly": {},
        "fit": {},
        "transfer": {},
        "reuse": {},
        "constraints": {},
        "ingest": {},
        "assembly_rules": {},
        "execution": {},
        "space": {},
        "repair_policy": {},
        "build": {},
        "validate": {},
        "package": {},
        "publish": {},
    }
    if draw(st.booleans()):
        node["uses"] = [draw(_IDENT)]
    if draw(st.booleans()):
        node["validate"] = {"threshold": draw(st.floats(min_value=0.5, max_value=1.0))}
    return node


@st.composite
def _random_profile_node(draw: Any) -> dict:
    return {
        "node_type": "profile",
        "name": draw(_IDENT),
        "uses": [],
        "defaults": {},
        "rules": [],
        "repair": {},
    }


def _empty_program() -> dict:
    """Mirror the canonical empty program shape from ``parse_text('')``."""
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
        "repair_policies": [],
        "fixtures": [],
        "tests": [],
        "benchmarks": [],
        "spaces": [],
        "assets": [],
        "variants": [],
    }


@st.composite
def _random_program(draw: Any) -> dict:
    """Build a parser-shaped program dict (list-typed top-level keys)."""
    program = _empty_program()
    n_assets = draw(st.integers(min_value=0, max_value=3))
    seen_names: set[str] = set()
    for _ in range(n_assets):
        node = draw(_random_asset_node())
        if node["name"] in seen_names:
            continue
        seen_names.add(node["name"])
        program["assets"].append(node)
    n_profiles = draw(st.integers(min_value=0, max_value=3))
    seen_p: set[str] = set()
    for _ in range(n_profiles):
        node = draw(_random_profile_node())
        if node["name"] in seen_p:
            continue
        seen_p.add(node["name"])
        program["profiles"].append(node)
    return program


# -- tests ---------------------------------------------------------------


@given(program=_random_program())
@settings(
    max_examples=MAX_EXAMPLES,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much],
)
def test_normalize_program_idempotent(program: dict) -> None:
    """Property: ``normalize_program(normalize_program(x)) == normalize_program(x)``."""
    _assert_idempotent_program(program)


@given(asset=_random_asset_node())
@settings(
    max_examples=MAX_EXAMPLES,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much],
)
def test_normalize_asset_idempotent(asset: dict) -> None:
    """Property: ``normalize_asset(normalize_asset(x)) == normalize_asset(x)``."""
    _assert_idempotent_asset(asset)


# -- regression seed -----------------------------------------------------


@pytest.mark.parametrize(
    "src",
    [
        "",
        "asset foo: prop {}",
        "profile p { defaults { build.optimize.lods = 4 } }",
        "asset foo: vehicle { validate { threshold = 0.85 } }",
    ],
)
def test_normalize_program_idempotent_from_source(src: str) -> None:
    """Idempotence on programs coming through the real parser pipeline."""
    program = parse_text(src)
    _assert_idempotent_program(program)
