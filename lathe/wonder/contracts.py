"""Schema-backed Wonder contracts.

This module is intentionally contract-only: it validates the JSON bridge
artifacts Project Wonder will hand to Lathe before the full scene compiler
exists.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import jsonschema

from lathe.errors import LatheConfigError
from lathe.security import InputClass, TrustLevel, boundary_policy, ingress_boundary

MAX_CONTRACT_BYTES = 2 * 1024 * 1024


class WonderContractError(LatheConfigError):
    """Raised when a Wonder JSON contract cannot be loaded or validated."""


@dataclass(frozen=True)
class ContractSpec:
    """A named Wonder contract and its committed schema file."""

    contract_id: str
    schema_filename: str
    schema_version: str
    description: str


CONTRACT_SPECS: dict[str, ContractSpec] = {
    "dream_brief": ContractSpec(
        contract_id="dream_brief",
        schema_filename="dream_brief.schema.json",
        schema_version="lathe.dream_brief.v1",
        description="Structured creative intent from prompt to scene planning.",
    ),
    "scene_graph": ContractSpec(
        contract_id="scene_graph",
        schema_filename="scene_graph.schema.json",
        schema_version="lathe.scene_graph.v1",
        description="Persistent multi-object scene graph with stable identities.",
    ),
    "scene_patch": ContractSpec(
        contract_id="scene_patch",
        schema_filename="scene_patch.schema.json",
        schema_version="lathe.scene_patch.v1",
        description="Continuity-aware edit request for a scene, region, object, or asset.",
    ),
    "scene_history": ContractSpec(
        contract_id="scene_history",
        schema_filename="scene_history.schema.json",
        schema_version="lathe.scene_history.v1",
        description="Forward/inverse Scene Patch records used for hash-guarded rollback.",
    ),
    "camera_lock": ContractSpec(
        contract_id="camera_lock",
        schema_filename="camera_lock.schema.json",
        schema_version="lathe.camera_lock.v1",
        description="Deterministic Scene Graph camera snapshot for before/after render comparison.",
    ),
    "render_comparison": ContractSpec(
        contract_id="render_comparison",
        schema_filename="render_comparison.schema.json",
        schema_version="lathe.render_comparison.v1",
        description="Deterministic proxy PNG before/after comparison report.",
    ),
    "llm_repair_playbook": ContractSpec(
        contract_id="llm_repair_playbook",
        schema_filename="llm_repair_playbook.schema.json",
        schema_version="lathe.llm_repair_playbook.v1",
        description="Deterministic repair instructions for LLM-facing diagnostics.",
    ),
    "render_inspection": ContractSpec(
        contract_id="render_inspection",
        schema_filename="render_inspection.schema.json",
        schema_version="lathe.render_inspection.v1",
        description="Vision or evaluator feedback for a scene render.",
    ),
    "world_memory": ContractSpec(
        contract_id="world_memory",
        schema_filename="world_memory.schema.json",
        schema_version="lathe.world_memory.v1",
        description="Durable scene facts, user decisions, hidden lore, and branch continuity.",
    ),
    "scene_manifest": ContractSpec(
        contract_id="scene_manifest",
        schema_filename="scene_manifest.schema.json",
        schema_version="lathe.scene_manifest.v1",
        description="Scene build manifest for planned and built objects, renders, exports, and package paths.",
    ),
    "scene_build_report": ContractSpec(
        contract_id="scene_build_report",
        schema_filename="scene_build_report.schema.json",
        schema_version="lathe.scene_build_report.v1",
        description="Auditable scene build report with asset cache reuse, artifact paths, and provider/fallback trace.",
    ),
    "wonder_report": ContractSpec(
        contract_id="wonder_report",
        schema_filename="wonder_report.schema.json",
        schema_version="lathe.wonder_report.v1",
        description="Human-facing and machine-readable Wonder scene quality, artifact, and readiness summary.",
    ),
    "scene_package_manifest": ContractSpec(
        contract_id="scene_package_manifest",
        schema_filename="scene_package_manifest.schema.json",
        schema_version="lathe.scene_package_manifest.v1",
        description="Folder-based scene package manifest for source, graph, build, render, export, and report paths.",
    ),
    "scene_plan": ContractSpec(
        contract_id="scene_plan",
        schema_filename="scene_plan.schema.json",
        schema_version="lathe.scene_plan.v1",
        description="Deterministic multi-asset scene plan for build, assembly, render, export, and cache work.",
    ),
    "scene_materialization_manifest": ContractSpec(
        contract_id="scene_materialization_manifest",
        schema_filename="scene_materialization_manifest.schema.json",
        schema_version="lathe.scene_materialization_manifest.v1",
        description="Deterministic Scene Graph to generated Lathe asset source manifest.",
    ),
    "scene_assembly": ContractSpec(
        contract_id="scene_assembly",
        schema_filename="scene_assembly.schema.json",
        schema_version="lathe.scene_assembly.v1",
        description="Deterministic scene assembly IR with identity, transform, material, camera, and selection metadata.",
    ),
    "scene_branch": ContractSpec(
        contract_id="scene_branch",
        schema_filename="scene_branch.schema.json",
        schema_version="lathe.scene_branch.v1",
        description="Scene version graph and branch metadata for continuity-preserving exploration.",
    ),
    "scene_diff": ContractSpec(
        contract_id="scene_diff",
        schema_filename="scene_diff.schema.json",
        schema_version="lathe.scene_diff.v1",
        description="Deterministic Scene Graph diff for object, material, state, transform, and metadata changes.",
    ),
    "scene_quality_report": ContractSpec(
        contract_id="scene_quality_report",
        schema_filename="scene_quality_report.schema.json",
        schema_version="lathe.scene_quality_report.v1",
        description="Machine-readable scene validator scores, diagnostics, and summary status.",
    ),
    "scene_repair_report": ContractSpec(
        contract_id="scene_repair_report",
        schema_filename="scene_repair_report.schema.json",
        schema_version="lathe.scene_repair_report.v1",
        description="Render inspection repair proposals, rounds, diagnostics, and offline repair loop status.",
    ),
    "scene_benchmark_report": ContractSpec(
        contract_id="scene_benchmark_report",
        schema_filename="scene_benchmark_report.schema.json",
        schema_version="lathe.scene_benchmark_report.v1",
        description="Wonder loop performance, quality, cache reuse, and readiness benchmark results.",
    ),
    "style_pack": ContractSpec(
        contract_id="style_pack",
        schema_filename="style_pack.schema.json",
        schema_version="lathe.style_pack.v1",
        description="Reusable palette, material, form, lighting, and instance-reuse style contract.",
    ),
    "layout_plan": ContractSpec(
        contract_id="layout_plan",
        schema_filename="layout_plan.schema.json",
        schema_version="lathe.layout_plan.v1",
        description=(
            "Deterministic room layout, placements, path plan, intersections, "
            "modular wall segments, and instance reuse groups."
        ),
    ),
    "game_readiness": ContractSpec(
        contract_id="game_readiness",
        schema_filename="game_readiness.schema.json",
        schema_version="lathe.game_readiness.v1",
        description="Scene object gameplay, collision, pivot, snap, socket, physics, and mobile readiness metadata.",
    ),
    "asset_provenance_scene": ContractSpec(
        contract_id="asset_provenance_scene",
        schema_filename="asset_provenance_scene.schema.json",
        schema_version="lathe.asset_provenance_scene.v1",
        description="Scene object provenance, content-safety hooks, rights metadata, and export permissions.",
    ),
    "roblox_profile": ContractSpec(
        contract_id="roblox_profile",
        schema_filename="roblox_profile.schema.json",
        schema_version="lathe.roblox_profile.v1",
        description="Roblox low-poly profile constraints for scene and asset-kit validation.",
    ),
    "roblox_manifest": ContractSpec(
        contract_id="roblox_manifest",
        schema_filename="roblox_manifest.schema.json",
        schema_version="lathe.roblox_manifest.v1",
        description="Roblox export-lane manifest with budgets, object metadata, diagnostics, and mobile score.",
    ),
    "roblox_export_bundle": ContractSpec(
        contract_id="roblox_export_bundle",
        schema_filename="roblox_export_bundle.schema.json",
        schema_version="lathe.roblox_export_bundle.v1",
        description="Roblox asset-kit export bundle report with GLB, thumbnail, manifest, and handoff artifacts.",
    ),
    "roblox_fbx_handoff": ContractSpec(
        contract_id="roblox_fbx_handoff",
        schema_filename="roblox_fbx_handoff.schema.json",
        schema_version="lathe.roblox_fbx_handoff.v1",
        description="Explicit downstream FBX conversion handoff for Roblox asset-kit bundles.",
    ),
}

_WONDER_CONTRACT_BOUNDARY = boundary_policy(
    name="wonder_contract_file",
    input_class=InputClass.WONDER_CONTRACT,
    trust_level=TrustLevel.UNTRUSTED,
    controls=(
        "byte_cap",
        "utf8_decode",
        "json_parse",
        "object_root_required",
        "json_schema_validation",
    ),
)


def _schema_root() -> Path:
    here = Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        candidate = parent / "schema"
        if candidate.exists():
            return candidate
    raise FileNotFoundError("Could not locate schema directory")


def _contract_spec(contract_id: str) -> ContractSpec:
    try:
        return CONTRACT_SPECS[contract_id]
    except KeyError as exc:
        supported = ", ".join(sorted(CONTRACT_SPECS))
        raise WonderContractError(f"unknown Wonder contract {contract_id!r}; supported: {supported}") from exc


def contract_schema_path(contract_id: str) -> Path:
    """Return the committed schema path for a Wonder contract."""
    spec = _contract_spec(contract_id)
    return _schema_root() / spec.schema_filename


@lru_cache(maxsize=len(CONTRACT_SPECS))
def get_contract_schema(contract_id: str) -> dict[str, Any]:
    """Load a Wonder contract schema by id."""
    path = contract_schema_path(contract_id)
    try:
        # JSON ingress: internal canonical schema shipped inside this repo. This payload is the validator input.
        schema = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WonderContractError(f"Wonder schema at {path} could not be loaded: {exc}") from exc
    return schema


def list_contract_summaries() -> list[dict[str, str]]:
    """Return CLI-friendly metadata for supported Wonder contracts."""
    summaries: list[dict[str, str]] = []
    for contract_id in sorted(CONTRACT_SPECS):
        spec = CONTRACT_SPECS[contract_id]
        schema = get_contract_schema(contract_id)
        summaries.append(
            {
                "id": spec.contract_id,
                "schema_version": spec.schema_version,
                "schema_id": str(schema.get("$id", "")),
                "schema_path": f"schema/{spec.schema_filename}",
                "description": spec.description,
            }
        )
    return summaries


def wonder_capabilities() -> dict[str, Any]:
    """Return machine-readable local Wonder-readiness capability flags."""
    contracts = list_contract_summaries()
    return {
        "schema_version": "lathe.wonder_capabilities.v1",
        "status": "milestone_a_local",
        "capabilities": {
            "json_first_authoring": True,
            "dream_brief_schema": "dream_brief" in CONTRACT_SPECS,
            "scene_graph_schema": "scene_graph" in CONTRACT_SPECS,
            "scene_patch_schema": "scene_patch" in CONTRACT_SPECS,
            "render_inspection_schema": "render_inspection" in CONTRACT_SPECS,
            "world_memory_schema": "world_memory" in CONTRACT_SPECS,
            "scene_manifest_schema": "scene_manifest" in CONTRACT_SPECS,
            "scene_build_report_schema": "scene_build_report" in CONTRACT_SPECS,
            "wonder_report_schema": "wonder_report" in CONTRACT_SPECS,
            "contract_validation_cli": True,
            "scene_graph_semantic_check_cli": True,
            "dream_brief_decomposition_cli": True,
            "brief_scene_consistency_cli": True,
            "deterministic_brief_to_scene_graph_lowering": True,
            "deterministic_scene_planning": True,
            "scene_asset_materialization": "scene_materialization_manifest" in CONTRACT_SPECS,
            "scene_materialization_manifest_schema": "scene_materialization_manifest" in CONTRACT_SPECS,
            "scene_quality_report_schema": "scene_quality_report" in CONTRACT_SPECS,
            "scene_assembly_ir": "scene_assembly" in CONTRACT_SPECS,
            "scene_branching_helpers": "scene_branch" in CONTRACT_SPECS and "scene_diff" in CONTRACT_SPECS,
            "scene_repair_loop": "scene_repair_report" in CONTRACT_SPECS,
            "curiosity_expansion": True,
            "scene_benchmark_report_schema": "scene_benchmark_report" in CONTRACT_SPECS,
            "style_pack_schema": "style_pack" in CONTRACT_SPECS,
            "layout_plan_schema": "layout_plan" in CONTRACT_SPECS,
            "game_readiness_schema": "game_readiness" in CONTRACT_SPECS,
            "asset_provenance_scene_schema": "asset_provenance_scene" in CONTRACT_SPECS,
            "optional_runtime_dependency_free_contract_cli": True,
            "scene_source_bridge": True,
            "scene_source_language": True,
            "scene_patch_application": True,
            "scene_patch_history": "scene_history" in CONTRACT_SPECS,
            "scene_patch_rollback": "scene_history" in CONTRACT_SPECS,
            "camera_lock_schema": "camera_lock" in CONTRACT_SPECS,
            "render_comparison_schema": "render_comparison" in CONTRACT_SPECS,
            "proxy_before_after_comparison": True,
            "llm_repair_playbook_schema": "llm_repair_playbook" in CONTRACT_SPECS,
            "llm_scene_plan_generation": True,
            "llm_repair_playbook": True,
            "offline_scene_build_pipeline": True,
            "scene_build_pipeline": True,
            "scene_render_pipeline": True,
            "scene_export_pipeline": True,
            "blender_scene_render_pipeline": False,
            "blender_scene_export_pipeline": True,
            "scene_package_format": True,
            "world_memory": True,
            "roblox_profile": "roblox_profile" in CONTRACT_SPECS,
            "roblox_manifest": "roblox_manifest" in CONTRACT_SPECS,
            "roblox_export_bundle_schema": "roblox_export_bundle" in CONTRACT_SPECS,
            "roblox_fbx_handoff_schema": "roblox_fbx_handoff" in CONTRACT_SPECS,
            "roblox_asset_kit_export": True,
        },
        "contracts": contracts,
        "notes": [
            "Local Milestone A contract commands and the Phase 4 folder-based package manifest are available.",
            "World Memory has schema and standalone validation helpers.",
            "Scene Plan is available as a deterministic helper over existing Scene Graph JSON.",
            "Scene Materialization can lower planned object groups into generated, checkable Lathe asset sources.",
            "Scene Patch application, JSON-first scene source bridge, and offline Scene Package builds are available.",
            "Deterministic camera locks and proxy PNG before/after comparison reports are available.",
            "LLM authoring helpers can generate deterministic Scene Plans and repair playbooks without provider calls.",
            "Roblox profile, manifest, and local asset-kit export are contract lanes; Roblox Studio import and .rbxmx writing are deferred.",
            "Deterministic proxy scene render, GLB/USD export artifacts, and sandboxed Blender scene export are available; Blender-backed scene rendering remains deferred.",
        ],
    }


def wonder_status() -> dict[str, Any]:
    """Return machine-readable Wonder readiness status without running checks."""
    capabilities = wonder_capabilities()
    capability_flags = capabilities["capabilities"]
    blocked_capabilities = sorted(name for name, enabled in capability_flags.items() if enabled is False)
    local_green_capabilities = sorted(name for name, enabled in capability_flags.items() if enabled is True)
    open_evidence_gaps = [
        "fresh_clone_or_ci_alpha_confirmation",
        "posix_lathe_wonder_validate_sh",
        "posix_demo_wonder_seed_scene_sh",
        "blender_backed_scene_render",
        "external_glb_usd_blender_export_validation",
        "roblox_studio_import_execution",
        "vision_model_render_inspection_loop",
    ]
    alpha_gate_blockers = [
        {
            "id": "fresh_clone_or_ci_alpha_confirmation_missing",
            "severity": "blocker",
            "message": "Review-snapshot evidence exists, but alpha promotion still needs a fresh clone or CI confirmation.",
        },
        {
            "id": "posix_evidence_missing",
            "severity": "blocker",
            "message": "Bash helper and seed demo still need POSIX runtime evidence.",
        },
        {
            "id": "final_renderer_export_missing",
            "severity": "blocker",
            "message": "Blender-backed scene renders and external GLB/USD/Blender viewer validation remain deferred.",
        },
        {
            "id": "roblox_studio_import_execution_missing",
            "severity": "blocker",
            "message": "Roblox local asset-kit export exists, but Roblox Studio import, upload, or .rbxmx execution is not proven.",
        },
    ]
    return {
        "schema_version": "lathe.wonder_status.v1",
        "ok": True,
        "readiness": {
            "score": 4,
            "max_score": 10,
            "label": "core_proxy_alpha_gate_passed_full_runtime_blocked",
            "current_milestone": (
                "Deterministic core/proxy alpha gate is locally decision-ready; full Wonder "
                "runtime/export readiness remains blocked by external evidence."
            ),
            "alpha_gate_ready": False,
            "core_proxy_alpha_gate_ready": True,
            "full_wonder_runtime_ready": False,
            "alpha_gate_scope": "core_proxy_contract_gate",
            "full_readiness_blockers": [
                "fresh_clone_or_hosted_ci_confirmation",
                "posix_helper_evidence",
                "blender_backed_scene_render",
                "roblox_studio_import_execution",
                "external_viewer_validation",
            ],
            "task_boxes_truthful": True,
            "task_boxes_truthful_reason": (
                "wonder-tasks.md checked boxes are backed by local review-snapshot evidence in "
                "docs/wonder-readiness/evidence.md; unchecked runtime/export tasks still gate full readiness."
            ),
        },
        "evidence": {
            "state": "review_snapshot_evidence_recorded_posix_and_alpha_gates_pending",
            "ledger": "docs/wonder-readiness/evidence.md",
            "status_doc": "docs/wonder-readiness/status.md",
            "task_ledger": "wonder-tasks.md",
            "validated_local_helpers": [
                "scripts/lathe_wonder_validate.ps1",
                "scripts/demo_wonder_seed_scene.ps1",
            ],
            "pending_posix_helpers": [
                "scripts/lathe_wonder_validate.sh",
                "scripts/demo_wonder_seed_scene.sh",
            ],
            "open_gaps": open_evidence_gaps,
        },
        "capability_summary": {
            "true": len(local_green_capabilities),
            "false": len(blocked_capabilities),
            "blocked_capabilities": blocked_capabilities,
        },
        "alpha_gate_blockers": alpha_gate_blockers,
        "core_alpha_gate": {
            "status": "passed_locally",
            "decision_ready": True,
            "command": "python -m lathe.cli wonder alpha-gate examples/wonder/alchemist_observatory --out <dir>",
            "scope": "deterministic core/proxy contract gate; optional runtime lanes are nonblocking",
        },
        "next_recommended_actions": [
            "Keep full alpha readiness blocked until clean checkout or hosted CI evidence agrees with local core gate evidence.",
            "Run scripts/lathe_wonder_validate.sh and scripts/demo_wonder_seed_scene.sh in a POSIX-capable environment if POSIX proof remains in scope.",
            "Implement Blender-backed reveal/topdown render execution and external export/viewer validation if final runtime proof remains in scope.",
            "Prove Roblox Studio import/upload or .rbxmx execution beyond the local asset-kit bundle if Roblox proof remains in scope.",
        ],
        "capabilities": capability_flags,
        "contracts": capabilities["contracts"],
        "notes": capabilities["notes"],
    }


def _format_pointer(path_parts: Any) -> str:
    parts = [str(part) for part in path_parts]
    return "/" + "/".join(parts) if parts else "/"


def validate_contract(contract_id: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Return JSON-schema diagnostics for a Wonder payload."""
    spec = _contract_spec(contract_id)
    schema = get_contract_schema(contract_id)
    validator = jsonschema.Draft202012Validator(schema)
    diagnostics: list[dict[str, Any]] = []
    schema_version = payload.get("schema_version")
    if isinstance(schema_version, str) and schema_version != spec.schema_version:
        diagnostics.append(
            {
                "code": "WONDER_UNSUPPORTED_SCHEMA_VERSION",
                "severity": "error",
                "contract": contract_id,
                "path": "/schema_version",
                "message": (
                    f"Unsupported schema_version {schema_version!r} for {contract_id}; "
                    f"supported version is {spec.schema_version!r}."
                ),
            }
        )
    for error in sorted(validator.iter_errors(payload), key=lambda item: list(item.absolute_path)):
        diagnostics.append(
            {
                "code": "WONDER_SCHEMA_VALIDATION",
                "severity": "error",
                "contract": contract_id,
                "path": _format_pointer(error.absolute_path),
                "message": error.message,
            }
        )
    return diagnostics


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        stat_result = path.stat()
    except FileNotFoundError as exc:
        raise WonderContractError(f"Wonder contract file not found: {path}") from exc
    except OSError as exc:
        raise WonderContractError(f"Wonder contract file could not be stat'd ({path}): {exc}") from exc
    if stat_result.st_size > MAX_CONTRACT_BYTES:
        raise WonderContractError(
            f"Wonder contract file exceeds 2 MiB ({stat_result.st_size} bytes > {MAX_CONTRACT_BYTES}): {path}"
        )
    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        raise WonderContractError(f"Wonder contract file is not valid UTF-8 ({path}): {exc}") from exc
    try:
        # JSON ingress: user-supplied Wonder contract file; validated by load_and_validate_contract.
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise WonderContractError(
            f"Wonder contract file contains invalid JSON ({path}): {exc.msg} at line {exc.lineno}, column {exc.colno}"
        ) from exc
    if not isinstance(raw, dict):
        raise WonderContractError(f"Wonder contract root must be a JSON object, got {type(raw).__name__} ({path})")
    return raw


@ingress_boundary(_WONDER_CONTRACT_BOUNDARY)
def load_and_validate_contract(contract_id: str, path: str | Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Load a user-supplied Wonder JSON contract and return schema diagnostics."""
    payload = _read_json_object(Path(path))
    return payload, validate_contract(contract_id, payload)
