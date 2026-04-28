from __future__ import annotations

from pathlib import Path

import pytest
from lathe.parser import LatheParseError, parse_file, parse_text
from lathe.parser.imports import _MAX_IMPORT_DEPTH, _MAX_SOURCE_BYTES
from lathe.parser.tokens import MAX_TOKENS


def test_parse_text_rejects_oversized_source() -> None:
    with pytest.raises(LatheParseError, match="byte parse budget"):
        parse_text(" " * (_MAX_SOURCE_BYTES + 1))


def test_parse_text_rejects_excessive_token_count() -> None:
    with pytest.raises(LatheParseError, match="token parse budget"):
        parse_text(" ".join("a" for _ in range(MAX_TOKENS + 1)))


def test_parse_file_rejects_deep_import_chain(tmp_path: Path) -> None:
    for index in range(_MAX_IMPORT_DEPTH + 2):
        next_line = f"import m{index + 1}\n" if index < _MAX_IMPORT_DEPTH + 1 else ""
        (tmp_path / f"m{index}.lth").write_text(next_line, encoding="utf-8")

    with pytest.raises(LatheParseError, match="Import depth exceeded"):
        parse_file(tmp_path / "m0.lth")
