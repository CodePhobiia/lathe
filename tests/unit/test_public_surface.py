from __future__ import annotations

import lathe
import lathe.parser


def test_top_level_public_surface_is_stable_and_minimal() -> None:
    assert lathe.__all__ == [
        "build_asset",
        "build_plan",
        "check_program",
        "get_schema",
        "list_backends",
        "list_stacks",
        "materialize_asset",
        "normalize_asset",
        "normalize_program",
        "parse_file",
        "parse_text",
    ]


def test_parser_facade_does_not_expose_private_implementation_helpers() -> None:
    private_helpers = {
        "_FastParser",
        "_LatheTransformer",
        "_TokenStream",
        "_merge_programs",
        "_parse_file_recursive",
        "_resolve_import_path",
    }

    assert private_helpers.isdisjoint(vars(lathe.parser))
    assert private_helpers.isdisjoint(lathe.parser.__all__)
