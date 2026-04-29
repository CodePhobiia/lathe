# LLM Authoring Rules

Lathe's LLM authoring layer is a helper and documentation surface. It does not
call an external model, does not apply patches, and does not replace canonical
schema validation.

## Canonical Schemas

Authoring prompts and tool adapters should link to the committed schemas rather
than copying them into prompts:

- [Canonical schema links](schema_links.md)
- [Good Scene Graph and generated source examples](good_outputs/README.md)
- [Scene Graph v1](../../schema/scene_graph.schema.json)
- [Scene Patch v1](../../schema/scene_patch.schema.json)
- [Render Inspection v1](../../schema/render_inspection.schema.json)
- [Scene Quality Report v1](../../schema/scene_quality_report.schema.json)
- [Scene Repair Report v1](../../schema/scene_repair_report.schema.json)
- [Scene Plan v1](../../schema/scene_plan.schema.json)
- [Scene Assembly v1](../../schema/scene_assembly.schema.json)
- [Scene Package Manifest v1](../../schema/scene_package_manifest.schema.json)
- [LLM Repair Playbook v1](../../schema/llm_repair_playbook.schema.json)

## Helper APIs

Use `lathe.wonder.llm.diagnose_for_llm(report_or_payload)` when an authoring
loop needs a compact diagnostic payload. The helper accepts an existing report,
a diagnostics list, a schema-versioned payload, or generated scene source text.
It returns:

- `schema_version`: `lathe.llm_diagnostic_summary.v1`
- `status`: `passed`, `passed_with_warnings`, or `failed`
- `summary`: diagnostic counts
- `diagnostics`: compact entries with `family`, `severity`, `code`,
  `json_pointer`, `message`, and `next_action`
- `repair_options`: JSON Patch or workflow hints when the diagnostic maps to a
  safe, deterministic edit suggestion

Use `lathe.wonder.llm.semantic_patch_request_to_scene_patch(...)` to turn a
semantic edit request into Scene Patch JSON. The helper supplies deterministic
patch IDs, preserve constraints, allowed-change categories, continuity, and
acceptance defaults. It validates the result against
[Scene Patch v1](../../schema/scene_patch.schema.json) before returning it.

Use `lathe.wonder.llm.generate_scene_plan(...)` or
`python -m lathe.cli wonder generate-scene-plan` to create a deterministic
Scene Plan from a Dream Brief and optional Scene Graph. Use
`lathe.wonder.llm.build_repair_playbook(...)` or
`python -m lathe.cli wonder repair-playbook` to turn diagnostics into repair
steps. Both helpers are offline and deterministic.

## Authoring Rules

- Treat IDs as stable public references. If an object, region, material, camera,
  light, curiosity anchor, hidden state, or memory event is missing an ID, add a
  schema-valid ID instead of relying on position in an array.
- Scene Patches must carry `preserve` and `allowed_changes`. For object edits,
  preserve `object_id`, `region`, and transform components unless the user
  explicitly requests a transform change.
- Keep Scene Patch operations inside the declared `scope` and `target_id`.
  Cross-object edits should be split into separate patches or raised to a wider
  scope with explicit allowed changes.
- Generated scene source is a bridge format. Full hand-authored scene syntax is
  not accepted by the Phase 7 bridge; use embedded Scene Graph JSON or generate
  source with `lathe.scene.source.scene_graph_to_source`.
- When `lathe scene scene-graph-to-source` emits `SS2001`, keep editing the
  listed JSON Pointer paths in Scene Graph JSON. Those fields are preserved in
  the embedded payload, but the source preview does not yet have first-class
  syntax for them.
- Repair options from `diagnose_for_llm` are suggestions for an authoring loop.
  Validate the edited payload again before applying, building, or reporting
  success.
