# Lathe Improvement Roadmap — Imagination to Life, Standalone Procedural

**Author:** synthesis-architect (lathe-imagination-research team)
**Date:** 2026-05-03
**Synthesizes:** auditor_report.md, quality_framework.md, stylization_atlas.md, procedural_3d_systems.md, lathe_language_design.md (with 2 design-doc addenda)
**Mandate:** turn Lathe from "expressive language but boxy procedural output" into "imagination to life across the full style spectrum, purely procedurally" — no AI 3D runtime dependency.

---

## 1. Executive Summary

Lathe is a declarative DSL with ~1,100+ authoring entries (rooms, vehicles, civilizations, AI directors, ecologies, packing solvers, building envelopes, district plans). It compiles via a 14-stage pipeline ending in certified .glb/.usd assets. The language is spectacular. The kernel that consumes it is not. The auditor's instrumented build of `examples/brassbound_chest.lth` produced 2,412 triangles of axis-aligned boxes with diagonal triangulation, no real bake (high == low), no decals painted in 3D, and a certification score of 0.888 against threshold 0.84 (`auditor §1`). The validator literally rewards box silhouettes via the formula `primitive_penalty = (bbox_area/area − 1.0) / 2.0` at `lathe/render_eval.py:99` — a perfect cube scores 0 (best) (`auditor §4`).

**The diagnosis is unambiguous: the language is implementing 5–10% of what it declares.** Three rot vectors compound:

1. **Vocabulary too narrow.** ShapeIR has three primitive types (`box`, `cylinder`, `revolved_profile`); 170 component-builders emit 464 box calls + 96 cylinder calls + 1 revolve (for a rifle scope). Domes are squashed boxes. Arches are step-stacked boxes. Lids are 2 boxes (`auditor §2`).
2. **Latent capability never wired.** `manifold3d` kernel supports spheres — zero authoring sites construct one. `mesh_grammar.py` parses `profile/extrude/sweep/loft/bevel/chamfer` — they all lower to box+cylinder façade. `creative_grammar.py` has 8 style preset tables — they only modulate box COUNTS, not primitive selection. `bake_runtime.py` has Substance-spirit curvature-aware wear — it reads curvature off a low-poly cube, so wear concentrates on box corners (`auditor §3`).
3. **Validators reward what the kernel produces.** Box silhouettes are penalty=0; calibration is locked to box-stack output (`auditor §4`).

**The path forward is procedural-only and self-contained.** Substance Designer is "now used in the majority of AAA games" with fully procedural-graph material authoring (`quality §4a.1`). SpeedTree ships AAA vegetation across Avatar / Witcher 1/2/3 / Destiny / Far Cry Primal / Batman: Arkham Knight — "since Avatar 2009, used in nearly 100 films and well over 1,000 games" (`procedural §S.4`). Houdini powers Naughty Dog / Insomniac / Pixar / Wētā FX without runtime AI. Frostbite ships SDF destruction at runtime in BF6 REDSEC. **Procedural at the limit produces tier-1 output** — the standalone-procedural posture is not a constraint, it is a discipline that produces *better* assets than AI generators do today (cleaner topology, deterministic, edit-after-generate, IP-clean, runtime-cheap) (`procedural §B`).

**The bet** is a phased rebuild of Lathe's kernel against an unchanged DSL philosophy — extending vocabulary where it must extend, but always under additive contracts that preserve `lathe.shape.intent_mesh_handoff_v1` per AGENTS.md.

- **Phase 0 (1 week)** — stop the bleeding. Replace the box-rewarding validator formula with the isoperimetric ratio (`lathe/render_eval.py:99`); deploy `revolved_profile` across the ~50 component builders the auditor identified; add `sphere` to ShapeIR; wire `target_quads` to a real decimater; build a real high-poly source so bakes mean something. All single-PR scope, immediate visible improvement, no contract migration.
- **Phase 1 (4–6 weeks)** — real geometry kernel. Real edge-aligned bevel/chamfer, real swept profiles, real lofted solids, real Blender geometry adapter (replacing the 60-line weld+triangulate). Asset class as first-class concept. Real-render validators (silhouette_multi_angle, box_stack_detector, frequency_energy). **Canonical hard-surface idiom: `boolean → bevel(seam_group)` chain — Boolean produces the A∩B seam group, PolyBevel consumes it. This single pattern is the most visible "before/after" in box-stack-to-hard-surface terms.**
- **Phase 2 (3–4 months)** — style routing + procedural surfaces. `style_target` stack vocabulary with refusal of incompatible stacks; `style_bridge` for sanctioned mixed compositions; **three-mode surface authoring** matching Substance's Designer/Sampler/Painter divide (`designer_graph` + `photo_fit` + `layer_stack`); HDA-class kit semantics with explicit ports; **`scatter` (Copy-to-Points) becomes the productivity multiplier** for greebles/rivets/vegetation tufts as one-line attribute-driven instancing.
- **Phase 3 (6–9 months)** — domain libraries + simulation. SpeedTree-class vegetation, terrain + erosion, WFC modular assembly, CGA-style assembly_rules, OpenSubDiv finishing, F-Rep/SDF authoring, instance_pattern surface-projected greebles.
- **Phase 4 (12–18 months)** — organic + animation forward vocabulary. **Rig-as-geometry** (KineFX/APEX position): rig becomes the eighth typed-data slot in TypedBundle alongside Mesh/Points/Volume/Heightfield/Spline/SDF/Image. Parametric humanoid anatomy, morph targets, parametric rigs (deferred per spec §1, but specced).
- **Phase 5 (18–36 months)** — Lathe Engine runtime. HDAs evaluated live in Unity / Unreal / Maya as live procedurals — the Substance .sbsar / Houdini Engine / Frostbite SDF-at-runtime pattern. Standalone-procedural mandate doesn't preclude shipping live procedurals; it precludes runtime AI dependencies.

**The 6-month bet:** Lathe ships hero-class procedural assets across Bands A (chunky low-poly) and D (stylized PBR). The brassbound_chest example, rebuilt under the typed-kernel contract, reads as a real chest with real bevels, real instanced rivets, real curvature-driven wear, real plank micro-displacement. Validators read pixels, not metadata.

**The 18-month bet:** Lathe adds Band B (anime/cel) authoring with anatomy presets, ramp-LUT synthesis, face-shadow SDF generation, inverted-hull outlines. The DSL supports the full eight-axis style stack from `stylization §S.1` and refuses incompatible compositions.

**The 3-year bet:** Lathe Engine runtime ships HDA-class procedurals into Unity/Unreal/Maya. Bands A, D, B production-ready; Band C (painterly single-asset), F (toy/Lego), G (Astro Bot variant) covered; E (AAA realistic) covered for hard-surface and natural environment but explicit about its organic-photoreal ceiling. The procedural pipeline that ships Naughty Dog / Insomniac / Pixar AAA today is now expressible as portable .lth source.

---

## 2. Diagnosis — Why imagination doesn't reach output

This section consolidates the auditor's instrumented findings, the quality framework's failure-mode catalog, the stylization atlas's stack-mismatch red flags, and the procedural systems map's primitive gaps into a single concrete account of where the rot lives.

### 2.1 The pipeline trace, end to end

For `examples/brassbound_chest.lth` (213 lines declaring style `["adventure", "stylized", "wood_and_brass"]`, 8 parts, materials `["oak_planks", "brass_bands", "red_velvet_lining"]`, target_quads 12000, hero validate threshold 0.84) the auditor instrumented the full build (auditor §1 appendix A):

```
Asset:          brassbound_chest
Build duration: ~3 minutes
Pipeline path:  intent → AssetGraph → blueprint(136 primitives) →
                ShapeIR (boxes/cyls — no revolved_profile in this asset) →
                exact_explicit_assembly union → Taubin smoothing 1× →
                blender weld+triangulate (rejected, non-watertight) →
                reference_cleanup fallback → atlas UV →
                procedural sin/cos basecolor + ORM + noise normal →
                LOD via decimation → USD/GLB package
Final mesh:     7,236 verts, 2,412 tris, NOT watertight (post-LOD0)
Provider used:  lathe.provider.shape.reference_conditioned_v1 (stub)
Cert score:     0.888 (PASS, threshold 0.84)
```

Visible artifact: a flat-shaded purple+yellow box with diagonal triangulation, 2 yellow strips for handles, a tiny green protrusion (lock plate), 2 small darker boxes for feet. **No wood texture, no brass bands, no rivets, no plank seams, no crest, no aged-brass trim** in 3D form.

Triangle target 12,000 quads (~24,000 tris); actual 2,412 tris. **Miss factor ~10×** (`auditor §1`).

### 2.2 Where vocabulary collapses

`lathe/shape_ir.py:14-37`. ShapePrimitive types: `{box, cylinder, revolved_profile}`. The Manifold kernel (`lathe/adapters/manifold_kernel.py:227-236`) **also supports `sphere` as a kernel-level primitive** but no `_<name>_primitives()` builder constructs one. `revolved_profile` is used in **exactly one** of 170 builders (`_sight_primitives` for sniper rifle scopes, `lathe/assembly_kernel.py:731-790`).

The 170 component-type builders in `lathe/assembly_kernel.py` (5,307 LOC) total **464 calls to `_box(...)` + 96 calls to `_cylinder(...)` + 1 use of `revolved_profile`** (`auditor §2`). Sampled chest-relevant builders:

| Component | Boxes | Cylinders | Revolved | Notes |
|---|---|---|---|---|
| `_shell_primitives` (l. 112-123) | 2 | 0 | 0 | Outer + liner |
| `_panel_primitives` (l. 126) | 1 | 0 | 0 | Single box |
| `_frame_primitives` (l. 130-161) | 4 | 0 | 0 | Rectangle of 4 thin boxes |
| `_lid_primitives` (l. 164-175) | 2 | 0 | 0 | Lid + crest |
| `_hinge_primitives` (l. 192-212) | 1 | 1 | 0 | Cyl barrel + box mount |
| `_handle_primitives` (l. 237-250) | 0 | 1 | 0 | One cylinder |
| `_foot_primitives` (l. 253-264) | 2 | 0 | 0 | Foot + pad — could be revolved |
| `_pommel_primitives` (l. 609) | box | cyl | 0 | **Should be revolved** |
| `_dome_primitives` (l. 1036) | box | 0 | 0 | A "dome" is a SQUASHED BOX |
| `_arch_primitives` (l. 1094) | boxes | 0 | 0 | Step-stacked boxes |

**The kernel knows how to build richer primitives but the assembly grammar doesn't deploy them** (auditor §2).

### 2.3 Feature ops add MORE boxes

`lathe/feature_ops/__init__.py` (1,881 LOC) is the parametric-detail layer. Every feature operator emits boxes (or rare cylinders) with metadata tags (`auditor §2`):

| Feature | What it builds |
|---|---|
| `edge_break_features` (l. 62-105) | 4 thin boxes around the silhouette tagged `"edge_break"` — **not real bevels**; thin strips placed AT edges (creating the random-triangulation_penalty the validator flags). |
| `trim_band_features` (l. 108-131) | 2 boxes as front/rear bands. |
| `panel_frame_features` (l. 134-173) | 4 boxes forming a rectangular lip. |
| `inset_panel_features` (l. 176-220) | Boxes with `blend_mode="subtract"` — real CSG cuts, but the cut shape is a box. |
| `groove_channel_features` (l. 770-794) | N subtractive boxes spaced across a face. **Sharp-cornered grooves**, not rounded channels. |
| `bolt_grid_features` (l. 913-940) | N tiny `_feature_cylinder` calls — actual cylindrical "bolts" via raised cylinders. |
| `corner_guard_features` (l. 853-878) | 4 corner boxes. |
| `layer_plate_features` (l. 823-850) | N stacked rectangular plates as raised boxes. |

**Every "feature" is a box (or rare cylinder) with metadata tags.** "edge_break" is not a beveled silhouette — it's a thin strip *on top* of a sharp edge. "trim_band" is a slightly thicker box. There is no parametric extrusion-along-a-curve, no surface displacement, no spline-swept profile, no real chamfer/bevel.

### 2.4 The mesh grammar is namespace theater

`lathe/mesh_grammar.py` (596 LOC) advertises six ops:

```python
_SUPPORTED_OPS = {"profile", "extrude", "sweep", "loft", "bevel", "chamfer"}
```

Under the hood every op lowers to box+cylinder placement (`auditor §2`):

- `_extrude_primitives` (mesh_grammar.py:255-280) → **single `box` ShapePrimitive** with `rounding=bevel`.
- `_sweep_primitives` (l. 283-325) → `cylinder` (round section) or `box` (rect section) along an axis. **Not a real sweep along a curve.**
- `_loft_primitives` (l. 328-367) → **N step-stacked `box` primitives** with linearly-interpolated width/height across sections.
- `_apply_edge_modifier` (l. 370-387) → only updates `primitive.rounding` on existing primitives. **No additional geometry. No bevel-along-edge with N segments.**

**The mesh grammar accepts authoring like `mesh_ops = [profile(...), sweep(...), loft(...)]` but produces the same box-stacks the rest of the kernel does.**

### 2.5 No high-poly source — bakes are theater

`lathe/highlow.py` is a 32-line dataclass. **No module actually CREATES a high-poly mesh.** For brassbound_chest:

```
is_real_highlow:     False
high_triangle_count: 2412   (== low)
low_triangle_count:  2412   (== high)
triangle_delta_ratio: 0.0
```

The "PBR normal map" is curvature-modulated 2D noise over UVs, not a baked high-poly (`auditor §3 finding 6`).

**Surface authoring is decent but garbage-in.** `lathe/bake_runtime.py:271-310` does have curvature-aware procedural wear (edge_wear, micro_scratches, dirt_grime, paint_chips, patina) — *Substance-Designer-spirit*. But the curvature comes from a low-poly box mesh's normals, so wear concentrates on the box's hard corners — the result reads as "weathered crate" (`auditor §3 finding 7`).

### 2.6 Bevel is corner-only, not edge-along

`lathe/exact_solids.py:121-159` `_rounded_box_mesh` rounds the **corners** of a box via convex-hull blending. It does NOT round edges. Real CAD-style bevel (edge-aligned bevel-loop with N segments, angle limit, hard-edge tags) does not exist (`auditor §2`).

### 2.7 No subdivision, displacement, or multires

The Blender topology adapter (`scripts/blender_topology_adapter.py`, 60 LOC) does ONLY `remove_doubles + triangulate + recalc_normals`. **No SUBSURF / BEVEL / DISPLACE / MULTIRES modifiers.** Everything that would let a box-stack become a curved surface is not invoked (`auditor §3 finding 5`).

### 2.8 Validators reward boxes (the calibration disaster)

`lathe/render_eval.py:81-247`, line 99:

```python
primitive_penalty = max(0.0, min(1.0, (bbox_area / max(1.0, area) - 1.0) / 2.0))
```

A perfect cube has `bbox_area == area` → primitive_penalty = 0 (best). The "render" is a 128×128 binary mask; no anti-aliasing, no shading texture, no lighting (`auditor §4`).

`lathe/validators/visual_quality.py:630-644` computes `primitive_likeness` from authoring metadata, not pixels — counting how many tagged boxes the kernel added. **The validator counts how many tagged boxes the kernel added, not whether the mesh looks non-primitive.** Asset got `primitive_likeness_penalty: 0.076` (very good); threshold is 0.44 (extremely loose). Composite 0.888 vs threshold 0.84 → CERTIFIED. The auto_until_pass repair loop never runs because the asset passed first try.

`vision_critique.py` (1,092 LOC) ran against a stub provider. `preview_render.py` (698 LOC) is a **2D clipart renderer** dispatching to `_draw_sword`, `_draw_machine`, `_draw_counter`, or `_draw_crate`. Lines 191-198: `"external_renderer_used": False, "real_render_output": False`.

### 2.9 The eight quality levers Lathe fails today

Per `quality §0`, the eight levers (in payback order):

| # | Lever | Lathe today |
|---|---|---|
| 1 | **Silhouette readability** | Fail — axis-aligned primitive stacks produce rectangle silhouettes. |
| 2 | **Proportion vocabulary** | Absent — no head-height target, no proportion grammar. |
| 3 | **Topology serves use** | Partial — random diagonal triangulation flagged but not blocking. |
| 4 | **UV strategy is asset class** | Partial — atlas UV exists; per-class budget unenforced. |
| 5 | **PBR is a contract** | Partial — `pbr_metal_rough` declared; values uniform per face. |
| 6 | **Layered authoring** | Fail — basecolor is sin/cos noise over flat UVs. |
| 7 | **Detail hierarchy** | Fail — silhouette band fails; form band absent; surface band procedural noise on a box. |
| 8 | **Validation gates** | Fail — validators score authoring metadata, render formula rewards cubes. |

### 2.10 Stack-mismatch red flags

Per `stylization §S.4`, the dominant failure mode is **mismatched material-model and shading-model** (PBR materials rendered with cel ramp, cel-shaded geometry with photogrammetric textures, photoreal materials on chunky low-poly geometry, etc.).

Lathe today has **no language vocabulary to declare a coherent style stack** and **no validator to refuse incompatible compositions**.

### 2.11 What Houdini / Substance / SpeedTree have that Lathe doesn't

Per `procedural §D.1, §D.2, §D.11, §S.2 (named SOP vocabulary)`:

| Primitive | Why it matters | Lathe analog today |
|---|---|---|
| Typed-data kernel (mesh, points, attrs, volume, heightfield, spline, SDF, **rig**) | Every node operates on typed-data with consistent attribute access | Stages operate on artifacts but lack uniform attribute model |
| Named geometry-kernel SOPs (Sweep, Polywire, PolyExtrude, PolyBevel, Boolean, Subdivide, Remesh, Loft/Skin, Copy-to-Points, Carve) | The vocabulary AAA pipelines speak; immediately recognizable | mesh_grammar parses ops but lowers to box+cylinder |
| **`Boolean → PolyBevel` chain** | Boolean produces A∩B seam group; PolyBevel consumes it. **Canonical hard-surface idiom.** | Absent — bevel is corner-only |
| VEX-style attribute language | Per-point/per-vertex/per-prim parallel computation | None |
| HDA encapsulation | Parameterized, versioned, composable procedural tools | `kit`, `library`, `mechanism` blocks (V1.1+); no ports/version pinning |
| **Three Substance modes** (Designer / Sampler / Painter) | Designer = author from-scratch graphs; Sampler = photo-fit deterministic; Painter = layer-stack-applied-via-mesh-baked-masks | Only "designer-graph-spirit" via `bake_runtime.py` sin/cos |
| Heightfield + erosion | Terrain at AAA quality | None |
| VDB volumes | Effects, sims, soft volumes | None |
| Splines + curve operators | Roads, branches, cables, flow fields | Implicit in some shape blocks |
| **Rig-as-geometry (KineFX/APEX)** | Skeletons + skin weights + rig logic flow through the same kernel as mesh | Rig is a separate non-procedural artifact today |
| Houdini Engine analog | Live procedural in DCC / engine | Static glb/usd export |
| Substance Smart Materials | Curvature-driven layered authoring | bake_runtime sin/cos textures |
| OpenSubDiv finishing | Film-grade smooth from low-poly cage | Absent |
| WFC modular assembly | Constraint-driven tile placement | Absent |
| L-System / branching | Organic/branching geometry | Absent |
| F-Rep / SDF authoring | Novel organic shape composition | Absent |
| CGA shape grammar | Declarative refinement assembly | Partial — `assembly_rules` exists as metadata |
| Erosion / weathering / settling | Sim-as-procedural primitive | Absent |
| MaterialX serialization | Portable surface DAG | Absent |
| USD Hydra Generative Procedural | Live procedural in USD stage | Static USD export |

### 2.12 The honest summary

The **language is enormously expressive but the procedural runtime is implementing maybe 5–10% of what it declares.** The path forward is clear and self-contained: **richer primitives + real edge-aware ops + real high-poly bake + style-driven primitive selection + real-pixel validators.** All standalone, all procedural, no AI dependencies. The Manifold kernel and trimesh between them have everything the kernel needs. The bake_runtime.py procedural wear shaders are already Substance-spirit. The geometry_detail.py density knobs are already authored. **The kernel just needs to actually USE its capabilities** (`auditor §6`).

---

## 3. Proposed Architecture

This section synthesizes the DSL architect's §3-§9 design (with addenda §3.2.1 named SOPs, §3.7+§7.7+§7.8 three-mode surface authoring, §5.1+§11.2 rig-as-geometry) and the procedural systems map's §D.11 architecture sketch into a single coherent target.

### 3.1 Architecture target (the picture)

```
.lth source (declarative DSL — already exists, expand grammar)
   ↓
AST + resolver (already exists)
   ↓
Stage pipeline (already exists)
   ↓  ←  per-stage NODE GRAPH KERNEL  (new — Houdini/Substance-class)
   ↓        operating on TYPED DATA  (mesh/points/attrs/volume/heightfield/spline/SDF/RIG)
   ↓        with VEX-STYLE EXPRESSION LANG  (new attribute mini-language)
   ↓        and HDA-STYLE ENCAPSULATION  (mature kit/library)
   ↓        named geometry-kernel ops (Sweep/Polywire/PolyExtrude/PolyBevel/Boolean/...)
   ↓
Domain libraries (vegetation / terrain / architecture / mechanism / humanoid / volume)
   ↓
F-Rep / SDF authoring primitives (new)
CGA-style assembly rules (mature assembly_rules)
WFC modular assembly (new)
Erosion / simulation passes (new)
Three-mode surface authoring (designer_graph + photo_fit + layer_stack)
   ↓
OpenSubDiv finishing pass (new optional stage)
   ↓
Package: glTF / USD / USD Hydra Generative Procedural (new option)
   ↓
Optional Lathe Engine runtime (new — HDA-class, evaluates in-engine)
```

This is what a 2026-grade declarative procedural compiler looks like, with no AI dependency (`procedural §D.11`).

### 3.2 The typed-data kernel — the meta-pivot

**Core change:** stages stop being one-mesh-per-stage. Each stage exposes a *node graph* over typed data. The current "mesh-in, mesh-out" stage signature becomes "typed-bundle in, typed-bundle out" with backwards-compatible adapters for v1 assets (`dsl §3.3, §5.1 with rig addendum`).

The TypedBundle bus carries **eight** data types with consistent attribute access:

| type | shape | attributes | typical use |
|---|---|---|---|
| `Mesh` | verts + faces + edges | per-vertex (`@P`, `@N`, `@uv`, `@skin.<bone_id>`), per-face (`@id`, `@material_zone`, `@seam_class`), per-edge (`@edge_class`, `@crease`) | the existing dominant type |
| `Points` | verts (no faces) | per-point (`@P`, `@N`, `@density`, `@scale`, `@orient`) | scatter, instance source |
| `Volume` | sparse 3D grid (VDB-style) | named channels: `@density`, `@temperature`, `@vel.x/y/z` | smoke, fluids, organic blobs |
| `Heightfield` | 2D grid + height | `@height`, `@slope`, `@flow`, `@deposition`, `@biome_id` | terrain |
| `Spline` | ordered control points | `@P`, `@tangent`, `@width`, `@twist` | paths, branches, cables, pipes |
| `SDF` | implicit equation tree | reads as `f(@P) → distance` | F-Rep authoring |
| `Image` | 2D pixel grid | RGBA + mask channels | textures, masks, decals |
| **`Rig`** (per `dsl §5.1, §11.2` addenda) | bone hierarchy + IK chains + skin weights + rig logic graph | per-bone (`@bone_id`, `@parent`, `@local_xform`, `@ik_target`); skin weights live as per-vertex attributes on the Mesh (`@skin.<bone_id>`) | rig-as-geometry; canonical anatomies, parametric morphs, animation library binding |

Cross-type operators (`mesh_to_points`, `points_to_instances`, `mesh_to_sdf`, `sdf_to_mesh`, `heightfield_to_mesh`, `spline_to_mesh`, `volume_to_mesh`, `mesh_to_heightfield`, `volume_to_points`) make the bus composable.

**Auto-derived attributes** every TypedBundle exposes lazily: `@P, @N, @curvature, @gaussian_curvature, @ao, @up_dot, @down_dot, @uv, @id, @material_zone, @seam_class, @edge_class`. These are referenceable from the attribute mini-language and from the surface graph.

**Backwards compatibility (critical).** Existing v1 sources without typed-kernel opt-in run through a thin compatibility shim. **No grammar break for old assets** (`dsl §5.4`).

**New contract ID:** `lathe.kernel.typed_bundle_v1`, opt-in via `build.shape.kernel = "lathe.shape.typed_kernel_v1"`. Stable contract `lathe.shape.intent_mesh_handoff_v1` is preserved per AGENTS.md.

### 3.3 Richer ShapeIR primitives — Activate / Real-implement / Net-new

Per `dsl §3.2` (with the post-addendum tier table), ShapeIR primitive types expand from 3 to ~25, organized in three explicit tiers:

**T1 — Activate latent capability** (kernel already supports it; only authoring sites need wiring; no new kernel code):

| Primitive | Status today | Phase | Effort |
|---|---|---|---|
| `revolved_profile` | Kernel: `lathe/exact_solids.py:103-135`, `adapters/manifold_kernel.py:168-194`. Used in 1 of 170 builders. ~50 should use it. | Phase 0 | Days |
| `sphere` | Kernel: `adapters/manifold_kernel.py:228-236`. **Zero authoring sites.** | Phase 0 | Hours (5-10 LOC + builder edits) |

**T2 — Real-implement façade** (language surface exists; kernel emission is a façade emitting boxes; replace with real implementation). Per `dsl §3.2.1` addendum, each maps to a named Houdini SOP:

| Primitive | Houdini SOP analog | Façade today | Real implementation | Phase |
|---|---|---|---|---|
| `sweep_profile` (`sweep`) | Sweep / Labs Curve Sweep | `mesh_grammar.py:283-325` emits cylinder/box | `trimesh.creation.sweep_polygon` along curve, polyline-extrude with mitering | Phase 1 |
| `lofted_solid` (`loft` / `skin`) | Loft / Skin | `mesh_grammar.py:328-367` emits N step-stacked boxes | Tapered convex hull / `trimesh.creation.extrude_polygon` with width(t)/height(t) per cross-section | Phase 1 |
| `fillet_edge` (`bevel`) | PolyBevel | `mesh_grammar.py:370-387` only updates `primitive.rounding` | Insert N edge loops parallel to hard-edge tagged seams; shift inward by `bevel_width`; weld to neighbors. Blender Bevel modifier OR pure-trimesh edge-loop insertion. | Phase 1 |
| `chamfer_edge` (`bevel`) | PolyBevel | as above | Two-segment chamfer | Phase 1 |
| `extrude_with_thickness` | PolyExtrude | partial (`_extrude_primitives` emits a box) | extrude faces with thickness, optional inset, twist, bevel | Phase 1 |
| `boolean_with_seam_group` | Boolean | partial — produces no seam group | **Critical: produce A∩B seam group on output for downstream PolyBevel.** Per `dsl §3.2.2` worked-snippet addendum: `boolean → bevel(seam_group)` is the canonical hard-surface authoring idiom. | Phase 1 |
| `panel_split` | (custom grammar) | `feature_ops.panel_seam_features` emits raised boxes | Real subtractive split lines on target face with width/depth/spacing_jitter | Phase 1-2 |
| `instance_pattern` (`scatter`) | Copy-to-Points | `feature_ops.bolt_grid_features` emits 2D-grid box cylinders | Surface-projected Poisson-disk / pattern distribution; `points_to_instances(surface_sample(face, density), part)`. **Per addendum: "the productivity multiplier" — promote in Phase 2.** | Phase 2 |
| `greeble` | Copy-to-Points + library | Implicit in feature_ops | Real surface-projected greeble kit dispatch | Phase 2 |
| `polywire_tube` | Polywire | Absent | Tube geometry around curve / wire network for scaffolding, antennas, branch skeletons | Phase 2 |
| `displaced_surface` | Per-vertex displacement | `mesh_grammar` carries intent; bake_runtime has 2D textures only | Per-face heightmap displacement modifying mesh vertices | Phase 2 |
| `remesh` | Remesh / Labs Quadrangulate | Absent in language | Uniform / adaptive remesh + Quadrangulate to target edge length | Phase 2 |
| `carve` | Carve | Absent | Extract sub-section of curve by parametric u-range | Phase 3 |

**T3 — Net-new** (new IR fields, new language surface, new emission paths, new tests; each ship-able additively):

| Primitive | Description | Phase |
|---|---|---|
| `polyhedron` | Hand-authored or library mesh chunk; format for Lego bricks, kit pieces, library imports | Phase 3 |
| `subdivision_cage` | OpenSubDiv Catmull-Clark output from low-poly cage + crease tags + level | Phase 3 |
| `sdf_blend` | Smooth boolean (IQ-style) with k-blend on SDFs | Phase 3 |
| `volume_field` | Meshed sparse volume via marching cubes / dual contouring / Faithful Contouring | Phase 3 |
| `heightfield_solid` | Heightfield extruded to mesh | Phase 3 |
| `spline_geometry` | Tube / wire / cable from spline + cross_section | Phase 3 |
| `metaball_cluster` | Metaball-blended blob | Phase 3 |
| `bezier_surface` | Bicubic / biquadratic patch | Phase 3 |
| `ffd_lattice_deform` | Free-form deformation lattice over input primitive | Phase 3 |
| `generalized_cylinder` | Radius-varying along path (organic limbs, antlers) | Phase 3 |
| `branching_l_system` | L-system geometry (branches, fractals) | Phase 3 |
| `weld_seam` | Real weld bead between two surfaces | Phase 3 |
| `rig_component` | KineFX-class rig piece: spine / limb / digit / mech_joint / wing_chain / tentacle_chain composing into a Rig typed-data artifact | Phase 4 |

The tier framework directly drives the phase ordering: T1 ships in Phase 0 (immediate), T2 in Phase 1-2 (weeks), T3 in Phase 3+ (months) (`dsl §3.2, §10.7`).

### 3.4 Style routing — style as STACK, not tag

Per `stylization §S.6.2` and `dsl §3.6`, the design pivot: **"Stylized PBR" is shorthand for: material-model + shading-model + texture-authoring-mode + outline-mode + lighting-strategy + detail-layer-composition + animation-rate + construction-grammar.** Eight axes.

```lathe
style_target stylized_pbr_aaa {
  material_model = pbr_metal_rough
  shading_model = pbr_continuous
  texture_authoring_mode = procedural_substance
  outline_mode = none
  lighting_strategy = dynamic_realtime
  detail_layer_composition = base_curvature_ao_position_storytelling
  animation_rate = fluid
  construction_grammar = free_or_kit
  pbr_chart = aaa_hero_pbr_chart
}

style_target chunky_low_poly {
  material_model = npr_flat
  shading_model = lambert_clamped_ambient
  texture_authoring_mode = vertex_color_or_quantized_palette
  outline_mode = none
  lighting_strategy = baked
  detail_layer_composition = flat
  construction_grammar = primitive_grammar_no_bevel
  no_pbr = true
  hard_normals_only = true
}

style_target anime_cel {
  material_model = npr_ramp
  shading_model = ramp_with_outline
  texture_authoring_mode = ramp_lut_face_sdf_id_mask
  outline_mode = inverted_hull_plus_post_sobel
  lighting_strategy = per_asset_light_rig
  detail_layer_composition = base_plus_masks
  construction_grammar = anatomy_grammar
  shadow_softness = 0.10
  artist_edited_normals = true
}
```

**Style bridge — explicit, named compositions.** When mixing PBR with cel ramp injection (Borderlands), or chars-cel + env-PBR (Octopath), the author *must* declare a bridge. Without an explicit `style_bridge`, the compiler refuses incompatible stacks (`dsl §6.3`).

**The primitive selector layer.** After Phase 1+2 ship, a small **primitive selector** module reads `style_target.construction_grammar` + per-component-type rules and picks the right primitive: `arcane` style → `revolved_profile` shells with carved insets; `industrial` → box+cylinder with `fillet_edge` + `panel_split` + `greeble`; `sleek_sci_fi` → `sweep_profile` fairings + `subdivision_cage` shells. **No new kernel work** — just routing that consumes the new `style_target` declaration and the existing `creative_grammar.py:9-460` style preset tables.

### 3.5 Asset class as first-class concept

Per `quality §6` and `dsl §3.1`, six distinct asset-quality classes — Hero, Mid-ground, Background, Mobile, Web, Roblox — each with hard poly/texture/material/LOD budgets.

```lathe
asset_class_profile aaa_hero {
  poly_budget { tris_max = 100000 quads_target = 0.85 ngons_max = 0 }
  texture_budget { basecolor = 4096px normal = 4096px orm = 2048px }
  texel_density { target = 1024..2048 px_per_m tolerance = 0.10 }
  uv_strategy = unique_udim
  material_count = 2..4
  lods = 4..6
  validation {
    threshold = 0.84
    silhouette_multi_angle = required
    box_stack_detector = required
    pbr_chart_compliance = required
  }
}
```

Resolver propagates `intent.asset_class` into `build.shape.target_quads`, `build.surface.resolution`, `build.optimize.lods`, `validate.threshold`, `validate.real_render.required`. Solves the auditor's `target_quads = 12000` declared but 2,412 emitted problem (`auditor §1`) by making the budget a hard contract.

### 3.6 Three-mode procedural surface authoring (Substance Designer/Sampler/Painter divide)

Per `dsl §3.7 + §7.7 + §7.8` addenda and `procedural §S.3`, surface authoring exposes three modes parallel to Substance's three apps:

**Mode 1 — `surface_program: designer_graph { ... }`** (Substance-Designer-equivalent).
Author from-scratch procedural materials via node graph composition. Default mode. Implements the canonical Substance recipe (`quality §4a`):

1. **Base Pattern** — multi-octave noise blending (Perlin + Worley + fractal).
2. **Patterns + Geometry** — bricks, tiles, weave, Shape Splatter for distributing rivets/screws.
3. **Height & Normal** — combine into height map; convert to normal.
4. **Curvature-Driven Channels** — Curvature Smooth → mask peaks (edge wear) and valleys (cavity dirt).
5. **AO + Position-Based Effects** — AO from height; world-position drives top dust / vertical streaks.
6. **Color Composition** — basecolor stack of layers gated by curvature + AO + position masks.
7. **Output** — packed PBR channels; mask set for downstream compositing.

```lathe
surface_program metal_painted_industrial_hero: designer_graph {
  inputs { @position, @normal, @uv, @curvature, @ao, @world_pos, @material_zone }
  noise base_macro { type = perlin octaves = 4 scale = 0.10 seed = 1 }
  noise base_micro { type = worley jitter = 0.6 scale = 0.005 seed = 2 }
  blend macro_micro { a = base_macro b = base_micro mode = overlay factor = 0.30 }
  ...
  layer base_paint { base_color = palette.lookup(0.4, industrial_paint_palette) ... }
  layer edge_wear_paint_chip {
    mask = mask.curvature_peaks(0.35)
    base_color = palette.lookup(0.85, exposed_metal_palette)
    roughness = 0.35
    metallic = 0.85
  }
  layer cavity_grime { mask = mask.ao_below(0.55) base_color_modulate = darken(0.30) }
  layer top_dust { mask = mask.world_up_facing(30deg) & mask.ao_below(0.80) ... }
  output { base_color = layered_basecolor normal = surface_normal orm = pack(...) }
}
```

**Mode 2 — `surface_program: photo_fit { reference: <path>, ... }`** (Substance-Sampler-equivalent).
Per `dsl §7.7` addendum. Fit a PBR set from a reference photo deterministically — palette extraction + frequency analysis + tile-fitting. **No learned model** per the standalone-procedural mandate. T2 win; ships under the existing `surface_graph` contract as a mode tag. Could ship in Phase 2 for stylized-PBR assets with reference photo inputs:

```lathe
surface_program weathered_concrete_courtyard: photo_fit {
  reference = "refs/concrete_courtyard.jpg"
  tile_strategy = wang_tile
  palette_quantize = 8
  frequency_separation = 3
  output { base_color, normal, orm }
}
```

**Mode 3 — `surface_program: layer_stack { ... applied via mask_program }`** (Substance-Painter-equivalent).
Per `dsl §7.8` addendum. Composite materials with mesh-aware masks — generators + filters work *per-mesh* via baked maps. T2.

```lathe
surface_program ornate_armor_layered: layer_stack {
  base = material_primitive.metal_steel
  apply_via mask_program.cavity_mask {
    layer cavity_grime { ... }
  }
  apply_via mask_program.edge_wear_mask {
    layer paint_chip { material = material_primitive.exposed_metal }
  }
  apply_via decal_library.heraldry {
    layer crest { ... }
  }
}
```

**Smart Mask library (built-in, ships in `std/masks/`).** `cavity_mask`, `edge_wear_mask`, `top_dirt_mask`, `bottom_grime_mask`, `slope_mask(t)`, `seam_mask`, `decal_zone_mask`.

**Material primitives library** ships in `std/materials/`: `metal_steel`, `dielectric_painted_plastic`, `wood_oak`, `fabric_felt`, `rubber_extruded`. Each carries physically-plausible PBR defaults; PBR violations rejected at validation.

**MaterialX serialization.** All three modes terminate in MaterialX as the portable surface DAG serialization standard. Downstream tools (Blender Cycles, USD Hydra, Unreal MaterialX importer) consume directly.

**Output spec is fixed** (always emits): `{base_color, normal, metallic, roughness, height, ao, emissive, opacity}` — per-channel resolutions tunable.

### 3.7 Pattern libraries → HDA-class

Per `procedural §A.1, §D.1` and `dsl §3.8`, the existing V1.1 `kit`, `library`, `mechanism` blocks mature to HDA semantics:

```lathe
kit hard_surface_industrial_v3 : kit {
  version = "3.1.0"
  ports {
    input mount_face : face_ref
    input style : style_target_ref
    input density : float (default = 0.30, range = 0.0..1.0)
    output instances : points
    output mask : image
  }
  parameters {
    rivet_size : length = 3mm range 1mm..6mm
    panel_seam_density : float = 0.5 range 0.0..1.0
    bolt_pattern : enum [grid, ring, scatter] = scatter
  }
  body {
    let surface_pts = surface_sample(face: ports.mount_face,
                                      density: ports.density,
                                      seed: ports.seed)
    instance_pattern(  // = scatter / Copy-to-Points
      points = surface_pts,
      instance = polyhedron(library.parts.rivet_brass_size(parameters.rivet_size)),
      align_to = surface_normal,
    )
    output ports.instances = surface_pts
  }
}
```

**HDA-class semantics:** explicit ports (typed inputs/outputs), parameter UI specs (typed parameters with default + range), version pinning, composability, tested.

### 3.8 CGA-style assembly_rules

Per `procedural §D.4` and `dsl §3.9`:

```lathe
assembly_rules HumanoidWithGear {
  Root --> Body, Head, Arms, Legs, Gear
  Body --> torso, hips
  Arms --> repeat(2, mirror: x) { Arm }
  Arm --> shoulder, upper_arm, elbow, forearm, hand
  Hand --> palm, repeat(5) { Finger }
}
```

Operators: `-->`, `split(axis) { a, b, c }`, `repeat(n) { ... mirror, rotate, pattern }`, `chooseOne { p1: a, ... }`, `extrude`, `translate/rotate/scale`. Existing `assembly_kernel.py` component-builders become *the implementations of the terminals* — the grammar layer above them organizes parts.

### 3.9 WFC modular assembly

Per `procedural §A.11, §D.5` and `dsl §3.10`:

```lathe
wfc_tileset dungeon_pieces_v1 {
  tiles { floor, wall, door, corner_inner, corner_outer, pillar, chest_alcove }
  connectors { ... }
}
asset dungeon_room: env_module uses mid_ground {
  geometry {
    wfc {
      tileset = dungeon_pieces_v1
      adjacency = dungeon_adj_v1
      grid_size = (10, 1, 10)
      seed = 19
    }
  }
}
```

### 3.10 SDF / F-Rep authoring

Per `procedural §A.5, §D.6` and `dsl §3.12`:

```lathe
geometry {
  f_rep {
    let body = sphere(r: 0.5m).smooth_subtract(sphere(r: 0.4m), k: 5cm)
    let arms = repeat(4, axis: z) { box(extents: (0.30m, 0.05m, 0.05m)).translate((0.40m, 0, 0)) }
    let combined = body.smooth_union(arms, k: 2cm)
    result = combined.displaced(noise(scale: 0.10, amp: 1cm))
    extraction = faithful_contouring  // CVPR'26
    voxel_size = 2mm
  }
}
```

### 3.11 OpenSubDiv finishing

Per `procedural §A.9, §D.7` and `dsl §3.11`:

```lathe
geometry {
  subdivision {
    cage = polyhedron(verts = [...], faces = [...])
    levels = 2
    creases = [edge_set(name: "spine", crease: 0.8)]
    boundary_rule = always_sharp
    scheme = catmull_clark
  }
}
```

### 3.12 Erosion / weathering / settling

Per `procedural §A.4, §D.8` and `dsl §3.13, §3.14`:

```lathe
terrain_program eroded_canyon {
  base = rolling_terrain
  passes = [
    simulate_hydraulic_erosion(iterations: 80, droplet_count: 5_000_000, ...),
    simulate_thermal_erosion(iterations: 30, angle_of_repose: 35deg),
  ]
  outputs = [@height, @flow, @deposition, @slope]
}
```

For asset weathering: deterministic procedural recipes (`weathering_pass(age_years: 80, environment: indoor_dry)` deterministically rounds edges + adds dirt accumulation in cavities + adds small dent noise).

### 3.13 Validators that read pixels

Per `auditor §4` and `dsl §9`:

**Real-render validators:** `silhouette_multi_angle`, `frequency_energy`, `edge_density_variance`, `curvature_distribution`.

**Topological validators (mesh-domain, fast):** `box_stack_detector`, `topology_class_compliance`, `texel_density_consistency`.

**Style validators:** `style_stack_compatibility`, `pbr_chart_compliance`.

**High-low bake validator:** `highlow_authentic` — high tri count > 5x low tri count; high carries detail (sub-millimeter displacement, edge bevels) the low does not. Mandatory for `aaa_hero` class.

### 3.14 Rig-as-geometry (KineFX/APEX position)

Per `dsl §5.1 + §11.2` addenda and `procedural §S.1`. Lathe should treat **rig as procedural geometry**, not a separate domain. The Houdini KineFX/APEX position adopted: skeletons + skin weights + rig logic flow through the same kernel as mesh / attrs / masks.

A Lathe `parametric_rig` block composes from named **rig components** (`spine`, `limb`, `digit`, `mech_joint`, `wing_chain`, `tentacle_chain`) and produces skeleton + skin weight as a *typed-data artifact* — the eighth slot in TypedBundle. Skin weights are per-vertex attributes (`@skin.<bone_id>`) on the Mesh. **No learned characters required.**

```lathe
parametric_rig humanoid_combat_rig_v1 {
  base = humanoid_anatomy.adult_male_realistic
  components = [
    rig_component.spine(segments: 5),
    rig_component.limb(side: left, segments: 4),
    rig_component.limb(side: right, segments: 4),
    repeat(5) { rig_component.digit(side: left, segments: 3) },
    repeat(5) { rig_component.digit(side: right, segments: 3) },
  ]
  ik_chains { arm_l, arm_r, leg_l, leg_r, spine }
  animation_library { combat_idle, combat_walk, combat_run, ... }
  retargeting = canonical_to_canonical_v1
}
```

Phase 4 territory; the framing is forward-compatible vocabulary for v0.2/v0.3.

### 3.15 USD Hydra Generative Procedural target

Per `procedural §A.16, §D.9`, `UsdHydraGenerativeProceduralAPI` is the standardized way to declare a procedural in a USD stage. Lathe's package stage already targets USD; the next move is to emit live procedurals (as opt-in), so Lathe-compiled assets can remain procedural in DCCs that consume them.

---

## 4. Phase 0 — "Stop the Bleeding" (1 week)

Phase 0 is the highest-ROI, lowest-risk batch. Single-PR scope each; narrow blast radius; immediate visible improvement on hero assets; **no contract migration**. All items align with the auditor's pass-2 §8 "Days" tier.

### 4.1 Replace the box-rewarding validator formula

**File:** `lathe/render_eval.py`, line 99
**Current code:**
```python
primitive_penalty = max(0.0, min(1.0, (bbox_area / max(1.0, area) - 1.0) / 2.0))
```
**Replacement:**
```python
import math
primitive_penalty = 1.0 - (4.0 * math.pi * area / (perimeter ** 2 + 1e-9))
```
**Rationale.** Isoperimetric ratio: circles 0.0 (perfect compactness, irregular silhouette = 1.0); squares 0.215; hexagons 0.10; irregular silhouettes 0.40-0.85. Single-line change, no new dependencies, immediately stops rewarding cubes (`auditor §7 #9, §8 Days; dsl §9.6`).

**Tests required.**
- New `tests/test_render_eval_isoperim.py` — cube silhouette penalty ≥ 0.20, sphere silhouette ≤ 0.05, real chest silhouette ≥ 0.40.
- Re-baseline existing render_eval tests; document re-baselined values referencing this fix.

### 4.2 Promote diagnostic warnings to blockers

**File:** `lathe/validators/visual_quality.py`
**Action.** Promote these warnings to threshold blockers under hero/aaa_hero asset class:
- `random_triangulation_penalty` (currently 0.461 for chest)
- `highlow_fake_detail_penalty` (currently 0.500)
- `geometry_dihedral_continuity` (currently 0.546)
- `geometry_stair_step_penalty` (currently 0.417)
- `boolean_scar_penalty` (currently 0.386)

Add `quality_diagnostics_threshold = 0.55` blocking gate on hero builds.

### 4.3 Deploy `revolved_profile` across ~50 component builders

**Files.** `lathe/assembly_kernel.py`, ~50 builder sites (`auditor §7 #1`):

```
chest legs (lines around 253-264)
sword pommels (609)
hinges/hinge barrels (192-212)
finials (1499)
domes (1036)
arches (1094)
columns (1334)
mast cores (1607, 1738, 1776)
valve wheels (2069)
transformer caps (3262)
oxygen tanks (3358)
pipes/turret pintles (3504)
gear/cog cores (3545, 3593, 3636)
treadmill rollers (3669)
balcony posts (3727)
furnace caps (3863)
crane jib pivots (4044)
turbine cores (4163, 4205, 4259)
piston caps (4485)
... and ~25 more
```

**Pattern.** For each site that today emits `_box(...)` or `_cylinder(...)` for a shape that's actually radially symmetric, replace with `ShapePrimitive(primitive_type="revolved_profile", profile_points=[...], axis="y", ...)`.

**Effort.** ~50 builders × ~30 min each = ~25 hours focused work. Single PR per ~10 builders.

**Tests.** Each migrated builder gets a regression test asserting emitted primitive_type is `revolved_profile`.

### 4.4 Add `sphere` primitive to ShapeIR

**Files.**
- `lathe/shape_ir.py:14-37` — extend `ShapePrimitive.primitive_type` enum with `"sphere"`.
- `lathe/exact_solids.py` — add `_sphere_mesh(radius, center)` builder using `trimesh.creation.icosphere(subdivisions=2)`.
- `lathe/adapters/manifold_kernel.py:227-236` — already supports it; expose via mesh path.
- `lathe/assembly_kernel.py` — add 5-10 builder sites (ball-finial, jewel, bulb, spheroidal pod, beacon, drone payload bay).

**Effort.** 5-10 LOC for IR + builder; 2-5 builder sites = ~4 hours.

### 4.5 Wire `target_quads` to a real Decimate fallback

**File.** `lathe/optimize.py`.
**Action.** When `build.shape.target_quads` is declared and emitted mesh exceeds it by >2×, run trimesh `simplify_quadric_decimation` to target. Also wire to the Blender Decimate modifier when alive.

### 4.6 Ship a real high-poly source for hero builds

**Files.** `lathe/scaffold_compiler.py:302-439`; new `_runtime_high_poly_from_shape_ir()`. `lathe/highlow.py` (32 LOC dataclass; needs a builder).

**Pattern.** When `intent.asset_class = aaa_hero`, the shape stage emits TWO meshes:
1. `lod_high` — same blueprint, with `subdivisions: 2`, `bevel_segments: 4`, `displacement-from-surface-program`.
2. `lod_runtime` — decimated retopo of the high mesh, target_quads enforced.

**Phase 0 minimal scope.** Land `lod_high = decimate(low) + subsurf level 1` (Blender alive) or `trimesh.loop_subdivide(level=1)` (Blender absent).

**Tests.** Hero asset emits `is_real_highlow = True`; `high_triangle_count > 5 × low_triangle_count`.

### 4.7 Wire style packs to drive primitive selection (minimal seed)

**File.** New module `lathe/primitive_selector.py`. Touches `lathe/assembly_kernel.py:_component_primitives:4781-4784`.

For Phase 0, only deploy rules where the target primitive already exists (revolved_profile, sphere). Sweep / loft / fillet rules slot into the same dispatch when those land in Phase 1.

```python
PRIMITIVE_RULES = {
    "shell": {
        "arcane": "revolved_profile",
        "default": "box",
    },
    "dome": {"any": "revolved_profile"},  # always revolved
    "arch": {"any": "revolved_profile"},  # always revolved
    ...
}
```

### 4.8 Mark AI providers `experimental_external`

**Files.**
- `lathe/asset_graph.py:1895-1909` — flip `self_reliant_target` default to `true`.
- `lathe/codex_imagegen_bridge.py` — annotate.
- `lathe/providers/adapters/hunyuan.py`, `vggt.py`, `reference_conditioned.py` — annotate.

### 4.9 Phase 0 deliverable summary

| Item | Effort | File:Line | Risk | Visible improvement |
|---|---|---|---|---|
| Replace primitive_penalty formula | 1 day | `lathe/render_eval.py:99` | Low (re-baselining) | Validators stop rewarding cubes |
| Promote diagnostic warnings | 1 day | `lathe/validators/visual_quality.py` | Low | Hero builds reject random triangulation |
| Deploy `revolved_profile` × 50 sites | 25 hours | `lathe/assembly_kernel.py` × 50 | Low | Domes are domes, pommels are orbs |
| Add `sphere` primitive | 4 hours | `shape_ir.py`, `exact_solids.py`, builders × 5-10 | Low | Finials are spheres |
| Wire `target_quads` to decimate | 1 day | `lathe/optimize.py` | Low | Mesh hits declared budget |
| Real high-poly source (minimal) | 2-3 days | `scaffold_compiler.py`, `highlow.py` | Medium | Real bakes possible |
| Primitive selector seed | 3 days | new `primitive_selector.py` | Low | Style packs influence primitives |
| Mark AI providers experimental | 1 day | trace + asset_graph | Low | Standalone discipline signaled |

**Total Phase 0 effort:** ~5-7 days; 1-2 weeks calendar with testing/review.

**User-visible milestone.** Brassbound chest's score drops below 0.84. The auto_until_pass repair loop runs for the first time. Domes are domes. Sword pommels are orbs.

---

## 5. Phase 1 — "Real Geometry Kernel" (4–6 weeks)

Phase 1 ships the T2 (Real-implement) primitives. Per `dsl §3.2.1` addendum, each maps to a named Houdini SOP — the vocabulary AAA pipelines speak.

### 5.1 The canonical hard-surface idiom: `boolean → bevel(seam_group)`

**Per `dsl §3.2.2` addendum, this is the most visible "before/after" in box-stack-to-hard-surface terms.** Boolean produces an A∩B seam group; PolyBevel consumes it. Chaining `boolean → bevel(seam_group)` is the canonical hard-surface authoring idiom.

```lathe
mesh_program {
  // Subtract a panel-cutout from the body; capture the seam edges
  let body = box(extents: (40cm, 30cm, 25cm))
  let cutout = box(extents: (35cm, 25cm, 5cm)).translate((0, 0, 12cm))
  let result = boolean(
    op: subtract,
    a: body,
    b: cutout,
    seam_group: "panel_cut_seam",  // tag the resulting A∩B edges
  )
  // Bevel the resulting seam edges (real bevel-loop, not corner-rounding)
  fillet_edge(target: result, edge_class: "panel_cut_seam", radius: 2mm, segments: 3)
}
```

**This single idiom is what Phase 1 should demonstrate first.** The first hero asset converted to `typed_kernel_v1` should use this chain.

### 5.2 Real edge-aligned bevel and chamfer (PolyBevel)

**Files.**
- `lathe/mesh_grammar.py:370-387` — `_apply_edge_modifier` becomes the dispatcher.
- New `lathe/exact_solids.py:_bevel_edge_loop_insertion(mesh, edge_class, width, segments)` — pure trimesh path.
- `scripts/blender_topology_adapter.py` — add Blender Bevel modifier with `width_type='OFFSET'`, `segments=N`, `angle_limit=30°`, hard-edge tag-driven Edge Marks.
- New `lathe/feature_ops/bevel_real.py`.

**Risk.** Bevel can break watertightness on complex booleans. Mitigation: when bevel breaks watertight, fall back to corner-rounding at the offending vertices and emit a diagnostic.

### 5.3 Real swept profile along curve (Sweep / Labs Curve Sweep)

**Files.**
- `lathe/mesh_grammar.py:283-325` — `_sweep_primitives` rewritten.
- New `lathe/exact_solids.py:_swept_profile_mesh(profile, path_points, twist=None, scale_curve=None)` using `trimesh.creation.sweep_polygon`.
- New language surface in `grammar/lathe.lark` for spline definitions.

### 5.4 Real lofted solid (Loft / Skin)

**Files.**
- `lathe/mesh_grammar.py:328-367` — `_loft_primitives` rewritten using `trimesh.creation.extrude_polygon` along path with width(t)/height(t) per cross-section.

### 5.5 Boolean with seam group (Boolean SOP analog)

**Files.**
- New `lathe/exact_solids.py:_boolean_with_seam_group(a, b, op, seam_group_name)` — runs the boolean and tags the resulting A∩B edges with `@edge_class = seam_group_name` for downstream `fillet_edge` / `chamfer_edge`.
- Existing `manifold3d` boolean is already used; extend to record edge groups in the output mesh.

**This is the linchpin** of real hard-surface authoring per addendum.

### 5.6 Replace 60-line Blender adapter with real geometry pipeline

**File.** `scripts/blender_topology_adapter.py` (currently 60 LOC: `remove_doubles + triangulate + recalc_normals`).
**New script:** `scripts/blender_geometry_pipeline.py`.

**Pipeline:**
1. Subdivision Surface modifier (level 1-2 on hero shells/lids/doors).
2. Bevel modifier (with `Hard Edge` tag-driven Edge Marks).
3. Decimate modifier to `target_quads`.
4. Optional GeometryNodes pass for surface-projected greebles.

### 5.7 Wire `asset_quality/shape_ir_v2.py` 30 semantic ops to real emission

**File.** `lathe/asset_quality/shape_ir_v2.py` (currently 30 advertised ops: `solid.prism`, `solid.rail`, `solid.panel`, `op.cut_panel_line`, `op.fastener_grid`, `op.vent_slats`, `op.trim_band`, `op.corner_guard_set`, etc.).

**Action.** Each of the 30 ops becomes a `mesh_program` op (per dsl §3.2). The IR vocabulary already aligns with the design's typed primitives.

### 5.8 Asset class profile + style target as first-class

**Files.**
- `grammar/lathe.lark` — add `asset_class_profile_decl`, `style_target_decl`, `style_bridge_decl`, `style_inline_block`.
- `lathe/normalizer.py` — add `asset_class_profiles`, `style_targets`, `style_bridges` to top-level mappings.
- `lathe/resolver.py` — propagate `intent.asset_class` into build directives. Propagate `style.target` into `intent.style_stack`.
- `lathe/checker.py` — add `style_stack_compatibility` check.
- `schema/lathe.schema.json` — register new declaration shapes.

### 5.9 Real-render validators (silhouette_multi_angle + box_stack_detector)

**Files.**
- New `lathe/validators/silhouette_multi_angle.py`.
- New `lathe/validators/box_stack_detector.py`.
- New `lathe/validators/render_eval_v2.py`.

**box_stack_detector algorithm.** Mesh-domain, fast:
```python
score = 1.0 - clamp(
    0.4 * (axis_aligned_face_pct > 0.85)
  + 0.4 * (unique_normals < 8)
  + 0.2 * (bbox_fill > 0.85),
    0, 1
)
```
Hard reject if score < 0.5. Runs first; fail fast without expensive renderers.

### 5.10 Phase 1 deliverables

| Capability | Files | Effort | Risk |
|---|---|---|---|
| **`boolean → bevel(seam_group)` chain (KEY DEMO)** | `exact_solids.py:_boolean_with_seam_group`, bevel | 1-2 weeks | Medium (manifold) |
| Real edge-aligned bevel/chamfer | `mesh_grammar.py:370-387`, `exact_solids.py`, `blender_topology_adapter.py` | 2-3 weeks | Medium |
| Real swept profile (Sweep) | `mesh_grammar.py:283-325`, `exact_solids.py` | 1-2 weeks | Low |
| Real lofted solid (Loft) | `mesh_grammar.py:328-367` | 1 week | Low |
| Blender geometry pipeline | `scripts/blender_geometry_pipeline.py` | 2 weeks | Medium |
| shape_ir_v2 wiring | `asset_quality/shape_ir_v2.py` | 2-3 weeks | Low |
| Asset class + style target | grammar + normalizer + resolver + checker | 1-2 weeks | Low |
| silhouette_multi_angle validator | `validators/silhouette_multi_angle.py` | 1-2 weeks | Medium (renderer dep) |
| box_stack_detector | `validators/box_stack_detector.py` | 1 week | Low |

**Total Phase 1 effort:** ~10-14 weeks of 1-engineer scope; ~5-7 weeks at 2-engineer.

**Migration safety.** All work additive under v1 contract. Stable shape contract `lathe.shape.intent_mesh_handoff_v1` preserved.

**User-visible milestone.** Brassbound chest under typed_kernel_v1 emits real beveled body, lofted lid, swept handles, instanced rivets, real high-poly bake. **Bands A and D production-viable for hard-surface props.**

---

## 6. Phase 2 — "Style Routing + Procedural Surfaces" (3–4 months)

Phase 2 ships the T3 surface-authoring contract (with three modes) and the style-routing depth.

### 6.1 Three-mode procedural surface authoring

**Files.**
- New `lathe/surface_graph/__init__.py` — graph dataclass + serialization.
- New `lathe/surface_graph/designer_graph_evaluator.py` — built-in deterministic evaluator (Mode 1).
- New `lathe/surface_graph/photo_fit.py` — palette extraction + frequency analysis + tile-fitting (Mode 2; T2 win).
- New `lathe/surface_graph/layer_stack_evaluator.py` — Painter-style layer compositing (Mode 3).
- New `lathe/surface_graph/materialx_emitter.py` — MaterialX export for all three modes.
- `lathe/bake_runtime.py` — refactor existing curvature-aware patterns into `surface_graph` nodes.

**Per addendum (`dsl §7.7, §7.8`):** `photo_fit` mode is a **relatively-cheap T2 win** — deterministic image processing, no learned model. Could ship alongside Phase 1 work.

**Effort.** 6-8 weeks Mode 1 + 2-3 weeks Mode 2 (T2) + 3-4 weeks Mode 3.

### 6.2 Attribute mini-language

**Files.**
- New `lathe/attr_lang/__init__.py` — parser, AST, evaluator.
- `grammar/lathe.lark` — add `attr_expr` productions.

**Design constraints.** No loops, recursion, I/O. Pure. Statically typed. Auto-derived signals always available (`@P, @N, @curvature, @ao, @height, @up_dot, @id, @material_zone, @uv, @world_pos`). Built-ins (`noise, worley, voronoi, ramp, palette.lookup, mask.*`).

### 6.3 HDA-class kit semantics

**Files.**
- `grammar/lathe.lark` — add `ports_block`, `parameters_block`, `body_block`.
- `lathe/normalizer.py`, `resolver.py`, `checker.py` — version compatibility, cycle detection.

### 6.4 Promote `scatter` (Copy-to-Points) per addendum

Per `dsl §S.2 productivity-multiplier note`, even at T2 `scatter` (= Copy-to-Points = `instance_pattern` in Lathe terms) **pays back hugely** — greebles, rivets, vegetation tufts all become one-line attribute-driven instancing. Promote in Phase 2 alongside surface_graph.

```lathe
features {
  greeble_scatter: scatter {
    target = "body_shell.front_face"
    library = hard_surface_kit_v3
    density = 0.30
    scale_range = 0.7..1.3
    align_to = surface_normal
    seed = 19
  }
}
```

### 6.5 Real-render validator suite (production)

**Files.**
- `lathe/validators/render_eval_v2.py` — replaces Phase 1 stub.
- `lathe/validators/frequency_energy.py` — FFT energy per channel per view.
- `lathe/validators/edge_density_variance.py` — Sobel + variance.
- `lathe/validators/curvature_distribution.py` — vertex curvature histogram.
- `lathe/validators/pbr_chart_compliance.py` — per-pixel chart enforcement.
- `lathe/validators/highlow_authentic.py` — high vs low mesh validity.
- `lathe/validators/style_stack_compatibility.py` — refuse incompatible stacks.
- `lathe/validators/topology_class_compliance.py` — quads, n-gons, poles.
- `lathe/validators/texel_density_consistency.py` — TD variance and shell padding.

### 6.6 Style stack routing per stage

Each stage entry-point reads `intent.style_stack.<axis>` and dispatches:
- `lathe/scaffold_compiler.py` — picks free / strict-grammar / anatomy-grammar path.
- `lathe/topology.py` — runs face-normal-bias for anime_cel.
- `lathe/uv.py` — vertex_color path skips UV unwrap; aaa_hero picks unique_udim.
- `lathe/surface_graph/` — picks designer_graph / photo_fit / layer_stack.
- `lathe/validators/preview_render.py` — runs inverted-hull pass for anime_cel; runs Sobel post for borderlands_pbr_cel bridge.

### 6.7 Phase 2 deliverables

| Capability | Files | Effort | Risk |
|---|---|---|---|
| Three-mode surface graph (designer / photo_fit / layer_stack) | `surface_graph/` | 11-15 weeks | Medium (MaterialX + image processing) |
| Attribute mini-language | `attr_lang/`, grammar | 3-4 weeks | Low |
| HDA-class kit semantics | grammar + normalizer + resolver + checker | 3-4 weeks | Low |
| `scatter` productivity-multiplier promotion | `instance_pattern` upgrade | 2 weeks | Low |
| Full real-render validator suite | `validators/render_eval_v2.py`, etc. | 6-8 weeks | Medium |
| Style stack per-stage routing | each stage entry-point | 4 weeks | Low |

**Total Phase 2 effort:** ~3-4 months at 2-engineer.

**User-visible milestone.** Authors declare `style.target = stylized_pbr_aaa` + write a `surface_program: designer_graph { ... }` block. Compiler emits MaterialX evaluated at 4K. Brassbound chest reads as actual aged brass + oak grain + velvet lining + crest decals. PBR chart compliance is a gate. Style stack incompatibility refused. **Band D production-viable for hard-surface and stylized props.**

---

## 7. Phase 3 — "Domain Libraries + Simulation" (6–9 months)

Phase 3 ships T3 net-new primitives and the domain-library investment.

### 7.1 SpeedTree-class vegetation library

Per `procedural §A.3, §D.3, §S.4`. Existence proof: SpeedTree credits include Avatar (2009), Witcher 1/2/3, Destiny, Far Cry Primal, Batman: Arkham Knight, "well over 1,000 games" since Avatar.

**Files.** New `lathe/std/vegetation/`. Phase 3 ships ~10 species: oak, pine, willow, palm, birch, fern, grass_temperate, grass_tropical, ivy, moss.

```lathe
vegetation_species oak_tree_v1 {
  trunk { base_radius = 30..60cm base_height = 1.5..2.5m taper = 0.7 ... }
  branches { iteration_count = 3..5 productions = [...] }
  leaves { leaf_card = oak_leaf_card_v1 cluster_density = 0.8 ... }
  wind_program { ... }
  growth_phases = [seedling, sapling, young, mature, ancient]
  lod_pyramid = auto
}
```

**Effort.** 8-12 weeks.

### 7.2 Terrain + erosion primitives

Per `procedural §A.4, §D.8`. Heightfield as first-class data type (with `@height, @slope, @flow, @deposition, @biome_id` attributes). Hydraulic erosion (Tu-Pham droplet, deterministic CPU). Thermal erosion. Outputs masks usable by `surface_graph` directly.

**Effort.** 6-8 weeks.

### 7.3 WFC modular assembly

Per `procedural §A.11, §D.5`. Failure raises hard error with deterministic seed-search hint.

**Effort.** 4-6 weeks.

### 7.4 CGA-style assembly_rules

Per `procedural §A.6, §D.4`. Operators: `-->`, `split`, `repeat`, `chooseOne`, `extrude`. Existing `assembly_kernel.py` component-builders become the implementations of the terminals.

**Effort.** 4-6 weeks.

### 7.5 OpenSubDiv finishing

Per `procedural §A.9, §D.7`. Catmull-Clark + Loop schemes. Boundary rules + creases. Reference runtime ships a CPU Catmull-Clark; OpenSubDiv backend opt-in.

**Effort.** 4-6 weeks.

### 7.6 F-Rep / SDF authoring

Per `procedural §A.5, §D.6`. IQ-style algebra. Reference runtime evaluates SDFs by built-in Python evaluator (deterministic), Numpy/Numba-accelerated voxel evaluator, optional GPU shader. Extraction picks marching cubes / dual contouring / Faithful Contouring (CVPR'26).

**Effort.** 6-8 weeks.

### 7.7 Real `instance_pattern` surface-projected greebles

Per `auditor §7 #12`. Take a face, sample N points by Poisson-disk distribution, project a parametric "greeble kit" (cylinder bolt cap + recessed Phillips-head + washer = 3 small primitives) onto each point.

**Effort.** 3-4 weeks (if not already advanced in Phase 2).

### 7.8 Volume primitives

Per `procedural §A.10`. Volume / VDB as first-class data type. Effects-class assets (fire, smoke, magic, fluids).

**Effort.** 6-8 weeks. Lower priority; effects typically engine-side.

### 7.9 Phase 3 deliverables

| Capability | Effort | Style band unlocked |
|---|---|---|
| Vegetation library | 8-12 weeks | Bands A, D, E (env content) |
| Terrain + erosion | 6-8 weeks | All bands (env) |
| WFC modular assembly | 4-6 weeks | Band D, F (modular content) |
| CGA assembly_rules | 4-6 weeks | All bands |
| OpenSubDiv finishing | 4-6 weeks | Bands C, D, E |
| F-Rep / SDF authoring | 6-8 weeks | Bands D, E (organic) |
| Real instance_pattern | 3-4 weeks | All bands |
| Volume primitives | 6-8 weeks | All bands (FX) |

**Total Phase 3 effort:** ~6-9 months at 2-3 engineer scope.

**User-visible milestone.** Authors ship procedural oak trees, eroded canyons, WFC dungeons, SDF alien creatures. **Bands A, D, F production-viable; Band E hard-surface and natural-environment viable.**

---

## 8. Phase 4 — "Organic + Animation Forward Vocabulary" (12–18 months horizon)

Phase 4 addresses the currently-out-of-scope organic capabilities. **Per the rig-as-geometry addendum, rig becomes the eighth typed-data slot in TypedBundle** — not a separate non-procedural artifact.

### 8.1 Parametric humanoid anatomy

Per `dsl §11.1, §11.2` and `procedural §A.13-A.14, §S.1`:

```lathe
humanoid_anatomy adult_male_realistic {
  topology = canonical_topology_humanoid_v1
  proportions {
    head_heights = 7.5
    shoulder_width_to_head = 2.2
    arm_length_to_body = 0.42
    leg_length_to_body = 0.50
  }
  morph_targets {
    body_mass : float = 0.5 range 0..1
    muscle_definition : float = 0.5 range 0..1
    height_offset : length = 0mm range -150mm..+150mm
    head_size : float = 1.0 range 0.85..1.15
    // 50+ morphs
  }
  bones { root, hip, spine_01-03, neck, head, clavicle_l/r, shoulder_l/r, ... }
  skinning_method = dual_quaternion
}
```

**Phase 4 initial scope:** ship 4 base anatomies — adult_male_realistic, adult_female_realistic, child_realistic, chibi_3head. Each ~50 morph targets.

**Effort.** 6-9 months.

### 8.2 Parametric rigs as geometry (KineFX/APEX position)

Per `dsl §5.1, §11.2` addenda. **Critical insight:** Lathe should treat **rig as procedural geometry**. A Lathe `parametric_rig` block composes from named rig components (`spine`, `limb`, `digit`, `mech_joint`, `wing_chain`, `tentacle_chain`) and produces skeleton + skin weight as a *typed-data artifact* (the eighth TypedBundle slot).

```lathe
parametric_rig humanoid_combat_rig_v1 {
  base = humanoid_anatomy.adult_male_realistic
  components = [
    rig_component.spine(segments: 5),
    rig_component.limb(side: left, segments: 4),
    ...
  ]
  ik_chains { arm_l, arm_r, leg_l, leg_r, spine }
  animation_library { combat_idle, combat_walk, combat_run, ... }
  retargeting = canonical_to_canonical_v1
}
```

**Effort.** 4-6 months on top of anatomy.

### 8.3 Cloth / hair / fluids forward vocabulary

Outline only:
- **Cloth.** A `cloth_program` declaration with mass, stiffness, damping; deterministic XPBD-style settling pass for static cloth. Dynamic cloth is engine-side.
- **Hair.** A `hair_program` declaration with strand grammar (root density, length distribution, wave amplitude/freq, color gradient). Cards or strands per asset_class.
- **Fluids.** Volume primitives suffice for asset-level smoke / fire / water surfaces.

### 8.4 Phase 4 deliverables

| Capability | Effort | Style band unlocked |
|---|---|---|
| Parametric humanoid anatomy | 6-9 months | Band B characters; Band D characters |
| Parametric rigs (rig-as-geometry) | 4-6 months | Animated content across all bands |
| Cloth forward vocab (static) | 3-4 months | All bands |
| Hair forward vocab | 3-4 months | All bands |

**Total Phase 4 effort:** ~12-18 months at 2-3 engineer scope.

**User-visible milestone.** Authors declare `asset hero_paladin: humanoid` with morph targets. Animation library + parametric rig produce animated assets. **Band B production-viable.**

---

## 9. Phase 5 — "Lathe Engine Runtime" (18–36 months horizon)

Per `procedural §D.11, §S.5`. **Three precedents:** Substance .sbsar pattern (engine re-evaluates with parameter overrides at load-time); Houdini Engine pattern (HDAs run inside Unity/Unreal/Maya as live procedural nodes); **Frostbite SDF-at-runtime pattern (BF6 REDSEC ships SDF destruction at runtime).**

**The standalone-procedural mandate doesn't preclude shipping live procedurals; it precludes runtime AI dependencies.** Substance Engine + Houdini Engine + Frostbite SDF are the closest commercial precedents.

### 9.1 Runtime targets

| Target | Format | Re-evaluation | Use case |
|---|---|---|---|
| **Unity Lathe Plugin** | `.lathe.bundle` | At engine load + parameter override | Per-asset variation in Unity |
| **Unreal Lathe Plugin** | as above | as above | Per-asset variation in UE |
| **USD Hydra Generative Procedural** | live procedural in USD stage via `UsdHydraGenerativeProceduralAPI` | At stage load | DCC interop |

**The .lathe.bundle format** carries: HDA-class kit definitions (compiled), parameter set with default values + ranges, compiled MaterialX surface graphs, LOD definitions.

### 9.2 Phase 5 deliverables

| Capability | Effort | Risk |
|---|---|---|
| `.lathe.bundle` format spec + compiler | 4-6 months | Medium |
| Unity Lathe Plugin (live evaluation) | 6-9 months | High |
| Unreal Lathe Plugin | 6-9 months | High |
| USD Hydra Generative Procedural emitter | 3-4 months | Medium |

**Total Phase 5 effort:** ~18-36 months.

**Strategic value.** Each engine plugin is a distribution channel — the pattern that made Substance Designer a $20M-revenue tool, generalized.

---

## 10. Per-phase deliverables matrix

### 10.1 Code change scope

| Phase | Files touched | New modules |
|---|---|---|
| 0 | `lathe/render_eval.py:99`, `lathe/validators/visual_quality.py`, `lathe/assembly_kernel.py` × 50, `lathe/shape_ir.py:14-37`, `lathe/optimize.py`, `lathe/scaffold_compiler.py:302-439`, `lathe/highlow.py`, `lathe/asset_graph.py:1895-1909`, `lathe/codex_imagegen_bridge.py` | `lathe/primitive_selector.py` |
| 1 | `lathe/mesh_grammar.py:283-387`, `lathe/exact_solids.py`, `scripts/blender_topology_adapter.py`, `lathe/asset_quality/shape_ir_v2.py`, `grammar/lathe.lark`, `lathe/normalizer.py`, `lathe/resolver.py`, `lathe/checker.py`, `schema/lathe.schema.json` | `scripts/blender_geometry_pipeline.py`, `lathe/feature_ops/bevel_real.py`, `lathe/validators/silhouette_multi_angle.py`, `lathe/validators/box_stack_detector.py` |
| 2 | `lathe/bake_runtime.py`, grammar, normalizer, resolver, checker, each stage entry-point | `lathe/surface_graph/` (with three modes), `lathe/attr_lang/`, `lathe/validators/render_eval_v2.py` + 8 more |
| 3 | new domain library tracks | `lathe/std/vegetation/`, `lathe/std/terrain/`, `lathe/wfc/`, `lathe/subdivision/`, `lathe/f_rep/`, `lathe/instance_pattern/`, `lathe/volume/` |
| 4 | new organic vocab modules | `lathe/humanoid/`, `lathe/parametric_rig/`, `lathe/animation/`, `lathe/cloth/`, `lathe/hair/`, `lathe/rig_components/` |
| 5 | new runtime modules + plugins | `lathe/runtime/`, Unity Plugin, Unreal Plugin, USD Hydra emitter |

### 10.2 Migration safety per phase

The stable shape contract `lathe.shape.intent_mesh_handoff_v1` is preserved across all phases. All new contracts are additive. Per AGENTS.md: "Preserve public Lathe source compatibility unless the task explicitly requests a language change. Keep the stable shape-stage contract at `lathe.shape.intent_mesh_handoff_v1` unless the task explicitly requests a migration plan."

### 10.3 Risks and dependencies

| Phase | Top risks | External dependencies |
|---|---|---|
| 0 | Test re-baselining cost | None |
| 1 | Bevel breaks watertightness on complex booleans; Blender adapter regressions | Blender (optional); trimesh |
| 2 | MaterialX adoption decision; renderer dependency | MaterialX library; Blender Cycles or Mitsuba |
| 3 | Domain libraries each are real engineering investment | OpenSubDiv (optional); OpenVDB (optional); Faithful Contouring ref impl |
| 4 | Anatomy presets need *taste* baked into preset libraries | None new |
| 5 | Engine integrations are platform-specific | Unity SDK, Unreal SDK, USD/Hydra |

### 10.4 User-visible milestone per phase

| Phase | Milestone |
|---|---|
| 0 | Brassbound chest's score with new validator drops below 0.84. Repair loop runs for the first time. Domes are domes. |
| 1 | Brassbound chest under typed_kernel_v1 with `boolean → bevel(seam_group)` chain emits real beveled body, lofted lid, swept handles, instanced rivets, real high-poly bake. |
| 2 | `surface_program: designer_graph { ... }` + MaterialX at 4K with curvature-driven layered authoring. PBR chart compliance gate. Style stack incompatibility refused. `photo_fit` mode delivers reference-photo materials. |
| 3 | Procedural oak tree, eroded canyon, WFC dungeon, SDF alien creature — all from .lth source. |
| 4 | `humanoid_anatomy adult_male_realistic` + composed character with morph targets, animated. |
| 5 | `.lathe.bundle` files into Unity / Unreal projects; per-asset variation re-evaluated at engine load. |

---

## 11. Cross-cutting Concerns

### 11.1 Validation contract evolution

1. **Phase 0 — Calibration fix.** Replace box-rewarding `primitive_penalty` with isoperimetric ratio. Promote diagnostics to blockers.
2. **Phase 1 — Real-render hooks.** silhouette_multi_angle + box_stack_detector at 512×512 with Cycles or Eevee.
3. **Phase 2 — Production validator suite.** Full eight-validator suite. Asset class profile drives validator stack selection.

**Re-baselining policy.** Re-baselining is acceptable — preserving existing scores is preserving the bug.

### 11.2 Performance budget per asset

| Phase | Build time per hero asset (target) |
|---|---|
| 0 | ~3 min (current baseline) |
| 1 | ~5-8 min |
| 2 | ~8-12 min |
| 3 | ~10-15 min |
| 4 | ~15-20 min |
| 5 | runtime evaluation moves to engine |

Opt-in fast-path: `build.fidelity = blockout` skips real-bevel + real-bake + real-render-validators.

### 11.3 Test infrastructure changes

| Phase | Test infra |
|---|---|
| 0 | Existing pytest infra suffices; re-baseline a few render_eval tests |
| 1 | Add Blender headless test runner; golden-image suite for silhouette_multi_angle and box_stack_detector |
| 2 | Add MaterialX validation test runner; golden-image suite per validator |
| 3 | Each domain library has its own integration test suite |
| 4 | Animation determinism tests; rig component cycle detection tests |
| 5 | Engine-side test runners (Unity headless, Unreal commandlet) |

### 11.4 Documentation updates

| Phase | Doc updates |
|---|---|
| 0 | Update CLAUDE.md; document re-baselined validator |
| 1 | Update spec/lathe-v0.1.md with `asset_class_profile`, `style_target`, typed_kernel_v1; new docs/typed_kernel.md and docs/named_sop_vocabulary.md (per addendum) |
| 2 | New docs/three_mode_surface_authoring.md (designer / photo_fit / layer_stack); update spec for attribute mini-language |
| 3 | One docs file per domain library |
| 4 | docs/organic_forward_vocabulary.md and docs/rig_as_geometry.md |
| 5 | Engine plugin developer docs |

---

## 12. Style-Band ROI Ordering

Per `stylization §S.7`:

### 12.1 Tier 1 — nail first (Phases 0-2)

**Band A — Chunky stylized low-poly.** Smallest tech surface; current Lathe behaviour closest to passable. Existence proof: Blender Studio's "Geometry Nodes from Scratch".

**Band D — Stylized PBR / "AAA stylized".** Existing `surface_program` / `surface_policy` / `trim_sheet` / `decal_library` architecture maps directly. Existence proof: Substance Designer's industry.

### 12.2 Tier 2 — nail next (Phase 3)

**Band F — Toy / claymation / Lego.** Most language-shaped band. Lego's "every model must be buildable from real bricks" rule is *literally a procedural compiler*. Phase 3 enables via `wfc_tileset` + `physical_substance` + strict construction grammar.

### 12.3 Tier 3 — nail third (Phase 3-4)

**Band B — Anime / cel-shaded.** Every "tell" is a deterministic recipe (ramp LUT, face-SDF, inverted-hull outline + Sobel post). Phase 3 base + Phase 4 humanoid anatomy.

### 12.4 Tier 4 — deferred / partial

- **Band C — Painterly.** Single assets tractable; directed Arcane / Spider-Verse sequences are not. Ship as single-asset target only.
- **Band E — AAA realistic.** Hard-surface and natural environment tractable; photoreal humans / fabric / hair require external capture. Hard-surface ceiling delivered Phase 3.
- **Band G — Hybrid.** Astro Bot variant fully procedural; HD-2D needs external sprite library.

### 12.5 Phase × band coverage matrix

| Phase | A | B | C | D | E | F | G |
|---|---|---|---|---|---|---|---|
| 0 | partial | — | — | partial | — | — | — |
| 1 | yes (basic) | — | — | yes (basic hard-surface) | — | — | — |
| 2 | yes (full) | partial | partial | yes (full) | partial | partial | yes (Astro variant) |
| 3 | full | partial | single-asset | full | hard-surface + env | full | Astro full; HD-2D needs sprite lib |
| 4 | + humanoid | full (anatomy + ramps) | + animated | + animated | + animated | + animated | full hybrid |
| 5 | + runtime | + runtime | + runtime | + runtime | + runtime | + runtime | + runtime |

---

## 13. Open Questions for the User

### 13.1 Phase ordering preferences

Recommended order: **Phase 0 → 1 → 2 → 3 → 4 → 5**. Two alternatives exist:
- **Surfaces-first.** Skip deep Phase 1 geometry; jump to Phase 2 surface_graph. Cost: Phase 1's high-poly source quality limits Phase 2's bake quality.
- **Vegetation-first.** Skip Phase 1+2; jump to Phase 3 vegetation. Cost: Phase 1's primitives are needed for the vegetation kit.

### 13.2 AI providers — kept experimental side-channel, or removed?

Three options:
- **Option 1 — Keep `experimental_external` indefinitely.** Recommended for Phases 0-3.
- **Option 2 — Remove at Phase 4 milestone.** If standalone-procedural produces AAA-tier output by then.
- **Option 3 — Remove now.**

### 13.3 Which style bands matter most for the use case?

The plan assumes nail Bands A and D first; B third; C/E/F/G deferred. Use cases:
- **Roblox / indie low-poly.** Reorder to A first, F second.
- **Stylized PBR AAA.** D first.
- **Open-world / environment heavy.** D first, then Phase 3 vegetation + terrain.
- **Anime / cel.** B first (requires Phase 4 anatomy first).

### 13.4 Timeline appetite

- **Aggressive (6-9 months):** Phase 0 + 1 + abbreviated Phase 2.
- **Standard (18 months):** Phase 0 + 1 + 2 + 3.
- **Full (3+ years):** Phase 0-5.

### 13.5 Houdini / Substance / Blender expertise on the team?

Components that ship better with domain expertise:
- **Houdini knowledge** speeds Phase 3 (vegetation, terrain, WFC) + Phase 1's named SOP vocabulary.
- **Substance Designer knowledge** speeds Phase 2 (three-mode surface authoring).
- **Blender Geometry Nodes knowledge** speeds Phase 1 (real Blender adapter pipeline).
- **OpenSubDiv / OpenVDB** speeds Phase 3.

### 13.6 Inviolable contracts beyond stable v0.1?

AGENTS.md preserves `lathe.shape.intent_mesh_handoff_v1` and `profile / contract / critic / asset / variant`. Any others?

### 13.7 Kernel: build vs. borrow?

- **Borrow-Blender path:** Blender as hard dependency. Faster shipping.
- **Build-pure-Python:** No external dep. Slower.
- **Hybrid (recommended):** Reference runtime ships deterministic Python evaluator; Blender / OCCT / OpenVDB are opt-in backends.

### 13.8 Domain library investment order?

Recommended: terrain_kit_v1 → vegetation_kit_v1 → volume_kit_v1.

### 13.9 USD Hydra Generative Procedural — earlier?

Phase 5 default. Could be Phase 3-4 if strategically valuable.

### 13.10 Lathe Engine runtime — scope?

Rank Unity / Unreal / USD by priority.

---

## 14. Closing — The Concrete Bet

### 14.1 The 6-month bet

Phase 0 + Phase 1 ship. The brassbound_chest under typed_kernel_v1 with `boolean → bevel(seam_group)` chain (the canonical hard-surface idiom per addendum) emits:
- Lofted body shell.
- Sweep-profile lid panel.
- Real revolved-profile brass bands instanced via `scatter`.
- Polyhedron lock plate from kit library.
- Sweep-profile handles.
- Generalized-cylinder feet.
- Real fillet bevels on hero edges.
- Real chamfer on trim edges.
- Real high-poly source feeding curvature-driven wear.
- Real instanced rivets via Copy-to-Points scatter.
- Real plank micro-displacement.

Validators read pixels. Box-stack detector rejects cubes. **Bands A and D production-viable for hard-surface props.**

### 14.2 The 18-month bet

Phase 0-3 ship. Three-mode procedural surface authoring (designer / photo_fit / layer_stack) with curvature-driven layered authoring at 4K, MaterialX-portable. HDA-class kits with explicit ports + version pinning. SpeedTree-class vegetation library ships ~10 species. Terrain + erosion. WFC dungeons. CGA assembly_rules. OpenSubDiv finishing. F-Rep alien creatures. `scatter` as productivity multiplier. Full eight-validator real-render suite. **Bands A, D, F production-viable; Band E hard-surface and natural environment viable.**

### 14.3 The 3-year bet

Phase 0-5 all ship. Lathe Engine runtime delivers Unity / Unreal plugins; USD Hydra Generative Procedural emission; portable `.lathe.bundle` format. Studios ship procedural assets that re-evaluate at engine load with parameter overrides — the Frostbite-class strategic move per addendum. Bands A, D, B, F production-viable; Band C single-asset; Band E hard-surface + environment; Band G Astro variant. **The procedural pipeline that ships Naughty Dog / Insomniac / Pixar AAA today is now expressible as portable .lth source.**

### 14.4 The discipline

The standalone-procedural posture is not a constraint — it is a discipline that produces *better* assets than AI generators do today. Cleaner topology. Deterministic. Edit-after-generate. IP-clean. Runtime-cheap. The proof is Substance Designer's industry, SpeedTree's ~1,000-game vegetation footprint since Avatar 2009, CityEngine's cities, Houdini's films, OpenSubDiv's animations, Frostbite's destruction — none of which need an AI generator at runtime (`procedural §C, §S.4`).

What Lathe needs to add is the vocabulary that lets authors hit the procedural ceiling those tools already prove exists: the named SOP geometry kernel (`boolean → bevel(seam_group)` etc.), the three-mode surface authoring divide, the rig-as-geometry position, and the typed-data kernel that ties them together.

The DSL is the imagination layer. The kernel is the discipline. Both must reach the same level. This roadmap is how.

---

## 15. Appendix — Quick reference

### 15.1 File:line cheat sheet

| Concern | Location | Phase to fix |
|---|---|---|
| Box-rewarding validator formula | `lathe/render_eval.py:99` | 0 |
| ShapePrimitive types | `lathe/shape_ir.py:14-37` | 0 (sphere added), 1+ (full set) |
| 170 component-builders emitting boxes | `lathe/assembly_kernel.py` × 170 | 0 (~50 revolved), 2+ (primitive selector) |
| Feature ops emitting tagged boxes | `lathe/feature_ops/__init__.py` (1881 LOC) | 1+ (real feature implementations) |
| Mesh grammar façade | `lathe/mesh_grammar.py:255-387` | 1 |
| Corner-only rounding | `lathe/exact_solids.py:121-159` | 1 (real bevel) |
| Boolean without seam group | `lathe/exact_solids.py` | 1 (add seam_group output) |
| 60-line Blender adapter | `scripts/blender_topology_adapter.py` | 1 |
| Bake source = bake target | `lathe/highlow.py` (32 LOC dataclass) | 0 (minimal), 1 (real) |
| Sin/cos texture procedural | `lathe/bake_runtime.py:_*_pattern` | 2 (refactor to surface_graph nodes) |
| Vision provider stub | `lathe/asset_quality/vision_critique.py` | 1 (replaced by real-render validators) |
| 2D clipart preview renderer | `lathe/asset_quality/preview_render.py` | 1 (replaced by real renderer) |
| AI provider scaffolding | `lathe/providers/adapters/*.py`, `lathe/codex_imagegen_bridge.py` | 0 (mark experimental_external), 4+ (decide removal) |
| Conformance scale-clamp | `lathe/conformance.py:67-69` | preserved with deprecation warning |
| Style preset tables | `lathe/creative_grammar.py:9-460` | 0 (seed primitive selector), 2 (full style routing) |
| Detail level + edge treatment vocab | `lathe/geometry_detail.py:9-34` | 1 (per-class fidelity expansion) |
| 30 advertised semantic ops, not wired | `lathe/asset_quality/shape_ir_v2.py` | 1 (wire to real emission) |
| Repair loop machinery | `lathe/repair_loop.py` + `validate.repair.mode` | 0 (becomes meaningful with stricter validators) |
| Self-reliant target gate | `lathe/asset_graph.py:1895-1909` | 0 (flip default to true) |
| Stable shape contract | `lathe.shape.intent_mesh_handoff_v1` | preserved across all phases |

### 15.2 Contract IDs introduced

| Contract ID | Phase | Purpose |
|---|---|---|
| `lathe.shape.intent_mesh_handoff_v1` (existing) | — | Stable, unchanged. |
| `lathe.shape.typed_kernel_v1` | 1 | Typed-bundle output; richer ShapeIR primitives; named SOPs. |
| `lathe.kernel.typed_bundle_v1` | 1 | TypedBundle bus (8 typed-data slots including Rig). |
| `lathe.attr_lang.v1` | 2 | VEX-style attribute mini-language. |
| `lathe.asset_class.profile_v1` | 1 | Asset class profiles with budgets. |
| `lathe.style.routing_v1` | 1-2 | Style target stack with refusal. |
| `lathe.style.bridge_v1` | 2 | Sanctioned mixed style compositions. |
| `lathe.surface.procedural_node_graph_v1` | 2 | Three-mode surface authoring (designer / photo_fit / layer_stack). |
| `lathe.surface.smart_mask_library_v1` | 2 | Named procedural masks. |
| `lathe.material.material_primitive_v1` | 2 | Typed material primitives with PBR validation. |
| `lathe.material.physical_substance_v1` | 3 | Substance taxonomy. |
| `lathe.kit.hda_v1` | 2 | HDA-class kits. |
| `lathe.assembly.shape_grammar_v1` | 3 | CGA-style declarative refinement. |
| `lathe.wfc.tileset_v1` / `adjacency_v1` / `solve_v1` | 3 | Modular tileset assembly. |
| `lathe.shape.subdivision_v1` | 3 | Catmull-Clark / Loop. |
| `lathe.shape.f_rep_v1` | 3 | F-Rep / SDF authoring. |
| `lathe.shape.heightfield_v1` | 3 | Heightfield first-class. |
| `lathe.shape.volume_v1` | 3 | Sparse volume (VDB). |
| `lathe.spline.v1` | 3 | Typed spline. |
| `lathe.simulation.deterministic_weathering_v1` | 3 | Erosion / settling / weathering. |
| `lathe.silhouette.intent_v1` | 1 | Silhouette target. |
| `lathe.rig.parametric_v1` | 4 | Rig-as-geometry typed-data slot. |
| `lathe.validate.real_render_v1` | 1-2 | Real raytraced render + pixel metrics. |
| `lathe.validate.box_stack_detector_v1` | 1 | Hard rejection. |
| `lathe.validate.style_stack_compatibility_v1` | 2 | Refuse incompatible stacks. |
| `lathe.validate.pbr_chart_compliance_v1` | 2 | Per-pixel PBR chart enforcement. |
| `lathe.validate.topology_class_compliance_v1` | 2 | Quad-domination / no-n-gons / pole-vertex rules. |

### 15.3 Phase × bands × effort summary

| Phase | Calendar effort (2-3 engineers) | Bands unlocked | Top deliverable |
|---|---|---|---|
| 0 | 1-2 weeks | A, D (partial) | Validator stops rewarding cubes; revolved_profile / sphere deployed |
| 1 | 2-3 months | A, D | `boolean → bevel(seam_group)` + real bevels + real high-poly + real Blender pipeline |
| 2 | 3-4 months | A, D, partial B/C | Three-mode surface graph (designer / photo_fit / layer_stack) + style routing + real-render validators |
| 3 | 6-9 months | A, D, F, partial B/E | Vegetation, terrain, WFC, OpenSubDiv, F-Rep, instance_pattern |
| 4 | 12-18 months | + B characters | Parametric humanoid anatomy + rig-as-geometry + animation |
| 5 | 18-36 months | runtime distribution | Lathe Engine: Unity/Unreal/USD plugins |

---

## 16. Addendum — Three pillars from the DSL design supplement

The DSL architect's second addendum (post-procedural-systems-supplement integration) added three concrete pillars to the design doc; they are integrated throughout this roadmap and called out explicitly here for traceability.

### 16.1 Named geometry-kernel SOP vocabulary (`dsl §3.2.1`)

The mesh_program ops commit to specific Houdini SOP names — the vocabulary AAA pipelines speak. Each name maps to a SideFX SOP doc. **The chain `boolean → bevel(seam_group)` is canonical hard-surface authoring** — Boolean produces the A∩B seam group, PolyBevel consumes it. This is what turns box-stack output into real beveled hard-surface assets.

**Roadmap integration:** §3.3 tier table maps each T2 primitive to its SOP analog (Sweep, Polywire, PolyExtrude, PolyBevel, Boolean, Subdivide, Remesh, Loft/Skin, Copy-to-Points, Carve). §5.1 calls out the `boolean → bevel(seam_group)` chain as the Phase 1 KEY DEMO. `scatter` (Copy-to-Points) is promoted in §6.4 as the productivity multiplier per addendum.

### 16.2 Three-mode surface authoring (`dsl §3.7 + §7.7 + §7.8`)

Substance Designer / Sampler / Painter divide explicitly modeled as three Lathe modes:
- `surface_program: designer_graph { ... }` — author from-scratch (the Substance-Designer-equivalent §3.7 already covered).
- `surface_program: photo_fit { reference: <path>, ... }` — fit PBR set from a reference photo deterministically (palette extraction + frequency analysis + tile-fitting; T2; **no learned model** per the standalone-procedural mandate).
- `surface_program: layer_stack { ... applied via mask_program ... }` — composite Smart Materials with mesh-aware masks; T2.

**Roadmap integration:** §3.6 specifies all three modes with worked examples. §6.1 schedules all three for Phase 2; per addendum, `photo_fit` could ship alongside Phase 1 as a relatively-cheap T2 win (deterministic image processing, no contract migration — ships under existing surface_graph contract as a mode tag).

### 16.3 Rig-as-geometry / KineFX position (`dsl §5.1 + §11.2`)

Houdini KineFX/APEX position adopted: rig is now the eighth typed-data slot in `TypedBundle` alongside Mesh/Points/Volume/Heightfield/Spline/SDF/Image. `parametric_rig` block composes rig from named rig_components (`spine`, `limb`, `digit`, `mech_joint`, `wing_chain`, `tentacle_chain`) — same kit-library HDA pattern. Skin weights are per-vertex attributes (`@skin.<bone_id>`) on the Mesh. **This is the procedural-equivalent of MetaHuman: fixed canonical topology + canonical rig + parametric morph database. No learned characters required.** Tier T3, Phase 4.

**Roadmap integration:** §3.2 TypedBundle table includes Rig as the eighth slot. §3.14 specifies the rig-as-geometry framing. §8.2 schedules `parametric_rig` for Phase 4.

### 16.4 Frostbite-class strategic move (`dsl §15.10`)

The Frostbite runtime-procedural pattern (BF6 REDSEC SDF destruction; Andersson SIGGRAPH 2010 procedural shader splatting; DICE Procedural team mission "develop and bring the latest cutting-edge procedural technologies into Frostbite") is the AAA proof for the Lathe Engine runtime distribution channel.

**Roadmap integration:** §9 (Phase 5) frames Lathe Engine runtime as the Frostbite-class strategic move. The standalone-procedural mandate doesn't preclude shipping live procedurals; it precludes runtime AI dependencies. Substance Engine SBS + Houdini Engine HDAs + Frostbite SDF-at-runtime are the closest commercial precedents.

### 16.5 SpeedTree's offline-procedural pattern (`dsl §15.11`)

SpeedTree's "offline procedural — runtime SDK renders the result, but the artist authors *with* SpeedTree's tools and ships *baked* trees + LODs" pattern is precisely the shape Lathe should adopt for vegetation. "Since Avatar 2009 — nearly 100 films and well over 1,000 games" is the standalone-procedural existence proof at AAA scale.

**Roadmap integration:** §7.1 specifies the SpeedTree pattern for Phase 3 vegetation library. §1 Executive Summary cites the SpeedTree footprint as standalone-procedural existence proof.

---

*End of roadmap. This is the final deliverable for the lathe-imagination-research effort. Total upstream research: ~6,500 lines across 5 reports + 2 design-doc addenda. This synthesis includes the three new pillars (named SOP vocabulary, three-mode surface authoring, rig-as-geometry) integrated throughout.*

*References — primary research documents:*
*- `D:\lathe_v0_1\.research_output\auditor_report.md` (lathe-internals-auditor) — code-level diagnosis, 432 lines.*
*- `D:\lathe_v0_1\.research_output\quality_framework.md` (3d-asset-quality-researcher) — 8-lever framework, 766 lines.*
*- `D:\lathe_v0_1\.research_output\stylization_atlas.md` (stylization-spectrum-researcher) — 7 style bands × 9 axes, 892 lines.*
*- `D:\lathe_v0_1\.research_output\procedural_3d_systems.md` (ai-3d-frontier-researcher) — procedural systems map, 925 lines.*
*- `D:\lathe_v0_1\.research_output\lathe_language_design.md` (dsl-language-architect) — DSL design specification, 3,180 lines (post-2-addenda).*

*Project context:*
*- `D:\lathe_v0_1\spec\lathe-v0.1.md` — Lathe v0.1 language specification.*
*- `D:\lathe_v0_1\AGENTS.md` — repository guidance, contract preservation rules.*
*- `D:\lathe_v0_1\CLAUDE.md` — project conventions and command reference.*
