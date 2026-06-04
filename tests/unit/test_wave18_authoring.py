"""Wave 18 tests: authoring layer scaffold (graph IR + NL intent)."""

from __future__ import annotations

from lathe.authoring import (
    AuthorGraph,
    AuthorGraphEdge,
    AuthorGraphNode,
    NLIntent,
    author_graph_from_construction_graph,
    construction_graph_from_author_graph,
    nl_intent_to_construction_payload,
    parse_nl_intent,
)


def test_author_graph_round_trip() -> None:
    """A construction_graph dict lifted to AuthorGraph and back is identical."""
    original = {
        "nodes": [
            {"node_id": "body", "node_type": "primary_volume", "domain": "hard_surface",
             "attributes": {"shape": "rounded_box"}},
            {"node_id": "handle_l", "node_type": "handle", "domain": "hard_surface",
             "attributes": {"length_cm": 14.0}},
        ],
        "edges": [
            {"edge_id": "e1", "source_id": "handle_l", "target_id": "body",
             "edge_type": "attached_to", "attributes": {"role": "left_side"}},
        ],
    }
    author = author_graph_from_construction_graph("crate_graph", original)
    assert len(author.nodes) == 2
    assert author.find_node("body").node_type == "primary_volume"
    projected = construction_graph_from_author_graph(author)
    assert projected["nodes"][0]["node_id"] == "body"
    assert projected["edges"][0]["edge_type"] == "attached_to"


def test_author_graph_handles_empty_construction() -> None:
    author = author_graph_from_construction_graph("empty", {})
    assert author.graph_id == "empty"
    assert author.nodes == ()
    assert author.edges == ()


def test_parse_nl_intent_clamps_condition() -> None:
    intent = parse_nl_intent("make a worn crate", "crate", condition=1.5)
    assert intent.condition == 1.0
    intent = parse_nl_intent("clean crate", "crate", condition=-0.5)
    assert intent.condition == 0.0


def test_nl_intent_to_construction_payload_crate() -> None:
    intent = parse_nl_intent(
        "a steampunk crate with brass corners",
        "crate",
        visual_language="steampunk_workshop_v1",
        condition=0.4,
        scale_m=0.9,
        parts_requested=("body", "handle_l", "handle_r", "corner_l", "corner_r"),
    )
    payload = nl_intent_to_construction_payload(intent)
    assert payload["kind"] == "hard_surface_prop"
    assert payload["from"] == "industrial_crate_family"
    assert payload["intent"]["scale"]["value"] == 0.9
    assert payload["intent"]["scale"]["unit"] == "m"
    assert "handle_l" in payload["intent"]["parts"]
    brief = payload["build"]["shape"]["procedural"]["brief"]
    assert brief["visual_language"] == "steampunk_workshop_v1"
    assert brief["condition"] == 0.4


def test_nl_intent_door_routes_to_env_module() -> None:
    intent = parse_nl_intent("a sci-fi airlock door", "door", scale_m=2.1)
    payload = nl_intent_to_construction_payload(intent)
    assert payload["kind"] == "env_module"
    assert payload["from"] == "mechanical_door_family"


def test_nl_intent_unknown_class_falls_back() -> None:
    intent = parse_nl_intent("a thing", "invented_class")
    payload = nl_intent_to_construction_payload(intent)
    assert payload["from"] == "invented_class_family"
    assert payload["kind"] == "hard_surface_prop"
