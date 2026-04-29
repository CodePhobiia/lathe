"""Golden fixture validation for Wonder examples.

The catalog helpers keep example folders honest without depending on Blender,
Roblox Studio, or any external viewer. They validate committed JSON contracts,
write deterministic proxy/example evidence when requested, and require
generated scene source fixtures to roundtrip through the Scene Graph source
bridge.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from .contracts import CONTRACT_SPECS, validate_contract
from .evidence import WONDER_EVIDENCE_TRACE_VERSION
from .llm import generate_scene_plan

WONDER_EXAMPLE_REPORT_VERSION = "lathe.wonder_example_report.v1"
WONDER_EXAMPLE_CATALOG_VERSION = "lathe.wonder_example_catalog.v1"
SCENE_SOURCE_STATUS_VERSION = "lathe.scene_source_status.v1"
PREVIEW_EVIDENCE_VERSION = "lathe.preview_evidence.v1"

REQUIRED_ROOT_FILES: tuple[tuple[str, str], ...] = (
    ("prompt.txt", "prompt"),
    ("dream_brief.json", "dream_brief"),
    ("scene_graph.json", "scene_graph"),
    ("scene_source.lth", "scene_source"),
    ("world_memory.json", "world_memory"),
    ("scene_patch.example.json", "scene_patch"),
    ("render_inspection.example.json", "render_inspection"),
)
REQUIRED_EXPECTED_FILES: tuple[tuple[str, str], ...] = (
    ("scene_plan.example.json", "scene_plan"),
    ("wonder_report.example.json", "wonder_report"),
    ("scene_manifest.example.json", "scene_manifest"),
    ("render_comparison.example.json", "render_comparison"),
    ("evidence_traceability.example.json", "evidence_traceability"),
    ("preview_evidence.example.json", "preview_evidence"),
)

_TOKEN_RE = re.compile(r"[a-z0-9]{4,}")
_SCENE_SOURCE_DEFERRED_REASON = (
    "Experimental scene source syntax is not complete enough to make this example "
    "a source-of-truth fixture."
)
_SCENE_SOURCE_TRACKING_ADR = "docs/adr/0010-experimental-scene-source-language.md"
_DOC_ROOT_FILES = {name for name, _contract in REQUIRED_ROOT_FILES}
_DOC_EXPECTED_FILES = {name for name, _contract in REQUIRED_EXPECTED_FILES}


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return payload


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def _display_path(path: Path) -> str:
    try:
        return path.resolve(strict=False).relative_to(Path.cwd().resolve(strict=False)).as_posix()
    except ValueError:
        return str(path)


def _json_pointer(*parts: object) -> str:
    escaped = [str(part).replace("~", "~0").replace("/", "~1") for part in parts]
    return "/" + "/".join(escaped) if escaped else "/"


def _diagnostic(
    code: str,
    name: str,
    path: str,
    message: str,
    *,
    severity: str = "error",
    contract: str = "wonder_example",
    details: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "code": code,
        "name": name,
        "severity": severity,
        "contract": contract,
        "phase": "wonder_example_validation",
        "path": path,
        "message": message,
    }
    if details:
        payload["details"] = dict(details)
    return payload


def _contract_result(
    contract: str,
    status: str,
    *,
    path: Path | None = None,
    diagnostics: list[dict[str, Any]] | None = None,
    details: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "contract": contract,
        "status": status,
        "diagnostics": diagnostics or [],
    }
    if path is not None:
        payload["path"] = _display_path(path)
    if details:
        payload["details"] = dict(details)
    return payload


def _has_errors(diagnostics: Iterable[Mapping[str, Any]]) -> bool:
    return any(item.get("severity", "error") == "error" for item in diagnostics)


def _canonical(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _canonical(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, list):
        return [_canonical(item) for item in value]
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    return str(value)


def _canonical_text(value: Any) -> str:
    return json.dumps(_canonical(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sha256(value: Any) -> str:
    digest = hashlib.sha256(_canonical_text(value).encode("utf-8"), usedforsecurity=False).hexdigest()
    return f"sha256:{digest}"


def _string_field(item: Mapping[str, Any], field: str) -> str | None:
    value = item.get(field)
    return value if isinstance(value, str) and value else None


def _items(payload: Mapping[str, Any], collection: str) -> list[Mapping[str, Any]]:
    raw = payload.get(collection, [])
    return [item for item in raw if isinstance(item, Mapping)] if isinstance(raw, list) else []


def _scene_id(scene_graph: Mapping[str, Any]) -> str:
    return _string_field(scene_graph, "scene_id") or "scene"


def _scene_version(scene_graph: Mapping[str, Any]) -> int:
    value = scene_graph.get("version")
    return value if isinstance(value, int) else 1


def _brief_prompt(brief: Mapping[str, Any]) -> str:
    for key in ("source_prompt", "one_sentence", "title"):
        value = _string_field(brief, key)
        if value is not None:
            return value
    return "A deterministic Wonder scene fixture."


def _prompt_tokens(value: str) -> set[str]:
    return set(_TOKEN_RE.findall(value.lower()))


def _prompt_alignment_diagnostics(prompt: str, brief: Mapping[str, Any]) -> list[dict[str, Any]]:
    prompt_tokens = _prompt_tokens(prompt)
    signal = _prompt_tokens(
        " ".join(
            str(value)
            for value in [
                brief.get("title"),
                brief.get("one_sentence"),
                brief.get("source_prompt"),
                brief.get("genre"),
                brief.get("mood"),
            ]
            if value
        )
    )
    if signal and not (prompt_tokens & signal):
        return [
            _diagnostic(
                "WE1005",
                "prompt_not_aligned_with_brief",
                "/prompt.txt",
                "prompt.txt is non-empty but does not share clear signal words with the Dream Brief.",
                contract="prompt",
                details={"expected_signal_tokens": sorted(signal)[:12]},
            )
        ]
    return []


def _primary_patch_target(scene_graph: Mapping[str, Any]) -> str:
    objects = _items(scene_graph, "objects")
    for role in ("hero_prop", "interactive", "narrative_clue", "architecture", "environment_structure"):
        for item in objects:
            if item.get("role") == role and isinstance(item.get("object_id"), str):
                return str(item["object_id"])
    for item in objects:
        object_id = item.get("object_id")
        if isinstance(object_id, str):
            return object_id
    return _scene_id(scene_graph)


def _camera_id(scene_graph: Mapping[str, Any]) -> str:
    for camera in _items(scene_graph, "cameras"):
        camera_id = _string_field(camera, "camera_id")
        if camera_id == "camera_reveal":
            return camera_id
    for camera in _items(scene_graph, "cameras"):
        camera_id = _string_field(camera, "camera_id")
        if camera_id is not None:
            return camera_id
    return "camera_reveal"


def _scene_source_status_payload() -> dict[str, Any]:
    return {
        "schema_version": SCENE_SOURCE_STATUS_VERSION,
        "status": "deferred",
        "reason": _SCENE_SOURCE_DEFERRED_REASON,
        "blocking": False,
        "tracked_by": _SCENE_SOURCE_TRACKING_ADR,
    }


def _world_memory_payload(scene_graph: Mapping[str, Any]) -> dict[str, Any]:
    from lathe.scene.memory import create_world_memory

    scene_id = _scene_id(scene_graph)
    return create_world_memory(
        scene_graph,
        summary=f"Continuity memory for the {scene_id} Wonder golden fixture.",
    )


def _scene_patch_payload(scene_graph: Mapping[str, Any]) -> dict[str, Any]:
    scene_id = _scene_id(scene_graph)
    target_id = _primary_patch_target(scene_graph)
    return {
        "schema_version": "lathe.scene_patch.v1",
        "patch_id": f"patch_{scene_id}_example_001",
        "scope": "object" if target_id.startswith("obj_") else "scene",
        "target_id": target_id,
        "instruction": (
            "Add a small deterministic proxy-safe emphasis pass while preserving stable IDs, "
            "layout, position, scale, and branch continuity."
        ),
        "preserve": [
            "object_id",
            "region",
            "transform.position",
            "transform.rotation",
            "transform.scale",
        ]
        if target_id.startswith("obj_")
        else ["stable_ids", "layout.focal_point", scene_id],
        "allowed_changes": ["style", "metadata"],
        "continuity": {
            "mode": "preserve_selected_ids",
            "preserved_ids": [target_id] if target_id.startswith("obj_") else [],
        },
        "acceptance": {
            "validators": ["style", "semantic", "composition", "continuity"],
            "minimum_score": 0.78,
        },
    }


def _render_inspection_payload(scene_graph: Mapping[str, Any]) -> dict[str, Any]:
    scene_id = _scene_id(scene_graph)
    camera_id = _camera_id(scene_graph)
    target_id = _primary_patch_target(scene_graph)
    return {
        "schema_version": "lathe.render_inspection.v1",
        "inspection_id": f"inspect_{scene_id}_001",
        "scene_id": scene_id,
        "render_ref": {
            "image_path": f"renders/{camera_id}/beauty.png",
            "camera_id": camera_id,
            "render_pass": "beauty",
        },
        "status": "passed_with_warnings",
        "visual_summary": (
            "Deterministic proxy inspection fixture: the scene contract is readable, "
            "while final visual judgment remains deferred to real render lanes."
        ),
        "scores": {
            "matches_brief": 0.82,
            "style_consistency": 0.8,
            "spatial_coherence": 0.84,
            "composition": 0.82,
            "curiosity": 0.8,
            "overall": 0.82,
        },
        "problems": [
            {
                "problem_id": f"problem_{scene_id}_proxy_only",
                "severity": "info",
                "target_id": target_id if target_id.startswith("obj_") else camera_id,
                "summary": "Only deterministic proxy inspection evidence is committed for this golden fixture.",
                "evidence": "Blender-backed visual inspection is intentionally not claimed by Wave 5 examples.",
            }
        ],
        "recommended_patches": [
            {
                "scope": "object" if target_id.startswith("obj_") else "scene",
                "target_id": target_id,
                "change": "Use the committed example Scene Patch as the first deterministic revision loop input.",
                "suggested_patch": {"patch_ref": "scene_patch.example.json"},
            }
        ],
    }


def _scene_manifest_payload(scene_graph: Mapping[str, Any], scene_plan: Mapping[str, Any]) -> dict[str, Any]:
    scene_id = _scene_id(scene_graph)
    objects: list[dict[str, Any]] = []
    for item in _items(scene_graph, "objects"):
        object_id = _string_field(item, "object_id")
        if object_id is None:
            continue
        source = None
        for field in ("lathe_asset", "source_asset", "source_family", "source_kit"):
            source = _string_field(item, field)
            if source is not None:
                break
        objects.append(
            {
                "object_id": object_id,
                "source": source or "generated_fallback",
                "status": "planned",
                "artifact_dir": f"build/objects/{object_id}",
            }
        )
    return {
        "schema_version": "lathe.scene_manifest.v1",
        "scene_id": scene_id,
        "scene_version": _scene_version(scene_graph),
        "mode": "preview",
        "status": "golden_fixture_proxy_contract",
        "offline": True,
        "source": {
            "prompt": "../prompt.txt",
            "dream_brief": "../dream_brief.json",
            "scene_graph": "../scene_graph.json",
            "world_memory": "../world_memory.json",
        },
        "objects": objects,
        "planned_renders": [
            {
                "task_id": task.get("task_id"),
                "camera_id": task.get("camera_id"),
                "status": "planned",
                "passes": list(task.get("passes", [])) if isinstance(task.get("passes"), list) else [],
                "artifact_path": None,
            }
            for task in scene_plan.get("render_tasks", [])
            if isinstance(task, Mapping)
        ],
        "planned_exports": [
            {
                "task_id": task.get("task_id"),
                "target": task.get("target"),
                "format": task.get("format"),
                "declared_path": task.get("path"),
                "status": "planned",
                "artifact_path": None,
            }
            for task in scene_plan.get("export_tasks", [])
            if isinstance(task, Mapping)
        ],
        "built_renders": [],
        "built_exports": [],
        "notes": [
            "Golden fixture reports deterministic proxy readiness only.",
            "Generated render/export artifacts are produced in .tmp_tests during evidence runs, not committed here.",
        ],
    }


def _wonder_report_payload(scene_graph: Mapping[str, Any], scene_plan: Mapping[str, Any]) -> dict[str, Any]:
    scene_id = _scene_id(scene_graph)
    counts = scene_plan.get("metadata", {}).get("counts", {}) if isinstance(scene_plan.get("metadata"), Mapping) else {}
    return {
        "schema_version": "lathe.wonder_report.v1",
        "scene_id": scene_id,
        "scene_version": _scene_version(scene_graph),
        "mode": "preview",
        "status": "golden_fixture_ready",
        "summary": (
            f"{scene_id} validates as a deterministic Wonder golden fixture with proxy-only "
            "preview build/render/export evidence."
        ),
        "counts": copy.deepcopy(counts),
        "optional_lanes": {
            "blender": {
                "status": "skipped_optional",
                "blocking": False,
                "reason": "Blender-backed rendering is outside Wave 5 example-golden core mode.",
            },
            "roblox": {
                "status": "skipped_optional",
                "blocking": False,
                "reason": "Roblox Studio execution is outside Wave 5 example-golden core mode.",
            },
        },
        "artifacts": {
            "scene_plan": "expected/scene_plan.example.json",
            "scene_manifest": "expected/scene_manifest.example.json",
            "preview_evidence": "expected/preview_evidence.example.json",
        },
        "diagnostics": copy.deepcopy(scene_plan.get("diagnostics", [])),
    }


def _render_comparison_payload(scene_graph: Mapping[str, Any]) -> dict[str, Any]:
    scene_id = _scene_id(scene_graph)
    camera_id = _camera_id(scene_graph)
    image_hash = _sha256({"scene_id": scene_id, "camera_id": camera_id, "proxy_fixture": "unchanged"})
    return {
        "schema_version": "lathe.render_comparison.v1",
        "camera_lock_status": "passed",
        "before_hash": image_hash,
        "after_hash": image_hash,
        "dimensions": {"width": 640, "height": 360},
        "pixel_delta": {
            "changed_pixels": 0,
            "changed_ratio": 0.0,
        },
        "semantic_delta": {
            "status": "not_evaluated",
            "reason": (
                "Wave 5 golden fixtures commit proxy comparison contracts only; "
                "target-level semantic visual evaluation is not implemented."
            ),
        },
        "status": "passed",
        "camera_hash": _sha256({"scene_id": scene_id, "camera_id": camera_id, "camera_lock": "fixture"}),
    }


def _evidence_traceability_payload(scene_graph: Mapping[str, Any]) -> dict[str, Any]:
    scene_id = _scene_id(scene_graph)
    item_id = f"ev_{scene_id}_golden_fixture"
    return {
        "schema_version": WONDER_EVIDENCE_TRACE_VERSION,
        "ok": True,
        "status": "passed",
        "tasks_path": "wonder-tasks.md",
        "evidence_path": "docs/wonder-readiness/evidence.md",
        "summary": {
            "checked_tasks": 0,
            "covered_checked_tasks": 0,
            "missing_evidence": 0,
            "evidence_items": 1,
            "used_evidence_items": 1,
            "diagnostics": 0,
        },
        "checked_tasks": [],
        "evidence_items": [
            {
                "evidence_id": item_id,
                "kind": "example_artifact",
                "text": f"{scene_id} is a committed Wonder golden fixture with proxy-only evidence.",
                "line": 1,
                "status": "passed",
                "paths": [
                    f"examples/wonder/{scene_id}/dream_brief.json",
                    f"examples/wonder/{scene_id}/scene_graph.json",
                    f"examples/wonder/{scene_id}/expected/preview_evidence.example.json",
                ],
            }
        ],
        "coverage": [],
        "missing_evidence": [],
        "diagnostics": [],
    }


def _preview_evidence_payload(scene_graph: Mapping[str, Any]) -> dict[str, Any]:
    scene_id = _scene_id(scene_graph)
    root = f"examples/wonder/{scene_id}"
    return {
        "schema_version": PREVIEW_EVIDENCE_VERSION,
        "scene_id": scene_id,
        "status": "passed",
        "core_mode": "deterministic_proxy",
        "preview_build": {
            "status": "passed",
            "blocking": True,
            "evidence_type": "deterministic_proxy_contract",
            "command": f"python -m lathe.cli scene build {root}/scene_graph.json --out .tmp_tests/wonder_preview_evidence/{scene_id}",
            "artifacts": [
                "scene_package_manifest.json",
                "reports/scene_plan.json",
                "reports/wonder_report.json",
                "reports/scene_manifest.json",
            ],
        },
        "preview_render": {
            "status": "passed",
            "blocking": True,
            "renderer": "lathe.scene.proxy_renderer.v1",
            "evidence_type": "deterministic_proxy_contract",
            "command": f"python -m lathe.cli scene render {root}/scene_graph.json --out .tmp_tests/wonder_preview_evidence/{scene_id}",
            "artifacts": ["renders/<camera_id>/beauty.png", "reports/scene_render_artifacts.json"],
        },
        "preview_export": {
            "status": "passed",
            "blocking": True,
            "exporter": "lathe.scene.proxy_glb_exporter.v1",
            "evidence_type": "deterministic_proxy_contract",
            "command": f"python -m lathe.cli scene export {root}/scene_graph.json --target glb --out .tmp_tests/wonder_preview_evidence/{scene_id}",
            "artifacts": ["exports/<scene_id>.glb", "reports/scene_export_artifacts.json"],
        },
        "blender": {
            "status": "skipped_optional",
            "blocking": False,
            "reason": "No Blender process was run for the committed Wave 5 golden fixture.",
        },
        "roblox": {
            "status": "skipped_optional",
            "blocking": False,
            "reason": "No Roblox Studio import or execution was run for the committed Wave 5 golden fixture.",
        },
        "notes": [
            "This file records deterministic/proxy fixture evidence only.",
            "Real Blender and Roblox lanes remain optional/nonblocking unless separately executed and recorded.",
        ],
    }


def write_example_golden_files(example_dir: str | Path) -> dict[str, Any]:
    """Create or refresh deterministic golden fixture files for one example."""
    root = Path(example_dir)
    brief = _read_json(root / "dream_brief.json")
    scene_graph = _read_json(root / "scene_graph.json")
    scene_plan = generate_scene_plan(brief, scene_graph=scene_graph)
    written: list[str] = []

    prompt_path = root / "prompt.txt"
    if not prompt_path.exists() or not prompt_path.read_text(encoding="utf-8").strip():
        prompt_path.write_text(_brief_prompt(brief).strip() + "\n", encoding="utf-8")
        written.append(_display_path(prompt_path))

    scene_source_path = root / "scene_source.lth"
    from ..scene.source import scene_graph_to_source

    source_text = scene_graph_to_source(scene_graph)
    if not scene_source_path.exists() or scene_source_path.read_text(encoding="utf-8") != source_text:
        scene_source_path.write_text(source_text, encoding="utf-8")
        written.append(_display_path(scene_source_path))

    memory_path = root / "world_memory.json"
    if not memory_path.exists():
        _write_json(memory_path, _world_memory_payload(scene_graph))
        written.append(_display_path(memory_path))

    patch_path = root / "scene_patch.example.json"
    if not patch_path.exists():
        _write_json(patch_path, _scene_patch_payload(scene_graph))
        written.append(_display_path(patch_path))

    inspection_path = root / "render_inspection.example.json"
    if not inspection_path.exists():
        _write_json(inspection_path, _render_inspection_payload(scene_graph))
        written.append(_display_path(inspection_path))

    expected_dir = root / "expected"
    expected_dir.mkdir(parents=True, exist_ok=True)
    expected_payloads = {
        "scene_plan.example.json": scene_plan,
        "wonder_report.example.json": _wonder_report_payload(scene_graph, scene_plan),
        "scene_manifest.example.json": _scene_manifest_payload(scene_graph, scene_plan),
        "render_comparison.example.json": _render_comparison_payload(scene_graph),
        "evidence_traceability.example.json": _evidence_traceability_payload(scene_graph),
        "preview_evidence.example.json": _preview_evidence_payload(scene_graph),
    }
    for filename, payload in expected_payloads.items():
        path = expected_dir / filename
        existing = _read_json(path) if path.exists() else None
        if existing == payload:
            continue
        _write_json(path, payload)
        written.append(_display_path(path))

    return {
        "schema_version": "lathe.wonder_example_normalization.v1",
        "example_name": root.name,
        "written": written,
    }


def _required_files(example_dir: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    required: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    for filename, contract in REQUIRED_ROOT_FILES:
        path = example_dir / filename
        status = "present" if path.exists() else "missing"
        item = {
            "path": _display_path(path),
            "contract": contract,
            "status": status,
            "blocking": True,
        }
        required.append(item)
        if status == "missing":
            diagnostics.append(
                _diagnostic(
                    "WE1001",
                    "missing_required_example_file",
                    f"/{filename}",
                    f"Wonder example is missing required file {filename!r}.",
                    details={"file": filename},
                )
            )
    expected_dir = example_dir / "expected"
    expected_status = "present" if expected_dir.is_dir() else "missing"
    required.append(
        {
            "path": _display_path(expected_dir),
            "contract": "expected",
            "status": expected_status,
            "blocking": True,
        }
    )
    if expected_status == "missing":
        diagnostics.append(
            _diagnostic(
                "WE1001",
                "missing_required_example_file",
                "/expected",
                "Wonder example is missing required expected/ directory.",
                details={"file": "expected/"},
            )
        )
    for filename, contract in REQUIRED_EXPECTED_FILES:
        path = expected_dir / filename
        status = "present" if path.exists() else "missing"
        item = {
            "path": _display_path(path),
            "contract": contract,
            "status": status,
            "blocking": True,
        }
        required.append(item)
        if status == "missing":
            diagnostics.append(
                _diagnostic(
                    "WE1001",
                    "missing_required_example_file",
                    f"/expected/{filename}",
                    f"Wonder example is missing required expected artifact {filename!r}.",
                    details={"file": f"expected/{filename}"},
                )
            )
    return required, diagnostics


def _load_required_json(example_dir: Path, relative_path: str) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    path = example_dir / relative_path
    if not path.exists():
        return None, []
    try:
        return _read_json(path), []
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        return None, [
            _diagnostic(
                "WE1002",
                "invalid_example_json",
                f"/{relative_path}",
                f"Could not load {relative_path!r} as a JSON object: {exc}",
                details={"file": relative_path},
            )
        ]


def _validate_contract_file(contract: str, path: Path) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    if not path.exists():
        return None, []
    payload, diagnostics = _load_required_json(path.parent, path.name)
    if payload is None:
        return None, diagnostics
    if contract in CONTRACT_SPECS:
        diagnostics.extend(validate_contract(contract, payload))
    return payload, diagnostics


def _validate_prompt(example_dir: Path, brief: Mapping[str, Any] | None) -> dict[str, Any]:
    path = example_dir / "prompt.txt"
    if not path.exists():
        return _contract_result("prompt", "missing", path=path)
    prompt = path.read_text(encoding="utf-8").strip()
    diagnostics: list[dict[str, Any]] = []
    if not prompt:
        diagnostics.append(
            _diagnostic(
                "WE1003",
                "empty_prompt",
                "/prompt.txt",
                "prompt.txt must be non-empty.",
                contract="prompt",
            )
        )
    elif brief is not None:
        diagnostics.extend(_prompt_alignment_diagnostics(prompt, brief))
    return _contract_result("prompt", "valid" if not diagnostics else "failed", path=path, diagnostics=diagnostics)


def _validate_scene_graph(example_dir: Path, scene_payload: dict[str, Any] | None) -> dict[str, Any]:
    from lathe.scene.graph import check_scene_graph

    path = example_dir / "scene_graph.json"
    if scene_payload is None:
        return _contract_result("scene_graph", "missing", path=path)
    diagnostics = validate_contract("scene_graph", scene_payload)
    if not diagnostics:
        diagnostics.extend(check_scene_graph(scene_payload, root=example_dir))
    return _contract_result("scene_graph", "valid" if not diagnostics else "failed", path=path, diagnostics=diagnostics)


def _validate_world_memory(
    example_dir: Path,
    memory_payload: dict[str, Any] | None,
    scene_payload: Mapping[str, Any] | None,
) -> dict[str, Any]:
    from lathe.scene.memory import validate_world_memory

    path = example_dir / "world_memory.json"
    if memory_payload is None:
        return _contract_result("world_memory", "missing", path=path)
    diagnostics = validate_world_memory(memory_payload, scene_graph=scene_payload)
    return _contract_result("world_memory", "valid" if not diagnostics else "failed", path=path, diagnostics=diagnostics)


def _validate_patch(
    example_dir: Path,
    patch_payload: dict[str, Any] | None,
    scene_payload: Mapping[str, Any] | None,
) -> dict[str, Any]:
    from lathe.scene.patch import apply_scene_patch

    path = example_dir / "scene_patch.example.json"
    if patch_payload is None:
        return _contract_result("scene_patch", "missing", path=path)
    diagnostics = validate_contract("scene_patch", patch_payload)
    details: dict[str, Any] = {}
    if not diagnostics and scene_payload is not None:
        result = apply_scene_patch(scene_payload, patch_payload)
        details = {
            "applied_operations": len(result.applied_operations),
            "rejected_operations": len(result.rejected_operations),
        }
        diagnostics.extend(result.diagnostics)
    return _contract_result("scene_patch", "valid" if not diagnostics else "failed", path=path, diagnostics=diagnostics, details=details)


def _validate_render_inspection(
    example_dir: Path,
    inspection_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    path = example_dir / "render_inspection.example.json"
    if inspection_payload is None:
        return _contract_result("render_inspection", "missing", path=path)
    diagnostics = validate_contract("render_inspection", inspection_payload)
    return _contract_result("render_inspection", "valid" if not diagnostics else "failed", path=path, diagnostics=diagnostics)


def _validate_expected_scene_plan(
    example_dir: Path,
    expected_payload: dict[str, Any] | None,
    brief: Mapping[str, Any] | None,
    scene_payload: Mapping[str, Any] | None,
) -> dict[str, Any]:
    from lathe.scene.planner import validate_scene_plan_payload

    path = example_dir / "expected" / "scene_plan.example.json"
    if expected_payload is None:
        return _contract_result("scene_plan", "missing", path=path)
    diagnostics = validate_scene_plan_payload(expected_payload)
    if not diagnostics and brief is not None and scene_payload is not None:
        generated = generate_scene_plan(brief, scene_graph=scene_payload)
        if _canonical(expected_payload) != _canonical(generated):
            diagnostics.append(
                _diagnostic(
                    "WE1004",
                    "scene_plan_example_not_deterministic",
                    "/expected/scene_plan.example.json",
                    "expected/scene_plan.example.json does not match deterministic generate-scene-plan output.",
                    contract="scene_plan",
                )
            )
    return _contract_result("scene_plan", "valid" if not diagnostics else "failed", path=path, diagnostics=diagnostics)


def _validate_expected_simple(
    example_dir: Path,
    relative_path: str,
    contract: str,
    payload: dict[str, Any] | None,
    *,
    required_schema_version: str | None = None,
) -> dict[str, Any]:
    path = example_dir / relative_path
    if payload is None:
        return _contract_result(contract, "missing", path=path)
    diagnostics: list[dict[str, Any]] = []
    if required_schema_version is not None and payload.get("schema_version") != required_schema_version:
        diagnostics.append(
            _diagnostic(
                "WE1006",
                "unexpected_example_schema_version",
                f"/{relative_path}/schema_version",
                f"{relative_path} must use schema_version {required_schema_version!r}.",
                contract=contract,
                details={"actual": payload.get("schema_version")},
            )
        )
    if contract in CONTRACT_SPECS:
        diagnostics.extend(validate_contract(contract, payload))
    return _contract_result(contract, "valid" if not diagnostics else "failed", path=path, diagnostics=diagnostics)


def _validate_render_comparison(
    example_dir: Path,
    payload: dict[str, Any] | None,
) -> dict[str, Any]:
    path = example_dir / "expected" / "render_comparison.example.json"
    if payload is None:
        return _contract_result("render_comparison", "missing", path=path)
    diagnostics = validate_contract("render_comparison", payload)
    semantic = payload.get("semantic_delta")
    if isinstance(semantic, Mapping) and semantic.get("status") != "not_evaluated":
        diagnostics.append(
            _diagnostic(
                "WE1008",
                "semantic_delta_must_be_truthful",
                "/expected/render_comparison.example.json/semantic_delta/status",
                "Wave 5 example fixtures must not claim semantic render evaluation.",
                contract="render_comparison",
            )
        )
    return _contract_result("render_comparison", "valid" if not diagnostics else "failed", path=path, diagnostics=diagnostics)


def _validate_preview_evidence(
    example_dir: Path,
    payload: dict[str, Any] | None,
) -> dict[str, Any]:
    path = example_dir / "expected" / "preview_evidence.example.json"
    if payload is None:
        return _contract_result("preview_evidence", "missing", path=path)
    diagnostics: list[dict[str, Any]] = []
    if payload.get("schema_version") != PREVIEW_EVIDENCE_VERSION:
        diagnostics.append(
            _diagnostic(
                "WE1006",
                "unexpected_example_schema_version",
                "/expected/preview_evidence.example.json/schema_version",
                f"preview_evidence.example.json must use schema_version {PREVIEW_EVIDENCE_VERSION!r}.",
                contract="preview_evidence",
            )
        )
    for lane in ("blender", "roblox"):
        lane_payload = payload.get(lane)
        if not isinstance(lane_payload, Mapping):
            diagnostics.append(
                _diagnostic(
                    "WE1007",
                    "missing_optional_runtime_lane",
                    f"/expected/preview_evidence.example.json/{lane}",
                    f"preview evidence must report the optional {lane} lane.",
                    contract="preview_evidence",
                )
            )
            continue
        if lane_payload.get("blocking") is not False or lane_payload.get("status") not in {
            "skipped_optional",
            "deferred_optional",
        }:
            diagnostics.append(
                _diagnostic(
                    "WE1009",
                    "external_runtime_lane_not_truthful",
                    f"/expected/preview_evidence.example.json/{lane}",
                    f"Committed Wave 5 examples must not claim {lane} execution.",
                    contract="preview_evidence",
                    details={"lane": lane, "payload": dict(lane_payload)},
                )
            )
    return _contract_result("preview_evidence", "valid" if not diagnostics else "failed", path=path, diagnostics=diagnostics)


def _validate_scene_source(
    example_dir: Path,
    scene_graph: Mapping[str, Any] | None,
    *,
    strict: bool,
    allow_deferred_scene_source: bool,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    source_path = example_dir / "scene_source.lth"
    status_path = example_dir / "scene_source_status.json"
    diagnostics: list[dict[str, Any]] = []
    if source_path.exists():
        from ..scene.source import source_to_scene_graph

        try:
            source_text = source_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            diagnostics.append(
                _diagnostic(
                    "WE1013",
                    "scene_source_load_failed",
                    "/scene_source.lth",
                    f"Scene source could not be loaded as UTF-8 text: {exc}",
                    contract="scene_source",
                )
            )
            return _contract_result("scene_source", "failed", path=source_path, diagnostics=diagnostics), []
        extracted, source_diagnostics = source_to_scene_graph(
            source_text,
            root=example_dir,
            source_path=source_path,
        )
        diagnostics.extend(source_diagnostics)
        if not source_diagnostics and scene_graph is not None and extracted != dict(scene_graph):
            diagnostics.append(
                _diagnostic(
                    "WE1014",
                    "scene_source_roundtrip_mismatch",
                    "/scene_source.lth",
                    "Scene source must roundtrip to the committed scene_graph.json payload.",
                    contract="scene_source",
                    details={
                        "scene_id": scene_graph.get("scene_id"),
                        "source_scene_id": extracted.get("scene_id"),
                    },
                )
            )
        return _contract_result(
            "scene_source",
            "valid" if not diagnostics else "failed",
            path=source_path,
            diagnostics=diagnostics,
        ), []
    payload = _read_json(status_path) if status_path.exists() else None
    if payload is None:
        diagnostics.append(
            _diagnostic(
                "WE1010",
                "missing_scene_source",
                "/scene_source.lth",
                "Example must include a roundtrippable scene_source.lth.",
                contract="scene_source",
            )
        )
        return _contract_result("scene_source", "failed", path=source_path, diagnostics=diagnostics), []
    expected = _scene_source_status_payload()
    for field in ("schema_version", "status", "blocking", "tracked_by"):
        if payload.get(field) != expected[field]:
            diagnostics.append(
                _diagnostic(
                    "WE1011",
                    "invalid_scene_source_deferral",
                    f"/scene_source_status.json/{field}",
                    "Scene source deferral must be explicit, truthful, and nonblocking.",
                    contract="scene_source",
                    details={"expected": expected[field], "actual": payload.get(field)},
                )
            )
    reason = payload.get("reason")
    if not isinstance(reason, str) or "not complete" not in reason.lower():
        diagnostics.append(
            _diagnostic(
                "WE1011",
                "invalid_scene_source_deferral",
                "/scene_source_status.json/reason",
                "Scene source deferral reason must truthfully state that full scene syntax is incomplete.",
                contract="scene_source",
            )
        )
    deferred_lane = {
        "lane": "scene_source",
        "status": "deferred",
        "blocking": False,
        "reason": str(payload.get("reason", "")),
        "tracked_by": str(payload.get("tracked_by", "")),
    }
    if strict and not allow_deferred_scene_source:
        diagnostics.append(
            _diagnostic(
                "WE1012",
                "scene_source_deferred_in_strict_mode",
                "/scene_source_status.json/status",
                "Strict example validation requires a real roundtrippable scene_source.lth.",
                contract="scene_source",
            )
        )
    status = "deferred" if not diagnostics else "failed"
    return _contract_result("scene_source", status, path=status_path, diagnostics=diagnostics), [deferred_lane]


def validate_wonder_example(
    example_dir: str | Path,
    *,
    strict: bool = False,
    allow_deferred_scene_source: bool = True,
    write_missing_proxy_evidence: bool = False,
) -> dict[str, Any]:
    """Validate one Wonder example golden fixture and return a machine-readable report."""
    root = Path(example_dir)
    normalization: dict[str, Any] | None = None
    if write_missing_proxy_evidence:
        normalization = write_example_golden_files(root)

    required_files, diagnostics = _required_files(root)
    loaded_diagnostics: list[dict[str, Any]] = []
    brief, errors = _load_required_json(root, "dream_brief.json")
    loaded_diagnostics.extend(errors)
    scene_graph, errors = _load_required_json(root, "scene_graph.json")
    loaded_diagnostics.extend(errors)
    memory, errors = _load_required_json(root, "world_memory.json")
    loaded_diagnostics.extend(errors)
    patch, errors = _load_required_json(root, "scene_patch.example.json")
    loaded_diagnostics.extend(errors)
    inspection, errors = _load_required_json(root, "render_inspection.example.json")
    loaded_diagnostics.extend(errors)
    expected: dict[str, dict[str, Any] | None] = {}
    for filename, _contract in REQUIRED_EXPECTED_FILES:
        payload, errors = _load_required_json(root, f"expected/{filename}")
        expected[filename] = payload
        loaded_diagnostics.extend(errors)
    diagnostics.extend(loaded_diagnostics)

    contract_results: list[dict[str, Any]] = []
    contract_results.append(_validate_prompt(root, brief))
    if brief is not None:
        brief_diagnostics = validate_contract("dream_brief", brief)
        contract_results.append(
            _contract_result(
                "dream_brief",
                "valid" if not brief_diagnostics else "failed",
                path=root / "dream_brief.json",
                diagnostics=brief_diagnostics,
            )
        )
    else:
        contract_results.append(_contract_result("dream_brief", "missing", path=root / "dream_brief.json"))
    contract_results.append(_validate_scene_graph(root, scene_graph))
    contract_results.append(_validate_world_memory(root, memory, scene_graph))
    contract_results.append(_validate_patch(root, patch, scene_graph))
    contract_results.append(_validate_render_inspection(root, inspection))
    contract_results.append(_validate_expected_scene_plan(root, expected["scene_plan.example.json"], brief, scene_graph))
    contract_results.append(
        _validate_expected_simple(
            root,
            "expected/wonder_report.example.json",
            "wonder_report",
            expected["wonder_report.example.json"],
            required_schema_version="lathe.wonder_report.v1",
        )
    )
    contract_results.append(
        _validate_expected_simple(
            root,
            "expected/scene_manifest.example.json",
            "scene_manifest",
            expected["scene_manifest.example.json"],
            required_schema_version="lathe.scene_manifest.v1",
        )
    )
    contract_results.append(_validate_render_comparison(root, expected["render_comparison.example.json"]))
    contract_results.append(
        _validate_expected_simple(
            root,
            "expected/evidence_traceability.example.json",
            "evidence_traceability",
            expected["evidence_traceability.example.json"],
            required_schema_version=WONDER_EVIDENCE_TRACE_VERSION,
        )
    )
    contract_results.append(_validate_preview_evidence(root, expected["preview_evidence.example.json"]))
    scene_source_result, deferred_lanes = _validate_scene_source(
        root,
        scene_graph,
        strict=strict,
        allow_deferred_scene_source=allow_deferred_scene_source,
    )
    contract_results.append(scene_source_result)

    for result in contract_results:
        result_diagnostics = result.get("diagnostics", [])
        if isinstance(result_diagnostics, list):
            diagnostics.extend(item for item in result_diagnostics if isinstance(item, dict))

    evidence_paths = [
        item["path"]
        for item in required_files
        if item.get("status") == "present"
        and (Path(str(item.get("path", ""))).name in _DOC_ROOT_FILES or Path(str(item.get("path", ""))).name in _DOC_EXPECTED_FILES)
    ]
    status = "failed" if _has_errors(diagnostics) else "passed"
    report: dict[str, Any] = {
        "schema_version": WONDER_EXAMPLE_REPORT_VERSION,
        "ok": status == "passed",
        "example_name": root.name,
        "example_dir": _display_path(root),
        "status": status,
        "strict": strict,
        "allow_deferred_scene_source": allow_deferred_scene_source,
        "required_files": required_files,
        "contract_results": contract_results,
        "deferred_lanes": deferred_lanes,
        "diagnostics": diagnostics,
        "evidence_paths": evidence_paths,
    }
    if normalization is not None:
        report["normalization"] = normalization
    return report


def _contract_status(report: Mapping[str, Any], contract: str) -> str:
    for result in report.get("contract_results", []):
        if isinstance(result, Mapping) and result.get("contract") == contract:
            status = result.get("status")
            if isinstance(status, str):
                if status in {"valid", "present"}:
                    return "valid" if contract not in {"prompt", "preview_evidence"} else "present"
                return status
    return "missing"


def _catalog_entry(report: Mapping[str, Any]) -> dict[str, Any]:
    deferred_lanes = [
        str(item.get("lane"))
        for item in report.get("deferred_lanes", [])
        if isinstance(item, Mapping) and isinstance(item.get("lane"), str)
    ]
    return {
        "name": str(report.get("example_name", "")),
        "status": str(report.get("status", "failed")),
        "prompt": "present" if _contract_status(report, "prompt") == "present" else _contract_status(report, "prompt"),
        "dream_brief": _contract_status(report, "dream_brief"),
        "scene_graph": _contract_status(report, "scene_graph"),
        "world_memory": _contract_status(report, "world_memory"),
        "patch": _contract_status(report, "scene_patch"),
        "render_inspection": _contract_status(report, "render_inspection"),
        "scene_source": "deferred" if "scene_source" in deferred_lanes else _contract_status(report, "scene_source"),
        "preview_evidence": _contract_status(report, "preview_evidence"),
        "deferred_lanes": deferred_lanes,
    }


def catalog_wonder_examples(
    examples_root: str | Path,
    *,
    strict: bool = False,
    allow_deferred_scene_source: bool = True,
    write_missing_proxy_evidence: bool = False,
    include_reports: bool = False,
) -> dict[str, Any]:
    """Validate and summarize every Wonder example under a root directory."""
    root = Path(examples_root)
    reports = [
        validate_wonder_example(
            path,
            strict=strict,
            allow_deferred_scene_source=allow_deferred_scene_source,
            write_missing_proxy_evidence=write_missing_proxy_evidence,
        )
        for path in sorted(item for item in root.iterdir() if item.is_dir())
    ]
    examples = [_catalog_entry(report) for report in reports]
    passed = sum(1 for item in examples if item["status"] == "passed")
    failed = sum(1 for item in examples if item["status"] == "failed")
    deferred_nonblocking = sum(1 for item in examples if item["deferred_lanes"])
    catalog: dict[str, Any] = {
        "schema_version": WONDER_EXAMPLE_CATALOG_VERSION,
        "examples_root": _display_path(root),
        "examples": examples,
        "summary": {
            "total": len(examples),
            "passed": passed,
            "failed": failed,
            "deferred_nonblocking": deferred_nonblocking,
        },
    }
    if include_reports:
        catalog["reports"] = reports
    return catalog


def render_example_catalog_markdown(catalog: Mapping[str, Any]) -> str:
    """Render a concise Markdown view of a Wonder example catalog."""
    lines = [
        "# Wonder Example Catalog",
        "",
        "This catalog is generated by `python -m lathe.cli wonder catalog-examples`.",
        "All examples are validated as deterministic/proxy golden fixtures; Blender and Roblox execution are optional lanes and are not claimed here.",
        "",
        "## Summary",
        "",
        "| Total | Passed | Failed | Deferred nonblocking |",
        "| --- | --- | --- | --- |",
    ]
    summary = catalog.get("summary", {}) if isinstance(catalog.get("summary"), Mapping) else {}
    lines.append(
        f"| {summary.get('total', 0)} | {summary.get('passed', 0)} | "
        f"{summary.get('failed', 0)} | {summary.get('deferred_nonblocking', 0)} |"
    )
    lines.extend(
        [
            "",
            "## Examples",
            "",
            "| Example | Status | Prompt | Dream Brief | Scene Graph | World Memory | Patch | Render Inspection | Scene Source | Preview Evidence | Deferred Lanes |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for item in catalog.get("examples", []):
        if not isinstance(item, Mapping):
            continue
        name = str(item.get("name", ""))
        deferred = ", ".join(str(lane) for lane in item.get("deferred_lanes", []) if isinstance(lane, str)) or ""
        lines.append(
            "| "
            + " | ".join(
                [
                    f"[`{name}`](../../examples/wonder/{name}/)",
                    str(item.get("status", "")),
                    str(item.get("prompt", "")),
                    str(item.get("dream_brief", "")),
                    str(item.get("scene_graph", "")),
                    str(item.get("world_memory", "")),
                    str(item.get("patch", "")),
                    str(item.get("render_inspection", "")),
                    str(item.get("scene_source", "")),
                    str(item.get("preview_evidence", "")),
                    deferred,
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Golden Fixture Rules",
            "",
            "- Required source contracts are `prompt.txt`, `dream_brief.json`, `scene_graph.json`, `scene_source.lth`, `world_memory.json`, `scene_patch.example.json`, and `render_inspection.example.json`.",
            "- Required expected artifacts live under `expected/` and include deterministic Scene Plan, Wonder report, scene manifest, render comparison, evidence traceability, and preview evidence examples.",
            "- `scene_source.lth` is generated from the committed Scene Graph and must roundtrip through `lathe scene source-to-scene-graph`.",
            "- Preview build, render, and export evidence is deterministic/proxy-only. Blender and Roblox lanes remain skipped optional lanes unless separate execution evidence is recorded.",
            "",
        ]
    )
    return "\n".join(lines)


__all__ = [
    "PREVIEW_EVIDENCE_VERSION",
    "REQUIRED_EXPECTED_FILES",
    "REQUIRED_ROOT_FILES",
    "SCENE_SOURCE_STATUS_VERSION",
    "WONDER_EXAMPLE_CATALOG_VERSION",
    "WONDER_EXAMPLE_REPORT_VERSION",
    "catalog_wonder_examples",
    "render_example_catalog_markdown",
    "validate_wonder_example",
    "write_example_golden_files",
]
