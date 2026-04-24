# ADR 0002: Blender and xatlas adapters degrade to deterministic reference paths, with attempted-vs-actual tracing

- **Status:** Accepted
- **Date:** 2026-04-23
- **Ticket:** Plan 03 Phase 4; Plan 07 (provider and capability tracing)
- **Related:** `lathe/backends.py` (BACKENDS for topology and UV);
  `lathe/providers/selection.py` (same attempted-vs-actual pattern for
  shape); `lathe/capabilities.py` probes; `build_report.json` tracing.

## Context

Lathe's first runnable stack binds topology to a headless-Blender
adapter (`lathe.topology.blender_hard_surface_v1`) and UV to xatlas
(`lathe.uv.xatlas_v1`). Both dependencies are heavy:

- Blender requires a working headless install on the build host, or
  the CLI must fall through to a deterministic pure-Python cleanup.
- xatlas is a compiled native library; wheel availability varies by
  platform and Python version.

A strict "require Blender and xatlas for every build" policy would
make smoke tests and CI on minimal runners impossible, and would
break the documented `scripts/lathe_smoke.sh` ergonomics. A silent
"fall back and pretend nothing changed" policy would leave operators
unable to tell whether a certified bundle came from the intended
adapter or from the reference path.

The contract is that **every build is reproducible**, and that a
reader of the build report can tell *which* adapter actually ran —
not merely which one was asked for.

## Decision

1. When Blender or xatlas is unavailable, the adapter falls back to a
   deterministic reference Python path that produces a conformant
   artifact under the same stage contract.
2. Every stage report records both the *attempted* backend/provider
   (what the stack / runtime config asked for) and the *actual*
   backend/provider (what ran). Both are written to `build_report.json`
   via the same structure the provider mux uses for shape (see ADR-0003).
3. When running without a `--runtime-config`, the default path is
   intentionally permissive: shape uses `reference_conditioned_v1`,
   topology and UV fall back to reference paths if the adapters are
   absent. This is the documented "conservative path" from CLAUDE.md
   and is required for `scripts/lathe_smoke.sh` to run on a bare
   interpreter.
4. Strict enforcement is opt-in: runtime configs may set
   `strict: true` on the shape stage (BL-37) to require the learned
   provider and fail with a non-zero exit if it is unavailable. An
   analogous knob is available for topology/UV when the operator
   needs to guarantee the Blender/xatlas path ran.

## Rationale

### Why graceful degradation and not hard failure

The compiler's value proposition is that a `.lth` source compiles on a
developer laptop, in CI, on a full build farm, and in a cloud runner
with variable capability. A first-run user hitting "install Blender to
smoke-test" would reasonably walk away. Degradation preserves the
smoke loop.

### Why attempted-vs-actual tracing is non-negotiable

Graceful degradation is only honest if the report says so. Without the
attempted-vs-actual split, an operator shipping a certified bundle has
no way to tell whether the "Blender-cleaned" topology in the trace is
actually Blender-cleaned or is the reference-path mesh. That
ambiguity would make certification untrustworthy. The two fields are
always populated; they are equal on the happy path and diverge on
fallback — both states are first-class.

### Why the same pattern as provider mux

The shape-provider mux already writes attempted-vs-actual
(`selected_provider_id` vs `actual_provider_id`, plus
`fallback_reason`) — see `lathe/providers/selection.py`. Topology and
UV reuse that shape so a single reader script can summarise fallback
across every stage, and so operators learn one trace-reading idiom.

### Why strict mode is a knob, not a global policy

Some operators need hard guarantees (production release pipelines).
Most do not (local iteration, CI smoke). A single global policy would
force one of those groups into friction. Per-stage strict flags under
`runtime_config` push the policy to where it is enforceable
per-invocation.

## Consequences

### Positive

- `scripts/lathe_smoke.sh` works on a bare Python install.
- CI smoke runs do not need Blender or xatlas.
- Every `build_report.json` is auditable for "did the intended
  adapter actually run here?" without parsing logs.
- Strict callers can opt into hard failure without imposing that cost
  on smoke-test users.

### Negative / accepted risks

- A reader who glances only at `actual_provider_id` and ignores the
  attempted/fallback fields may miss that they are reading a
  reference-path build. Mitigated by (a) always including the
  `fallback_reason`, (b) surfacing fallback in `lathe doctor`
  output.
- Two code paths per adapter (real + reference) double the surface
  that must stay in contract. Tests cover both paths; contract
  tripwires (ADR-0001 for shape, equivalent BL-25-style tests for
  other stages) pin the output shape regardless of which path ran.
- Operators who forget to set `strict: true` may ship a reference-path
  bundle to production unintentionally. Mitigated by the V0.2 default
  flip (BL-37 deprecation warning already in place) and by runtime
  configs that hard-code strict in release pipelines.

## Alternatives considered

- **Hard-require Blender and xatlas.** Rejected: breaks smoke ergonomics
  on day one and for contributors on minimal machines.
- **Silent fallback without tracing.** Rejected: makes certified
  bundles unverifiable.
- **Require strict=true at the CLI level unconditionally.** Rejected:
  pushes the friction onto every user to benefit release pipelines,
  which can opt in explicitly instead.

## Re-evaluation criteria

Re-open this decision if:

1. A third adapter needs fallback semantics and the attempted-vs-actual
   field layout needs consolidation into a shared module (currently
   duplicated between `providers/selection.py` and the topology/UV
   adapters).
2. Operator surveys show the "silent reference-path build" failure
   mode biting production. At that point flip default strict to true
   with a deprecation window (BL-37 already does this for shape).
3. Blender or xatlas wheels become universally available across
   supported platforms, making the fallback obsolete. Unlikely in
   practice; Blender is a large native dependency.
