# Downstream-Pipeline Blocker Audit

Scope: everything downstream of shape — topology, UV, surface, materials, bakes, validators, LOD, package, repair, engine manifests. Read by reproducing a `python -m lathe.cli build examples/brassbound_chest.lth brassbound_chest --out tmp_audit_pipe` and inspecting bundle.json + emitted PNGs/GLBs alongside source.

## Top Blockers (ranked by visible impact)

### 1. Bakes paint per-low-face polygons in **world-space**, not per-texel rays in tangent-space
The "baker" in `lathe/bake_runtime.py` is `PIL.ImageDraw.polygon(uv_polygon, fill=rgb)` per low-poly face. For normals (`bake_normal_map` line 492) the fill is `((normal*0.5+0.5)*255)` — i.e. **object/world-space normals painted as a flat constant per triangle.** Game engines reading the resulting PNG as a tangent-space normal map will display garbage. The chest's `normal.png` (verified in `tmp_audit_pipe/.../surface/maps/normal.png`) is full of saturated red / teal / magenta solids — that's the world-space face normal of each low triangle, not the (128,128,255-ish) variations a tangent-space map should show.

The high→low transfer (`bake_highlow_normal_transfer_map` line 704) is slightly better: it does cast one ray per *low-face centroid* and reads the matching high-face normal in tangent space. But it still paints a *single flat color per low triangle*. There is no per-texel raycast: every UV texel inside a polygon gets the same RGB. So normal maps can never represent sub-triangle detail (rivets, scratches, plank bevels) regardless of how dense the high source is.

`bake_ao_map` (line 843) is even worse: it's literally `value = 72 + upward*150 + face_normal_y*18` — a fake directional-light proxy painted into UV polygons. It is not ambient occlusion. The map looks like top-lit black-and-white shading because it is.

`bake_curvature_map` (line 832) reads dihedral angles between adjacent faces and paints them per-face; cannot encode the per-pixel curvature gradient that drives Substance-class edge wear masks.

**Why this kills SOTA quality**: every map that should hold detail (normal, curvature, AO, basecolor wear) is fundamentally a per-face flat fill. The pixels you see in the engine are the same color the entire UV island over a flat region. There is no "surface" beneath the face — and there is no path to making the bakes look richer until they sample at the texel level (per-pixel `mesh.ray.intersects_location` for normal/AO/displacement transfer) instead of `ImageDraw.polygon`.

### 2. The Blender topology adapter has been silently broken by Blender 5.x
`scripts/blender_topology_adapter.py:36` calls `bpy.ops.import_scene.gltf(filepath=args.input)` which Blender 5.0 rejects with `RuntimeError: Error: Please select a file` (visible in `tmp_audit_pipe/.../topology/bundle.json` `fallback_reason`). The chest build I ran reports `actual_adapter: "reference_cleanup"` even though `requested_adapter: "auto"` and `real_adapter_available: true`.

So the entire Blender hard-surface topology pass — which is what `target_quads`, subsurf level, the bevel-seam edge weighting, the polybevel modifier stack, and the GeometryNodes scatter records all flow into — has been a no-op on current Blender. The "topology" the user sees is just `mesh.merge_vertices() + mesh.fix_normals() + seal_non_watertight_mesh()` (`lathe/core/geometry.py:242`). That's why the wireframe preview is full of long sliver triangles radiating out from boolean-cut corners — that's raw shape-stage output with vertex welds, no retopology.

Even when Blender works, the adapter is **not** real retopology. It is a Subsurf+Bevel+Decimate modifier stack on the input mesh (lines 183–233 of `blender_topology_adapter.py`). Modifies vertex/edge density of the existing topology; cannot recover from sliver triangles, cannot orient quads to surface flow, and can't produce edge loops along seams. Real retopology = quadriflow / instant-meshes / Blender's `Remesh` quad mode / hand authoring; none of those are wired up.

### 3. Validators score from bundle metadata + texture entropy, never from rendered pixels
The asset comes out **certified at score 0.888** with a world-space normal map and a chunky proxy mesh. That tells you all you need to know about validator-vs-reality alignment.

Concrete misalignments:
- `lathe/validators/silhouette.py` reads bbox extents/ratios + per-part bbox centers. Never opens an image.
- `lathe/validators/visual_quality.py:142–270` reads texture entropy / std-dev / chroma variance from the *already-baked* sin/cos textures. Since the bake creates lots of std-dev synthetically, the validator rewards "noisy bake" regardless of whether it is plausible PBR. There's no oracle; e.g. rewarding `_image_entropy(basecolor)` rewards both real wood grain and random noise equally.
- `lathe/render_eval.py` rasterizes flat lambert mask polygons at 128×128 and computes silhouette area / perimeter / cosine-of-light-direction. There are no textures in the render. So `render_silhouette_complexity`, `render_shading_variance` etc. are computed from untextured proxies — they cannot reflect what the asset will actually look like.
- `lathe/validators/silhouette_multi_angle.py` and `frequency_energy.py` *would* read PNGs if the renderer emitted them, but no Lathe code writes to `silhouette_render_dir`. The validators always report `status='renderer_unavailable'`. Confirmed by `grep -rn "silhouette_render_dir"` — only the readers reference that key.

Result: a textbook Goodhart's-Law setup. The number certifies, the picture looks 2002.

### 4. Surface authoring graphs (designer / photo / layer) compile but never produce pixels
`lathe/surface_graph/designer_graph.py` builds a typed DAG and exposes a `DesignerGraph.evaluate(size=...)` that returns numpy buffers per output channel. **`evaluate(...)` is never called in the production path** (verified: `grep -rn "graph.evaluate\|DesignerGraph(" lathe/` only matches in tests / unrelated names). The compile step writes a MaterialX 1.39 document and stops. The actual pixel bytes that ship are still `bake_basecolor_map(...)` etc. with sin/cos/wood/metal `_pattern` noise and color-zone tinting (`bake_runtime.py:45–95`). So the "Substance-class three-mode authoring" feature is a typed IR + a sidecar `.mtlx` file — no pixels, no engine consumption pathway. This is exactly the "GOAL_PROGRESS reports complete, output looks bad" gap.

### 5. High-source for high→low bake is just a `mesh.subdivide()` of the low
`lathe/core/stages/optimize.py:525-571 _procedural_high_source_mesh` builds the "high mesh" by edge-length subdivision of the *runtime mesh*. Same shape, more verts. No procedural displacement, no plank-grain offset, no rivet protrusions, no bevel rounding micro-detail. So when `bake_highlow_normal_transfer_map` casts rays from the low to the high, the high's normals are nearly identical to the low's by construction; there is no detail to bake. `surface_highlow_realness` ends up at 0.0 (see `_metadata_surface_evidence`) which is consistent — but the validator gives partial credit elsewhere and certifies anyway.

The plank_displacement modifier does exist (`_apply_plank_displacement` line 398) and runs *on the LOD0 itself*, not on a high source — so any plank ripples become visible LOD0 geometry (good for silhouette but expensive) rather than baked-down high-frequency detail. There is no "high source ≠ low source" model anywhere in the codebase.

### 6. UV stage runs single-mesh xatlas, not the per-part variant; texel-density is not equalized
The build I ran reports `actual_adapter: "xatlas"` not `xatlas_per_part`. Code path in `lathe/core/stages/uv.py:101` chooses per-part only when `scene_part_count > 1 OR distinct_face_parts > 1`. Both conditions failed at runtime — likely because `topology_runtime.face_parts` collapsed to a single fallback name due to the topology fallback path. Net effect: xatlas sees a single fused mesh and packs charts ignoring per-part importance + texel-density weighting. The UV layout PNG shows the body lid taking ~25% of atlas while feet are scattered chartlets — texel density varies wildly.

Even when `apply_xatlas_uv_per_part` runs (`uv_ops.py:363`), it currently passes a uniform `pack_options.texels_per_unit = 1024.0` (line 438) to xatlas — importance weights from `_DEFAULT_PART_IMPORTANCE` (lines 21-41) are *recorded as telemetry* but no longer scale UV space. So `lid_panel` gets the same texels/m as `rivet`. Hero parts look soft, decorative parts look oversampled.

### 7. LOD0 → LOD3 is one-shot QEM decimate; no LOD-specific texturing or normal-baking-down
`lathe/stages/lod.py:119 decimate` is a deterministic QEM with normal-flip rejection — solid implementation. `build_lods(mesh, ratios, lod_config)` runs that decimate at each ratio (line 366). Result: 4 meshes with 100/50/25/10% face counts, **all sharing the same 2k texture**, all with the same UVs. No silhouette-preserving simplification, no LOD0-to-LOD3 normal-bake transfer, no impostor / billboard for LOD3. So LOD3 is geometrically chunky AND its normal map (already a flat-per-face object-space painting) gets stretched across decimated triangles. The LOD chain only saves draw calls, not memory and not visual quality.

### 8. Engine manifests are JSON sidecars; only Godot has a real importer
`lathe/engine_manifests/{godot,unity,unreal}.py` emit JSON like `lathe_for_godot.json` / `lathe_for_unity.json` / `lathe_for_unreal.json` describing what an engine plugin should do (LODGroup wiring, sockets, colliders, runtime-semantics resource). Engines cannot natively read these. Godot has a real addon at `editors/godot/lathe-addon/lathe_importer.gd` that calls `GLTFDocument.append_from_file` then post-processes sockets/collision/LODs — that's the one engine where end-to-end actually works. **Unity and Unreal have NO importer plugin in the repo** (`grep -rn` for `*.cs` / `*.uplugin` / `*.uasset` returns nothing — only `engine_manifests/{unity,unreal}.py` JSON emitters exist). For Unity/Unreal users, the asset arrives as a glb + JSON sidecar nobody reads.

Even on the Godot path, world-space normals will display incorrectly because Godot interprets normal maps as tangent-space by default (per `MetallicRoughnessMaterial`) and there's no flag flip happening.

### 9. Repair loop exists, but operators don't fix what's wrong
`lathe/repair_loop.py` orchestrates rounds with rollback. The classifier picks one of {local_repair, reselect_candidate, regenerate_with_patch, mesh-operators} based on diagnostic *names*. The mesh operators (`lathe/repair_operators.py`) are real:
- `seal_mesh` — calls `mesh.fill_holes()` + `merge_vertices` (real fix).
- `retopo_auto` — knocks `target_quads` down 25% and reruns topology. **But topology is broken**, so this does nothing useful.
- `reduce_tris` — calls QEM decimate to 70%. Drops detail without regaining quality.
- `repack_uvs` — re-runs xatlas. OK.
- `rebake_maps` — re-runs bake. **Same bake, same texture.** Doesn't fix the world-space normal bug or the per-face flat fill.
- `enforce_symmetry`, `normalize_pivots` — placeholder edits.

Diagnostics for "world-space normals," "fake AO," "high source identical to low," "texel density variance," "atlas under-utilized," "renders unavailable" don't exist, so the loop never tries to repair the actual quality blockers. It can fix watertight + tri budget, that's about it.

### 10. Atlas / decals layer barely populates the texture
`lathe/atlas_assembler.py` is **42 lines** (top of file: `from typing import Any\nfrom .surface_grammar import ...`). It builds an `atlas_assembly_ir` dict — i.e. a record of which decal libraries should map to which UV regions. It does not actually rasterize decals into the basecolor / normal channels. `apply_decal_overlays` in `bake_runtime.py` does a Pillow paste, but it's gated on `decal_masks` being declared and they aren't auto-generated. The atlas is empty space (verified by the basecolor PNG having huge black gaps).

## Stage-by-stage: real vs nominal

| Stage | Nominal | Reality |
|---|---|---|
| topology | "Blender hard-surface retopo with subsurf+bevel modifier stack and target_quads decimate" | (a) On Blender 5.x, adapter crashes on `import_scene.gltf` and silently falls back to merge_vertices+seal. (b) Even when it works, it's a modifier stack on input topology — not retopology. |
| uv | "xatlas-per-part with importance-weighted texel density and shared atlas" | (a) Runs single-mesh xatlas because `face_parts` distinct count is 1 after topology fallback. (b) Per-part variant ignores importance weights since `texels_per_unit` was equalized. |
| surface (graph) | "designer_graph / photo_fit / layer_stack three-mode authoring with MaterialX export" | Compiles a node IR + writes `material.mtlx`. `evaluate()` is never called. Graph IR doesn't reach any image bytes. |
| surface (bakes) | "PBR maps with high→low transfer" | Per-face `ImageDraw.polygon` fills. Normals: world-space, not tangent. AO: fake directional light. Curvature: face dihedral. High-source: subdivide of low. |
| validators | "Evidence-based certification including pixel-level silhouette / curvature distribution" | bbox metadata, sidecar reading, texture entropy of the noise we just baked. The renderer-dependent validators never run because no renderer writes their inputs. |
| optimize / LOD | "Hero LOD chain with decimation honoring polybudget" | Deterministic QEM decimate at fixed ratios. Same texture/UV across LODs. No silhouette-aware reduction. |
| package | "USD + glTF + previews + collision" | Works; produces glb/usd/lod_*.glb/collision_hull.glb + PIL preview pngs. This stage is fine. |
| engine_manifests | "Godot/Unity/Unreal-ready" | JSON sidecars only. Godot addon exists. Unity/Unreal addon does not. |
| repair_loop | "Autonomous multi-round semantic+mesh repair with rollback" | Loop machinery is real and rolls back. Operators fix watertight / tri budget, not surface/normal/AO/material plausibility. |

## Modularity smells

- **`lathe/surface_runtime.py:47-73`**: Two hardcoded family lists — `HERO_FAMILIES` and `V09_HERO_FAMILIES` — gate hero-quality surface emission. Includes literal `"brassbound_chest"`, `"console_terminal"`, `"procedural_vehicle"`, `"hero_sword"`, etc. New asset families silently drop to non-hero quality unless the maintainer edits this set. The router for hero behavior should dispatch on `intent.asset_class`, the part-tag set, or component types — not a hand-curated allowlist.
- **`lathe/assembly_kernel.py:8375-8500`**: Almost 130 lines of chest-only feature emission (`_chest_polybevel_modifier`, `_apply_chest_edge_class_bevels`, `_chest_brass_band_primitives`). Triggered by `if asset_graph.family == "brassbound_chest"` at line 8642. That's the chest fixture leaking into the kernel as a hardcoded code path. Generalization: declarative "edge-class bevel" + "horizontal band primitive" feature ops, dispatched from authored geometry blocks.
- **`lathe/asset_graph.py:84` and `:1574`**: hardcoded family detection by part-name set — `{"lid_panel", "front_hatch", "lock_plate"} <= set(parts) → "brassbound_chest"`. Anything that includes these tokens gets chest blueprints applied.
- **`lathe/blueprints/containers.py:_chest_blueprint`**: the chest-specific blueprint factory; OK as a fixture, problem only if other "container-class" blueprints cant share its layout primitives.
- **`lathe/asset_quality/highlow_relation.py:107`**: chest-only highlow relation override.
- **`lathe/core/uv_ops.py:21-41 _DEFAULT_PART_IMPORTANCE`**: a hand-curated `(part_name_token, weight)` tuple set with explicit `body, lid_panel, brass_band, hinge, foot, lock_plate, rivet, ...`. Smells like "the parts the chest declares" rather than a tag-driven importance derivation. New asset classes need to be added by editing this tuple. Ought to be importance derived from `part.tags` (`hero`, `support`, `decorative`) + a configurable mapping in user-editable rules.
- **`lathe/materials.py:632`**: token-based dispatch (`if any(t in lname for t in ("handle","hinge","lock","frame",...))`) is OK-ish as a fallback but is fundamentally substring-soup that won't generalize past the seven asset families it was tuned for.

## Hidden capability (implemented but unreachable)

These are real chunks of code that aren't in the production path — fixing the wiring would unlock visible quality immediately:

1. **`DesignerGraph.evaluate(size)` in `lathe/surface_graph/designer_graph.py:122`.** Returns numpy buffers per channel from a typed surface DAG. If `bake_runtime.py` emitted those buffers as PNGs (via `Image.fromarray`) instead of `ImageDraw.polygon`, the basecolor / normal / height / AO would be coherent multi-octave noise + brick + warp + AO from height — actually look like Substance output. The compile step is already in the pipeline (`_compile_surface_graph_handoff` in `surface_runtime.py:752`); just nothing consumes the buffers.
2. **`apply_xatlas_uv_per_part`** with importance weights. The function exists, accepts a `multi_part_scene`, and would equalize texel density per part if `pack_options.texels_per_unit` were actually scaled by `norm_weights[i]` (currently the comment says importance weights are surfaced as telemetry only — see `uv_ops.py:413-417`). Two-line change to bias the per-part xatlas Atlas pack scale.
3. **Multi-part topology preservation step** (`core/stages/topology.py:456-497`) does correctly recover Blender's 18-part scene when Blender ran. So *if* the Blender adapter were fixed to work on Blender 5.x, downstream stages would already use the real multi-part scene. The blocker is one-line: the `bpy.ops.import_scene.gltf(filepath=args.input)` call signature changed; needs to be `bpy.ops.import_scene.gltf(filepath=args.input)` updated for Blender 5.x or replaced with `bpy.ops.wm.append`/`bpy.ops.import_mesh.gltf` per the new API.
4. **Per-pixel raycast bake** could reuse the `_ray_projected_high_faces` infrastructure (`bake_runtime.py:538`). Today it casts one ray per low-face centroid; the same code structure can cast one ray per UV-texel by enumerating `(u,v) → world position via barycentric reverse-map` and writing per-pixel rather than per-polygon. The infrastructure (high mesh, low mesh, tangent frames, `intersects_location`) is all there — it's just looped at the wrong granularity.
5. **`silhouette_render_dir`** validator: ready to consume PNGs at the configured path. A 200-line offscreen renderer (Mitsuba / glcontext / `pyrender`) writing 512×512 silhouette masks at front/side/iso would unlock all three pixel-level validators (silhouette_multi_angle, frequency_energy, soft_silhouette). The validator side is done.

## Calibration questions for synthesis

1. **Do we accept "no Blender at all" as a path forward?** The current adapter is a Subsurf+Bevel+Decimate stack — it doesn't really retopologize. If the answer is "ship without Blender," then Lathe needs an in-Python retopologizer (quadriflow bindings, geogram, instant-meshes). If the answer is "Blender required," then the adapter must be fixed AND upgraded to a real quad-flow pass.
2. **Where is the per-texel bake budget?** Going from per-face polygon-fill to per-texel raycast is a ~100x cost increase at 2k. Acceptable on a hero asset (still tens of seconds), prohibitive at fleet scale. Probably need: per-texel bakes for hero, polygon-fill for background props, with a quality-axis switch — currently the only knob is the family allowlist.
3. **Does Lathe own the renderer, or does it rely on a Blender Cycles offscreen pass?** Validators want silhouettes from real renders. Adding a Cycles bake script is straightforward; adding an in-Python Mitsuba pass keeps Lathe self-contained but is heavier. Picking one unblocks ~5 dormant validators.
4. **Is the surface-graph IR the real target, or just a handoff?** If `DesignerGraph.evaluate` is the future, kill the `bake_runtime.py` legacy bakers and ship only the graph-rasterized PNGs. If MaterialX export is the target (engines consume `.mtlx`), the bakers can stay but should at least produce tangent-space normals.
5. **What's the canonical test of "looks like SOTA"?** GOAL_PROGRESS reports completion percentages, but the certifier scored a chest-with-broken-textures at 0.888. A side-by-side render of `tmp_audit_pipe/.../package/brassbound_chest.glb` rendered in Cycles vs a hand-authored reference would set the bar more honestly than a metric — and would expose the world-space-normals bug in 30 seconds.
