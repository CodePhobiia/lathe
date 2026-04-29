# Wonder Readiness Overview

Lathe's current stable center is still asset compilation. The Wonder layer is
the contract bridge that lets an AI product describe, persist, revise, inspect,
and export multi-object scenes without forcing scene syntax into core Lathe too
early.

The first readiness target is intentionally narrow:

```text
prompt
-> Dream Brief JSON
-> Scene Graph JSON
-> Lathe scene/source lowering
-> check/build/render
-> render inspection
-> scene patch
-> export package
```

This commit establishes the first two links, plus the patch and render
inspection contracts needed by the revision loop.

## Layer Boundary

Lathe owns:

- Wonder contract schemas that can be validated locally.
- Stable scene/object identity vocabulary.
- Compiler, validator, build, render, export, and package artifacts as those
  scene capabilities are added.

Project Wonder owns:

- Chat and product UX.
- LLM routing and prompt interpretation.
- Long-term user memory, accounts, projects, sharing, and cloud orchestration.

The shared boundary is schema-first: Dream Brief, Scene Graph, Scene Patch, and
Render Inspection JSON.

## Current Commands

```bash
python -m lathe.cli wonder schemas
python -m lathe.cli wonder schema scene_graph
python -m lathe.cli wonder validate-brief examples/wonder/alchemist_observatory/dream_brief.json
python -m lathe.cli wonder validate-scene examples/wonder/alchemist_observatory/scene_graph.json
python -m lathe.cli wonder validate-patch examples/wonder/alchemist_observatory/scene_patch_more_sacred.json
python -m lathe.cli wonder validate-render-inspection examples/wonder/alchemist_observatory/render_inspection.example.json
```

## Deliberate Scope

This layer does not add `.lth` scene declarations yet. It gives authors and
models a strict JSON bridge first, so future parser and compiler changes can be
driven by validated examples instead of free-form scene text.
