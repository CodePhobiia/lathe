# Current Limitations

Last updated: 2026-04-29

Lathe can now run a deterministic Wonder seed path with proxy render/export
artifacts, but that path is not the same thing as Project Wonder alpha
readiness. The current implementation is best understood as a contract,
planning, package, proxy artifact, patch, repair, and curiosity evidence path
over JSON-first scene data.

## What The Demo Proves

`scripts/demo_wonder_seed_scene.ps1` passed locally against
`examples/wonder/alchemist_observatory/` on 2026-04-28. It proves that the
current CLI can:

- validate Dream Brief, Scene Graph, Scene Patch, Render Inspection, World
  Memory, Scene Plan, Scene Assembly, Repair Report, and Scene Package
  contracts;
- lower a Dream Brief into a deterministic fallback Scene Graph;
- generate a JSON-first scene source bridge and roundtrip it back to a Scene
  Graph;
- plan, assemble, build, and validate deterministic Scene Packages;
- write deterministic proxy PNG renders, declared proxy GLB exports, and
  requested proxy USDA layout exports into local output folders;
- render deterministic before/after proxy images after the `more_sacred` patch
  and compare them with a locked reveal camera;
- turn a Render Inspection contract into bounded repair proposals;
- apply the `more_sacred` semantic Scene Patch;
- expand the `opened_archive` curiosity option while preserving existing scene
  IDs.

## What The Demo Does Not Prove

The demo does not yet produce final engine-grade render or export artifacts. In
particular:

- no Blender process is launched;
- reveal and topdown images are deterministic proxy PNGs, not Blender renders;
- the before/after comparison is a deterministic proxy render comparison, not a
  Blender or external-viewer comparison;
- the Render Inspection file is a checked input contract, not a vision/evaluator
  product from the generated PNGs;
- the GLB and USDA files are deterministic proxy exports, while the Blender
  export path is explicit and sandboxed rather than part of the default demo;
- no external viewer has validated the generated export outputs;
- asset builds are represented by deterministic offline package records, not by
  generated meshes.

Those gates remain deferred until the scene render/export runtime can be
validated with final artifacts. The current proxy files are evidence of package
wiring, deterministic artifact creation, object identity, and manifest
validation; they are not yet a substitute for final Blender, USD, Roblox, or
external-viewer validation.

## Scene Source Boundary

The current source bridge is JSON-first. It emits reviewable scene source text
with an embedded Scene Graph JSON payload, then extracts that payload back into
Scene Graph JSON. This is useful for review and roundtrip evidence, but it is
not the final `.lth` scene grammar/parser integration.

Until the grammar lands, Scene Graph JSON remains the durable truth for Wonder
scene examples.

## Environment Coverage

PowerShell validation is available and passed locally for the demo path. POSIX
validation of `scripts/demo_wonder_seed_scene.sh` is still open because the
available local `bash` command routes to a WSL environment without `/bin/bash`.

The recommended-next-PR scope and Phase 0 baseline now have Git-backed
review-snapshot evidence. A fresh-clone or CI confirmation pass is still needed
before alpha promotion.

## Product Boundary

Lathe owns contracts, CLI/runtime evidence, validation, packages, reports, and
export artifacts. Project Wonder still owns product concerns such as chat UX,
accounts, galleries, payments, model routing, and cloud orchestration.
