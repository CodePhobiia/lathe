"""``lathe.rig.contract_v1`` — rigid-constraint rig substrate.

Per research §11: for crates/doors/terminals/panels/mechanical props,
most moving parts should not be skinned. They should be rigid node
hierarchies with constraint metadata. Use bones/skinning only for
deforming meshes.

This module:
  - defines ``RigContract`` (bodies + joints + animations)
  - reads ``hinge`` / ``attached_to.joint`` metadata from construction
    graph edges and emits the joint records
  - hands off to ``AssetRuntimeContract.joints`` for engine adapters
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from ..runtime.asset_contract import RigJoint

CONTRACT_VERSION = "lathe.rig.contract_v1"


@dataclass(frozen=True)
class RigBody:
    """One rigid body in the rig hierarchy."""

    body_id: str
    role: str  # static_parent | dynamic_child | floating
    mass_kg: float = 1.0


@dataclass(frozen=True)
class RigAnimation:
    """One named animation clip."""

    clip_id: str
    joint_id: str
    from_value: float
    to_value: float
    duration_s: float = 1.0


@dataclass(frozen=True)
class RigContract:
    """Full rig contract for one asset."""

    rig_id: str
    rig_type: str  # rigid_constraint | bone_skinned | mixed
    bodies: tuple[RigBody, ...]
    joints: tuple[RigJoint, ...]
    animations: tuple[RigAnimation, ...] = ()


def rig_from_construction_edges(
    asset_name: str,
    edges: Iterable[Mapping[str, Any]],
    body_node_ids: Iterable[str],
) -> RigContract:
    """Derive a RigContract from construction-graph edges with rig metadata.

    Looks for edges with ``metadata.joint == "hinge"`` (or attributes/
    role pointing at a hinge relation). Each such edge becomes a
    ``RigJoint``; the source/target node_ids become ``RigBody``
    entries.
    """
    body_ids: list[str] = []
    seen: set[str] = set()
    for bid in body_node_ids:
        if bid and bid not in seen:
            body_ids.append(bid)
            seen.add(bid)

    bodies: list[RigBody] = []
    joints: list[RigJoint] = []
    animations: list[RigAnimation] = []

    for edge in edges:
        if not isinstance(edge, Mapping):
            continue
        metadata = edge.get("metadata") if isinstance(edge.get("metadata"), Mapping) else {}
        attributes = edge.get("attributes") if isinstance(edge.get("attributes"), Mapping) else {}
        joint_type = (
            metadata.get("joint")
            or attributes.get("joint")
            or metadata.get("relation_joint")
        )
        if not isinstance(joint_type, str):
            continue
        if joint_type not in ("hinge", "slider", "fixed", "ball"):
            continue
        source = str(edge.get("source_id") or edge.get("source") or "")
        target = str(edge.get("target_id") or edge.get("target") or "")
        if not source or not target:
            continue
        axis_raw = metadata.get("axis", "Z")
        axis_map = {
            "X": (1.0, 0.0, 0.0),
            "Y": (0.0, 1.0, 0.0),
            "Z": (0.0, 0.0, 1.0),
        }
        axis = axis_map.get(str(axis_raw).upper(), (0.0, 0.0, 1.0))
        limits_raw = metadata.get("limits_deg", [-180.0, 180.0])
        try:
            limits = (float(limits_raw[0]), float(limits_raw[1]))
        except (TypeError, ValueError, IndexError):
            limits = (-180.0, 180.0)
        joint_id = f"joint.{source}_to_{target}.{joint_type}"
        joints.append(
            RigJoint(
                joint_id=joint_id,
                type=joint_type,
                parent_part=target,
                child_part=source,
                axis_world=axis,
                limits_deg=limits,
                default_angle_deg=float(metadata.get("default_angle_deg", 0.0)),
                motorized=bool(metadata.get("motorized", False)),
            )
        )
        if joint_type == "hinge":
            animations.append(
                RigAnimation(
                    clip_id=f"{source}_open",
                    joint_id=joint_id,
                    from_value=limits[0],
                    to_value=limits[1],
                )
            )

    # Ensure every referenced node has a body record.
    referenced = {b for j in joints for b in (j.parent_part, j.child_part)}
    for bid in body_ids:
        bodies.append(RigBody(body_id=bid, role="static_parent" if bid not in {j.child_part for j in joints} else "dynamic_child"))
    for bid in referenced - set(body_ids):
        bodies.append(RigBody(body_id=bid, role="floating"))

    return RigContract(
        rig_id=f"{asset_name}.rig",
        rig_type="rigid_constraint",
        bodies=tuple(bodies),
        joints=tuple(joints),
        animations=tuple(animations),
    )


__all__ = [
    "CONTRACT_VERSION",
    "RigBody",
    "RigAnimation",
    "RigContract",
    "rig_from_construction_edges",
]
