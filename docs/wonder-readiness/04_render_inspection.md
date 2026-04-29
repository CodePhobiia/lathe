# Render Inspection

Render Inspection is the bridge from rendered evidence back into repair and
revision. It can be produced by a vision model, a deterministic evaluator, or a
human review tool, as long as it returns structured problems and patch
recommendations.

Schema:

```text
schema/render_inspection.schema.json
```

The contract records:

- `render_ref`: image path, camera ID, and render pass.
- `scores`: brief match, style consistency, spatial coherence, composition,
  curiosity, and overall quality.
- `problems`: target-specific issues grounded in the render.
- `recommended_patches`: bounded changes that can become Scene Patch inputs.

Validation:

```bash
python -m lathe.cli wonder validate-render-inspection examples/wonder/alchemist_observatory/render_inspection.example.json
```

Lathe does not need to own the vision model. It does need to own this exchange
format so inspection, repair, and continuity can stay structured.
