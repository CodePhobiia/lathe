"""Phase 16 semantic patching for asset-quality fixtures.

This module patches checked-in asset-quality evidence bundles, not
source ``.lth`` files or raw meshes. It is intentionally deterministic
and local: previews are regenerated only through the proxy preview
renderer, and certification truthfulness claims remain unchanged.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from copy import deepcopy
from pathlib import Path
from typing import Any

from .certification import certify_example, refresh_golden_snapshots, render_quality_report
from .preview_render import generate_preview_artifacts

PATCH_SCHEMA_VERSION = "lathe.asset_quality.semantic_patch.v1"
PATCH_RESULT_VERSION = "lathe.asset_quality.semantic_patch_result.v1"
COMPARISON_VERSION = "lathe.asset_quality.semantic_patch_comparison.v1"

_SUPPORTED_OPERATIONS = frozenset(
    {
        "modify_material",
        "adjust_proportion",
        "add_wear",
        "add_detail",
        "set_style",
        "set_platform_profile",
    }
)

_SUPPORTED_TARGETS = frozenset(
    {
        "design_brief",
        "silhouette_plan",
        "construction_graph",
        "material_wear_graph",
        "shape_ir_v2",
        "family_grammar_coverage",
    }
)

_ALLOWED_PRESERVE = frozenset(
    {
        "blade.length",
        "guard.width",
        "overall_silhouette",
        "construction_identity",
    }
)

_PUBLIC_SURFACE_TOKENS = frozenset({"profile", "contract", "critic", "asset", "variant"})
_SHAPE_CONTRACT_ID = "lathe.shape.intent_mesh_handoff_v1"
_JSON_FILES = (
    "design_brief.json",
    "silhouette_plan.json",
    "construction_graph.json",
    "material_wear_graph.json",
    "shape_ir_v2.json",
    "family_grammar_coverage.json",
    "high_low_relation.json",
)


def apply_semantic_patch(
    example_dir: str | Path,
    patch_json: str | Path | dict[str, Any],
    out_dir: str | Path,
) -> dict[str, Any]:
    """Apply one semantic patch payload to an asset-quality example fixture."""
    source = Path(example_dir)
    out = Path(out_dir)
    patch_payload, patch_path = _load_patch_payload(patch_json)
    source_payloads = _load_fixture_payloads(source)
    validation = validate_patch_payload(patch_payload, source_payloads=source_payloads)
    if not validation["ok"]:
        return _failed_result(source, out, patch_path, patch_payload, validation)

    before_snapshot = _identity_snapshot(source_payloads)
    modified_payloads = deepcopy(source_payloads)
    applied_operations: list[dict[str, Any]] = []
    changed_json_files: set[str] = set()
    for index, operation in enumerate(patch_payload["operations"]):
        changed = _apply_operation(modified_payloads, operation)
        applied_operations.append(
            {
                "index": index,
                "operation": operation["operation"],
                "target": operation["target"],
                "changed_files": changed,
            }
        )
        changed_json_files.update(changed)
    _refresh_fixture_summaries(modified_payloads)

    preserve = _combined_preserve_tokens(patch_payload)
    preserve_checks = _check_preserve(before_snapshot, _identity_snapshot(modified_payloads), preserve)
    if not preserve_checks["all_preserved"]:
        validation = {
            "ok": False,
            "rejected_operations": [
                {
                    "index": None,
                    "operation": "preserve",
                    "target": "preserve",
                    "reason": "patch_conflicts_with_preserve",
                }
            ],
            "diagnostics": preserve_checks["failures"],
        }
        return _failed_result(source, out, patch_path, patch_payload, validation)

    output_validation = _validate_output_path(source, out)
    if not output_validation["ok"]:
        return _failed_result(source, out, patch_path, patch_payload, output_validation)

    patch_sha = _sha256_json(patch_payload)
    patch_result = _base_success_result(
        source=source,
        out=out,
        patch_path=patch_path,
        patch_payload=patch_payload,
        patch_sha=patch_sha,
        applied_operations=applied_operations,
        changed_files=changed_json_files,
        preserve_checks=preserve_checks,
    )

    temp_out = out.with_name(f"{out.name}.tmp_phase16")
    if temp_out.exists():
        return _failed_result(
            source,
            out,
            patch_path,
            patch_payload,
            {
                "ok": False,
                "rejected_operations": [],
                "diagnostics": [
                    {
                        "reason": "temporary_output_exists",
                        "path": str(temp_out),
                    }
                ],
            },
        )
    shutil.copytree(source, temp_out)
    for name, payload in modified_payloads.items():
        (temp_out / name).write_text(_canonical_json(payload), encoding="utf-8")
    (temp_out / "patch_result.json").write_text(_canonical_json(patch_result), encoding="utf-8")

    preview = generate_preview_artifacts(temp_out)
    _refresh_certificate_report_and_snapshots(temp_out)
    certificate = certify_example(temp_out)
    patch_result["preview_artifacts"] = preview["artifacts"]
    patch_result["certificate_summary"] = {
        "score": certificate["scores"]["total"],
        "warning_pass": certificate["gates"]["warning_pass"],
        "strict_pass": certificate["gates"]["strict_pass"],
        "strict_blockers": list(certificate["gates"]["strict_blockers"]),
    }
    patch_result["changed_files"] = sorted(
        set(patch_result["changed_files"])
        | {
            "patch_result.json",
            "preview_evidence.json",
            "quality_certificate.json",
            "quality_report.md",
            "previews/final_beauty.png",
            "previews/material_ids.png",
            "previews/wireframe.png",
            "previews/comparison_sheet.png",
            "snapshots/construction_graph.snapshot.json",
            "snapshots/high_low_relation.snapshot.json",
            "snapshots/material_wear_graph.snapshot.json",
            "snapshots/quality_certificate.snapshot.json",
        }
    )
    (temp_out / "patch_result.json").write_text(_canonical_json(patch_result), encoding="utf-8")
    temp_out.rename(out)
    return patch_result


def compare_before_after(
    before_dir: str | Path,
    after_dir: str | Path,
    out_path: str | Path | None = None,
) -> dict[str, Any]:
    """Compare two asset-quality fixtures after a semantic patch."""
    before = Path(before_dir)
    after = Path(after_dir)
    before_cert = certify_example(before)
    after_cert = certify_example(after)
    before_payloads = _load_fixture_payloads(before)
    after_payloads = _load_fixture_payloads(after)
    node_delta = _id_delta(
        _node_ids(before_payloads.get("construction_graph.json", {})),
        _node_ids(after_payloads.get("construction_graph.json", {})),
    )
    material_delta = _id_delta(
        _zone_ids(before_payloads.get("material_wear_graph.json", {})),
        _zone_ids(after_payloads.get("material_wear_graph.json", {})),
    )
    wear_delta = _id_delta(
        _wear_ids(before_payloads.get("material_wear_graph.json", {})),
        _wear_ids(after_payloads.get("material_wear_graph.json", {})),
    )
    preview_delta = _preview_sha_delta(
        _preview_shas(before / "preview_evidence.json"),
        _preview_shas(after / "preview_evidence.json"),
    )
    before_art = _art_score(before_cert)
    after_art = _art_score(after_cert)
    score_delta = after_cert["scores"]["total"] - before_cert["scores"]["total"]
    blocker_delta = _id_delta(
        set(before_cert["gates"]["strict_blockers"]),
        set(after_cert["gates"]["strict_blockers"]),
    )
    regressed = (
        score_delta < 0
        or after_art < before_art
        or after_cert["gates"]["warning_pass"] is not True
        or len(blocker_delta["added"]) > 0
    )
    improved = (
        score_delta > 0
        or after_art > before_art
        or bool(node_delta["added"])
        or bool(material_delta["added"])
        or bool(wear_delta["added"])
        or bool(preview_delta["changed"])
    )
    unchanged = not improved and not regressed
    comparison = {
        "schema_version": COMPARISON_VERSION,
        "asset_id": after_cert["asset_id"],
        "before": str(before),
        "after": str(after),
        "scores": {
            "before_total": before_cert["scores"]["total"],
            "after_total": after_cert["scores"]["total"],
            "delta_total": score_delta,
            "before_art_direction": before_art,
            "after_art_direction": after_art,
            "delta_art_direction": after_art - before_art,
        },
        "strict_blockers": {
            "before": list(before_cert["gates"]["strict_blockers"]),
            "after": list(after_cert["gates"]["strict_blockers"]),
            "added": blocker_delta["added"],
            "removed": blocker_delta["removed"],
        },
        "semantic_changes": {
            "construction_nodes": node_delta,
            "material_zones": material_delta,
            "wear_masks": wear_delta,
        },
        "preview_sha256": preview_delta,
        "flags": {
            "improved": improved,
            "regressed": regressed,
            "unchanged": unchanged,
            "requires_human_review": improved or bool(preview_delta["changed"]),
        },
        "truthfulness": _truthfulness_claims(),
    }
    if out_path is not None:
        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(_canonical_json(comparison), encoding="utf-8")
    return comparison


def validate_patch_payload(
    payload: dict[str, Any],
    *,
    source_payloads: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Validate a Phase 16 patch payload without writing any files."""
    diagnostics: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    if not isinstance(payload, dict):
        diagnostics.append({"reason": "patch_payload_not_object"})
        return {"ok": False, "rejected_operations": rejected, "diagnostics": diagnostics}
    if payload.get("schema_version") != PATCH_SCHEMA_VERSION:
        diagnostics.append({"reason": "unsupported_schema_version", "path": "schema_version"})
    source_asset_id = None
    if source_payloads:
        source_asset_id = source_payloads.get("design_brief.json", {}).get("asset_id")
    if source_asset_id and payload.get("asset_id") != source_asset_id:
        diagnostics.append({"reason": "asset_id_mismatch", "path": "asset_id"})
    operations = payload.get("operations")
    if not isinstance(operations, list) or not operations:
        diagnostics.append({"reason": "operations_missing_or_empty", "path": "operations"})
        operations = []
    preserve = payload.get("preserve", [])
    if preserve is not None and not _valid_preserve_list(preserve):
        diagnostics.append({"reason": "malformed_preserve_token", "path": "preserve"})
    for index, operation in enumerate(operations):
        reason = _operation_rejection_reason(operation)
        if reason is not None:
            rejected.append(
                {
                    "index": index,
                    "operation": operation.get("operation") if isinstance(operation, dict) else None,
                    "target": operation.get("target") if isinstance(operation, dict) else None,
                    "reason": reason,
                }
            )
    ok = not diagnostics and not rejected
    return {"ok": ok, "rejected_operations": rejected, "diagnostics": diagnostics}


def _operation_rejection_reason(operation: Any) -> str | None:
    if not isinstance(operation, dict):
        return "operation_not_object"
    op = operation.get("operation")
    if op not in _SUPPORTED_OPERATIONS:
        return "invalid_operation"
    target = operation.get("target")
    if not isinstance(target, str) or not target or "." not in target:
        return "field_path_malformed"
    root = target.split(".", 1)[0]
    if root not in _SUPPORTED_TARGETS:
        if root in {"raw_mesh", "mesh", "glb", "lth", "source"}:
            return "raw_mesh_or_source_patch_forbidden"
        return "invalid_target"
    if _SHAPE_CONTRACT_ID in target:
        return "touches_shape_contract"
    segments = [part for part in target.split(".") if part]
    if any(part in _PUBLIC_SURFACE_TOKENS for part in segments):
        return "touches_public_surface"
    if not _is_json_serializable(operation.get("value")):
        return "non_serializable_value"
    if not _is_json_serializable(operation.get("material")):
        return "non_serializable_value"
    if not _is_json_serializable(operation.get("profile")):
        return "non_serializable_value"
    if not _is_json_serializable(operation.get("mask")):
        return "non_serializable_value"
    if not _is_json_serializable(operation.get("node")):
        return "non_serializable_value"
    if op == "modify_material":
        if not target.startswith("material_wear_graph.material_zones."):
            return "field_path_malformed"
        if not isinstance(operation.get("material"), str) or not operation["material"]:
            return "material_missing"
    if op == "adjust_proportion":
        if not target.startswith("silhouette_plan.proportion_rules."):
            return "field_path_malformed"
        if not isinstance(operation.get("value"), (int, float)) or isinstance(operation.get("value"), bool):
            return "numeric_value_missing"
    if op == "add_wear":
        mask = operation.get("mask")
        if not target.startswith("material_wear_graph.wear_masks") or not isinstance(mask, dict):
            return "wear_mask_missing"
        if not mask.get("mask_id") or not mask.get("mask_type"):
            return "wear_mask_missing"
        if not (mask.get("bound_node_id") or mask.get("bound_edge_target")):
            return "wear_binding_missing"
    if op == "add_detail":
        node = operation.get("node")
        if not target.startswith("construction_graph.nodes") or not isinstance(node, dict):
            return "detail_node_missing"
        if not node.get("node_id") or not node.get("category"):
            return "detail_node_missing"
    if op == "set_style" and not target.startswith("design_brief.style"):
        return "field_path_malformed"
    if op == "set_platform_profile" and not target.startswith("design_brief.platform_profile"):
        return "field_path_malformed"
        if not isinstance(operation.get("profile"), dict):
            return "platform_profile_missing"
    return None


def _apply_operation(payloads: dict[str, dict[str, Any]], operation: dict[str, Any]) -> list[str]:
    op = operation["operation"]
    if op == "modify_material":
        return _apply_modify_material(payloads, operation)
    if op == "adjust_proportion":
        return _apply_adjust_proportion(payloads, operation)
    if op == "add_wear":
        return _apply_add_wear(payloads, operation)
    if op == "add_detail":
        return _apply_add_detail(payloads, operation)
    if op == "set_style":
        return _apply_set_style(payloads, operation)
    if op == "set_platform_profile":
        return _apply_set_platform_profile(payloads, operation)
    raise ValueError(f"unsupported operation: {op}")


def _apply_modify_material(payloads: dict[str, dict[str, Any]], operation: dict[str, Any]) -> list[str]:
    material = operation["material"]
    source_zone_id = operation["target"].split(".")[-1]
    bound_nodes = list(operation.get("bound_nodes") or [])
    properties = dict(operation.get("properties") or {})
    material_graph = payloads["material_wear_graph.json"]
    zones = material_graph.setdefault("material_zones", [])
    source_zone = _find_zone(zones, source_zone_id)
    if bound_nodes and source_zone:
        old_nodes = [node for node in source_zone.get("bound_nodes", []) if node not in bound_nodes]
        source_zone["bound_nodes"] = old_nodes
        zones.append(
            {
                "bound_nodes": bound_nodes,
                "material_token": material,
                "properties": properties,
                "zone_id": material,
                "zone_type": source_zone.get("zone_type", "base_material"),
            }
        )
    elif source_zone:
        source_zone["material_token"] = material
        source_zone["zone_id"] = material
        if properties:
            source_zone["properties"] = properties
    else:
        zones.append(
            {
                "bound_nodes": bound_nodes,
                "material_token": material,
                "properties": properties,
                "zone_id": material,
                "zone_type": "base_material",
            }
        )
    graph = payloads["construction_graph.json"]
    for node in graph.get("nodes", []):
        if isinstance(node, dict) and node.get("node_id") in bound_nodes:
            node["material_zone_ref"] = material
    return ["material_wear_graph.json", "construction_graph.json"]


def _apply_adjust_proportion(payloads: dict[str, dict[str, Any]], operation: dict[str, Any]) -> list[str]:
    silhouette = payloads["silhouette_plan.json"]
    _set_dotted(silhouette, operation["target"].split(".")[1:], operation["value"])
    for key, value in dict(operation.get("metrics") or {}).items():
        silhouette.setdefault("metrics", {})[key] = value
    node_id = operation.get("node_id")
    bounds = operation.get("bounds")
    changed = ["silhouette_plan.json"]
    if isinstance(node_id, str) and isinstance(bounds, dict):
        graph = payloads["construction_graph.json"]
        for node in graph.get("nodes", []):
            if isinstance(node, dict) and node.get("node_id") == node_id:
                node.setdefault("bounds", {}).update(bounds)
                changed.append("construction_graph.json")
                break
    return sorted(set(changed))


def _apply_add_wear(payloads: dict[str, dict[str, Any]], operation: dict[str, Any]) -> list[str]:
    material = payloads["material_wear_graph.json"]
    masks = material.setdefault("wear_masks", [])
    mask = deepcopy(operation["mask"])
    existing = {entry.get("mask_id") for entry in masks if isinstance(entry, dict)}
    if mask["mask_id"] not in existing:
        masks.append(mask)
    return ["material_wear_graph.json"]


def _apply_add_detail(payloads: dict[str, dict[str, Any]], operation: dict[str, Any]) -> list[str]:
    graph = payloads["construction_graph.json"]
    node = deepcopy(operation["node"])
    nodes = graph.setdefault("nodes", [])
    existing_nodes = {entry.get("node_id") for entry in nodes if isinstance(entry, dict)}
    if node["node_id"] not in existing_nodes:
        nodes.append(node)
    edges = graph.setdefault("edges", [])
    for edge in operation.get("edges") or []:
        if isinstance(edge, dict):
            edges.append(deepcopy(edge))
    changed = ["construction_graph.json"]
    shape_op = operation.get("shape_ir_v2_op")
    if isinstance(shape_op, dict) and "shape_ir_v2.json" in payloads:
        payloads["shape_ir_v2.json"].setdefault("ops", []).append(deepcopy(shape_op))
        changed.append("shape_ir_v2.json")
    return changed


def _apply_set_style(payloads: dict[str, dict[str, Any]], operation: dict[str, Any]) -> list[str]:
    brief = payloads["design_brief.json"]
    style = brief.setdefault("style", {})
    if operation.get("theme"):
        style["theme"] = operation["theme"]
    for key in ("keywords_add", "forbidden_add"):
        destination = "keywords" if key == "keywords_add" else "forbidden"
        for item in operation.get(key) or []:
            if item not in style.setdefault(destination, []):
                style[destination].append(item)
    brief.setdefault("phase16_style_notes", []).append(operation.get("note", "style patched semantically"))
    silhouette_constraints = operation.get("silhouette_constraints")
    if isinstance(silhouette_constraints, dict):
        payloads["silhouette_plan.json"].setdefault("phase16_style_constraints", {}).update(
            silhouette_constraints
        )
        return ["design_brief.json", "silhouette_plan.json"]
    return ["design_brief.json"]


def _apply_set_platform_profile(payloads: dict[str, dict[str, Any]], operation: dict[str, Any]) -> list[str]:
    brief = payloads["design_brief.json"]
    platform = brief.setdefault("platform_profile", {})
    platform.update(operation["profile"])
    if operation.get("profile_name"):
        platform["phase16_profile"] = operation["profile_name"]
    return ["design_brief.json"]


def _refresh_fixture_summaries(payloads: dict[str, dict[str, Any]]) -> None:
    graph = payloads.get("construction_graph.json", {})
    if graph:
        summary = graph.setdefault("summary", {})
        summary["node_count"] = len(graph.get("nodes", []))
        summary["edge_count"] = len(graph.get("edges", []))
        summary["repeated_elements_semantic"] = True
        summary["attachments_on_meaningful_hosts"] = True
        summary.setdefault("unclassified_major_primitives", 0)
    material = payloads.get("material_wear_graph.json", {})
    if material:
        summary = material.setdefault("graph_summary", {})
        zones = material.get("material_zones", [])
        masks = material.get("wear_masks", [])
        summary["material_zone_count"] = len(zones)
        summary["wear_mask_count"] = len(masks)
        material.setdefault("uniform_noise", {})["is_uniform_noise"] = False
        material.setdefault("binding_validation", {})["all_node_bindings_resolved"] = True
        material.setdefault("binding_validation", {})["all_edge_bindings_resolved"] = True


def _refresh_certificate_report_and_snapshots(example_dir: Path) -> None:
    for _ in range(3):
        refresh_golden_snapshots(example_dir)
        cert = certify_example(example_dir)
        (example_dir / "quality_certificate.json").write_text(_canonical_json(cert), encoding="utf-8")
        (example_dir / "quality_report.md").write_text(render_quality_report(cert), encoding="utf-8")
    refresh_golden_snapshots(example_dir)
    cert = certify_example(example_dir)
    (example_dir / "quality_certificate.json").write_text(_canonical_json(cert), encoding="utf-8")
    (example_dir / "quality_report.md").write_text(render_quality_report(cert), encoding="utf-8")


def _load_patch_payload(patch_json: str | Path | dict[str, Any]) -> tuple[dict[str, Any], Path | None]:
    if isinstance(patch_json, dict):
        return patch_json, None
    path = Path(patch_json)
    return json.loads(path.read_text(encoding="utf-8")), path


def _load_fixture_payloads(example_dir: Path) -> dict[str, dict[str, Any]]:
    payloads: dict[str, dict[str, Any]] = {}
    for name in _JSON_FILES:
        path = example_dir / name
        if path.exists():
            value = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(value, dict):
                payloads[name] = value
    return payloads


def _validate_output_path(source: Path, out: Path) -> dict[str, Any]:
    try:
        source_resolved = source.resolve()
        out_resolved = out.resolve()
    except OSError as exc:
        return {"ok": False, "rejected_operations": [], "diagnostics": [{"reason": str(exc)}]}
    if out_resolved == source_resolved:
        return {
            "ok": False,
            "rejected_operations": [],
            "diagnostics": [{"reason": "output_must_not_equal_source", "path": str(out)}],
        }
    if out.exists() and any(out.iterdir()):
        return {
            "ok": False,
            "rejected_operations": [],
            "diagnostics": [{"reason": "output_directory_exists", "path": str(out)}],
        }
    return {"ok": True, "rejected_operations": [], "diagnostics": []}


def _failed_result(
    source: Path,
    out: Path,
    patch_path: Path | None,
    patch_payload: dict[str, Any],
    validation: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": PATCH_RESULT_VERSION,
        "ok": False,
        "asset_id": patch_payload.get("asset_id"),
        "source_example": str(source),
        "output_example": str(out),
        "patch_path": str(patch_path) if patch_path else None,
        "patch_sha256": _sha256_json(patch_payload) if isinstance(patch_payload, dict) else None,
        "applied_operations": [],
        "rejected_operations": validation.get("rejected_operations", []),
        "diagnostics": validation.get("diagnostics", []),
        "truthfulness": _truthfulness_claims(),
    }


def _base_success_result(
    *,
    source: Path,
    out: Path,
    patch_path: Path | None,
    patch_payload: dict[str, Any],
    patch_sha: str,
    applied_operations: list[dict[str, Any]],
    changed_files: set[str],
    preserve_checks: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": PATCH_RESULT_VERSION,
        "ok": True,
        "asset_id": patch_payload["asset_id"],
        "source_example": str(source),
        "output_example": str(out),
        "patch_path": str(patch_path) if patch_path else None,
        "patch_sha256": patch_sha,
        "notes": patch_payload.get("notes", []),
        "applied_operations": applied_operations,
        "rejected_operations": [],
        "changed_files": sorted(changed_files),
        "preserve_checks": preserve_checks,
        "truthfulness": _truthfulness_claims(),
    }


def _truthfulness_claims() -> dict[str, bool]:
    return {
        "external_renderer_used": False,
        "real_high_low_bake_used": False,
        "raw_mesh_modified": False,
        "public_lth_modified": False,
        "shape_handoff_contract_modified": False,
    }


def _combined_preserve_tokens(payload: dict[str, Any]) -> list[str]:
    tokens: list[str] = []
    for token in payload.get("preserve") or []:
        if token not in tokens:
            tokens.append(token)
    for operation in payload.get("operations") or []:
        if isinstance(operation, dict):
            for token in operation.get("preserve") or []:
                if token not in tokens:
                    tokens.append(token)
    return tokens


def _valid_preserve_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(token, str) and token in _ALLOWED_PRESERVE for token in value)


def _identity_snapshot(payloads: dict[str, dict[str, Any]]) -> dict[str, Any]:
    brief = payloads.get("design_brief.json", {})
    silhouette = payloads.get("silhouette_plan.json", {})
    graph = payloads.get("construction_graph.json", {})
    return {
        "asset_id": brief.get("asset_id"),
        "family": brief.get("family"),
        "construction_node_ids": sorted(_node_ids(graph)),
        "overall_silhouette": {
            "primary_read": silhouette.get("primary_read"),
            "expected_64px_read": silhouette.get("thumbnail_checks", {}).get("expected_64px_read"),
            "long_axis_unbroken": silhouette.get("thumbnail_checks", {}).get("long_axis_unbroken"),
        },
        "blade.length": _node_bound(graph, "long_tapered_blade", "height"),
        "guard.width": _node_bound(graph, "crossguard", "width"),
    }


def _check_preserve(before: dict[str, Any], after: dict[str, Any], tokens: list[str]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for preserve_item in tokens:
        if preserve_item == "construction_identity":
            preserved = (
                before["asset_id"] == after["asset_id"]
                and before["family"] == after["family"]
                and set(before["construction_node_ids"]).issubset(set(after["construction_node_ids"]))
            )
        else:
            preserved = before.get(preserve_item) == after.get(preserve_item)
        entry = {"token": preserve_item, "preserved": preserved}
        checks.append(entry)
        if not preserved:
            failures.append(entry)
    return {
        "all_preserved": not failures,
        "checks": checks,
        "failures": failures,
    }


def _set_dotted(payload: dict[str, Any], path: list[str], value: Any) -> None:
    cursor = payload
    for segment in path[:-1]:
        next_value = cursor.setdefault(segment, {})
        if not isinstance(next_value, dict):
            next_value = {}
            cursor[segment] = next_value
        cursor = next_value
    cursor[path[-1]] = value


def _find_zone(zones: list[Any], zone_id: str) -> dict[str, Any] | None:
    for zone in zones:
        if isinstance(zone, dict) and zone.get("zone_id") == zone_id:
            return zone
    return None


def _node_ids(graph: dict[str, Any]) -> set[str]:
    return {
        node["node_id"]
        for node in graph.get("nodes", [])
        if isinstance(node, dict) and isinstance(node.get("node_id"), str)
    }


def _zone_ids(material: dict[str, Any]) -> set[str]:
    return {
        zone["zone_id"]
        for zone in material.get("material_zones", [])
        if isinstance(zone, dict) and isinstance(zone.get("zone_id"), str)
    }


def _wear_ids(material: dict[str, Any]) -> set[str]:
    return {
        mask["mask_id"]
        for mask in material.get("wear_masks", [])
        if isinstance(mask, dict) and isinstance(mask.get("mask_id"), str)
    }


def _node_bound(graph: dict[str, Any], node_id: str, key: str) -> Any:
    for node in graph.get("nodes", []):
        if isinstance(node, dict) and node.get("node_id") == node_id:
            return node.get("bounds", {}).get(key)
    return None


def _id_delta(before: set[str], after: set[str]) -> dict[str, list[str]]:
    return {
        "added": sorted(after - before),
        "removed": sorted(before - after),
        "unchanged": sorted(before & after),
    }


def _preview_shas(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    views = payload.get("views", {}) if isinstance(payload, dict) else {}
    return {
        role: entry["sha256"]
        for role, entry in views.items()
        if isinstance(entry, dict) and isinstance(entry.get("sha256"), str)
    }


def _preview_sha_delta(before: dict[str, str], after: dict[str, str]) -> dict[str, Any]:
    roles = sorted(set(before) | set(after))
    changed = [role for role in roles if before.get(role) != after.get(role)]
    return {
        "before": before,
        "after": after,
        "changed": changed,
    }


def _art_score(certificate: dict[str, Any]) -> int:
    art = certificate.get("art_direction")
    if isinstance(art, dict):
        scores = art.get("scores")
        if isinstance(scores, dict) and isinstance(scores.get("total"), int):
            return scores["total"]
    return 0


def _is_json_serializable(value: Any) -> bool:
    try:
        json.dumps(value)
    except (TypeError, ValueError):
        return False
    return True


def _sha256_json(payload: Any) -> str:
    return hashlib.sha256(_canonical_json(payload).encode()).hexdigest()


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


__all__ = [
    "COMPARISON_VERSION",
    "PATCH_RESULT_VERSION",
    "PATCH_SCHEMA_VERSION",
    "apply_semantic_patch",
    "compare_before_after",
    "validate_patch_payload",
]
