"""Unit tests for STAGE-12 gameplay tag validator."""

from __future__ import annotations

from lathe.selector_manifest import (
    GAMEPLAY_TAG_CATALOG,
    build_selector_manifest,
    write_selector_manifest,
)
from lathe.validators.composition import build_gameplay_tag_validator


def _evaluate(asset: dict) -> dict:
    validator = build_gameplay_tag_validator()
    return validator.evaluate(runtime={}, asset=asset, artifacts={})


def test_declared_tags_in_catalog_pass():
    asset = {"publish": {"tags": ["kinematic", "door"]}}
    report = _evaluate(asset)
    assert report["passes"] is True
    assert report["diagnostics"] == []
    assert sorted(report["evidence"]["valid_tags"]) == ["door", "kinematic"]


def test_unknown_tag_emits_l6410_warning_by_default():
    asset = {"publish": {"tags": ["kinematic", "bomb"]}}
    report = _evaluate(asset)
    warns = [d for d in report["diagnostics"] if d.get("severity") == "warning"]
    assert len(warns) == 1
    assert warns[0]["code"] == "L6410"
    assert "bomb" in warns[0]["message"]
    assert "kinematic" in warns[0]["details"]["allowed"]
    assert report["passes"] is True


def test_unknown_tag_escalates_to_error_under_strict_mode():
    asset = {
        "publish": {"tags": ["kinematic", "bomb"]},
        "build": {"strict_gameplay_tags": True},
    }
    report = _evaluate(asset)
    assert report["passes"] is False
    errs = [d for d in report["diagnostics"] if d.get("severity") == "error"]
    assert len(errs) == 1
    assert errs[0]["code"] == "L6410"
    assert "bomb" in errs[0]["message"]


def test_multiple_unknown_tags_produce_one_diagnostic_each():
    asset = {"publish": {"tags": ["foo", "bar", "kinematic"]}}
    report = _evaluate(asset)
    codes = {d["code"] for d in report["diagnostics"]}
    assert codes == {"L6410"}
    offenders = {d["details"]["tag"] for d in report["diagnostics"]}
    assert offenders == {"foo", "bar"}


def test_asset_without_tags_is_a_noop_pass():
    report = _evaluate({"publish": {}})
    assert report["diagnostics"] == []
    assert report["passes"] is True


def test_non_list_tags_field_is_tolerated():
    report = _evaluate({"publish": {"tags": "kinematic"}})
    # String (not list) → treated as no tags rather than crashing.
    assert report["passes"] is True
    assert report["diagnostics"] == []


def test_gameplay_tags_round_trip_through_manifest(tmp_path):
    """Declared tags in the catalog must surface under ``gameplayTags`` and
    the manifest must still pass schema validation."""
    asset = {"publish": {"tags": ["kinematic", "door", "vfx_anchor"]}}
    manifest = build_selector_manifest(
        asset_name="x",
        variant_name=None,
        source_path="examples/x.lth",
        build_hash="abcd1234" * 4,
        runtime={},
        asset=asset,
        build_dir=tmp_path / "x",
    )
    path = write_selector_manifest(manifest, tmp_path / "x")
    assert path.exists()
    assert manifest["gameplayTags"] == ["kinematic", "door", "vfx_anchor"]


def test_unknown_tag_not_surfaced_in_manifest(tmp_path):
    """Unknown tags are filtered out of the manifest (the validator emits the
    error; the manifest carries only canonical tags)."""
    asset = {"publish": {"tags": ["kinematic", "bogus_tag"]}}
    manifest = build_selector_manifest(
        asset_name="x",
        variant_name=None,
        source_path="examples/x.lth",
        build_hash="abcd1234" * 4,
        runtime={},
        asset=asset,
        build_dir=tmp_path / "x",
    )
    # Schema write must succeed even with an unknown tag present in the source.
    write_selector_manifest(manifest, tmp_path / "x")
    assert manifest.get("gameplayTags") == ["kinematic"]


def test_catalog_contains_required_game_engine_tags():
    for tag in ("kinematic", "static", "interactable", "door", "weapon"):
        assert tag in GAMEPLAY_TAG_CATALOG
