"""Phase 13 schema tests for the experimental block.

Covers:
- A normalized asset with a populated ``experimental`` block validates
  against the schema.
- An unknown sub-block (e.g. ``construction``) fails schema validation.
- Existing assets without ``experimental`` validate as before once the
  normalizer defaults the field to ``{}``.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import jsonschema

from lathe.normalizer import normalize_asset, normalize_program


_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCHEMA_PATH = _REPO_ROOT / "schema" / "lathe.schema.json"


def _schema() -> dict[str, Any]:
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


def _minimal_program() -> dict[str, Any]:
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
        "assets": [],
        "variants": [],
    }


def _program_with_asset(experimental: dict[str, Any]) -> dict[str, Any]:
    asset_input = {
        "name": "crate",
        "kind": "hard_surface_prop",
        "experimental": experimental,
    }
    program = _minimal_program()
    program["assets"] = [normalize_asset(asset_input)]
    # Run through the program normalizer to ensure cross-field defaults.
    return normalize_program(program)


def _validate_program(program: dict[str, Any]) -> list[str]:
    schema = _schema()
    validator = jsonschema.Draft202012Validator(schema)
    return [err.message for err in validator.iter_errors(program)]


def _validate_program_strict_asset(program: dict[str, Any]) -> list[str]:
    """Strict: tighten the asset schema to forbid extra top-level keys
    so we can detect schema violations reliably (the relaxed
    ``additionalProperties: true`` on assets at the program root would
    otherwise hide violations)."""
    schema = deepcopy(_schema())
    schema["$defs"]["asset"]["additionalProperties"] = False
    validator = jsonschema.Draft202012Validator(schema)
    return [err.message for err in validator.iter_errors(program)]


def test_normalized_asset_with_experimental_validates_against_schema() -> None:
    program = _program_with_asset(
        {
            "art_direction": {
                "style_tags": ["weathered_industrial"],
                "wear": "heavy",
                "material_age": "aged",
                "detail_density": "high",
            },
            "references": {
                "use": "refs/asset_quality/industrial_crate",
                "_resolved_path": "/abs/path",
            },
            "kit": {"use": ["fasteners.hex_bolt_m6"]},
        }
    )
    errors = _validate_program(program)
    assert errors == [], errors


def test_asset_without_experimental_validates_as_empty_dict() -> None:
    program = _program_with_asset({})
    assert program["assets"][0]["experimental"] == {}
    errors = _validate_program(program)
    assert errors == [], errors


def test_unknown_subblock_fails_schema() -> None:
    """Unknown sub-blocks fail validation under the strict asset schema."""
    program = _program_with_asset({})
    program["assets"][0]["experimental"] = {"construction": {"build": "modular"}}
    errors = _validate_program_strict_asset(program)
    assert any("construction" in err or "additional" in err.lower() for err in errors), errors


def test_art_direction_with_unknown_field_fails_schema() -> None:
    program = _program_with_asset({})
    program["assets"][0]["experimental"] = {
        "art_direction": {"silhouette": "bold"}
    }
    errors = _validate_program_strict_asset(program)
    assert any("silhouette" in err or "additional" in err.lower() for err in errors), errors


def test_kit_use_must_be_list_of_strings() -> None:
    program = _program_with_asset({})
    program["assets"][0]["experimental"] = {
        "kit": {"use": "fasteners.hex_bolt_m6"}
    }
    errors = _validate_program_strict_asset(program)
    assert errors


def test_references_use_required() -> None:
    program = _program_with_asset({})
    program["assets"][0]["experimental"] = {"references": {}}
    errors = _validate_program_strict_asset(program)
    assert any("use" in err for err in errors), errors


def test_existing_industrial_crate_program_validates() -> None:
    """Back-compat: the existing example with no experimental block
    still validates after the schema change."""
    from lathe.parser import parse_file

    program = parse_file(_REPO_ROOT / "examples" / "industrial_crate.lth")
    program.pop("_source_path", None)
    normalized = normalize_program(program)
    errors = _validate_program(normalized)
    assert errors == [], errors
