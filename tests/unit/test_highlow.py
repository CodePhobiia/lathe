"""Unit tests for ``lathe.highlow`` (BL-22e Tranche C tail).

``lathe.highlow`` exposes ``HighLowRelation``, a small dataclass that pins the
high-poly / low-poly bake relationship recorded in the surface runtime trace.
Surface_runtime is integration-tested elsewhere; these are pure-data unit
checks on the dataclass itself.
"""

from __future__ import annotations

import unittest
from dataclasses import fields, is_dataclass

from lathe.highlow import HighLowRelation


class HighLowConstructionTests(unittest.TestCase):
    def test_construct_with_required_fields(self) -> None:
        rel = HighLowRelation(
            high_mesh_uri="stages/shape/high.glb",
            low_mesh_uri="stages/topology/low.glb",
            bake_cage_offset_cm=1.25,
            source="hero_surface_runtime_v1",
        )
        self.assertEqual(rel.high_mesh_uri, "stages/shape/high.glb")
        self.assertEqual(rel.low_mesh_uri, "stages/topology/low.glb")
        self.assertEqual(rel.bake_cage_offset_cm, 1.25)
        self.assertEqual(rel.source, "hero_surface_runtime_v1")

    def test_defaults_match_documented_invariants(self) -> None:
        rel = HighLowRelation(
            high_mesh_uri="h.glb",
            low_mesh_uri="l.glb",
            bake_cage_offset_cm=0.5,
            source="test_runtime",
        )
        # Authoritative defaults to True — bakes are by default trusted.
        self.assertTrue(rel.authoritative)
        # Counts and ratio start at zero before population.
        self.assertEqual(rel.high_triangle_count, 0)
        self.assertEqual(rel.low_triangle_count, 0)
        self.assertEqual(rel.distinction_ratio, 0.0)
        # Bake groups optional — None until set.
        self.assertIsNone(rel.bake_groups)


class HighLowSerializationTests(unittest.TestCase):
    def test_to_dict_round_trip(self) -> None:
        rel = HighLowRelation(
            high_mesh_uri="h.glb",
            low_mesh_uri="l.glb",
            bake_cage_offset_cm=2.0,
            source="round_trip",
            high_triangle_count=12000,
            low_triangle_count=2400,
            distinction_ratio=0.8,
            bake_groups=["body", "trim"],
            authoritative=False,
        )
        payload = rel.to_dict()
        # Round-trip via the dataclass constructor.
        rebuilt = HighLowRelation(**payload)
        self.assertEqual(rebuilt.to_dict(), payload)
        self.assertEqual(rebuilt, rel)

    def test_to_dict_keys_match_dataclass_fields(self) -> None:
        rel = HighLowRelation(high_mesh_uri="h", low_mesh_uri="l", bake_cage_offset_cm=0.0, source="s")
        payload = rel.to_dict()
        expected = {f.name for f in fields(HighLowRelation)}
        self.assertEqual(set(payload.keys()), expected)


class HighLowEdgeCaseTests(unittest.TestCase):
    def test_equal_high_and_low_uris_are_permitted(self) -> None:
        # Some pipelines author the same mesh as both high and low (e.g. when
        # baking from the authored mesh itself). This is a legal configuration.
        rel = HighLowRelation(
            high_mesh_uri="same.glb",
            low_mesh_uri="same.glb",
            bake_cage_offset_cm=0.0,
            source="degenerate",
        )
        self.assertEqual(rel.high_mesh_uri, rel.low_mesh_uri)
        self.assertEqual(rel.bake_cage_offset_cm, 0.0)

    def test_distinction_ratio_monotone_when_high_dominates(self) -> None:
        # When high-poly has more triangles than low, the canonical ratio
        # should reflect a non-zero distinction. We don't fix the formula here
        # (it lives in surface_runtime), only that callers can supply a value
        # consistent with their own monotone-improvement rule.
        small = HighLowRelation(
            high_mesh_uri="h",
            low_mesh_uri="l",
            bake_cage_offset_cm=0.0,
            source="s",
            high_triangle_count=1000,
            low_triangle_count=900,
            distinction_ratio=0.1,
        )
        large = HighLowRelation(
            high_mesh_uri="h",
            low_mesh_uri="l",
            bake_cage_offset_cm=0.0,
            source="s",
            high_triangle_count=1000,
            low_triangle_count=200,
            distinction_ratio=0.8,
        )
        self.assertLess(small.distinction_ratio, large.distinction_ratio)

    def test_empty_string_uris_are_permitted_but_distinguishable(self) -> None:
        # Constructing with empty URIs should not raise — validation is the
        # caller's responsibility — but to_dict should preserve the empty
        # strings rather than silently substituting placeholders.
        rel = HighLowRelation(high_mesh_uri="", low_mesh_uri="", bake_cage_offset_cm=0.0, source="")
        payload = rel.to_dict()
        self.assertEqual(payload["high_mesh_uri"], "")
        self.assertEqual(payload["low_mesh_uri"], "")
        self.assertEqual(payload["source"], "")

    def test_none_uris_are_preserved_as_missing_evidence(self) -> None:
        rel = HighLowRelation(
            high_mesh_uri=None,
            low_mesh_uri=None,
            bake_cage_offset_cm=0.0,
            source="missing_evidence",
        )
        payload = rel.to_dict()
        self.assertIsNone(payload["high_mesh_uri"])
        self.assertIsNone(payload["low_mesh_uri"])

    def test_missing_required_field_raises_typeerror(self) -> None:
        # Dataclass constructor enforces required-field presence — a malformed
        # call (omitting a required positional/keyword) raises TypeError.
        with self.assertRaises(TypeError):
            HighLowRelation(  # type: ignore[call-arg]
                high_mesh_uri="h",
                low_mesh_uri="l",
                # missing bake_cage_offset_cm and source
            )

    def test_is_a_dataclass(self) -> None:
        # Pin that HighLowRelation stays a dataclass — surface_runtime relies
        # on ``asdict`` semantics via ``to_dict``; switching to a plain class
        # would break the trace contract silently.
        self.assertTrue(is_dataclass(HighLowRelation))


if __name__ == "__main__":
    unittest.main()
