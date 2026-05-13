"""Lathe Asset Foundry — manufacture beautiful, semantic, game-ready 3D assets from code.

The Foundry is the layer between Lathe's compiler+language substrate and
the @lathe/three web product. Its goal is to turn semantic intent into
real visible geometry + material zones + runtime evidence + .lthpkg
package output that the web viewer can inspect honestly.

Layered architecture (per docs/asset-quality/lathe-frontier-asset-foundry-masterplan.md):
  Layer 0 — Geometry Core            (kernel, KernelProgram, Manifold lane)
  Layer 1 — Stylized Operators       (prismatic, facet_field, half-space polyhedra)
  Layer 2 — Asset Grammar / Generators (per-family generator framework)
  Layer 3 — Runtime Asset Cooking    (collision, nav, LOD, materials, manifests)
  Layer 4 — Evidence, Diagnostics, Repair (certificates, quality ladders)
  Layer 5 — Package/Inspector Contract (.lthpkg writer for @lathe/three)

Phase mapping (masterplan §18):
  F0 — capability_matrix.py          (this phase: enumerate kernel ops + statuses)
  F1 — op_graph.py                   (typed GeometryOpGraph + planner)
  F2 — kernel telemetry (already in lathe/geometry/kernel_program.py)
  F3 — mesh feature ops (already in lathe/asset_quality/feature_ops_v2_lowering.py)
  F4 — prismatic.py + facet_field.py + polyhedron.py
  F5 — generators/ (crystal_cluster, pine_tree, stone_path, ...)
  F6 — runtime_cook.py
  F7 — certificates.py
  F8 — Golden Asset Set (drives generators + recorded fixtures)
  F9 — package_writer.py (.lthpkg emission)

The Foundry's non-negotiable contract: **no fake quality**. Every claim
must be backed by real geometry/material/runtime evidence OR labeled
explicitly as unsupported / fallback / proxy / not_verified.
"""

from __future__ import annotations

from .capability_matrix import (
    CAPABILITY_MATRIX_VERSION,
    CapabilityRecord,
    CapabilityStatus,
    FoundryCapabilityMatrix,
    build_capability_matrix,
    capability_matrix_to_dict,
)
from .certificates import (
    CERTIFICATE_VERSION,
    AssetQualityCertificate,
    QualityLadderLevel,
    compute_asset_certificate,
    quality_ladder_level_for_score,
)
from .facet_field import (
    FACET_FIELD_VERSION,
    FacetField2D,
    FacetField3D,
    FacetSample,
    sample_facet_field,
)
from .op_graph import (
    OP_GRAPH_VERSION,
    AttributeMapping,
    BackendLane,
    GeometryOpGraph,
    GeometryOpNode,
    OpGraphPlan,
    plan_op_graph,
)
from .package_writer import (
    LTHPKG_VERSION,
    LthpkgManifest,
    write_lthpkg,
)
from .polyhedron import (
    POLYHEDRON_VERSION,
    HalfSpace,
    HalfSpacePolyhedron,
    PrismMesh,
    build_half_space_polyhedron,
    build_prism_mesh,
)
from .prismatic import (
    PRISMATIC_VERSION,
    CrystalParameters,
    CrystalPrism,
    PrismaticCluster,
    build_crystal_cluster,
)
from .runtime_cook import (
    RUNTIME_COOK_VERSION,
    CollisionProxySpec,
    LodPolicySpec,
    NavContributionSpec,
    RuntimeArtifactManifest,
    cook_runtime_artifact,
)
from .style_pack import (
    STYLE_PACK_VERSION,
    LowPolyFantasyPalette,
    StylePack,
    lowpoly_fantasy_sunset_crystal,
)

__all__ = [
    # F0
    "CAPABILITY_MATRIX_VERSION",
    "CapabilityRecord",
    "CapabilityStatus",
    "FoundryCapabilityMatrix",
    "build_capability_matrix",
    "capability_matrix_to_dict",
    # F1
    "OP_GRAPH_VERSION",
    "AttributeMapping",
    "BackendLane",
    "GeometryOpGraph",
    "GeometryOpNode",
    "OpGraphPlan",
    "plan_op_graph",
    # F4
    "FACET_FIELD_VERSION",
    "FacetField2D",
    "FacetField3D",
    "FacetSample",
    "POLYHEDRON_VERSION",
    "PRISMATIC_VERSION",
    "CrystalParameters",
    "CrystalPrism",
    "HalfSpace",
    "HalfSpacePolyhedron",
    "PrismMesh",
    "PrismaticCluster",
    "build_crystal_cluster",
    "build_half_space_polyhedron",
    "build_prism_mesh",
    "sample_facet_field",
    # F6
    "RUNTIME_COOK_VERSION",
    "CollisionProxySpec",
    "LodPolicySpec",
    "NavContributionSpec",
    "RuntimeArtifactManifest",
    "cook_runtime_artifact",
    # F7
    "CERTIFICATE_VERSION",
    "AssetQualityCertificate",
    "QualityLadderLevel",
    "compute_asset_certificate",
    "quality_ladder_level_for_score",
    # F9
    "LTHPKG_VERSION",
    "LthpkgManifest",
    "write_lthpkg",
    # Style pack
    "STYLE_PACK_VERSION",
    "LowPolyFantasyPalette",
    "StylePack",
    "lowpoly_fantasy_sunset_crystal",
]
