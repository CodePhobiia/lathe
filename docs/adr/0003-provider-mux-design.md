# ADR 0003: Shape-provider selection via mux with probe-then-fallback

- **Status:** Accepted
- **Date:** 2026-04-23
- **Ticket:** Plan 03 Phase 4; Plan 07 Phase 8 (BL-37 strict mode);
  Plan 01 Phase 5 (`shape_providers.py` split).
- **Related:** `lathe/providers/selection.py`, `lathe/providers/registry.py`,
  `lathe/providers/transport/http.py`, `lathe/providers/adapters/*.py`;
  ADR-0001 (shape handoff contract), ADR-0002 (fallback policy).

## Context

Lathe supports multiple shape providers under the frozen
`lathe.shape.intent_mesh_handoff_v1` contract: a built-in heuristic
fallback (`reference_conditioned_v1`), an HTTP bridge to
Hunyuan3D-2.1 (`hunyuan2_1_http_v1`), and a local VGGT multiview
runtime (`vggt_local_v1`). More providers will land over time.

Each provider has different availability characteristics: the built-in
has none (always available), Hunyuan requires a reachable HTTP
endpoint, VGGT requires a torch install and weights on disk. Selection
logic that is scattered across call sites — "is torch importable? is
the endpoint reachable? does this mode require multiview?" — leads to
subtle drift (different rules in different places) and to network I/O
being executed at import time rather than at explicit selection time.

The selection layer is also where strict-mode policy (BL-37) lands:
the decision of whether to fail the build or fall back is per-run and
must be made in one place with full knowledge of probe results and
runtime-config flags.

## Decision

1. **Central mux in `lathe/providers/selection.py`.** All shape
   provider selection goes through `resolve_shape_provider` and
   `maybe_run_shape_provider`. These are the only entry points; call
   sites do not duplicate the rules.
2. **`auto` vs explicit selection.** `shape.provider: "auto"` triggers
   mode-and-refs-driven heuristics (multiview reconstruct → VGGT;
   single-image generate/reconstruct → Hunyuan; no image refs → built-in
   reference). Any other value selects explicitly and skips heuristics.
3. **Alias table in `providers/registry.py::PROVIDER_ALIASES`.** Short
   names (`hunyuan2_1_http`, `vggt_local`, `reference_conditioned`)
   resolve to full IDs. The alias table is the only place short forms
   are recognised; call sites always see the full ID after
   `normalize_provider_id`.
4. **Probe-then-fallback ordering.** After selection, a capability
   probe (health check, torch import test, endpoint ping) runs via
   `probe_shape_provider`. If the probe fails in non-strict mode, the
   mux falls back to `reference_conditioned_v1` and records the
   reason. If the probe fails in strict mode, the mux raises
   `ShapeProviderExecutionError` with code `provider_fallback_blocked`.
   Execution-time errors follow the same split.
5. **Network I/O quarantine in `providers/transport/`.** All `urllib`
   calls live in `providers/transport/http.py`. Selection and the
   registry import no network modules; importing
   `lathe.providers.registry` is safe at interpreter start and
   exercises no optional dependencies.
6. **Strict-mode semantics (BL-37).** `shape.strict=true` means
   "never silently fall back". V0.1.x emits a `DeprecationWarning`
   when a learned provider is selected with `strict=false` and
   `allow_fallback` is not explicitly set; the default flips to
   `strict=true` in V0.2. `allow_fallback=true` is the explicit
   opt-in for legacy behaviour during the deprecation window.

## Rationale

### Why centralise selection

Before the split, provider rules were spread across `shape_backend.py`,
`executor.py`, and ad-hoc CLI glue. A bug like "VGGT selected despite
single-image input" could be introduced in any of those files and
would only show up when a user tripped that exact mode combination.
Centralising the rules makes them testable (`tests/test_shape_providers.py`)
and makes drift between sites impossible.

### Why alias the short names

Runtime configs in `examples/runtime_configs/*.json` and CLI args are
human-facing; full IDs like `lathe.provider.shape.hunyuan2_1_http_v1`
are machine-facing. The alias layer absorbs that without requiring
users to type full IDs and without letting short forms leak into the
internal trace (which always writes the full ID).

### Why probe before run

Running an unreachable provider and parsing the exception to decide
fallback is expensive (timeouts) and loses structured context. A
probe up front produces a structured report (`available`, `code`,
`message`, `details`) that the mux can consume cleanly, and that
`lathe doctor` can surface identically.

### Why quarantine network I/O

Selection and registry code runs at import time in tests and in
`lathe doctor`. If `urllib` imports (or worse, network calls) leaked
into those paths, a disconnected developer would be unable to run
unit tests. Pinning network I/O to `providers/transport/` makes the
selection and registry layers safe to import anywhere. The rule is
enforced by the import-linter "providers isolation" contract (see
ADR-0005).

### Why strict mode is opt-in today and default tomorrow

BL-37's deprecation window matches Plan 08 Phase 11's policy: one
minor version of warning before a default flip. Today, users who
install Hunyuan or VGGT want them to run when available and fall back
when not — `strict=false` captures that. In V0.2, the same users will
want the opposite (don't silently give me a reference-path build I
thought was learned), so the default flips. The `allow_fallback=true`
flag is the explicit backstop for anyone who genuinely wants the old
behaviour permanently.

## Consequences

### Positive

- One place to read the selection rules (`resolve_shape_provider`).
- `tests/test_shape_providers.py` can mock the probes
  (`_probe_vggt`, `_probe_hunyuan_endpoint`) and exercise every
  selection path deterministically.
- `lathe doctor` and the mux share probe code, so their reports
  cannot diverge.
- Adding a new provider is a four-file change (registry entry,
  adapter module, alias entry, new test) with no ripple into
  executor or CLI.
- The selection/registry modules are zero-dependency at import time.

### Negative / accepted risks

- The `allow_fallback` flag is a transitional API. It must be removed
  on the V0.2 default flip or it will outlive its deprecation window
  and become a permanent footgun.
- The probe adds a small latency to every build that uses a learned
  provider (one health check, one import test). Acceptable; it is
  cheap compared to the run itself.
- The mux holds more state than a pure function would (selection
  result + probe report + execution report). Keeping all three in a
  single `provider_report` dict is the chosen trade; splitting them
  would force callers to re-assemble the trace.

## Alternatives considered

- **Per-call-site provider selection.** Rejected: exactly the
  pre-split state, demonstrably drift-prone.
- **Always try, never probe.** Rejected: loses structured failure
  context; every unavailability becomes a generic execution error
  and users cannot tell "endpoint unreachable" from "auth failed".
- **Strict-by-default from V0.1.** Rejected: breaks smoke ergonomics
  for users whose Hunyuan endpoint is occasionally down. The
  deprecation window gives users one version to adapt their runtime
  configs.
- **Kill the alias table; require full IDs everywhere.** Rejected:
  pushes friction onto every runtime-config author and every CLI
  user for ~0 benefit (the alias layer is 20 lines and fully tested).

## Re-evaluation criteria

Re-open this decision if:

1. A provider needs to be selectable by something other than mode +
   refs (e.g. per-project policy, per-asset quality budget). At that
   point the heuristic block grows into a proper policy engine and
   probably wants its own module.
2. Probe latency becomes load-bearing (many providers, tight build
   loops). Introduce a per-process memoisation at that point —
   Plan 03 Phase 7 item 3 already flags capability-probe
   deduplication as a consolidation target.
3. A non-shape stage acquires multiple providers. Generalise the mux
   into `lathe/providers/mux.py` and let topology/UV/surface use the
   same machinery instead of each building their own.
