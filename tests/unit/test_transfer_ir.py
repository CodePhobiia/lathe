"""Unit tests for ``lathe.transfer_ir.TransferIR``.

``TransferIR`` extracts an asset's ``transfer`` block, its resolved
``adapt_policy``, and its resolved ``transfer_rules``. A notable detail
is that ``values`` is filtered to drop any ``resolved_*`` keys so the
raw authoring intent stays separated from the resolver-produced
bundles. These tests cover that filter, end-to-end extraction through a
real ``.lth`` example, and defaulting behaviour on missing blocks.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from lathe.parser import parse_file
from lathe.resolver import materialize_asset
from lathe.transfer_ir import TransferIR

ROOT = Path(__file__).resolve().parents[2]
ADAPT_EXAMPLE = ROOT / "examples" / "console_terminal_mobile_adapt.lth"


class TransferIRTests(unittest.TestCase):
    def test_basic_construction(self) -> None:
        ir = TransferIR(
            values={"adapt_policy": "p", "rules": ["r1"]},
            adapt_policy={"name": "p"},
            transfer_rules=[{"name": "r1"}],
        )
        self.assertEqual(ir.values["adapt_policy"], "p")
        self.assertEqual(ir.adapt_policy["name"], "p")
        self.assertEqual(ir.transfer_rules[0]["name"], "r1")

    def test_to_dict_round_trip(self) -> None:
        ir = TransferIR(
            values={"adapt_policy": "p", "rules": ["r1", "r2"]},
            adapt_policy={"name": "p", "mode": "adapt"},
            transfer_rules=[{"name": "r1"}, {"name": "r2"}],
        )
        payload = ir.to_dict()
        restored = TransferIR(**payload)
        self.assertEqual(restored.to_dict(), payload)
        self.assertEqual(set(payload), {"values", "adapt_policy", "transfer_rules"})

    def test_from_asset_filters_resolved_prefix_from_values(self) -> None:
        # ``values`` must contain only authoring-side fields — the
        # resolver's ``resolved_*`` keys are extracted into the dedicated
        # ``adapt_policy`` / ``transfer_rules`` fields instead.
        asset = {
            "transfer": {
                "adapt_policy": "p",
                "rules": ["r1"],
                "resolved_adapt_policy": {"name": "p"},
                "resolved_transfer_rules": [{"name": "r1"}],
            }
        }
        ir = TransferIR.from_asset(asset)
        self.assertIn("adapt_policy", ir.values)
        self.assertIn("rules", ir.values)
        self.assertNotIn("resolved_adapt_policy", ir.values)
        self.assertNotIn("resolved_transfer_rules", ir.values)
        self.assertEqual(ir.adapt_policy, {"name": "p"})
        self.assertEqual(ir.transfer_rules, [{"name": "r1"}])

    def test_from_asset_missing_block_defaults(self) -> None:
        ir = TransferIR.from_asset({})
        self.assertEqual(ir.values, {})
        self.assertEqual(ir.adapt_policy, {})
        self.assertEqual(ir.transfer_rules, [])

    def test_empty_transfer_rules_list(self) -> None:
        asset = {
            "transfer": {
                "adapt_policy": "p",
                "rules": [],
                "resolved_adapt_policy": {"name": "p"},
                "resolved_transfer_rules": [],
            }
        }
        ir = TransferIR.from_asset(asset)
        self.assertEqual(ir.values["rules"], [])
        self.assertEqual(ir.transfer_rules, [])

    def test_from_asset_real_mobile_adapt_example(self) -> None:
        # console_terminal_mobile_adapt.lth declares
        # ``adapt_policy = mobile_console_policy`` and
        # ``rules = [preserve_console_surface]`` — the IR must track both
        # after resolution.
        asset = materialize_asset(parse_file(ADAPT_EXAMPLE), "console_terminal_mobile")
        ir = TransferIR.from_asset(asset)
        self.assertEqual(ir.adapt_policy.get("name"), "mobile_console_policy")
        rule_names = [r.get("name") for r in ir.transfer_rules]
        self.assertEqual(rule_names, ["preserve_console_surface"])
        # Authoring-side view preserved, resolved keys filtered out.
        self.assertEqual(ir.values.get("adapt_policy"), "mobile_console_policy")
        for key in ir.values:
            self.assertFalse(str(key).startswith("resolved_"))

    def test_multiple_rules_preserve_ordering(self) -> None:
        # Rule ordering is significant (priority / application order); the
        # IR must preserve list order exactly rather than reordering.
        asset = {
            "transfer": {
                "resolved_transfer_rules": [
                    {"name": "high"},
                    {"name": "mid"},
                    {"name": "low"},
                ]
            }
        }
        ir = TransferIR.from_asset(asset)
        self.assertEqual([r["name"] for r in ir.transfer_rules], ["high", "mid", "low"])


if __name__ == "__main__":
    unittest.main()
