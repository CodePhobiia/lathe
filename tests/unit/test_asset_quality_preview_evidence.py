"""Phase 9 tests for ``lathe.asset_quality.preview_evidence``.

Covers per task #9 of ``docs/asset-quality/improvement-tasklist.md``:

- The payload shape contract is the canonical eight top-level keys
  declared in the master prompt (``version``, ``asset_name``,
  ``previews``, ``preview_summary``, ``report_links``,
  ``skipped_reasons``, ``warnings``, ``diagnostics``).
- ``PreviewEntry``, ``BakeMapEntry``, and ``SkippedReason`` are
  frozen dataclasses with ``to_dict`` round-trips.
- The full preview set (``turntable``, ``wireframe``,
  ``material_ids``, ``uv_layout``, ``collision``, ``lod_sheet``)
  lands one entry per category in fixed emission order.
- ``distinct_final_from_material_ids`` is True iff both previews
  are requested and their paths differ.
- A package config requesting ``material_ids`` without
  ``turntable`` fires the documented warning and keeps the flag
  False.
- An unrecognised preview name lands in ``skipped_reasons`` with
  category ``unknown_preview_<name>`` and reason
  ``preview_role_not_recognized``.
- Bake-map evidence sourced from ``surface.bundle.maps`` /
  ``surface.bundle.outputs`` populates ``bake_maps`` and emits a
  structured skipped reason for every absent canonical map.
- The comparison sheet records ``comparison_sheet_not_requested``
  when ``package.comparison_sheet`` is absent and
  ``comparison_sheet_renderer_unavailable`` when requested (Phase 9
  ships the renderer as a no-op stub by design).
- Every entry in ``report_links`` is a relative path (no leading
  slash, no scheme), and the published URIs are deduplicated.
- The evaluator is deterministic — identical input yields identical
  output across calls.
- An empty ``package.previews`` list emits the per-category
  ``preview_not_requested_by_package_config`` skipped tokens and a
  zero ``total_preview_count``.
- The ``ValidatorPipeline`` publishes the evidence under
  ``runtime["preview_evidence"]`` (the composition layer's
  automatic per-validator publication).
"""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from typing import Any

import pytest

from lathe.asset_quality.preview_evidence import (
    PREVIEW_EVIDENCE_VERSION,
    BakeMapEntry,
    PreviewEntry,
    SkippedReason,
    evaluate_preview_evidence,
)
from lathe.validators.composition import FunctionValidator, ValidatorPipeline


_PAYLOAD_KEYS: frozenset[str] = frozenset(
    {
        "version",
        "asset_name",
        "previews",
        "preview_summary",
        "report_links",
        "skipped_reasons",
        "warnings",
        "diagnostics",
    }
)


_PREVIEW_CATEGORY_ORDER: tuple[str, ...] = (
    "final_beauty",
    "material_ids",
    "wireframe",
    "uv_layout",
    "collision",
    "lod_sheet",
    "bake_maps",
    "comparison_sheet",
)


_RENDERABLE_CATEGORIES: frozenset[str] = frozenset(
    {
        "final_beauty",
        "material_ids",
        "wireframe",
        "uv_layout",
        "collision",
        "lod_sheet",
    }
)


def _full_preview_asset() -> dict[str, Any]:
    """Return an asset dict requesting all six standard previews."""
    return {
        "name": "industrial_crate",
        "build": {
            "package": {
                "previews": [
                    "turntable",
                    "wireframe",
                    "material_ids",
                    "uv_layout",
                    "collision",
                    "lod_sheet",
                ]
            }
        },
    }


def _runtime_with_full_bake_outputs() -> dict[str, Any]:
    """Return a runtime dict with all four canonical bake maps published."""
    return {
        "surface": {
            "bundle": {
                "maps": ["basecolor", "normal", "ao", "curvature", "id"],
                "outputs": {
                    "normal": {"uri": "stages/surface/maps/normal.png"},
                    "ao": {"uri": "stages/surface/maps/ao.png"},
                    "curvature": {"uri": "stages/surface/maps/curvature.png"},
                    "id": {"uri": "stages/surface/maps/id.png"},
                },
            }
        }
    }


def _runtime_with_partial_bake_outputs() -> dict[str, Any]:
    """Return a runtime dict with only normal + ao + id published."""
    return {
        "surface": {
            "bundle": {
                "maps": ["basecolor", "normal", "ao", "orm", "id"],
                "outputs": {
                    "normal": {"uri": "stages/surface/maps/normal.png"},
                    "ao": {"uri": "stages/surface/maps/ao.png"},
                    "id": {"uri": "stages/surface/maps/id.png"},
                },
            }
        }
    }


def _empty_runtime() -> dict[str, Any]:
    """Return a runtime dict with no surface bundle published yet."""
    return {}


# ---------------------------------------------------------------------------
# Frozen dataclass contract
# ---------------------------------------------------------------------------


def test_preview_entry_is_frozen() -> None:
    entry = PreviewEntry(
        role="final_beauty",
        mode="shaded",
        name="turntable",
        path="stages/package/previews/turntable.png",
        status="declared",
    )
    with pytest.raises(FrozenInstanceError):
        entry.path = "different.png"  # type: ignore[misc]


def test_bake_map_entry_is_frozen() -> None:
    entry = BakeMapEntry(role="normal_map", uri="x.png", status="declared")
    with pytest.raises(FrozenInstanceError):
        entry.uri = "y.png"  # type: ignore[misc]


def test_skipped_reason_is_frozen() -> None:
    record = SkippedReason(category="comparison_sheet", reason="x")
    with pytest.raises(FrozenInstanceError):
        record.reason = "y"  # type: ignore[misc]


def test_preview_entry_to_dict_round_trip() -> None:
    entry = PreviewEntry(
        role="final_beauty",
        mode="shaded",
        name="turntable",
        path="stages/package/previews/turntable.png",
        status="declared",
    )
    payload = entry.to_dict()
    assert payload == {
        "role": "final_beauty",
        "mode": "shaded",
        "name": "turntable",
        "path": "stages/package/previews/turntable.png",
        "status": "declared",
    }


# ---------------------------------------------------------------------------
# Top-level payload shape
# ---------------------------------------------------------------------------


def test_evaluate_preview_evidence_returns_v1_payload() -> None:
    asset = _full_preview_asset()
    runtime = _runtime_with_full_bake_outputs()
    payload = evaluate_preview_evidence(asset, runtime)

    assert payload["version"] == PREVIEW_EVIDENCE_VERSION
    assert payload["version"] == "preview_evidence_v1"
    missing = _PAYLOAD_KEYS - payload.keys()
    extra = payload.keys() - _PAYLOAD_KEYS
    assert not missing, f"missing required keys: {sorted(missing)}"
    assert not extra, f"unexpected keys: {sorted(extra)}"
    assert payload["asset_name"] == "industrial_crate"
    assert isinstance(payload["previews"], dict)
    assert isinstance(payload["preview_summary"], dict)
    assert isinstance(payload["report_links"], list)
    assert isinstance(payload["skipped_reasons"], list)
    assert isinstance(payload["warnings"], list)
    assert isinstance(payload["diagnostics"], list)


def test_previews_dict_uses_fixed_emission_order() -> None:
    payload = evaluate_preview_evidence(
        _full_preview_asset(), _runtime_with_full_bake_outputs()
    )

    assert tuple(payload["previews"].keys()) == _PREVIEW_CATEGORY_ORDER


def test_full_preview_set_categorizes_correctly() -> None:
    asset = _full_preview_asset()
    runtime = _runtime_with_full_bake_outputs()
    payload = evaluate_preview_evidence(asset, runtime)
    previews = payload["previews"]

    final_beauty = previews["final_beauty"]
    assert len(final_beauty) == 1
    assert final_beauty[0]["role"] == "final_beauty"
    assert final_beauty[0]["mode"] == "shaded"
    assert final_beauty[0]["name"] == "turntable"
    assert final_beauty[0]["path"] == "stages/package/previews/turntable.png"
    assert final_beauty[0]["status"] == "declared"

    assert len(previews["material_ids"]) == 1
    assert previews["material_ids"][0]["mode"] == "material_ids"
    assert previews["material_ids"][0]["name"] == "material_ids"

    assert len(previews["wireframe"]) == 1
    assert previews["wireframe"][0]["mode"] == "wireframe"
    assert previews["wireframe"][0]["name"] == "wireframe"

    assert len(previews["uv_layout"]) == 1
    assert previews["uv_layout"][0]["mode"] == "uv_layout"

    assert len(previews["collision"]) == 1
    assert previews["collision"][0]["mode"] == "wireframe"

    assert len(previews["lod_sheet"]) == 1
    assert previews["lod_sheet"][0]["mode"] == "lod_sheet"

    assert payload["preview_summary"]["total_preview_count"] == 6
    assert payload["preview_summary"]["final_beauty_present"] is True
    assert payload["preview_summary"]["material_ids_present"] is True
    assert payload["preview_summary"]["wireframe_present"] is True


# ---------------------------------------------------------------------------
# Final-beauty distinction
# ---------------------------------------------------------------------------


def test_final_beauty_distinct_from_material_ids() -> None:
    payload = evaluate_preview_evidence(
        _full_preview_asset(), _runtime_with_full_bake_outputs()
    )

    final_paths = {entry["path"] for entry in payload["previews"]["final_beauty"]}
    material_paths = {entry["path"] for entry in payload["previews"]["material_ids"]}
    assert final_paths != material_paths
    assert payload["preview_summary"]["distinct_final_from_material_ids"] is True
    assert payload["warnings"] == []


def test_only_material_ids_warns_about_missing_final_beauty() -> None:
    asset = {
        "name": "minimal_asset",
        "build": {"package": {"previews": ["material_ids"]}},
    }
    payload = evaluate_preview_evidence(asset, _empty_runtime())

    assert payload["preview_summary"]["final_beauty_present"] is False
    assert payload["preview_summary"]["material_ids_present"] is True
    assert payload["preview_summary"]["distinct_final_from_material_ids"] is False
    assert any(
        "material_ids" in warning and "turntable" in warning
        for warning in payload["warnings"]
    ), payload["warnings"]


def test_only_turntable_does_not_set_distinct_flag() -> None:
    asset = {
        "name": "turntable_only",
        "build": {"package": {"previews": ["turntable"]}},
    }
    payload = evaluate_preview_evidence(asset, _empty_runtime())

    assert payload["preview_summary"]["final_beauty_present"] is True
    assert payload["preview_summary"]["material_ids_present"] is False
    assert payload["preview_summary"]["distinct_final_from_material_ids"] is False
    assert payload["warnings"] == []


# ---------------------------------------------------------------------------
# Unknown previews
# ---------------------------------------------------------------------------


def test_unknown_preview_name_emits_skipped_reason() -> None:
    asset = {
        "name": "exotic",
        "build": {"package": {"previews": ["turntable", "exotic_view"]}},
    }
    payload = evaluate_preview_evidence(asset, _empty_runtime())

    skipped = {record["category"]: record["reason"] for record in payload["skipped_reasons"]}
    assert "unknown_preview_exotic_view" in skipped
    assert skipped["unknown_preview_exotic_view"] == "preview_role_not_recognized"
    # Unknown previews never land in any of the renderable categories.
    for category in _RENDERABLE_CATEGORIES:
        for entry in payload["previews"][category]:
            assert entry["name"] != "exotic_view"


def test_duplicate_unknown_preview_names_dedupe_to_single_skipped_entry() -> None:
    asset = {
        "name": "duplicate",
        "build": {"package": {"previews": ["foo", "foo", "foo"]}},
    }
    payload = evaluate_preview_evidence(asset, _empty_runtime())

    foo_records = [
        record
        for record in payload["skipped_reasons"]
        if record["category"] == "unknown_preview_foo"
    ]
    assert len(foo_records) == 1
    assert foo_records[0]["reason"] == "preview_role_not_recognized"


# ---------------------------------------------------------------------------
# Bake-map handling
# ---------------------------------------------------------------------------


def test_bake_maps_populated_from_surface_bundle() -> None:
    payload = evaluate_preview_evidence(
        _full_preview_asset(), _runtime_with_full_bake_outputs()
    )
    bake_maps = payload["previews"]["bake_maps"]

    roles = [entry["role"] for entry in bake_maps]
    assert roles == ["normal_map", "ao_map", "curvature_map", "id_map"]
    for entry in bake_maps:
        assert entry["status"] == "declared"
        assert isinstance(entry["uri"], str) and entry["uri"]


def test_bake_maps_partial_outputs_emit_skipped_reason_for_missing() -> None:
    payload = evaluate_preview_evidence(
        _full_preview_asset(), _runtime_with_partial_bake_outputs()
    )
    bake_maps = payload["previews"]["bake_maps"]
    bake_map_by_role = {entry["role"]: entry for entry in bake_maps}

    assert bake_map_by_role["normal_map"]["uri"] is not None
    assert bake_map_by_role["ao_map"]["uri"] is not None
    assert bake_map_by_role["id_map"]["uri"] is not None
    # curvature is not declared in maps and not published — skipped
    # reason fires.
    assert bake_map_by_role.get("curvature_map") is None or bake_map_by_role[
        "curvature_map"
    ]["uri"] is None

    skipped_categories = {record["category"] for record in payload["skipped_reasons"]}
    skipped_reasons = {
        record["category"]: record["reason"] for record in payload["skipped_reasons"]
    }
    assert "curvature_map" in skipped_categories
    assert skipped_reasons["curvature_map"] == "bake_map_not_produced"
    assert payload["preview_summary"]["bake_map_count"] == 3


def test_bake_maps_no_surface_bundle_emits_all_skipped() -> None:
    payload = evaluate_preview_evidence(_full_preview_asset(), _empty_runtime())
    skipped_categories = {record["category"] for record in payload["skipped_reasons"]}

    assert {"normal_map", "ao_map", "curvature_map", "id_map"} <= skipped_categories
    assert payload["preview_summary"]["bake_map_count"] == 0


def test_bake_map_declared_without_uri_records_none_status() -> None:
    asset = _full_preview_asset()
    runtime = {
        "surface": {
            "bundle": {
                "maps": ["normal", "ao", "curvature", "id"],
                # Empty outputs: maps are declared but not published.
                "outputs": {},
            }
        }
    }
    payload = evaluate_preview_evidence(asset, runtime)
    bake_maps = payload["previews"]["bake_maps"]

    # Every canonical map should be present in the entries with uri=None.
    by_role = {entry["role"]: entry for entry in bake_maps}
    for role in ("normal_map", "ao_map", "curvature_map", "id_map"):
        assert by_role[role]["uri"] is None, role
        assert by_role[role]["status"] == "declared", role

    skipped_reasons = {
        record["category"]: record["reason"] for record in payload["skipped_reasons"]
    }
    for role in ("normal_map", "ao_map", "curvature_map", "id_map"):
        assert skipped_reasons[role] == "bake_map_not_produced"


def test_bake_outputs_short_form_string_uri_is_tolerated() -> None:
    asset = _full_preview_asset()
    runtime = {
        "surface": {
            "bundle": {
                "maps": ["normal"],
                "bake_outputs": {"normal": "stages/surface/maps/normal.png"},
            }
        }
    }
    payload = evaluate_preview_evidence(asset, runtime)
    bake_maps = payload["previews"]["bake_maps"]
    by_role = {entry["role"]: entry for entry in bake_maps}

    assert by_role["normal_map"]["uri"] == "stages/surface/maps/normal.png"


# ---------------------------------------------------------------------------
# Comparison sheet
# ---------------------------------------------------------------------------


def test_comparison_sheet_skipped_by_default() -> None:
    payload = evaluate_preview_evidence(
        _full_preview_asset(), _runtime_with_full_bake_outputs()
    )
    skipped_reasons = {
        record["category"]: record["reason"] for record in payload["skipped_reasons"]
    }

    assert payload["preview_summary"]["comparison_sheet_present"] is False
    assert skipped_reasons["comparison_sheet"] == "comparison_sheet_not_requested"
    assert payload["previews"]["comparison_sheet"] == []


def test_comparison_sheet_renderer_unavailable_when_requested() -> None:
    asset = _full_preview_asset()
    asset["build"]["package"]["comparison_sheet"] = True
    payload = evaluate_preview_evidence(asset, _runtime_with_full_bake_outputs())
    skipped_reasons = {
        record["category"]: record["reason"] for record in payload["skipped_reasons"]
    }

    assert (
        skipped_reasons["comparison_sheet"]
        == "comparison_sheet_renderer_unavailable"
    )
    assert payload["preview_summary"]["comparison_sheet_present"] is False
    assert payload["previews"]["comparison_sheet"] == []


# ---------------------------------------------------------------------------
# Report links
# ---------------------------------------------------------------------------


def test_report_links_are_relative_paths() -> None:
    payload = evaluate_preview_evidence(
        _full_preview_asset(), _runtime_with_full_bake_outputs()
    )

    assert payload["report_links"], "report_links should be non-empty for full set"
    for link in payload["report_links"]:
        assert isinstance(link, str)
        assert not link.startswith("/"), link
        assert "://" not in link, link
        assert link.startswith(("stages/package/previews/", "stages/surface/")), link


def test_report_links_preserve_canonical_order_and_dedupe() -> None:
    payload = evaluate_preview_evidence(
        _full_preview_asset(), _runtime_with_full_bake_outputs()
    )
    links = payload["report_links"]

    # Render-preview paths come first in fixed emission order.
    assert links[0] == "stages/package/previews/turntable.png"
    assert "stages/package/previews/material_ids.png" in links
    assert "stages/package/previews/wireframe.png" in links
    # Bake URIs follow the renderable-preview links.
    expected_bake_uris = [
        "stages/surface/maps/normal.png",
        "stages/surface/maps/ao.png",
        "stages/surface/maps/curvature.png",
        "stages/surface/maps/id.png",
    ]
    for uri in expected_bake_uris:
        assert uri in links
    # No duplicates.
    assert len(links) == len(set(links))


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_evidence_is_deterministic() -> None:
    asset = _full_preview_asset()
    runtime = _runtime_with_full_bake_outputs()

    a = evaluate_preview_evidence(asset, runtime)
    b = evaluate_preview_evidence(asset, runtime)
    # Round-trip through JSON to ensure dict-equality is also
    # sortable / serialisable.
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_skipped_reasons_are_sorted_deterministically() -> None:
    asset = {
        "name": "ordering",
        "build": {
            "package": {
                "previews": ["material_ids", "uv_layout", "lod_sheet"],
                "comparison_sheet": True,
            }
        },
    }
    payload = evaluate_preview_evidence(asset, _empty_runtime())

    categories = [record["category"] for record in payload["skipped_reasons"]]
    assert categories == sorted(categories)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_no_package_config_emits_skipped_reasons() -> None:
    asset = {"name": "empty_package", "build": {"package": {}}}
    payload = evaluate_preview_evidence(asset, _empty_runtime())

    assert payload["preview_summary"]["total_preview_count"] == 0
    assert payload["preview_summary"]["final_beauty_present"] is False
    assert payload["preview_summary"]["material_ids_present"] is False
    skipped_categories = {record["category"] for record in payload["skipped_reasons"]}
    expected_renderable_skipped = {
        "final_beauty",
        "material_ids",
        "wireframe",
        "uv_layout",
        "collision",
        "lod_sheet",
    }
    assert expected_renderable_skipped <= skipped_categories
    assert "comparison_sheet" in skipped_categories


def test_missing_asset_name_falls_back_to_unnamed_asset() -> None:
    payload = evaluate_preview_evidence({}, {})
    assert payload["asset_name"] == "unnamed_asset"


def test_top_level_asset_package_shape_is_tolerated() -> None:
    """Some test fixtures stash the package config at ``asset["package"]``
    instead of ``asset["build"]["package"]``. The evaluator falls back
    when the build form is absent."""
    asset = {
        "name": "fallback",
        "package": {"previews": ["turntable"]},
    }
    payload = evaluate_preview_evidence(asset, _empty_runtime())
    assert payload["preview_summary"]["final_beauty_present"] is True


def test_non_dict_inputs_do_not_crash() -> None:
    # Defensive shape: pipeline shouldn't crash on a None runtime.
    payload = evaluate_preview_evidence({}, None)  # type: ignore[arg-type]
    assert payload["version"] == PREVIEW_EVIDENCE_VERSION


# ---------------------------------------------------------------------------
# Pipeline integration
# ---------------------------------------------------------------------------


def test_validator_pipeline_publishes_preview_evidence_to_runtime() -> None:
    asset = _full_preview_asset()
    runtime: dict[str, Any] = _runtime_with_full_bake_outputs()
    pipeline = ValidatorPipeline(
        [
            FunctionValidator(
                name="preview_evidence",
                fn=evaluate_preview_evidence,
                stage_dependencies=["surface"],
                weight=0.0,
            )
        ]
    )

    cert_bundle = pipeline.run(runtime, asset, artifacts={})

    assert "preview_evidence" in cert_bundle["validators"]
    report = cert_bundle["validators"]["preview_evidence"]
    assert report["passes"] is True
    evidence = report["evidence"]
    assert evidence["version"] == PREVIEW_EVIDENCE_VERSION
    assert evidence["asset_name"] == "industrial_crate"
    # The composition layer publishes the evidence to runtime under
    # the validator name.
    assert runtime.get("preview_evidence") == evidence


def test_validator_pipeline_keeps_passes_true_in_default_mode() -> None:
    asset = {
        "name": "missing_final",
        "build": {"package": {"previews": ["material_ids"]}},
    }
    runtime: dict[str, Any] = _empty_runtime()
    pipeline = ValidatorPipeline(
        [
            FunctionValidator(
                name="preview_evidence",
                fn=evaluate_preview_evidence,
                stage_dependencies=[],
                weight=0.0,
            )
        ]
    )

    cert_bundle = pipeline.run(runtime, asset, artifacts={})
    report = cert_bundle["validators"]["preview_evidence"]

    # Phase 9 emits warnings but never diagnostics; ``passes`` remains
    # True because the FunctionValidator reads ``diagnostics``, not
    # ``warnings``.
    assert report["passes"] is True
    assert report["evidence"]["warnings"], "warning should fire"
    assert report["diagnostics"] == []
