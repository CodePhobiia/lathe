# Render Repair Loop

Phase 17 makes render feedback actionable without requiring Lathe to own a
vision model. A Render Inspection payload is treated as structured evidence:
Lathe validates that referenced camera, problem, and patch target IDs exist in
the Scene Graph, then turns each recommendation into a bounded Scene Patch
proposal.

Helpers:

```python
from lathe.scene.repair import inspect_render, propose_repairs, repair_scene_offline
```

Contracts:

```text
schema/render_inspection.schema.json
schema/scene_patch.schema.json
schema/scene_repair_report.schema.json
```

The loop is deterministic and offline:

1. `inspect_render(scene_graph, inspection)` returns schema and semantic
   diagnostics for a Render Inspection payload.
2. `propose_repairs(scene_graph, inspection, goal="wonder_preview")` converts
   valid `recommended_patches` into Scene Patch proposals and emits a repair
   report.
3. `repair_scene_offline(scene_graph, inspection, max_rounds=3)` applies valid
   proposals with `lathe.scene.patch.apply_scene_patch`, records applied and
   rejected rounds, and stops at `max_rounds`.

No renderer, external vision service, or model call happens inside these
helpers. If a proposal has only semantic intent, the existing Scene Patch helper
records patch memory and preserves scene geometry. If a proposal includes
explicit JSON Patch operations, normal Scene Patch scope, allowed-change,
preserve, and continuity checks decide whether it applies.

Repair goals are intentionally narrow:

- `wonder_preview`: style, semantic, composition, and continuity acceptance.
- `export_ready`: semantic, continuity, and export acceptance.
- `roblox_ready`: semantic, continuity, and platform acceptance.

Failed repairs are not hidden. The repair report carries every schema,
inspection, and patch diagnostic plus per-proposal and per-round status so a CLI
or product layer can decide whether to ask for another inspection, adjust the
patch, or stop the loop.
