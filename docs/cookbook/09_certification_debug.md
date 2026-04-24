# Recipe 09 — Debugging a failing certification

## Goal

Work through a failing build report from the top: identify the failing validator, locate the offending metric, apply a targeted fix (either a source change, a variant patch, or a repair allow-list tweak), and rebuild. This recipe is the survival guide when `lathe build` exits with `status: rejected`.

## Prerequisites

- Lathe v0.1+.
- Any asset; we use `examples/courier_drone.lth` as the running example.
- Familiarity with the five shipped validators: [`semantic_quality`](../api/validators/semantic_quality.md), [`visual_quality`](../api/validators/visual_quality.md), [`flow_quality`](../api/validators/flow_quality.md), [`surface_quality`](../api/validators/surface_quality.md), [`silhouette`](../api/validators/silhouette.md).

## Walkthrough

### Step 1 — reproduce the failure

Simulate a failing build by tightening the threshold:

```lth
variant courier_drone_strict on courier_drone {
  set validate.threshold = 0.95
}
```

Then:

```bash
python -m lathe.cli build examples/courier_drone.lth courier_drone_strict --out dist
```

Expected exit code != 0 with:

```
build: rejected
  score: 0.88
  threshold: 0.95
  see: dist/courier_drone_strict/build_report.json
```

### Step 2 — read `build_report.json`

Open `dist/courier_drone_strict/build_report.json`. The interesting sections:

```json
{
  "status": "rejected",
  "validate": {
    "score": 0.88,
    "threshold": 0.95,
    "critic": "hero_prop",
    "per_metric": {
      "prompt_match": 0.85,
      "silhouette_readability": 0.93,
      "topology_quality": 0.80,
      "material_quality": 0.90,
      "runtime_efficiency": 0.95,
      "part_coherence": 0.90
    },
    "diagnostics": [
      {
        "code": "TOPO_NGON_FOUND",
        "validator": "semantic_quality",
        "severity": "warn",
        "message": "3 ngons detected in retopo output",
        "location": "stages/topology/bundle.json#/mesh_stats/ngons"
      }
    ]
  }
}
```

The **per-metric** block is the first thing to read. In this case `topology_quality = 0.80` is dragging the weighted average below the threshold. That immediately tells you the topology stage is the problem.

### Step 3 — use `lathe explain`

`explain` summarizes the rejection in a human-readable form:

```bash
python -m lathe.cli explain dist/courier_drone_strict
```

Output:

```
Asset: courier_drone_strict
Status: REJECTED (score 0.88 < threshold 0.95)

Worst metric: topology_quality = 0.80 (weight 0.20)
Contributing diagnostics:
  [semantic_quality/warn]  TOPO_NGON_FOUND  3 ngons detected in retopo output

Attempted repair rounds: 4/4 exhausted
  round 1: retopo_auto     -> topology_quality 0.78 -> 0.80
  round 2: reduce_tris     -> no metric change
  round 3: repack_uvs      -> material_quality 0.88 -> 0.90
  round 4: rebake_maps     -> no metric change

Suggested next action: the repair loop cannot fix ngon count because `rebuild_shape` is denied.
See validate.repair.deny in source.
```

### Step 4 — locate the diagnostic code

Every diagnostic has a stable code. They are grouped by validator:

| Validator | Example codes |
|---|---|
| `semantic_quality` | `TOPO_NGON_FOUND`, `PART_GRAPH_BROKEN`, `SYMMETRY_LOST`, `SEAM_UNCLASSIFIED` |
| `visual_quality` | `SILHOUETTE_IOU_LOW`, `RENDER_BLUR_DETECTED`, `NORMAL_MAP_CLIPPED` |
| `flow_quality` | `SEMANTIC_PRESERVATION_LOW`, `JOIN_LEGALITY_LOW`, `RECONSTRUCT_HONESTY_LOW` |
| `surface_quality` | `ZONE_COVERAGE_LOW`, `DECAL_BUDGET_EXCEEDED`, `MASK_COVERAGE_OVER` |
| `silhouette` | `SILHOUETTE_COARSE`, `SILHOUETTE_FRAGMENTED` |

Look the code up with `grep` under `lathe/validators/`:

```bash
grep -rn 'TOPO_NGON_FOUND' lathe/validators/
```

The hit points at the exact function that raised the diagnostic, which tells you what knob controls it.

### Step 5 — pick a fix strategy

Three common fixes:

**Fix A — source change.** Edit the `.lth` to push topology toward quads:

```lth
build {
  topology {
    retopo = auto
    target_quads = 22000      // up from 18000
    ngons = forbid            // already forbid; make sure it's set
    preserve = [hard_edges, part_borders]
  }
}
```

**Fix B — variant patch.** Add a one-off override without touching the hero source:

```lth
variant courier_drone_strict on courier_drone {
  set validate.threshold = 0.95
  set build.topology.target_quads = 22000
}
```

**Fix C — repair policy.** If the hero is fine but specific edge cases fail, allow a broader repair move:

```lth
validate {
  repair {
    mode = auto_until_pass
    max_rounds = 6              // up from 4
    allow = [
      reselect_candidate,
      retopo_auto,
      reduce_tris,
      repack_uvs,
      rebake_maps,
      rebuild_shape              // was in `deny`; now allowed
    ]
  }
}
```

Use Fix A for systemic issues, Fix B for variant-specific tweaks, Fix C only when you are sure the looser repair is safe.

### Step 6 — rebuild and compare

```bash
python -m lathe.cli build examples/courier_drone.lth courier_drone_strict --out dist
python -m lathe.cli diff-asset \
    examples/courier_drone.lth courier_drone \
    examples/courier_drone.lth courier_drone_strict
```

`diff-asset` shows the new topology parameters. `build_report.json` should now show `status: certified`.

## Quick reference — diagnostic → likely fix

| Diagnostic | Most likely fix |
|---|---|
| `TOPO_NGON_FOUND` | Raise `target_quads`, ensure `ngons = forbid`, allow `retopo_auto` repair. |
| `PART_GRAPH_BROKEN` | Add `part_graph` to `build.shape.preserve`. |
| `SYMMETRY_LOST` | Add `symmetry` to `preserve`, or set `build.shape.symmetry = x`. |
| `SILHOUETTE_IOU_LOW` | More `candidates`, or add reference images to `refs`. |
| `ZONE_COVERAGE_LOW` | Check V1.2 `material_zones` — a zone has no filler. |
| `DECAL_BUDGET_EXCEEDED` | Trim `surface.decals`, or loosen `runtime_budget.texture_memory`. |
| `SEMANTIC_PRESERVATION_LOW` | Reduce aggressiveness of `adapt_policy`, or widen `preserve`. |
| `JOIN_LEGALITY_LOW` | The asset used a join not in `kit.allowed_joins`; pick a different kit or extend it. |
| `RECONSTRUCT_HONESTY_LOW` | Reconstruct output drifted too far from the refs; tighten `fit_profile`. |

## Output

A certified build emits:

```json
{
  "status": "certified",
  "validate": {
    "score": 0.96,
    "threshold": 0.95,
    "diagnostics": []
  }
}
```

`status: certified` with empty `diagnostics` is the clean success. A certified build with non-empty warn-level diagnostics is still a pass — treat warns as lint.

## Variations

- **Only rerun validation** — if you have a `dist/<asset>/` from a previous run and just want to re-score:
  ```bash
  python -m lathe.cli surface-validate examples/courier_drone.lth courier_drone --out dist
  ```
  Works for V1.2 surface only; other stages require a full rebuild.
- **Crank repair rounds** — `set validate.repair.max_rounds = 8` before giving up entirely. Diminishing returns past 4–5.
- **Reset and retry with a different seed** — failing once at seed 42 does not mean failing at seed 7. Change `build.shape.seed` and rebuild before blaming the source.

## Troubleshooting

- `explain: build_report.json not found` — the build never got to the validator stage. Rerun `build` and check for an earlier failure in stdout.
- `diagnostics: []` but `status: rejected` — a `fatal` diagnostic from an earlier stage was surfaced differently. Check the stage bundles directly: `stages/shape/bundle.json`, `stages/topology/bundle.json`, etc.

## See also

- API: [validators index](per_validator.md), [`lathe.executor`](../api/executor.md).
- [Reading a trace](reading_a_trace.md).
- [Recipe 06 — Variant patching](06_variant_patching.md).
