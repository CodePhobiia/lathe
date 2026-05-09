"""Phase 13 resolver tests for the experimental block.

Covers:
- ``experimental.references.use`` resolves relative to the source ``.lth``.
- The resolved path lands as ``experimental.references._resolved_path``.
- ``experimental.kit.use`` passes through unchanged.
- Existing assets without ``experimental`` materialize without the sub-keys.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from lathe.resolver import materialize_asset

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _program(experimental: dict[str, Any]) -> dict[str, Any]:
    """Build a minimal program with one asset carrying ``experimental``."""
    asset = {
        "node_type": "asset",
        "name": "crate",
        "kind": "hard_surface_prop",
        "from": "",
        "uses": [],
        "refs": {},
        "intent": {"role": "cargo"},
        "geometry": {},
        "features": {},
        "surface": {},
        "assembly": {},
        "fit": {},
        "transfer": {},
        "reuse": {},
        "constraints": {},
        "ingest": {},
        "assembly_rules": {},
        "execution": {},
        "space": {},
        "repair_policy": {},
        "build": {},
        "validate": {},
        "package": {},
        "publish": {},
        "experimental": experimental,
    }
    return {
        "module": None,
        "imports": [],
        "profiles": [],
        "contracts": [],
        "critics": [],
        "libraries": [],
        "kits": [],
        "patterns": [],
        "families": [],
        "components": [],
        "assemblies": [],
        "traits": [],
        "mechanisms": [],
        "materials": [],
        "surface_programs": [],
        "surface_backends": [],
        "surface_policies": [],
        "decal_libraries": [],
        "mask_programs": [],
        "trim_sheets": [],
        "palettes": [],
        "style_packs": [],
        "reference_sets": [],
        "reconstruct_policies": [],
        "adapt_policies": [],
        "assembly_policies": [],
        "fit_profiles": [],
        "transfer_rules": [],
        "execution_profiles": [],
        "render_fixtures": [],
        "bake_profiles": [],
        "library_bindings": [],
        "material_graphs": [],
        "inspection_policies": [],
        "asset_class_profiles": [],
        "repair_policies": [],
        "fixtures": [],
        "tests": [],
        "benchmarks": [],
        "spaces": [],
        "scenes": [],
        "assets": [asset],
        "variants": [],
        "_source_path": str(_REPO_ROOT / "examples" / "industrial_crate.lth"),
    }


def test_references_use_resolves_relative_to_source() -> None:
    program = _program(
        {"references": {"use": "refs/asset_quality/industrial_crate"}}
    )
    asset = materialize_asset(program, "crate")
    resolved = asset["experimental"]["references"]["_resolved_path"]
    assert isinstance(resolved, str) and resolved
    assert Path(resolved).resolve() == (
        _REPO_ROOT / "examples" / "refs" / "asset_quality" / "industrial_crate"
    ).resolve()


def test_references_use_resolves_to_existing_directory() -> None:
    program = _program(
        {"references": {"use": "refs/asset_quality/industrial_crate"}}
    )
    asset = materialize_asset(program, "crate")
    resolved_path = Path(asset["experimental"]["references"]["_resolved_path"])
    assert resolved_path.exists()
    assert resolved_path.is_dir()


def test_references_use_rejects_path_escape(tmp_path: Path) -> None:
    outside = tmp_path / "outside_refs"
    outside.mkdir()
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    program = _program({"references": {"use": "../outside_refs"}})
    program["_source_path"] = str(source_dir / "asset.lth")

    asset = materialize_asset(program, "crate")

    assert asset["experimental"]["references"].get("_resolved_path", "") == ""


def test_references_use_can_resolve_repo_root_relative_path() -> None:
    program = _program(
        {"references": {"use": "examples/refs/asset_quality/industrial_crate"}}
    )
    asset = materialize_asset(program, "crate")
    resolved = asset["experimental"]["references"]["_resolved_path"]
    assert Path(resolved).resolve() == (
        _REPO_ROOT / "examples" / "refs" / "asset_quality" / "industrial_crate"
    ).resolve()


def test_kit_use_passes_through_unchanged() -> None:
    program = _program(
        {"kit": {"use": ["fasteners.hex_bolt_m6", "rails.foot_rail_bar"]}}
    )
    asset = materialize_asset(program, "crate")
    assert asset["experimental"]["kit"]["use"] == [
        "fasteners.hex_bolt_m6",
        "rails.foot_rail_bar",
    ]


def test_art_direction_passes_through_unchanged() -> None:
    program = _program(
        {
            "art_direction": {
                "style_tags": ["weathered_industrial"],
                "wear": "heavy",
            }
        }
    )
    asset = materialize_asset(program, "crate")
    assert asset["experimental"]["art_direction"] == {
        "style_tags": ["weathered_industrial"],
        "wear": "heavy",
    }


def test_no_experimental_block_remains_empty() -> None:
    program = _program({})
    asset = materialize_asset(program, "crate")
    assert asset["experimental"] == {}
