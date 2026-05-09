# SOTA Art Direction for Procedural 3D — Authoring Systems & Lathe's Path

**Audience.** Lathe team-lead. Companion to algorithmic-geometry, topology/UV, and surface/material research streams.
**Question.** What *authoring systems* let a procedural pipeline produce assets that look art-directed instead of generic, "boxy," or "AI-generated" — and how does Lathe close the gap, standalone-procedural, ultra-modular, no AI 3D models?
**Frame.** The other streams answer "how do we generate good polygons / good UVs / good textures." This stream answers: *what does an art director author against?* The leverage in Houdini, SpeedTree, Substance, CityEngine and Geometry Nodes is **not** the kernel — it's the authoring surface that exposes the kernel to a director with a vocabulary tight enough to reject bad output and rich enough to express intent.

A short claim before the survey: **Lathe's procedural ceiling is set by its authoring vocabulary, not its kernel.** Substance Designer, SpeedTree, and CityEngine each ship one extremely sharp authoring surface and have owned their domain for ~15 years on procedural rails. Each Lathe section below has a "Maps to Lathe via:" line with concrete files and DSL keyword additions.

---

## 1. Houdini HDAs — the contract that scales art direction

The Houdini Digital Asset is the load-bearing idea here. An HDA is a node network packaged as a typed black box with **only the parameters and ports that matter for art direction exposed**, everything else hidden. The convention SideFX evangelizes — and that production pipelines treat as gospel — is roughly:

- **Inputs are typed and minimal** (a face_ref, a curve, a points stream). Optional inputs are a code smell because they break consistency downstream.
- **Outputs are explicit** — a SOP geometry stream, a points stream, a baked attribute, a cache file. Downstream tools must know what to expect.
- **Parameters use strict naming** (`isActive`, `hasMotionBlur`, `baseScale`, `enableShadows`) so pipeline tools can auto-generate UI and docs.
- **Hide complexity, expose the dial.** The classic HDA mantra: the parent network sees only what a director would touch. Internal sub-networks may have hundreds of parameters; only ~5–15 reach the surface.
- **Version pinning.** HDAs ship as `kit@3.1.0`; downstream pipelines pin and migrate explicitly.
- **Composability.** HDAs use other HDAs by reference — the asset library is a graph, not a flat file pile.

This is the difference between a "scattering tool that does everything" and a `scatter_industrial_rivets_v3` HDA whose three knobs (`density`, `pattern: grid|ring|scatter`, `seed`) capture the actual decisions a director makes.

Lathe's `kit_ir.py` already moves toward HDA semantics — `version`, `ports` (typed `direction: in|out`), `parameters`, `body_kit_uses`, `resolved_kit_use`, `hda: bool`. The roadmap §3.7/§6.5 sketches the surface keyword (`kit hard_surface_industrial_v3 : kit { version, ports, parameters, body, ... }`). The **gap is enforcement, not expressivity**:

1. Most components are in `assembly_kernel.py` (170 component-builders), not in `kit` blocks. They have no port/parameter contract.
2. There is no UI hint metadata (`range`, `step`, `units`, `enum_choices`, `tooltip`) — directors cannot author against a visible dial vocabulary.
3. There is no published version registry; the language has no `kit @ semver` resolution path.
4. Validation does not enforce port contracts at the boundary (e.g., "this kit declares `output instances : points` — at evaluation time, did it produce points?").

**Maps to Lathe via:**
- `lathe/kit_ir.py` — extend `KitIR` parameter dict with `range, step, units, ui_hint` ; add `validate_ports(produced_typed_bundle)`.
- `grammar/lathe.lark` — promote `parameters { name : type = default range a..b ui hint }` and `ports { input/output name : type }` to first-class block grammar (already partly authored in §3.7 worked example).
- `lathe/checker.py` — port-contract enforcement at kit boundary (refuse asset that consumes kit if its port types don't match).
- New `lathe/std/kits/registry.json` — versioned kit registry; reject `uses kit_x@3.1.0` when registry has only `3.0.x`.
- DSL additions: `parameter`, `port`, `kit_use ... constraint = ">=3.1.0,<4"`, `tooltip "..."`, `units: length|float|angle`.

---

## 2. KineFX / APEX — rig as procedural geometry

The KineFX/APEX position is the most provocative idea in modern procedural authoring: **the rig is a piece of typed data, not a separate domain.** A skeleton is a points-and-lines geometry. Skin weights are per-vertex attributes (`@skin.left_shoulder = 0.42`). Rig logic is an APEX graph that the engine evaluates lazily — you can author a skeleton in SOPs, then build a rig graph on top using rig components (spine, limb, digit, mech_joint, wing_chain, tentacle_chain), then animate via a separate context.

The architectural payoff:
- **Procedural rigs.** Composition rules: `rig_component.spine(segments: 5) + rig_component.limb(side: left, segments: 4) × 4 + rig_component.digit × 10` — a humanoid emerges from typed rig parts the same way a hard-surface asset emerges from kit parts.
- **Non-destructive iteration.** A rig is regenerated when the skeleton changes; it does not need re-authoring.
- **Delayed evaluation.** APEX defers cooking the rig logic, so building it is fast even when the rig is huge.
- **Skin capture is procedural.** Joint Capture Biharmonic produces weights from rest geo + capture pose; Lathe-equivalent: a `skin_program` that emits `@skin.<bone_id>` attributes derived from voxelized distance fields and biharmonic falloff.

Roadmap Phase 4 §3.14 + §8.2 already names this the "eighth typed-data slot in TypedBundle." The concrete proposal:

- `parametric_rig` block (Phase 4) composing from `rig_component` library entries.
- `rig_component` HDA semantics — same port/parameter contract as `kit`.
- `skin_program` — declarative "compute weights via biharmonic voxel field."
- `animation_library` — a typed reference set of animation clips (typed against the canonical skeleton).
- `retargeting = canonical_to_canonical_v1` — same canonical topology + canonical skeleton across humanoid family is what makes MetaHuman's "every avatar is the same skeleton" work; Lathe's procedural equivalent is a fixed canonical_topology_humanoid + canonical_rig_humanoid.

What this gives art directors: **an authored rig is a buildable thing, not a hand-tweaked artifact.** They declare "humanoid_combat_rig_v1 with 5 spine segments, IK chains on arms+legs, wing_chain disabled" and the rig is regenerable. Animation libraries are reusable across morph variants of the base anatomy.

**Maps to Lathe via:**
- `lathe/typed_bundle.py` (forward-compatible vocabulary now; implementation Phase 4) — eighth slot `Rig`.
- `lathe/rig/` (new) — `parametric_rig.py`, `rig_components/`, `skin_program.py`, `animation_library.py`.
- DSL additions: `parametric_rig`, `rig_component`, `skin_program`, `animation_library`, `humanoid_anatomy`, `morph_targets`.
- Contract `lathe.rig.parametric_v1` (already drafted in roadmap §15.2).
- The proposal: even pre-Phase-4, allow `rig_component` *declarations* in `.lth` so authors can declare intent now; Phase 4 makes them buildable.

---

## 3. Geometry Nodes — fields, bundles, closures

Blender's Geometry Nodes is the second biggest authoring innovation of the last five years. Two ideas:

**Fields.** A field is a function evaluated per-element with whatever inputs are in scope — `position`, `normal`, `index`, `uv`, anonymous attributes. Field nodes (per-element) and data-flow nodes (per-geometry) are visually distinguished by dashed vs solid links. Authors compose: `density = remap(noise(position * 0.05), 0..1, 0.2..0.8)` and the field is evaluated when needed, where needed. Anonymous attributes flow with geometry without polluting the user-facing attribute namespace.

**Bundles & closures (Blender 5.0, late 2025).** Bundles are typed key-value packets (e.g. `{ mesh, weights, hair_root_uvs }`). Closures are first-class "node sub-functions" — you can author a procedural recipe and pass it as a value. The 2026 roadmap puts XPBD/PBD physics on top of this for hair/cloth/soft-body, plus an online asset library for community node groups.

**What Lathe should learn:** the `attr_lang` mini-DSL (roadmap §6.2) is exactly the "field" idea — `@curvature.smooth(0.6)` is a field expression evaluated per-element. Lathe should commit to:

- Field expressions everywhere (mask programs, surface programs, instance counts, scatter densities).
- Anonymous attributes — outputs of one HDA flowing into another without globally namespacing every channel.
- Bundles — a TypedBundle is exactly the bundle idea; rename if necessary to align with industry vocabulary.
- Node-group reuse — `surface_graph` should be importable as a `surface_program` symbol and re-instantiated with overrides.

The big failure mode of node-graph authoring at scale is "spaghetti graphs" where one author understands the wiring. Lathe avoids it by being **declarative text**, not visual nodes — but the same risk applies to deeply-nested `mask_program` compositions. Mitigation: name and version every `mask_program` / `surface_program` / `kit` ; expose only typed ports.

**Maps to Lathe via:**
- `lathe/asset_quality/shape_ir_v2.py` — promote 30 semantic ops to field-style expressions taking `@position, @normal, @uv, @curvature` etc.
- `grammar/lathe.lark` — `@<attr>` syntax, `field { ... }` block, `closure { ... }` block.
- `lathe/std/masks/smart_masks.lth` — already names smart masks; rewrite expressions in field DSL once §6.2 lands.
- Contract `lathe.attr_lang.v1` (roadmap §15.2).

---

## 4. Unreal PCG — density-based scattering with typed graphs

Unreal PCG (5.4+) is the most production-relevant case of "modular, art-directable scatter." It uses density-based point sampling along splines, surfaces, and volumes; biome graphs compose recursively (BiomeCore + sample plugins ship Attribute Set Tables, feedback loops, recursive sub-graphs); the 5.7 PCG editor mode adds spline drawing, point painting, volume creation directly in the editor; the Houdini-PCG bridge makes any HDA a PCG node.

The art-direction model:

- **Density is a field.** You paint or compute density across a surface. Scatter consumes density.
- **Splines are first-class.** Roads, fences, pipes, vegetation borders.
- **Biomes are recursive subgraphs.** "Forest" pulls in "tree-mix" and "ground-cover" and "rock-cover" subgraphs, each parameterized.
- **Attribute Set Tables.** Instead of hard-coding "use oak tree", use a table that references oak/pine/birch with weights — directors swap tables per region.

Lathe's `instance_pattern` / `scatter` (roadmap §6.4) is the analog. The current weakness: Lathe has no spline-as-first-class type, no density-as-field idiom, no recursive subgraph composition for `scatter`. Roadmap §15.2 names `lathe.spline.v1` for Phase 3.

The win for art directors: **a director declares "industrial floor with rivet density 0.3 along weld seams, density 0.05 elsewhere, biased to corners by curvature, snap-aligned to surface normal" in 6 lines**, instead of placing 200 rivets by hand. The leverage is in expressing the *rule*, not the points.

**Maps to Lathe via:**
- `lathe/feature_ops/scatter.py` (currently a stub per roadmap audit) — implement as `density × sampler × instancer` triple where each is a typed pluggable.
- DSL: `scatter { density = field(...) sampler = poisson_disk instance = kit.rivet_brass align_to = surface_normal }`.
- New `spline` typed-data slot.
- `attribute_table` block — director-swappable list of (instance, weight) rows.
- Recursive `scatter` subgraphs (a scatter can call another scatter as a subgraph).

---

## 5. SpeedTree — proof a procedural authoring surface owns AAA vegetation

SpeedTree is the existence proof for "one tightly-scoped procedural surface owns its art-direction domain for ~17 years." Avatar (2009), every Witcher, Destiny, Far Cry Primal, Arkham Knight, ~1,000 games. Why does it own?

- **Nodes that map to art-direction concepts.** Every node is a `branch_generator`, `leaf_generator`, `card_generator`, `spine`, `force`, `zone`, `proxy`. A director sees the tree as branches → sub-branches → leaves, exactly the mental model.
- **Forces.** Direction, magnet, gnarl, twist, curl, planar, mesh, return — the director shapes the canopy by placing a magnet near the top to draw branches up, a planar force to flatten the silhouette, a twist to gnarl the trunk. **The forces *are* the art direction.**
- **Hand-edit on top of procedural.** Select an individual branch and bump its polygonal resolution. Sculpt, trim, bend with freehand on top of the procedural base. This is the "art-directable technically-efficient" invariant.
- **Wind + LOD in the same authoring surface.** Wind program declared with the model; LOD pyramid auto-generated.
- **Seasonal phases as morph targets.** seedling → sapling → young → mature → ancient.

The roadmap §7.1 claims `lathe/std/vegetation/` will ship 10 species. Honest assessment: **the authoring surface for "what is a tree" needs to mirror SpeedTree's vocabulary or it will fail.** A tree species declaration without `branches { iteration_count, productions, force_field }` and `leaves { card, cluster_density, distribution_field }` and `forces { magnet, planar, gnarl }` is too thin to art-direct.

The deeper point: **SpeedTree did not invent better tree algorithms — it invented a directable vocabulary.** Lathe's vegetation vocabulary should be benchmarked against SpeedTree node semantics, not against L-system papers.

**Maps to Lathe via:**
- `lathe/std/vegetation/` — vocabulary mirroring SpeedTree (`branch_generator`, `leaf_generator`, `card_generator`, `spine`, `force`).
- `lathe/feature_ops/vegetation.py` — implement the generators as Lathe HDAs.
- DSL: `vegetation_species`, `branch_generator { ... }`, `force { type: magnet|gnarl|... position: ... radius: ... }`.
- Hand-edit override: a `species_override { branch_id: foo, custom_geometry: bar.lth }` so the procedural base remains regenerable while specific branches are pinned.
- Wind program reuses style stack's animation_rate.

---

## 6. CGA / Shape Grammars — the production rule as authoring primitive

CityEngine's CGA is the cleanest example of **declarative refinement** as art direction. A rule file is a sequence of productions: `Lot --> extrude(15) Building`, `Building --> split(y) { 3: Ground | ~1: Floors | 1: Roof }`, `Roof --> pyramid(45deg)`. The director writes **what gets built**, not how. The rule rewriter handles the recursion.

The CGA operator vocabulary that translates directly to procedural authoring (roadmap §3.8):

- `-->` production rule.
- `split(axis) { ratio: a | ratio: b }` — divide a shape along an axis.
- `repeat(n, mirror|rotate|pattern)` — replicate.
- `chooseOne { p1: a, p2: b }` — randomized variant from a curated set, gated by probability or by attribute value.
- `extrude/translate/rotate/scale` — local transforms with bounding-box scope.
- `texture/setMaterial` — attach surface intent.

Why this is art-directable: the director writes a 30-line grammar and the system enumerates an entire variation family. Houdini's `attribrandomize` is dumb (uniform jitter); CGA is **smart**: variation is **constrained by the grammar's curated palette**, and symmetry/snap/align is preserved by construction.

**Maps to Lathe via:**
- `lathe/asset_grammar/` (new) — productions, splits, repeats, chooseOne.
- `lathe/assembly_kernel.py` becomes the *terminals* — the existing component-builders are the leaves of a CGA tree, not the whole authoring surface.
- DSL: `assembly_rules { Root --> A, B, C; A --> split(x) { ... } }` (roadmap §3.8 already drafts this).
- Contract `lathe.assembly.shape_grammar_v1` (roadmap §15.2, Phase 3).

The combination CGA + WFC + HDA terminals is exactly the architecture that lets a director declare "Soviet-era industrial corridor, 30m, with two side rooms" and get a coherent build with curated variation.

---

## 7. Style without ML — algorithmic stylization per band

The standalone-procedural mandate forbids neural style transfer. The good news: every "stylized" look in production today **decomposes into a deterministic recipe**. The roadmap's 8-axis stack and the seven existing presets in `lathe/style_presets.py` are the right scaffold; the *content* of each preset needs the band-specific recipe.

**Band A — Chunky low-poly (Roblox / indie).** Hard normals only. No bevel. Uniform-quantized palette per asset (≤6 colors). Vertex color or flat texture. Lambert + clamped ambient. No outline. Existence proof: indie low-poly is a multi-billion category on its own.

**Band B — Anime / cel-shaded.** Three deterministic tells:
1. **Toon ramp** — 1D LUT (lighting → color band) with 2–4 hard steps.
2. **Inverted-hull outline** — duplicate geometry, invert normals, scale slightly outward, color black. Stable in motion; cheap.
3. **Face SDF** — for character faces, an artist-painted SDF mask defines the "shadow shape" so the cheek shadow doesn't break across angles. This is the Genshin / Honkai trick. Lathe procedural equivalent: bake a face-region mask at character build time and treat as a per-vertex `@face_shadow_zone` attribute.

**Band C — Painterly.** Brushstroke composite shader. Curvature-driven brush direction. Posterized normals. Single-asset tractable; full-scene Arcane/Spider-Verse needs directed art passes (out of scope per roadmap §12.4).

**Band D — Stylized PBR AAA.** What roadmap §3.6 covers in depth. Multi-band PBR composition: base + curvature peaks (edge wear) + AO valleys (cavity dirt) + world-position top-dust + per-zone material. This is Substance Designer's industry. The Lathe v0.1 surface_program / smart_mask architecture targets this directly.

**Band E — AAA realistic.** Hard-surface and natural-environment tractable. Photoreal humans need scan/capture data, deferred per roadmap.

**Band F — Toy / Lego.** Strict construction grammar — every part snaps to a brick or sub-brick lattice. "Every model must be buildable from real bricks" is **literally a constraint solver**. Lathe `wfc_tileset` + tight `physical_substance` constraints.

**Band G — Hybrid.** Astro Bot's PBR+stylized character on PBR environment is fully expressible by Lathe's `style_bridge` mechanism (roadmap §3.4, already in `style_presets.py`). HD-2D needs an external sprite library (deferred).

The non-obvious leverage: **the refusal table in `style_presets.py:155-227` is more important than the presets themselves.** It encodes the *negative space* — "PBR-realistic + ramp_outline produces an uncanny plasticky look unless explicitly bridged." That refusal turns "I picked some axes" into "the system rejected an incoherent style," which is what art directors actually need.

**Maps to Lathe via:**
- `lathe/style_presets.py` — already strong; expand to band-specific surface_program defaults per preset.
- `lathe/std/styles/` (new directory) — one `.lth` per band with all the deterministic recipe pieces (toon_ramp_lut, inverted_hull_outline, face_sdf_template, brushstroke_composite_shader_program).
- `lathe/style_routing.py` (new) — per-stage axis dispatch (already partly in `style_presets.stage_axis`).
- DSL additions: `toon_ramp`, `inverted_hull_outline`, `face_shadow_zone`, `brushstroke_composite`, `posterize_normals`.

---

## 8. Reference-driven authoring without neural generation

`lathe/asset_quality/reference_board.py` already exists. The non-AI approach to "match this concept image" has three deterministic legs:

**Palette extraction.** k-means on the concept image yields ≤8 dominant colors; the asset's palette is constrained to that set (with luminance buckets). This is Substance Sampler's photo-fit recipe.

**Frequency analysis.** Wavelet decomposition of the reference splits low-frequency (silhouette / large value pattern) from mid (panel/seam structure) from high (micro-noise / wear). Lathe maps low-freq → silhouette intent; mid → panel/seam grammar; high → procedural noise scale.

**Multi-view CAD reverse engineering.** The 2024-25 research line (Img2CAD, Automatic Reverse Engineering) demonstrates that 3 orthographic views can deterministically reconstruct a CAD-grade procedural model via constraint solving. **No ML required for the constraint solver step** — only the optional VLM hint stage. Lathe can adopt the constraint-solver-only path.

The director-facing vocabulary:
- `reference_set { front: "concept_front.png", side: "concept_side.png", top: "concept_top.png" }` — already in V1.1.
- `reference_palette { source: reference_set, colors: 6 }` — extracted palette becomes the asset's authored palette.
- `reference_silhouette { source: reference_set, view: front }` — silhouette intent for the validator.
- `reference_frequency_split { source: reference_set, bands: [low, mid, high] }` — bands feed surface_program scale parameters.

**Maps to Lathe via:**
- `lathe/asset_quality/reference_board.py` — already partial; extend with palette/frequency/silhouette extractors.
- DSL: `reference_palette`, `reference_silhouette`, `reference_frequency_split`, `match_silhouette`.
- Validator: `silhouette_match` (compare rendered silhouette against `reference_silhouette` via Hu moments / chamfer distance).

---

## 9. Constraint-driven variation

Houdini's `attribrandomize` produces uniform jitter, which is what assets *look like* when "variation" is added naively — every rivet slightly different in scale and rotation, all faintly off, none meaningful. Real art-directable variation is **constraint-driven**:

- **Curated palette variation.** "Pick from {oak, walnut, mahogany} with weights {0.5, 0.3, 0.2}" — chooseOne, not random.
- **Snap-to-grid jitter.** Translate within 5cm tolerance, but always to a 1cm sub-grid.
- **Symmetry preservation.** Mirror left/right by construction; jitter only along axes that don't break symmetry.
- **Authored bounds.** rivet_size = 3mm range 1mm..6mm — the range is the contract; variation samples within.
- **Constraint solver.** WFC ensures adjacency; bricks-must-snap-to-bricks is a hard constraint.

The pattern is: **author a *shape* of variation** (palette, range, symmetry, adjacency), not just a number. The PATEX paper (SIGGRAPH 2016, ACM TOG) and the Snappable Meshes literature both formalize this — variation is a sampler over an authored constraint manifold.

**Maps to Lathe via:**
- `lathe/feature_grammar.py` (already exists) — extend with `chooseOne`, `range_jitter`, `snap_grid_jitter`, `mirror_constraint`.
- DSL: `range = 1mm..6mm`, `snap_to = 1cm`, `mirror_axis = x`, `chooseOne { 0.5: oak, 0.3: walnut, 0.2: mahogany }`.
- `lathe/asset_quality/family_grammar.py` — already touches this; align vocabulary.
- Refuse `random()` calls without an explicit bound.

---

## 10. What signals "AAA production-ready"

The visual cues that distinguish "looks shipped" from "looks AI-generated" are mostly authoring-vocabulary issues, not algorithm issues:

- **Edge bevels at silhouette.** Roadmap Phase 1 §5.1 — the canonical `boolean → bevel(seam_group)` chain. Without this, hard-surface assets read as toy-blocky.
- **Triplanar wear at concave intersections.** Substance smart-mask cavity dirt + edge wear, layered.
- **Trim-sheet motifs at seams.** Repeated tileable motif across modular kit pieces — the snap-grid kit assumption.
- **Decals at unique points.** Hero unique detail (a serial number, a faded warning sticker, a heraldry crest) at one specific point breaks the uniformity that screams "procedural."
- **Distinct material zones.** Two to four named material zones (`@material_zone = body | trim | accent | decal`) gating per-zone surface programs.
- **NOT uniform noise.** A single Perlin noise applied globally is the #1 "looks AI-generated" tell.
- **NOT identical silhouettes.** Real assets have asymmetric details — a battered corner, a bent handle. Curated asymmetry, not random jitter.

Lathe's authoring vocabulary supports most of this declaratively (`material_zone`, `decal_library`, `trim_sheet`, smart_masks). The gap is **defaulting to it** — a hero asset built without explicit material zones and without decal placements should be flagged at validation.

**Maps to Lathe via:**
- `lathe/validators/visual_quality.py` — promote "missing material zones," "missing decal placements," "uniform noise dominance" to warnings on hero class (already partly in roadmap §4.2).
- `std/repair/hero_hardsurface.lth` — defaults that pre-populate material zones / decal placements when not declared.

---

## 11. The "imagination layer" claim — closing the vocabulary gap

The remaining gap is the **noun vocabulary** an art director uses informally and Lathe currently can't accept. Examples a director would write today:

- "Battered Soviet-era console terminal salvaged from an oilrig"
- "Sun-bleached desert kiosk, vinyl wrap peeling at corners"
- "Ornate pre-industrial brassbound chest with velvet interior"
- "Cyberpunk neon-lit gacha capsule"

These decompose into the existing axes plus a few missing ones:

- **Era / period.** Pre-industrial / Industrial / Soviet / Post-war / Cyberpunk / Solar-punk. Maps to material palette + construction grammar + wear program.
- **Provenance.** Salvaged / Pristine / Restored / Bootleg / Mass-produced. Maps to wear severity + material consistency + decal density.
- **Environment exposure history.** Indoor-dry / Coastal / Desert / Industrial / Underwater. Maps to weathering recipe (rust vs salt-bloom vs dust vs algae).
- **Cultural register.** Military / Civilian / Religious / Recreational / Industrial. Maps to decal_library + trim_sheet motif.
- **Condition arc.** Age years × use intensity × damage events. Maps to a single `weathering_program(age_years: 80, environment: indoor_dry, use: heavy)` recipe that is *deterministic*.

These are not new geometric primitives — they are **named compositions of existing axes**. Lathe should ship a small "director vocabulary" library that maps these nouns to style_target + surface_program + decal_library + weathering_program tuples, and let directors override.

**Maps to Lathe via:**
- `lathe/std/director_vocab/` (new) — `era_soviet_industrial.lth`, `provenance_salvaged.lth`, `environment_coastal.lth`, etc., each declaring a compatible style_target subset + recommended palette + recommended wear program.
- DSL: `era`, `provenance`, `environment_history`, `cultural_register`, `condition_arc` — each resolving to existing axes via the std/director_vocab/ definitions.
- A `director_vocab_compose` step in the resolver that turns "era: soviet_industrial + provenance: salvaged + environment: coastal" into concrete style_target + surface_program + weathering parameters.

This is genuinely modular — every entry in `std/director_vocab/` is a pure composition of existing axes; no new kernel work; new vocabulary terms can be added without grammar changes (they live in std/, not in `lathe.lark`).

---

## Top 5 art-direction-leverage changes (ROI-ordered)

These are the highest-leverage authoring-surface investments for closing the "looks AI-generated" gap. Each is implementable standalone-procedural with no AI model dependency.

### 1. HDA-class kit contract enforcement (S, ~2-3 weeks)

Promote the existing `kit_ir.py` HDA fields (version, ports, parameters) from data-only to enforced contract. Add `range`, `step`, `units`, `enum_choices`, `tooltip` to parameter metadata; add port-type validation at kit boundary; ship a `lathe/std/kits/registry.json` with semver resolution.

**Why this is #1.** Every other authoring improvement (style routing, scatter, surface_program reuse) compounds when the kit boundary is typed. Today the boundary is loose, so kits-as-HDAs is a documentation goal, not a contract. Closing this lets directors declare against versioned kits and the checker rejects bad uses.

**Maps to:** `lathe/kit_ir.py`, `lathe/checker.py`, `grammar/lathe.lark`, new `lathe/std/kits/registry.json`. Contract `lathe.kit.hda_v1` (already drafted).

### 2. Director-vocabulary compositional layer (S, ~2-3 weeks)

Ship `std/director_vocab/` with ~12 entries (3 eras × 2 provenances × 2 environments × 2 cultural registers, sparse). Each is a pure composition of existing style_target + surface_program + decal_library + weathering_program. Resolver auto-composes "era: soviet_industrial + provenance: salvaged + environment: coastal" into concrete configs.

**Why this is #2.** Highest leverage for "imagination → output" because it accepts the actual nouns directors use. No grammar change, no kernel change — pure std/ content + a small composer in the resolver. Massively shortens the gap between a one-line creative brief and a buildable asset.

**Maps to:** `lathe/std/director_vocab/`, `lathe/resolver.py` (compose hook), existing DSL keywords with new value vocabulary.

### 3. Field-style `attr_lang` mini-DSL across all programs (M, ~6-8 weeks)

Promote roadmap §6.2 from a Phase 2 plan to a Phase 1 prerequisite. Field expressions in `mask_program`, `surface_program`, `scatter`, `instance_pattern`, `deform`. `@curvature.smooth(0.6)`, `@ao.below(0.55)`, `@world_pos.up_facing(30deg)`. Per-element evaluation by default; aggregations explicit.

**Why this is #3.** Every smart-mask, surface-program layer, and scatter density expression today is hard-coded as a string in `std/masks/smart_masks.lth`. Replacing with a real field expression DSL turns the existing 7 smart masks into a recombinable algebra: directors author new masks by composition, not by registering a new module. This is the productivity multiplier of Geometry Nodes' field system.

**Maps to:** `grammar/lathe.lark` (`@<attr>` syntax, `field { ... }` block), new `lathe/attr_lang/`, `lathe/std/masks/smart_masks.lth` rewrite. Contract `lathe.attr_lang.v1` already drafted.

### 4. CGA-style assembly_rules + scatter-as-density-graph (M, ~8-12 weeks)

Ship `assembly_rules` with `-->`, `split`, `repeat`, `chooseOne` operators (roadmap §3.8) and rebuild `scatter` / `instance_pattern` (roadmap §6.4 / §7.7) as `density_field × sampler × instancer × align_to_field`. Existing `assembly_kernel.py` component-builders become the *terminals* of the grammar.

**Why this is #4.** Replaces ~170 monolithic component-builders with composable terminal + grammar + scatter layer. Directors author "console terminal with 2 side panels split 30/70, repeat 4 vents on top, scatter rivets along weld seams at density 0.3" in one block instead of editing 6 component-builder Python files.

**Maps to:** `lathe/asset_grammar/` (new), `lathe/feature_ops/scatter.py` (rewrite), `lathe/assembly_kernel.py` (refactored to terminals). Contracts `lathe.assembly.shape_grammar_v1`, `lathe.spline.v1`.

### 5. Reference-driven authoring (palette + silhouette + frequency split) (M, ~6-8 weeks)

Extend `lathe/asset_quality/reference_board.py` with deterministic palette extraction (k-means), silhouette intent (Hu moments), and frequency band split (wavelet). Ship `reference_palette`, `reference_silhouette`, `reference_frequency_split`, `match_silhouette` as DSL keywords. New validator `silhouette_match` compares rendered against reference silhouette.

**Why this is #5.** This is the standalone-procedural answer to "match my concept art" without any neural model. Closes the largest authoring-frustration loop — directors today have to translate concept art to a brief manually; this lets them point at the image. The constraint-solver-only multi-view CAD path (no VLM, no learned model) is a research direction Phase 3+ can extend, but the deterministic palette + silhouette + frequency triple is shippable now and immediately useful.

**Maps to:** `lathe/asset_quality/reference_board.py`, new `lathe/validators/silhouette_match.py`, DSL: `reference_palette`, `reference_silhouette`, `reference_frequency_split`, `match_silhouette`.

---

## Sources

Houdini & HDAs:
- [SideFX Houdini docs — KineFX overview](https://www.sidefx.com/docs/houdini/character/kinefx/overview.html)
- [SideFX — Skin capture](https://www.sidefx.com/docs/houdini/character/kinefx/capture.html)
- [SideFX — APEX graph basics](https://www.sidefx.com/docs/houdini/character/kinefx/apexgraphbasics.html)
- [SideFX — APEX Autorig Component](https://www.sidefx.com/docs/houdini/nodes/sop/apex--autorigcomponent.html)
- [SideFX — What's new APEX/KineFX](https://www.sidefx.com/docs/houdini/news/20_5/kinefx.html)
- [SideFX — HDA Dynamic Payload](https://www.sidefx.com/docs/houdini/nodes/lop/hdadynamicpayload.html)
- [Beginner's Guide to HDAs — ArtStation](https://www.artstation.com/blogs/julianbragagna/yVO4/the-beginners-guide-to-hdas-parameters)
- [Building Reusable HDAs — Artivoxa](https://www.artivoxa.com/building-reusable-hdas-houdini-digital-assets-for-your-studio-pipeline/)
- [Houdini KineFX for Character Motion Design — Artivoxa](https://www.artivoxa.com/houdini-kinefx-for-character-based-motion-design/)
- [Basic Auto-rigging in APEX with Houdini 20 — Andreas KJ](https://www.andreaskj.com/fast-autorig-with-apex-in-houdini-20/)

Geometry Nodes:
- [Blender 5.1 Manual — Fields](https://docs.blender.org/manual/en/latest/modeling/geometry_nodes/fields.html)
- [Blender 5.1 Manual — Node Groups](https://docs.blender.org/manual/en/latest/interface/controls/nodes/groups.html)
- [Geometry Nodes Workshop September 2025](https://code.blender.org/2025/10/geometry-nodes-workshop-september-2025/)
- [Bundles and Closures — Blender Developers Blog](https://code.blender.org/2025/08/bundles-and-closures/)
- [Beginner's Guide to Geometry Nodes 2026 — CGWire](https://blog.cg-wire.com/blender-scripting-geometry-nodes/)
- [80lv — Introduction to Blender's Geometry Nodes](https://80.lv/articles/introduction-to-blender-s-geometry-nodes-understanding-proceduralism)

Unreal PCG:
- [Unreal 5.7 PCG Overview](https://dev.epicgames.com/documentation/en-us/unreal-engine/procedural-content-generation-overview)
- [PCG Biome Core and Sample Plugins](https://dev.epicgames.com/documentation/en-us/unreal-engine/procedural-content-generation-pcg-biome-core-and-sample-plugins-overview-guide-in-unreal-engine)
- [Unreal 5.7 PCG Updates — Creative Bloq](https://www.creativebloq.com/3d/video-game-design/the-unreal-engine-5-7-procedural-content-generation-update-explained)
- [SideFX PCG Overview](https://www.sidefx.com/docs/houdini/unreal/pcg/index.html)

SpeedTree:
- [SpeedTree industry-standard product page](https://unity.com/products/speedtree)
- [SpeedTree branch_generator docs](https://docs9.speedtree.com/modeler/doku.php?id=branch_generator)
- [SpeedTree leaf_generator docs](https://docs.speedtree.com/doku.php?id=leaf_generator)
- [SpeedTree tips and tricks — Creative Bloq](https://www.creativebloq.com/3d/speedtree-tips-and-tricks-master-the-basics-of-this-industry-standard-software)
- [Creating High-Resolution Custom Trees — Gnomon](https://www.thegnomonworkshop.com/workshops/creating-high-resolution-custom-trees-using-speedtree)

CGA / CityEngine:
- [CityEngine CGA Shape Grammar Manual](http://cehelp.esri.com/help/topic/com.procedural.cityengine.help/html/manual/cga/basics/toc.html)
- [Tutorial 6: Basic shape grammar — Esri PDF](https://content.esri.com/resources/cityengine/tutorial_6_basic_shape_grammar.pdf)
- [CityEngine Wikipedia](https://en.wikipedia.org/wiki/CityEngine)

Stylization & art direction:
- [Cel shading — Wikipedia](https://en.wikipedia.org/wiki/Cel_shading)
- [Cel-shading tricks — Torchinsky](https://torchinsky.me/cel-shading/)
- [Cel-shading process and examples — UDIT](https://www.udit.es/en/cel-shading-que-es-su-proceso-paso-a-paso-y-10-ejemplos-imprescindibles/)
- [80lv — Decal Technique for Hard-Surface Scenes](https://80.lv/articles/decal-technique-for-hard-surface-scenes)
- [80lv — Procedural Materials From Big to Small](https://80.lv/articles/procedural-materials-from-big-to-small)
- [Substance 3D Designer — Metal Edge Wear](https://helpx.adobe.com/substance-3d-designer/substance-compositing-graphs/nodes-reference-for-substance-compositing-graphs/node-library/mesh-based-generators/mask-generators/metal-edge-wear.html)
- [Substance 3D Designer — Edge Wear](https://helpx.adobe.com/substance-3d-designer/substance-compositing-graphs/nodes-reference-for-substance-compositing-graphs/node-library/mesh-based-generators/mask-generators/edge-wear.html)
- [Substance 3D Designer — Mask Builder](https://experienceleague.adobe.com/en/docs/substance-3d-designer/using/substance-graphs/nodes-reference-for-substance-graphs/node-library/mesh-based-generators/mask-generators/mask-builder)
- [Polycount — Trim Sheet 4-Part Tutorial](https://polycount.com/discussion/214726/creating-trim-sheets-4-part-tutorial-polygon-academy)
- [Polycount — Hard Surface Decals vs Trim Sheets](https://polycount.com/discussion/227421/hard-surface-model-decals-vs-trim-sheets)
- [VSQUAD — Indie Game Art Styles Guide](https://vsquad.art/blog/mastering-indie-game-art-styles-a-developers-guide)

Reference-driven authoring:
- [Img2CAD: Reverse Engineering 3D CAD Models from Images](https://arxiv.org/html/2408.01437v1)
- [Automatic Reverse Engineering — multi-view CAD](https://arxiv.org/abs/2309.13281)
- [From 2D CAD Drawings to 3D Parametric Models](https://arxiv.org/html/2412.11892v1)

Constraint-driven variation:
- [PATEX: exploring pattern variations — ACM TOG](https://dl.acm.org/doi/10.1145/2897824.2925950)
- [Snappable Meshes — arXiv](https://arxiv.org/pdf/2108.00056)
- [WFC 3D Generator — Blender Extensions](https://extensions.blender.org/add-ons/wfc-3d-generator/)
- [Survey of Control Mechanisms for Creative Pattern Generation — Gieseke 2021](https://onlinelibrary.wiley.com/doi/10.1111/cgf.142658)
