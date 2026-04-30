# High-Poly / Low-Poly Relation v1

> **Phase 7 deliverable** for `docs/asset-quality/improvement-tasklist.md`.
> Documents the deterministic evidence layer that makes the high-poly
> versus low-poly relationship truthful and staged — without running
> Blender, running a bake, or producing high-poly geometry.
>
> **Companion docs:**
> `docs/asset-quality/lathe-asset-quality-upgrade-spec.md` Section 11
> (high-poly / low-poly reality gate),
> `docs/asset-quality/improvement-tasklist.md` Section 7 (Phase 7 task list),
> `docs/asset-quality/quality-diagnostics-v1.md` (Phase 1 — the
> `highlow_fake_detail_penalty` metric this layer strengthens),
> `docs/asset-quality/baseline-evidence.md` (Phase 0 blocker B-08
> documenting the staged rollout).

**Date:** 2026-04-30
**Module:** `lathe/asset_quality/highlow_relation.py`
**Validator name:** `highlow_relation`
**Payload version field:** `highlow_relation_v1`

---

## 1. Overview

The high-poly / low-poly relation evaluator is the warning-only layer
that surfaces *whether* a hero asset's high-poly source is real or
fake. The visual_quality validator's `highlow_distinction_quality`
heuristic at `lathe/validators/visual_quality.py:310-329` predates
this layer and only inspects the surface bundle locally; the
quality_diagnostics validator's `highlow_fake_detail_penalty`
(introduced in Phase 1) gives the prototype-look proxy. Phase 7 adds
a richer evidence record that:

- enumerates each canonical bake map with structured presence and
  skipped-reason fields;
- compares the runtime low-poly mesh URI against the surface bundle's
  declared low URI;
- computes a strengthened realness score consuming distinct URIs,
  positive high-over-low triangle delta, bake-map completeness, and
  manifest quality;
- emits a warning when the score is below the warning threshold
  (`is_real_highlow == False`) and the asset is hero-surface scoped.

The Phase 1 `highlow_fake_detail_penalty` metric now consumes this
evidence when present (`penalty = 1.0 - realness_score`) and falls
back to the legacy heuristic when absent so existing callers stay
defined.

### What this layer does

- Reads the live runtime — the surface bundle's `highlow_relation`
  record, the `outputs` and `bake_outputs` maps, and the topology
  bundle's `mesh_uri` — and builds a frozen `HighlowEvidence`
  record.
- Scores the relation with four weighted credits and emits the
  `is_real_highlow` verdict.
- Publishes a `required` flag so non-hero/generic assets can carry
  evidence without receiving hero-only warnings or penalties.
- Records structured `skipped_reason` entries for every missing bake
  map and every absent URI.
- Publishes the result on `runtime["highlow_relation"]` and emits an
  additive `highlow_relation` key on the validate-stage report (the
  21st top-level key, on top of the 20 from Phases 0 through 6).

### What this layer does *not* do

- Run Blender, run a bake, or produce high-poly geometry. Phase 7 is
  evidence + diagnostic only. The real high-poly producer is the
  Phase 7 strict-mode follow-up (see `## 7. Strict mode`) and Phase 8.
- Touch `.lth` source syntax. The Phase 7 contract is internal-only.
- Touch `lathe.shape.intent_mesh_handoff_v1`, `lathe/shape_backend.py`,
  `lathe/shape_providers.py`, or `lathe/shape_ir.py`.
- Modify, rename, or remove any existing report field.
- Block certification by default. The validator is registered with
  `weight=0.0` and emits an empty `diagnostics` list unless the
  caller explicitly opts into strict mode.
- Invent results when an external tool is unavailable. Per
  `AGENTS.md` ("Do not fake Blender, Roblox, external viewer,
  vision-model, or renderer evidence."), every missing map records a
  structured `skipped_reason` instead.

---

## 2. Goals and non-goals

**Goals:**

- Surface a richer, deterministic evidence layer for the high/low
  relationship so reviewers can audit the verdict.
- Strengthen `highlow_fake_detail_penalty` so a hidden fake (distinct
  URIs but identical maps and triangle counts) is no longer credited
  as real.
- Provide a strict-mode opt-in path so projects that require a real
  high-poly source can flip the warning into a blocking diagnostic.

**Non-goals:**

- Generate any geometry, drive Blender, or trigger a bake.
- Replace the visual_quality `highlow_distinction_quality` heuristic
  (which still runs as part of the visual_quality validator).
- Change the Phase 1 metric set in `quality_diagnostics.metrics` —
  the metric count stays at 6.

---

## 3. Payload schema

Returned by `evaluate_highlow_relation(asset, runtime)`:

```json
{
  "version": "highlow_relation_v1",
  "is_real_highlow": false,
  "realness_score": 0.5,
  "high_mesh_uri": "stages/shape/candidate_01.glb",
  "low_mesh_uri": "stages/topology/topology.glb",
  "runtime_low_uri": "stages/topology/topology.glb",
  "high_triangle_count": 1376,
  "low_triangle_count": 1376,
  "triangle_delta_ratio": 0.0,
  "distinct_uris": true,
  "distinct_triangle_counts": false,
  "bake_maps": [
    {"map_name": "normal", "present": true, "uri": "stages/surface/maps/normal.png", "skipped_reason": null},
    {"map_name": "ao", "present": true, "uri": "stages/surface/maps/ao.png", "skipped_reason": null},
    {"map_name": "curvature", "present": true, "uri": "stages/surface/maps/curvature.png", "skipped_reason": null},
    {"map_name": "id", "present": true, "uri": "stages/surface/maps/id.png", "skipped_reason": null}
  ],
  "bake_map_count_present": 4,
  "bake_map_count_expected": 4,
  "skipped_reasons": [],
  "warnings": [
    "hero asset uses fake high/low: high_triangle_count == low_triangle_count == 1376; consider a real high-poly producer (Phase 8+)."
  ],
  "diagnostics": [],
  "required": true
}
```

The 18 top-level keys above are the stable contract returned directly
by `evaluate_highlow_relation`. The published `runtime["highlow_relation"]`
and `report["highlow_relation"]` payloads contain 17 keys — the
`FunctionValidator.evaluate` wrapper extracts `diagnostics` out of the
evidence dict and routes it to the validator-pipeline's per-validator
`diagnostics` field per the standard contract (see
`lathe/validators/composition.py:103`). The two surfaces are equivalent
for downstream consumers; only the publication path differs.

---

## 4. Realness scoring formula

The score is a sum of four weighted credits, clamped to `[0.0, 1.0]`:

```
distinct_uri_credit       = 0.15  if distinct_uris else 0.0
distinct_triangle_credit  = 0.30  if triangle_delta_ratio >= 0.20
                          = 0.30 * (triangle_delta_ratio / 0.20)  otherwise
bake_map_completeness     = 0.25 * (bake_map_count_present / max(1, bake_map_count_expected))
manifest_quality          = 0.10  if (high_uri and low_uri and skipped_reasons == []) else 0.0

realness_score = clamp(
    distinct_uri_credit
    + distinct_triangle_credit
    + bake_map_completeness
    + manifest_quality,
    0.0,
    1.0,
)
```

`is_real_highlow == realness_score >= 0.80` is the warning threshold.
`triangle_delta_ratio` is directional: it is `(high - low) / high`
only when `high_triangle_count > low_triangle_count >= 0`; missing,
equal, or inverted counts yield `0.0`.

### Reference values

| Fixture | distinct URIs | tri delta ratio | bake maps | skipped | score |
|---|---|---|---|---|---|
| Fake (no URIs, no maps) | False | 0.0 | 0 / 4 | yes | 0.0 |
| Industrial crate baseline | True | 0.0 | 4 / 4 | no | 0.50 |
| Inverted counts (low > high) | True | 0.0 | 4 / 4 | no | 0.50 |
| Real (distinct + 30% delta + 4 maps) | True | >= 0.20 | 4 / 4 | no | 0.80 |

The industrial crate baseline lands at exactly 0.50, well above 0.05
(fake) and well below 0.80 (real) — clearly mid-tier, fires the
warning, and signals that a real high-poly producer is required to
clear the gate.

---

## 5. Skipped-evidence contract

When the surface bundle does not publish a usable URI for a canonical
bake map, the `BakeMapEvidence` records a structured
`skipped_reason` token instead of a fabricated URI:

| Reason | When it fires |
|---|---|
| `no_high_poly_source` | `high_mesh_uri` is absent — there is no source mesh to bake from. |
| `manifest_incomplete` | The high mesh URI is present but a specific bake map is missing from the surface outputs. |
| `blender_unavailable` | Reserved for the Phase 8 producer integration; not emitted at Phase 7. |

The same reason tokens are aggregated under the top-level
`skipped_reasons` list in the form `{"tool": "...", "reason": "..."}`
so downstream consumers can surface the cause without re-keying.

---

## 6. Pipeline placement

The validator is registered in `lathe/core/stages/validate.py`'s
`_PIPELINE` immediately after `flow_quality` and before
`geometry_integrity`. The full validate-stage validator order is:

```
design_brief
construction_graph
grammar_lowering
family_grammar
semantic_quality
visual_quality
flow_quality
highlow_relation        # Phase 7
material_wear_graph
geometry_integrity
quality_diagnostics
urdf_validation
gameplay_tags
```

`highlow_relation` declares `stage_dependencies=["topology",
"surface"]` and `weight=0.0`. The pipeline composition layer
publishes each validator's `evidence` dict to `runtime[name]` after
it runs, so `quality_diagnostics` (registered later) observes the
new `runtime["highlow_relation"]` block when it computes the
strengthened `highlow_fake_detail_penalty`.

---

## 7. Strict mode

Strict mode is opt-in via the `LATHE_STRICT_HIGHLOW` environment
variable. Truthy values (`"1"`, `"true"`, `"yes"`, case-insensitive)
flip the validator behaviour:

- Default mode keeps `diagnostics=[]` even when the verdict fails.
  The warning text appears under the `warnings` key only. The
  `FunctionValidator` wrapper computes `passes=True` because no
  diagnostic carries `severity="error"`.
- Strict mode appends one diagnostic per failed verdict with
  `severity="error"`, `code="L6701"`, and
  `name="highlow_fake_detail"`. The `FunctionValidator` wrapper
  flips `passes=False`, and `validate.py:run` extends the top-level
  `diagnostics` list with the strict-mode entry. This causes
  `certified` to drop to `False` regardless of the aggregate score.
- The build-cache fingerprint includes the strict-mode flag, so a
  non-strict cached build cannot be restored for a strict build.

### When to use strict mode

- For projects that require a real high-poly source as a hard
  contract (e.g. the Phase 14 golden examples).
- For CI lanes that explicitly gate on the high-poly producer.

### When not to use strict mode

- For the default v0.2.0 release lanes — strict mode would block
  every existing example because none of them ship with a real
  high-poly producer yet.
- For unit tests of unrelated validators, where polluting the
  environment leaks state across tests.

### Enabling strict mode

```bash
# bash / zsh
export LATHE_STRICT_HIGHLOW=1
python -m lathe.cli build examples/industrial_crate.lth industrial_crate --out dist

# PowerShell
$env:LATHE_STRICT_HIGHLOW = '1'
python -m lathe.cli build examples/industrial_crate.lth industrial_crate --out dist
```

---

## 8. Phase 1 strengthening

The Phase 1 metric `highlow_fake_detail_penalty` lives in
`lathe/asset_quality/diagnostics.py` and was originally a heuristic
over the surface bundle alone. Phase 7 strengthens the computation:

- When `runtime["highlow_relation"]` is published (the live pipeline
  case once Phase 7 is wired), the penalty is sourced from the
  strengthened evidence: `penalty = 1.0 - realness_score`.
- When the new evidence is absent (legacy callers, unit tests that
  mock only the surface bundle), the metric falls back to the
  Phase 1 heuristic so the metric stays defined at every callsite.

The metric value still lives at the same path
(`quality_diagnostics.metrics.highlow_fake_detail_penalty`),
preserves the same `[0.0, 1.0]` bounds, and uses the same warning
threshold (0.40). For the industrial_crate baseline the live
penalty drops from the Phase 1 heuristic value to `0.50`
(= `1.0 - 0.50`) — slightly different, still above the threshold,
and now resistant to hidden-fake configurations the Phase 1
heuristic credited as real.

---

## 9. Forward references

- **Phase 8 — material / wear graph.** Will consume the same
  surface evidence (`bake_maps`, `bake_map_count_present`) to drive
  authored wear-mask and material-zone variation. The
  `op.chip_edges` and `op.repeat` v2 ops emitted by Phase 6's
  industrial_crate recipe are the upstream wear-zone hooks that
  Phase 8 will lower against.
- **Phase 14 — golden examples.** Will demonstrate a real
  high-poly producer driving distinct triangle counts, distinct
  URIs, and four bake maps with no skipped reasons; running the
  Phase 14 example with `LATHE_STRICT_HIGHLOW=1` is the canonical
  end-to-end verification.

---

## 10. Verification commands

```bash
# Unit tests for the new module
python -m pytest tests/unit/test_asset_quality_highlow_relation.py -v

# Phase 0-7 asset-quality test suite
python -m pytest tests/unit/test_asset_quality_*.py -q

# Validator-pipeline + report-shape contract tests
python -m pytest tests/unit/test_validate_stage_report.py \
                 tests/unit/test_reports.py \
                 tests/unit/test_reports_extended.py \
                 tests/unit/test_quality_gate_wiring.py -q

# Existing example still parses + checks clean
python -m lathe.cli check examples/industrial_crate.lth

# Inspect the live payload
python -c "from lathe.asset_quality.highlow_relation import HIGHLOW_RELATION_VERSION; print(HIGHLOW_RELATION_VERSION)"

# Regenerate the baseline fixture and inspect the new report key
python -m lathe.cli build examples/industrial_crate.lth industrial_crate \
       --out .tmp_tests/baseline_industrial_crate --deterministic
python -c "import json; r=json.load(open('.tmp_tests/baseline_industrial_crate/industrial_crate/stages/validate/report.json')); print(len(r), 'highlow_relation' in r, r['highlow_relation']['is_real_highlow'], r['highlow_relation']['realness_score'])"
```

Strict-mode smoke check:

```bash
LATHE_STRICT_HIGHLOW=1 python -c "
from lathe.asset_quality.highlow_relation import evaluate_highlow_relation
runtime = {'surface': {'bundle': {'highlow_relation': {'high_mesh_uri': None, 'low_mesh_uri': None, 'high_triangle_count': 0, 'low_triangle_count': 0}, 'outputs': {}}}}
r = evaluate_highlow_relation({'name': 'industrial_crate'}, runtime)
assert r['diagnostics'], 'strict mode should produce a diagnostic'
print('strict mode OK')
"
```
