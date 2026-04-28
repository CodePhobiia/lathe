from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from lathe.core.stages import package as package_stage
from lathe.errors import BuildError


def test_selector_manifest_write_failure_is_hard_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    executor = SimpleNamespace(
        asset_name="demo",
        program={"variants": []},
        cache_key="abc123",
        runtime={},
        asset={},
        out_dir=tmp_path,
    )
    monkeypatch.setattr(package_stage, "build_selector_manifest", lambda **_: {"schemaVersion": 1})

    def _fail_write(_manifest: dict, _build_dir: Path) -> Path:
        raise ValueError("schema invalid")

    monkeypatch.setattr(package_stage, "write_selector_manifest", _fail_write)

    with pytest.raises(BuildError, match=r"selector_manifest[.]json could not be written") as excinfo:
        package_stage._write_selector_manifest(executor, {"diagnostics": []})

    assert excinfo.value.diagnostics[0]["code"] == "LPKG_SELECTOR_MANIFEST_WRITE_FAILED"
