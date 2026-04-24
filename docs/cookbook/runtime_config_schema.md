# Runtime config schema reference

This page is the field-level reference for the JSON passed via `lathe ... --runtime-config <file>.json`. The authoritative schema lives at [`schema/runtime_config.schema.json`](https://github.com/talmerri/lathe/blob/main/schema/runtime_config.schema.json); this page documents each field with usage notes.

Three example configs ship in-tree under [`examples/runtime_configs/`](https://github.com/talmerri/lathe/tree/main/examples/runtime_configs) — see [Recipe 08 — Runtime config](08_runtime_config.md) for a runnable walkthrough.

The schema id is `https://lathe.dev/schemas/runtime_config-v1.json`. Unknown keys are permitted (warned at load time) until stricter gates land in a later release.

## Top-level shape

```json
{
  "shape":    { ... },
  "topology": { ... },
  "uv":       { ... },
  "surface":  { ... },
  "execution":{ ... }
}
```

All top-level blocks are optional. An empty object `{}` is a valid runtime config — it just means "use all defaults".

## `shape`

Controls which provider the probabilistic shape stage calls.

| Field | Type | Notes |
|---|---|---|
| `shape.provider` | string | Provider alias (`auto`, `reference_conditioned_v1`, `hunyuan2_1_http`, `vggt_local`, `codex_imagegen`) or fully-qualified provider id. Pattern `^[a-zA-Z0-9_.-]+$`. |
| `shape.strict` | bool | If `true`, the build fails instead of falling back when the selected provider is unavailable or errors. Default `false`. |
| `shape.providers.<name>` | object | Per-provider configuration. Only the providers you configure need entries. |

### `shape.providers.hunyuan2_1_http`

| Field | Type | Notes |
|---|---|---|
| `base_url` | string (uri) | HTTP endpoint, e.g. `http://localhost:8081`. |
| `timeout_s` | int 1–3600 | Request timeout. |
| `url_allowlist` | array<string> | Optional host allowlist; any other host is rejected. |
| `remove_background` | bool | Ask the server to strip background from input images. |
| `texture` | bool | Request textured geometry (heavier). |
| `octree_resolution` | int >= 1 | Octree resolution for surface extraction. 256 is a good default. |
| `num_inference_steps` | int >= 1 | Diffusion steps. Lower = faster, noisier. |
| `guidance_scale` | number | CFG scale. |
| `face_count` | int >= 1 | Target face count for the returned mesh. |
| `type` | string | Output geometry format (`glb`, `obj`). |

### `shape.providers.vggt_local`

| Field | Type | Notes |
|---|---|---|
| `path` | string | Filesystem path to a local VGGT checkout (optional; default uses installed package). |
| `weights` | string | HuggingFace repo id or local path, e.g. `facebook/VGGT-1B`. |
| `device` | string | `auto`, `cuda`, `cpu`, or a specific device like `cuda:0`. |
| `dtype` | string | `auto`, `float32`, `bfloat16`, `float16`. |
| `max_views` | int >= 1 | Upper bound on views fed to VGGT. |
| `stride` | int >= 1 | View subsampling stride. |
| `min_confidence` | number | Depth-point confidence threshold. |
| `max_edge_ratio` | number | Edge-aspect-ratio reject filter. |
| `candidate_variants` | int >= 1 | How many candidate reconstructions to return. |
| `use_point_head` | bool | Enable the VGGT point head (heavier, more detail). |

## `topology`

Controls the topology stage adapter (usually Blender).

| Field | Type | Notes |
|---|---|---|
| `topology.adapter` | string | Which adapter to use (`blender`, `reference`). |
| `topology.strict` | bool | Fail instead of falling back when the adapter is unavailable. |
| `topology.blender.path` | string \| null | Path to the Blender binary. `null` uses PATH. |
| `topology.blender.timeout_s` | int 1–3600 | Per-invocation timeout. |
| `topology.blender.asset_libraries` | array<string> | Directories to register as Blender asset libraries. |
| `topology.blender.addons` | array<string> | Addons to enable at startup. |

## `uv`

| Field | Type | Notes |
|---|---|---|
| `uv.adapter` | string | `xatlas` or `reference`. |
| `uv.strict` | bool | Fail if the adapter is unavailable. |
| `uv.xatlas.resolution` | int >= 1 | Atlas resolution target. |

## `surface`

V1.2 surface backend wiring.

| Field | Type | Notes |
|---|---|---|
| `surface.backend` | string | `codex_imagegen` today; more backends planned. |
| `surface.fallback_mode` | string | `strict` = fail, `allow_fallback` = fall through to native. |
| `surface.codex_imagegen.mode` | string | `auto`, `fallback`, `emit`, `consume`. Matches the CLI `--codex-imagegen` flag. |
| `surface.codex_imagegen.request_dir` | string | Where Lathe writes imagegen requests. |
| `surface.codex_imagegen.output_dir` | string | Where Lathe reads imagegen results back. |

## `execution`

V1.3 Blender execution + V1.3.1 bridge settings.

| Field | Type | Notes |
|---|---|---|
| `execution.blender.path` | string \| null | Blender binary. |
| `execution.blender.strict` | bool | Fail if Blender is unavailable. |
| `execution.blender.allow_autoexec` | bool | Permit Blender to auto-execute Python in loaded `.blend` files. Leave `false`. |
| `execution.blender.trusted` | bool | Mark the execution environment as trusted. Required alongside `unsafe_blender_python_allowed = true` in an inspection policy for Python execution. |
| `execution.blender.preserve_blend` | string | `always`, `on_failure`, `never`. Controls whether the retained `.blend` is kept. |
| `execution.blender.asset_libraries` | array<string> | Asset libraries to register. |
| `execution.blender.addons` | array<string> | Addons to enable. |
| `execution.blender.render_device` | string | `cpu`, `cuda`, `optix`, etc. |
| `execution.blender.request_dir` | string | Where bridge requests are written (V1.3.1). |
| `execution.blender.output_dir` | string | Where bridge outputs are read (V1.3.1). |

## Strict-mode cheat sheet

`strict: true` turns the corresponding fallback into an error. Recommended combinations:

| Environment | `shape.strict` | `topology.strict` | `uv.strict` | `surface.fallback_mode` |
|---|---|---|---|---|
| Local dev | `false` | `false` | `false` | `allow_fallback` |
| CI smoke | `false` | `false` | `false` | `allow_fallback` |
| CI real-provider | `true` | `true` | `true` | `strict` |
| Release build | `true` | `true` | `true` | `strict` |

## Validation

Load-time validation is permissive: unknown keys warn, malformed types raise. To validate a config before running a build:

```bash
python -c "import json, jsonschema; jsonschema.validate(json.load(open('my_config.json')), json.load(open('schema/runtime_config.schema.json')))"
```

The CLI will eventually gain a `lathe validate-runtime-config <file>` command.

## See also

- [Recipe 08 — Runtime config](08_runtime_config.md) — runnable examples.
- [Reading a trace](reading_a_trace.md) — how attempted-vs-actual is recorded.
- API: [`lathe.runtime_config`](../api/runtime_config.md).
