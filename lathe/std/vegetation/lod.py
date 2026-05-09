"""Auto-LOD pipeline for vegetation.

Produces LOD0..LOD3 ladders:

- **LOD0**: the full procedural mesh — every branch + every leaf card.
  Triangle target: 5K-30K depending on species.
- **LOD1**: branch simplification — depth-truncated branch tree, leaf
  cards consolidated into denser fewer cards. Target: 1K-3K tris.
- **LOD2**: trunk + main branches only + a small leaf-card cluster.
  Target: 200-500 tris.
- **LOD3**: billboard imposter — single quad with the 8-view atlas.
  Target: 2 tris.

Each LOD is emitted as a list of stable ShapeIR primitive dicts so the
caller can hand them off to the assembly stage without coupling to the
ShapePrimitive dataclass at this layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .branches import (
    BranchSegment,
    collect_leaf_anchor_points,
    generate_branch_skeleton,
    lower_to_swept_profiles,
)
from .imposter import generate_imposter
from .leaves import lower_to_extruded_profiles, scatter_leaf_cards


@dataclass
class LODBundle:
    """A single LOD level."""

    level: int
    primitives: list[dict] = field(default_factory=list)
    triangle_estimate: int = 0
    description: str = ""

    def to_dict(self) -> dict:
        return {
            "level": self.level,
            "primitives": list(self.primitives),
            "triangle_estimate": self.triangle_estimate,
            "description": self.description,
        }


def _truncate_branches(
    segments: list[BranchSegment], *, max_depth: int
) -> list[BranchSegment]:
    """Return only the segments whose depth <= max_depth."""
    return [s for s in segments if s.depth <= max_depth]


def _estimate_triangles(primitives: list[dict]) -> int:
    """Cheap triangle estimate per primitive type."""
    total = 0
    for prim in primitives:
        ptype = prim.get("primitive_type")
        if ptype == "swept_profile":
            cs = prim.get("cross_section") or []
            sweep = prim.get("sweep_path") or []
            sides = max(3, len(cs))
            steps = max(1, len(sweep) - 1)
            total += sides * steps * 2
        elif ptype == "extruded_profile":
            poly = prim.get("profile_polygon") or []
            sides = max(3, len(poly))
            total += sides * 2 + (sides - 2) * 2  # walls + caps
        elif ptype == "revolved_profile":
            pts = prim.get("profile_points") or []
            total += max(0, len(pts) - 1) * 24 * 2
        elif ptype == "torus":
            total += 24 * 16 * 2
        elif ptype == "subdivision_box":
            total += 6 * 8
        elif ptype == "sphere":
            total += 12 * 24
        elif ptype == "box":
            total += 12
        elif ptype == "cylinder":
            total += 24 * 2
        else:
            total += 12
    return total


def _consolidate_leaves(leaf_primitives: list[dict], *, target_count: int) -> list[dict]:
    """Reduce leaf cards by sampling ~ target_count of them."""
    if not leaf_primitives:
        return []
    if len(leaf_primitives) <= target_count:
        return list(leaf_primitives)
    stride = max(1, len(leaf_primitives) // target_count)
    return [leaf_primitives[i] for i in range(0, len(leaf_primitives), stride)][:target_count]


def _silhouette_bounds(primitives: list[dict]) -> tuple[float, float, float]:
    """Compute the axis-aligned bounding box width × height × depth."""
    if not primitives:
        return (200.0, 400.0, 200.0)
    xs: list[float] = []
    ys: list[float] = []
    zs: list[float] = []
    for prim in primitives:
        center = prim.get("center") or (0.0, 0.0, 0.0)
        sweep = prim.get("sweep_path") or []
        if sweep:
            for p in sweep:
                xs.append(p[0])
                ys.append(p[1])
                zs.append(p[2])
        else:
            xs.append(center[0])
            ys.append(center[1])
            zs.append(center[2])
    if not xs:
        return (200.0, 400.0, 200.0)
    width = max(40.0, max(xs) - min(xs))
    height = max(40.0, max(ys) - min(ys))
    depth = max(40.0, max(zs) - min(zs))
    return (width, height, depth)


def generate_lods(
    species: Any,
    *,
    lod_count: int = 4,
) -> list[LODBundle]:
    """Generate LOD0..LOD{lod_count-1} for a compiled VegetationSpecies.

    Reads the species' branch grammar parameters and seeds, regenerates
    the full skeleton at LOD0, then progressively decimates depth and
    leaf count for higher LOD indices, and finally swaps in a billboard
    imposter at the last LOD when ``lod_count >= 4``.
    """
    branch_params = dict(species.branch_grammar)
    leaf_params = dict(species.leaf_grammar)
    # Build the full skeleton once.
    segments = generate_branch_skeleton(**branch_params)
    full_branch_prims = lower_to_swept_profiles(segments)
    leaf_anchors = collect_leaf_anchor_points(
        segments, min_depth=leaf_params.get("min_depth", 2)
    )
    leaf_cards = scatter_leaf_cards(
        leaf_anchors,
        leaf_size_cm=leaf_params.get("leaf_size_cm", 12.0),
        leaf_aspect=leaf_params.get("leaf_aspect", 1.4),
        leaves_per_anchor=leaf_params.get("leaves_per_anchor", 3),
        min_spacing_cm=leaf_params.get("min_spacing_cm", 4.0),
        palette_size=leaf_params.get("palette_size", 4),
        seed=leaf_params.get("seed", 4321),
    )
    full_leaf_prims = lower_to_extruded_profiles(
        leaf_cards, extrude_height_cm=leaf_params.get("extrude_height_cm", 0.05)
    )

    lods: list[LODBundle] = []
    if lod_count >= 1:
        prims = full_branch_prims + full_leaf_prims
        lods.append(
            LODBundle(
                level=0,
                primitives=prims,
                triangle_estimate=_estimate_triangles(prims),
                description="full procedural mesh — every branch and leaf card",
            )
        )
    if lod_count >= 2:
        max_depth = max(1, branch_params.get("max_depth", 4) - 1)
        truncated = _truncate_branches(segments, max_depth=max_depth)
        l1_branches = lower_to_swept_profiles(truncated)
        l1_leaves = _consolidate_leaves(full_leaf_prims, target_count=max(8, len(full_leaf_prims) // 4))
        prims = l1_branches + l1_leaves
        lods.append(
            LODBundle(
                level=1,
                primitives=prims,
                triangle_estimate=_estimate_triangles(prims),
                description="depth-truncated branches + consolidated leaf cards",
            )
        )
    if lod_count >= 3:
        max_depth = 1
        truncated = _truncate_branches(segments, max_depth=max_depth)
        l2_branches = lower_to_swept_profiles(truncated)
        l2_leaves = _consolidate_leaves(full_leaf_prims, target_count=max(4, len(full_leaf_prims) // 12))
        prims = l2_branches + l2_leaves
        lods.append(
            LODBundle(
                level=2,
                primitives=prims,
                triangle_estimate=_estimate_triangles(prims),
                description="trunk + first-tier branches + leaf-card cluster",
            )
        )
    if lod_count >= 4:
        bounds = _silhouette_bounds(full_branch_prims + full_leaf_prims)
        imposter = generate_imposter(silhouette_extents_cm=bounds)
        prims = list(imposter["primitives"])
        bundle = LODBundle(
            level=3,
            primitives=prims,
            triangle_estimate=2,
            description="billboard imposter (8-view sprite atlas, scaffold)",
        )
        # Stash the imposter atlas spec on the bundle so the caller can
        # forward it to engine adapters.
        bundle_dict_extra = {"imposter_atlas": imposter["imposter_atlas"]}
        lods.append(bundle)
        # Attach it via a side-channel attribute (LODBundle is a dataclass
        # but Python lets us add attributes ad-hoc on the instance; we
        # also expose it explicitly through to_dict).
        bundle.imposter_atlas = bundle_dict_extra["imposter_atlas"]  # type: ignore[attr-defined]
    return lods


def lods_to_dict(lods: list[LODBundle]) -> list[dict]:
    """Serialize LODs and inline the imposter atlas if present."""
    out: list[dict] = []
    for bundle in lods:
        record = bundle.to_dict()
        atlas = getattr(bundle, "imposter_atlas", None)
        if atlas is not None:
            record["imposter_atlas"] = atlas
        out.append(record)
    return out
