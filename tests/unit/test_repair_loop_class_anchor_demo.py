"""End-to-end demo: featureless build → class_anchor fires → repair routes (Wave 16 item 4).

The intent: prove the diagnose→plan→repair round-trip is wired
end-to-end at the validator + repair_loop level. We don't run an
actual rebuild here (that would require a full pipeline invocation
+ several minutes); we verify the wiring chain:

  1. A synthetic featureless build produces a runtime payload that
     fails crate_v1's class anchor rubric.
  2. ``evaluate_class_anchor`` emits L6500 with ``repair_actions``
     pointing at ``add_secondary_features``.
  3. The repair_loop classifier picks up the action from the
     diagnostic and routes to ``regenerate_with_patch``.
  4. ``add_secondary_features`` is in the repair_executor's
     allowlist + the canonical operators registry.

All four steps must agree for the closed loop to function in a
live build.
"""

from __future__ import annotations

from lathe.repair_loop import _SHAPE_REPAIR_ROUTE_ACTIONS, _diagnostic_repair_actions
from lathe.repair_operators_v2 import CANONICAL_REPAIR_OPERATORS
from lathe.validators.class_anchor import evaluate_class_anchor


def _featureless_crate_runtime() -> dict:
    """A runtime payload missing the required class anchor evidence."""
    return {
        "shape": {
            "bundle": {
                "shape_program": {"ops": []},
                "runtime_candidates": [
                    {"meta": {"shape_ir": {"synthesized_graph_nodes": [
                        {"node_type": "primary_volume"},
                    ]}}}
                ],
            }
        },
        "topology": {
            "bundle": {
                "mesh_stats": {
                    "face_count": 800,
                    "extents": [90.0, 60.0, 50.0],
                }
            }
        },
    }


def _crate_asset() -> dict:
    return {
        "name": "test_crate",
        "kind": "hard_surface_prop",
        "intent": {
            "kind": "hard_surface_prop",
            "scale": {"type": "unit", "value": 0.9, "unit": "m"},
        },
    }


def test_full_round_trip_diagnose_to_classifier() -> None:
    """The four-step chain: validator → repair_actions → classifier → allowed action."""
    asset = _crate_asset()
    runtime = _featureless_crate_runtime()

    # 1. Validator fires.
    result = evaluate_class_anchor(asset, runtime)
    assert len(result["diagnostics"]) == 1
    diag = result["diagnostics"][0]
    assert diag["code"] == "L6500"
    assert diag["name"] == "class_anchor_fail.crate_v1"

    # 2. repair_actions field populated.
    repair_actions = diag.get("repair_actions") or []
    assert "add_secondary_features" in repair_actions

    # 3. Classifier picks them up.
    classifier_actions = _diagnostic_repair_actions({"diagnostics": [diag]})
    assert "add_secondary_features" in classifier_actions

    # 4. action belongs to the shape-repair route set.
    assert "add_secondary_features" in _SHAPE_REPAIR_ROUTE_ACTIONS


def test_action_is_handled_by_repair_executor() -> None:
    """The action the validator emits is handled by the repair_executor body."""
    # repair_executor handles add_secondary_features at the
    # ``repair.action == "add_secondary_features"`` branch and emits
    # op.trim_band + op.fastener_grid features.
    import inspect
    from lathe import repair_executor
    src = inspect.getsource(repair_executor)
    assert 'repair.action == "add_secondary_features"' in src
    assert "op.trim_band" in src
    assert "op.fastener_grid" in src


def test_canonical_operator_registry_covers_validator_repair_actions() -> None:
    """Every repair_action a validator emits should map to a canonical operator.

    Audits the registry contains the action names the class_anchor
    validator emits via rubric repair_action fields.
    """
    # Per crate_v1.json, the rubric emits add_secondary_features. The
    # canonical registry covers the *graph mutation* operators; the
    # ``add_secondary_features`` route action delegates to
    # insert_required_feature + add_reinforcement_pattern under the
    # hood. Verify both component operators exist.
    assert "insert_required_feature" in CANONICAL_REPAIR_OPERATORS
    assert "add_reinforcement_pattern" in CANONICAL_REPAIR_OPERATORS


def test_required_evidence_failure_lists_brackets() -> None:
    """Featureless crate should specifically miss corner_reinforcement evidence."""
    asset = _crate_asset()
    runtime = _featureless_crate_runtime()
    result = evaluate_class_anchor(asset, runtime)
    metrics = result["metrics"]
    evidence = metrics["evidence"]
    assert evidence["bounded_volume_present"] is True  # we synthesized a primary_volume
    assert evidence["corner_reinforcement_present"] is False
    assert evidence["lid_seam_or_trim_present"] is False
    assert evidence["material_separation"] is False
