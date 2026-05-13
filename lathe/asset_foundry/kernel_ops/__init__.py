"""Foundry Lane A future-tasks — kernel op modules.

Per northstar §10 Lane A "potential future tasks", these modules add
typed contracts + deterministic builders for operations not yet in
the core kernel. Each module is internal-only and additive; none
break the public ``.lth`` syntax or ``lathe.shape.intent_mesh_handoff_v1``.

Modules:
  - minkowski.py            Minkowski-sum operator (box+box analytic, polyhedron approximation)
  - extrude_deformers.py    twist + scale variants on extruded profiles
  - partial_revolve.py      partial rotate-extrude (sweep angle < 360°)
  - helical_sweep.py        helix sweep operator
  - involute_gear.py        involute gear primitive
  - nurbs_curve.py          NURBS-backed profile curves
  - deformers.py            bend / twist / taper deformers
  - half_edge_bevel.py      half-edge bevel operator for arbitrary topology
  - tessellation_policy.py  unified tessellation policy for primitive resampling
  - brep_ir.py              B-Rep IR scaffold (typed; OCCT/build123d integration external)
"""

from __future__ import annotations

from .brep_ir import (
    BREP_IR_VERSION,
    BrepEdge,
    BrepFace,
    BrepIR,
    BrepShell,
    BrepVertex,
    build_box_brep,
)
from .deformers import (
    DEFORMERS_VERSION,
    BendDeformer,
    TaperDeformer,
    TwistDeformer,
    apply_bend,
    apply_taper,
    apply_twist,
)
from .extrude_deformers import (
    EXTRUDE_DEFORMERS_VERSION,
    ExtrudeDeformer,
    ScalingExtrude,
    TwistedExtrude,
)
from .half_edge_bevel import (
    HALF_EDGE_BEVEL_VERSION,
    HalfEdgeBevelRequest,
    HalfEdgeBevelResult,
    plan_half_edge_bevel,
)
from .helical_sweep import (
    HELICAL_SWEEP_VERSION,
    HelicalSweep,
    sample_helical_path,
)
from .involute_gear import (
    INVOLUTE_GEAR_VERSION,
    InvoluteGearParameters,
    InvoluteGearProfile,
    build_involute_gear_profile,
)
from .minkowski import (
    MINKOWSKI_VERSION,
    MinkowskiSumRequest,
    MinkowskiSumResult,
    minkowski_box_box,
    minkowski_polyhedron_polyhedron,
)
from .nurbs_curve import (
    NURBS_CURVE_VERSION,
    NurbsCurve,
    NurbsControlPoint,
    evaluate_nurbs_at,
    sample_nurbs_curve,
)
from .partial_revolve import (
    PARTIAL_REVOLVE_VERSION,
    PartialRevolveRequest,
    PartialRevolveMesh,
    build_partial_revolve,
)
from .tessellation_policy import (
    TESSELLATION_POLICY_VERSION,
    TessellationPolicy,
    TessellationProfile,
    apply_tessellation_policy,
)

__all__ = [
    "BREP_IR_VERSION",
    "BrepEdge",
    "BrepFace",
    "BrepIR",
    "BrepShell",
    "BrepVertex",
    "build_box_brep",
    "DEFORMERS_VERSION",
    "BendDeformer",
    "TaperDeformer",
    "TwistDeformer",
    "apply_bend",
    "apply_taper",
    "apply_twist",
    "EXTRUDE_DEFORMERS_VERSION",
    "ExtrudeDeformer",
    "ScalingExtrude",
    "TwistedExtrude",
    "HALF_EDGE_BEVEL_VERSION",
    "HalfEdgeBevelRequest",
    "HalfEdgeBevelResult",
    "plan_half_edge_bevel",
    "HELICAL_SWEEP_VERSION",
    "HelicalSweep",
    "sample_helical_path",
    "INVOLUTE_GEAR_VERSION",
    "InvoluteGearParameters",
    "InvoluteGearProfile",
    "build_involute_gear_profile",
    "MINKOWSKI_VERSION",
    "MinkowskiSumRequest",
    "MinkowskiSumResult",
    "minkowski_box_box",
    "minkowski_polyhedron_polyhedron",
    "NURBS_CURVE_VERSION",
    "NurbsCurve",
    "NurbsControlPoint",
    "evaluate_nurbs_at",
    "sample_nurbs_curve",
    "PARTIAL_REVOLVE_VERSION",
    "PartialRevolveRequest",
    "PartialRevolveMesh",
    "build_partial_revolve",
    "TESSELLATION_POLICY_VERSION",
    "TessellationPolicy",
    "TessellationProfile",
    "apply_tessellation_policy",
]
