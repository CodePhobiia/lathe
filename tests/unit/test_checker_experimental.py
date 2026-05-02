"""Phase 13 checker tests for the experimental block.

Covers L7100-L7105 diagnostics and the clean-block passthrough.
"""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from lathe.checker import check_program

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _program(
    experimental: dict[str, Any],
    source_dir: Path | None = None,
    *,
    family: str = "industrial_crate",
) -> dict[str, Any]:
    asset = {
        "node_type": "asset",
        "name": "crate",
        "kind": "hard_surface_prop",
        "from": "",
        "family": family,
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
        "repair_policies": [],
        "fixtures": [],
        "tests": [],
        "benchmarks": [],
        "spaces": [],
        "scenes": [],
        "assets": [asset],
        "variants": [],
        "_source_path": str(
            (source_dir or (_REPO_ROOT / "examples")) / "industrial_crate.lth"
        ),
    }


def _codes(diagnostics: list[dict[str, Any]]) -> list[str]:
    return [diag["code"] for diag in diagnostics]


def test_clean_experimental_block_passes_checker() -> None:
    """A well-formed experimental block produces no diagnostics."""
    program = _program(
        {
            "art_direction": {
                "style_tags": ["weathered_industrial"],
                "wear": "heavy",
                "material_age": "aged",
                "detail_density": "high",
            },
            "references": {
                "use": "refs/asset_quality/industrial_crate",
                "_resolved_path": str(
                    _REPO_ROOT
                    / "examples"
                    / "refs"
                    / "asset_quality"
                    / "industrial_crate"
                ),
            },
            "kit": {
                "use": ["fasteners.hex_bolt_m6", "rails.foot_rail_bar"],
            },
        }
    )
    diagnostics = check_program(program)
    experimental_codes = [
        c for c in _codes(diagnostics) if c.startswith("L71")
    ]
    assert experimental_codes == [], diagnostics


def test_unknown_subblock_emits_L7100() -> None:
    program = _program({"_unknown_subblocks": ["construction"]})
    diagnostics = check_program(program)
    assert "L7100" in _codes(diagnostics)


def test_art_direction_unknown_field_emits_L7101() -> None:
    program = _program({"art_direction": {"silhouette": "bold"}})
    diagnostics = check_program(program)
    assert "L7101" in _codes(diagnostics)


def test_art_direction_invalid_value_emits_L7102_for_non_string() -> None:
    program = _program({"art_direction": {"wear": 42}})
    diagnostics = check_program(program)
    assert "L7102" in _codes(diagnostics)


def test_art_direction_invalid_value_emits_L7102_for_non_list_style_tags() -> None:
    program = _program({"art_direction": {"style_tags": "weathered"}})
    diagnostics = check_program(program)
    assert "L7102" in _codes(diagnostics)


def test_references_invalid_path_emits_L7103_for_missing_directory() -> None:
    program = _program(
        {
            "references": {
                "use": "refs/does/not/exist",
                "_resolved_path": str(_REPO_ROOT / "refs" / "does" / "not" / "exist"),
            }
        }
    )
    diagnostics = check_program(program)
    assert "L7103" in _codes(diagnostics)


def test_references_resolved_path_must_stay_inside_allowed_roots() -> None:
    with TemporaryDirectory() as outside_root:
        outside = Path(outside_root) / "outside_refs"
        outside.mkdir()
        program = _program(
            {
                "references": {
                    "use": "refs/does/not/exist",
                    "_resolved_path": str(outside),
                }
            }
        )

        diagnostics = check_program(program)

    assert "L7103" in _codes(diagnostics)


def test_references_invalid_path_emits_L7103_for_non_string_use() -> None:
    program = _program({"references": {"use": 42}})
    diagnostics = check_program(program)
    assert "L7103" in _codes(diagnostics)


def test_kit_unknown_part_emits_L7104() -> None:
    program = _program({"kit": {"use": ["fasteners.does_not_exist"]}})
    diagnostics = check_program(program)
    assert "L7104" in _codes(diagnostics)


def test_kit_invalid_format_emits_L7105_for_non_list() -> None:
    program = _program({"kit": {"use": "fasteners.hex_bolt_m6"}})
    diagnostics = check_program(program)
    assert "L7105" in _codes(diagnostics)


def test_kit_invalid_format_emits_L7105_for_missing_dot() -> None:
    program = _program({"kit": {"use": ["nopart"]}})
    diagnostics = check_program(program)
    assert "L7105" in _codes(diagnostics)


def test_kit_invalid_format_emits_L7105_for_non_string_entry() -> None:
    program = _program({"kit": {"use": [123]}})
    diagnostics = check_program(program)
    assert "L7105" in _codes(diagnostics)


def test_references_extra_field_emits_L7103() -> None:
    program = _program(
        {
            "references": {
                "use": "refs/asset_quality/industrial_crate",
                "_resolved_path": str(
                    _REPO_ROOT
                    / "examples"
                    / "refs"
                    / "asset_quality"
                    / "industrial_crate"
                ),
                "unexpected": "nope",
            }
        }
    )
    diagnostics = check_program(program)
    assert "L7103" in _codes(diagnostics)


def test_kit_extra_field_emits_L7105() -> None:
    program = _program(
        {
            "kit": {
                "use": ["fasteners.hex_bolt_m6"],
                "mode": "decorate",
            }
        }
    )
    diagnostics = check_program(program)
    assert "L7105" in _codes(diagnostics)


def test_kit_part_disallowed_for_asset_family_emits_L7106() -> None:
    program = _program(
        {"kit": {"use": ["rails.foot_rail_bar"]}},
        family="service_cabinet",
    )
    diagnostics = check_program(program)
    assert "L7106" in _codes(diagnostics)


def test_kit_family_allows_from_family_suffix_alias() -> None:
    program = _program(
        {"kit": {"use": ["fasteners.hex_bolt_m6", "rails.foot_rail_bar"]}},
        family="",
    )
    program["assets"][0]["from"] = "industrial_crate_family"

    diagnostics = check_program(program)

    assert "L7106" not in _codes(diagnostics)


def test_variant_experimental_patch_is_checked() -> None:
    program = _program({})
    program["variants"] = [
        {
            "node_type": "variant",
            "name": "crate_mobile",
            "on": "crate",
            "patches": [
                {
                    "op": "set",
                    "path": "experimental.art_direction.wear",
                    "value": 42,
                }
            ],
        }
    ]
    diagnostics = check_program(program)
    phase13 = [d for d in diagnostics if d["code"].startswith("L71")]
    assert any(d["asset"] == "crate_mobile" and d["code"] == "L7102" for d in phase13)


def test_each_diagnostic_carries_actionable_suggested_repairs() -> None:
    """Every Phase 13 diagnostic provides at least one suggested_repairs entry
    so authors and LLMs can repair from evidence alone."""
    program = _program(
        {
            "_unknown_subblocks": ["construction"],
            "art_direction": {"silhouette": "bold", "wear": 42},
            "references": {"use": "refs/missing"},
            "kit": {"use": [42, "nopart", "fasteners.unknown_part"]},
        }
    )
    diagnostics = check_program(program)
    phase13 = [d for d in diagnostics if d["code"].startswith("L71")]
    assert phase13
    for d in phase13:
        assert d["suggested_repairs"], (
            f"Diagnostic {d['code']} {d['name']} missing suggested_repairs"
        )
