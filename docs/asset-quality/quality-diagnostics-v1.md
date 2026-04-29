# Asset-Quality Diagnostics v1

> **Phase 1 deliverable** for `docs/asset-quality/improvement-tasklist.md`.
> Documents the metrics, thresholds, limitations, and improvement guidance for
> the deterministic visual-quality diagnostics layer added on top of the
> existing `visual_quality` validator.
>
> **Companion docs:**
> `docs/asset-quality/lathe-asset-quality-upgrade-spec.md` Section 13 (spec),
> `docs/asset-quality/baseline-evidence.md` (the baseline this diagnostic
> layer was tuned against), `docs/asset-quality/phase1-preflight.md` (preflight).

**Date:** 2026-04-30
**Module:** `lathe/asset_quality/diagnostics.py`
**Validator name:** `quality_diagnostics`
**Payload version field:** `asset_quality_diagnostics_v1`

---

## 1. Overview

`quality_diagnostics` is a deterministic, additive diagnostic layer that runs
after `visual_quality` in the validate-stage pipeline
(`lathe/core/stages/validate.py:_PIPELINE`). It synthesizes existing runtime
signals into five proxy metrics that flag prototype-quality failure modes
which the existing certification gate currently lets through.

### What this layer does

- Emits a flat `quality_diagnostics` object on the validate-stage report.
- Surfaces five deterministic metrics in `[0.0, 1.0]`.
- Emits human-readable warnings + paired recommendations when a metric
  crosses its threshold.
- Never blocks certification (registered with `weight=0.0` in the
  validator pipeline; the function returns no `diagnostics` field).

### What this layer does *not* do

- Render images or call any external service.
- Modify, rename, or remove any existing report field.
- Touch `.lth` source syntax.
- Touch `lathe.shape.intent_mesh_handoff_v1`.
- Implement ShapeIR v2, public syntax, kit library, high-poly producer,
  references, vision critique, or CI lanes — those are scoped to later
  phases per `improvement-tasklist.md`.

---

## 2. Payload schema

The validator returns this additive payload, which is exposed under
`report["quality_diagnostics"]` on the validate-stage report:

```json
{
  "version": "asset_quality_diagnostics_v1",
  "metrics": {
    "random_triangulation_penalty": 0.261,
    "debug_material_preview_penalty": 0.332,
    "highlow_fake_detail_penalty": 0.55,
    "attachment_seating_quality": 0.992,
    "primary_secondary_tertiary_balance": 0.978
  },
  "warnings": [
    "hero asset lacks meaningful high-poly/low-poly distinction (highlow_fake_detail_penalty=0.550)"
  ],
  "recommendations": [
    "Add a real high-poly source ..."
  ],
  "findings": [
    {
      "metric": "highlow_fake_detail_penalty",
      "severity": "warning",
      "warning": "hero asset lacks meaningful high-poly/low-poly distinction (highlow_fake_detail_penalty=0.550)",
      "recommendation": "Add a real high-poly source ..."
    }
  ]
}
```

The three result arrays are index-aligned. `warnings[i]`,
`recommendations[i]`, and `findings[i]` refer to the same triggered
metric. The simple-string `warnings` and `recommendations` arrays are
preserved for backward compatibility with any consumer wired to Phase 1
RC1; the `findings` array is the structured form intended for downstream
classifiers (e.g. Phase 10's vision-critique loop) that need to map a
warning back to its source metric without re-parsing the warning text.

### 2.1 `findings` entry shape

Each `findings[i]` record contains:

| Field | Type | Notes |
|---|---|---|
| `metric` | string | One of the five metric names listed in §3. |
| `severity` | string | Always `"warning"` at Phase 1. Phase 7 strict mode may add `"error"`. |
| `warning` | string | Identical to `warnings[i]` — verbatim copy for self-contained record. |
| `recommendation` | string | Identical to `recommendations[i]` — verbatim copy. |

Because `severity` is always `"warning"` at Phase 1, the validator
remains informational-only and never blocks certification. Phase 7's
strict-mode opt-in is the first place a `severity: "error"` finding
could appear; until then, downstream tools may safely treat all Phase 1
findings as advisory.

---

## 3. Metrics

Each metric is a deterministic proxy synthesized from already-computed
fields in `runtime["visual_quality"]`, `runtime["shape"]`, and
`runtime["surface"]`. Penalty metrics warn when **above** their
threshold; quality metrics warn when **below** theirs.

### 3.1 `random_triangulation_penalty` (penalty, warn > 0.30)

**Detects:** "uncontrolled triangulation" — large flat surfaces split by
arbitrary diagonals, tiny shrapnel faces, boolean-residue scarring.

**Formula:**
```
0.45 * geometry_tiny_face_penalty
+ 0.30 * geometry_stair_step_penalty (or stair_step_penalty fallback)
+ 0.25 * boolean_scar_penalty
```

All three inputs come from `runtime["visual_quality"]["metrics"]` and are
already computed by `lathe/validators/visual_quality.py`.

**Industrial crate baseline value:** 0.261 (no warning — mid-tier noise,
within tolerance).

**Recommendation when triggered:** add controlled panel lines / bevels /
simplified topology on large flat faces; avoid arbitrary diagonal
triangulation.

### 3.2 `debug_material_preview_penalty` (penalty, warn > 0.50)

**Detects:** surfaces that read like raw material-ID / debug colors
rather than authored PBR — flat albedo, low roughness variation, low
chroma variation.

**Formula:**
```
0.40 * (1 - texture_entropy)
+ 0.35 * (1 - roughness_variation)
+ 0.25 * (1 - surface_chroma_variation)   # falls back to texture_entropy
```

**Industrial crate baseline value:** 0.332 (no warning — surface has
moderate authoring evidence).

**Recommendation when triggered:** vary roughness, add albedo
storytelling (paint chips, dirt), use a richer normal map.

### 3.3 `highlow_fake_detail_penalty` (penalty, warn > 0.40)

**Detects:** hero assets where the high-poly / low-poly relationship is
fake — either no distinct mesh URIs, or distinct URIs with identical
triangle counts (the visual_quality validator already computes a
"realness" score that this metric inverts).

**Formula:**
```
realness = (0.45 if distinct URIs else 0.0)
         + min(0.55, |high_tri - low_tri| / max(1, high_tri) / 0.18)
penalty  = 1.0 - realness
```

Inputs come from `runtime["surface"]["bundle"]["highlow_relation"]`.

**Industrial crate baseline value:** **0.55 → warns.** The high and low
mesh URIs are distinct (`stages/shape/candidate_01.glb` vs
`stages/topology/topology.glb`) but the triangle counts are identical
(1376 == 1376), so the realness contribution from the triangle-delta
component is zero. This is exactly the failure mode `lathe-asset-quality-upgrade-spec.md`
Section 5.7 calls out — the validator was previously emitting
`highlow_distinction_quality = 0.45` from the realness heuristic, which
let the issue pass technical certification.

**Phase 7 (warning-only path) covered:** today's diagnostic surfaces the
issue without changing pass/fail. Phase 7's strict mode will require an
opt-in real high-poly producer (see `phase0-blockers.md` B-08).

**Recommendation when triggered:** add a real high-poly source (bevels,
embossed detail, chamfered edges) and bake to the runtime low-poly's
normal/AO/curvature maps.

### 3.4 `attachment_seating_quality` (quality, warn < 0.50)

**Detects:** attachments (handles, hinges, latches, panels) that read as
"stuck-on" rather than seated into sockets / brackets / mount plates /
recessed insets.

**Formula:**
```
attach_coverage = min(1, attachment_region_count / max(1, parts_count / 2))
quality = 0.50 * attach_coverage
        + 0.30 * attachment_integration_quality
        + 0.20 * feature_coherence
```

`attachment_region_count` comes from
`runtime["shape"]["bundle"]["shape_assessment"]` (or
`scaffold_report.shape_assessment` as a fallback).
`attachment_integration_quality` and `feature_coherence` come from
`runtime["visual_quality"]["metrics"]`.

**Industrial crate baseline value:** 0.992 (no warning — 5 attachment
regions for 6 parts, integration_quality=1.0, feature_coherence=0.96).

**Limitation:** the existing `attachment_integration_quality` metric is
itself a coarse proxy that the spec calls out as "suspiciously high" for
some hero assets (`upgrade-spec.md` Section 5.4). Phase 4's semantic
construction graph will replace `attach_coverage` with a real edge-type
count over `socket`, `bracket`, `inset_into`, `mounted_on`. Until then,
this metric trusts the count of attachment regions as a structural
signal.

**Recommendation when triggered:** seat attachments into sockets,
brackets, mount plates, or recessed insets rather than placing them as
separate primitives on top of the body.

### 3.5 `primary_secondary_tertiary_balance` (quality, warn < 0.50)

**Detects:** "one primary body + tiny noise only" cases — assets with no
medium-scale construction features (frames, rails, corner guards, panel
breaks, trim) between the primary body and tertiary details.

**Formula:**
```
secondary_count = max(0, feature_count - parts_count)
secondary_coverage = min(1, secondary_count / max(2, parts_count * 1.5))
balance = 0.40 * secondary_coverage
        + 0.30 * silhouette_complexity
        + 0.30 * detail_density
```

**Industrial crate baseline value:** 0.978 (no warning — 81 features
across 6 parts means 75 secondary-tier features, silhouette_complexity
0.93, detail_density 1.0).

**Limitation:** this metric assumes "features beyond parts" approximates
medium-scale construction. Phase 3's family grammar IR will provide
explicit construction-zone coverage (corner guards, lid seam, latch
plate, foot rails) that supersedes this proxy.

**Recommendation when triggered:** add medium-scale construction
features — frames, rails, corner guards, panel breaks, trim — between
the primary body and tertiary details.

---

## 4. Thresholds

Phase 1 thresholds are conservative — calibrated against the
v0.2.0rc1 baseline (`industrial_crate` and `mechanical_door`) so that
clearly mid-tier assets do not over-warn. The only metric expected to
warn for the current hero baselines is `highlow_fake_detail_penalty`,
because both heroes have identical high/low triangle counts.

| Metric | Direction | Warn at | Industrial crate baseline | Mechanical door baseline |
|---|---|---:|---:|---:|
| `random_triangulation_penalty` | penalty | > 0.30 | 0.261 | 0.153 |
| `debug_material_preview_penalty` | penalty | > 0.50 | 0.332 | 0.296 |
| `highlow_fake_detail_penalty` | penalty | > 0.40 | **0.55** ⚠ | **0.55** ⚠ |
| `attachment_seating_quality` | quality | < 0.50 | 0.992 | 0.95 (approx) |
| `primary_secondary_tertiary_balance` | quality | < 0.50 | 0.978 | 0.95 (approx) |

These thresholds are intentionally tight enough to catch obvious failure
patterns and loose enough that current passing assets remain quiet.
Future phases will tighten thresholds once richer metrics replace the
proxies (see Section 3 limitations).

---

## 5. Improvement guidance

When a warning fires, the corresponding `recommendations[i]` entry
spells out the structural fix. Per spec Section 13.3, the warnings are
human-readable so they double as repair-loop hints (Phase 1 does not
auto-apply repairs; that is Phase 10's vision-critique loop).

| Warning | Improvement |
|---|---|
| noisy diagonal topology | Author hard-surface panels with deliberate quad cuts and bevels; let the topology stage own diagonals only inside small detail regions. |
| material-ID / debug look | Add a roughness gradient, paint-chip mask, or wear edge — replace flat fills. |
| fake high/low | Land Phase 7's real high-poly producer behind a runtime config flag. Until then, document the limitation in the asset's evidence bundle. |
| stuck-on attachments | Add `socket`, `bracket`, or `mount_plate` metadata in the asset's part graph (Phase 4 will formalize these as graph-edge types). |
| weak medium-scale hierarchy | Add `corner_guard`, `lid_seam`, `latch_plate`, `foot_rail`, `trim_band` features in Phase 3 family grammar terms. |

---

## 6. Limitations and forward references

- All five metrics are **proxies** synthesized from existing signals.
  Each one explicitly notes the future phase that supersedes it
  (Phases 3, 4, 7, 10).
- The `attachment_seating_quality` and `primary_secondary_tertiary_balance`
  metrics rely on counts (`attachment_region_count`, `feature_count`)
  rather than semantic graph edges — they will be re-baselined when the
  Phase 4 construction graph lands.
- Thresholds are global; Phase 3 will introduce family-specific
  thresholds via the family grammar IR.
- Phase 1 emits warnings as informational strings only. The validator
  pipeline treats `quality_diagnostics` as `weight=0.0` so the aggregate
  certification score is unchanged.
- The opt-in integration test in
  `tests/unit/test_asset_quality_baseline_report_shape.py::test_validate_report_top_level_keys_match_baseline_contract`
  verifies that adding the new `quality_diagnostics` key did not displace
  any baseline key.

---

## 7. Pipeline placement

The validator is registered in
`lathe/core/stages/validate.py:_PIPELINE` immediately after
`geometry_integrity` and before `urdf_validation`. Because the
ValidatorPipeline propagates each validator's evidence into runtime
under its own name (`lathe/validators/composition.py:287-291`),
`quality_diagnostics` reads `runtime["visual_quality"]` populated by the
preceding `visual_quality` run. `stage_dependencies=["shape", "topology",
"uv", "surface"]` ensures the topological order matches expectations.

---

## 8. Verification

```bash
# Per-metric and per-warning unit tests
python -m pytest tests/unit/test_asset_quality_diagnostics.py -v   # 13 passed

# Contract tests (baseline report shape preserved)
python -m pytest tests/unit/test_asset_quality_baseline_report_shape.py -v   # 5 passed

# Targeted regression
python -m pytest tests/unit/test_validators_visual_surface_fast.py \
                  tests/unit/test_validate_stage_report.py \
                  tests/unit/test_reports.py \
                  tests/unit/test_reports_extended.py \
                  tests/unit/test_quality_gate_wiring.py \
                  tests/unit/test_marker_inventory.py -q   # all pass

# End-to-end build with quality_diagnostics in report
python -m lathe.cli build examples/industrial_crate.lth industrial_crate \
  --out .tmp_tests/phase1_industrial_crate --deterministic
# Inspect: .tmp_tests/phase1_industrial_crate/industrial_crate/stages/validate/report.json
# top-level "quality_diagnostics" key exists with version, metrics, warnings, recommendations.
```
