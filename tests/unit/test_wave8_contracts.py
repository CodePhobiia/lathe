"""Wave 8 tests: Class Anchor validator + render rigs + canonical views."""

from __future__ import annotations

from lathe.render_rigs.canonical_views import (
    AUXILIARY_PASSES,
    CANONICAL_VIEWS,
    auto_representation_for_feature,
    projected_pixel_width,
    view_camera_position,
)
from lathe.render_rigs.standard_rigs import LIGHTING_RIGS
from lathe.validators.class_anchor import (
    evaluate_class_anchor,
    load_all_rubrics,
)


def test_all_rubrics_loaded() -> None:
    rubrics = load_all_rubrics()
    expected = {"crate_v1", "door_v1", "panel_v1", "terminal_v1", "weapon_v1"}
    assert expected.issubset(rubrics.keys())


def test_crate_rubric_required_checks_named() -> None:
    rubrics = load_all_rubrics()
    crate = rubrics["crate_v1"]
    required = {c.evidence_key for c in crate.required_checks()}
    assert "bounded_volume_present" in required
    assert "corner_reinforcement_present" in required
    assert "lid_seam_or_trim_present" in required
    assert "material_separation" in required


def test_class_anchor_fires_on_featureless_crate() -> None:
    """A featureless crate (only primary_volume, no corners/trim) should fail crate_v1."""
    asset = {
        "name": "test_crate",
        "kind": "hard_surface_prop",
        "intent": {"kind": "hard_surface_prop", "scale": {"type": "unit", "value": 0.9, "unit": "m"}},
    }
    runtime = {
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
                    "face_count": 1000,
                    "extents": [90.0, 60.0, 50.0],
                }
            }
        },
    }
    result = evaluate_class_anchor(asset, runtime)
    assert len(result["diagnostics"]) == 1
    diag = result["diagnostics"][0]
    assert diag["code"] == "L6500"
    assert diag["name"] == "class_anchor_fail.crate_v1"
    assert "add_secondary_features" in diag["repair_actions"]
    # Missing required: corner_reinforcement, lid_seam_or_trim, material_separation.
    assert result["metrics"]["evidence"]["corner_reinforcement_present"] is False
    assert result["metrics"]["evidence"]["lid_seam_or_trim_present"] is False


def test_class_anchor_passes_composed_crate() -> None:
    """A crate with all required roles should pass crate_v1."""
    asset = {
        "name": "test_crate",
        "kind": "hard_surface_prop",
        "intent": {"kind": "hard_surface_prop", "scale": {"type": "unit", "value": 0.9, "unit": "m"}},
    }
    runtime = {
        "shape": {
            "bundle": {
                "shape_program": {
                    "ops": [{"op": "op.material_zone"}]
                },
                "runtime_candidates": [
                    {"meta": {"shape_ir": {"synthesized_graph_nodes": [
                        {"node_type": "primary_volume"},
                        {"node_type": "bracket"},
                        {"node_type": "trim"},
                        {"node_type": "handle"},
                        {"node_type": "material_zone"},
                    ]}}}
                ],
            }
        },
        "topology": {
            "bundle": {
                "mesh_stats": {
                    "face_count": 50000,
                    "extents": [110.0, 65.0, 50.0],
                }
            }
        },
    }
    result = evaluate_class_anchor(asset, runtime)
    assert result["diagnostics"] == []
    assert result["metrics"]["evidence"]["bounded_volume_present"] is True
    assert result["metrics"]["evidence"]["corner_reinforcement_present"] is True
    assert result["metrics"]["evidence"]["lid_seam_or_trim_present"] is True


def test_door_rubric_required_hinge_and_handle() -> None:
    rubrics = load_all_rubrics()
    door = rubrics["door_v1"]
    required = {c.evidence_key for c in door.required_checks()}
    assert "vertical_panel_present" in required
    assert "hinge_present" in required
    assert "handle_present" in required


def test_lighting_rigs_complete() -> None:
    assert set(LIGHTING_RIGS.keys()) == {
        "neutral_studio",
        "three_point_product",
        "outdoor_gameplay",
        "low_key_rim",
    }
    # Each rig has at least one light.
    for rig in LIGHTING_RIGS.values():
        assert len(rig.lights) >= 1


def test_canonical_views_complete() -> None:
    assert len(CANONICAL_VIEWS) == 8
    ids = {v.view_id for v in CANONICAL_VIEWS}
    assert "front" in ids
    assert "top" in ids
    assert "three_quarter_front_right" in ids


def test_auxiliary_passes() -> None:
    expected = {"rgb", "normal", "depth", "material_id", "part_id", "silhouette"}
    assert expected.issubset(set(AUXILIARY_PASSES))


def test_view_camera_position_distance() -> None:
    pos = view_camera_position(CANONICAL_VIEWS[0], (0.0, 0.0, 0.0), 100.0)
    # Front view at distance_factor 1.5 → 150cm radial distance.
    distance = (pos[0] ** 2 + pos[1] ** 2 + pos[2] ** 2) ** 0.5
    assert 140 < distance < 160


def test_projected_pixel_width() -> None:
    # 0.6cm chamfer at 2m camera distance, 60° vFOV, 1080p ≈ 2.8px.
    px = projected_pixel_width(0.006, 1080, 2.0, 60.0)
    assert 2.5 < px < 3.0


def test_auto_representation_decision() -> None:
    # Small non-silhouette feature → normal stamp or texture.
    assert auto_representation_for_feature(0.3, is_silhouette_feature=False) in (
        "texture_only",
        "normal_stamp",
        "removed",
    )
    # Large silhouette feature → geometry.
    assert auto_representation_for_feature(5.0, is_silhouette_feature=True) == "geometry"
    # Sub-pixel non-silhouette feature → removed.
    assert auto_representation_for_feature(0.01, is_silhouette_feature=False) == "removed"
