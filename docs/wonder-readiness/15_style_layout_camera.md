# Style, Layout, Camera

Phase 18-21 groundwork adds JSON helpers for style packs, deterministic layout
planning, instance reuse grouping, and camera/light readiness. The additive
`.lth` language surface now includes top-level `style_pack` declarations,
scene-local `style_pack = <id>` references from `style` blocks, and scene-local
`camera_intent` / `lighting_plan` declarations that lower into the existing
camera and light IR. Scene Graph v1 also accepts object-level
`surface_overrides` metadata for per-instance surface variation.

## Style Packs

`schema/style_pack.schema.json` defines `lathe.style_pack.v1`.

`lathe.scene.style.extract_style_pack(scene_graph)` builds a deterministic pack
from a Scene Graph `style_bible`, material definitions, lights, form terms, and
the default reuse policy. `validate_style_pack_payload(style_pack)` runs the
schema plus semantic checks for palette references and fingerprint freshness.

`apply_style_pack(scene_graph, style_pack)` returns a copy of the Scene Graph
with the pack's style bible and any missing pack materials merged in. It does
not mutate the input scene.

`validate_scene_style(scene_graph, style_pack)` checks that scene style terms,
material bindings, and palette references are covered by the pack.

Lathe also ships curated built-in packs for early Wonder scenes:

- `dead_god_observatory`
- `dark_fantasy_ruin`
- `cozy_fantasy_workshop`
- `sci_fi_industrial`
- `roblox_lowpoly_cute`
- `roblox_horror_lowpoly`

They are available through `lathe.scene.style.get_builtin_style_pack(id)` and
the CLI:

```bash
python -m lathe.cli scene style-pack --builtin dead_god_observatory --out style_pack.json
```

Built-in packs use `source.kind: curated`, include palette roles such as
primary, secondary, accent, and emissive, and are fingerprinted the same way as
packs extracted from Scene Graphs.

The `.lth` source surface accepts lightweight top-level declarations:

```lathe
style_pack dead_god_observatory {
  display_name = "Dead God Observatory"
  source.kind = curated
  palette.primary = bone_ivory
}

scene alchemist_observatory {
  style style_scene {
    style_pack = dead_god_observatory
  }
  region region_central_chamber: interior {}
}
```

The checker accepts references to in-file `style_pack` declarations and curated
built-ins, and rejects unknown or non-identifier style-pack references. Full
`lathe.style_pack.v1` JSON remains the durable contract for material PBR data,
lighting presets, fingerprints, and reuse policy.
`style_pack ... uses ...` inheritance is not part of this minimal source slice;
use the JSON Style Pack contract for full reuse policy authoring.

## Instance Reuse

`lathe.scene.layout.plan_instance_reuse(scene_graph, style_pack=None)` groups
objects by deterministic asset signatures. By default, source asset identity,
variant, and material bindings define the shared asset; name, role, region,
transform, semantic tags, state, surface overrides, affordances, and provenance
are treated as instance overrides.

This means repeated objects can share one asset even when their transform or
state, surface finish, or interactions differ. A style pack may provide a
stricter `reuse_policy`; the helper only accepts known Scene Graph object
fields.

Proxy GLB exports write this reuse metadata into object `extras` and the
export object index under `instancing`. Blender exports pass the same metadata
through the sandbox helper and write object custom properties such as
`lathe_reuse_group_id`, `lathe_asset_signature`,
`lathe_shared_asset`, and `lathe_instance_fingerprint`.

## Layout Plans

`schema/layout_plan.schema.json` defines `lathe.layout_plan.v1`.

`lathe.scene.layout.plan_layout(scene_graph, style_pack=None)` returns:

- normalized room layout metadata
- region bounds with min/max coordinates
- object placements with footprints and inside-region status
- main-path waypoints and blockers
- instance reuse groups
- footprint intersections
- modular wall segment constraints when `layout.modular_walls` is enabled
- deterministic diagnostics

`layout.modular_walls` is a JSON-first Scene Graph constraint block. It can
target region IDs, perimeter sides, module length, snap grid, height, and
thickness. The Layout Plan emits deterministic `wall_segments` on region
perimeter center lines and warns when generated segments are not aligned to the
requested snap grid.

The current layout helper is a validator/planner. It does not solve or move
objects, generate meshes for wall segments, repair intersections, or run
physics.

## Camera And Lighting

`lathe.scene.camera_lighting.plan_camera_lighting(scene_graph, layout_plan=None)`
returns camera records, light records, and camera-to-light links. It resolves
targets from a layout plan when supplied, otherwise from Scene Graph transforms
and region bounds.

The helper classifies lights as key, fill, practical, or accent, computes camera
view vectors and target distances, and reports missing targets, missing camera
positions, out-of-range camera FOV, and non-positive light intensity.

The `.lth` source surface accepts Wonder-facing aliases for camera and light
authoring:

```lathe
scene alchemist_observatory {
  region region_central_chamber: interior {}
  object obj_astrolabe_table: hero_prop from ornate_table {
    region = region_central_chamber
  }
  camera_intent camera_reveal: cinematic_wide {
    target = obj_astrolabe_table
  }
  lighting_plan light_moonbeam: moonbeam {
    target = obj_astrolabe_table
  }
}
```

`camera_intent` normalizes to `scene_camera`, and `lighting_plan` normalizes to
`scene_light`. Older `camera` and `light` blocks remain compatibility aliases
for the same normalized IR.

The deterministic proxy renderer can now consume camera records to write PNG
evidence, including a generated topdown debug camera when the authored Scene
Graph has no topdown camera. There is still no Blender renderer, exposure
solver, shadow system, or camera path animation in this phase. The output is
readiness metadata for downstream final render/export work.
