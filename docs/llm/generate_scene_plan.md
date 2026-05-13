# Generate Scene Plan

`lathe wonder generate-scene-plan` creates a deterministic offline Scene Plan
from a Dream Brief and, when provided, an existing Scene Graph.

```powershell
python -m lathe.cli wonder generate-scene-plan `
  examples/wonder/alchemist_observatory/dream_brief.json `
  --scene-graph examples/wonder/alchemist_observatory/scene_graph.json `
  --out .tmp_tests/wonder_scene_plan.json
```

Input contracts:

- Dream Brief: [schema/dream_brief.schema.json](../schema/dream_brief.schema.json)
- Scene Graph: [schema/scene_graph.schema.json](../schema/scene_graph.schema.json)

Output contract:

- Scene Plan: [schema/scene_plan.schema.json](../schema/scene_plan.schema.json)

The command does not call an LLM, learned provider, Blender, Roblox Studio, or
an external viewer. Asset tasks use existing deterministic/proxy planning
language. Render tasks are derived from Scene Graph cameras when available. If
`--scene-graph` is omitted, Lathe lowers the brief through the deterministic
brief-to-scene helper and emits a warning diagnostic that object and camera
specificity is reduced.

