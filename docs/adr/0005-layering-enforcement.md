# ADR 0005: Enforce package layering via `import-linter` contracts

- **Status:** Proposed
- **Date:** 2026-04-23
- **Ticket:** Plan 03 Phase 3 (surgeon-plugins task #1, Wave 5.II);
  Plan 03 Phase 7 (pydeps audit).
- **Related:** ADR-0004 (plugin entry points — depends on a stable
  `lathe.contracts` surface); Plan 03 target-architecture diagram.

## Context

Plan 03 defines a target architecture as a layered import graph:

```
frontend  →  core  →  contracts  →  { shape, backends, providers, validators }
```

- `frontend` = parser + grammar + normalizer + resolver + checker
- `core` = planner + executor + capabilities + runtime_config
- `contracts` = pure protocols / stage contracts (no numeric or I/O deps)
- the leaf layer = implementations of those protocols

Without tooling, layering drifts. A future contributor under deadline
will write `from lathe.executor import BuildExecutor` inside a
validator, or `import numpy` inside `lathe.contracts`, and no
reviewer will catch it until the next architectural-audit pass
months later. By then the easy fix is dead and the cleanup cost has
compounded.

The industry-standard tool for enforcing layering in Python is
`import-linter` (config in `.importlinter`, run in CI). It reads the
real import graph and fails CI when a declared contract is violated.

## Decision

Adopt `import-linter` with four contracts, wired into CI via
`scripts/check_arch.sh` and `tests/test_architecture.py`.

### Contract 1 — Layers

`frontend → core → contracts → { shape, backends, providers, validators }`.
Forbid reverse imports. No leaf-layer module imports from `core` or
`frontend`; `contracts` imports from nothing above.

### Contract 2 — Backend independence

`lathe.backends.*` sibling packages cannot import each other. The
Blender topology adapter does not know about xatlas; the USD
packager does not know about the shape handoff adapter. Each
backend's only upstream import is `lathe.contracts`.

### Contract 3 — Contracts purity

`lathe.contracts` is forbidden from importing `numpy`, `trimesh`,
`PIL`, and `urllib`. The contracts layer is pure-Python protocol and
typed-dict definitions only; anything that costs import-time I/O or
native-library load lives in a leaf layer.

### Contract 4 — Providers isolation

`lathe.providers.adapters.*` may import `lathe.providers.transport`
but not `lathe.shape.backend` or any other leaf-layer internal. This
is the rule that keeps the network-I/O quarantine (ADR-0003) from
leaking back into the shape kernel.

## Rationale

### Why `import-linter` specifically

It reads the real import graph (not a convention list or a docstring
contract). Contracts are declared in a single `.importlinter` file.
Failures in CI produce a specific "module X imports module Y which
violates contract Z" message — actionable without debugging.

### Why four contracts and not one

A single "layers" contract would catch the big cross-layer violations
but would miss intra-layer issues like "xatlas imports Blender
adapter" or "contracts imports numpy". Each of the four contracts
enforces one property, and each property has a specific cost if
violated: layer inversion causes cycles, backend coupling blocks
plugin independence, contracts impurity breaks plugin authors who
cannot install numpy in their environment, provider leakage undoes
the transport quarantine.

### Why these four specifically

They match the four properties the plugin model (ADR-0004) assumes:
plugin authors import only `lathe.contracts`; plugins of the same
kind do not know about each other; the contracts layer is light
enough that a plugin author's dependency tree does not pull in the
entire compiler; provider adapters stay decoupled from downstream
stages. Without these four guarantees, plugins work today and break
tomorrow on internal refactors.

### Why a separate test file AND a script

`tests/test_architecture.py` fails unit-test runs so local
development catches violations early. `scripts/check_arch.sh` is
the CI hook and can be run independently when investigating a
layering issue without running the full test suite.

## Tightening over time

Import-linter supports per-contract `ignore_imports` lists for
seed-point violations. The plan is:

1. **Land with a seed `ignore_imports`** covering every current
   violation, so CI turns green immediately.
2. **Publish the pydeps graph.** `python -m pydeps lathe
   --max-bacon=2 --noshow -o deps.svg` attached to this ADR as
   `docs/adr/0005-dep-graph.svg` (or linked from it) gives reviewers
   a picture of the current graph.
3. **Tighten contract-by-contract.** Each wave that touches a
   violation either removes it or documents why it stays. The
   `ignore_imports` list shrinks monotonically.
4. **Strict mode at Plan 03 Phase 8.** When the exit criteria land
   (≥ 6 ADRs, no cycles, fan-in/fan-out budgets met), the
   `ignore_imports` list must be empty or every remaining entry
   must have its own ADR-style justification in `.importlinter`
   comments.

## Consequences

### Positive

- Layer inversions fail CI instead of drifting for months.
- Plugin authors can trust `lathe.contracts` as a narrow, stable
  surface — Contract 3 guarantees it does not grow heavy deps.
- The pydeps graph acts as living documentation for the import
  architecture; ADR-0005 is the written form of what the graph
  shows.
- New contributors get layer-violation errors at the first bad
  import, not at architecture-audit time.

### Negative / accepted risks

- Seed `ignore_imports` lists can become a parking lot if nobody
  tightens them. Mitigated by the Phase 8 strict-mode gate; every
  remaining ignore must be justified by the time Phase 8 lands.
- Import-linter itself is a new CI dependency. Low risk: pure Python,
  small install footprint.
- False positives on dynamic imports are possible (import-linter
  reads static imports). Mitigated by `ignore_imports` entries with
  comments explaining the dynamic pattern; dynamic imports are rare
  in Lathe and are concentrated in `lathe/providers/selection.py`'s
  probe-function indirection.
- Import-linter contracts enforce the *declared* graph; they do not
  prove the declared graph is the right one. This ADR plus Plan 03
  target-architecture diagram is the record of what the graph should
  be; the tool enforces the record.

## Alternatives considered

- **Custom AST-walking test.** Rejected: reinvents `import-linter`
  and accumulates maintenance cost; declarative `.importlinter`
  config is easier to read and harder to silently weaken.
- **Docstring / convention only.** Rejected: proven to drift in every
  codebase that has tried it. Plan 01 Phase 1 explicitly makes
  linting mechanical where it can be.
- **Single "no cycles" check (pydeps or networkx only).** Rejected:
  catches cycles, misses the narrower layer and purity properties
  that the four-contract design guarantees.
- **Enforce at runtime (import hook).** Rejected: adds import-time
  cost to every user run for a property that only needs to be
  checked in CI.

## Re-evaluation criteria

Re-open this decision if:

1. A fifth leaf layer emerges (e.g. a new `lathe.bridges` or
   `lathe.execution` area). Add the layer to Contract 1 at that
   point; do not silently widen existing contracts.
2. Import-linter's maintenance status degrades. At that point
   evaluate `pydeps` gating + a custom CI script as a replacement,
   but keep the four properties — the choice of tool is separable
   from the choice of properties.
3. Plugin authors report `lathe.contracts` has grown heavy transitive
   deps. Contract 3 has failed somehow; tighten rather than relax.
4. CI surfaces flaky layering failures. Almost certainly a dynamic
   import that needs an explicit `ignore_imports` comment — not a
   reason to weaken the contracts.

## Cross-references

- Import-linter config: `.importlinter` (to be created in
  surgeon-plugins task #1).
- Architecture test: `tests/test_architecture.py`.
- Script: `scripts/check_arch.sh`.
- pydeps graph: `docs/adr/0005-dep-graph.svg` (to be generated
  during Plan 03 Phase 7 item 1).
- Once surgeon-plugins task #1 lands, this ADR flips to Accepted.
