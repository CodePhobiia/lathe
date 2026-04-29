# Phase 1 Preflight — Lathe Asset-Quality Upgrade

> Confirms the repository is in a state where Phase 1 of `docs/asset-quality/improvement-tasklist.md` can begin without unresolved blockers.
> Companions: `docs/asset-quality/baseline-evidence.md` (Phase 0 baseline), `docs/asset-quality/phase0-blockers.md` (full blocker inventory and history).

**Date:** 2026-04-30
**Branch:** `main`
**Working tree:** clean (no modified, no untracked files outside `.gitignore`).

---

## Recent merge status

All three pre-Phase-1 workstreams have been merged into `main` and Phase 0's resolution event B-05 in `phase0-blockers.md` records the audit trail:

| Stream | Merge commit | PR | Files |
|---|---|---|---:|
| Wonder/Scene subsystem + Roblox export lane | `3bb8de3` | #12 | 318 |
| v0.2.0rc1 readiness pass — language/grammar/schema/docs/tests | `b230e0d` | #13 | 49 (modified) |
| asset-quality Phase 0 baseline + diagnostics scaffolding | `3706fe5` | #11 | 7 |

`main` HEAD: `b230e0d` (also matches `origin/main`). Total diff scope between pre-merge `e94a202` and current main: **374 files**, +102,336 / -160 lines. This reconciles exactly with the per-stream file counts above (7 + 318 + 49 = 374).

---

## Phase 1 status

**Ready to begin.**

**Phase 1 blockers: none.** B-01, B-02, B-03 (cleared by Phase 0) and B-05 (resolved by today's main-merges) covered every Phase 1 prerequisite. No further commit-strategy preflight is required.

---

## Future-phase blockers (still tracked, do not block Phase 1)

| ID | Title | Phase it applies to |
|---|---|---|
| **B-06** | No moodboard / reference fixtures under `examples/refs/asset_quality/` | Phase 11 |
| **B-07** | No kit-library scaffolding (`std/kits/hardsurface/`, `schema/kit_part.schema.json`, `lathe/asset_quality/kit_library.py`) | Phase 12 |
| **B-08** | No real high-poly producer in pipeline (current `highlow_distinction_quality = 0.45` is from the heuristic at `lathe/validators/visual_quality.py:310-329`, not real high-vs-low geometry) | Phase 7 strict mode only — warning-only path covered by Phase 1 |
| **B-09** | No asset-quality CI workflow under `.github/workflows/` | Phase 15 |
| **B-10** | Public-syntax coordination across spec + grammar + schema + parser + normalizer + resolver + checker + examples + tests must land in a single PR | Phase 13 only |

Non-blocking items (B-04 stale docs, B-11 slow benchmark, B-12 CRLF) are also tracked in `phase0-blockers.md` and remain non-blocking for Phase 1.

---

## Phase 1 implementation scope

Phase 1 ships **deterministic visual-quality diagnostics** and nothing else.

### In scope

- Add a new top-level `quality_diagnostics` object **additively** to the certification report, sourced from a new `FunctionValidator` registered in `lathe/core/stages/validate.py:_PIPELINE`.
- Implement the five Phase 1 deterministic metrics defined in `improvement-tasklist.md` Section 1 / `lathe-asset-quality-upgrade-spec.md` Section 13:
  - `random_triangulation_penalty`
  - `debug_material_preview_penalty`
  - `highlow_fake_detail_penalty`
  - `attachment_seating_quality`
  - `primary_secondary_tertiary_balance`
- Emit human-readable warnings + recommendations per metric.
- New code lives under `lathe/asset_quality/` (the package marker created in Phase 0).
- New tests live in `tests/unit/test_asset_quality_*.py` files (additive to the contract tests already in place).
- Hook plan reference: `docs/asset-quality/baseline-evidence.md` Section 9.

### Hard preservation guarantees (per spec Sections 4 and 18 + AGENTS.md)

- **Preserve all existing report fields.** No rename or removal of any key in `validate/report.json`, `visual_quality`, `semantic_quality`, `flow_quality`, `geometry_integrity`, `urdf_validation`, `rule_results`, `diagnostics`, `repair_*`, or `failure_summary`. Verified by `tests/unit/test_asset_quality_baseline_report_shape.py`.
- **Preserve `.lth` source compatibility.** No grammar, schema, or parser change.
- **Preserve `lathe.shape.intent_mesh_handoff_v1`.** No change to the stable shape-stage contract.

### Out of scope for Phase 1 (deferred to later phases per `improvement-tasklist.md`)

- ShapeIR v2 internal model and adapter — Phase 5.
- Public `.lth` syntax (`art_direction`, `construction`, `material_graph`, `references`, `kit`) — Phase 13.
- Standard kit library (`std/kits/hardsurface/`) — Phase 12.
- Real high-poly producer (separate `stages/shape/high_poly.glb` artifact) — Phase 7.
- Reference / moodboard ingestion fixtures — Phase 11.
- Asset-quality CI lane — Phase 15.
- Vision critique loop — Phase 10.

---

## Verification (this preflight)

```bash
git status --short
# (no output — working tree clean)

python -m pytest tests/unit/test_asset_quality_baseline_report_shape.py -v
# 5 passed
```

When this preflight was filed, both commands above succeeded.

---

## Phase 1 implementation closure (2026-04-30)

Phase 1 has shipped per the scope above. Deliverables:

| Path | Purpose |
|---|---|
| `lathe/asset_quality/diagnostics.py` | `evaluate_quality_diagnostics(asset, runtime)` — 5 deterministic proxy metrics + warning/recommendation emission. |
| `lathe/core/stages/validate.py` | Registers `quality_diagnostics` `FunctionValidator` in `_PIPELINE` after `visual_quality` (`weight=0.0`); adds additive top-level `quality_diagnostics` key to the validate-stage report. |
| `tests/unit/test_asset_quality_diagnostics.py` | 13 unit tests covering payload shape, version, numeric metrics, each of the 5 warnings, missing/partial runtime data, paired warnings/recommendations. |
| `docs/asset-quality/quality-diagnostics-v1.md` | Per-metric reference (formulas, baselines, thresholds, limitations, forward references to Phases 3/4/7/10). |

Key behaviour:

- The hero baselines now correctly surface the **fake high/low** failure
  mode (`highlow_fake_detail_penalty = 0.55` for both `industrial_crate`
  and `mechanical_door`, since `high_triangle_count == low_triangle_count`
  in the existing pipeline).
- All other Phase 1 metrics stay quiet for the v0.2.0rc1 hero baselines
  by design — Phase 1 was tuned to flag *clearly* prototype-quality
  output and not over-warn on mid-tier hero passes.
- `quality_diagnostics` is registered with `weight=0.0` and returns no
  blocking `diagnostics` entries, so the aggregate certification score
  is unchanged. Verified via the existing
  `tests/unit/test_asset_quality_baseline_report_shape.py` contract suite
  (still passing).

Forward references for later phases:

- Phase 3 (family grammar) replaces the `primary_secondary_tertiary_balance`
  proxy with explicit construction-zone coverage.
- Phase 4 (semantic construction graph) replaces the
  `attachment_seating_quality` proxy with real edge-type counts over
  `socket`, `bracket`, `inset_into`, `mounted_on`.
- Phase 7 (high-poly producer) gives `highlow_fake_detail_penalty` a
  real path to zero — until then the metric correctly surfaces that the
  current pipeline does not produce a separate high-poly artifact.
- Phase 10 (vision critique) consumes the `warnings` strings as
  semantic-patch hints.

---

## Next step

Begin Phase 2 (Design Brief IR defaults) per `docs/asset-quality/improvement-tasklist.md` Section 2.
