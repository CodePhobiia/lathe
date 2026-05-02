"""Aggregate nested child asset builds into parent-consumable assemblies."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

NESTED_ASSEMBLY_MANIFEST_VERSION = "lathe.nested_asset_assembly.v1"


def nested_assembly_manifest(
    *,
    parent_asset_name: str,
    parent_source_path: str,
    parent_metadata_path: str,
    parent_build: Mapping[str, Any] | None,
    nested_assets: Mapping[str, Any] | None,
    package_root: Path,
) -> dict[str, Any]:
    """Build a parent-facing assembly payload from nested child build outputs."""
    nested = nested_assets if isinstance(nested_assets, Mapping) else {}
    assets = [asset for asset in nested.get("assets", []) or [] if isinstance(asset, Mapping)]
    children = [
        _child_entry(asset, package_root=package_root, parent_asset_name=parent_asset_name)
        for asset in assets
    ]
    attachments = [_attachment_entry(child) for child in children]
    parent_outputs = _build_outputs(parent_build, package_root=package_root)
    built_children = [child for child in children if child.get("build", {}).get("ok")]
    manifest = {
        "schema_version": NESTED_ASSEMBLY_MANIFEST_VERSION,
        "parent_asset_name": parent_asset_name,
        "parent_source_path": parent_source_path,
        "parent_metadata_path": parent_metadata_path,
        "parent_build": dict(parent_build or {}),
        "parent_outputs": parent_outputs,
        "children": children,
        "attachments": attachments,
        "build_graph": dict(nested.get("build_graph") or {}),
        "aggregate_package": {
            "assembly_id": f"{parent_asset_name}_nested_assembly",
            "parent_asset": parent_asset_name,
            "primary_parent_outputs": parent_outputs,
            "child_output_count": sum(len(child.get("outputs", [])) for child in children),
            "built_child_count": len(built_children),
            "child_asset_names": [str(child.get("asset_name") or "") for child in children],
            "build_order": [parent_asset_name, *[str(child.get("asset_name") or "") for child in children]],
            "package_roots": _package_roots(parent_build, children),
        },
        "summary": {
            "child_count": len(children),
            "built_child_count": len(built_children),
            "failed_child_count": len(children) - len(built_children),
            "attachment_count": len(attachments),
            "parent_output_count": len(parent_outputs),
            "child_output_count": sum(len(child.get("outputs", [])) for child in children),
        },
    }
    manifest["consumable"] = {
        "ready": bool(parent_build and parent_build.get("ok")) and len(built_children) == len(children),
        "kind": "nested_asset_subassembly",
        "root": parent_asset_name,
        "children": [
            {
                "asset_name": child.get("asset_name"),
                "slot_id": child.get("slot_id"),
                "outputs": child.get("outputs", []),
                "local_transform": child.get("placement", {}).get("local_transform"),
            }
            for child in children
        ],
    }
    return manifest


def _child_entry(
    asset: Mapping[str, Any],
    *,
    package_root: Path,
    parent_asset_name: str,
) -> dict[str, Any]:
    build = dict(asset.get("build") or {}) if isinstance(asset.get("build"), Mapping) else {}
    package = dict(asset.get("package") or {}) if isinstance(asset.get("package"), Mapping) else {}
    placement = dict(asset.get("placement") or {}) if isinstance(asset.get("placement"), Mapping) else {}
    dependency = dict(asset.get("dependency") or {}) if isinstance(asset.get("dependency"), Mapping) else {}
    outputs = _build_outputs(build, package_root=package_root)
    package_manifest = _package_manifest(build, package, package_root=package_root)
    return {
        "asset_name": str(asset.get("asset_name") or ""),
        "asset_kind": str(asset.get("asset_kind") or ""),
        "family": str(asset.get("family") or ""),
        "instance_id": str(asset.get("instance_id") or ""),
        "slot_id": str(asset.get("slot_id") or ""),
        "slot_kind": str(asset.get("slot_kind") or ""),
        "template": str(asset.get("template") or ""),
        "source_path": str(asset.get("source_path") or ""),
        "metadata_path": str(asset.get("metadata_path") or package.get("metadata_path") or ""),
        "placement": placement,
        "dependency": dependency or {
            "from": parent_asset_name,
            "to": str(asset.get("asset_name") or ""),
            "relation": "attached_to",
        },
        "package": package,
        "build": build,
        "outputs": outputs,
        "package_manifest": package_manifest,
        "consumable_outputs": _consumable_outputs(outputs, package_manifest),
    }


def _attachment_entry(child: Mapping[str, Any]) -> dict[str, Any]:
    placement = child.get("placement") if isinstance(child.get("placement"), Mapping) else {}
    attach = placement.get("attach") if isinstance(placement.get("attach"), Mapping) else {}
    return {
        "id": f"{child.get('asset_name')}_to_{child.get('slot_id')}",
        "parent_asset_name": placement.get("parent_asset_name"),
        "child_asset_name": child.get("asset_name"),
        "slot_id": child.get("slot_id"),
        "slot_kind": child.get("slot_kind"),
        "parent_endpoint": attach.get("parent_endpoint"),
        "child_endpoint": attach.get("child_endpoint"),
        "local_transform": placement.get("local_transform"),
        "local_position": placement.get("local_position"),
        "local_rotation_degrees": placement.get("local_rotation_degrees"),
        "snap": dict(placement.get("snap") or {}) if isinstance(placement.get("snap"), Mapping) else {},
    }


def _build_outputs(build: Mapping[str, Any] | None, *, package_root: Path) -> list[dict[str, Any]]:
    if not isinstance(build, Mapping):
        return []
    report_path = build.get("report_path")
    if not isinstance(report_path, str) or not report_path:
        return []
    report = _read_json(package_root / report_path)
    outputs = report.get("outputs") if isinstance(report, Mapping) else []
    if not isinstance(outputs, list):
        return []
    return [
        {
            "uri": str(output.get("uri") or ""),
            "format": str(output.get("format") or ""),
            "sha256": str(output.get("sha256") or ""),
        }
        for output in outputs
        if isinstance(output, Mapping) and output.get("uri")
    ]


def _package_manifest(
    build: Mapping[str, Any],
    package: Mapping[str, Any],
    *,
    package_root: Path,
) -> dict[str, Any]:
    candidates = [
        package.get("package_manifest_path"),
        _package_manifest_path_from_build(build),
    ]
    for candidate in candidates:
        if not isinstance(candidate, str) or not candidate:
            continue
        manifest = _read_json(package_root / candidate)
        if manifest:
            return {
                "path": candidate,
                "asset_id": manifest.get("asset_id"),
                "kind": manifest.get("kind"),
                "formats": list(manifest.get("formats") or []),
                "outputs": list(manifest.get("outputs") or []),
                "nested_assets": dict(manifest.get("nested_assets") or {})
                if isinstance(manifest.get("nested_assets"), Mapping)
                else {},
            }
    return {}


def _package_manifest_path_from_build(build: Mapping[str, Any]) -> str:
    out_dir = build.get("out_dir")
    if not isinstance(out_dir, str) or not out_dir:
        return ""
    return f"{out_dir}/stages/package/package_manifest.json"


def _consumable_outputs(
    outputs: Sequence[Mapping[str, Any]],
    package_manifest: Mapping[str, Any],
) -> list[dict[str, Any]]:
    manifest_outputs = package_manifest.get("outputs") if isinstance(package_manifest.get("outputs"), list) else []
    combined = [*outputs, *[item for item in manifest_outputs if isinstance(item, Mapping)]]
    seen: set[str] = set()
    consumable: list[dict[str, Any]] = []
    for output in combined:
        uri = str(output.get("uri") or "")
        fmt = str(output.get("format") or "")
        if not uri or uri in seen:
            continue
        if fmt and fmt not in {"glb", "gltf", "gltf_resource", "usd", "obj", "game_asset_manifest"}:
            continue
        seen.add(uri)
        consumable.append(
            {
                "uri": uri,
                "format": fmt,
                "sha256": str(output.get("sha256") or ""),
            }
        )
    return consumable


def _package_roots(parent_build: Mapping[str, Any] | None, children: Sequence[Mapping[str, Any]]) -> list[str]:
    roots: list[str] = []
    if isinstance(parent_build, Mapping) and isinstance(parent_build.get("out_dir"), str):
        roots.append(parent_build["out_dir"])
    for child in children:
        build = child.get("build") if isinstance(child.get("build"), Mapping) else {}
        out_dir = build.get("out_dir")
        if isinstance(out_dir, str) and out_dir not in roots:
            roots.append(out_dir)
    return roots


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return {}
    return payload if isinstance(payload, dict) else {}
