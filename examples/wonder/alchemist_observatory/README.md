# Alchemist Observatory Wonder Seed

This folder is the first schema-first Wonder readiness seed. It does not use
new `.lth` scene syntax yet; the committed JSON contracts are the stable bridge
for the future scene runtime.

Run the contract checks from the repository root:

```bash
python -m lathe.cli wonder validate-brief examples/wonder/alchemist_observatory/dream_brief.json
python -m lathe.cli wonder validate-scene examples/wonder/alchemist_observatory/scene_graph.json
python -m lathe.cli wonder validate-patch examples/wonder/alchemist_observatory/scene_patch_more_sacred.json
python -m lathe.cli wonder validate-render-inspection examples/wonder/alchemist_observatory/render_inspection.example.json
```
