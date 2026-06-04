"""Engine adapter manifest emitters (Wave 7).

Each adapter takes an ``AssetRuntimeContract`` and produces a
manifest the engine importer consumes. Adapters live here as
*declarative manifests*: actual engine import code is the engine's
job; Lathe's job is to emit truthful, well-typed manifest data.

Per research §13: Roblox, Unity, Unreal each need different metadata.
USD + glTF are the interchange formats. This module produces all five.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .asset_contract import AssetRuntimeContract


def emit_roblox_manifest(contract: AssetRuntimeContract) -> dict[str, Any]:
    """Roblox MeshPart hierarchy + CollisionFidelity + HingeConstraint + Attachments."""
    manifest: dict[str, Any] = {
        "engine": "roblox",
        "model_name": contract.asset_id,
        "lod_strategy": {
            "model_level_of_detail": "StreamingMesh" if len(contract.lods) > 1 else "Disabled",
            "lod_count": len(contract.lods),
        },
        "mesh_parts": [
            {
                "name": l.lod_id,
                "mesh_uri": l.glb_path,
                "collision_fidelity": _roblox_collision_fidelity(contract.collision.type),
            }
            for l in contract.lods
        ],
        "constraints": [
            {
                "name": j.joint_id,
                "class": "HingeConstraint" if j.type == "hinge" else "WeldConstraint",
                "limits_min_deg": j.limits_deg[0],
                "limits_max_deg": j.limits_deg[1],
                "actuator_type": "Motor" if j.motorized else "None",
            }
            for j in contract.joints
        ],
        "attachments": [
            {
                "name": s.socket_id,
                "parent": s.parent_part,
                "cframe_translation_cm": list(s.transform_world_cm),
                "cframe_euler_deg": list(s.rotation_euler_deg),
            }
            for s in contract.sockets
        ],
        "tags": list(contract.semantic_tags),
    }
    return manifest


def _roblox_collision_fidelity(collision_type: str) -> str:
    return {
        "box": "Box",
        "convex": "Hull",
        "compound": "Default",
        "mesh": "PreciseConvexDecomposition",
        "none": "Default",
    }.get(collision_type, "Default")


def emit_unity_manifest(contract: AssetRuntimeContract) -> dict[str, Any]:
    """Unity GameObject hierarchy + LODGroup + colliders + HingeJoint + light probes."""
    return {
        "engine": "unity",
        "prefab_name": contract.asset_id,
        "lod_group": {
            "lods": [
                {
                    "renderer_glb": l.glb_path,
                    "screen_relative_transition_height": max(0.01, l.screen_size_threshold),
                }
                for l in contract.lods
            ],
        },
        "renderers": [
            {"name": l.lod_id, "mesh": l.glb_path, "materials": list(contract.materials)}
            for l in contract.lods
        ],
        "colliders": [
            {
                "type": _unity_collider_type(contract.collision.type),
                "is_compound": contract.collision.type == "compound",
                "parts": [dict(p) for p in contract.collision.parts],
            }
        ],
        "joints": [
            {
                "type": "HingeJoint" if j.type == "hinge" else "FixedJoint",
                "anchor_cm": list(j.pivot_world_cm),
                "axis": list(j.axis_world),
                "limits_min_deg": j.limits_deg[0],
                "limits_max_deg": j.limits_deg[1],
            }
            for j in contract.joints
        ],
        "audio_sources": [dict(a) for a in contract.audio_emitters],
        "light_probe_proxy_volumes": [dict(l) for l in contract.light_probe_anchors],
        "rigidbody": {"mass_kg": contract.collision.mass_kg} if contract.collision.enabled else None,
        "tags": list(contract.semantic_tags),
        "addressable_group": contract.streaming.chunk,
    }


def _unity_collider_type(collision_type: str) -> str:
    return {
        "box": "BoxCollider",
        "convex": "MeshCollider",
        "compound": "MultipleColliders",
        "mesh": "MeshCollider",
        "none": "None",
    }.get(collision_type, "BoxCollider")


def emit_unreal_manifest(contract: AssetRuntimeContract) -> dict[str, Any]:
    """Unreal StaticMesh / Blueprint + LODs + simple/complex collision + sockets + constraints."""
    return {
        "engine": "unreal",
        "asset_path": f"/Game/Lathe/{contract.asset_id}",
        "static_mesh_lods": [
            {"lod_index": i, "screen_size": l.screen_size_threshold, "source_glb": l.glb_path}
            for i, l in enumerate(contract.lods)
        ],
        "simple_collision": {
            "type": _unreal_simple_collision(contract.collision.type),
            "compound_parts": [dict(p) for p in contract.collision.parts],
        },
        "complex_collision": "UseComplexAsSimple" if contract.collision.type == "mesh" else "Default",
        "sockets": [
            {
                "name": s.socket_id,
                "relative_location_cm": list(s.transform_world_cm),
                "relative_rotation_deg": list(s.rotation_euler_deg),
            }
            for s in contract.sockets
        ],
        "physics_constraints": [
            {
                "name": j.joint_id,
                "type": "PhysicsConstraintActor",
                "bone_a": j.parent_part,
                "bone_b": j.child_part,
                "linear_limit_size_cm": 0.0,
                "angular_limit_deg": [j.limits_deg[0], j.limits_deg[1]],
            }
            for j in contract.joints
        ],
        "audio_components": [dict(a) for a in contract.audio_emitters],
        "nav_modifier_volumes": [dict(n) for n in (contract.nav_hints.get("modifiers", []) or [])],
        "tags": list(contract.semantic_tags),
        "hlod_streaming_group": contract.streaming.chunk,
    }


def _unreal_simple_collision(collision_type: str) -> str:
    return {
        "box": "BoxSimplified",
        "convex": "ConvexHullSimplified",
        "compound": "CompoundSimplified",
        "mesh": "ComplexAsSimple",
        "none": "None",
    }.get(collision_type, "BoxSimplified")


def emit_usd_manifest(contract: AssetRuntimeContract) -> dict[str, Any]:
    """USD variants + GeomSubset + UsdPhysics + UsdLux + proxy/render purpose."""
    return {
        "engine": "usd",
        "prim_path": f"/Lathe/{contract.asset_id}",
        "variants": {
            "lod": [l.lod_id for l in contract.lods],
            "materials": list(contract.materials),
        },
        "geom_subsets": [
            {"name": f"{contract.asset_id}_subset_{i}", "material_binding": m}
            for i, m in enumerate(contract.materials)
        ],
        "usd_physics": {
            "rigid_body_api_applied": contract.collision.enabled,
            "mass_kg": contract.collision.mass_kg,
            "collision_api": _usd_collision_kind(contract.collision.type),
        },
        "usd_lux_anchors": [dict(l) for l in contract.light_probe_anchors],
        "purpose": "render",
        "proxy_purpose_lod": contract.lods[-1].lod_id if contract.lods else None,
    }


def _usd_collision_kind(collision_type: str) -> str:
    return {
        "box": "BoxCollision",
        "convex": "ConvexHullCollision",
        "compound": "CompoundCollision",
        "mesh": "MeshCollision",
        "none": "None",
    }.get(collision_type, "BoxCollision")


def emit_gltf_manifest(contract: AssetRuntimeContract) -> dict[str, Any]:
    """glTF node hierarchy + mesh primitives + materials + MSFT_lod sidecar."""
    return {
        "engine": "gltf",
        "asset_id": contract.asset_id,
        "scene_root": f"{contract.asset_id}_root",
        "nodes": [
            {"name": l.lod_id, "mesh_uri": l.glb_path, "lod_index": i}
            for i, l in enumerate(contract.lods)
        ],
        "materials": list(contract.materials),
        "extensions": {
            "MSFT_lod": {
                "lods": [l.lod_id for l in contract.lods[1:]],  # primary is LOD0
                "screen_coverages": [l.screen_size_threshold for l in contract.lods[1:]],
            }
            if len(contract.lods) > 1
            else None,
        },
        "extras": {
            "lathe_contract_version": "lathe.runtime.asset_contract_v1",
            "semantic_tags": list(contract.semantic_tags),
            "interfaces": [
                {"id": i.interface_id, "kind": i.kind} for i in contract.interfaces
            ],
        },
    }


ENGINE_ADAPTERS: Mapping[str, Any] = {
    "roblox": emit_roblox_manifest,
    "unity": emit_unity_manifest,
    "unreal": emit_unreal_manifest,
    "usd": emit_usd_manifest,
    "gltf": emit_gltf_manifest,
}


def emit_all_engine_manifests(
    contract: AssetRuntimeContract,
) -> dict[str, dict[str, Any]]:
    """Emit all 5 engine adapter manifests for a runtime contract."""
    return {engine: emitter(contract) for engine, emitter in ENGINE_ADAPTERS.items()}


__all__ = [
    "emit_roblox_manifest",
    "emit_unity_manifest",
    "emit_unreal_manifest",
    "emit_usd_manifest",
    "emit_gltf_manifest",
    "ENGINE_ADAPTERS",
    "emit_all_engine_manifests",
]
