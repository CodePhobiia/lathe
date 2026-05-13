# Lathe Frontier Geometry Kernel Research & Upgrade Roadmap

Date: 2026-05-06

> Supporting research memo for `docs/asset-quality/lathe-implementation-northstar.md`.
>
> This is **not** a detour from the current asset-quality north star. It is the deeper kernel thesis behind it: Lathe cannot become a state-of-the-art 3D asset machine until its geometry kernel can build, preserve, inspect, and repair real production-grade geometry.

---

## 0. Executive thesis

Theyab's read is correct: the geometry kernel is now one of Lathe's main bottlenecks.

Lathe already has a promising semantic engine: `.lth`, construction intent, ShapeIR, MeshIR, material zones, diagnostics, evidence, and a repair loop. But a frontier 3D asset system cannot stop at semantic labels. The kernel must turn those semantics into visible geometry that survives booleans, bevels, panel cuts, sockets, material-zone assignment, UVs, collisions, LODs, and export.

The upgrade target is **not merely “swap in Manifold”** and call it solved.

The upgrade target is:

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

A state-of-the-art Lathe asset should be able to prove:

1. what it intended to build;
2. which geometry operations were executed;
3. which backend produced each operation;
4. whether the result is watertight/manifold/valid;
5. where every part/material zone/feature landed on the mesh;
6. which claims are real, fallback, proxy, or unsupported;
7. how to repair weak geometry without throwing away the asset semantics.

That is the difference between a procedural asset generator and a true AI-native 3D construction engine.

---

## 1. Source evidence inspected

### Repo / Lathe evidence

- `docs/asset-quality/lathe-implementation-northstar.md`
- `docs/asset-quality/quality-diagnostics-v1.md`
- `docs/geometry_kernel_eval.md`
- `pyproject.toml`
- `lathe/geometry/kernel.py`
- `lathe/geometry/kernel_program.py`
- `lathe/geometry/shape_ir_lowering.py`
- `lathe/geometry/manifold_kernel.py`
- `lathe/geometry/reference_kernel.py`
- `lathe/adapters/manifold_kernel.py`
- `lathe/exact_solids.py`
- `lathe/shape_ir.py`
- `lathe/mesh_ir.py`
- `lathe/mesh_finalize.py`

### External references checked

- Manifold geometry library README: <https://github.com/elalish/manifold>
- Manifold raw README: <https://raw.githubusercontent.com/elalish/manifold/master/README.md>
- OpenUSD `UsdGeomMesh`: <https://openusd.org/release/api/class_usd_geom_mesh.html>
- OpenUSD `UsdGeomPrimvarsAPI`: <https://openusd.org/release/api/class_usd_geom_primvars_a_p_i.html>
- Houdini geometry attributes: <https://www.sidefx.com/docs/houdini/model/attributes.html>
- Blender Geometry Nodes attributes reference: <https://docs.blender.org/manual/en/latest/modeling/geometry_nodes/attributes_reference.html>
- Unreal Static Mesh docs: <https://dev.epicgames.com/documentation/en-us/unreal-engine/static-meshes>
- Unreal Nanite virtualized geometry docs: <https://dev.epicgames.com/documentation/en-us/unreal-engine/nanite-virtualized-geometry-in-unreal-engine>

### Existing internal benchmark signal

`docs/geometry_kernel_eval.md` already proves the first major point:

- current native SDF/voxel fusion can fail on dense mixed-primitive assemblies;
- Manifold lifted `courier_drone` from `0.00` watertight to `1.00` watertight;
- Manifold preserved already-healthy hero assets;
- Manifold was dramatically faster in the benchmark;
- recommendation was already **ADOPT** for `manifold3d` as the primary shape → topology solid kernel under `lathe.shape.intent_mesh_handoff_v1`.

So the next step is not deciding whether Manifold matters. It does.

The next step is deciding what **frontier kernel architecture** means beyond first-pass watertight booleans.

---

## 2. Current Lathe kernel architecture read

Lathe already has more kernel infrastructure than a toy generator.

### 2.1 Existing kernel registry

`lathe/geometry/kernel.py` defines a `GeometryKernel` protocol and registry.

Current stable surface includes:

```text
probe()
build_primitive(kind, **params)
from_trimesh(mesh)
union(a, b)
batch_union(meshes)
difference(a, b)
intersection(a, b)
hull(meshes)
transform(handle, matrix)
to_trimesh(handle)
is_watertight(handle)
body_count(handle)
```

Built-in kernels:

```text
lathe.geometry.manifold_v1
lathe.geometry.reference_v1
```

Selection precedence:

```text
LATHE_GEOMETRY_BACKEND env var
-> runtime_config["runtime"]["geometry"]["backend"]
-> default manifold when available, else reference
```

This is good. It means Lathe already has the beginning of a pluggable kernel architecture.

### 2.2 Existing kernel program layer

`lathe/geometry/kernel_program.py` defines an executable kernel-program seam with:

- `KernelOperand`;
- operation counts;
- capability errors;
- operation records;
- trace metadata;
- boolean/hull/minkowski/transform/import/instances program execution paths.

This is extremely important. It means Lathe is not just calling random mesh functions; it is moving toward an operation graph with provenance.

### 2.3 Existing Manifold adapter

`lathe/adapters/manifold_kernel.py` and `lathe/geometry/manifold_kernel.py` wrap `manifold3d` as a first-class kernel.

The adapter advertises support for:

- union;
- difference;
- intersection;
- hull;
- transform;
- batch union;
- primitive construction;
- from-trimesh import;
- watertight/body-count probes;
- several advanced primitive imports.

`pyproject.toml` already exposes:

```toml
[project.optional-dependencies]
geometry = [
  "scikit-image>=0.25",
  "manifold3d>=2.5",
]

[project.entry-points."lathe.geometry_kernels"]
"lathe.geometry.manifold_v1" = "lathe.geometry.manifold_kernel:manifold_kernel"
"lathe.geometry.reference_v1" = "lathe.geometry.reference_kernel:reference_kernel"
```

This is the right direction.

### 2.4 Existing fallback problem

`lathe/exact_solids.py` has honest fallback traces, but also still has degraded routes like:

```text
exact_boolean_fallback_clustered_union_omit_cutters
exact_boolean_fallback_concatenate
```

Those routes may be acceptable for early development, but they cannot pass as production-quality geometry.

A frontier kernel must make fallback states first-class:

```text
real_geometry
fallback_geometry
proxy_geometry
unsupported_claim
```

If a cutter was omitted, Lathe can still return a debug artifact — but certification and marketing claims must know that the asset is not geometrically faithful.

---

## 3. Root-cause diagnosis

Lathe's current problem is not only “the kernel is weak.”

The sharper diagnosis:

```text
Lathe's semantic language is ahead of its geometry-construction capability.
```

The system can talk about features like panels, bevels, trim, sockets, seams, material zones, and repair intent. But the kernel must consistently lower those concepts into real visible mesh operations.

The false-success state to eliminate:

```text
The report says “beveled panel / seated attachment / material zone / playable collision”
but the mesh or package does not visibly prove it.
```

This is the state that makes assets look like prototype/blockout geometry even when validation passes.

The standard should be **geometry capability parity**:

Every public or internal semantic promise must be one of:

1. **Buildable** — the kernel can produce real geometry for it.
2. **Lowerable** — the planner can decompose it into supported operations.
3. **Verifiably approximated** — the output is marked approximation/proxy with evidence.
4. **Rejected** — Lathe says unsupported and refuses to certify the claim.
5. **Not exposed yet** — syntax/product docs do not promise it until the kernel catches up.

---

## 4. What “frontier geometry kernel” should mean for Lathe

A frontier Lathe geometry kernel is not a single library.

It is a layered kernel stack with a semantic contract.

```text
.lth / intent
  ↓
Semantic Construction Graph
  ↓
Typed Geometry Operation Graph
  ↓
Capability Planner
  ↓
Backend Lanes
  - Solid CSG lane
  - Mesh feature/topology lane
  - Field/SDF/terrain lane
  - DCC/offline reference lane
  - Game-finalization lane
  ↓
MeshIR + semantic sidecars
  ↓
Diagnostics / Evidence / Repair
```

### Required properties

#### 1. Robustness

- deterministic output for fixed seeds;
- watertight where solidity is claimed;
- no silent non-manifold geometry;
- stable body-count semantics;
- exact or bounded-tolerance booleans;
- traceable fallback.

#### 2. Feature awareness

The kernel must know and preserve:

- parts;
- components;
- face/edge/vertex attributes;
- material zones;
- seam classes;
- hard-edge classes;
- bevel groups;
- panel regions;
- sockets/attachment seating;
- collision intent;
- LOD source relationships.

#### 3. Production asset operations

The kernel needs first-class support for asset-making operations, not only primitive union:

- bevel / chamfer / fillet;
- inset panels;
- panel-line cuts/grooves;
- rails / trim / ribs;
- vents / grilles / slats;
- sockets / brackets / seated attachments;
- repeated detail along surfaces;
- surface scatter constrained by semantic zones;
- weighted normals / hard-edge marking;
- remesh / decimate / reduce;
- UV seam planning hooks;
- collision proxy generation;
- LOD derivation.

#### 4. Attribute preservation

DCC and game tools are attribute-first.

Examples:

- Houdini stores attributes on vertices, points, primitives, and objects.
- OpenUSD primvars interpolate across primitive topology and can override shader inputs.
- Manifold supports arbitrary vertex properties and IDs for tracking materials/surfaces.

Lathe should adopt the same mindset: every geometry operation must either preserve, transform, split, merge, or explicitly drop semantic attributes.

The frontier kernel question is not just:

```text
Did the boolean succeed?
```

It is:

```text
Did the boolean succeed while preserving which faces belong to which semantic part, material, bevel, seam, socket, and repair history?
```

---

## 5. Backend candidate matrix

This matrix is intentionally practical. The goal is not to worship libraries. The goal is to assign each backend to the job it is best suited for.

| Backend / lane | Use it for | Strength | Risk / limitation | Lathe recommendation |
|---|---|---|---|---|
| **Manifold / manifold3d** | Primary solid CSG lane: watertight booleans, primitive fusion, batch union, hulls | Guaranteed manifold-output thesis; fast; Python/WASM paths; supports properties/IDs; already adopted in Lathe | Not a full DCC topology toolkit; fillet/bevel/panel operations still need Lathe-level feature logic | **Make it the default solid kernel. Do not ask it to be the entire asset kernel.** |
| **trimesh** | Mesh IO, analysis, repair helpers, simple fallback/reference path | Already used; Python-native; excellent utility layer | Booleans are backend-dependent; not enough for frontier production geometry alone | Keep as analysis/reference/glue, not source of truth for hard booleans. |
| **libigl-style mesh processing** | Remeshing, decimation, parameterization, topology algorithms, smoothing, distances | Strong geometry-processing toolbox | Python packaging/integration and license review required; not a semantic asset kernel by itself | Evaluate for mesh-feature and finalization lane. |
| **Blender / bmesh / Geometry Nodes** | Offline reference backend for bevels, modifiers, normals, UVs, baking, visual comparison | Mature artist/DCC operations; excellent hard-surface modifier stack | Headless dependency, determinism/versioning, slower than pure kernel path | Use as optional reference/golden backend, not mandatory core runtime. |
| **Houdini SOP-style model** | Architecture inspiration: procedural node graph + geometry attributes | Best-in-class procedural modeling mental model | Houdini itself is commercial/external; not core dependency | Copy the architectural pattern: typed op graph + attributes + diagnostics. |
| **OpenUSD** | Scene/package representation, composition, primvars, variants, asset hierarchy | Strong semantics/composition/primvar model | Not a geometry kernel; heavier than glTF for simple web preview | Use later as package/scene sidecar/export lane, especially for worlds/kits. |
| **OpenCascade / OCCT** | CAD/B-rep/NURBS/true fillets/industrial solids | Mature CAD kernel; real fillets and analytic surfaces | LGPL-style/legal review, heavier integration, mesh conversion complexity | Later optional CAD lane for analytic/industrial assets. Not Phase 1. |
| **CGAL** | Computational geometry algorithms, robust predicates, mesh ops | Deep geometry toolkit | License/package complexity; broad library, not turnkey asset kernel | Research-only/optional algorithm source unless a narrow need emerges. |
| **SDF / OpenVDB / dual contouring lane** | Organic terrain, stylized rocks, roots, floating islands, smooth blends | Great for organic forms and field-based operations | Can blur hard-surface semantics; marching-cubes artifacts if uncontrolled | Keep as a separate field lane, especially for later fantasy-world terrain. |
| **xatlas / UV tools** | UV unwrapping and charting | Already in project optional deps | Only works well after topology/parts are sane | Keep, but feed it better part/seam/material attributes. |

### Key decision

Lathe should become **multi-kernel**, not mono-kernel.

```text
Manifold = solid truth
Mesh feature kernel = production hard-surface operations
SDF/field lane = organic/fantasy terrain and soft blends
DCC lane = offline reference/golden evidence
OpenUSD/glTF lane = package/export semantics
```

---

## 6. Game/DCC pipeline lessons for Lathe

### 6.1 Game assets are not just meshes

A production game asset is a bundle of geometry plus downstream usability:

- render mesh;
- material assignments;
- UVs;
- normals/tangents;
- collision;
- LODs;
- pivots/origin;
- scale/unit conventions;
- import metadata;
- engine constraints;
- evidence previews.

For Lathe, “asset quality” must include kernel outputs that make those stages reliable.

### 6.2 Attributes are a first-class modeling concept

Houdini and OpenUSD both reinforce the same principle: geometry is not just vertex positions and triangle indices. It carries attributes/primvars over topology.

Lathe's equivalent should be explicit:

```text
Face attributes:
- part_id
- component
- material_zone
- operation_id
- semantic_feature
- source_primitive
- bevel_group
- panel_group
- collision_role
- lod_role

Edge attributes:
- seam_class
- hard_edge_class
- bevel_weight
- support_loop_role
- uv_seam_candidate

Vertex attributes:
- source_ids
- normals/tangents
- color/material helper data
- deformation/scatter metadata when needed
```

Every geometry operation should output an attribute mapping report:

```json
{
  "operation_id": "op.panel_inset.body.front_01",
  "backend": "lathe.geometry.manifold_v2",
  "attributes_preserved": ["part_id", "material_zone"],
  "attributes_split": ["face_id"],
  "attributes_dropped": [],
  "new_regions": ["front_panel_inner", "front_panel_bevel_ring"]
}
```

### 6.3 High detail does not remove the need for structure

Unreal's Nanite direction proves that engines can handle far more triangles than older pipelines, but it does not remove the need for:

- clean authored meshes;
- materials;
- collision;
- pivots;
- LOD/proxy decisions for non-Nanite targets;
- semantic package data.

For Lathe, this means:

```text
more triangles != better asset
```

Better asset = intentional geometry hierarchy + correct finalization.

### 6.4 Procedural DCC tools are operation graphs, not one-shot mesh dumps

Houdini SOPs and Blender Geometry Nodes are powerful because they preserve an editable graph of operations and attributes.

Lathe should internalize this:

```text
A Lathe asset should remain a repairable semantic operation graph until final export.
```

The mesh is evidence and runtime output. The construction graph is the source of truth.

---

## 7. Proposed Lathe kernel architecture

### 7.1 New internal artifact: `GeometryOpGraph`

Do not change `.lth` public syntax yet.

Add an internal typed graph between ShapeIR and backend execution:

```text
ShapeIR
  ↓
GeometryOpGraph v1
  ↓
Kernel planner
  ↓
Backend lanes
```

A node should include:

```json
{
  "operation_id": "op.crate.front_panel.inset_01",
  "op": "panel.inset",
  "semantic_part": "front_panel",
  "inputs": ["body_shell"],
  "params": {
    "depth": 0.08,
    "bevel_radius": 0.025,
    "margin": 0.12
  },
  "required_capabilities": [
    "solid.boolean.difference",
    "mesh.bevel.edge_group",
    "attributes.face_region_preservation"
  ],
  "fallback_policy": "fail_certification_if_missing",
  "evidence_requirements": [
    "visible_depth",
    "bevel_ring_faces",
    "material_zone_inner_panel"
  ]
}
```

### 7.2 Capability Planner

The planner chooses backends by operation type and required guarantees.

Example:

```text
box/cylinder/sphere solid fusion      -> Manifold lane
panel groove subtract                 -> Manifold lane + attribute remap
bevel ring generation                 -> mesh feature lane
organic rock / floating island field  -> SDF/field lane
UV unwrap                             -> xatlas lane
collision proxy                       -> game-finalization lane
reference render / bake               -> Blender optional lane
```

If a backend cannot satisfy required capabilities, the planner must emit:

```text
unsupported_capability
```

not silently degrade into fake geometry.

### 7.3 Feature-aware mesh kernel

Manifold solves solid reliability. It does not by itself solve artist-level mesh feature construction.

Lathe needs a mesh feature kernel with operations like:

```text
mesh.bevel.edge_group
mesh.inset.face_region
mesh.panel_groove.region
mesh.trim_along_path
mesh.slats_in_region
mesh.socket_cut_and_bracket
mesh.weighted_normals
mesh.support_loop
mesh.mark_hard_edges
mesh.decimate_preserve_features
mesh.generate_collision_proxy
mesh.generate_lod_chain
```

This can be built incrementally over existing code, with optional helper backends later.

### 7.4 Attribute propagation contract

Every op must declare what happens to semantics.

Required output per operation:

```text
attribute_mapping:
  preserved: [...]
  transformed: [...]
  split: [...]
  merged: [...]
  generated: [...]
  dropped: [...]
```

If `material_zone` or `part_id` gets dropped during a boolean/bevel/remesh, that must become a diagnostic finding.

### 7.5 Evidence hooks

Each feature operation needs an evidence contract.

Examples:

| Semantic claim | Required visible/kernel evidence |
|---|---|
| `beveled panel` | bevel ring faces exist; bevel radius above min threshold; normals/hard edges marked; panel depth measurable |
| `vent slats` | repeated slat geometry count; spacing regularity; material zone assigned; not just texture/decal |
| `socketed attachment` | receiver cut/seat exists; attachment intersects/aligns within tolerance; bracket/fastener evidence exists |
| `hard-surface crate` | primary/secondary/tertiary hierarchy; panel intentionality; edge treatment; material zones; no random triangulation |
| `game-ready asset` | UVs, collision, LOD/proxy policy, pivot/scale, engine import package, manifest |

---

## 8. Upgrade phases

The phases below are designed to fit the current sequence:

```text
1. Finish asset-quality north star / visible-geometry-kernel-sprint-0
2. Then three.lth / @lathe/three / Lathe Web Studio
3. Then Floating Fantasy World North Star
```

This roadmap belongs mainly to step 1.

---

### Phase K0 — Capability matrix and no-fake-quality gate

**Goal:** Make Lathe explicitly know what its kernel can and cannot build.

**Create:**

```text
docs/asset-quality/kernel-capability-parity-matrix.md
```

**Implement:**

- kernel capability probe schema;
- capability parity matrix for current `.lth`/ShapeIR claims;
- diagnostics that flag semantic claims with no geometric evidence;
- certification rule: degraded/proxy/fallback geometry cannot pass as production proof.

**Acceptance:**

- a claimed feature can be traced to a real operation or marked unsupported;
- fallback modes like cutter omission are visible in the report;
- diagnostics do not block Phase 1 initially unless wired into certification later;
- no `.lth` syntax changes.

---

### Phase K1 — Manifold as the solid truth lane

**Goal:** Finish the already-started Manifold adoption as the primary solid CSG path.

**Touch likely files:**

```text
lathe/geometry/kernel.py
lathe/geometry/kernel_program.py
lathe/geometry/shape_ir_lowering.py
lathe/geometry/manifold_kernel.py
lathe/adapters/manifold_kernel.py
lathe/exact_solids.py
tests/unit/test_manifold_adapter.py
tests/golden/test_geometry_fixtures.py
tests/integration/test_manifold_hero_watertight.py
```

**Implement:**

- ensure `lathe.geometry.manifold_v1` is default when available;
- record backend choice in every asset report;
- refuse silent cutter omission for certified assets;
- expose boolean backend chain in diagnostics;
- cache deterministic Manifold results;
- improve face-part assignment on multi-body Manifold output;
- preserve body separation where semantically correct.

**Acceptance:**

- industrial sci-fi crate hard-surface benchmark uses Manifold for solid booleans;
- watertightness is measured;
- body count is stable;
- no fallback is hidden;
- any fallback causes an explicit quality diagnostic.

---

### Phase K2 — Semantic feature operation graph

**Goal:** Move from primitive assembly to asset-making operations.

**Create likely files:**

```text
lathe/geometry/op_graph.py
lathe/geometry/capabilities.py
lathe/geometry/planner.py
lathe/geometry/attribute_mapping.py
tests/unit/test_geometry_op_graph.py
tests/unit/test_kernel_capabilities.py
tests/unit/test_attribute_mapping.py
```

**Initial operation vocabulary:**

```text
solid.primitive.box
solid.primitive.cylinder
solid.boolean.union
solid.boolean.difference
solid.boolean.intersection
solid.hull.convex
mesh.feature.bevel_edges
mesh.feature.panel_inset
mesh.feature.panel_groove
mesh.feature.trim_band
mesh.feature.vent_slats
mesh.feature.fastener_grid
mesh.normals.weighted
mesh.edge.mark_hard
mesh.finalize.collision_proxy
mesh.finalize.lod_chain
```

**Acceptance:**

- every operation has an `operation_id`;
- every operation has `required_capabilities`;
- unsupported capabilities fail honestly;
- operation traces survive into diagnostics and package metadata.

---

### Phase K3 — Real bevels, insets, panel cuts, and attachment seating

**Goal:** Attack the visible quality bottleneck directly.

This is the phase that makes the asset stop looking like a blockout.

**Implement first for the industrial sci-fi crate:**

1. real bevels/chamfers on body edges;
2. inset panel geometry with measurable depth;
3. panel-line grooves as real cuts or extrusions;
4. trim bands with distinct material zones;
5. vent/slat geometry as real repeated forms;
6. fastener grids with actual sockets or raised heads;
7. attachment seating checks.

**Acceptance metrics:**

```text
bevel_ring_face_count > 0
panel_depth_measured >= threshold
material_zone_face_coverage >= threshold
attachment_seating_quality >= threshold
random_triangulation_penalty <= threshold
fallback_geometry_count == 0 for certified asset
```

---

### Phase K4 — High/low production path

**Goal:** Make Lathe output game-asset packages, not just single render meshes.

**Implement:**

- high-detail source mesh path;
- low/runtime mesh path;
- normal/AO/curvature/material-ID bake evidence;
- LOD generation;
- collision proxy generation;
- UV seam/material-zone aware unwrap;
- pivot/scale/unit verification.

**Acceptance:**

- package contains high/source and low/runtime outputs where claimed;
- baked maps are derived from real geometry, not report text;
- collision exists and matches declared role;
- LODs reduce complexity while preserving silhouette/semantic features.

---

### Phase K5 — Field/SDF lane for organic/fantasy geometry

**Goal:** Prepare the later fantasy-world push without distracting Phase 1.

This lane matters for:

- rocks;
- floating islands;
- terrain chunks;
- roots;
- crystals;
- clouds/mist proxies;
- smooth organic blends.

**Guardrail:**

SDF/field geometry must not blur hard-surface assets where crisp bevels/panels are required.

**Acceptance:**

- field-generated assets are marked as field lane;
- terrain/rock output has clean material zones and collision proxies;
- hard-surface crates still use Manifold + mesh feature lane.

---

### Phase K6 — DCC reference backend

**Goal:** Use Blender/Houdini-style operations as reference evidence, not core dependency.

**Implement optional path:**

```text
Lathe op graph -> Blender headless script -> reference mesh/evidence
```

Use it to compare:

- bevel quality;
- weighted normals;
- material assignment;
- UVs;
- bake outputs;
- preview screenshots.

**Acceptance:**

- DCC backend is optional;
- core tests do not require Blender;
- reference backend can generate evidence for selected golden assets;
- divergence between core kernel and DCC reference becomes an actionable diagnostic.

---

## 9. Immediate implementation order inside the current north star

Because the active work is still `docs/asset-quality/lathe-implementation-northstar.md`, the next implementation should be deliberately narrow.

Recommended order:

```text
1. Add kernel capability parity diagnostics.
2. Tighten fallback reporting: no hidden cutter omission / concatenate pass.
3. Make Manifold lane the default solid proof path where available.
4. Add operation evidence for real bevel/panel/trim features.
5. Add the first industrial sci-fi crate geometry-kernel benchmark.
6. Only then broaden into high/low bake, DCC reference, or world terrain.
```

### First benchmark asset

Use the current preferred hard-surface proof:

```text
industrial sci-fi crate
```

Why this is the right first target:

- stresses hard edges;
- stresses bevels;
- stresses inset panels;
- stresses material zones;
- stresses vents/slats/fasteners;
- does not require world-scale composition;
- directly reveals whether the kernel can produce production-like geometry.

---

## 10. Concrete acceptance checklist for the first crate proof

A generated crate is not accepted merely because it exports.

It should pass these visible/kernel checks:

### Solid validity

- [ ] output mesh is watertight where solid is claimed;
- [ ] body count is deterministic;
- [ ] no non-manifold edges in certified geometry;
- [ ] no hidden concatenate/cutter-omit fallback;
- [ ] boolean backend chain is recorded.

### Feature reality

- [ ] bevels are real geometry, not only normals/shading;
- [ ] panel insets have measurable depth;
- [ ] trim bands are separate semantic/material regions;
- [ ] vents/slats are actual geometry or explicitly marked decal/proxy;
- [ ] fasteners have seating/attachment evidence;
- [ ] material-zone faces exist and cover expected regions.

### Game readiness

- [ ] UVs exist and are valid;
- [ ] collision proxy exists if game-ready is claimed;
- [ ] LOD/proxy policy is declared;
- [ ] pivot/scale is verified;
- [ ] package manifest records geometry/evidence/diagnostics.

### No-fake-quality

- [ ] bloom/post-processing/lighting is not used to hide weak geometry;
- [ ] fallback/proxy features cannot count as certified production features;
- [ ] every semantic claim links to operation evidence or an unsupported finding.

---

## 11. Suggested docs/tasks to create next

### 11.1 Kernel capability parity matrix

Create:

```text
docs/asset-quality/kernel-capability-parity-matrix.md
```

Include columns:

```text
Semantic claim
Current source/IR field
Required geometry operation
Required backend capability
Current status
Evidence required
Fallback policy
Certification impact
```

Example rows:

| Semantic claim | Required capability | Status standard |
|---|---|---|
| beveled panel | bevel edge group + inset region + material-zone preservation | must produce visible bevel ring faces or mark unsupported |
| vent slats | repeated geometry in bounded region | geometry/decal distinction must be explicit |
| socketed attachment | cut/receiver/seat alignment | must measure seating overlap/tolerance |
| hard-surface trim | trim band mesh + material zone | must preserve face attributes through boolean/finalize |
| playable collision | collision proxy generation/export | metadata-only collision claim fails |

### 11.2 Kernel op graph spec

Create:

```text
docs/asset-quality/geometry-op-graph-v1.md
```

Define:

- operation schema;
- capability schema;
- attribute propagation contract;
- fallback/degradation contract;
- evidence hooks;
- first operation vocabulary.

### 11.3 Industrial crate kernel benchmark

Create:

```text
docs/asset-quality/industrial-sci-fi-crate-kernel-benchmark.md
```

Define:

- visual target;
- required operations;
- metrics;
- fixtures;
- acceptance thresholds;
- screenshots/evidence package.

---

## 12. Immediate Codex / Claude Code prompt candidate

```text
We are in /mnt/d/lathe_v0_1.

Current priority: implement docs/asset-quality/lathe-implementation-northstar.md without changing .lth syntax or lathe.shape.intent_mesh_handoff_v1.

Task: Add Phase K0 kernel capability parity diagnostics for Lathe's geometry kernel.

Read:
- docs/asset-quality/lathe-implementation-northstar.md
- docs/asset-quality/lathe-frontier-geometry-kernel-roadmap.md
- docs/geometry_kernel_eval.md
- lathe/geometry/kernel.py
- lathe/geometry/kernel_program.py
- lathe/geometry/shape_ir_lowering.py
- lathe/exact_solids.py
- lathe/shape_ir.py
- lathe/mesh_finalize.py

Implement narrowly:
1. Add a non-blocking diagnostic payload that reports geometry backend capability parity for current ShapeIR/operation claims.
2. Detect fallback/degraded geometry states from existing boolean/finalization reports, including cutter omission and concatenate fallback.
3. Emit findings/warnings/recommendations but keep certification weight at 0.0 in Phase 1.
4. Do not change public .lth syntax.
5. Do not change lathe.shape.intent_mesh_handoff_v1.
6. Add targeted tests proving unsupported/degraded geometry is reported honestly.

Acceptance:
- tests pass for the new diagnostic;
- existing geometry kernel behavior is not rewritten;
- reports show backend, route, capability/fallback state, and certification impact;
- no semantic feature can silently pass as real geometry when the backend omitted/approximated it.
```

---

## 13. Strategic conclusion

Lathe should aim higher than “a procedural mesh generator.”

The real target is:

```text
AI-native semantic geometry construction.
```

That means the kernel must become the place where semantics become visible truth.

The right architecture is:

```text
Lathe semantic graph = source of truth
Manifold = robust solid CSG lane
Mesh feature kernel = hard-surface production operations
SDF/field lane = organic/world geometry
DCC reference lane = optional quality benchmark
Game-finalization lane = UV/collision/LOD/export proof
three.lth = later browser evidence/inspection surface
```

So yes: the kernel is holding Lathe back — but the fix is bigger and more powerful than one dependency.

The fix is to make Lathe's geometry kernel a **capability-aware, attribute-preserving, evidence-producing construction engine**.

That is the path from prototype assets to a state-of-the-art 3D asset machine.
