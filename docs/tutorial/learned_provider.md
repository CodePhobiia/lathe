# Learned Provider Workflow

**Time:** about 15 minutes after the provider service is available.
**Prerequisite:** [Fallback provider workflow](fallback_provider.md).

This tutorial shows how to opt into a learned shape provider without weakening
Lathe's traceability contract.

## 1. Probe the runtime config

```bash
python -m lathe.cli doctor --runtime-config examples/runtime_configs/hunyuan_http.json
```

The doctor command reports whether the Hunyuan HTTP endpoint is reachable and
whether the runtime config passes schema validation.

## 2. Build with the learned route requested

```bash
python -m lathe.cli build examples/courier_drone.lth courier_drone --out dist_hunyuan --runtime-config examples/runtime_configs/hunyuan_http.json
```

If the endpoint is available, the shape stage may use the learned provider. If
it is unavailable and strict mode is not enabled, Lathe falls back and records
that fallback explicitly.

## 3. Verify the provider claim

Read:

- `dist_hunyuan/courier_drone/stages/shape/bundle.json`
- `dist_hunyuan/courier_drone/stages/package/trace_manifest.json`
- `dist_hunyuan/courier_drone/build_report.json`

The useful question is not "did the command pass"; it is "does the trace say
which provider actually produced the candidate?" A learned-provider run is only
accepted when the trace and package evidence agree.

## 4. Try strict mode when you need certainty

Strict learned-provider mode should fail if the requested provider cannot run.
Use it for provider certification or release evidence when fallback output would
be misleading.
