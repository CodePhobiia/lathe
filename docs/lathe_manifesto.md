# Lathe Manifesto

## Lathe: The Programming Language for Production 3D Assets

Lathe exists to make 3D asset creation programmable, reproducible, and industrial-grade.

The goal is not to build another prompt wrapper, model demo, or loosely connected generation toolchain. The goal is to create the first system where a developer, designer, or agent can write a Lathe program and compile it into a production-ready 3D asset package.

That means geometry, topology, UVs, materials, interfaces, collision, optimization, validation, repair, packaging, and provenance must all be first-class parts of the system. If the output is not shippable, the work is not done.

## The Thesis

Today’s 3D generation systems optimize for novelty.

Production pipelines optimize for reliability.

Most asset-generation products fail in the gap between those two worlds.

Lathe should close that gap by treating asset generation as a compiler problem, not merely a model invocation problem.

A model can propose shape.
A compiler must guarantee outcomes.

Lathe should become the system that turns asset intent into enforceable contracts, routes work through the correct learned and deterministic stages, validates the result, repairs failures, and emits a build artifact teams can trust.

## What Lathe Must Be

Lathe must be a language, compiler, and runtime for assets.

Lathe must not be only:

- a prompt front-end
- a provider router
- an exporter wrapper
- a mesh generator without downstream guarantees

Lathe must own the full build contract.

The shape stage is only one phase in a larger asset compiler. The output of generation is not the product. The certified packaged asset is the product.

## The Product Promise

A user should be able to write a Lathe file, run one build command, and receive:

- a semantically correct asset
- production-usable geometry
- valid UVs and material structure
- pivots, sockets, anchors, and collision where relevant
- optimization outputs such as LODs and budget compliance
- exports such as `usd`, `glb`, and other target formats
- previews, manifests, traces, and diagnostics
- a clear pass/fail result against declared requirements

The user should not need to manually coordinate multiple disconnected tools. They should not need to understand which backend or model was selected. They should not need to babysit generation and repair the result by hand.

They should be able to say: “I wrote Lathe, and Lathe made the asset.”

## North Star

Lathe should become for 3D assets what a real programming language is for software:

- declarative enough to express intent cleanly
- structured enough for machines to edit and reason about
- strict enough to validate correctness
- modular enough to swap implementations
- reproducible enough for teams and CI
- powerful enough to ship real work

The defining user experience is not “look what the model made.”

It is: “the build passed.”

## The Core Insight

A production asset is not a mesh.

A production asset is a verified artifact that satisfies a contract.

That contract includes:

- what the asset is
- how it should be built
- what stages are allowed
- what quality bars it must pass
- what outputs must be emitted
- what repair actions are permitted
- what budgets and platform constraints apply

Lathe should be the formal system that expresses and enforces that contract.

## What Success Looks Like

A mature Lathe system should support these workflows:

- generate a new hero prop from declared intent and style constraints
- reconstruct an asset from reference images into a certifiable game-ready package
- adapt an input mesh into a new target profile without manual DCC work
- assemble modular assets from components while preserving interfaces and budgets
- produce deterministic downstream outputs even when the shape stage is probabilistic
- repair failed builds automatically until they pass or exhaust declared policy
- run in local, hosted, and hybrid environments without changing Lathe source semantics

## What “Standalone” Means

For Lathe to truly stand alone, it must eventually provide first-party capability for:

- text-to-3D generation
- image-to-3D reconstruction
- mesh adaptation
- component assembly
- topology cleanup and retopology
- UV generation
- material and texture synthesis
- collision, sockets, pivots, anchors, and interface generation
- optimization and LOD derivation
- validation and repair
- packaging and publishing

Under the hood, Lathe may still remain modular. But from the user’s perspective, it should behave as one coherent compiler/runtime.

## Product Principles

Lathe should be guided by these principles:

- Contract first: every stage must have explicit inputs, outputs, and guarantees.
- Production over novelty: quality means usable assets, not just interesting previews.
- Explicit validation: an asset that fails its contract is not complete.
- Repair as a first-class stage: fixing failures is part of compilation.
- Reproducibility by default: builds must be traceable and, where feasible, replayable.
- Backend independence: source semantics should survive provider swaps.
- AI as a stage, not the whole system: learned generation is important, but it is not the whole product.
- Progressive autonomy: Lathe should move from scaffolded generation to fully autonomous asset compilation.

## What We Must Avoid

The team should explicitly avoid:

- optimizing for demos instead of real assets
- overfitting to one asset family and calling it general
- shipping visually impressive but structurally broken outputs
- hiding fallback behavior behind vague language
- treating prompt engineering as a substitute for language design
- conflating model quality with system quality
- breaking public source semantics whenever a backend changes

If Lathe becomes a thin orchestration layer over third-party models, it may still be useful.

If Lathe becomes a true asset compiler, it can define a category.

## Manifesto Statement

Lathe should make 3D assets programmable.

It should turn intent into build artifacts.
It should make AI generation governable.
It should make asset quality testable.
It should make repair automatic.
It should make production constraints native.
It should make provenance non-optional.
It should make backend choice an implementation detail.
It should make “the build passed” the real signal of success.

If we succeed, Lathe will not just help create assets.

It will become the system by which assets are created.
