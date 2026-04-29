"""Render inspection validation and deterministic scene repair helpers."""

from __future__ import annotations

import copy
import json
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from lathe.wonder import validate_contract

from .ids import clamp_id_body, digest_text, is_scene_entity_id, snake_id
from .patch import apply_scene_patch

SCENE_REPAIR_REPORT_VERSION = "lathe.scene_repair_report.v1"
SCENE_REPAIR_REPORT_SCHEMA_FILENAME = "scene_repair_report.schema.json"
SCENE_REPAIR_REPORT_CONTRACT = "scene_repair_report"
RENDER_INSPECTION_CONTRACT = "render_inspection"
RENDER_INSPECTION_PHASE = "render_inspection_semantics"
SCENE_REPAIR_PHASE = "scene_repair_loop"

RepairGoal = Literal["wonder_preview", "export_ready", "roblox_ready"]

REPAIR_GOALS: tuple[RepairGoal, ...] = ("wonder_preview", "export_ready", "roblox_ready")

_TARGET_COLLECTIONS: dict[str, tuple[str, str]] = {
    "object": ("objects", "object_id"),
    "region": ("regions", "region_id"),
    "camera": ("cameras", "camera_id"),
    "light": ("lights", "light_id"),
    "curiosity_anchor": ("curiosity_anchors", "anchor_id"),
    "hidden_state": ("hidden_state", "hidden_id"),
}

_ENTITY_COLLECTIONS: dict[str, str] = {
    "regions": "region_id",
    "objects": "object_id",
    "lights": "light_id",
    "cameras": "camera_id",
    "curiosity_anchors": "anchor_id",
    "hidden_state": "hidden_id",
    "materials": "material_id",
    "relationships": "relationship_id",
}

_ASSET_FIELDS = ("lathe_asset", "source_family", "source_kit", "variant")
_FULL_PATCH_FIELDS = {
    "schema_version",
    "patch_id",
    "scope",
    "target_id",
    "instruction",
    "preserve",
    "allowed_changes",
    "operations",
    "continuity",
    "acceptance",
}
_PROBLEM_TARGET_PREFIXES = ("object", "region", "camera", "light", "curiosity", "hidden")
_PATCH_SCENE_REF_PREFIXES = ("object", "region", "camera", "light", "curiosity", "hidden")

_GOAL_ACCEPTANCE: dict[RepairGoal, dict[str, Any]] = {
    "wonder_preview": {
        "validators": ["style", "semantic", "composition", "continuity"],
        "minimum_score": 0.75,
    },
    "export_ready": {
        "validators": ["semantic", "continuity", "export"],
        "minimum_score": 0.85,
    },
    "roblox_ready": {
        "validators": ["semantic", "continuity", "platform"],
        "minimum_score": 0.8,
    },
}

_WONDER_PREVIEW_ALLOWED: dict[str, list[str]] = {
    "asset": ["assets", "materials", "style", "metadata"],
    "object": ["materials", "style", "lighting", "metadata"],
    "region": ["layout", "style", "lighting", "metadata"],
    "scene": ["layout", "style", "lighting", "metadata"],
    "camera": ["cameras", "metadata"],
    "light": ["lighting", "metadata"],
    "curiosity_anchor": ["curiosity_anchors", "metadata"],
    "hidden_state": ["hidden_state", "metadata"],
}


@dataclass(frozen=True)
class SceneRepairProposalResult:
    """Scene Patch proposals plus the repair report describing them."""

    proposals: list[dict[str, Any]]
    report: dict[str, Any]


@dataclass(frozen=True)
class SceneRepairLoopResult:
    """Updated Scene Graph plus the report emitted by the offline repair loop."""

    scene_graph: dict[str, Any]
    report: dict[str, Any]
    proposals: list[dict[str, Any]]


def _schema_root() -> Path:
    here = Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        candidate = parent / "schema" / SCENE_REPAIR_REPORT_SCHEMA_FILENAME
        if candidate.exists():
            return candidate.parent
    raise FileNotFoundError(f"Could not locate schema/{SCENE_REPAIR_REPORT_SCHEMA_FILENAME}")


def get_scene_repair_report_schema() -> dict[str, Any]:
    """Return the committed Scene Repair Report JSON Schema."""
    return json.loads((_schema_root() / SCENE_REPAIR_REPORT_SCHEMA_FILENAME).read_text(encoding="utf-8"))


def validate_scene_repair_report_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Return JSON-schema diagnostics for a Scene Repair Report payload."""
    import jsonschema

    validator = jsonschema.Draft202012Validator(get_scene_repair_report_schema())
    diagnostics: list[dict[str, Any]] = []
    for error in sorted(validator.iter_errors(payload), key=lambda item: list(item.absolute_path)):
        diagnostics.append(
            {
                "code": "SCENE_REPAIR_REPORT_SCHEMA_VALIDATION",
                "severity": "error",
                "contract": SCENE_REPAIR_REPORT_CONTRACT,
                "path": _json_pointer(*error.absolute_path),
                "message": error.message,
            }
        )
    return diagnostics


def _json_pointer(*parts: object) -> str:
    escaped = [str(part).replace("~", "~0").replace("/", "~1") for part in parts]
    return "/" + "/".join(escaped) if escaped else "/"


def _diagnostic(
    code: str,
    name: str,
    path: str,
    message: str,
    *,
    contract: str = RENDER_INSPECTION_CONTRACT,
    phase: str = RENDER_INSPECTION_PHASE,
    severity: str = "error",
    details: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "code": code,
        "name": name,
        "severity": severity,
        "contract": contract,
        "phase": phase,
        "path": path,
        "message": message,
    }
    if details:
        payload["details"] = dict(details)
    return payload


def _items(scene_graph: Mapping[str, Any], collection: str) -> Iterator[tuple[int, Mapping[str, Any]]]:
    raw = scene_graph.get(collection, [])
    if not isinstance(raw, list):
        return
    for index, item in enumerate(raw):
        if isinstance(item, Mapping):
            yield index, item


def _string_field(item: Mapping[str, Any], field_name: str) -> str | None:
    value = item.get(field_name)
    return value if isinstance(value, str) else None


def _entity_locations(scene_graph: Mapping[str, Any]) -> dict[str, str]:
    locations: dict[str, str] = {}
    scene_id = scene_graph.get("scene_id")
    if isinstance(scene_id, str):
        locations[scene_id] = "/scene_id"
    for collection, field_name in _ENTITY_COLLECTIONS.items():
        for index, item in _items(scene_graph, collection):
            entity_id = _string_field(item, field_name)
            if entity_id is not None and entity_id not in locations:
                locations[entity_id] = _json_pointer(collection, index, field_name)
    return locations


def _scene_ref_exists(scene_graph: Mapping[str, Any], target_id: str) -> bool:
    return target_id in _entity_locations(scene_graph)


def _target_exists(scene_graph: Mapping[str, Any], scope: str, target_id: str) -> bool:
    if scope == "scene":
        return scene_graph.get("scene_id") == target_id
    if scope == "asset":
        return any(item.get(field_name) == target_id for _, item in _items(scene_graph, "objects") for field_name in _ASSET_FIELDS)
    target = _TARGET_COLLECTIONS.get(scope)
    if target is None:
        return False
    collection, field_name = target
    return any(item.get(field_name) == target_id for _, item in _items(scene_graph, collection))


def _render_camera_exists(scene_graph: Mapping[str, Any], camera_id: str) -> bool:
    return any(item.get("camera_id") == camera_id for _, item in _items(scene_graph, "cameras"))


def _is_problem_target_id(value: str) -> bool:
    return any(is_scene_entity_id(prefix, value) for prefix in _PROBLEM_TARGET_PREFIXES)


def _is_scene_ref_id(value: str) -> bool:
    return any(is_scene_entity_id(prefix, value) for prefix in _PATCH_SCENE_REF_PREFIXES)


def inspect_render(
    scene_graph: Mapping[str, Any],
    render_inspection_payload: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Return schema and semantic diagnostics for a Render Inspection payload."""
    payload = dict(render_inspection_payload)
    diagnostics = validate_contract(RENDER_INSPECTION_CONTRACT, payload)
    diagnostics.extend(_inspect_render_semantics(scene_graph, payload))
    return diagnostics


def _inspect_render_semantics(
    scene_graph: Mapping[str, Any],
    payload: Mapping[str, Any],
) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    scene_id = payload.get("scene_id")
    if isinstance(scene_id, str) and scene_graph.get("scene_id") != scene_id:
        diagnostics.append(
            _diagnostic(
                "RR1001",
                "inspection_scene_id_mismatch",
                "/scene_id",
                f"Render Inspection scene_id {scene_id!r} does not match Scene Graph scene_id {scene_graph.get('scene_id')!r}.",
                details={"scene_id": scene_id, "scene_graph_scene_id": scene_graph.get("scene_id")},
            )
        )

    render_ref = payload.get("render_ref")
    if isinstance(render_ref, Mapping):
        camera_id = render_ref.get("camera_id")
        if isinstance(camera_id, str) and not _render_camera_exists(scene_graph, camera_id):
            diagnostics.append(
                _diagnostic(
                    "RR1002",
                    "inspection_camera_missing",
                    "/render_ref/camera_id",
                    f"Render Inspection camera_id {camera_id!r} does not exist in the Scene Graph.",
                    details={"camera_id": camera_id},
                )
            )

    problems = payload.get("problems", [])
    if isinstance(problems, list):
        diagnostics.extend(_problem_target_diagnostics(scene_graph, problems))

    recommendations = payload.get("recommended_patches", [])
    if isinstance(recommendations, list):
        diagnostics.extend(_recommended_patch_diagnostics(scene_graph, recommendations))
    return diagnostics


def _problem_target_diagnostics(
    scene_graph: Mapping[str, Any],
    problems: Sequence[Any],
) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    for index, problem in enumerate(problems):
        if not isinstance(problem, Mapping):
            continue
        target_id = problem.get("target_id")
        if not isinstance(target_id, str) or not _is_problem_target_id(target_id):
            continue
        if _scene_ref_exists(scene_graph, target_id):
            continue
        diagnostics.append(
            _diagnostic(
                "RR1003",
                "inspection_problem_target_missing",
                _json_pointer("problems", index, "target_id"),
                f"Render Inspection problem target_id {target_id!r} does not exist in the Scene Graph.",
                details={"target_id": target_id, "problem_id": problem.get("problem_id")},
            )
        )
    return diagnostics


def _recommended_patch_diagnostics(
    scene_graph: Mapping[str, Any],
    recommendations: Sequence[Any],
) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    for index, recommendation in enumerate(recommendations):
        if not isinstance(recommendation, Mapping):
            continue
        scope = recommendation.get("scope")
        target_id = recommendation.get("target_id")
        if not isinstance(scope, str) or not isinstance(target_id, str):
            continue
        if _target_exists(scene_graph, scope, target_id):
            continue
        diagnostics.append(
            _diagnostic(
                "RR1004",
                "recommended_patch_target_missing",
                _json_pointer("recommended_patches", index, "target_id"),
                f"Render Inspection recommended patch target {target_id!r} does not exist for scope {scope!r}.",
                details={"scope": scope, "target_id": target_id},
            )
        )
    return diagnostics


def propose_repairs(
    scene_graph: Mapping[str, Any],
    render_inspection_payload: Mapping[str, Any],
    goal: RepairGoal = "wonder_preview",
) -> SceneRepairProposalResult:
    """Convert Render Inspection recommendations into deterministic Scene Patch proposals."""
    if goal not in REPAIR_GOALS:
        supported = ", ".join(REPAIR_GOALS)
        raise ValueError(f"goal must be one of: {supported}")

    payload = dict(render_inspection_payload)
    diagnostics = inspect_render(scene_graph, payload)
    proposals: list[dict[str, Any]] = []
    proposal_reports: list[dict[str, Any]] = []
    if not diagnostics:
        for index, recommendation in enumerate(payload.get("recommended_patches", [])):
            if not isinstance(recommendation, Mapping):
                continue
            proposal = _proposal_from_recommendation(payload, recommendation, index, goal)
            proposal_diagnostics = validate_contract("scene_patch", proposal)
            proposals.append(proposal)
            proposal_reports.append(
                _proposal_report(
                    proposal,
                    status="proposed" if not proposal_diagnostics else "rejected",
                    source_recommendation_index=index,
                    diagnostics=proposal_diagnostics,
                )
            )
            diagnostics.extend(proposal_diagnostics)

    report = _repair_report(
        scene_graph=scene_graph,
        payload=payload,
        goal=goal,
        status=_proposal_status(proposals, diagnostics),
        max_rounds=0,
        rounds_completed=0,
        proposal_reports=proposal_reports,
        rounds=[],
        diagnostics=diagnostics,
    )
    return SceneRepairProposalResult(proposals=proposals, report=report)


def repair_scene_offline(
    scene_graph: Mapping[str, Any],
    render_inspection_payload: Mapping[str, Any],
    *,
    goal: RepairGoal = "wonder_preview",
    max_rounds: int = 3,
) -> SceneRepairLoopResult:
    """Apply valid repair proposals with no external render, vision, or model calls."""
    if max_rounds < 0:
        raise ValueError("max_rounds must be greater than or equal to 0")

    proposal_result = propose_repairs(scene_graph, render_inspection_payload, goal=goal)
    payload = dict(render_inspection_payload)
    working = copy.deepcopy(dict(scene_graph))
    proposal_reports: list[dict[str, Any]] = []
    rounds: list[dict[str, Any]] = []
    diagnostics = list(proposal_result.report.get("diagnostics", []))

    if diagnostics:
        report = _repair_report(
            scene_graph=working,
            payload=payload,
            goal=goal,
            status="blocked",
            max_rounds=max_rounds,
            rounds_completed=0,
            proposal_reports=list(proposal_result.report.get("proposals", [])),
            rounds=[],
            diagnostics=diagnostics,
        )
        return SceneRepairLoopResult(scene_graph=working, report=report, proposals=proposal_result.proposals)

    for index, proposal in enumerate(proposal_result.proposals):
        if index >= max_rounds:
            max_round_diagnostic = _diagnostic(
                "RR3001",
                "repair_max_rounds_reached",
                _json_pointer("proposals", index),
                f"Repair proposal {proposal.get('patch_id')!r} was skipped because max_rounds was reached.",
                contract=SCENE_REPAIR_REPORT_CONTRACT,
                phase=SCENE_REPAIR_PHASE,
                severity="warning",
                details={"max_rounds": max_rounds},
            )
            diagnostics.append(max_round_diagnostic)
            proposal_reports.append(
                _proposal_report(
                    proposal,
                    status="skipped",
                    source_recommendation_index=index,
                    diagnostics=[max_round_diagnostic],
                )
            )
            continue

        patch_diagnostics = validate_contract("scene_patch", proposal)
        if patch_diagnostics:
            diagnostics.extend(patch_diagnostics)
            proposal_reports.append(
                _proposal_report(proposal, status="rejected", source_recommendation_index=index, diagnostics=patch_diagnostics)
            )
            rounds.append(_round_report(index + 1, proposal, status="rejected", diagnostics=patch_diagnostics))
            continue

        patch_result = apply_scene_patch(working, proposal)
        round_status = "applied" if not patch_result.diagnostics else "rejected"
        if patch_result.diagnostics:
            diagnostics.extend(patch_result.diagnostics)
        else:
            working = patch_result.scene_graph
        proposal_reports.append(
            _proposal_report(
                proposal,
                status=round_status,
                source_recommendation_index=index,
                diagnostics=patch_result.diagnostics,
            )
        )
        rounds.append(
            _round_report(
                index + 1,
                proposal,
                status=round_status,
                diagnostics=patch_result.diagnostics,
                applied_operations=len(patch_result.applied_operations),
                rejected_operations=len(patch_result.rejected_operations),
            )
        )

    report = _repair_report(
        scene_graph=working,
        payload=payload,
        goal=goal,
        status=_loop_status(proposal_reports, diagnostics),
        max_rounds=max_rounds,
        rounds_completed=len(rounds),
        proposal_reports=proposal_reports,
        rounds=rounds,
        diagnostics=diagnostics,
    )
    return SceneRepairLoopResult(scene_graph=working, report=report, proposals=proposal_result.proposals)


def _proposal_status(proposals: Sequence[Mapping[str, Any]], diagnostics: Sequence[Mapping[str, Any]]) -> str:
    if diagnostics:
        return "blocked"
    if not proposals:
        return "no_repairs_needed"
    return "proposed"


def _loop_status(proposal_reports: Sequence[Mapping[str, Any]], diagnostics: Sequence[Mapping[str, Any]]) -> str:
    if not proposal_reports:
        return "no_repairs_needed"
    if any(report.get("status") == "skipped" for report in proposal_reports):
        return "max_rounds_reached"
    applied = sum(1 for report in proposal_reports if report.get("status") == "applied")
    rejected = sum(1 for report in proposal_reports if report.get("status") == "rejected")
    if rejected and applied:
        return "partial"
    if rejected or diagnostics:
        return "failed"
    return "applied"


def _proposal_from_recommendation(
    payload: Mapping[str, Any],
    recommendation: Mapping[str, Any],
    index: int,
    goal: RepairGoal,
) -> dict[str, Any]:
    suggested = recommendation.get("suggested_patch")
    patch = {
        str(key): copy.deepcopy(value)
        for key, value in suggested.items()
        if isinstance(suggested, Mapping) and isinstance(key, str) and key in _FULL_PATCH_FIELDS
    }
    scope = str(recommendation.get("scope", patch.get("scope", "scene")))
    target_id = str(recommendation.get("target_id", patch.get("target_id", payload.get("scene_id", "scene"))))
    patch["schema_version"] = "lathe.scene_patch.v1"
    patch["patch_id"] = str(patch.get("patch_id") or _patch_id(payload, recommendation, index))
    patch["scope"] = scope
    patch["target_id"] = target_id
    patch["instruction"] = _instruction(payload, recommendation, goal, patch.get("instruction"))
    patch["preserve"] = _preserve_list(scope, target_id, patch.get("preserve"))
    patch["allowed_changes"] = _allowed_changes(scope, goal, patch.get("allowed_changes"))
    patch["continuity"] = _continuity(scope, target_id, patch.get("continuity"))
    patch["acceptance"] = _acceptance(goal, patch.get("acceptance"))
    return patch


def _patch_id(payload: Mapping[str, Any], recommendation: Mapping[str, Any], index: int) -> str:
    seed = {
        "inspection_id": payload.get("inspection_id"),
        "scene_id": payload.get("scene_id"),
        "index": index,
        "scope": recommendation.get("scope"),
        "target_id": recommendation.get("target_id"),
        "change": recommendation.get("change"),
    }
    body = snake_id(
        f"{payload.get('inspection_id', 'inspect')}_{index + 1}_{recommendation.get('target_id', 'target')}",
        fallback="repair",
    )
    return f"patch_{clamp_id_body(f'{body}_{digest_text(seed, length=10)}')}"


def _repair_id(payload: Mapping[str, Any], goal: RepairGoal) -> str:
    seed = f"{payload.get('inspection_id', 'inspect')}_{goal}_{payload.get('scene_id', 'scene')}"
    return f"repair_{clamp_id_body(snake_id(seed, fallback='repair'))}"


def _instruction(
    payload: Mapping[str, Any],
    recommendation: Mapping[str, Any],
    goal: RepairGoal,
    suggested_instruction: object,
) -> str:
    if isinstance(suggested_instruction, str) and suggested_instruction.strip():
        instruction = suggested_instruction.strip()
    else:
        instruction = str(recommendation.get("change") or "Repair the render inspection recommendation.").strip()
    context = f"Render inspection {payload.get('inspection_id', 'unknown')} goal {goal}."
    combined = f"{instruction} {context}"
    return combined[:1200]


def _preserve_list(scope: str, target_id: str, suggested: object) -> list[str]:
    if isinstance(suggested, list) and all(isinstance(item, str) and item for item in suggested):
        return _unique_strings(suggested)
    if scope == "object":
        return ["object_id", "region", "transform.position", "transform.rotation", "transform.scale"]
    if scope in {"camera", "light"}:
        return [f"{scope}_id", "target"]
    if scope == "region":
        return ["region_id", "bounds"]
    if scope == "curiosity_anchor":
        return ["anchor_id", "attached_to"]
    if scope == "hidden_state":
        return ["hidden_id", "attached_to"]
    if _is_scene_ref_id(target_id):
        return [target_id]
    return ["stable_ids"]


def _allowed_changes(scope: str, goal: RepairGoal, suggested: object) -> list[str]:
    if isinstance(suggested, list) and all(isinstance(item, str) and item for item in suggested):
        return _unique_strings(suggested)
    if goal == "wonder_preview":
        return list(_WONDER_PREVIEW_ALLOWED.get(scope, ["metadata"]))
    if goal == "export_ready":
        return ["assets", "materials", "geometry", "transforms", "metadata"]
    return ["assets", "materials", "scale", "metadata"]


def _continuity(scope: str, target_id: str, suggested: object) -> dict[str, Any]:
    if isinstance(suggested, Mapping):
        return dict(suggested)
    continuity: dict[str, Any] = {"mode": "preserve_selected_ids"}
    if scope != "asset" and _is_scene_ref_id(target_id):
        continuity["preserved_ids"] = [target_id]
    return continuity


def _acceptance(goal: RepairGoal, suggested: object) -> dict[str, Any]:
    if isinstance(suggested, Mapping):
        return dict(suggested)
    return copy.deepcopy(_GOAL_ACCEPTANCE[goal])


def _unique_strings(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _proposal_report(
    patch: Mapping[str, Any],
    *,
    status: str,
    source_recommendation_index: int,
    diagnostics: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        "patch_id": patch.get("patch_id"),
        "scope": patch.get("scope"),
        "target_id": patch.get("target_id"),
        "status": status,
        "source_recommendation_index": source_recommendation_index,
        "instruction": patch.get("instruction"),
        "allowed_changes": list(patch.get("allowed_changes", [])) if isinstance(patch.get("allowed_changes"), list) else [],
        "diagnostics": [dict(diagnostic) for diagnostic in diagnostics],
        "patch": copy.deepcopy(dict(patch)),
    }


def _round_report(
    round_number: int,
    patch: Mapping[str, Any],
    *,
    status: str,
    diagnostics: Sequence[Mapping[str, Any]],
    applied_operations: int = 0,
    rejected_operations: int = 0,
) -> dict[str, Any]:
    return {
        "round": round_number,
        "patch_id": patch.get("patch_id"),
        "status": status,
        "applied_operations": applied_operations,
        "rejected_operations": rejected_operations,
        "diagnostics": [dict(diagnostic) for diagnostic in diagnostics],
    }


def _repair_report(
    *,
    scene_graph: Mapping[str, Any],
    payload: Mapping[str, Any],
    goal: RepairGoal,
    status: str,
    max_rounds: int,
    rounds_completed: int,
    proposal_reports: Sequence[Mapping[str, Any]],
    rounds: Sequence[Mapping[str, Any]],
    diagnostics: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    applied = sum(1 for proposal in proposal_reports if proposal.get("status") == "applied")
    rejected = sum(1 for proposal in proposal_reports if proposal.get("status") == "rejected")
    skipped = sum(1 for proposal in proposal_reports if proposal.get("status") == "skipped")
    return {
        "schema_version": SCENE_REPAIR_REPORT_VERSION,
        "repair_id": _repair_id(payload, goal),
        "scene_id": scene_graph.get("scene_id"),
        "scene_version": scene_graph.get("version"),
        "inspection_id": payload.get("inspection_id"),
        "goal": goal,
        "status": status,
        "max_rounds": max_rounds,
        "rounds_completed": rounds_completed,
        "summary": {
            "proposals": len(proposal_reports),
            "applied": applied,
            "rejected": rejected,
            "skipped": skipped,
            "diagnostics": len(diagnostics),
            "errors": sum(1 for diagnostic in diagnostics if diagnostic.get("severity") == "error"),
            "warnings": sum(1 for diagnostic in diagnostics if diagnostic.get("severity") == "warning"),
        },
        "proposals": [copy.deepcopy(dict(proposal)) for proposal in proposal_reports],
        "rounds": [copy.deepcopy(dict(round_report)) for round_report in rounds],
        "diagnostics": [dict(diagnostic) for diagnostic in diagnostics],
    }


__all__ = [
    "REPAIR_GOALS",
    "SCENE_REPAIR_REPORT_CONTRACT",
    "SCENE_REPAIR_REPORT_SCHEMA_FILENAME",
    "SCENE_REPAIR_REPORT_VERSION",
    "SceneRepairLoopResult",
    "SceneRepairProposalResult",
    "get_scene_repair_report_schema",
    "inspect_render",
    "propose_repairs",
    "repair_scene_offline",
    "validate_scene_repair_report_payload",
]
