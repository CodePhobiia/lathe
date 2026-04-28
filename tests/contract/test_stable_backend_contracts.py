"""Compatibility pins for stable backend and stack public contracts.

These tests complement the byte-level shape handoff pin by covering the
registry-level contract promised in ``docs/versioning.md`` and
``docs/architecture/contracts.md``: stable IDs must remain registered,
exported, versioned, and available through backend resolution.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from lathe.backends import (
    BACKEND_SELECTION_STAGES,
    BACKENDS,
    STACKS,
    BackendResolutionError,
    evaluate_stack,
    get_backend,
    resolve_selected_backends,
    stage_bundle_contract_version_issue,
)
from lathe.checker.cross_stage import check_backend_resolution
from lathe.core.errors import contract_version_stage_error
from lathe.shape.backend import run_shape_backend

pytestmark = pytest.mark.contract


ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = ROOT / "pyproject.toml"

STABLE_BACKEND_STAGES = {
    "lathe.shape.intent_mesh_handoff_v1": "shape",
    "lathe.topology.blender_hard_surface_v1": "topology",
    "lathe.uv.xatlas_v1": "uv",
    "lathe.package.openusd_gltf_v1": "package",
}

STABLE_STACK_IDS = {
    "lathe.stack.hard_surface_game_asset_v1",
    "lathe.stack.soft_surface_prop_v1",
}

SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:[+-][0-9A-Za-z.-]+)?$")


def _minimal_supported_asset() -> dict[str, Any]:
    return {
        "name": "contract_probe",
        "kind": "hard_surface_prop",
        "intent": {"role": "contract probe"},
        "build": {
            "shape": {"backend": "auto", "mode": "generate"},
            "topology": {"backend": "auto", "retopo": "auto"},
            "uv": {"backend": "auto", "sets": ["base"], "unwrap": "auto", "tile_mode": "zero_to_one"},
        },
        "package": {"backend": "auto", "formats": ["usd", "glb"]},
    }


def _pyproject_entry_point_names(group: str) -> set[str]:
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    return set(data["project"]["entry-points"][group])


@pytest.mark.parametrize(("backend_id", "stage"), sorted(STABLE_BACKEND_STAGES.items()))
def test_stable_backend_ids_remain_registered_and_versioned(backend_id: str, stage: str) -> None:
    assert backend_id in BACKENDS

    backend = get_backend(backend_id)
    assert backend["id"] == backend_id
    assert backend["stage"] == stage
    assert SEMVER_RE.fullmatch(backend["version"]), backend["version"]
    assert backend["determinism_class"]
    assert isinstance(backend["toolchain"], list)

    contract = backend["contract"]
    assert set(contract) == {"summary", "inputs", "outputs"}
    assert isinstance(contract["summary"], str)
    assert contract["summary"]
    assert "required" in contract["inputs"]
    assert "artifact" in contract["outputs"]
    assert "required_fields" in contract["outputs"]
    assert all(isinstance(field, str) for field in contract["outputs"]["required_fields"])
    assert contract["outputs"]["required_fields"]


def test_stable_stack_ids_remain_registered_and_bind_known_stage_backends() -> None:
    asset = _minimal_supported_asset()

    for stack_id in sorted(STABLE_STACK_IDS):
        assert stack_id in STACKS
        stack = STACKS[stack_id]
        assert set(stack["stage_backends"]) == set(BACKEND_SELECTION_STAGES)
        for stage, backend_id in stack["stage_backends"].items():
            assert backend_id in BACKENDS, f"{stack_id} binds unknown {stage} backend {backend_id}"
            assert BACKENDS[backend_id]["stage"] == stage

        ok, reasons = evaluate_stack(stack_id, asset)
        assert ok, f"{stack_id} no longer accepts the minimal public asset shape: {reasons}"


def test_pyproject_entry_points_export_stable_backend_and_stack_ids() -> None:
    backend_entry_points = _pyproject_entry_point_names("lathe.backends")
    stack_entry_points = _pyproject_entry_point_names("lathe.stacks")

    assert set(STABLE_BACKEND_STAGES).issubset(backend_entry_points)
    assert STABLE_STACK_IDS.issubset(stack_entry_points)


def test_resolved_backend_contracts_surface_versions_for_every_stage() -> None:
    resolved = resolve_selected_backends(_minimal_supported_asset())
    selected = resolved["selected"]

    assert set(selected) == set(BACKEND_SELECTION_STAGES)
    for stage in BACKEND_SELECTION_STAGES:
        backend_id = selected[stage]["id"]
        assert backend_id in BACKENDS
        assert selected[stage]["version"] == BACKENDS[backend_id]["version"]
        assert selected[stage]["contract"] == BACKENDS[backend_id]["contract"]
        assert selected[stage]["selected_via"] == "stack"


def test_resolved_contract_metadata_isolated_from_registry_mutation() -> None:
    resolved = resolve_selected_backends(_minimal_supported_asset())
    shape_contract = resolved["selected"]["shape"]["contract"]
    shape_contract["summary"] = "mutated by consumer"

    fresh = get_backend("lathe.shape.intent_mesh_handoff_v1")
    assert fresh["contract"]["summary"] != "mutated by consumer"


def test_explicit_backend_with_unsupported_contract_version_gets_clear_checker_diagnostic(
    monkeypatch,
) -> None:
    backend_id = "lathe.shape.intent_mesh_handoff_v1"
    monkeypatch.setitem(BACKENDS[backend_id], "version", "9.0.0")
    asset = _minimal_supported_asset()
    asset["build"]["shape"]["backend"] = backend_id
    checker = SimpleNamespace(diagnostics=[])

    check_backend_resolution(checker, asset)

    diagnostic = next(item for item in checker.diagnostics if item["code"] == "L4610")
    assert diagnostic["name"] == "unsupported_backend_contract_version"
    assert "unsupported contract version '9.0.0'" in diagnostic["message"]
    assert "supported: 2.0.0" in diagnostic["message"]


def test_shape_handoff_rejects_unsupported_contract_version_before_execution(tmp_path) -> None:
    with pytest.raises(BackendResolutionError) as exc:
        run_shape_backend(
            "lathe.shape.intent_mesh_handoff_v1",
            _minimal_supported_asset(),
            source_root=ROOT,
            seed=1,
            candidates_count=1,
            conditioning={},
            work_dir=tmp_path,
            backend_version="9.0.0",
        )

    message = str(exc.value)
    assert "shape handoff contract" in message
    assert "unsupported contract version '9.0.0'" in message
    assert "supported: 2.0.0" in message


def test_stage_bundle_with_unsupported_contract_version_gets_clear_error_code() -> None:
    issue = stage_bundle_contract_version_issue(
        "topology",
        {
            "backend_id": "lathe.topology.blender_hard_surface_v1",
            "backend_version": "9.0.0",
        },
    )
    assert issue is not None

    error = contract_version_stage_error(
        "contract_probe",
        "topology",
        "lathe.topology.blender_hard_surface_v1",
        issue,
        details={"backend_version": "9.0.0", "consumer_stage": "uv"},
    )

    diagnostic = error.diagnostics[0]
    assert diagnostic["code"] == "L5102"
    assert diagnostic["name"] == "unsupported_stage_contract_version"
    assert "unsupported contract version '9.0.0'" in diagnostic["message"]
    assert diagnostic["details"]["backend_version"] == "9.0.0"
