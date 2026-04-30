"""Phase 7 deterministic high-poly / low-poly relation evidence.

Builds the additive evidence layer that makes the high-poly versus
low-poly relationship truthful and staged. Phase 7 is **evidence and
diagnostic only** — it does not run Blender, run a bake, or produce
high-poly geometry. The evaluator inspects the live shape, topology,
and surface bundles, scores how real the high/low relationship is,
and emits warnings when the score is below the warning threshold.

Spec: ``docs/asset-quality/lathe-asset-quality-upgrade-spec.md`` Section 11.
Tasklist: ``docs/asset-quality/improvement-tasklist.md`` Phase 7.
Per-metric reference: ``docs/asset-quality/high-low-relation-v1.md``.

Design summary
--------------

Phase 7 reads three sources from the runtime:

- ``runtime["surface"]["bundle"]["highlow_relation"]`` — the
  :class:`lathe.highlow.HighLowRelation` dict published by
  ``surface_runtime`` carrying ``high_mesh_uri``, ``low_mesh_uri``,
  ``high_triangle_count``, ``low_triangle_count``.
- ``runtime["surface"]["bundle"]["bake_outputs"]`` (and the broader
  ``outputs`` map) — the per-map evidence the bake stage publishes for
  ``normal``, ``ao``, ``curvature``, and ``id``.
- ``runtime["topology"]["bundle"]["mesh_uri"]`` — the runtime low-poly
  mesh URI, used as cross-evidence for the low side of the relation.

The evaluator computes a strengthened ``realness_score`` from four
weighted credits:

- ``distinct_uri_credit`` (max 0.15) — the high and low URIs are
  distinct paths, evidence that the surface stage produced a separate
  candidate mesh and a separate runtime topology mesh.
- ``distinct_triangle_credit`` (max 0.30) — the high mesh carries a
  meaningful triangle delta over the low mesh; awards full credit at
  >= 0.20 delta ratio and scales linearly below.
- ``bake_map_completeness`` (max 0.25) — the four canonical bake maps
  (normal, ao, curvature, id) are present in the surface outputs.
- ``manifest_quality`` (max 0.10) — both high and low URIs are
  populated and no external tool was skipped.

Score >= 0.80 clears the warning (``is_real_highlow=True``); score
< 0.80 fires the warning. The warning text is informational only and
appears under the ``warnings`` key of the payload.

Strict mode
-----------

Strict mode is opt-in via the ``LATHE_STRICT_HIGHLOW`` environment
variable. When set to a truthy value (``"1"``, ``"true"``, ``"yes"``,
case-insensitive) and the realness check fails, the validator emits
a ``severity="error"`` diagnostic that the validator-pipeline
composition layer surfaces as a certification failure. Default mode
keeps ``diagnostics=[]`` so existing examples build clean.

Skipped-evidence contract
-------------------------

When a tool is unavailable or the manifest is incomplete, the
``BakeMapEvidence`` for the missing map records a structured
``skipped_reason`` (``"manifest_incomplete"``,
``"blender_unavailable"``, ``"no_high_poly_source"``). Per
``AGENTS.md``, the evaluator never invents results.

Pipeline placement
------------------

The validator is registered in ``lathe/core/stages/validate.py``'s
``_PIPELINE`` immediately after ``flow_quality`` (so the surface
bundle is fully populated) and before ``geometry_integrity``. Output
additively appears under the top-level ``highlow_relation`` key of
the validate-stage report (the 21st top-level key, on top of the 20
that Phases 0 through 6 publish).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


HIGHLOW_RELATION_VERSION = "highlow_relation_v1"

_REALNESS_PASS_THRESHOLD = 0.80
_TRIANGLE_DELTA_FULL_CREDIT_RATIO = 0.20
_DISTINCT_URI_CREDIT = 0.15
_DISTINCT_TRIANGLE_CREDIT = 0.30
_BAKE_MAP_COMPLETENESS_CREDIT = 0.25
_MANIFEST_QUALITY_CREDIT = 0.10

_EXPECTED_BAKE_MAPS: tuple[str, ...] = ("normal", "ao", "curvature", "id")

_STRICT_TRUTHY_VALUES: frozenset[str] = frozenset({"1", "true", "yes"})

_STRICT_ENV_VAR = "LATHE_STRICT_HIGHLOW"

_DIAGNOSTIC_CODE = "L6701"
_DIAGNOSTIC_NAME = "highlow_fake_detail"

_HERO_FAMILIES: frozenset[str] = frozenset(
    {
        "brassbound_chest",
        "courier_drone",
        "console_terminal",
        "industrial_crate",
        "mechanical_door",
        "service_cabinet",
        "control_pedestal",
        "supply_container",
    }
)


@dataclass(frozen=True)
class BakeMapEvidence:
    """Evidence for one canonical bake map (normal / ao / curvature / id).

    ``present`` is ``True`` when the surface stage published a usable
    URI for the map. ``skipped_reason`` is a structured token recorded
    when the map is absent because an external tool was unavailable or
    the manifest is incomplete; it is ``None`` when the map is present.
    """

    map_name: str
    present: bool
    uri: str | None
    skipped_reason: str | None


@dataclass(frozen=True)
class HighlowEvidence:
    """Aggregate high-poly / low-poly evidence record.

    Carries the URIs, triangle counts, derived deltas, per-map bake
    evidence, structured skipped reasons, and the verdict
    (``is_real_highlow``) plus its source ``realness_score``.
    """

    high_mesh_uri: str | None
    low_mesh_uri: str | None
    runtime_low_uri: str | None
    high_triangle_count: int | None
    low_triangle_count: int | None
    distinct_uris: bool
    distinct_triangle_counts: bool
    triangle_delta_ratio: float
    bake_maps: tuple[BakeMapEvidence, ...]
    bake_map_count_present: int
    bake_map_count_expected: int
    skipped_reasons: tuple[dict[str, str], ...]
    is_real_highlow: bool
    realness_score: float
    required: bool


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_str_or_none(value: Any) -> str | None:
    if isinstance(value, str) and value:
        return value
    return None


def _as_int_or_none(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return None


def _strict_mode_enabled() -> bool:
    raw = os.environ.get(_STRICT_ENV_VAR)
    if raw is None:
        return False
    return raw.strip().lower() in _STRICT_TRUTHY_VALUES


def _normalise_family_token(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    token = value.strip().lower()
    if not token:
        return None
    if token.endswith("_family"):
        token = token[: -len("_family")]
    return token


def _family_tokens_from_runtime(runtime: dict[str, Any]) -> list[str]:
    tokens: list[str] = []
    design_brief = _as_dict(runtime.get("design_brief"))
    brief = _as_dict(design_brief.get("brief"))
    shape_bundle = _as_dict(_as_dict(runtime.get("shape")).get("bundle"))
    asset_graph = _as_dict(shape_bundle.get("asset_graph"))
    for value in (brief.get("family"), asset_graph.get("family")):
        token = _normalise_family_token(value)
        if token:
            tokens.append(token)
    return tokens


def _family_tokens_from_asset(asset: dict[str, Any]) -> list[str]:
    tokens: list[str] = []
    for value in (
        asset.get("name"),
        _as_dict(asset.get("assembly")).get("family"),
        asset.get("family"),
    ):
        token = _normalise_family_token(value)
        if token:
            tokens.append(token)
    return tokens


def is_highlow_required(asset: dict[str, Any], runtime: dict[str, Any]) -> bool:
    """Return whether Phase 7 high/low evidence is required for this asset."""
    surface_bundle = _surface_bundle(runtime)
    manifest = _as_dict(surface_bundle.get("surface_manifest"))
    hero_surface = manifest.get("hero_surface")
    if isinstance(hero_surface, bool):
        return hero_surface
    tokens = _family_tokens_from_runtime(runtime) + _family_tokens_from_asset(asset)
    return any(token in _HERO_FAMILIES for token in tokens)


def _surface_bundle(runtime: dict[str, Any]) -> dict[str, Any]:
    return _as_dict(_as_dict(runtime.get("surface")).get("bundle"))


def _topology_bundle(runtime: dict[str, Any]) -> dict[str, Any]:
    return _as_dict(_as_dict(runtime.get("topology")).get("bundle"))


def _resolve_bake_map_uri(outputs: dict[str, Any], map_name: str) -> str | None:
    """Return the URI string for ``map_name`` or ``None`` if not present.

    Outputs may store either a flat string URI or a nested entry dict
    with a ``uri`` field (the surface stage uses the dict shape). Both
    are tolerated.
    """
    entry = outputs.get(map_name)
    if isinstance(entry, str) and entry:
        return entry
    if isinstance(entry, dict):
        return _as_str_or_none(entry.get("uri"))
    return None


def _bake_map_evidence(
    outputs: dict[str, Any],
    high_mesh_uri: str | None,
    skipped_reasons: list[dict[str, str]],
) -> tuple[BakeMapEvidence, ...]:
    """Return the per-map evidence tuple for the four canonical maps."""
    evidence_records: list[BakeMapEvidence] = []
    for map_name in _EXPECTED_BAKE_MAPS:
        uri = _resolve_bake_map_uri(outputs, map_name)
        if uri is not None:
            evidence_records.append(
                BakeMapEvidence(
                    map_name=map_name,
                    present=True,
                    uri=uri,
                    skipped_reason=None,
                )
            )
            continue
        if high_mesh_uri is None:
            reason = "no_high_poly_source"
        else:
            reason = "manifest_incomplete"
        skipped_reasons.append({"tool": f"bake_{map_name}", "reason": reason})
        evidence_records.append(
            BakeMapEvidence(
                map_name=map_name,
                present=False,
                uri=None,
                skipped_reason=reason,
            )
        )
    return tuple(evidence_records)


def _triangle_delta_ratio(
    high_triangle_count: int | None, low_triangle_count: int | None
) -> float:
    """Return positive high-over-low detail delta as a non-negative float.

    The relation only earns triangle credit when the high-poly source
    has strictly more triangles than the runtime low mesh. Missing,
    zero, negative, or inverted counts yield ``0.0``.
    """
    high_value = float(high_triangle_count) if isinstance(high_triangle_count, int) else 0.0
    low_value = float(low_triangle_count) if isinstance(low_triangle_count, int) else 0.0
    if high_value <= 0.0 or low_value < 0.0 or high_value <= low_value:
        return 0.0
    return round((high_value - low_value) / max(1.0, high_value), 6)


def _compute_realness_score(
    *,
    distinct_uris: bool,
    triangle_delta_ratio: float,
    bake_map_count_present: int,
    bake_map_count_expected: int,
    high_mesh_uri: str | None,
    low_mesh_uri: str | None,
    skipped_reasons_count: int,
) -> float:
    """Compute the realness score in ``[0.0, 1.0]``.

    Four weighted credits sum to a single score:

    - ``distinct_uri_credit`` (0.15) — high and low URIs are distinct.
    - ``distinct_triangle_credit`` (0.30) — full credit at delta ratio
      >= 0.20; linear scale below.
    - ``bake_map_completeness`` (0.25) — fraction of the four canonical
      bake maps that are present.
    - ``manifest_quality`` (0.10) — both URIs populated and no skipped
      reasons recorded.
    """
    distinct_uri_credit = _DISTINCT_URI_CREDIT if distinct_uris else 0.0
    if triangle_delta_ratio >= _TRIANGLE_DELTA_FULL_CREDIT_RATIO:
        distinct_triangle_credit = _DISTINCT_TRIANGLE_CREDIT
    else:
        ratio = max(0.0, triangle_delta_ratio) / _TRIANGLE_DELTA_FULL_CREDIT_RATIO
        distinct_triangle_credit = _DISTINCT_TRIANGLE_CREDIT * ratio
    bake_map_completeness = _BAKE_MAP_COMPLETENESS_CREDIT * (
        bake_map_count_present / max(1, bake_map_count_expected)
    )
    manifest_complete = bool(high_mesh_uri and low_mesh_uri and skipped_reasons_count == 0)
    manifest_quality = _MANIFEST_QUALITY_CREDIT if manifest_complete else 0.0
    score = (
        distinct_uri_credit
        + distinct_triangle_credit
        + bake_map_completeness
        + manifest_quality
    )
    return round(max(0.0, min(1.0, score)), 6)


def _bake_map_outputs(surface_bundle: dict[str, Any]) -> dict[str, Any]:
    """Return the merged bake outputs dict.

    ``bake_outputs`` (when present) is the canonical map-name -> URI
    short-form. ``outputs`` carries the full per-map record. Either is
    tolerated; the canonical short-form takes precedence.
    """
    bake_outputs = _as_dict(surface_bundle.get("bake_outputs"))
    outputs = _as_dict(surface_bundle.get("outputs"))
    merged: dict[str, Any] = dict(outputs)
    for map_name, value in bake_outputs.items():
        if value:
            merged[map_name] = value
    return merged


def _runtime_low_uri(topology_bundle: dict[str, Any]) -> str | None:
    return _as_str_or_none(topology_bundle.get("mesh_uri"))


def _build_evidence(asset: dict[str, Any], runtime: dict[str, Any]) -> HighlowEvidence:
    surface_bundle = _surface_bundle(runtime)
    topology_bundle = _topology_bundle(runtime)
    required = is_highlow_required(asset, runtime)
    highlow = _as_dict(surface_bundle.get("highlow_relation"))
    high_mesh_uri = _as_str_or_none(highlow.get("high_mesh_uri"))
    low_mesh_uri = _as_str_or_none(highlow.get("low_mesh_uri"))
    runtime_low_uri = _runtime_low_uri(topology_bundle)
    high_triangle_count = _as_int_or_none(highlow.get("high_triangle_count"))
    low_triangle_count = _as_int_or_none(highlow.get("low_triangle_count"))
    distinct_uris = bool(
        high_mesh_uri and low_mesh_uri and high_mesh_uri != low_mesh_uri
    )
    distinct_triangle_counts = bool(
        high_triangle_count is not None
        and low_triangle_count is not None
        and high_triangle_count != low_triangle_count
    )
    triangle_delta_ratio = _triangle_delta_ratio(high_triangle_count, low_triangle_count)
    # Per-bake-map skipped reasons live inside each ``BakeMapEvidence``
    # entry (granular, one per requested map). The top-level
    # ``skipped_reasons`` list captures URI-level gaps (missing high or
    # low mesh URI). The two stores are deliberately disjoint — consumers
    # iterate ``bake_maps`` for per-map evidence and read top-level
    # ``skipped_reasons`` for whole-pipeline gaps.
    skipped_reasons: list[dict[str, str]] = []
    bake_outputs = _bake_map_outputs(surface_bundle)
    bake_maps = _bake_map_evidence(bake_outputs, high_mesh_uri, skipped_reasons)
    bake_map_count_present = sum(1 for entry in bake_maps if entry.present)
    bake_map_count_expected = len(_EXPECTED_BAKE_MAPS)
    if high_mesh_uri is None:
        skipped_reasons.append({"tool": "shape_high_poly", "reason": "no_high_poly_source"})
    if low_mesh_uri is None:
        skipped_reasons.append(
            {"tool": "topology_low_poly", "reason": "manifest_incomplete"}
        )
    realness_score = _compute_realness_score(
        distinct_uris=distinct_uris,
        triangle_delta_ratio=triangle_delta_ratio,
        bake_map_count_present=bake_map_count_present,
        bake_map_count_expected=bake_map_count_expected,
        high_mesh_uri=high_mesh_uri,
        low_mesh_uri=low_mesh_uri,
        skipped_reasons_count=len(skipped_reasons),
    )
    is_real_highlow = realness_score >= _REALNESS_PASS_THRESHOLD
    return HighlowEvidence(
        high_mesh_uri=high_mesh_uri,
        low_mesh_uri=low_mesh_uri,
        runtime_low_uri=runtime_low_uri,
        high_triangle_count=high_triangle_count,
        low_triangle_count=low_triangle_count,
        distinct_uris=distinct_uris,
        distinct_triangle_counts=distinct_triangle_counts,
        triangle_delta_ratio=triangle_delta_ratio,
        bake_maps=bake_maps,
        bake_map_count_present=bake_map_count_present,
        bake_map_count_expected=bake_map_count_expected,
        skipped_reasons=tuple(skipped_reasons),
        is_real_highlow=is_real_highlow,
        realness_score=realness_score,
        required=required,
    )


def _bake_map_to_dict(entry: BakeMapEvidence) -> dict[str, Any]:
    return {
        "map_name": entry.map_name,
        "present": entry.present,
        "uri": entry.uri,
        "skipped_reason": entry.skipped_reason,
    }


def _warning_text(evidence: HighlowEvidence) -> str:
    # Specific-first; generic fallback last. The order is deliberate:
    # the most diagnostic phrasing (identical triangle counts -> high-mesh
    # absent -> generic low-realness) leads so readers see the actionable
    # cause before the generic score statement.
    high_count = evidence.high_triangle_count
    low_count = evidence.low_triangle_count
    if (
        high_count is not None
        and low_count is not None
        and high_count == low_count
        and high_count > 0
    ):
        return (
            f"hero asset uses fake high/low: high_triangle_count == low_triangle_count "
            f"== {high_count}; consider a real high-poly producer (Phase 8+)."
        )
    if (
        high_count is not None
        and low_count is not None
        and high_count > 0
        and low_count > high_count
    ):
        return (
            f"hero asset uses inverted high/low: low_triangle_count ({low_count}) "
            f"exceeds high_triangle_count ({high_count}); consider a real "
            f"high-poly producer (Phase 8+)."
        )
    if not evidence.high_mesh_uri:
        return (
            "hero asset has no high-poly source; consider a real high-poly producer "
            "(Phase 8+)."
        )
    return (
        f"hero asset has weak high/low realness "
        f"(realness_score={evidence.realness_score:.3f}); consider a real high-poly "
        f"producer (Phase 8+)."
    )


def _diagnostic_record(evidence: HighlowEvidence) -> dict[str, Any]:
    return {
        "code": _DIAGNOSTIC_CODE,
        "name": _DIAGNOSTIC_NAME,
        "severity": "error",
        "message": _warning_text(evidence),
        "details": {
            "realness_score": evidence.realness_score,
            "is_real_highlow": evidence.is_real_highlow,
            "high_mesh_uri": evidence.high_mesh_uri,
            "low_mesh_uri": evidence.low_mesh_uri,
            "high_triangle_count": evidence.high_triangle_count,
            "low_triangle_count": evidence.low_triangle_count,
            "triangle_delta_ratio": evidence.triangle_delta_ratio,
            "bake_map_count_present": evidence.bake_map_count_present,
            "bake_map_count_expected": evidence.bake_map_count_expected,
        },
    }


def evaluate_highlow_relation(
    asset: dict[str, Any], runtime: dict[str, Any]
) -> dict[str, Any]:
    """Build the additive high-poly / low-poly relation payload.

    Args:
        asset: normalized asset dict. Carried for signature parity with
            other validators; the evaluator currently reads only the
            runtime bundles.
        runtime: stage-bundle runtime dict. Reads the surface bundle's
            ``highlow_relation``, ``outputs``, and ``bake_outputs``
            keys plus the topology bundle's ``mesh_uri``.

    Returns:
        Additive payload with ``version`` (``"highlow_relation_v1"``),
        verdict (``is_real_highlow``), score (``realness_score``),
        URIs (``high_mesh_uri``, ``low_mesh_uri``, ``runtime_low_uri``),
        triangle counts and derived ``triangle_delta_ratio``,
        ``distinct_uris`` and ``distinct_triangle_counts`` flags,
        per-map ``bake_maps`` list with ``bake_map_count_present`` /
        ``bake_map_count_expected`` summary, structured
        ``skipped_reasons``, ``warnings`` (string list — non-empty when
        the verdict fails), and ``diagnostics`` (empty by default; in
        strict mode a single ``severity="error"`` record when the
        verdict fails).
    """
    safe_asset = asset if isinstance(asset, dict) else {}
    safe_runtime = runtime if isinstance(runtime, dict) else {}
    evidence = _build_evidence(safe_asset, safe_runtime)
    bake_maps_payload = [_bake_map_to_dict(entry) for entry in evidence.bake_maps]
    skipped_reasons_payload = [dict(record) for record in evidence.skipped_reasons]
    warnings: list[str] = []
    diagnostics: list[dict[str, Any]] = []
    if evidence.required and not evidence.is_real_highlow:
        warnings.append(_warning_text(evidence))
        if _strict_mode_enabled():
            diagnostics.append(_diagnostic_record(evidence))
    return {
        "version": HIGHLOW_RELATION_VERSION,
        "is_real_highlow": evidence.is_real_highlow,
        "realness_score": evidence.realness_score,
        "high_mesh_uri": evidence.high_mesh_uri,
        "low_mesh_uri": evidence.low_mesh_uri,
        "runtime_low_uri": evidence.runtime_low_uri,
        "high_triangle_count": evidence.high_triangle_count,
        "low_triangle_count": evidence.low_triangle_count,
        "triangle_delta_ratio": evidence.triangle_delta_ratio,
        "distinct_uris": evidence.distinct_uris,
        "distinct_triangle_counts": evidence.distinct_triangle_counts,
        "bake_maps": bake_maps_payload,
        "bake_map_count_present": evidence.bake_map_count_present,
        "bake_map_count_expected": evidence.bake_map_count_expected,
        "skipped_reasons": skipped_reasons_payload,
        "warnings": warnings,
        "diagnostics": diagnostics,
        "required": evidence.required,
    }
