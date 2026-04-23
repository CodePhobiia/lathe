---
name: lathe-backend-swap
description: Use when swapping or extending a Lathe backend or shape provider implementation while preserving the public backend contract and downstream pipeline expectations.
---

Change the implementation under a stable contract, not the contract itself.

Workflow:
1. Identify the stable contract ID that must remain unchanged.
2. Inspect:
   - `lathe/backends.py`
   - `lathe/shape_backend.py`
   - `lathe/shape_providers.py`
   - `lathe/executor.py`
3. Preserve input expectations, output bundle fields, and trace metadata.
4. Prefer a provider mux or adapter layer over direct invasive rewrites.
5. Add capability probing and structured failure handling.
6. Add or update mocked tests that exercise the new seam.
7. Re-run `python -m pytest -q`.

Guardrails:
- Keep `lathe.shape.intent_mesh_handoff_v1` stable unless the task explicitly requests a migration plan.
- Do not change downstream topology, UV, or package contracts unless that is the actual task.
