# Scene Source Language Design

Status: Phase 6A design plus later implementation notes through Phase 23.

This page defines the first proposed `.lth` scene source surface for Project
Wonder. The original Phase 6A entry was design-only; later phases have started
landing additive parser, grammar, normalizer, checker, formatter, and source
bridge support for the constructs documented below.

## Decision

Minimal additive `.lth` scene syntax is experimental for v0.3. It must preserve
v0.1 asset source compatibility: existing `profile`, `contract`, `critic`,
`asset`, `variant`, and build-stage syntax keep their current meaning, parser
behavior, normalized AST shape, and asset build behavior.

Scene syntax is not a replacement for the Scene Graph JSON contract. For v0.3,
the Scene Graph remains the durable truth model and source syntax is a human and
model authoring surface that lowers into `lathe.scene_graph.v1`.

Project Wonder owns chat, user, product, account, gallery, payment, project
memory, cloud orchestration, and prompt-routing concerns. Lathe owns public
contracts, compiler/runtime behavior, validation, render/export artifacts,
package manifests, and diagnostic reports.

Related ADR: [ADR 0010](../adr/0010-experimental-scene-source-language.md).

## Compatibility Boundary

The v0.3 scene surface is additive:

- `scene` is introduced only as a top-level declaration in scene-aware source.
- `region`, `object`, `relationship`, `camera`, `light`, `style`, and `export`
  are scene-local constructs.
- Asset declarations do not gain scene semantics.
- Asset-only `.lth` files that are valid today must parse, normalize, check,
  plan, and build the same way after scene syntax lands.
- Scene-aware tooling may require an explicit scene entry point, but the stable
  v0.1 asset build path must not depend on Project Wonder product state.

## Minimum Viable Syntax

The first scene surface should stay close to existing Lathe source: named
declarations, brace blocks, path assignments, identifier references, string
literals, numbers, booleans, and lists.

```text
scene <scene_id> {
  version = <integer>
  brief = <brief_id>
  prompt = "<source prompt>"

  style <style_ref> {
    mood = [<tag>, ...]
    palette = ["<color or palette term>", ...]
    materials = ["<material term>", ...]
    forms = ["<form term>", ...]
    lighting = ["<lighting term>", ...]
    avoid = ["<negative style term>", ...]
  }

  region <region_id>: <region_type> {
    name = "<display name>"
    purpose = "<scene purpose>"
    mood = "<local mood>"
    bounds.center = [x, y, z]
    bounds.size = [x, y, z]
    semantic_tags = [<tag>, ...]
  }

  object <object_id>: <scene_role> from <lathe_asset> {
    name = "<display name>"
    region = <region_id>
    source_family = <family_id>
    source_kit = <kit_id>
    variant = <variant_id>
    transform.position = [x, y, z]
    transform.rotation = [x, y, z]
    transform.scale = [x, y, z]
    material_bindings.<slot> = <material_id>
    semantic_tags = [<tag>, ...]
    gameplay {
      interactable = <boolean>
      collision = <collision_mode>
      pivot = <pivot_mode>
      tags = [<tag>, ...]
      affordances.<affordance_id>.action = <action_id>
      affordances.<affordance_id>.reveals = <scene_ref>
      affordances.<affordance_id>.requires = <condition_id>
    }
    state.<name> = <string | number | boolean>
  }

  relationship <relationship_id>: <relationship_type> {
    from = <scene_ref>
    to = <scene_ref>
    description = "<why the relationship matters>"
  }

  camera <camera_id>: <framing> {
    target = <scene_ref>
    purpose = "<camera purpose>"
    transform.position = [x, y, z]
    transform.rotation = [x, y, z]
    transform.scale = [x, y, z]
    fov_degrees = <number>
  }

  light <light_id>: <light_type> {
    target = <scene_ref>
    color = "<color or palette term>"
    intensity = <number>
    purpose = "<lighting purpose>"
  }

  export <export_target> {
    format = <format_id>
    path = "<relative artifact path>"
  }
}
```

Required identifiers keep the Scene Graph prefixes:

- `region_...`
- `obj_...`
- `rel_...`
- `camera_...`
- `light_...`
- `mat_...`

The style reference name is a source label used by authoring tools and trace
metadata. The expanded style fields populate the Scene Graph `style_bible`
object; the style reference label is not itself a Scene Graph v1 field.

## Construct Mapping

| Source construct | Scene Graph fields |
|---|---|
| `scene <scene_id>` | `scene_id`; child declarations populate `regions`, `objects`, `relationships`, `lights`, `cameras`, and `exports`; `schema_version` is emitted as `lathe.scene_graph.v1`. |
| `scene.version` | `version`. |
| `scene.brief` | `brief_id`. |
| `scene.prompt` | `prompt`. |
| `style <style_ref> { ... }` | `style_bible.mood`, `style_bible.palette`, `style_bible.materials`, `style_bible.forms`, `style_bible.lighting`, and optional `style_bible.avoid`. |
| `region <region_id>: <region_type>` | One `regions[]` entry with `region_id` and `type`. |
| `region.name` | `regions[].name`. |
| `region.purpose` | `regions[].purpose`. |
| `region.mood` | `regions[].mood`. |
| `region.bounds.center`, `region.bounds.size` | `regions[].bounds.center` and `regions[].bounds.size`. |
| `region.semantic_tags` | `regions[].semantic_tags`. |
| `object <object_id>: <scene_role> from <lathe_asset>` | One `objects[]` entry with `object_id`, `role`, and `lathe_asset`. |
| `object.name` | `objects[].name`. |
| `object.region` | `objects[].region`. |
| `object.source_family`, `object.source_kit`, `object.variant` | `objects[].source_family`, `objects[].source_kit`, and `objects[].variant`. |
| `object.transform.position`, `object.transform.rotation`, `object.transform.scale` | `objects[].transform.position`, `objects[].transform.rotation`, and `objects[].transform.scale`. |
| `object.material_bindings.<slot>` | One `objects[].material_bindings[]` item with `slot` and `material`. |
| `object.semantic_tags` | `objects[].semantic_tags`. |
| `object.gameplay { ... }` | Normalized scene-object `values.gameplay`; generated source also previews Scene Graph `objects[].affordances[]` as `gameplay.affordances.<id>.*`. |
| `object.state.<name>` | `objects[].state.<name>`. |
| `relationship <relationship_id>: <relationship_type>` | One `relationships[]` entry with `relationship_id` and `type`. |
| `relationship.from`, `relationship.to` | `relationships[].from` and `relationships[].to`. |
| `relationship.description` | `relationships[].description`. |
| `camera <camera_id>: <framing>` | One `cameras[]` entry with `camera_id` and `framing`. |
| `camera.target` | `cameras[].target`. |
| `camera.purpose` | `cameras[].purpose`. |
| `camera.transform.*` | `cameras[].transform.*`. |
| `camera.fov_degrees` | `cameras[].fov_degrees`. |
| `light <light_id>: <light_type>` | One `lights[]` entry with `light_id` and `type`. |
| `light.target` | `lights[].target`. |
| `light.color` | `lights[].color`. |
| `light.intensity` | `lights[].intensity`. |
| `light.purpose` | `lights[].purpose`. |
| `export <export_target>` | One `exports[]` entry with `target`. |
| `export.format` | `exports[].format`. |
| `export.path` | `exports[].path`. |

## JSON And Metadata Only In v0.3

These Scene Graph fields stay out of first-pass scene source syntax:

- `materials[]` definitions and `materials[].pbr`; scene source may bind to
  `mat_...` IDs, while material definition remains JSON/style metadata.
- `layout.main_path`, `layout.focal_point`, `layout.density`,
  `layout.avoid_intersections`, and `layout.modular_walls`; region bounds plus
  JSON-first modular wall constraints are enough for the first source surface.
- `objects[].provenance`; provenance is recorded by JSON contracts, package
  manifests, and reports.
- `exports[].metadata`; export metadata is produced by export planning and
  package/report layers.
- `build_artifacts[]`; these are runtime outputs, not authoring declarations.
- `memory_events[]`; world memory is owned by the memory contract and package
  history flow.

## Deferred Constructs

These constructs are outside the first scene syntax implementation:

- `scene_variant` declarations and branch/merge source syntax.
- Standalone `lathe.game_readiness.v1` payload source syntax; object-local
  `gameplay { ... }` blocks cover authoring hints, while the richer payload
  remains a JSON contract.
- Scene-side sockets, snap points, snap groups, and arbitrary modular alignment
  rules beyond the JSON-first `layout.modular_walls` constraint block.
- Provenance source syntax for provider, license, commercial-use, and user-input
  rights metadata.
- Advanced layout constraints, including relative placement solvers, path
  clearance solvers, density optimization, and intersection repair rules.

Existing asset-level interfaces, pivots, sockets, and package rules remain part
of asset source. They are not replaced by scene source.

## Examples

These examples show the proposed source shape. They are complete scene syntax
examples for Phase 6A, not parser fixtures.

### Example 1: Alchemist Observatory

```text
module wonder.examples.alchemist_observatory

scene alchemist_observatory {
  version = 1
  brief = alchemist_observatory
  prompt = "A forgotten alchemist observatory inside the ribcage of a dead god."

  style alchemist_dark_ritual {
    mood = [sacred, eerie, antique]
    palette = ["bone ivory", "oxidized copper", "black glass", "candle gold", "lunar blue"]
    materials = ["bone stone", "oxidized brass", "obsidian glass", "cracked enamel", "wax"]
    forms = ["ribbed arches", "circular instruments", "thin spires", "constellation engraving"]
    lighting = ["cold moonbeam", "warm candle clusters", "subtle dust haze"]
    avoid = ["modern electronics", "clean sci-fi panels"]
  }

  region region_central_chamber: interior {
    name = "Central Chamber"
    purpose = "Main reveal space for the observatory."
    mood = "sacred and abandoned"
    bounds.center = [0, 0, 2.2]
    bounds.size = [12, 8, 4.4]
    semantic_tags = [observatory, ritual, bone_architecture]
  }

  region region_entry_threshold: threshold {
    name = "Entry Threshold"
    purpose = "Approach path that frames the central table."
    mood = "quiet and dust-filled"
    bounds.center = [0, -4.2, 1.5]
    bounds.size = [3, 1.4, 3]
    semantic_tags = [entry, framing]
  }

  region region_sealed_archive: threshold {
    name = "Sealed Archive Door"
    purpose = "Unopened expansion hook behind the observatory."
    mood = "forbidden and quiet"
    bounds.center = [4.8, 1.5, 1.7]
    bounds.size = [1.6, 1, 3.4]
    semantic_tags = [sealed, archive, expansion]
  }

  object obj_astrolabe_table_001: hero_prop from astrolabe_table {
    name = "Central Astrolabe Table"
    region = region_central_chamber
    source_family = ornate_mechanical_table
    transform.position = [0, 0, 0.75]
    transform.rotation = [0, 0, 0]
    transform.scale = [1.4, 1.4, 1]
    material_bindings.metal = mat_oxidized_brass
    material_bindings.lens = mat_black_glass
    semantic_tags = [astronomy, ritual, interactive]
    state.powered = true
    state.secret_compartment = "unopened"
  }

  object obj_rib_arches_001: architecture from rib_arch_ring {
    name = "Rib Arch Ring"
    region = region_central_chamber
    source_kit = bone_architecture
    transform.position = [0, 0, 2]
    transform.rotation = [0, 0, 0]
    transform.scale = [1, 1, 1]
    material_bindings.bone = mat_bone_ivory
    semantic_tags = [ribcage, architecture, shelter]
    state.load_bearing = true
  }

  object obj_archive_door_001: interactive from sealed_archive_door {
    name = "Sealed Archive Door"
    region = region_sealed_archive
    source_family = mechanical_door
    transform.position = [4.8, 1.5, 1.7]
    transform.rotation = [0, 0, -90]
    transform.scale = [1, 1, 1]
    material_bindings.frame = mat_oxidized_brass
    material_bindings.panel = mat_bone_ivory
    semantic_tags = [sealed, archive, mystery]
    state.locked = true
    state.requires = "star_lens_alignment"
  }

  relationship rel_lens_points_to_archive: points_toward {
    from = obj_astrolabe_table_001
    to = obj_archive_door_001
    description = "The table alignment suggests the archive door is part of the same mechanism."
  }

  light light_moonbeam_001: moonbeam {
    target = obj_astrolabe_table_001
    color = "lunar blue"
    intensity = 0.82
    purpose = "Cold key light across the hero table."
  }

  camera camera_reveal: cinematic_wide {
    target = obj_astrolabe_table_001
    purpose = "First impression of chamber scale, rib architecture, and focal object."
    transform.position = [-5.2, -5.6, 2.4]
    transform.rotation = [66, 0, -40]
    transform.scale = [1, 1, 1]
    fov_degrees = 48
  }

  export scene_graph {
    format = json
    path = "scene_graph.json"
  }

  export glb {
    format = glb
    path = "dist/exports/alchemist_observatory.glb"
  }
}
```

### Example 2: Roblox Shop Interior

```text
module wonder.examples.roblox_shop_interior

scene roblox_shop_interior {
  version = 1
  brief = roblox_shop_interior
  prompt = "A compact low-poly potion shop with readable counters and a glowing display shelf."

  style roblox_cozy_lowpoly {
    mood = [cozy, playful, readable]
    palette = ["leaf green", "warm plank", "amber glow", "painted violet"]
    materials = ["painted wood", "soft plastic", "warm glass"]
    forms = ["chunky shelves", "wide counters", "simple bottle silhouettes"]
    lighting = ["warm practicals", "soft doorway fill"]
    avoid = ["thin fragile trim", "photoreal clutter"]
  }

  region region_sales_floor: interior {
    name = "Sales Floor"
    purpose = "Readable player-facing shop area."
    mood = "welcoming and bright"
    bounds.center = [0, 0, 2]
    bounds.size = [10, 8, 4]
    semantic_tags = [shop, lowpoly, player_space]
  }

  region region_display_wall: interior {
    name = "Display Wall"
    purpose = "Back wall with products and identity props."
    mood = "warm and magical"
    bounds.center = [0, 3.2, 2]
    bounds.size = [8, 1.2, 4]
    semantic_tags = [display, bottles, focal_wall]
  }

  object obj_shop_counter_001: architecture from lowpoly_shop_counter {
    name = "Potion Counter"
    region = region_sales_floor
    source_kit = roblox_shop_kit
    transform.position = [0, -1.8, 0.65]
    transform.rotation = [0, 0, 0]
    transform.scale = [1, 1, 1]
    material_bindings.body = mat_warm_plank
    semantic_tags = [counter, service, readable]
    state.checkout_side = "front"
  }

  object obj_display_shelf_001: dressing_prop from potion_display_shelf {
    name = "Glowing Display Shelf"
    region = region_display_wall
    source_kit = roblox_shop_kit
    transform.position = [0, 3.1, 1.5]
    transform.rotation = [0, 0, 0]
    transform.scale = [1.2, 0.8, 1]
    material_bindings.frame = mat_painted_violet
    material_bindings.bottles = mat_amber_glow
    semantic_tags = [display, potions, identity]
    state.bottle_count = 9
  }

  object obj_door_mat_001: navigation from welcome_mat {
    name = "Welcome Mat"
    region = region_sales_floor
    source_family = flat_decor_props
    transform.position = [0, -3.6, 0.03]
    transform.rotation = [0, 0, 0]
    transform.scale = [1.5, 0.8, 1]
    material_bindings.surface = mat_leaf_green
    semantic_tags = [entry, navigation, scale_cue]
    state.walkable = true
  }

  relationship rel_counter_faces_entry: points_toward {
    from = obj_shop_counter_001
    to = obj_door_mat_001
    description = "The counter is oriented toward the player entry."
  }

  relationship rel_shelf_frames_counter: framed_by {
    from = obj_display_shelf_001
    to = obj_shop_counter_001
    description = "The shelf gives the counter a strong shop identity backdrop."
  }

  light light_shop_warm_001: area {
    target = obj_shop_counter_001
    color = "amber glow"
    intensity = 0.55
    purpose = "Soft readable shop lighting."
  }

  camera camera_reveal: cinematic_wide {
    target = obj_shop_counter_001
    purpose = "Show the full shop path from entry to counter."
    transform.position = [-4, -5, 2.6]
    transform.rotation = [62, 0, -36]
    transform.scale = [1, 1, 1]
    fov_degrees = 55
  }

  export scene_package {
    format = lathepkg
    path = "dist/roblox_shop_interior.lathepkg"
  }

  export roblox_manifest {
    format = json
    path = "dist/exports/roblox_manifest.json"
  }
}
```

### Example 3: Desert Oracle Shrine

```text
module wonder.examples.desert_oracle_shrine

scene desert_oracle_shrine {
  version = 1
  brief = desert_oracle_shrine
  prompt = "A small desert oracle shrine at dusk with a cracked mirror altar and wind-worn stones."

  style desert_oracle_dusk {
    mood = [quiet, ancient, luminous]
    palette = ["sunset rose", "sandstone", "deep teal shadow", "mirror silver"]
    materials = ["weathered stone", "polished mirror", "woven cloth"]
    forms = ["low arch", "stepped plinth", "round mirror", "wind-carved markers"]
    lighting = ["low sunset key", "cool reflected fill"]
    avoid = ["large city skyline", "modern signage"]
  }

  region region_shrine_floor: exterior {
    name = "Shrine Floor"
    purpose = "Small playable courtyard around the oracle altar."
    mood = "still and windswept"
    bounds.center = [0, 0, 0.2]
    bounds.size = [9, 7, 0.4]
    semantic_tags = [shrine, courtyard, desert]
  }

  region region_oracle_niche: threshold {
    name = "Oracle Niche"
    purpose = "Focal threshold where the mirror altar sits."
    mood = "luminous and expectant"
    bounds.center = [0, 2.8, 1.4]
    bounds.size = [4, 1.2, 2.8]
    semantic_tags = [oracle, altar, focal]
  }

  object obj_mirror_altar_001: hero_prop from cracked_oracle_mirror {
    name = "Cracked Oracle Mirror"
    region = region_oracle_niche
    source_family = shrine_relics
    transform.position = [0, 2.7, 1.1]
    transform.rotation = [0, 0, 0]
    transform.scale = [1, 1, 1]
    material_bindings.frame = mat_weathered_stone
    material_bindings.mirror = mat_mirror_silver
    semantic_tags = [oracle, mirror, focal_object]
    state.cracked = true
    state.reflects_sunset = true
  }

  object obj_marker_ring_001: environment_structure from wind_marker_ring {
    name = "Wind Marker Ring"
    region = region_shrine_floor
    source_kit = desert_shrine_kit
    transform.position = [0, 0, 0.35]
    transform.rotation = [0, 0, 0]
    transform.scale = [1.1, 1.1, 1]
    material_bindings.stone = mat_sandstone
    semantic_tags = [stones, boundary, path]
    state.stones_missing = 2
  }

  object obj_cloth_banner_001: dressing_prop from faded_oracle_banner {
    name = "Faded Oracle Banner"
    region = region_oracle_niche
    source_family = cloth_dressing
    transform.position = [-1.4, 2.9, 1.8]
    transform.rotation = [0, 0, 6]
    transform.scale = [0.8, 0.8, 0.8]
    material_bindings.cloth = mat_sunset_rose
    semantic_tags = [banner, weathered, color_accent]
    state.wind_torn = true
  }

  relationship rel_markers_contain_altar: contains {
    from = obj_marker_ring_001
    to = obj_mirror_altar_001
    description = "The marker ring defines the ritual area around the altar."
  }

  relationship rel_banner_frames_mirror: framed_by {
    from = obj_cloth_banner_001
    to = obj_mirror_altar_001
    description = "The banner adds color and scale around the mirror."
  }

  light light_sunset_key_001: directional {
    target = obj_mirror_altar_001
    color = "sunset rose"
    intensity = 0.7
    purpose = "Low warm key light reflected by the mirror."
  }

  camera camera_reveal: cinematic_wide {
    target = obj_mirror_altar_001
    purpose = "Reveal the shrine floor, marker ring, and oracle mirror."
    transform.position = [-4.5, -4.2, 2.1]
    transform.rotation = [60, 0, -42]
    transform.scale = [1, 1, 1]
    fov_degrees = 50
  }

  export scene_graph {
    format = json
    path = "scene_graph.json"
  }

  export glb {
    format = glb
    path = "dist/exports/desert_oracle_shrine.glb"
  }
}
```

## Acceptance Criteria For Phase 6B

The implementation phase can start only after this design is accepted and the
Wonder contract baseline is green. Its implementation must update the spec,
grammar, normalized AST schema, parser, normalizer, resolver, checker, planner,
formatter, examples, and tests together.

Phase 6B should prove:

- Existing v0.1 asset examples still parse, check, and build unchanged.
- Scene Graph to source to Scene Graph roundtrips preserve stable IDs.
- The scene syntax rejects unknown Scene Graph references with clear diagnostics.
- Asset-only commands do not require Project Wonder app state.
