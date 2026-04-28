# Lathe v0.5 — five-asset study

_Plan 09 Phase 4. Last measured: 2026-04-24._

This is the headline benchmark document for Lathe v0.5. It compares Lathe
against five established 3D asset pipelines on the same five reference assets.

> **Read me first:** the methodology, metric definitions, and rules for
> adding a competitor live in [`methodology.md`](./methodology.md). Per-run
> raw JSON lives under [`data/`](./data/). This document is the
> human-readable summary; the JSON is the ground truth.

## What was measured

- 5 reference assets: `industrial_crate`, `sci_fi_wall_panel`,
  `mechanical_door`, `control_pedestal`, `service_cabinet`.
- 8 system columns: Lathe-fallback, Lathe-learned, Meshy, Hunyuan3D, Luma,
  Houdini HDA + SideFX Labs, Quixel Megascans, Blender-by-hand.
- Harness: `scripts/run_benchmark.py`.
- Host: Windows 10 Home, repo `.venv` (Python 3.12), no GPU, psutil not
  installed in this run (so `peak_memory_mb` is `null`).

## Lathe-fallback results (measured 2026-04-24)

The floor row — deterministic, no learned provider, no runtime config. Every
future Lathe release must keep this row green.

| Asset | Score | Threshold | Certified | Tri count | UV valid | Collision | Pivot | Repro (3 rounds) | Wall (s) | `.glb` SHA-256 (prefix) |
|---|---:|---:|:---:|---:|:---:|:---:|:---:|:---:|---:|:---|
| `industrial_crate` | 0.8848 | 0.84 | yes | 2222 | yes | yes | yes | yes | 1.9 | `47cb8cad3a3d…` |
| `sci_fi_wall_panel` | 0.8620 | 0.84 | yes | 1008 | yes | yes | yes | yes | 1.7 | `dcd499e6ad74…` |
| `mechanical_door` | 0.8769 | 0.84 | yes | 1838 | yes | yes | yes | yes | 1.7 | `ed4c8d41d134…` |
| `control_pedestal` | 0.8424 | 0.83 | yes | 56 | yes | yes | yes | yes | 1.9 | `9e2ceed007dc…` |
| `service_cabinet` | 0.8209 | 0.82 | yes | 82 | yes | yes | yes | yes | 1.8 | `5ce826894017…` |

**All 5 certify.** All 5 are reproducible across 3 fresh builds. Wall clock
for the full 5-asset sweep including reproducibility rounds: well under one
minute on the test host.

Raw per-run JSON:

- `data/industrial_crate_lathe_fallback_2026-04-24.json`
- `data/sci_fi_wall_panel_lathe_fallback_2026-04-24.json`
- `data/mechanical_door_lathe_fallback_2026-04-24.json`
- `data/control_pedestal_lathe_fallback_2026-04-24.json`
- `data/service_cabinet_lathe_fallback_2026-04-24.json`
- Aggregate: `data/summary_2026-04-24.json`

To reproduce:

```bash
python scripts/run_benchmark.py --lathe-only
```

The harness auto-selects `.venv/Scripts/python.exe` (or `.venv/bin/python` on
POSIX) so that Lathe's downstream deps (`trimesh`, `Pillow`, etc.) are on the
path regardless of how the harness itself is launched.

## Lathe-learned results

_Pending. Run with:_

```bash
python scripts/run_benchmark.py --runtime-config examples/runtime_configs/auto_learned.json
```

_Requires provider wiring (Hunyuan HTTP or local VGGT) — see the
`examples/runtime_configs/` directory. When populated, each row should record
both the attempted provider and the actually-used provider, since Lathe's
mux logs both under `shape_backend_report.provider_attempted` vs.
`provider_selected`._

## Competitor results (pending)

| System | Status | Run instructions |
|---|---|---|
| Meshy | pending | [`competitors/meshy.md`](./competitors/meshy.md) |
| Hunyuan3D (raw, not via Lathe) | pending | [`competitors/hunyuan.md`](./competitors/hunyuan.md) |
| Luma (Genie) | pending | [`competitors/luma.md`](./competitors/luma.md) |
| Houdini HDA + SideFX Labs | pending | [`competitors/houdini_hda.md`](./competitors/houdini_hda.md) |
| Quixel Megascans | pending | [`competitors/quixel.md`](./competitors/quixel.md) |
| Blender (by hand) | pending | [`competitors/blender_by_hand.md`](./competitors/blender_by_hand.md) |

Every competitor row is a `not_run` entry in
`data/<asset>_<system>_2026-04-24.json`. The per-run JSON carries a `note`
field pointing back at the corresponding instruction file.

**No numbers will be filled in for competitors until a human operator runs
the pipeline per the instruction file and ingests the result.** This is a
hard rule — see `methodology.md#principles`.

## Per-asset summary matrix (will fill as competitors run)

| Asset | Lathe-fallback | Lathe-learned | Meshy | Hunyuan | Luma | Houdini | Quixel | Blender-hand |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| `industrial_crate` | **A** (certified, repro, tris=2222) | pending | pending | pending | pending | pending | pending | pending |
| `sci_fi_wall_panel` | **A** (certified, repro, tris=1008) | pending | pending | pending | pending | pending | pending | pending |
| `mechanical_door` | **A** (certified, repro, tris=1838) | pending | pending | pending | pending | pending | pending | pending |
| `control_pedestal` | **A** (certified, repro, tris=56) | pending | pending | pending | pending | pending | pending | pending |
| `service_cabinet` | **A** (certified, repro, tris=82) | pending | pending | pending | pending | pending | pending | pending |

Letter grades use the rubric from `methodology.md#scoring-rubric`.

## Godot-import grade (pending)

The `.glb` files from Lathe-fallback above need to be import-tested in Godot
once the addon MVP (Plan 09 Phase 2, task #1) lands. Goal: all 5 load without
material or scale remapping and apply the emitted collision proxy correctly.

## Iteration speed (pending)

The methodology calls for a "make it 10% wider" re-export test per system.
Lathe: edit `.lth`, re-run `lathe build`, measure wall clock. Competitors:
re-prompt / re-author per their per-competitor doc. Not captured in this wave.

## Open items

- Run Lathe-learned once provider credentials are plumbed for the CI host.
- Human operator runs for all 6 competitor systems.
- Godot-import grading once the Godot addon exists.
- Iteration-speed column once the "narrow → wider" edit pass has been scripted.
- Wave 6: `--ingest-manifest` flag on `scripts/run_benchmark.py` so competitor
  `.glb` can be ingested via CLI instead of hand-editing JSON.

## Change log

- 2026-04-24 — initial harness + methodology + Lathe-fallback row populated
  (Plan 09 Phase 4 / wave 5 task #2).
