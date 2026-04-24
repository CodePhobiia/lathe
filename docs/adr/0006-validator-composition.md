# ADR 0006: Validator protocol and topological composition via `ValidatorPipeline`

- **Status:** Proposed
- **Date:** 2026-04-23
- **Ticket:** Plan 03 Phase 5 (surgeon-validators task #3, Wave 5.II)
- **Related:** ADR-0004 (plugin entry points — `lathe.validators`
  is one of the four groups); `lathe/core/stages/validate.py`
  (current ad-hoc composition); Plan 01 Phase 4b (executor
  decomposition).

## Context

Validators today are a set of free functions called sequentially from
`lathe/core/stages/validate.py`:

```
semantic = evaluate_semantic_quality(asset, runtime)
visual   = evaluate_visual_quality(asset, runtime)
flow     = evaluate_flow_quality(asset, runtime)
# ... then rule evaluation and critic score
```

Each validator receives the whole `runtime` dict and pulls what it
needs. There is no declared dependency between validators, no typed
report shape, and no way for a third-party validator (Plan 03's
plugin goal) to register under a common protocol. Score aggregation
(min-of-gates, weighted-sum) is open-coded inside the stage step.

The consequences show up as soon as a new validator lands:

- The call site in `validate.py` grows an inline function call,
  which is fine for five validators and painful for fifteen.
- A validator that depends on another's output (e.g. a silhouette
  check that needs the topology report) has no way to declare that;
  ordering is implicit.
- Plan 06's plugin goal (Plan 03 Phase 6b: custom
  `lathe.validators.silhouette_soft_v1` registered via entry point)
  requires a protocol surface that does not exist yet.

## Decision

1. **Introduce `Validator` protocol in `lathe/contracts/validator.py`.**
   The protocol exposes:
   - `name: str` (stable ID)
   - `stage_dependencies: list[str]` (which stages must have produced
     output before this validator can run)
   - `evaluate(runtime, asset, artifacts) -> ValidationReport`
   - `ValidationReport` is a typed dict / dataclass with `score:
     float`, `passes: bool`, `evidence: dict`, `subreports: list`.
2. **Introduce `ValidatorPipeline` in `lathe/validators/composition.py`.**
   The pipeline:
   - accepts a list of `Validator` instances (built-in + entry-point
     discovered)
   - topologically orders them by `stage_dependencies`
   - runs each, collects reports, aggregates into a
     `certification_bundle`
3. **Certification aggregation rule.** Score is `weighted_sum` of
   each validator's `score` weighted by its declared weight; gate
   passage is `min` (any single `passes=False` fails the bundle).
   Both are recorded separately in the bundle so operators can see
   which metric fell below threshold.
4. **Migrate existing five validators to the protocol.** Each of
   `semantic_quality`, `visual_quality`, `flow_quality`,
   `surface_quality`, `silhouette` adopts the protocol shape. Their
   internal logic is unchanged; only the interface and the call site
   change.
5. **Register built-ins via the `lathe.validators` entry point**
   (ADR-0004). Dogfood the plugin mechanism.
6. **Replace ad-hoc call sites.** `lathe/core/stages/validate.py`
   becomes a thin wrapper that builds the pipeline and runs it.

## Rationale

### Why a protocol and not a base class

Protocols (`typing.Protocol`) give third parties type-checkable
conformance without inheriting from a base class. This matches how
plugin authors think about their validator: "I have a callable and
some metadata, does Lathe accept it?" rather than "I must subclass
and override". It also keeps `lathe.contracts` free of implementation
detail, which is required by ADR-0005 Contract 3 (contracts purity).

### Why topological ordering

Implicit "run them in the order the list was built" ordering breaks
when a validator's inputs depend on another validator's outputs.
Topological order from `stage_dependencies` makes the dependency
explicit and makes cycles detectable (a declared cycle between
validators is a configuration error and must fail at pipeline
construction, not silently mis-order).

### Why min-of-gates and weighted-sum separately

A single scalar (either weighted sum OR min) hides information. A
validator that declares itself a gate (`passes=False`) must fail the
bundle regardless of how well other validators scored — that is the
definition of a gate. A validator that declares itself a metric
contributes a weighted score. Operators need to see both so they can
tell "the bundle failed because semantic gate didn't pass" from "the
bundle failed because the weighted score was below threshold".

### Why migrate all five at once

Partial migration would leave `validate.py` maintaining two call
conventions (protocol + free-function). Cost-wise, moving five
functions to a protocol is a mechanical change; leaving half of
them outside the protocol would persistently confuse new validator
authors ("do I follow semantic's pattern or surface's?"). One
commit, one convention.

### Why dogfood entry-point registration

ADR-0004 claims built-ins use the same registration mechanism as
plugins. If the five built-in validators skipped entry-point
registration, the claim would be false: built-ins would live in a
special-case path, and the first third-party validator would hit
bugs the built-ins never exercised. Dogfooding catches that early.

## Consequences

### Positive

- Adding a validator is a three-file change: protocol implementation,
  entry-point registration in `pyproject.toml`, test.
  `validate.py` does not change.
- Third-party validators (Plan 03 Phase 6b's `silhouette_soft_v1`)
  compose with built-ins transparently via the same pipeline.
- Certification reports distinguish gate failure from score failure,
  which is the distinction operators actually make when triaging
  failed builds.
- Dependency-aware ordering makes it safe for a validator to
  consume another's output without relying on insertion order.
- The pipeline is unit-testable in isolation from the executor.

### Negative / accepted risks

- Introduces one more layer between "write a validator" and "run a
  validator". Mitigated by keeping the protocol surface small
  (four attributes, one method) and by publishing a minimal
  validator example in `docs/extending.md`.
- Topological ordering + declared dependencies add a small amount of
  ceremony for the common case (validator depends on nothing). The
  `stage_dependencies: list[str]` can be empty; no extra code is
  required for independent validators.
- `ValidationReport` is a new typed shape; existing validators'
  internal dict returns must be adapted. Straightforward — all five
  current validators already return dicts with similar fields
  (`diagnostics`, score-like numbers, evidence).

## Alternatives considered

- **Keep free functions, formalise nothing.** Rejected: blocks
  Plan 03 Phase 6b plugin proof.
- **Class-based validators with a shared `Validator` base class.**
  Rejected: requires plugin authors to inherit; protocols are
  cheaper for conformance.
- **Declare dependencies as a static graph outside the validators.**
  Rejected: makes dependencies invisible from the validator source,
  which is the first place a reader looks.
- **Single scalar (`score`) only, no separate gate flag.** Rejected:
  collapses the gate/metric distinction that operators rely on for
  triage.
- **Arbitrary aggregation via user-supplied function.** Rejected as
  first cut: min-of-gates + weighted-sum covers every current use
  case; a pluggable aggregator can be added later if a real need
  emerges.

## Re-evaluation criteria

Re-open this decision if:

1. A validator needs to consume another validator's report mid-run
   (not just declare a stage dependency). That is an intra-pipeline
   dependency the current protocol does not model; introduce
   `validator_dependencies: list[str]` alongside `stage_dependencies`
   rather than folding them together.
2. Aggregation turns out to need something other than min-of-gates +
   weighted-sum (e.g. a tier-based certification level). Introduce
   a pluggable aggregator at that point.
3. Pipeline construction cost grows visible in profiles (many
   validators). Memoise the topological sort per process.
4. The protocol surface grows more than one attribute in any given
   change. That is a signal the protocol is trying to encode
   implementation concerns; push them down into the validator
   instead.

## Cross-references

- Validator protocol: `lathe/contracts/validator.py` (to be created
  in surgeon-validators task #3).
- Pipeline: `lathe/validators/composition.py` (to be created).
- Current ad-hoc composition: `lathe/core/stages/validate.py`.
- Entry-point group: `lathe.validators` (ADR-0004).
- Once surgeon-validators task #3 lands, this ADR flips to Accepted
  and a commit SHA is recorded here.
