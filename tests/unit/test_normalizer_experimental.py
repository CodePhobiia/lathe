"""Phase 13 normalizer tests for the experimental block."""

from __future__ import annotations

from lathe.normalizer import normalize_asset


def test_normalizer_defaults_experimental_to_empty_dict() -> None:
    """An asset that omits ``experimental`` gets ``{}`` (always present)."""
    asset = {"name": "crate", "kind": "hard_surface_prop"}
    out = normalize_asset(asset)
    assert "experimental" in out
    assert out["experimental"] == {}


def test_normalizer_does_not_inject_subblock_defaults() -> None:
    """Sub-blocks (``art_direction``/``references``/``kit``) are NOT
    defaulted — only present when the user wrote them explicitly."""
    asset = {
        "name": "crate",
        "kind": "hard_surface_prop",
        "experimental": {"art_direction": {"wear": "heavy"}},
    }
    out = normalize_asset(asset)
    assert out["experimental"] == {"art_direction": {"wear": "heavy"}}
    assert "references" not in out["experimental"]
    assert "kit" not in out["experimental"]


def test_normalizer_preserves_user_written_subblocks() -> None:
    asset = {
        "name": "crate",
        "kind": "hard_surface_prop",
        "experimental": {
            "art_direction": {
                "style_tags": ["weathered_industrial"],
                "wear": "heavy",
            },
            "references": {"use": "refs/asset_quality/industrial_crate"},
            "kit": {"use": ["fasteners.hex_bolt_m6"]},
        },
    }
    out = normalize_asset(asset)
    assert out["experimental"]["art_direction"]["wear"] == "heavy"
    assert out["experimental"]["references"]["use"] == "refs/asset_quality/industrial_crate"
    assert out["experimental"]["kit"]["use"] == ["fasteners.hex_bolt_m6"]


def test_normalizer_drops_non_dict_experimental() -> None:
    """A malformed experimental field that isn't a dict normalizes to ``{}``."""
    asset = {
        "name": "crate",
        "kind": "hard_surface_prop",
        "experimental": "invalid",
    }
    out = normalize_asset(asset)
    assert out["experimental"] == {}


def test_normalizer_forwards_unknown_subblocks_for_checker() -> None:
    """Parser-tolerated unknown sub-blocks survive normalization so the
    checker can emit ``L7100`` diagnostics."""
    asset = {
        "name": "crate",
        "kind": "hard_surface_prop",
        "experimental": {"_unknown_subblocks": ["construction"]},
    }
    out = normalize_asset(asset)
    assert out["experimental"]["_unknown_subblocks"] == ["construction"]
