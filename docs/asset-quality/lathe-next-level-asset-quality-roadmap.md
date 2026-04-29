# Lathe Next-Level Asset Quality Roadmap

Date: 2026-04-29

## Source evidence inspected

Evidence folder:

```text
automation evidence bundle: lathe-hero-asset-certification-gate/evidence_20260429_111025
```

WSL path:

```text
automation evidence bundle: lathe-hero-asset-certification-gate/evidence_20260429_111025
```

Representative previews inspected:

- `service_cabinet/stages/package/previews/turntable.png`
- `industrial_crate/stages/package/previews/turntable.png`
- `mechanical_door/stages/package/previews/turntable.png`

Repo areas inspected:

- `examples/industrial_crate.lth`
- `examples/mechanical_door.lth`
- `lathe/asset_graph.py`
- `lathe/core/stages/shape.py`
- `lathe/scaffold_compiler.py`
- `lathe/assembly_kernel.py`
- `lathe/shape_ir.py`
- `lathe/surface_runtime.py`
- `lathe/validators/visual_quality.py`
- `hero_certification_audit.json`

## Current quality read

Lathe is much better than Day 1. The generated assets now have:

- coherent asset families and names;
- part lists and semantic assembly intent;
- multi-stage build evidence;
- material zones and PBR map output;
- candidate selection;
- validation/certification reports;
- preview renders, GLBs, package manifests, LOD/collision output;
- beginnings of hero-surface authoring.

However, the previews still look closer to **procedural blockouts / certification prototypes** than high-quality production assets.

The core reason is not one bug. It is architectural: Lathe currently has enough language to describe *what* an object should be, but not enough expressive control over *how its forms are artistically constructed*.

## Repeated visual gaps

Across the inspected assets:

1. **Uncontrolled triangulation / faceting**
   - Large flat surfaces are visibly broken by arbitrary triangles.
   - Diagonal topology reads as accidental rather than designed.
   - Some surfaces look folded or crystal-like even when the asset is meant to be industrial hard-surface.

2. **Weak primary/secondary/tertiary hierarchy**
   - The asset often has one big primitive body plus small attachments.
   - Medium-scale construction features are underdeveloped: frames, rails, panels, hinges, handles, sockets, bevel systems, trim bands.
   - Tiny details compete with random topology instead of supporting the design.

3. **Silhouette still too primitive**
   - Many props read as “box/slab with attachments.”
   - Surface lines add complexity but do not meaningfully improve the outer profile.
   - Production quality requires silhouette-first control.

4. **Attachments are not integrated enough**
   - Handles, cylinders, plates, hinges, rails, and panels often feel stuck onto the base rather than seated into sockets, brackets, welds, fasteners, frame cuts, or local support geometry.

5. **Materials are still mostly procedural map evidence, not material art direction**
   - Material zones exist, but preview surfaces read as flat/debug-colored.
   - Wear, roughness variation, decals, grime, edge chips, contact dirt, scratches, and stamped details are under-authored.

6. **Design language is not enforced**
   - Assets mix boxy hard-surface, random triangulation, circular lathe cylinders, and colored slivers without a strong unifying motif.
   - A crate should have crate grammar; a door should have door grammar; a cabinet should have cabinet grammar.

7. **Validator scores can certify assets that still look visually mid**
   - Example metric pattern from `hero_certification_audit.json`:
     - many assets are certified around `0.82–0.88`;
     - `highlow_distinction_quality` is often only `0.45` or even `0.0`;
     - `geometry_tiny_face_penalty` is high on some assets (`0.34–0.41`);
     - `surface_authoring_quality` often hovers around `0.74–0.80`;
     - screenshots still show flat colors and visible topology noise.
   - This means the validator is catching contract completeness more than human-perceived art quality.

## Research-grounded principles to import

Production game asset workflows converge on these principles:

1. **Planning/reference before modeling**
   - Understand how the prop is made, used, assembled, worn, and scaled.

2. **Blockout first**
   - Primary forms, silhouette, proportions, and camera readability are solved before details.

3. **High-poly / low-poly split**
   - High poly carries bevels, panel gaps, chips, dents, welds, screws, trims, and damage.
   - Low poly is optimized and receives baked normal/AO/curvature/material detail.

4. **Every edge has a purpose**
   - Edge supports a bevel, crease, panel line, silhouette, deformation, or material border.
   - Random topology hurts shading and readability.

5. **Bevels are non-negotiable**
   - Hard-surface assets need controlled bevel widths so edges catch light.

6. **Trim sheets, decals, masks, and material IDs are major quality multipliers**
   - Not every detail should be geometry.
   - Use authored trims/decals for panel seams, warning stripes, labels, bolts, scratches, vents, and stamped features.

7. **Shape grammar and procedural grammars are powerful, but only if rules are art-directed**
   - Grammar should encode “crate construction,” “door construction,” “cabinet construction,” etc., not generic primitive assembly.

## Architectural diagnosis

Current Lathe stack has a strong pipeline:

```text
.lth intent -> asset graph -> assembly blueprint -> ShapeIR -> scaffold/fusion -> topology -> UV -> surface -> validate -> package
```

But the decisive weakness is that `ShapeIR` and assembly lowering are still too primitive for hero-quality hard-surface assets.

Current `ShapePrimitive` supports basically:

- box;
- cylinder;
- center/extents/radius/height/axis;
- tags;
- blend mode;
- rounding scalar.

That is not enough to express production hard-surface control such as:

- explicit bevel chains;
- panel insets;
- grooves/channels;
- trim rails;
- sockets/mounts;
- repeated fasteners;
- corner guards;
- hinge brackets;
- boolean cutters with named design role;
- high-poly detail sources;
- low-poly bake targets;
- silhouette landmarks;
- style grammar constraints;
- material/wear masks bound to geometry semantics.

The `.lth` examples already ask for these things in human terms, but the compiler cannot yet translate them into enough controlled geometry.

## Novel direction: Lathe should become a “semantic CAD art director,” not just an asset generator

The winning architecture is a layered representation:

```text
Intent
  -> Design Brief / Reference Board
  -> Family Shape Grammar
  -> Semantic CAD Graph
  -> High-poly Detail Graph
  -> Low-poly Runtime Mesh
  -> Material/Wear Graph
  -> Vision-scored Iteration Loop
```

The key idea: Lathe assets should not be generated as one mesh. They should be authored as **meaningful construction decisions**.

Example:

Instead of:

```text
make industrial_crate with body, latch_plate, handles
```

Lathe should lower to something like:

```text
crate_body_shell
  silhouette: squat_rectangular_volume
  bevel_system: crate_hero_bevels
  construction:
    - reinforced_corner_guards
    - inset_lid_panel
    - stackable_top_ribs
    - lower_foot_rails
    - side_grip_recesses
  seams:
    - lid_break around top third
    - latch_cut on front center
  detail grammar:
    - fasteners along trim rails every 12cm
    - warning stripe band across latch side
  wear grammar:
    - chipped paint on convex edges
    - grime in panel seams
    - scuffed lower feet
```

That representation gives the compiler actual levers.

## Implementation tracks

### Track 1 — Asset Quality DSL v1: construction grammar blocks

Add language-level or normalized IR support for explicit construction grammar.

Proposed concepts:

```lathe
construction {
  primary_form = crate_squat_box(width: 92cm, height: 58cm, depth: 64cm)
  silhouette {
    landmarks = [top_lip, side_grips, bottom_feet, front_latch]
    breakups = [corner_guards, lid_step, recessed_front_panel]
  }
  grammar = hard_surface_crate_v1
  detail_hierarchy = [primary, secondary, tertiary]
}
```

For doors:

```lathe
construction {
  grammar = mechanical_airlock_door_v1
  frame = heavy_outer_frame(thickness: 12cm, bevel: 1.2cm)
  leaf = inset_panel(depth: 4cm, panel_count: 2)
  mechanisms = [hinge_stack(left, count: 3), lock_module(right), status_light]
}
```

Why this matters:

- The generator stops guessing what “door” means.
- Art direction becomes controllable in `.lth`.
- Validators can check actual grammar coverage.

### Track 2 — ShapeIR v2: from primitives to semantic operations

Extend ShapeIR with richer operation types while preserving `lathe.shape.intent_mesh_handoff_v1` compatibility through adapters.

New operation classes:

- `solid.box`, `solid.cylinder`, `solid.rounded_box`
- `op.union`, `op.subtract`, `op.intersect`
- `op.bevel(edge_set, width, segments, profile)`
- `op.inset(face_set, margin, depth)`
- `op.panel_line(path, width, depth)`
- `op.trim_band(path/region, width, height)`
- `op.repeat(feature, along_edge/around_face, count/spacing)`
- `op.socket(part, mount_type, clearance)`
- `op.fastener_grid(region, spacing, style)`
- `op.damage(mask, chip_depth, scratch_density)`

This is the biggest unlock for control.

### Track 3 — Family grammars: crate/door/cabinet/terminal/pedestal/supply/drone/chest

Move from generic assembly heuristics to explicit family grammars.

Each family should define:

- required construction zones;
- optional variants;
- silhouette landmarks;
- medium-form rules;
- tertiary detail rules;
- material zones;
- attachment integration rules;
- wear mask rules;
- validation metrics.

Example crate grammar rules:

- body shell must have corner guards;
- lid seam must wrap around body;
- latch must be centered or intentionally offset;
- handles must be recessed or bracketed;
- feet must touch bottom plane and be paired;
- warning decals belong on exposed panels, not random faces.

Example door grammar rules:

- outer frame, inner leaf, hinge side, lock side, threshold;
- handles and hinges must have sockets/brackets;
- door leaf must be visibly separable from frame;
- status light / lock plate / warning signage occupy semantic zones.

### Track 4 — High-poly/low-poly dual generation

Make high/low distinction real, not just a metric.

Pipeline should produce:

```text
shape/high_poly.glb
shape/low_proxy.glb
topology/runtime_low.glb
surface/bakes/normal.png
surface/bakes/ao.png
surface/bakes/curvature.png
surface/bakes/id.png
```

High poly should contain:

- bevels;
- panel gaps;
- embossed/debossed details;
- bolts;
- trims;
- damage chips;
- welds/scratches where appropriate.

Low poly should preserve:

- silhouette;
- hard edges;
- material IDs;
- panel boundary loops;
- bake cage correctness.

A validator should fail hero assets when high/low distinction is fake.

### Track 5 — Surface Material Graph v1

Current hero surface is useful, but still too procedural/noisy. Add semantic material programs.

New concepts:

```lathe
material_graph painted_steel_body {
  base = painted_metal(color: #4f5668, roughness: 0.62, metalness: 0.0)
  underlayer = dark_bare_metal
  wear {
    convex_edges = chipped_paint(amount: 0.28)
    lower_edges = scuff(amount: 0.35)
    recesses = grime(amount: 0.22)
    handles = touch_wear(amount: 0.18)
  }
}
```

Surface must understand:

- convex edge masks;
- concave grime masks;
- contact dirt masks;
- interaction wear masks;
- material-specific roughness/noise;
- decal placement constraints;
- trim sheets.

### Track 6 — Design-language validator, not only geometry validator

Add a validator that evaluates “does this look like an intentional object?”

New metrics:

- `primary_secondary_tertiary_balance`
- `silhouette_iconicity`
- `family_grammar_coverage`
- `attachment_seating_quality`
- `panel_line_intentionality`
- `bevel_highlight_quality`
- `material_storytelling_quality`
- `wear_plausibility`
- `scale_cue_quality`
- `random_triangulation_penalty`
- `debug_color_penalty`
- `stuck_on_greeble_penalty`

This should be vision-assisted if available, but deterministic proxy metrics can start it.

### Track 7 — Vision-in-the-loop art director

Use rendered preview scoring as a first-class feedback loop.

Process:

1. Generate 3–8 candidates.
2. Render fixed views: front, side, iso, hero, detail crops, material ID, wireframe.
3. Run deterministic metrics and optional vision critique.
4. Convert critique into patch operations:
   - strengthen silhouette;
   - integrate attachments;
   - widen bevels;
   - add medium forms;
   - reduce random triangulation;
   - add wear masks;
   - improve material zones.
5. Rebuild and compare.

Important: vision should not blindly edit mesh. It should propose semantic grammar patches.

### Track 8 — Reference/moodboard ingestion

Assets need reference grounding.

Add `.lth` support for reference boards:

```lathe
references {
  mood = refs/crate_moodboard.json
  silhouette = refs/crate_silhouette_front.png
  material = refs/painted_steel_worn_edges.png
  negative = refs/toy_like_crate.png
}
```

Reference board should feed:

- silhouette targets;
- material palette;
- detail motifs;
- scale cues;
- negative constraints.

### Track 9 — Kitbash/part-library integration

High-quality hard-surface generation benefits massively from reusable authored parts.

Create a Lathe standard kit library:

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

Each kit part should include:

- mesh/shape recipe;
- material zones;
- sockets;
- placement constraints;
- scale range;
- allowed families;
- LOD behavior;
- bake group.

This gives Lathe production-level detail without needing to invent everything from primitives.

### Track 10 — Author controls for intentionality

Expose controls artists/LLMs can actually steer:

```lathe
art_direction {
  silhouette = bold
  bevel_language = chunky_industrial
  shape_language = rectangular_with_45deg_cuts
  detail_density = hero
  asymmetry = low
  wear = medium_edge_wear
  material_age = used_not_destroyed
  scale_cues = human_handled
  greeble_style = functional_only
}
```

These controls should compile into concrete grammar and validator thresholds.

## Recommended next implementation order

### Phase A — Quick quality wins

1. Add `random_triangulation_penalty` / `wireframe_noise_penalty` to visual validation.
2. Add an explicit `debug_color_penalty` for flat material-ID-looking final renders.
3. Tighten `highlow_distinction_quality` thresholds for hero families.
4. Add validator diagnostics that name visual failure modes in human terms.
5. Improve preview modes so final previews do not look like topology/debug renders unless explicitly requested.

### Phase B — ShapeIR v2 design doc + compatibility adapter

1. Draft `docs/architecture/shape-ir-v2.md`.
2. Define semantic operations and JSON schema.
3. Add adapter to lower ShapeIR v2 into existing v1 handoff for backwards compatibility.
4. Add tests proving old assets still build.

### Phase C — Family grammar MVP

Implement one family deeply before broad rollout.

Best first target: `industrial_crate`.

Why:

- easy to judge visually;
- strong hard-surface grammar;
- clear primary/secondary/tertiary hierarchy;
- good for Roblox/game asset needs;
- current output already shows the key weaknesses.

Crate MVP grammar:

- body shell;
- lid seam;
- corner guards;
- latch plate;
- recessed handles;
- foot rails;
- trim bands;
- fasteners;
- warning decal zones;
- edge wear masks.

### Phase D — Real high-poly/low-poly bake relation

1. Generate separate high and low meshes.
2. Bake high detail to low maps.
3. Require high/low distinction for hero certification.
4. Add visual evidence side-by-side in package previews.

### Phase E — Material/wear graph

1. Implement convex/concave/contact/interact masks.
2. Apply material-specific wear recipes.
3. Add decal placement constraints.
4. Add trim sheet metadata.

### Phase F — Vision critique loop

1. Render candidate sheet.
2. Produce structured critique JSON.
3. Convert critique into grammar patch.
4. Rebuild and compare.
5. Store iteration history.

## Immediate Codex prompt candidate

```text
You are working in the Lathe repository root.

Goal: begin the Lathe asset-quality leap by adding a deterministic visual-quality diagnosis layer that catches the current prototype/blockout look of hero assets without changing public .lth syntax yet.

Context:
- Latest evidence is under automation evidence bundle `lathe-hero-asset-certification-gate/evidence_20260429_111025`.
- Current assets certify even when screenshots still show uncontrolled triangulation, flat/debug-like material colors, weak high/low distinction, stuck-on attachments, and insufficient design hierarchy.
- Preserve the stable shape-stage contract lathe.shape.intent_mesh_handoff_v1.

Implement:
1. Add deterministic visual metrics/diagnostics in lathe/validators/visual_quality.py or adjacent module:
   - random_triangulation_penalty
   - debug_material_preview_penalty
   - highlow_fake_detail_penalty
   - attachment_seating_diagnostic
   - primary_secondary_tertiary_balance proxy
2. The metrics can use existing mesh stats, topology part groups, render reports, surface maps, id map/material zones, and highlow_relation. Do not require external services.
3. Add human-readable diagnostics like:
   - "large flat face is split by noisy diagonal topology"
   - "surface appears material-ID/debug colored rather than authored PBR"
   - "hero asset lacks meaningful high-poly/low-poly distinction"
   - "attachments appear under-integrated relative to body scale"
4. Integrate diagnostics into certification reports without breaking existing JSON consumers.
5. Update tests with fixtures that simulate:
   - a flat colored box with good contract completeness but poor art quality;
   - a high/low fake relation;
   - a hero asset with sufficient authored surface evidence.
6. Update docs explaining that this is a diagnosis gate, not the full ShapeIR v2 implementation.

Do not:
- change .lth syntax yet;
- fake Blender/Roblox/external runtime evidence;
- remove existing certification fields;
- weaken current contract tests.

Run targeted tests and report exact commands/results.
```

## Strategic conclusion

Lathe is close because the pipeline is real. But to reach high-quality assets, the next breakthrough is not “more candidates” or “more validation.”

The breakthrough is **more controllable semantic construction**:

```text
family grammar + ShapeIR v2 semantic ops + real high/low bake + material/wear graph + vision critique loop
```

That combination turns Lathe from a procedural mesh generator into a programmable art director for game-ready 3D assets.
