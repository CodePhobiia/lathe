"""Golden text snapshots for docs-visible CLI help output."""

from __future__ import annotations

from pathlib import Path

import pytest
from scripts.generate_cli_reference import _help_for

pytestmark = pytest.mark.golden

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "cli_help"


@pytest.mark.parametrize(
    ("command_path", "fixture_name"),
    [
        ((), "lathe.txt"),
        (("cache",), "lathe_cache.txt"),
    ],
    ids=["lathe", "lathe-cache"],
)
def test_cli_help_output_snapshot(command_path: tuple[str, ...], fixture_name: str) -> None:
    expected = (FIXTURE_DIR / fixture_name).read_text(encoding="utf-8").rstrip("\n")
    assert _help_for(command_path) == expected
