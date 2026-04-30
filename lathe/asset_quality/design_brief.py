"""Phase 2 deterministic ``DesignBrief`` representation.

Adds an internal ``DesignBrief`` IR that captures explicit art-direction
intent for every hero asset *before* geometry is generated, without
changing public ``.lth`` syntax. Existing assets receive a deterministic
default brief inferred from the asset name and intent role; future
phases (family grammar, semantic construction graph, material/wear
graph) consume the brief to drive thresholds and structural rules.

Spec: ``docs/asset-quality/lathe-asset-quality-upgrade-spec.md`` Section 7.
Tasklist: ``docs/asset-quality/improvement-tasklist.md`` Phase 2.
Per-field reference: ``docs/asset-quality/design-brief-ir.md``.

Family inference rule
---------------------

``_infer_family`` examines, in order:

1. ``asset["name"]`` (case-insensitive substring match);
2. ``asset["intent"]["role"]`` (case-insensitive substring match);
3. ``asset["kind"]`` (case-insensitive substring match) when present.

The first match wins. Substring tokens are tried in this order:
``crate`` -> ``industrial_crate``; ``door`` -> ``mechanical_door``;
``cabinet`` -> ``service_cabinet``. If no token matches the asset falls
back to the ``generic`` family. Tokens are checked deterministically
(no random sampling, no hashing) so the same input always yields the
same family.

The validator is registered in ``lathe/core/stages/validate.py``'s
``_PIPELINE`` first (no stage dependencies, ``weight=0.0``) so the
brief lands on ``runtime["design_brief"]`` before any other validator
runs and is therefore available as input to downstream phases.

Output additively appears under the top-level ``design_brief`` key of
the validate-stage report. Existing report fields are preserved and the
validator never produces blocking diagnostics — like Phase 1, this layer
is informational evidence for downstream classifiers and grammar
checks.

Phase 11 negative-constraint integration
----------------------------------------

When the executor publishes a reference board to
``runtime["_reference_board"]`` (see
``lathe.asset_quality.reference_board``), the brief's
``negative_constraints`` field is extended with each
reference-negative constraint string. Existing per-family default
constraints come first; reference negatives are appended in the order
they appear in the fixture, deduplicated against the existing list.
This is the only Phase 11 edit to ``design_brief.py`` — every other
field of the brief (asset name, family, role, style tags, silhouette,
bevel/shape language, detail density, wear, material age, greeble
style) is unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


VERSION = "design_brief_v1"


@dataclass(frozen=True)
class DesignBrief:
    """Immutable record of art-direction intent for one asset.

    All twelve fields are populated for every brief; the per-family
    defaults below guarantee no field is ever ``None``. ``style_tags``
    and ``negative_constraints`` are tuples (not lists) so the dataclass
    remains hashable and frozen.
    """

    asset_name: str
    family: str
    role: str
    style_tags: tuple[str, ...]
    silhouette: str
    bevel_language: str
    shape_language: str
    detail_density: str
    wear: str
    material_age: str
    greeble_style: str
    negative_constraints: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dict (lists in place of tuples)."""
        return {
            "asset_name": self.asset_name,
            "family": self.family,
            "role": self.role,
            "style_tags": list(self.style_tags),
            "silhouette": self.silhouette,
            "bevel_language": self.bevel_language,
            "shape_language": self.shape_language,
            "detail_density": self.detail_density,
            "wear": self.wear,
            "material_age": self.material_age,
            "greeble_style": self.greeble_style,
            "negative_constraints": list(self.negative_constraints),
        }


_FAMILY_TOKENS: tuple[tuple[str, str], ...] = (
    ("crate", "industrial_crate"),
    ("door", "mechanical_door"),
    ("cabinet", "service_cabinet"),
)


_FAMILY_DEFAULTS: dict[str, dict[str, Any]] = {
    "industrial_crate": {
        "role": "reinforced industrial cargo crate",
        "style_tags": ("utility", "industrial", "shipping"),
        "silhouette": "bold",
        "bevel_language": "chunky_industrial",
        "shape_language": "rectangular_with_45deg_cuts",
        "detail_density": "hero",
        "wear": "medium_edge_wear",
        "material_age": "used_not_destroyed",
        "greeble_style": "functional_only",
        "negative_constraints": ("toy_like", "random_faceting", "ornate"),
    },
    "mechanical_door": {
        "role": "industrial mechanical access door",
        "style_tags": ("utility", "industrial", "access"),
        "silhouette": "balanced",
        "bevel_language": "crisp_industrial",
        "shape_language": "framed_panel_with_inset_leaf",
        "detail_density": "hero",
        "wear": "medium_edge_wear",
        "material_age": "used_not_destroyed",
        "greeble_style": "functional_only",
        "negative_constraints": ("toy_like", "random_faceting", "ornate"),
    },
    "service_cabinet": {
        "role": "wall-mounted service utility cabinet",
        "style_tags": ("utility", "industrial", "service"),
        "silhouette": "compact",
        "bevel_language": "crisp_industrial",
        "shape_language": "rectangular_panelled_box",
        "detail_density": "hero",
        "wear": "light_edge_wear",
        "material_age": "in_service",
        "greeble_style": "functional_only",
        "negative_constraints": ("toy_like", "random_faceting", "ornate"),
    },
    "generic": {
        "role": "hard-surface utility asset",
        "style_tags": ("utility", "industrial"),
        "silhouette": "balanced",
        "bevel_language": "crisp_industrial",
        "shape_language": "rectangular_panelled",
        "detail_density": "standard",
        "wear": "light_edge_wear",
        "material_age": "in_service",
        "greeble_style": "functional_only",
        "negative_constraints": ("toy_like", "random_faceting"),
    },
}


def _as_str(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _match_token(text: str) -> str:
    """Return the family token that matches ``text`` (case-insensitive)."""
    if not text:
        return ""
    lowered = text.lower()
    for token, _family in _FAMILY_TOKENS:
        if token in lowered:
            return token
    return ""


def _infer_family(asset: dict[str, Any]) -> tuple[str, str, str]:
    """Pick the family for ``asset`` deterministically.

    Returns ``(family, signal, token)`` where ``signal`` is one of
    ``"name"``, ``"role"``, ``"kind"``, or ``"default"`` and ``token``
    is the matched substring (empty when ``signal == "default"``).
    """
    name = _as_str(asset.get("name"))
    intent = asset.get("intent") if isinstance(asset.get("intent"), dict) else {}
    role = _as_str(intent.get("role"))
    kind = _as_str(asset.get("kind"))

    for signal, source in (("name", name), ("role", role), ("kind", kind)):
        token = _match_token(source)
        if token:
            family = next(family for tok, family in _FAMILY_TOKENS if tok == token)
            return family, signal, token

    return "generic", "default", ""


def _build_default_brief(asset_name: str, family: str) -> DesignBrief:
    """Return the deterministic per-family default brief."""
    defaults = _FAMILY_DEFAULTS.get(family, _FAMILY_DEFAULTS["generic"])
    return DesignBrief(
        asset_name=asset_name,
        family=family,
        role=defaults["role"],
        style_tags=tuple(defaults["style_tags"]),
        silhouette=defaults["silhouette"],
        bevel_language=defaults["bevel_language"],
        shape_language=defaults["shape_language"],
        detail_density=defaults["detail_density"],
        wear=defaults["wear"],
        material_age=defaults["material_age"],
        greeble_style=defaults["greeble_style"],
        negative_constraints=tuple(defaults["negative_constraints"]),
    )


def _reference_negative_constraints(runtime: dict[str, Any]) -> tuple[str, ...]:
    """Extract negative constraint strings from a Phase 11 reference board.

    Reads ``runtime["_reference_board"]`` (the raw dict the executor
    publishes from ``lathe.asset_quality.reference_board.load_reference_board``).
    Tolerates missing/None/non-dict slots by returning an empty tuple.
    Each entry is preserved in fixture order; the caller dedupes.
    """
    raw = runtime.get("_reference_board") if isinstance(runtime, dict) else None
    if not isinstance(raw, dict):
        return ()
    negatives = raw.get("negatives")
    if not isinstance(negatives, list):
        return ()
    out: list[str] = []
    for entry in negatives:
        if not isinstance(entry, dict):
            continue
        constraint = entry.get("constraint")
        if isinstance(constraint, str) and constraint:
            out.append(constraint)
    return tuple(out)


def _merge_negative_constraints(
    existing: tuple[str, ...], references: tuple[str, ...]
) -> tuple[str, ...]:
    """Append reference negatives to existing brief constraints.

    Existing brief values are preserved in their original order and
    placed first; reference values are appended in fixture order.
    Duplicates are dropped while preserving first-occurrence order so
    the result is deterministic regardless of how the reference list
    overlaps the brief defaults.
    """
    seen: set[str] = set()
    merged: list[str] = []
    for value in (*existing, *references):
        if not isinstance(value, str) or not value:
            continue
        if value in seen:
            continue
        seen.add(value)
        merged.append(value)
    return tuple(merged)


def evaluate_design_brief(
    asset: dict[str, Any], runtime: dict[str, Any]
) -> dict[str, Any]:
    """Build the additive design-brief payload for the validate stage.

    Args:
        asset: normalized asset dict. May omit ``intent``, ``name``, or
            ``kind``; the function tolerates partial/empty input.
        runtime: stage-bundle runtime dict. Phase 2 does not consume any
            stage runtime evidence directly — the brief itself is
            derived from the asset alone. Phase 11 adds a single read
            of ``runtime["_reference_board"]`` (the raw dict the
            executor publishes from
            :func:`lathe.asset_quality.reference_board.load_reference_board`)
            to merge reference-supplied negative constraints into the
            brief's ``negative_constraints`` field. When the slot is
            missing the brief is identical to the Phase 2 baseline.

    Returns:
        Additive payload with ``version`` (``"design_brief_v1"``),
        ``brief`` (12-field dict from :meth:`DesignBrief.to_dict`), and
        ``family_inference`` (``matched_family``/``match_signal``/
        ``match_token``). No top-level ``diagnostics`` key — like
        Phase 1, this validator is informational only and never blocks
        certification.
    """
    safe_asset = asset if isinstance(asset, dict) else {}
    safe_runtime = runtime if isinstance(runtime, dict) else {}
    asset_name = _as_str(safe_asset.get("name")) or "unnamed_asset"
    family, signal, token = _infer_family(safe_asset)
    base_brief = _build_default_brief(asset_name=asset_name, family=family)
    reference_negatives = _reference_negative_constraints(safe_runtime)
    merged_negatives = _merge_negative_constraints(
        base_brief.negative_constraints, reference_negatives
    )
    if merged_negatives != base_brief.negative_constraints:
        brief = DesignBrief(
            asset_name=base_brief.asset_name,
            family=base_brief.family,
            role=base_brief.role,
            style_tags=base_brief.style_tags,
            silhouette=base_brief.silhouette,
            bevel_language=base_brief.bevel_language,
            shape_language=base_brief.shape_language,
            detail_density=base_brief.detail_density,
            wear=base_brief.wear,
            material_age=base_brief.material_age,
            greeble_style=base_brief.greeble_style,
            negative_constraints=merged_negatives,
        )
    else:
        brief = base_brief
    return {
        "version": VERSION,
        "brief": brief.to_dict(),
        "family_inference": {
            "matched_family": family,
            "match_signal": signal,
            "match_token": token,
        },
    }
