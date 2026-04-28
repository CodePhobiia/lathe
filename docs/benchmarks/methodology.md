# Lathe v0.5 benchmark methodology

_Plan 09 Phase 4. Last revised: 2026-04-24._

This document defines **how** we compare Lathe against established 3D asset
pipelines on the same 5 reference assets. It is intentionally separate from the
per-run results — results live in `v0_5_five_asset_study.md`. If you are adding
a competitor or a new metric, read this document first.

## Principles

- **Honest evidence.** No competitor row is fabricated. If a system cannot be
  run in the current session (external service, paid account, human labor), the
  harness records `result: "not_run"` and points at the per-competitor
  instruction file. Claims in the results document must trace back to a JSON
  file under `docs/benchmarks/data/`.
- **Same asset intent.** The 5 `.lth` sources drive Lathe. For competitors we
  phrase the same intent as a prompt or a reference image bundle (see each
  `docs/benchmarks/competitors/<name>.md`). The intent is the contract; the
  authoring surface changes per system.
- **Certified or not.** Lathe's validator has a pass/fail boundary
  (`certified`), not just a score. Competitors get the same pass/fail
  treatment via manual Godot-import + silhouette inspection.
- **Reproducibility is a first-class metric.** A deterministic pipeline that
  re-runs bit-identical is worth more than a one-shot win. We re-run Lathe 3
  times and compare `.glb` SHA256.

## 5 reference assets

Chosen to stress different backend-stack lanes without duplicating the
container family:

| Asset | Family | Why it's in the 5 |
|---|---|---|
| `industrial_crate` | container | Baseline hard-surface box with panel breaks — everyone should be able to do this, differences show up in UVs/collision. |
| `sci_fi_wall_panel` | architecture | Tileable flat surface; stresses UV packing, trim-sheet reuse, and decal placement. |
| `mechanical_door` | architecture | Hinged articulation + panel seams; pivot correctness matters and is a common failure mode for single-mesh generators. |
| `control_pedestal` | prop | Low tri-count silhouette test; cheap-to-render prop where generators often over-geometry. |
| `service_cabinet` | architecture | Door + internal volume; multi-part assembly + clearance anchors. |

Sources live in `examples/*.lth`; they are the canonical intent specs.

## 6 systems compared

| System | Class | Why it's in the 6 |
|---|---|---|
| **Lathe (fallback)** | Declarative, native | The floor — deterministic path, no learned provider. Any future regression below this line is a bug. |
| **Lathe (learned)** | Declarative, provider-backed | Same `.lth` source, `--runtime-config examples/runtime_configs/auto_learned.json`. Measures how much a learned shape provider adds on top of the floor. |
| **Meshy** | AI mesh, text-to-3D | Market-leading text-to-mesh SaaS; representative of the "prompt and download" flow Persona B/C use. |
| **Hunyuan3D** | AI mesh, text/image-to-3D (self-hosted) | Tencent's open-weights model; the canonical counter-example for "you could just run a model." |
| **Luma (Genie / AI)** | AI mesh, text-to-3D | Second major closed SaaS — separate IP/training base from Meshy, useful for variance. |
| **Houdini HDA + SideFX Labs** | Procedural authoring, visual | Non-AI reference: the "parametric authoring done properly" baseline for architecture-family assets. |
| **Quixel Megascans** | Asset library | The "buy, don't build" baseline — used when the asset is a known prop and scanning/licensing beats generation. |
| **Blender (by hand)** | Manual authoring | Skilled human ceiling. Measures what a senior 3D artist can produce given the same intent in comparable time. |

> 8 systems ship in the harness; the Plan 09 brief says "6 competitors + Lathe".
> The extra row is that we split **Lathe (fallback)** from **Lathe (learned)**
> because they are legitimately different paths that users choose between via
> `--runtime-config`.

## Metric definitions

Per-run JSON in `docs/benchmarks/data/<asset>_<system>_<date>.json` carries:

| Metric | Unit | Definition | Source |
|---|---|---|---|
| `wall_clock_s` | seconds | Wall time from CLI invocation to exit, measured by `time.monotonic()` around `subprocess.Popen`. | Harness. |
| `peak_memory_mb` | MB | Peak combined RSS of the build subprocess + children, polled at 10 Hz via psutil. `null` if psutil not installed. | Harness (psutil optional). |
| `score` | float [0,1] | Lathe validator's weighted ensemble score. For competitors: N/A (manual grade). | `build_report.json.score`. |
| `threshold` | float [0,1] | Certification gate declared in the `.lth`. | `build_report.json.threshold`. |
| `certified` | bool | `score ≥ threshold` AND no hard validator failure. | `build_report.json.certified`. |
| `glb_sha256` | hex | SHA256 of the published `.glb`. Different every run ⇒ non-reproducible. | Harness (`hashlib`). |
| `triangle_count` | int | Triangle count of the authoritative mesh. Low-is-better for props, panels. | `stages/topology/bundle.json.mesh_stats.triangle_count`. |
| `uv_valid` | bool | `packing_report.chart_count ≥ 1 AND lightmap_ready == True`. | `stages/uv/bundle.json`. |
| `collision_present` | bool | A separate collision proxy exists (convex decomp or hull). | `stages/physics/bundle.json.collision_proxy`. |
| `pivot_correct` | bool | Heuristic: at least one named interface anchor is emitted. For doors, this should be the hinge anchor; for floor props, `floor_contact`. | `stages/interfaces/bundle.json.anchors`. |
| `reproducibility_hashes` | list[hex] | `.glb` SHA256 from 3 additional fresh runs. | Harness (`_run_reproducibility_check`). |
| `reproducible` | bool | `len(set(reproducibility_hashes)) == 1`. | Derived. |

### Cost (external to the harness)

Cost is not tracked per-run automatically because SaaS systems price per credit
or per month. `v0_5_five_asset_study.md` records cost as "USD per asset as
configured on 2026-04-24" with a link to the pricing page, and cites the date
so future readers know to re-check.

### Godot-import + iteration speed (manual)

Two qualitative metrics recorded in the study doc, not the harness:

- **Godot-import**: "clean | needs tweaks | broken". Clean = `.glb` imports
  without remapping materials or fixing scale; collision layer applied correctly.
- **Iteration speed**: time from "I want the door 10% wider" to a re-exported
  asset. For Lathe this is editing the `.lth` and re-running build; for
  competitors it is the UX of re-prompting or editing.

## Scoring rubric

For each (asset, system) pair the study assigns a letter grade based on the
per-metric result:

- **A**: certified, Godot-clean import, reproducible, competitive tri count
  (within 2× the Lathe-fallback floor), collision + pivot correct.
- **B**: certified, minor import tweaks, one metric worse.
- **C**: renders okay, but fails two or more of {certified, Godot-clean,
  reproducible, collision, pivot}.
- **F**: does not produce a usable asset.

Grades are summary-level only; the numeric JSON is the ground truth.

## Reproducibility notes

- **Hardware.** Lathe rows captured on: Windows 10 Home, Intel desktop-class
  CPU, 16 GB RAM, no GPU acceleration required for the fallback path. For the
  Lathe-learned row, GPU / remote inference depends on the chosen runtime
  config (Hunyuan HTTP or VGGT local); record the host spec in the study doc
  when populating that row.
- **Python.** `3.12+` via the repo `.venv` (`.venv/Scripts/python.exe` on
  Windows, `.venv/bin/python` on POSIX). The harness auto-selects the repo
  venv over `sys.executable` so it picks up `trimesh`/`Pillow`.
- **Seed.** Lathe shape backends run under `lathe.runtime.shape.provider_mux_v2`
  which threads the intent seed deterministically. Three consecutive runs must
  produce bit-identical `.glb`.
- **Determinism expectation.** Downstream stages (topology → UV → surface →
  validate → package) are required to be deterministic by the stable contract
  `lathe.shape.intent_mesh_handoff_v1`. Any `reproducible: false` row on
  Lathe-fallback is a ship-blocker.

## How to add a new competitor

1. Add the system name to `COMPETITOR_SYSTEMS` in `scripts/run_benchmark.py`.
2. Create `docs/benchmarks/competitors/<name>.md` using an existing
not_run manual-entry page as a template. It must document: account setup, prompt text, export
   path, licensing, and how to feed the exported `.glb` back through
   `scripts/run_benchmark.py`'s ingest mode (to be added in a later wave).
3. If the competitor is self-hosted and deterministic, add it to the per-asset
   matrix in `v0_5_five_asset_study.md`. Otherwise keep it as a "not_run" row
   until a human operator has run it.
4. Do **not** backfill rows with estimated numbers. The credibility of this
   document depends on every cell being either measured or `pending`.

## Licensing notes

| System | Free to run in CI? | Required to populate results doc |
|---|---|---|
| Lathe (fallback) | Yes — MIT, all local. | Always. |
| Lathe (learned) | Yes, with a local provider. Hunyuan HTTP costs if used against the hosted API. | Optional; only if runtime config is supplied. |
| Meshy | No — SaaS, paid credits. | Manual; requires a Meshy account. |
| Hunyuan3D | Yes if self-hosted (Apache 2.0 weights as of writing); paid via Tencent Cloud API. | Manual; either self-host or use API key. |
| Luma | No — SaaS, paid. | Manual; requires Luma account. |
| Houdini HDA + SideFX Labs | Commercial license required (Indie or higher). | Manual; requires Houdini install. |
| Quixel Megascans | Free for non-UE use with an Epic account, paid for indie commercial use. | Manual; requires Megascans account and asset search. |
| Blender (by hand) | Free (GPL). | Manual; requires a named operator and timer. |

Always record the license + cost state as of the run date in the per-run JSON's
`note` field so old rows remain self-documenting.
