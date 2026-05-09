# Lathe Frontier Asset Foundry Masterplan

Date: 2026-05-06  
Status: Master synthesis and implementation bridge  
Placement in sequence: **after** `docs/asset-quality/lathe-implementation-northstar.md`, **before** `three.lth` / `@lathe/three` / Lathe Web Studio  
Primary benchmark ladder: single asset quality -> asset generators -> scene assembly -> world compiler -> intent / imagination interface  
Long-term north star: stylized low-poly fantasy dioramas and playable adventure spaces

---

## 0. Why this document exists

This document is the master bridge between three currently separate threads:

1. **The active Lathe asset-quality implementation north star**
   - `docs/asset-quality/lathe-implementation-northstar.md`
   - Current sprint: `visible-geometry-kernel-sprint-0`
   - Current proof asset: `industrial_crate` / industrial sci-fi crate

2. **The frontier geometry-kernel research pass**
   - `docs/asset-quality/lathe-frontier-geometry-kernel-roadmap.md`
   - External and agent-swarm findings on Manifold, CGAL, OCCT, libigl, trimesh, Blender, Houdini, OpenUSD, Unreal, Unity, Godot, SDF/field workflows, and game-asset finalization
   - Core diagnosis: **Lathe's semantic language is ahead of its geometry-construction capability.**

3. **The newly uploaded strategy/research docs**
   - `gpt_research.md`: Lathe Forge, Styled Semantic Shape Graph, Facet Fields, style certificates, world compiler pipeline, Skyborne Village benchmark
   - `gemeini_research.md`: Prismatic Kernel Architecture, polyhedral F-Reps, Voronoi-cellular meshing, half-space CSG, analytic edge lighting, origami kinematics, premium faceted/high-fidelity low-poly aesthetic
   - `quality_before_intent.md`: quality before intent, Lathe Asset Foundry, Golden Asset Set, manual-first procedural-second quality process, asset quality ladder

The user direction is explicit:

```text
Finish lathe-implementation-northstar.md first.
Then implement this comprehensive geometry/kernel/asset-foundry foundation.
Then build three.lth / @lathe/three / Lathe Web Studio.
Then push toward the full floating fantasy world north star.
```

This document defines the second step: the **Lathe Asset Foundry** and its frontier geometry foundation.

It is not a replacement for the current asset-quality north star. It is what we do **after** the current visible-geometry work proves one asset can visibly improve and **before** the browser product layer makes Lathe public, inspectable, and shareable.

---

## 1. Executive thesis

Lathe should not jump from current asset-generation quality directly into a browser studio or a floating-world compiler.

The missing layer is the **Lathe Asset Foundry**:

```text
Lathe Asset Foundry
= geometry core
+ stylized asset operators
+ asset grammars
+ material/style rules
+ variation systems
+ runtime asset cooking
+ evidence / diagnostics / repair hooks
```

The Asset Foundry's job is simple but brutal:

> Make Lathe reliably manufacture beautiful, semantic, game-ready assets from code.

Until that is true, high-level intent becomes theatre. It produces instructions for a builder that does not exist yet.

The immediate strategic correction from the uploaded research is:

```text
Intent is the director, not the builder.
The builder must exist first.
```

So the true stack becomes:

```text
1. Asset build quality
2. Asset generators
3. Scene assembly
4. World compiler
5. Intent / imagination interface
```

Or in product-language terms:

```text
Lathe Foundry = asset generation and quality
Lathe Forge   = world compilation
Lathe Dream   = intent / imagination layer
```

This document is about **Foundry first**.

---

## 2. The corrected implementation sequence

The current repo/product sequence should now be treated as:

```text
Step 1 — Finish the current active north star
  docs/asset-quality/lathe-implementation-northstar.md
  visible-geometry-kernel-sprint-0
  industrial sci-fi crate proof

Step 2 — Implement this Foundry foundation
  docs/asset-quality/lathe-frontier-asset-foundry-masterplan.md
  kernel capability parity
  semantic GeometryOpGraph
  Prismatic/FacetField stylized mesh operators
  Golden Asset Set foundation
  game-ready asset cooking

Step 3 — Build @lathe/three / three.lth / Lathe Web Studio
  load .lthpkg
  inspect real geometry
  surface diagnostics
  evidence overlays
  repair UI

Step 4 — Push toward the floating fantasy world north star
  LowPolyFantasy.SunsetCrystal style pack
  Golden Asset Set -> micro-scene -> diorama -> playable scene
  Skyborne Village / floating fantasy village benchmark
```

The new insertion is deliberate. `@lathe/three` can make Lathe visible, but it cannot make weak geometry good. The browser studio must not become a beautiful wrapper around fake or low-quality output.

The Foundry exists so the first `three.lth` demo can show real evidence:

```text
real mesh
real semantic parts
real material zones
real operation provenance
real diagnostics
real before/after repair
real unsupported/fallback labels
```

---

## 3. Non-negotiable product principle: no fake quality

Lathe's credibility depends on a hard truth rule:

```text
A claim is only allowed if geometry/material/runtime evidence proves it.
```

Examples:

- If Lathe claims `beveled panels`, the viewer must show real bevel geometry or explicitly label it `unsupported`, `fallback`, `proxy`, or `not_verified`.
- If Lathe claims `socketed attachment`, the mesh must contain a receiver/seat/bracket relationship or a diagnostic must say it is only placed-on geometry.
- If Lathe claims `game-ready`, the package must include collision, scale/pivot, UV/material conventions, budget report, and runtime metadata.
- If Lathe claims `playable scene`, traversal, collision, nav/path data, hazards, and reachable anchors must exist.
- If Lathe uses analytic shader edge highlights, that can be a **lighting enhancement**, not proof of physical bevel geometry unless explicitly categorized as `analytic_edge_shading` rather than `mesh_bevel`.

This is how we absorb the ambitious Prismatic Kernel ideas without violating current quality philosophy.

Renderer tricks are allowed only when they are labeled as renderer techniques. They cannot pretend to be geometry.

---

## 4. Source synthesis: what each input contributes

### 4.1 `lathe-implementation-northstar.md`

The current north star defines the active work:

```text
intent -> artifact -> evidence -> judgment -> repair -> better artifact
```

It identifies the current practical target:

```text
visible-geometry-kernel-sprint-0
```

With the objective:

```text
Make one existing hard-surface fixture visibly better while preserving public source compatibility and the stable shape handoff contract.
```

The proof fixture is:

```text
industrial_crate / sci-fi crate
```

The done chain is:

```text
.lth intent
-> baseline crate artifact
-> visible weakness diagnostic
-> concrete operation or repair path
-> rebuilt crate artifact
-> before/after preview
-> report metrics change
-> export/package artifacts exist
```

This masterplan starts **after** that loop has a real visible win.

### 4.2 `quality-diagnostics-v1.md`

Diagnostics currently provide a non-blocking, additive evidence layer:

```json
{
  "version": "asset_quality_diagnostics_v1",
  "metrics": {
    "random_triangulation_penalty": 0.261,
    "debug_material_preview_penalty": 0.332,
    "highlow_fake_detail_penalty": 0.55,
    "attachment_seating_quality": 0.992,
    "primary_secondary_tertiary_balance": 0.978
  },
  "warnings": [],
  "recommendations": [],
  "findings": []
}
```

Key constraints to preserve during Foundry work:

- deterministic metrics in `[0.0, 1.0]`;
- additive payloads;
- warnings/recommendations/findings;
- Phase 1 `weight=0.0`;
- no public `.lth` syntax change by default;
- no break to `lathe.shape.intent_mesh_handoff_v1`;
- no fake pass based on metadata alone.

Foundry extends this concept from asset diagnostics into **kernel capability diagnostics**, **style diagnostics**, and **runtime asset cooking diagnostics**.

### 4.3 `family-grammar-v1.md`

Family grammar proves an important internal pattern:

```text
internal IR first, public syntax later
```

It defines construction requirements for a family without changing `.lth` syntax. For industrial crates, it can require concepts like:

- body shell;
- lid seam;
- corner guards;
- latch/latch plate;
- bracketed handles;
- foot rails;
- trim bands;
- fasteners;
- decal zones;
- edge wear masks.

Foundry generalizes this from one family into a real asset-manufacturing system:

```text
FamilyGrammar -> AssetGrammar -> GeneratorGrammar -> StylePackGrammar
```

### 4.4 `lathe-frontier-geometry-kernel-roadmap.md`

The prior swarm roadmap gives the kernel thesis:

```text
Lathe Frontier Geometry Kernel
= semantic construction graph
+ robust solid/boolean kernel
+ feature-aware mesh/topology kernel
+ attribute-preserving operation graph
+ field/SDF lane for organic terrain/detail
+ game-asset finalization lane
+ evidence + diagnostics + repair hooks
```

Its phases remain valid:

```text
K0 — Capability matrix and no-fake-quality gate
K1 — Manifold as the solid truth lane
K2 — Semantic feature operation graph
K3 — Real bevels, insets, panel cuts, and attachment seating
K4 — High/low production path
K5 — Field/SDF lane for organic/fantasy geometry
K6 — DCC reference backend
```

This masterplan absorbs those phases into a larger Foundry layer and adds the LowPolyFantasy/Prismatic/FacetField direction.

### 4.5 `geometry_kernel_eval.md`

The existing evaluation proves Manifold is not hypothetical. It already showed:

```text
courier_drone native watertight: 0.00
courier_drone Manifold watertight: 1.00
```

And:

- Manifold preserved healthy heroes at watertight `1.00`;
- Manifold was deterministic;
- Manifold was much faster on tested fixtures;
- Manifold should be adopted as the solid truth lane under `lathe.shape.intent_mesh_handoff_v1`, with the SDF/reference path retained as explicit fallback.

Foundry therefore does **not** start from zero. It should complete the path from `GeometryKernel`/`KernelProgram` into production-ready asset operators.

### 4.6 Current repo architecture

Lathe already has important foundation pieces:

- `lathe/geometry/kernel.py`
  - `GeometryKernel` protocol;
  - registry;
  - `lathe.geometry.manifold_v1`;
  - `lathe.geometry.reference_v1`;
  - environment/runtime config backend selection;
  - probe/capability metadata surface.

- `lathe/geometry/program.py`
  - `KernelProgram` seam;
  - `KernelOperand` provenance;
  - boolean/hull/minkowski/transform/import/instances operation counting;
  - semantic metadata extraction from primitives;
  - capability errors.

- `lathe/geometry/shape_ir_program.py`
  - ShapeIR primitive lowering into kernel primitives;
  - supported primitive kinds: box, cylinder, sphere, revolved/extruded profiles, torus, subdivision box, swept profile, lofted solid, heightfield, sdf_mesh;
  - heightfield solidification;
  - non-watertight primitive diagnostics.

- `lathe/adapters/manifold_kernel.py` and `lathe/geometry/manifold_kernel.py`
  - Manifold adapter and kernel lane.

- `lathe/mesh_ir.py`, `lathe/mesh_finalize.py`, `lathe/mesh_program/__init__.py`
  - mesh finalization and procedural mesh operations.

- `lathe/exact_solids.py`
  - exact/fallback geometry logic.

The gap is not absence of foundation. The gap is turning these seams into a **truthful asset-manufacturing machine**.

### 4.7 `three-lth-lathe-web-studio-v1-product-path.md`

The web/product decision is:

```text
Build @lathe/three first. Do not fork Three.js first.
```

Three.js provides:

- browser rendering;
- scene graph;
- cameras;
- loaders;
- materials;
- ecosystem.

Lathe provides:

- semantic construction truth;
- operation provenance;
- material zones;
- diagnostics;
- unsupported/fallback labels;
- evidence;
- repair history.

This masterplan must land before the web surface so `@lathe/three` can inspect meaningful `.lthpkg` content rather than merely loading an anonymous mesh.

### 4.8 `lathe-floating-fantasy-world-northstar.md`

The eventual benchmark is intentionally narrow:

```text
stylized low-poly fantasy dioramas and playable adventure spaces
```

The world ladder is:

```text
single asset quality
-> coherent asset families / kits
-> micro-scenes
-> full scenic diorama
-> playable scene
```

The required asset families include:

- cozy fantasy cottage kit;
- stylized pine tree kit;
- crystal cluster kit;
- lantern post kit;
- stone path kit;
- rope bridge kit;
- fence kit;
- floating island / cliff kit;
- waterfall kit;
- mushrooms / flowers / grass props;
- background islands / mountains / clouds.

This masterplan lays the foundations for those assets, not the world compiler itself.

### 4.9 `gpt_research.md`

The GPT research contributes several big ideas:

- Lathe needs an **art-directed world geometry kernel**, not a generic geometry kernel alone.
- The world style requires a **style kernel**, because quality is visual grammar, not just valid solids.
- The canonical representation should be a **Styled Semantic Shape Graph**.
- **Facet Fields** should control intentional low-poly planar facets.
- The first-class world primitives should be floating islands, paths, cottages, crystals, pines/foliage, bridges/fences/lamps, and waterfalls.
- The style pack `LowPolyFantasy.SunsetCrystal` should be executable.
- Lathe should emit **art-direction certificates** and not only geometry certificates.
- The eventual compiler pipeline is semantic scene graph -> layout solver -> styled geometry generation -> facet field -> material/lighting assignment -> runtime artifact compilation -> validation/certificates -> playable scene.

This is valuable but must be sequenced after Foundry has asset builders.

### 4.10 `gemeini_research.md`

The Gemini research contributes the **Prismatic Kernel Architecture**:

- premium faceted / high-fidelity low-poly aesthetic;
- mathematical sharpness and planar geometry as first-class citizens;
- polyhedral F-Reps and non-Euclidean distance metrics;
- Voronoi-cellular meshing for faceted terrain;
- half-space CSG for crystals and architecture;
- analytic edge beveling for lighting highlights;
- origami kinematics for preserving flat faces under animation;
- reinvesting low-poly efficiency into high-end lighting.

This should be treated as an **advanced style-kernel lane**, not as an immediate rewrite of Lathe. The immediate value is to formalize faceted/polygonal math for the LowPolyFantasy asset stack.

Important adaptation:

```text
Analytic edge lighting may improve visual quality, but it cannot be counted as real mesh bevel evidence unless explicitly labeled.
```

### 4.11 `quality_before_intent.md`

This is the key sequencing correction:

```text
Intent is worthless unless Lathe can reliably manufacture beautiful, usable assets.
```

It defines the real near-term question:

```text
Can Lathe build one cottage, one crystal cluster, one pine tree, one bridge,
one island cliff, one waterfall, and one path at concept-art quality?
```

It also defines the immediate foundation:

```text
geometry operators
style operators
asset grammars
material rules
variation systems
runtime asset cooking
```

And the Golden Asset Set:

```text
1. CozyCottage
2. ElderHouse
3. VioletCrystalCluster
4. AlpinePine
5. StonePathSegment
6. RopeBridge
7. WoodenFence
8. LanternPost
9. FloatingIslandSmall
10. WaterfallRibbon
```

This masterplan makes that foundation concrete.

---

## 5. The Foundry / Forge / Dream stack

Lathe should split the long-term ambition into three layers.

### 5.1 Lathe Foundry

Purpose:

```text
Manufacture beautiful, semantic, game-ready assets from code.
```

Scope:

- geometry primitives;
- mesh feature operators;
- stylized low-poly/faceted operators;
- asset grammars;
- material/style rules;
- variation systems;
- collision/proxy/LOD cooking;
- semantic sockets;
- evidence and diagnostics;
- repair patches.

Foundry is the focus of this document.

### 5.2 Lathe Forge

Purpose:

```text
Compile asset kits into coherent scenes/worlds.
```

Scope:

- scene graph;
- layout solver;
- path/route systems;
- scatter and placement;
- biome/style propagation;
- nav/collision scene integration;
- streaming chunks;
- world packages;
- playable scene certificates.

Forge comes after Foundry assets exist.

### 5.3 Lathe Dream

Purpose:

```text
Let natural-language/high-level intent direct a working builder.
```

Scope:

- prompt-to-plan;
- imagination loop;
- preference/style memory;
- high-level design changes;
- semantic editing;
- automatic repair proposals;
- Wonder visual repair loop.

Dream is not useful until Foundry and Forge can execute.

---

## 6. Foundry architecture overview

The Foundry stack should be layered like this:

```text
Layer 0 — Geometry Core
Layer 1 — Stylized Operators
Layer 2 — Asset Grammar / Generator System
Layer 3 — Runtime Asset Cooking
Layer 4 — Evidence, Diagnostics, Repair
Layer 5 — Package/Inspector Contract for @lathe/three
```

### 6.1 Layer 0 — Geometry Core

Goal:

```text
Reliable deterministic mesh construction with truthful backend capability reporting.
```

Minimum operations:

```text
create box / wedge / prism / cone / cylinder / sphere
extrude face/profile
sweep/loft where stable
inset face
bevel/chamfer edge group
split face
triangulate / beauty triangulate / quadify where useful
merge vertices / weld seams
boolean union/difference/intersection
convex hull
minkowski approximation where safe
assign part/material/semantic IDs
assign vertex colors
compute flat normals
compute weighted/smooth normals selectively
generate UVs or projection coordinates
generate collision hulls
generate bounds
generate sockets
```

Current Lathe alignment:

- `GeometryKernel` and `KernelProgram` already provide the backend seam.
- Manifold should be the solid truth lane.
- Reference/SDF paths remain explicit fallback lanes.
- Future Prismatic/FacetField lanes can be internal backends or generator modules, not public syntax.

### 6.2 Layer 1 — Stylized Operators

Goal:

```text
Make the target aesthetic executable, not merely described.
```

Operators:

```text
facet()
chunkify()
taper()
sag()
bend()
twist()
warp()
irregularize_outline()
jitter_controlled_vertices()
preserve_silhouette()
flat_normal_policy()
selective_smooth_normal_policy()
color_ramp()
style_grid_snap()
lowpoly_faceted_cliff()
crystal_prism_cluster()
thatched_roof_chunkify()
irregular_stone_slab_path()
```

These should compile into real geometry/material operations and emit evidence.

### 6.3 Layer 2 — Asset Grammar / Generator System

Goal:

```text
Create reusable, variable, coherent asset families.
```

Core concepts:

```text
asset
part
subpart
socket
material_slot
variant
seed
style_pack
collision_role
nav_role
lod_policy
semantic_tag
quality_certificate
```

The immediate assets:

- industrial sci-fi crate remains the hard-surface proof;
- CozyCottage;
- ElderHouse;
- VioletCrystalCluster;
- AlpinePine;
- StonePathSegment;
- RopeBridge;
- WoodenFence;
- LanternPost;
- FloatingIslandSmall;
- WaterfallRibbon.

### 6.4 Layer 3 — Runtime Asset Cooking

Goal:

```text
Turn authored/procedural geometry into game-ready artifact bundles.
```

Each asset package should include:

```text
render mesh
collision proxy
nav contribution if applicable
occlusion bounds
material assignments
semantic sockets
LOD/proxy policy where claimed
scale/pivot/unit evidence
source identity map
diagnostics
preview/debug artifacts
```

### 6.5 Layer 4 — Evidence, Diagnostics, Repair

Goal:

```text
Make every quality claim inspectable and repairable.
```

Evidence must prove:

- silhouette quality;
- proportion quality;
- facet quality;
- material/color quality;
- assembly quality;
- runtime quality;
- fallback/proxy honesty.

Repair mappings should begin with deterministic allowed operations:

```text
weak_primary_secondary_tertiary_balance -> add trim band / fastener grid / vent slats
missing_bevel_chamfer_detail_evidence -> add bevel/chamfer or mark unsupported
debug_material_preview_penalty -> apply family/style-aware material defaults
attachment_seating_quality low -> add socket / bracket / mount plate
weak_style_match -> apply style pack material/facet/proportion rules
path_not_walkable -> widen route / reduce slope / insert stairs
```

### 6.6 Layer 5 — Package/Inspector Contract for `@lathe/three`

Goal:

```text
Prepare meaningful .lthpkg output before the web viewer exists.
```

Package shape:

```text
asset_name.lthpkg/
  asset.lth
  manifest.json
  mesh.glb
  semantic-index.json
  diagnostics.json
  materials.json
  operations.json
  evidence.json
  runtime.json
  previews/
```

`@lathe/three` should not be responsible for inventing semantics. It should load and inspect what Foundry preserved.

---

## 7. The internal representation: from ShapeIR to GeometryOpGraph to AssetGraph

Lathe should not make triangles the source of truth.

The proposed internal chain is:

```text
.lth / existing asset intent
  -> DesignBrief / FamilyGrammar / ShapeIR
  -> GeometryOpGraph
  -> Kernel planner
  -> Backend lanes
  -> MeshIR / RuntimeArtifact
  -> .lthpkg evidence
```

### 7.1 `GeometryOpGraph`

A `GeometryOpGraph` is an internal typed graph of build operations.

Example node:

```json
{
  "operation_id": "op.cottage.roof.chunkify_01",
  "op": "style.chunkify_roof_panels",
  "semantic_part": "roof",
  "inputs": ["roof_base_volume"],
  "params": {
    "panel_size": 1.1,
    "facet_bias": "strong",
    "preserve_silhouette": true
  },
  "required_capabilities": [
    "mesh.face_split",
    "mesh.flat_normals",
    "attributes.material_zone_preservation"
  ],
  "fallback_policy": "diagnose_unsupported",
  "evidence_requirements": [
    "panel_face_count",
    "flat_normal_faces",
    "material_zone_roof_panels"
  ]
}
```

### 7.2 Required operation fields

Every operation should record:

```text
operation_id
operation type
inputs
semantic part / family requirement mapping
parameters
seed if stochastic
required capabilities
backend selected
fallback policy
attribute mapping
result metrics
evidence requirements
repair/rebuild eligibility
```

### 7.3 Attribute mapping contract

Every geometry operation must report what happened to identity:

```yaml
attribute_mapping:
  preserved:
    - part_id
    - material_zone
  transformed:
    - face_id
  split:
    - roof_panel_region
  merged: []
  generated:
    - bevel_ring_faces
  dropped: []
```

Dropping `part_id`, `material_zone`, `semantic_socket`, `collision_role`, or `nav_role` must produce a diagnostic.

### 7.4 Backend lanes

The planner should select from lanes:

```text
Manifold solid CSG lane
Reference/trimesh fallback lane
Mesh feature/topology lane
Prismatic polyhedral/facet lane
SDF/field lane for terrain/organic forms
DCC reference lane for quality targets and optional baking
Game finalization lane
```

This avoids the trap of one universal backend trying to do everything.

---

## 8. Kernel lanes and what they are for

### 8.1 Manifold solid truth lane

Use for:

- robust watertight CSG;
- boxes/cylinders/spheres where covered;
- solid fusion;
- boolean difference for cuts/panel grooves where attribute remap is supported;
- deterministic hard-surface foundations.

Must emit:

- kernel name/version;
- watertightness;
- body count;
- primitive coverage;
- fallback chain;
- attribute preservation report.

### 8.2 Mesh feature lane

Use for artist-level visible detail:

- bevels/chamfers;
- insets;
- panel grooves;
- trim bands;
- fastener grids;
- sockets/brackets;
- weighted normals;
- hard-edge marking;
- feature-preserving decimation;
- collision proxy generation.

This lane is where assets stop looking like blockouts.

### 8.3 Prismatic / polyhedral lane

Use for LowPolyFantasy/faceted style:

- crystals;
- faceted cliffs;
- floating island undersides;
- stylized roofs;
- angular rocks;
- chunky path stones;
- premium faceted silhouettes.

The Gemini research's **polyhedral F-Reps**, **half-space CSG**, and **Voronoi-cellular meshing** should enter here as incremental capabilities.

Immediate subset:

```text
convex polyhedron from plane set
prism/crystal generator
Voronoi/seeded planar facet field for terrain patches
flat-normal region preservation
facet-size and sliver-triangle controls
```

### 8.4 SDF / field lane

Use for:

- organic terrain masses;
- floating island base fields;
- smooth-to-faceted remeshing experiments;
- collision approximation;
- repair of rough forms.

Constraint:

```text
SDF output must not become melted or Minecraft-stair-stepped unless that style is explicitly requested.
```

For LowPolyFantasy, SDF should feed a controlled facet mesher, not raw marching-cubes blobs.

### 8.5 DCC reference lane

Use for:

- manual-first procedural-second quality targets;
- Blender/Houdini-style reference assets;
- optional render/bake/preview workflows;
- decomposition of hero assets into grammars.

Non-goal:

```text
Do not make Blender the permanent source of truth.
```

Use DCC assets to set quality targets, decompose style, and validate Lathe-generated equivalents.

### 8.6 Game finalization lane

Use for:

- collision proxies;
- nav contribution;
- scale/pivot/unit validation;
- LOD/proxy policy;
- UV/material conventions;
- performance budgets;
- engine export manifests.

This lane turns a beautiful mesh into a usable asset.

---

## 9. External research synthesis and Lathe-specific decisions

### 9.1 Manifold

Decision:

```text
Adopt as solid truth lane, not as the whole Foundry.
```

Reason:

- proven watertight improvements in Lathe evaluation;
- deterministic;
- fast;
- appropriate for solid CSG.

Gap:

- does not solve feature-aware mesh bevels/insets/semantics by itself;
- needs attribute remap and face-part assignment;
- should not hide unsupported operations.

### 9.2 CGAL

Decision:

```text
Research/reference candidate for exact geometry, not immediate default runtime.
```

Potential:

- computational geometry algorithms;
- robust triangulation/arrangements/polyhedra;
- future exact operations.

Caution:

- dependency/licensing/build complexity;
- broad scope;
- likely too heavy for immediate Foundry v0.1.

### 9.3 OpenCascade / OCCT

Decision:

```text
Future B-Rep/high-ceiling CAD lane, not Foundry v0.1 core.
```

Potential:

- NURBS/B-Rep solids;
- fillets/chamfers;
- CAD-quality modeling.

Caution:

- Foundry's first benchmark is stylized, faceted, game-ready assets, not universal CAD.
- Do not delay visible asset quality waiting for a full B-Rep stack.

### 9.4 libigl / trimesh / mesh-processing libraries

Decision:

```text
Use selectively for mesh analysis, remeshing, decimation, normals, topology utilities.
```

Potential:

- geometry processing;
- smoothing/decimation;
- mesh repair;
- diagnostics.

Caution:

- generated assets should be valid by construction where possible;
- repair libraries should not become a crutch for sloppy generators.

### 9.5 Blender Geometry Nodes / BMesh

Decision:

```text
Study as operation-graph and attribute-propagation reference; use as optional DCC reference backend.
```

Lessons:

- attributes/domains matter;
- procedural node graphs remain editable;
- modifier stacks preserve authoring intent;
- preview and visual validation are essential.

### 9.6 Houdini SOPs

Decision:

```text
Houdini is the reference mental model for procedural asset graphs.
```

Lessons:

- everything is an operation graph;
- attributes are first-class;
- proceduralism works when local edits and recompute boundaries are clean;
- asset generators should expose parameters, not random mesh dumps.

### 9.7 OpenUSD

Decision:

```text
Use composition/variant/primvar lessons for package and scene metadata design.
```

Lessons:

- layers/composition;
- variants;
- references;
- primvars/material bindings;
- stable identities across assets and scenes.

Foundry implication:

```text
.lthpkg should preserve semantic IDs, material zones, variants, and operation provenance in sidecars that can later map cleanly into USD-like scene packages.
```

### 9.8 Unreal / Unity / Godot game pipelines

Decision:

```text
Game-ready means more than render mesh.
```

Lessons:

- collision is separate from render mesh;
- LOD/proxy decisions matter;
- pivots/units/import settings matter;
- material conventions and normal map conventions matter;
- navmesh/playability is not automatic;
- high triangle budgets do not eliminate asset structure.

Foundry implication:

```text
Each asset must cook render, collision, semantic, material, and budget data together.
```

---

## 10. Prismatic Kernel adaptation for Lathe

The Prismatic Kernel Architecture is a strong north-star idea, but it must be adapted to Lathe's no-fake-quality discipline and current implementation sequence.

### 10.1 What we should adopt now

Adopt these ideas as Foundry primitives:

```text
flat planes as style primitives
half-space polyhedra for crystals/architecture
facet fields for cliffs/terrain/roofs/stones
Voronoi/seeded planar cells for faceted terrain patches
non-Euclidean distance metrics for stylized shape biases
flat normals by default for LowPolyFantasy
selective smooth normals for water/effects only
```

### 10.2 What we should defer

Defer:

- full custom renderer;
- hardware path-tracing dependency;
- real-time origami kinematics;
- universal polyhedral F-Rep engine;
- shader-only bevel claims;
- replacing current geometry stack wholesale.

### 10.3 Analytic edge lighting policy

Analytic edge lighting can be valuable for the high-fidelity low-poly look, but must be categorized honestly.

Allowed:

```text
analytic_edge_highlight
shader_micro_rounding_preview
style lighting enhancement
```

Not allowed:

```text
claiming mesh bevel evidence when no bevel geometry exists
passing missing bevel diagnostics because shader normals look nice
hiding blockout geometry behind sunset lighting or bloom
```

### 10.4 Foundry v0.1 Prismatic subset

Implementable subset:

```text
PrismMeshBuilder
HalfSpacePolyhedronBuilder
FacetField2D/3D data model
CrystalClusterGenerator
FacetedCliffPatchGenerator
FlatNormalPolicy
FacetQualityDiagnostics
SliverTriangleDiagnostics
Palette/vertex-color material zones
```

This gives immediate value to the Golden Asset Set without derailing into a full engine rewrite.

---

## 11. The LowPolyFantasy style pack

The first official style pack should be:

```text
LowPolyFantasy.SunsetCrystal
```

Why this wedge works:

- visually stunning;
- technically achievable;
- benefits heavily from procedural generation;
- does not require photoreal scans;
- naturally supports gameplay readability;
- fits Roblox/Unity/Three.js prototype ambitions;
- makes Lathe's promise obvious.

### 11.1 Style rules

Geometry:

```text
flat normals by default
chunky readable silhouettes
intentional planar facets
limited, visible bevels/chamfers where claimed
no random decimation scars
no tiny sliver triangles
exaggerated roofs/cliffs/crystals
simple strong shape hierarchy
```

Materials:

```text
vertex-color-first or simple material-zone-first workflow
warm window/lantern emissive
violet/magenta/cyan crystals
golden roofs
cream walls
teal/deep-green pines
emerald/lime grass
purple/lavender cliffs
cyan/turquoise water
painterly ramps over photoreal textures
```

Composition:

```text
clear paths
strong landmarks
foreground/midground/background layering
village center readability
dangerous cliffs fenced or tagged
crystals as magical accents
lanterns along paths
```

Runtime:

```text
third-person scale
walkable path width
collision separate from render mesh
nav contribution where relevant
sockets for props/effects
semantic picking
performance budgets
```

### 11.2 Style certificates

Every LowPolyFantasy asset should eventually emit a style certificate:

```json
{
  "style": "LowPolyFantasy.SunsetCrystal",
  "version": "lowpoly_fantasy_style_certificate_v1",
  "metrics": {
    "silhouette_readability": 0.91,
    "facet_intentionality": 0.87,
    "palette_compliance": 0.94,
    "material_zone_contrast": 0.89,
    "primary_secondary_tertiary_balance": 0.84,
    "runtime_asset_readiness": 0.78
  },
  "findings": []
}
```

Phase 1 can keep this advisory. Later strict modes can block false hero claims.

---

## 12. Asset quality definition

For Lathe, asset quality is not just polygon count or watertightness.

The Foundry must optimize six qualities.

### 12.1 Silhouette quality

The asset must read instantly at thumbnail distance.

Examples:

- cottage: charming, exaggerated roofline;
- crystal: heroic radial form;
- pine: stacked tiered mass;
- island: iconic top mass and faceted underside;
- path: readable route through the scene.

### 12.2 Proportion quality

Stylized assets need intentional exaggeration:

- oversized roofs;
- chunky beams;
- tall crystals;
- broad stone slabs;
- wide heroic paths;
- simple tree masses;
- dramatic island depth.

### 12.3 Facet quality

Low-poly does not mean random triangles.

Facet diagnostics should detect:

- tiny sliver triangles;
- chaotic triangulation;
- melted SDF surfaces;
- stair-stepped voxel artifacts;
- facet size outside style range;
- silhouette-destroying decimation.

### 12.4 Material and color quality

Assets must carry style material zones:

- not grey debug meshes;
- not material-ID colors masquerading as final art;
- clear warm/cool color hierarchy;
- emissive regions for windows/crystals/lanterns;
- palette compliance.

### 12.5 Assembly quality

A good asset is an assembly, not a blob:

```text
Cottage = walls + roof + beams + windows + door + chimney + sockets + collision
CrystalCluster = main crystal + side crystals + base rocks + glow socket + collision
Bridge = planks + posts + ropes + rail + nav/collision ribbon
Path = route spline + nav ribbon + stone slabs + side sockets + grass exclusions
```

### 12.6 Runtime quality

An asset is not game-ready unless it includes:

- render mesh;
- collision proxy;
- nav contribution when relevant;
- material assignments;
- semantic sockets;
- scale/pivot/units;
- LOD/proxy policy when claimed;
- source identity map;
- package evidence.

---

## 13. The asset quality ladder

Foundry should use a ladder, not a binary pass/fail illusion.

```text
Level 0 — Valid mesh
Level 1 — Recognizable object
Level 2 — Styled object
Level 3 — Beautiful object
Level 4 — Variant family
Level 5 — Game-ready asset
Level 6 — Scene-ready asset
Level 7 — Hero-quality asset
```

Near-term requirement:

```text
Lathe must reach Level 5 before high-level intent matters.
Lathe must reach Level 6 before world compiler work matters.
```

Level definitions:

### Level 0 — Valid mesh

- non-empty mesh;
- no catastrophic topology errors;
- exported artifact exists.

### Level 1 — Recognizable object

- object reads as intended family;
- major parts identifiable;
- crude but coherent.

### Level 2 — Styled object

- style pack applied;
- palette/material zones exist;
- flat/faceted normal policy is intentional.

### Level 3 — Beautiful object

- strong silhouette;
- proportion/charm;
- no obvious procedural ugliness;
- readable primary/secondary/tertiary detail.

### Level 4 — Variant family

- multiple seeds produce coherent variants;
- variation does not break style or runtime constraints;
- shared sockets/material/semantic schema.

### Level 5 — Game-ready asset

- collision;
- scale/pivot;
- material conventions;
- semantic sockets;
- export package;
- budget checks.

### Level 6 — Scene-ready asset

- composes with other assets;
- snap/attach/scatter rules;
- path/nav/collision interactions;
- style compatibility with kit.

### Level 7 — Hero-quality asset

- benchmark/showcase quality;
- suitable for `@lathe/three` demo;
- before/after evidence;
- strict no-fake-quality certification.

---

## 14. Manual-first, procedural-second process

The uploaded research proposes an important process:

```text
manual-first, procedural-second
```

This does not mean Lathe depends on manual DCC work forever. It means we need real quality targets.

### Step 1 — Build or acquire one hero reference asset

Example:

- one beautiful stylized cottage;
- one high-quality crystal cluster;
- one faceted island chunk.

### Step 2 — Decompose the asset

Extract grammar:

```text
base volumes
proportions
silhouette rules
part hierarchy
socket placement
facet rules
material zones
collision simplification
variation axes
```

### Step 3 — Rebuild procedurally in Lathe

The goal is not import. The goal is to reproduce the family through code.

### Step 4 — Generate variants

Examples:

```text
small cottage
wide cottage
tall cottage
wizard cottage
shop cottage
elder cottage
```

### Step 5 — Compare against hero target

Judge:

```text
silhouette
proportions
materials
facets
charm
runtime usability
variant stability
```

This is how Lathe climbs from procedural geometry to art quality.

---

## 15. Golden Asset Set v0.1

The first Foundry milestone is not a world. It is a **Golden Asset Set**.

### 15.1 Required assets

```text
1. CozyCottage
2. ElderHouse
3. VioletCrystalCluster
4. AlpinePine
5. StonePathSegment
6. RopeBridge
7. WoodenFence
8. LanternPost
9. FloatingIslandSmall
10. WaterfallRibbon
```

### 15.2 Required output for each asset

```text
render mesh
materials / material zones
collision proxy
semantic sockets
variant controls
debug/evidence view
style certificate
runtime readiness report
.lthpkg package
```

### 15.3 Required quality for each asset

Each asset must be:

- beautiful in isolation;
- beautiful in a small scene;
- procedurally variable;
- game-ready;
- style-consistent;
- semantically inspectable;
- honest about unsupported/fallback/proxy states.

### 15.4 The first diorama after Golden Asset Set

Only after the Golden Asset Set works, assemble:

```text
one island
one path
three cottages
ten trees
three crystal clusters
one bridge
one waterfall
lanterns and fences
```

No AI intent. No big world. Just proof that Lathe can build.

---

## 16. Golden asset specifications

### 16.1 CozyCottage

Must include:

- wall/body shell;
- exaggerated gable or fantasy roof;
- roof overhang;
- sag/chunkify/facet option;
- door;
- warm emissive windows;
- timber frame / chunky beams;
- chimney or roof accent;
- material zones: wall, roof, wood trim, window glow, door;
- collision hull;
- door entry socket;
- lantern sockets;
- variant controls.

Not good enough:

```text
A box with a roof.
```

Hard quality bar:

```text
strong silhouette from 100m
exaggerated roof proportions
visible warm windows
chunky timber framing
clean flat-shaded facets
no random noise
coherent material regions
collision
door socket
20 good variants
looks good next to pine/crystal assets
```

### 16.2 ElderHouse

Purpose:

```text
Hero landmark variant of CozyCottage.
```

Additional requirements:

- larger scale;
- more expressive roofline;
- visible destination marker socket;
- plaza/path-facing front;
- stronger window/lantern composition;
- optional balcony/sign/chimney cluster;
- landmark visibility certificate.

### 16.3 VioletCrystalCluster

Must include:

- 3–9 faceted crystal prisms;
- varied heights/radii/rotations;
- main crystal + secondary shards;
- radial or clustered growth rules;
- saturated violet/magenta/cyan material;
- optional emissive core;
- base rocks/socket integration;
- simple collision;
- glow/light socket;
- collectible/resource semantic tag optional.

Not good enough:

```text
One cone or stretched pyramid.
```

### 16.4 AlpinePine

Must include:

- tapered trunk;
- stacked conical/frustum foliage masses;
- 6-sided or low-sided faceted geometry;
- flat normals;
- material zones: trunk, foliage;
- controlled asymmetry;
- scale variants;
- trunk-only collision by default;
- scatter metadata.

Not good enough:

```text
A cone on a cylinder.
```

### 16.5 StonePathSegment

Must include:

- logical path spline;
- clean nav/walkable ribbon;
- decorative stone slabs;
- slope correction;
- optional stair insertion;
- grass/prop exclusion region;
- lantern/fence sockets;
- material zones;
- collision/nav semantics.

Not good enough:

```text
A texture strip or random stones that break traversal.
```

### 16.6 RopeBridge

Must include:

- span/curve;
- planks;
- posts;
- rope rails;
- sag;
- endpoint sockets;
- collision ribbon;
- nav link;
- material zones: wood, rope, fasteners.

Not good enough:

```text
A flat rectangle labeled bridge.
```

### 16.7 WoodenFence

Must include:

- posts and rails;
- boundary/path placement logic;
- gaps at exits;
- cliff-hazard semantic link;
- collision blocker or visual-only role explicitly declared;
- style material.

### 16.8 LanternPost

Must include:

- post;
- base/ground anchor;
- crossbeam or bracket;
- lantern housing;
- glass/emissive core;
- warm light hook;
- optional collision;
- path/socket placement compatibility.

Not good enough:

```text
A glowing cube on a stick.
```

### 16.9 FloatingIslandSmall

Must include:

- walkable top plateau;
- faceted cliff ring;
- dramatic underside shards;
- grass/rock material boundary;
- bridge sockets;
- waterfall sockets;
- scatter surfaces;
- simplified collision;
- nav extraction;
- terrace/path support;
- far-distance silhouette quality.

Hard quality bar:

```text
top is walkable
cliff sides are faceted and dramatic
underside has shard-like massing
grass/rock boundary is clean
silhouette reads from far away
edge sockets for bridges/waterfalls
scatter surfaces for trees/crystals/props
simplified collision
nav extraction for top
supports terraces and paths
```

### 16.10 WaterfallRibbon

Must include:

- source socket;
- stylized ribbon mesh;
- faceted water material;
- foam mesh/decal hooks;
- mist particle socket;
- sound region hook;
- non-walkable volume;
- collision/no-entry metadata.

Not required yet:

```text
Full fluid simulation.
```

---

## 17. Industrial sci-fi crate remains the hard-surface bridge

Even though the world north star is fantasy, the immediate proof remains the industrial sci-fi crate.

Why:

- it is already in the current asset-quality path;
- it stresses hard-surface operations;
- it is a good test for Manifold/CSG/bevels/insets/fasteners/material zones;
- it forces no-fake-quality discipline before fantasy aesthetics.

The crate should prove:

```text
real panel geometry
real trim bands
real fastener grids
real bevel/chamfer evidence or honest unsupported labels
family grammar coverage improvement
before/after diagnostics
.lthpkg evidence bundle
```

Then Foundry generalizes the same mechanisms into fantasy assets.

---

## 18. Implementation plan after current northstar, before `three.lth`

This is the concrete modular/agile plan for the Foundry phase.

### Phase F0 — Foundry baseline and capability freeze

Goal:

```text
Document exactly what current Lathe can build, where it fakes/falls back, and what capabilities Foundry v0.1 needs.
```

Create/update:

```text
docs/asset-quality/foundry-capability-matrix.md
docs/asset-quality/foundry-golden-asset-set-v0.md
```

Implement:

- kernel capability probe schema;
- operation capability matrix;
- current asset quality ladder assessment for crate/door and any fantasy fixtures;
- fallback/proxy taxonomy.

Acceptance:

- every Foundry v0.1 required operation has status: `supported`, `partial`, `fallback`, `unsupported`, or `not_started`;
- no hidden fake-quality gaps.

### Phase F1 — GeometryOpGraph v1

Goal:

```text
Create the internal operation graph that connects semantic claims to executable geometry operations.
```

Likely files:

```text
lathe/geometry/op_graph.py
lathe/geometry/capabilities.py
lathe/geometry/planner.py
lathe/geometry/attribute_mapping.py
tests/unit/test_geometry_op_graph.py
tests/unit/test_kernel_capabilities.py
tests/unit/test_attribute_mapping.py
```

Requirements:

- stable operation IDs;
- deterministic serialization;
- required capabilities;
- backend selection trace;
- fallback policy;
- attribute mapping;
- no public `.lth` syntax change;
- no break to `lathe.shape.intent_mesh_handoff_v1`.

Acceptance:

- industrial crate build can emit operation traces for at least one visible feature operation;
- unsupported op emits diagnostic, not silent degradation.

### Phase F2 — Manifold production lane completion

Goal:

```text
Make Manifold the reliable solid truth lane where coverage exists.
```

Implement:

- default Manifold use when available and appropriate;
- backend chain telemetry;
- face/part assignment validation on multi-body output;
- watertight/body-count metrics;
- deterministic cache key reuse;
- fallback diagnostics.

Acceptance:

- crate hard-surface solid ops use Manifold when supported;
- fallback is explicit;
- watertightness and body count are reported;
- no unsupported cutter omission passes silently.

### Phase F3 — Mesh feature operator slice

Goal:

```text
Add a narrow set of visible feature operators that directly improve assets.
```

First operators:

```text
op.trim_band
op.fastener_grid
op.panel_inset
op.vent_slats
op.socket
op.mount_plate
op.bevel_or_chamfer_edge_group
```

Acceptance:

- industrial crate visibly improves;
- diagnostics detect before-state weakness;
- repair can add at least one operation;
- output package preserves operation provenance.

### Phase F4 — Prismatic/facet operator slice

Goal:

```text
Introduce LowPolyFantasy faceted geometry capabilities without a full engine rewrite.
```

First operators:

```text
mesh.prism()
mesh.crystal_prism()
mesh.half_space_polyhedron()
style.facet_field()
style.chunkify_surface()
style.flat_normal_policy()
terrain.faceted_cliff_patch()
terrain.underside_shards()
```

Acceptance:

- `VioletCrystalCluster` prototype generates real faceted prisms;
- `FloatingIslandSmall` can generate one faceted cliff/underside patch;
- facet diagnostics report slivers/randomness/style range.

### Phase F5 — Asset grammar/generator framework

Goal:

```text
Turn operation slices into reusable asset generators.
```

Likely files:

```text
lathe/asset_foundry/__init__.py
lathe/asset_foundry/generator.py
lathe/asset_foundry/grammar.py
lathe/asset_foundry/style_pack.py
lathe/asset_foundry/lowpoly_fantasy.py
lathe/asset_foundry/generators/crystal_cluster.py
lathe/asset_foundry/generators/pine_tree.py
lathe/asset_foundry/generators/cottage.py
```

Requirements:

- parameter schema;
- deterministic seed behavior;
- variant generation;
- material slots;
- sockets;
- collision hooks;
- style pack link;
- quality ladder output.

Acceptance:

- at least three Golden Asset Set assets can be generated from code:
  - `VioletCrystalCluster`;
  - `AlpinePine`;
  - `StonePathSegment` or `CozyCottage` first slice.

### Phase F6 — Runtime asset cooking

Goal:

```text
Make assets game-ready, not just pretty.
```

Implement:

- collision proxy generation;
- nav contribution for path/bridge/island top;
- material-zone manifest;
- scale/pivot/unit validation;
- LOD/proxy policy field;
- runtime artifact manifest.

Acceptance:

- each generated Golden Asset Set prototype emits `runtime.json` with render/collision/nav/material/semantic data;
- path and bridge separate visual geometry from traversal geometry.

### Phase F7 — Foundry diagnostics and certificates

Goal:

```text
Make Foundry output measurable and repairable.
```

Add metrics:

```text
silhouette_readability
proportion_style_score
facet_intentionality
sliver_triangle_penalty
material_palette_compliance
semantic_socket_coverage
runtime_readiness_score
variant_stability_score
style_pack_compliance
collision_visual_deviation
```

Acceptance:

- each asset emits an asset-quality ladder level;
- diagnostics explain why it is not yet Level 5/6/7;
- at least one diagnostic maps to an executable repair or regeneration strategy.

### Phase F8 — Golden Asset Set v0.1

Goal:

```text
Build and package the first Foundry asset set.
```

Minimum first cut:

```text
VioletCrystalCluster
AlpinePine
StonePathSegment
LanternPost
RopeBridge
CozyCottage slice
FloatingIslandSmall slice
```

Full v0.1:

```text
CozyCottage
ElderHouse
VioletCrystalCluster
AlpinePine
StonePathSegment
RopeBridge
WoodenFence
LanternPost
FloatingIslandSmall
WaterfallRibbon
```

Acceptance:

- each asset reaches at least Level 3;
- at least three assets reach Level 5;
- at least one family reaches Level 4 variant quality;
- package artifacts exist for `@lathe/three` future loading.

### Phase F9 — Micro-diorama evidence package

Goal:

```text
Assemble a tiny scene without high-level intent.
```

Scene:

```text
one island
one path
one cottage
three trees
two crystal clusters
one lantern
one fence segment
```

Acceptance:

- visual output is coherent;
- semantic scene graph exists;
- path has nav/collision evidence;
- assets are selectable/traceable;
- style certificate exists;
- package can become the fixture for `@lathe/three`.

---

## 19. Agile execution model

This phase must stay modular and agile. Do not build a grand kernel cathedral before visible proof.

### 19.1 Sprint shape

Each sprint should deliver:

```text
one asset or operation
one diagnostic
one evidence artifact
one regression test
one package/report update
```

### 19.2 Vertical slices over horizontal rewrites

Good slice:

```text
VioletCrystalCluster
-> prism builder
-> material zones
-> collision hull
-> style certificate
-> .lthpkg evidence
```

Bad slice:

```text
Rewrite entire geometry kernel for all future assets.
```

### 19.3 Recommended sprint order

After `visible-geometry-kernel-sprint-0`:

```text
Sprint F1: Foundry capability matrix
Sprint F2: GeometryOpGraph internal seam
Sprint F3: Manifold telemetry + fallback diagnostics
Sprint F4: one mesh feature op on industrial crate
Sprint F5: crystal prism generator
Sprint F6: pine tree generator
Sprint F7: path/nav ribbon + stone slabs
Sprint F8: style certificate v1
Sprint F9: .lthpkg Foundry package fixture
Sprint F10: micro-diorama
```

### 19.4 Definition of done per sprint

A sprint is not done until:

- code exists;
- tests exist;
- evidence exists;
- generated artifact exists;
- diagnostics explain unsupported/fallback states;
- docs update the capability matrix;
- no public `.lth` or handoff contract break occurred unless explicitly approved.

---

## 20. Diagnostics, certificates, and debug views

The Foundry should produce debug/evidence surfaces that later map directly into `@lathe/three`.

### 20.1 Asset debug views

For a single asset:

```text
render view
wireframe view
material-zone view
semantic-part view
operation-provenance view
collision view
socket view
style-score view
fallback/proxy view
```

### 20.2 Scene/world debug views

For the eventual floating fantasy benchmark:

```text
render view
collision view
navmesh view
semantic view
style score view
performance view
```

These were explicitly requested in the uploaded research and should become future Lathe Web Studio panels.

### 20.3 Certificate families

Foundry should prepare these certificates:

```text
geometry_certificate_v1
style_certificate_v1
runtime_asset_certificate_v1
variant_family_certificate_v1
package_evidence_certificate_v1
```

Later Forge adds:

```text
scene_composition_certificate_v1
playability_certificate_v1
performance_certificate_v1
```

---

## 21. How this prepares `@lathe/three`

`@lathe/three` should load `.lthpkg` packages with real metadata.

Foundry must ensure package sidecars contain:

```text
semantic-index.json
operations.json
materials.json
diagnostics.json
evidence.json
runtime.json
```

Then `@lathe/three` can expose:

- semantic part picker;
- material-zone picker;
- diagnostics overlay;
- operation provenance panel;
- unsupported/fallback labels;
- collision/nav overlays;
- before/after comparison;
- repair suggestions.

Without Foundry, the web viewer becomes a generic GLB viewer. With Foundry, it becomes Lathe's body.

---

## 22. How this prepares the floating fantasy world north star

The world north star should not begin with a prompt.

It should begin with this ladder:

```text
Golden Asset Set
-> asset families/kits
-> micro-diorama
-> controlled diorama
-> playable scene
-> intent-directed world
```

### 22.1 From Foundry assets to kits

Each asset family needs:

```text
part schema
variant schema
socket schema
material schema
collision/nav schema
style certificate
quality ladder level
```

### 22.2 From kits to micro-scenes

A micro-scene proves composition:

```text
path + cottage + lantern + fence
path + bridge + island edge
crystal cluster + tree + mushroom scatter
waterfall + cliff edge + no-entry volume
```

### 22.3 From micro-scenes to Skyborne Village

Only after micro-scenes work should Forge compile:

```text
a cozy low-poly floating village at sunset,
with crystal gardens, pine trees, cottages,
a main path, a rope bridge, and a waterfall
```

Required proof:

```text
playable third_person
all houses reachable
path readable
style LowPolyFantasy.SunsetCrystal
render/collision/nav/semantic/style/performance debug views
```

---

## 23. Risks and mitigations

### Risk 1 — Building too broad a kernel

Failure mode:

```text
Trying to solve universal CAD/AAA geometry before one asset looks good.
```

Mitigation:

```text
Industrial crate -> crystal -> pine -> path -> cottage -> micro-diorama.
```

### Risk 2 — Fake quality through renderer polish

Failure mode:

```text
Bloom/sunset/path tracing hides weak mesh construction.
```

Mitigation:

```text
Require wireframe/material/semantic/collision/debug views and no-fake-quality labels.
```

### Risk 3 — Style pack becomes vague adjectives

Failure mode:

```text
make_chunky means nothing executable.
```

Mitigation:

```text
Every style operator lowers to geometry/material operations with metrics and evidence.
```

### Risk 4 — Asset generators become random ugly variation

Failure mode:

```text
20 variants but only 2 look good.
```

Mitigation:

```text
Variant stability certificate and seed corpus testing.
```

### Risk 5 — Web viewer arrives too early

Failure mode:

```text
@lathe/three shows weak geometry beautifully.
```

Mitigation:

```text
Foundry package fixture must include real operation/evidence/diagnostics before Web Studio MVP.
```

### Risk 6 — Overfitting to fantasy

Failure mode:

```text
Lathe becomes only a fantasy asset generator.
```

Mitigation:

```text
Keep industrial crate as hard-surface anchor; structure Foundry as style-pack/generator framework, not hardcoded fantasy one-offs.
```

### Risk 7 — Overfitting to crate/chest

Failure mode:

```text
All fixes become family-specific Python branches.
```

Mitigation:

```text
Use operation graphs, selectors, component tags, asset grammars, and style packs.
```

---

## 24. Non-goals for this phase

Do not implement these in the Foundry bridge phase unless explicitly authorized:

- public `.lth` syntax rewrite;
- `lathe.shape.intent_mesh_handoff_v1` break;
- full Three.js fork;
- full world compiler;
- high-level natural-language intent layer;
- universal CAD/B-Rep kernel;
- full shader/render engine replacement;
- photoreal scan ingestion;
- arbitrary all-style generation;
- open-ended infinite worlds;
- claiming playable scenes without collision/nav/path evidence.

---

## 25. Concrete file/module map

Likely new docs:

```text
docs/asset-quality/foundry-capability-matrix.md
docs/asset-quality/foundry-golden-asset-set-v0.md
docs/asset-quality/foundry-style-pack-lowpoly-fantasy.md
docs/asset-quality/foundry-diagnostics-v1.md
docs/asset-quality/foundry-runtime-cooking-v1.md
```

Likely new modules:

```text
lathe/asset_foundry/__init__.py
lathe/asset_foundry/generator.py
lathe/asset_foundry/grammar.py
lathe/asset_foundry/style_pack.py
lathe/asset_foundry/certificates.py
lathe/asset_foundry/runtime_cook.py
lathe/asset_foundry/package_writer.py
lathe/asset_foundry/lowpoly_fantasy.py
lathe/asset_foundry/generators/crystal_cluster.py
lathe/asset_foundry/generators/pine_tree.py
lathe/asset_foundry/generators/stone_path.py
lathe/asset_foundry/generators/lantern.py
lathe/asset_foundry/generators/bridge.py
lathe/asset_foundry/generators/cottage.py
lathe/asset_foundry/generators/floating_island.py
```

Likely geometry modules:

```text
lathe/geometry/op_graph.py
lathe/geometry/capabilities.py
lathe/geometry/planner.py
lathe/geometry/attribute_mapping.py
lathe/geometry/prismatic.py
lathe/geometry/facet_field.py
lathe/geometry/polyhedron.py
lathe/geometry/feature_ops.py
```

Likely tests:

```text
tests/unit/test_geometry_op_graph.py
tests/unit/test_kernel_capabilities.py
tests/unit/test_attribute_mapping.py
tests/unit/test_prismatic_polyhedron.py
tests/unit/test_facet_field.py
tests/unit/test_asset_foundry_generator.py
tests/unit/test_lowpoly_fantasy_style_pack.py
tests/unit/test_foundry_runtime_cook.py
tests/integration/test_foundry_crystal_cluster.py
tests/integration/test_foundry_micro_diorama.py
```

---

## 26. Acceptance criteria for the entire Foundry phase

This phase is complete when:

1. Current `visible-geometry-kernel-sprint-0` has already produced a visible before/after improvement.
2. Foundry capability matrix exists and is honest.
3. `GeometryOpGraph` exists internally and preserves operation provenance.
4. Manifold lane is truthful, measured, and default where supported.
5. At least one hard-surface feature operation visibly improves the crate.
6. Prismatic/facet operators generate at least crystals and one faceted terrain/island patch.
7. At least three Golden Asset Set assets reach Level 5 game-ready status.
8. At least one asset family reaches Level 4 variant-family status.
9. Runtime asset cooking outputs render mesh + collision + semantic sockets + material zones.
10. Foundry diagnostics/certificates can explain quality gaps.
11. `.lthpkg` package fixtures exist for future `@lathe/three` work.
12. No public `.lth` syntax break occurred without explicit approval.
13. `lathe.shape.intent_mesh_handoff_v1` remains intact.
14. Unsupported/fallback/proxy claims are visible in reports.
15. A micro-diorama proves assets can compose coherently before high-level intent.

---

## 27. Strategic conclusion

Lathe's future is not merely a Three.js integration and not merely a procedural mesh generator.

The real wedge is:

```text
A programming language that can manufacture beautiful, semantic, game-ready stylized assets from code,
then assemble them into playable worlds,
then let intent direct that working builder.
```

The reason this document belongs between the current north star and `three.lth` is simple:

```text
The web surface should expose Lathe's truth, not compensate for its weakness.
```

The Foundry gives Lathe that truth.

The immediate path is:

```text
industrial crate visible proof
-> Foundry kernel/operation graph
-> Prismatic/FacetField stylized operators
-> Golden Asset Set
-> runtime asset cooking
-> .lthpkg evidence fixtures
-> @lathe/three / Lathe Web Studio
-> micro-scenes
-> Skyborne Village / floating fantasy world
-> intent-directed imagination loop
```

Quality before intent.  
Foundry before Forge.  
Builder before Dream.  
Real evidence before public magic.
