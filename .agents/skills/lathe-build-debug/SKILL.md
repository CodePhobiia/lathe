---
name: lathe-build-debug
description: Use when a Lathe asset or build is failing and the goal is to reproduce, isolate, and fix the failure without weakening the public contract.
---

Diagnose the failure stage first, then make the smallest defensible fix.

Workflow:
1. Reproduce with `python -m lathe.cli check`, then `plan`, then `build`.
2. Inspect the closest stage-local artifacts in `dist*/<asset>/stages/` and the build report.
3. Decide whether the defect is in:
   - source asset data
   - resolver or checker logic
   - backend selection
   - shape provider output handling
   - deterministic downstream execution
4. Fix the narrowest layer that explains the failure.
5. Add a regression test whenever the bug is not purely local to one example.
6. Re-run the narrow reproduction, then `python -m pytest -q`.

Guardrails:
- Do not lower certification thresholds unless the evidence in the trace justifies it.
- Do not rename stable backend or provider IDs just to fix a local bug.
- Prefer mocked tests for provider or network behavior.
