"""Canonical topology + rig families.

Per northstar §11 Phase 4. Canonical topology templates declare the
expected bone names + IK chains + morph slots for a rig family
(biped, quadruped, crystal pulse, foliage_sway). Animations target
canonical names, then map to instance rigs via name lookup.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from .rig_ir import RigBone, RigIR, SkeletonHierarchy

CANONICAL_TOPOLOGY_VERSION = "lathe.asset_foundry.canonical_topology_v1"


@dataclass(frozen=True)
class CanonicalTopologyTemplate:
    template_id: str
    expected_bone_names: tuple[str, ...]
    ik_chains: tuple[tuple[str, ...], ...] = ()
    """List of bone-name chains that form IK chains."""
    morph_slots: tuple[str, ...] = ()
    handedness: str = "right"


def biped_template() -> CanonicalTopologyTemplate:
    return CanonicalTopologyTemplate(
        template_id="canonical.biped_v1",
        expected_bone_names=(
            "root",
            "hips",
            "spine_01",
            "spine_02",
            "spine_03",
            "neck",
            "head",
            "clavicle_l",
            "upper_arm_l",
            "lower_arm_l",
            "hand_l",
            "clavicle_r",
            "upper_arm_r",
            "lower_arm_r",
            "hand_r",
            "thigh_l",
            "calf_l",
            "foot_l",
            "thigh_r",
            "calf_r",
            "foot_r",
        ),
        ik_chains=(
            ("upper_arm_l", "lower_arm_l", "hand_l"),
            ("upper_arm_r", "lower_arm_r", "hand_r"),
            ("thigh_l", "calf_l", "foot_l"),
            ("thigh_r", "calf_r", "foot_r"),
        ),
        morph_slots=(
            "smile",
            "frown",
            "blink_left",
            "blink_right",
            "open_mouth",
        ),
    )


def quadruped_template() -> CanonicalTopologyTemplate:
    return CanonicalTopologyTemplate(
        template_id="canonical.quadruped_v1",
        expected_bone_names=(
            "root",
            "hips",
            "spine",
            "chest",
            "neck",
            "head",
            "shoulder_l",
            "upper_leg_front_l",
            "lower_leg_front_l",
            "paw_front_l",
            "shoulder_r",
            "upper_leg_front_r",
            "lower_leg_front_r",
            "paw_front_r",
            "thigh_l",
            "calf_l",
            "paw_back_l",
            "thigh_r",
            "calf_r",
            "paw_back_r",
            "tail_01",
            "tail_02",
        ),
        ik_chains=(
            ("upper_leg_front_l", "lower_leg_front_l", "paw_front_l"),
            ("upper_leg_front_r", "lower_leg_front_r", "paw_front_r"),
            ("thigh_l", "calf_l", "paw_back_l"),
            ("thigh_r", "calf_r", "paw_back_r"),
        ),
    )


def crystal_pulse_template() -> CanonicalTopologyTemplate:
    """Stylized 'animated' template — no skeleton, just morphs.

    Crystals don't have bones but they DO pulse/glow — this template
    formalizes the morph slots LowPolyFantasy crystals use.
    """
    return CanonicalTopologyTemplate(
        template_id="canonical.crystal_pulse_v1",
        expected_bone_names=("root",),
        morph_slots=("pulse", "shimmer", "growth_phase_a", "growth_phase_b"),
    )


def validate_topology_against_template(
    rig: RigIR, template: CanonicalTopologyTemplate
) -> tuple[str, ...]:
    """Return diagnostic strings for missing/extra bones."""
    diagnostics: list[str] = []
    template_set = set(template.expected_bone_names)
    actual_set = set(rig.hierarchy.bones)
    missing = template_set - actual_set
    extra = actual_set - template_set
    for name in sorted(missing):
        diagnostics.append(f"canonical_topology_missing_bone: {name!r}")
    for name in sorted(extra):
        diagnostics.append(f"canonical_topology_extra_bone: {name!r}")
    return tuple(diagnostics)


__all__ = [
    "CANONICAL_TOPOLOGY_VERSION",
    "CanonicalTopologyTemplate",
    "biped_template",
    "crystal_pulse_template",
    "quadruped_template",
    "validate_topology_against_template",
]
