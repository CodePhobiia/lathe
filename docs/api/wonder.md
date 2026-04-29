# `lathe.wonder`

::: lathe.wonder

## Purpose

`lathe.wonder` contains the schema-first JSON bridge for Project Wonder. It
loads committed Wonder schemas, validates untrusted JSON files at the Wonder
contract boundary, reports machine-readable capabilities, and lowers structured
Dream Brief payloads into deterministic initial Scene Graphs.

These helpers intentionally avoid optional mesh, Blender, learned-provider, and
runtime-heavy imports so contract validation can run in lightweight
environments.

## Current Public Helpers

- `get_contract_schema`, `list_contract_summaries`, and `contract_schema_path`
  expose committed Wonder schemas.
- `load_and_validate_contract` and `validate_contract` validate Dream Brief,
  Scene Graph, Scene Patch, Render Inspection, World Memory, and Scene Package
  Manifest JSON, plus Scene Plan JSON.
- `lower_dream_brief_to_scene_graph` provides deterministic offline lowering for
  tests, examples, and local Wonder readiness demos.
- `decompose_dream_brief` and `check_brief_scene_consistency` support the
  JSON-first prompt-to-scene bridge.
- `wonder_capabilities` emits the current machine-readable capability surface.

Scene patching, source bridge conversion, offline package building, and quality
validation live under `lathe.scene`; `lathe.wonder` stays focused on shared JSON
contracts and LLM-safe authoring boundaries.
