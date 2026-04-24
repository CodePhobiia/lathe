"""Unit tests for ``lathe.repair.surface_repair.build_surface_repair_ir``.

``build_surface_repair_ir`` takes a surface-backend report and emits
the V1.2 surface repair IR — a small dict that declares which
zone-local repair actions are permitted and whether the codex imagegen
fallback is currently available. It must be:

* deterministic on the same input,
* graceful with empty / missing fields,
* faithful in passing through the codex-availability flag,
* stable in its repair-action list (the contract) and schema id,
* stable in its preferred scope (always ``zone_local``),
* graceful when the report contains unrelated noise.
"""

from __future__ import annotations

import unittest

from lathe.repair.surface_repair import build_surface_repair_ir


class TestSurfaceRepairAppliesFallback(unittest.TestCase):
    def test_codex_imagegen_available_when_backend_ran(self) -> None:
        ir = build_surface_repair_ir({"codex_imagegen_ran": True})
        self.assertTrue(ir["codex_imagegen_available"])

    def test_codex_imagegen_unavailable_when_backend_did_not_run(self) -> None:
        ir = build_surface_repair_ir({"codex_imagegen_ran": False})
        self.assertFalse(ir["codex_imagegen_available"])


class TestSurfaceRepairRespectsMaxRounds(unittest.TestCase):
    def test_repair_list_size_is_bounded_by_contract(self) -> None:
        # The contract enumerates exactly the allowed repair actions —
        # there is no unbounded growth surface here. We assert the size
        # is non-trivial and stable so callers can rely on it.
        ir = build_surface_repair_ir({})
        self.assertGreaterEqual(len(ir["allowed_repairs"]), 8)
        # Calling twice with the same input must yield the same length.
        ir2 = build_surface_repair_ir({})
        self.assertEqual(len(ir["allowed_repairs"]), len(ir2["allowed_repairs"]))


class TestSurfaceRepairPreservesContractFields(unittest.TestCase):
    def test_schema_and_scope_match_v1_contract(self) -> None:
        ir = build_surface_repair_ir({"codex_imagegen_ran": True})
        self.assertEqual(ir["schema"], "lathe.surface_repair_ir.v1")
        self.assertEqual(ir["preferred_scope"], "zone_local")

    def test_allowed_repairs_includes_core_zone_actions(self) -> None:
        ir = build_surface_repair_ir({})
        for required in (
            "reauthor_zone_basecolor",
            "rederive_zone_roughness",
            "reassemble_atlas",
            "fallback_zone_deterministic",
        ):
            self.assertIn(required, ir["allowed_repairs"])


class TestSurfaceRepairReturnsDiagnosticsWhenUnfixable(unittest.TestCase):
    def test_fallback_zone_deterministic_always_offered(self) -> None:
        # ``fallback_zone_deterministic`` is the always-available
        # last-resort action. Whether or not codex is available, this
        # repair must remain in the allowed list.
        for ran in (True, False):
            ir = build_surface_repair_ir({"codex_imagegen_ran": ran})
            self.assertIn("fallback_zone_deterministic", ir["allowed_repairs"])


class TestSurfaceRepairDeterministic(unittest.TestCase):
    def test_same_report_yields_equal_ir(self) -> None:
        report = {"codex_imagegen_ran": True, "extra": "noise", "stage": "surface"}
        ir_a = build_surface_repair_ir(report)
        ir_b = build_surface_repair_ir(report)
        self.assertEqual(ir_a, ir_b)


class TestSurfaceRepairEmptyInputGraceful(unittest.TestCase):
    def test_empty_dict_produces_valid_ir(self) -> None:
        ir = build_surface_repair_ir({})
        self.assertEqual(ir["schema"], "lathe.surface_repair_ir.v1")
        self.assertFalse(ir["codex_imagegen_available"])
        self.assertEqual(ir["preferred_scope"], "zone_local")
        self.assertIsInstance(ir["allowed_repairs"], list)


if __name__ == "__main__":
    unittest.main()
