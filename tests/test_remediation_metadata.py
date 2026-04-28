from __future__ import annotations

import importlib.metadata
from pathlib import Path
from unittest.mock import patch

import lathe
from lathe.backends import get_backend, resolve_selected_backends
from lathe.core.stages import package as package_stage
from lathe.executor import BuildExecutor
from lathe.parser import parse_file
from lathe.resolver import materialize_asset

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "courier_drone.lth"


def _deterministic_reports(*, xatlas_version: str, probe_path: str) -> list[dict[str, object]]:
    return [
        {
            "backend_id": "lathe.package.openusd_gltf_v1",
            "requested_adapter": "builtin",
            "selected_adapter": "reference_package",
            "strict": False,
            "available": True,
            "real_adapter_available": True,
            "fallback_available": False,
            "probe": {"available": True, "code": "ok"},
        },
        {
            "backend_id": "lathe.topology.blender_hard_surface_v1",
            "requested_adapter": "auto",
            "selected_adapter": "reference_cleanup",
            "strict": False,
            "available": True,
            "real_adapter_available": False,
            "fallback_available": True,
            "probe": {
                "available": False,
                "code": "not_found",
                "path": probe_path,
                "message": "host-specific path should not affect cache key",
            },
        },
        {
            "backend_id": "lathe.uv.xatlas_v1",
            "requested_adapter": "auto",
            "selected_adapter": "xatlas",
            "strict": False,
            "available": True,
            "real_adapter_available": True,
            "fallback_available": True,
            "probe": {
                "available": True,
                "code": "ok",
                "version": xatlas_version,
                "path": probe_path,
            },
        },
    ]


def _cache_key(tmp_path: Path, reports: list[dict[str, object]]) -> str:
    program = parse_file(EXAMPLE)
    with patch("lathe.executor.deterministic_backend_reports", return_value=reports):
        return BuildExecutor(program, "courier_drone", tmp_path / "out").cache_key


def test_cache_key_changes_when_tool_capability_version_changes(tmp_path: Path) -> None:
    first = _cache_key(
        tmp_path,
        _deterministic_reports(xatlas_version="0.0.11", probe_path="C:/tool/a"),
    )
    second = _cache_key(
        tmp_path,
        _deterministic_reports(xatlas_version="0.0.12", probe_path="C:/tool/a"),
    )

    assert first != second


def test_cache_key_ignores_host_specific_probe_paths(tmp_path: Path) -> None:
    first = _cache_key(
        tmp_path,
        _deterministic_reports(xatlas_version="0.0.11", probe_path="C:/tool/a"),
    )
    second = _cache_key(
        tmp_path,
        _deterministic_reports(xatlas_version="0.0.11", probe_path="D:/different/tool"),
    )

    assert first == second


def test_xatlas_backend_metadata_advertises_xatlas_runtime() -> None:
    backend = get_backend("lathe.uv.xatlas_v1")

    assert backend["runtime_executor"] == "lathe.runtime.uv.xatlas_v1"
    assert "xatlas" in backend["toolchain"]
    assert "reference_runtime" not in backend["toolchain"]


def test_resolved_xatlas_backend_metadata_advertises_xatlas_runtime() -> None:
    program = parse_file(EXAMPLE)
    asset = materialize_asset(program, "courier_drone")
    resolved = resolve_selected_backends(asset)

    assert resolved["selected"]["uv"]["runtime_executor"] == "lathe.runtime.uv.xatlas_v1"


def test_compiler_version_uses_package_metadata(monkeypatch) -> None:
    monkeypatch.setattr(package_stage.importlib.metadata, "version", lambda name: "0.2.0rc1")

    assert package_stage._compiler_version() == "0.2.0rc1"


def test_compiler_version_falls_back_to_imported_version(monkeypatch) -> None:
    def _raise_package_not_found(name: str) -> str:
        raise importlib.metadata.PackageNotFoundError(name)

    monkeypatch.setattr(package_stage.importlib.metadata, "version", _raise_package_not_found)

    assert package_stage._compiler_version() != "unknown"


def test_compiler_version_prefers_source_version_over_stale_editable_metadata(monkeypatch) -> None:
    monkeypatch.setattr(package_stage.importlib.metadata, "version", lambda name: "0.1.0")

    assert package_stage._compiler_version() == lathe.__version__
