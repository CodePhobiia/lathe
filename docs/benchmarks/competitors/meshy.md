# Meshy — manual run instructions

_Status: not_run. No Meshy runs have been executed in this study yet._

Meshy is a closed-SaaS text-to-3D generator. It has a web UI and an HTTP API.
This doc is what a human operator follows to populate the Meshy column of
`docs/benchmarks/v0_5_five_asset_study.md` with real numbers.

## Account setup

1. Sign up at https://www.meshy.ai (as of 2026-04-24 — re-check URL before running).
2. Meshy prices per credit. Note the credits-per-generation and USD-per-credit
   on the day of the run, and record them in the per-run JSON's `note` field.
3. If running against the API instead of the UI, generate an API key in
   Settings → API.

## Prompt / input per asset

Keep prompts minimal and intent-aligned with the `.lth` source. Paste these
exactly — do not add stylistic modifiers, because the `.lth` source doesn't
carry them either.

| Asset | Prompt |
|---|---|
| `industrial_crate` | "Industrial shipping crate, hard-surface, game-ready, low-poly, with visible panel breaks and reinforced corners." |
| `sci_fi_wall_panel` | "Sci-fi wall panel, tileable, trim-sheet-friendly, hard-surface, subtle greeble, game-ready." |
| `mechanical_door` | "Mechanical sliding/hinged industrial door, hard-surface, game-ready, visible hinge and frame." |
| `control_pedestal` | "Low-poly control pedestal, single base + angled control surface, game-ready prop." |
| `service_cabinet` | "Service cabinet with door and vented front, game-ready, hard-surface, architectural prop." |

Use Meshy's "text-to-3D" mode, standard quality, default poly target.

## Export

1. Download the `.glb` export (not FBX — we compare to Lathe's `.glb`).
2. Also download any auto-generated PBR texture set so the import can be
   rendered in Godot for the Godot-import grade.

## Ingest into the harness (manual ingest flow planned for wave 6)

As of wave 5 the harness does not yet accept a `--ingest-manifest` flag; this
is a wave-6 addition. For now:

1. Place the downloaded `.glb` at
   `docs/benchmarks/data/meshy_runs/<asset>.glb`.
2. Fill in a JSON by hand at
   `docs/benchmarks/data/<asset>_meshy_<date>.json` using the schema a
   `lathe_fallback` run produces (copy one as a template), replacing:
   - `system: "meshy"`
   - `result: "ok"` (or `"failed"`)
   - `metrics.wall_clock_s`: total time from prompt submit to download complete.
   - `metrics.score`, `metrics.certified`: leave `null`; competitors do not
     run through Lathe's validator. Grade manually in the study doc instead.
   - `metrics.glb_sha256`: `sha256sum` of the downloaded file.
   - `metrics.triangle_count`: report from Godot or `trimesh.load(...).faces`.
   - `metrics.uv_valid`, `metrics.collision_present`, `metrics.pivot_correct`:
     **be honest** — competitor `.glb` typically has UVs but no separate
     collision proxy and no named pivot anchors.
   - `note`: include Meshy credit cost, model version (Meshy labels them),
     and any retries needed.

## Licensing

Paid SaaS. Per-asset output is typically licensed for use in the paying
account's projects — re-check Meshy's ToS before using outputs in a public
demo or in the study's rendered gallery.
