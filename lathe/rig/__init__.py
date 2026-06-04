"""Lathe rig contract package.

Rigid constraint hierarchies first, bone-based skinning second.
Hinge edges in the construction graph become hinge joints in the rig
contract; the engine adapters lower those to HingeConstraint / HingeJoint /
PhysicsConstraint / UsdPhysics joints.
"""

from .rig_contract import (
    RigBody,
    RigContract,
    rig_from_construction_edges,
)

__all__ = ["RigBody", "RigContract", "rig_from_construction_edges"]
