# SOTA Survey: Mesh Topology and UV Authoring for Lathe

**Date:** 2026-05-04
**Author:** topology-uv-researcher
**Mandate:** STANDALONE PROCEDURAL. No AI 3D. ULTRA MODULAR.
**Scope:** What is the best Python-feasible (PyPI / C-extension / Blender headless) tech for retopology, smoothing, decimation, UV unwrap, packing, and texel density in a procedural pipeline today.

This survey is intentionally biased toward what we can ship in Lathe **this quarter** under the existing constraints: native-only fallbacks must work, providers are optional proposal sources, and the shape-stage contract `lathe.shape.intent_mesh_handoff_v1` is sacred.

---

## 0. Current Lathe state (audit baseline)

Topology stage today (`lathe/topology_runtime.py`, `scripts/blender_topology_adapter.py`):
- Output is a `MultiPartScene` (trimesh.Scene + parallel `PartManifest` list). One Trimesh per blueprint component (~18 parts on a chest). Good — enables per-part retopo budgets.
- Blender adapter: subsurf + bevel-by-seam-group + decimate stack, configured by sidecar JSON.
- **Pipeline-auditor finding:** the adapter's GLB import call uses an API signature broken in Blender 5.x. When the import fails, the entire multi-part path silently falls back to the legacy `weld + triangulate + recalc_face_normals` cleanup — no quad remesh, no support loops, no edge-flow control. This is producing the "non-watertight, ugly shading" complaint.
- **No retopology happens** on the deterministic fallback path. The mesh that comes out of the SDF/exact-solid integrator is what the user gets, modulo a weld and a triangulation.

UV stage today (`lathe/uv_runtime.py`, `lathe/core/stages/uv.py`, `lathe/core/uv_ops.py`):
- xatlas is the only unwrap engine. Wired through `mworchel/xatlas-python`.
- Per-part xatlas atlas with `pack_options.texels_per_unit = target_px_per_m` (default 1024). This is the *intended* uniform texel density mechanism — but it's set globally on the atlas, and `uv_runtime.py` line ~438 (per the auditor) currently hard-codes 1024 px/m, ignoring per-part importance weights and the asset's `texel_density` request when packing.
- Importance weights are recorded as telemetry on `per_part_islands` but do nothing to scale.
- No trim sheet / UDIM / triplanar path exists. No OptCuts / BFF fallback. No texel-density audit pass.
- Validators surface `texel_density_consistency: 0.0` as a known failure on hero assets.

Net effect: shape stage produces a clean SDF or exact-solid mesh → topology either degrades it (broken adapter path) or passes it through (fallback path) → UV stage packs charts at a single uniform density that is silently overridden. **Bad topology + uniform-but-uncontrolled UV density = the "assets look bad" symptom.**

---

## 1. Topology / retopology SOTA

### 1.1 Quad remesh (the core question)

Three open-source contenders are realistically Python-feasible:

| Engine | Algorithm | Python access | License | Fit for Lathe |
|---|---|---|---|---|
| **Instant Meshes** (Jakob 2015) | Field-aligned local smoothing, frame field guided | `pynanoinstantmeshes` on PyPI (v0.0.3, Jan 2025) and `pymeshlab` filter | MIT (engine), BSD-style wrapper | **Best fit.** Pure-Python install, no Blender dependency, fast on hard-surface input. Crease angle controllable. |
| **QuadriFlow** (Huang 2018, MIT) | Cross-field with integer constraints, scalable | `pyQuadriFlow` on PyPI (Python ≥3.8) | MIT | **Strong second.** More robust on organic input; preserves sharp edges and boundaries via flags. Slower than Instant Meshes. |
| **Blender QuadriFlow** | Same algorithm, Blender's port | `bpy.ops.object.quadriflow_remesh()` | GPL | **Avoid as primary.** Documented to crash via bpy in headless / batch loops; memory leak in Python path; works in UI but not reliably in our shell-out flow. |

Instant Meshes via `pynanoinstantmeshes` accepts crease angle, target vertex count, RoSy symmetry order, and align-to-boundaries — which directly matches our hard-surface profile (`profile.hard_surface_game_asset_v1`). This is what Stable-Fast-3D and Hunyuan3D's Comfy workflows ship for postprocessing, which is a useful signal of robustness and packaging.

QuadriFlow is more aggressive about producing well-conditioned cross fields and is the textbook answer for organic shapes. For Lathe's near-term hero set (chest, crate, door, panel, pedestal, container) Instant Meshes will produce better results faster because hard surfaces benefit more from frame-field cleanliness than from MIQ's global integer constraints.

**Maps to Lathe via:** new `lathe/topology/quad_remesh.py` adapter. Provider mux pattern (`shape_providers.py` style): `topology.quad_remesh.instant_meshes_v1` (primary), `topology.quad_remesh.quadriflow_v1` (fallback for organic / when Instant Meshes fails to converge), `topology.quad_remesh.passthrough_v1` (current behavior, last-resort).

DSL surface: extend `topology` block with `quad_remesh: { engine: auto, target_face_count: <int>, crease_angle_deg: 60, rosy: 4 }`. Default `auto` → Instant Meshes for hard-surface profile, QuadriFlow for organic.

**Effort:** S — both are pip-installable; the wrapper is mostly numpy ↔ engine glue. **Lift:** large — moves us from triangulated soup to AAA-style quad-dominant flow.

### 1.2 Field-guided remeshing (MIQ family)

`libigl-python-bindings` exposes Mixed-Integer Quadrangulation (Bommes 2009) and the cross-field machinery. This is the same family QuadriFlow is built on, but exposes the cross field directly so we could author / constrain it from Lathe DSL (e.g. "this seam group is a feature ridge, align field to it").

**Maps to Lathe via:** longer-term `lathe/topology/cross_field.py` module that emits a constrained cross field from the V1.1 `seam_group` declarations, then feeds it to Instant Meshes / QuadriFlow as boundary constraints. This is the principled answer to "boolean+bevel produces ugly seams" — we tell the remesher *where to put the loops*.

**Effort:** L. **Lift:** large but indirect. Defer to phase 2.

### 1.3 Hard-surface vs organic flow — what AAA actually does

Industry convention for game-ready hard-surface (the polycount/Frank/Topology Guides corpus):
1. Block out form.
2. Boolean / kitbash hardpoints.
3. **Add support / chamfer loops at every hard edge** — this is what makes Sub-D produce crisp edges with smooth shading. Without support loops, Sub-D pillows everything.
4. Smooth and bake.

Lathe's current `boolean → bevel(seam_group)` idiom is *philosophically* the same as a chamfer modifier: "bevel the edges in this group, leave the rest". The gap is that PolyBevel-style operations require well-prepared adjacent topology — boolean output rarely qualifies. The SideFX/PolyBevel docs are blunt: "you cannot expect to bevel beyond the ring of polygons incident to edges being bevelled." This is precisely the failure mode the chest hits when the post-boolean Blender bevel produces inverted faces or open strips.

The right answer in our pipeline:
- **Pre-bevel cleanup:** ensure boolean output has at least one face ring of buffer around each seam edge before bevelling. This is a pre-step the Blender adapter should run (bmesh `dissolve_limit` + `subdivide_edges` on near-coplanar regions). Houdini's PolyBevel 3.0 has this baked in; `bmesh` in Blender does not by default.
- **Use chamfer width derived from edge length**, not a global value. Current `bevel_width` is a single float. Hero-asset bevel width should be ~3% of the shorter incident edge so silhouette weight stays balanced.
- **Then quad-remesh after bevel.** Instant Meshes will convert the bevel-strip triangles back into clean quads aligned to the strip direction. This is the missing step.

**Maps to Lathe via:** `lathe/topology/hard_surface_pipeline.py` — `bool_cleanup → adaptive_bevel → quad_remesh`, configured by per-part tag dispatch (chest body gets all three, plank-displaced parts skip the remesh). **Effort:** M. **Lift:** large.

### 1.4 Triangulation for engines

The runtime contract for Unity/Unreal/Godot is triangulated mesh. The right rule for shading-preserving triangulation is **edge-priority Delaunay-like flip** (matching the pre-existing quad diagonal that minimizes dihedral angle). bmesh `triangulate(quad_method='BEAUTY')` does this. Trimesh's default does not — it fans every quad on vertex 0, which produces shading artifacts on bevels.

**Maps to Lathe via:** swap the trimesh fallback triangulation for a beauty-diagonal pass (small numpy implementation, ~30 lines). **Effort:** S. **Lift:** medium — fixes shading artifacts on every quad-output asset.

### 1.5 Smoothing / fairing

PyMeshLab exposes Taubin smoothing directly (`apply_filter('apply_coord_taubin_smoothing', ...)`). Taubin avoids the shrinkage of plain Laplacian, costs almost nothing, and is the right cadence for procedural meshes that are fundamentally clean but have voxel-grid stair-stepping from the SDF integrator.

For the cases where stair-stepping is severe (low-resolution voxel grid, organic profiles), bilateral mesh denoising (Jones 2003, Fleishman 2003) preserves features by weighting neighbors by normal similarity. Available in PyMeshLab as `apply_coord_laplacian_smoothing_surf_preserve`.

**Maps to Lathe via:** topology stage gets a `smoothing: { method: taubin, iterations: 5, preserve_features_deg: 35 }` block. Default to taubin-light for SDF-derived parts (`tags: voxel_origin`), off for exact-solid parts. **Effort:** S. **Lift:** medium.

### 1.6 Decimation respecting edge flow

Current pipeline has a Blender Decimate modifier. The SOTA standalone-Python answer is `pyfqmr` (Cython wrapper around sp4cerat/Fast-Quadric-Mesh-Simplification, Garland-Heckbert with appearance-aware extension) or `open3d.geometry.simplify_quadric_decimation`. PyMeshLab's `meshing_decimation_quadric_edge_collapse` with `preservenormal=True` and the `_with_texture` variant (`extra_tex_coord_weight`) preserves UV seams during decimation — which matters once we start emitting UVs from topology stage.

The 2024 paper "Single Edge Collapse Quad-Dominant Mesh Reduction" (ACM TOG 2025) is the modern frontier — it produces quad-dominant decimations directly, avoiding the quad → tri → decimate → re-quad round-trip. Not yet in any Python package; track for phase 2.

**Maps to Lathe via:** keep Blender decimate when bpy is available; when not, fall back to `pyfqmr` rather than today's `passthrough`. **Effort:** S. **Lift:** medium.

---

## 2. UV SOTA

### 2.1 Modern UV unwrap

Three open-source unwrappers are realistically Python-accessible:

| Engine | Algorithm | Python | Distortion | Seam quality | Fit |
|---|---|---|---|---|---|
| **xatlas** (Witness, jpcy) | LSCM-like with greedy chart growth | `xatlas` PyPI (mworchel) | Medium | Medium — lots of small charts on non-smooth surfaces | **Current.** Ship as default. |
| **OptCuts** (Li 2018) | Joint optimization of cuts and parameterization, no parameter tuning | Compile-from-source (CMake, libigl, TBB); no PyPI | Low (controllable) | Excellent — minimizes seam length under distortion bound | High effort but high quality. Ship as opt-in for hero. |
| **BFF** (Sawhney/Crane 2018) | Boundary First Flattening, linear conformal | `confmap` GitHub (pip install -e), `conformal-flattening` on RTD | Low (conformal) | Best when boundary is pre-cut (we have seams from V1.1) | **Strong opt-in.** Designed for the case where seams are user-specified. |

**Recommendation:** add a provider mux in UV stage with three engines under the same `lathe.uv.unwrap_v1` contract:
- `lathe.uv.unwrap.xatlas_v1` (default, today's behavior).
- `lathe.uv.unwrap.bff_v1` — when V1.1 `seam_group` declarations are present and the part is topologically a disk (has cuts that flatten to a disk). BFF requires a cut topology, which is exactly what `seam_group` gives us.
- `lathe.uv.unwrap.optcuts_v1` — opt-in via runtime config; fall back to xatlas if libigl/TBB compile is unavailable.

**Maps to Lathe via:** `lathe/uv/unwrap_providers.py`, parallel to `lathe/shape_providers.py`. DSL surface: `uv: { engine: auto | xatlas | bff | optcuts, distortion_bound: 0.05 }`.

**Effort:** xatlas tweaks S, BFF M, OptCuts L. **Lift:** large for hero parts (OptCuts is widely accepted as the highest-quality automatic unwrapper available; the Nuvo paper explicitly compares to it as the gold standard for non-NeRF inputs).

### 2.2 Texel-density management — the algorithmic answer

The validator's `texel_density_consistency: 0.0` failure has a precise algorithmic fix.

**The math:** for each chart $c$, compute $\sigma_c = \frac{\text{texels}(c)}{\text{world\_area}(c)}$ in (px/m)². The validator wants $\max(\sigma) / \min(\sigma) \le k$ across all charts in the part (industry hero standard: $k \le 1.25$, i.e. ±25%). Today's xatlas wrapper sets `texels_per_unit` globally on the atlas, which gives a *target* density but does not enforce it because xatlas can scale charts during pack to fit the resolution. When the resolution is tight the smallest charts get crushed.

**The fix has three layers:**
1. **Audit pass** (cheap, no engine change): after xatlas, compute per-chart texel density; emit `texel_density_report` with $(\min, \max, \text{ratio}, \text{worst\_chart\_id})$.
2. **Constrained packing**: instead of letting xatlas auto-scale, pre-scale each chart to its target world-area-derived UV size before packing. Pass `xatlas` only the bounded packing problem (rectpack-style 2D bin packing of fixed-size islands). `rectpack` on PyPI does this; it supports rotation + multiple bins (= multiple UDIM tiles).
3. **Spillover to UDIM**: when constrained packing exceeds 1 tile, emit additional 0-1 squares as UDIM tiles 1002, 1003, ... (Pixar UDIM convention). Hero assets ship with UDIM-aware materials anyway.

**Maps to Lathe via:** `lathe/uv/texel_density.py` (audit + constrained pack), `lathe/uv/udim_packer.py` (rectpack-based spillover). **Effort:** M. **Lift:** very large — this is the *quantitative* fix the validator is already asking for.

### 2.3 UDIM / atlas packing for atlas reuse

UDIM is the industry standard for >1k texel density on hero assets. UVPackmaster 4 (commercial Blender plugin) added "Dynamic Tiles" auto-UDIM in 2026 — that's our target behavior, and it's implementable on top of `rectpack`:

```
for each part:
    compute target chart sizes from world area * target_density
    pack into 1024x1024 bins via rectpack.MaxRectsBssf
    each bin -> one UDIM tile (1001 + bin_index)
```

The `package` stage already emits glTF / USD; both natively support UDIM via the `<UDIM>` token in texture paths.

**Trim sheets** are the other axis: a trim sheet is a tile-able strip texture (e.g. all the panel edges, screws, bolts on one strip). Asset UV strips that map to trim regions can overlap freely. V1.2 `trim_sheet` declarations already exist as an authoring concept — the gap is that the unwrapper doesn't know about them. Workflow:

1. Author trim sheet in Lathe as a `trim_sheet` block with named UV regions.
2. In the part definition, mark edges/faces as `trim_sheet_target: panel_edge` (per-tag dispatch — fits the ultra-modular mandate cleanly).
3. UV unwrap respects the override: charts tagged with a trim region are aligned to the trim strip's UV range and excluded from xatlas packing.

**Maps to Lathe via:** `lathe/uv/trim_sheets.py`. Per-part-tag dispatch consumes `trim_sheet_target` and produces aligned UV strips before packing. Pack only the un-tagged charts. **Effort:** M. **Lift:** very large — this is what makes hero assets actually look hand-authored.

### 2.4 Triplanar mapping (when UV is the wrong abstraction)

For the parts of an asset where UV is fundamentally a bad fit — bumpy organic forms, terrain-y plinths, displacement-heavy regions — triplanar projection in the shader is the right answer. It eliminates seams and stretching at the cost of 3x texture lookups (or 2x with biplanar mapping per Inigo Quilez).

In Lathe terms: triplanar belongs to the `surface` stage, not UV. The asset declares a part as `surface_method: triplanar` (V1.2 `surface_program`), and the UV stage emits an empty / placeholder UV for that part (or a world-space fallback UV) plus a flag in the surface bundle. The engine manifest emits an appropriate triplanar shader binding.

**Maps to Lathe via:** `surface_program` extension (V1.2 already), `lathe/engine_manifests/{godot,unity,unreal}.py` triplanar shader templates. **Effort:** M. **Lift:** medium — only a subset of parts benefit, but it's the right answer for those.

### 2.5 UV vs procedural materials — the strategic question

For a procedural pipeline like Lathe, the right policy is:
- **Hard-surface, panel-like, baked texture target → UV-authored** with strict texel density and trim-sheet reuse. This is 80% of the hero set.
- **Organic, noise-driven, world-space material → triplanar / object-space**, no UV needed. ~10%.
- **Layered / hybrid → UV-authored base + triplanar detail layer** in the shader. ~10%.

This policy is per-part, dispatched on tags. It maps cleanly to the existing V1.2 surface_program family.

---

## 3. Top 5 topology changes (ranked)

1. **Wire Instant Meshes via `pynanoinstantmeshes` as the topology engine.** The single biggest lift available — replaces the broken-adapter / passthrough fallback with proper quad-dominant retopology. Effort S. *Provider:* `lathe.topology.quad_remesh.instant_meshes_v1` under the existing `lathe.topology.*_v1` contract.
2. **Fix the Blender 5.x GLB import call AND make the adapter optional rather than central.** The auditor's finding. Even with Instant Meshes added, the Blender adapter is still our path for Sub-D + bevel; a one-line API fix unblocks the whole multi-part bevel path. Effort S.
3. **Add a `bool_cleanup → adaptive_bevel → quad_remesh` hard-surface pipeline behind a tag dispatch.** This is what AAA artists actually do. Bevels become per-edge-length adaptive; quad remesh cleans up the bevel-strip topology. Effort M.
4. **Replace the trimesh-default fan triangulation with a beauty-diagonal pass.** Quick win that fixes shading artifacts on every quad-output asset, including the chest. Effort S.
5. **Add Taubin smoothing pass (PyMeshLab) gated by part tags (`voxel_origin`).** Low-cost, removes voxel stair-stepping from SDF-derived parts without touching exact-solid parts. Effort S.

QuadriFlow as a fallback engine, libigl-MIQ for cross-field-driven retopo, and pyfqmr decimation are the next tier and rolling them in is a phase-2 task.

## 4. Top 5 UV changes (ranked)

1. **Texel-density audit pass + constrained packing (rectpack).** Directly fixes `texel_density_consistency: 0.0`. Pre-scale charts by world area, then 2D bin-pack with `rectpack` instead of letting xatlas auto-scale. Effort M. **Highest leverage on the "assets look bad" symptom because hero asset critique is dominated by inconsistent texel density.**
2. **Honor the asset's `texel_density` request and per-part importance weights at pack time.** Auditor finding — these are recorded but unused. Effort S, but only meaningful in conjunction with (1).
3. **Trim-sheet authoring path** (V1.2 `trim_sheet` already declared) — per-part-tag `trim_sheet_target` dispatch that pre-aligns flagged charts to trim strips and excludes them from xatlas. Effort M.
4. **UDIM spillover** when constrained packing exceeds one 0-1 tile. Hero assets ship at >1k px/m and this becomes mandatory. Effort M.
5. **BFF as opt-in unwrapper for parts with V1.1 `seam_group` declarations.** Conformal, seam-respecting, ships in `confmap`. Effort M. (OptCuts is higher quality but L effort due to libigl/TBB build; defer.)

Triplanar surface programs and OptCuts integration are the next tier.

---

## 5. Top 5 overall (cross-cutting)

Ranking by **expected visual-quality lift per effort unit**:

1. **Texel-density audit + constrained packing (UV).** Medium effort, large lift, addresses a known validator failure. Pure Python (rectpack on PyPI). Should ship first.
2. **Instant Meshes via `pynanoinstantmeshes` (topology).** Small effort, large lift, addresses "non-watertight, ugly shading" complaint. Pure Python (PyPI).
3. **Fix Blender 5.x GLB import + adopt a beauty-diagonal triangulation fallback (topology).** Tiny effort, large lift — it unblocks every other topology improvement and fixes shading artifacts that masquerade as topology bugs.
4. **Trim sheets + UDIM (UV).** Medium effort, large lift on hero assets. The V1.2 authoring surface is already partly there, so this is mostly wiring and a `rectpack`-based packer.
5. **Adaptive hard-surface pipeline (`bool_cleanup → adaptive_bevel → quad_remesh`).** Medium effort, large lift, but only meaningful after (2) lands so the quad_remesh step has an engine.

Everything in this top 5 is Python-feasible without Blender as a hard dependency: rectpack, pynanoinstantmeshes, pymeshlab, xatlas, confmap. Blender adapters remain the high-quality path when bpy is available, with these as deterministic fallbacks — exactly the existing "attempted vs actual provider" pattern.

---

## Sources

- [pynanoinstantmeshes on PyPI](https://pypi.org/project/pynanoinstantmeshes/)
- [PyNanoInstantMeshes GitHub](https://github.com/vork/PyNanoInstantMeshes)
- [Instant Meshes (Wenzel Jakob)](https://github.com/wjakob/instant-meshes)
- [pyQuadriFlow on PyPI](https://pypi.org/project/pyQuadriFlow/)
- [QuadriFlow GitHub](https://github.com/hjwdzh/QuadriFlow)
- [Blender QuadriFlow bpy crash issue #124004](https://projects.blender.org/blender/blender/issues/124004)
- [PyMeshLab](https://github.com/cnr-isti-vclab/PyMeshLab)
- [PyMeshLab filter list](https://pymeshlab.readthedocs.io/en/latest/filter_list.html)
- [xatlas-python](https://github.com/mworchel/xatlas-python)
- [xatlas (jpcy)](https://github.com/jpcy/xatlas)
- [OptCuts](https://github.com/liminchen/OptCuts)
- [Boundary First Flattening (Sawhney/Crane)](https://github.com/GeometryCollective/boundary-first-flattening)
- [confmap (Python BFF/CETM)](https://github.com/russelmann/confmap)
- [libigl Python bindings](https://github.com/libigl/libigl-python-bindings)
- [Mixed-Integer Quadrangulation (Bommes 2009)](https://www-sop.inria.fr/members/David.Bommes/publications/miq.pdf)
- [Houdini PolyBevel docs](https://www.sidefx.com/docs/houdini/nodes/sop/polybevel.html)
- [Topology Guides](https://topologyguides.com/)
- [Beyond Extent — Texel Density deep dive](https://www.beyondextent.com/deep-dives/deepdive-texeldensity)
- [Beyond Extent — Trim sheets deep dive](https://www.beyondextent.com/deep-dives/trimsheets)
- [UVPackmaster 4 Dynamic Tiles](https://digitalproduction.com/2026/01/23/uvpackmaster-4-unwraps-a-smarter-way-to-pack/)
- [Triplanar mapping (Catlike Coding)](https://catlikecoding.com/unity/tutorials/advanced-rendering/triplanar-mapping/)
- [Biplanar mapping (Inigo Quilez)](https://iquilezles.org/articles/biplanar/)
- [Taubin smoothing (Stanford)](https://graphics.stanford.edu/courses/cs468-01-fall/Papers/taubin-smoothing.pdf)
- [Bilateral mesh denoising (Jones et al. 2003)](https://geometry.caltech.edu/pubs/JDD03.pdf)
- [Surface Simplification Using Quadric Error Metrics (Garland-Heckbert)](https://www.cs.cmu.edu/~garland/Papers/quadrics.pdf)
- [pyfqmr / Fast-Quadric-Mesh-Simplification](https://github.com/sp4cerat/Fast-Quadric-Mesh-Simplification)
- [OpenSubdiv crease/sharpness docs](https://graphics.pixar.com/opensubdiv/docs_3x_alpha/subdivision_surfaces.html)
- [Nuvo: Neural UV Mapping (compares OptCuts/xatlas)](https://arxiv.org/html/2312.05283v1)
