"""LLM-facing authoring helpers for Wonder contracts.

The helpers in this module are deliberately offline and deterministic. They
compact existing Lathe diagnostics into a small model-friendly shape and turn
semantic edit requests into Scene Patch JSON without calling an external model.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from typing import Any

from .contracts import CONTRACT_SPECS, validate_contract

LLM_DIAGNOSTIC_SUMMARY_VERSION = "lathe.llm_diagnostic_summary.v1"
LLM_REPAIR_PLAYBOOK_VERSION = "lathe.llm_repair_playbook.v1"
SCENE_PATCH_SCHEMA_VERSION = "lathe.scene_patch.v1"

_MAX_MESSAGE_CHARS = 240
_DEFAULT_MAX_DIAGNOSTICS = 20
_REQUIRED_PROPERTY_RE = re.compile(r"^'(?P<field>[^']+)' is a required property$")
_SCENE_REF_RE = re.compile(r"^(obj|region|camera|light|curiosity|hidden)_[a-z0-9_]{3,80}$")
_SNAKE_RE = re.compile(r"^[a-z][a-z0-9_]{2,79}$")
_SLUG_RE = re.compile(r"[^a-z0-9]+")

_CONTRACT_BY_SCHEMA_VERSION = {
    "lathe.dream_brief.v1": "dream_brief",
    "lathe.scene_graph.v1": "scene_graph",
    "lathe.scene_patch.v1": "scene_patch",
    "lathe.render_inspection.v1": "render_inspection",
    "lathe.world_memory.v1": "world_memory",
    "lathe.scene_package_manifest.v1": "scene_package_manifest",
    "lathe.scene_plan.v1": "scene_plan",
    "lathe.camera_lock.v1": "camera_lock",
    "lathe.render_comparison.v1": "render_comparison",
    "lathe.llm_repair_playbook.v1": "llm_repair_playbook",
    "lathe.scene_quality_report.v1": "scene_quality_report",
    "lathe.scene_repair_report.v1": "scene_repair_report",
    "lathe.scene_assembly.v1": "scene_assembly",
    "lathe.scene_branch.v1": "scene_branch",
    "lathe.scene_diff.v1": "scene_diff",
    "lathe.scene_benchmark_report.v1": "scene_benchmark_report",
    "lathe.style_pack.v1": "style_pack",
    "lathe.layout_plan.v1": "layout_plan",
    "lathe.game_readiness.v1": "game_readiness",
    "lathe.asset_provenance_scene.v1": "asset_provenance_scene",
    "lathe.roblox_profile.v1": "roblox_profile",
    "lathe.roblox_manifest.v1": "roblox_manifest",
}

_SCENE_PATCH_SCOPES = (
    "asset",
    "object",
    "region",
    "scene",
    "camera",
    "light",
    "curiosity_anchor",
    "hidden_state",
)

_PATCH_ALLOWED_CHANGES = {
    "affordances",
    "assets",
    "cameras",
    "curiosity_anchors",
    "debris",
    "geometry",
    "hidden_state",
    "layout",
    "lighting",
    "materials",
    "metadata",
    "objects",
    "props",
    "relationships",
    "scale",
    "state",
    "style",
    "transforms",
}

_DEFAULT_ALLOWED_BY_SCOPE = {
    "asset": ("assets", "materials", "style", "metadata"),
    "object": ("materials", "style", "lighting", "state", "metadata"),
    "region": ("layout", "style", "lighting", "metadata"),
    "scene": ("layout", "style", "lighting", "metadata"),
    "camera": ("cameras", "metadata"),
    "light": ("lighting", "metadata"),
    "curiosity_anchor": ("curiosity_anchors", "metadata"),
    "hidden_state": ("hidden_state", "metadata"),
}

_ID_VALUE_HINTS = {
    "object_id": "obj_<stable_snake_id>",
    "region_id": "region_<stable_snake_id>",
    "relationship_id": "rel_<stable_snake_id>",
    "material_id": "mat_<stable_snake_id>",
    "light_id": "light_<stable_snake_id>",
    "camera_id": "camera_<stable_snake_id>",
    "anchor_id": "curiosity_<stable_snake_id>",
    "hidden_id": "hidden_<stable_snake_id>",
    "event_id": "mem_<stable_snake_id>",
    "patch_id": "patch_<stable_snake_id>",
    "scene_id": "<stable_scene_snake_id>",
}


def compact_diagnostic(
    diagnostic: Mapping[str, Any],
    *,
    payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a compact LLM-facing view of one Lathe diagnostic."""
    code = _string_or(diagnostic.get("code"), "UNKNOWN_DIAGNOSTIC")
    severity = _string_or(diagnostic.get("severity"), "error")
    pointer = _json_pointer_or_root(diagnostic.get("path"))
    compact: dict[str, Any] = {
        "family": _diagnostic_family(diagnostic),
        "severity": severity,
        "code": code,
        "json_pointer": pointer,
        "message": _compact_message(diagnostic.get("message")),
        "next_action": _next_action(diagnostic, payload=payload),
    }
    for key in ("name", "contract", "phase"):
        value = diagnostic.get(key)
        if isinstance(value, str) and value:
            compact[key] = value
    source_span = diagnostic.get("source_span")
    if isinstance(source_span, Mapping):
        compact["source_span"] = copy.deepcopy(dict(source_span))

    options = diagnostic_repair_options(diagnostic, payload=payload)
    if options:
        compact["repair_options"] = options
    return compact


def compact_diagnostic_summary(
    diagnostics: Sequence[Mapping[str, Any]],
    *,
    payload: Mapping[str, Any] | None = None,
    max_diagnostics: int = _DEFAULT_MAX_DIAGNOSTICS,
) -> dict[str, Any]:
    """Return a compact diagnostic summary with aggregate repair options."""
    compacted = [
        compact_diagnostic(diagnostic, payload=payload)
        for diagnostic in diagnostics[: max(max_diagnostics, 0)]
    ]
    errors = sum(1 for diagnostic in diagnostics if diagnostic.get("severity") == "error")
    warnings = sum(1 for diagnostic in diagnostics if diagnostic.get("severity") == "warning")
    info = sum(1 for diagnostic in diagnostics if diagnostic.get("severity") == "info")
    summary = {
        "diagnostics": len(diagnostics),
        "errors": errors,
        "warnings": warnings,
        "info": info,
    }
    omitted = max(len(diagnostics) - len(compacted), 0)
    if omitted:
        summary["omitted"] = omitted

    result: dict[str, Any] = {
        "schema_version": LLM_DIAGNOSTIC_SUMMARY_VERSION,
        "status": _status_for_counts(errors, warnings),
        "summary": summary,
        "diagnostics": compacted,
    }
    repair_options = _unique_repair_options(
        option
        for diagnostic in compacted
        for option in diagnostic.get("repair_options", [])
        if isinstance(option, Mapping)
    )
    if repair_options:
        result["repair_options"] = repair_options
    return result


def diagnose_for_llm(
    report_or_payload: Mapping[str, Any] | Sequence[Mapping[str, Any]] | str,
    *,
    contract: str | None = None,
    root: str | None = None,
    max_diagnostics: int = _DEFAULT_MAX_DIAGNOSTICS,
) -> dict[str, Any]:
    """Validate or compact a Wonder report/payload for LLM authoring loops."""
    payload = _payload_context(report_or_payload)
    diagnostics = _diagnostics_for_input(report_or_payload, contract=contract, root=root)
    summary = compact_diagnostic_summary(diagnostics, payload=payload, max_diagnostics=max_diagnostics)
    source = _source_summary(report_or_payload, contract=contract)
    if source:
        summary["source"] = source
    return summary


def generate_scene_plan(
    dream_brief: Mapping[str, Any],
    *,
    scene_graph: Mapping[str, Any] | None = None,
    mode: str = "preview",
) -> dict[str, Any]:
    """Generate a deterministic offline Scene Plan from a brief and optional Scene Graph."""
    from lathe.scene.planner import plan_scene, validate_scene_plan_payload

    if mode not in {"preview", "final"}:
        raise ValueError("scene plan mode must be 'preview' or 'final'")
    diagnostics = validate_contract("dream_brief", dict(dream_brief))
    if diagnostics:
        first = diagnostics[0]
        raise ValueError(f"Dream Brief cannot generate a Scene Plan: {first['path']}: {first['message']}")

    reduced_specificity_diagnostic: dict[str, Any] | None = None
    if scene_graph is None:
        from lathe.wonder.brief import lower_dream_brief_to_scene_graph

        scene_graph = lower_dream_brief_to_scene_graph(dream_brief)
        reduced_specificity_diagnostic = {
            "code": "SP4001",
            "name": "brief_only_plan_reduced_specificity",
            "severity": "warning",
            "contract": "scene_plan",
            "phase": "scene_planning",
            "path": "/",
            "message": (
                "Scene Plan was generated from Dream Brief only; object, camera, and export specificity "
                "is reduced until a Scene Graph is provided."
            ),
            "repair_hint": "Provide --scene-graph to derive asset, render, and export tasks from stable scene IDs.",
        }

    plan = plan_scene(scene_graph, mode=mode)  # type: ignore[arg-type]
    brief_id = dream_brief.get("brief_id")
    if isinstance(brief_id, str) and brief_id:
        plan["source_brief_id"] = brief_id
    source_prompt = dream_brief.get("source_prompt") or dream_brief.get("one_sentence")
    if isinstance(source_prompt, str) and source_prompt:
        plan["source_prompt"] = source_prompt
    if reduced_specificity_diagnostic is not None:
        plan["diagnostics"] = [*plan.get("diagnostics", []), reduced_specificity_diagnostic]
        plan["warnings"] = [*plan.get("warnings", []), reduced_specificity_diagnostic]

    validation_diagnostics = validate_scene_plan_payload(plan)
    if validation_diagnostics:
        first = validation_diagnostics[0]
        raise ValueError(f"generated Scene Plan is invalid: {first['path']}: {first['message']}")
    return plan


def build_repair_playbook(
    diagnostics_input: Mapping[str, Any] | Sequence[Mapping[str, Any]],
    *,
    max_diagnostics: int = _DEFAULT_MAX_DIAGNOSTICS,
) -> dict[str, Any]:
    """Build deterministic LLM/human repair steps for diagnostics."""
    diagnostics = _diagnostics_for_playbook_input(diagnostics_input)
    steps = [
        _repair_step(diagnostic, index)
        for index, diagnostic in enumerate(diagnostics[: max(max_diagnostics, 0)], start=1)
    ]
    playbook = {
        "schema_version": LLM_REPAIR_PLAYBOOK_VERSION,
        "status": "ready",
        "summary": {
            "diagnostics": len(diagnostics),
            "steps": len(steps),
            "omitted": max(len(diagnostics) - len(steps), 0),
        },
        "steps": steps,
    }
    validation_diagnostics = validate_repair_playbook_payload(playbook)
    if validation_diagnostics:
        first = validation_diagnostics[0]
        raise ValueError(f"generated LLM repair playbook is invalid: {first['path']}: {first['message']}")
    return playbook


def validate_repair_playbook_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Return JSON-schema diagnostics for an LLM repair playbook payload."""
    return validate_contract("llm_repair_playbook", payload)


def diagnostic_repair_options(
    diagnostic: Mapping[str, Any],
    *,
    payload: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Return compact repair options when a diagnostic maps to a safe edit hint."""
    code = _string_or(diagnostic.get("code"), "")
    name = _string_or(diagnostic.get("name"), "")
    contract = _string_or(diagnostic.get("contract"), "")
    message = _string_or(diagnostic.get("message"), "")
    pointer = _json_pointer_or_root(diagnostic.get("path"))

    missing_field = _required_field(message)
    if missing_field is not None:
        return [
            {
                "kind": "json_patch",
                "op": "add",
                "path": _join_pointer(pointer, missing_field),
                "value_hint": _value_hint_for_required_field(missing_field, payload=payload),
            }
        ]

    if code in {"SS1001", "SS1002"}:
        return [
            {
                "kind": "source_bridge",
                "helper": "lathe.scene.source.scene_graph_to_source",
                "source_contract": "scene_graph",
                "schema": "schema/scene_graph.schema.json",
            }
        ]

    if code == "SP1505":
        details = diagnostic.get("details")
        restored_path = details.get("path") if isinstance(details, Mapping) else None
        options: list[dict[str, Any]] = [{"kind": "json_patch", "op": "remove", "path": _operation_pointer(pointer)}]
        if isinstance(restored_path, str) and restored_path.startswith("/"):
            options.append({"kind": "json_patch", "op": "replace", "path": restored_path, "value_hint": "previous_value"})
        return options

    if code == "SP1504":
        details = diagnostic.get("details")
        change_categories = details.get("change_categories") if isinstance(details, Mapping) else None
        category = _first_string(change_categories) or "metadata"
        return [
            {"kind": "json_patch", "op": "add", "path": "/allowed_changes/-", "value_hint": category},
            {"kind": "json_patch", "op": "remove", "path": _operation_pointer(pointer)},
        ]

    if code == "SP1508":
        return [
            {
                "kind": "scene_patch",
                "field": "scope",
                "action": "retarget_operation_or_patch_scope",
            }
        ]

    if code == "SP1501":
        return [
            {"kind": "scene_patch", "field": "target_id", "action": "choose_existing_target_for_scope"},
        ]

    if _is_duplicate_id_diagnostic(code, name):
        return [
            {
                "kind": "json_patch",
                "op": "replace",
                "path": pointer,
                "value_hint": _duplicate_id_value_hint(diagnostic),
            }
        ]

    if contract == "scene_build" or code.startswith("SB"):
        return [{"kind": "build_input", "path": pointer, "action": "fix_path_or_input_then_rerun_build"}]

    return []


def semantic_patch_request_to_scene_patch(
    request: Mapping[str, Any] | None = None,
    *,
    scene_graph: Mapping[str, Any] | None = None,
    patch_id: str | None = None,
    scope: str | None = None,
    target_id: str | None = None,
    instruction: str | None = None,
    preserve: Sequence[str] | None = None,
    allowed_changes: Sequence[str] | None = None,
    operations: Sequence[Mapping[str, Any]] | None = None,
    continuity: Mapping[str, Any] | None = None,
    acceptance: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Convert a semantic edit request into schema-valid Scene Patch JSON."""
    source = _merged_request(request)
    scope_value = _patch_scope(scope if scope is not None else source.get("scope"))
    target_value = _patch_target(
        target_id if target_id is not None else source.get("target_id"),
        scope=scope_value,
        scene_graph=scene_graph,
        request=source,
    )
    instruction_value = _patch_instruction(
        instruction if instruction is not None else source.get("instruction", source.get("change"))
    )
    patch_id_value = _patch_id(
        patch_id if patch_id is not None else source.get("patch_id"),
        scope=scope_value,
        target_id=target_value,
        instruction=instruction_value,
    )
    preserve_value = _patch_preserve(
        preserve if preserve is not None else source.get("preserve"),
        scope=scope_value,
        target_id=target_value,
        scene_graph=scene_graph,
    )
    allowed_value = _patch_allowed_changes(
        allowed_changes if allowed_changes is not None else source.get("allowed_changes"),
        scope=scope_value,
    )

    patch: dict[str, Any] = {
        "schema_version": SCENE_PATCH_SCHEMA_VERSION,
        "patch_id": patch_id_value,
        "scope": scope_value,
        "target_id": target_value,
        "instruction": instruction_value,
        "preserve": preserve_value,
        "allowed_changes": allowed_value,
    }
    operation_value = operations if operations is not None else source.get("operations")
    if operation_value is not None:
        patch["operations"] = _patch_operations(operation_value)
    patch["continuity"] = _patch_continuity(
        continuity if continuity is not None else source.get("continuity"),
        scope=scope_value,
        target_id=target_value,
    )
    patch["acceptance"] = _patch_acceptance(
        acceptance if acceptance is not None else source.get("acceptance"),
    )

    diagnostics = validate_contract("scene_patch", patch)
    if diagnostics:
        first = diagnostics[0]
        raise ValueError(f"semantic patch request produced invalid Scene Patch: {first['message']}")
    return patch


def _diagnostics_for_input(
    value: Mapping[str, Any] | Sequence[Mapping[str, Any]] | str,
    *,
    contract: str | None,
    root: str | None,
) -> list[dict[str, Any]]:
    if isinstance(value, str):
        return _diagnostics_for_source_text(value, root=root)
    if isinstance(value, Sequence) and not isinstance(value, Mapping | str | bytes | bytearray):
        return [dict(item) for item in value if isinstance(item, Mapping)]
    if not isinstance(value, Mapping):
        return []

    existing = _collect_existing_diagnostics(value)
    if existing:
        return existing

    contract_id = contract or _CONTRACT_BY_SCHEMA_VERSION.get(_string_or(value.get("schema_version"), ""))
    if contract_id is None:
        return []
    return _validate_payload(contract_id, value, root=root)


def _diagnostics_for_playbook_input(value: Mapping[str, Any] | Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    if isinstance(value, Sequence) and not isinstance(value, Mapping | str | bytes | bytearray):
        return [dict(item) for item in value if isinstance(item, Mapping)]
    if isinstance(value, Mapping):
        if _is_diagnostic(value):
            return [dict(value)]
        diagnostics = _collect_existing_diagnostics(value)
        if diagnostics:
            return diagnostics
    return []


def _repair_step(diagnostic: Mapping[str, Any], index: int) -> dict[str, Any]:
    repair_options = _playbook_repair_options(diagnostic)
    step: dict[str, Any] = {
        "step_id": f"repair_{index:03d}",
        "diagnostic_name": _diagnostic_name(diagnostic),
        "diagnostic_code": _string_or(diagnostic.get("code"), "UNKNOWN_DIAGNOSTIC"),
        "path": _json_pointer_or_root(diagnostic.get("path") or diagnostic.get("json_pointer")),
        "instruction": _playbook_instruction(diagnostic),
        "allowed_values": _allowed_values_from_diagnostic(diagnostic),
        "example_patch": _example_patch_from_options(repair_options),
    }
    source_span = diagnostic.get("source_span")
    if isinstance(source_span, Mapping):
        step["source_span"] = copy.deepcopy(dict(source_span))
    repair_hint = diagnostic.get("repair_hint")
    if isinstance(repair_hint, str) and repair_hint:
        step["repair_hint"] = repair_hint
    elif isinstance(diagnostic.get("next_action"), str) and diagnostic.get("next_action"):
        step["repair_hint"] = diagnostic["next_action"]
    return step


def _diagnostic_name(diagnostic: Mapping[str, Any]) -> str:
    for key in ("name", "code", "family"):
        value = diagnostic.get(key)
        if isinstance(value, str) and value:
            return value
    return "unknown_diagnostic"


def _playbook_instruction(diagnostic: Mapping[str, Any]) -> str:
    for key in ("repair_hint", "next_action"):
        value = diagnostic.get(key)
        if isinstance(value, str) and value:
            return value
    code = _string_or(diagnostic.get("code"), "")
    if code == "WONDER_SCHEMA_VALIDATION":
        return "Edit the payload at the indicated JSON pointer so it satisfies the canonical schema, then validate again."
    if code == "SP1501":
        return "Choose an existing Scene Graph target_id for the Scene Patch scope, then rerun patch validation."
    if code == "SP3002" or _diagnostic_name(diagnostic) == "missing_render_task":
        return "Add at least one deterministic scene_render task derived from a Scene Graph camera, then validate the Scene Plan."
    if code.startswith("SS"):
        return "Use generated scene source with an embedded Scene Graph JSON payload, then rerun source conversion."
    return "Inspect the diagnostic path, make the smallest schema-valid correction, then rerun the validator."


def _playbook_repair_options(diagnostic: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = diagnostic.get("repair_options")
    if isinstance(raw, list):
        return [copy.deepcopy(dict(item)) for item in raw if isinstance(item, Mapping)]
    return diagnostic_repair_options(diagnostic)


def _allowed_values_from_diagnostic(diagnostic: Mapping[str, Any]) -> list[Any]:
    details = diagnostic.get("details")
    if not isinstance(details, Mapping):
        return []
    for key in ("allowed_values", "allowed", "supported", "supported_values", "choices"):
        raw = details.get(key)
        if isinstance(raw, list):
            return copy.deepcopy(raw)
        if isinstance(raw, tuple):
            return list(raw)
    return []


def _example_patch_from_options(repair_options: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    for option in repair_options:
        if option.get("kind") != "json_patch":
            continue
        op_name = option.get("op")
        path = option.get("path")
        if not isinstance(op_name, str) or not isinstance(path, str):
            continue
        patch: dict[str, Any] = {"op": op_name, "path": path}
        if "value" in option:
            patch["value"] = copy.deepcopy(option["value"])
        elif "value_hint" in option:
            patch["value_hint"] = copy.deepcopy(option["value_hint"])
        return patch
    return {}


def _diagnostics_for_source_text(source_text: str, *, root: str | None) -> list[dict[str, Any]]:
    from lathe.scene.source import source_to_scene_graph

    _payload, diagnostics = source_to_scene_graph(source_text, root=root)
    return diagnostics


def _validate_payload(contract_id: str, payload: Mapping[str, Any], *, root: str | None) -> list[dict[str, Any]]:
    data = dict(payload)
    if contract_id in CONTRACT_SPECS:
        diagnostics = validate_contract(contract_id, data)
        if diagnostics:
            return diagnostics
    if contract_id == "scene_graph":
        from lathe.scene.graph import check_scene_graph

        return check_scene_graph(data, root=root)
    if contract_id == "scene_plan":
        from lathe.scene.planner import validate_scene_plan_payload

        return validate_scene_plan_payload(data)
    if contract_id == "llm_repair_playbook":
        return validate_repair_playbook_payload(data)
    if contract_id == "scene_repair_report":
        from lathe.scene.repair import validate_scene_repair_report_payload

        return validate_scene_repair_report_payload(data)
    if contract_id == "scene_assembly":
        from lathe.scene.assembly import validate_scene_assembly_payload

        return validate_scene_assembly_payload(data, package_root=root)
    if contract_id == "scene_branch":
        from lathe.scene.versioning import validate_scene_branch_payload

        return validate_scene_branch_payload(data)
    if contract_id == "scene_diff":
        from lathe.scene.versioning import validate_scene_diff_payload

        return validate_scene_diff_payload(data)
    if contract_id == "scene_benchmark_report":
        from lathe.scene.bench import validate_scene_benchmark_report_payload

        return validate_scene_benchmark_report_payload(data)
    if contract_id == "style_pack":
        from lathe.scene.style import validate_style_pack_payload

        return validate_style_pack_payload(data)
    if contract_id == "layout_plan":
        from lathe.scene.layout import validate_layout_plan_payload

        return validate_layout_plan_payload(data)
    if contract_id == "game_readiness":
        from lathe.scene.game_readiness import validate_game_readiness_payload

        return validate_game_readiness_payload(data)
    if contract_id == "asset_provenance_scene":
        from lathe.scene.provenance import validate_asset_provenance_scene_payload

        return validate_asset_provenance_scene_payload(data)
    if contract_id == "roblox_profile":
        from lathe.scene.roblox import validate_roblox_profile_payload

        return validate_roblox_profile_payload(data)
    if contract_id == "roblox_manifest":
        from lathe.scene.roblox import validate_roblox_manifest_payload

        return validate_roblox_manifest_payload(data)
    return [
        {
            "code": "LLM1001",
            "name": "unsupported_llm_diagnostic_contract",
            "severity": "error",
            "contract": "llm_authoring",
            "phase": "llm_diagnostic_summary",
            "path": "/schema_version",
            "message": f"diagnose_for_llm does not know how to validate contract {contract_id!r}.",
        }
    ]


def _collect_existing_diagnostics(value: Mapping[str, Any]) -> list[dict[str, Any]]:
    if _is_diagnostic(value):
        return [dict(value)]
    raw = value.get("diagnostics")
    if isinstance(raw, list):
        return [dict(item) for item in raw if isinstance(item, Mapping) and _is_diagnostic(item)]

    diagnostics: list[dict[str, Any]] = []
    for key in ("validators", "proposals", "rounds", "rejected_operations", "quality"):
        child = value.get(key)
        if isinstance(child, Mapping):
            diagnostics.extend(_collect_existing_diagnostics(child))
        elif isinstance(child, list):
            for item in child:
                if isinstance(item, Mapping):
                    diagnostics.extend(_collect_existing_diagnostics(item))
    return diagnostics


def _is_diagnostic(value: Mapping[str, Any]) -> bool:
    return isinstance(value.get("code"), str) and isinstance(value.get("message"), str)


def _payload_context(value: Any) -> Mapping[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    payload = value.get("payload")
    if isinstance(payload, Mapping):
        return payload
    return value


def _source_summary(value: Any, *, contract: str | None) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    summary: dict[str, Any] = {}
    schema_version = value.get("schema_version")
    if isinstance(schema_version, str):
        summary["schema_version"] = schema_version
    status = value.get("status")
    if isinstance(status, str):
        summary["status"] = status
    contract_value = contract or value.get("contract") or _CONTRACT_BY_SCHEMA_VERSION.get(str(schema_version))
    if isinstance(contract_value, str):
        summary["contract"] = contract_value
    return summary


def _diagnostic_family(diagnostic: Mapping[str, Any]) -> str:
    code = _string_or(diagnostic.get("code"), "")
    contract = _string_or(diagnostic.get("contract"), "")
    if code == "WONDER_SCHEMA_VALIDATION" or code.endswith("_SCHEMA_VALIDATION"):
        return "schema"
    if contract == "scene_build" or code.startswith("SB"):
        return "build"
    if contract.endswith("_report") or contract in {"scene_quality_report", "scene_repair_report"}:
        return "report"
    if contract == "scene_source_bridge" or code.startswith("SS"):
        return "source_bridge"
    if contract == "scene_patch":
        return "scene_patch"
    if contract.startswith("scene_") or code.startswith(("S", "SV", "SA", "SP", "RR")):
        return "scene"
    return "general"


def _next_action(diagnostic: Mapping[str, Any], *, payload: Mapping[str, Any] | None) -> str:
    code = _string_or(diagnostic.get("code"), "")
    name = _string_or(diagnostic.get("name"), "")
    contract = _string_or(diagnostic.get("contract"), "")
    message = _string_or(diagnostic.get("message"), "")
    pointer = _json_pointer_or_root(diagnostic.get("path"))
    missing_field = _required_field(message)
    if missing_field is not None:
        return f"Add the missing required field at {_join_pointer(pointer, missing_field)}."
    if code == "SS1002":
        return "Use generated scene source with an embedded Scene Graph JSON block, or submit Scene Graph JSON directly."
    if code == "SS1001":
        return "Regenerate the source bridge so it includes the Scene Graph JSON fence pair."
    if code == "SP1505":
        return "Keep preserved fields and IDs unchanged, or remove the operation that changes them."
    if code == "SP1504":
        return "Add the required category to allowed_changes or remove the operation."
    if code == "SP1508":
        return "Retarget the operation so it stays inside the declared scope and target_id."
    if code == "SP1501":
        return "Choose an existing target_id for the patch scope before applying the patch."
    if _is_duplicate_id_diagnostic(code, name):
        return "Rename the duplicate stable ID and update every reference to that entity."
    if code in {"SP1000", "SP1001"}:
        return "Add stable object IDs and source fields before planning production builds."
    if contract == "scene_build" or code.startswith("SB"):
        return "Fix the referenced build input or output path, then rerun the scene build."
    if contract.endswith("_report"):
        return "Fix the report payload or the scene input that produced this report, then validate again."
    if code == "WONDER_SCHEMA_VALIDATION":
        return "Edit the payload to satisfy the canonical JSON Schema at the indicated pointer."
    if payload is not None and payload.get("schema_version") == SCENE_PATCH_SCHEMA_VERSION:
        return "Update the Scene Patch payload, then validate it against schema/scene_patch.schema.json."
    return "Fix the value at the indicated JSON pointer and rerun the relevant validator."


def _required_field(message: str) -> str | None:
    match = _REQUIRED_PROPERTY_RE.match(message.strip())
    return match.group("field") if match else None


def _value_hint_for_required_field(field: str, *, payload: Mapping[str, Any] | None) -> Any:
    if field == "schema_version":
        return _schema_version_hint(payload)
    if field == "preserve":
        return _default_preserve_for_payload(payload)
    if field == "allowed_changes":
        return list(_DEFAULT_ALLOWED_BY_SCOPE.get(_payload_scope(payload), ("metadata",)))
    if field == "continuity":
        target_id = _payload_target_id(payload)
        if target_id is not None and _is_scene_ref(target_id):
            return {"mode": "preserve_selected_ids", "preserved_ids": [target_id]}
        return {"mode": "preserve_layout"}
    return _ID_VALUE_HINTS.get(field, f"<{field}>")


def _schema_version_hint(payload: Mapping[str, Any] | None) -> str:
    if payload is None:
        return "lathe.<contract>.v1"
    contract = _string_or(payload.get("contract"), "")
    spec = CONTRACT_SPECS.get(contract)
    if spec is not None:
        return spec.schema_version
    return "lathe.<contract>.v1"


def _default_preserve_for_payload(payload: Mapping[str, Any] | None) -> list[str]:
    scope = _payload_scope(payload)
    target_id = _payload_target_id(payload)
    return _default_preserve(scope, target_id=target_id, scene_graph=payload)


def _payload_scope(payload: Mapping[str, Any] | None) -> str:
    scope = payload.get("scope") if isinstance(payload, Mapping) else None
    return scope if isinstance(scope, str) and scope in _SCENE_PATCH_SCOPES else "scene"


def _payload_target_id(payload: Mapping[str, Any] | None) -> str | None:
    target_id = payload.get("target_id") if isinstance(payload, Mapping) else None
    return target_id if isinstance(target_id, str) and target_id else None


def _is_duplicate_id_diagnostic(code: str, name: str) -> bool:
    return name.startswith("duplicate_") or code in {"S1001", "S1006", "S1007", "S1008", "S1009", "S1010", "S1011"}


def _duplicate_id_value_hint(diagnostic: Mapping[str, Any]) -> str:
    details = diagnostic.get("details")
    if isinstance(details, Mapping):
        for field, hint in _ID_VALUE_HINTS.items():
            if field in details:
                return hint
    pointer = _json_pointer_or_root(diagnostic.get("path"))
    field = pointer.rsplit("/", 1)[-1]
    return _ID_VALUE_HINTS.get(field, "<unique_stable_id>")


def _operation_pointer(pointer: str) -> str:
    if pointer.startswith("/operations/"):
        parts = pointer.split("/")
        if len(parts) >= 3 and parts[2].isdigit():
            return f"/operations/{parts[2]}"
    return "/operations/<index>"


def _json_pointer_or_root(value: Any) -> str:
    if not isinstance(value, str) or not value:
        return "/"
    if value.startswith("/"):
        return value
    return _join_pointer("/", value)


def _join_pointer(parent: str, *parts: object) -> str:
    parent_parts = [] if parent in {"", "/"} else parent.strip("/").split("/")
    escaped = [str(part).replace("~", "~0").replace("/", "~1") for part in parts]
    combined = [*parent_parts, *escaped]
    return "/" + "/".join(combined) if combined else "/"


def _compact_message(value: Any) -> str:
    message = " ".join(str(value or "").split())
    if len(message) <= _MAX_MESSAGE_CHARS:
        return message
    return message[: _MAX_MESSAGE_CHARS - 1].rstrip() + "..."


def _status_for_counts(errors: int, warnings: int) -> str:
    if errors:
        return "failed"
    if warnings:
        return "passed_with_warnings"
    return "passed"


def _unique_repair_options(options: Any) -> list[dict[str, Any]]:
    unique: list[dict[str, Any]] = []
    seen: set[str] = set()
    for option in options:
        if not isinstance(option, Mapping):
            continue
        data = dict(option)
        key = json.dumps(data, sort_keys=True, default=str)
        if key in seen:
            continue
        seen.add(key)
        unique.append(data)
    return unique


def _merged_request(request: Mapping[str, Any] | None) -> dict[str, Any]:
    if request is None:
        return {}
    source: dict[str, Any] = {}
    suggested = request.get("suggested_patch")
    if isinstance(suggested, Mapping):
        source.update({str(key): value for key, value in suggested.items() if isinstance(key, str)})
    source.update({str(key): value for key, value in request.items() if isinstance(key, str)})
    return source


def _patch_scope(value: Any) -> str:
    if value is None:
        return "scene"
    if isinstance(value, str) and value in _SCENE_PATCH_SCOPES:
        return value
    supported = ", ".join(_SCENE_PATCH_SCOPES)
    raise ValueError(f"Scene Patch scope must be one of: {supported}")


def _patch_target(
    value: Any,
    *,
    scope: str,
    scene_graph: Mapping[str, Any] | None,
    request: Mapping[str, Any],
) -> str:
    if isinstance(value, str) and value:
        return value
    if scope == "scene":
        scene_id = _mapping_string(scene_graph, "scene_id") or _mapping_string(request, "scene_id")
        if scene_id is not None:
            return scene_id
    raise ValueError("semantic patch request requires target_id unless scope is scene and scene_id is available")


def _patch_instruction(value: Any) -> str:
    if isinstance(value, str) and value.strip():
        return " ".join(value.split())[:1200]
    raise ValueError("semantic patch request requires a non-empty instruction or change")


def _patch_id(value: Any, *, scope: str, target_id: str, instruction: str) -> str:
    if isinstance(value, str) and value:
        return value
    digest = hashlib.sha256(f"{scope}:{target_id}:{instruction}".encode()).hexdigest()[:10]
    body = _clamp_id_body(f"{_snake_id(scope)}_{_snake_id(target_id)}_{digest}", max_body=80)
    return f"patch_{body}"


def _patch_preserve(
    value: Any,
    *,
    scope: str,
    target_id: str,
    scene_graph: Mapping[str, Any] | None,
) -> list[str]:
    if _nonempty_string_sequence(value):
        return _unique_strings(value)
    return _default_preserve(scope, target_id=target_id, scene_graph=scene_graph)


def _default_preserve(
    scope: str,
    *,
    target_id: str | None,
    scene_graph: Mapping[str, Any] | None,
) -> list[str]:
    if scope == "object":
        return ["object_id", "region", "transform.position", "transform.rotation", "transform.scale"]
    if scope == "region":
        return ["region_id", "bounds"]
    if scope == "camera":
        return ["camera_id", "target", "transform.position", "transform.rotation"]
    if scope == "light":
        return ["light_id", "target"]
    if scope == "curiosity_anchor":
        return ["anchor_id", "attached_to", "hidden_fact"]
    if scope == "hidden_state":
        return ["hidden_id", "attached_to", "fact"]
    if scope == "asset":
        return ["stable_ids", "lathe_asset"]

    preserve = ["stable_ids", "layout.focal_point"]
    scene_id = _mapping_string(scene_graph, "scene_id")
    if scene_id is not None:
        preserve.append(scene_id)
    elif target_id is not None:
        preserve.append(target_id)
    return _unique_strings(preserve)


def _patch_allowed_changes(value: Any, *, scope: str) -> list[str]:
    if _nonempty_string_sequence(value):
        unsupported = sorted(set(value) - _PATCH_ALLOWED_CHANGES)
        if unsupported:
            raise ValueError(f"unsupported Scene Patch allowed_changes: {', '.join(unsupported)}")
        return _unique_strings(value)
    return list(_DEFAULT_ALLOWED_BY_SCOPE[scope])


def _patch_operations(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes | bytearray):
        raise ValueError("Scene Patch operations must be a sequence of JSON objects")
    operations: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, Mapping):
            raise ValueError("Scene Patch operation entries must be JSON objects")
        operations.append(copy.deepcopy(dict(item)))
    return operations


def _patch_continuity(value: Any, *, scope: str, target_id: str) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return copy.deepcopy(dict(value))
    if _is_scene_ref(target_id):
        return {"mode": "preserve_selected_ids", "preserved_ids": [target_id]}
    if scope == "scene":
        return {"mode": "preserve_layout"}
    return {"mode": "preserve_selected_ids"}


def _patch_acceptance(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return copy.deepcopy(dict(value))
    return {
        "validators": ["style", "semantic", "composition", "continuity"],
        "minimum_score": 0.78,
    }


def _mapping_string(value: Mapping[str, Any] | None, key: str) -> str | None:
    if value is None:
        return None
    item = value.get(key)
    return item if isinstance(item, str) and item else None


def _nonempty_string_sequence(value: Any) -> bool:
    return isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray) and all(
        isinstance(item, str) and item for item in value
    ) and bool(value)


def _unique_strings(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _first_string(value: Any) -> str | None:
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        for item in value:
            if isinstance(item, str) and item:
                return item
    return value if isinstance(value, str) and value else None


def _is_scene_ref(value: str) -> bool:
    return _SCENE_REF_RE.fullmatch(value) is not None


def _snake_id(value: object, *, fallback: str = "item") -> str:
    raw = str(value).strip().lower().replace("&", " and ")
    slug = _SLUG_RE.sub("_", raw)
    slug = re.sub(r"_+", "_", slug).strip("_")
    if not slug:
        slug = fallback
    if not slug[0].isalpha():
        slug = f"{fallback}_{slug}"
    if len(slug) < 3:
        slug = f"{slug}_{fallback}"
    return _clamp_id_body(slug)


def _clamp_id_body(body: str, *, max_body: int = 80) -> str:
    if len(body) <= max_body:
        return body
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()[:8]
    trim_length = max_body - len(digest) - 1
    return f"{body[:trim_length].rstrip('_')}_{digest}"


def _string_or(value: Any, fallback: str) -> str:
    return value if isinstance(value, str) and value else fallback


__all__ = [
    "LLM_DIAGNOSTIC_SUMMARY_VERSION",
    "LLM_REPAIR_PLAYBOOK_VERSION",
    "SCENE_PATCH_SCHEMA_VERSION",
    "build_repair_playbook",
    "compact_diagnostic",
    "compact_diagnostic_summary",
    "diagnose_for_llm",
    "diagnostic_repair_options",
    "generate_scene_plan",
    "semantic_patch_request_to_scene_patch",
    "validate_repair_playbook_payload",
]
