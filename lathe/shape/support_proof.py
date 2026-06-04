"""Support-relation load-path proof (Wave 19 / S4).

Per research §11+§12: a ``supports`` relation declares that one body
holds another against gravity. The resolver needs to verify a load
path: the source's contact face actually rests under the target's
center-of-mass, the contact area is above a minimum threshold, and
no other geometry obstructs the path between them.

This module is the proof framework. Failure to prove yields an
unresolved placement binding; success annotates the binding with
load-path evidence the package stage can emit as physics metadata.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

CONTRACT_VERSION = "lathe.shape.support_proof_v1"

# Default gravity vector — world-down. Engine adapters may override
# at the runtime contract level for non-standard orientations.
_GRAVITY_VECTOR = (0.0, 0.0, -1.0)


@dataclass(frozen=True)
class LoadPathEvidence:
    """Result of a support-relation load-path verification."""

    valid: bool
    contact_area_cm2: float
    com_offset_from_support_cm: float
    normal_alignment_score: float  # 1.0 = perfectly opposed to gravity
    rejection_reason: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "contact_area_cm2": self.contact_area_cm2,
            "com_offset_from_support_cm": self.com_offset_from_support_cm,
            "normal_alignment_score": self.normal_alignment_score,
            "rejection_reason": self.rejection_reason,
        }


def prove_support_relation(
    source_contact_origin: tuple[float, float, float],
    source_contact_normal: tuple[float, float, float],
    source_contact_bounds_cm: tuple[float, float, float],
    target_com_world_cm: tuple[float, float, float],
    target_footprint_bounds_cm: tuple[float, float, float],
    min_contact_area_cm2: float = 4.0,
    max_com_offset_cm: float = 5.0,
) -> LoadPathEvidence:
    """Verify a support-relation load path.

    Conditions:
      1. The source contact normal aligns with gravity (within
         tolerance). A floor's normal is +Z; gravity is -Z; alignment
         score = -dot(source_normal, gravity).
      2. The target's center of mass projects onto the source contact
         region within ``max_com_offset_cm``.
      3. The contact bounding area meets the minimum threshold.

    Returns a structured ``LoadPathEvidence`` record. The placement
    resolver consumes ``.valid``; the package stage reads the rest
    for physics metadata.
    """
    # 1. Normal alignment.
    sn = source_contact_normal
    gn = _GRAVITY_VECTOR
    dot = sn[0] * gn[0] + sn[1] * gn[1] + sn[2] * gn[2]
    normal_alignment_score = -dot  # +1.0 when source faces upward (opposed to gravity)
    if normal_alignment_score < 0.5:
        return LoadPathEvidence(
            valid=False,
            contact_area_cm2=0.0,
            com_offset_from_support_cm=0.0,
            normal_alignment_score=normal_alignment_score,
            rejection_reason=(
                f"normal alignment {normal_alignment_score:.2f} insufficient "
                f"(need ≥ 0.5 — source contact face must face roughly upward)"
            ),
        )

    # 2. Contact area: approximate as the bounding rectangle product
    # of the X and Y dimensions (the support plane).
    contact_area = float(source_contact_bounds_cm[0]) * float(source_contact_bounds_cm[1])
    if contact_area < min_contact_area_cm2:
        return LoadPathEvidence(
            valid=False,
            contact_area_cm2=contact_area,
            com_offset_from_support_cm=0.0,
            normal_alignment_score=normal_alignment_score,
            rejection_reason=(
                f"contact area {contact_area:.2f} cm² < min {min_contact_area_cm2} cm²"
            ),
        )

    # 3. COM offset: distance between target COM XY projection and
    # source contact origin XY.
    dx = float(target_com_world_cm[0]) - float(source_contact_origin[0])
    dy = float(target_com_world_cm[1]) - float(source_contact_origin[1])
    com_offset = (dx * dx + dy * dy) ** 0.5
    if com_offset > max_com_offset_cm:
        return LoadPathEvidence(
            valid=False,
            contact_area_cm2=contact_area,
            com_offset_from_support_cm=com_offset,
            normal_alignment_score=normal_alignment_score,
            rejection_reason=(
                f"target COM offset {com_offset:.2f}cm > max {max_com_offset_cm}cm"
            ),
        )

    return LoadPathEvidence(
        valid=True,
        contact_area_cm2=contact_area,
        com_offset_from_support_cm=com_offset,
        normal_alignment_score=normal_alignment_score,
    )


__all__ = ["CONTRACT_VERSION", "LoadPathEvidence", "prove_support_relation"]
