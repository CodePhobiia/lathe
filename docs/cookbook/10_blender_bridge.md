# Recipe 10 — Blender bridge and inspection (V1.3.1)

## Goal

Drive the V1.3.1 Codex-operated Blender bridge from a Lathe asset: probe readiness, emit a typed bridge plan, inspect the retained `.blend` artifact and the render-fixture evidence. This recipe uses the `brassbound_chest_v13_1_codex_blender` example, which layers a V1.3.1 inspection policy on top of the V1.3 Blender execution asset.

## Prerequisites

- Lathe v0.1+ with V1.3.1 language support (scaffold ships with it).
- A Blender 4.x install on PATH (the bridge doctor will probe for it).
- The two related examples:
    - [`examples/brassbound_chest_v13_blender.lth`](https://github.com/talmerri/lathe/blob/main/examples/brassbound_chest_v13_blender.lth) — base V1.3 asset with Blender execution + bake/render intent.
    - [`examples/brassbound_chest_v13_1_codex_blender.lth`](https://github.com/talmerri/lathe/blob/main/examples/brassbound_chest_v13_1_codex_blender.lth) — V1.3.1 variant adding the `hero_visual_gate` inspection policy.

## Walkthrough

### Step 1 — read the variant

Open `examples/brassbound_chest_v13_1_codex_blender.lth`:

```lth
module studio.props.containers.v13_1
import examples.brassbound_chest_v13_blender

inspection_policy hero_visual_gate {
  require = [geometry_evidence, topology_evidence, uv_evidence, bake_evidence, surface_evidence]
  render_fixture = hero_prop_eval
  bake_profile = hero_pbr_bakes
  patch_source_allowed = true
  unsafe_blender_python_allowed = false
  recovery_branches = [reselect_candidate, repair_candidate, regenerate_candidate, patch_source]
}

variant brassbound_chest_v13_1 on brassbound_chest_v13 {
  set execution.inspection_policy = hero_visual_gate
  set publish.version = "0.1.1"
}
```

The variant is tiny because all the heavy lifting lives in the base V1.3 asset. What's new in V1.3.1:

- `inspection_policy` is a first-class block type.
- It enumerates the evidence kinds required for certification (`geometry_evidence`, `topology_evidence`, `uv_evidence`, `bake_evidence`, `surface_evidence`).
- `unsafe_blender_python_allowed = false` means the bridge refuses to run arbitrary Python in the `.blend`. This is the safe default; flip to `true` only for trusted source.
- `recovery_branches` lists the tactics the bridge may try before surfacing a failure back to the source author.

### Step 2 — probe the bridge

```bash
python -m lathe.cli bridge doctor
```

This checks:

- Blender is on PATH and reports its version.
- `allow_autoexec` and `trusted` flags from your runtime config.
- Whether `render-fixture` and `bake-audit` subcommands can be invoked.
- Whether the asset library paths resolve.

Expected healthy output:

```
bridge: ready
  blender: 4.2.0 at C:\Program Files\Blender Foundation\Blender 4.2\blender.exe
  autoexec: disabled
  trusted: true
  asset_libraries: 0 configured
```

If `blender` is missing, pass `--runtime-config` with `execution.blender.path` pointing at the binary.

### Step 3 — emit the bridge plan

```bash
python -m lathe.cli bridge plan \
    examples/brassbound_chest_v13_1_codex_blender.lth brassbound_chest_v13_1
```

This writes a typed bridge plan (JSON) to `dist/brassbound_chest_v13_1/bridge_plan.json`. The plan enumerates every Blender-side operation the bridge is allowed to execute:

```json
{
  "bridge_plan_version": "1.3.1",
  "steps": [
    { "op": "scene_prep",         "needs": ["authoritative_mesh"] },
    { "op": "uv_unwrap",          "needs": ["part_groups", "uv.sets"] },
    { "op": "bake",               "needs": ["uv_bundle"], "profile": "hero_pbr_bakes" },
    { "op": "render_fixture",     "needs": ["bake_bundle"], "fixture": "hero_prop_eval" },
    { "op": "export",             "needs": ["rendered"], "formats": ["glb", "usd"] }
  ],
  "forbidden_ops": ["python_exec", "unknown_addon_call"],
  "inspection_policy": "hero_visual_gate"
}
```

Nothing outside `steps` is permitted to run. This is the contract between Lathe and whatever Codex agent drives Blender.

### Step 4 — run the build

```bash
python -m lathe.cli build \
    examples/brassbound_chest_v13_1_codex_blender.lth brassbound_chest_v13_1 \
    --out dist
```

The executor spawns headless Blender per step in the bridge plan. Between steps, Lathe snapshots evidence into `dist/brassbound_chest_v13_1/stages/` so the inspection policy can read it without re-running Blender.

If you want a full render-eval pass at the same time:

```bash
python -m lathe.cli render-eval \
    examples/brassbound_chest_v13_1_codex_blender.lth brassbound_chest_v13_1 \
    --out dist
```

### Step 5 — inspect the retained `.blend`

The V1.3 execution profile retains the final `.blend` so you can open it in Blender if certification fails. Two inspection commands:

```bash
python -m lathe.cli inspect-blend dist/brassbound_chest_v13_1
```

Reports a text summary: object count, material count, UV layer names, bake targets, render output paths — read from the `.blend` header without launching Blender. Good for CI.

```bash
python -m lathe.cli export-blend dist/brassbound_chest_v13_1 --out ./investigate/chest.blend
```

Copies the retained `.blend` to a location of your choosing. Open it in Blender locally to debug.

### Step 6 — inspect V1.3.1 evidence

```bash
python -m lathe.cli inspect dist/brassbound_chest_v13_1
```

Reports:

- Which evidence kinds the inspection policy required, which are present, which are missing.
- The `render_fixture` outputs (per-camera PNGs) and their certification scores.
- The `bake_audit` report — any baked maps that did not meet coverage/precision thresholds.

Drill into specifics with:

```bash
python -m lathe.cli render-fixture dist/brassbound_chest_v13_1
python -m lathe.cli bake-audit dist/brassbound_chest_v13_1
```

## Output

```
dist/brassbound_chest_v13_1/
  build_report.json
  bridge_plan.json
  stages/
    shape/bundle.json
    topology/bundle.json
    uv/bundle.json
    surface/bundle.json
    bake/bundle.json
    render/bundle.json
  evidence/
    geometry_evidence.json
    topology_evidence.json
    uv_evidence.json
    bake_evidence.json
    surface_evidence.json
    render_fixture/
      hero_prop_eval_front.png
      hero_prop_eval_3q.png
      hero_prop_eval_top.png
  artifacts/
    brassbound_chest_v13_1.blend       <- retained, inspectable
    brassbound_chest_v13_1.usd
    brassbound_chest_v13_1.glb
```

## Variations

- **Require only a subset of evidence** — narrow `inspection_policy.require` to `[geometry_evidence, uv_evidence]` for a cheap smoke-test policy.
- **Enable Python execution** — for a trusted internal pipeline that legitimately needs custom Python, set `unsafe_blender_python_allowed = true` *and* pin the runtime config `execution.blender.trusted = true`. Never enable both from an untrusted source.
- **Change the render fixture** — declare a new `render_fixture` under `std/spaces/` (e.g. a close-up hero turntable) and reference it in the policy.
- **Different preserve_blend policy** — runtime config `execution.blender.preserve_blend = "on_failure"` retains the `.blend` only when the build fails. Default is `"always"`; use `"never"` to save disk.

## Troubleshooting

- `bridge doctor: blender unavailable` — supply `execution.blender.path` in a runtime config, or install Blender.
- `inspect-blend: no .blend artifact` — the V1.3 execution profile was not used. Check `plan.execution.blender.preserve_blend` is `always` or `on_failure`.
- `inspect: missing evidence 'bake_evidence'` — the bake stage did not run (or its outputs did not land in `evidence/`). Check `stages/bake/bundle.json` for errors.
- `bridge plan: step 'python_exec' forbidden` — an asset requested Python execution while `unsafe_blender_python_allowed = false`. Either relax the policy (carefully) or remove the requesting step.

## See also

- [Spec — V1.3.1](../Specs/Lathe-V1.3.1-Spec.md) — `inspection_policy`, `recovery_branches`, bridge plan schema.
- API: [`lathe.bridge.blender_plan`](../api/bridge/blender_plan.md).
- Related: [Recipe 05 — Surface control](05_surface_control.md) for how Codex ImageGen plugs into the bridge for surface authoring.
- Related: [Recipe 09 — Certification debug](09_certification_debug.md).
