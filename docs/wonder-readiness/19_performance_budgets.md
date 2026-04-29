# Wonder Performance Budgets

Phase 30 defines lightweight, deterministic budgets for the Project Wonder
preview loop. These budgets are targets for benchmark reports, not proof that a
scene has rendered or exported.

## Budget Constants

The committed helper is `lathe.scene.bench.benchmark_scene`. It consumes a
Scene Graph plus measured timing and score dictionaries, then returns a
`lathe.scene_benchmark_report.v1` report.

| Stage | Budget | Applies to |
| --- | ---: | --- |
| Dream Brief | 10 s | preview and final |
| Scene Graph | 20 s | preview and final |
| Scene source generation | 10 s | preview and final |
| Check and plan | 5 s | preview and final |
| Preview build | 60 s | preview |
| Preview render | 30 s | preview |
| Patch preview | 45 s | preview |
| Final export | 180 s | final |

Time to first render is the sum of Dream Brief, Scene Graph, source generation,
check/plan, preview build, and preview render. The current target is 135 s.

## Final Export Exceptions

Final export should normally be measured against the 180 s budget. A report may
mark final export as excepted only when the timing input records one of these
explicit reasons:

- `external_exporter_unavailable`
- `manual_review_required`
- `target_runtime_unavailable`

An excepted final export keeps the report honest by returning
`passed_with_exceptions` rather than `passed`.

## Score Thresholds

The benchmark helper evaluates these normalized score metrics:

| Metric | Threshold |
| --- | ---: |
| Prompt to brief | 0.80 |
| Brief to scene | 0.80 |
| Parse and check | 1.00 |
| Build success | 1.00 |
| Scene validation | 0.85 |
| Style consistency | 0.80 |
| Object count accuracy | 0.80 |
| Render quality | 0.80 |
| Patch success | 1.00 |
| Continuity preservation | 0.85 |
| Export validity | 1.00 |

Scores can be numeric values in `[0, 1]`; boolean scores are accepted for
binary gates and map to `1.0` or `0.0`.

## Cache Reuse

Reports include two cache signals:

- Observed reuse: `hits / eligible` from the timing input. The minimum passing
  ratio is 0.25.
- Potential reuse: a deterministic estimate from Scene Graph object source
  signatures. It shows how many objects could share asset work even before a
  runner measures cache hits.

Missing cache data fails the benchmark report because Phase 31 needs cache reuse
to be tracked as a first-class readiness metric.

## Report Contract

The report schema lives at `schema/scene_benchmark_report.schema.json`.
Validation helpers are available as:

```python
from lathe.scene.bench import (
    benchmark_scene,
    get_scene_benchmark_report_schema,
    validate_scene_benchmark_report_payload,
)
```

The helper is pure: it does not run builds, renderers, exporters, network calls,
or CLI commands. The future `lathe scene bench` command can wire real
measurements into this report without changing the contract.

## CI And Nightly Lane

The deterministic Wonder benchmark lane is defined in
`.github/workflows/wonder-benchmarks.yml`. It runs on a nightly schedule and by
manual dispatch, executes `scripts/ci_wonder_benchmarks.py`, and uploads both
the CI lane report and the generated `lathe.scene_benchmark_report.v1` artifact.

The lane remains deterministic: it validates the benchmark helper, exercises
`lathe scene bench` against the alchemist observatory Scene Graph with checked
timing/score inputs, and validates the emitted benchmark report. It does not
claim provider cost, real renderer timing, hosted CI success, or external export
viewer proof until those environments produce their own evidence.
