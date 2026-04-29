# Wonder Service Contract Envelopes

This page defines the Phase 29 service API contract boundary for Project
Wonder. It is documentation and schema only. It does not define a Lathe server,
HTTP router, authentication layer, account model, billing model, gallery, or
chat experience.

The committed schema is
[`schema/service_wonder_api.schema.json`](../../schema/service_wonder_api.schema.json).
Each endpoint has a named request and response schema under that file's
`$defs`.

## Boundary Rule

Service envelopes add transport metadata around existing Lathe payloads:

- `correlation_id` traces a request across app, service, CLI, and report logs.
- `job_id` appears on operations that can be long-running or polled.
- `status` reports service lifecycle state such as `queued`, `running`,
  `succeeded`, or `failed`.
- `diagnostics` reuse Lathe's machine-readable diagnostic shape.
- `artifacts` are package-relative references to files or contract payloads.

The nested payloads remain existing Lathe contracts:

- Dream Brief:
  [`schema/dream_brief.schema.json`](../../schema/dream_brief.schema.json)
- Scene Graph:
  [`schema/scene_graph.schema.json`](../../schema/scene_graph.schema.json)
- Scene Patch:
  [`schema/scene_patch.schema.json`](../../schema/scene_patch.schema.json)
- Render Inspection:
  [`schema/render_inspection.schema.json`](../../schema/render_inspection.schema.json)
- Scene Package Manifest:
  [`schema/scene_package_manifest.schema.json`](../../schema/scene_package_manifest.schema.json)
- Scene Plan:
  [`schema/scene_plan.schema.json`](../../schema/scene_plan.schema.json)
- Scene Assembly:
  [`schema/scene_assembly.schema.json`](../../schema/scene_assembly.schema.json)
- Scene Quality Report:
  [`schema/scene_quality_report.schema.json`](../../schema/scene_quality_report.schema.json)
- Scene Repair Report:
  [`schema/scene_repair_report.schema.json`](../../schema/scene_repair_report.schema.json)

## Endpoints

| Endpoint | Request schema | Response schema | Wrapped Lathe payloads |
| --- | --- | --- | --- |
| `dream-brief/check` | `dream_brief_check_request` | `dream_brief_check_response` | Dream Brief validation diagnostics |
| `scene-graph/check` | `scene_graph_check_request` | `scene_graph_check_response` | Scene Graph schema and semantic diagnostics |
| `scene/build` | `scene_build_request` | `scene_build_response` | Scene Graph input, Scene Plan, Scene Assembly, Scene Quality Report, Scene Package Manifest, artifact refs |
| `scene/render` | `scene_render_request` | `scene_render_response` | Scene Graph input, optional Scene Plan, Render Inspection records, optional Scene Repair Report, artifact refs |
| `scene/patch` | `scene_patch_request` | `scene_patch_response` | Scene Graph input and output, Scene Patch, patch operation records, artifact refs |
| `artifacts/list` | `artifacts_list_request` | `artifacts_list_response` | Scene Package Manifest refs and normalized artifact refs |
| `status` | `status_request` | `status_response` | Job status, diagnostics, artifact refs |

## Non-Goals

Lathe core does not own Project Wonder app features. These service envelopes
must not include account, payment, gallery, chat, product-plan, subscription, or
user-interface fields. Those concerns belong to an application layer that calls
Lathe through the documented contract boundary.

The render endpoint is a contract boundary for future service integration. The
current local Wonder readiness surface still reports render execution as not
implemented in `lathe wonder capabilities`; existing local build work produces
deterministic offline packages and planned proxy records.

## Compatibility

The service schema is versioned as `lathe.service.*.v1`. A compatible service
may add a transport adapter around these envelopes, but it must not change the
nested Lathe contract versions without updating the corresponding Lathe schema,
docs, and tests.

Responses should map to existing CLI-style payload fields where those fields
already exist:

- `ok`, `contract`, `check`, `schema_id`, and `diagnostics` mirror Wonder
  validation and semantic-check command output.
- `command`, `mode`, `package_dir`, `manifest_path`, `artifact_paths`,
  `counts`, and `quality` mirror the current `scene.build` command output.
- `preview`, `written`, `patch_event`, `scene_memory_event`,
  `applied_operations`, `rejected_operations`, and `scene_graph` mirror the
  current `scene.patch` command output.

The envelope `artifacts` list is the service-normalized view of existing
package manifest sections, build reports, render inspection records, and CLI
artifact maps. Paths are package-relative and must not use absolute paths or
parent traversal.
