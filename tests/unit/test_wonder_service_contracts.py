from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import jsonschema
import pytest
from referencing import Registry, Resource

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = REPO_ROOT / "schema"
SERVICE_SCHEMA_PATH = SCHEMA_DIR / "service_wonder_api.schema.json"
EXAMPLE_DIR = REPO_ROOT / "examples" / "wonder" / "alchemist_observatory"
SERVICE_SCHEMA_ID = "https://lathe.dev/schema/wonder/service-api-v1.json"

REFERENCED_SCHEMA_PATHS = (
    SCHEMA_DIR / "dream_brief.schema.json",
    SCHEMA_DIR / "scene_graph.schema.json",
    SCHEMA_DIR / "scene_patch.schema.json",
    SCHEMA_DIR / "render_inspection.schema.json",
    SCHEMA_DIR / "scene_package_manifest.schema.json",
    SCHEMA_DIR / "scene_plan.schema.json",
    SCHEMA_DIR / "scene_assembly.schema.json",
    SCHEMA_DIR / "scene_quality_report.schema.json",
    SCHEMA_DIR / "scene_repair_report.schema.json",
)

SERVICE_DEF_NAMES = (
    "dream_brief_check_request",
    "dream_brief_check_response",
    "scene_graph_check_request",
    "scene_graph_check_response",
    "scene_build_request",
    "scene_build_response",
    "scene_render_request",
    "scene_render_response",
    "scene_patch_request",
    "scene_patch_response",
    "artifacts_list_request",
    "artifacts_list_response",
    "status_request",
    "status_response",
)

FORBIDDEN_APP_FIELDS = (
    "account_id",
    "chat_thread_id",
    "product_plan",
    "payment_id",
    "gallery_id",
)


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _service_schema() -> dict[str, Any]:
    return _json(SERVICE_SCHEMA_PATH)


def _registry() -> Registry:
    resources = []
    for path in (SERVICE_SCHEMA_PATH, *REFERENCED_SCHEMA_PATHS):
        schema = _json(path)
        resources.append((schema["$id"], Resource.from_contents(schema)))
    return Registry().with_resources(resources)


def _validator(def_name: str) -> jsonschema.Draft202012Validator:
    return jsonschema.Draft202012Validator(
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$ref": f"{SERVICE_SCHEMA_ID}#/$defs/{def_name}",
        },
        registry=_registry(),
    )


def _artifact(kind: str, path: str, status: str, **extra: Any) -> dict[str, Any]:
    return {"kind": kind, "path": path, "status": status, **extra}


def _scene_package_manifest() -> dict[str, Any]:
    return {
        "schema_version": "lathe.scene_package_manifest.v1",
        "package_id": "alchemist_observatory",
        "scene_id": "alchemist_observatory",
        "version": 1,
        "layout": {
            "source": "source",
            "graph": "graph",
            "build": "build",
            "renders": "renders",
            "exports": "exports",
            "reports": "reports",
        },
        "source": [
            {"kind": "prompt", "path": "source/prompt.txt"},
            {"kind": "dream_brief", "path": "source/dream_brief.json"},
        ],
        "graph": {
            "scene_graph": "graph/scene_graph.json",
            "patches": ["graph/scene_patch_more_sacred.json"],
        },
        "build": [
            {
                "kind": "scene_build",
                "path": "build/scene_build_proxy_manifest.json",
                "status": "planned",
            }
        ],
        "renders": [
            {
                "camera_id": "camera_reveal",
                "path": "renders/camera_reveal/beauty.png",
                "passes": ["beauty"],
                "status": "built",
            }
        ],
        "exports": [
            {
                "target": "glb",
                "path": "exports/alchemist_observatory.glb",
                "status": "planned",
            }
        ],
        "reports": [
            {
                "kind": "validation",
                "path": "reports/scene_quality_report.json",
                "status": "validated",
            }
        ],
    }


def _samples() -> dict[str, dict[str, Any]]:
    brief = _json(EXAMPLE_DIR / "dream_brief.json")
    scene_graph = _json(EXAMPLE_DIR / "scene_graph.json")
    patch = _json(EXAMPLE_DIR / "scene_patch_more_sacred.json")
    render_inspection = _json(EXAMPLE_DIR / "render_inspection.example.json")
    manifest = _scene_package_manifest()
    correlation_id = "corr_20260428_observatory_001"
    job_id = "job_alchemist_observatory_001"
    artifacts = [
        _artifact("scene_graph", "graph/scene_graph.json", "validated", contract="scene_graph"),
        _artifact("scene_package_manifest", "scene_package_manifest.json", "validated"),
        _artifact("scene_plan", "reports/scene_plan.json", "validated", contract="scene_plan"),
    ]

    return {
        "dream_brief_check_request": {
            "schema_version": "lathe.service.dream_brief_check.request.v1",
            "correlation_id": correlation_id,
            "endpoint": "dream-brief/check",
            "dream_brief": brief,
        },
        "dream_brief_check_response": {
            "schema_version": "lathe.service.dream_brief_check.response.v1",
            "correlation_id": correlation_id,
            "endpoint": "dream-brief/check",
            "ok": True,
            "status": "succeeded",
            "contract": "dream_brief",
            "check": "dream_brief_schema",
            "schema_id": "https://lathe.dev/schema/wonder/dream-brief-v1.json",
            "diagnostics": [],
        },
        "scene_graph_check_request": {
            "schema_version": "lathe.service.scene_graph_check.request.v1",
            "correlation_id": correlation_id,
            "endpoint": "scene-graph/check",
            "scene_graph": scene_graph,
        },
        "scene_graph_check_response": {
            "schema_version": "lathe.service.scene_graph_check.response.v1",
            "correlation_id": correlation_id,
            "endpoint": "scene-graph/check",
            "ok": True,
            "status": "succeeded",
            "contract": "scene_graph",
            "check": "scene_graph_semantics",
            "scene_id": "alchemist_observatory",
            "schema_id": "https://lathe.dev/schema/wonder/scene-graph-v1.json",
            "diagnostics": [],
        },
        "scene_build_request": {
            "schema_version": "lathe.service.scene_build.request.v1",
            "correlation_id": correlation_id,
            "endpoint": "scene/build",
            "mode": "preview",
            "scene_graph": scene_graph,
        },
        "scene_build_response": {
            "schema_version": "lathe.service.scene_build.response.v1",
            "correlation_id": correlation_id,
            "endpoint": "scene/build",
            "job_id": job_id,
            "ok": True,
            "status": "succeeded",
            "command": "scene.build",
            "contract": "scene_package_manifest",
            "scene_id": "alchemist_observatory",
            "scene_version": 1,
            "mode": "preview",
            "package_dir": "dist_scene/alchemist_observatory",
            "manifest_path": "dist_scene/alchemist_observatory/scene_package_manifest.json",
            "artifact_paths": {
                "scene_graph": "graph/scene_graph.json",
                "scene_plan": "reports/scene_plan.json",
                "scene_package_manifest": "scene_package_manifest.json",
            },
            "artifacts": artifacts,
            "counts": {
                "objects": 4,
                "asset_tasks": 4,
                "assembly_tasks": 4,
                "render_tasks": 2,
                "export_tasks": 2,
                "memory_events": 2,
            },
            "quality": {"status": "passed", "score": 96},
            "scene_package_manifest": manifest,
            "diagnostics": [],
        },
        "scene_render_request": {
            "schema_version": "lathe.service.scene_render.request.v1",
            "correlation_id": correlation_id,
            "endpoint": "scene/render",
            "mode": "preview",
            "scene_graph": scene_graph,
            "camera_ids": ["camera_reveal"],
            "render_passes": ["beauty"],
        },
        "scene_render_response": {
            "schema_version": "lathe.service.scene_render.response.v1",
            "correlation_id": correlation_id,
            "endpoint": "scene/render",
            "job_id": "job_alchemist_render_001",
            "ok": True,
            "status": "succeeded",
            "scene_id": "alchemist_observatory",
            "scene_version": 1,
            "mode": "preview",
            "artifacts": [
                _artifact(
                    "render",
                    "renders/camera_reveal/beauty.png",
                    "built",
                    camera_id="camera_reveal",
                    media_type="image/png",
                )
            ],
            "render_inspections": [render_inspection],
            "diagnostics": [],
        },
        "scene_patch_request": {
            "schema_version": "lathe.service.scene_patch.request.v1",
            "correlation_id": correlation_id,
            "endpoint": "scene/patch",
            "scene_graph": scene_graph,
            "patch": patch,
            "preview": False,
        },
        "scene_patch_response": {
            "schema_version": "lathe.service.scene_patch.response.v1",
            "correlation_id": correlation_id,
            "endpoint": "scene/patch",
            "ok": True,
            "status": "succeeded",
            "command": "scene.patch",
            "contract": "scene_patch",
            "scene_id": "alchemist_observatory",
            "patch_id": "patch_more_sacred_001",
            "preview": False,
            "written": True,
            "patch_event": {
                "event_id": "mem_patch_more_sacred_001",
                "type": "patch",
                "scope": "object",
                "text": "Scene patch patch_more_sacred_001 applied.",
                "affected_ids": ["obj_astrolabe_table_001"],
                "branch_id": "main",
                "source": "scene.patch",
            },
            "scene_memory_event": {
                "event_id": "mem_scene_patch_more_sacred_001",
                "type": "patch",
                "scope": "scene",
                "text": "The scene keeps continuity after the sacred table patch.",
                "affected_ids": ["alchemist_observatory"],
                "branch_id": "main",
                "source": "scene.patch",
            },
            "applied_operations": [
                {"op": "replace", "path": "/objects/0/material_bindings/0/material"}
            ],
            "rejected_operations": [],
            "scene_graph": scene_graph,
            "artifacts": [
                _artifact("scene_graph", "graph/scene_graph.patched.json", "validated", contract="scene_graph")
            ],
            "diagnostics": [],
        },
        "artifacts_list_request": {
            "schema_version": "lathe.service.artifacts_list.request.v1",
            "correlation_id": correlation_id,
            "endpoint": "artifacts/list",
            "job_id": job_id,
            "scene_package_manifest": manifest,
            "kinds": ["scene_graph", "scene_package_manifest"],
        },
        "artifacts_list_response": {
            "schema_version": "lathe.service.artifacts_list.response.v1",
            "correlation_id": correlation_id,
            "endpoint": "artifacts/list",
            "job_id": job_id,
            "scene_id": "alchemist_observatory",
            "ok": True,
            "status": "succeeded",
            "scene_package_manifest": manifest,
            "artifacts": artifacts,
            "diagnostics": [],
        },
        "status_request": {
            "schema_version": "lathe.service.status.request.v1",
            "correlation_id": correlation_id,
            "endpoint": "status",
            "job_id": job_id,
        },
        "status_response": {
            "schema_version": "lathe.service.status.response.v1",
            "correlation_id": correlation_id,
            "endpoint": "status",
            "job_id": job_id,
            "target_endpoint": "scene/build",
            "scene_id": "alchemist_observatory",
            "ok": True,
            "status": "succeeded",
            "message": "Scene build completed.",
            "artifacts": artifacts,
            "diagnostics": [],
        },
    }


def test_service_schema_is_valid_json_schema() -> None:
    jsonschema.Draft202012Validator.check_schema(_service_schema())


@pytest.mark.parametrize("def_name", SERVICE_DEF_NAMES)
def test_service_sample_payloads_validate(def_name: str) -> None:
    _validator(def_name).validate(_samples()[def_name])


@pytest.mark.parametrize("def_name", SERVICE_DEF_NAMES)
def test_service_top_level_schema_accepts_each_sample_payload(def_name: str) -> None:
    jsonschema.Draft202012Validator(_service_schema(), registry=_registry()).validate(_samples()[def_name])


@pytest.mark.parametrize("field_name", FORBIDDEN_APP_FIELDS)
@pytest.mark.parametrize("def_name", SERVICE_DEF_NAMES)
def test_service_envelopes_reject_project_wonder_app_fields(def_name: str, field_name: str) -> None:
    payload = copy.deepcopy(_samples()[def_name])
    payload[field_name] = "app_layer_value"

    with pytest.raises(jsonschema.ValidationError):
        _validator(def_name).validate(payload)


def test_artifacts_list_request_requires_job_scene_or_manifest_lookup_key() -> None:
    payload = {
        "schema_version": "lathe.service.artifacts_list.request.v1",
        "correlation_id": "corr_20260428_observatory_001",
        "endpoint": "artifacts/list",
    }

    with pytest.raises(jsonschema.ValidationError):
        _validator("artifacts_list_request").validate(payload)


def test_nested_contract_payload_rejects_chat_field() -> None:
    payload = copy.deepcopy(_samples()["dream_brief_check_request"])
    payload["dream_brief"]["chat_thread_id"] = "chat_app_owned_001"

    with pytest.raises(jsonschema.ValidationError):
        _validator("dream_brief_check_request").validate(payload)


def test_artifact_records_reject_account_field() -> None:
    payload = copy.deepcopy(_samples()["scene_build_response"])
    payload["artifacts"][0]["account_id"] = "acct_app_owned_001"

    with pytest.raises(jsonschema.ValidationError):
        _validator("scene_build_response").validate(payload)
