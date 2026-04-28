from __future__ import annotations

from pathlib import Path

from scripts.check_release_metadata import (
    display_version,
    expected_tag_for_version,
    normalize_version_token,
    validate_release_metadata,
)

ROOT = Path(__file__).resolve().parents[2]


def test_release_metadata_and_version_docs_are_consistent() -> None:
    assert validate_release_metadata(ROOT, expected_tag="v0.2.0-rc.1") == []


def test_release_version_normalization_accepts_pep440_and_semver_rc_forms() -> None:
    assert normalize_version_token("0.2.0rc1") == normalize_version_token("v0.2.0-rc.1")
    assert display_version("0.2.0rc1") == "0.2.0-rc.1"
    assert expected_tag_for_version("0.2.0rc1") == "v0.2.0-rc.1"
