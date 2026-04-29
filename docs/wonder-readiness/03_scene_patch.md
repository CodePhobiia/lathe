# Scene Patch

Scene Patch is the continuity-aware edit contract. It is meant for commands such
as "make this object more sacred" or "open this region while preserving the
central chamber layout."

Schema:

```text
schema/scene_patch.schema.json
```

Patch scopes:

- `asset`
- `object`
- `region`
- `scene`
- `camera`
- `light`
- `curiosity_anchor`
- `hidden_state`

Each patch names:

- `target_id`: the stable scene, region, object, or related ID to edit.
- `instruction`: human or model-authored semantic edit intent.
- `preserve`: facts, IDs, transforms, or constraints that must remain stable.
- `allowed_changes`: the limited edit surface for the patch.
- `continuity`: optional branch and identity preservation metadata.
- `acceptance`: validators and minimum score expected after the patch.

Validation:

```bash
python -m lathe.cli wonder validate-patch examples/wonder/alchemist_observatory/scene_patch_more_sacred.json
```

Application:

```bash
python -m lathe.cli scene patch \
  examples/wonder/alchemist_observatory/scene_graph.json \
  examples/wonder/alchemist_observatory/scene_patch_more_sacred.json \
  --out dist/updated_scene_graph.json
```

Use `--preview` to emit the updated Scene Graph, diagnostics, and World
Memory-ready patch event without writing `--out`.

Patch application is JSON-first. Explicit `operations` are applied as JSON
Patch-style edits after scope, `allowed_changes`, `preserve`, and continuity
checks. If a patch has only `instruction`, Lathe records the semantic request
as patch memory and does not invent geometry or layout edits.

Continuity defaults are conservative:

- existing stable IDs are preserved unless the patch declares
  `continuity.mode: "free_revision"`;
- object transforms are preserved unless `allowed_changes` includes
  `transforms` or the edited component is `scale` and `allowed_changes`
  includes `scale`;
- fields, IDs, and transforms named in `preserve` are never mutated by the
  helper.

The CLI validates the Scene Graph before and after patching. Failures are
reported as machine-readable diagnostics and do not write the output file.
