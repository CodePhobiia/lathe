from __future__ import annotations

import pytest
from lathe.scene.ids import (
    is_scene_entity_id,
    is_snake_id,
    require_scene_entity_id,
    scene_entity_id,
    snake_id,
)


def test_snake_id_normalizes_arbitrary_text() -> None:
    assert snake_id("A Forgotten Observatory!") == "a_forgotten_observatory"
    assert snake_id("500 years earlier") == "item_500_years_earlier"


def test_scene_entity_id_uses_schema_prefixes_and_suffixes() -> None:
    assert scene_entity_id("object", "Central Astrolabe Table", suffix=1) == "obj_central_astrolabe_table_001"
    assert scene_entity_id("region", "Central Chamber") == "region_central_chamber"
    assert scene_entity_id("relationship", "points toward moon") == "rel_points_toward_moon"
    assert scene_entity_id("material", "Bone Ivory") == "mat_bone_ivory"
    assert scene_entity_id("memory", "Initial Fact") == "mem_initial_fact"


def test_scene_entity_id_clamps_long_text_with_digest() -> None:
    entity_id = scene_entity_id("curiosity", "warm lens " * 30)

    assert len(entity_id) <= len("curiosity_") + 80
    assert entity_id.startswith("curiosity_warm_lens")
    assert is_scene_entity_id("curiosity", entity_id)


def test_id_predicates_match_wonder_schema_patterns() -> None:
    assert is_snake_id("alchemist_observatory")
    assert not is_snake_id("1bad_id")
    assert is_scene_entity_id("object", "obj_astrolabe_table_001")
    assert not is_scene_entity_id("object", "object_astrolabe_table_001")


def test_require_scene_entity_id_returns_value_or_clear_error() -> None:
    assert require_scene_entity_id("camera", "camera_reveal_001") == "camera_reveal_001"

    with pytest.raises(ValueError, match="camera ID must match"):
        require_scene_entity_id("camera", "reveal")


def test_scene_entity_id_rejects_unsupported_prefix() -> None:
    with pytest.raises(ValueError, match="unsupported scene entity prefix"):
        scene_entity_id("asset", "table")
