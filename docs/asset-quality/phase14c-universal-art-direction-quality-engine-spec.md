# Phase 14C Spec — Universal Art Direction Quality Engine

Date: 2026-04-30  
Project: Lathe asset-quality upgrade  
Phase: 14C  
Status: Implementation spec / agent handoff  
Primary goal: Upgrade Lathe from object-specific quality tricks to a reusable, family-agnostic art-direction quality system.

---

## 1. Executive Summary

Phase 14C is **not** a request to make one beautiful sword, one beautiful crate, or one beautiful Roblox prop.

Phase 14C is the beginning of Lathe becoming a **compiler for taste**.

The goal is to add a reusable quality layer that can look at any asset request and reason about why it should look good:

```text
asset intent
→ art direction IR
→ family grammar context
→ quality plan
→ construction/material/detail requirements
→ preview evidence
→ critique
→ semantic repair suggestions
→ certification
```

The reference fantasy sword quality target is useful only because it demonstrates the level of polish Lathe should eventually reach:

- strong silhouette;
- clear material separation;
- intentional motif language;
- primary / secondary / tertiary detail hierarchy;
- functional readability;
- emotional/art-direction coherence;
- no random procedural noise pretending to be detail.

But Phase 14C must generalize across object families.

The proof set must include at least four different asset categories:

```text
fantasy weapon
sci-fi crate
Roblox tycoon machine
environment/shop counter prop
```

If the upgrade only helps swords, Phase 14C failed.

---

## 2. Product Intent

Lathe should not compete as a basic prompt-to-mesh system.

Lathe should become:

> The compiler for AI-native, editable, certifiable, art-directed game assets and worlds.

Current Lathe asset-quality phases already introduced pieces like:

- design briefs;
- family grammar coverage;
- semantic construction graphs;
- high/low evidence;
- material/wear graphs;
- preview evidence;
- quality certificates.

Phase 14C adds the missing general layer:

> A universal art-direction engine that explains what “good” means before geometry is built, then validates and repairs outputs after preview/certification.

This matters because high-quality generated assets are not just more polygons. They require better design decisions:

- what should the object read as from far away?
- what is the primary shape?
- what secondary forms support it?
- what details are motif-driven versus noisy?
- how do material zones separate function and story?
- where should wear/grime/glow/decals appear?
- what should be forbidden for this style?
- what would make the asset look cheap, generic, or incoherent?

Lathe needs to answer those questions in a reusable way.

---

## 3. Non-Goals

Phase 14C must **not** implement:

1. A one-off celestial sword generator.
2. A one-off hardcoded fantasy weapon style.
3. A full real renderer, Blender pipeline, Roblox exporter, or USD viewer.
4. Real high/low baking unless already available and safe to wire truthfully.
5. A full kit compiler.
6. Scene/world generation.
7. Semantic patch execution over real meshes.
8. CI gating for all quality examples.
9. Public `.lth` syntax changes unless every public language layer is updated together.
10. Production-game certification claims without real render/bake/export evidence.

Phase 14C may create internal JSON fixtures, Python helpers, validators, docs, tests, and CLI/report integration.

---

## 4. Core Principle

The core principle is:

```text
Do not teach Lathe what a sword looks like.
Teach Lathe what visual quality means, then apply that to swords, crates, machines, furniture, props, and future worlds.
```

This means every module should ask:

- Is this family-agnostic?
- Can this consume family metadata instead of hardcoded object names?
- Can this produce useful output for at least four different object categories?
- Does this produce repair suggestions, not just scores?

---

## 5. Existing Context to Read First

Implementation agents must read these before coding:

```text
AGENTS.md
CLAUDE_CODE_ASSET_QUALITY_MASTER_PROMPT.md
docs/asset-quality/lathe-asset-quality-upgrade-spec.md
docs/asset-quality/lathe-next-level-asset-quality-roadmap.md
docs/asset-quality/design-brief-ir.md
docs/asset-quality/family-grammar-v1.md
docs/asset-quality/semantic-construction-graph.md
docs/asset-quality/high-low-relation-v1.md
docs/asset-quality/material-wear-graph-v1.md
docs/asset-quality/reference-board-v1.md
docs/asset-quality/preview-evidence-v1.md
docs/asset-quality/vision-critique-loop.md
docs/asset-quality/quality-upgrade-evidence.md
docs/asset-quality/phase14-golden-example-quality-certification-guide.md
```

Relevant current implementation paths may include:

```text
lathe/asset_quality/
lathe/cli/asset_quality_cmd.py
examples/asset_quality/golden_industrial_crate/
examples/asset_quality/smoke_mechanical_door/
examples/asset_quality/smoke_service_cabinet/
examples/asset_quality/smoke_terminal_or_supply_chest/
tests/unit/test_asset_quality_certification.py
tests/unit/test_asset_quality_phase14_examples.py
```

Do not duplicate existing concepts. Extend or compose them.

---

## 6. New Architecture

Phase 14C introduces five conceptual layers.

```text
1. Art Direction IR
2. Quality Planner
3. Universal Quality Validators
4. Semantic Critique / Repair Suggestions
5. Multi-family Proof Fixtures
```

### 6.1 Art Direction IR

The Art Direction IR captures the general visual/design intent for any asset.

It lives above family-specific construction.

It answers:

- What is the desired style?
- What should be the primary read?
- What materials should contrast?
- What motifs are allowed or forbidden?
- What surface story should exist?
- What platform constraints matter?
- What failure modes should be avoided?

Suggested file:

```text
lathe/asset_quality/art_direction.py
```

Suggested docs:

```text
docs/asset-quality/art-direction-ir-v1.md
```

### 6.2 Quality Planner

The Quality Planner converts:

```text
design brief + family metadata + reference/style context
```

into:

```text
quality_plan.json
```

The quality plan should be the bridge between intent and construction/material decisions.

Suggested file:

```text
lathe/asset_quality/quality_planner.py
```

Suggested docs:

```text
docs/asset-quality/quality-planner-v1.md
```

### 6.3 Universal Quality Validators

Universal validators score quality dimensions that apply across many asset families:

```text
silhouette_strength
proportion_intent
material_contrast
detail_hierarchy
motif_coherence
surface_storytelling
functional_readability
style_consistency
procedural_noise_penalty
```

These validators may consume family metadata, construction graph nodes, material/wear graph zones, and preview evidence, but their logic should not be sword-specific or crate-specific.

Suggested file:

```text
lathe/asset_quality/universal_quality.py
```

or compose inside existing certification modules if the repo already has a better pattern.

### 6.4 Semantic Critique / Repair Suggestions

A high-quality validation system should not only say:

```text
material contrast failed
```

It should produce actionable semantic repair guidance:

```json
{
  "issue": "low_material_contrast",
  "target": "material_zones.primary_vs_accent",
  "repair": "increase value and hue separation between primary and accent zones; bind accent to focal affordance",
  "preserve": ["primary_silhouette", "functional_parts"]
}
```

Suggested file:

```text
lathe/asset_quality/semantic_critique.py
```

### 6.5 Multi-Family Proof Fixtures

Phase 14C must prove generalization with multiple asset families.

Suggested fixture root:

```text
examples/asset_quality/quality_engine/
```

Required fixture examples:

```text
examples/asset_quality/quality_engine/fantasy_weapon/
examples/asset_quality/quality_engine/sci_fi_crate/
examples/asset_quality/quality_engine/roblox_tycoon_machine/
examples/asset_quality/quality_engine/environment_shop_counter/
```

Each fixture should include:

```text
design_brief.json
art_direction.json
quality_plan.json
family_metadata.json or family_grammar_coverage.json
material_wear_graph.json
preview_evidence.json
quality_certificate.json
semantic_critique.example.json
```

If existing naming conventions differ, follow repo conventions and document the deviation.

---

## 7. Universal Quality Dimensions

These are the quality dimensions Phase 14C must model.

### 7.1 Silhouette Strength

Question:

> Can the object be recognized at thumbnail distance?

Applies to every object.

Evidence may include:

- silhouette goals in `quality_plan.json`;
- construction graph primary forms;
- preview evidence, if available;
- family metadata listing distinctive features.

Scoring should consider:

- primary outline clarity;
- distinctive feature count;
- boring primitive penalty;
- clutter/noise penalty;
- thumbnail readability goal.

Example outputs:

```json
{
  "dimension": "silhouette_strength",
  "score": 8,
  "max_score": 10,
  "diagnostics": [],
  "repair_suggestions": []
}
```

Failure example:

```json
{
  "dimension": "silhouette_strength",
  "score": 4,
  "diagnostics": ["primary outline is a generic rectangular block"],
  "repair_suggestions": [
    {
      "issue": "generic_silhouette",
      "target": "quality_plan.silhouette.required_distinctive_features",
      "repair": "add one family-specific silhouette feature and one style-specific silhouette accent",
      "preserve": ["platform_budget", "functional_parts"]
    }
  ]
}
```

### 7.2 Proportion Intent

Question:

> Are the major parts sized intentionally relative to function and style?

This should be family-aware but not family-hardcoded.

Examples:

- weapon blade/hilt relationship;
- crate panel/frame relationship;
- machine body/button/conveyor relationship;
- counter height/display/storage relationship.

Scoring should consider:

- proportions defined in plan;
- family grammar proportion bands;
- functional part scale;
- style exaggeration policy.

### 7.3 Material Contrast

Question:

> Are materials separated clearly enough to communicate form, function, and story?

A good asset usually has:

- primary material;
- secondary material;
- accent material;
- interaction/wear material;
- optional emissive/glow/decal material.

The validator should not require every asset to have all five. It should require a coherent plan and meaningful contrast.

### 7.4 Detail Hierarchy

Question:

> Are details organized into primary, secondary, and tertiary reads instead of random noise?

Scoring should reward:

- named primary forms;
- medium details that reinforce construction;
- tertiary detail zones with bounds;
- detail density variation;
- explicit no-noise policy.

Scoring should penalize:

- uniform detail everywhere;
- repeated stripes/ribs with no semantic purpose;
- tiny details without supporting large forms;
- detail that contradicts motif/style.

### 7.5 Motif Coherence

Question:

> Do decorative details belong to the asset’s theme and world?

Motifs are not only fantasy symbols. They can be industrial, cute, horror, sci-fi, premium, toy-like, Roblox-y, etc.

Examples:

```text
fantasy_weapon: stars, crystal facets, crescent arcs, runes
sci_fi_crate: panels, latches, labels, vents, corner guards
roblox_tycoon_machine: bright upgrade buttons, arrows, coin/cash icons, conveyor language
environment_shop_counter: signage, trim, display shelves, scuffs, product zones
```

The motif validator should compare used motifs against allowed/forbidden motifs.

### 7.6 Surface Storytelling

Question:

> Do wear, grime, decals, scratches, glow, polish, and color accents appear where they make sense?

Reward:

- contact wear on contact points;
- grime in recesses/lower regions;
- hand polish around handles/buttons;
- damage on exposed edges;
- decals on readable flat zones;
- glow on magical/energy/electrical zones.

Penalize:

- random noise as material detail;
- wear on impossible/unreachable places;
- decals crossing seams incoherently;
- every surface having the same wear.

### 7.7 Functional Readability

Question:

> Can a viewer infer what the object does?

Examples:

- weapon has blade/grip/guard or equivalent;
- crate has lid/seam/latch/handle or equivalent;
- machine has input/output/button/status/interaction region;
- counter has top surface/display/storage/customer-facing side.

This is core to game art.

### 7.8 Style Consistency

Question:

> Do all forms, materials, motifs, and surface stories belong to the same world?

This validator should catch:

- fantasy motifs mixed with random industrial parts with no bridge;
- premium material next to toy proportions accidentally;
- sci-fi panels on a medieval chest unless style says techno-fantasy;
- visual language conflicts between family and style.

### 7.9 Procedural Noise Penalty

Question:

> Is the asset hiding weak design behind repeated procedural clutter?

This is one of the most important validators.

Penalize:

- repeated unmotivated ribs;
- uniformly distributed tiny panels;
- random greebles without function/motif;
- high-frequency stripes on every surface;
- detail not linked to construction graph, motif language, material graph, or functional affordance.

---

## 8. Data Contracts

### 8.1 `art_direction.json`

Recommended shape:

```json
{
  "schema_version": "lathe.asset_quality.art_direction.v1",
  "asset_id": "example_asset",
  "object_family": "weapon.blade",
  "style_intent": {
    "genre": "fantasy",
    "substyle": "celestial frost",
    "mood": ["elegant", "magical", "premium"],
    "audience": "game asset",
    "quality_bar": "hero"
  },
  "visual_hierarchy": {
    "primary_read": "recognizable object identity at thumbnail distance",
    "secondary_read": "functional parts and major silhouette accents",
    "tertiary_read": "ornament, decals, wear, microdetail",
    "noise_policy": "tertiary detail must map to motif, material, function, or surface story"
  },
  "silhouette": {
    "target_strength": "high",
    "thumbnail_size_px": 128,
    "required_distinctive_features": [],
    "forbidden_shapes": []
  },
  "materials": {
    "required_separation": "high",
    "contrast_policy": "primary/secondary/accent/readability",
    "zones": []
  },
  "motifs": {
    "allowed": [],
    "forbidden": [],
    "placement_rules": []
  },
  "surface_story": {
    "wear_logic": [],
    "decals": [],
    "grime_logic": [],
    "glow_logic": []
  },
  "platform": {
    "target": "realtime_proxy",
    "triangle_budget_warning": 2500,
    "triangle_budget_strict": 1500,
    "texture_policy": "proxy_or_deferred"
  },
  "forbidden_failure_modes": [
    "generic_primitive_silhouette",
    "uniform_noise_detail",
    "unseparated_materials",
    "motif_style_conflict"
  ]
}
```

### 8.2 `quality_plan.json`

Recommended shape:

```json
{
  "schema_version": "lathe.asset_quality.quality_plan.v1",
  "asset_id": "example_asset",
  "source_art_direction": "art_direction.json",
  "source_family_metadata": "family_metadata.json",
  "primary_secondary_tertiary": {
    "primary": [],
    "secondary": [],
    "tertiary": []
  },
  "silhouette_requirements": {
    "required_features": [],
    "thumbnail_readability": "high",
    "forbidden_generic_shapes": []
  },
  "proportion_requirements": {
    "family_bands": [],
    "style_exaggerations": []
  },
  "material_requirements": {
    "zones": [],
    "contrast_pairs": [],
    "accent_policy": "bind accents to focal/function zones"
  },
  "detail_requirements": {
    "density_zones": [],
    "tertiary_detail_budget": "bounded",
    "noise_policy": "semantic-only"
  },
  "motif_requirements": {
    "allowed": [],
    "forbidden": [],
    "placement_rules": []
  },
  "surface_story_requirements": {
    "wear": [],
    "grime": [],
    "decals": [],
    "glow": []
  },
  "certification_targets": {
    "warning_min_score": 70,
    "strict_min_score": 90,
    "required_dimensions": [
      "silhouette_strength",
      "proportion_intent",
      "material_contrast",
      "detail_hierarchy",
      "motif_coherence",
      "surface_storytelling",
      "functional_readability",
      "style_consistency",
      "procedural_noise_penalty"
    ]
  },
  "likely_failure_modes": []
}
```

### 8.3 `semantic_critique.example.json`

Recommended shape:

```json
{
  "schema_version": "lathe.asset_quality.semantic_critique.v1",
  "asset_id": "example_asset",
  "source_quality_plan": "quality_plan.json",
  "summary": {
    "status": "warning_pass_with_repairs",
    "highest_priority_issue": "low_material_contrast"
  },
  "issues": [
    {
      "issue": "low_material_contrast",
      "severity": "warning",
      "dimension": "material_contrast",
      "target": "material_zones.primary_vs_accent",
      "evidence": ["material_wear_graph.json"],
      "repair": "increase value/hue separation between primary and accent zones and bind accent material to focal affordance",
      "preserve": ["primary_silhouette", "functional_parts"]
    }
  ]
}
```

---

## 9. Proof Fixtures

### 9.1 Fantasy Weapon Fixture

Path:

```text
examples/asset_quality/quality_engine/fantasy_weapon/
```

Purpose:

Proves the quality engine can handle high-polish decorative objects without hardcoded sword logic.

Required quality concepts:

- strong object silhouette;
- primary/secondary/tertiary reads;
- magical or premium material separation;
- motif language;
- ornament placement rules;
- no procedural-noise-as-detail;
- functional grip/interaction readability.

Important: This can be a sword-like fixture, but validators and planner must not contain sword-specific branches unless driven by `object_family` metadata.

### 9.2 Sci-Fi Crate Fixture

Path:

```text
examples/asset_quality/quality_engine/sci_fi_crate/
```

Purpose:

Proves the quality engine supports hard-surface utilitarian assets.

Required quality concepts:

- box-like but not boring silhouette;
- panels, latches, handles, corner guards;
- material zone separation;
- decals/labels where readable;
- contact wear and grime;
- functional readability.

### 9.3 Roblox Tycoon Machine Fixture

Path:

```text
examples/asset_quality/quality_engine/roblox_tycoon_machine/
```

Purpose:

Proves the quality engine supports game/business-relevant Roblox asset families.

Required quality concepts:

- bright thumbnail readability;
- clear interaction affordance;
- button/conveyor/dropper/status zones;
- platform budget awareness;
- stylized material contrast;
- no excessive microdetail that fails at Roblox scale.

### 9.4 Environment Shop Counter Fixture

Path:

```text
examples/asset_quality/quality_engine/environment_shop_counter/
```

Purpose:

Proves the quality engine handles environmental/furniture props, not just weapons/machines.

Required quality concepts:

- usable scale/proportion;
- front/back/customer-facing readability;
- trim/signage/display motif;
- surface story from use;
- material hierarchy;
- style consistency with a shop/world context.

---

## 10. Certification Integration

Existing quality certificates should be extended to include universal quality categories.

Add a section like:

```json
{
  "universal_quality": {
    "silhouette_strength": {
      "score": 8,
      "max_score": 10,
      "diagnostics": [],
      "repair_suggestions": []
    },
    "proportion_intent": {
      "score": 7,
      "max_score": 10,
      "diagnostics": [],
      "repair_suggestions": []
    },
    "material_contrast": {
      "score": 8,
      "max_score": 10,
      "diagnostics": [],
      "repair_suggestions": []
    }
  }
}
```

Certification must still distinguish:

```text
warning pass
strict pass/fail
critical missing artifacts
strict blockers
unsupported claims
```

New universal quality categories should improve the quality signal, not replace truthfulness gates.

A high universal quality score must not hide missing render/bake/export evidence.

---

## 11. CLI Behavior

If current CLI patterns support it, add or extend commands for the quality engine.

Suggested commands:

```bash
python -m lathe.cli asset-quality plan-quality examples/asset_quality/quality_engine/fantasy_weapon --out .tmp_tests/asset_quality/fantasy_weapon_quality_plan.json

python -m lathe.cli asset-quality critique-quality examples/asset_quality/quality_engine/fantasy_weapon --out .tmp_tests/asset_quality/fantasy_weapon_critique.json

python -m lathe.cli asset-quality validate-example examples/asset_quality/quality_engine/fantasy_weapon --mode warning

python -m lathe.cli asset-quality catalog-examples examples/asset_quality/quality_engine --out .tmp_tests/asset_quality/quality_engine_catalog.json
```

If adding CLI commands creates too much scope, implement the core Python modules and tests first, then document CLI as future work. Do not create brittle CLI wiring that bypasses the project’s command conventions.

---

## 12. Testing Requirements

Add tests for the new quality engine.

Suggested files:

```text
tests/unit/test_asset_quality_art_direction.py
tests/unit/test_asset_quality_quality_planner.py
tests/unit/test_asset_quality_universal_quality.py
tests/unit/test_asset_quality_semantic_critique.py
```

Update if needed:

```text
tests/unit/test_asset_quality_certification.py
tests/unit/test_asset_quality_phase14_examples.py
```

### 12.1 Art Direction IR Tests

Required cases:

- loads valid art direction fixture;
- applies defaults for optional sections;
- rejects missing required asset/family/style fields;
- preserves forbidden failure modes;
- supports all four proof fixture families.

### 12.2 Quality Planner Tests

Required cases:

- creates `quality_plan` for fantasy weapon;
- creates `quality_plan` for sci-fi crate;
- creates `quality_plan` for Roblox tycoon machine;
- creates `quality_plan` for environment shop counter;
- outputs primary/secondary/tertiary reads for every family;
- outputs material contrast requirements;
- outputs motif requirements;
- outputs surface story requirements;
- outputs likely failure modes;
- does not rely on hardcoded `sword` checks.

### 12.3 Universal Validator Tests

Required cases:

- silhouette validator rewards distinctive features;
- silhouette validator penalizes generic primitive silhouette;
- material contrast validator rewards separated semantic zones;
- material contrast validator produces repair suggestion when contrast is weak;
- detail hierarchy validator penalizes uniform procedural noise;
- motif validator catches forbidden motifs;
- functional readability validator consumes family metadata;
- style consistency validator catches contradictory motifs/materials.

### 12.4 Semantic Critique Tests

Required cases:

- converts low score into semantic repair suggestion;
- includes issue, severity, dimension, target, evidence, repair, and preserve fields;
- suggestions are deterministic;
- suggestions do not request random regeneration;
- suggestions are family-agnostic.

### 12.5 Certification Integration Tests

Required cases:

- certificate includes universal quality section;
- universal quality issues affect warning/strict status according to thresholds;
- render/bake/export strict blockers remain truthful;
- golden industrial crate warning validation still passes;
- proof fixtures validate in warning mode;
- production-game certification remains false unless supported by evidence.

---

## 13. Verification Commands

Run focused tests first:

```bash
python -m pytest -q \
  tests/unit/test_asset_quality_art_direction.py \
  tests/unit/test_asset_quality_quality_planner.py \
  tests/unit/test_asset_quality_universal_quality.py \
  tests/unit/test_asset_quality_semantic_critique.py
```

Then run related existing tests:

```bash
python -m pytest -q \
  tests/unit/test_asset_quality_certification.py \
  tests/unit/test_asset_quality_phase14_examples.py
```

Validate existing golden crate behavior:

```bash
python -m lathe.cli asset-quality validate-example examples/asset_quality/golden_industrial_crate --mode warning
```

Validate new proof fixtures if CLI supports it:

```bash
python -m lathe.cli asset-quality validate-example examples/asset_quality/quality_engine/fantasy_weapon --mode warning
python -m lathe.cli asset-quality validate-example examples/asset_quality/quality_engine/sci_fi_crate --mode warning
python -m lathe.cli asset-quality validate-example examples/asset_quality/quality_engine/roblox_tycoon_machine --mode warning
python -m lathe.cli asset-quality validate-example examples/asset_quality/quality_engine/environment_shop_counter --mode warning
```

Check formatting/diff hygiene:

```bash
git diff --check
```

If broad behavior changed:

```bash
python -m pytest -q
```

---

## 14. Acceptance Criteria

Phase 14C is complete when:

- `art_direction.py` or equivalent exists and models reusable art-direction data.
- `quality_planner.py` or equivalent can create quality plans for at least four different object families.
- Universal quality validators exist for the required quality dimensions.
- Semantic critique can convert validation failures into deterministic repair suggestions.
- Four multi-family proof fixtures exist under `examples/asset_quality/quality_engine/` or a documented equivalent path.
- Quality certificates can include universal quality scoring.
- Existing Phase 14 golden crate warning validation still passes.
- No production-game, real bake, external renderer, Roblox, Blender, or USD claims are made unless actually evidenced.
- Tests cover generalization and prevent sword-specific hardcoding.
- Docs explain the new Art Direction IR, Quality Planner, and Universal Quality Engine.

---

## 15. Failure Conditions

Phase 14C should be rejected if:

- it hardcodes a specific sword/reference image as the main logic;
- it improves only the fantasy weapon fixture and not the other proof families;
- it weakens existing certification truthfulness;
- it removes strict blockers without real evidence;
- it makes production-readiness claims based only on JSON presence;
- it adds public `.lth` syntax without updating all public language layers;
- it creates non-deterministic tests or fixtures;
- it treats decorative noise as equivalent to motif-driven detail;
- it has no semantic repair suggestions.

---

## 16. Implementation Plan

### Task 1 — Inventory Existing Asset-Quality APIs

Objective: Avoid duplicate architecture.

Files to inspect:

```text
lathe/asset_quality/
lathe/cli/asset_quality_cmd.py
tests/unit/test_asset_quality_certification.py
tests/unit/test_asset_quality_phase14_examples.py
examples/asset_quality/golden_industrial_crate/
```

Output:

- Identify existing dataclass/schema/helper patterns.
- Decide exact module names for Phase 14C.
- Do not modify files yet unless needed.

### Task 2 — Add Art Direction IR

Objective: Create reusable data model/helpers for art direction.

Suggested file:

```text
lathe/asset_quality/art_direction.py
```

Must support:

- loading JSON;
- applying deterministic defaults;
- validating required keys;
- exposing normalized dict output;
- no object-specific hardcoding.

Tests:

```text
tests/unit/test_asset_quality_art_direction.py
```

### Task 3 — Add Quality Planner

Objective: Convert art direction + family metadata into `quality_plan.json`.

Suggested file:

```text
lathe/asset_quality/quality_planner.py
```

Planner should produce:

- primary/secondary/tertiary reads;
- silhouette requirements;
- proportion requirements;
- material requirements;
- detail requirements;
- motif requirements;
- surface story requirements;
- certification targets;
- likely failure modes.

Tests:

```text
tests/unit/test_asset_quality_quality_planner.py
```

### Task 4 — Add Universal Quality Validators

Objective: Score general quality dimensions.

Suggested file:

```text
lathe/asset_quality/universal_quality.py
```

Must include deterministic scoring and diagnostics for:

```text
silhouette_strength
proportion_intent
material_contrast
detail_hierarchy
motif_coherence
surface_storytelling
functional_readability
style_consistency
procedural_noise_penalty
```

Tests:

```text
tests/unit/test_asset_quality_universal_quality.py
```

### Task 5 — Add Semantic Critique

Objective: Convert quality failures into repair suggestions.

Suggested file:

```text
lathe/asset_quality/semantic_critique.py
```

Must output:

- issue;
- severity;
- dimension;
- target;
- evidence;
- repair;
- preserve.

Tests:

```text
tests/unit/test_asset_quality_semantic_critique.py
```

### Task 6 — Add Proof Fixtures

Objective: Prove generalization across multiple object families.

Create:

```text
examples/asset_quality/quality_engine/fantasy_weapon/
examples/asset_quality/quality_engine/sci_fi_crate/
examples/asset_quality/quality_engine/roblox_tycoon_machine/
examples/asset_quality/quality_engine/environment_shop_counter/
```

Each fixture includes:

```text
design_brief.json
art_direction.json
quality_plan.json
family_metadata.json or family_grammar_coverage.json
material_wear_graph.json
preview_evidence.json
quality_certificate.json
semantic_critique.example.json
```

### Task 7 — Integrate Certification

Objective: Include universal quality scores in quality certificates.

Likely files:

```text
lathe/asset_quality/certification.py
examples/asset_quality/**/quality_certificate.json
```

Requirements:

- preserve existing score/gate behavior;
- add universal quality category details;
- do not remove strict blockers without evidence;
- keep existing golden crate warning behavior passing.

### Task 8 — Add Docs

Create:

```text
docs/asset-quality/art-direction-ir-v1.md
docs/asset-quality/quality-planner-v1.md
docs/asset-quality/universal-quality-engine.md
```

Docs must explain:

- why this is not a sword-specific system;
- data contracts;
- quality dimensions;
- fixture examples;
- certification integration;
- current limitations.

### Task 9 — Optional CLI Wiring

Objective: Expose planner/critique if project conventions make it clean.

Potential commands:

```bash
python -m lathe.cli asset-quality plan-quality <example> --out <path>
python -m lathe.cli asset-quality critique-quality <example> --out <path>
```

Do this only if it fits existing CLI patterns. Otherwise document as future work.

### Task 10 — Final Verification

Run:

```bash
python -m pytest -q \
  tests/unit/test_asset_quality_art_direction.py \
  tests/unit/test_asset_quality_quality_planner.py \
  tests/unit/test_asset_quality_universal_quality.py \
  tests/unit/test_asset_quality_semantic_critique.py \
  tests/unit/test_asset_quality_certification.py \
  tests/unit/test_asset_quality_phase14_examples.py

python -m lathe.cli asset-quality validate-example examples/asset_quality/golden_industrial_crate --mode warning

git diff --check
```

---

## 17. Ready-to-Paste Codex Prompt

```text
Implement Phase 14C only: Universal Art Direction Quality Engine.

Do not build a one-off sword generator. The goal is a reusable quality layer that can improve any asset family.

Read first:
- AGENTS.md
- CLAUDE_CODE_ASSET_QUALITY_MASTER_PROMPT.md
- docs/asset-quality/phase14c-universal-art-direction-quality-engine-spec.md
- docs/asset-quality/design-brief-ir.md
- docs/asset-quality/family-grammar-v1.md
- docs/asset-quality/semantic-construction-graph.md
- docs/asset-quality/material-wear-graph-v1.md
- docs/asset-quality/reference-board-v1.md
- docs/asset-quality/preview-evidence-v1.md
- docs/asset-quality/quality-upgrade-evidence.md

Context:
Lathe currently has asset-quality evidence, family grammar, construction graph, material/wear graph, preview evidence, and certification. Phase 14B is adding deterministic preview images. The next upgrade is to make quality planning general across object families.

Goal:
Add a reusable art-direction quality engine that converts an asset design brief + family grammar/style context into a quality plan used by construction, material/wear, preview critique, and certification.

Core principle:
The system should be able to target reference-level quality like a high-polish fantasy sword, but the architecture must generalize to crates, machines, furniture, environment props, and Roblox assets. Do not hardcode sword-specific logic.

Implement:
1. Art Direction IR
   - Add `lathe/asset_quality/art_direction.py` or equivalent.
   - Define helpers for style intent, visual hierarchy, silhouette goals, proportion policy, material contrast policy, motif language, surface storytelling, platform target, and forbidden visual failure modes.

2. Quality Planner
   - Add `lathe/asset_quality/quality_planner.py` or equivalent.
   - Input: design brief, family grammar/family metadata, optional reference board/style pack.
   - Output: `quality_plan.json`.
   - The plan must define primary/secondary/tertiary read, silhouette requirements, material separation requirements, detail density zones, motif placement rules, surface story rules, certification targets, and likely failure modes.

3. Universal quality validators
   - Add `lathe/asset_quality/universal_quality.py` or equivalent.
   - Add validators/scorers for silhouette_strength, proportion_intent, material_contrast, detail_hierarchy, motif_coherence, surface_storytelling, functional_readability, style_consistency, and procedural_noise_penalty.
   - These validators must be family-agnostic but may consume family grammar metadata.

4. Semantic critique shape
   - Add `lathe/asset_quality/semantic_critique.py` or equivalent.
   - Convert quality failures into semantic repair suggestions, not random regeneration.
   - Suggestions must include issue, severity, dimension, target, evidence, repair, and preserve fields.

5. Fixtures proving generalization
   Add fixtures under:
   - examples/asset_quality/quality_engine/fantasy_weapon/
   - examples/asset_quality/quality_engine/sci_fi_crate/
   - examples/asset_quality/quality_engine/roblox_tycoon_machine/
   - examples/asset_quality/quality_engine/environment_shop_counter/

   Each fixture must include:
   - design_brief.json
   - art_direction.json
   - quality_plan.json
   - family_metadata.json or family_grammar_coverage.json
   - material_wear_graph.json
   - preview_evidence.json
   - quality_certificate.json
   - semantic_critique.example.json

6. Docs
   Add:
   - docs/asset-quality/art-direction-ir-v1.md
   - docs/asset-quality/quality-planner-v1.md
   - docs/asset-quality/universal-quality-engine.md

7. Certification integration
   Update quality certification so it can include universal quality categories:
   - silhouette_strength
   - proportion_intent
   - material_contrast
   - detail_hierarchy
   - motif_coherence
   - surface_storytelling
   - functional_readability
   - style_consistency
   - procedural_noise_penalty

Behavior requirements:
- Do not hardcode the celestial sword/reference image.
- The fantasy weapon fixture is only one proof case.
- The same planner/validators must run for crate, tycoon machine, and shop counter.
- The system must produce actionable repair suggestions for failures.
- It must not claim production quality unless preview/render/bake/export evidence exists.
- Existing Phase 14 golden crate validation must continue to pass warning mode.
- Strict mode must remain truthful about missing bake/render/export lanes.

Tests:
Add/update tests for:
- art direction IR parsing/defaulting
- quality planner output for all four fixture families
- universal validators
- semantic critique repair suggestions
- certification category integration
- no sword-specific hardcoding
- existing golden crate warning validation remains passing

Suggested test commands:
python -m pytest -q tests/unit/test_asset_quality_art_direction.py tests/unit/test_asset_quality_quality_planner.py tests/unit/test_asset_quality_universal_quality.py tests/unit/test_asset_quality_semantic_critique.py tests/unit/test_asset_quality_certification.py tests/unit/test_asset_quality_phase14_examples.py
python -m lathe.cli asset-quality validate-example examples/asset_quality/golden_industrial_crate --mode warning
git diff --check

Final response must include:
- files changed
- fixtures added
- commands run
- how the quality engine generalizes beyond weapons
- any remaining limitations
- whether any production/render/bake claims are made

Stop after Phase 14C. Do not implement kit compiler, semantic patching execution, CI gates, or engine export in this phase.
```

---

## 18. Strategic Handoff

Phase 14C should move Lathe from:

```text
I can certify evidence for a specific generated asset.
```

toward:

```text
I can plan, score, critique, and repair visual quality across arbitrary asset families.
```

That is the difference between an asset pipeline and a real creative compiler.

The fantasy sword target is a useful north-star image, but the product breakthrough is not the sword.

The product breakthrough is this:

> Lathe learns the transferable structure of quality.

