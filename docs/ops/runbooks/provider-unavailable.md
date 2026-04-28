# Runbook: Provider Unavailable

A learned provider (Hunyuan, VGGT, Codex) is unreachable or returns an error mid-build.

**Owner:** Tal Merri (@talmerri). Backup: `requires-human`

## Symptoms

- Build trace contains `fallbacks: [{attempted: "hunyuan_http_v1", actual: "reference_conditioned_v1", reason: "connection_refused"}]` or similar.
- User reports that the shape stage produced a fallback result despite having a runtime config that names a specific provider.
- `lathe doctor --json` shows a provider as `available: false` when it should be reachable.

## First response (≤5 min)

1. Ask the user to share their runtime config path and the `dist/<asset>/stages/shape/trace.json`.
2. Check whether `strict: true` is set in the runtime config — if so, the build will fail rather than silently fall back.

## Investigation

Check whether the provider URL is reachable from the build machine:

```bash
# For Hunyuan HTTP
curl -s --connect-timeout 5 http://<hunyuan-host>:<port>/health || echo "UNREACHABLE"
```

Inspect the network egress allowlist and proxy settings in `lathe/net.py`. Confirm the machine has outbound access to the provider host.

Check the runtime config for strict vs fallback mode:

```bash
python -c "import json; c=json.load(open('examples/runtime_configs/hunyuan_http.json')); print(c.get('strict', False))"
```

Review the attempted-vs-actual trace:

```bash
python -c "import json; t=json.load(open('dist/<asset>/stages/shape/trace.json')); print(json.dumps(t.get('fallbacks',[]), indent=2))"
```

For VGGT local: confirm the `vggt` Python package is installed in the active venv (`pip show vggt`). VGGT requires a manual source install (see README "Manual VGGT source install").

## Mitigation

- **Offline / CI environment:** switch to the offline runtime config:
  ```bash
  python -m lathe.cli build <file> <asset> --out dist --runtime-config examples/runtime_configs/auto_learned.json
  ```
  Or drop `--runtime-config` entirely to use the conservative reference path.
- **Provider host is temporarily down:** set `strict: false` in the runtime config to allow fallback, or wait for the provider to recover.
- **Provider URL misconfigured:** update the `url` field in the runtime config to the correct endpoint.

## Communication

Apply Macro: provider unavailable from `docs/support/readiness-checklist.md`. If the provider outage is external and affects many users, post a status note on the GitHub repo Discussions.

## Escalation

Escalates to release blocker only if the fallback path itself is broken (i.e. the build fails even on the conservative reference path). A functional fallback with an honest trace is expected behavior, not an escalation trigger.

## Postmortem trigger

Any case where a provider failure caused a certification pass on a materially degraded artifact — i.e. strict mode was off and the fallback produced a result that should not have certified.
