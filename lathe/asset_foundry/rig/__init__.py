"""Phase 4 organic + animation vocabulary.

Per northstar §11 Phase 4. Rig + skin + morph + canonical topology +
animation library compatibility. All contracts are typed dataclasses
so the future runtime backend (engine plugins, USD generative) can
consume them without a public-language change.

The Foundry rig contract is intentionally minimal at v0.1: enough
typed structure that downstream engine adapters (Roblox / Unity /
Unreal / glTF) know how to map the rig + skin + morphs. Real
skinning + posing is delegated to the engine.
"""

from __future__ import annotations

from .animation_compat import (
    ANIMATION_COMPAT_VERSION,
    AnimationClip,
    AnimationLibrary,
    AnimationTrack,
    build_idle_breathing_clip,
)
from .canonical_topology import (
    CANONICAL_TOPOLOGY_VERSION,
    CanonicalTopologyTemplate,
    biped_template,
    crystal_pulse_template,
    quadruped_template,
)
from .morph_targets import (
    MORPH_TARGETS_VERSION,
    MorphTarget,
    MorphTargetSet,
)
from .rig_ir import (
    RIG_IR_VERSION,
    RigBone,
    RigConstraint,
    RigIR,
    SkeletonHierarchy,
)
from .skin_program import (
    SKIN_PROGRAM_VERSION,
    SkinBinding,
    SkinProgram,
    VertexWeight,
)

__all__ = [
    "ANIMATION_COMPAT_VERSION",
    "AnimationClip",
    "AnimationLibrary",
    "AnimationTrack",
    "build_idle_breathing_clip",
    "CANONICAL_TOPOLOGY_VERSION",
    "CanonicalTopologyTemplate",
    "biped_template",
    "crystal_pulse_template",
    "quadruped_template",
    "MORPH_TARGETS_VERSION",
    "MorphTarget",
    "MorphTargetSet",
    "RIG_IR_VERSION",
    "RigBone",
    "RigConstraint",
    "RigIR",
    "SkeletonHierarchy",
    "SKIN_PROGRAM_VERSION",
    "SkinBinding",
    "SkinProgram",
    "VertexWeight",
]
