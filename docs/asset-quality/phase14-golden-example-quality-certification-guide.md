# Phase 14 Guide — Golden Example Upgrade Evidence / Quality Certification

Date: 2026-04-30  
Scope: Lathe asset-quality upgrade Phase 14  
Primary example: Golden industrial crate  
Supporting smoke examples: mechanical door, service cabinet, terminal or supply chest

## 1. Phase 14 goal

Phase 14 proves that the asset-quality upgrade is no longer just architecture, diagnostics, or isolated fixtures. It must demonstrate a representative asset that moves through the upgraded quality pipeline and produces stable, reviewable evidence.

The target is not merely “the example builds.” The target is:

> One golden asset, with a complete design brief, grammar-backed construction, high/low relationship evidence, material/wear evidence, preview evidence, certification thresholds, deterministic snapshots, and an honest quality report that can be used as a regression fixture.

This phase should end with a checked-in evidence document:

```text
docs/asset-quality/quality-upgrade-evidence.md
```

and a golden fixture bundle that future phases and CI can validate.

## 2. Non-negotiable rules

1. **Do not fake renderer output.** If a final preview, Blender render, baked texture, USD export, or external viewer output was not actually produced, record a truthful skipped reason.
2. **Do not claim strict certification until examples pass strict thresholds.** Strict mode stays opt-in until the golden example satisfies the strict bar.
3. **Do not rely on visual vibes alone.** Certification must combine machine-readable evidence, human-readable summaries, deterministic diagnostics, and preview/evidence artifacts where available.
4. **Do not break public `.lth` compatibility.** Phase 14 should consume proven internals from earlier phases. Public syntax changes belong to Phase 13 only if all parser/spec/schema/checker/docs/tests layers were updated together.
5. **Do not certify smoke examples at the same level as the hero golden example.** The smoke examples exist to prove breadth and regression coverage, not full hero readiness.
6. **Every pass/fail must be traceable.** If the report says “passed,” it must point to the evidence file, score, threshold, fixture, or diagnostic that justifies the claim.

## 3. Expected output shape

Recommended fixture layout:

```text
examples/asset_quality/golden_industrial_crate/
  design_brief.json
  asset_source.lth                         # if public syntax exists and is valid
  source_status.json                       # if `.lth` source is deferred/partial
  construction_graph.json
  family_grammar_coverage.json
  shape_ir_v2.json
  high_low_relation.json
  material_wear_graph.json
  reference_board.json
  preview_evidence.json
  vision_critique.example.json
  quality_certificate.json
  quality_report.md
  snapshots/
    construction_graph.snapshot.json
    high_low_relation.snapshot.json
    material_wear_graph.snapshot.json
    quality_certificate.snapshot.json
  previews/
    final_beauty.png                       # only if actually generated
    material_ids.png                       # only if actually generated
    wireframe.png                          # only if actually generated
    comparison_sheet.png                   # only if actually generated
```

Supporting examples:

```text
examples/asset_quality/smoke_mechanical_door/
examples/asset_quality/smoke_service_cabinet/
examples/asset_quality/smoke_terminal_or_supply_chest/
```

Smoke example minimum files:

```text
design_brief.json
construction_graph.json
family_grammar_coverage.json
material_wear_graph.json
preview_evidence.json
quality_certificate.json
```

Phase-level evidence document:

```text
docs/asset-quality/quality-upgrade-evidence.md
```

## 4. Definition of done

Phase 14 is complete only when all of the following are true:

- Golden industrial crate fixture exists and is deterministic.
- Golden fixture includes a design brief with art direction, constraints, style, platform budget, and acceptance goals.
- Family grammar coverage proves which grammar rules were used and which required crate-family features are represented.
- Construction graph proves the asset is built from semantic parts, not anonymous primitive clutter.
- High/low relation evidence exists and honestly describes whether a real bake, proxy bake, or deferred bake was used.
- Material/wear graph exists and maps material/wear decisions to semantic surfaces or construction nodes.
- Preview evidence exists and distinguishes final beauty, debug/material-ID/wireframe views, missing outputs, and skipped lanes.
- Quality certificate exists with warning and strict thresholds.
- Strict mode is opt-in unless the golden fixture passes strict mode.
- Smoke examples exist for mechanical door, service cabinet, and terminal/supply chest.
- Deterministic tests or snapshots cover the report/certificate/evidence artifacts.
- `docs/asset-quality/quality-upgrade-evidence.md` summarizes what was proven, what was skipped, and what remains non-certified.

## 5. Golden industrial crate specification

The industrial crate is the hero because it is simple enough to make deterministic but rich enough to reveal whether the quality upgrade matters.

### 5.1 Design brief requirements

`design_brief.json` should answer:

- What is the asset?
- What world/style does it belong to?
- What makes it production-like rather than blockout-like?
- What semantic surfaces exist?
- What platform profile does it target?
- What visual details are required?
- What details are forbidden?
- What certification tier is being attempted?

Example shape:

```json
{
  "schema_version": "lathe.asset_quality.design_brief.v1",
  "asset_id": "golden_industrial_crate",
  "family": "industrial_crate",
  "style": {
    "theme": "used hard-surface sci-fi utility crate",
    "keywords": ["rugged", "modular", "edge-worn", "readable silhouette"],
    "forbidden": ["toy-like proportions", "random greebles", "flat unbroken cube"]
  },
  "platform_profile": {
    "target": "game_runtime_proxy",
    "triangle_budget_warning": 2500,
    "triangle_budget_strict": 1500,
    "texture_budget": "proxy_or_deferred"
  },
  "required_features": [
    "beveled outer shell",
    "reinforced corners",
    "recessed side panels",
    "latch or handle affordance",
    "material-zone separation",
    "edge wear or contact grime intent"
  ],
  "acceptance_goals": {
    "silhouette_readability": "clear at thumbnail distance",
    "construction_intent": "all visible major forms trace to semantic parts",
    "material_storytelling": "wear appears on plausible exposed/contact regions"
  }
}
```

### 5.2 Family grammar coverage

The fixture must prove the crate is produced by a crate grammar, not arbitrary primitives.

`family_grammar_coverage.json` should include:

- family ID;
- required grammar rules;
- optional grammar rules;
- rules used by the fixture;
- missing rules;
- warning/strict status;
- references to construction graph node IDs.

Required crate grammar concepts:

- outer shell;
- reinforced frame or corner protection;
- recessed panels;
- lid seam or access face;
- latch/handle/interaction affordance;
- bevel policy;
- material zones;
- wear mask anchors.

The pass condition should not be “some crate-looking parts exist.” It should be “required semantic crate rules are represented and traceable.”

### 5.3 Construction graph

`construction_graph.json` should show the asset as a hierarchy of intentional parts.

Minimum node categories:

- `shell`;
- `frame`;
- `corner_guard`;
- `panel`;
- `seam`;
- `latch` or `handle`;
- `feet` or `base_contact`;
- `material_zone`;
- `wear_anchor`.

Each node should include:

- stable ID;
- semantic role;
- parent/child relation;
- approximate transform or bounds;
- material zone reference;
- quality-relevant annotations such as bevel/inset/socket/panel-line intent.

Certification checks:

- no major visible primitive is unclassified;
- repeated elements are represented as repeated semantic instances, not unrelated copies;
- attachments sit on meaningful hosts;
- latches/handles have plausible scale and placement;
- major silhouette contributors are named.

### 5.4 High/low relation evidence

`high_low_relation.json` must state one of three modes:

1. `real_bake` — real high-poly to low-poly bake was performed and outputs are present.
2. `proxy_bake` — deterministic proxy evidence exists, but no real DCC bake occurred.
3. `deferred` — bake lane is not executed; reason and future owner are recorded.

For Phase 14, `proxy_bake` is acceptable if truthful. The important thing is not to pretend that proxy evidence is a final production bake.

Required fields:

```json
{
  "schema_version": "lathe.asset_quality.high_low_relation.v1",
  "asset_id": "golden_industrial_crate",
  "mode": "proxy_bake",
  "high_source": "shape_ir_v2 or construction_graph",
  "low_target": "runtime_proxy_mesh",
  "maps": {
    "normal": { "status": "skipped", "reason": "No real bake producer in this lane" },
    "ao": { "status": "proxy", "evidence": "preview_evidence.json" },
    "curvature": { "status": "proxy", "evidence": "material_wear_graph.json" },
    "material_id": { "status": "present", "evidence": "previews/material_ids.png" }
  },
  "certification": {
    "warning_pass": true,
    "strict_pass": false,
    "strict_blockers": ["real_bake_not_executed"]
  }
}
```

### 5.5 Material/wear graph

`material_wear_graph.json` should prove material decisions are semantic.

Required material zones:

- base painted metal or composite;
- dark rubber/plastic feet or pads;
- exposed metal edges or fasteners;
- warning/decal/accent zone if supported;
- dirt/grime/contact wear zone if supported.

Required wear logic:

- convex edge wear attaches to exposed edges/corners;
- contact grime attaches to feet/base/lower panels;
- handling wear attaches near latch/handle;
- panel dirt respects seams/recesses;
- random noise is not treated as storytelling.

The material graph should reference construction graph nodes or semantic surface IDs.

### 5.6 Preview evidence

`preview_evidence.json` should describe every expected visual artifact, whether present or skipped.

Minimum fields:

```json
{
  "schema_version": "lathe.asset_quality.preview_evidence.v1",
  "asset_id": "golden_industrial_crate",
  "views": {
    "final_beauty": {
      "status": "present",
      "path": "previews/final_beauty.png"
    },
    "material_ids": {
      "status": "present",
      "path": "previews/material_ids.png"
    },
    "wireframe": {
      "status": "present",
      "path": "previews/wireframe.png"
    },
    "comparison_sheet": {
      "status": "present",
      "path": "previews/comparison_sheet.png"
    }
  },
  "truthfulness": {
    "external_renderer_used": false,
    "reason": "Deterministic proxy preview only; no Blender/Roblox lane claimed."
  }
}
```

If previews are not generated, use:

```json
{
  "status": "skipped",
  "reason": "No preview producer available in this environment",
  "blocking_for_warning": false,
  "blocking_for_strict": true
}
```

## 6. Quality certification model

Phase 14 should introduce two quality modes.

### 6.1 Warning mode

Warning mode is the default certification level. It is intended to be strict enough to catch obvious prototype/blockout failures while allowing deferred external-runtime lanes.

Warning mode can pass with:

- deterministic proxy previews;
- proxy high/low evidence;
- skipped real bake if explicitly documented;
- skipped external renderer if explicitly documented;
- smoke examples that validate structure but not final beauty.

Warning mode should fail if:

- design brief is missing;
- construction graph is missing;
- family grammar coverage is missing;
- material/wear graph is missing;
- evidence files contradict each other;
- asset is mostly unclassified primitives;
- required crate features are absent;
- quality report makes unsupported claims.

### 6.2 Strict mode

Strict mode is opt-in until golden examples pass. It is the future CI/release gate.

Strict mode should require:

- all warning checks pass;
- final preview evidence present or explicit strict-approved renderer alternative;
- material-ID/wireframe/comparison evidence present;
- high/low relation is `real_bake` or an explicitly accepted strict proxy;
- no critical diagnostics;
- all required family grammar rules represented;
- smoke examples pass warning mode;
- deterministic snapshots are stable.

Strict mode should fail on:

- truthful-but-skipped final preview if strict requires preview;
- real bake missing when strict requires bake;
- unresolved major construction graph gaps;
- material/wear graph not traceable to construction nodes;
- random/anonymous primitive clusters;
- score below strict threshold.

### 6.3 Suggested scoring categories

Use a 100-point score, but keep pass/fail based on named gates too. Do not let a high aggregate score hide a critical missing artifact.

Suggested categories:

| Category | Weight | Warning threshold | Strict threshold |
|---|---:|---:|---:|
| Design brief completeness | 10 | 8 | 10 |
| Family grammar coverage | 15 | 10 | 14 |
| Construction graph traceability | 15 | 10 | 14 |
| Shape/detail hierarchy | 10 | 7 | 9 |
| High/low relation evidence | 10 | 6 | 9 |
| Material/wear graph | 15 | 10 | 14 |
| Preview evidence truthfulness | 10 | 7 | 10 |
| Platform/runtime budget | 5 | 3 | 5 |
| Determinism/snapshot stability | 5 | 4 | 5 |
| Report traceability | 5 | 4 | 5 |

Suggested gates:

```text
warning_pass = score >= 70 and no critical_missing_artifact
strict_pass  = score >= 90 and warning_pass and no strict_blockers
```

Critical missing artifacts:

- design brief;
- construction graph;
- family grammar coverage;
- material/wear graph;
- quality certificate;
- evidence report.

Strict blockers:

- final preview missing, unless strict policy explicitly allows proxy;
- real/proxy bake relation not documented;
- material IDs missing;
- unstable snapshot;
- any unsupported production-readiness claim.

## 7. Quality certificate format

Recommended `quality_certificate.json`:

```json
{
  "schema_version": "lathe.asset_quality.certificate.v1",
  "asset_id": "golden_industrial_crate",
  "certification_profile": "phase14_warning",
  "generated_at": "2026-04-30T00:00:00Z",
  "status": "warning_pass_strict_fail",
  "scores": {
    "total": 78,
    "design_brief": 10,
    "family_grammar": 12,
    "construction_graph": 13,
    "shape_detail_hierarchy": 7,
    "high_low_relation": 6,
    "material_wear_graph": 11,
    "preview_evidence": 7,
    "platform_budget": 4,
    "determinism": 4,
    "traceability": 4
  },
  "gates": {
    "warning_pass": true,
    "strict_pass": false,
    "critical_missing_artifact": false,
    "strict_blockers": ["real_bake_not_executed"]
  },
  "evidence": {
    "design_brief": "design_brief.json",
    "family_grammar_coverage": "family_grammar_coverage.json",
    "construction_graph": "construction_graph.json",
    "high_low_relation": "high_low_relation.json",
    "material_wear_graph": "material_wear_graph.json",
    "preview_evidence": "preview_evidence.json"
  },
  "claims": {
    "certified_for_production_game_use": false,
    "certified_for_phase14_quality_upgrade": true,
    "external_renderer_verified": false,
    "real_high_low_bake_verified": false
  },
  "notes": [
    "Phase 14 warning certification proves deterministic quality-pipeline evidence, not final DCC/game-engine production readiness."
  ]
}
```

## 8. Supporting smoke examples

The three smoke examples should prove the pipeline generalizes across hard-surface families.

### 8.1 Mechanical door

Must demonstrate:

- planar panel hierarchy;
- frame/threshold alignment;
- hinge/track/lock affordance;
- material zones;
- wear at edges/handle/threshold;
- platform budget diagnostics.

### 8.2 Service cabinet

Must demonstrate:

- vertical cabinet body;
- doors/drawers/panels;
- vents or handles;
- label/decal zone if supported;
- grime around base and handles;
- stable construction graph.

### 8.3 Terminal or supply chest

Must demonstrate:

- distinct interaction face;
- screen/keypad/button/lock/handle affordance;
- panel seams;
- accent material zone;
- readable silhouette;
- no random greeble clusters.

Smoke examples can pass warning mode with less preview evidence than the hero crate, but they still need truthful evidence files and deterministic validation.

## 9. Implementation checklist

### Step 1 — Inventory current asset-quality docs and modules

Confirm existing contracts from:

```text
docs/asset-quality/design-brief-ir.md
docs/asset-quality/family-grammar-v1.md
docs/asset-quality/semantic-construction-graph.md
docs/asset-quality/high-low-relation-v1.md
docs/asset-quality/material-wear-graph-v1.md
docs/asset-quality/preview-evidence-v1.md
docs/asset-quality/vision-critique-loop.md
docs/asset-quality/reference-board-v1.md
```

Do not invent a new schema if an existing one already defines the artifact.

### Step 2 — Create golden fixture directories

Create:

```text
examples/asset_quality/golden_industrial_crate/
examples/asset_quality/smoke_mechanical_door/
examples/asset_quality/smoke_service_cabinet/
examples/asset_quality/smoke_terminal_or_supply_chest/
```

If the repo already has a different fixture convention, follow the existing convention and document the path in `quality-upgrade-evidence.md`.

### Step 3 — Add deterministic evidence artifacts

For the golden crate, add or generate:

```text
design_brief.json
family_grammar_coverage.json
construction_graph.json
shape_ir_v2.json
high_low_relation.json
material_wear_graph.json
preview_evidence.json
quality_certificate.json
quality_report.md
```

For smoke examples, add minimum evidence artifacts.

### Step 4 — Add validator/certifier code only where needed

Prefer small modules over broad rewrites. Good targets may include:

```text
lathe/asset_quality/certification.py
lathe/asset_quality/examples.py
lathe/asset_quality/reports.py
lathe/asset_quality/snapshots.py
```

Only create these if equivalent modules do not already exist.

The certifier should:

- load evidence bundle;
- validate required files;
- validate internal references;
- compute category scores;
- produce `quality_certificate.json`;
- produce `quality_report.md`;
- distinguish warning and strict modes.

### Step 5 — Add CLI commands if project conventions support them

Suggested commands:

```bash
python -m lathe.cli asset-quality validate-example examples/asset_quality/golden_industrial_crate --mode warning
python -m lathe.cli asset-quality validate-example examples/asset_quality/golden_industrial_crate --mode strict
python -m lathe.cli asset-quality certify examples/asset_quality/golden_industrial_crate --out .tmp_tests/asset_quality/golden_crate_cert
python -m lathe.cli asset-quality catalog-examples examples/asset_quality --out .tmp_tests/asset_quality/example_catalog.json
```

If no `asset-quality` command group exists, either add it cleanly or use the repository’s existing CLI grouping. Do not bolt commands into unrelated command groups.

### Step 6 — Add tests and snapshots

Recommended tests:

```text
tests/unit/test_asset_quality_phase14_examples.py
tests/unit/test_asset_quality_certification.py
tests/snapshots/asset_quality/golden_industrial_crate_certificate.snapshot.json
tests/snapshots/asset_quality/golden_industrial_crate_report.snapshot.md
```

Test cases:

- golden crate warning mode passes;
- golden crate strict mode is opt-in and either passes or fails truthfully with named blockers;
- missing design brief fails;
- missing material/wear graph fails;
- skipped preview is allowed in warning mode but blocks strict mode when policy requires preview;
- smoke examples pass warning validation;
- certificate claims do not overstate external renderer or real bake status;
- snapshots are deterministic.

### Step 7 — Write `quality-upgrade-evidence.md`

The evidence doc should contain:

```markdown
# Asset Quality Upgrade Evidence

## Summary
## Golden example path
## Certification result
## Evidence artifacts
## Warning vs strict thresholds
## Smoke examples
## Preview/render truthfulness
## High/low and bake truthfulness
## Material/wear proof
## Known limitations
## Commands run
## Next phase handoff
```

The summary must be blunt. Example:

```text
Phase 14 proves deterministic quality-pipeline evidence for a golden industrial crate and three hard-surface smoke families. It does not claim final production-game certification because real DCC high/low baking and external renderer/game-engine verification remain outside this lane unless those artifacts are actually present.
```

## 10. Verification commands

Start narrow:

```bash
python -m pytest -q tests/unit/test_asset_quality_phase14_examples.py tests/unit/test_asset_quality_certification.py
```

Then run the relevant asset-quality command, if implemented:

```bash
python -m lathe.cli asset-quality certify examples/asset_quality/golden_industrial_crate --out .tmp_tests/asset_quality/golden_crate_cert
```

Validate warning and strict separately:

```bash
python -m lathe.cli asset-quality validate-example examples/asset_quality/golden_industrial_crate --mode warning
python -m lathe.cli asset-quality validate-example examples/asset_quality/golden_industrial_crate --mode strict
```

Catalog all examples:

```bash
python -m lathe.cli asset-quality catalog-examples examples/asset_quality --out .tmp_tests/asset_quality/example_catalog.json
```

If behavior changed broadly, run broader tests:

```bash
python -m pytest -q
```

## 11. Expected final summary for implementation agent

At the end of Phase 14, the implementation agent should report:

```text
Phase 14 complete.

Created/updated:
- examples/asset_quality/golden_industrial_crate/...
- examples/asset_quality/smoke_mechanical_door/...
- examples/asset_quality/smoke_service_cabinet/...
- examples/asset_quality/smoke_terminal_or_supply_chest/...
- docs/asset-quality/quality-upgrade-evidence.md
- tests/unit/test_asset_quality_phase14_examples.py
- tests/unit/test_asset_quality_certification.py

Certification:
- golden_industrial_crate warning: PASS/FAIL
- golden_industrial_crate strict: PASS/FAIL/SKIPPED with blockers
- smoke_mechanical_door warning: PASS/FAIL
- smoke_service_cabinet warning: PASS/FAIL
- smoke_terminal_or_supply_chest warning: PASS/FAIL

Truthfulness:
- external renderer used: yes/no
- real high/low bake used: yes/no
- proxy evidence used: yes/no
- skipped lanes: list

Commands run:
- <exact commands>

Remaining blockers:
- <exact blockers, if any>
```

## 12. Ready-to-paste Codex prompt

```text
You are working in the Lathe repo. Implement Phase 14 — Golden Examples and Quality Certification for the asset-quality upgrade.

Read and follow:
- AGENTS.md
- CLAUDE_CODE_ASSET_QUALITY_MASTER_PROMPT.md, Phase 14 section
- docs/asset-quality/design-brief-ir.md
- docs/asset-quality/family-grammar-v1.md
- docs/asset-quality/semantic-construction-graph.md
- docs/asset-quality/high-low-relation-v1.md
- docs/asset-quality/material-wear-graph-v1.md
- docs/asset-quality/preview-evidence-v1.md
- docs/asset-quality/vision-critique-loop.md
- docs/asset-quality/reference-board-v1.md
- docs/asset-quality/phase14-golden-example-quality-certification-guide.md

Goal:
Prove the quality upgrade with a golden industrial crate and stable certification evidence. Add supporting smoke examples for mechanical door, service cabinet, and terminal or supply chest.

Hard rules:
- Do not fake renderer, bake, Blender, Roblox, USD, or external viewer evidence.
- If an output is unavailable, write a truthful skipped reason with blocking_for_warning/blocking_for_strict semantics.
- Keep strict mode opt-in until examples pass strict thresholds.
- Do not change public `.lth` syntax unless all spec/grammar/schema/parser/normalizer/resolver/checker/examples/tests layers are updated together. Prefer internal evidence fixtures for this phase.
- Preserve existing Lathe public contracts unless this task explicitly requires a small additive internal module.

Implement:
1. Create or upgrade the golden industrial crate fixture.
   Include design brief, family grammar coverage, semantic construction graph, high/low relation evidence, material/wear graph, reference/preview evidence, quality certificate, quality report, and deterministic snapshots where appropriate.
2. Add smoke fixtures for mechanical door, service cabinet, and terminal or supply chest.
   Each smoke fixture must include minimum evidence needed for warning-mode validation.
3. Implement or extend asset-quality certification logic.
   It must support warning and strict modes, named category scores, critical missing artifact gates, strict blockers, and truthfulness claims.
4. Add or extend CLI support if project conventions support it:
   - validate one asset-quality example in warning/strict mode
   - certify one example to an output directory
   - catalog all asset-quality examples
5. Create `docs/asset-quality/quality-upgrade-evidence.md`.
   It must summarize what Phase 14 proves, the exact fixture paths, certification results, thresholds, commands run, skipped lanes, and known limitations.
6. Add deterministic tests/snapshots.
   Cover warning pass, strict opt-in/failure blockers if applicable, missing artifact failures, skipped preview truthfulness, smoke example validation, and unsupported production-readiness claim prevention.

Suggested paths, if no existing convention overrides them:
- examples/asset_quality/golden_industrial_crate/
- examples/asset_quality/smoke_mechanical_door/
- examples/asset_quality/smoke_service_cabinet/
- examples/asset_quality/smoke_terminal_or_supply_chest/
- lathe/asset_quality/certification.py
- lathe/asset_quality/examples.py
- lathe/asset_quality/reports.py
- tests/unit/test_asset_quality_phase14_examples.py
- tests/unit/test_asset_quality_certification.py
- docs/asset-quality/quality-upgrade-evidence.md

Suggested commands to support/run if implemented:
- python -m lathe.cli asset-quality validate-example examples/asset_quality/golden_industrial_crate --mode warning
- python -m lathe.cli asset-quality validate-example examples/asset_quality/golden_industrial_crate --mode strict
- python -m lathe.cli asset-quality certify examples/asset_quality/golden_industrial_crate --out .tmp_tests/asset_quality/golden_crate_cert
- python -m lathe.cli asset-quality catalog-examples examples/asset_quality --out .tmp_tests/asset_quality/example_catalog.json

Run the narrowest relevant pytest commands first, then broader tests if behavior changed.

Final response must include:
- files changed
- exact commands run
- certification results for golden crate and smoke examples
- whether external renderer was used
- whether real high/low bake was used
- whether strict mode passed or the exact strict blockers
- remaining limitations

Stop after Phase 14. Do not proceed into Phase 15 CI/regression gates unless asked.
```
