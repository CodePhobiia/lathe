"""Tests for the featureless_silhouette validator (B10).

Two surfaces:

1. The validator fires on the canonical "featureless cube" signature
   (hard-surface kind, body-only synthesis, no protrusions).
2. The diagnostic's ``repair_actions`` field is consumed by the
   repair_loop's diagnostic classifier and routes to an allowed
   shape-repair action (B11 wiring).
"""

from __future__ import annotations

from lathe.repair_loop import _SHAPE_REPAIR_ROUTE_ACTIONS, _diagnostic_repair_actions
from lathe.validators.featureless_silhouette import (
    VERSION,
    evaluate_featureless_silhouette,
)


def _asset(kind: str = "hard_surface_prop", scale_m: float = 0.9) -> dict:
    return {
        "name": "test_crate",
        "kind": kind,
        "intent": {
            "kind": kind,
            "scale": {"type": "unit", "value": scale_m, "unit": "m"},
        },
    }


def _runtime(
    synthesized_node_count: int,
    face_count: int,
    extents: tuple[float, float, float] | None,
) -> dict:
    candidate_meta: dict = {
        "shape_assessment": {
            "synthesized_node_count": synthesized_node_count,
            "shape_source": "procedural_synthesizer",
            "family_dispatch_used": False,
            "attempted_via": "procedural_engine",
        },
    }
    topology_bundle: dict = {
        "mesh_stats": {"face_count": face_count},
    }
    if extents is not None:
        topology_bundle["mesh_stats"]["bounds_cm"] = {
            "min": [-extents[0] / 2, -extents[1] / 2, -extents[2] / 2],
            "max": [extents[0] / 2, extents[1] / 2, extents[2] / 2],
        }
    return {
        "shape": {
            "bundle": {
                "runtime_candidates": [{"meta": candidate_meta}],
            }
        },
        "topology": {"bundle": topology_bundle},
    }


def test_fires_on_featureless_cube() -> None:
    """Body-only synthesis with flush mesh extents fires the diagnostic."""
    asset = _asset(scale_m=0.9)  # 90cm → dimensions ~(90, 63, 49.5)
    runtime = _runtime(
        synthesized_node_count=1,  # only primary_volume — low_node_count fires
        face_count=5000,
        extents=(90.0, 63.0, 49.5),  # exactly matches intent — no protrusions
    )

    result = evaluate_featureless_silhouette(asset, runtime)

    assert result["version"] == VERSION
    diagnostics = result["diagnostics"]
    assert len(diagnostics) == 1
    diag = diagnostics[0]
    assert diag["code"] == "L6403"
    assert diag["name"] == "featureless_silhouette"
    assert diag["severity"] == "warning"
    assert diag["asset"] == "test_crate"
    metrics = diag["details"]
    assert metrics["low_node_count"] is True
    assert metrics["has_visible_protrusion"] is False


def test_skips_on_composed_asset() -> None:
    """A composed asset (many nodes + visible protrusions) does not fire."""
    asset = _asset(scale_m=0.9)
    runtime = _runtime(
        synthesized_node_count=13,  # auto-graph + policy expanded
        face_count=125000,
        extents=(110.0, 63.0, 49.5),  # X extent exceeds intent.x=90 → protrusion
    )
    result = evaluate_featureless_silhouette(asset, runtime)
    assert result["diagnostics"] == []
    assert result["metrics"]["fires"] is False


def test_skips_on_unknown_kind() -> None:
    """Non-hard-surface kinds (vegetation, fluid) don't activate."""
    asset = _asset(kind="vegetation", scale_m=0.9)
    runtime = _runtime(
        synthesized_node_count=1,
        face_count=500,
        extents=(90.0, 63.0, 49.5),
    )
    result = evaluate_featureless_silhouette(asset, runtime)
    assert result["diagnostics"] == []


def test_skips_below_face_floor() -> None:
    """Tiny meshes don't activate the diagnostic."""
    asset = _asset(scale_m=0.05)  # 5cm
    runtime = _runtime(
        synthesized_node_count=1,
        face_count=50,  # below 200 floor
        extents=(5.0, 3.5, 2.75),
    )
    result = evaluate_featureless_silhouette(asset, runtime)
    assert result["diagnostics"] == []


def test_repair_actions_route_to_shape_repair() -> None:
    """The diagnostic's repair_actions feeds the repair_loop classifier (B11 wiring)."""
    asset = _asset(scale_m=0.9)
    runtime = _runtime(
        synthesized_node_count=1,
        face_count=5000,
        extents=(90.0, 63.0, 49.5),
    )
    result = evaluate_featureless_silhouette(asset, runtime)
    diag = result["diagnostics"][0]
    # The validator emits repair_actions in the dict shape the repair
    # loop reads.
    assert diag["repair_actions"] == ["add_secondary_features"]
    # And the repair_loop's diagnostic classifier picks it up.
    actions = _diagnostic_repair_actions({"diagnostics": [diag]})
    assert "add_secondary_features" in actions
    # add_secondary_features is in the shape-repair route action set,
    # so it routes via regenerate_with_patch.
    assert "add_secondary_features" in _SHAPE_REPAIR_ROUTE_ACTIONS
