# MVP Demo

The current MVP demo is the Alchemist Observatory seed scene:

```text
examples/wonder/alchemist_observatory/
```

It is a deterministic core/proxy demo for the Wonder execution substrate. It is
not a claim that the full Project Wonder runtime is ready.

## Inputs

The demo consumes:

- `prompt.txt`;
- `dream_brief.json`;
- `scene_graph.json`;
- `scene_patch_more_sacred.json`;
- `render_inspection.example.json`;
- `world_memory.json`;
- expected reports under `expected/`.

## One-Command Path

Use the platform helper:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/demo_wonder_seed_scene.ps1 -OutDir .tmp_tests/phase33_seed_demo
```

The POSIX helper has the same intent:

```bash
bash scripts/demo_wonder_seed_scene.sh --out .tmp_tests/phase33_seed_demo
```

Local POSIX execution remains a separate evidence gate because the current
Windows environment has not proven that helper in a POSIX-capable shell.

## What The Demo Produces

The demo writes:

- `_demo_evidence/` with command outputs and validation reports;
- `preview_build/<scene_id>/` with the original proxy preview Scene Package;
- `patched_build/<scene_id>/` with the `more_sacred` patch applied;
- `expanded_build/<scene_id>/` with one curiosity expansion applied;
- `before_after/` with before/after proxy PNGs, camera lock, render comparison,
  scene history, and a before/after report.

The before/after comparison uses the deterministic proxy renderer and a locked
`camera_reveal`. It performs real PNG hashing and pixel comparison, while
semantic visual evaluation remains `not_evaluated`.

## CI Smoke Lane

The local CI wrapper is:

```bash
python scripts/ci_wonder_demo.py --out .tmp_tests/wonder_ci_demo/report.json
```

It runs focused before/after tests, executes `wonder demo-before-after`,
validates the generated Render Comparison, and validates Scene History. The
GitHub workflow `.github/workflows/wonder-demo.yml` wires this into a
deterministic hosted lane, but hosted execution must still be recorded before
full alpha promotion.

## What Remains Outside The Demo

The demo does not prove:

- Blender-backed scene rendering;
- external GLB, USD, or `.blend` viewer validation;
- Roblox Studio import, upload, or execution;
- provider-backed final mesh generation;
- product chat, accounts, galleries, or cloud orchestration.

Those remain full runtime readiness gates. The demo proves the local
contract/package/patch/repair/curiosity/comparison loop that Project Wonder can
build on.
