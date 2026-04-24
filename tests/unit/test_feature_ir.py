"""Unit tests for ``lathe.feature_ir.FeatureIR``.

``FeatureIR`` is a thin dataclass container lifting an asset's
``geometry`` and ``features`` authoring blocks for downstream feature
compilation. It exposes ``from_asset`` (adapter from a materialized
asset dict) and ``to_dict`` (dataclass serialization). Tests pin
construction, round-trip, default-factory isolation, empty/malformed
inputs, and scaling to a large feature set.
"""

from __future__ import annotations

import unittest

from lathe.feature_ir import FeatureIR


class FeatureIRConstructionTests(unittest.TestCase):
    def test_default_construction_yields_empty_dicts(self) -> None:
        ir = FeatureIR()
        self.assertEqual(ir.geometry, {})
        self.assertEqual(ir.features, {})

    def test_explicit_fields_preserved(self) -> None:
        ir = FeatureIR(
            geometry={"symmetry": "x", "scale": 1.2},
            features={"density": "high", "edge_break": True},
        )
        self.assertEqual(ir.geometry["symmetry"], "x")
        self.assertEqual(ir.features["density"], "high")
        self.assertIs(ir.features["edge_break"], True)

    def test_default_factories_are_per_instance(self) -> None:
        a = FeatureIR()
        b = FeatureIR()
        a.geometry["k"] = 1
        a.features["tag"] = "x"
        # fresh instance must not share the mutation
        self.assertNotIn("k", b.geometry)
        self.assertNotIn("tag", b.features)


class FeatureIRFromAssetTests(unittest.TestCase):
    def test_from_asset_copies_blocks_verbatim(self) -> None:
        asset = {
            "geometry": {"symmetry": "z"},
            "features": {"density": "medium"},
        }
        ir = FeatureIR.from_asset(asset)
        self.assertEqual(ir.geometry, {"symmetry": "z"})
        self.assertEqual(ir.features, {"density": "medium"})

    def test_from_asset_missing_blocks_defaults_to_empty(self) -> None:
        ir = FeatureIR.from_asset({})
        self.assertEqual(ir.geometry, {})
        self.assertEqual(ir.features, {})

    def test_from_asset_copies_dicts_defensively(self) -> None:
        # from_asset wraps with dict(...) so caller mutation must not leak.
        source_geometry = {"key": "value"}
        source_features = {"density": "low"}
        ir = FeatureIR.from_asset(
            {"geometry": source_geometry, "features": source_features}
        )
        source_geometry["key"] = "mutated"
        source_features["density"] = "mutated"
        self.assertEqual(ir.geometry["key"], "value")
        self.assertEqual(ir.features["density"], "low")


class FeatureIRSerializationTests(unittest.TestCase):
    def test_to_dict_round_trip(self) -> None:
        ir = FeatureIR(
            geometry={"symmetry": "x"},
            features={"edge_break": True, "panel_depth": 1.1},
        )
        payload = ir.to_dict()
        self.assertEqual(set(payload), {"geometry", "features"})
        restored = FeatureIR(**payload)
        self.assertEqual(restored, ir)
        self.assertEqual(restored.to_dict(), payload)

    def test_to_dict_handles_large_feature_set(self) -> None:
        features = {f"feature_{i}": {"scale": float(i), "enabled": bool(i % 2)} for i in range(256)}
        ir = FeatureIR(geometry={"scale": 1.0}, features=features)
        payload = ir.to_dict()
        self.assertEqual(len(payload["features"]), 256)
        self.assertEqual(payload["features"]["feature_17"]["scale"], 17.0)
        # round-trip survives scale
        restored = FeatureIR(**payload)
        self.assertEqual(restored.features["feature_254"]["enabled"], False)


class FeatureIRMalformedInputTests(unittest.TestCase):
    def test_from_asset_rejects_non_dict_input(self) -> None:
        # `asset.get("geometry", {})` expects a mapping; passing None
        # raises AttributeError on .get.
        with self.assertRaises(AttributeError):
            FeatureIR.from_asset(None)  # type: ignore[arg-type]

    def test_from_asset_rejects_non_mapping_geometry_block(self) -> None:
        # `dict(asset["geometry"])` must receive a mapping or iterable of
        # pairs; a bare string raises ValueError when iterated into dict.
        with self.assertRaises((TypeError, ValueError)):
            FeatureIR.from_asset({"geometry": "not a mapping"})


if __name__ == "__main__":
    unittest.main()
