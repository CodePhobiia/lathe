# Scene Graph

The Scene Graph is the persistent truth model for a Wonder scene. It gives every
region, object, camera, light, curiosity anchor, and hidden fact a stable ID so
future patches can preserve continuity.

Schema:

```text
schema/scene_graph.schema.json
```

Required top-level arrays:

- `regions`
- `objects`
- `relationships`
- `materials`
- `lights`
- `cameras`
- `curiosity_anchors`
- `hidden_state`
- `exports`
- `build_artifacts`
- `memory_events`

Object instances carry:

- Stable `object_id` values such as `obj_astrolabe_table_001`.
- Scene-local `transform` data.
- Links to `lathe_asset`, `source_family`, or `source_kit`.
- `semantic_tags`, `state`, `affordances`, material bindings, and provenance.

Validation:

```bash
python -m lathe.cli wonder validate-scene examples/wonder/alchemist_observatory/scene_graph.json
```

JSON Schema validates the shape of the scene graph. A future scene validator
will add cross-reference checks, layout checks, continuity checks, and export
target checks.
