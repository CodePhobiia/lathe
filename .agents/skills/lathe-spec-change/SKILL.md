---
name: lathe-spec-change
description: Use when changing the Lathe language contract itself, including new fields, grammar, schema, semantic rules, or diagnostics.
---

Treat the spec as the source of truth and update every affected layer.

Workflow:
1. Start in `spec/lathe-v0.1.md` and define the change precisely.
2. Update the grammar in `grammar/lathe.lark` if the surface syntax changes.
3. Update `schema/lathe.schema.json` for normalized AST shape changes.
4. Update parser, defaults, normalizer, resolver, checker, and planner logic as needed.
5. Update examples so at least one concrete source file exercises the new feature.
6. Add or update regression tests for parsing, normalization, semantics, and build planning.
7. Run `python -m pytest -q`.

Guardrails:
- Do not leave spec, grammar, schema, and implementation out of sync.
- Prefer additive, backward-compatible changes unless the task explicitly requests a breaking change.
