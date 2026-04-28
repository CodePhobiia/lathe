# `perf/` — Lathe performance budgets

This directory holds per-hero, per-stage build-time baselines and a
forward-looking regression gate.

## Files

- `manifest.json` - authored per-hero, per-stage ceilings consumed by
  `python scripts/profile_heroes.py --manifest`. This is the CI-facing
  regression gate for common hero builds.

- `budgets.json` — current source of truth. Schema:
  ```json
  {
    "heroes": {
      "<hero_name>": {
        "wall_ms": 12345.6,
        "stages": {
          "<stage>": {
            "current_ms": 1234.5,
            "source": "build_report" | "mtime_delta" | "mtime_delta_first_stage_unknown" | "mtime_delta_untrusted_cache_mtime" | "stage_not_present",
            "budget_ms": 1481.4
          }
        },
        "score": 0.87,
        "threshold": 0.86,
        "certified": true
      }
    },
    "budget_headroom": 1.2,
    "updated_utc": "2026-04-24T..."
  }
  ```
- `heroes_<UTC-date>.json` — historical record of one profile run. Useful
  for plotting drift over time. Not consumed by the regression gate.

## Why

Each hero build is a deterministic, cached pipeline. Once a hero is
green, its build time is the closest thing Lathe has to a continuous
performance signal. A 20% slowdown on `surface` for `courier_drone` is
almost always a regression, not a "feature" — even when functional
tests stay green.

`budgets.json` makes that regression detectable. The gate fires at
`current_ms > budget_ms` (i.e., `current_ms > baseline * BUDGET_HEADROOM`,
default 1.20).

## Refreshing baselines

```bash
# Refresh all heroes
python scripts/profile_heroes.py --write

# Refresh just one hero
python scripts/profile_heroes.py --only courier_drone

# Sanity-verify against the existing budget (exits 2 on regression)
python scripts/profile_heroes.py --verify
```

`--write` is the default mode. `--only NAME` is additive — it merges
into the existing `budgets.json` rather than replacing it.

## Current Gate

- Script: `scripts/profile_heroes.py`.
- Per-stage timings: opportunistic. We prefer
  `build_report.json["stages"][<stage>]["elapsed_ms"]` (BL-33 / BL-36 may
  wire it later) and fall back to **bundle-file mtime deltas** when the
  executor has not been instrumented yet. mtime deltas are coarse but
  monotonic enough for "did this stage just get 5x slower" detection.
- The authored manifest gate runs in `.github/workflows/benchmarks.yml`
  and can be run locally with `python scripts/profile_heroes.py --manifest`.
  The legacy inferred-budget gate remains available with `--verify`.

### Known limitations

- Re-profiling a hero whose build cache is warm may copy stage artifacts
  with preserved historical mtimes. Those stages are now reported as
  `current_ms: null` with `source: "mtime_delta_untrusted_cache_mtime"`
  instead of producing false regressions. The resulting `wall_ms` is the
  cache-hit total. To baseline a clean run, delete `tmp_profile/<hero>/`
  and the relevant Lathe build cache first.
- The `shape` stage is always `current_ms: null` under mtime deltas
  because there is no prior bundle to subtract from. Real wall time is
  encoded in `wall_ms - sum(stages_after_shape)`.
- mtime resolution on Windows can be 10–15 ms, so very fast stages
  (rig, physics, interfaces, optimize) are noisy at the floor.

## Wave 5+ roadmap

1. Wire `time.perf_counter` into `BuildExecutor` per stage; surface as
   `build_report["stages"][<stage>]["elapsed_ms"]`. Drops the mtime
   fallback to "diagnostic only" status.
2. Add `--clean` to `profile_heroes.py` to force a cache-cold rebuild.
3. Move from a single global `BUDGET_HEADROOM = 1.20` to per-stage
   tuned headroom (e.g. shape = 1.30, validate = 1.10).
4. Track cross-hero medians and percentiles from the
   `heroes_<UTC-date>.json` historical record; surface in the
   benchmarks scoreboard.

See `plans/08_product_quality.md` Phase 10 for the full Wave 5 spec.
