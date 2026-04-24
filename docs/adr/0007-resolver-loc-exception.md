# ADR 0007: Accept `lathe/resolver.py` 540 LOC as a file-size exception

- **Status:** Accepted
- **Date:** 2026-04-23
- **Ticket:** `plans/WAVE4_BACKLOG.md` BL-18 (Wave 4.I)
- **Related:** Plan 01 (module size cap of 500 LOC), BL-8 (Wave 3 deferral under the
  "split only if multi-concern" clause), reviewer-plan-audit Wave 3 report.

## Context

Plan 01 sets a soft cap of 500 LOC per module as a readability and onboarding
heuristic. `lathe/resolver.py` is currently 540 LOC — 40 LOC (8%) over the cap.

BL-8 in Wave 3 deferred the split on the grounds that the file expresses one
cohesive concern. The Wave 3 reviewer-plan-audit then correctly objected that a
silent defer is not the same as an explicit decision, and requested either a
split under Path A or a documented exception under Path B. BL-18 is that
explicit decision.

## Decision

Accept `lathe/resolver.py` at 540 LOC as a file-size exception. Do not split
it into a `lathe/resolver/` package. Revisit under the re-evaluation criteria
below.

## Rationale

### The file is one cohesive concern

`lathe/resolver.py` implements a single concern: **materialise a named asset
declaration into a fully-resolved normalised asset dict.** Every top-level
helper and every `Resolver` method exists to serve one pipeline, `Resolver.
materialize_asset`, which reads top-to-bottom as a linear composition:

1. derive the explicit asset (asset-or-variant with its patches applied)
2. walk the `uses` chain across profiles and contracts
3. seed `merged` from inherited `defaults` / `rules` / `repair`
4. fold in the kit and family (`from` / `assembly.family`)
5. overlay the explicit asset
6. re-merge family geometry/features/surface/assembly/space/repair over the
   result
7. resolve `space` and `repair_policy` specs, rewire `validate.repair`
8. resolve palette, materials, components, mechanisms, traits
9. resolve the surface stack (program, policy, backend, decal libraries, mask
   programs, trim sheets, patterns, material graph)
10. resolve execution (profile, inspection policy, library bindings)
11. resolve `build.surface` (bake profile, render fixture)
12. resolve V1.1+ named policies (fit profile, reconstruct policy, adapt
    policy, assembly policy, transfer rules)
13. hand the merged dict to `normalize_asset`

Every resolver helper — `_resolve_palette`, `_resolve_material`,
`_resolve_surface_*`, `_resolve_component`, `_resolve_mechanism`,
`_resolve_trait`, `_resolve_named_policies`, `_resolve_reference_sets`,
`resolve_space_spec`, `resolve_repair_policy_spec`, `resolve_use_chain`,
`derive_explicit_asset`, `apply_patch` — is called from
`materialize_asset`, and each reads or mutates the same `merged` dict. The
module-level helpers (`_dedupe`, `_merge_space_spec`,
`_merge_repair_policy_spec`, `_repair_policy_to_validate_repair`,
`_resolve_required`, `_resolve_optional`) are small pure functions that
exist to keep `materialize_asset` readable.

There is no seam inside this file between "uses-chain resolution" and
"variant patching" and "reference-set resolution" that a caller ever uses
independently. The only public entry points are `Resolver`,
`materialize_asset` (module-level shim), and the re-exported
`ResolutionError` / `UnresolvedNameError`. Every private helper is an
implementation detail of the one pipeline.

### Why splitting would fragment, not clarify

The Path A sketch proposed `uses.py` / `variants.py` / `refs.py` / `core.py`.
Evaluating each:

- **`uses.py`** — `resolve_use_chain` is 21 LOC and is called exactly once,
  inside `materialize_asset` (line 331). Extracting it to another module
  buys no isolation; it just adds an import hop for a one-call helper.
- **`variants.py`** — `derive_explicit_asset` (13 LOC) and `apply_patch`
  (18 LOC) operate on the explicit asset *before* any merging. They are
  called by `materialize_asset` and recursively by `derive_explicit_asset`
  itself. Pulling them out would split a 31-LOC pair away from their only
  caller.
- **`refs.py`** — `_resolve_reference_sets` is 20 LOC and consumes
  `self.reference_set_map`, which is built in `Resolver.__init__` alongside
  30+ other namespace maps. Moving it to a sibling module would require
  either passing the full `Resolver` instance across the boundary or
  duplicating the map-building contract — both worse than the current
  inline call.
- **`core.py`** — whatever remained would still be the 210-LOC
  `materialize_asset` plus `Resolver.__init__`'s namespace wiring. The
  "orchestrator" after extraction would still be over 300 LOC on its own,
  and the extracted sub-modules would each be small enough that their
  existence is pure cost.

The LOC cap exists to protect readability and onboarding. The signal that
this file violates *that* intent would be: a reader opens it and cannot
orient. In practice the file opens with six short, named pure helpers, then
a `Resolver` class whose public method is `materialize_asset`, which reads
as a numbered pipeline. A split would trade that linear read for three
cross-module jumps to follow the same logic.

### What the 40 LOC actually represents

The bulk of the length is the namespace-map wiring in `Resolver.__init__`
(lines 78–116, ~39 LOC of `self.X_map = {decl["name"]: decl for decl in
program.get("Xs", [])}`). That pattern scales with the number of top-level
declaration kinds the language supports, and V1.1 / V1.2 / V1.3 each added
new kinds (reference sets, reconstruct policies, adapt policies, assembly
policies, fit profiles, transfer rules, execution profiles, render
fixtures, bake profiles, library bindings, material graphs, inspection
policies, repair policies, surface backends, surface policies, decal
libraries, mask programs, trim sheets). The LOC growth is a direct
consequence of the language surface growing; it is not accidental bloat.

## Consequences

### Positive

- Readers continue to see the full asset-resolution pipeline in one file,
  in execution order.
- No new import graph edges, no partial-import circularity risk against
  `normalizer` / `utils` / `errors`.
- Downstream code keeps `from lathe.resolver import Resolver,
  ResolutionError, UnresolvedNameError` working without a compatibility
  shim.
- Zero behaviour change — no risk of regression from a byte-for-byte move.

### Negative / accepted risks

- `lathe/resolver.py` formally violates the 500-LOC Plan 01 cap. Future
  linting that enforces the cap mechanically must allowlist this file.
- If the file grows further, the "one cohesive concern" argument weakens;
  a future contributor might reasonably want to split then.

## Re-evaluation criteria

Re-open this decision (and prefer Path A — the package split) if **any** of
the following becomes true:

1. `lathe/resolver.py` exceeds **650 LOC**. At that point the linear-read
   argument no longer holds in practice.
2. A new caller outside `materialize_asset` starts consuming one of the
   currently-private helpers (e.g. a V1.4 ref-resolution path that wants
   `_resolve_reference_sets` on its own, or a standalone variant
   patch-applier). That indicates a real seam that did not exist when this
   ADR was written.
3. A future language layer introduces a second orchestrator alongside
   `materialize_asset` (for example, a streaming or incremental resolver).
   Two orchestrators sharing one file would genuinely be two concerns.
4. `Resolver.__init__` namespace-map wiring exceeds roughly half the file
   on its own, suggesting the namespace-map building should become its own
   module.

None of these are true today.
