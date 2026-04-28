# Hunyuan3D — manual run instructions

_Status: not_run. No Hunyuan runs have been executed in this study yet, outside
of the existing Lathe→Hunyuan-provider path, which is measured under
`lathe_learned`, not here._

Hunyuan3D is Tencent's open-weights text-and-image-to-3D model. Two ways to
run it as a competitor (distinct from Lathe's built-in provider bridge):

- **Self-hosted inference** — download weights, run locally.
- **Tencent Cloud API** — paid per-call hosted endpoint.

## Account / install

- **Self-hosted:** follow Tencent's official repo instructions (re-check the
  model license on the day of the run — previously Apache 2.0, but always
  verify). GPU with sufficient VRAM required; record GPU model in the run JSON.
- **Hosted:** sign up at Tencent Cloud, enable the 3D generation product, and
  generate a `SecretId` / `SecretKey` pair. Record the per-call price at run
  time.

## Prompt / input per asset

Use the same intent text as `meshy.md`. Hunyuan accepts optional image
conditioning — for the **image-to-3D** variant, use reference renders from
`examples/refs/` when the `.lth` source cites them:

| Asset | Refs available under `examples/refs/`? |
|---|---|
| `industrial_crate` | Check `examples/industrial_crate.lth` for `ref {}` blocks. |
| `sci_fi_wall_panel` | Check `examples/sci_fi_wall_panel.lth` for `ref {}` blocks. |
| `mechanical_door` | Check `examples/mechanical_door.lth`. |
| `control_pedestal` | Check `examples/control_pedestal.lth`. |
| `service_cabinet` | Check `examples/service_cabinet.lth`. |

If a reference image is present, run image-to-3D. If not, run text-to-3D with
the prompts from `meshy.md`.

## Export

Save the returned `.glb` or convert the returned `.ply` via `trimesh`. Do not
alter geometry; we want to measure what Hunyuan actually produces, not what a
cleanup pass does.

## Ingest

Same manual flow as `meshy.md`: place `.glb` under
`docs/benchmarks/data/hunyuan_runs/<asset>.glb`, fill in
`docs/benchmarks/data/<asset>_hunyuan_<date>.json`, and record in the `note`
field whether it was self-hosted or hosted API + the per-call cost.

## Why this is **separate** from `lathe_learned`

When Lathe is configured with `examples/runtime_configs/hunyuan_http.json`,
Hunyuan is a proposal source inside Lathe's shape contract — the mesh still
goes through Lathe's topology/UV/validate stages and gets certified. The
**Hunyuan** column in this study, by contrast, is Hunyuan's *raw output* with
no downstream cleanup. This separation is deliberate: it's the clearest way to
show how much of Lathe's value is the validator + downstream stages vs. the
shape proposal itself.

## Licensing

Model weights: re-check on the day of the run. API: paid per call, pricing at
Tencent Cloud's product page. Record both in the `note` field of the run JSON.
