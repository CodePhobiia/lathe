"""Unit tests for ``lathe.kit_ir.KitIR``.

``KitIR`` is a thin extractor: it lifts ``assembly.kit`` +
``assembly.resolved_kit.values`` + ``constraints.resolved_assembly_policy``
from a materialized asset. It performs no validation of its own — the
resolver/checker enforce semantic rules upstream — so these tests focus
on extraction correctness, defaulting, and dict round-tripping. One case
drives through a real ``.lth`` example (``service_corridor_wall``) to
confirm the IR tracks the V1.1 ``library`` / ``kit`` language flow end
to end.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from lathe.kit_ir import KitIR
from lathe.parser import parse_file
from lathe.resolver import materialize_asset

ROOT = Path(__file__).resolve().parents[2]
ASSEMBLE_EXAMPLE = ROOT / "examples" / "service_corridor_wall.lth"


class KitIRTests(unittest.TestCase):
    def test_construction_with_components_and_policy(self) -> None:
        ir = KitIR(
            kit_name="industrial_wall_kit",
            values={"family": "sci_fi_wall_panel_family", "modules": ["a", "b", "c"]},
            assembly_policy={"name": "industrial_wall_policy"},
        )
        self.assertEqual(ir.kit_name, "industrial_wall_kit")
        self.assertEqual(ir.values["modules"], ["a", "b", "c"])
        self.assertEqual(ir.assembly_policy["name"], "industrial_wall_policy")

    def test_to_dict_round_trip(self) -> None:
        ir = KitIR(
            kit_name="k1",
            values={"family": "f1", "modules": ["m1"]},
            assembly_policy={"name": "p1", "rules": ["r1"]},
        )
        payload = ir.to_dict()
        restored = KitIR(**payload)
        self.assertEqual(restored.to_dict(), payload)
        # keys match dataclass field names exactly
        self.assertEqual(set(payload), {"kit_name", "values", "assembly_policy"})

    def test_from_asset_zero_components(self) -> None:
        # kit present, but no modules resolved yet (e.g. partially materialized)
        asset = {
            "assembly": {"kit": "empty_kit", "resolved_kit": {"values": {}}},
            "constraints": {},
        }
        ir = KitIR.from_asset(asset)
        self.assertEqual(ir.kit_name, "empty_kit")
        self.assertEqual(ir.values, {})
        self.assertEqual(ir.assembly_policy, {})

    def test_from_asset_defaults_when_missing_blocks(self) -> None:
        # No assembly, no constraints — IR stays empty (no exceptions).
        ir = KitIR.from_asset({})
        self.assertEqual(ir.kit_name, "")
        self.assertEqual(ir.values, {})
        self.assertEqual(ir.assembly_policy, {})

    def test_from_asset_real_service_corridor_wall(self) -> None:
        # End-to-end: parse + resolve a real example and confirm the IR
        # tracks the ``from industrial_wall_kit`` + ``assembly_policy``
        # wiring exposed by the V1.1 resolver.
        asset = materialize_asset(parse_file(ASSEMBLE_EXAMPLE), "service_corridor_wall")
        ir = KitIR.from_asset(asset)
        self.assertEqual(ir.kit_name, "industrial_wall_kit")
        self.assertEqual(ir.values["family"], "sci_fi_wall_panel_family")
        self.assertIn("modules", ir.values)
        self.assertGreater(len(ir.values["modules"]), 0)
        self.assertEqual(ir.assembly_policy.get("name"), "industrial_wall_policy")

    def test_nested_policy_values_preserved(self) -> None:
        # Kits can carry nested constraint structures (snap_grid, allowed_joins).
        asset = {
            "assembly": {
                "kit": "nested_kit",
                "resolved_kit": {
                    "values": {
                        "family": "fam",
                        "modules": ["m1", "m2"],
                        "snap_grid": "10cm",
                        "allowed_joins": ["a_to_b", "b_to_c"],
                    }
                },
            },
            "constraints": {
                "resolved_assembly_policy": {
                    "name": "p",
                    "rules": [{"kind": "clearance", "value": "1cm"}],
                }
            },
        }
        ir = KitIR.from_asset(asset)
        self.assertEqual(ir.values["snap_grid"], "10cm")
        self.assertEqual(ir.values["allowed_joins"], ["a_to_b", "b_to_c"])
        self.assertEqual(ir.assembly_policy["rules"][0]["kind"], "clearance")

    def test_from_asset_copies_mapping_at_top_level(self) -> None:
        # ``from_asset`` wraps the sub-dicts with ``dict(...)``, so mutating
        # the IR's top-level containers must not touch the source asset.
        src = {
            "assembly": {
                "kit": "k",
                "resolved_kit": {"values": {"family": "f"}},
            },
            "constraints": {"resolved_assembly_policy": {"name": "p"}},
        }
        ir = KitIR.from_asset(src)
        ir.values["extra"] = 1
        ir.assembly_policy["extra"] = 1
        self.assertNotIn("extra", src["assembly"]["resolved_kit"]["values"])
        self.assertNotIn("extra", src["constraints"]["resolved_assembly_policy"])


if __name__ == "__main__":
    unittest.main()
