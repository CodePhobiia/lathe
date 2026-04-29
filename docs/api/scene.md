# `lathe.scene`

::: lathe.scene

## Purpose

`lathe.scene` is the Wonder-readiness package for scene-level contracts that sit
above the current asset compiler. The package currently exposes helpers for
Scene Graph semantic checks, stable scene IDs, folder-based scene packages, World
Memory validation, and scene quality validation.

The package is contract and validation oriented. It does not own Project Wonder
chat, account, gallery, payment, or model-routing behavior.

## Current Public Helpers

- `check_scene_graph` and `load_and_check_scene_graph` validate references and
  safe artifact paths in schema-valid Scene Graph payloads.
- `scene_entity_id`, `snake_id`, and ID predicate helpers produce deterministic
  identifiers that match the Wonder schemas.
- `init_scene_package`, `check_scene_package_manifest`, and
  `load_and_validate_scene_package_manifest` create and validate folder-based
  scene packages.
- `run_scene_validators` and `validate_scene_quality` run the current
  scene-level quality validators.

