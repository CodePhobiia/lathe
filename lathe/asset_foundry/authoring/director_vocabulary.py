"""Director vocabulary — stdlib compositions for style direction.

Per northstar §10 Lane I priority task #3. A director vocabulary
maps short author-friendly tokens (``stylized_low_poly_fantasy``,
``chunky_industrial_bevel``, ``warning_decal_grid``) to executable
compositions of operators + style policies. Authors invoke the term;
the compiler lowers it into ops the kernel can execute.

This module hosts the typed registry + canonical v1 vocabulary. New
terms register without changing public ``.lth`` syntax — they slot
into ``art_direction`` blocks as enum values.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

DIRECTOR_VOCABULARY_VERSION = "lathe.asset_foundry.director_vocabulary_v1"


@dataclass(frozen=True)
class DirectorComposition:
    """The executable composition one term expands to."""

    style_pack_id: str | None = None
    """Bind to a specific style pack when set."""

    facet_policy: Mapping[str, str] = field(default_factory=dict)
    bevel_policy: Mapping[str, str] = field(default_factory=dict)
    material_policy: Mapping[str, str] = field(default_factory=dict)
    feature_ops_required: tuple[str, ...] = ()
    """Op tokens (matching capability_matrix records) the term
    requires when applied."""

    forbidden_failure_modes: tuple[str, ...] = ()


@dataclass(frozen=True)
class DirectorTerm:
    """One vocabulary term."""

    term_id: str
    description: str
    composition: DirectorComposition
    applies_to_families: tuple[str, ...] = ("*",)
    """When ``("*",)``, term applies to any family."""


@dataclass
class DirectorRegistry:
    """Mutable registry. Use ``director_registry_v1()`` for the canonical set."""

    terms: list[DirectorTerm] = field(default_factory=list)

    def register(self, term: DirectorTerm) -> None:
        for existing in self.terms:
            if existing.term_id == term.term_id:
                raise ValueError(f"director term {term.term_id!r} already registered")
        self.terms.append(term)

    def lookup(self, term_id: str) -> DirectorTerm | None:
        for t in self.terms:
            if t.term_id == term_id:
                return t
        return None

    def list_for_family(self, family: str) -> tuple[DirectorTerm, ...]:
        return tuple(
            t for t in self.terms if family in t.applies_to_families or "*" in t.applies_to_families
        )


def resolve_director_term(
    registry: DirectorRegistry,
    term_id: str,
) -> DirectorComposition:
    """Resolve a term to its composition. Raises ``KeyError`` when missing."""
    term = registry.lookup(term_id)
    if term is None:
        raise KeyError(f"unknown director term: {term_id!r}")
    return term.composition


def director_registry_v1() -> DirectorRegistry:
    """Canonical v1 director vocabulary."""
    reg = DirectorRegistry()
    reg.register(
        DirectorTerm(
            term_id="stylized_low_poly_fantasy",
            description="LowPolyFantasy style pack, flat normals, faceted everything.",
            composition=DirectorComposition(
                style_pack_id="lowpoly_fantasy_sunset_crystal_v1",
                facet_policy={"all": "flat_normals"},
                bevel_policy={"silhouette": "none", "timber": "chunky_2mm"},
                material_policy={"crystal": "crystal_violet_emissive"},
                feature_ops_required=("style.facet_field", "style.flat_normal_policy"),
                forbidden_failure_modes=("uncontrolled_random_triangulation",),
            ),
        )
    )
    reg.register(
        DirectorTerm(
            term_id="chunky_industrial_bevel",
            description="6mm chamfer on silhouette edges + 2mm bevels elsewhere.",
            composition=DirectorComposition(
                bevel_policy={
                    "silhouette": "chamfer_6mm_1seg",
                    "secondary": "chamfer_2mm_1seg",
                    "tertiary": "none",
                },
                feature_ops_required=("op.chamfer",),
            ),
            applies_to_families=("*",),
        )
    )
    reg.register(
        DirectorTerm(
            term_id="warning_decal_grid",
            description="Yellow/black warning stripes on exposed flat panels.",
            composition=DirectorComposition(
                feature_ops_required=("op.decal_zone", "op.repeat"),
                forbidden_failure_modes=("decal_uniform_noise_no_intent",),
            ),
            applies_to_families=("industrial_crate", "service_cabinet", "mechanical_door"),
        )
    )
    reg.register(
        DirectorTerm(
            term_id="factory_hardsurface",
            description="Panel inset + fastener grid + trim band hierarchy.",
            composition=DirectorComposition(
                feature_ops_required=(
                    "op.panel_inset",
                    "op.fastener_grid",
                    "op.trim_band",
                ),
            ),
            applies_to_families=("industrial_crate", "service_cabinet", "control_pedestal"),
        )
    )
    reg.register(
        DirectorTerm(
            term_id="faceted_cliffside",
            description="Radial facet field on cliff sides + dramatic underside shards.",
            composition=DirectorComposition(
                style_pack_id="lowpoly_fantasy_sunset_crystal_v1",
                facet_policy={"cliff": "flat_normals"},
                feature_ops_required=("style.facet_field", "mesh.crystal_prism"),
            ),
            applies_to_families=("floating_island_small", "violet_crystal_cluster"),
        )
    )
    reg.register(
        DirectorTerm(
            term_id="sunset_crystal_palette",
            description="Violet+magenta+cyan+golden+lavender palette.",
            composition=DirectorComposition(
                style_pack_id="lowpoly_fantasy_sunset_crystal_v1",
                material_policy={
                    "primary": "crystal_violet_emissive",
                    "secondary": "crystal_magenta",
                    "accent": "crystal_cyan_dim",
                    "wall": "wall_plaster",
                    "roof": "roof_thatch_golden",
                },
            ),
        )
    )
    return reg


__all__ = [
    "DIRECTOR_VOCABULARY_VERSION",
    "DirectorComposition",
    "DirectorRegistry",
    "DirectorTerm",
    "director_registry_v1",
    "resolve_director_term",
]
