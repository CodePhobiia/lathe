# Runbook: Missing Generated Artifact

Build report says certified but an expected output file is absent from disk.

**Owner:** Tal Merri (@talmerri). Backup: `requires-human`

## Symptoms

- `dist/<asset>/stages/validate/certification_bundle.json` shows `certified: true` but the `.glb`, `.gltf`, `.obj`, or `.usd` is missing.
- `package_manifest.json` lists a file that does not exist at the listed path.
- `lathe build` exits 0 but the output directory is empty or incomplete.

## First response (≤5 min)

1. Re-list the output directory: `ls -la dist/<asset>/` (or `dir dist\<asset>\` on Windows).
2. Check filesystem write permissions on the output path.

## Investigation

Inspect the package manifest to confirm what was expected vs what landed:

```bash
python -c "
import json
m = json.load(open('dist/<asset>/stages/package/trace_manifest.json'))
print(json.dumps(m, indent=2))
"
```

Check whether `LATHE_ALLOW_EXTERNAL_OUT` is relevant. This env var gates writing output to paths outside the working tree. If it's not set and the `--out` path is outside the project, the package stage may have silently skipped writes.

Rerun with `--report html` to inspect bundling metadata:

```bash
python -m lathe.cli build examples/<file>.lth <asset> --out dist --report html
```

Open `dist/<asset>/report.html` and look at the package stage section for skipped or errored file writes.

Also check whether the output path has a name collision with a directory that already existed (e.g., a partial previous run). The package stage may have skipped overwriting.

## Mitigation

- If permissions: fix the target directory permissions or use `--out` to redirect to a writable path.
- If `LATHE_ALLOW_EXTERNAL_OUT` was the gate: set the env var if external output is intentional.
- If a name collision: remove the partial previous output and rerun.
- If a genuine package stage bug: open a labeled issue (`bug`, `release-blocker` if artifacts are missing on the canonical hero build).

## Communication

No standard macro for this case. Acknowledge within 24 h. Ask the user for `trace_manifest.json` and their `--out` path before triaging further.

## Escalation

Escalates to release blocker if artifacts are systematically missing from the canonical hero-family builds. A one-off permissions or path issue is P1.

## Postmortem trigger

Any confirmed case where the certification report and the package manifest agreed but files were missing from a published or recommended workflow.
