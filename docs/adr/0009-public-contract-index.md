# ADR 0009: Maintain a public contract index for downstream boundaries

- **Status:** Accepted
- **Date:** 2026-04-25
- **Ticket:** Architecture/contracts documentation hardening
- **Related:** ADR-0001, ADR-0003, ADR-0004, ADR-0005, ADR-0006, ADR-0008,
  `docs/architecture/contracts.md`, `docs/versioning.md`

## Context

Lathe exposes several kinds of public surface: the `.lth` language, backend and
stack IDs, the shape handoff, provider descriptors, stage bundle artifacts,
validation reports, package traces, schema-versioned manifests, engine
manifests, and report renderers. Those surfaces are implemented by many modules,
some of which are intentionally refactorable internals.

Without a single contract map, downstream docs can accidentally teach users to
depend on whichever helper module currently emits an artifact. That makes
healthy refactors look like breaking changes and hides real contract changes in
ordinary implementation diffs.

## Decision

Maintain `docs/architecture/contracts.md` as the authoritative public-contract
index. It identifies the ground-truth source file or schema for each public
surface, names the compatibility rule, and lists implementation areas that are
internal-only.

## Rationale

Lathe already has strong decisions for individual areas: shape handoff pinning,
provider muxing, plugin entry points, import layering, validator composition,
and the geometry kernel. The missing piece is the cross-cutting rule that tells
readers which artifacts may be consumed by downstream systems and which modules
are only how the reference compiler currently produces them.

Putting that rule in architecture docs keeps it visible to authors, plugin
writers, and maintainers. Recording it as an ADR makes future weakening visible:
if a new page wants to document an internal helper as a downstream dependency,
it must either point back to the public contract index or deliberately supersede
this decision.

## Consequences

### Positive

- Downstream users get one stable map for language, shape, provider, stage,
  validation, report, and manifest contracts.
- Implementation modules can be refactored without turning accidental docs into
  compatibility promises.
- Future contract changes have a migration checklist that links versioning,
  schemas, docs, and contract tests.

### Negative / accepted risks

- The contract index must be kept current when a new public artifact lands.
  Stale architecture docs would be worse than no index because they imply
  safety where none exists.
- Some surfaces are currently protected by schemas and focused unit tests rather
  than dedicated contract tests. The index calls that out instead of pretending
  every public surface has the same tripwire strength as the shape handoff.

## Alternatives considered

- **Leave boundaries distributed across existing ADRs.** Rejected: readers still
  need to stitch together language, provider, manifest, and report rules from
  many pages.
- **Mark every module under `lathe/` as public.** Rejected: it would freeze the
  reference implementation and make stage extraction or provider refactors look
  like breaking API changes.
- **Keep the rule only in `docs/versioning.md`.** Rejected: versioning explains
  bump policy, but it does not identify internal-only modules or downstream doc
  boundaries.

## Re-evaluation criteria

Re-open this decision if:

1. Lathe introduces a formal Python SDK with a stable import surface distinct
   from CLI artifacts and schemas.
2. Engine manifests gain dedicated JSON/YAML schemas and need their own
   schema-version policy page.
3. More than one probabilistic stage becomes public, requiring a family-level
   contract index rather than the current single shape-handoff framing.
