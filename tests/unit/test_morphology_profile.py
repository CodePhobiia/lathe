"""Tests for lathe.knowledge.morphology_profile_v1 (Wave 5)."""

from __future__ import annotations

from lathe.asset_quality.procedural_synthesizer.knowledge_loader.morphology import (
    load_all_morphology_profiles,
    profile_from_dict,
)


def test_crate_profile_loaded_with_required_parts() -> None:
    profiles = load_all_morphology_profiles()
    assert "container_crate_morphology_v1" in profiles
    crate = profiles["container_crate_morphology_v1"]
    required = crate.required_roles()
    assert "primary_volume" in required
    assert "corner_reinforcement" in required
    assert "lid_seam" in required
    assert "primary_material" in required


def test_door_profile_aspects_door_shaped() -> None:
    profiles = load_all_morphology_profiles()
    assert "swing_door_morphology_v1" in profiles
    door = profiles["swing_door_morphology_v1"]
    # Door body should be flat: Y aspect << X aspect, Z dominant.
    assert door.body.aspect_bounds["y"][1] < 0.15
    assert door.body.aspect_bounds["z"][0] >= 1.0
    assert door.body.long_axis == "Z"
    # Has hinge_line as required part.
    required = door.required_roles()
    assert "hinge_line" in required
    assert "handle" in required


def test_profile_round_trip_from_dict() -> None:
    raw = {
        "id": "test_morphology",
        "description": "test",
        "domain": "hard_surface",
        "body": {
            "archetype": "bounded_volume",
            "long_axis": "X",
            "expected_aspect": {"x": [0.8, 1.0], "y": [0.5, 0.7], "z": [0.4, 0.6]},
        },
        "parts_ladder": [
            {"role": "primary_volume", "required": True, "min_count": 1, "max_count": 1},
            {"role": "handle", "required": False, "min_count": 0, "max_count": 4},
        ],
        "anchor_emitters": [{"role": "side_face", "selector": "exterior_face"}],
        "default_relations": [
            {"source_role": "handle", "relation": "attached_to", "target_role": "side_face"}
        ],
    }
    profile = profile_from_dict(raw)
    assert profile.profile_id == "test_morphology"
    assert profile.required_roles() == ("primary_volume",)
    assert profile.role_min_count("primary_volume") == 1
    assert profile.role_min_count("handle") == 0
    assert len(profile.anchor_emitters) == 1
    assert len(profile.default_relations) == 1


def test_morphology_profile_drives_aspect() -> None:
    """The wired morphology aspect should produce door-like dimensions for the door alias."""
    from lathe.parser import parse_file
    from lathe.normalizer import normalize_program
    from lathe.resolver import materialize_asset
    from lathe.shape.procedural_program_path import _scale_to_dimensions, _aspect_for_morphology

    aspect = _aspect_for_morphology("swing_door_morphology_v1")
    assert aspect is not None
    # Door's Y should be very thin (door thickness).
    assert aspect[1] < 0.15
    # Door's Z should be dominant.
    assert aspect[2] >= 1.0

    dims = _scale_to_dimensions(
        {"type": "unit", "value": 2.1, "unit": "m"},
        kind="env_module",
        morphology_aspect=aspect,
    )
    # 2.1m * aspect_z midpoint (1.0) = 210cm tall.
    assert dims["z"] >= 200.0
    # Thickness should be very thin.
    assert dims["y"] < 20.0
