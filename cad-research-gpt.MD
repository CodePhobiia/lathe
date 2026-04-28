# CAD Harness Research Findings For Lathe

Prepared by: GPT/Codex
Research date: 2026-04-24
External repo: https://github.com/earthtojake/text-to-cad
External commit inspected: `710655f`
Local research clone: `%TEMP%\lathe_repo_research\text-to-cad`
Target repo: `D:\lathe_v0_1`

## Executive Summary

`earthtojake/text-to-cad` is not a direct competitor to Lathe's language/compiler thesis. It is a compact, agent-oriented CAD harness with a very good interaction loop:

1. Source-controlled generator files or imported CAD files are the source of truth.
2. Explicit generation tools produce STEP/STL/DXF/GLB/URDF outputs.
3. Generated package-local topology sidecars make geometry addressable.
4. A local web viewer discovers artifacts and lets users copy stable `@cad[...]` refs.
5. Agents can inspect those refs, resolve face/edge/corner facts, and make precise follow-up edits.

The core lesson for Lathe:

> Lathe already makes assets declarative and certifiable. It should also make every generated asset addressable in conversation.

Lathe should not copy text-to-cad's Python-generator-first architecture. Lathe should copy the workflow primitives: stable refs, selector sidecars, ref inspection, aligned snapshots, local viewer, explicit target generation, source-of-truth discipline, and agent skill distribution.

## Repository Development Status Of text-to-cad

### Current Stage

Core logic partially implemented. It is a usable local harness and viewer with strong agent workflow ideas, but it is not production-hardened: no CI found, no release process, no real bundled model corpus, and some tooling has current Node/Python friction.

### System Map

- Frontend: React 18, Vite 7, three.js local CAD Explorer under `viewer/`.
- Backend/API: none; Vite middleware scans and serves local CAD artifacts.
- CAD runtime: Python scripts using `build123d`, OCP/OpenCascade, `ezdxf`, `numpy`, `trimesh`, and `vtk`.
- Robot runtime: Python URDF scripts using `yourdfpy`.
- Database: none.
- Auth: none.
- Persistence: browser `sessionStorage` and `localStorage`.
- CI: no `.github` directory found in the inspected clone.

### What Is Fully Implemented

- Agent-facing product loop:
  - `README.md:29-34` lists generate, export, browse, reference, review, reproduce, local.
  - `README.md:44-51` defines describe -> edit -> regenerate -> inspect -> reference -> commit.
- Agent workflow policy:
  - `AGENTS.md:42-47` says generated CAD/URDF outputs are derived and should not be hand-edited.
  - `AGENTS.md:51-53` says screenshots are supporting context and `@cad[...]` refs are stable handles.
- CAD skill:
  - `skills/cad/SKILL.md:10-20` defines workflow for file-targeted STEP/STL/DXF/GLB/topology/snapshot work.
  - `skills/cad/SKILL.md:32` states command interfaces are target-explicit.
- Generator contract:
  - `skills/cad/references/generator-contract.md:7-22` defines zero-argument `gen_step()` envelopes and deterministic generator rules.
  - `skills/cad/references/generator-contract.md:92-104` documents Y-up/meters GLB/viewer pipeline.
  - `skills/cad/references/generator-contract.md:108-118` documents package-local generated artifacts.
- Static generator metadata parsing:
  - `skills/cad/scripts/common/metadata.py:154` -> `parse_generator_metadata`.
  - `skills/cad/scripts/common/metadata.py:376` -> `_parse_literal_return_envelope`.
  - `skills/cad/scripts/common/metadata.py:401` -> `_reject_unsupported_fields`.
  - `skills/cad/scripts/common/metadata.py:433` -> `_parse_path_field`.
- Target-explicit generation:
  - `skills/cad/scripts/common/generation.py:845` -> `generate_step_part_targets`.
  - `skills/cad/scripts/common/generation.py:868` -> `generate_step_assembly_targets`.
  - `skills/cad/scripts/common/generation.py:891` -> `generate_dxf_targets`.
  - `skills/cad/scripts/common/generation.py:904` -> `generate_urdf_targets`.
  - `skills/cad/scripts/common/generation.py:1017` -> `run_tool_cli`.
- Topology sidecars:
  - `skills/cad/scripts/common/step_scene.py:1228` -> `extract_selectors_from_scene`.
  - `skills/cad/scripts/common/step_scene.py:1698` emits selector manifest schema version.
  - `skills/cad/scripts/common/step_scene.py:1714-1716` emits faces, edges, vertices.
  - `skills/cad/scripts/common/step_scene.py:1791` -> `write_selector_artifacts`.
- Ref-aware inspection:
  - `skills/cad/references/prompt-refs.md:16-27` defines `@cad[...]` token shapes.
  - `skills/cad/scripts/cadref/cli.py:118` -> `run_inspect`.
  - `skills/cad/scripts/cadref/cli.py:150` -> `run_planes`.
  - `skills/cad/scripts/cadref/cli.py:172` -> `run_diff`.
- Local viewer:
  - `viewer/README.md:7-14` documents prompt workflow and `@cad[...]` refs.
  - `viewer/README.md:17-31` documents data model for STEP/STL/DXF/URDF entries.
  - `viewer/vite.config.mjs:103` -> `cadCatalogPlugin`.
  - `viewer/vite.config.mjs:163` configures dev middleware.
  - `viewer/lib/cadDirectoryScanner.mjs:216` -> `scanCadDirectory`.
  - `viewer/lib/cadDirectoryScanner.mjs:252` -> `isServedCadAsset`.
  - `viewer/lib/renderAssetClient.js:159` -> `loadRenderSelectorBundle`.
- Viewer ref grammar:
  - `viewer/lib/cadRefs.js:157` -> `parseCadRefToken`.
  - `viewer/lib/cadRefs.js:173` -> `buildCadRefToken`.
- Viewer picking:
  - `viewer/components/viewer/hooks/useViewerPicking.js:149` -> `faceMatchAtPoint`.
  - `viewer/components/viewer/hooks/useViewerPicking.js:301` -> `findBestFaceReference`.
- URDF validation:
  - `skills/urdf/scripts/urdf_source.py:45` -> `read_urdf_source`.
  - `skills/urdf/scripts/urdf_source.py:193` -> `_validate_with_yourdfpy`.

### What Is Partially Implemented Or Risky

- The viewer is featureful but has very large components:
  - `viewer/components/CadViewer.js` is about 5208 lines.
  - `viewer/components/CadWorkspace.js` is about 3310 lines.
- `viewer/package.json:9` uses `node --test --experimental-default-type=module`, which fails on Node 24.
- Node tests pass when that deprecated/rejected flag is removed, but the package script itself fails on the tested Node version.
- Python tests require manual `PYTHONPATH` setup and CAD dependencies. Direct system pytest failed before the CAD stack was installed.
- `models/` only contains `README.md`, so the repo demonstrates the harness pattern more than a real production asset corpus.
- No `.github` workflows were present in the clone, so CI status is not established.
- There is no backend service, hosted artifact registry, or release/packaging process in the inspected repo.

## Validation Performed On text-to-cad

Commands run in the local temp clone:

```powershell
git clone https://github.com/earthtojake/text-to-cad %TEMP%\lathe_repo_research\text-to-cad
git log --oneline --decorate --max-count=12
```

Result: inspected commit `710655f`.

```powershell
cd viewer
npm ci
```

Result: passed, 161 packages installed, 0 vulnerabilities reported.

```powershell
npm run build:app
```

Result: passed. Vite production verification build completed.

```powershell
npm run test:node
```

Result: failed because Node 24 rejects `--experimental-default-type=module`.

```powershell
node --test lib/perspective.test.js lib/lookSettings.test.js lib/urdf/parseUrdf.test.js lib/urdf/kinematics.test.js lib/dxf/parseDxf.test.js lib/workbench/sidebar.test.js lib/cadDirectoryScanner.test.mjs lib/viewer/sceneScale.test.js components/viewer/hooks/useViewerPicking.test.js lib/assembly/meshData.test.js lib/selectors/runtime.test.js lib/async/concurrency.test.js lib/clipboard.test.js
```

Result: passed, 46 tests.

```powershell
python -m pytest -q skills/cad/scripts/common/tests/test_generation.py skills/urdf/scripts/tests/test_urdf_source.py
```

Result: failed during collection because script modules were not on `PYTHONPATH`.

```powershell
$env:PYTHONPATH = "skills/cad/scripts;skills/urdf/scripts"
python -m pytest -q skills/cad/scripts/common/tests/test_generation.py skills/urdf/scripts/tests/test_urdf_source.py
```

Result: failed because `ezdxf` was not installed in the ambient Python environment.

## The Big Ideas Lathe Should Take

### 1. Conversational Geometry References

text-to-cad's most important invention is not its CAD generation. It is the `@cad[...]` reference system.

Current `@cad[...]` examples:

- Whole entry: `@cad[models/path/to/entry]`
- Occurrence: `@cad[models/path/to/entry#o1.2]`
- Shape/body: `@cad[models/path/to/entry#o1.2.s3]`
- Face: `@cad[models/path/to/entry#o1.2.f12]`
- Edge: `@cad[models/path/to/entry#o1.2.e7]`
- Corner/vertex: `@cad[models/path/to/entry#o1.2.v4]`
- Grouped selectors: `@cad[models/path/to/entry#o1.2.f12,f13,e7,v4]`

Why it matters:

- Humans can point at exact geometry without vague language.
- Agents can resolve refs into facts before editing.
- Viewer selections become prompt-ready.
- Follow-up edits become anchored to source geometry, not screenshots.

Lathe equivalent:

```text
@lathe[examples/courier_drone.lth#asset.courier_drone]
@lathe[examples/courier_drone.lth#variant.courier_drone_mobile]
@lathe[build/courier_drone#part.body_shell]
@lathe[build/courier_drone#part.engine_mount.face12]
@lathe[build/courier_drone#socket.payload_mount]
@lathe[build/courier_drone#collision.hull3]
@lathe[build/courier_drone#lod1.part.body_shell]
@lathe[build/courier_drone#material.brushed_metal]
@lathe[build/courier_drone#diagnostic.semantic.fragmentation_penalty]
```

Recommended Lathe integration:

- Add a `lathe/ref.py` module for token parsing, normalization, and resolution.
- Add CLI:
  - `lathe ref parse`
  - `lathe ref inspect`
  - `lathe ref planes`
  - `lathe ref diff`
  - `lathe ref copy`
- Add viewer copy buttons for every selectable object.
- Include refs in validation diagnostics and HTML reports.

### 2. Selector Sidecars As A Public Artifact

text-to-cad writes package-local sidecars:

```text
.<step-filename>/model.glb
.<step-filename>/topology.json
.<step-filename>/topology.bin
```

The JSON contains high-level tables and metadata. The binary file contains compact proxy geometry and relation arrays.

Why it matters:

- The viewer can pick faces/edges/corners without reading source STEP repeatedly.
- Agents can inspect stable selector facts.
- Artifacts are local to the generated model.
- Ref resolution is deterministic and explainable.

Lathe equivalent:

```text
<build>/<asset>/
  manifest.json
  build_report.json
  report.html
  package/
    asset.glb
    asset.usda
  refs/
    selectors.json
    selectors.bin
  snapshots/
    isometric.png
    front.png
```

Recommended Lathe selector manifest:

```json
{
  "schemaVersion": 1,
  "latheVersion": "0.1",
  "sourcePath": "examples/courier_drone.lth",
  "asset": "courier_drone",
  "variant": null,
  "buildHash": "...",
  "packageHash": "...",
  "coordinateSystem": {
    "upAxis": "Y",
    "unit": "meter"
  },
  "tables": {
    "partColumns": ["id", "name", "role", "bbox", "meshRange"],
    "faceColumns": ["id", "partId", "surfaceType", "area", "normal", "bbox"],
    "edgeColumns": ["id", "partId", "curveType", "length", "bbox"],
    "socketColumns": ["id", "partId", "origin", "axis", "kind"],
    "collisionColumns": ["id", "partId", "kind", "bbox", "volume"],
    "lodColumns": ["id", "sourcePartId", "level", "triangleCount"]
  },
  "parts": [],
  "faces": [],
  "edges": [],
  "vertices": [],
  "sockets": [],
  "pivots": [],
  "collisions": [],
  "lods": [],
  "materials": [],
  "diagnostics": [],
  "relations": {},
  "buffers": {
    "uri": "selectors.bin",
    "littleEndian": true,
    "views": {}
  }
}
```

Implementation landing spots in Lathe:

- `lathe/selector_manifest.py`: schema and writer.
- `lathe/selector_extract.py`: extract selectors from internal mesh/part graph.
- `lathe/ref.py`: resolve `@lathe[...]` tokens against selector manifests.
- `lathe/executor.py`: write selector artifacts after topology/optimize/validate.
- `schema/lathe.selector.schema.json`: validate selector sidecars.
- `docs/refs.md`: public ref grammar.

### 3. Ref-Aware Inspect, Planes, And Diff

text-to-cad has:

- `cadref inspect`
- `cadref planes`
- `cadref diff`

This is exactly the right agent interface. It avoids guessing from screenshots and turns geometry into structured facts.

Lathe should add:

```powershell
python -m lathe.cli ref inspect '@lathe[tmp_repo_study_build/courier_drone#part.body_shell.face12]' --facts --json
python -m lathe.cli ref planes '@lathe[tmp_repo_study_build/courier_drone#part.panel]' --json
python -m lathe.cli ref diff dist_a/courier_drone dist_b/courier_drone --json
```

Fact payload should include:

- bbox min/max/center/size
- part role
- surface or curve type
- area/length
- normal/dominant axis
- material assignment
- UV island or chart
- collision membership
- LOD membership
- adjacent faces/edges
- source declaration span where available
- validation diagnostics that reference the selector

Integration with existing Lathe:

- Extend `lathe/cli.py` with `ref` subcommands.
- Reuse existing `diff-asset` concepts where possible.
- Wire into `lathe/explain` so a diagnostic can point to a ref.
- Wire into `report.html` so clicking a diagnostic highlights the selector in the viewer.

### 4. Local Viewer As Agent Workbench

text-to-cad's CAD Explorer is read-only with respect to files, scans from `?dir=`, hot reloads on CAD artifact changes, and copies refs.

Lathe needs a first-party viewer. It does not need to start as large as text-to-cad's viewer.

Minimum viable Lathe viewer:

- `lathe serve <build_dir>` starts localhost.
- Scans one build directory.
- Shows GLB/USD-derived preview.
- Shows part tree.
- Shows certification status.
- Shows stage bundles.
- Shows diagnostics.
- Allows copy of `@lathe[...]` refs.
- Supports URL state:
  - `?asset=`
  - `?variant=`
  - `?stage=`
  - `?ref=`
  - `?diagnostic=`

Later viewer:

- Face/edge/socket/collision picking.
- Toggle LODs.
- Toggle collision and sockets.
- Compare two builds.
- Show repair rounds.
- Show source declaration side panel.
- Show UV layout.
- Show material maps and budgets.

Recommended architecture:

- Keep a small static viewer under `lathe/viewer/static/` or `web/viewer/`.
- Use Vite/React/three.js only if Lathe is ready to own frontend complexity.
- Keep viewer read-only.
- Serve only files under the selected build directory.
- Use content hashes or mtime hashes for cache-busting.

### 5. Explicit Generation Targets

text-to-cad avoids broad directory-wide generation. The tools require explicit targets.

Why Lathe should care:

- Agents are safer when they regenerate one asset/variant.
- Rebuild scope is understandable.
- It avoids accidental broad churn.
- It aligns with Lathe's public compatibility contract.

Lathe already mostly does this:

```powershell
python -m lathe.cli build examples/courier_drone.lth courier_drone --out dist
python -m lathe.cli materialize examples/courier_drone.lth courier_drone_mobile
```

Recommended upgrade:

- Keep explicit asset/variant target commands as the default.
- Add a `--changed-only` or manifest-driven CI helper later, but keep direct build commands primary.
- Add build summaries that tell users exactly which source and variant were rebuilt.

### 6. Non-Visual Validation First, Snapshot Second

text-to-cad's validation guidance is excellent:

- Prefer generator assertions, bounds, dimensions, solid counts, transforms, planes, and diffs.
- Add snapshots when numeric checks do not make correctness obvious.
- Treat screenshots as supporting evidence, not source of truth.

Lathe already has semantic and visual quality scoring. The missing piece is workflow polish:

- Make validation facts easy to inspect.
- Connect diagnostics to refs.
- Use snapshots as evidence artifacts, not the primary correctness signal.

Recommended Lathe commands:

```powershell
python -m lathe.cli inspect tmp_repo_study_build/courier_drone --json
python -m lathe.cli ref inspect '@lathe[tmp_repo_study_build/courier_drone#socket.payload_mount]' --facts --json
python -m lathe.cli snapshot tmp_repo_study_build/courier_drone --view isometric --out tmp/courier_drone.png
python -m lathe.cli snapshot tmp_repo_study_build/courier_drone --align-ref '@lathe[tmp_repo_study_build/courier_drone#part.body.face12]' --out tmp/body-face12.png
```

### 7. Snapshot Alignment To Refs

text-to-cad's `snapshot --align-ref` resolves a face or edge ref and chooses an aligned orthographic view.

Lathe should implement this because it maps directly to:

- checking seams,
- checking panel alignment,
- checking sockets,
- checking collision hull placement,
- checking pivot axes,
- checking UV or trim alignment,
- reviewing failed diagnostics.

Implementation idea:

- Ref inspection returns dominant normal or edge direction.
- Snapshot code maps that vector to closest orthographic view.
- Report links include prebuilt aligned images for severe diagnostics.

### 8. Agent Skills As Distribution

text-to-cad packages reusable behavior as `skills/cad` and `skills/urdf`.

Lathe should ship official agent skills:

- `lathe-author`: write/edit `.lth`, preserve public language surface.
- `lathe-build-debug`: run check/plan/build, inspect diagnostics, repair.
- `lathe-ref-workflow`: use `@lathe[...]` refs, inspect facts, make targeted edits.
- `lathe-godot`: build and import certified assets into Godot.

The repo already has Lathe-specific skills in `.agents/skills/`. The opportunity is to make them user-facing distribution artifacts, not just internal repo helpers.

### 9. LFS And Artifact Policy

text-to-cad tracks CAD exchange files and generated render artifacts through Git LFS:

- `.gitattributes:2-6` for STEP/STP/STL/DXF/GLB.
- `.gitattributes:7-8` for topology sidecars.

Lathe should have a documented artifact policy:

- `.lth`, specs, schema, examples, and small reference inputs are normal Git.
- Large generated outputs are ignored by default.
- Curated golden outputs can be Git LFS if intentionally versioned.
- Selector sidecars and reports for release gallery assets can be stored in docs/gallery or LFS.
- CI artifacts should upload generated packages rather than committing them by default.

### 10. Assembly And Robot Lessons

text-to-cad separates CAD and URDF skills because robot correctness is kinematic, not just geometric.

Lathe should apply the same separation concept:

- General game asset semantics: parts, materials, LODs, collisions, sockets.
- Mechanical/interactive semantics: pivots, hinges, joints, constraints.
- Robot/URDF-style semantics: links, joints, limits, rooted kinematic tree.

Lathe does not need URDF as a primary target, but the validation pattern is useful:

- root exists,
- links are unique,
- joints are unique,
- parent/child references resolve,
- graph is connected,
- graph is acyclic,
- limits are valid,
- referenced meshes exist.

This maps to Lathe rig/interface validation:

- every socket references an existing part,
- every pivot references an existing part or assembly node,
- every collision proxy references an existing part,
- no duplicate gameplay-facing IDs,
- every exported engine node has valid transform and bounds,
- mechanical constraints form valid graphs where required.

## How This Integrates Into Lathe

### Proposed Lathe Concepts

#### `@lathe[...]` Ref Grammar

Initial grammar:

```text
@lathe[<build-or-source-path>]
@lathe[<build-or-source-path>#asset.<name>]
@lathe[<build-or-source-path>#variant.<name>]
@lathe[<build-or-source-path>#stage.<stage-name>]
@lathe[<build-or-source-path>#part.<part-id>]
@lathe[<build-or-source-path>#part.<part-id>.face<n>]
@lathe[<build-or-source-path>#part.<part-id>.edge<n>]
@lathe[<build-or-source-path>#part.<part-id>.vertex<n>]
@lathe[<build-or-source-path>#socket.<socket-id>]
@lathe[<build-or-source-path>#pivot.<pivot-id>]
@lathe[<build-or-source-path>#collision.<collision-id>]
@lathe[<build-or-source-path>#lod<n>.<part-id>]
@lathe[<build-or-source-path>#material.<material-id>]
@lathe[<build-or-source-path>#diagnostic.<diagnostic-id>]
```

Keep the first version conservative:

- support whole build,
- part,
- socket,
- pivot,
- collision,
- material,
- diagnostic,
- face/edge if selector extraction is ready.

#### Selector Identity Rules

Stable identity should prefer semantic IDs over ordinal IDs:

- `part.body_shell` is better than `shape3`.
- `socket.payload_mount` is better than `o1.4.s2`.
- `diagnostic.semantic.fragmentation_penalty` is better than `diagnostic7`.

Ordinal face/edge refs are still useful, but must be treated as topology handles that can go stale after topology changes.

Ref resolution should return stale-ref warnings when:

- source hash changed,
- build hash changed,
- selector manifest hash changed,
- face/edge counts changed,
- selector ordinal no longer resolves.

#### Selector Manifest Location

Recommended build output layout:

```text
<out>/<asset>/
  manifest.json
  build_report.json
  report.html
  trace.json
  package/
    asset.glb
    asset.usda
  refs/
    selectors.json
    selectors.bin
  snapshots/
    isometric.png
  stages/
    shape/
    topology/
    uv/
    surface/
    rig/
    interfaces/
    physics/
    optimize/
    validate/
    package/
```

The selector manifest should be written after the latest stage that can affect final geometry and game metadata. For initial integration, write it after `optimize` and enrich it after `validate`.

#### Ref Inspection Output

Example:

```json
{
  "ok": true,
  "ref": "@lathe[tmp_repo_study_build/courier_drone#socket.payload_mount]",
  "buildDir": "tmp_repo_study_build/courier_drone",
  "selectorType": "socket",
  "selectorId": "payload_mount",
  "facts": {
    "partId": "body_shell",
    "origin": [0.0, 1.2, 0.4],
    "axis": [0.0, 1.0, 0.0],
    "bbox": {"min": [-0.1, 1.1, 0.3], "max": [0.1, 1.3, 0.5]},
    "diagnostics": []
  }
}
```

#### Diagnostic Integration

Every diagnostic should optionally include:

```json
{
  "code": "semantic.fragmentation_penalty",
  "severity": "warning",
  "message": "...",
  "refs": [
    "@lathe[tmp_repo_study_build/courier_drone#part.body_shell]",
    "@lathe[tmp_repo_study_build/courier_drone#diagnostic.semantic.fragmentation_penalty]"
  ],
  "suggestedCommands": [
    "python -m lathe.cli ref inspect '@lathe[...]' --facts --json"
  ]
}
```

This turns reports into an agent-operable interface.

### Proposed File-Level Integration

Likely new Lathe files:

- `lathe/ref.py`: parse and normalize `@lathe[...]` tokens.
- `lathe/selector_manifest.py`: schema-level dataclasses/helpers and writer.
- `lathe/selector_extract.py`: extract selector facts from final mesh/stage bundles.
- `lathe/ref_inspect.py`: inspect refs, planes, diff.
- `lathe/snapshot.py`: build/asset snapshot generation and `--align-ref`.
- `lathe/viewer/`: static local viewer or viewer scaffold.
- `schema/lathe.selector.schema.json`: selector sidecar schema.
- `docs/refs.md`: ref grammar and stale-ref behavior.
- `docs/viewer.md`: local viewer usage.
- `tests/test_refs.py`: parser and resolver tests.
- `tests/test_selector_manifest.py`: selector schema and generated bundle tests.
- `tests/test_ref_cli.py`: CLI tests.

Likely touched existing files:

- `lathe/cli.py`: add `ref` and `snapshot` commands.
- `lathe/executor.py`: emit selector artifacts and include paths in build report.
- `lathe/visual_quality.py`: attach refs to diagnostics.
- `lathe/semantic_quality.py`: attach refs to diagnostics.
- `lathe/explain.py` or equivalent explain path: explain refs and diagnostics.
- `README.md`: document viewer/ref workflow.
- `AGENTS.md`: add `@lathe[...]` prompt-ref rules once implemented.

### Proposed Implementation Phases

#### Phase 1: Ref Grammar And Build-Level Refs

Goal: make Lathe builds addressable even before face picking exists.

Deliverables:

- `lathe/ref.py`
- parse/build/normalize refs
- whole build refs
- asset/variant/stage/diagnostic refs
- tests for valid, invalid, stale, and path-traversal cases

Commands:

```powershell
python -m lathe.cli ref parse '@lathe[tmp_repo_study_build/courier_drone#stage.validate]' --json
python -m lathe.cli ref inspect '@lathe[tmp_repo_study_build/courier_drone#diagnostic.semantic.fragmentation_penalty]' --json
```

Acceptance:

- Does not require new geometry extraction.
- Can resolve refs against existing `build_report.json` and stage bundles.

#### Phase 2: Selector Manifest For Parts, Sockets, Collisions, Materials

Goal: expose the game-asset entities Lathe already knows about.

Deliverables:

- `refs/selectors.json`
- `schema/lathe.selector.schema.json`
- part table
- material table
- socket/interface table where available
- collision table where available
- validation diagnostic refs

Acceptance:

- Every certified build emits a selector manifest.
- Manifest validates against schema.
- `lathe ref inspect` returns facts for parts/materials/collisions/sockets.

#### Phase 3: Face/Edge Selector Extraction

Goal: make final mesh geometry inspectable like text-to-cad.

Deliverables:

- face table
- edge table
- vertex table
- compact optional `selectors.bin`
- adjacency relations
- bbox/area/length/normal facts

Acceptance:

- Viewer can highlight selected faces/edges.
- `lathe ref planes` groups major planar surfaces.
- topology-changing rebuilds can warn stale refs.

#### Phase 4: Local Viewer

Goal: human/agent workbench for generated Lathe assets.

Deliverables:

- `lathe serve <build_dir>`
- GLB preview
- part tree
- diagnostic panel
- copy `@lathe[...]`
- URL ref focus

Acceptance:

- User can open a build, click a part or diagnostic, copy a ref, and paste it into an agent prompt.

#### Phase 5: Snapshot And Report Integration

Goal: make visual evidence and reports ref-aware.

Deliverables:

- `lathe snapshot`
- `--align-ref`
- report links to refs
- report links to aligned snapshots for severe diagnostics

Acceptance:

- Failed diagnostics can be inspected with one command.
- Reports become navigable, not just JSON dumps.

#### Phase 6: Agent Skill Distribution

Goal: make Lathe usable by coding agents outside this repo.

Deliverables:

- official `lathe` skill
- ref workflow docs
- build/debug skill
- Godot import skill later

Acceptance:

- Agent instructions include exact rules: edit `.lth`, build explicit targets, inspect refs, never edit generated artifacts.

## Concrete Design Choices Lathe Should Copy

### Copy

- Stable prompt refs.
- Target-explicit CLI tools.
- Sidecar topology/selector artifacts.
- Geometry facts before screenshots.
- `inspect`, `planes`, `diff`.
- Snapshot alignment to refs.
- Read-only local viewer.
- Browser URL state for selected file/ref.
- Source-of-truth policy for generated outputs.
- LFS/large-artifact policy for intentionally versioned generated outputs.
- Agent skills as reusable workflow packaging.

### Adapt

- Use Lathe `.lth` as source, not Python generators.
- Use Lathe build reports and stage bundles as artifact backbone.
- Prefer semantic IDs over raw ordinals.
- Include certification and game metadata, not just CAD topology.
- Include sockets, pivots, collision, LODs, materials, UV charts, diagnostics.
- Integrate with Godot importer and certification report.

### Do Not Copy

- Python generator scripts as the main user language.
- Huge monolithic viewer components.
- Node script flags that fail on current Node versions.
- Lack of CI.
- Empty example corpus.
- Screenshot-first review.

## Impact On Lathe's Existing Roadmap

This research strengthens several recommendations already captured in `research-findings-gpt.MD`:

- The local viewer should move up in priority because refs make it an agent workbench, not just a visual nicety.
- Certification reports should include copyable refs and ref-focused snapshots.
- Godot integration should consume the same selector manifest, especially sockets, collisions, pivots, LODs, and materials.
- The robust geometry effort should expose stable semantic/selector identities as a contract, not just produce cleaner meshes.
- The LSP/editor work should understand `@lathe[...]` refs.

Recommended roadmap adjustment:

1. Keep geometry robustness as P0.
2. Add ref grammar and selector manifest as P0/P1, alongside certification report work.
3. Build viewer earlier than originally planned, but as a small read-only workbench.
4. Delay broad marketplace work until ref/report/viewer workflow is strong.

## Lathe-Specific Acceptance Criteria

Lathe has absorbed the useful lessons from text-to-cad when:

- Every build emits `refs/selectors.json`.
- Every diagnostic can optionally point to one or more `@lathe[...]` refs.
- `lathe ref inspect` can resolve build, asset, stage, part, socket, collision, material, and diagnostic refs.
- `lathe ref planes` works for major planar mesh groups once face extraction lands.
- `lathe ref diff` summarizes selector, geometry, diagnostic, and certification changes between two builds.
- `lathe snapshot --align-ref` renders a targeted review image.
- `lathe serve` opens a local viewer that can copy refs.
- Ref resolution warns when source/build hashes changed.
- The viewer is read-only and never treats generated artifacts as source.
- Agent skills instruct models to use refs instead of vague screenshots whenever possible.

## Recommended Immediate Tasks For Lathe

1. Draft `docs/refs.md` with the initial `@lathe[...]` grammar.
2. Implement `lathe/ref.py` parser and normalizer.
3. Add `lathe ref parse` and `lathe ref inspect` for build/stage/diagnostic refs using existing build outputs.
4. Add selector manifest schema for non-face entities first: parts, materials, collisions, sockets, diagnostics.
5. Emit `refs/selectors.json` from `lathe/executor.py`.
6. Add refs into validation diagnostics and report JSON.
7. Add `lathe snapshot --align-ref` after ref inspection exposes normals/axes.
8. Build a minimal `lathe serve` viewer after selector manifests stabilize.

## Open Questions For Lathe Design

- Should refs use source paths, build dirs, or both?
- Should source refs and build refs have separate prefixes, such as `@lathe-src[...]` and `@lathe-build[...]`, or one grammar?
- How stable can face/edge ordinals be after topology repair?
- Should selector manifests be public contract or explicitly experimental in v0.1?
- How should refs map back to `.lth` source spans?
- Should Godot node names preserve `@lathe` selector IDs?
- Should selector sidecars be included in package outputs or only build outputs?

## Final Recommendation

Lathe should integrate text-to-cad's best idea as a first-class capability:

> A certified asset should be inspectable, addressable, and editable by reference.

The practical path is:

1. Start with `@lathe[...]` refs for build/stage/part/diagnostic entities.
2. Emit selector manifests from builds.
3. Add ref inspect/diff commands.
4. Add viewer copy-ref workflows.
5. Add face/edge picking after geometry extraction is strong enough.

This would make Lathe much easier for agents and humans to use. Instead of "make the front panel wider," a user could say:

```text
Make @lathe[dist/courier_drone#part.front_panel] 20 percent wider,
keep @lathe[dist/courier_drone#socket.payload_mount] fixed,
and make sure the certification still passes.
```

That is the bridge between declarative asset language and practical agent-driven production.

## Source Links

- text-to-cad repository: https://github.com/earthtojake/text-to-cad
- build123d: https://github.com/gumyr/build123d
- OCP/OpenCascade Python package context: https://github.com/CadQuery/OCP
- three.js: https://threejs.org/
- Vite: https://vite.dev/
