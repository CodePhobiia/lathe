# Product value and vision

Lathe is a declarative asset compiler for game-ready 3D props. It turns a
reviewable `.lth` source file into packaged artifacts, validation reports,
manifests, traces, and engine handoff data. The wedge is not "make a prettier
mesh than every generative model." The wedge is: make hard-surface assets
repeatable, certifiable, portable, and safe to automate.

## Positioning

**Target users.** Lathe serves technical artists, tools engineers, AI asset
pipeline builders, and maintainers who need asset builds to pass a contract
rather than merely look plausible.

**Core problem.** Current asset workflows split intent, generation, cleanup,
engine import, validation, and provenance across prompts, DCC files, scripts,
manual review, and tribal knowledge. The result is slow iteration and weak
confidence.

**Why Lathe is better.** Lathe keeps asset intent, constraints, providers,
validators, variants, and package targets in one source-controlled contract.
Build outputs can be inspected, compared, reproduced, and blocked in CI.

**Alternatives.** Blender scripts and Houdini HDAs are powerful but local to
their toolchain. Direct provider APIs are good at raw generation but weak at
contracts and downstream QA. Procedural libraries can be deterministic but
rarely carry game-engine packaging, trace, and certification as first-class
outputs. See [Competitive Landscape](competitive_landscape.md).

## Primary user journeys

| User | Journey | Must feel true |
|---|---|---|
| Solo technical artist | Edit a crate, panel, door, or cabinet source; run `lathe build`; import the packaged asset into Godot. | The first working asset takes minutes, and failures say what to fix. |
| Game tools engineer | Encode studio budgets and handoff rules in reusable contracts; run builds in CI; review source diffs. | The asset contract is versioned and enforceable, not a wiki page. |
| AI asset pipeline builder | Swap fallback, local, and learned providers under the same handoff contract. | Provider upgrades improve output without rewriting asset source. |
| CI asset validation maintainer | Run Lathe on asset PRs and release candidates; archive reports, manifests, and traces. | A pass/fail result is machine-readable and trustworthy. |

The wedge persona remains the indie or small-studio Godot technical artist
described in [Personas](personas.md) and [Jobs To Be Done](jtbd.md). Secondary
journeys must not make that first workflow heavier.

## Smallest lovable workflow

The smallest lovable workflow is:

1. Start from a canonical hard-surface `.lth` example.
2. Make a meaningful variant by changing intent, parts, material policy, or
   runtime budget.
3. Run `python -m lathe.cli check`.
4. Run `python -m lathe.cli build`.
5. Inspect `build_report.json`, stage reports, and the packaged GLB/USD
   artifacts.
6. Import into the target engine with correct scale, pivot, collision, LOD,
   material slots, and manifest data.

This workflow should be excellent before Lathe expands into more asset
families, repair automation, SaaS, or broader engine targets. "Excellent"
means clean-clone reproducible, fast enough for repeated use, honest when a
provider is unavailable, and specific when certification fails.

The release-facing version of this workflow is tracked in the
[Canonical Gallery](gallery.md). That page defines the exact asset set,
commands, acceptance criteria, and known limitations used to judge whether the
product output feels complete rather than half-baked.

## Why declarative beats ad hoc scripts

Ad hoc asset scripts can generate geometry, but they usually hide the contract
inside imperative code. A declarative `.lth` file separates what the asset is
from how each stage executes, which gives users:

- repeatable variants that review as small text diffs
- validator rules that can block release without human interpretation
- provider swapping without changing public asset intent
- reproducible traces of which stages, refs, and runtime modes actually ran
- package manifests that downstream tools and agents can consume

Example: a studio door can declare dimensions, pivot side, collision policy,
tri-budget, UV density, and engine target once. A junior artist changes the
style or dimensions; CI verifies the same contract. A Blender script can do
that only if the team builds and maintains a private compiler around it.

## Real-world use cases

| Use case | Measurable benefit |
|---|---|
| Deterministic prop families | Rebuild the same source from a clean clone and compare output manifests and hashes. |
| Portable asset contracts | Move the same `.lth` source between fallback and learned provider modes while preserving public intent. |
| Provider swapping | Record attempted and actual providers so quality improves without hiding fallback behavior. |
| Asset QA in CI | Block merges on topology, UV, collision, budget, packaging, or certification failures. |
| Engine-ready packaging | Emit GLB/USD artifacts, manifests, previews, trace data, and engine handoff metadata together. |
| Agent-authored assets | Let coding agents edit text source and rely on structured diagnostics instead of visual guessing. |

## Success metrics

| Metric | Target signal |
|---|---|
| Clean-clone build rate | Canonical examples pass documented setup and build commands on supported platforms. |
| Time to first asset | A new user can go from checkout to certified first asset inside the quickstart budget. |
| Certification pass rate | Canonical assets either certify or are explicitly labeled as known limitations. |
| Provider failure recovery | Provider unavailable, timeout, or denied-network paths produce actionable diagnostics and usable offline examples. |
| Artifact quality | Outputs meet declared topology, UV, collision, LOD, scale, naming, material-slot, and package-completeness criteria. |
| Return build rate | Users who complete one build come back and run another build within seven days. |

These metrics are user-value metrics. Internal test coverage, linting, and
security gates remain necessary release gates, but they are not substitutes for
proof that users can ship assets faster and with more confidence.

## Roadmap by user value

1. **Make the wedge workflow undeniable.** Clean-clone build, clear
   diagnostics, canonical gallery, Godot import, and certification reports.
2. **Make contracts portable.** Stable language, stable handoff bundles,
   provider truthfulness, runtime config safety, and reproducible traces.
3. **Make QA automatable.** Machine-readable reports, CI examples, failure
   taxonomy, and release candidate artifact review.
4. **Make extension useful.** Third-party providers, validators, and engine
   targets through stable plugin entry points and compatibility tests.
5. **Make generation richer.** Learned lanes, repair loops, surface authoring,
   and hosted registry features only after the core workflow is trusted.

Roadmap items should move up when they improve the wedge workflow or reduce
adoption risk. They should move down when they mainly add technical breadth
without improving a user's ability to finish a certified asset.

## Product-critical vs experimental

**Product-critical for the next release:**

- parse, normalize, check, plan, materialize, and build for canonical examples
- stable `lathe.shape.intent_mesh_handoff_v1`
- honest fallback and provider diagnostics
- certification reports that name the failing stage, rule, value, and artifact
- packaged GLB/USD outputs with manifests and traces
- docs that show the current commands and artifact layout
- extension points for providers, validators, and engine targets that do not
  require patching Lathe internals

**Experimental until proven by examples and users:**

- autonomous repair loops
- broad learned-provider quality claims
- new engine targets beyond the current documented path
- hosted registry and CI certification SaaS
- non-hard-surface asset families
- research-only validators or metrics without release gates

Experimental features may exist, but release notes and docs must label them
honestly and keep them out of the critical path for the smallest lovable
workflow.

## Extension story

Lathe should be extendable without forking the compiler. The stable extension
story is:

- providers implement a declared provider contract and report actual runtime
  behavior
- validators return structured metrics and diagnostics that can be composed
  into certification
- engine targets consume packaged artifacts and manifests without depending on
  internal stage implementations
- plugin entry points register backends, stacks, shape providers, and
  validators through the public surface described in [Extending Lathe](extending.md)

The extension promise is compatibility at the contract boundary, not freedom
to depend on private internals. Future extensions should add capability while
preserving source compatibility and trace truthfulness.

## Evidence and feedback

Current evidence lives in the canonical examples, benchmark data, scenario
walkthroughs, and design-partner plan:

- [Examples catalog](examples_catalog.md)
- [Benchmark methodology](benchmarks/methodology.md)
- [Five-asset benchmark](benchmarks/v0_5_five_asset_study.md)
- [Scenario walkthroughs](walkthroughs/README.md)
- [Design partners](business/design_partners.md)

Target-user feedback is not complete until interview notes or design-partner
findings are recorded. Until then, roadmap decisions should be described as
product hypotheses, not validated market facts.
