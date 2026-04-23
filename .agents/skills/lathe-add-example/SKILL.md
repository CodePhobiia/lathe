---
name: lathe-add-example
description: Use when asked to add a new Lathe example asset, variant, or reference bundle that demonstrates an existing feature end to end.
---

Add one example that is runnable, representative, and minimal.

Workflow:
1. Pick the closest existing example as a template.
2. Keep the new example scoped to one capability or asset family.
3. Place any new refs under `examples/refs/`.
4. Prefer the built-in fallback or documented mock runtime path so the example remains runnable in this repo.
5. Run:
   - `python -m lathe.cli check <file>`
   - `python -m lathe.cli plan <file> <asset>`
   - `scripts/lathe_asset_loop.sh <file> <asset>`
6. If the example introduces a new expected flow, add or update a test.

Guardrails:
- Do not add large binary refs unless they are necessary and compact.
- Keep examples pedagogical: clear names, clear intent, and clear outputs.
