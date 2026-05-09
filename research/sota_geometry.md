# SOTA in Procedural Geometry Kernels — for Lathe

**Author:** geometry-kernel-researcher
**Date:** 2026-05-04
**Audience:** team-lead; downstream of `pipeline-auditor` and peer-of `openscad-specialist-v2`
**Mandate:** standalone procedural, ultra-modular, additive-only, Python or PyPI-installable.

> **Scope deconfliction.** The peer agent `openscad-specialist-v2` covers OpenSCAD,
> Manifold (the kernel), and BOSL2. This report covers the surrounding landscape:
> the geometry-processing kernels (libigl/CGAL/Cinolib/geogram/MCUT), exact-predicate
> arrangements (Cherchi family), SDF/F-Rep extraction (DC/MDC/ODC), volumetric (OpenVDB/NanoVDB),
> B-Rep (OCCT via pythonocc / CadQuery / build123d), real bevel-on-arbitrary-topology,
> and procedural-primitive families (NURBS, gears, threads, sweeps).

> **Pipeline context (from `pipeline-auditor`).** Bakes are broken, validators
> don't read pixels, `DesignerGraph.evaluate` is never called. That means even
> if we drop in a perfect kernel, the *visual* return won't materialize until
> the pipeline blockers are unblocked. This report assumes those will be fixed
> in parallel — the kernel work is the thing that *raises the ceiling* once
> they are.

---

## 1. CSG kernels (excluding OpenSCAD/Manifold)

Lathe's current state, from `lathe/exact_solids.py`:

```py
# 1164: trimesh.boolean.union(meshes, check_volume=False)
# 1175: trimesh.boolean.difference(...)
# 1185: trimesh.boolean.intersection(...)
```

These call `trimesh.boolean`, which dispatches to `manifold3d` if installed, else
to Blender (subprocess) or the legacy `scad` engine. `manifold3d` is excellent
for *manifold input → manifold output* but throws when input meshes are
non-manifold, have coincident faces, or thin slivers (very common in our
generated extruded/swept profiles after orientation/sweep rounding).

### 1.1 libigl / `igl.copyleft.cgal.mesh_boolean`

`libigl` (PyPI: `libigl 2.6.x`) ships nanobind-built Python bindings with a
NumPy/SciPy-only runtime. The mesh-boolean entry point lives in
`igl/copyleft/cgal/mesh_boolean.h`. Key facts:

- **Backend:** uses CGAL's exact-arithmetic kernel (`Exact_predicates_exact_constructions_kernel`) under the hood for the `cgal` mesh boolean.
- **License:** the `copyleft/cgal/*` headers are GPL/LGPL (CGAL's licensing). For Lathe, this is fine for a *runtime backend* — the user's `.lth` source and the Lathe Python source remain unaffected; we only need a clean LICENSE/NOTICE file. (For commercial-distribution scenarios this matters; for a standalone procedural DSL whose users invoke it locally it does not.)
- **Robustness:** higher than `manifold3d` on arbitrary triangle soup — it self-corrects through a CGAL co-refinement pass. Still requires the input to *eventually* triangulate cleanly; degenerate inputs (zero-area faces) fail.
- **Perf:** measurable on our scale (target meshes ≤ 200k tris) — sub-second per op. Slower than `manifold3d` for clean input by ~3-10×, but doesn't fail.
- **Python availability:** the PyPI `libigl` wheel bundles only the *non-CGAL* core. Boolean is gated behind a CMake `LIBIGL_WITH_CGAL=ON` flag. `pyigl_cgal`-style wheels are not on PyPI. Practical conclusion: **libigl-python boolean today requires a custom build**.

**Maps to Lathe via:** `lathe/exact_solids.py` `_boolean_*` functions, `lathe/shape/backend.py`. Concrete change: add an optional secondary backend `lathe.boolean.libigl_cgal_v1` selectable per primitive (in `v2_polybevel_modifier`-style metadata) when `_boolean_difference` is called for a part tagged `seam_critical`. Falls back to current `manifold3d` path. Not the default until a wheel is published.

### 1.2 CGAL Polygon Mesh Processing (PMP) directly

CGAL PMP exposes `corefine_and_compute_*` (union, intersection, difference) which
reportedly outperforms `libigl::mesh_boolean` by ~10× via a single-pass
co-refinement. But:

- **No first-class Python wheel on PyPI**. The `seagullmesh` package (github.com/darikg/seagullmesh) provides nanobind bindings to CGAL's Surface_mesh + PMP — actively maintained, but PyPI distribution lags conda-forge.
- **License:** CGAL is GPL-or-commercial. Same caveats as 1.1.
- **Robustness:** highest of the surveyed kernels for clean-input, but co-refinement still chokes on coplanar coincident faces. Cherchi 2022 is more robust there.

**Maps to Lathe via:** `lathe/shape/backend.py`. Concrete change: define `lathe.boolean.cgal_pmp_v1` and gate it on `import seagullmesh`. Treat as the high-quality fallback when `manifold3d` returns an empty mesh (we currently raise `ValueError` from `_require_boolean_mesh` — see line 1153–1161 of `exact_solids.py`). Effort: M.

### 1.3 Cinolib

Cinolib (github.com/mlivesu/cinolib) is a header-only C++ polyhedral-mesh library used to host Cherchi's research code (FastAndRobustMeshArrangements, InteractiveAndRobustMeshBooleans). For Lathe it is mostly a *dependency* of the Cherchi pipeline rather than a direct target. **No Python bindings.**

### 1.4 geogram

geogram (github.com/BrunoLevy/geogram) bundles Bruno Lévy's exact-predicate kernel and the `mesh_boolean` operator. Robust and fast (used in Graphite). **No PyPI Python bindings**; pulling it in would need pybind11/nanobind glue.

### 1.5 MCUT

MCUT (github.com/cutdigital/mcut) is a different beast: it's a *cutting* library, not a CSG kernel. It exactly resolves the intersection curves between two surface meshes and partitions them into fragments. CSG can be assembled on top of those fragments (a union is "the outer fragments of A and B", a difference is "A's outer fragments minus B's inner fragments"), but MCUT itself is one level lower than what `_boolean_*` needs.

- **License:** LGPL (more permissive than CGAL) — preferable for libraries that may be redistributed.
- **Python:** **no official Python bindings**. The C API is small and clean, so a thin nanobind wrapper is feasible (~200 LoC) but is real engineering effort.
- **Strength:** great for *partial cuts* (engraving, slot-cutting, embossing) — these are exactly the operations that today fail under `trimesh.boolean.difference` when the cutter doesn't fully traverse the base.

**Maps to Lathe via:** `lathe/exact_solids.py` would gain `_partial_cut_via_mcut(base, cutter, depth)` for sub-features like rail slots, picatinny grooves, magazine wells. The current path simulates these with full-traversal cylinders/boxes — when the cutter mesh is itself slightly non-manifold (common when extruding a U-profile), `manifold3d` fails and we fall back to a worse mesh.

### 1.6 Comparative table

| Kernel | Lib lang | Python wheel | Robustness | Perf | License | Notes |
|---|---|---|---|---|---|---|
| **manifold3d** (current) | C++ | yes | high on manifold input, fails on non-manifold | fastest | Apache-2 | guaranteed-manifold output; what we have |
| libigl mesh_boolean (CGAL) | C++ | partial — non-CGAL core only | very high | medium | GPL-via-CGAL | needs custom wheel |
| CGAL PMP corefine | C++ | via `seagullmesh` (conda) | highest, but coplanar issues | fast | GPL | best quality bound |
| Cherchi 2022 (interactive booleans) | C++ | none | highest including degenerates | fastest exact | research-license | the actual SOTA |
| geogram boolean | C++ | none | high | medium | BSD-ish | no Python |
| MCUT | C++ | none | partial-cut speciality | fast | LGPL | needs binding work |

### 1.7 Recommendation for Lathe

**Tiered backends.** Replace the single `trimesh.boolean.*` call sites in
`exact_solids.py` with a tier:

```
tier 0 (default): manifold3d  — what we have
tier 1 (fallback): seagullmesh (CGAL PMP)  — install-optional
tier 2 (research):  Cherchi via cinolib + nanobind binding  — far-future
```

Tier-1 is the sweet spot — it eliminates the failure class where
`manifold3d` raises on degenerate inputs without rewriting our existing
ShapeIR primitive emitters. **Effort: M.**

**Maps to Lathe via:** `lathe/exact_solids.py` `_require_boolean_mesh`, `_boolean_union`, `_boolean_difference`, `_boolean_intersection`. Add `lathe/shape/backend.py` `BooleanBackendChain` selecting attempted/actual under the same attempted-vs-actual telemetry pattern Lathe already uses for shape providers.

---

## 2. Exact arithmetic / robustness — Cherchi line of work

Currently Lathe leans on `manifold3d`'s ε-tolerance robustness. The literature
SOTA is **floating-point exact predicates** (Shewchuk 1997 → Attene 2020 indirect
predicates → Cherchi 2020 mesh arrangements → Cherchi 2022 interactive booleans → Attene/Cherchi 2025 exact constructions for CSG combinatorics).

The key insight from Attene 2020 + Cherchi 2020/2022:

- Don't compute exact intersection coordinates. Represent each intersection point
  symbolically as a triple of input vertices — then derive *exact predicates*
  (orientation, in-segment, in-triangle, ...) from these symbolic descriptions
  using *interval arithmetic with FP-hardware certification*.
- Avoid the extreme cost of pure rational/multi-precision arithmetic, which is
  why CGAL EPECK feels slow on big meshes.

The 2022 paper ("Interactive and Robust Mesh Booleans") clocks 200k-tri inputs
at interactive frame rates, with provable correctness on *adversarial* inputs
(coplanar, coincident-edge, self-intersecting). That is the actual SOTA today.

There is no Python wheel. The reference repos
(github.com/gcherchi/InteractiveAndRobustMeshBooleans,
github.com/gcherchi/FastAndRobustMeshArrangements) are header-only C++ with a
demo executable. Wrapping them is non-trivial because they sit on top of
Cinolib + a custom indirect-predicate library (`indirectPredicates`).

**Recommendation.** Track this for a *future* tier-2 backend. In the near
term, the practical robustness win is from CGAL PMP (which uses Shewchuk
predicates internally even if not the Cherchi indirect ones) — see §1.

**Maps to Lathe via:** longer-term — `lathe/shape/backend.py` would gain a
`lathe.boolean.cherchi_indirect_v1` provider with full attempted-vs-actual
tracing. For now, the architectural investment is making the boolean call
site a *backend chain* so this drops in cleanly later. Effort: L.

---

## 3. SDF / F-Rep SOTA

Lathe already has `lathe/f_rep/` with marching cubes (default) and a *scaffold*
dual contouring (the file's own docstring says QEF/SVD is left as follow-up).
Looking at what the literature offers in 2024–2026:

### 3.1 Quilez SDF library — already in scope

The expression algebra Lathe encodes (`Sphere`, `Box`, `Capsule`, `SmoothUnion`, `Displace`, `Warp`, etc. — see `lathe/f_rep/expressions.py`) is the standard Inigo Quilez vocabulary. Recent additions worth pulling in:

- **`opSmoothUnion3` (chamfer-bias)** and **`opSmoothUnion4` (steps)** — alternative smooth-union shapes that don't bulge at narrow seams. (Lathe today exposes only the standard quadratic `SmoothUnion`.)
- **`opOnion`** — shell extraction: `abs(d) - thickness`, useful for hollowing/walls without an explicit boolean subtract. Massive simplification for crates, helmets, cabinets.
- **`opExtrusion`/`opRevolution` of 2D SDFs** — in Lathe these would dovetail with `extruded_profile` and `revolved_profile` ShapeIR primitives, giving F-Rep equivalents for free.

**Maps to Lathe via:** `lathe/f_rep/expressions.py` — add `Onion`, `SmoothUnionChamfer`, `Extrude2D`, `Revolve2D`. Pure-Python, additive. **Effort: S.**

### 3.2 Sharp-feature extraction: real Dual Contouring

Lathe's DC scaffold uses cell-centroid placement (a degenerate QEF — equivalent to MC vertex averaging, sharp-feature loss). Real DC needs:

1. **Hermite samples on edges**: instead of just sign + linear-interp position, sample the *gradient* of the SDF at the intersection (we already have an analytic-gradient SDF, so this is cheap).
2. **QEF solve per cell**: minimize `Σ_i (n_i · (x - p_i))²` via SVD with truncated singular values. This is 6 LoC of NumPy — `np.linalg.svd` then build the pseudo-inverse with σ-thresholding.
3. **Vertex clamping**: clamp the QEF solution to the cell AABB to handle degenerate sharp corners (Schaefer & Warren §4).

This is well within reach in pure NumPy and would lift dual-contouring extraction from "scaffold" to "production sharp-feature ready". Maps cleanly to current f_rep/dual_contouring.py.

### 3.3 Manifold Dual Contouring (MDC) — Schaefer/Ju/Warren 2007

Vanilla DC can produce non-manifold outputs (multiple cell vertices that should be split). MDC fixes this by detecting non-manifold-creating configurations and *splitting* the cell vertex into 2-4 sub-vertices that each represent one surface sheet through the cell. Critical for clean watertight output downstream of subdivision/UV.

A pure-Python MDC implementation is ~400 LoC. The cell-classification table is finite and lookup-table-able like MC tables.

### 3.4 Occupancy-Based Dual Contouring (ODC, SIGGRAPH Asia 2024)

Doesn't require gradient information — uses 1D/2D auxiliary points within cells to localize sharp corners. Useful when the input is a black-box occupancy function (e.g., neural). For Lathe's *known-analytic* SDF graph this is overkill — we have gradients for free.

### 3.5 Recommendation

**Sharpen Lathe's DC.** Promote `lathe/f_rep/dual_contouring.py` from scaffold to real QEF/SVD; layer MDC on top. Add Quilez additions to the F-Rep vocabulary in parallel.

**Maps to Lathe via:** `lathe/f_rep/dual_contouring.py` (QEF/SVD), `lathe/f_rep/expressions.py` (Quilez vocab), tests in `tests/test_f_rep_extraction.py`. Pure-Python, additive. The new `Onion` op in particular unlocks shell-construction (chest interiors, helmet liners, container walls) we currently fake with paired booleans. **Effort: M (DC), S (vocab).**

---

## 4. Voxel / OpenVDB-class

Lathe has `lathe/volume/vdb_backend.py` already gated on `pyopenvdb`.
Status quo:

- **`pyopenvdb`** *exists* on PyPI but the published wheels are stale (last meaningful update years ago) and a known-bad fit on Windows 10 (where the user runs).
- **OpenVDB main 13.x + nanobind bindings** — the Academy Software Foundation has been migrating from pybind11 → nanobind for the canonical `openvdb` Python module. Recent CGAL-style performance wins on `csgUnion`/`csgIntersection`/`csgDifference` via parallel breadth-first algorithms.
- **NanoVDB** — read-only GPU-mappable volume format. Useful for export to renderers (Cycles, V-Ray, USD Volume) but not for kernel-side authoring.

### 4.1 Why this matters for Lathe

OpenVDB level-set CSG is *the* answer for:

- **Smoke/cloud/destruction (organic) volumes** — exactly the class of asset that purely-mesh kernels can't author (you can't boolean a smoke plume).
- **Robust mesh booleans on geometry that won't behave**: voxelize → level-set CSG → polygonize. This is a totally different robustness profile from triangle-arithmetic kernels — it can never fail topologically (closed level set in → closed level set out), only lose detail at the voxel scale.
- **Mesh-to-volume-to-mesh repair**: when an emitter produces a near-watertight mesh that `manifold3d` rejects, you can voxelize at high res, polygonize, and recover.

### 4.2 Cheap-vs-expensive Python integration

- **Cheap (today):** keep `pyopenvdb` optional in `lathe/volume/vdb_backend.py`, with a numpy-`.npz` fallback (already implemented). For the mesh-repair path, add a *pure-NumPy* `mesh_to_levelset` (winding-number-based — robust and computable in NumPy) + the Lathe-internal MC/DC for polygonization. This gives 80% of OpenVDB's repair value with zero binary deps.
- **Mid-cost:** wait for the openvdb 13.x nanobind wheels to publish to PyPI for Windows. Once available, swap the backend silently.
- **Expensive:** package OpenVDB ourselves as a wheel for Lathe — out of scope, IMO.

### 4.3 Recommendation

Add `lathe.volume.repair_v1`: a pure-NumPy mesh→levelset→mesh repair pass that the boolean backend chain can call as a *last-resort* tier (tier 3 in §1). Watertight by construction. Loses sharp features (voxel resolution-limited) but never fails. This is the difference between a `ContractViolation` and a slightly soft mesh.

**Maps to Lathe via:** `lathe/volume/repair.py` (new), `lathe/volume/extract.py` (already exists). The repair function reads `lathe/f_rep/dual_contouring.py` for the polygonizer to keep sharpness up where possible. **Effort: M.**

---

## 5. B-Rep / parametric solids — OCCT path

Right now, Lathe is purely mesh-based: ShapeIR primitives → trimesh meshes → boolean → topology stage (`lathe/topology_runtime.py`). The whole chain is *post*-topology, meaning every modification (chamfer, fillet, draft) operates on triangles, not on the conceptual edge/face it was *meant* to apply to.

OCCT (Open CASCADE Technology) is the open-source B-Rep kernel. Two Python paths today:

- **`pythonocc-core`** (PyPI: `pythonocc-core 7.9.x`) — direct OCCT bindings. Conda-forge wheels for Python 3.10–3.14. Windows wheel works.
- **`build123d`** (PyPI: `build123d 0.10.x`) — a Pythonic CAD framework on top of OCCT (via the OCP wrapper). The successor to `cadquery`'s API direction. Released Nov 5, 2025.
- **`cadquery 2.x`** — the original. Same OCP wrapper underneath. Stable.

### 5.1 Why a B-Rep "feature tree" alongside ShapeIR

Lathe today has tree-of-primitives → mesh. A B-Rep feature tree would be tree-of-primitives → tree-of-faces-and-edges → mesh-on-demand. The win is *exact* operations that mesh kernels approximate or fail at:

- **`BRepFilletAPI_MakeFillet`** / **`BRepFilletAPI_MakeChamfer`** — fillet/chamfer arbitrary edge sets with parametric radii, miter handling, draft. The result is *analytic* (G2 surface) — when finally meshed, the tessellation error is bounded.
- **`BRepFeat_MakePrism`** / **`BRepFeat_MakeRevol`** — feature operators that respect surface continuity.
- **`BRepOffsetAPI_MakeThickSolid`** — exact shell/hollow.
- **`BRepBuilderAPI_MakeWire` + `BRepFill_PipeShell`** — sweep along a curve with auxiliary spine, frame control, transition smoothing.
- **`GeomAPI_PointsToBSplineSurface`** — fit smooth surfaces to point sets.

### 5.2 Architectural shape

Lathe doesn't need to *replace* ShapeIR with B-Rep. The right move is *additive*: a parallel `BRepIR` for components that benefit from analytic operations (curved hard-surface assets — barrels, scopes, ergonomic stocks, shell parts), with a defined `BRepIR → ShapeIR (mesh)` lowering at stage boundary. The stable contract `lathe.shape.intent_mesh_handoff_v1` is preserved because B-Rep stays *upstream* of it.

### 5.3 Recommendation

Add `lathe/b_rep/` mirroring `lathe/f_rep/`, with:
- `lathe/b_rep/expressions.py` — `Box`, `Cylinder`, `Sweep`, `Loft`, `Fillet`, `Chamfer`, `Shell`, `Boolean*`.
- `lathe/b_rep/backend.py` — gated on `import OCP` / `import OCC.Core` (pythonocc).
- `lathe/b_rep/lower.py` — `to_shape_ir(mesh_quality)` that tessellates via OCCT's `BRepMesh_IncrementalMesh` and produces a `ShapeIR`-compatible payload.
- New ShapeIR primitive type `"b_rep_brep"` whose mesh emitter calls the lower.

**Maps to Lathe via:** new `lathe/b_rep/` module. New ShapeIR primitive type. `lathe/shape_ir.py` enum of `primitive_type` extended additively. **Effort: L** — but this is the single highest-quality-ceiling change in this whole report.

---

## 6. Hard-surface CAD operators — real bevel on arbitrary topology

Lathe's current bevel path:

```py
# lathe/exact_solids.py
# 996: _general_mesh_bevel (post-boolean PolyBevel cutback)
# 1359: _post_boolean_polybevel_cutback_mesh
```

This is *post-boolean* — it runs after `manifold3d` produces the union/diff
result, then attempts to identify and cut back the seam edges. The
implementation is limited (the file's own comments call it out for box/cube
shapes). Real CAD bevels need:

### 6.1 Three real techniques in the wild

1. **Blender's PolyBevel (limit-method `weight`/`angle`)** — operates on edge-halfedge data, with full control over miter type (`patch`/`arc`/`spread`), profile (concave/convex curves up to 15-segment Bezier), per-edge weight. The Blender source is GPL but the *algorithm* is well documented and re-implementable.
2. **Houdini PolyBevel SOP (`limit-method`)** — solves the bevel as a face-offset followed by a corner-fill. The `Modeler` author has a clean writeup.
3. **OCCT BRepFilletAPI_MakeFillet** — analytic. Works on B-Rep edges, not mesh edges. See §5.

### 6.2 What it takes for Lathe to have real mesh bevel

A real bevel-on-arbitrary-topology mesh op needs:

- **Edge classification** — which edges to bevel. Lathe today carries this intent in `boolean_seam_groups` / `bevel_seam_groups` / `v2_polybevel_modifier`. So the *intent* is already first-class.
- **Half-edge data structure** — current `trimesh.Trimesh` doesn't expose this; we'd build one or use `igl.edge_topology`.
- **Edge offset** — push selected edges inward along the perpendicular bisector of the two adjacent face normals.
- **Corner solve** — at every vertex incident to ≥2 beveled edges, solve the planar miter. Three sub-cases: 2 edges (planar), 3 edges (corner), 4+ (T-junction).
- **Optional rounding profile** — replace each beveled edge with N segments along a circular arc.

This is non-trivial (the full Blender PolyBevel is ~5k LoC of C). However, a
*functional* version covering the cases Lathe actually emits (mostly box and
extruded-profile edge sets) is ~1k LoC of pure Python.

### 6.3 Recommendation

**Two-track.**

- **Short-term:** the post-boolean PolyBevel cutback in `_general_mesh_bevel` already works for boxy assets. Add an *evaluation-and-fallback* tier: if the cutback ends up degenerate, emit a `bevel_fidelity: low` flag on the asset rather than silently producing a worse mesh.
- **Medium-term:** add `lathe.bevel.half_edge_v1` — a real half-edge bevel operator that handles arbitrary topology. Implement covering box, extruded-profile, swept-profile, lofted-solid (the geometries Lathe actually generates).
- **Long-term:** when B-Rep IR (§5) lands, route fillet/chamfer through OCCT for *analytic* bevels on the assets that matter (curved hard-surface).

**Maps to Lathe via:** `lathe/exact_solids.py` `_general_mesh_bevel` is replaced by `lathe/bevel/half_edge.py` with a backend chain (current cutback → half-edge → OCCT). Effort: **M (short-term tier)**, **L (half-edge)**.

---

## 7. Procedural primitives to add

A standalone-procedural DSL is only as expressive as its primitive vocabulary. Lathe today has 11 primitives (`box`, `cylinder`, `sphere`, `revolved_profile`, `extruded_profile`, `torus`, `subdivision_box`, `swept_profile`, `lofted_solid`, `heightfield` — and most recently swept_profile/torus/subdivision_box per recent commits). Major gaps:

### 7.1 Helical / threaded

Threading (machine threads, helical springs, screw fasteners, helical staircases). Today these would need `swept_profile` with a manually-authored helix path — error-prone. A `helical_sweep` primitive parametrized by `pitch`, `turns`, `start_diameter`, `taper`, `cross_section` would close this gap.

**Implementation:** Frenet/parallel-transport frame along a helix curve, sweep cross-section. ~150 LoC. Watertight by construction.

### 7.2 Gears (involute)

Game-asset doors, mechanisms, exposed clockwork. An `involute_gear` primitive parametrized by `module`, `tooth_count`, `pressure_angle`, `face_width`, `helix_angle` (for helical gears), `rack_shift` would be a hero feature for mechanical assets.

**Implementation:** generate the involute curve in 2D analytically (no NURBS approximation needed), tile around the pitch circle, extrude with optional helix twist. ~250 LoC. Reference: ISO 21771 / DIN 867.

### 7.3 Spirals

Archimedean, logarithmic, conical. Useful for ornamental work, springs, antennas.

### 7.4 NURBS-backed profiles via `geomdl`

`geomdl` (PyPI: `geomdl`) is pure-Python NURBS/B-spline. Right now, Lathe's `revolved_profile` and `extruded_profile` accept polyline points only — meaning curved profiles get faceted at author-time. Letting profiles be **NURBS curves** (control points + knots + degree) would dramatically improve curved-surface fidelity (gun stocks, ergonomic grips, art-deco mouldings).

**Implementation:** add `profile_curve` field as alternative to `profile_polygon` / `profile_points`. Dispatch in the emitter to call `geomdl` for tessellation at the requested fidelity.

### 7.5 Sweep with frame control

`swept_profile` today implicitly uses a Frenet frame. The known torsion/flip
issues with Frenet (curves with low curvature flip the binormal) mean the
current sweep produces twists where there shouldn't be any. **Parallel
transport** is the SOTA fix:

> Parallel transport chooses two perpendicular vectors at the start of the curve and transports them along the tangent without large orientation changes — unlike Frenet, which can flip when the curvature passes through zero.

**Implementation:** replace Frenet with parallel-transport in the sweep emitter. Add an `up_vector` parameter for cases where the user wants a fixed up. ~50 LoC change.

### 7.6 Loft with tangent control

`lofted_solid` today linearly interpolates between cross-sections. Adding **tangent control** at endpoints (G1 continuity) would let lofts smoothly pick up where a `swept_profile` ends — important for assemblies (handle → barrel transitions).

### 7.7 Bend / twist / taper deformers as first-class ops

Today these would be authored as `swept_profile` with hand-crafted paths. Treating them as deformer ops (`Bend(axis, angle, axis_range)`, `Twist(axis, turns, axis_range)`, `Taper(axis, scale_start, scale_end)`) on top of any primitive multiplies the expressiveness without adding primitives.

**Implementation:** at the ShapeIR mesh-emit boundary, post-multiply vertex positions by the deformer transform. ~200 LoC for the three. Pure-Python.

### 7.8 Recommendation

Add, in priority order:
1. `helical_sweep` (threads, springs) — **S effort, huge unlock for fasteners and mechanical assets**.
2. Parallel-transport sweep (fix existing) — **S, fixes a quality bug**.
3. `involute_gear` — **M, hero feature**.
4. NURBS-backed profile curves via `geomdl` — **M, fidelity multiplier**.
5. Bend/twist/taper deformers — **M, expressiveness multiplier**.

**Maps to Lathe via:** `lathe/shape_ir.py` (new `primitive_type`s and fields, additive — preserves the stable contract), `lathe/exact_solids.py` (new emitter functions), `grammar/lathe.lark` + `schema/lathe.schema.json` (language coordination per `AGENTS.md`).

---

## 8. Implementability

Quick check across all proposals against the non-negotiables:

| Proposal | Pure-Python? | PyPI installable? | Additive to `intent_mesh_handoff_v1`? | AI model? |
|---|---|---|---|---|
| Boolean tier-1 (CGAL PMP via `seagullmesh`) | no, but conda-forge wheel | yes (conda); PyPI lags | yes | no |
| DC sharp-feature QEF/SVD | yes (NumPy only) | yes | yes | no |
| MDC manifold output | yes | yes | yes | no |
| Quilez vocabulary additions | yes | yes | yes | no |
| Mesh-to-levelset repair (NumPy) | yes | yes | yes | no |
| OpenVDB CSG | depends on `pyopenvdb` install | wheel yes, but stale | yes | no |
| B-Rep IR via pythonocc | no, C++ via wheel | yes (conda + PyPI) | yes — new IR | no |
| Half-edge bevel | yes | yes | yes | no |
| Helical/gear primitives | yes | yes | yes — additive `primitive_type` | no |
| Parallel-transport sweep | yes | yes | yes — bug fix in existing emitter | no |

All proposals pass.

---

## 9. Top 5 ranked implementable changes

Ranked by *quality-ceiling-raised per unit-of-effort*, given Lathe's mandate
(standalone procedural, ultra-modular, additive). Effort: S (≤1 week), M (1–4 weeks), L (>1 month).

### #1 — Real Dual Contouring sharp-feature extraction in `lathe/f_rep/`
**Effort:** **M** (~400–600 LoC NumPy)
**Why it tops the list:** Lathe's F-Rep path is currently extraction-quality-limited, not feature-limited — the SDF expression vocabulary is rich, but the extractor (DC scaffold) loses sharp features. Promoting DC to real QEF/SVD + adding MDC produces *immediately better* hard-surface F-Rep output across every asset that uses the F-Rep path. Pure NumPy, no new deps.
**Files:** `lathe/f_rep/dual_contouring.py` (rewrite from scaffold), `lathe/f_rep/expressions.py` (add `Onion`, smooth-union variants).
**Risk:** low; isolated module, has tests.

### #2 — Helical sweep + parallel-transport frame fix
**Effort:** **S** (~200 LoC)
**Why high:** standalone procedural is *only* impressive if it can do mechanical fasteners, springs, and threaded fittings without faking them. A `helical_sweep` primitive plus the Frenet→parallel-transport fix in the existing `swept_profile` emitter is small, additive, and immediately visible in output quality. Hits the ultra-modular value (any component can have a thread).
**Files:** `lathe/shape_ir.py` (new `primitive_type="helical_sweep"`, fields), `lathe/exact_solids.py` (emitter, parallel-transport replaces Frenet), `grammar/lathe.lark`, `schema/lathe.schema.json`.
**Risk:** low; pure new emitter + bug fix on existing.

### #3 — Boolean backend chain (manifold3d → CGAL PMP → mesh-to-levelset repair)
**Effort:** **M** (~500 LoC + integration of optional deps)
**Why high:** the audit found bakes broken; the *visual* return depends on the boolean stage *not failing silently*. Today, when `manifold3d` rejects a degenerate cutter, we raise. With a tiered chain (CGAL PMP fallback → voxel-based repair tier-3) we get watertight output across the whole input distribution. This is **the** robustness lever.
**Files:** `lathe/exact_solids.py` (`_boolean_*` becomes chain dispatch), `lathe/shape/backend.py` (chain wiring under attempted-vs-actual telemetry), `lathe/volume/repair.py` (new pure-NumPy tier-3).
**Risk:** medium — needs careful telemetry to avoid hiding mesh-quality regressions. Mitigated by Lathe's existing attempted-vs-actual tracing pattern.

### #4 — B-Rep IR (`lathe/b_rep/`) backed by OCCT via `pythonocc-core`
**Effort:** **L** (~3–6 weeks, ~2k LoC across IR + lowering + emitter)
**Why high (despite the cost):** this is the *only* path on this list that gets Lathe to *analytic-quality* fillets, chamfers, sweeps, and surfaces. Single highest quality ceiling on the report. Stays additive — runs *before* `intent_mesh_handoff_v1` and lowers to ShapeIR — so the contract holds. `pythonocc-core` ships Windows wheels, so install pain is minimal.
**Files:** new `lathe/b_rep/` (mirror `lathe/f_rep/`), new `primitive_type="b_rep_brep"` in `lathe/shape_ir.py`, new lowering layer.
**Risk:** medium — OCCT API surface is large; we'd ship a thin curated subset, not the whole thing. Defer the full feature-tree concept to v2 of the IR.

### #5 — Real half-edge bevel operator (`lathe/bevel/half_edge_v1`)
**Effort:** **M** (~1–2 weeks, ~1k LoC)
**Why on the list:** the existing post-boolean PolyBevel cutback is the single biggest known mesh-quality limit on hard-surface output. A proper half-edge implementation handles arbitrary topology (extruded profiles, swept profiles, lofted solids) and emits clean miter corners that downstream subdivision/UV stages can take advantage of. Pairs especially well with #4 — a half-edge mesh bevel for the mesh path, OCCT analytic for the B-Rep path.
**Files:** new `lathe/bevel/half_edge.py`, `lathe/exact_solids.py` `_general_mesh_bevel` becomes a backend chain entry.
**Risk:** medium — the Blender PolyBevel reference algorithm is non-trivial. Mitigation: scope the v1 to box/extrusion/sweep-derived edge sets, which cover ~90% of Lathe's emitted geometry.

---

## 10. Rejected / lower-priority items (recorded for completeness)

- **MCUT direct integration** — needs a custom binding effort just to cover *partial cuts*. Defer; the boolean chain in #3 covers the practical failure cases.
- **Cherchi 2022 indirect-predicate booleans** — true SOTA but no Python wheel and binding effort is high. Track as a future tier-2 in the boolean chain when a binding lands.
- **Cinolib direct integration** — only valuable as a Cherchi prereq; defer with Cherchi.
- **NanoVDB** — read-only GPU format; no kernel-side authoring value for Lathe. Skip.
- **Full quad-dominant remeshing** — not a v0.1 priority; Lathe's stable contract is triangle output.

---

## Sources

- [libigl/include/igl/copyleft/cgal/mesh_boolean.h](https://github.com/libigl/libigl/blob/main/include/igl/copyleft/cgal/mesh_boolean.h)
- [libigl Python Bindings](https://libigl.github.io/python-bindings/)
- [libigl PyPI](https://pypi.org/project/libigl/)
- [Cherchi — Fast and Robust Mesh Arrangements (PDF)](https://www.gianmarcocherchi.com/pdf/mesh_arrangement.pdf)
- [Cherchi — Interactive and Robust Mesh Booleans (PDF)](https://www.gianmarcocherchi.com/pdf/interactive_exact_booleans.pdf)
- [Cherchi — InteractiveAndRobustMeshBooleans GitHub](https://github.com/gcherchi/InteractiveAndRobustMeshBooleans)
- [Cherchi — FastAndRobustMeshArrangements GitHub](https://github.com/gcherchi/FastAndRobustMeshArrangements)
- [Exact Predicates, Exact Constructions and Combinatorics for Mesh CSG (ACM TOG)](https://dl.acm.org/doi/10.1145/3744642)
- [MCUT GitHub](https://github.com/cutdigital/mcut)
- [MCUT site](https://cutdigital.github.io/mcut.site/)
- [manifold3d on PyPI](https://pypi.org/project/manifold3d/)
- [elalish/manifold GitHub](https://github.com/elalish/manifold)
- [trimesh boolean.py source](https://github.com/mikedh/trimesh/blob/main/trimesh/boolean.py)
- [PyMeshLab GitHub](https://github.com/cnr-isti-vclab/PyMeshLab)
- [CGAL Polygon Mesh Processing User Manual](https://doc.cgal.org/latest/Polygon_mesh_processing/index.html)
- [seagullmesh GitHub (CGAL Python bindings)](https://github.com/darikg/seagullmesh)
- [Polygon Mesh Processing Library (pmp)](https://www.pmp-library.org/)
- [Inigo Quilez — Distance Functions](https://iquilezles.org/articles/distfunctions/)
- [Schaefer & Warren — Manifold Dual Contouring (PDF)](https://people.engr.tamu.edu/schaefer/research/dualsimp_tvcg.pdf)
- [Occupancy-Based Dual Contouring (SIGGRAPH Asia 2024) — site](https://occupancy-based-dual-contouring.github.io/)
- [Occupancy-Based Dual Contouring (CVPR 2024 Self-Supervised paper PDF)](https://openaccess.thecvf.com/content/CVPR2024/papers/Sundararaman_Self-Supervised_Dual_Contouring_CVPR_2024_paper.pdf)
- [Boris the Brave — Dual Contouring Tutorial](https://www.boristhebrave.com/2018/04/15/dual-contouring-tutorial/)
- [OpenVDB Python documentation](https://www.openvdb.org/documentation/doxygen/python.html)
- [OpenVDB Release Notes](https://academysoftwarefoundation.github.io/openvdb/changes.html)
- [pyopenvdb on PyPI](https://pypi.org/project/pyopenvdb/)
- [pythonocc-core GitHub](https://github.com/tpaviot/pythonocc-core)
- [build123d on PyPI](https://pypi.org/project/build123d/)
- [build123d GitHub](https://github.com/gumyr/build123d)
- [CadQuery Documentation](https://cadquery.readthedocs.io/)
- [OCCT BRepFilletAPI_MakeFillet2d Reference](https://old.opencascade.com/doc/occt-7.2.0/refman/html/class_b_rep_fillet_a_p_i___make_fillet2d.html)
- [Blender Bevel Modifier Manual](https://docs.blender.org/manual/en/latest/modeling/modifiers/generate/bevel.html)
- [geomdl (NURBS-Python) on PyPI](https://pypi.org/project/geomdl/)
- [NURBS-Python Documentation](https://nurbs-python.readthedocs.io/en/5.x/)
- [Framing Parametric Curves (Frenet vs parallel transport)](https://janakiev.com/blog/framing-parametric-curves/)
