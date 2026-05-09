# Lathe North Star: Floating Fantasy World Quality Roadmap

Date: 2026-05-06
Status: North Star quality target and phased implementation roadmap
Reference folder: `D:\lathe_v0_1\North Star`

## Reference Images

This document is anchored to the two images in this folder:

- `ChatGPT Image May 6, 2026, 12_54_03 PM.png` — hero-render target: a beautiful low-poly floating-island fantasy village diorama.
- `ChatGPT Image May 6, 2026, 12_53_50 PM.png` — playable-scene target: a third-person adventure view with pathing, UI, quest marker, minimap, traversal readability, and game-space intent.

These images define the first world-scale Lathe benchmark:

```text
stylized low-poly fantasy dioramas and playable adventure spaces
```

This is intentionally narrow. The goal is **not** to say "Lathe can create anything." The goal is to make Lathe excellent at a constrained, visually compelling, repeatable world style before expanding outward.

---

## 1. Strategic Thesis

The vision is possible, but not by jumping directly from current Lathe asset generation to full worlds.

Lathe must earn this in layers:

```text
single asset quality
-> coherent asset families / kits
-> micro-scenes
-> full scenic diorama
-> playable scene
```

The benchmark world is not just a rendered picture. It implies a complete semantic construction package:

```text
floating islands
village layout
cottages
bridges
paths
trees
crystals
waterfalls
lanterns
fences
materials
lighting
camera views
collision
walkable surfaces
quest anchors
NPC zones
minimap data
export evidence
repair history
```

Lathe should eventually create the **world recipe**, not only the final pixels.

The desired end state is:

```text
prompt / .lth source
-> semantic world plan
-> procedural construction graph
-> asset kit selection and generation
-> scene assembly
-> terrain and traversal validation
-> material/style application
-> .lthpkg / world package
-> @lathe/three preview and inspector
-> diagnostics and repair loop
-> game-engine export evidence
```

---

## 2. Current Reality Check

We are still in **Phase 1 — single asset quality**.

That is not a failure. It is the correct diagnosis.

If Lathe cannot create one beautiful, inspectable, stylized cottage or one strong crystal cluster, it is not ready to create a full floating fantasy village. World generation would only multiply weak assets into a larger weak scene.

Current operating truth:

```text
The crate / visible-geometry-kernel sprint proves Lathe can make one object honestly.
The floating fantasy village proves whether Lathe can become a world generator.
```

Both are needed:

- `industrial_crate` remains the hard-surface visible-geometry kernel proof.
- `floating_fantasy_village` becomes the world-generation product proof.

The implementation priority remains aligned with `docs/asset-quality/lathe-implementation-northstar.md`:

```text
intent -> artifact -> evidence -> judgment -> repair -> better artifact
```

No fake quality. No renderer polish hiding weak geometry. No report saying a feature exists unless the mesh/material/preview/package evidence proves it.

---

## 3. Product Positioning Constraint

The first world benchmark should be explicit:

> Lathe's first world-style benchmark is stylized low-poly fantasy dioramas and playable adventure spaces.

This gives us:

- a narrow art language;
- a clear visual benchmark;
- repeatable evaluation criteria;
- a demo category people immediately understand;
- a tractable technical scope;
- a natural path into Roblox, Unity, Three.js, and game prototypes.

Do **not** dilute the product by promising "anything." Lathe should first become dangerously good at one coherent world style.

---

## 4. What The Reference Style Requires

### 4.1 Visual Style

The benchmark style is:

```text
stylized
low-poly / faceted
colorful
fantasy
cozy
high-saturation
painterly
chunky and readable
game-like, not photorealistic
```

Required palette language:

- grass: saturated lime / emerald / olive green;
- trees: teal, turquoise, deep green, blue-green;
- roofs: golden yellow, ochre, warm orange;
- wood: warm brown, reddish brown;
- walls: cream, tan, light beige;
- cliffs: purple, lavender, indigo, muted blue;
- crystals: violet, magenta, pink, cyan;
- waterfall: bright cyan / turquoise;
- windows and lanterns: warm amber/orange emissive;
- sky: peach, pink, lavender, violet, sunset yellow.

The style should be clean and intentional. Low-poly facets should read as an art direction, not as unfinished geometry.

### 4.2 Composition Requirements

The hero image requires:

- a large central floating island;
- visible faceted cliff underside;
- a clear foreground-to-midground path;
- a bridge or path entry in the foreground;
- a central village cluster;
- one larger hero cottage / inn;
- smaller supporting cottages;
- trees framing the village;
- crystals as magical color accents;
- warm lantern/window glow;
- waterfall over the island edge;
- cloud layer below;
- background floating islands;
- distant low-poly mountains;
- sunset sky and atmospheric depth.

The playable image adds:

- third-person scale;
- clear walkable path;
- traversal-safe layout;
- readable cliff hazards;
- quest destination;
- minimap-friendly layout;
- UI/resource semantics;
- camera sightlines;
- gameplay readable landmarks.

### 4.3 Asset Families Needed

The style cannot be generated from isolated one-off objects. It needs reusable families:

- cozy fantasy cottage kit;
- stylized pine tree kit;
- crystal cluster kit;
- lantern post kit;
- stone path kit;
- rope bridge kit;
- fence kit;
- floating island / cliff kit;
- waterfall kit;
- mushroom / flower / grass prop kit;
- background island kit;
- mountain / cloud backdrop kit.

Each family needs semantic construction, not just mesh output.

Example semantic tags:

```text
house
roof
wall
window_emissive
door
chimney
path
walkable_surface
bridge
fence
lantern
crystal_node
tree
flower_patch
mushroom_cluster
floating_island
cliff_edge
waterfall_source
waterfall_drop
background_island
village_square
quest_marker
npc_spawn
player_spawn
camera_vista_point
```

---

## 5. Phase Roadmap

## Phase 1 — Single Asset Quality

Question:

> Can Lathe create one beautiful, controllable, semantic asset in this style?

Required single assets:

1. one cottage;
2. one crystal cluster;
3. one stylized pine tree;
4. one lantern post;
5. one bridge segment.

Each asset must prove:

- semantic structure;
- material zones;
- strong silhouette;
- controllable style;
- visible geometry quality;
- package evidence;
- honest unsupported/fallback labels.

### Phase 1 Acceptance Criteria

For each asset, Lathe must produce a package with:

```text
asset.lth
mesh.glb or equivalent geometry artifact
semantic-index.json
materials.json
diagnostics.json
evidence.json
preview image(s)
```

Each asset must pass these checks:

- The silhouette is recognizable at thumbnail size.
- The asset has named semantic parts, not anonymous primitive blobs.
- Material zones are visually distinct and mapped to semantic regions.
- The object has primary, secondary, and tertiary detail hierarchy.
- Important edges are beveled, faceted, or intentionally shaped.
- The style matches the low-poly fantasy palette.
- The preview does not rely on bloom/post-processing to hide weak geometry.
- The diagnostics can identify at least one visible weakness and recommend an executable repair.

### Phase 1 Asset-Specific Requirements

#### Cottage

Must include:

- body / wall shell;
- steep roof with non-boxy silhouette;
- door;
- warm emissive windows;
- timber frame or trim pieces;
- chimney or roof accent;
- material zones for roof, wall, wood, window glow, trim.

Failure state:

```text
A box with a roof is not enough.
```

#### Crystal Cluster

Must include:

- 3–7 faceted crystal prisms;
- varied heights and rotations;
- saturated magenta/violet/cyan material;
- optional subtle emissive/rim effect;
- base/socket or ground integration;
- semantic parts for primary crystal, secondary shards, base.

Failure state:

```text
One cone or stretched pyramid is not enough.
```

#### Stylized Pine Tree

Must include:

- trunk;
- stacked/conical foliage masses;
- low-poly faceted silhouette;
- 2–5 scale variants later;
- material zones for trunk and foliage;
- intentional asymmetry or layer variation.

Failure state:

```text
A cone on a cylinder is not enough.
```

#### Lantern Post

Must include:

- wooden post;
- base/feet or ground anchor;
- lantern housing;
- warm emissive light core;
- crossbeam or hanging bracket;
- material zones for wood, metal/trim, glass, emissive.

Failure state:

```text
A glowing cube on a stick is not enough.
```

#### Bridge Segment

Must include:

- plank boards;
- rope or rail system;
- posts;
- modular endpoints;
- collision/walkable surface metadata;
- material zones for wood, rope, fasteners.

Failure state:

```text
A flat rectangle labelled bridge is not enough.
```

### Phase 1 Technical Work Needed

- Strengthen visible geometry operations: bevel, inset, trim, repeated features, sockets, faceted prism generation, board/plank repetition.
- Extend family grammar beyond `industrial_crate` into fantasy asset families.
- Add style/art-direction IR for `stylized_low_poly_fantasy`.
- Add deterministic material-zone generation for warm/cool fantasy palettes.
- Add diagnostics for:
  - primitive/blockout appearance;
  - weak silhouette;
  - missing material-zone contrast;
  - missing semantic parts;
  - fake/detail-only metadata;
  - style mismatch.
- Ensure every Phase 1 asset emits `.lthpkg` evidence for `@lathe/three`.

Phase 1 is the current bottleneck.

---

## Phase 2 — Asset Families / Kits

Question:

> Can Lathe create coherent families of assets in the same art language?

Required kits:

- 8 cottage variants;
- 5 tree variants;
- 6 crystal variants;
- stone path kit;
- fence kit;
- cliff / floating-island kit;
- lantern kit;
- bridge kit.

This is the real prerequisite for worlds.

### Phase 2 Acceptance Criteria

A kit is successful when:

- variants share the same style vocabulary;
- variants are visibly different without looking random;
- all variants preserve semantic structure;
- material zones are consistent across the family;
- scale/proportion rules are coherent;
- modular pieces connect cleanly;
- family grammar coverage is measurable;
- variants can be selected by constraints, not by hardcoded family-name hacks.

### Required Family-Level Semantics

Each kit should define:

```text
family_id
style_id
variant_parameters
required_parts
recommended_parts
material_zone_schema
scale_bounds
proportion_rules
connection_points
placement_constraints
collision_policy
lod_policy
export_budget
repair_rules
```

Example:

```text
family: cozy_fantasy_cottage
style: stylized_low_poly_fantasy
required_parts:
  - wall_shell
  - roof
  - door
  - window_emissive
  - trim_or_timber_frame
recommended_parts:
  - chimney
  - dormer
  - sign
  - flower_box
material_zones:
  - roof_thatch
  - wall_plaster
  - wood_trim
  - window_glow
```

### Phase 2 Technical Work Needed

- Asset family grammar registry.
- Kit parameter system.
- Variant generation and selection.
- Style consistency validator.
- Family coverage validator.
- Modular seam/connector validation.
- Material palette consistency enforcement.
- `@lathe/three` kit browser mode for inspecting variants side by side.

---

## Phase 3 — Micro-Scenes

Question:

> Can Lathe compose several good assets into a small intentional scene?

Required micro-scenes:

1. cottage + path + trees + lanterns + crystals;
2. mini overlook scene;
3. bridge crossing;
4. cliff waterfall vignette.

This phase proves composition.

### Phase 3 Acceptance Criteria

A micro-scene is successful when:

- assets are placed with semantic intent;
- paths connect to doors, bridges, or overlooks;
- lanterns follow paths instead of scattering randomly;
- fences protect edges or frame spaces;
- crystals act as landmarks/resources, not random decoration;
- trees frame sightlines without blocking traversal;
- terrain supports the objects placed on it;
- the scene has foreground/midground/background intent;
- camera evidence shows the scene reads well.

### Required Scene Semantics

Micro-scenes should introduce:

```text
scene_graph
placement_constraints
path_spline
terrain_anchor
prop_cluster
landmark
vista_point
walkable_surface
hazard_edge
composition_role
```

### Phase 3 Technical Work Needed

- Semantic scene graph IR.
- Placement constraint solver.
- Path spline generator.
- Scatter rules that obey semantic zones.
- Terrain anchoring and object seating checks.
- Scene diagnostics for clutter, weak focal point, blocked path, floating props, scale mismatch.
- `@lathe/three` semantic picking across multi-asset scenes.

---

## Phase 4 — Full Scenic Diorama

Question:

> Can Lathe create a hero-render floating-island fantasy village like the first reference image?

Required output:

```text
beautiful floating-island fantasy village
art-directed as a hero render
composed for beauty
not yet required to be fully playable
```

This is a realistic major milestone.

### Phase 4 Acceptance Criteria

The diorama must visibly include:

1. large central floating island;
2. faceted cliff underside;
3. cozy fantasy village with at least 4–6 buildings;
4. one larger hero cottage / inn;
5. golden thatched roofs and timber-frame details;
6. stone path leading through the village;
7. foreground bridge or path entry;
8. warm glowing windows and lanterns;
9. stylized pine trees;
10. colorful crystal clusters;
11. cyan waterfall over island edge;
12. cloud layer below;
13. distant floating islands;
14. faceted fantasy mountains;
15. sunset/pastel sky;
16. strong warm/cool lighting balance;
17. camera-composed hero render.

### Phase 4 Technical Work Needed

- Floating island terrain generator.
- Cliff/facet/underside geometry builder.
- Terrain plateau and building-pad generation.
- Village layout grammar.
- Background island generation.
- Waterfall generator.
- Atmosphere/sky/cloud render layer.
- Composition planner for hero camera.
- Diorama diagnostics:
  - missing focal point;
  - weak path readability;
  - flat island silhouette;
  - style inconsistency;
  - lack of depth layers;
  - missing required hero elements.
- `@lathe/three` hero render evidence capture.

### Important Phase 4 Non-Goal

Do not claim game readiness yet.

A beautiful diorama is allowed to optimize for composition before gameplay. It still needs truthful geometry and semantic evidence, but it does not yet need full traversal, collision, navmesh, or engine import proof.

---

## Phase 5 — Playable Scene

Question:

> Can Lathe create something closer to the second reference image: a playable adventure space?

Required output:

```text
third-person explorable floating-island village scene
with pathing, traversal-safe layout, quest anchor, and game-engine export evidence
```

This is when the vision becomes genuinely powerful.

### Phase 5 Acceptance Criteria

The playable scene must include:

- player spawn point;
- main path network;
- traversal-safe bridge and stone path;
- walkable surfaces;
- collision meshes;
- non-walkable cliff/drop zones;
- camera/sightline anchors;
- village square;
- NPC elder location;
- quest marker location;
- minimap outline data;
- interactable/resource tags for crystals or pickups;
- engine export package;
- import evidence or truthful blocker.

### Required Gameplay Semantics

```text
player_spawn
quest_route
village_square
elder_npc_spawn
main_path
secondary_path
walkable_surface
collision_mesh
hazard_edge
non_walkable_drop
bridge_crossing
camera_vista_point
minimap_polygon
quest_marker
collectible_crystal
safe_zone
```

### Phase 5 Technical Work Needed

- Traversal graph generation.
- Walkability validation.
- Collision mesh generation.
- Game-engine export adapters.
- Minimap data generation.
- Quest/NPC anchor metadata.
- Runtime budget validation.
- Gameplay readability diagnostics.
- Engine import evidence pipeline.
- `@lathe/three` playable preview mode with path/collision overlays.

---

## 6. `three.lth` / `@lathe/three` Role In This Roadmap

`three.lth` is not what makes weak geometry good.

Its job is to make Lathe worlds:

- visible;
- inspectable;
- shareable;
- diagnosable;
- repairable;
- exportable.

The correct architecture remains:

```text
Lathe Core
  -> Lathe IR / .lthpkg / world package
  -> @lathe/three
  -> Lathe Web Viewer
  -> Lathe Playground / Studio
  -> Wonder visual repair loop
```

For this world benchmark, `@lathe/three` should evolve through these modes:

### Phase 1 Viewer Mode — Single Asset Inspector

- load one `.lthpkg`;
- show material/wireframe/normals;
- pick semantic parts;
- inspect material zones;
- view diagnostics;
- capture evidence screenshots.

### Phase 2 Viewer Mode — Kit Browser

- compare variants side by side;
- validate style consistency;
- inspect family grammar coverage;
- show parameter differences;
- flag weak variants.

### Phase 3 Viewer Mode — Micro-Scene Inspector

- load multi-asset scene package;
- inspect placement constraints;
- show path splines;
- show object anchors;
- flag floating/intersecting/mis-scaled props.

### Phase 4 Viewer Mode — Hero Diorama Review

- render wide hero camera;
- show semantic scene graph;
- inspect composition roles;
- compare before/after repairs;
- export image evidence.

### Phase 5 Viewer Mode — Playability Overlay

- show collision meshes;
- show walkable surfaces;
- show quest route;
- show spawn/NPC anchors;
- show minimap data;
- validate export/import evidence.

Rule:

```text
If the viewer makes a weak world look good only through lighting/post-processing, it is lying.
If the viewer exposes why the world is weak and helps repair it, it is Lathe's product surface.
```

---

## 7. Required Internal Capabilities

To reach the reference quality, Lathe needs these internal layers.

### 7.1 Style / Art Direction IR

A stable internal representation for:

```text
style_id: stylized_low_poly_fantasy
palette
shape_language
facet_policy
bevel_policy
material_policy
lighting_policy
composition_policy
forbidden_patterns
```

This lets Lathe produce assets in the same art language instead of treating every prompt as unrelated.

### 7.2 Semantic Asset Grammar

For each asset family:

```text
parts
required features
recommended features
material zones
connectors
placement constraints
variant parameters
repair rules
```

This extends the current family-grammar concept beyond the crate into fantasy assets.

### 7.3 Real Geometry Operations

Needed operations include:

- bevel/chamfer;
- inset panels;
- trim strips;
- repeated boards/planks;
- faceted prism generation;
- stacked conic foliage;
- gabled roof construction;
- roof curvature/sag stylization;
- timber frame placement;
- path stone tiling;
- rope/rail bridge generation;
- cliff facet generation;
- terrain plateau cutting;
- waterfall sheet/ribbon generation.

### 7.4 Material Zone System

Needed material concepts:

- semantic material zones;
- palette-bound materials;
- vertex color / simple gradient support;
- emissive windows/lanterns/crystals;
- faceted rock color variation;
- warm/cool lighting evidence;
- material-zone diagnostics.

### 7.5 Kit / Variant System

A kit system must support:

- families;
- variant counts;
- constrained randomness;
- style consistency;
- parameter traces;
- scale/proportion bounds;
- reusable connectors;
- family-level diagnostics.

### 7.6 Semantic Scene Graph

The world needs scene-level truth:

```text
scene
island
zone
path
building_pad
landmark
prop_cluster
vista
quest_area
hazard
background_layer
```

The graph must know why objects are placed, not only where they are.

### 7.7 Terrain / Island Generator

Needed terrain features:

- floating island outlines;
- grass top surfaces;
- faceted cliff sides;
- tapered undersides;
- ledges and terraces;
- building pads;
- path carving;
- waterfall source and drop;
- background island LODs.

### 7.8 Composition Planner

Needed composition concepts:

- hero camera;
- foreground/midground/background layers;
- focal point;
- leading path;
- landmark placement;
- skyline/silhouette balance;
- warm/cool color balance;
- clutter control.

### 7.9 Gameplay / Export Layer

For playable scenes:

- walkability;
- collision;
- nav/path graph;
- spawn points;
- quest markers;
- NPC anchors;
- minimap polygons;
- engine budget validation;
- import evidence.

### 7.10 Diagnostics And Repair

Every phase needs diagnostics that map to executable repairs.

Examples:

| Finding | Repair |
| --- | --- |
| cottage silhouette too boxy | regenerate roof/body proportions with stronger gable and trim |
| crystal cluster too simple | add secondary shards, varied heights, base integration |
| tree reads as cone-on-cylinder | add stacked foliage layers and asymmetry |
| lantern lacks semantic zones | add glass/emissive/wood/metal subparts |
| kit variants too similar | resample variant parameters under style constraints |
| path does not connect to door | reroute path spline to semantic entrance anchor |
| props float or intersect | reseat objects using terrain anchors |
| diorama lacks focal point | scale/promote hero cottage and recompose camera |
| playable path unsafe | rebuild collision/walkable graph and add fences/hazard labels |

---

## 8. Evaluation Standard

Lathe should not advance phases based on subjective excitement alone.

Use phase gates.

### Phase Gate A — Asset Truth

For each single asset:

- semantic parts present;
- material zones visible;
- silhouette strong;
- style palette matched;
- preview evidence generated;
- diagnostics emitted;
- at least one repair route exists.

### Phase Gate B — Kit Coherence

For each kit:

- required variant count met;
- variants differ meaningfully;
- style stays coherent;
- connectors/material zones consistent;
- weak variants flagged;
- side-by-side evidence generated.

### Phase Gate C — Composition Truth

For micro-scenes:

- semantic placement reasons recorded;
- paths connect;
- props are seated;
- focal point exists;
- clutter is controlled;
- camera evidence reads clearly.

### Phase Gate D — Hero Diorama Quality

For the full scenic diorama:

- all required hero elements visible;
- strong wide composition;
- foreground/midground/background readable;
- warm/cool palette balanced;
- no random scatter feel;
- no proxy-only world claim.

### Phase Gate E — Playability Truth

For playable scenes:

- walkable surfaces validated;
- collision generated;
- quest route exists;
- spawn/NPC anchors exist;
- minimap data exists;
- export/import evidence exists or blocker is truthfully reported.

---

## 9. Recommended Near-Term Execution Order

Do not start by building the full island.

Start here:

```text
Phase 1A: cottage
Phase 1B: crystal cluster
Phase 1C: stylized pine tree
Phase 1D: lantern post
Phase 1E: bridge segment
```

Each Phase 1 asset should become a small benchmark fixture with:

```text
.lth source
semantic construction graph
family grammar requirements
material zones
preview evidence
.lthpkg package
diagnostics
repair suggestion
@lathe/three inspection target
```

After all five Phase 1 fixtures work, move to:

```text
Phase 2A: cottage variants
Phase 2B: tree variants
Phase 2C: crystal variants
Phase 2D: path/fence/bridge kit
Phase 2E: cliff/floating-island kit
```

Only then should Lathe attempt the first composed scene.

---

## 10. First Concrete Implementation Spec Candidate

The first fantasy benchmark implementation should be:

```text
stylized_fantasy_cottage_v0
```

Goal:

> Produce one cottage that proves Lathe can generate a stylized low-poly fantasy building with semantic structure, material zones, strong silhouette, and evidence suitable for `@lathe/three` inspection.

Minimum required parts:

```text
wall_shell
roof
door
window_emissive
wood_trim_or_timber_frame
chimney_or_roof_accent
foundation_or_ground_seat
```

Minimum material zones:

```text
wall_plaster
roof_thatch
wood_trim
window_glow
door_wood
chimney_stone_or_metal
```

Minimum diagnostics:

```text
boxy_cottage_silhouette
missing_roof_detail
missing_window_glow
missing_timber_frame
weak_material_contrast
primitive_blockout_appearance
```

Minimum repair mappings:

```text
boxy_cottage_silhouette -> increase roof pitch, add overhang, vary wall proportions
missing_roof_detail -> add ridge cap, shingles/tiles, dormer or trim
missing_window_glow -> add emissive window zone
missing_timber_frame -> add timber beams and corner posts
weak_material_contrast -> rebalance palette/material zones
```

Minimum evidence:

```text
front preview
three-quarter preview
wireframe preview
material-zone preview
semantic inspector screenshot
package manifest
```

This is the correct first step because cottages are the center of the reference images. If Lathe can make one cottage feel charming and intentional, the whole world benchmark becomes credible.

---

## 11. Non-Goals

Do not do these yet:

- Do not promise arbitrary world generation.
- Do not start with a full map before the five Phase 1 assets are strong.
- Do not use Three.js rendering polish as proof of geometry quality.
- Do not fork Three.js to solve asset-quality problems.
- Do not add public `.lth` syntax before the internal execution path proves visible output.
- Do not claim Roblox/Unity/Unreal readiness without import/export evidence.
- Do not call a scene playable unless traversal/collision/path/quest metadata exist.
- Do not let metadata-only reports pass as visual quality.

---

## 12. Strategic Conclusion

Yes, Lathe should be able to create worlds like the references.

But the path is disciplined:

```text
make one asset good
make families coherent
compose micro-scenes
compose a hero diorama
make it playable
```

This North Star should live beside the existing implementation northstar:

- `docs/asset-quality/lathe-implementation-northstar.md` — operational truth for current visible-geometry work.
- `docs/product/three-lth-lathe-web-studio-v1-product-path.md` — browser/studio/product surface path.
- `North Star/lathe-floating-fantasy-world-northstar.md` — world-generation quality benchmark and phased path.

The dream is not a pretty screenshot generator.

The dream is:

```text
AI-native semantic world construction
with visible geometry,
truthful evidence,
style control,
repairable packages,
and game-engine export.
```

That is the road from current Lathe to a floating fantasy village world as high-quality as the references.
