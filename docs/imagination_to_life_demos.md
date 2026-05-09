# Imagination-to-Life demos

Lathe ships one kernel covering five procedural-content paradigms. Each demo
below is a self-contained `.lth` source that exercises one paradigm in
isolation; the **alien_grove_showcase** at the bottom proves all five coexist
inside a single `mesh_program{}` block.

Run any of them with:

```bash
python -m lathe.cli check examples/<demo>.lth
python -m lathe.cli quick examples/<demo>.lth <asset_name> --out tmp.glb --no-cache
```

`<asset_name>` matches the `asset <name> :` line in each file.

## 1. Hard-surface bevel — `examples/bevel_demo.lth`

Source-level boolean → bevel(seam_group) chain. The canonical hard-surface
idiom: subtract a cutout, fillet the resulting edge class.

```lathe
mesh_program {
  let body = box(extents: [10cm, 10cm, 10cm])
  let cutout = box(extents: [8cm, 8cm, 4cm]).translate([0cm, 0cm, 4cm])
  let result = boolean(op: subtract, a: body, b: cutout, seam_group: "lip")
  fillet_edge(target: result, edge_class: "lip", radius: 1cm, segments: 4)
}
```

Proves: deterministic CAD-style boolean + cutback bevel pipeline.

## 2. Hard-surface mechanical — `examples/mech_prop_demo.lth`

Eight `shape_ir_v2` first-wave ops (`solid_panel`, `solid_rounded_box`,
`solid_cylinder`, `solid_rail`, `solid_prism`, `op_vent_slats`,
`op_fastener_grid`, `op_trim_band`) composed into a single mechanical panel.

Proves: the full V1.4 §5.7 op vocabulary is authorable from `.lth` source.

## 3. Vegetation — `examples/oak_tree_demo.lth`

```lathe
mesh_program {
  let trunk = vegetation_trunk(height: 4m, base_radius: 25cm, taper: 0.4, segments: 6)
  vegetation_canopy(parent: trunk, branch_count: 10, leaf_density: 60,
                    leaf_size: 6cm, foliage_radius: 140cm)
}
```

Proves: same kernel that builds chests builds trees — `vegetation_trunk`
lowers to a tapered lofted solid, `vegetation_canopy` to branch cylinders +
leaf spheres. No vegetation-specific code path through topology/UV/package.

## 4. Terrain — `examples/rocky_hill_demo.lth`

```lathe
mesh_program {
  let ground = terrain_heightfield(extents: [40m, 40m], resolution: 64,
                                   scale_z: 8m, seed: 1234)
  terrain_biome(target: ground, biome: "alpine",
                roughness: 0.6, peak_density: 0.3)
}
```

Proves: heightfield terrain via the stable `ShapePrimitive("heightfield")`
record consumed by `exact_solids._heightfield_mesh`. Biomes
(`alpine`/`rolling_hills`/`rocky`) are mutator passes, not separate kernels.

## 5. Organic SDF creature — `examples/alien_blob_demo.lth`

```lathe
mesh_program {
  let body = sdf_capsule(half_height: 50cm, radius: 30cm)
  let arm_a = sdf_capsule(half_height: 40cm, radius: 10cm).translate([50cm, 0cm, 0cm])
  let arm_b = sdf_capsule(half_height: 40cm, radius: 10cm).translate([-50cm, 0cm, 0cm])
  let head = sdf_sphere(radius: 20cm).translate([0cm, 60cm, 0cm])
  let blended = sdf_smooth_union(targets: [body, arm_a, arm_b, head], k: 15cm)
  sdf_extract(target: blended, resolution: 96,
              bounds_min: [-1.2m, -1.2m, -1.2m],
              bounds_max: [1.2m, 1.2m, 1.2m])
}
```

Proves: implicit-surface organic primitives via the existing F-Rep kernel at
`lathe/f_rep/`. `sdf_extract` runs marching cubes inside the bounds box and
emits a single `ShapePrimitive("sdf_mesh")` consumed by the same exact-solid
pipeline as the box+cylinder hard-surface ops.

## 6. WFC modular composition — `examples/dungeon_corridor_demo.lth`

```lathe
mesh_program {
  let floor = solid_panel(extents: [3m, 30cm, 3m])
  let wall = solid_panel(extents: [3m, 3m, 30cm])
  let pillar = solid_cylinder(radius: 30cm, height: 3m, axis: "y")

  let mod_floor  = wfc_module(name: "floor",  primitive: floor,  weight: 0.7)
  let mod_wall   = wfc_module(name: "wall",   primitive: wall,   weight: 0.2)
  let mod_pillar = wfc_module(name: "pillar", primitive: pillar, weight: 0.1)

  let rule_ff_x = wfc_rule(a: "floor", b: "floor", direction: "x")
  let rule_ff_z = wfc_rule(a: "floor", b: "floor", direction: "z")

  wfc_modular(canvas_size: [10, 1, 10], cell_size: 3m,
              modules: [mod_floor, mod_wall, mod_pillar],
              adjacency: [rule_ff_x, rule_ff_z], seed: 42)
}
```

Proves: Wave Function Collapse modular assembly via the existing
`lathe.wfc` solver. `wfc_module` wraps any primitive (regardless of which
paradigm built it), `wfc_rule` declares allowable adjacencies, `wfc_modular`
runs the solver and emits one translated copy per cell.

## CAPSTONE — `examples/alien_grove_showcase.lth`

The single `.lth` source that combines **all five paradigms** in one
`mesh_program{}` block:

- 30m × 30m rolling-hills heightfield ground
- 2 procedural trees scattered across the grove
- 1 mechanical chest with rivet grid + trim band
- 1 alien guardian — smooth-blended SDF capsules + sphere head
- 1 4×4 WFC modular dungeon corridor

Same kernel. One shape stage call. One topology pipeline. One GLB output.

```bash
python -m lathe.cli quick examples/alien_grove_showcase.lth alien_grove \
    --out tmp_alien_grove.glb --no-cache
```

This is the definitive proof of Lathe-as-imagination-layer: an author writes
~30 functional lines of declarative source and gets a complete scene. Every
paradigm is composable with every other paradigm because they all lower to
the same `ShapePrimitive` / `ShapeIR` records that the deterministic
downstream pipeline already understands.
