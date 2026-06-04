"""Foundry F0 — capability matrix.

Per docs/asset-quality/lathe-frontier-asset-foundry-masterplan.md §18.F0
and docs/asset-quality/lathe-frontier-geometry-kernel-roadmap.md §11.1,
the Foundry's first deliverable is a truthful enumeration of every
operation Foundry v0.1 needs, paired with its current status:

  supported   — kernel can build it as real visible geometry
  partial     — supported only on some inputs; falls back otherwise
  fallback    — only a deterministic degraded path exists
  unsupported — explicitly rejected or warns
  not_started — code exists but has not been wired to execute

The matrix is the anti-bullshit shield (per masterplan §3): every
public claim must map to one of these statuses. The matrix is
JSON-serializable so future Foundry phases (.lthpkg sidecars,
@lathe/three diagnostics overlay) can read and surface it.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

CAPABILITY_MATRIX_VERSION = "lathe.asset_foundry.capability_matrix_v1"


class CapabilityStatus(str, Enum):
    """Status tokens per the Foundry's no-fake-quality rule."""

    SUPPORTED = "supported"
    PARTIAL = "partial"
    FALLBACK = "fallback"
    UNSUPPORTED = "unsupported"
    NOT_STARTED = "not_started"


class CapabilityClaimLevel(str, Enum):
    """Truth tier for how far a capability claim can be promoted."""

    TYPED_CONTRACT = "typed_contract"
    EXECUTION_PARTIAL = "execution_partial"
    ARTIFACT_REAL = "artifact_real"
    PRODUCT_COMPLETE = "product_complete"


@dataclass(frozen=True)
class CapabilityRecord:
    """One row in the capability matrix.

    Maps a Foundry operation/claim to the kernel/runtime support it
    currently has, plus the evidence it should emit when executed.
    """

    operation_id: str
    """Stable canonical ID. Maps to a ShapeIR v2 op
    (``op.bevel``, ``op.fastener_grid``, ...), a mesh-program feature,
    a kernel capability (``solid.boolean.union``), or a Foundry stylized
    operator (``style.facet_field``, ``mesh.crystal_prism``)."""

    op_family: str
    """Coarse family: ``solid``, ``boolean``, ``feature``, ``edge``,
    ``repetition``, ``integration``, ``wear``, ``stylized``,
    ``surface``, ``runtime``, ``package``."""

    status: CapabilityStatus
    """Current execution status under the v0.1 Foundry contract."""

    supporting_kernels: tuple[str, ...] = ()
    """Kernel IDs that report support: e.g.
    ``("lathe.geometry.manifold_v1", "lathe.geometry.reference_v1")``."""

    evidence_requirements: tuple[str, ...] = ()
    """The artifact evidence this operation should produce when it runs
    successfully: e.g. ``("visible_geometry", "operation_id_in_provenance")``."""

    fallback_reason: str | None = None
    """When status is ``fallback`` or ``partial``, the canonical reason
    token (``boolean_kernel_fallback``, ``no_v1_equivalent``, ...)."""

    backend_required: str | None = None
    """Optional backend/dependency needed before a partial row can promote."""

    claim_level: CapabilityClaimLevel | None = None
    """Highest static claim tier for this capability row.

    ``product_complete`` is intentionally not inferred from a static
    matrix row; it requires asset-specific generated evidence.
    """

    notes: str = ""
    """Free-form notes (e.g. linking to the responsible Foundry phase
    if status is ``not_started``)."""


@dataclass(frozen=True)
class FoundryCapabilityMatrix:
    """Full capability enumeration emitted by ``build_capability_matrix``."""

    version: str
    records: tuple[CapabilityRecord, ...]
    record_count: int
    counts_by_status: Mapping[str, int]
    counts_by_family: Mapping[str, int]
    counts_by_claim_level: Mapping[str, int]

    def filter_by_status(
        self, status: CapabilityStatus
    ) -> tuple[CapabilityRecord, ...]:
        """Return records matching one status."""
        return tuple(r for r in self.records if r.status == status)

    def filter_by_family(self, family: str) -> tuple[CapabilityRecord, ...]:
        """Return records in one op family."""
        return tuple(r for r in self.records if r.op_family == family)

    def lookup(self, operation_id: str) -> CapabilityRecord | None:
        """Look up a specific operation by canonical ID."""
        for r in self.records:
            if r.operation_id == operation_id:
                return r
        return None


# Canonical operation table. The status reflects current code in the
# repo (as of Foundry F0 commit). Updating a row should be paired with
# code or evidence that demonstrates the change.
_CAPABILITY_TABLE: tuple[CapabilityRecord, ...] = (
    # ---- Solid primitives (kernel-backed) ----
    CapabilityRecord(
        operation_id="solid.box",
        op_family="solid",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=("lathe.geometry.manifold_v1", "lathe.geometry.reference_v1"),
        evidence_requirements=("visible_geometry", "watertight"),
        notes="Native ShapeIR v1 primitive; lowered to kernel.build_primitive.",
    ),
    CapabilityRecord(
        operation_id="solid.cylinder",
        op_family="solid",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=("lathe.geometry.manifold_v1", "lathe.geometry.reference_v1"),
        evidence_requirements=("visible_geometry", "watertight"),
    ),
    CapabilityRecord(
        operation_id="solid.sphere",
        op_family="solid",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=("lathe.geometry.manifold_v1", "lathe.geometry.reference_v1"),
        evidence_requirements=("visible_geometry", "watertight"),
    ),
    CapabilityRecord(
        operation_id="solid.rounded_box",
        op_family="solid",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=("lathe.geometry.manifold_v1", "lathe.geometry.reference_v1"),
        evidence_requirements=("visible_geometry", "watertight"),
        notes="Implemented as subdivision_box in ShapeIR v1.",
    ),
    CapabilityRecord(
        operation_id="solid.revolved_profile",
        op_family="solid",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=("lathe.geometry.manifold_v1", "lathe.geometry.reference_v1"),
        evidence_requirements=("visible_geometry", "watertight"),
    ),
    CapabilityRecord(
        operation_id="solid.extruded_profile",
        op_family="solid",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=("lathe.geometry.manifold_v1", "lathe.geometry.reference_v1"),
        evidence_requirements=("visible_geometry", "watertight"),
        notes="Requires shapely + mapbox-earcut for triangulation.",
    ),
    CapabilityRecord(
        operation_id="solid.swept_profile",
        op_family="solid",
        status=CapabilityStatus.PARTIAL,
        supporting_kernels=("lathe.geometry.reference_v1",),
        evidence_requirements=("visible_geometry",),
        fallback_reason="path_non_planar_falls_back_to_linear_extrude",
        notes="Frame policy + miter/bevel joins not yet implemented; see newresearch.md §4.",
    ),
    CapabilityRecord(
        operation_id="solid.torus",
        op_family="solid",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=("lathe.geometry.manifold_v1", "lathe.geometry.reference_v1"),
        evidence_requirements=("visible_geometry", "watertight"),
    ),
    CapabilityRecord(
        operation_id="solid.subdivision_box",
        op_family="solid",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=("lathe.geometry.manifold_v1", "lathe.geometry.reference_v1"),
        evidence_requirements=("visible_geometry", "watertight"),
    ),
    CapabilityRecord(
        operation_id="solid.lofted_solid",
        op_family="solid",
        status=CapabilityStatus.PARTIAL,
        supporting_kernels=("lathe.geometry.reference_v1",),
        evidence_requirements=("visible_geometry",),
        fallback_reason="manifold_lane_coverage_gap",
        notes="Reference kernel produces tessellated approximation; Manifold path TBD.",
    ),
    CapabilityRecord(
        operation_id="solid.heightfield",
        op_family="solid",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=("lathe.geometry.manifold_v1", "lathe.geometry.reference_v1"),
        evidence_requirements=("visible_geometry",),
        notes="Solidification adds a base plane to make heightfield closed.",
    ),
    CapabilityRecord(
        operation_id="solid.sdf_mesh",
        op_family="solid",
        status=CapabilityStatus.PARTIAL,
        supporting_kernels=("lathe.geometry.reference_v1",),
        evidence_requirements=("visible_geometry",),
        fallback_reason="meshing_resolution_dependent",
        notes="Marching-cubes-style extraction; not optimal for crisp hard-surface.",
    ),
    # ---- Boolean operations ----
    CapabilityRecord(
        operation_id="op.union",
        op_family="boolean",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=("lathe.geometry.manifold_v1", "lathe.geometry.reference_v1"),
        evidence_requirements=("watertight", "kernel_id_in_report"),
        notes="Manifold backend is default when available.",
    ),
    CapabilityRecord(
        operation_id="op.subtract",
        op_family="boolean",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=("lathe.geometry.manifold_v1", "lathe.geometry.reference_v1"),
        evidence_requirements=("watertight", "kernel_id_in_report"),
    ),
    CapabilityRecord(
        operation_id="op.intersect",
        op_family="boolean",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=("lathe.geometry.manifold_v1", "lathe.geometry.reference_v1"),
        evidence_requirements=("watertight", "kernel_id_in_report"),
    ),
    CapabilityRecord(
        operation_id="op.hull",
        op_family="boolean",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=("lathe.geometry.manifold_v1", "lathe.geometry.reference_v1"),
        evidence_requirements=("visible_geometry",),
    ),
    CapabilityRecord(
        operation_id="op.minkowski",
        op_family="boolean",
        status=CapabilityStatus.PARTIAL,
        supporting_kernels=(),
        evidence_requirements=("visible_geometry",),
        fallback_reason="approximated_via_half_space_normal_match_for_non_matching_inputs",
        notes="Foundry kernel_ops.minkowski — box+box analytic + polyhedron half-space approximation.",
    ),
    # ---- Edge / bevel ops ----
    CapabilityRecord(
        operation_id="op.bevel",
        op_family="edge",
        status=CapabilityStatus.PARTIAL,
        supporting_kernels=(),
        evidence_requirements=("bevel_ring_face_count", "bevel_seam_group"),
        fallback_reason="post_boolean_polybevel_only",
        notes="Post-boolean polybevel works; pre-boolean bevel not yet wired. See newresearch.md §4 'Defer bevels'.",
    ),
    CapabilityRecord(
        operation_id="op.chamfer",
        op_family="edge",
        status=CapabilityStatus.PARTIAL,
        supporting_kernels=(),
        evidence_requirements=("chamfer_ring_face_count",),
        fallback_reason="post_boolean_polychamfer_only",
    ),
    CapabilityRecord(
        operation_id="op.weighted_normals",
        op_family="edge",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=(),
        evidence_requirements=("normal_consistency",),
        notes="Computed in mesh_finalize.",
    ),
    CapabilityRecord(
        operation_id="op.mark_hard_edge",
        op_family="edge",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=(),
        evidence_requirements=("hard_edge_seam_record",),
    ),
    # ---- Feature ops (trim/fastener/vent/etc.) ----
    CapabilityRecord(
        operation_id="op.trim_band",
        op_family="feature",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=("lathe.geometry.manifold_v1", "lathe.geometry.reference_v1"),
        evidence_requirements=("visible_geometry", "trim_band_count", "material_zone"),
        notes="Implemented in lathe.asset_quality.feature_ops_v2_lowering.lower_trim_band.",
    ),
    CapabilityRecord(
        operation_id="op.fastener_grid",
        op_family="feature",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=("lathe.geometry.manifold_v1", "lathe.geometry.reference_v1"),
        evidence_requirements=("visible_geometry", "fastener_count"),
    ),
    CapabilityRecord(
        operation_id="op.vent_slats",
        op_family="feature",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=("lathe.geometry.manifold_v1", "lathe.geometry.reference_v1"),
        evidence_requirements=("visible_geometry", "slat_count"),
    ),
    CapabilityRecord(
        operation_id="op.corner_guard_set",
        op_family="feature",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=("lathe.geometry.manifold_v1", "lathe.geometry.reference_v1"),
        evidence_requirements=("visible_geometry", "guard_count"),
    ),
    CapabilityRecord(
        operation_id="op.panel_inset",
        op_family="feature",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=("lathe.geometry.manifold_v1",),
        evidence_requirements=("visible_geometry", "panel_depth_measured"),
    ),
    CapabilityRecord(
        operation_id="op.cut_panel_line",
        op_family="feature",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=("lathe.geometry.manifold_v1",),
        evidence_requirements=("visible_geometry",),
    ),
    CapabilityRecord(
        operation_id="op.inset",
        op_family="feature",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=("lathe.geometry.manifold_v1",),
        evidence_requirements=("visible_geometry", "panel_depth_measured"),
    ),
    CapabilityRecord(
        operation_id="op.extrude",
        op_family="feature",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=("lathe.geometry.manifold_v1", "lathe.geometry.reference_v1"),
        evidence_requirements=("visible_geometry",),
    ),
    CapabilityRecord(
        operation_id="op.shell",
        op_family="feature",
        status=CapabilityStatus.PARTIAL,
        supporting_kernels=(),
        evidence_requirements=("visible_geometry",),
        fallback_reason="inner_shell_offset_kernel_not_landed",
        notes="Reserved for future OCCT or libigl-style implementation.",
    ),
    # ---- Repetition / scatter ----
    CapabilityRecord(
        operation_id="op.repeat",
        op_family="repetition",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=(),
        evidence_requirements=("instance_count", "placement_trace"),
    ),
    CapabilityRecord(
        operation_id="op.mirror",
        op_family="repetition",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=(),
        evidence_requirements=("mirror_axis_recorded",),
    ),
    CapabilityRecord(
        operation_id="op.distribute",
        op_family="repetition",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=(),
        evidence_requirements=("visible_geometry", "instance_count", "placement_trace"),
        notes="ShapeIR v2 lowers linear/grid/radial/arc/along_path/points/surface_grid distribution; Foundry distribution emits arc/along_path placement reports.",
    ),
    # ---- Integration / attachment ----
    CapabilityRecord(
        operation_id="op.socket",
        op_family="integration",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=("lathe.geometry.manifold_v1",),
        evidence_requirements=("visible_geometry", "socket_clearance_recorded"),
    ),
    CapabilityRecord(
        operation_id="op.bracket",
        op_family="integration",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=("lathe.geometry.manifold_v1",),
        evidence_requirements=("visible_geometry",),
    ),
    CapabilityRecord(
        operation_id="op.mount_plate",
        op_family="integration",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=("lathe.geometry.manifold_v1",),
        evidence_requirements=("visible_geometry",),
    ),
    CapabilityRecord(
        operation_id="op.weld_seam",
        op_family="integration",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=(),
        evidence_requirements=("visible_geometry", "seam_geometry", "seam_group", "weld_bead"),
        notes="ShapeIR v2 lowers path/axis weld seams to visible weld_seam records and records exact-mesh/boolean attachment fallback metadata when source-backed.",
    ),
    # ---- Wear / damage masks ----
    CapabilityRecord(
        operation_id="op.chip_edges",
        op_family="wear",
        status=CapabilityStatus.PARTIAL,
        supporting_kernels=(),
        evidence_requirements=("wear_mask",),
        fallback_reason="mask_only_no_geometry",
        notes="Drives wear mask in surface_runtime; no high-poly chip geometry yet.",
    ),
    CapabilityRecord(
        operation_id="op.scratch_mask",
        op_family="wear",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=(),
        evidence_requirements=("wear_mask",),
    ),
    CapabilityRecord(
        operation_id="op.dent_mask",
        op_family="wear",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=(),
        evidence_requirements=("wear_mask",),
    ),
    CapabilityRecord(
        operation_id="op.grime_mask",
        op_family="wear",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=(),
        evidence_requirements=("wear_mask",),
    ),
    # ---- Zone / decal / material ----
    CapabilityRecord(
        operation_id="op.material_zone",
        op_family="surface",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=(),
        evidence_requirements=("zone_id_in_face_attribution",),
    ),
    CapabilityRecord(
        operation_id="op.decal_zone",
        op_family="surface",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=(),
        evidence_requirements=("decal_zone_id",),
    ),
    CapabilityRecord(
        operation_id="op.wear_zone",
        op_family="surface",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=(),
        evidence_requirements=("wear_zone_id",),
    ),
    # ---- Stylized Foundry operators (F4) ----
    CapabilityRecord(
        operation_id="style.facet_field",
        op_family="stylized",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=(),
        evidence_requirements=("facet_sample_count",),
        notes="Foundry F4 — lathe/asset_foundry/facet_field.py.",
    ),
    CapabilityRecord(
        operation_id="style.flat_normal_policy",
        op_family="stylized",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=(),
        evidence_requirements=("flat_normal_face_count",),
        notes="Used by LowPolyFantasy style pack.",
    ),
    CapabilityRecord(
        operation_id="style.chunkify_surface",
        op_family="stylized",
        status=CapabilityStatus.PARTIAL,
        supporting_kernels=(),
        evidence_requirements=("chunk_face_count",),
        fallback_reason="chunk_grid_only_no_irregular_outline",
        notes="Grid-based chunkify works; irregular_outline variant pending.",
    ),
    CapabilityRecord(
        operation_id="mesh.prism",
        op_family="stylized",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=(),
        evidence_requirements=("visible_geometry",),
        notes="Foundry F4 — lathe/asset_foundry/prismatic.py.",
    ),
    CapabilityRecord(
        operation_id="mesh.crystal_prism",
        op_family="stylized",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=(),
        evidence_requirements=("visible_geometry",),
        notes="Foundry F4 — crystal cluster generator.",
    ),
    CapabilityRecord(
        operation_id="mesh.half_space_polyhedron",
        op_family="stylized",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=(),
        evidence_requirements=("visible_geometry",),
        notes="Foundry F4 — lathe/asset_foundry/polyhedron.py.",
    ),
    CapabilityRecord(
        operation_id="terrain.faceted_cliff_patch",
        op_family="stylized",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=(),
        evidence_requirements=("facet_sample_count", "material_zone_manifest"),
        notes="Foundry F8 floating_island generator uses facet_field.sample_facet_field_3d_radial for cliff rings.",
    ),
    # ---- Runtime cooking ----
    CapabilityRecord(
        operation_id="runtime.collision_proxy",
        op_family="runtime",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=(),
        evidence_requirements=(
            "collision_proxy_artifact",
            "proxy_component_count",
            "decomposition_strategy",
        ),
        notes="Runtime cooker records real proxy paths and component decomposition metadata; prismatic Golden Asset emits per-component convex AABB hulls.",
    ),
    CapabilityRecord(
        operation_id="runtime.nav_contribution",
        op_family="runtime",
        status=CapabilityStatus.PARTIAL,
        supporting_kernels=(),
        evidence_requirements=("nav_polygon",),
        fallback_reason="walkable_surface_only",
        notes="Per-asset walkable surface extraction; scene-level navmesh pending.",
    ),
    CapabilityRecord(
        operation_id="runtime.lod_chain",
        op_family="runtime",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=(),
        evidence_requirements=("lod_glb_count",),
        notes="4-LOD chain emitted by optimize stage.",
    ),
    CapabilityRecord(
        operation_id="runtime.scale_pivot_units",
        op_family="runtime",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=(),
        evidence_requirements=("scale_validated", "pivot_recorded", "units_recorded"),
    ),
    CapabilityRecord(
        operation_id="runtime.material_zone_manifest",
        op_family="runtime",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=(),
        evidence_requirements=("zone_to_material_mapping",),
    ),
    # ---- Package ----
    CapabilityRecord(
        operation_id="package.glb",
        op_family="package",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=(),
        evidence_requirements=("glb_artifact",),
    ),
    CapabilityRecord(
        operation_id="package.usda",
        op_family="package",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=(),
        evidence_requirements=("usda_artifact",),
    ),
    CapabilityRecord(
        operation_id="package.lthpkg",
        op_family="package",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=(),
        evidence_requirements=(
            "manifest_json",
            "semantic_index_json",
            "diagnostics_json",
            "materials_json",
            "operations_json",
            "evidence_json",
            "runtime_json",
        ),
        notes="Foundry F9 — lathe/asset_foundry/package_writer.py.",
    ),
    # ---- Lane A future-tasks (Wave 1) ----
    CapabilityRecord(
        operation_id="op.distribute.along_path",
        op_family="repetition",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=(),
        evidence_requirements=("instance_count", "placement_trace"),
        notes="Foundry distribution.distribute_along_path.",
    ),
    CapabilityRecord(
        operation_id="op.distribute.arc",
        op_family="repetition",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=(),
        evidence_requirements=("instance_count", "placement_trace"),
        notes="Foundry distribution.distribute_arc.",
    ),
    CapabilityRecord(
        operation_id="solid.extrude_twisted",
        op_family="solid",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=(),
        evidence_requirements=("visible_geometry",),
        notes="Foundry kernel_ops.extrude_deformers.TwistedExtrude.",
    ),
    CapabilityRecord(
        operation_id="solid.extrude_scaled",
        op_family="solid",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=(),
        evidence_requirements=("visible_geometry",),
        notes="Foundry kernel_ops.extrude_deformers.ScalingExtrude.",
    ),
    CapabilityRecord(
        operation_id="solid.partial_revolve",
        op_family="solid",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=(),
        evidence_requirements=("visible_geometry",),
        notes="Foundry kernel_ops.partial_revolve.",
    ),
    CapabilityRecord(
        operation_id="op.helical_sweep",
        op_family="solid",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=(),
        evidence_requirements=("visible_geometry",),
        notes="Foundry kernel_ops.helical_sweep — path sampler; kernel sweep consumes path.",
    ),
    CapabilityRecord(
        operation_id="primitive.involute_gear",
        op_family="solid",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=(),
        evidence_requirements=("visible_geometry",),
        notes="Foundry kernel_ops.involute_gear — 2D profile builder; pair with extrude.",
    ),
    CapabilityRecord(
        operation_id="curve.nurbs",
        op_family="solid",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=(),
        evidence_requirements=("curve_sample_count",),
        notes="Foundry kernel_ops.nurbs_curve — Cox-de Boor B-spline evaluator with weights.",
    ),
    CapabilityRecord(
        operation_id="deform.bend",
        op_family="edge",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=(),
        evidence_requirements=("visible_geometry",),
        notes="Foundry kernel_ops.deformers.apply_bend.",
    ),
    CapabilityRecord(
        operation_id="deform.twist",
        op_family="edge",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=(),
        evidence_requirements=("visible_geometry",),
        notes="Foundry kernel_ops.deformers.apply_twist.",
    ),
    CapabilityRecord(
        operation_id="deform.taper",
        op_family="edge",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=(),
        evidence_requirements=("visible_geometry",),
        notes="Foundry kernel_ops.deformers.apply_taper.",
    ),
    CapabilityRecord(
        operation_id="op.half_edge_bevel",
        op_family="edge",
        status=CapabilityStatus.PARTIAL,
        supporting_kernels=(),
        evidence_requirements=("bevel_ring_face_count",),
        fallback_reason="polybevel_fallback_when_half_edge_backend_absent",
        notes="Foundry kernel_ops.half_edge_bevel — planning only; polybevel fallback or unsupported when half_edge forced.",
    ),
    CapabilityRecord(
        operation_id="kernel.brep_ir",
        op_family="solid",
        status=CapabilityStatus.PARTIAL,
        supporting_kernels=(),
        evidence_requirements=("brep_face_count",),
        fallback_reason="occt_backend_not_configured",
        backend_required="occt_or_build123d",
        notes="Foundry kernel_ops.brep_ir — typed scaffold; OCCT/build123d integration deferred.",
    ),
    CapabilityRecord(
        operation_id="kernel.tessellation_policy",
        op_family="solid",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=(),
        evidence_requirements=("segment_counts_in_report",),
        notes="Foundry kernel_ops.tessellation_policy with 3 canonical profiles.",
    ),
    CapabilityRecord(
        operation_id="kernel.mesh_to_levelset_repair",
        op_family="solid",
        status=CapabilityStatus.PARTIAL,
        supporting_kernels=(),
        evidence_requirements=("levelset_status",),
        fallback_reason="openvdb_backend_not_configured",
        backend_required="openvdb_or_levelset_backend",
        notes="Foundry mesh_levelset_repair — last-resort fallback; output never claimed real.",
    ),
    # ---- Lane D additions ----
    CapabilityRecord(
        operation_id="color.oklab_mix",
        op_family="surface",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=(),
        evidence_requirements=("color_ramp_samples",),
        notes="Foundry oklab.oklab_mix / oklab_ramp.",
    ),
    CapabilityRecord(
        operation_id="material.materialx_lowering",
        op_family="surface",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=(),
        evidence_requirements=("materialx_document",),
        notes="Foundry materialx_lowering — stdlib lowering + colorspace sidecars.",
    ),
    CapabilityRecord(
        operation_id="material.materialx_serialization",
        op_family="surface",
        status=CapabilityStatus.PARTIAL,
        supporting_kernels=(),
        evidence_requirements=("materialx_file_path",),
        fallback_reason="materialx_serializer_not_configured",
        backend_required="materialx_serializer",
        notes="Typed MaterialX document generation exists; real .mtlx serialization is a backend boundary.",
    ),
    # ---- Lane F additions ----
    CapabilityRecord(
        operation_id="uv.constrained_packing",
        op_family="surface",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=(),
        evidence_requirements=("packing_report"),
        notes="Foundry constrained_packing — rectpack-style + UDIM overflow.",
    ),
    # ---- Lane H additions ----
    CapabilityRecord(
        operation_id="repair.rollback_loop",
        op_family="runtime",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=(),
        evidence_requirements=("repair_loop_result",),
        notes="Foundry repair_rollback — snapshot + restore on worse output.",
    ),
    # ---- Lane I additions ----
    CapabilityRecord(
        operation_id="authoring.stdlib_registry",
        op_family="package",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=(),
        evidence_requirements=("stdlib_entry_lookup",),
        notes="Foundry authoring.stdlib_registry — versioned kit registry.",
    ),
    CapabilityRecord(
        operation_id="authoring.director_vocabulary",
        op_family="package",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=(),
        evidence_requirements=("director_term_lookup",),
        notes="Foundry authoring.director_vocabulary — 6 v1 canonical terms.",
    ),
    CapabilityRecord(
        operation_id="authoring.field_attrs",
        op_family="package",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=(),
        evidence_requirements=("field_expression_evaluated",),
        notes="Foundry authoring.field_attrs — shunting-yard expression evaluator.",
    ),
    CapabilityRecord(
        operation_id="authoring.cga_assembly",
        op_family="package",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=(),
        evidence_requirements=("assembly_output_shapes",),
        notes="Foundry authoring.cga_assembly — Shape + SplitOp + AssemblyRule rewriting.",
    ),
    CapabilityRecord(
        operation_id="authoring.reference_extraction",
        op_family="package",
        status=CapabilityStatus.PARTIAL,
        supporting_kernels=(),
        evidence_requirements=("reference_board_signature",),
        fallback_reason="vision_pipeline_external",
        notes="Foundry authoring.reference_extraction — typed contract; vision pipeline is external.",
    ),
    # ---- Lane G later validators ----
    CapabilityRecord(
        operation_id="validator.silhouette_multi_angle",
        op_family="runtime",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=(),
        evidence_requirements=("silhouette_drift_ratio",),
        notes="Foundry validators.silhouette_multi_angle.",
    ),
    CapabilityRecord(
        operation_id="validator.frequency_energy",
        op_family="runtime",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=(),
        evidence_requirements=("frequency_compliance_score",),
        notes="Foundry validators.frequency_energy.",
    ),
    CapabilityRecord(
        operation_id="validator.topology_class_compliance",
        op_family="runtime",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=(),
        evidence_requirements=("topology_compliance_score",),
        notes="Foundry validators.topology_class_compliance.",
    ),
    CapabilityRecord(
        operation_id="validator.pbr_chart_compliance",
        op_family="runtime",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=(),
        evidence_requirements=("pbr_compliance_score",),
        notes="Foundry validators.pbr_chart.",
    ),
    CapabilityRecord(
        operation_id="validator.style_stack_compatibility",
        op_family="runtime",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=(),
        evidence_requirements=("style_band_compatibility_result",),
        notes="Foundry validators.style_stack_compatibility.",
    ),
    # ---- Phase 3 domain libraries ----
    CapabilityRecord(
        operation_id="domain.vegetation_tree_structure",
        op_family="stylized",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=(),
        evidence_requirements=("branch_count", "leaf_cluster_count"),
        notes="Foundry domain.vegetation — SpeedTree-inspired structure builder.",
    ),
    CapabilityRecord(
        operation_id="domain.terrain_heightfield",
        op_family="stylized",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=(),
        evidence_requirements=("heightfield_dim",),
        notes="Foundry domain.terrain — heightfield + erosion + material bands.",
    ),
    CapabilityRecord(
        operation_id="domain.wfc_solver",
        op_family="stylized",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=(),
        evidence_requirements=("wfc_grid_solved_or_contradiction",),
        notes="Foundry domain.wfc.solve_wfc_grid.",
    ),
    CapabilityRecord(
        operation_id="domain.opensubdiv_refinement",
        op_family="stylized",
        status=CapabilityStatus.PARTIAL,
        supporting_kernels=(),
        evidence_requirements=("subdivision_target_level",),
        fallback_reason="opensubdiv_backend_not_configured",
        backend_required="opensubdiv",
        notes="Foundry domain.opensubdiv — typed contract; backend external.",
    ),
    CapabilityRecord(
        operation_id="domain.scatter",
        op_family="stylized",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=(),
        evidence_requirements=("scatter_instance_count",),
        notes="Foundry domain.scatter — rectangle + polygon scatter.",
    ),
    CapabilityRecord(
        operation_id="domain.trim_sheets",
        op_family="surface",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=(),
        evidence_requirements=("trim_sheet_slot_binding",),
        notes="Foundry domain.trim_sheets — typed sheets + slot bindings.",
    ),
    CapabilityRecord(
        operation_id="domain.sdf_extraction",
        op_family="stylized",
        status=CapabilityStatus.PARTIAL,
        supporting_kernels=(),
        evidence_requirements=("sdf_extraction_method",),
        fallback_reason="openvdb_backend_not_configured",
        backend_required="openvdb_or_dual_contouring_backend",
        notes="Foundry domain.sdf_extraction — typed contract for dual-contouring / DMC.",
    ),
    # ---- Phase 4 organic + animation ----
    CapabilityRecord(
        operation_id="rig.skeleton_hierarchy",
        op_family="runtime",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=(),
        evidence_requirements=("rig_bone_count",),
        notes="Foundry rig.rig_ir — typed skeleton hierarchy.",
    ),
    CapabilityRecord(
        operation_id="rig.skin_program",
        op_family="runtime",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=(),
        evidence_requirements=("skin_weight_count",),
        notes="Foundry rig.skin_program with influence cap validation.",
    ),
    CapabilityRecord(
        operation_id="rig.morph_targets",
        op_family="runtime",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=(),
        evidence_requirements=("morph_count",),
        notes="Foundry rig.morph_targets — sparse vertex displacements.",
    ),
    CapabilityRecord(
        operation_id="rig.canonical_topology",
        op_family="runtime",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=(),
        evidence_requirements=("template_validation_diagnostics",),
        notes="Foundry rig.canonical_topology — biped + quadruped + crystal_pulse templates.",
    ),
    CapabilityRecord(
        operation_id="rig.animation_clip",
        op_family="runtime",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=(),
        evidence_requirements=("clip_duration_s", "track_count"),
        notes="Foundry rig.animation_compat — typed clip + track + library.",
    ),
    # ---- Phase 5 runtime/engine ----
    CapabilityRecord(
        operation_id="runtime.usd_generative_stage",
        op_family="package",
        status=CapabilityStatus.PARTIAL,
        supporting_kernels=(),
        evidence_requirements=("usd_stage_spec",),
        fallback_reason="usd_writer_not_configured",
        backend_required="usd_writer",
        notes="Foundry runtime.usd_generative — typed stage spec; USD writer external.",
    ),
    CapabilityRecord(
        operation_id="runtime.live_overrides",
        op_family="runtime",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=(),
        evidence_requirements=("override_session_history",),
        notes="Foundry runtime.live_overrides with constraint validation.",
    ),
    CapabilityRecord(
        operation_id="package.lthpkg_signed",
        op_family="package",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=(),
        evidence_requirements=("signed_envelope",),
        notes="Foundry runtime.signed_package — HMAC-SHA256 envelope + verify.",
    ),
    # ---- Strict geometry mode ----
    CapabilityRecord(
        operation_id="kernel.strict_geometry_mode",
        op_family="runtime",
        status=CapabilityStatus.SUPPORTED,
        supporting_kernels=(),
        evidence_requirements=("strict_geometry_report",),
        notes="Foundry strict_geometry_mode — env + runtime-config gated.",
    ),
)


def _claim_level_for_record(record: CapabilityRecord) -> CapabilityClaimLevel:
    """Return the static truth tier for a capability row.

    The matrix is not asset evidence. A supported row can claim a real
    artifact path is possible for valid inputs, but never
    ``product_complete`` without generated package/render evidence.
    """
    if record.claim_level is not None:
        return record.claim_level
    if record.status == CapabilityStatus.SUPPORTED:
        return CapabilityClaimLevel.ARTIFACT_REAL
    if record.backend_required or record.status in {
        CapabilityStatus.NOT_STARTED,
        CapabilityStatus.UNSUPPORTED,
    }:
        return CapabilityClaimLevel.TYPED_CONTRACT
    return CapabilityClaimLevel.EXECUTION_PARTIAL


def build_capability_matrix() -> FoundryCapabilityMatrix:
    """Build the full Foundry capability matrix.

    Pure deterministic function — does not consult the live kernel
    registry to avoid coupling status to optional dependencies. Each
    record's ``supporting_kernels`` describes which kernels *could*
    support the op when the dependency is installed; runtime probes
    (e.g. ``lathe.geometry.kernel.resolve_geometry_kernel``) determine
    which is *actually* selected for a given build.
    """
    counts_by_status: dict[str, int] = {s.value: 0 for s in CapabilityStatus}
    counts_by_family: dict[str, int] = {}
    counts_by_claim_level: dict[str, int] = {
        level.value: 0 for level in CapabilityClaimLevel
    }
    for record in _CAPABILITY_TABLE:
        counts_by_status[record.status.value] = (
            counts_by_status.get(record.status.value, 0) + 1
        )
        counts_by_family[record.op_family] = counts_by_family.get(record.op_family, 0) + 1
        claim_level = _claim_level_for_record(record)
        counts_by_claim_level[claim_level.value] = (
            counts_by_claim_level.get(claim_level.value, 0) + 1
        )
    return FoundryCapabilityMatrix(
        version=CAPABILITY_MATRIX_VERSION,
        records=_CAPABILITY_TABLE,
        record_count=len(_CAPABILITY_TABLE),
        counts_by_status=counts_by_status,
        counts_by_family=counts_by_family,
        counts_by_claim_level=counts_by_claim_level,
    )


def capability_matrix_to_dict(matrix: FoundryCapabilityMatrix) -> dict[str, Any]:
    """Serialize the capability matrix to a JSON-compatible dict."""
    return {
        "version": matrix.version,
        "record_count": matrix.record_count,
        "counts_by_status": dict(matrix.counts_by_status),
        "counts_by_family": dict(matrix.counts_by_family),
        "counts_by_claim_level": dict(matrix.counts_by_claim_level),
        "records": [
            {
                "operation_id": r.operation_id,
                "op_family": r.op_family,
                "status": r.status.value,
                "claim_level": _claim_level_for_record(r).value,
                "supporting_kernels": list(r.supporting_kernels),
                "evidence_requirements": list(r.evidence_requirements),
                "fallback_reason": r.fallback_reason,
                "backend_required": r.backend_required,
                "notes": r.notes,
            }
            for r in matrix.records
        ],
    }


__all__ = [
    "CAPABILITY_MATRIX_VERSION",
    "CapabilityClaimLevel",
    "CapabilityStatus",
    "CapabilityRecord",
    "FoundryCapabilityMatrix",
    "build_capability_matrix",
    "capability_matrix_to_dict",
]
