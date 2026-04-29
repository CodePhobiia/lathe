# Branching, Versioning, Diff, and Merge

Phase 16 adds pure helpers and CLI surfaces for scene continuity workflows. The
core helpers live in:

```text
lathe/scene/versioning.py
```

Schemas:

```text
schema/scene_branch.schema.json
schema/scene_diff.schema.json
schema/scene_history.schema.json
```

## Branch Payloads

`create_branch(scene_graph, name, parent="main")` returns a
`lathe.scene_branch.v1` payload with:

- a stable `branch_id` derived from the branch name;
- an explicit `parent_branch`;
- a base version node tied to the parent branch;
- a head version node tied to the new branch;
- deterministic scene fingerprints and version IDs.

The helper does not mutate the Scene Graph and does not create files.

## Diff Payloads

`diff_scene_graphs(left, right)` returns a `lathe.scene_diff.v1` payload. Diffs
are keyed by stable scene IDs rather than list positions where possible, so
object changes remain reviewable when arrays are reordered.

Tracked changes include:

- object additions and removals;
- object transform changes;
- object material binding changes;
- object state changes;
- material additions, removals, and definition changes;
- other scene entity additions, removals, and definition changes;
- top-level scene metadata changes.

`validate_scene_diff_payload(payload)` checks both JSON Schema shape and
semantic invariants such as unique change IDs, add/remove/replace value shape,
same-scene endpoints, and summary counters.

## Merge Behavior

`merge_scene_graphs(source, target)` returns a `SceneMergeResult` containing the
target-shaped merged Scene Graph, diagnostics, the source-vs-target diff, and
applied/skipped change records.

The merge is deterministic and conservative:

- source-only regions, materials, objects, relationships, lights, cameras,
  curiosity anchors, and hidden state are appended by stable ID order;
- existing object `state` keys are merged only when the source key is absent or
  already equal in the target;
- existing object material binding slots are merged only when the source slot is
  absent or already equal in the target;
- object transforms are never overwritten when same-ID objects differ;
- material definitions with the same `material_id` are never overwritten when
  they differ;
- non-mergeable same-ID object field differences are reported as diagnostics.

Stable object IDs are preserved. The helper does not rename or regenerate object
IDs to resolve conflicts.

## Branch Asset Reuse

`plan_scene(scene_graph, reuse_from_plan=base_plan)` embeds a
`lathe.scene_plan_branch_reuse.v1` report under `branch_reuse`. The report
compares the branch Scene Plan's asset cache keys with the base plan and
separates unchanged asset builds from new, non-shareable, and base-only tasks.
Transform, naming, role, and other instance-only edits keep the same asset cache
key; material bindings, state, variant, source, and plan mode changes produce a
new key and are not reused.

The CLI exposes the same comparison:

```powershell
python -m lathe.cli scene plan base.scene_graph.json --out base.scene_plan.json
python -m lathe.cli scene plan branch.scene_graph.json --reuse-from-plan base.scene_plan.json --out branch.scene_plan.json
```

The comparison is deterministic and diagnostic-only. It does not mutate the
Scene Graph or copy build artifacts; it tells the scene build layer which
planned asset tasks can safely share prior work.

## Patch History And Rollback

Wave 2 adds deterministic patch history records for mutation safety. Successful
`lathe wonder apply-patch` calls can update a `lathe.scene_history.v1` payload
with:

- the patch memory `event_id`;
- a forward patch path or payload;
- an embedded inverse patch payload;
- `before_scene_hash` and `after_scene_hash`;
- deterministic timestamp data;
- validation and render report arrays, empty when optional reports are absent.

Rollback is hash guarded. `lathe scene rollback` and
`lathe wonder rollback-scene` refuse to apply an inverse patch unless the current
Scene Graph hash matches the selected history record's `after_scene_hash`. When
the guard passes, the inverse patch is applied and the resulting Scene Graph
must match `before_scene_hash`.

Branch history is reported from World Memory with linked patch-history reports
when available. Linked records carry optional `validation_reports`,
`render_reports`, and `comparison_reports` arrays so branch views can keep
quality, render, and before/after comparison evidence attached to the patch
events that produced them:

```powershell
python -m lathe.cli wonder apply-patch scene_graph.json patch.json --out patched.scene_graph.json --history history.json
python -m lathe.cli scene rollback patched.scene_graph.json --history history.json --to mem_patch_001 --out rolled_back.scene_graph.json
python -m lathe.cli wonder rollback-scene patched.scene_graph.json --history history.json --to-event mem_patch_001 --out rolled_back.scene_graph.json
python -m lathe.cli wonder branch-history --memory world_memory.json --branch main --history history.json --out branch_history.json
```

Missing optional validation or render history is represented as empty arrays.
These helpers are JSON-only and do not invoke Blender, Roblox Studio, provider
runtimes, or external viewers.

## Validation

Focused local checks:

```bash
python -m pytest tests/unit/test_scene_versioning.py -q
python -m pytest tests/unit/test_scene_history.py tests/unit/test_scene_rollback.py -q
python -m ruff check lathe/scene/versioning.py tests/unit/test_scene_versioning.py
```
