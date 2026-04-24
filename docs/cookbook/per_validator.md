# Per-validator reference

One-page index into the five shipped validators under `lathe/validators/`. Each validator has its own generated API page with pass/fail criteria and metric definitions; this page is the jumping-off point.

Validators run at the end of the stage pipeline, after `optimize`. Their aggregated output determines whether a build is `certified` or `rejected`. See [Reading a trace](reading_a_trace.md) for how their output lands in `build_report.json`, and [Recipe 09 — Certification debug](09_certification_debug.md) for the triage workflow.

## Validators

| Validator | Source | Page | Scope |
|---|---|---|---|
| `semantic_quality` | [`lathe/validators/semantic_quality.py`](https://github.com/talmerri/lathe/blob/main/lathe/validators/semantic_quality.py) | [API page](../api/validators/semantic_quality.md) | Intent preservation, geometry integration, symmetry, part graph. |
| `visual_quality` | [`lathe/validators/visual_quality.py`](https://github.com/talmerri/lathe/blob/main/lathe/validators/visual_quality.py) | [API page](../api/validators/visual_quality.md) | Render-level silhouette checks, normal/bake quality, visual readability. |
| `flow_quality` | [`lathe/validators/flow_quality.py`](https://github.com/talmerri/lathe/blob/main/lathe/validators/flow_quality.py) | [API page](../api/validators/flow_quality.md) | Flow-specific metrics: `semantic_preservation_quality` (adapt), `join_legality` (assemble), `reconstruct_honesty_score` (reconstruct). |
| `surface_quality` | [`lathe/validators/surface_quality.py`](https://github.com/talmerri/lathe/blob/main/lathe/validators/surface_quality.py) | [API page](../api/validators/surface_quality.md) | V1.2 zone coverage, decal budgets, mask drift, trim compliance. |
| `silhouette` | [`lathe/validators/silhouette.py`](https://github.com/talmerri/lathe/blob/main/lathe/validators/silhouette.py) | [API page](../api/validators/silhouette.md) | Silhouette IOU, fragmentation, coarse/fine readability. |

## Which validators run when

The validator set fires every build, but individual metrics only score against the features actually declared in the asset:

- `semantic_quality` — always; core geometry/topology checks.
- `visual_quality` — always when a surface stage ran; otherwise skipped.
- `flow_quality` — active when the shape mode is `reconstruct`, `adapt`, or `assemble`. In `generate` mode the validator still runs but reports `n/a` for flow-specific metrics.
- `surface_quality` — active when the V1.2 surface backend was used. Otherwise reports `n/a`.
- `silhouette` — always.

## Critic vs validator

Two distinct concepts:

- **Critic** — declared in the `.lth` as `critic foo(a: asset) = weighted { ... }`. Assigns weights to metric names and aggregates them into a single score. Passed/failed via `validate.threshold`.
- **Validator** — Python code under `lathe/validators/` that *produces* the metrics the critic weights. Validators also emit diagnostics (codes like `TOPO_NGON_FOUND`) independent of the critic score.

A build can pass the critic threshold but still have validator warns. Warn-level diagnostics are lint; `severity = fatal` ones block certification regardless of the score.

## Diagnostic severity levels

| Severity | Effect |
|---|---|
| `info` | Informational; no gating. |
| `warn` | Recorded; does not block certification. |
| `error` | Contributes negatively to the metric; may cause the score to dip below threshold. |
| `fatal` | Hard-blocks certification regardless of score. |

## See also

- [Reading a trace](reading_a_trace.md) — the `validate` block of `build_report.json`.
- [Recipe 09 — Certification debug](09_certification_debug.md) — triage playbook.
- API (top-level): [validators index in mkdocs nav](../api/validators/semantic_quality.md).
