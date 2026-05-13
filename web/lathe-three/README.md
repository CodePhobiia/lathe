# @lathe/three

Lathe-native semantic 3D inspection layer over Three.js.

`@lathe/three` is the bridge between Lathe's deterministic asset
compiler/runtime and a browser viewer. It loads `.lthpkg` packages
produced by `lathe.asset_foundry.package_writer` and decorates a
Three.js `Object3D` with the Foundry's semantic sidecars (parts,
material slots, sockets, operation provenance, diagnostics, quality
certificate, runtime evidence).

## Design rules

1. **No Three.js fork.** We import zero from `three`. Consumers pass
   their own GLTF loader + Object3D factory; we attach metadata via
   `userData`.
2. **Lathe is the source of truth.** `@lathe/three` does not invent
   semantics. Everything in `userData.lathe` came from a `.lthpkg`
   sidecar Lathe authored.
3. **No fake quality.** When `mesh.glb` is unbuilt, the loader
   produces a clearly-labeled proxy `Object3D` and surfaces the
   `meshUnbuiltReason` so the viewer's diagnostics panel can show it.

## Usage

```ts
import { LatheLoader } from "@lathe/three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { Group } from "three";

const loader = new LatheLoader({
  gltfLoader: new GLTFLoader(),
  proxyObject3DFactory: () => new Group(),
});

const result = await loader.load("/assets/violet_crystal_cluster_a.lthpkg");
scene.add(result.object3D);

// Inspect the semantic sidecars.
console.log(result.semanticIndex.semantic_parts);
console.log(result.diagnostics.capability_matrix.counts_by_status);
console.log(result.evidence.certificate.achieved_level);
```

## `.lthpkg` layout

```text
violet_crystal_cluster_a.lthpkg/
  manifest.json              top-level manifest
  semantic-index.json        parts + sockets + material slots + bbox
  materials.json             material slot list
  operations.json            generator parameters + op graph + plan
  diagnostics.json           capability matrix slice + findings
  evidence.json              runtime manifest + certificate
  runtime.json               cooked runtime artifact manifest
  mesh.glb                   (optional) the render mesh
  previews/                  (optional) turntable.png, wireframe.png, etc.
```

## Contract versions

This package is pinned to `lathe.asset_foundry.lthpkg_v1`. When the
Python Foundry's package writer bumps the contract version, this
package must bump in lockstep.

## Status

`v0.1.0` — minimal loader + parsers + types. Real GLTFLoader
integration depends on the consumer's three.js version.
