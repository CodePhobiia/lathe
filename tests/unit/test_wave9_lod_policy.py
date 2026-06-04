"""Wave 9: LOD policy compiler tests."""

from __future__ import annotations

from lathe.asset_quality.lod_policy import (
    DEFAULT_LOD_LADDER,
    LODPolicy,
    default_lod_policy,
    projected_px_for_camera_distance,
    representation_for_lod,
)


def test_default_ladder_descends() -> None:
    """Target tris should decrease with LOD level."""
    tris = [t for _, t, _ in DEFAULT_LOD_LADDER]
    assert tris == sorted(tris, reverse=True)


def test_crate_lod_policy_complete() -> None:
    policy = default_lod_policy("crate")
    assert len(policy.levels) == 4
    ids = [l.lod_id for l in policy.levels]
    assert ids == ["LOD0", "LOD1", "LOD2", "LOD3"]
    # LOD0 has highest tris.
    assert policy.levels[0].target_tris > policy.levels[-1].target_tris


def test_door_lod_policy_drops_fasteners_early() -> None:
    """Door class LOD policy degrades fasteners earlier than crate."""
    door = default_lod_policy("door")
    # At LOD1, door fasteners go to normal_stamp; at LOD2 to texture.
    assert door.levels[1].fastener_representation == "normal_stamp"
    assert door.levels[2].fastener_representation == "texture_only"


def test_projected_pixel_width() -> None:
    # 6mm chamfer at 2m, 1080p, 60° vFOV.
    px = projected_px_for_camera_distance(0.6, 2.0)
    assert 2.5 < px < 3.0


def test_representation_geometry_for_silhouette_at_close_lod() -> None:
    policy = default_lod_policy("crate")
    rep = representation_for_lod(
        feature_world_cm=3.0,  # 3cm bracket
        lod_level=policy.levels[0],  # LOD0
        is_silhouette_feature=True,
    )
    assert rep.representation == "geometry"


def test_representation_drops_to_texture_at_distant_lod() -> None:
    policy = default_lod_policy("crate")
    rep = representation_for_lod(
        feature_world_cm=0.5,  # small fastener
        lod_level=policy.levels[-1],  # LOD3
        is_silhouette_feature=False,
    )
    assert rep.representation in ("removed", "texture_only")
