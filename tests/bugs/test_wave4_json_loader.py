"""Wave 4 regression tests: JSON-loader hardening + typed dict access.

Covers:

- Wave 4 helper ``lathe.io_json.load_json_dict`` returns typed Lathe errors
  for missing files / bad encoding / bad JSON / non-dict top level.
- M7 ``parser.imports._parse_file_recursive`` wraps read_text failures.
- M14 ``asset_quality.certification._read_json`` covers OSError /
  UnicodeDecodeError too (previously only JSONDecodeError).
- M15 ``normalizer._normalize_rule`` / ``_normalize_assert`` raise
  ``NormalizationError`` on malformed AST nodes.
- M15 ``checker.assets.check_materialized_asset`` raises ``CheckerError`` on
  missing ``name``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from lathe.asset_quality import certification
from lathe.checker.assets import check_materialized_asset
from lathe.errors import (
    BuildError,
    CheckerError,
    LatheParseError,
    NormalizationError,
)
from lathe.io_json import load_json_dict
from lathe.normalizer import _normalize_assert, _normalize_rule

# --- io_json --------------------------------------------------------


def test_load_json_dict_missing_file_raises_build_error(tmp_path: Path) -> None:
    with pytest.raises(BuildError, match="could not read"):
        load_json_dict(tmp_path / "nope.json")


def test_load_json_dict_bad_json_raises_build_error(tmp_path: Path) -> None:
    p = tmp_path / "bad.json"
    p.write_text("{not json", encoding="utf-8")
    with pytest.raises(BuildError, match="not valid JSON"):
        load_json_dict(p)


def test_load_json_dict_non_dict_raises_build_error(tmp_path: Path) -> None:
    p = tmp_path / "list.json"
    p.write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(BuildError, match="must be an object"):
        load_json_dict(p)


def test_load_json_dict_returns_dict(tmp_path: Path) -> None:
    p = tmp_path / "ok.json"
    p.write_text('{"a": 1}', encoding="utf-8")
    assert load_json_dict(p) == {"a": 1}


# --- M7 -------------------------------------------------------------


def test_parser_wraps_read_text_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from lathe.parser import parse_file

    # Create a real file so the stat path passes, then sabotage read_text.
    p = tmp_path / "x.lth"
    p.write_text("", encoding="utf-8")

    real_read_text = Path.read_text

    def angry_read_text(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        if self == p.resolve():
            raise OSError("simulated I/O failure")
        return real_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", angry_read_text)
    with pytest.raises(LatheParseError, match="Could not read source file"):
        parse_file(p)


# --- M14 ------------------------------------------------------------


def test_certification_read_json_wraps_oserror(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="could not read"):
        certification._read_json(tmp_path / "missing.json")


# --- M15 ------------------------------------------------------------


def test_normalize_rule_raises_on_missing_kind() -> None:
    with pytest.raises(NormalizationError, match="rule node is missing"):
        _normalize_rule({"expr": {"type": "noop"}})


def test_normalize_rule_raises_on_missing_expr() -> None:
    with pytest.raises(NormalizationError, match="rule node is missing"):
        _normalize_rule({"kind": "demo"})


def test_normalize_assert_raises_on_missing_expr() -> None:
    with pytest.raises(NormalizationError, match="assert node is missing"):
        _normalize_assert({})


def test_check_materialized_asset_raises_on_missing_name() -> None:
    from types import SimpleNamespace

    checker = SimpleNamespace(diagnostics=[], program={"backends": [], "stacks": []})
    with pytest.raises(CheckerError, match="missing required 'name'"):
        check_materialized_asset(checker, {})
