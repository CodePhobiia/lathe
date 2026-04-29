# Bad LLM Outputs

These fixtures show repairable model-output failures and the expected
diagnostic category for each one. They are checked by
`tests/unit/test_wonder_llm.py`.

- `invalid_scene_plan_missing_camera.json`: a Scene Plan missing a render task.
  Repair by adding a deterministic camera-backed render task and rerunning
  Scene Plan validation.
- `invalid_patch_unknown_target.json`: a Scene Patch targeting an object ID not
  present in the Scene Graph. Repair by choosing an existing target for the
  declared scope or adding the entity before patch validation.
- `invalid_memory_with_secret.json`: a World Memory-like payload containing
  sensitive operator metadata. Repair by redacting secret-bearing fields before
  preserving memory.
- `invalid_scene_source_bad_id.lth`: generated scene source with an invalid
  object ID inside the embedded Scene Graph payload. Repair by replacing the ID
  with a stable `obj_<snake_id>` value and updating references.
