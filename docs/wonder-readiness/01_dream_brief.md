# Dream Brief

The Dream Brief is the structured bridge between natural language and scene
planning. It captures the user's intent in a compact form that can be checked
before any Lathe scene graph or asset source is generated.

Schema:

```text
schema/dream_brief.schema.json
```

Required concepts:

- `brief_id`: stable snake-case identity for the brief.
- `title` and `one_sentence`: concise product-facing description.
- `scale`: first target scene scale, such as `single_room`.
- `intent`: setting, emotional goal, primary interaction, and spatial logic.
- `style`: palette, materials, lighting, form language, and avoided styles.
- `required_elements`: objects or features that must survive lowering.
- `constraints`: platform, complexity, performance, and content boundaries.
- `export_targets`: requested outputs such as `scene_graph`, `glb`, or
  `scene_package`.

Validation:

```bash
python -m lathe.cli wonder validate-brief examples/wonder/alchemist_observatory/dream_brief.json
```

The Dream Brief should be the first machine-authored artifact in a Wonder loop.
Models should emit this JSON before scene graph JSON or `.lth` source.
