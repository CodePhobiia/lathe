from __future__ import annotations

from pathlib import Path

from scripts.generate_cli_reference import OUTPUT_PATH, render_cli_reference


def test_cli_reference_is_generated_from_current_help_output() -> None:
    expected = render_cli_reference()
    actual = Path(OUTPUT_PATH).read_text(encoding="utf-8")

    assert actual == expected
