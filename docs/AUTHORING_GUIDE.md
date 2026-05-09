# Lathe Authoring Guide

A single-document tutorial for authoring `.lth` source covering all five
procedural paradigms shipped in the Lathe kernel — hard-surface mechanical,
vegetation, terrain, organic SDF, and WFC modular composition — plus the
scatter family productivity multipliers.

After reading this guide once, an author can write a chest, a tree, a
hilltop, an alien creature, or a dungeon corridor — and compose all of
them inside a single `mesh_program{}` block.

## Table of contents

1. [What Lathe ships — the 5 paradigms](#1-what-lathe-ships)
2. [Quick start — your first build](#2-quick-start)
3. [`.lth` source structure](#3-lth-source-structure)
4. [The 5 paradigms](#4-the-5-paradigms)
   - [4.1 Hard-surface mechanical](#41-hard-surface-mechanical)
   - [4.2 Procedural vegetation](#42-procedural-vegetation)
   - [4.3 Terrain](#43-terrain)
   - [4.4 Organic SDF](#44-organic-sdf)
   - [4.5 Modular WFC composition](#45-modular-wfc-composition)
5. [Productivity — the scatter family](#5-productivity-scatter-family)
6. [Composing all paradigms](#6-composing-all-paradigms)
7. [Velocity loop](#7-velocity-loop)
8. [Op reference table](#8-op-reference-table)
9. [Common patterns / idioms](#9-common-patterns--idioms)

---

## 1. What Lathe ships

Lathe is a declarative `.lth` language plus a single procedural kernel
covering five paradigms. Every paradigm lowers to the same stable
`ShapePrimitive` records and flows through the same deterministic
topology / UV / package pipeline.

| Paradigm | Produces | Smallest demo |
|---|---|---|
| Hard-surface mechanical | Chests, panels, drones, fasteners, vents, trim, beveled CAD-style booleans | `examples/bevel_demo.lth` |
| Procedural vegetation | Tapered/bent trunks, branch + leaf canopies | `examples/oak_tree_demo.lth` |
| Terrain | Heightfield ground planes with biome modifiers | `examples/rocky_hill_demo.lth` |
| Organic SDF | Smooth-blended capsules / spheres / boxes (creatures, blobs) | `examples/alien_blob_demo.lth` |
| Modular WFC | Wave-Function-Collapse cell tiling of any primitives | `examples/dungeon_corridor_demo.lth` |

**Capstone proof point:** `examples/alien_grove_showcase.lth` runs all
five paradigms in a single `mesh_program{}` block, producing one GLB.

---

## 2. Quick start

The smallest interesting demo is `examples/bevel_demo.lth` — a 10cm
cube with an 8x8x4cm cutout and a 1cm bevel on the resulting lip.

```bash
# Check the source parses + type-checks.
python -m lathe.cli check examples/bevel_demo.lth

# Run a fast preview build (~30-60s wall-clock, multi-part GLB).
python -m lathe.cli quick examples/bevel_demo.lth bevel_demo \
    --out preview.glb --no-cache
```

Open `preview.glb` in any glTF viewer (e.g. https://gltf-viewer.donmccurdy.com/)
or load it programmatically:

```python
import trimesh
mesh = trimesh.load("preview.glb")
print(mesh.bounds, len(mesh.geometry) if hasattr(mesh, "geometry") else "single")
```

The full `lathe build` pipeline takes ~20-25 minutes because it runs
bakes, validators, repair rounds, and packaging. For authoring iteration
always use `lathe quick` (see §7).

---

## 3. `.lth` source structure

Every `.lth` source has three layers — module declaration, optional
imports, and one or more `asset` blocks.

```lathe
module demo.tutorial

asset my_first_asset : hard_surface_prop {
  intent {
    role = "tutorial demo"
    asset_class = "hero"
  }

  build {
    shape {
      mode = generate
      candidates = 1
      seed = 42

      mesh_program {
        let body = solid_panel(extents: [40cm, 30cm, 2cm])
      }
    }
  }
}
```

Anatomy:

- **`module <dotted.name>`** — namespace declaration (one per file).
- **`asset <name> : <profile>`** — names the asset and inherits a profile
  (e.g. `hard_surface_prop`). The profile sets backend stack defaults.
- **`intent { ... }`** — semantic metadata. `role` is human-readable;
  `asset_class` controls fidelity tier (`hero` / `cinematic` enable richer
  features). Optional fields: `style`, `materials`, `scale`.
- **`build { shape { ... } }`** — the build plan. `mode = generate` enables
  procedural generation. `candidates` and `seed` make builds deterministic
  (`candidates = 1` is fastest for authoring).
- **`mesh_program { ... }`** — the imperative block where you author
  geometry. This is the focus of the rest of the guide.

Inside `mesh_program`:

- **`let <name> = <call>(...)`** — bind a primitive, SDF, or point set.
- **Bare statements** — calls without `let` apply effects (booleans,
  fillets, scatter, biome modifiers).
- **Method chaining** — `.translate([x, y, z])` shifts a primitive or SDF.
- **Unit literals** — `10cm`, `4mm`, `2m`, `1.5m`. Negative literals
  (`-12cm`) are supported.
- **Vector literals** — `[10cm, 5cm, 0cm]`.

---

## 4. The 5 paradigms

Each subsection shows minimum-viable usage, key parameters, and
variations. Order is simplest → richest.

### 4.1 Hard-surface mechanical

**What it produces:** chests, panels, drones, fasteners, vents, trim,
beveled CAD-style booleans.

**Minimum viable example** (full demo: `examples/bevel_demo.lth`):

```lathe
mesh_program {
  let body = box(extents: [10cm, 10cm, 10cm])
  let cutout = box(extents: [8cm, 8cm, 4cm]).translate([0cm, 0cm, 4cm])
  let result = boolean(op: subtract, a: body, b: cutout, seam_group: "lip")
  fillet_edge(target: result, edge_class: "lip", radius: 1cm, segments: 4)
}
```

**Solid primitives:**

| Op | Required args | Optional | Notes |
|---|---|---|---|
| `box(extents)` | `extents: [W,H,D]` | — | Plain axis-aligned box. |
| `solid_panel(extents)` | `extents: [W,H,D]` | — | Thin slab; tagged for CAD intent. |
| `solid_rail(length, profile)` | `length`, `profile` | `axis: "x"\|"y"\|"z"` | Square-section bar; default axis `"x"`. |
| `solid_prism(extents)` | `extents: [W,H,D]` | — | Triangular prism (gusset/ramp). |
| `solid_cylinder(radius, height)` | `radius`, `height` | `axis: "x"\|"y"\|"z"` | Default axis `"y"`. |
| `solid_rounded_box(extents, radius)` | `extents`, `radius` | — | Box with corner rounding. |

**Compound ops** (mutate a `target` primitive in place by appending
features to the program's primitive list):

| Op | Key args |
|---|---|
| `op_fastener_grid(target, face, rows, cols, spacing, fastener_radius, fastener_height)` | `seam_group?` |
| `op_vent_slats(target, face, count, slot_width, slot_length, slot_depth, spacing, axis)` | `seam_group?` |
| `op_trim_band(target, axis, width, depth)` | `offset?`, `seam_group?` |

`face` accepts `"+x"`, `"-x"`, `"+y"`, `"-y"`, `"+z"`, `"-z"`.
`axis` accepts `"x"`, `"y"`, `"z"`.

**Boolean + bevel idiom** — declare a `seam_group` on the boolean, then
`fillet_edge` on the resulting binding using that name as `edge_class`:

```lathe
let result = boolean(op: subtract, a: body, b: cutout, seam_group: "lip")
fillet_edge(target: result, edge_class: "lip", radius: 1cm, segments: 4)
```

**Common variation — the full mechanical panel** (excerpt from
`examples/mech_prop_demo.lth`):

```lathe
let body = solid_panel(extents: [40cm, 30cm, 2cm])
op_fastener_grid(
  target: body, face: "+z",
  rows: 2, cols: 6, spacing: 5cm,
  fastener_radius: 3mm, fastener_height: 4mm,
)
op_vent_slats(
  target: body, face: "+z",
  count: 6, slot_width: 8mm, slot_length: 12cm,
  slot_depth: 1cm, spacing: 16mm, axis: "x",
)
op_trim_band(target: body, axis: "y", width: 1cm, depth: 2mm)
```

Tip: `op_trim_band` keeps a panel body in the primitive list when used
alone (it always emits the band as a child), so you can use it to anchor
a body that would otherwise only be referenced by scatter / compound ops.

Full demo: `examples/mech_prop_demo.lth`.

### 4.2 Procedural vegetation

**What it produces:** tapered/bent trunks plus branch + leaf canopies.
Same kernel that builds chests, no vegetation-specific code path.

**Minimum viable example** (full demo: `examples/oak_tree_demo.lth`):

```lathe
mesh_program {
  let trunk = vegetation_trunk(
    height: 4m,
    base_radius: 25cm,
    taper: 0.4,
    segments: 6,
  )
  vegetation_canopy(
    parent: trunk,
    branch_count: 10,
    leaf_density: 60,
    leaf_size: 6cm,
    foliage_radius: 140cm,
  )
}
```

**Key parameters:**

| Op | Required | Optional |
|---|---|---|
| `vegetation_trunk` | `height`, `base_radius` | `taper` (0..1, default 0.3), `segments` (≥2, default 6), `bend` (radians, default 0.05) |
| `vegetation_canopy` | `parent`, `branch_count` (≥1), `leaf_density` (≥0), `leaf_size`, `foliage_radius` | `branch_pitch` (radians, default 1.05) |

`taper = 0.0` is a perfect cylinder. `taper = 0.5` shrinks the top to
half the base radius. `bend` adds a gentle natural lean. `leaf_density:
0` produces a skeleton-only tree. The trunk is a `lofted_solid`; the
canopy emits branches as cylinders and leaves as spheres.

**Variations:**
- A second trunk: `let trunk_b = vegetation_trunk(...).translate([6m, 0cm, -4m])`
- A leafless winter version: `leaf_density: 0`.
- Tighter columnar tree: `taper: 0.7`, `branch_pitch: 0.4` (branches reach more upward).

### 4.3 Terrain

**What it produces:** triangulated heightfield ground plane with optional
biome modifier (alpine peaks, rolling hills, rocky crinkle).

**Minimum viable example** (full demo: `examples/rocky_hill_demo.lth`):

```lathe
mesh_program {
  let ground = terrain_heightfield(
    extents: [40m, 40m],
    resolution: 64,
    scale_z: 8m,
    seed: 1234,
  )
  terrain_biome(
    target: ground,
    biome: "alpine",
    roughness: 0.6,
    peak_density: 0.3,
  )
}
```

**Key parameters:**

| Op | Required | Optional |
|---|---|---|
| `terrain_heightfield` | `extents: [W, H]` (XY footprint), `resolution` (≥8), `scale_z` (peak vertical relief), `seed` | `octaves` (1..10, default 5) |
| `terrain_biome` | `target`, `biome` | `roughness` (0..1, default 0.5), `peak_density` (0..1, default 0.2) |

**Biomes:**
- `"alpine"` — sharp Gaussian peaks; rocky outcrops.
- `"rolling_hills"` — soft sinusoidal envelope; long swells.
- `"rocky"` — high-frequency fractal detail layer.

The fbm noise is normalised to `[0, 1]` and multiplied by `scale_z`, then
tapered with a raised cosine at the rim so terrain reads as a hilltop
rather than a torn rectangle.

**Variation — rolling-hills + rim-tapered ground** (from showcase):

```lathe
let ground = terrain_heightfield(extents: [30m, 30m], resolution: 48,
                                 scale_z: 4m, seed: 7)
terrain_biome(target: ground, biome: "rolling_hills",
              roughness: 0.3, peak_density: 0.1)
```

### 4.4 Organic SDF

**What it produces:** smooth-blended implicit surfaces (capsules, spheres,
boxes) → marching-cubes mesh. The way to author shapes the box+cylinder
vocabulary cannot express (creatures, blobs, organic membranes).

**Minimum viable example** (full demo: `examples/alien_blob_demo.lth`):

```lathe
mesh_program {
  let body  = sdf_capsule(half_height: 50cm, radius: 30cm)
  let arm_a = sdf_capsule(half_height: 40cm, radius: 10cm).translate([50cm, 0cm, 0cm])
  let arm_b = sdf_capsule(half_height: 40cm, radius: 10cm).translate([-50cm, 0cm, 0cm])
  let head  = sdf_sphere(radius: 20cm).translate([0cm, 60cm, 0cm])
  let blended = sdf_smooth_union(
    targets: [body, arm_a, arm_b, head],
    k: 15cm,
  )
  sdf_extract(
    target: blended,
    resolution: 96,
    bounds_min: [-1.2m, -1.2m, -1.2m],
    bounds_max: [1.2m, 1.2m, 1.2m],
  )
}
```

**Key flow:**
1. Build SDF primitives (`sdf_sphere`, `sdf_capsule`, `sdf_box`).
2. Translate them in place via `.translate([...])`.
3. Combine via `sdf_smooth_union(targets: [...], k: <blend>)`.
4. `sdf_extract(target, resolution, bounds_min, bounds_max)` runs marching
   cubes inside the bounds box and emits a single
   `ShapePrimitive(primitive_type="sdf_mesh")` for the deterministic
   downstream pipeline.

**Key parameters:**

| Op | Required |
|---|---|
| `sdf_sphere` | `radius` |
| `sdf_capsule` | `half_height`, `radius` (axis +Y) |
| `sdf_box` | `extents: [W,H,D]` |
| `sdf_smooth_union` | `targets: [<idents>]`, `k` (blend radius) |
| `sdf_extract` | `target`, `resolution`, `bounds_min: [x,y,z]`, `bounds_max: [x,y,z]` |

`k` controls the blend radius — larger `k` produces a more organic /
membrane-y silhouette where parts merge. `resolution` is the marching
cubes grid (96 = ~250k tris worst case; bump to 128/192 for cinematic).

**Tip:** make `bounds_min` / `bounds_max` slightly larger than the AABB
of the union so isosurface extraction has room to close — too tight a
box clips the surface.

### 4.5 Modular WFC composition

**What it produces:** Wave Function Collapse modular tile assembly
(dungeons, buildings, procedural rooms). Any primitive (regardless of
which paradigm built it) can be wrapped as a WFC module.

**Minimum viable example** (full demo: `examples/dungeon_corridor_demo.lth`):

```lathe
mesh_program {
  let floor  = solid_panel(extents: [3m, 30cm, 3m])
  let wall   = solid_panel(extents: [3m, 3m, 30cm])
  let pillar = solid_cylinder(radius: 30cm, height: 3m, axis: "y")

  let mod_floor  = wfc_module(name: "floor",  primitive: floor,  weight: 0.7)
  let mod_wall   = wfc_module(name: "wall",   primitive: wall,   weight: 0.2)
  let mod_pillar = wfc_module(name: "pillar", primitive: pillar, weight: 0.1)

  let rule_ff_x = wfc_rule(a: "floor", b: "floor", direction: "x")
  let rule_ff_z = wfc_rule(a: "floor", b: "floor", direction: "z")

  wfc_modular(
    canvas_size: [10, 1, 10],
    cell_size: 3m,
    modules: [mod_floor, mod_wall, mod_pillar],
    adjacency: [rule_ff_x, rule_ff_z],
    seed: 42,
  )
}
```

**Key parameters:**

| Op | Args |
|---|---|
| `wfc_module` | `name`, `primitive`, `weight` (0..1) |
| `wfc_rule` | `a`, `b` (module names), `direction: "x"\|"y"\|"z"`, `probability?` |
| `wfc_modular` | `canvas_size: [nx, ny, nz]`, `cell_size`, `modules: [...]`, `adjacency: [...]`, `seed` |

`canvas_size` is the WFC grid in cells; `cell_size` is the cell pitch.
The solver collapses the grid then emits one translated copy of the
chosen module's primitive per cell.

`wfc_rule(direction: "x")` allows the adjacency in both `+x` and `-x`.
Higher `weight` modules are picked more often during collapse.

**Tip:** the v1 op produces a single primitive per module (no rotation
handling). For visually richer assemblies, vary the module primitives
themselves (different cylinder radii, different panel sizes).

---

## 5. Productivity — scatter family

The scatter family removes hand-written `.translate([...])` chains for
N copies. Same op generalises across all 5 paradigms — rivets on a
panel, leaves on a branch, rocks on terrain, bumps on a creature,
decorations on dungeon cells.

### 5.1 Explicit point sets — `scatter`

`scatter(primitive: <ident>, points: <ident>)` emits one translated copy
of `primitive` per point. Points come from one of four generators:

| Generator | What it produces |
|---|---|
| `points_grid(extents: [W,H], rows, cols, plane?)` | Uniform 2D grid (`rows*cols` points). |
| `points_random(count, seed, extents: [W,H] or [W,H,D])` | Deterministic uniform random cloud. |
| `points_circle(count, radius, axis?)` | Evenly-spaced ring. |
| `points_combine([a, b, c])` | Concatenate multiple point-set bindings. |

**Example — three patterns on one panel** (full demo:
`examples/scatter_demo.lth`):

```lathe
let body = solid_panel(extents: [40cm, 30cm, 2cm])
op_trim_band(target: body, axis: "x", width: 2cm, depth: 5mm)

// 4x8 = 32 rivets via one declaration.
let rivet = solid_cylinder(radius: 3mm, height: 4mm, axis: "z")
      .translate([0cm, 0cm, 1cm])
let rivet_grid = points_grid(extents: [36cm, 26cm], rows: 4, cols: 8)
scatter(primitive: rivet, points: rivet_grid, jitter: 0.5mm)

// 12 deterministic random screws.
let screw = solid_cylinder(radius: 2mm, height: 6mm, axis: "z")
      .translate([0cm, 0cm, 1cm])
let screw_random = points_random(count: 12, seed: 7, extents: [10cm, 10cm])
scatter(primitive: screw, points: screw_random)

// Two concentric rings of bolts merged via points_combine.
let bolt = solid_cylinder(radius: 4mm, height: 5mm, axis: "z")
      .translate([0cm, 0cm, 1cm])
let ring_a = points_circle(count: 8, radius: 12cm, axis: "z")
let ring_b = points_circle(count: 4, radius: 5cm, axis: "z")
let bolt_points = points_combine([ring_a, ring_b])
scatter(primitive: bolt, points: bolt_points)
```

**`scatter(...)` arguments:**
- `primitive` (required) — identifier of a primitive (or SDF) let-binding.
- `points` (required) — identifier of a `point_set` binding.
- `jitter` (optional) — peak per-axis random offset; deterministic per call.
- `seam_group` (optional) — tag every emitted instance into a seam group
  so a downstream `fillet_edge` can bevel the cloud.

`scatter` itself does not auto-emit the template (it emits N instances,
not N+1) — if you want the template visible, anchor it via
`op_trim_band` or another op.

### 5.2 Surface-projected — `scatter_on_surface`

Same productivity multiplier, but points are sampled directly from the
surface of another primitive. Lets you say "rocks on terrain" or "rivets
on a curved panel" without computing the cloud by hand.

**Example** (full demo: `examples/scatter_on_surface_demo.lth`):

```lathe
mesh_program {
  let ground = terrain_heightfield(extents: [20m, 20m], resolution: 32,
                                   scale_z: 2m, seed: 5)
  terrain_biome(target: ground, biome: "rolling_hills",
                roughness: 0.3, peak_density: 0.1)

  // ~200 pebbles on the actual terrain surface (0.5 items/m² * 400 m²).
  let pebble = solid_cylinder(radius: 8cm, height: 5cm, axis: "y")
  scatter_on_surface(
    primitive: pebble,
    target: ground,
    density: 0.5,
    seed: 7,
    jitter: 5cm,
  )
}
```

**Arguments:**
- `primitive` — template primitive ident.
- `target` — primitive ident whose mesh defines the sampling surface.
- `density` — items per square metre. `count = int(density * area_m²)`,
  capped to prevent runaway scatter.
- `seed` (optional, default 0) — feeds both the surface sampler and per-instance jitter.
- `jitter` (optional, default 0) — per-axis uniform offset.
- `align_to_normal` (optional, default `false`) — align template's local
  +Z to the face normal at the sampled point.

**Generalises across all paradigms:** swap `target` for a
`vegetation_trunk` (leaves on branch), an `sdf_extract`'d creature
(bumps on skin), or a `wfc_modular` cell (decorations on walls).

---

## 6. Composing all paradigms

The capstone proof point is `examples/alien_grove_showcase.lth` — a
single `mesh_program{}` block exercising all 5 paradigms in ~30
functional lines:

```lathe
module demo.showcase

asset alien_grove : hard_surface_prop {
  intent { role = "alien grove with guardian and ruined dungeon"; asset_class = "hero" }
  build { shape {
    mode = generate; candidates = 1; seed = 7
    mesh_program {
      // ===== Terrain =====
      let ground = terrain_heightfield(extents: [30m, 30m], resolution: 48, scale_z: 4m, seed: 7)
      terrain_biome(target: ground, biome: "rolling_hills", roughness: 0.3, peak_density: 0.1)

      // ===== Vegetation =====
      let trunk_a = vegetation_trunk(height: 6m, base_radius: 30cm, taper: 0.4, segments: 6)
      vegetation_canopy(parent: trunk_a, branch_count: 8, leaf_density: 40,
                        leaf_size: 8cm, foliage_radius: 150cm)

      // ===== Hard-surface chest =====
      let chest_body = solid_panel(extents: [80cm, 50cm, 50cm]).translate([-3m, 0cm, 5m])
      op_fastener_grid(target: chest_body, face: "+y", rows: 1, cols: 4, spacing: 18cm,
                       fastener_radius: 15mm, fastener_height: 8mm)
      op_trim_band(target: chest_body, axis: "y", width: 4cm, depth: 5mm)

      // ===== Organic SDF guardian =====
      let body = sdf_capsule(half_height: 80cm, radius: 40cm)
      let arm_l = sdf_capsule(half_height: 60cm, radius: 12cm).translate([60cm, 0cm, 0cm])
      let arm_r = sdf_capsule(half_height: 60cm, radius: 12cm).translate([-60cm, 0cm, 0cm])
      let head = sdf_sphere(radius: 30cm).translate([0cm, 0cm, 100cm])
      let alien = sdf_smooth_union(targets: [body, arm_l, arm_r, head], k: 25cm)
      sdf_extract(target: alien, resolution: 48,
                  bounds_min: [-1500mm, -1500mm, -500mm], bounds_max: [1500mm, 1500mm, 2m])

      // ===== WFC modular dungeon =====
      let dungeon_floor = solid_panel(extents: [3m, 30cm, 3m])
      let dungeon_wall  = solid_panel(extents: [3m, 3m, 30cm])
      let mod_floor = wfc_module(name: "floor", primitive: dungeon_floor, weight: 0.7)
      let mod_wall  = wfc_module(name: "wall",  primitive: dungeon_wall,  weight: 0.3)
      let rule_ff   = wfc_rule(a: "floor", b: "floor", direction: "x")
      wfc_modular(canvas_size: [4, 1, 4], cell_size: 3m,
                  modules: [mod_floor, mod_wall], adjacency: [rule_ff], seed: 123)
    }
  } }
}
```

Run:

```bash
python -m lathe.cli quick examples/alien_grove_showcase.lth alien_grove \
    --out tmp_alien_grove.glb --no-cache
```

This is the proof: every paradigm composes with every other paradigm
because they all lower to the same `ShapePrimitive` records.

---

## 7. Velocity loop

Lathe ships a fast preview pipeline so authoring iteration stays under
60 seconds wall-clock.

**Cold preview (fastest, lowest quality):**

```bash
python -m lathe.cli quick <file.lth> <asset> \
    --out preview.glb \
    --candidates 1 --no-search --no-cache
```

- `--candidates 1` — overrides asset's `build.shape.candidates` to 1.
- `--no-search` — zeroes `space.select.best_of`, collapsing the candidate
  sweep to first-emitted.
- `--no-cache` — bypass the quick-preview cache (use after parser changes).

**Warm rebuild (subsequent runs):** content-hashed cache means warm
rebuilds with no source changes complete in <5s. Just drop `--no-cache`:

```bash
python -m lathe.cli quick <file.lth> <asset> --out preview.glb
```

**Cache management:**

```bash
# Clear every cached preview entry.
python -m lathe.cli quick <file.lth> <asset> --out preview.glb --clear-cache
```

**Optional flags:**
- `--render <path.png>` — write a turntable preview PNG (best-effort).
- `--runtime-config <file.json>` — wire a learned shape provider.
- `--shape-provider <id>` — override the shape provider adapter.

**Inspect the GLB programmatically:**

```python
import trimesh
scene = trimesh.load("preview.glb")
if hasattr(scene, "geometry"):
    for name, mesh in scene.geometry.items():
        print(name, mesh.bounds.tolist(), len(mesh.vertices))
else:
    print(scene.bounds.tolist(), len(scene.vertices))
```

**Full validated build** — `lathe build` runs the entire stack
(execution, rig, interfaces, physics, optimize, validate, package, repair)
and is what you run before shipping. Targets ~25 minutes on hero assets.

---

## 8. Op reference table

Comprehensive reference grouped by category.

### Solid primitives (return `ShapePrimitive`)

| Op | Required args | Optional |
|---|---|---|
| `box(extents)` | `extents: [W,H,D]` | — |
| `solid_panel(extents)` | `extents: [W,H,D]` | — |
| `solid_rail(length, profile)` | `length`, `profile` | `axis` (default `"x"`) |
| `solid_prism(extents)` | `extents: [W,H,D]` | — |
| `solid_cylinder(radius, height)` | `radius`, `height` | `axis` (default `"y"`) |
| `solid_rounded_box(extents, radius)` | `extents`, `radius` | — |

### Boolean + bevel

| Op | Args |
|---|---|
| `boolean(op, a, b)` | `op: union\|subtract\|intersect`, `a`, `b`; optional `seam_group` |
| `fillet_edge(target, edge_class, radius)` | `target`, `edge_class` (must match a `seam_group`), `radius`; optional `segments` (default 4) |

### Compound mechanical ops (mutate target)

| Op | Args |
|---|---|
| `op_fastener_grid` | `target`, `face`, `rows`, `cols`, `spacing`, `fastener_radius`, `fastener_height`; optional `seam_group` |
| `op_vent_slats` | `target`, `face`, `count`, `slot_width`, `slot_length`, `slot_depth`, `spacing`, `axis`; optional `seam_group` |
| `op_trim_band` | `target`, `axis`, `width`, `depth`; optional `offset`, `seam_group` |

### Vegetation

| Op | Args |
|---|---|
| `vegetation_trunk` | `height`, `base_radius`; optional `taper` (default 0.3), `segments` (default 6), `bend` (default 0.05) |
| `vegetation_canopy` | `parent`, `branch_count`, `leaf_density`, `leaf_size`, `foliage_radius`; optional `branch_pitch` (default 1.05) |

### Terrain

| Op | Args |
|---|---|
| `terrain_heightfield` | `extents: [W,H]`, `resolution` (≥8), `scale_z`, `seed`; optional `octaves` (default 5) |
| `terrain_biome` | `target`, `biome` (`"alpine"\|"rolling_hills"\|"rocky"`); optional `roughness` (default 0.5), `peak_density` (default 0.2) |

### SDF (return implicit form until extracted)

| Op | Args |
|---|---|
| `sdf_sphere` | `radius` |
| `sdf_capsule` | `half_height`, `radius` |
| `sdf_box` | `extents: [W,H,D]` |
| `sdf_smooth_union` | `targets: [<idents>]`, `k` |
| `sdf_extract` | `target`, `resolution`, `bounds_min: [x,y,z]`, `bounds_max: [x,y,z]` |

### WFC modular

| Op | Args |
|---|---|
| `wfc_module` | `name`, `primitive`, `weight` |
| `wfc_rule` | `a`, `b`, `direction`; optional `probability` |
| `wfc_modular` | `canvas_size: [nx,ny,nz]`, `cell_size`, `modules: [...]`, `adjacency: [...]`, `seed` |

### Scatter

| Op | Args |
|---|---|
| `scatter` | `primitive`, `points`; optional `jitter`, `seam_group` |
| `scatter_on_surface` | `primitive`, `target`, `density`; optional `seed`, `jitter`, `align_to_normal` |
| `points_grid` | `extents: [W,H]`, `rows`, `cols`; optional `plane` (default `"+z"`) |
| `points_random` | `count`, `seed`, `extents: [W,H]` or `[W,H,D]` |
| `points_circle` | `count`, `radius`; optional `axis` (default `"y"`) |
| `points_combine` | positional list of point-set idents |

### Method calls (chained on let-bindings)

| Method | Receiver | Args |
|---|---|---|
| `.translate([x, y, z])` | primitive or SDF binding | length-unit vector |

### Argument types

- **Length unit literals:** `10cm`, `4mm`, `2m`, `1.5m`, `-12cm`. Stored
  internally as cm.
- **Vectors:** `[10cm, 5cm, 0cm]` (3-element) or `[40m, 40m]` (2-element).
- **Identifiers:** bare names referring to a previous `let` binding.
- **Strings:** `"+z"`, `"alpine"`, `"floor"` — quoted.
- **Numbers:** `0.4`, `5`, `1.05` — unitless floats / ints.
- **Lists of identifiers:** `[trunk, leaves, head]`.
- **Booleans:** `true`, `false`.

---

## 9. Common patterns / idioms

### 9.1 "Mechanical mounting plate" — body + fasteners + trim

```lathe
let body = solid_panel(extents: [40cm, 30cm, 2cm])
op_fastener_grid(target: body, face: "+z", rows: 2, cols: 6,
                 spacing: 5cm, fastener_radius: 3mm, fastener_height: 4mm)
op_trim_band(target: body, axis: "y", width: 1cm, depth: 2mm)
```

### 9.2 "Tree on terrain" — terrain + offset trunk

```lathe
let ground = terrain_heightfield(extents: [20m, 20m], resolution: 32,
                                 scale_z: 2m, seed: 1)
terrain_biome(target: ground, biome: "rolling_hills", roughness: 0.3, peak_density: 0.1)

let trunk = vegetation_trunk(height: 5m, base_radius: 25cm, taper: 0.4, segments: 6)
vegetation_canopy(parent: trunk, branch_count: 8, leaf_density: 40,
                  leaf_size: 6cm, foliage_radius: 120cm)
```

### 9.3 "Forest floor" — terrain + scatter rocks (surface-projected)

```lathe
let ground = terrain_heightfield(extents: [20m, 20m], resolution: 32,
                                 scale_z: 2m, seed: 5)
terrain_biome(target: ground, biome: "rolling_hills", roughness: 0.3, peak_density: 0.1)

let pebble = solid_cylinder(radius: 8cm, height: 5cm, axis: "y")
scatter_on_surface(primitive: pebble, target: ground, density: 0.5, seed: 7, jitter: 5cm)
```

### 9.4 "Dungeon room" — WFC + decorations

```lathe
let floor = solid_panel(extents: [3m, 30cm, 3m])
let wall  = solid_panel(extents: [3m, 3m, 30cm])
let mod_floor = wfc_module(name: "floor", primitive: floor, weight: 0.7)
let mod_wall  = wfc_module(name: "wall",  primitive: wall,  weight: 0.3)
let rule_ff = wfc_rule(a: "floor", b: "floor", direction: "x")
wfc_modular(canvas_size: [4, 1, 4], cell_size: 3m,
            modules: [mod_floor, mod_wall], adjacency: [rule_ff], seed: 123)
```

### 9.5 "Alien creature" — smooth-union of capsules + sphere head

```lathe
let body  = sdf_capsule(half_height: 50cm, radius: 30cm)
let arm_a = sdf_capsule(half_height: 40cm, radius: 10cm).translate([50cm, 0cm, 0cm])
let arm_b = sdf_capsule(half_height: 40cm, radius: 10cm).translate([-50cm, 0cm, 0cm])
let head  = sdf_sphere(radius: 20cm).translate([0cm, 60cm, 0cm])
let alien = sdf_smooth_union(targets: [body, arm_a, arm_b, head], k: 15cm)
sdf_extract(target: alien, resolution: 96,
            bounds_min: [-1.2m, -1.2m, -1.2m], bounds_max: [1.2m, 1.2m, 1.2m])
```

### 9.6 "Hero asset" — boolean + bevel + scattered details

```lathe
let body = box(extents: [10cm, 10cm, 10cm])
let cutout = box(extents: [8cm, 8cm, 4cm]).translate([0cm, 0cm, 4cm])
let result = boolean(op: subtract, a: body, b: cutout, seam_group: "lip")
fillet_edge(target: result, edge_class: "lip", radius: 1cm, segments: 4)

let rivet = solid_cylinder(radius: 3mm, height: 3mm, axis: "z").translate([0cm, 0cm, 5cm])
let pts = points_grid(extents: [6cm, 6cm], rows: 3, cols: 3)
scatter(primitive: rivet, points: pts)
```

### 9.7 "Hard-surface mounting rail with gusset"

```lathe
let body = solid_panel(extents: [40cm, 30cm, 2cm])
let rail = solid_rail(length: 38cm, profile: 8mm, axis: "x")
      .translate([0cm, 12cm, 1cm])
let body_plus_rail = boolean(op: union, a: body, b: rail, seam_group: "rail_lip")

let gusset = solid_prism(extents: [3cm, 3cm, 1cm]).translate([18cm, 13cm, 1cm])
let body_plus_gusset = boolean(op: union, a: body_plus_rail, b: gusset, seam_group: "gusset_lip")
```

---

## Where to go next

- `docs/imagination_to_life_demos.md` — the demo catalog (one paragraph per demo).
- `docs/cli_reference.md` — full CLI reference (build, plan, materialize, doctor).
- `docs/language_reference.md` — language spec covering the surface beyond `mesh_program`.
- `docs/error_codes.md` — what diagnostic codes mean.
- `examples/*.lth` — every demo file in this guide is a runnable example.
