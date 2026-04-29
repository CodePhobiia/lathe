# MVP Demo Path

The current Wonder seed lives at:

```text
examples/wonder/alchemist_observatory/
```

It includes:

- `prompt.txt`
- `dream_brief.json`
- `scene_graph.json`
- `scene_patch_more_sacred.json`
- `render_inspection.example.json`
- `expected/scene_manifest.example.json`
- `expected/wonder_report.example.json`

The near-term golden path is:

```text
prompt
-> dream_brief.json
-> scene_graph.json
-> validate contracts
-> lower scene graph into asset builds
-> assemble preview scene
-> render canonical cameras
-> inspect render
-> apply scene patch
-> compare before/after proxy renders
-> export scene package
```

The current slice reaches the deterministic package path with checked proxy PNG
renders, a before/after proxy comparison after patching, and a declared proxy
GLB export in the Scene Package. The remaining demo gap is final artifact
confidence: vision/evaluator inspection of produced images, external viewer
validation, Roblox export lanes, POSIX evidence, and fresh-clone or hosted CI
confirmation before alpha promotion.
