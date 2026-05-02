"""Machine-readable build-stage contract inventory.

The concrete stage implementations live under :mod:`lathe.core.stages`.
This module records the public input shape, output artifact, trace surface,
and failure mode for every stage in ``lathe.executor.STAGE_ORDER`` without
importing the executor or any heavy runtime adapter.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import BackendResolutionError


@dataclass(frozen=True)
class StageContract:
    """Stable public contract summary for a build stage."""

    stage: str
    inputs: tuple[str, ...]
    output_schema: tuple[str, ...]
    artifact: str
    trace_records: tuple[str, ...]
    failure_modes: tuple[str, ...]


STAGE_ORDER_CONTRACT = (
    "shape",
    "topology",
    "uv",
    "surface",
    "execution",
    "rig",
    "interfaces",
    "physics",
    "optimize",
    "validate",
    "package",
)

SUPPORTED_BACKEND_CONTRACT_VERSIONS: dict[str, frozenset[str]] = {
    "lathe.shape.intent_mesh_handoff_v1": frozenset({"2.0.0"}),
    "lathe.topology.blender_hard_surface_v1": frozenset({"1.0.0"}),
    "lathe.topology.blender_subdiv_v1": frozenset({"0.1.0"}),
    "lathe.uv.xatlas_v1": frozenset({"1.0.0"}),
    "lathe.package.openusd_gltf_v1": frozenset({"1.0.0"}),
}

STAGE_CONTRACTS: dict[str, StageContract] = {
    "shape": StageContract(
        stage="shape",
        inputs=(
            "materialized asset intent",
            "selected shape backend descriptor",
            "runtime-configured shape provider",
            "reference conditioning inputs",
        ),
        output_schema=(
            "backend_id",
            "backend_version",
            "selected_candidate_id",
            "candidates[]",
            "provider_report",
            "provenance",
        ),
        artifact="stages/shape/bundle.json",
        trace_records=("stage_bundle_refs.shape", "shape", "candidate_selection"),
        failure_modes=(
            "unsupported shape handoff contract version",
            "provider unavailable or failed under strict mode",
            "no selected candidate",
            "geometry-strict watertightness failure",
        ),
    ),
    "topology": StageContract(
        stage="topology",
        inputs=("shape bundle", "selected topology backend descriptor", "build.topology config"),
        output_schema=("backend_id", "backend_version", "mesh_uri", "mesh_stats", "adapter_report"),
        artifact="stages/topology/bundle.json",
        trace_records=("stage_bundle_refs.topology", "topology"),
        failure_modes=(
            "unsupported consumed shape contract version",
            "Blender adapter failure",
            "topology backend unavailable",
        ),
    ),
    "uv": StageContract(
        stage="uv",
        inputs=("topology bundle", "selected UV backend descriptor", "build.uv config"),
        output_schema=("backend_id", "backend_version", "mesh_uri", "uv_sets", "adapter_report"),
        artifact="stages/uv/bundle.json",
        trace_records=("stage_bundle_refs.uv", "uv"),
        failure_modes=(
            "unsupported consumed topology contract version",
            "UV backend unavailable",
            "mesh export failure",
        ),
    ),
    "surface": StageContract(
        stage="surface",
        inputs=("UV bundle", "surface programs", "material graph", "runtime surface config"),
        output_schema=("backend_id", "materials", "surface_control_pack", "surface_backend_report"),
        artifact="stages/surface/bundle.json",
        trace_records=("stage_bundle_refs.surface", "surface"),
        failure_modes=("surface backend failure", "texture request/output validation failure"),
    ),
    "execution": StageContract(
        stage="execution",
        inputs=("optimize bundle", "execution policy", "runtime execution config"),
        output_schema=("backend_id", "diagnostics", "render_eval_ir", "blend_artifact_ir"),
        artifact="stages/execution/bundle.json",
        trace_records=("stage_bundle_refs.execution", "execution"),
        failure_modes=("sandboxed subprocess failure", "expected artifact missing", "stderr deny pattern"),
    ),
    "rig": StageContract(
        stage="rig",
        inputs=("surface bundle", "topology runtime mesh", "build.rig config"),
        output_schema=("backend_id", "type", "joints"),
        artifact="stages/rig/bundle.json",
        trace_records=("stage_bundle_refs.rig",),
        failure_modes=("missing topology runtime mesh", "rig config unsupported"),
    ),
    "interfaces": StageContract(
        stage="interfaces",
        inputs=("rig bundle", "topology runtime mesh", "build.interfaces config"),
        output_schema=("backend_id", "sockets", "pivots", "anchors", "aabbs"),
        artifact="stages/interfaces/bundle.json",
        trace_records=("stage_bundle_refs.interfaces",),
        failure_modes=("invalid typed interface entry", "duplicate interface id"),
    ),
    "physics": StageContract(
        stage="physics",
        inputs=("interfaces bundle", "topology runtime mesh", "build.physics config"),
        output_schema=("backend_id", "collision", "mass_kg", "collision_uri"),
        artifact="stages/physics/bundle.json",
        trace_records=("stage_bundle_refs.physics",),
        failure_modes=("collision proxy export failure", "missing topology runtime mesh"),
    ),
    "optimize": StageContract(
        stage="optimize",
        inputs=("physics bundle", "UV runtime mesh", "build.optimize config"),
        output_schema=("backend_id", "lods", "collision", "budget_report", "diagnostics"),
        artifact="stages/optimize/bundle.json",
        trace_records=("stage_bundle_refs.optimize",),
        failure_modes=("empty runtime mesh", "LOD export failure", "budget gate diagnostic"),
    ),
    "validate": StageContract(
        stage="validate",
        inputs=("optimize bundle", "validator runtime", "validate rules", "critic score config"),
        output_schema=(
            "certified",
            "threshold",
            "score",
            "diagnostics",
            "failure_summary",
            "quality_diagnostics",
            "preview_evidence",
            "vision_critique",
        ),
        artifact="stages/validate/report.json",
        trace_records=("stage_bundle_refs.validate", "diagnostics", "repairs_applied"),
        failure_modes=("validator diagnostic", "ensure rule failure", "score below threshold"),
    ),
    "package": StageContract(
        stage="package",
        inputs=("optimize bundle", "validate report", "package formats", "engine manifest context"),
        output_schema=("backend_id", "outputs", "manifest_path", "trace_path", "selector_manifest_path"),
        artifact="stages/package/bundle.json",
        trace_records=("stage_bundle_refs.package", "package_outputs", "previews"),
        failure_modes=(
            "package artifact collision",
            "format export failure",
            "selector manifest validation error",
        ),
    ),
}


def stage_contract(stage: str) -> StageContract:
    """Return the contract inventory entry for ``stage``."""
    return STAGE_CONTRACTS[stage]


def _version_text(version: Any) -> str:
    if version in (None, ""):
        return "<missing>"
    return str(version)


def backend_contract_version_issue(backend_id: str, version: Any) -> str | None:
    """Return a clear reason when a known backend contract version is unsupported."""
    supported = SUPPORTED_BACKEND_CONTRACT_VERSIONS.get(backend_id)
    if supported is None:
        return None
    version_text = _version_text(version)
    if version_text in supported:
        return None
    supported_text = ", ".join(sorted(supported))
    return (
        f"unsupported contract version '{version_text}' for backend '{backend_id}' "
        f"(supported: {supported_text})"
    )


def supported_backend_contract_versions(backend_id: str) -> list[str]:
    """Return supported contract versions for a known stable backend ID."""
    return sorted(SUPPORTED_BACKEND_CONTRACT_VERSIONS.get(backend_id, frozenset()))


def assert_supported_backend_contract_version(
    backend_id: str,
    version: Any,
    *,
    context: str = "backend contract",
) -> None:
    """Raise when a known backend/stage contract version is not supported."""
    issue = backend_contract_version_issue(backend_id, version)
    if issue is not None:
        raise BackendResolutionError(f"{context}: {issue}")


__all__ = [
    "STAGE_CONTRACTS",
    "STAGE_ORDER_CONTRACT",
    "SUPPORTED_BACKEND_CONTRACT_VERSIONS",
    "StageContract",
    "assert_supported_backend_contract_version",
    "backend_contract_version_issue",
    "stage_contract",
    "supported_backend_contract_versions",
]
