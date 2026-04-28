# Recipe 08 — Runtime configuration (Hunyuan / VGGT / auto)

## Goal

Drive Lathe with external learned providers — Hunyuan 2.1 via HTTP, VGGT via a local install, or auto-learned provider selection. This recipe walks through the shipped runtime configs in [`examples/runtime_configs/`](https://github.com/talmerri/lathe/tree/main/examples/runtime_configs) and shows how to read the attempted-vs-actual provider trace.

## Prerequisites

- Lathe v0.1+.
- For Hunyuan: a running Hunyuan 2.1 HTTP server reachable from your machine (the example defaults to `http://localhost:8081`).
- For VGGT: a local VGGT install with weights (the example points at `facebook/VGGT-1B`).
- For auto: both providers available, plus the native fallback (always available).

Even without any learned provider installed, these configs still work — Lathe falls back to the native `reference_conditioned_v1` path and records the attempted provider in the trace.

## Walkthrough

### Option A — offline deterministic mode

`examples/runtime_configs/offline.json` forces the built-in reference shape,
topology, UV, and surface fallbacks. It is the safest config for airplanes,
trains, clean rooms, and any CI job that must not touch network or optional
native tools.

```bash
python -m lathe.cli build examples/courier_drone.lth courier_drone --out dist \
    --runtime-config examples/runtime_configs/offline.json
```

### Option B — reference-only shape mode

`examples/runtime_configs/reference_only.json` pins only the shape provider to
`reference_conditioned_v1`. Other deterministic stages can still use installed
Blender or xatlas adapters when available.

```bash
python -m lathe.cli build examples/courier_drone.lth courier_drone --out dist \
    --runtime-config examples/runtime_configs/reference_only.json
```

### Option C — mocked learned-provider mode

`examples/runtime_configs/mock_hunyuan_http.json` points at a local
Hunyuan-compatible test endpoint on `127.0.0.1:8081`, uses a small generation
budget, and keeps `strict: true` so provider failures are visible during
adapter development.

```bash
python -m lathe.cli probe-providers \
    --runtime-config examples/runtime_configs/mock_hunyuan_http.json
```

Use this config as the provider test double in CI and adapter development: run
a local Hunyuan-compatible fake server, assert that `probe-providers` sees the
mock endpoint, then run the build in strict mode so transport errors,
malformed payloads, and timeout handling fail loudly. Tests should mock the
HTTP boundary or use a loopback service; they should not call the real
provider fleet.

### Option D — Hunyuan over HTTP

`examples/runtime_configs/hunyuan_http.json`:

```json
{
  "shape": {
    "provider": "hunyuan2_1_http",
    "strict": true,
    "providers": {
      "hunyuan2_1_http": {
        "base_url": "http://localhost:8081",
        "timeout_s": 600,
        "url_allowlist": ["localhost"],
        "remove_background": true,
        "texture": false,
        "octree_resolution": 256,
        "num_inference_steps": 5,
        "guidance_scale": 5.0,
        "face_count": 40000,
        "type": "glb"
      }
    }
  }
}
```

Key fields:

- `shape.provider` — the alias Lathe should try first.
- `shape.strict: true` — fail the build if the provider is unavailable or errors. Use this in CI.
- `providers.hunyuan2_1_http.base_url` — where the HTTP server is. Pair it with `url_allowlist` to pin allowed hosts; outbound provider requests are denied when this allowlist is empty.
- `providers.hunyuan2_1_http.timeout_s` — request timeout for generation calls.
- `octree_resolution`, `num_inference_steps`, `guidance_scale`, `face_count`, `type` — mapped directly onto the Hunyuan request body.

Run:

```bash
python -m lathe.cli build examples/courier_drone.lth courier_drone --out dist \
    --runtime-config examples/runtime_configs/hunyuan_http.json
```

Check `dist/courier_drone/build_report.json`:

```json
{
  "shape": {
    "selected_provider_id": "lathe.provider.shape.hunyuan2_1_http_v1",
    "actual_provider_id": "lathe.provider.shape.hunyuan2_1_http_v1",
    "external_job_id": "hunyuan-20260423-abc",
    "consumed_refs": ["refs/courier_front.png", "refs/courier_side.png"]
  }
}
```

`selected_provider_id == actual_provider_id` means the real provider ran. If they differ, see [Attempted-vs-actual](#attempted-vs-actual).

### Option E — real learned-provider mode

`examples/runtime_configs/real_learned_hunyuan_http.json` is the production
shape of a real Hunyuan configuration: HTTPS, strict mode, no fallback, a
non-empty `url_allowlist`, strict topology, and strict UV. Replace
`https://hunyuan.internal.example` with the real endpoint before use.

```bash
python -m lathe.cli build examples/courier_drone.lth courier_drone --out dist \
    --runtime-config examples/runtime_configs/real_learned_hunyuan_http.json
```

### Option F — VGGT local

`examples/runtime_configs/vggt_local.json`:

```json
{
  "shape": {
    "provider": "vggt_local",
    "strict": true,
    "providers": {
      "vggt_local": {
        "weights": "facebook/VGGT-1B",
        "device": "auto",
        "dtype": "auto",
        "max_views": 6,
        "stride": 6,
        "min_confidence": 0.2,
        "max_edge_ratio": 6.0,
        "candidate_variants": 2,
        "use_point_head": false
      }
    }
  }
}
```

VGGT is the right choice when you have reference images and want real multi-view reconstruction:

```bash
python -m lathe.cli build examples/reconstruct_courier_from_views.lth \
    reconstruct_courier_from_views --out dist \
    --runtime-config examples/runtime_configs/vggt_local.json
```

The `max_views`, `stride`, and `min_confidence` knobs control how the provider samples the input views. Lower `min_confidence` to keep more points; raise `stride` to skip cheaper views.

### Option G — auto

`examples/runtime_configs/auto_learned.json`:

```json
{
  "shape": {
    "provider": "auto",
    "strict": false,
    "providers": {
      "hunyuan2_1_http": {
        "base_url": "http://localhost:8081",
        "timeout_s": 600,
        "url_allowlist": ["localhost"]
      },
      "vggt_local": { "weights": "facebook/VGGT-1B", "device": "auto" }
    }
  }
}
```

`provider = auto` delegates the choice to Lathe's `shape_providers` mux. The rules today:

1. If the asset's shape mode is `reconstruct` and ref images are present → try `vggt_local`.
2. If the mode is `generate` with ref images → try `hunyuan2_1_http`.
3. If neither is available → fall back to `reference_conditioned_v1`.

`strict: false` means the fallback is permitted. Use this in local dev, leave strict on in CI.

```bash
python -m lathe.cli build examples/courier_drone.lth courier_drone --out dist \
    --runtime-config examples/runtime_configs/auto_learned.json
```

### Attempted-vs-actual

Every shape build records both fields. There are three interesting combinations:

| `selected_provider_id` | `actual_provider_id` | Meaning |
|---|---|---|
| `hunyuan2_1_http_v1` | `hunyuan2_1_http_v1` | Success; real provider produced the bundle. |
| `hunyuan2_1_http_v1` | `reference_conditioned_v1` | Selected provider unavailable/failed; native fallback ran. The build still certified because the fallback is authoritative. |
| `hunyuan2_1_http_v1` | `null` (with `strict: true`) | Selected provider failed in strict mode; build aborted. |

Probe before you build:

```bash
python -m lathe.cli probe-providers --runtime-config examples/runtime_configs/hunyuan_http.json
```

Reports `available`, `fallback`, or `unavailable` per provider, plus the exact error when relevant.

### Other stages in the runtime config

Runtime config is not just for shape. The schema at `schema/runtime_config.schema.json` also covers:

- `topology.adapter = blender` + `topology.blender.path` + `topology.blender.timeout_s`.
- `topology.strict: true` — fail if Blender is unavailable.
- `uv.adapter = xatlas` + `uv.xatlas.resolution`.
- `uv.strict: true` — fail if xatlas is unavailable.
- `surface.backend = codex_imagegen` + `surface.codex_imagegen.request_dir` + `surface.codex_imagegen.output_dir`.
- `surface.fallback_mode = strict | allow_fallback`.
- `execution.blender.path`, `execution.blender.preserve_blend`, `execution.blender.render_device`, etc. for V1.3 bake/render execution.

See [Runtime config schema](runtime_config_schema.md) for the full field inventory.

## Output

The runtime config does not change `dist/` layout. It changes:

- Which executors actually run (`actual_provider_id`, `actual_backend_id`).
- Per-provider parameters recorded in `provenance`.
- Whether a build is allowed to fall back or must fail.

## Variations

- **Pin an allowlist** — add `"url_allowlist": ["localhost", "hunyuan.internal.studio"]` to the Hunyuan provider block. The HTTP client rejects any other host.
- **Force strict everywhere** — set `shape.strict: true`, `topology.strict: true`, `uv.strict: true`. Nothing falls back. Good for release builds.
- **Override just one stage at the CLI** — `--shape-provider hunyuan2_1_http --strict` overrides the shape block without a config file. The older `--strict-shape-provider` alias is deprecated.
- **Combine with variants** — variants inherit the runtime config; you do not need a separate config per variant.

## Troubleshooting

- `probe-providers: hunyuan2_1_http unavailable (connection refused)` — the HTTP server is not up, or not on the configured `base_url`.
- `probe-providers: vggt_local unavailable (import error)` — missing deps. `pip install -e .[vggt]` or follow the VGGT upstream README.
- `build: strict provider failed` — you set `strict: true` and the provider errored. Either relax strict mode or fix the provider. For CI, let it fail.

## See also

- [Runtime config schema](runtime_config_schema.md).
- [Reading a trace](reading_a_trace.md) — attempted-vs-actual in depth.
- API: [`lathe.runtime_config`](../api/runtime_config.md), [`lathe.shape_providers`](../api/shape_providers.md).
