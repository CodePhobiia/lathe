# Wonder Benchmark Suite

Phase 31 adds a compact benchmark prompt corpus at `benchmarks/wonder/`. The
corpus is data-only; it is not a claim that the scenes currently build, render,
patch, or export.

## Corpus

`benchmarks/wonder/prompts.json` contains ten named prompts:

1. `alchemist_observatory`
2. `mountain_lightning_city`
3. `abandoned_roblox_mall`
4. `underwater_train_station`
5. `desert_oracle_shrine`
6. `cozy_witch_greenhouse`
7. `cyberpunk_noodle_alley`
8. `ancient_moon_elevator`
9. `horror_obby_lobby`
10. `luxury_tycoon_showroom`

Each prompt includes:

- the canonical natural-language prompt
- a scene type
- three style variations
- three continuity-preserving patch operations
- scoring focus tags

## Report Helper

`lathe.scene.bench.benchmark_scene(scene_graph, timings, scores)` produces a
`lathe.scene_benchmark_report.v1` payload with:

- stage timing pass/fail results against committed budgets
- normalized score pass/fail results against committed thresholds
- observed and potential cache reuse metrics
- deterministic stage and metric ordering
- a summary status of `passed`, `failed`, or `passed_with_exceptions`

The helper is intentionally lightweight. It evaluates measured input and emits a
report; it does not orchestrate CLI commands or run external providers.

## Timing Input

Timing values can be passed as stage mappings:

```json
{
  "stages": {
    "brief": {"duration_ms": 8000},
    "scene_graph": {"duration_ms": 18000},
    "source_generation": {"duration_ms": 8000},
    "check_plan": {"duration_ms": 4000},
    "preview_build": {"duration_ms": 50000},
    "preview_render": {"duration_ms": 20000},
    "patch_preview": {"duration_ms": 30000},
    "final_export": {"duration_ms": 120000}
  },
  "cache": {"hits": 2, "misses": 2, "writes": 1}
}
```

Bare numeric timing values are interpreted as seconds to match the existing
Lathe benchmark harness convention.

## Score Input

Scores are normalized values in `[0, 1]`. Boolean values are accepted for binary
gates such as parse/check, build success, patch success, and export validity.

The report schema is `schema/scene_benchmark_report.schema.json`; focused unit
coverage lives in `tests/unit/test_scene_bench.py`.
