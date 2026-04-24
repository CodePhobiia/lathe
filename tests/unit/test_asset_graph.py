"""Unit tests for ``lathe.asset_graph``.

Covers the pure-data transformation from a materialized asset dict to
the :class:`AssetGraph` used by the shape stage: ``build_asset_graph``
plus the ``infer_asset_family`` / ``infer_blueprint_id`` helpers. The
tests exercise family inference over multiple heuristic paths, part
tagging, symmetry mate detection, and round-trip serialization so that
downstream stages can rely on the graph's shape without loading the
full parser/resolver pipeline.
"""

from __future__ import annotations

import unittest

from lathe.asset_graph import (
    AssetGraph,
    PartNode,
    build_asset_graph,
    infer_asset_family,
    infer_blueprint_id,
)


def _asset(
    *,
    name: str = "demo",
    kind: str = "prop",
    role: str = "",
    parts: list[str] | None = None,
    extra: dict | None = None,
) -> dict:
    payload: dict = {
        "name": name,
        "kind": kind,
        "intent": {"role": role, "parts": list(parts or [])},
        "build": {"shape": {"symmetry": "auto"}, "rig": {}, "interfaces": {}},
        "validate": {"threshold": 0.80},
    }
    if extra:
        # shallow-merge for test override convenience
        for key, value in extra.items():
            payload[key] = value
    return payload


class InferFamilyTests(unittest.TestCase):
    def test_explicit_runtime_family_takes_precedence(self) -> None:
        asset = _asset(
            extra={
                "assembly": {
                    "resolved_family": {"values": {"runtime_family": "brassbound_chest"}}
                }
            }
        )
        self.assertEqual(infer_asset_family(asset), "brassbound_chest")

    def test_drone_family_heuristic_via_rotor_parts(self) -> None:
        asset = _asset(
            role="drone",
            parts=["rotor_fl", "rotor_fr", "rotor_rl", "rotor_rr", "body"],
        )
        self.assertEqual(infer_asset_family(asset), "courier_drone")

    def test_chest_family_heuristic_via_chest_token(self) -> None:
        asset = _asset(role="loot_chest", parts=["body", "lid", "lock_plate"])
        self.assertEqual(infer_asset_family(asset), "brassbound_chest")

    def test_env_module_generic_fallback(self) -> None:
        asset = _asset(kind="env_module", role="decor", parts=["base"])
        self.assertEqual(infer_asset_family(asset), "env_module_generic")

    def test_hard_surface_prop_generic_fallback(self) -> None:
        asset = _asset(role="unknown", parts=["widget"])
        self.assertEqual(infer_asset_family(asset), "hard_surface_prop_generic")


class InferBlueprintIDTests(unittest.TestCase):
    def test_explicit_blueprint_id_used_directly(self) -> None:
        asset = _asset(
            extra={
                "assembly": {
                    "resolved_family": {
                        "values": {"blueprint_id": "custom.blueprint.id.v1"}
                    }
                }
            }
        )
        self.assertEqual(infer_blueprint_id(asset), "custom.blueprint.id.v1")

    def test_derived_blueprint_id_matches_family(self) -> None:
        asset = _asset(role="crate", parts=["body", "lid"])
        self.assertEqual(
            infer_blueprint_id(asset),
            "lathe.blueprint.hard_surface_crate_v1",
        )


class BuildAssetGraphTests(unittest.TestCase):
    def test_two_part_asset_produces_graph_and_part_edges(self) -> None:
        asset = _asset(
            role="crate",
            parts=["body", "lid"],
            extra={
                "assembly": {"resolved_components": []},
                "build": {
                    "shape": {"symmetry": "x"},
                    "rig": {"joints": ["lid_hinge"]},
                    "interfaces": {"sockets": ["grip"], "anchors": ["floor"]},
                },
            },
        )
        graph = build_asset_graph(asset)

        self.assertIsInstance(graph, AssetGraph)
        self.assertEqual(graph.name, "demo")
        self.assertEqual(graph.family, "industrial_crate")
        self.assertEqual([p.name for p in graph.parts], ["body", "lid"])
        self.assertEqual(graph.symmetry_axis, "x")
        self.assertEqual(graph.joints, ["lid_hinge"])
        self.assertEqual(graph.sockets, ["grip"])
        self.assertEqual(graph.anchors, ["floor"])
        # body-lid edge should appear in inferred graph
        pairs = {(edge["from"], edge["to"]) for edge in graph.part_graph}
        self.assertIn(("body", "lid"), pairs)

    def test_empty_parts_list_still_yields_graph(self) -> None:
        asset = _asset(role="crate", parts=[])
        graph = build_asset_graph(asset)

        self.assertEqual(graph.parts, [])
        self.assertEqual(graph.part_graph, [])
        self.assertEqual(graph.family, "industrial_crate")

    def test_symmetry_mate_detection_for_left_right_pair(self) -> None:
        asset = _asset(
            role="drone",
            parts=["rotor_fl", "rotor_fr", "rotor_rl", "rotor_rr", "body"],
        )
        graph = build_asset_graph(asset)
        by_name = {part.name: part for part in graph.parts}

        self.assertEqual(by_name["rotor_fl"].symmetry_mate, "rotor_fr")
        self.assertEqual(by_name["rotor_fr"].symmetry_mate, "rotor_fl")
        # body has no mate
        self.assertIsNone(by_name["body"].symmetry_mate)

    def test_missing_name_raises_key_error(self) -> None:
        # build_asset_graph reads asset["name"] unconditionally; a bare
        # dict without name must surface as KeyError (callers always set it).
        with self.assertRaises(KeyError):
            build_asset_graph({"kind": "prop", "intent": {"role": "x", "parts": []}})

    def test_large_graph_twenty_parts(self) -> None:
        parts = [f"part_{i:02d}" for i in range(22)]
        asset = _asset(role="crate", parts=parts)
        graph = build_asset_graph(asset)

        self.assertEqual(len(graph.parts), 22)
        # Every part is a PartNode with at least a name
        for part in graph.parts:
            self.assertIsInstance(part, PartNode)
            self.assertTrue(part.name.startswith("part_"))
        # part_graph may be empty since no role tags — but must serialize
        payload = graph.to_dict()
        self.assertEqual(len(payload["parts"]), 22)

    def test_to_dict_round_trip_preserves_payload_shape(self) -> None:
        asset = _asset(role="crate", parts=["body", "lid"])
        graph = build_asset_graph(asset)
        payload = graph.to_dict()

        self.assertEqual(payload["name"], "demo")
        self.assertEqual(payload["family"], "industrial_crate")
        self.assertIsInstance(payload["parts"], list)
        self.assertIsInstance(payload["semantic_requirements"], dict)
        self.assertIsInstance(payload["authoring"], dict)
        # scale_cm default for non-env_module is 100.0
        self.assertEqual(payload["scale_cm"], 100.0)


class ScaleCmTests(unittest.TestCase):
    def test_env_module_default_scale_is_200cm(self) -> None:
        asset = _asset(kind="env_module", role="decor", parts=["base"])
        graph = build_asset_graph(asset)
        self.assertEqual(graph.scale_cm, 200.0)

    def test_explicit_unit_scale_parsed_from_intent(self) -> None:
        asset = _asset(role="crate", parts=["body"])
        asset["intent"]["scale"] = {"type": "unit", "value": 2.5, "unit": "m"}
        graph = build_asset_graph(asset)
        self.assertEqual(graph.scale_cm, 250.0)


if __name__ == "__main__":
    unittest.main()
