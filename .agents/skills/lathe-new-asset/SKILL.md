---
name: lathe-new-asset
description: Use when asked to create a new Lathe asset, variant, or production-ready example that should build end to end in this repository. Do not use for language grammar or schema changes.
---

Create or extend a Lathe asset while preserving the existing language contract.

Workflow:
1. Inspect the closest existing example under `examples/`.
2. Choose the narrowest asset kind and build mode that fit the request.
3. Add or reuse minimal refs under `examples/refs/` when needed.
4. Keep names, parts, and build settings consistent with current Lathe conventions.
5. Validate with:
   - `python -m lathe.cli check <file>`
   - `python -m lathe.cli plan <file> <asset>`
   - `scripts/lathe_asset_loop.sh <file> <asset>`
6. If the new asset changes expected behavior, add or update a regression test.
7. Summarize the produced outputs and any scaffold limitations.

Guardrails:
- Do not broaden the language grammar unless the task explicitly requests it.
- Keep example refs small and local to the repo.
- Prefer one strong example over several incomplete ones.
