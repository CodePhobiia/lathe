"""Property-based tests for ``lathe.feature_grammar``.

Invariants covered:

- Empty feature grammar (ShapeIR with no regions) produces exactly zero
  feature ops: the grammar has nothing to attach to.
- Applying the grammar twice with identical input produces identical
  output *at the report level* (same ``feature_count_added`` and same
  ``feature_ops_used``). The second call re-derives features from the
  pristine input shape_ir, so it is idempotent at the compilation level.
- Feature-count monotonicity: strictly widening the region set (more
  regions → more feature-producing surface) produces an equal-or-greater
  feature count. This is the grammar's fundamental contract: features
  scale with component count, they don't drop.

Hypothesis unavailable; parametrized with explicit fixtures.
"""

from __future__ import annotations

import copy

import numpy as np
import pytest
from lathe.assembly_kernel import compile_assembly_blueprint
from lathe.asset_graph import build_asset_graph
from lathe.blueprints import resolve_blueprint
from lathe.candidate_search import generate_candidate_params
from lathe.feature_grammar import compile_feature_enhancements
from lathe.fidelity import infer_fidelity_profile

pytestmark = pytest.mark.property


def _make_graph(family_payload: dict) -> object:
    return build_asset_graph(family_payload)


FAMILY_PAYLOADS = [
    pytest.param(
        {
            "name": "industrial_crate",
            "kind": "hard_surface_prop",
            "intent": {"role": "crate", "parts": ["body", "lid"]},
            "build": {"shape": {"symmetry": "auto", "mode": "generate"}, "rig": {}, "interfaces": {}},
            "validate": {"threshold": 0.80},
        },
        id="industrial_crate",
    ),
    pytest.param(
        {
            "name": "console_terminal",
            "kind": "hard_surface_prop",
            "intent": {"role": "terminal", "parts": ["body", "screen"]},
            "build": {"shape": {"symmetry": "auto", "mode": "generate"}, "rig": {}, "interfaces": {}},
            "validate": {"threshold": 0.80},
        },
        id="console_terminal",
    ),
    pytest.param(
        {
            "name": "brassbound_chest",
            "kind": "hard_surface_prop",
            "intent": {"role": "chest", "parts": ["body", "lid"]},
            "build": {"shape": {"symmetry": "auto", "mode": "generate"}, "rig": {}, "interfaces": {}},
            "validate": {"threshold": 0.80},
        },
        id="brassbound_chest",
    ),
    pytest.param(
        {
            "name": "mechanical_door",
            "kind": "hard_surface_prop",
            "intent": {"role": "door", "parts": ["frame", "panel"]},
            "build": {"shape": {"symmetry": "auto", "mode": "generate"}, "rig": {}, "interfaces": {}},
            "validate": {"threshold": 0.80},
        },
        id="mechanical_door",
    ),
    pytest.param(
        {
            "name": "courier_drone",
            "kind": "mechanical_assembly",
            "intent": {
                "role": "drone",
                "parts": ["body", "rotor_fl", "rotor_fr", "rotor_rl", "rotor_rr"],
            },
            "build": {"shape": {"symmetry": "x", "mode": "generate"}, "rig": {}, "interfaces": {}},
            "validate": {"threshold": 0.80},
        },
        id="courier_drone",
    ),
]


def _compile(graph):
    rng = np.random.default_rng(0)
    blueprint = resolve_blueprint(graph, {}, rng, 0)
    return compile_assembly_blueprint(graph, blueprint)


@pytest.mark.parametrize("payload", FAMILY_PAYLOADS)
def test_empty_regions_yield_zero_feature_ops(payload: dict) -> None:
    """Stripping regions from the ShapeIR before invoking the grammar
    produces a zero-feature output: the grammar has nothing to bind.
    ``feature_count_added == 0`` and ``feature_ops_used`` is empty.
    """
    graph = _make_graph(payload)
    fidelity = infer_fidelity_profile(graph)
    params = generate_candidate_params(graph, seed=0, candidate_index=0, fidelity=fidelity)
    shape_ir = _compile(graph)
    stripped = copy.deepcopy(shape_ir)
    stripped.regions = []
    enriched, report = compile_feature_enhancements(graph, stripped, fidelity=fidelity, params=params)
    assert report["feature_count_added"] == 0
    assert report["feature_ops_used"] == []
    # primitives list unchanged in count
    assert len(enriched.primitives) == len(stripped.primitives)


@pytest.mark.parametrize("payload", FAMILY_PAYLOADS)
def test_grammar_is_deterministic_at_report_level(payload: dict) -> None:
    """Running the grammar twice on identical input produces identical
    ``feature_count_added`` and identical ``feature_ops_used``. The
    grammar does not carry mutation state across calls — it is
    idempotent at the compile level.
    """
    graph = _make_graph(payload)
    fidelity = infer_fidelity_profile(graph)
    params = generate_candidate_params(graph, seed=0, candidate_index=0, fidelity=fidelity)
    shape_ir = _compile(graph)
    _, report_a = compile_feature_enhancements(
        graph, copy.deepcopy(shape_ir), fidelity=fidelity, params=params
    )
    _, report_b = compile_feature_enhancements(
        graph, copy.deepcopy(shape_ir), fidelity=fidelity, params=params
    )
    assert report_a["feature_count_added"] == report_b["feature_count_added"]
    assert report_a["feature_ops_used"] == report_b["feature_ops_used"]


@pytest.mark.parametrize("payload", FAMILY_PAYLOADS)
def test_feature_count_is_monotonic_under_region_dropping(payload: dict) -> None:
    """Dropping regions from the ShapeIR cannot INCREASE the feature
    count — removing a region strictly shrinks the grammar's input
    surface. This is a one-direction monotonicity invariant: more
    regions ≥ fewer regions.
    """
    graph = _make_graph(payload)
    fidelity = infer_fidelity_profile(graph)
    params = generate_candidate_params(graph, seed=0, candidate_index=0, fidelity=fidelity)
    shape_ir = _compile(graph)
    if len(shape_ir.regions) < 2:
        pytest.skip("family has too few regions to meaningfully test monotonicity")

    _, report_full = compile_feature_enhancements(
        graph, copy.deepcopy(shape_ir), fidelity=fidelity, params=params
    )
    partial = copy.deepcopy(shape_ir)
    partial.regions = partial.regions[:-1]  # drop one region
    _, report_partial = compile_feature_enhancements(graph, partial, fidelity=fidelity, params=params)
    # Full input must yield at least as many features as the partial.
    assert report_full["feature_count_added"] >= report_partial["feature_count_added"]


@pytest.mark.parametrize("payload", FAMILY_PAYLOADS)
def test_grammar_report_shape_invariants(payload: dict) -> None:
    """Report dict always carries the four contract keys regardless of
    family or input size. ``feature_ops_used`` is always a sorted list
    (the grammar sorts its output for deterministic serialization).
    """
    graph = _make_graph(payload)
    fidelity = infer_fidelity_profile(graph)
    params = generate_candidate_params(graph, seed=0, candidate_index=0, fidelity=fidelity)
    shape_ir = _compile(graph)
    _, report = compile_feature_enhancements(graph, shape_ir, fidelity=fidelity, params=params)
    for key in ("fidelity", "candidate_params", "feature_ops_used", "feature_count_added"):
        assert key in report, f"expected report key {key!r}"
    assert list(report["feature_ops_used"]) == sorted(report["feature_ops_used"])
    assert report["feature_count_added"] >= 0
