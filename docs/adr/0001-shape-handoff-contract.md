# ADR 0001: Freeze `lathe.shape.intent_mesh_handoff_v1` as the single probabilistic seam

- **Status:** Accepted
- **Date:** 2026-04-23
- **Ticket:** Plan 03 Phase 4, Plan 04 Phase 9 (BL-25 contract tripwire)
- **Related:** `lathe/backends.py` BACKENDS entry for `lathe.shape.intent_mesh_handoff_v1`;
  `tests/contract/test_shape_handoff_v1.py`; CLAUDE.md "core invariant" statement.

## Context

Lathe's compiler pipeline runs 11+ stages end to end. Every stage except
shape is deterministic by design: topology cleanup, UV unwrap, surface
bake, validate, package, publish all produce byte-identical output for
identical input. Shape is the only probabilistic step — it is the
boundary at which an AI-native or learned component may be asked to
produce a mesh from intent, references, or both.

If shape's *interface* also drifts — required inputs, output field set,
provenance contract — every downstream stage loses its ability to
assume stable artifacts. A single unversioned widening of the shape
handoff (e.g. silently dropping `candidates[].units`) would break
topology, UV packing, and validation simultaneously and leave callers
with no way to detect the break until a bundle explodes far downstream.

The contract ID `lathe.shape.intent_mesh_handoff_v1` is referenced at
~75 sites across the codebase — not because it is cosmetically central
but because it is load-bearing: it is the handoff between the one
probabilistic step and the rest of the compiler.

## Decision

Treat the contract ID `lathe.shape.intent_mesh_handoff_v1` as a
**public, frozen contract**. Its ID, its pinned top-level field set,
its inner `contract.inputs` / `contract.outputs` required fields, and
its byte-level canonical serialisation are all tripwired by a test in
`tests/contract/test_shape_handoff_v1.py`. A new version *replaces*
this ID with a new one (e.g. `…_v2`), never mutates it.

Providers that sit under this contract (`reference_conditioned_v1`,
`hunyuan2_1_http_v1`, `vggt_local_v1`, future learned providers) are
proposal sources. They can come and go. The contract above them does
not.

## Rationale

### Why freeze the ID specifically

The ID is how 75 call sites reach this backend. Changing the ID without
a migration would require a coordinated rename across source, schema,
runtime configs, provider registry, validators, plans, docs, and tests
in one atomic change — which is exactly the kind of change a
contract-freeze tripwire is designed to block until the change is
intentional. The frozen ID forces any migration to land as a
documented v2, not a silent in-place edit.

### Why tripwire the byte-level hash, not just the field set

The field set alone is not sufficient: a reordering, rename, or
subtle semantic change (e.g. swapping "candidate_id" for "id") would
slip past a field-name check. The pinned SHA-256 of the canonical
JSON serialisation of `BACKENDS[CONTRACT_ID]` catches any of these
edits and forces the maintainer to re-read the diff before updating
the pin. See `PINNED_CONTRACT_SHA256` in the contract test. When the
hash fails the test message directs the maintainer to re-read the
diff, verify downstream is wired to the existing shape, then update
both the hash pin and the field-set frozensets (`PINNED_TOP_LEVEL_KEYS`,
`PINNED_INNER_CONTRACT_KEYS`, `PINNED_REQUIRED_OUTPUT_FIELDS`) together.

### Why the hash must be updated in the same commit as the contract edit

The test fails loudly when the hash drifts. That is a feature, not a
bug — it surfaces every contract edit as an intentional migration
rather than a drive-by change. If the hash were updated after the fact,
the intent of the change would be invisible to review.

## Consequences

### Positive

- Downstream stages (topology, UV, surface, validate, package) can
  assume a stable shape-bundle shape without defensive parsing.
- Provider churn is absorbed below the contract boundary — swapping
  Hunyuan for a different HTTP model, or adding a new local runtime,
  does not ripple through the pipeline.
- The 75 call sites survive provider changes.
- Reviewers see contract edits as first-class events in the diff
  (the hash pin must be updated, attracting attention).

### Negative / accepted risks

- Adding fields to the contract — even strictly additive ones — is
  deliberately painful. A new optional output field requires updating
  both the field-set frozenset and the hash pin. This is by design:
  additive drift is still drift, and optional-today often becomes
  required-tomorrow.
- A future v2 migration carries real cost: new ID, new entries in
  `BACKENDS`, new contract test module, migration of every runtime
  config and provider that bound to v1. We accept that cost as the
  price of never having to debug silent contract drift.
- Maintainers must resist the temptation to "just fix the test"
  when the hash changes — the test is the whole point.

## Alternatives considered

- **Fuzzy version tag (no hash pin).** Rejected: a version bump is a
  convention that can be forgotten; a hash mismatch is a fact that
  cannot be skipped.
- **Freeze only the required-output field names.** Rejected: does not
  catch renames, reorders, or semantic drift in `contract.summary` /
  `contract.inputs.mode_requirements`.
- **Treat shape as an ordinary internal API.** Rejected: 75 call sites
  and one probabilistic step make this the highest-leverage surface
  in the compiler; an internal API policy does not match its blast
  radius.

## Re-evaluation criteria

Re-open this decision if **any** of the following becomes true:

1. A second probabilistic stage is introduced (e.g. a learned UV
   unwrap or learned topology). At that point the "single
   probabilistic seam" framing no longer describes the pipeline and
   a contract-family policy, not a single-contract policy, is needed.
2. A v2 migration is needed. This ADR stays Accepted as the v1 record;
   a new ADR documents the v2 contract and the migration path. The v1
   contract and its tripwire remain in place during the deprecation
   window.
3. The ~75 call-site count grows materially (>150) without a
   corresponding consumer-side abstraction. That is a sign that
   downstream code is over-coupled to the shape bundle shape and a
   consumer-side adapter layer should be introduced before the next
   contract change.
