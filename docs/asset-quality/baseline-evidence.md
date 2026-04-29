# Lathe Asset Quality Upgrade — Baseline Evidence

> **Phase 0 deliverable** for `docs/asset-quality/improvement-tasklist.md`.
> Captures the state of Lathe's hero-asset pipeline before any quality-upgrade work begins.
> Future phases must remain additive on top of this baseline.

**Date:** 2026-04-29
**Branch:** `main`
**Commit at baseline run:** `e94a202` (Merge readiness pass v0.2.0rc1 into main)
**Determinism flag:** `--deterministic` (all builds)
**Runtime config:** none (conservative path: shape falls back to `lathe.provider.shape.reference_conditioned_v1`; topology/UV use deterministic adapters)

---

## 1. Commands Executed

```bash
# Static checks (both pass cleanly)
python -m lathe.cli check examples/industrial_crate.lth
python -m lathe.cli check examples/mechanical_door.lth

# Deterministic builds
python -m lathe.cli build examples/industrial_crate.lth industrial_crate \
  --out .tmp_tests/baseline_industrial_crate --deterministic

python -m lathe.cli build examples/mechanical_door.lth mechanical_door \
  --out .tmp_tests/baseline_mechanical_door --deterministic

# Targeted regression (24 tests, 2.59s, all pass)
python -m pytest tests/unit/test_validators_visual_surface_fast.py \
                  tests/unit/test_validate_stage_report.py \
                  tests/unit/test_reports.py \
                  tests/unit/test_reports_extended.py \
                  tests/unit/test_quality_gate_wiring.py -q
```

All five commands succeeded. The build outputs are written under `.tmp_tests/` (gitignored — see `.gitignore` line 12).

---

## 2. Baseline Certification Scores

| Asset | Certified | Score | Threshold | Repair rounds | Notes |
|---|---|---:|---:|---:|---|
| `industrial_crate` | ✅ | **0.8855** | 0.84 | 1 (reselect 0.7503 → 0.8855) | Crate hero; hard-surface prop |
| `mechanical_door` | ✅ | **0.8837** | 0.84 | 0 | Door hero; env_module |

Both assets pass certification at the **0.04 margin or less** above threshold. One reselect attempt was needed for `industrial_crate` to clear the gate. This margin matters: per Section 2.7 of the spec ("certification can pass assets that still look visually prototype-level"), passing certification is necessary but not sufficient — the upgrade must add diagnostics that distinguish "passes the gate" from "actually looks good."

Report paths (relative to repo root):

```text
.tmp_tests/baseline_industrial_crate/industrial_crate/build_report.json
.tmp_tests/baseline_industrial_crate/industrial_crate/stages/validate/report.json
.tmp_tests/baseline_mechanical_door/mechanical_door/build_report.json
.tmp_tests/baseline_mechanical_door/mechanical_door/stages/validate/report.json
```

---

## 3. Current Validator Coverage

The validate stage assembles a top-level report at `lathe/core/stages/validate.py:run`. The pipeline (built from `_PIPELINE` at `lathe/core/stages/validate.py:26`) currently runs:

| Validator | Source | Stage deps |
|---|---|---|
| `semantic_quality` | `lathe/validators/semantic_quality.py` | shape, topology |
| `visual_quality` | `lathe/validators/visual_quality.py` | shape, topology, uv, surface |
| `flow_quality` | `lathe/validators/flow_quality.py` | shape, topology, uv, surface |
| `geometry_integrity` | `lathe/validators/geometry_integrity.py` | topology |
| `urdf_validation` | `lathe/core/stages/urdf_validation.py` | (gameplay) |
| `gameplay_tags` | `lathe/selector_manifest.py` | (gameplay) |

The certification report top-level keys are stable:

```text
certified, threshold, score,
semantic_quality, visual_quality, flow_quality, geometry_integrity, urdf_validation,
rule_results, diagnostics, repair_policy, repair_suggestions,
failure_summary, semantic_repairs_applied, reselection_attempts
```

The `visual_quality` sub-report shape is:

```text
{family, blueprint_id, metrics, thresholds, render_report, diagnostics}
```

**Phase 1 hooks here additively:** a new `quality_diagnostics` top-level key on the report, sourced from a new `FunctionValidator` in `_PIPELINE`. No existing key is renamed or removed.

---

## 4. Visual-Quality Metrics — Baseline Values

`industrial_crate` (selected metrics):

| Metric | Value | Threshold | Margin |
|---|---:|---:|---:|
| detail_density | 0.997 | 0.70 | +0.297 |
| silhouette_complexity | 0.928 | 0.68 | +0.248 |
| edge_readability | 0.798 | 0.66 | +0.138 |
| attachment_integration_quality | **1.000** | 0.70 | +0.300 |
| support_plausibility | 1.000 | 0.60 | +0.400 |
| feature_coherence | 0.959 | 0.68 | +0.279 |
| geometry_integration_quality | 1.000 | 0.78 | +0.220 |
| surface_authoring_quality | 0.749 | 0.70 | +0.049 |
| primitive_likeness_penalty | 0.060 | ≤0.22 | -0.160 |
| assembled_primitives_penalty | 0.005 | ≤0.24 | -0.235 |
| **highlow_distinction_quality** | **0.450** | (informational) | — |
| boolean_scar_penalty | 0.204 | (informational) | — |
| stair_step_penalty | 0.189 | (informational) | — |
| geometry_tiny_face_penalty | 0.340 | (informational) | — |

`mechanical_door` (selected metrics):

| Metric | Value | Threshold | Margin |
|---|---:|---:|---:|
| detail_density | 0.997 | 0.70 | +0.297 |
| silhouette_complexity | 0.947 | 0.68 | +0.267 |
| edge_readability | 0.805 | 0.66 | +0.145 |
| attachment_integration_quality | 0.970 | 0.70 | +0.270 |
| support_plausibility | 0.750 | 0.60 | +0.150 |
| feature_coherence | 0.956 | 0.68 | +0.276 |
| geometry_integration_quality | 1.000 | 0.78 | +0.220 |
| surface_authoring_quality | 0.750 | 0.72 | +0.030 |
| **highlow_distinction_quality** | **0.450** | (informational) | — |

---

## 5. Visual Failure Modes — Confirmed by Baseline

The spec ("Section 2.2 Current visual failure modes") predicts seven failure modes. The baseline data confirms each one:

### 5.1 Uncontrolled triangulation
- `industrial_crate` `geometry_tiny_face_penalty = 0.340` — meaningful share of small triangles relative to median face area.
- `industrial_crate` `boolean_scar_penalty = 0.204` and `stair_step_penalty = 0.189` — boolean residue and noisy diagonals visible.
- **Phase 1 metric to add:** `random_triangulation_penalty` — synthesizes these signals into one diagnostic with a human-readable warning.

### 5.2 Weak primary/secondary/tertiary hierarchy
- Both assets have `feature_coherence ≈ 0.96` and `silhouette_complexity ≈ 0.93` — high overall, but the validator does not currently distinguish *medium-scale construction features* (frames, rails, guards, trim) from primary mass + tertiary noise.
- **Phase 1 metric to add:** `primary_secondary_tertiary_balance` — explicit scale-bucketed feature count.

### 5.3 Primitive silhouette
- Already partially detected: `primitive_likeness_penalty = 0.060` (industrial_crate) is well below threshold but not zero.
- `render_primitive_penalty` per-view: front 0.052, side 0.056, **iso 0.180** — the iso view shows much higher primitive look than the orthographics. This is consistent with the spec's "box-with-attachments" diagnosis.
- No Phase 1 metric needed beyond the existing penalty; the iso-view spike is interesting telemetry.

### 5.4 Poor attachment integration
- Both assets show `attachment_integration_quality ≥ 0.97`, which is **suspiciously high** given the spec's diagnosis that handles/hinges/rails read as "stuck-on."
- The current proxy rewards the *presence* of attachment regions and adjacency continuity, not whether attachments are *seated* in sockets/brackets.
- **Phase 1 metric to add:** `attachment_seating_quality` — explicitly checks for socket/bracket/inset metadata vs. naive attachment.

### 5.5 Material flatness / debug look
- `surface_authoring_quality ≈ 0.75` for both — passing but mid-tier.
- `roughness_variation ≈ 0.58`, `material_zone_coherence ≈ 0.79`, `texture_entropy ≈ 0.65` — surface signals exist but are not strongly storytelling.
- **Phase 1 metric to add:** `debug_material_preview_penalty` — detects the "looks like material-ID/debug colors" failure mode that current metrics do not flag.

### 5.6 No strong family grammar
- Both assets carry `family` ("industrial_crate", "mechanical_door") and `blueprint_id` (e.g. `lathe.blueprint.hard_surface_crate_v2`), but there is no metric reporting whether required construction zones (corner guards, lid seam, latch plate, foot rails) are present.
- **Phase 3 metric to add:** `family_grammar_coverage` — measurable per-family requirement satisfaction.

### 5.7 Fake high/low
- **Confirmed:** both assets report `highlow_distinction_quality = 0.450`. This is the same value across assets — strong evidence it is being computed from a coarse heuristic, not real high/low geometry. The spec calls this out in Section 11.5.
- The high/low pair URIs and triangle deltas in `surface_bundle.highlow_relation` are not yet reflected in produced artifacts (no separate `high_poly.glb`).
- **Phase 1 metric to add:** `highlow_fake_detail_penalty` — penalizes hero assets where high/low distinction is near-zero or fake. **Phase 7** will produce real high/low artifacts; Phase 1 just makes the gap visible.

---

## 6. Other Diagnostic Signals Worth Surfacing

`industrial_crate` baseline carries **one warning** in `geometry_integrity`:

```json
{
  "code": "L6202",
  "name": "inconsistent_normals",
  "severity": "warning",
  "message": "Geometry integrity detected inconsistent face winding / normals (4 flipped edge-adjacencies of 2064)"
}
```

This is non-blocking but indicates a small face-winding issue. Captured here for completeness; not in scope for Phase 0–1.

`industrial_crate` `repair_rounds` shows a **reselect from 0.7503 → 0.8855** — i.e. the first shape candidate did not pass and a reselection occurred. The reselection log is informative for post-hoc debugging and Phase 6 grammar lowering: it shows that the deterministic pipeline already has a feedback signal that could be amplified by family grammar.

---

## 7. Existing Tests — Snapshot Coverage Map

These tests cover validator + report shape today and must keep passing as Phase 1+ adds fields:

| Test | Scope | Mode |
|---|---|---|
| `tests/unit/test_validators_visual_surface_fast.py` | `evaluate_visual_quality` happy/edge/null surface metadata | fast |
| `tests/unit/test_validate_stage_report.py` | `_failure_summary`, validate stage end-to-end | fast |
| `tests/unit/test_reports.py` | terminal/HTML report rendering | fast |
| `tests/unit/test_reports_extended.py` | report rendering edge cases | fast |
| `tests/unit/test_quality_gate_wiring.py` | quality gate wiring | fast |
| `tests/test_visual_quality.py` | benchmark suite legacy/positive coverage | slow |

Phase 0 adds (see Phase 0.3) a complementary contract test that snapshots the **top-level keys** of the validate report so additive Phase 1+ fields cannot accidentally remove existing keys downstream consumers depend on.

---

## 8. Repository State Notes

The current working tree has substantial uncommitted work in **two independent streams** unrelated to asset-quality:

1. **Wonder/Scene subsystem** (~150 untracked files) — `lathe/wonder/`, `lathe/scene/`, ~30 schemas, ~30 tests, 6 CI workflows, `wonder-tasks.md`, ADRs 0010–0013.
2. **v0.2.0rc1 readiness pass** (~50 modified files in `lathe/parser/`, `lathe/checker/`, `lathe/cli/`, `grammar/`, `schema/`, `spec/`, plus docs and tests). Latest merge commit: `e94a202`.

**Implication for asset-quality phases:** all Phase 0–N additions must be additive. Specifically:

- Do **not** modify any of the 49 currently-modified files.
- Place new Phase 1+ source under a new package: `lathe/asset_quality/`.
- Place new tests under `tests/unit/test_asset_quality_*.py`.
- Place new docs under `docs/asset-quality/` (this directory).
- Build outputs go to `.tmp_tests/` (gitignored).
- No commits without explicit user approval.

---

## 9. Phase 1 Hook Plan (forward reference)

When Phase 1 lands, the integration is:

```python
# lathe/asset_quality/__init__.py
# lathe/asset_quality/diagnostics.py — new evaluate_quality_diagnostics(asset, runtime)

# lathe/core/stages/validate.py — additive: register the new validator
_PIPELINE = ValidatorPipeline([
    ...,  # existing
    FunctionValidator(
        name="quality_diagnostics",
        fn=evaluate_quality_diagnostics,
        stage_dependencies=["shape", "topology", "uv", "surface"],
    ),
])

# Then in run(): additively expose under the new top-level key
report = {
    ...,  # all existing keys preserved
    "quality_diagnostics": {**diagnostics_report, "diagnostics": entry["diagnostics"]},
}
```

Phase 1's `quality_diagnostics` payload (per spec Section 13 + tasklist Section 1.2):

```json
{
  "version": "asset_quality_diagnostics_v1",
  "metrics": {
    "random_triangulation_penalty": <float>,
    "debug_material_preview_penalty": <float>,
    "highlow_fake_detail_penalty": <float>,
    "attachment_seating_quality": <float>,
    "primary_secondary_tertiary_balance": <float>
  },
  "warnings": [<string>, ...],
  "recommendations": [<string>, ...]
}
```

---

## 10. Definition of Done — Phase 0

- [x] Baseline commands recorded with concrete results.
- [x] Baseline scores recorded for both hero examples.
- [x] Visual failure modes from spec mapped to specific baseline numbers.
- [x] Existing test coverage map recorded.
- [x] Phase 1 integration hook plan recorded.
- [x] Repository state caveats documented.
- [x] Asset-quality package scaffolding created (`lathe/asset_quality/__init__.py`).
- [x] Regression snapshot test added (`tests/unit/test_asset_quality_baseline_report_shape.py`, 5 tests passing).
- [x] Blocker inventory (`docs/asset-quality/phase0-blockers.md`, 12 items, 3 cleared, 1 user-decision, 8 future-phase).

**Verification commands** (all green):

```bash
python -m lathe.cli check examples/industrial_crate.lth         # ok
python -m lathe.cli check examples/mechanical_door.lth          # ok
python -m pytest tests/unit/test_asset_quality_baseline_report_shape.py -v   # 5 passed
python -m pytest tests/unit/test_validators_visual_surface_fast.py \
                  tests/unit/test_validate_stage_report.py \
                  tests/unit/test_reports.py \
                  tests/unit/test_reports_extended.py \
                  tests/unit/test_quality_gate_wiring.py -q     # 24 passed
python -c "import lathe.asset_quality"                          # OK
```

**Critical path forward:** see `phase0-blockers.md` B-05 (commit-strategy decision) before Phase 1 begins commit work. Phase 1 implementation itself can start immediately on top of this baseline since all additions are additive.
