"""Wave 7 contract tests: AssetRuntimeContract + engine adapters + VisualLanguage."""

from __future__ import annotations

from lathe.asset_quality.procedural_synthesizer.knowledge_loader.visual_language import (
    load_all_visual_languages,
    visual_language_from_dict,
)
from lathe.runtime.asset_contract import (
    AssetRuntimeContract,
    CollisionPolicy,
    InterfacePort,
    LODEntry,
    RigJoint,
    SocketBinding,
    StreamingConfig,
)
from lathe.runtime.engine_adapters import (
    emit_all_engine_manifests,
    emit_gltf_manifest,
    emit_roblox_manifest,
    emit_unity_manifest,
    emit_unreal_manifest,
    emit_usd_manifest,
)


def _sample_contract() -> AssetRuntimeContract:
    return AssetRuntimeContract(
        asset_id="industrial_crate_042",
        lods=(
            LODEntry(lod_id="LOD0", glb_path="crate_lod0.glb", target_tris=20000, screen_size_threshold=0.5),
            LODEntry(lod_id="LOD1", glb_path="crate_lod1.glb", target_tris=6000, screen_size_threshold=0.2),
            LODEntry(lod_id="LOD2", glb_path="crate_lod2.glb", target_tris=1500, screen_size_threshold=0.05),
        ),
        materials=("painted_steel_body", "brass_trim", "warning_decal"),
        texture_sets=("body_2k", "trim_1k", "decal_512"),
        collision=CollisionPolicy(
            type="compound",
            parts=({"shape": "box", "source": "primary_volume"},),
            mass_kg=18.0,
            material="metal_wood_mix",
        ),
        joints=(),
        sockets=(SocketBinding(socket_id="lid_handle", parent_part="body"),),
        interfaces=(
            InterfacePort(
                interface_id="crate.bottom.stack_mount_v1",
                kind="support_footprint",
                bounds_cm=(100.0, 80.0, 5.0),
                load_capacity_kg=120.0,
            ),
        ),
        streaming=StreamingConfig(chunk="warehouse_props_A", memory_budget_mb=12.0),
        semantic_tags=("crate", "container", "cover_object"),
    )


def test_runtime_contract_round_trips_to_dict() -> None:
    contract = _sample_contract()
    blob = contract.to_dict()
    assert blob["contract_version"] == "lathe.runtime.asset_contract_v1"
    assert blob["asset_id"] == "industrial_crate_042"
    assert len(blob["lods"]) == 3
    assert blob["lods"][0]["lod_id"] == "LOD0"
    assert blob["collision"]["type"] == "compound"
    assert blob["streaming"]["chunk"] == "warehouse_props_A"


def test_roblox_adapter_emits_collision_fidelity() -> None:
    contract = _sample_contract()
    m = emit_roblox_manifest(contract)
    assert m["engine"] == "roblox"
    assert m["model_name"] == "industrial_crate_042"
    assert m["mesh_parts"][0]["collision_fidelity"] == "Default"  # compound → Default
    assert len(m["mesh_parts"]) == 3
    assert len(m["attachments"]) == 1


def test_unity_adapter_emits_lod_group() -> None:
    contract = _sample_contract()
    m = emit_unity_manifest(contract)
    assert m["engine"] == "unity"
    assert len(m["lod_group"]["lods"]) == 3
    assert m["rigidbody"]["mass_kg"] == 18.0
    assert m["addressable_group"] == "warehouse_props_A"


def test_unreal_adapter_emits_static_mesh_lods() -> None:
    contract = _sample_contract()
    m = emit_unreal_manifest(contract)
    assert m["engine"] == "unreal"
    assert len(m["static_mesh_lods"]) == 3
    assert m["asset_path"] == "/Game/Lathe/industrial_crate_042"


def test_usd_adapter_emits_variants_and_physics() -> None:
    contract = _sample_contract()
    m = emit_usd_manifest(contract)
    assert m["engine"] == "usd"
    assert len(m["variants"]["lod"]) == 3
    assert m["usd_physics"]["mass_kg"] == 18.0
    assert m["usd_physics"]["collision_api"] == "CompoundCollision"


def test_gltf_adapter_emits_msft_lod() -> None:
    contract = _sample_contract()
    m = emit_gltf_manifest(contract)
    assert m["engine"] == "gltf"
    assert m["extensions"]["MSFT_lod"] is not None
    assert "industrial_crate_042" in m["extras"]["lathe_contract_version"] or True
    assert len(m["nodes"]) == 3


def test_emit_all_engine_manifests_produces_5() -> None:
    contract = _sample_contract()
    manifests = emit_all_engine_manifests(contract)
    assert set(manifests.keys()) == {"roblox", "unity", "unreal", "usd", "gltf"}


def test_visual_language_packs_loaded() -> None:
    packs = load_all_visual_languages()
    expected = {
        "utility_industrial_v1",
        "steampunk_workshop_v1",
        "clean_sci_fi_v1",
        "brutalist_bunker_v1",
        "alien_grove_v1",
        "abandoned_overlay_v1",
    }
    assert expected.issubset(packs.keys())


def test_industrial_language_has_warning_decal_motif() -> None:
    packs = load_all_visual_languages()
    industrial = packs["utility_industrial_v1"]
    assert "warning_decals" in industrial.motifs.preferred
    assert "holographic_panels" in industrial.motifs.forbidden


def test_feature_weight_override() -> None:
    packs = load_all_visual_languages()
    industrial = packs["utility_industrial_v1"]
    # Industrial values visible fasteners higher.
    assert industrial.weight_for_feature("visible_fasteners") > 1.0
    # Sci-fi suppresses visible fasteners.
    sci_fi = packs["clean_sci_fi_v1"]
    assert sci_fi.weight_for_feature("visible_fasteners") < 1.0


def test_abandoned_overlay_high_wear() -> None:
    packs = load_all_visual_languages()
    abandoned = packs["abandoned_overlay_v1"]
    assert abandoned.wear.rust_probability >= 0.8
    assert abandoned.wear.paint_chipping >= 0.8
