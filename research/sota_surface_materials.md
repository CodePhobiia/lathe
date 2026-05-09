# SOTA in procedural surface and material authoring (Lathe v2)

Audit context, Lathe state, and concrete fixes ordered by ROI. Standalone-procedural mandate respected throughout — every recommendation is algorithmic + curvature/AO masks + MaterialX. AI image-gen is never the primary path.

## 0. Lathe today, with receipts

A grep + read pass on `lathe/surface_runtime.py`, `lathe/bake_runtime.py`, `lathe/surface_graph/*.py` confirms the pipeline-auditor's diagnosis and adds three more pixel-level findings:

1. **`DesignerGraph.evaluate(size)` is dead code.** `lathe/surface_graph/designer_graph.py:122` defines a real per-channel buffer evaluator. `lathe/surface_runtime.py:752 _compile_surface_graph_handoff` only writes the MaterialX XML sidecar via `compile_materialx`; the numpy buffers it can produce are never consumed. The texture pipeline runs `bake_basecolor_map(...)` etc. from `bake_runtime.py` instead.
2. **`bake_normal_map` is broken.** `bake_runtime.py:492-503` writes per-face *world-space* face normals as flat polygon fills into the normal RGB texture. That is not a tangent-space normal map. Loaded into Unreal/Unity it will produce wrong lighting at every face that is not aligned with the world frame. There is per-face tangent-frame code at `bake_runtime.py:638` (`_low_face_tangent_frames`) but the simple `bake_normal_map` skips it.
3. **`bake_curvature_map` is per-face dihedral angle.** `bake_runtime.py:506-516`, `832-840` — curvature is computed as max edge-dihedral angle per low-poly triangle, then drawn flat into the UV polygon. On a low-poly cube this means curvature is binary at the 12 edges; *all* "edge wear" then concentrates on box silhouettes, never on real geometry detail.
4. **`bake_ao_map` is upward-bias-only.** `bake_runtime.py:843-853` writes `72 + max(0, normal_y) * 150`. Bottom faces are dark, top faces are bright. That is not occlusion — it is `dot(N, +Y)` lighting.
5. **No height map, no slope blur, no edge detect.** The seven-stage designer recipe is allocated but never *evaluated* into pixels for the bake. Procedural patterns are sin/cos: `_wood_pattern`, `_metal_pattern`, etc. at `bake_runtime.py:58-157`.
6. **MaterialX serialization is structurally accurate** (1.39, `standard_surface`, `nodegraph` with `heighttonormal`, `ambientocclusion`, `curvature`, `mix`) — **but** the node category names are not all part of the MaterialX 1.39 PBR spec. `splatter`, `mask_expression`, `material_lookup`, `blend_overlay`, `constant_passthrough` are Lathe-private. Houdini/Maya/Blender will not resolve them. The MaterialX *frame* is correct; the *node vocabulary* needs to be 1.39 stdlib only or wrapped in a custom `nodedef`.

The good news: the IR scaffolding (typed nodes, layers, masks, MaterialX shape) is mostly there. The bad news: the bake never sees it. **Wiring `DesignerGraph.evaluate` and `LayerStack.evaluate` into the bake is the biggest single quality lever in the codebase.**

---

## 1. Substance Designer-class graphs (deepish)

### What SOTA looks like
Substance Designer is now used in the majority of AAA games. Designer 14 (2025) added a Kuwahara stylization filter and a `curvature_smooth` node. The atomic node-class budget that covers ~95% of tileable PBR is small:

- **Generators**: `noise2d` (Perlin/Simplex/Worley/Gabor), `tile_generator`, `tile_sampler` (bricks/scales/weave with per-cell jitter on hue/scale/rotation), `shape` (disc, square, polygon, gradient_radial).
- **Filters**: `blur`, `slope_blur` (anisotropic blur driven by a heightmap), `directional_warp`, `curvature_smooth`, `edge_detect`, `levels`, `gradient_map`.
- **Conversion**: `height_to_normal` (Sobel of height + normalize), `normal_to_curvature`, `height_to_ao` (multi-tap horizon AO), `normal_to_height` (rare).
- **Compositing**: `blend` (16+ Photoshop modes), `mix`, `mask_expression`, `histogram_scan`, `multi_switch`.
- **Mesh-aware (in Substance Painter / Designer mesh-based generators)**: `cracks_weathering` reads curvature + AO + position.

The Substance "smart material" pattern is layered: 4–8 named layers, each with `{material, mask}`, where masks compose `curvature * (1-AO) * worldY * dirt_noise`. Each mask is a *generator graph*, not a paint stroke.

### What Lathe has vs. what's missing
Lathe's node taxonomy at `lathe/surface_graph/nodes.py` already has `Noise, Pattern, ShapeSplatter, Warp, Blend, Normal, CurvatureSmooth, AO, Mask, Layer, Output` — directly comparable to Designer atomics. Missing nodes that matter:

- **`SlopeBlur`** — drives chipped/eroded edges and rust streaks. The single most expressive Designer node.
- **`HistogramScan` / `Levels`** — turns a noise field into a binary or soft-edged mask with a `position` + `range` knob. Underpins all generator-style masks.
- **`EdgeDetect`** (Sobel on height) — produces a sharp curvature-style mask straight from height.
- **`GradientMap`** — colorize a grayscale field through a 1D LUT. The only *correct* way to author painted-metal palettes (RGB lerp through HSV is wrong).
- **`Tri2D` / `MultiSwitch`** — graph-time A/B/C selection driven by a parameter. Used to switch surface dialect (`hard_metal` vs `painted_metal` vs `wood`).
- **`PositionMask` / `WorldYMask`** — needed for "top-dirt" / "bottom-rust" effects in object/world space. Lathe has `mask_top` as a string preset; should be a real node reading object-space position.

### Maps to Lathe via
`lathe/surface_graph/nodes.py` (add 5–6 nodes), `lathe/surface_graph/designer_graph.py` (replace 7-stage hand-recipe with a graph that uses them), and **critically** `lathe/surface_runtime.py:1031-1090` to call `DesignerGraph.evaluate(size=2048)` and use those buffers as the final basecolor/normal/roughness/ao/curvature instead of the current sin/cos bake.

DSL surface: extend `surface_program designer_graph { ... }` with `node` declarations or a `recipe` selector (`recipe: "weathered_metal"`).

Visible-quality lift: large. This is the difference between flat-fill polygons and Substance-class procedural texture. Effort: **M** — node implementations are ~30–80 lines each in numpy; wiring evaluate into bake is ~60 lines.

---

## 2. MaterialX & USD-shade interop

### SOTA
- **MaterialX 1.39.4** (Sept 2025) is the lingua franca: WebGPU shading language target, hex-tiled and lat-long images, NanoColor color spaces, 2D fractals, animated materials.
- **OpenUSD 25.05** is sync'd to MaterialX 1.39.3, so a `.usda` importing a `.mtlx` round-trips today in Houdini Solaris, Maya USD, Blender 4.x.
- **Two PBR shaders** in 1.39: `standard_surface` (Autodesk-origin, Arnold/USD default) and `OpenPBR Surface` (new, 2024) with shader-translation graphs between them. UsdPreviewSurface is the lowest-common-denominator and is what `gltf` validators expect.
- **The big interop unlock**: a MaterialX nodegraph with stdlib nodes (`noise2d`, `tiledimage`, `heighttonormal`, `mix`, `range`, `image`) loads into any MaterialX-aware renderer **without baked textures**. Author once, render anywhere.

### Lathe state
`lathe/surface_graph/materialx.py` correctly emits MaterialX 1.39 with `standard_surface`, `nodegraph`, `heighttonormal`, `curvature`, `ambientocclusion`, `mix`. Three real gaps:

1. **Non-stdlib categories**: `splatter`, `mask_expression`, `material_lookup`, `blend_overlay`, `constant_passthrough`, `tiledimage` (used as a procedural pattern but is actually an image-sampling node). Houdini/Maya/Blender silently drop unknown categories. Either map them onto stdlib (`splatter` → `tile_sampler` with circular shape; `mask_expression` → composition of `range` + `multiply`; `blend_overlay` → `screen` or `mix`+`max`) or emit a `nodedef` block declaring them as Lathe-namespaced custom nodes.
2. **`tangentspace`** — a tangent-space normal map should drive `standard_surface.normal` through `<normalmap>` not directly from `vector3`. The current `_channel_to_mtlx_input` maps `normal → "normal"` raw.
3. **Color space declarations**: `colorspace="lin_rec709"` is set on root in `_write_materialx_direct_xml:380`. Each `<image>`/`<tiledimage>` node should declare its own colorspace (`srgb_texture` for basecolor, `lin_rec709` or `none` for normal/roughness/AO). Without this, basecolor double-gamma-corrects in Houdini.

### Maps to Lathe via
`lathe/surface_graph/materialx.py` (the four functions). Add a 1.39-stdlib lowering layer; keep the dict-shaped IR; produce only stdlib categories. Add a smoke test that loads the emitted `.mtlx` with the optional `MaterialX` Python module and asserts no validation warnings.

DSL surface: none — it's a serialization fix.

Visible-quality lift: medium directly (correct color in DCCs), large indirectly (unblocks "load Lathe asset in Houdini/Blender for review/repair without re-baking").  Effort: **S** — ~150 lines.

---

## 3. Trim sheets & decals as authoring primitives

### SOTA
The trim-sheet pattern is the second-biggest lever for hard-surface AAA quality after smart materials. DECALmachine, DecalMaster, TrimSheetFast all converge on the same data shape:

- **Atlas**: a 2K/4K texture (basecolor+normal+ORM+id) where each rectangular sub-region is a named decal/trim slot.
- **Sidecar**: a `data.json` with `{slot_name: {uv_rect, type: trim|decal|seam, repeat: x|y|none, projection: planar|surface}}`.
- **Authoring**: artist marks an edge loop "this is trim slot `metal_strip_03`" or stamps a decal "warning_label_07" at a UV face. The mesh stores per-face references into the atlas.
- **Layered detail**: macro from triplanar smart material + micro-detail from trim-sheet bevels + unique callouts from decals.

### Lathe state
`std/` has `trim_sheets` and `decal_libraries` as named string handles. `lathe/surface_runtime.py:635 _surface_library_decals` lowers library names into hardcoded decal token lists ("hazard_stripe", "edge_rub"). There is no atlas, no UV rect, no per-face binding — the decal is a tag the bake interprets via `apply_decal_overlays`. `manifest["trim_sheets"]` is a list of strings.

### What to add
- **Trim-sheet IR**: `TrimSheet { id, atlas_texture, slots: [{name, uv_rect_px, repeat}] }`. Pre-bake a 2K trim-sheet atlas with tile_sampler-generated bevels/grooves/panels at known UV rects.
- **Per-face trim binding**: `assembly_kernel` already produces a `bake_groups` list with face groups. Add `trim_slot` and a UV transform so the chart's UV is a sub-rect of the trim atlas instead of a unique chart in xatlas. This is **the move that makes long edge details look hand-authored at low texel cost.**
- **Decal placement IR** (Lathe already has `surface_story_placement_plan`): extend each placement with `atlas_slot` + projected UV, then draw via `PIL.Image.alpha_composite` not `ImageDraw.polygon`.

### Maps to Lathe via
`lathe/atlas_assembler.py` (currently 42 lines — needs a real trim-atlas builder), new `lathe/surface_graph/trim_sheet.py`, hook in `lathe/uv_runtime.py` (UV transform for trim charts) and `lathe/bake_runtime.py:apply_decal_overlays`.

DSL surface: extend `trim_sheet { id ... slots { ... } }` and `assembly_rules` to allow `edge_loop -> trim_slot:metal_strip_03`.

Visible-quality lift: large for any asset with edges, panels, seams (i.e. all hard-surface). Effort: **L** — touches IR, UV, and bake.

---

## 4. Wear & weathering programs (curvature-driven)

### SOTA
- Curvature mask = (`+255` convex, `0` concave, `128` flat). Edge wear = `histogram_scan(curvature, position=0.7, range=0.1) * (1 - dirt_noise)`. Cavity dirt = `histogram_scan(1-curvature, position=0.7, range=0.1) * (1 - AO)`.
- **Curvature must come from a real high-poly source**, transferred via cage-projected raycast. Curvature off the *low-poly* mesh gives garbage (only edge-loops, no real surface curvature). This is what Marmoset Toolbag, xNormal, Substance Painter all do.
- ZBrush/Blender pattern: bake curvature + AO + position + thickness *first*, then *every* generator reads them. Smart materials are then "intelligent Photoshop layers that understand 3D surfaces."
- "Real" wear is *anisotropic* + *flow-driven*: rain streaks run downward (use object-space `+Y`), wear concentrates on grip points (use `worldHeight` masks), patina pools in concave regions (use AO + position).

### Lathe state
- `lathe/surface_runtime.py:1031-1090` already builds a procedural high-source mesh (`_procedural_high_source_mesh`) and ray-projects high-face-normal/curvature to low UVs via `bake_highlow_normal_transfer_map` and `bake_highlow_curvature_transfer_map`. **This is the right architecture and works.** The trace records `projection_quality` with a `decision` of `ray_primary` / `mixed_ray_fallback` / `fallback_primary` based on hit ratios.
- *But* the procedural high source is just `subdivide_to_size` of the low — same surface, more triangles. Curvature off it is still flat. `bake_curvature_map(low_mesh)` falls back when the high source is missing, and computes only edge dihedrals.
- The wear masks themselves (`_surface_wear_masks`) at `bake_runtime.py:~720` *do* read curvature and AO — so as soon as curvature improves, wear improves automatically.

### What to fix
1. **Real high-poly procedural source**: instead of subdividing the low-poly, take the ShapeIR primitives (`subdivision_box`, `revolved_profile`, `swept_profile`, `extruded_profile`, `torus`) and tessellate each at *its* native curvature (chamfered cube edges, fillets at radius). The high-source then has actual curvature where edges are rounded — and curvature transfer fills the bevel strip in UV space. Lathe already has a "shape IR v2" that supports per-corner radii (commit `d4f7ced`); use it.
2. **Histogram scan masks instead of multiplications**: replace `np.clip(curvature - 0.48, 0, 0.42) * wear * 0.48` with a parameterised `_histogram_scan(curvature, pos, range)` that gives a clean tunable mask. Authors get one knob per mask.
3. **Drive direction from object space**: pass per-pixel object-space position (already implicit in UV→3D bake) into the wear masks so streaks run "down" and dirt pools "below".

### Maps to Lathe via
`lathe/asset_quality/shape_ir_v2.py` + `lathe/surface_runtime.py:_procedural_high_source_mesh` (replace subdivision with primitive-native tessellation), `lathe/bake_runtime.py:_surface_wear_masks` (add histogram_scan), `lathe/bake_runtime.py:bake_curvature_map` (object-space position channel).

DSL surface: extend `surface_program` with `wear { edge_wear, cavity_dirt, top_dust, streaks }`; each takes a histogram pos+range.

Visible-quality lift: large. This is what makes weathering "read" instead of "look noisy". Effort: **M**.

---

## 5. PBR correctness across engines

### SOTA / what each engine expects
- **Tangent space**: MikkTSpace is universal — Blender (≥2.57), xNormal (≥3.17.5), glTF spec, Unity, Godot. Unreal accepts MikkTSpace via FBX import options.
- **Green channel convention**:
  - **OpenGL / Y+ / right-handed**: Blender, Maya, Modo, Toolbag, **Unity** (default), **Godot** (default).
  - **DirectX / Y- / left-handed**: 3ds Max, **Unreal Engine** (default), CryEngine, Source.
- **glTF spec**: MikkTSpace + OpenGL Y+ — but glTF 2.0 does *not* convert; whatever you ship is what's sampled.
- **Color spaces**: basecolor sRGB, normal/roughness/metallic/AO **linear**. Unreal autodetects from filename suffix `_N` / `_ORM`. Unity uses the import inspector flag. Godot uses `srgb=enable/disable` in the resource.
- **Channel packing**: ORM = AO (R), Roughness (G), Metallic (B). This is the de-facto standard for Unity HDRP, Godot 4, Unreal "ORM" packing, glTF `metallicRoughnessTexture` (G+B; AO separate).

### Lathe state
- `lathe/pbr_deriver.py` calls `combine_orm` to produce ORM correctly. ✓
- `lathe/bake_runtime.py:492-503 bake_normal_map` writes **world-space** face normals into the normal map. **Wrong.** This image won't decode correctly in *any* engine — the math is `(face_normal_world * 0.5 + 0.5)`, but engines expect tangent-space `(0.5, 0.5, 1.0)` neutral. This is the highest-confidence bug in the codebase.
- `_low_face_tangent_frames` at `bake_runtime.py:638` exists but is only used by `bake_highlow_normal_transfer_map`. The fallback `bake_normal_map` skips it.
- No engine-specific export variant. A single `normal.png` can't satisfy both Unreal and Unity if green flip is required.

### What to fix
1. **Fix `bake_normal_map`** to use `_low_face_tangent_frames`: per-face transform to tangent space, write `(tx, ty, tz)*0.5+0.5` per polygon. When there is no high-poly to project from, the result should be the neutral `(128,128,255)` everywhere, not a per-face flat color.
2. **Per-engine export variant**: in `lathe/engine_manifests/{unreal,unity,godot}.py`, emit a `normal_dx.png` for Unreal and a `normal_gl.png` for Unity/Godot/glTF. One bake, one cheap green-flip on copy. Document the convention in the manifest JSON.
3. **glTF/USD packaging**: confirm `core/stages/package.py` writes `metallicRoughness` with G=roughness, B=metallic, no R; and a separate `occlusionTexture`. ORM should be a redundant supplemental.

### Maps to Lathe via
`lathe/bake_runtime.py:bake_normal_map`, `lathe/engine_manifests/{unreal,unity,godot}.py`, `lathe/core/stages/package.py`.

DSL surface: none.

Visible-quality lift: catastrophic if not fixed (lighting is wrong everywhere). Effort: **S** — ~80 lines.

---

## 6. Procedural shaders beyond textures (triplanar, runtime parametric)

### SOTA
- **Triplanar projection** projects a tileable texture three times along world XYZ, blends by `pow(abs(world_normal), k)`. No UV unwrap required, no seams. Standard for terrain, large hard-surface, anything with poor UVs.
- **Per-engine runtime parametric**: Unreal Materials (HLSL DAG), Unity ShaderGraph (URP/HDRP), Godot VisualShader, MaterialX (renderer-agnostic). The MaterialX-as-runtime path is what unlocks "author once, ship to all four."
- **Substance .sbsar**: a *parameterised* binary that re-bakes textures at runtime per-call. The MaterialX equivalent for procedural-only graphs (no images) is a `nodegraph` with explicit `<input>` parameters; consumers expose those as material instance knobs.
- **Compact PBR**: pack basecolor luminance + roughness + metallic + AO into one RGBA texture, derive chroma from a gradient. Unity's `compact_pbr` Sub Graph does six layers of lerp from one texture lookup.

### Lathe state
- Triplanar: not implemented. UVs come from xatlas; `apply_decal_overlays` operates in UV space.
- Runtime parametric: only via the MaterialX sidecar, which is currently emitted with non-stdlib categories (see §2). The stdlib fix unlocks Unreal/Maya/Blender/Houdini directly.
- No engine-specific HLSL/ShaderGraph emit. This is fine — MaterialX 1.39 + WebGPU SL is a better target.

### What to add
- **Triplanar fallback**: when a chart's UV stretch ratio exceeds a threshold (xatlas reports it), emit a `triplanar` MaterialX node group as the basecolor sampler. Even cheaper: emit `<triplanar>` for *all* large flat surfaces ≥X cm² as a redundant secondary texture coordinate.
- **Parametric MaterialX**: lift `surface_program designer_graph` knobs (palette, frequencies, wear amount) to nodegraph `<input>` declarations so a downstream Houdini artist can dial them.

### Maps to Lathe via
`lathe/surface_graph/materialx.py` (add `triplanar` and `<input>` lifting), `lathe/surface_graph/designer_graph.py`.

Visible-quality lift: medium for terrain/large props; small for hero hard-surface (UVs already exist). Effort: **M**.

---

## 7. Stylization beyond PBR

### SOTA
- **Cel/anime**: replace `standard_surface` with `<surface_unlit>` + ramp LUT. SIGGRAPH Asia 2021 has a "procedural matcap" paper where each surface samples a 1D `sphere_normal_to_color` LUT in tangent or world space.
- **Painterly**: Kuwahara filter (Designer 14 ships this), bilateral blur, multi-tap stroke alignment.
- **MatCaps**: pre-baked sphere lighting; `viewspace_normal -> uv -> sample`. Cheap, controllable, ZBrush-pattern.
- **Ramp shading**: 1D gradient texture indexed by `dot(N, L)` quantized to 2/3/4 bands. Authoring is just a `gradient_map` node fed by `surface.diffuse_term`.

### Lathe state
- The roadmap names "Bands A-G" of stylization (per task brief). Not implemented in surface code — `lathe/materials.py` and `lathe/surface_runtime.py` are PBR-only.
- `lathe/surface_graph/nodes.py` would need a `RampLUT`, `MatCap`, `Kuwahara` node.

### What to add
- **`stack: cel|painterly|pbr`** in `surface_program`. Cel emits a MaterialX `<surface_unlit>` shader with a `<gradient_map>` node group instead of `<standard_surface>`. PBR-derived basecolor still works as input.
- **MatCap node**: a 2D image sampled by view-space normal. Procedural matcap baking from a few `point_light` + `material_color` directives.

### Maps to Lathe via
`lathe/surface_graph/nodes.py` (3 nodes), `lathe/surface_graph/materialx.py` (alt shader emit), new `lathe/surface_graph/stylized.py`.

Visible-quality lift: large for stylized targets; doesn't affect PBR path. Effort: **M**.

---

## 8. Color science

### SOTA
- **ACEScg** is scene-referred linear with AP1 primaries and D60 white point. **sRGB** is display-referred with gamma ~2.2 and D65. Mixing them silently gives visibly oversaturated red/orange.
- For game asset authoring, the workable rule: **basecolor textures live in sRGB**, the *engine* converts to linear at sample time; everything else (normal, roughness, metallic, AO, height) is linear from authoring through rendering.
- **Procedural palette generation**: HSV is a poor space for harmony — equal hue rotations don't preserve perceived lightness. **LCh / OKLCh / OKLab** is what palette generators actually use (poline, colormaker). Five-color schemes via golden-ratio hue rotation in OKLCh produce "designer-quality" palettes.

### Lathe state
- `std/palettes/` has named palettes as RGB triples.
- Material wear blending in `bake_runtime.py:_material_layer_color` and `bake_basecolor_map` mixes in **straight RGB**, not perceptual space. Mixing dark brown with bright orange in RGB gives muddy mid-grey; the same mix in OKLab gives the perceived correct intermediate.
- No color space tagging on outputs. PNGs are saved as is; consumers must guess.

### What to fix
1. **OKLab blending**: in `bake_basecolor_map` and `bake_wear_mask`, convert RGB→OKLab, lerp, OKLab→RGB. ~30 lines, no dependencies (formulas are public, ~10 lines of numpy).
2. **Palette synthesis**: in `std/palettes/`, replace literal RGB triples with declarative palettes (`base_lch + harmony: split_complementary + count: 5`). `lathe/materials.py` resolves them at compile time.
3. **Color space tagging**: write a sidecar `.png.json` per output map declaring `colorspace: srgb|linear`. MaterialX nodegraph references the same.

### Maps to Lathe via
`lathe/bake_runtime.py:bake_basecolor_map` + new `lathe/color_ops.py`, `std/palettes/*`, `lathe/materials.py`.

Visible-quality lift: medium and *cheap* — color is half of "looks good." Effort: **S**.

---

## 9. Baking that doesn't suck

### SOTA
- **Cage offset**: a slightly inflated copy of the low-poly mesh; ray origins. Small offsets (1–4 cm in our units) work for most assets; offset must exceed the largest high-poly bump on every face or rays miss.
- **Hit-distance limit**: reject ray hits beyond `max_distance` so a far face on the back side doesn't bake into the front.
- **AA samples**: 4×4 = 16 supersample per texel kills bake aliasing. Marmoset Toolbag default is 4×.
- **Edge padding/dilation**: minimum padding = `2^mip_levels / 2` pixels. For a 2K with full mip chain that's 1024 — impossible. Practical: 16–32 px at 2K, plus padding-aware mip generation. xNormal's dilation filter is the reference.
- **Tangent-space transfer**: high-poly normal in *high* tangent frame projected to *low* tangent frame via shared world space. Substance Painter and Marmoset both do this; the math is in the Marmoset bake tutorial.

### Lathe state
- Cage offset and max ray distance: **already there** at `surface_runtime.py:1002-1004` and `bake_runtime.py:_ray_projected_high_faces`. ✓
- Bidirectional rays: ✓
- Projection-quality reporting: ✓ (`_projection_quality` decision tree).
- AA supersampling: ✗ — `ImageDraw.polygon` is single-sample.
- Edge padding: partial — `pad_low_coverage_atlas_maps` pads in UV space but not via mip-aware dilation.
- Tangent-space transfer: ✓ in `bake_highlow_normal_transfer_map`, ✗ in fallback `bake_normal_map`.

### What to add
- **Real rasterizer**, not `PIL.ImageDraw.polygon`. Even a tiny custom polygon rasterizer with 4×4 supersample would turn the bake from polygon-flat-fill into per-texel raycast. This is needed for any of §1–§4 to pay off.
- **Edge padding via mip-aware dilation**: after bake, expand each UV island outward by 32 px using a flood-fill in UV space (xNormal-style).
- **Per-output AA**: 16 spp for normal/curvature/AO; 1 spp for ID map (preserves hard masks).

### Maps to Lathe via
`lathe/bake_runtime.py` (a new `_rasterize_uv_polygon_with_samples` replacing the `ImageDraw.polygon` calls in `bake_normal_map`, `bake_curvature_map`, `bake_ao_map`, `bake_id_map`).

Visible-quality lift: large — fixes the visible polygon edges in maps. Effort: **M**.

---

# Top 5 ROI-ordered recommendations

1. **Wire `DesignerGraph.evaluate` and `LayerStack.evaluate` into `build_surface_bundle`.** The numpy buffers exist, the typed IR exists, the MaterialX sidecar exists — the bake just doesn't call any of it. Replace the sin/cos `_profile_pattern` path in `bake_runtime.py:421 bake_basecolor_map` and friends with `graph.evaluate(size=2048)["basecolor"]` etc. Add the missing `SlopeBlur`, `HistogramScan`, `EdgeDetect`, `GradientMap`, `PositionMask` nodes (~200 lines numpy total). **Effort: M. Quality lift: largest single change in the codebase.** *Files:* `lathe/surface_runtime.py:1031-1090`, `lathe/surface_graph/designer_graph.py`, `lathe/surface_graph/nodes.py`.

2. **Fix `bake_normal_map` to be tangent-space.** The current implementation writes world-space face normals as flat polygon fills — broken everywhere. Use the existing `_low_face_tangent_frames` + a real per-texel rasterizer (4×4 SS). **Effort: S–M. Quality lift: catastrophic-bug fix; lighting will become correct.** *Files:* `lathe/bake_runtime.py:492-503`, `lathe/bake_runtime.py:638` (already-built).

3. **Procedural high-source from ShapeIR primitives, not subdivision.** Instead of `subdivide_to_size` of the low mesh (which has no real curvature), tessellate each ShapeIR primitive at its native curvature (radius, fillet, chamfer). Then every existing bake transfer (`bake_highlow_curvature_transfer_map`, `bake_highlow_normal_transfer_map`) automatically delivers real bevel-strip detail — no other changes required. **Effort: M. Quality lift: large; "edge wear" will appear on actual bevels not box silhouettes.** *Files:* `lathe/surface_runtime.py:_procedural_high_source_mesh:299-350`, `lathe/asset_quality/shape_ir_v2.py`.

4. **Trim-sheet IR + per-edge UV binding.** Pre-bake a 2K trim atlas per family (metal strips, panel bands, ornate brass), bind edge loops to slots in `assembly_kernel`, sub-rect their UVs to the atlas. **Effort: L. Quality lift: large for any hard-surface; this is the AAA differentiator.** *Files:* new `lathe/surface_graph/trim_sheet.py`, `lathe/atlas_assembler.py` (currently 42 lines), `lathe/uv_runtime.py`, `lathe/bake_runtime.py:apply_decal_overlays`.

5. **MaterialX 1.39 stdlib lowering + colorspace + per-engine normal flip.** Map `splatter`, `mask_expression`, `material_lookup`, `blend_overlay` onto MaterialX 1.39 stdlib categories so the sidecar actually loads in Houdini/Blender. Tag each `<image>` with `colorspace`. Emit `normal_gl.png` (Unity/Godot/glTF) and `normal_dx.png` (Unreal) variants. **Effort: S. Quality lift: medium directly (correct rendering in DCCs, no green-channel bug); large indirectly (unblocks third-party validation/repair without re-baking).** *Files:* `lathe/surface_graph/materialx.py`, `lathe/engine_manifests/{unreal,unity,godot}.py`, `lathe/core/stages/package.py`.

---

## Sources

- [Substance 3D Designer key concepts](https://helpx.adobe.com/substance-3d-designer/substance-compositing-graphs/substance-compositing-graph-key-concepts.html)
- [Substance 3D Designer 14 review (Creative Bloq)](https://www.creativebloq.com/3d/adobe-substance-3d-designer-14-0-review-stylisation-at-your-fingertips)
- [Substance 3D Designer Slope Blur](https://helpx.adobe.com/substance-3d-designer/substance-compositing-graphs/nodes-reference-for-substance-compositing-graphs/node-library/filters/blurs/slope-blur.html)
- [Substance Designer Cracks Weathering](https://experienceleague.adobe.com/en/docs/substance-3d-designer/using/substance-graphs/nodes-reference-for-substance-graphs/node-library/mesh-based-generators/weathering/cracks-weathering)
- [Smart Materials in Substance Designer (FlippedNormals)](https://library.flippednormals.com/product/smart-materials-in-substance-designer-for-games-16121)
- [MaterialX home](https://materialx.org/)
- [MaterialX PBR Spec (GitHub)](https://github.com/AcademySoftwareFoundation/MaterialX/blob/main/documents/Specification/MaterialX.PBRSpec.md)
- [MaterialX 1.39 releases](https://github.com/AcademySoftwareFoundation/MaterialX/releases)
- [MaterialX USD utilities](https://kwokcb.github.io/materialxusd/)
- [PBR Material Interoperability — MaterialX, USD, glTF](https://metaverse-standards.org/wp-content/uploads/PBR-material-interoperability.pdf)
- [DECALmachine trim sheets](https://machin3.io/DECALmachine/docs/trim_sheet_creation/)
- [Beyond Extent — Trim sheets deep dive](https://www.beyondextent.com/deep-dives/trimsheets)
- [TrimSheetFast](https://trimsheetfast.com/for)
- [DecalMaster (Maya)](https://www.xealot.tech/decalmaster/introduction/)
- [3DCoat — Cavity and Curvature maps](https://3dcoat.com/documentation/2025/01/31/cavity-and-curvature-maps/)
- [Mastering Smart Materials Creation In Substance Painter (CyPaint)](https://cypaint.com/article/how-to-create-smart-materials-in-substance-painter)
- [Marmoset Toolbag baking tutorial](https://marmoset.co/posts/toolbag-baking-tutorial/)
- [Polycount — Texture Baking](http://wiki.polycount.com/wiki/Texture_Baking)
- [Polycount — Normal Map Technical Details](http://wiki.polycount.com/wiki/Normal_Map_Technical_Details)
- [Marmoset Toolbag — Tangent & Handedness](https://docs.marmoset.co/docs/tangent-handedness/)
- [Polycount — Edge padding](http://wiki.polycount.com/wiki/Edge_padding)
- [Kyle Halladay — Mip Map Artifacts in Atlassed Textures](https://kylehalladay.com/blog/tutorial/2016/11/04/Texture-Atlassing-With-Mips.html)
- [Substance Painter Texture dilation/padding](https://helpx.adobe.com/substance-3d-painter/technical-support/workflow-issues/export-issues/texture-dilation-or-padding.html)
- [Triplanar mapping — Catlike Coding](https://catlikecoding.com/unity/tutorials/advanced-rendering/triplanar-mapping/)
- [Normal Mapping for a Triplanar Shader (Ben Golus)](https://bgolus.medium.com/normal-mapping-for-a-triplanar-shader-10bf39dca05a)
- [Unity Shader Graph compact PBR sub graphs](https://blog.unity.com/engine-platform/experimenting-with-shader-graph-doing-more-with-less)
- [ArtStation — UE5 Procedural Material Layers](https://www.artstation.com/blogs/alishantia/Lz74q/procedural-material-layers-for-ue5)
- [ACES Central — ACEScg and sRGB texture authoring](https://community.acescentral.com/t/acescg-and-srgb-questions-texture-asset-creation/3336)
- [Toadstorm — An Idiot's Guide to ACES](https://www.toadstorm.com/blog/?p=694)
- [Procedural Color Algorithm (Shahriar Shahrabi)](https://shahriyarshahrabi.medium.com/procedural-color-algorithm-a37739f6dc1)
- [Color theory for games (Shahriar Shahrabi)](https://shahriyarshahrabi.medium.com/introduction-to-color-theory-for-games-art-and-tech-67bd4c8607d7)
- [colormaker — LCH palette generator](https://github.com/julienlabat/colormaker)
- [Cel shading (Wikipedia)](https://en.wikipedia.org/wiki/Cel_shading)
- [Procedural MatCap System for Cel-Shaded Animation (SIGGRAPH Asia 2021)](https://dl.acm.org/doi/10.1145/3476124.3488620)
