# Runbook: Learned Provider Fallback Complaint

User claims a learned provider should have run but Lathe fell back to the reference path.

**Owner:** Tal Merri (@talmerri). Backup: `requires-human`

## Symptoms

- User expected Hunyuan or VGGT to run but the shape stage trace shows `actual: "reference_conditioned_v1"`.
- User believes the provider ran but produced a degraded result they attribute to fallback.
- User is confused about why fallback happened when the provider appears available locally.

## First response (≤5 min)

1. Ask the user to share `dist/<asset>/build_report.json` — specifically the `shape_provider` record.
2. Confirm whether `strict: true` is in their runtime config.

## Investigation

Open the shape provider record in the build report:

```bash
python -c "
import json
r = json.load(open('dist/<asset>/build_report.json'))
sp = r.get('shape_provider', {})
print(json.dumps(sp, indent=2))
"
```

The record contains `attempted`, `actual`, and `reason`. Common reasons:

- `connection_refused` / `timeout` — provider host unreachable.
- `quality_gate_fail` — provider returned a mesh that failed the conformance check; Lathe fell back as designed.
- `strict_mode_disabled` — provider failed and strict mode was off, so fallback ran silently.
- `no_runtime_config` — user did not pass `--runtime-config`; no learned provider was ever activated.

**Strict-mode configuration:** If the user wants the build to fail rather than fall back, they must set `strict: true` in their runtime config. Document this per ADR-0002 if asked:

```bash
# ADR-0002 is at docs/adr/0002-shape-provider-fallback.md (if it exists)
# or reference CLAUDE.md: "Providers are optional proposal sources under a stable contract"
```

## Mitigation

- If the fallback was due to a quality-gate failure on the provider's mesh, that is correct behavior — the provider produced a result that didn't meet the conformance threshold.
- If the user wants strict mode, update their runtime config: `"strict": true`.
- If the fallback was silent when it should have been loud, check whether `strict` defaults need to be documented more clearly in the runtime config examples.

## Communication

Apply Macro: provider unavailable from `docs/support/readiness-checklist.md`. Reference the `attempted`/`actual`/`reason` fields in the trace when explaining.

## Escalation

Escalates only if the fallback produced a build that certified but is materially worse than what the user's provider would have produced — this is a design question, not a bug, unless certification thresholds are miscalibrated.

## Postmortem trigger

Any confirmed case where strict mode was not respected (i.e. the build fell back despite `strict: true`).
