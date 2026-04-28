# Perf budgets (PERF-4) and snapshot diff (RPT-5)

This page describes two V0.2, Wave 6.VI tools that together close the
performance / reproducibility loop for hero builds:

- `perf/manifest.json` — hand-authored per-hero per-stage wall-time
  ceilings. Enforced by `scripts/profile_heroes.py --manifest`.
- `lathe diff <a> <b>` — compare two `.lathe_snapshot.json` files from
  RPT-4 and report stage-hash drift, score delta, certified flip, and
  version/source mismatches.

## Why both

`perf/budgets.json` (BL-38 / BL-43) infers a budget from a recent
measurement times `BUDGET_HEADROOM` (default 1.20). That works for "did
this stage just get 2x slower" detection but has two downsides:

1. A slow baseline is "locked in". If `surface` drifts from 40s to 90s
   over three merges, no single step crosses the +20% gate, and the
   90s becomes the new normal.
2. Reviewers have no explicit, authored opinion about what "fast enough"
   means; they see ratios against the last observation.

`perf/manifest.json` makes that opinion explicit. Each hero has:

```json
{
  "heroes": {
    "courier_drone": {
      "total_ms_max": 200000,
      "stages": {
        "shape":    {"ms_max": 6000},
        "topology": {"ms_max": 4000},
        "uv":       {"ms_max": 1000},
        "surface":  {"ms_max": 180000},
        "optimize": {"ms_max": 200},
        "validate": {"ms_max": 80000},
        "package":  {"ms_max": 20000}
      }
    }
  }
}
```

Rows emitted by the profiler:

- `pass`: `current_ms <= ms_max`
- `warn`: `0.9 * ms_max < current_ms <= ms_max` (heads-up; still passes)
- `fail`: `current_ms > ms_max` (exit non-zero unless `--no-fail-on-regression`)
- `skip`: no measurement or no budget for that stage

Cached builds can legitimately emit `skip` rows for stages whose only
available timing source is a preserved artifact mtime from an older run.
The total wall-clock row still gates the current build, while per-stage
rows resume once the executor reports structured timings or the build is
profiled from a cold cache.

## Running the manifest gate

```bash
# Build + verify all heroes against perf/manifest.json.
python scripts/profile_heroes.py --manifest

# Only one hero.
python scripts/profile_heroes.py --manifest --only courier_drone

# Report-only mode (does not exit non-zero on fail).
python scripts/profile_heroes.py --manifest --no-fail-on-regression
```

The legacy `--verify` mode continues to compare against
`perf/budgets.json`; the two modes do not collide and you can run either
(or both) in CI.

## Updating a budget

When a hero legitimately needs more time (for example, a new LOD tier
added 600ms to `optimize`), open a PR that edits `perf/manifest.json`
and explains the cause in the commit message. Do **not** widen
`perf/budgets.json` by re-baselining — that silently masks drift from
prior PRs.

## `lathe diff` — snapshot comparator

`lathe snapshot <build_dir>` (RPT-4) emits a `.lathe_snapshot.json`
sidecar with a per-stage SHA-256 hash. `lathe diff` compares two such
files and surfaces:

- **Drifted stages** — stages present in both snapshots with different
  hashes; short hash prefixes are shown in human mode.
- **Added / removed stages** — stages present in only one snapshot.
- **Score delta** — difference in the validation score.
- **Certified flip** — `certified` changed between `true` and `false`.
- **latheVersion mismatch** — snapshots from different Lathe versions.
- **sourcePath mismatch** — snapshots from different `.lth` sources.

```bash
# Human-readable (default).
lathe diff baseline.snapshot.json candidate.snapshot.json

# Structured for CI consumers.
lathe diff baseline.snapshot.json candidate.snapshot.json --json

# Include matching stages in the output.
lathe diff baseline.snapshot.json candidate.snapshot.json --verbose
```

Exit codes:

- `0` — no drift (matches score, certified, stages, version, source).
- `1` — drift detected.
- `2` — usage error (missing file, unreadable JSON).

Matching stages are suppressed by default so the output is focused on
what changed. Pass `--verbose` to see them.

### Does this collide with `ref diff`?

No. `lathe ref diff <build_a> <build_b>` (REF-11) is a
sub-subcommand of `ref`; it diffs selector manifests (the asset graph,
sockets, pivots, materials). `lathe diff <snap_a> <snap_b>` is a
top-level subcommand that diffs RPT-4 snapshot hashes. The two are
independent and complementary.

## Typical workflow

```bash
# Baseline.
lathe build examples/courier_drone.lth courier_drone --out dist-a
lathe snapshot dist-a/courier_drone --deterministic --out baseline.snapshot.json

# Candidate (e.g. after a PR).
lathe build examples/courier_drone.lth courier_drone --out dist-b
lathe snapshot dist-b/courier_drone --deterministic --out candidate.snapshot.json

# Drift?
lathe diff baseline.snapshot.json candidate.snapshot.json

# Perf?
python scripts/profile_heroes.py --manifest --only courier_drone
```
