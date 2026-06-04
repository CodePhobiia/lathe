"""Engine adapter manifest validation (Wave 25 / P7+P14).

Validates that each emitted manifest conforms to the schema its target
engine expects. Without live engine importers in the test
environment, validation runs against declarative engine schemas (per-
engine JSON shape requirements) — proving the manifest's structure
without actually invoking the engine.

The next integration step (engine-importer wiring) is the responsibility
of the engine bridges; this module's job is "ready-to-import" certification.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

CONTRACT_VERSION = "lathe.runtime.engine_validator_v1"


@dataclass(frozen=True)
class EngineValidationResult:
    """Outcome of validating one engine manifest."""

    engine: str
    valid: bool
    missing_keys: tuple[str, ...] = ()
    notes: str = ""


# Per-engine required-keys table. Each entry names the top-level keys
# the target engine's importer expects to see in the manifest dict.
_ENGINE_REQUIRED_KEYS: Mapping[str, tuple[str, ...]] = {
    "roblox": ("engine", "model_name", "mesh_parts", "constraints", "attachments", "tags"),
    "unity": ("engine", "prefab_name", "lod_group", "renderers", "colliders", "joints"),
    "unreal": (
        "engine",
        "asset_path",
        "static_mesh_lods",
        "simple_collision",
        "complex_collision",
        "sockets",
        "physics_constraints",
    ),
    "usd": ("engine", "prim_path", "variants", "geom_subsets", "usd_physics"),
    "gltf": ("engine", "asset_id", "scene_root", "nodes", "materials", "extensions"),
}


def validate_engine_manifest(engine: str, manifest: Mapping[str, Any]) -> EngineValidationResult:
    """Validate that ``manifest`` has the keys ``engine`` requires.

    Doesn't actually invoke the engine — runs against the declarative
    required-keys table. Real engine import is the integration test
    layer above this.
    """
    required = _ENGINE_REQUIRED_KEYS.get(engine)
    if required is None:
        return EngineValidationResult(
            engine=engine,
            valid=False,
            missing_keys=(),
            notes=f"unknown engine: {engine}",
        )
    missing = tuple(k for k in required if k not in manifest)
    return EngineValidationResult(
        engine=engine,
        valid=not missing,
        missing_keys=missing,
        notes="" if not missing else f"manifest missing {len(missing)} required keys",
    )


def validate_all_engine_manifests(
    manifests: Mapping[str, Mapping[str, Any]],
) -> dict[str, EngineValidationResult]:
    """Validate each manifest against its target engine."""
    return {engine: validate_engine_manifest(engine, m) for engine, m in manifests.items()}


def validate_hinge_physics(rig_joint: Mapping[str, Any]) -> EngineValidationResult:
    """Sanity-check a RigJoint's hinge parameters before engine emission.

    Required: axis_world non-zero magnitude, limits_deg ordered
    correctly, default_angle_deg within limits.
    """
    axis = rig_joint.get("axis_world") or [0, 0, 0]
    if not isinstance(axis, (list, tuple)) or len(axis) != 3:
        return EngineValidationResult(
            engine="rig", valid=False, notes="axis_world must be 3-tuple"
        )
    mag = (axis[0] ** 2 + axis[1] ** 2 + axis[2] ** 2) ** 0.5
    if mag < 1e-6:
        return EngineValidationResult(
            engine="rig", valid=False, notes="axis_world has zero magnitude"
        )
    limits = rig_joint.get("limits_deg") or [-180, 180]
    if not isinstance(limits, (list, tuple)) or len(limits) != 2:
        return EngineValidationResult(
            engine="rig", valid=False, notes="limits_deg must be 2-tuple"
        )
    if limits[0] >= limits[1]:
        return EngineValidationResult(
            engine="rig",
            valid=False,
            notes=f"limits inverted: min {limits[0]} >= max {limits[1]}",
        )
    default = float(rig_joint.get("default_angle_deg", 0.0))
    if default < limits[0] or default > limits[1]:
        return EngineValidationResult(
            engine="rig",
            valid=False,
            notes=f"default {default} outside limits [{limits[0]}, {limits[1]}]",
        )
    return EngineValidationResult(engine="rig", valid=True)


__all__ = [
    "CONTRACT_VERSION",
    "EngineValidationResult",
    "validate_engine_manifest",
    "validate_all_engine_manifests",
    "validate_hinge_physics",
]
