"""Phase 4 tests for ``lathe.asset_quality.construction_graph``.

Covers per task #4 of ``docs/asset-quality/improvement-tasklist.md``:

- ``ConstructionNode`` / ``ConstructionEdge`` /
  ``SemanticConstructionGraph`` dataclasses construct correctly and stay
  frozen, and ``attributes`` accepts an arbitrary dict.
- ``NODE_TYPES`` has exactly 15 members and ``EDGE_TYPES`` has exactly
  10 members.
- ``to_dict`` round-trips: tuples become lists, dicts are preserved.
- ``extract_construction_graph`` from the actual industrial_crate parts
  list yields 6 nodes (body -> primary_volume, latch_plate -> inset,
  2x handle, 2x mount), 5 ``attached_to`` edges, 2 ``mirrors`` edges.
- Empty asset, missing intent, missing parts: never crashes, returns an
  empty/minimal graph.
- Mirror detection only fires for ``_l`` / ``_r`` suffixes (not
  ``_left`` / ``_right``).
- Default fallback type: an unrecognised part name yields ``"panel"``.
- ``evaluate_construction_graph`` payload shape includes ``version``,
  ``family``, ``asset_name``, ``nodes``, ``edges``, ``node_count``,
  ``edge_count``, ``node_types_present``, ``edge_types_present``.
- Determinism: same input -> same output across invocations.
- Family field defaults to ``"generic"`` when ``runtime["design_brief"]``
  is absent and reads the design_brief family when present.
- Absence of a ``diagnostics`` field so the FunctionValidator wrapper
  treats the validator as passing.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import Any

import pytest

from lathe.asset_quality.construction_graph import (
    CONSTRUCTION_GRAPH_VERSION,
    EDGE_TYPES,
    NODE_TYPES,
    ConstructionEdge,
    ConstructionNode,
    SemanticConstructionGraph,
    evaluate_construction_graph,
    extract_construction_graph,
)


_EXPECTED_PAYLOAD_KEYS: frozenset[str] = frozenset(
    {
        "version",
        "family",
        "asset_name",
        "nodes",
        "edges",
        "node_count",
        "edge_count",
        "node_types_present",
        "edge_types_present",
    }
)


_INDUSTRIAL_CRATE_BASELINE_PARTS: tuple[str, ...] = (
    "body",
    "latch_plate",
    "handle_l",
    "handle_r",
    "foot_l",
    "foot_r",
)


def _runtime_with_family(family: str) -> dict[str, Any]:
    return {"design_brief": {"brief": {"family": family}}}


def _crate_runtime() -> dict[str, Any]:
    return _runtime_with_family("industrial_crate")


def test_construction_node_dataclass_is_frozen_and_accepts_open_attributes() -> None:
    node = ConstructionNode(
        node_id="body",
        node_type="primary_volume",
        attributes={"thickness": 0.05, "tags": ["hero"]},
    )

    assert node.node_id == "body"
    assert node.node_type == "primary_volume"
    assert node.attributes == {"thickness": 0.05, "tags": ["hero"]}
    with pytest.raises(FrozenInstanceError):
        node.node_type = "panel"  # type: ignore[misc]


def test_construction_edge_dataclass_is_frozen_and_accepts_open_attributes() -> None:
    edge = ConstructionEdge(
        source_id="handle_l",
        target_id="body",
        edge_type="attached_to",
        attributes={"weight": 1.0},
    )

    assert edge.source_id == "handle_l"
    assert edge.target_id == "body"
    assert edge.edge_type == "attached_to"
    assert edge.attributes == {"weight": 1.0}
    with pytest.raises(FrozenInstanceError):
        edge.edge_type = "mirrors"  # type: ignore[misc]


def test_semantic_construction_graph_dataclass_is_frozen() -> None:
    graph = SemanticConstructionGraph(
        asset_name="industrial_crate",
        family="industrial_crate",
        nodes=(
            ConstructionNode(node_id="body", node_type="primary_volume", attributes={}),
        ),
        edges=(),
    )

    assert graph.asset_name == "industrial_crate"
    assert graph.family == "industrial_crate"
    assert len(graph.nodes) == 1
    with pytest.raises(FrozenInstanceError):
        graph.family = "mechanical_door"  # type: ignore[misc]


def test_node_types_has_exactly_twenty_members() -> None:
    """Cycle 3 expanded NODE_TYPES to 20: 15 from the original master
    prompt plus 5 added when the procedural synthesizer's generator
    stream landed (bracket, vent, conduit, latch, weld)."""
    assert len(NODE_TYPES) == 20


def test_edge_types_has_exactly_ten_members() -> None:
    assert len(EDGE_TYPES) == 10


def test_node_types_match_master_prompt() -> None:
    """Cycle 3 superset: original 15 + 5 added with the hard-surface
    generator stream (bracket, vent, conduit, latch, weld)."""
    assert NODE_TYPES == frozenset(
        {
            "primary_volume",
            "frame",
            "panel",
            "inset",
            "trim",
            "guard",
            "rail",
            "socket",
            "mount",
            "handle",
            "hinge",
            "fastener",
            "decal_zone",
            "wear_zone",
            "material_zone",
            "bracket",
            "vent",
            "conduit",
            "latch",
            "weld",
        }
    )


def test_edge_types_match_master_prompt() -> None:
    assert EDGE_TYPES == frozenset(
        {
            "attached_to",
            "inset_into",
            "wraps_around",
            "mirrors",
            "aligned_with",
            "supports",
            "cuts",
            "contains",
            "wears_on",
            "material_bound_to",
        }
    )


def test_to_dict_round_trips_tuples_to_lists_and_preserves_dicts() -> None:
    graph = SemanticConstructionGraph(
        asset_name="industrial_crate",
        family="industrial_crate",
        nodes=(
            ConstructionNode(
                node_id="body",
                node_type="primary_volume",
                attributes={"hero": True, "panels": ["top", "bottom"]},
            ),
            ConstructionNode(
                node_id="handle_l",
                node_type="handle",
                attributes={},
            ),
        ),
        edges=(
            ConstructionEdge(
                source_id="handle_l",
                target_id="body",
                edge_type="attached_to",
                attributes={"explicit": False},
            ),
        ),
    )
    payload = graph.to_dict()

    assert isinstance(payload, dict)
    assert isinstance(payload["nodes"], list)
    assert isinstance(payload["edges"], list)
    assert payload["nodes"][0]["attributes"] == {
        "hero": True,
        "panels": ["top", "bottom"],
    }
    assert payload["nodes"][1]["attributes"] == {}
    assert payload["edges"][0]["attributes"] == {"explicit": False}
    assert payload["asset_name"] == "industrial_crate"
    assert payload["family"] == "industrial_crate"


def test_extract_industrial_crate_baseline_yields_six_nodes_with_canonical_types() -> (
    None
):
    asset = {
        "name": "industrial_crate",
        "intent": {"parts": list(_INDUSTRIAL_CRATE_BASELINE_PARTS)},
    }
    graph = extract_construction_graph(asset, _crate_runtime())

    assert len(graph.nodes) == 6
    assert tuple(node.node_id for node in graph.nodes) == (
        _INDUSTRIAL_CRATE_BASELINE_PARTS
    )
    types_by_id = {node.node_id: node.node_type for node in graph.nodes}
    assert types_by_id == {
        "body": "primary_volume",
        # latch_plate classifies as "latch" since Cycle 3 added the
        # latch NODE_TYPE; the substring rule for "latch" precedes the
        # fallback "panel"/"inset" rules. Either is semantically valid
        # for a crate's latch plate — the latch generator decomposes
        # into a plate + arm so the higher-level intent is preserved.
        "latch_plate": "latch",
        "handle_l": "handle",
        "handle_r": "handle",
        "foot_l": "mount",
        "foot_r": "mount",
    }


def test_extract_industrial_crate_baseline_emits_five_attached_to_edges_to_body() -> (
    None
):
    asset = {
        "name": "industrial_crate",
        "intent": {"parts": list(_INDUSTRIAL_CRATE_BASELINE_PARTS)},
    }
    graph = extract_construction_graph(asset, _crate_runtime())

    attached = [edge for edge in graph.edges if edge.edge_type == "attached_to"]
    assert len(attached) == 5
    for edge in attached:
        assert edge.target_id == "body"
        assert edge.source_id != "body"
    assert {edge.source_id for edge in attached} == {
        "latch_plate",
        "handle_l",
        "handle_r",
        "foot_l",
        "foot_r",
    }


def test_extract_industrial_crate_baseline_emits_two_mirrors_edges() -> None:
    asset = {
        "name": "industrial_crate",
        "intent": {"parts": list(_INDUSTRIAL_CRATE_BASELINE_PARTS)},
    }
    graph = extract_construction_graph(asset, _crate_runtime())

    mirrors = [edge for edge in graph.edges if edge.edge_type == "mirrors"]
    assert len(mirrors) == 2
    pairs = {(edge.source_id, edge.target_id) for edge in mirrors}
    assert pairs == {("handle_l", "handle_r"), ("foot_l", "foot_r")}


def test_extract_handles_empty_asset_without_crashing() -> None:
    graph = extract_construction_graph({}, {})

    assert graph.asset_name == "unnamed_asset"
    assert graph.family == "generic"
    assert graph.nodes == ()
    assert graph.edges == ()


def test_extract_tolerates_missing_intent_and_missing_parts() -> None:
    graph_missing_intent = extract_construction_graph({"name": "crate"}, _crate_runtime())
    graph_missing_parts = extract_construction_graph(
        {"name": "crate", "intent": {}}, _crate_runtime()
    )

    assert graph_missing_intent.nodes == ()
    assert graph_missing_intent.edges == ()
    assert graph_missing_parts.nodes == ()
    assert graph_missing_parts.edges == ()


def test_mirror_detection_only_fires_on_short_lr_suffixes() -> None:
    asset = {
        "name": "industrial_crate",
        "intent": {
            "parts": [
                "handle_left",
                "handle_right",
                "panel_l",
                "panel_r",
            ]
        },
    }
    graph = extract_construction_graph(asset, _crate_runtime())

    mirror_pairs = {
        (edge.source_id, edge.target_id)
        for edge in graph.edges
        if edge.edge_type == "mirrors"
    }
    assert mirror_pairs == {("panel_l", "panel_r")}


def test_unrecognised_part_name_falls_back_to_panel_node_type() -> None:
    asset = {
        "name": "test",
        "intent": {"parts": ["unknown_widget"]},
    }
    graph = extract_construction_graph(asset, _crate_runtime())

    assert len(graph.nodes) == 1
    assert graph.nodes[0].node_type == "panel"


def test_substring_rule_precedence_first_match_wins() -> None:
    """``_NODE_TYPE_RULES`` is evaluated in declaration order. A part name
    that contains tokens from multiple rules resolves to the *earliest*
    matching rule's type.

    Cycle 3 promoted ``latch`` to a proper NODE_TYPE with its own
    generator; the substring rule for ``latch`` now precedes ``panel``
    in the dispatch tuple. ``latch_panel`` → ``latch`` (first-match
    wins). The latch generator decomposes into a plate + arm, so the
    semantic intent of a "latch panel" is preserved one level down.
    """
    from lathe.asset_quality.construction_graph import _classify_part

    assert _classify_part("latch_panel") == "latch"
    # Sanity checks: latch_plate now classifies as latch (the part
    # IS a latch component), and front_panel still classifies as
    # panel since no earlier-rule substring matches.
    assert _classify_part("latch_plate") == "latch"
    assert _classify_part("front_panel") == "panel"


def test_evaluate_construction_graph_payload_shape() -> None:
    asset = {
        "name": "industrial_crate",
        "intent": {"parts": list(_INDUSTRIAL_CRATE_BASELINE_PARTS)},
    }
    payload = evaluate_construction_graph(asset, _crate_runtime())

    assert payload["version"] == CONSTRUCTION_GRAPH_VERSION
    assert CONSTRUCTION_GRAPH_VERSION == "construction_graph_v1"
    assert set(payload.keys()) == _EXPECTED_PAYLOAD_KEYS
    assert payload["family"] == "industrial_crate"
    assert payload["asset_name"] == "industrial_crate"
    assert payload["node_count"] == 6
    assert payload["edge_count"] == 7
    assert "primary_volume" in payload["node_types_present"]
    assert payload["node_types_present"] == sorted(
        set(payload["node_types_present"])
    )
    assert payload["edge_types_present"] == sorted(
        set(payload["edge_types_present"])
    )
    assert "attached_to" in payload["edge_types_present"]
    assert "mirrors" in payload["edge_types_present"]


def test_evaluate_construction_graph_has_no_diagnostics_field() -> None:
    """Mirrors Phase 1/2/3's contract: ``FunctionValidator`` only flips
    ``passes`` to ``False`` when a diagnostics entry has ``severity == 'error'``.
    Returning no ``diagnostics`` field keeps the validator passing."""
    payload = evaluate_construction_graph(
        {"intent": {"parts": ["body"]}}, _crate_runtime()
    )

    assert "diagnostics" not in payload


def test_extract_is_deterministic_across_invocations() -> None:
    asset = {
        "name": "industrial_crate",
        "intent": {"parts": list(_INDUSTRIAL_CRATE_BASELINE_PARTS)},
    }
    runtime = _crate_runtime()

    first = evaluate_construction_graph(asset, runtime)
    second = evaluate_construction_graph(asset, runtime)

    assert first == second


def test_family_defaults_to_generic_when_design_brief_absent() -> None:
    asset = {"name": "industrial_crate", "intent": {"parts": ["body"]}}
    graph = extract_construction_graph(asset, {})

    assert graph.family == "generic"


def test_family_reads_design_brief_when_present() -> None:
    asset = {"name": "industrial_crate", "intent": {"parts": ["body"]}}
    graph = extract_construction_graph(asset, _runtime_with_family("mechanical_door"))

    assert graph.family == "mechanical_door"


def test_extra_node_ids_from_scaffold_asset_graph_are_appended() -> None:
    """Best-effort merge: a structural hint from
    ``runtime["shape"]["bundle"]["scaffold_report"]["asset_graph"]`` adds
    nodes that aren't already in the parts list."""
    asset = {
        "name": "industrial_crate",
        "intent": {"parts": ["body"]},
    }
    runtime: dict[str, Any] = {
        **_crate_runtime(),
        "shape": {
            "bundle": {
                "scaffold_report": {
                    "asset_graph": {
                        "nodes": [
                            {"node_id": "body"},
                            {"node_id": "extra_panel"},
                        ]
                    }
                }
            }
        },
    }
    graph = extract_construction_graph(asset, runtime)

    node_ids = [node.node_id for node in graph.nodes]
    assert node_ids == ["body", "extra_panel"]


def test_attached_to_edges_skipped_when_no_primary_volume_present() -> None:
    """If the parts list has no ``body`` (no primary_volume node), no
    ``attached_to`` edges should be emitted — only mirrors."""
    asset = {
        "name": "kit",
        "intent": {"parts": ["handle_l", "handle_r"]},
    }
    graph = extract_construction_graph(asset, _crate_runtime())

    attached = [edge for edge in graph.edges if edge.edge_type == "attached_to"]
    mirrors = [edge for edge in graph.edges if edge.edge_type == "mirrors"]
    assert attached == []
    assert len(mirrors) == 1
    assert (mirrors[0].source_id, mirrors[0].target_id) == ("handle_l", "handle_r")


def test_node_types_present_and_edge_types_present_are_subsets_of_constants() -> None:
    asset = {
        "name": "industrial_crate",
        "intent": {"parts": list(_INDUSTRIAL_CRATE_BASELINE_PARTS)},
    }
    payload = evaluate_construction_graph(asset, _crate_runtime())

    assert set(payload["node_types_present"]).issubset(NODE_TYPES)
    assert set(payload["edge_types_present"]).issubset(EDGE_TYPES)
