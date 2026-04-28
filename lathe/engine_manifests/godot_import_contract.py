"""Static validation for the in-repo Godot addon import workflow.

The Godot addon has two relevant consumers today:

* ``lathe_importer.gd`` watches ``stages/package/package_manifest.json``,
  finds the first ``outputs[]`` entry with ``format == "glb"``, verifies the
  file exists, loads it with ``GLTFDocument``, and reads certification values
  from the sibling ``build_report.json``.
* ``editor_import_plugin.gd`` imports optional ``.lathe_snapshot.json``
  sidecars and resolves the same package manifest GLB entry for Resource meta.

This module intentionally validates that current consumer contract instead of
guessing at a future headless Godot pipeline.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..paths import PathGuardError, safe_resolve

_PACKAGE_MANIFEST = Path("stages") / "package" / "package_manifest.json"


def validate_godot_import_contract(build_dir: str | Path) -> dict[str, Any]:
    """Validate a built asset against the current Godot addon import contract.

    The check is static and does not launch Godot. It verifies the exact files
    and fields the GDScript importer reads, then cross-checks the emitted Godot
    engine manifest sidecar against packaged artifact paths.
    """
    root = Path(build_dir)
    diagnostics: list[dict[str, Any]] = []
    evidence: dict[str, Any] = {
        "build_dir": str(root),
        "package_manifest": str(_PACKAGE_MANIFEST),
        "addon_consumers": [
            "editors/godot/lathe-addon/lathe_importer.gd",
            "editors/godot/lathe-addon/editor_import_plugin.gd",
        ],
    }

    package_manifest_path = root / _PACKAGE_MANIFEST
    package_manifest = _read_json_object(package_manifest_path, diagnostics, "LENG001", "package_manifest")
    if package_manifest is None:
        return _report(diagnostics, evidence)

    asset_id = package_manifest.get("asset_id")
    if not isinstance(asset_id, str) or not asset_id:
        _add_diag(
            diagnostics,
            "LENG002",
            "error",
            "stages/package/package_manifest.json must contain a non-empty asset_id for Godot scene naming.",
            str(_PACKAGE_MANIFEST / "asset_id"),
        )
        asset_id = root.name
    evidence["asset_id"] = asset_id

    glb_entry = _first_output_with_format(package_manifest, "glb")
    if glb_entry is None:
        _add_diag(
            diagnostics,
            "LENG003",
            "error",
            "Godot importer requires at least one package outputs[] entry with format == 'glb'.",
            str(_PACKAGE_MANIFEST / "outputs"),
        )
    else:
        glb_uri = glb_entry.get("uri")
        evidence["glb_uri"] = glb_uri
        _validate_artifact_uri(
            root,
            glb_uri,
            diagnostics,
            "LENG004",
            str(_PACKAGE_MANIFEST / "outputs" / "glb" / "uri"),
            expected_suffix=".glb",
        )

    formats = package_manifest.get("formats")
    if isinstance(formats, list) and "glb" not in formats:
        _add_diag(
            diagnostics,
            "LENG005",
            "warning",
            (
                "Package manifest formats[] does not list 'glb' even though "
                "the Godot importer resolves outputs[] directly."
            ),
            str(_PACKAGE_MANIFEST / "formats"),
        )

    _validate_build_report(root, diagnostics)
    _validate_optional_snapshot(root, diagnostics, evidence)
    _validate_godot_engine_manifest(root, asset_id, diagnostics, evidence)
    return _report(diagnostics, evidence)


def _validate_build_report(root: Path, diagnostics: list[dict[str, Any]]) -> None:
    report_path = root / "build_report.json"
    report = _read_json_object(report_path, diagnostics, "LENG006", "build_report")
    if report is None:
        return
    if not isinstance(report.get("certified"), bool):
        _add_diag(
            diagnostics,
            "LENG007",
            "error",
            "Godot dock expects build_report.json certified to be a boolean.",
            "build_report.json/certified",
        )
    for key in ("score", "threshold"):
        if _numeric_report_value(report, key) is None:
            _add_diag(
                diagnostics,
                "LENG009",
                "error",
                f"Godot importer expects build_report.json {key} or certification.{key} to be numeric.",
                f"build_report.json/{key}",
            )


def _validate_optional_snapshot(
    root: Path,
    diagnostics: list[dict[str, Any]],
    evidence: dict[str, Any],
) -> None:
    snapshot_path = root / ".lathe_snapshot.json"
    if not snapshot_path.exists():
        evidence["snapshot_sidecar"] = "absent_optional"
        return
    snapshot = _read_json_object(snapshot_path, diagnostics, "LENG010", "lathe_snapshot")
    if snapshot is None:
        return
    evidence["snapshot_sidecar"] = ".lathe_snapshot.json"
    for key in ("asset_id", "snapshot_hash", "stage_hashes"):
        if key not in snapshot:
            _add_diag(
                diagnostics,
                "LENG011",
                "error",
                (
                    f"Godot snapshot importer reads .lathe_snapshot.json {key}; "
                    "the field must be present when a snapshot is shipped."
                ),
                f".lathe_snapshot.json/{key}",
            )


def _validate_godot_engine_manifest(
    root: Path,
    asset_id: str,
    diagnostics: list[dict[str, Any]],
    evidence: dict[str, Any],
) -> None:
    manifest_rel = Path(f"{asset_id}.lathe_for_godot.json")
    evidence["godot_engine_manifest"] = str(manifest_rel)
    manifest = _read_json_object(root / manifest_rel, diagnostics, "LENG012", "godot_engine_manifest")
    if manifest is None:
        return
    if manifest.get("schemaVersion") != 1:
        _add_diag(
            diagnostics,
            "LENG013",
            "error",
            "Godot engine manifest schemaVersion must be 1.",
            f"{manifest_rel}/schemaVersion",
        )
    if manifest.get("engine") != "godot":
        _add_diag(
            diagnostics,
            "LENG014",
            "error",
            "Godot engine manifest engine must be 'godot'.",
            f"{manifest_rel}/engine",
        )
    if manifest.get("assetName") != asset_id:
        _add_diag(
            diagnostics,
            "LENG015",
            "error",
            "Godot engine manifest assetName must match package manifest asset_id.",
            f"{manifest_rel}/assetName",
        )
    for index, lod in enumerate(manifest.get("lodGroup") or []):
        if not isinstance(lod, dict):
            _add_diag(
                diagnostics,
                "LENG016",
                "error",
                "Godot engine manifest lodGroup entries must be objects.",
                f"{manifest_rel}/lodGroup/{index}",
            )
            continue
        _validate_artifact_uri(
            root,
            lod.get("meshUri"),
            diagnostics,
            "LENG017",
            f"{manifest_rel}/lodGroup/{index}/meshUri",
            expected_suffix=".glb",
        )
    collision = manifest.get("collision")
    shapes = collision.get("shapes") if isinstance(collision, dict) else []
    for index, shape in enumerate(shapes or []):
        if not isinstance(shape, dict):
            _add_diag(
                diagnostics,
                "LENG018",
                "error",
                "Godot engine manifest collision shapes must be objects.",
                f"{manifest_rel}/collision/shapes/{index}",
            )
            continue
        _validate_artifact_uri(
            root,
            shape.get("meshUri"),
            diagnostics,
            "LENG019",
            f"{manifest_rel}/collision/shapes/{index}/meshUri",
            expected_suffix=".glb",
        )


def _read_json_object(
    path: Path,
    diagnostics: list[dict[str, Any]],
    code: str,
    label: str,
) -> dict[str, Any] | None:
    if not path.is_file():
        _add_diag(diagnostics, code, "error", f"Required {label} file is missing.", str(path))
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        _add_diag(diagnostics, code, "error", f"Required {label} file is not valid JSON: {exc}", str(path))
        return None
    if not isinstance(payload, dict):
        _add_diag(diagnostics, code, "error", f"Required {label} JSON root must be an object.", str(path))
        return None
    return payload


def _first_output_with_format(manifest: dict[str, Any], fmt: str) -> dict[str, Any] | None:
    outputs = manifest.get("outputs")
    if not isinstance(outputs, list):
        return None
    for entry in outputs:
        if isinstance(entry, dict) and entry.get("format") == fmt:
            return entry
    return None


def _numeric_report_value(report: dict[str, Any], key: str) -> float | None:
    certification = report.get("certification")
    value = certification.get(key) if isinstance(certification, dict) else None
    if isinstance(value, int | float) and not isinstance(value, bool):
        return float(value)
    value = report.get(key)
    if isinstance(value, int | float) and not isinstance(value, bool):
        return float(value)
    return None


def _validate_artifact_uri(
    root: Path,
    uri: Any,
    diagnostics: list[dict[str, Any]],
    code: str,
    pointer: str,
    *,
    expected_suffix: str | None = None,
) -> None:
    if not isinstance(uri, str) or not uri:
        _add_diag(diagnostics, code, "error", "Artifact URI must be a non-empty relative path.", pointer)
        return
    if "\\" in uri:
        _add_diag(
            diagnostics,
            code,
            "error",
            "Artifact URI must use POSIX '/' separators for Godot resource-path compatibility.",
            pointer,
            details={"uri": uri},
        )
        return
    try:
        resolved = safe_resolve(root, uri)
    except (PathGuardError, TypeError, ValueError, OSError) as exc:
        _add_diag(diagnostics, code, "error", f"Artifact URI is not safe for import: {exc}", pointer)
        return
    if expected_suffix and resolved.suffix.lower() != expected_suffix:
        _add_diag(
            diagnostics,
            code,
            "error",
            f"Artifact URI must point to a {expected_suffix} file.",
            pointer,
            details={"uri": uri},
        )
        return
    if not resolved.is_file():
        _add_diag(
            diagnostics,
            code,
            "error",
            "Artifact URI does not resolve to an existing file under the build directory.",
            pointer,
            details={"uri": uri},
        )


def _add_diag(
    diagnostics: list[dict[str, Any]],
    code: str,
    severity: str,
    message: str,
    path: str,
    *,
    details: dict[str, Any] | None = None,
) -> None:
    diag: dict[str, Any] = {
        "code": code,
        "severity": severity,
        "stage": "package",
        "name": "godot_import_contract",
        "message": message,
        "path": path,
    }
    if details:
        diag["details"] = details
    diagnostics.append(diag)


def _report(diagnostics: list[dict[str, Any]], evidence: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": not any(diag.get("severity") == "error" for diag in diagnostics),
        "diagnostics": diagnostics,
        "evidence": evidence,
    }


__all__ = ["validate_godot_import_contract"]
