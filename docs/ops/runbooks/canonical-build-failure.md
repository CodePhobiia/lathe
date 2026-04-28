# Runbook: Canonical Build Failure

`lathe build examples/courier_drone.lth courier_drone --out dist` fails on a system where it should pass.

**Owner:** Tal Merri (@talmerri). Backup: `requires-human`

## Symptoms

- Build exits non-zero on a clean install with the default (no runtime config) path.
- `dist/courier_drone/stages/validate/certification_bundle.json` contains `certified: false`.
- A previously passing CI run fails after a code change.

## First response (≤5 min)

1. Rerun with `--report json` to capture structured output.
2. Check `dist/courier_drone/build_report.json` for the first failing stage.

## Investigation

```bash
python -m lathe.cli build examples/courier_drone.lth courier_drone --out dist --report json
```

Collect these three files and compare to `tests/golden/`:

```
dist/courier_drone/build_report.json
dist/courier_drone/stages/validate/report.json
dist/courier_drone/stages/package/trace_manifest.json
```

Diff against golden snapshots:

```bash
python -m pytest tests/test_build.py -q -k courier_drone
```

**Stage-specific investigation:**

- **Shape stage failure:** Check `dist/courier_drone/stages/shape/trace.json` for `attempted` vs `actual` provider. A fallback to `reference_conditioned_v1` is expected on a no-runtime-config run; a shape stage that produces no mesh is the real failure.
- **Validate failure:** Open `stages/validate/certification_bundle.json` and find the gate with `passes: false`. Each validator (`semantic_quality`, `visual_quality`, `flow_quality`, `surface_quality`, `silhouette`) records an `evidence` field.
- **Package failure:** Check `stages/package/trace_manifest.json` for missing artifacts. Confirm the output directory is writable.

For regressions from a recent commit:

```bash
git log --oneline -10
git diff HEAD~1 lathe/executor.py lathe/planner.py lathe/checker.py
```

## Mitigation

- **Regression from a code change:** revert the offending commit; test on the golden snapshot before re-landing.
- **Golden snapshot drift:** if the change was intentional, regenerate the golden via `python -m pytest tests/ --update-golden` (check `tests/conftest.py` for the actual flag).
- **Genuine environment issue:** run `lathe doctor` to confirm all deps, then try with `scripts/lathe_asset_loop.sh examples/courier_drone.lth courier_drone dist`.

## Communication

For a CI regression: comment on the failing PR with the `build_report.json` diff. For a user report: apply Macro: certification failure from `docs/support/readiness-checklist.md`.

## Escalation

Any regression to the `courier_drone` canonical build is a release blocker (hero-family trigger #5 in `docs/support/readiness-checklist.md`).

## Postmortem trigger

Any confirmed regression that reached a published release tag.
