# Luma (Genie / AI) — manual run instructions

_Status: not_run. No Luma runs have been executed in this study yet._

Luma offers text-to-3D ("Genie") and NeRF-derived mesh capture. For this
5-asset study we use the text-to-3D pathway because none of the 5 assets are
real objects we could NeRF-scan.

## Account setup

1. Sign up at https://lumalabs.ai (verify URL before running).
2. Luma is credit-metered SaaS. Record credits-per-generation and
   USD-per-credit as of the run day in the per-run JSON `note` field.
3. The Genie web UI or the Luma API both work; the API is preferable for a
   timed, reproducible run.

## Prompt per asset

Reuse the prompts from `meshy.md` verbatim. Avoid adding Luma-specific
stylistic modifiers — the comparison is cleanest when we feed every SaaS the
same text intent.

## Export

Download the `.glb` (Luma Genie exports GLB directly). Do not post-process in
Blender; record the raw export.

## Ingest

Same manual flow as `meshy.md`. File path:
`docs/benchmarks/data/<asset>_luma_<date>.json` with a pointer to
`docs/benchmarks/data/luma_runs/<asset>.glb`.

## Known caveats

- Luma Genie historically returns meshes without a collision proxy or named
  pivot anchors. Record `collision_present: false`, `pivot_correct: false`
  honestly rather than trying to derive them post-hoc.
- Generation time varies widely (30s–5min) depending on queue. Capture the
  full clock including queue time in `wall_clock_s` and note whether it was a
  peak or off-peak slot.

## Licensing

Paid SaaS. Terms vary by plan; re-check before public use.
