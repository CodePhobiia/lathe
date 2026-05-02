"""Phase 13 parser tests for the experimental block.

Covers:
- Empty ``experimental { }`` block parses without error.
- All four MVP ``art_direction`` fields parse.
- ``references { use = "..." }`` parses.
- ``kit { use = [...] }`` parses.
- An asset without ``experimental`` parses unchanged (back-compat).
"""

from __future__ import annotations

from lathe.parser import GRAMMAR_PATH, parse_text

_BASE_ASSET = """
asset crate: hard_surface_prop {
  intent {
    role = "reinforced industrial cargo crate"
  }
"""


def _asset(experimental_body: str) -> str:
    return _BASE_ASSET + "  experimental {\n" + experimental_body + "  }\n}\n"


def _parse_asset(experimental_body: str) -> dict:
    program = parse_text(_asset(experimental_body))
    return program["assets"][0]


def test_experimental_block_parses_minimal() -> None:
    asset = _parse_asset("")
    assert asset["experimental"] == {}


def test_art_direction_subblock_parses_all_fields() -> None:
    asset = _parse_asset(
        """
    art_direction {
      style_tags = ["weathered_industrial", "well_used"]
      wear = "heavy"
      material_age = "aged"
      detail_density = "high"
    }
"""
    )
    assert asset["experimental"]["art_direction"] == {
        "style_tags": ["weathered_industrial", "well_used"],
        "wear": "heavy",
        "material_age": "aged",
        "detail_density": "high",
    }


def test_references_subblock_parses() -> None:
    asset = _parse_asset(
        """
    references {
      use = "examples/refs/asset_quality/industrial_crate"
    }
"""
    )
    assert asset["experimental"]["references"] == {
        "use": "examples/refs/asset_quality/industrial_crate"
    }


def test_kit_subblock_parses() -> None:
    asset = _parse_asset(
        """
    kit {
      use = ["fasteners.hex_bolt_m6", "rails.foot_rail_bar"]
    }
"""
    )
    assert asset["experimental"]["kit"] == {
        "use": ["fasteners.hex_bolt_m6", "rails.foot_rail_bar"]
    }


def test_asset_without_experimental_parses_unchanged() -> None:
    """Back-compat: omitting the wrapper keeps experimental as ``{}``."""
    program = parse_text(_BASE_ASSET + "}\n")
    asset = program["assets"][0]
    assert asset["experimental"] == {}


def test_all_three_subblocks_in_one_experimental_wrapper() -> None:
    asset = _parse_asset(
        """
    art_direction {
      wear = "heavy"
    }
    references {
      use = "examples/refs/asset_quality/industrial_crate"
    }
    kit {
      use = ["fasteners.hex_bolt_m6"]
    }
"""
    )
    assert "art_direction" in asset["experimental"]
    assert "references" in asset["experimental"]
    assert "kit" in asset["experimental"]


def test_unknown_subblock_is_tolerated_by_parser() -> None:
    """Unknown sub-blocks are tolerated at the parser level so the
    checker can emit an actionable L7100 diagnostic; the parser
    captures them under ``_unknown_subblocks``."""
    asset = _parse_asset(
        """
    construction {
      build = "modular"
    }
"""
    )
    assert asset["experimental"].get("_unknown_subblocks") == ["construction"]


def test_references_extra_field_reaches_checker_surface() -> None:
    asset = _parse_asset(
        """
    references {
      use = "examples/refs/asset_quality/industrial_crate"
      unexpected = "nope"
    }
"""
    )
    assert asset["experimental"]["references"]["unexpected"] == "nope"


def test_kit_extra_field_reaches_checker_surface() -> None:
    asset = _parse_asset(
        """
    kit {
      use = ["fasteners.hex_bolt_m6"]
      mode = "decorate"
    }
"""
    )
    assert asset["experimental"]["kit"]["mode"] == "decorate"


def test_formal_grammar_keeps_experimental_blocks_checker_visible() -> None:
    grammar = GRAMMAR_PATH.read_text(encoding="utf-8")

    assert 'experimental_art_direction_block: "art_direction" "{" assign_stmt* "}"' in grammar
    assert 'experimental_references_block: "references" "{" assign_stmt* "}"' in grammar
    assert 'experimental_kit_block: "kit" "{" assign_stmt* "}"' in grammar
    assert 'experimental_unknown_subblock: IDENT "{" assign_stmt* "}"' in grammar
