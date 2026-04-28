from __future__ import annotations

from pathlib import Path

from scripts.generate_language_schema_reference import (
    LANGUAGE_OUTPUT_PATH,
    SCHEMA_OUTPUT_PATH,
    render_language_reference,
    render_schema_reference,
)


def test_language_reference_is_generated_from_current_grammar_and_schema() -> None:
    expected = render_language_reference()
    actual = Path(LANGUAGE_OUTPUT_PATH).read_text(encoding="utf-8")

    assert actual == expected


def test_schema_reference_is_generated_from_current_schema_and_defaults() -> None:
    expected = render_schema_reference()
    actual = Path(SCHEMA_OUTPUT_PATH).read_text(encoding="utf-8")

    assert actual == expected
