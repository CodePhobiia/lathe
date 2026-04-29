# Lathe Asset Quality Upgrade Spec Sheet

> **For Hermes/Codex:** Use this as the product + technical spec for upgrading Lathe from certification-prototype asset generation to art-directed, production-quality 3D asset generation. Pair with `docs/asset-quality/improvement-tasklist.md` for execution.

**Status:** Draft v0.1  
**Date:** 2026-04-29  
**Repo:** `lathe_v0_1`  
**Primary evidence:** `lathe-hero-asset-certification-gate/evidence_20260429_111025`  
**Related roadmap:** `docs/asset-quality/lathe-next-level-asset-quality-roadmap.md`

---

## 1. Executive Summary

Lathe has reached a strong functional baseline: it can parse `.lth`, resolve asset intent, build asset graphs, create shape candidates, run topology/UV/surface stages, validate outputs, package GLBs/USD-style artifacts, and produce evidence bundles. The generated hero assets are a major improvement over the project's first day.

The next leap is **asset quality and control**.

Current outputs still often read as:

- procedural blockouts;
- fused primitive assemblies;
- debug-colored material previews;
- random triangulated meshes;
- objects with stuck-on details rather than integrated construction;
- assets with passing machine certification but only mid human visual quality.

This spec defines the upgrade path for turning Lathe into a **semantic CAD art director**: a compiler that turns high-level creative intent into controlled construction grammar, production hard-surface geometry, real high/low bake relationships, material/wear storytelling, and vision-scored iteration.

---

## 2. Problem Statement

### 2.1 Current capability

Lathe currently supports an end-to-end pipeline:

```text
.lth source
  -> parser / normalizer / resolver / checker
  -> asset graph
  -> assembly blueprint
  -> ShapeIR
  -> scaffold/fusion mesh
  -> topology cleanup
  -> UV
  -> surface maps
  -> validation/certification
  -> packaging and previews
```

This pipeline is valuable and should be preserved.

### 2.2 Current visual failure modes

Across inspected evidence for `service_cabinet`, `industrial_crate`, and `mechanical_door`, recurring gaps appear:

1. **Uncontrolled triangulation**
   - Large flat surfaces are split by arbitrary diagonals.
   - Facets look accidental, not designed.
   - Some industrial assets read like crystal/folded-paper geometry.

2. **Weak primary/secondary/tertiary hierarchy**
   - Primary body is present.
   - Secondary construction — frames, guards, rails, panels, sockets, trim — is underdeveloped.
   - Tertiary details — bolts, scratches, decals, wear — are sparse or generic.

3. **Primitive silhouette**
   - Many objects read as a box/slab with attachments.
   - Internal surface marks add visual noise but do not improve outer profile.

4. **Poor attachment integration**
   - Handles, hinges, plates, cylinders, and rails often look placed onto the object, not seated into brackets, sockets, welds, frame cuts, or mount geometry.

5. **Material flatness**
   - Material zones and maps exist, but final previews can read like debug/material-ID colors.
   - Wear, grime, scratches, chipped edges, contact dirt, and roughness storytelling are not convincing enough.

6. **No strong family grammar**
   - A crate should have crate construction logic.
   - A mechanical door should have door construction logic.
   - A cabinet should have cabinet construction logic.
   - Current family inference and assembly heuristics are useful, but not sufficient for hero-quality hard-surface design.

7. **Certification can pass assets that still look visually prototype-level**
   - Existing metrics validate contracts, completeness, and some surface evidence.
   - They do not yet strongly detect blockout look, random topology, fake high/low distinction, material debug look, weak silhouette, or poor design-language coherence.

---

## 3. Product Goal

Build Lathe into a system that can generate **game-ready, art-directed 3D assets** from `.lth` with substantially more control over geometry, surfaces, detail hierarchy, style, and production-readiness.

### Target user experience

A creator should be able to write or generate `.lth` that says not only:

```lathe
asset industrial_crate: hard_surface_prop { ... }
```

but also meaningfully control:

```lathe
construction {
  grammar = hard_surface_crate_v1
  primary_form = crate_squat_box(width: 92cm, height: 58cm, depth: 64cm)
  silhouette.landmarks = [top_lip, side_grips, bottom_feet, front_latch]
  detail_hierarchy = [primary, secondary, tertiary]
  required_features = [corner_guards, lid_seam, latch_plate, recessed_handles, foot_rails]
}

art_direction {
  silhouette = bold
  bevel_language = chunky_industrial
  detail_density = hero
  material_age = used_not_destroyed
  wear = medium_edge_wear
  greeble_style = functional_only
}

material_graph painted_steel_body {
  base = painted_metal(color: #4f5668, roughness: 0.62)
  underlayer = dark_bare_metal
  wear {
    convex_edges = chipped_paint(amount: 0.28)
    lower_edges = scuff(amount: 0.35)
    recesses = grime(amount: 0.22)
    handles = touch_wear(amount: 0.18)
  }
}
```

Lathe should then compile that into a controlled asset with readable construction, believable material zones, high/low bake detail, and preview evidence.

---

## 4. Non-Goals

This upgrade must not:

- break existing `.lth` source compatibility without an explicit migration gate;
- replace the current pipeline wholesale;
- fake external runtime evidence such as Blender, Roblox, or external-viewer validation;
- remove existing certification/report fields consumed by current tools;
- weaken current shape-stage handoff stability;
- turn vision models into uncontrolled mesh editors;
- require paid/external services for deterministic local tests;
- overfit only to one evidence run.

---

## 5. Core Design Principle

The project needs to shift from:

```text
intent -> mesh
```

to:

```text
intent -> art direction -> family grammar -> semantic construction graph -> high/low geometry -> material/wear graph -> validation -> iteration
```

The important conceptual change:

> Lathe assets should be authored as meaningful construction decisions, not just generated as fused primitives.

---

## 6. Architecture Overview

### 6.1 Current architecture to preserve

```text
.lth source
  -> parser / normalizer / resolver / checker
  -> build_plan
  -> BuildExecutor
  -> shape stage
  -> topology stage
  -> UV stage
  -> surface stage
  -> validate stage
  -> package stage
```

Preserve:

- `lathe.shape.intent_mesh_handoff_v1` compatibility;
- current examples/build flow;
- current deterministic build paths;
- current evidence and package outputs;
- existing report consumers.

### 6.2 New conceptual layers

Add new layers incrementally:

```text
Design Brief IR
Family Grammar IR
Semantic Construction Graph
ShapeIR v2 Semantic Ops
High/Low Mesh Relation
Material/Wear Graph
Design-Language Validator
Vision Critique Patch Loop
Reference/Moodboard Ingestion
Standard Kit Library
```

Each layer should degrade gracefully: if the new layer is absent, legacy assets should still build.

---

## 7. Specification: Design Brief IR

### 7.1 Purpose

Capture the artistic and production intent before geometry generation.

### 7.2 Inputs

Sources:

- existing `intent` block;
- new/normalized `art_direction` block;
- references/moodboard metadata;
- family defaults;
- build/validation thresholds.

### 7.3 Fields

Proposed normalized shape:

```json
{
  "asset_name": "industrial_crate",
  "family": "industrial_crate",
  "role": "reinforced industrial cargo crate",
  "style": ["utility", "industrial", "shipping"],
  "camera_distance": "gameplay_mid",
  "silhouette": "bold",
  "shape_language": "rectangular_with_45deg_cuts",
  "bevel_language": "chunky_industrial",
  "detail_density": "hero",
  "wear": "medium_edge_wear",
  "material_age": "used_not_destroyed",
  "greeble_style": "functional_only",
  "negative_constraints": ["toy_like", "random_faceting", "ornate"]
}
```

### 7.4 Acceptance criteria

- Existing assets get a deterministic default design brief.
- The brief is included in shape-stage or validation reports.
- The brief drives thresholds or grammar selection without changing existing `.lth` syntax initially.

---

## 8. Specification: Family Grammar IR

### 8.1 Purpose

Encode what a crate, door, cabinet, terminal, chest, drone, etc. must contain and how parts should relate.

### 8.2 MVP family

Start with `industrial_crate`.

Reasons:

- easy to judge visually;
- strong hard-surface grammar;
- common game asset;
- current output exposes the exact weakness;
- grammar rules are concrete.

### 8.3 Industrial crate grammar

Required construction zones:

- body shell;
- lid seam;
- corner guards;
- latch plate;
- recessed handles or bracketed handles;
- foot rails or feet;
- trim bands;
- fastener strips;
- warning/label decal zones;
- edge wear masks.

Rules:

- body shell must be the dominant primary form;
- lid seam must wrap coherently around top third or top face;
- corner guards must attach to body edges and affect silhouette;
- handles must be recessed into body or seated in brackets;
- feet must contact the bottom plane and be paired/symmetrical unless intentionally asymmetric;
- latch must be centered or explicitly offset by design brief;
- warning decals must be placed on visible semantic panels;
- detail density must be distributed across primary/secondary/tertiary layers.

### 8.4 Mechanical door grammar

Required zones:

- outer frame;
- inner door leaf;
- hinge side;
- lock/handle side;
- threshold plate;
- status light or control plate;
- seal/rubber strip;
- warning decal zone.

Rules:

- door leaf must be visually separable from frame;
- hinges must have barrels plus mounting plates;
- lock/handle must be seated into a plate or recess;
- threshold must sit at the bottom and read as a structural element;
- frame bevel and leaf bevel must be consistent.

### 8.5 Service cabinet grammar

Required zones:

- cabinet body shell;
- front door panel;
- handle/lock zone;
- side/top structural lips;
- hinge or seam indicators;
- vent or service panel detail;
- base contact or wall-mount logic.

### 8.6 Acceptance criteria

- Family grammar coverage is measurable.
- Grammar failures are human-readable.
- `industrial_crate` can be validated against grammar without requiring external services.
- Legacy assets can default to generic grammar without failing immediately.

---

## 9. Specification: Semantic Construction Graph

### 9.1 Purpose

Bridge family grammar and ShapeIR by representing construction decisions as named graph nodes and relationships.

### 9.2 Node types

- `primary_volume`
- `frame`
- `panel`
- `inset`
- `trim`
- `guard`
- `rail`
- `socket`
- `mount`
- `handle`
- `hinge`
- `fastener`
- `decal_zone`
- `wear_zone`
- `material_zone`

### 9.3 Edge types

- `attached_to`
- `inset_into`
- `wraps_around`
- `mirrors`
- `aligned_with`
- `supports`
- `cuts`
- `contains`
- `wears_on`
- `material_bound_to`

### 9.4 Example

```json
{
  "nodes": [
    {"id": "body_shell", "type": "primary_volume", "part": "body"},
    {"id": "lid_seam", "type": "trim", "part": "lid_break"},
    {"id": "front_latch_plate", "type": "panel", "part": "latch_plate"},
    {"id": "left_handle_socket", "type": "socket", "part": "handle_l"}
  ],
  "edges": [
    {"from": "lid_seam", "to": "body_shell", "type": "wraps_around"},
    {"from": "front_latch_plate", "to": "body_shell", "type": "attached_to"},
    {"from": "left_handle_socket", "to": "body_shell", "type": "inset_into"}
  ]
}
```

### 9.5 Acceptance criteria

- Graph can be emitted in shape bundle metadata.
- Graph can be validated independently of mesh generation.
- Graph can lower to ShapeIR v1/v2 operations.

---

## 10. Specification: ShapeIR v2 Semantic Operations

### 10.1 Purpose

Move beyond boxes/cylinders into production hard-surface operations.

### 10.2 Compatibility rule

Do not break `lathe.shape.intent_mesh_handoff_v1`.

Instead:

- introduce ShapeIR v2 internally;
- write compatibility adapters;
- preserve v1 bundle fields;
- add v2 fields under additive keys.

### 10.3 Operation families

#### Solids

- `solid.box`
- `solid.rounded_box`
- `solid.cylinder`
- `solid.prism`
- `solid.rail`
- `solid.panel`

#### Boolean and construction

- `op.union`
- `op.subtract`
- `op.intersect`
- `op.inset`
- `op.extrude`
- `op.shell`
- `op.cut_panel_line`

#### Edge control

- `op.bevel`
- `op.chamfer`
- `op.weighted_normals`
- `op.mark_hard_edge`

#### Repetition/detail

- `op.repeat`
- `op.fastener_grid`
- `op.vent_slats`
- `op.trim_band`
- `op.corner_guard_set`

#### Integration

- `op.socket`
- `op.bracket`
- `op.mount_plate`
- `op.weld_seam`

#### Wear/damage construction

- `op.chip_edges`
- `op.scratch_mask`
- `op.dent_mask`
- `op.grime_mask`

### 10.4 Example v2 operation payload

```json
{
  "op": "op.bevel",
  "target": "body_shell.outer_edges",
  "width_cm": 1.2,
  "segments": 3,
  "profile": "chunky_industrial",
  "purpose": "catch_light_and_support_hard_surface_readability"
}
```

### 10.5 Acceptance criteria

- ShapeIR v2 can represent crate MVP grammar.
- ShapeIR v2 can be serialized deterministically.
- ShapeIR v2 can be lowered to current scaffold primitives where possible.
- Unsupported v2 ops fail with actionable diagnostics, not silent degradation.

---

## 11. Specification: High-Poly / Low-Poly Relation

### 11.1 Purpose

Make production game-asset workflow real in Lathe.

### 11.2 Required outputs

For hero assets:

```text
stages/shape/high_poly.glb
stages/shape/low_proxy.glb
stages/topology/runtime_low.glb
stages/surface/maps/normal.png
stages/surface/maps/ao.png
stages/surface/maps/curvature.png
stages/surface/maps/id.png
```

### 11.3 High-poly responsibilities

- bevel detail;
- panel line depth;
- embossed/debossed surface features;
- bolts/fasteners;
- trims and rails;
- damage chips and dents;
- welds or seams;
- high-frequency shape detail that should bake to normal/AO/curvature.

### 11.4 Low-poly responsibilities

- runtime silhouette;
- material IDs;
- part boundaries;
- important hard edges;
- collision and LOD compatibility;
- bake cage correctness.

### 11.5 Validator changes

Certification should fail or warn when:

- high and low triangle counts are nearly identical for a hero asset;
- normal/curvature/AO maps do not reflect high-poly detail;
- high-poly detail does not map to material/part zones;
- low-poly loses silhouette landmarks.

---

## 12. Specification: Material/Wear Graph

### 12.1 Purpose

Create material storytelling, not just color variation.

### 12.2 Required mask concepts

- convex edge wear;
- concave grime;
- lower/contact scuff;
- handle/touch wear;
- hinge grease/darkening;
- exposed underlayer;
- decal wear;
- directional scratches;
- dust on horizontal surfaces.

### 12.3 Material graph example

```json
{
  "material": "painted_steel_body",
  "base": {
    "type": "painted_metal",
    "color": "#4f5668",
    "roughness": 0.62,
    "metalness": 0.0
  },
  "underlayer": "dark_bare_metal",
  "wear": {
    "convex_edges": {"type": "chipped_paint", "amount": 0.28},
    "lower_edges": {"type": "scuff", "amount": 0.35},
    "recesses": {"type": "grime", "amount": 0.22},
    "interaction_zones": {"type": "touch_wear", "amount": 0.18}
  }
}
```

### 12.4 Acceptance criteria

- Surface bundle includes material/wear graph metadata.
- Generated maps visibly reflect convex/concave/contact/interaction masks.
- Wear placement is semantic, not uniform noise.
- Existing hero surface maps still generate deterministically.

---

## 13. Specification: Design-Language Validator

### 13.1 Purpose

Detect when an asset passes technical contracts but still looks like a prototype.

### 13.2 New metrics

Add deterministic metrics first:

- `random_triangulation_penalty`
- `debug_material_preview_penalty`
- `highlow_fake_detail_penalty`
- `attachment_seating_quality`
- `primary_secondary_tertiary_balance`
- `family_grammar_coverage`
- `silhouette_iconicity`
- `panel_line_intentionality`
- `bevel_highlight_quality`
- `material_storytelling_quality`
- `wear_plausibility`
- `scale_cue_quality`
- `stuck_on_greeble_penalty`

### 13.3 Human-readable diagnostics

Examples:

- `large flat face is split by noisy diagonal topology`
- `surface appears material-ID/debug colored rather than authored PBR`
- `hero asset lacks meaningful high-poly/low-poly distinction`
- `attachments appear under-integrated relative to body scale`
- `family grammar missing required crate corner guards`
- `handles are present but not seated in sockets or brackets`
- `wear is uniform noise rather than edge/contact/story-driven`

### 13.4 Acceptance criteria

- Diagnostics appear in certification report.
- Existing JSON consumers do not break.
- At least one deliberately poor fixture fails/warns despite satisfying old technical completeness.

---

## 14. Specification: Vision Critique Loop

### 14.1 Purpose

Use rendered previews as an art director feedback source.

### 14.2 Rule

Vision should propose **semantic patches**, not direct mesh mutation.

### 14.3 Loop

```text
build candidates
  -> render fixed view sheet
  -> deterministic metrics
  -> optional vision critique
  -> structured semantic patch proposal
  -> apply patch to design brief / grammar / ShapeIR v2
  -> rebuild
  -> compare before/after
```

### 14.4 Structured critique format

```json
{
  "asset": "industrial_crate",
  "observations": [
    {
      "issue": "attachments_under_integrated",
      "severity": "high",
      "evidence_view": "front_iso",
      "recommendation": "add recessed sockets and bracket plates for side handles"
    }
  ],
  "patches": [
    {
      "action": "add_socket",
      "target": "handle_l",
      "parameters": {"mount_type": "recessed_bracket", "clearance_cm": 1.5}
    }
  ]
}
```

### 14.5 Acceptance criteria

- Loop stores iteration history.
- Before/after reports include image paths, metrics, and patch rationale.
- Vision absence does not block deterministic local builds.

---

## 15. Specification: Reference/Moodboard Ingestion

### 15.1 Purpose

Ground generation in references, negative examples, and material targets.

### 15.2 Proposed `.lth` concept

```lathe
references {
  mood = refs/crate_moodboard.json
  silhouette = refs/crate_silhouette_front.png
  material = refs/painted_steel_worn_edges.png
  negative = refs/toy_like_crate.png
}
```

### 15.3 Acceptance criteria

- Reference metadata is recorded in conditioning reports.
- Missing references produce actionable warnings.
- Local deterministic tests can use small minimal reference fixtures.

---

## 16. Specification: Standard Kit Library

### 16.1 Purpose

Use curated reusable hard-surface parts to raise quality quickly.

### 16.2 Proposed library

```text
std.kit.hardsurface.v1
  fasteners/
  hinges/
  brackets/
  vents/
  handles/
  rails/
  corner_guards/
  cable_ports/
  status_lights/
  labels/
  warning_decals/
```

### 16.3 Kit part metadata

Each kit part should define:

- mesh or procedural recipe;
- material zones;
- sockets;
- placement constraints;
- scale range;
- allowed families;
- LOD behavior;
- bake group;
- preview thumbnail;
- license/provenance.

### 16.4 Acceptance criteria

- Industrial crate MVP can use at least fasteners, corner guards, handles, warning labels.
- Kit usage is deterministic and traceable.
- Kit failures degrade with diagnostics.

---

## 17. Public Language Strategy

### Phase 1: No syntax change

Implement diagnostics, normalized internal IR, and report additions without changing `.lth` grammar.

### Phase 2: Experimental syntax

Introduce syntax behind an experimental flag/profile:

```lathe
experimental construction_grammar_v1
experimental material_graph_v1
```

### Phase 3: Stabilize

Only after examples/tests/docs prove value:

- update `spec/lathe-v0.1.md` or next version spec;
- update grammar/schema/parser/checker;
- update examples and docs;
- add migration notes.

---

## 18. Validation Strategy

### 18.1 Unit tests

Add tests for:

- design brief defaults;
- grammar coverage checks;
- ShapeIR v2 serialization;
- v2-to-v1 adapter;
- material/wear graph normalization;
- visual-quality diagnostics.

### 18.2 Integration tests

Add tests for:

- `industrial_crate` grammar MVP;
- existing examples still building;
- certification report additive compatibility;
- high/low output presence when hero mode is enabled.

### 18.3 Golden evidence tests

Use fixed examples and assert:

- report fields exist;
- diagnostics are stable;
- poor fixtures trigger expected warnings;
- good fixtures pass expected gates.

### 18.4 Commands

Use repo-standard commands from `AGENTS.md`:

```bash
python -m lathe.cli check examples/industrial_crate.lth
python -m lathe.cli build examples/industrial_crate.lth industrial_crate --out .tmp_tests/asset_quality_crate --deterministic
python -m pytest -q tests/unit/test_visual_quality.py
python -m pytest -q tests/unit/test_shape_ir_v2.py
python -m pytest -q tests/integration/test_industrial_crate_grammar.py
```

---

## 19. Acceptance Criteria for the Full Upgrade

The upgrade is successful when:

1. **Deterministic diagnosis catches current prototype look**
   - random triangulation/debug material/fake high-low issues are visible in reports.

2. **Industrial crate has a real family grammar**
   - body, lid seam, corner guards, handles, feet, latch, trims, fasteners, and decal zones are represented.

3. **ShapeIR v2 can represent semantic construction**
   - at least crate MVP operations serialize and lower into current pipeline.

4. **High/low relation is meaningful**
   - hero high-poly has detail not present in runtime low-poly;
   - baked maps reflect the detail.

5. **Material/wear graph is semantic**
   - edge chips, grime, scuffs, and interaction wear appear through masks.

6. **Vision critique loop can propose patches**
   - optional vision path writes structured critique and semantic patch proposals.

7. **Existing assets still build**
   - no public source compatibility regression.

8. **Docs and examples teach the new controls**
   - creators can understand how to control asset quality.

---

## 20. Risk Register

| Risk | Impact | Mitigation |
|---|---:|---|
| ShapeIR v2 breaks stable handoff | High | Keep additive v2 fields and v1 adapter |
| Grammar overfits `industrial_crate` | Medium | Define generic graph concepts and tests for door/cabinet later |
| Validator becomes subjective/flaky | High | Start deterministic; vision optional and non-blocking |
| Surface wear becomes noisy texture spam | Medium | Use semantic masks and material-specific recipes |
| Scope explosion | High | Follow tasklist phases; crate MVP first |
| External tools unavailable | Medium | Keep deterministic fallback and explicit skipped evidence |

---

## 21. Recommended Execution Order

1. Add deterministic visual-quality diagnosis layer.
2. Add design brief defaults and report fields.
3. Add family grammar IR with industrial crate MVP.
4. Add construction graph emission and validation.
5. Draft and implement ShapeIR v2 additive model + adapter.
6. Add crate grammar lowering to semantic ops.
7. Add real high/low distinction outputs.
8. Add material/wear graph and masks.
9. Add optional vision critique loop.
10. Add references and kit library.
11. Stabilize syntax/docs/examples.

---

## 22. Definition of Done

For any phase/task:

- tests added or updated;
- docs updated if public behavior changes;
- report/evidence output verified;
- no secrets/absolute user paths committed into docs or fixtures;
- existing examples still check/build where relevant;
- external runtime gates are truthful, skipped if unavailable, never faked.
