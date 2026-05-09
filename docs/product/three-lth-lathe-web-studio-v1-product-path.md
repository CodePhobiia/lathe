# three.lth / Lathe Web Studio V1 Product Path

Date: 2026-05-06
Status: Product direction memo and implementation sequencing guide
Source: Theyab/Icarus co-founder decision thread

## Decision

Build `@lathe/three` first. Do **not** fork Three.js first.

Public-facing brand options:

- `three.lth` for the Lathe-native browser 3D surface.
- `Lathe Web Studio` for the product shell.

Actual package name:

```text
@lathe/three
```

The strategic architecture is:

```text
Lathe Core
  -> Lathe IR / .lthpkg
  -> @lathe/three
  -> Lathe Web Viewer
  -> Lathe Playground / Studio
  -> Wonder visual repair loop
```

## Product Thesis

`three.lth` should mean:

> A browser-native semantic 3D layer that lets humans and AI generate, inspect, repair, and export Lathe-built assets.

It should **not** mean:

> A renamed Three.js fork.

Three.js provides the browser-native 3D foundation: scene graph, meshes, materials, cameras, renderers, loaders, examples, ecosystem, WebGL/WebGPU surface, and an existing editor reference. Lathe provides the semantic construction truth: assets, parts, operations, material zones, unsupported claims, diagnostics, evidence, and repair history.

The moat is the combination:

```text
Three.js: renderable 3D objects
Lathe: semantically constructed, inspectable, repairable 3D assets
```

## Strategic Rule

Three.js is the viewport and runtime frontend. Lathe remains the source of truth.

No fake quality:

- Do not hide weak geometry behind bloom, lighting, post-processing, or shader tricks.
- If Lathe claims `beveled panels`, the viewer must show real bevels or mark the claim as `unsupported`, `fallback`, `proxy`, or `not verified`.
- Preserve the northstar loop: `intent -> artifact -> evidence -> judgment -> repair -> better artifact`.

## Relationship To Current Lathe Northstar

This product path complements, but does not replace, `docs/asset-quality/lathe-implementation-northstar.md`.

Current implementation priority remains:

```text
visible-geometry-kernel-sprint-0
```

Reason: `@lathe/three` can make Lathe visible, inspectable, and shareable, but it cannot make bad geometry good. The first web demo must therefore be anchored to a real visible geometry improvement, preferably the existing `industrial_crate / sci-fi crate` fixture.

## V1 Stack

### 1. `.lthpkg`

A Lathe asset package should bundle compatible geometry plus Lathe semantic sidecars.

Proposed package layout:

```text
industrial_crate.lthpkg/
  asset.lth
  manifest.json
  mesh.glb
  semantic-index.json
  diagnostics.json
  materials.json
  evidence.json
  screenshots/
```

The `.glb` path gives broad compatibility. The sidecar JSON files preserve Lathe's actual advantage:

- semantic part IDs;
- face/triangle groups;
- source operation provenance;
- material intent and zones;
- unsupported or degraded claims;
- repair suggestions;
- export constraints;
- visual evidence;
- before/after repair history.

### 2. `@lathe/three`

The bridge package should expose a loader similar in spirit to Three.js loaders:

```ts
import { LatheLoader } from "@lathe/three";

const loader = new LatheLoader();
const result = await loader.load("/assets/industrial_crate.lthpkg");
scene.add(result.object3D);
```

Target return type:

```ts
type LatheThreeResult = {
  object3D: THREE.Object3D;
  semanticIndex: LatheSemanticIndex;
  diagnostics: LatheDiagnostics;
  materialZones: LatheMaterialZone[];
  provenance: LatheConstructionProvenance;
  exportEvidence: LatheEvidence;
};
```

Initial implementation should preserve semantic metadata using `Object3D.userData` and sidecar indices instead of modifying Three.js core.

### 3. Lathe Web Viewer

First visible product demo.

Required MVP features:

- drag/drop `.lthpkg`;
- orbit viewport;
- material view;
- wireframe view;
- normals view;
- semantic part picker;
- diagnostic overlay;
- before/after comparison;
- export to glTF/GLB;
- screenshot evidence capture.

### 4. Lathe Playground / Studio

Second product surface.

Recommended layout:

```text
+----------------------+------------------------+----------------------+
| .lth Editor           | Three.js Viewport      | Diagnostics / Repair |
|                      |                        |                      |
| asset crate { ... }   | Live generated object  | Missing bevels       |
|                      | Semantic selection     | Weak silhouette      |
|                      | Material zones         | Export warnings      |
+----------------------+------------------------+----------------------+
```

The Playground should let a user write or paste source such as:

```lth
asset industrial_crate {
  purpose "Roblox sci-fi storage crate"
  style "weathered industrial"
  feature allow panels vents trim_bands fasteners edge_wear
  material zones painted_metal rubber dark_trim exposed_steel
  budget mobile
}
```

Then the system compiles, renders, diagnoses, and suggests executable repairs.

### 5. Wonder Visual Repair Loop

Wonder should eventually use the web surface as its visual body:

```text
Wonder proposes or edits .lth
  -> Lathe compiles and packages
  -> @lathe/three renders and exposes semantic evidence
  -> diagnostics/vision critique identify weaknesses
  -> semantic patches are selected
  -> Lathe rebuilds
  -> viewer shows before/after evidence
```

## Fork Decision Tree

| Need | Fork Three.js? |
| --- | ---: |
| Load Lathe assets | No |
| Attach semantic metadata | No |
| Add inspector panels | No |
| Build standalone viewer | No |
| Build custom editor shell | Maybe fork editor |
| Deep semantic face picking | Maybe |
| Custom render/evidence pipeline | Maybe |
| Renderer-level Lathe material system | Maybe |
| Fundamental scene graph changes | Yes, but late |

Default position: stay upstream-compatible until a concrete limitation proves otherwise.

## MVP Demo

MVP asset:

```text
industrial sci-fi crate
```

Input:

```text
.lth source
```

Output:

```text
.lthpkg with mesh.glb + semantic sidecars + evidence
```

Viewer proof:

- browser viewport loads the asset;
- semantic inspector selects named parts;
- diagnostics panel reports truth checks;
- before/after view shows a repair improved visible quality;
- export path produces GLB or reports a truthful blocker.

Required truth checks for the first demo:

1. Missing bevels.
2. Non-manifold geometry.
3. Weak silhouette.
4. UV/material-zone mismatch.
5. Export budget violation.

Required repair button:

```text
Improve asset quality
```

The button should trigger at least one executable semantic repair path and generate a before/after visual comparison. If any part is proxy-only, the UI must label it as proxy.

## First Implementation Sequence

### Phase A: Preserve Package Evidence

Goal: make one Lathe build emit or assemble a `.lthpkg` directory without changing public `.lth` syntax.

Tasks:

1. Define `lthpkg` manifest schema.
2. Add semantic sidecar model for parts, operations, material zones, diagnostics, and evidence.
3. Add a package writer that can collect existing generated mesh/report/preview artifacts into the layout.
4. Add tests proving unsupported/fallback/proxy states survive into package metadata.
5. Run against the industrial crate fixture and record package paths.

### Phase B: Build `@lathe/three` Prototype

Goal: load a package into a browser-side Three.js scene while preserving semantics.

Tasks:

1. Create a TypeScript package boundary for `@lathe/three`.
2. Implement `LatheLoader.load(url)`.
3. Load `mesh.glb` via Three.js GLTF loading.
4. Attach package metadata to `Object3D.userData`.
5. Expose `semanticIndex`, `diagnostics`, `materialZones`, `provenance`, and `exportEvidence` in the loader result.
6. Add a fixture package and loader tests.

### Phase C: Build Lathe Web Viewer

Goal: create the first visible product surface.

Tasks:

1. Create viewer app shell.
2. Add drag/drop package import.
3. Add viewport, lighting, orbit controls, and camera framing.
4. Add mode toggles: material, wireframe, normals.
5. Add semantic picking and inspector panel.
6. Add diagnostics overlay and severity badges.
7. Add screenshot evidence capture.
8. Add before/after package comparison.

### Phase D: Connect Repair Loop

Goal: prove the northstar loop in the browser.

Tasks:

1. Map at least one visible diagnostic to an executable semantic patch.
2. Add `Improve asset quality` action.
3. Rebuild or load repaired package.
4. Show before/after visual diff.
5. Record repair provenance in package metadata.
6. Verify report metrics and visible evidence changed.

### Phase E: Playground / Studio

Goal: make Lathe authoring interactive.

Tasks:

1. Add `.lth` editor.
2. Add compile/build trigger.
3. Stream or display compiler diagnostics.
4. Load the generated package into the viewer.
5. Add repair suggestions.
6. Add export/download panel.

## Acceptance Criteria

The V1 path is proven when:

- `@lathe/three` loads a real `.lthpkg` package.
- The browser viewport displays the asset using real exported geometry, not only debug/proxy visuals.
- Semantic part selection works for at least the crate fixture.
- Diagnostics are visible and trace to package metadata.
- At least one repair action produces a before/after package pair.
- The UI truthfully labels unsupported, fallback, proxy, and not-verified claims.
- No Three.js fork is required for MVP.

## Non-Goals For V1

- Do not fork Three.js core.
- Do not create public `.lth` syntax only for the viewer.
- Do not claim Roblox/Unity/Unreal production readiness from browser preview alone.
- Do not hide weak Lathe geometry with renderer effects.
- Do not make the web viewer the source of truth; Lathe package evidence remains the source of truth.

## Strategic Conclusion

Build this.

`@lathe/three` is the fastest path to making Lathe visible, inspectable, shareable, and believable while keeping the hard-won Lathe northstar intact. Three.js gives Lathe a browser body. Lathe gives Three.js-native workflows semantic construction, evidence, and repair.

The result is not a Three.js clone. It is an AI-native 3D creation surface.
