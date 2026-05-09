# OpenSCAD Deep Study — Lessons for Lathe

**Author:** OpenSCAD specialist (audit team)
**Date:** 2026-05-04
**Scope:** Translate every relevant OpenSCAD / Manifold / BOSL2 lesson to concrete Lathe changes.
**Companion finding (peer pipeline-auditor):** validators score metadata not pixels, bakes are broken, `DesignerGraph.evaluate()` is dead code. Several recommendations below build on that.

OpenSCAD is the closest living relative of Lathe: a declarative DSL whose source is "what the asset is" and whose compiler is the imagination layer. It has 15+ years of hard-won lessons on language ergonomics, CSG kernels, parametric ecosystems, and what *actually* makes hard-surface authoring scale. Most of those lessons translate directly.

---

## 1. OpenSCAD core architecture in 2025-2026

### 1.1 The CSG tree + lazy evaluation

OpenSCAD parses `.scad` source into a CSG tree of nodes (primitives + transforms + boolean operators). The tree is **not** evaluated eagerly — primitives are kept symbolic until a final operation requires concrete geometry. This is conceptually identical to Lathe's `ShapeProgram` (`lathe/asset_quality/shape_ir_v2.py`), which is an ordered tuple of `ShapeOp` records that downstream stages lower into geometry. **Lathe is on the right path here.** The remaining lift is closing the loop so the program drives the build (the dead `DesignerGraph.evaluate()` finding).

### 1.2 F5 preview vs F6 render — the dual-tier evaluator

OpenSCAD has two distinct evaluation paths:

- **F5 (preview):** OpenCSG GPU-based stenciling. Cheap, fast, surfaces may have visible boolean seams. Used during authoring.
- **F6 (render):** Full mesh boolean evaluation. Slow, exact, watertight. Used before export.

`$preview` is exposed as a special variable so authors can cheaply downgrade `$fn` during preview:
```openscad
$fn = $preview ? 12 : 72;
sphere(r=10);
```

**Lathe already has this concept** as `FidelityProfile` (`blockout` / `game` / `hero`) — but it is wired for *feature density*, not for kernel cost. Lathe should adopt OpenSCAD's discipline: a single `tier` value cascades from "cheap voxel SDF preview" to "exact manifold mesh" without authors writing two paths.

### 1.3 Manifold is now the default backend (Aug 2025)

This is the **biggest** OpenSCAD change in years and the most relevant to Lathe.

- OpenSCAD made Manifold (`github.com/elalish/manifold`) the default CSG backend in nightly builds starting Aug 17, 2025.
- Manifold is **30× to 1,000× faster than CGAL** depending on workload — published benchmarks show 18.75 s in CGAL vs 0.228 s in Manifold for the same model.
- Manifold provides **guaranteed-manifold output** by construction. CGAL's Nef polyhedra approach approximates it; trimesh's blender/scad/manifold backends can produce non-manifold edges. Manifold is the first algorithm with a mathematical guarantee.
- Manifold tracks **vertex properties through booleans** — UV maps, material IDs, normals all survive a union/difference. This is exactly what Lathe needs for the broken bake stage (peer finding): you cannot bake reliably if booleans destroy UVs.

**Lathe currently uses `trimesh.boolean.union/difference/intersection` in `lathe/exact_solids.py` (3 call sites) and `lathe/geometry/reference_kernel.py` (3 call sites).** Trimesh's default boolean delegates to manifold3d if installed, but only as a backend hint — and only on the geometry, with no property tracking. Lathe also has `lathe/adapters/manifold_kernel.py` (446 lines) and `lathe/geometry/manifold_kernel.py` (46 lines) — adapters exist but are not the production path.

### 1.4 fa/fs/fn fragment resolution

OpenSCAD's `$fa` (min angle), `$fs` (min size), `$fn` (forced count) form a tessellation contract:

| variable | default | meaning |
|---|---|---|
| `$fa` | 12° | min fragment angle on a circle |
| `$fs` | 2 mm | min fragment chord length |
| `$fn` | 0 | force exact count when > 0 |

Resolution is computed as `n = ceil(min(360/fa, 2*pi*r/fs))`. **This is the right contract for Lathe to adopt for `revolved_profile`, `swept_profile`, `torus`, `cylinder`, `sphere`** — it lets the same source author at any tier without hand-tuning segment counts. Currently Lathe has scattered `corner_segments`, `tube_segments`, etc. — should consolidate into one `tessellation_policy` block at the asset/profile level.

### 1.5 Customizer — parametric UX

OpenSCAD's Customizer is a comment-driven parameter UI:
```openscad
length = 50;       // [10:100]      slider
mode = "fast";     // [fast, hero]  dropdown
holes = 4;         // [0:1:8]       stepped slider
```

The genius is that **the comment IS the schema** — no separate JSON, no manifest. Lathe's `params {}` blocks could trivially adopt the same convention; it would unlock a `lathe customize <file.lth> --asset X` command that opens a TUI/web slider over every parameter and writes a variant. Hugely lowers the authoring barrier.

---

## 2. Language design — what OpenSCAD has, what Lathe is missing

OpenSCAD's language surface is small but expressive. Comparing to `grammar/lathe.lark`:

| feature | OpenSCAD | Lathe today | gap |
|---|---|---|---|
| `module` (parametric block) | yes | `family`, `component`, `assembly` | ≈ equivalent |
| `function` (pure) | yes | `let`/expressions | partial — no first-class functions |
| `children()` (operator modules) | **yes — operators that wrap children** | **no** | **major gap** |
| `let()` | yes | unclear | likely missing |
| `for(i = list)` | yes | `op.repeat` only | expression-level for missing |
| `intersection_for()` | yes | no | minor |
| List comprehensions | yes | no | major (very useful for procedural detail) |
| Named arguments | yes | partial | mostly OK |
| `hull()` / `minkowski()` | yes | **no** | **major gap** |
| `linear_extrude(twist=, scale=, slices=)` | yes | extruded_profile only — **no twist, no scale taper** | **major gap** |
| `rotate_extrude(angle=)` | yes — partial revolves | revolved_profile is full 360 | minor |
| Modifier chars (`#`, `%`, `!`, `*`) | yes — debug/highlight/disable/root | no | minor authoring nicety |

### 2.1 The `children()` mechanism — the biggest missing primitive

In OpenSCAD, a module that calls `children()` becomes an **operator** — it transforms whatever is inside. Example:
```openscad
module ring_of(n=8, r=20) {
  for (i = [0:n-1]) rotate([0,0,i*360/n]) translate([r,0,0]) children();
}
ring_of(n=12, r=30) cylinder(h=5, r=2);   // 12 cylinders in a ring
```

This is how BOSL2 builds `xcopies()`, `rot_copies()`, `arc_copies()`, `path_copies()` — every distribution pattern is an operator over arbitrary children. **Lathe has no equivalent.** The repetition ops (`op.repeat`, `op.fastener_grid`, `op.vent_slats` in `shape_ir_v2.py`) are hard-coded and chest-flavored, not generic. **In Lathe this would be wired into `lathe/asset_quality/shape_ir_v2.py:REPETITION_OPS`** by adding a generic `op.distribute(pattern, count, axis)` that takes a sub-program as payload — directly inspired by BOSL2's copy distribution family.

### 2.2 `let()` and list comprehensions

```openscad
points = [for (a = [0:5:360]) [r*cos(a), r*sin(a)]];
twisted = [for (i = [0:n], let(t = i/n)) rotate(360*t) ...];
```

This is how OpenSCAD authors generate procedural profiles, paths, and instances inline. Lathe currently encodes the same intent through Python feature_ops modules — meaning the *.lth* author cannot procedurally generate a profile in source. **Adding list comprehensions to `grammar/lathe.lark` and `lathe/parser/transformer_expr.py` is mechanical** and would let users write profile polylines, sweep paths, and instance grids in `.lth` source instead of forking Python.

### 2.3 `hull()` and `minkowski()` — the two most important missing operators

These are *the* OpenSCAD operators that make hard-surface authoring possible without writing full polyhedra by hand:

```openscad
// Smooth-corner box from 4 cylinders:
hull() {
  translate([ 10, 10, 0]) cylinder(r=2, h=5);
  translate([-10, 10, 0]) cylinder(r=2, h=5);
  translate([ 10,-10, 0]) cylinder(r=2, h=5);
  translate([-10,-10, 0]) cylinder(r=2, h=5);
}

// Minkowski-rounded plate:
minkowski() {
  cube([20, 20, 2]);
  sphere(r=1);   // every edge is now radius-1 rounded
}
```

`hull()` is the canonical way to build organic-feeling but exact-CSG forms (rifle stocks, ergonomic grips, control pedestals, fairings). `minkowski(sphere)` is the canonical way to globally round all edges of a complex form. **Both are Manifold-native operations** (`manifold3d.Manifold.hull()`, `.minkowski()`). Lathe has neither.

**In Lathe these would be wired into:**
- `lathe/asset_quality/shape_ir_v2.py:BOOLEAN_OPS` — add `op.hull` and `op.minkowski`.
- `lathe/exact_solids.py` — add the lowering using `manifold3d.Manifold.hull()` and `.minkowski()`. (No need to implement; Manifold provides them.)
- `grammar/lathe.lark` — surface as `hull { ... }` and `minkowski { ... }` blocks.

---

## 3. Geometry primitives & operators

### 3.1 What Lathe has (per `lathe/shape_ir.py:ShapePrimitive`)

`box`, `cylinder`, `sphere`, `revolved_profile`, `extruded_profile`, `torus`, `subdivision_box` (per-corner radii), `swept_profile` (cross-section + 3D path), `heightfield`, `lofted_solid`. This is a strong primitive set — actually richer than vanilla OpenSCAD.

### 3.2 What OpenSCAD has that Lathe is missing

| primitive | OpenSCAD | Lathe | Why it matters for hard-surface |
|---|---|---|---|
| `linear_extrude(h, twist, scale, slices)` | yes | extruded_profile lacks `twist` and `scale` | Twisted bits, tapered fins, gun handles, drill bits — **huge expressiveness gap** |
| `rotate_extrude(angle<360)` | yes — partial revolves | revolved_profile is 360 only | Spiral ramps, partial domes, opening hatches |
| `polyhedron(points, faces)` | yes | no — `lofted_solid` is closest | Escape valve when no other primitive fits |
| `surface(file=...)` | yes — DEM heightmap | `heightfield` exists | Equivalent — already there |
| `offset(r=)` (2D) | yes | no | Inset/outset 2D profiles for varied panel lines |
| `hull()` / `minkowski()` (3D) | yes | no | (covered above) |

The single highest-ROI gap is **`linear_extrude` with `twist` and `scale`**. Twist is the difference between a barrel and a *rifled* barrel, between a fin and a turbine vane, between a column and a fluted column. Scale is the difference between a prism and a tapered shroud. Lathe already has `extruded_profile` and `lofted_solid` — adding `twist_degrees` and `scale_end` parameters to `extruded_profile` is a 30-line change in `lathe/exact_solids.py:_compile_extruded_profile`.

### 3.3 OpenSCAD's tessellation discipline

OpenSCAD's `$fa/$fs/$fn` apply uniformly across primitives — a sphere, a cylinder, and a `rotate_extrude` all read the same special variables. **Lathe's tessellation density is currently scattered across primitive-specific fields** (`corner_segments` on subdivision_box, `tube_segments` on torus, `revolution_segments` on revolved_profile). Consolidating into a single `TessellationPolicy(min_angle_deg=12, min_chord_cm=0.2, force_count=None)` carried on `ShapeIR` (and overrideable per-primitive) is a clear refactor.

---

## 4. The Manifold library — the right CSG kernel for Lathe

### 4.1 Why OpenSCAD switched

The OpenSCAD team's PR #4533 ("Use Manifold for much faster & multithreaded CSG & minkowski operations") shows the motivation crystal-clearly:
- **Speed:** 30-1000× speedup, multithreaded by default.
- **Robustness:** mathematically-guaranteed manifold output. CGAL approximates this with floating-point Nef polyhedra and occasionally fails on degenerate input.
- **Property tracking:** UV maps, materials, and normals propagate through booleans. This is *the* feature for downstream baking.
- **Cross-section support:** `manifold3d.CrossSection` provides 2D Clipper-equivalent ops + `linear_extrude`/`rotate_extrude` first-class.

### 4.2 Why this matters for Lathe specifically

The peer pipeline-auditor's finding is that **bakes are broken**. One major contributor: `trimesh.boolean.union` does not preserve UVs across the operation — every boolean re-tessellates and emits a fresh mesh with default UVs. So even if topology/UV stages produce correct output, the final boolean fusion in `exact_solids.py` destroys it.

**Manifold's MeshGL preserves vertex properties through booleans.** Switching the production path from `trimesh.boolean` to `manifold3d` directly addresses this without changing the bake stage at all.

### 4.3 Lathe already has the adapter

`lathe/adapters/manifold_kernel.py` (446 lines) is non-trivial — it's a serious adapter, not a stub. The work is **promoting it from adapter to production path** in `exact_solids.py` and ensuring `trimesh.boolean` is only the conservative fallback.

---

## 5. The BOSL2 ecosystem — the gold standard authoring layer

BOSL2 (`github.com/BelfrySCAD/BOSL2`) is a 50k-line OpenSCAD library that effectively *is* the OpenSCAD hard-surface authoring layer. It demonstrates what a mature `std/` directory looks like.

### 5.1 BOSL2 module families

| .scad file | what it provides |
|---|---|
| `shapes2d.scad` | 2D building blocks (regular polygons, stars, gears, teardrops, ovals, supershape) |
| `shapes3d.scad` | `cuboid()`, `prismoid()`, `regular_prism()`, `rect_tube()`, `tube()`, `wedge()`, `octahedron()`, `pie_slice()`, `teardrop()`, `onion()` — all with chamfer/rounding parameters |
| `masks2d.scad` / `masks3d.scad` | profile masks for edges: `chamfer`, `rounding`, `cove`, `ogee`, `rabbet`, `dovetail`, `teardrop` |
| `rounding.scad` | `round_corners()`, `smooth_path()` (G2 continuous-curvature), `offset_sweep()`, `rounded_prism()`, `join_prism()` |
| `paths.scad` | path operations on 2D/3D point lists |
| `transforms.scad` | shorthand for translate/rotate/mirror/scale |
| `attachments.scad` | the anchor/orient/spin/attach system |
| `screws.scad` | dimensionally-accurate standard screws (M3, M5, etc.) |
| `threading.scad` | parametric threaded rod / nuts |
| `gears.scad` | spur gears, bevel gears, racks, worms |
| `hinges.scad` | living hinges, snap hinges |
| `joiners.scad` | clips, dovetails, snap connections |
| `bottlecaps.scad` | standard bottle thread profiles |

### 5.2 The killer features

**`cuboid()`** — a single primitive that subsumes Lathe's `box` + `subdivision_box`:
```openscad
cuboid([20, 20, 5], chamfer=1, edges=[TOP+RIGHT, BOT+RIGHT]);
cuboid([20, 20, 5], rounding=2, except_edges=[BOT]);
```

The `edges` and `except_edges` selectors are the secret — you don't pre-compute 8 corner radii (Lathe's `subdivision_box` design), you select edge sets symbolically. `BOT`, `TOP`, `LEFT`, `RIGHT`, `FRONT`, `BACK`, plus combinations (`TOP+FRONT` = the front-top edge) and groups (`Z_AXIS_EDGES`).

**In Lathe this would be wired into `lathe/shape_ir.py:ShapePrimitive`** — replace `corner_radii` (per-corner array) with `chamfer_edges` / `round_edges` (edge selectors + radii). It's a richer, less error-prone authoring surface.

**`edge_profile()`** — walks the edges of an attachable parent and applies a 2D profile mask along each. This is how BOSL2 makes "this whole box has a 0.5mm chamfer except where it joins the base" express in 1 line. Lathe's `op.bevel` and `op.chamfer` (in `EDGE_OPS`) need an equivalent edge-selector vocabulary.

**`offset_sweep()` and `rounded_prism()` with G2 continuous-curvature** — BOSL2 supports 4th-order Bezier transitions (parameter `k`) for premium-feeling rounds. This is the difference between a "3D-printer-rounded" cube and a "production hardware product" cube. Lathe's bevel ops should expose a `continuity` parameter (`g1` chamfer, `g1_round` arc, `g2_smooth` Bezier).

**`screws.scad`, `threading.scad`, `gears.scad`** — none of these exist in Lathe's `std/` directory. For an asset DSL that wants to handle "production-ready hard-surface assets", standard fasteners and gears are table stakes. They are also extremely hard to author correctly from primitives — exactly the kind of thing a stdlib should solve once.

### 5.3 What Lathe's `std/` is missing

Lathe `std/` currently has: families, components, materials, patterns, surface_programs, palettes, repair, spaces, benchmarks, kits, libraries, mechanisms, policies, masks, terrain, vegetation. Notably absent:

- **`std/fasteners/`** — screws, bolts, rivets, cap heads, hex heads with dimensionally-accurate profiles (M2 through M12). Currently `brass_band_rivets_features` (in `feature_ops/`) is hardcoded for the chest fixture — exactly the chest-as-product smell flagged in user memory.
- **`std/threading/`** — threaded rod profiles (ISO metric, UNC).
- **`std/gears/`** — involute spur, bevel, rack/pinion.
- **`std/edge_profiles/`** — chamfer, rounding, ogee, cove, teardrop as named 2D profiles attachable to any edge.
- **`std/joinery/`** — clips, snaps, dovetails, mortise/tenon. Useful for modular assets that snap together.

---

## 6. Implementable proposals — ROI-ranked

Each proposal: (a) inspiration, (b) Lathe file(s) to modify, (c) why it improves visible asset quality, (d) effort.

### Proposal 1 — Switch CSG kernel to manifold3d in production path **(M, highest ROI)**

- **Inspiration:** OpenSCAD's Aug 2025 default-backend switch. Manifold is 30-1000× faster, guarantees manifold output, and preserves vertex properties (UVs, materials, normals) through booleans.
- **Lathe files:** `lathe/exact_solids.py` (3 `trimesh.boolean.*` call sites lines ~1170/1179/1189), `lathe/geometry/reference_kernel.py` (3 sites). The adapter already exists at `lathe/adapters/manifold_kernel.py` (446 lines).
- **Why it improves visible asset quality:** Directly addresses the broken-bake finding from the pipeline auditor. Booleans will no longer destroy UV maps. Combined with already-correct topology/UV stages, baked textures will map correctly for the first time.
- **Effort:** M. Adapter exists; the work is wiring it as the primary path with `trimesh.boolean` as conservative fallback, plus property-preservation tests (`tests/test_csg_uv_preservation.py`).

### Proposal 2 — Add `hull()` and `minkowski()` operators **(M, very high ROI)**

- **Inspiration:** OpenSCAD's two highest-leverage CSG operators. `hull()` is how authors build organic-feeling exact CSG (grips, fairings, stocks). `minkowski(sphere)` is the canonical "round all edges" operator.
- **Lathe files:** Add `op.hull` and `op.minkowski` to `BOOLEAN_OPS` in `lathe/asset_quality/shape_ir_v2.py`. Surface as `hull { ... }` and `minkowski { ... }` blocks in `grammar/lathe.lark`. Lower in `lathe/exact_solids.py` using `manifold3d.Manifold.hull()` and `.minkowski()` (Manifold has both natively).
- **Why it improves visible asset quality:** Authors can build smooth ergonomic forms (control pedestals, helmet shells, vehicle fairings) without falling back to mesh sculpting. This is the single biggest expressiveness gap vs OpenSCAD.
- **Effort:** M. Manifold provides the math; wiring is straightforward.

### Proposal 3 — Add `twist` and `scale_end` to extruded_profile **(S, high ROI)**

- **Inspiration:** `linear_extrude(h, twist=360, scale=[1,2], slices=N)`. Twist for fluted columns / rifled barrels / drill bits / turbine vanes. Scale for tapered shrouds / fins / tubes.
- **Lathe files:** `lathe/shape_ir.py:ShapePrimitive` (add `twist_degrees: float = 0.0`, `scale_end: tuple[float,float] | None = None`, `slices: int = 1`). Update `lathe/exact_solids.py:_compile_extruded_profile` to interpolate cross-section through slices.
- **Why it improves visible asset quality:** Unlocks an entire class of hard-surface details — rifled/fluted/twisted features — that are currently impossible. ~30 lines of code for a major expressiveness gain.
- **Effort:** S.

### Proposal 4 — Operator/`children()` mechanism + generic `op.distribute` **(M, high ROI for modularity)**

- **Inspiration:** OpenSCAD `module` calling `children()`. BOSL2 `xcopies/ycopies/rot_copies/arc_copies/path_copies/grid_copies` — every distribution pattern is an operator over arbitrary children.
- **Lathe files:** Replace chest-specific `op.fastener_grid`, `op.vent_slats`, `op.trim_band`, `op.corner_guard_set` in `lathe/asset_quality/shape_ir_v2.py:REPETITION_OPS` with a single generic `op.distribute(pattern, count, axis, spacing)` that takes a child sub-program. Pattern enum: `linear`, `grid`, `radial`, `arc`, `along_path`. Lower in `lathe/feature_ops/__init__.py` by removing chest-specific helpers.
- **Why it improves visible asset quality + modularity:** Directly addresses the "Lathe must be ultra modular" feedback. The current feature_ops directory is a wall of chest-specific helpers (`brass_band_rivets_features`, `fastener_strip_features`, `bolt_grid_features`, `rivet_grid_features`...). Generalizing to one operator with a pattern parameter shrinks the API surface 20×.
- **Effort:** M. Mostly deletion + thin generalization.

### Proposal 5 — BOSL2-style `edge_selector` + edge_profile mask system **(M, high ROI for premium feel)**

- **Inspiration:** BOSL2 `cuboid(edges=[TOP+RIGHT], chamfer=1)`, `edge_profile()` with mask2d profiles (`chamfer`, `rounding`, `cove`, `ogee`, `teardrop`, `dovetail`).
- **Lathe files:** Replace `subdivision_box.corner_radii` (8-tuple) in `lathe/shape_ir.py` with `EdgeSelector` + `edge_treatments: dict[selector, profile]`. Add `std/edge_profiles/` with 2D profile defs (chamfer, rounding, ogee, cove, teardrop). Wire `op.bevel`/`op.chamfer` in `shape_ir_v2.py:EDGE_OPS` to accept an edge selector and a profile name.
- **Why it improves visible asset quality:** This is the single largest "production-feel" lever. Real hard-surface assets have selective edge treatments — a base might have rounded top edges and chamfered bottom edges; a panel might have an ogee on the front face and crisp on the back. Lathe currently can only round all corners uniformly.
- **Effort:** M.

### Proposal 6 — `std/fasteners/` + `std/threading/` + `std/gears/` **(L, high ROI for breadth)**

- **Inspiration:** BOSL2 `screws.scad`, `threading.scad`, `gears.scad`. Dimensionally-accurate parametric standards.
- **Lathe files:** New directories `std/fasteners/`, `std/threading/`, `std/gears/`. Delete chest-specific `lathe/feature_ops/__init__.py:brass_band_rivets_features` and replace with `std/fasteners/rivet.lth`-defined rivet that the chest example *imports*.
- **Why it improves visible asset quality + modularity:** Closes the "chest-as-product" smell directly. Chest becomes one example among many, all assembled from a real shared parts library. Also unlocks mechanical assets (mounts, brackets, gear boxes, latched containers).
- **Effort:** L. Lots of careful dimensional standards work, but pure data — no kernel changes.

### Proposal 7 — Customizer-style `// [range]` parameter UI **(S, high ROI for adoption)**

- **Inspiration:** OpenSCAD Customizer comment-driven parameter UI.
- **Lathe files:** Extend `lathe/parser/transformer_blocks.py` to parse `// [10:100]` and `// [fast,hero]` comments on `params {}` block entries. New CLI command `python -m lathe.cli customize <file.lth> <asset>` that reads the schema and either prints a TUI form or emits a JSON parameter manifest.
- **Why it improves visible asset quality:** It doesn't, *directly* — but it dramatically lowers the authoring barrier. A non-programmer can tweak parameters without editing source. This unlocks the "imagination layer" promise for users who can't write `.lth`.
- **Effort:** S for the parser piece; M total if you build a real GUI.

### Proposal 8 — `let()` and list comprehensions in `.lth` expressions **(S, medium ROI)**

- **Inspiration:** OpenSCAD `[for (i = [0:n]) let(t = i/n) [r*cos(t*2*PI), r*sin(t*2*PI)]]`.
- **Lathe files:** `grammar/lathe.lark` (add list comprehension production), `lathe/parser/transformer_expr.py` (lower to a Python list comprehension during evaluation). Tests in `tests/test_parser_comprehensions.py`.
- **Why it improves visible asset quality:** Lets authors generate procedural profiles, sweep paths, and instance grids inline in `.lth`. Today, authors must fork into Python `feature_ops` to do this — meaning new procedural patterns require Python changes, not just `.lth` changes.
- **Effort:** S.

### Proposal 9 — Unified `TessellationPolicy(fa, fs, fn)` on ShapeIR **(S, medium ROI)**

- **Inspiration:** OpenSCAD's `$fa/$fs/$fn` cascade.
- **Lathe files:** `lathe/shape_ir.py` — add `TessellationPolicy` dataclass on `ShapeIR`, with per-primitive override slots. Migrate `corner_segments`, `tube_segments`, `revolution_segments` etc. into per-primitive overrides. Drive from `FidelityProfile`.
- **Why it improves visible asset quality:** Cleaner authoring; one knob for "blockout vs hero", consistent silhouettes across primitives at the same tier. Reduces stair-stepping artifacts where one primitive uses 16 segments and an adjacent one uses 64.
- **Effort:** S.

### Proposal 10 — G2 continuous-curvature option on bevel/round ops **(M, medium-high ROI for premium feel)**

- **Inspiration:** BOSL2 `round_corners(method="smooth", k=0.5)` using 4th-order Bezier transitions.
- **Lathe files:** Add `continuity: Literal["g0_chamfer", "g1_arc", "g2_smooth"]` and `k: float = 0.5` to `op.bevel`/`op.chamfer` in `lathe/asset_quality/shape_ir_v2.py:EDGE_OPS`. Implement g2 path generation in `lathe/exact_solids.py`.
- **Why it improves visible asset quality:** Specular highlights track smoothly across G2 surfaces; G1 arcs show a visible curvature discontinuity at the tangent. This is the difference between "looks OK" and "looks like a real product". Premium feel for hero assets.
- **Effort:** M. Bezier math is standard, but proper edge-walk integration takes care.

---

## 7. Synthesis — what OpenSCAD says about Lathe's trajectory

OpenSCAD, BOSL2, and Manifold are an existence proof for the Lathe thesis: **declarative-source + deterministic-CSG-kernel + community-stdlib is enough to author production hard-surface assets.** The shape stage is right; the problem is execution gaps:

1. **The kernel is the problem.** `trimesh.boolean` on the production path destroys properties through booleans. Manifold solves this. The adapter already exists.
2. **The primitive set is 80% there.** `hull`, `minkowski`, `linear_extrude(twist=, scale=)` close the last gap.
3. **The stdlib is chest-shaped.** Generic distribution operators + a real fasteners/edge_profiles library would dissolve the chest-specific code paths.
4. **The language is 80% there.** List comprehensions + `let()` + `children()`-equivalent close the authoring gap.
5. **The customizer pattern is free adoption juice.** Comment-driven parameter UI is one of OpenSCAD's most loved features and trivial to copy.

The proposals above are ordered so that #1 (Manifold) and #2 (hull/minkowski) land first — they unblock the bake stage and the largest authoring gap simultaneously. #3 and #4 close the "lathe is ultra modular" loop. #5-10 are quality and ergonomic refinements.

**None of these recommendations conflict with "Lathe is standalone procedural" — Manifold, OpenSCAD, and BOSL2 are all 100% deterministic procedural. No AI is being added.**

---

## Sources

- [OpenSCAD Manifold default backend (Aug 2025)](https://fosstodon.org/@OpenSCAD/113256867413539398)
- [Make Manifold integration release ready (issue #4825)](https://github.com/openscad/openscad/issues/4825)
- [Manifold performance discussion (#383)](https://github.com/elalish/manifold/discussions/383)
- [Use Manifold for much faster CSG (PR #4533)](https://github.com/openscad/openscad/pull/4533)
- [OpenSCAD User Manual — 2D to 3D Extrusion](https://en.wikibooks.org/wiki/OpenSCAD_User_Manual/2D_to_3D_Extrusion)
- [OpenSCAD User Manual — User-Defined Functions and Modules](https://en.wikibooks.org/wiki/OpenSCAD_User_Manual/User-Defined_Functions_and_Modules)
- [OpenSCAD User Manual — Conditional and Iterator Functions](https://en.wikibooks.org/wiki/OpenSCAD_User_Manual/Conditional_and_Iterator_Functions)
- [OpenSCAD CSG Modelling](https://en.wikibooks.org/wiki/OpenSCAD_User_Manual/CSG_Modelling)
- [OpenSCAD Customizer](https://en.wikibooks.org/wiki/OpenSCAD_User_Manual/Customizer)
- [OpenSCAD Cheatsheet](https://openscad.org/cheatsheet/)
- [OpenSCAD Other Language Features ($fa/$fs/$fn/$preview)](https://files.openscad.org/documentation/manual/Other_Language_Features.html)
- [Hackaday: OpenSCAD hull() guide](https://hackaday.com/2018/02/13/openscad-tieing-it-together-with-hull/)
- [Manifold core library (DeepWiki)](https://deepwiki.com/elalish/manifold/2-core-library)
- [manifold3d on PyPI](https://pypi.org/project/manifold3d/)
- [BOSL2 repository](https://github.com/BelfrySCAD/BOSL2)
- [BOSL2 CheatSheet](https://github.com/BelfrySCAD/BOSL2/wiki/CheatSheet)
- [BOSL2 rounding.scad reference](https://github.com/BelfrySCAD/BOSL2/wiki/rounding.scad)
- [BOSL2 shapes3d.scad reference](https://github.com/BelfrySCAD/BOSL2/wiki/shapes3d.scad)
- [BOSL2 masks3d.scad reference](https://github.com/BelfrySCAD/BOSL2/wiki/masks3d.scad)
- [BOSL2 Tutorial — Rounding the Cube](https://github.com/BelfrySCAD/BOSL2/wiki/Tutorial-Rounding_the_Cube)
