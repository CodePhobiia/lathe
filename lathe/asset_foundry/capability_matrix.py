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
        status=CapabilityStatus.NOT_STARTED,
        supporting_kernels=(),
        evidence_requirements=(),
        notes="Reserved for Foundry F4+. Use op.hull for shrink-wrap approximation today.",
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
        status=CapabilityStatus.PARTIAL,
        supporting_kernels=(),
        evidence_requirements=("instance_count",),
        fallback_reason="along_path_distribute_pending",
        notes="Grid + line + ring + perimeter implemented; along_path pending.",
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
        status=CapabilityStatus.PARTIAL,
        supporting_kernels=(),
        evidence_requirements=("seam_geometry",),
        fallback_reason="weld_bead_modeling_pending",
        notes="Currently emitted as a metadata-only seam record; bead geometry pending.",
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
        status=CapabilityStatus.NOT_STARTED,
        supporting_kernels=(),
        evidence_requirements=(),
        notes="Reserved for Foundry F8 (Floating Island generator).",
    ),
    # ---- Runtime cooking ----
    CapabilityRecord(
        operation_id="runtime.collision_proxy",
        op_family="runtime",
        status=CapabilityStatus.PARTIAL,
        supporting_kernels=(),
        evidence_requirements=("collision_glb",),
        fallback_reason="hull_only_no_decomposition",
        notes="Hull/concat collision works; convex decomposition pending.",
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
)


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
    for record in _CAPABILITY_TABLE:
        counts_by_status[record.status.value] = (
            counts_by_status.get(record.status.value, 0) + 1
        )
        counts_by_family[record.op_family] = counts_by_family.get(record.op_family, 0) + 1
    return FoundryCapabilityMatrix(
        version=CAPABILITY_MATRIX_VERSION,
        records=_CAPABILITY_TABLE,
        record_count=len(_CAPABILITY_TABLE),
        counts_by_status=counts_by_status,
        counts_by_family=counts_by_family,
    )


def capability_matrix_to_dict(matrix: FoundryCapabilityMatrix) -> dict[str, Any]:
    """Serialize the capability matrix to a JSON-compatible dict."""
    return {
        "version": matrix.version,
        "record_count": matrix.record_count,
        "counts_by_status": dict(matrix.counts_by_status),
        "counts_by_family": dict(matrix.counts_by_family),
        "records": [
            {
                "operation_id": r.operation_id,
                "op_family": r.op_family,
                "status": r.status.value,
                "supporting_kernels": list(r.supporting_kernels),
                "evidence_requirements": list(r.evidence_requirements),
                "fallback_reason": r.fallback_reason,
                "notes": r.notes,
            }
            for r in matrix.records
        ],
    }


__all__ = [
    "CAPABILITY_MATRIX_VERSION",
    "CapabilityStatus",
    "CapabilityRecord",
    "FoundryCapabilityMatrix",
    "build_capability_matrix",
    "capability_matrix_to_dict",
]
