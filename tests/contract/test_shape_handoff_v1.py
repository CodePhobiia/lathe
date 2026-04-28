"""Contract pin for ``lathe.shape.intent_mesh_handoff_v1`` (BL-25, Plan 04 Phase 9).

The contract ID ``lathe.shape.intent_mesh_handoff_v1`` is referenced at ~75 sites
across the codebase. These tests pin its bytes so any accidental change fails
loudly in CI. The hash test, in particular, is intended as a tripwire: when it
fails, a maintainer is expected to re-read the diff carefully before updating
the pinned hash here.
"""

from __future__ import annotations

import hashlib
import json
import unittest

import pytest
from lathe.backends import BACKENDS, STACKS, get_backend
from lathe.providers import PROVIDERS

pytestmark = pytest.mark.contract


CONTRACT_ID = "lathe.shape.intent_mesh_handoff_v1"

# Pinned outer field set of BACKENDS[CONTRACT_ID]. Sourced from the current
# ground truth in ``lathe/backends.py`` head 11abfa0. Add an entry here only
# when intentionally extending the contract surface; never silently widen.
PINNED_TOP_LEVEL_KEYS: frozenset[str] = frozenset(
    {
        "id",
        "version",
        "stage",
        "toolchain",
        "runtime_executor",
        "determinism_class",
        "supported_asset_kinds",
        "supported_shape_modes",
        "supported_preserve",
        "provider_slots",
        "contract",
    }
)

# Pinned set of fields inside the inner ``contract`` block.
PINNED_INNER_CONTRACT_KEYS: frozenset[str] = frozenset(
    {
        "summary",
        "inputs",
        "outputs",
    }
)

# Pinned required-output-fields the bundle must declare downstream consumers
# can rely on. Never quietly remove an entry here without a migration.
PINNED_REQUIRED_OUTPUT_FIELDS: frozenset[str] = frozenset(
    {
        "candidates[].mesh_uri",
        "candidates[].units",
        "candidates[].frame",
        "candidates[].candidate_id",
        "provenance.backend_id",
        "provenance.backend_version",
    }
)

# SHA-256 of the canonical-JSON-serialized contract dict at head 11abfa0.
# When this fails: the contract bytes drifted. Read the diff carefully —
# downstream is wired to the existing shape — then update this pin AND
# the field-set frozensets above to match.
PINNED_CONTRACT_SHA256 = "51e02c6ed7e524cca42d0e638aa936da222af5a006358bd1d4e931aea671b085"


def _canonical_bytes(payload: object) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


class ShapeHandoffV1IdentityTests(unittest.TestCase):
    def test_id_string_is_registered_in_backends(self) -> None:
        self.assertIn(CONTRACT_ID, BACKENDS)
        backend = BACKENDS[CONTRACT_ID]
        self.assertEqual(backend["id"], CONTRACT_ID)
        self.assertEqual(backend["stage"], "shape")
        self.assertIn("contract", backend)
        self.assertIsInstance(backend["contract"], dict)

    def test_id_is_default_shape_binding_for_hard_surface_stack(self) -> None:
        stack = STACKS["lathe.stack.hard_surface_game_asset_v1"]
        self.assertEqual(stack["stage_backends"]["shape"], CONTRACT_ID)


class ShapeHandoffV1FieldSetTests(unittest.TestCase):
    def test_top_level_field_set_pinned(self) -> None:
        backend = BACKENDS[CONTRACT_ID]
        actual = frozenset(backend.keys())
        added = actual - PINNED_TOP_LEVEL_KEYS
        removed = PINNED_TOP_LEVEL_KEYS - actual
        self.assertFalse(
            added or removed,
            msg=(
                f"Contract '{CONTRACT_ID}' top-level field set drifted. "
                f"Added: {sorted(added)}; Removed: {sorted(removed)}. "
                "Update PINNED_TOP_LEVEL_KEYS only if this is an intentional "
                "migration."
            ),
        )

    def test_inner_contract_field_set_pinned(self) -> None:
        contract = BACKENDS[CONTRACT_ID]["contract"]
        actual = frozenset(contract.keys())
        added = actual - PINNED_INNER_CONTRACT_KEYS
        removed = PINNED_INNER_CONTRACT_KEYS - actual
        self.assertFalse(
            added or removed,
            msg=(f"Inner contract block drifted. Added: {sorted(added)}; Removed: {sorted(removed)}."),
        )

    def test_required_output_fields_superset_of_pin(self) -> None:
        contract = BACKENDS[CONTRACT_ID]["contract"]
        required = frozenset(contract["outputs"]["required_fields"])
        missing = PINNED_REQUIRED_OUTPUT_FIELDS - required
        self.assertFalse(
            missing,
            msg=(
                f"Contract no longer guarantees required output fields: "
                f"{sorted(missing)}. Downstream stages depend on these."
            ),
        )


class ShapeHandoffV1HashStabilityTests(unittest.TestCase):
    def test_canonical_hash_pinned(self) -> None:
        backend = get_backend(CONTRACT_ID)
        actual = hashlib.sha256(_canonical_bytes(backend)).hexdigest()
        self.assertEqual(
            actual,
            PINNED_CONTRACT_SHA256,
            msg=(
                f"Contract bytes drifted. New sha256: {actual}. "
                "If intentional: update PINNED_CONTRACT_SHA256 + the field-set "
                "frozensets in this file. Otherwise: revert the source change."
            ),
        )


class ShapeHandoffV1ProviderRegistryTests(unittest.TestCase):
    def test_provider_slots_match_registry(self) -> None:
        backend = BACKENDS[CONTRACT_ID]
        slots = set(backend["provider_slots"])
        # Every advertised slot must resolve to a registered provider.
        unknown = slots - set(PROVIDERS.keys())
        self.assertFalse(
            unknown,
            msg=f"provider_slots references unregistered providers: {sorted(unknown)}",
        )

    def test_every_registered_shape_provider_advertises_supported_modes(self) -> None:
        # Minimum bundle-shape claim: every provider advertises which modes it
        # can serve under the shape contract. Without this, the mux can't
        # honor the contract's mode_requirements.
        contract_modes = set(BACKENDS[CONTRACT_ID]["supported_shape_modes"])
        for provider_id, provider in PROVIDERS.items():
            with self.subTest(provider=provider_id):
                self.assertIn("modes", provider, msg=f"{provider_id} missing modes")
                provider_modes = set(provider["modes"])
                self.assertTrue(
                    provider_modes.issubset(contract_modes),
                    msg=(
                        f"{provider_id} declares modes {sorted(provider_modes)} "
                        f"that exceed the contract modes {sorted(contract_modes)}"
                    ),
                )


class ShapeHandoffV1RegistryShapeTests(unittest.TestCase):
    def test_v1_pin_does_not_assume_uniqueness(self) -> None:
        # Future shape contracts (v2, v3, ...) may coexist in BACKENDS. The
        # v1 pin must remain valid regardless of how many shape backends are
        # registered alongside it.
        shape_backends = [bid for bid, b in BACKENDS.items() if b.get("stage") == "shape"]
        self.assertIn(CONTRACT_ID, shape_backends)
        # Don't assert exact count or uniqueness — only that v1 is present.
        self.assertGreaterEqual(len(shape_backends), 1)

    def test_get_backend_returns_independent_copy(self) -> None:
        # Mutating a fetched copy must not mutate the registered contract —
        # downstream code routinely augments returned bundles with provenance
        # fields and we must not let that leak back into the registry.
        backend = get_backend(CONTRACT_ID)
        backend["contract"]["summary"] = "MUTATED"
        backend["provider_slots"].append("lathe.provider.shape.fake_v9")
        fresh = get_backend(CONTRACT_ID)
        self.assertNotEqual(fresh["contract"]["summary"], "MUTATED")
        self.assertNotIn("lathe.provider.shape.fake_v9", fresh["provider_slots"])


if __name__ == "__main__":
    unittest.main()
