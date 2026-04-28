# Release-note value guidance

Every Lathe release note should explain what users can now do, trust, or debug
that they could not before. Internal implementation details belong in the
changelog only when they help users assess impact, migration risk, or release
readiness.

## Required shape

Each release note should include:

- **Headline value:** one sentence about the user-visible outcome.
- **Who benefits:** technical artist, tools engineer, AI pipeline builder, CI
  maintainer, or contributor.
- **Workflow impact:** the command, artifact, diagnostic, provider mode, or
  engine handoff that changed.
- **Evidence:** tests, examples, benchmark rows, docs pages, or release-gate
  commands that prove the change.
- **Migration or limitation:** what users must update, what remains
  experimental, and any approved release exception.

## Good release-note examples

Use value-first wording:

- "Canonical hard-surface examples now emit package manifests and validation
  reports that CI can archive and diff."
- "Provider timeouts now fail before network access when the runtime config
  violates the allowlist, making learned-provider builds safer to run in CI."
- "The quickstart now points at the current staged artifact layout, including
  `build_report.json`, selector manifests, previews, and validation reports."

Avoid implementation-only wording:

- "Refactored cache metadata helpers."
- "Updated executor internals."
- "Changed tests."

If an implementation detail matters, attach it to user impact:

- "Cache metadata now records real asset attribution, so `lathe cache clean
  --asset` does not remove unrelated entries."

## Release checklist prompt

Before promotion, the release owner should be able to answer:

1. Which user journey improved?
2. Which artifact, command, or diagnostic proves it?
3. Which canonical example or test covers it?
4. Is the feature product-critical, experimental, or intentionally deferred?
5. Does the release note state the limitation honestly?

If the answer is only "the code is cleaner," keep the change in the changelog
as maintenance and do not present it as product value.
