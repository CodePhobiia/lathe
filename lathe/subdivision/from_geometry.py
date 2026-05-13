"""Lift a normalised asset's ``geometry.subdivision`` block into a spec.

``apply_finishing`` is the entry point the executor calls between the
topology stage and any downstream stage that needs a refined mesh.
The function reads the asset record (a dict produced by the resolver),
returns the original mesh untouched if no subdivision finishing was
requested, and otherwise builds a :class:`SubdivisionFinishingSpec`,
runs the validator, and refines the mesh.

The authoring surface accepts two shapes:

* an inline geometry block::

    geometry {
        subdivision.scheme   = "catmull_clark"
        subdivision.levels   = 2
        subdivision.boundary = "smooth"
        subdivision.creases  = [
            { vertices = [4, 5], sharpness = 1.0 },
            { vertices = [5, 6], sharpness = "infinity" },
        ]
    }

* a top-level ``subdivision_finishing`` decl referenced from the asset's
  ``build.topology.subdivision_finishing`` field (e.g.
  ``build.topology.subdivision_finishing = "chest_lid_finish"``). When
  present the named decl's payload is merged with the inline block,
  with the asset's inline values taking priority.

Hero asset classes (per :func:`hero_default_spec`) get an implicit
``catmull_clark`` level-1 finishing pass when neither explicit form
is present and ``build.topology.subdivision_finishing != "disabled"``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .boundary import BoundaryRule
from .creases import CreaseTags
from .mesh import SubdivMesh, mesh_from_arrays
from .scheme import SubdivisionScheme, parse_scheme

HERO_CLASS_DEFAULTS: dict[str, dict[str, Any]] = {
    "hard_surface_prop": {"scheme": "catmull_clark", "levels": 1, "boundary": "smooth"},
    "env_module": {"scheme": "catmull_clark", "levels": 1, "boundary": "sharp"},
    "mechanical_assembly": {"scheme": "catmull_clark", "levels": 1, "boundary": "sharp"},
}


@dataclass(frozen=True)
class SubdivisionFinishingSpec:
    """Finishing-pass parameters resolved for a single asset."""

    scheme: SubdivisionScheme
    levels: int
    boundary: BoundaryRule
    creases: CreaseTags
    backend: str = "auto"
    source: str = "explicit"  # "explicit" | "hero_default" | "decl"

    @classmethod
    def from_block(
        cls,
        block: Mapping[str, Any] | None,
        *,
        source: str = "explicit",
    ) -> SubdivisionFinishingSpec | None:
        """Build a spec from a subdivision block, ``None`` if disabled."""
        if not block:
            return None
        if str(block.get("disabled", "")).lower() in {"true", "1", "yes"}:
            return None
        levels_raw = block.get("levels", block.get("level", 1))
        try:
            levels = int(levels_raw)
        except (TypeError, ValueError):
            levels = 1
        if levels <= 0:
            return None
        scheme = parse_scheme(block.get("scheme", "catmull_clark"))
        boundary_raw = block.get("boundary", "smooth")
        boundary = (
            boundary_raw
            if isinstance(boundary_raw, BoundaryRule)
            else BoundaryRule.from_text(str(boundary_raw))
        )
        creases = CreaseTags.from_records(
            edge_records=block.get("creases", block.get("crease_tags")),
            corner_records=block.get("corners", block.get("corner_tags")),
        )
        backend = str(block.get("backend", "auto"))
        return cls(
            scheme=scheme,
            levels=levels,
            boundary=boundary,
            creases=creases,
            backend=backend,
            source=source,
        )


def hero_default_spec(asset_class: str | None) -> SubdivisionFinishingSpec | None:
    """Return the implicit hero-build subdivision pass for ``asset_class``."""
    if not asset_class:
        return None
    defaults = HERO_CLASS_DEFAULTS.get(asset_class)
    if not defaults:
        return None
    return SubdivisionFinishingSpec.from_block(defaults, source="hero_default")


def from_geometry_block(
    asset: Mapping[str, Any],
    *,
    decl_lookup: Mapping[str, Mapping[str, Any]] | None = None,
) -> SubdivisionFinishingSpec | None:
    """Extract the subdivision finishing spec for ``asset``.

    Resolution order:
        1. ``build.topology.subdivision_finishing`` decl reference, if any.
        2. ``geometry.subdivision`` inline block (overrides decl values).
        3. hero default for ``asset.kind`` when neither is present.
        4. ``None`` when the build explicitly disables the pass.
    """
    geometry = asset.get("geometry") or {}
    inline_block = geometry.get("subdivision") or geometry.get("subdivision_finishing")

    build = asset.get("build") or {}
    topology_cfg = build.get("topology") or {}
    finishing_setting = topology_cfg.get("subdivision_finishing")
    if isinstance(finishing_setting, str) and finishing_setting.strip().lower() in {
        "disabled",
        "off",
        "none",
        "skip",
    }:
        return None

    decl_block: Mapping[str, Any] | None = None
    if (
        isinstance(finishing_setting, str)
        and decl_lookup
        and finishing_setting in decl_lookup
    ):
        decl_block = decl_lookup[finishing_setting]
    elif isinstance(finishing_setting, Mapping):
        decl_block = finishing_setting

    merged: dict[str, Any] = {}
    if decl_block:
        merged.update(dict(decl_block))
    if isinstance(inline_block, Mapping):
        merged.update(dict(inline_block))

    if merged:
        spec = SubdivisionFinishingSpec.from_block(
            merged,
            source="decl" if decl_block and not inline_block else "explicit",
        )
        if spec is not None:
            return spec

    return hero_default_spec(asset.get("kind"))


def apply_finishing(
    mesh: SubdivMesh,
    spec: SubdivisionFinishingSpec | None,
) -> tuple[SubdivMesh, dict[str, Any]]:
    """Run ``spec`` against ``mesh`` and return ``(refined_mesh, report)``.

    ``spec=None`` returns the mesh unchanged with a ``skipped`` report.
    """
    if spec is None or spec.levels <= 0:
        return mesh, {"applied": False, "reason": "no subdivision spec"}

    from . import subdivide_mesh
    from .opensubdiv_backend import opensubdiv_availability
    from .validator import validate_for_subdivision

    sanity = validate_for_subdivision(mesh)
    refined = subdivide_mesh(
        mesh,
        scheme=spec.scheme,
        levels=spec.levels,
        creases=spec.creases,
        boundary=spec.boundary,
        backend=spec.backend,
    )
    osd = opensubdiv_availability()
    report: dict[str, Any] = {
        "applied": True,
        "scheme": spec.scheme.value,
        "levels": spec.levels,
        "boundary": spec.boundary.value,
        "spec_source": spec.source,
        "input_stats": sanity,
        "output_stats": {
            "vertex_count": refined.vertex_count(),
            "edge_count": refined.edge_count(),
            "face_count": refined.face_count(),
            "is_quad_only": refined.is_quad_only(),
        },
        "crease_count": len(spec.creases.edges),
        "corner_count": len(spec.creases.corners),
        "backend_attempted": spec.backend,
        "backend_actual": "opensubdiv" if (spec.backend != "cpu" and osd.available) else "cpu",
        "opensubdiv_available": osd.available,
        "opensubdiv_module": osd.module_name,
        "opensubdiv_version": osd.version,
    }
    if not osd.available and spec.backend != "cpu":
        report["fallback_reason"] = osd.reason
    return refined, report


@dataclass
class WorkedChestLidExample:
    """Reproducible chest-lid cage + crease setup used in docs/tests.

    The cage is a 1.0 x 0.4 x 0.6 m cuboid with the *top-back* edge
    declared as a fully sharp crease; applying Catmull-Clark twice
    yields a pillow-shaped lid with a knife-sharp hinge edge -- the
    canonical "smooth surface, one preserved sharp edge" output the
    roadmap names as the success criterion.
    """

    width: float = 1.0
    height: float = 0.4
    depth: float = 0.6

    def cage(self) -> SubdivMesh:
        """Return the low-poly cuboid cage."""
        hw = self.width * 0.5
        hh = self.height * 0.5
        hd = self.depth * 0.5
        positions = [
            (-hw, -hh, -hd),  # 0 bottom-front-left
            (hw, -hh, -hd),   # 1 bottom-front-right
            (hw, -hh, hd),    # 2 bottom-back-right
            (-hw, -hh, hd),   # 3 bottom-back-left
            (-hw, hh, -hd),   # 4 top-front-left
            (hw, hh, -hd),    # 5 top-front-right
            (hw, hh, hd),     # 6 top-back-right
            (-hw, hh, hd),    # 7 top-back-left
        ]
        faces = [
            (0, 1, 2, 3),  # bottom
            (4, 7, 6, 5),  # top
            (0, 4, 5, 1),  # front
            (1, 5, 6, 2),  # right
            (2, 6, 7, 3),  # back
            (3, 7, 4, 0),  # left
        ]
        return mesh_from_arrays(positions, faces)

    def spec(self, levels: int = 2) -> SubdivisionFinishingSpec:
        """Catmull-Clark spec with the top-back hinge edge sharpened.

        The hinge edge runs between vertices 6 and 7. Marking just the
        single edge produces a "dart" -- the edge stays crisp at the
        first refinement but the corner vertices drift inward as the
        rest of the lid eases off. To produce the canonical
        "smooth surface, one preserved sharp edge" result the example
        promises, we additionally pin the corner vertices (``corners``)
        so they stay locked to the cage. The remaining 11 edges are
        smooth, so the lid pillows out everywhere except along the
        hinge -- exactly the chest-lid silhouette that hero builds want.
        """
        creases = CreaseTags.from_records(
            edge_records=(
                {"vertices": [6, 7], "sharpness": "infinity"},
            ),
            corner_records=(
                {"vertex": 6, "sharpness": "infinity"},
                {"vertex": 7, "sharpness": "infinity"},
            ),
        )
        return SubdivisionFinishingSpec(
            scheme=SubdivisionScheme.CATMULL_CLARK,
            levels=levels,
            boundary=BoundaryRule.SMOOTH,
            creases=creases,
            source="explicit",
        )

    def run(self, levels: int = 2) -> tuple[SubdivMesh, dict[str, Any]]:
        """Run the example end-to-end and return ``(refined_mesh, report)``."""
        mesh = self.cage()
        return apply_finishing(mesh, self.spec(levels=levels))


__all__ = [
    "HERO_CLASS_DEFAULTS",
    "SubdivisionFinishingSpec",
    "WorkedChestLidExample",
    "apply_finishing",
    "from_geometry_block",
    "hero_default_spec",
]
