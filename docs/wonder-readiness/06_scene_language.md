# Scene Language

Scene source is an additive Wonder authoring surface. It is not the durable
runtime truth yet. The durable truth for the current Wonder layer remains
`lathe.scene_graph.v1`, and checked-in Wonder examples still record their scene
source status as deferred until hand-authored scene files can be promoted
without losing stable IDs or schema coverage.

The design background lives in
[Scene Source Language Design](06_scene_language_design.md) and
[ADR 0010](../adr/0010-experimental-scene-source-language.md).

## Current Contract Boundary

The scene source bridge currently supports a JSON-first flow:

```text
scene_graph.json
-> scene-graph-to-source
-> generated reviewable scene source
-> source-to-scene-graph
-> checked Scene Graph JSON
```

This bridge is useful for model repair, code review, and roundtrip checks. It
does not replace the Scene Graph as the source of record for Wonder examples.

The existing Lathe asset language remains stable. Asset declarations such as
`profile`, `contract`, `critic`, `asset`, `variant`, and build-stage blocks do
not inherit Project Wonder product state. Scene-aware source is layered above
assets and lowers to the same JSON contracts used by the runtime.

## Implemented Shape

The bridge can describe the scene-level concepts already present in the Scene
Graph:

- scene identity, version, prompt, and brief reference;
- style bible values;
- regions with bounds, purpose, mood, and semantic tags;
- object instances with stable object IDs, source assets, transforms,
  material bindings, state, and gameplay hints;
- relationships between scene references;
- lights and cameras;
- export declarations.

The bridge preserves the Scene Graph ID prefixes such as `region_`, `obj_`,
`rel_`, `camera_`, `light_`, and `mat_`.

## What Remains Deferred

These claims are still out of scope for the current scene language page:

- every Wonder example as a committed `.lth` scene source fixture;
- full grammar parity with every Scene Graph field;
- branch and merge syntax;
- provenance syntax;
- advanced layout solver syntax;
- direct Blender, Roblox, or external-viewer execution through scene source.

Until those land, JSON contracts remain the interface Project Wonder should
call, and scene source is a review/repair bridge.

## Validation Surface

The current evidence is covered by:

- `tests/unit/test_scene_source_language.py`;
- `tests/unit/test_scene_source_roundtrip.py`;
- `tests/unit/test_scene_source_diagnostics.py`;
- `tests/unit/test_wonder_examples_catalog.py`.

Those tests prove the source bridge can roundtrip supported scene data and emit
useful diagnostics, while the example catalog truthfully reports source files as
deferred rather than complete.
