# Lathe Asset-Quality Synthesis — Real Blockers + Implementable Breakthroughs

**Compiled by:** team-lead (synthesis of 7 specialist agents)
**Date:** 2026-05-04
**Mandate:** standalone procedural · ultra-modular · additive-only to `lathe.shape.intent_mesh_handoff_v1` · no AI 3D models

**Inputs:**
- `audit_pipeline_blockers.md` (downstream pipeline audit)
- `audit_shape_blockers.md` (shape stage audit)
- `openscad_lessons.md` (OpenSCAD / Manifold / BOSL2)
- `sota_geometry.md` (CSG kernels, SDF, B-Rep, voxel)
- `sota_topology_uv.md` (retopo, UV unwrap, texel density)
- `sota_surface_materials.md` (Substance-class graphs, MaterialX, baking, PBR)
- `sota_art_direction.md` (HDA contract, director vocabulary, fields, refusal tables)

---

## TL;DR — why your assets don't look good

Lathe is **two systems**: a sophisticated declarative authoring layer (~9000 LOC across V0.8–V1.3) and a kernel that consumes ~15% of what's authored and silently ignores the rest. Six structural blockers compound:

1. **Authored intent never reaches geometry.** ~85% of `.lth` source fields (`features.allow`, `surface.patterns`, `geometry.integration_rules`, `intent.style_target`, `assembly.components` content) are dropped before the asset graph is built. The kernel routes by 3-token family name match, then by hardcoded per-family blueprint factory.
2. **Latent capability is wired as validators, not drivers.** ShapeIR v2's seven op families, `grammar_lowering`, `construction_graph`, and `DesignerGraph.evaluate()` all exist as code — and are wired as `weight=0.0` informational validators that produce JSON nothing reads. Same pattern across pipeline stages.
3. **Chest is the type system.** The "brassbound_chest" fixture is referenced by name in `feature_fusion.py`, `highlow_relation.py`, `surface_runtime.py`, `assembly_kernel.py`, `feature_grammar.py`, `primitive_selector.py` — gating CSG, bevels, hero-quality emission, and feature density. Adding a new family requires Python edits in 7 files.
4. **The robust kernel is the fallback.** `manifold_available() → True` on the dev machine. `MANIFOLD_KERNEL_ID` is the registered default. But the production CSG path is `trimesh.boolean.*` → only when *that* fails does Manifold get a chance. Manifold preserves UVs/materials through booleans; trimesh destroys them. **This is why the bake is broken.**
5. **The bake paints world-space normals as polygon fills.** `bake_normal_map` writes `face_normal*255` into UV polygons — saturated reds/teals, not tangent-space. AO is `dot(N, +Y)`, not occlusion. Curvature is per-face dihedral on the low poly. Bake maps that should hold sub-triangle detail are flat per-low-triangle fills.
6. **Validators score metadata, not pixels.** `silhouette_render_dir` consumers exist; nothing writes there. The asset that ships with broken textures and proxy mesh certifies at 0.888 because no validator reads the rendered image.

These six are upstream of every other quality concern. **Manifold-as-primary kernel + DesignerGraph wired into the bake + tangent-space normal bake is the smallest set that produces a visibly better asset on Day 1.**

---

## The Punch-List — Top 12 Blockers, Ranked by Visible Quality / Effort

### Tier S (Day 1 wins — small effort, large visible lift)

#### B1. Promote Manifold to primary CSG kernel · S
**Files:** `lathe/scaffold_compiler.py:154-260,453-475`, `lathe/exact_solids.py:1164/1175/1185/1916-1918`, `lathe/geometry/reference_kernel.py` (3 sites). Manifold adapter already exists at `lathe/adapters/manifold_kernel.py` (446 lines). Currently *only* invoked when `fused_mesh_ir is None and geometry_kernel_id == "lathe.geometry.manifold_v1"` — i.e., as a fallback after trimesh fails.
**Why:** Manifold preserves vertex properties (UVs, materials) through booleans; trimesh destroys them. The broken bake / sliver-shading / random-triangulation findings all trace back here. OpenSCAD made Manifold default in Aug 2025 (30–1000× faster than CGAL, guaranteed manifold output). Cross-confirmed by openscad-specialist + geometry-sota + shape-auditor.
**Fix:** Re-order `_runtime_from_shape_ir` so manifold is tried first when it's the resolved kernel. Add `lofted_solid` to `_fuse_via_manifold_kernel`'s primitive switch (currently returns `None` — line 234) — chest body's primary primitive currently can't go through manifold.
**Modular:** removes one fallback hack; not chest-specific.

#### B2. Wire `DesignerGraph.evaluate` into the bake · S–M
**Files:** `lathe/surface_runtime.py:1031-1090`, `lathe/surface_graph/designer_graph.py`, `lathe/surface_graph/nodes.py`, `lathe/bake_runtime.py:492-503`.
**Why:** The numpy-buffer evaluator exists. The IR exists. The MaterialX sidecar exists. `grep -rn "graph.evaluate\|DesignerGraph(" lathe/` returns nothing — production never calls it. What ships are legacy `bake_basecolor_map` / `bake_normal_map` etc. with sin/cos noise polygon-fills.
**Fix:** Replace `bake_basecolor_map`'s polygon fill with `DesignerGraph.evaluate(size=(2048,2048))` per part. Add SlopeBlur, HistogramScan, EdgeDetect, GradientMap, PositionMask nodes (~200 LOC numpy). Substance-class procedural materials in production.
**Modular:** generic — works for any part with a designer graph; no family check.

#### B3. Tangent-space normal bake (replace world-space polygon-fill) · S
**Files:** `lathe/bake_runtime.py:492-503`, frame builder `_low_face_tangent_frames` already exists at `:638` and is unused.
**Why:** Today the bake does `ImageDraw.polygon(uv_polygon, fill=face_normal*255)` — saturated world-space fill. Engines expect tangent-space normal maps; they will not display this correctly anywhere. Catastrophic bug, single-file fix.
**Fix:** Use the existing tangent frame to convert per-texel normals; add a 4×4 supersampled rasterizer to replace `ImageDraw.polygon`. Fix AO (`dot(N,+Y)`) to actually do AO via raycast or curvature-from-height. Fix curvature transfer to read from a real high-poly source (B5).
**Modular:** generic, no family branching.

#### B4. Fix Blender-5.x topology adapter and ungate hero CSG/bevel · S
**Files:** `scripts/blender_topology_adapter.py:36`, `lathe/feature_fusion.py:25-48`, `lathe/assembly_kernel.py:8642`.
**Why:** One broken API call (`bpy.ops.import_scene.gltf(filepath=...)` rejected by Blender 5.x with "Please select a file") wedges the entire downstream multi-part topology path. Adapter silently falls back to weld+seal, target_quads is dead, multi-part bevel is dead. Separately, `integration_config_for_family` returns `enabled=hero_family ∈ frozen 8-name set` — every other family gets concatenated meshes (no CSG). And `_apply_chest_edge_class_bevels` only fires `if asset_graph.family == "brassbound_chest"`.
**Fix:** (a) one-line API fix; (b) replace family allowlist with capability check (`intent.asset_class in {hero,prop,weapon,tool}` OR authored `geometry.integration_rules` OR `build.shape.mode in {generate,assemble,adapt}`); (c) generalize `_apply_chest_edge_class_bevels` to `_apply_edge_class_bevels(primitives, edge_classes, seam_classes, *, mapping)` — drop the family-equality gate; fire whenever `geometry.edge_classes` is authored.
**Modular:** removes 3 chest-specific code paths.

### Tier A (1–4 weeks, large quality lift)

#### B5. Procedural high-source from ShapeIR primitives, not subdivision · M
**Files:** `lathe/surface_runtime.py:_procedural_high_source_mesh:299-350`, `lathe/core/stages/optimize.py:525`.
**Why:** Today's high source is `subdivide_to_size` of the low mesh — same surface, more triangles. So `highlow_normal_transfer` ray-casts onto the same shape it's transferring from — there's no detail to bake. Wear concentrates on box corners because the low-poly cube *is* the source curvature reads from.
**Fix:** Re-tessellate the ShapeIR source primitives at native curvature (radii, fillets, chamfers) so curvature transfer fills bevel strips. Real high-poly source means real curvature-driven wear on actual bevels.
**Modular:** generic — works for any primitive.

#### B6. Quad retopology via `pynanoinstantmeshes` (PyPI) · S
**Files:** `lathe/topology_runtime.py`, new `lathe/topology/instant_meshes_v1.py`. Optional fallback `pyQuadriFlow` for organic shapes.
**Why:** Even with Blender adapter fixed, current adapter is Subsurf+Bevel+Decimate on the input mesh — NOT real quad-flow retopology. No quadriflow / instant-meshes wired up at all. SOTA quad-dominant retopo is a single PyPI package away. Ship as `lathe.topology.quad_remesh.instant_meshes_v1` provider; wire as default with Blender path as alternative.
**Modular:** standalone Python — no Blender hard-dep.

#### B7. Texel-density audit + constrained UV packing · M
**Files:** `lathe/uv_runtime.py:438` (currently uniform 1024 px/m, ignores xatlas importance weights), `rectpack` PyPI.
**Why:** Validator's `texel_density_consistency: 0.0` is the loudest pixel-level signal that's actually meaningful. Hero-asset critique is dominated by inconsistent texel density. Pre-scale charts by world area, then 2D bin-pack with `rectpack` instead of letting xatlas auto-scale and silently override authored `texel_density`.
**Modular:** purely algorithmic; honors per-part importance attributes.

#### B8. Generic `op.distribute(pattern, count, axis)` replacing chest-specific REPETITION_OPS · M
**Files:** `lathe/asset_quality/shape_ir_v2.py` REPETITION_OPS (`fastener_grid`, `vent_slats`, `trim_band`, `corner_guard_set` — chest-specific), new `lathe/feature_ops/distribute.py`. Inspired by BOSL2 `xcopies/rot_copies/path_copies` + OpenSCAD `children()` mechanism.
**Why:** Removes ~20 chest-specific helpers from `feature_ops/`. Patterns: linear/grid/radial/arc/along_path. Author-controllable count. The directory `lathe/feature_ops/` was clearly built for individual ops but `__init__.py` is the only file (2546 LOC awkwardly inside it).
**Modular:** the canonical generalization — directly closes the "chest is fixture not product" smell.

#### B9. BOSL2-style edge_selector + edge_profile masks · M
**Files:** `lathe/shape_ir.py` (replace `subdivision_box.corner_radii` 8-tuple with EdgeSelector + edge_treatments dict), new `std/edge_profiles/` with named 2D profiles (`chamfer`, `rounding`, `ogee`, `cove`, `teardrop`, `dovetail`), `lathe/asset_quality/shape_ir_v2.py` EDGE_OPS to consume selector + profile.
**Why:** "THE single largest production-feel lever" (openscad-specialist). Real assets have selective edge treatments by feature; Lathe today can only round all corners uniformly. Selective bevels are the difference between CAD output and AAA hard-surface.
**Modular:** generic; works for any solid.

#### B10. `hull()` + `minkowski()` operators · M
**Files:** add `op.hull`, `op.minkowski` to `lathe/asset_quality/shape_ir_v2.py:BOOLEAN_OPS`, surface in `grammar/lathe.lark` as `hull{}` `minkowski{}` blocks, lower in `lathe/exact_solids.py`. Manifold has both natively (B1 makes this trivial).
**Why:** OpenSCAD's two highest-leverage CSG operators. `hull()` builds organic exact-CSG forms (grips, fairings, stocks). `minkowski(sphere)` is the canonical "round all edges" operator. Closes the single biggest expressiveness gap vs OpenSCAD. Once Manifold is primary (B1) these are essentially free.

### Tier B (longer runway — strategic ceilings)

#### B11. Promote ShapeIR v2 / `grammar_lowering` / `construction_graph` from validators to drivers · L
**Files:** `lathe/asset_quality/shape_ir_v2.py:1-58`, `grammar_lowering.py:1-49`, `construction_graph.py:39-53`, `lathe/scaffold_compiler.py`, `lathe/assembly_kernel.py`.
**Why:** Shape-auditor's most architectural finding. ShapeIR v2 has 7 op families (SOLID/BOOLEAN/EDGE/SOP/REPETITION/INTEGRATION/WEAR), `construction_graph` has 15 node-types and 10 edge-types (`inset_into`, `wraps_around`, `cuts`, `mirrors`, `aligned_with`), `grammar_lowering` has hardcoded canonical dimensions per family — **all wired as `weight=0.0` informational validators that synthesize JSON nothing reads.** This is the dormant authoring layer that makes 85% of dropped fields meaningful.
**Fix:** Asset graph builder calls `grammar_lowering.lower(design_brief, parts, construction_graph_nodes)` to produce a `ShapeProgram` — sequence of `ShapeOp`s. Assembly kernel consumes `ShapeProgram` *before* the family-specific blueprint factory. `_chest_blueprint` becomes a fallback for assets without explicit ShapeProgram. ~800 LOC, careful staging.
**Modular:** the architectural change — kernel becomes a deterministic op-dispatcher.

#### B12. B-Rep IR (`lathe/b_rep/`) backed by OCCT via `pythonocc-core` · L
**Files:** new `lathe/b_rep/` mirroring `lathe/f_rep/`, new `primitive_type="b_rep_brep"` in `lathe/shape_ir.py`, lowering layer to ShapeIR mesh. `pythonocc-core` ships Windows wheels.
**Why:** The single highest quality ceiling in the geometry-sota report. OCCT gives analytic-quality fillets/chamfers/sweeps/surfaces — `BRepFilletAPI_MakeFillet` produces G2 surfaces; `BRepOffsetAPI_MakeThickSolid` is exact shell/hollow. Stays additive — runs *before* `intent_mesh_handoff_v1` and lowers to ShapeIR — so the contract holds.
**Modular:** parallel IR; not a replacement.

---

## Cross-Cutting Themes (every agent surfaced these)

### 1. The 7 dormant systems
| System | Where it is | Status |
|---|---|---|
| Manifold CSG | `lathe/adapters/manifold_kernel.py`, default kernel ID registered | only as fallback |
| `DesignerGraph.evaluate` | `surface_graph/designer_graph.py` | never called in production |
| ShapeIR v2 ops | `asset_quality/shape_ir_v2.py` | weight=0.0 validator |
| `grammar_lowering` | `asset_quality/grammar_lowering.py` | weight=0.0 validator |
| `construction_graph` | `asset_quality/construction_graph.py` | weight=0.0 validator |
| `feature_ops/` | `feature_ops/__init__.py` only file | empty registry |
| Pixel-level validators | `silhouette_render_dir` consumers exist | no producer writes there |

These are accumulating cost, not capability. Wiring even half of them yields the visible-quality lift the user is paying for.

### 2. Chest-specific code paths to delete (modularity smells)
- `lathe/assembly_kernel.py:341-357` `_is_container_component` — hardcoded tag set
- `:8400-8402` `_CHEST_HERO_COMPONENTS / _CHEST_SUPPORT_COMPONENTS / _CHEST_TRIM_COMPONENTS`
- `:8503-8526` `_chest_brass_band_primitives`
- `:8642` `if asset_graph.family == "brassbound_chest":` (130 LOC)
- `lathe/feature_grammar.py:143` `if asset_graph.family == "brassbound_chest" and "plank_displacement"`
- `:134, :202` `if asset_graph.family == "console_terminal"`
- `lathe/feature_fusion.py:25-34` `_HERO_FAMILIES` frozenset (repeated in `highlow_relation.py:105-116` and `surface_runtime.py:47-73`)
- `lathe/primitive_selector.py:225-373` seven per-family `_X_VOLUME_COMPONENTS / _PANEL_COMPONENTS / _TAGS` set-literals
- `lathe/primitive_selector.py:546-735` 200-line `_select_replacement` if-cascade
- `lathe/asset_graph.py:84-300` 15 family token-match rules

**Generalization pattern:** dispatch on `intent.asset_class`, `component.tags`, and authored `selector_rules` from family stdlib (YAML/JSON in `std/`), not on family name equality. Most can become 1-line fixes once B11 lands.

### 3. SOTA breakthroughs that map cleanly into Lathe
| SOTA technique | Source | Lathe insertion |
|---|---|---|
| Manifold-as-primary CSG | OpenSCAD 2025 default | `lathe/exact_solids.py` (B1) |
| `hull()` + `minkowski()` | OpenSCAD/Manifold | `shape_ir_v2.py` BOOLEAN_OPS (B10) |
| `linear_extrude` twist + scale | OpenSCAD | `shape_ir.py` `extruded_profile` ~30 LOC |
| BOSL2 edge_selector + edge_profile masks | BOSL2 | `shape_ir.py` (B9) |
| BOSL2 fasteners/threading/gears libraries | BOSL2 | new `std/fasteners/`, `std/threading/`, `std/gears/` |
| Helical sweep + parallel-transport frame | geometry kernels | `shape_ir.py` new primitive (S, ~200 LOC) |
| Real Dual Contouring (QEF/SVD) | Schaefer/Ju/Warren | `lathe/f_rep/dual_contouring.py` (M, NumPy-only) |
| MDC manifold output | Schaefer 2007 | `lathe/f_rep/dual_contouring.py` extension |
| Quilez `Onion` / smooth-union variants | iquilezles.org | `lathe/f_rep/expressions.py` (S) |
| Mesh-to-levelset repair (NumPy) | OpenVDB-class workflow | new `lathe/volume/repair.py` (M) |
| Instant Meshes / QuadriFlow retopo | wjakob, Huang 2018 | `lathe/topology/` (B6) |
| OptCuts UV unwrap (Phase 2) | Li 2018 | `lathe/uv_runtime.py` opt-in |
| Boundary First Flattening (Phase 2) | Sawhney/Crane 2018 | `lathe/uv_runtime.py` for `seam_group`-tagged parts |
| Substance smart materials (curvature/AO/cavity-driven wear) | Substance Designer | `lathe/surface_graph/` (B2 enables) |
| MaterialX 1.39 stdlib + per-engine normal flip | MaterialX standard | `surface_graph/materialx.py`, `engine_manifests/*` |
| Trim sheets + per-edge UV binding | AAA hard-surface | new `surface_graph/trim_sheet.py` |
| HDA contract (range/units/enum/tooltip + port-types) | Houdini HDA | `lathe/kit_ir.py` enforcement |
| Field-style attr_lang (`@curvature.smooth(0.6)`) | Geometry Nodes / VEX | promote roadmap §6.2 |
| CGA-style `assembly_rules` (split/repeat/chooseOne) | CityEngine / Houdini | roadmap §3.8 |
| Director vocabulary (era × provenance × environment) | meta-authoring | new `std/director_vocab/` |
| Reference-driven palette + silhouette + frequency split | deterministic, no ML | `asset_quality/reference_board.py` |
| OCCT B-Rep feature tree | pythonocc-core | new `lathe/b_rep/` (B12) |

---

## Day-1 / Week-2 / Quarter-1 sequencing

**Week 1 — Day-1 wins (Tier S):**
1. B1 Manifold-as-primary CSG kernel
2. B3 Tangent-space normal bake
3. B4 Blender-5.x adapter fix + CSG/bevel ungating
4. B2 Wire `DesignerGraph.evaluate` into the bake

This gets the chest from the current "polygon-fill world-space normals + missing topology + no bevels" state to "Manifold-fused + tangent-space-baked + procedural-material-baked + edge-bevels-on-all-hero-families" — visible asset-quality lift on every existing example.

**Weeks 2–4 — Tier A:**
5. B5 Real procedural high-source for bake transfer
6. B6 Instant Meshes retopology
7. B7 Texel-density audit + rectpack
8. B8 `op.distribute(pattern, count, axis)` (modularity)
9. B9 BOSL2 edge_selector + edge_profile masks
10. B10 `hull()` + `minkowski()`

**Quarter 1 — Tier B (strategic):**
11. B11 Promote ShapeIR v2 / grammar_lowering / construction_graph from validators to drivers
12. B12 B-Rep IR via OCCT (parallel)
13. HDA contract enforcement on `kit_ir.py`
14. Director vocabulary `std/director_vocab/`
15. Field-style `attr_lang` across all programs

---

## Open Calibration Questions (for you, the user)

1. **Should authored `features.allow = [...]` be source-of-truth or hint?** Source-of-truth makes the kernel a deterministic dispatcher and removes all `if family == "chest"` branches — but it means an unknown family with a sensible `features.allow` gets a real asset.
2. **Is `family` a closed enum or open?** Today: closed (15 hardcoded token rules + 8 hero names). Open requires B11 to land cleanly. The current state pays "closed" cost without "open" benefit.
3. **B-Rep parallel IR (B12) — yes or defer?** L effort, but biggest quality ceiling. The decision shapes whether Lathe targets *analytic* hard-surface (yachts, cars, weapons with curved hulls) or stays mesh-only.
4. **No-Blender or fix-Blender?** B6 (Instant Meshes) + a small offscreen renderer (Cycles or pyrender at 512×512 to feed dormant pixel-level validators) means Lathe could ship without Blender as a hard dep. Or commit to Blender-5.x parity.
5. **Pure-Python tier 3 mesh repair (mesh→levelset→mesh) — adopt as default?** Watertight by construction, never fails. Loses sharp features at voxel scale. Recommended as last-resort tier of the boolean chain.

---

## Bottom Line

The user said "the assets just do not look good." The reports converge on a single explanation: **Lathe ships a sophisticated declarative authoring layer connected to a kernel that uses ~15% of what's authored, paints world-space normals into UV polygons, and only invokes its own robust CSG kernel as a fallback.** Plumbing is rich; pixels are starved.

Four things together produce a visibly better asset on Day 1 — Manifold primary, DesignerGraph evaluated, tangent-space normals, ungated CSG/bevels. None are speculative; all the underlying code already exists. After that, the deeper modularity work (B11) unlocks the rest of the dormant authoring layer and removes the chest-as-type-system smell across the codebase.

Standalone-procedural mandate is preserved throughout — Manifold/OpenSCAD/BOSL2/Substance/Houdini patterns are 100% deterministic. No agent recommended bolting on Hunyuan3D / Tripo / Meshy. The procedural ceiling, when the kernel actually consumes the language, is genuinely AAA.
