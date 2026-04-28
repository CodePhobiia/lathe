# Pull request

## Summary
<!-- What changed, and why? 1-3 bullet points. -->

## AGENTS.md coordinated-change checklist

Check every box that applies. Language-contract changes must land as a single coordinated PR across all layers.

- [ ] Preserved the stable shape-stage contract ID `lathe.shape.intent_mesh_handoff_v1` (or this PR is an explicit, approved migration).
- [ ] For language-contract changes, updated **all** of: `spec/lathe-v0.1.md`, `grammar/lathe.lark`, `schema/lathe.schema.json`, parser, normalizer, resolver, checker.
- [ ] Added or updated tests that cover the new or changed behavior.
- [ ] Kept at least one runnable `generate` example and one runnable `reconstruct` example.
- [ ] Did **not** weaken any validator (`semantic_quality`, `visual_quality`, `flow_quality`, `surface_quality`, `silhouette`) unless the PR explicitly describes the intent and justification.
- [ ] Preserved stable backend IDs, the shape bundle contract, and downstream topology/UV/packaging contracts unless this is an explicit migration.
- [ ] Ran the fast pytest partition locally, or explained why a broader/narrower partition was appropriate.
- [ ] Ran `python -m lathe.cli check` on any example touched.
- [ ] Updated `CHANGELOG.md` under `[Unreleased]`.
- [ ] Followed the specialist review requirements in `docs/review_requirements.md` for language, provider, security, or release-sensitive changes.
- [ ] Signed commits with DCO (`Signed-off-by: Name <email>`).

## Stages touched
<!-- refs → intent → shape → topology → uv → surface → execution → rig → interfaces → physics → optimize → validate → package → publish -->

## Backwards compatibility
<!-- Any behavior change a current user would notice? Any migration steps? -->

## Test plan
<!-- How did you verify this locally? -->
