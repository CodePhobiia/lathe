# `agents.md` listing template for Lathe

**Status.** Targeting Month-5 (V0.6) submission to `agents.md` public listings (see `docs/roadmap_public.md` § Persona-C GTM). The `agents.md` spec is the closest thing to a neutral, framework-agnostic directory for agent-facing tools. A good `agents.md` entry reads like a machine-readable README: what the tool is, when an agent should reach for it, what signals it emits, and what not to do.

## Why `agents.md` matters even though it's smaller

Claude Code / Continue / Cursor / OpenHands / Devin are five different surfaces with five different formats. `agents.md` is the canonical thing we point to from each of those five — one source of truth, five adapters. When the Lathe CLI contract changes, we update one place and the others re-consume it.

## Target content of `agents.md` in the Lathe repo root

```markdown
# Lathe — agents.md

This file is the machine-readable contract for how automated agents should
interact with the Lathe repository.

## Project identity

- name: Lathe
- kind: compiler / runtime for declarative 3D-asset intent
- primary language: Python 3.10+
- primary engine target (V0.x): Godot 4.x
- stable contract id: `lathe.shape.intent_mesh_handoff_v1` (do not modify
  without an explicit migration task)

## What this repo is not

- Not a text-to-3D prompt tool. Lathe compiles explicit intent (`.lth`
  sources); it does not hallucinate from one-liners.
- Not a generic Blender plugin. Blender is one execution substrate; the
  compiler is the product.
- Not a runtime. It emits artifacts (`.glb` + manifest + trace); consumers
  import those.

## Primary commands

    python -m lathe.cli doctor
    python -m lathe.cli check <file.lth>
    python -m lathe.cli plan <file.lth> <asset_id>
    python -m lathe.cli build <file.lth> <asset_id> --out dist

Exit code 0 on certified pass, non-zero on fail. Failures are formatted:

    [stage:rule] value (reason) at: file:line

On success, `dist/<asset_id>/stages/package/trace_manifest.json` holds stage-by-stage records
(including attempted vs actual providers).

## When an agent should invoke Lathe

- The user asks for a 3D asset AND a `.lth` source exists in the repo.
- The user asks to validate / certify / diff a `.lth` file.
- A CI job needs a yes/no on whether an asset source meets the studio
  contract.

## When an agent should NOT invoke Lathe

- Organic assets (characters, cloth, foliage). Out of scope for V0.x.
- No `.lth` source exists and the user has not asked to scaffold one.
- The task is editing the Lathe compiler itself (`lathe/*.py`) — that is
  normal code work, not a Lathe invocation.

## Stable contracts (agent-relevant)

- CLI subcommand names and exit-code semantics.
- Failure format `[stage:rule] value (reason) at: file:line`.
- `stages/package/trace_manifest.json` top-level shape: `{ stages: [...], contract: "...", providers: {attempted, actual} }`.
- Public language surface: `profile`, `contract`, `critic`, `asset`, `variant`.

## Non-stable internals (do not depend on)

- Internal module boundaries in `lathe/` — these may refactor between minor
  versions.
- Fallback provider choice — the compiler may silently upgrade fallbacks;
  read `providers.actual` to see what happened.

## Trace contract

An agent that cites "the build passed" should cite the trace field that
proves it:

    trace.stages[].name     # e.g. "validate"
    trace.stages[].status   # "pass" | "fail"
    trace.providers.actual  # e.g. "lathe.provider.shape.reference_conditioned_v1"

Never claim success without a trace field backing it.

## Reproducibility

Same `.lth` source + same runtime-config + same Lathe version ⇒ same
`.glb` bytes within the deterministic stages. Shape is the only
probabilistic stage; its seeding is explicit in the source.

## External service calls

Opt-in only, via `--runtime-config`. No network calls on the default
(fallback) path. See `examples/runtime_configs/` for the opt-in templates.
```

## Why this file belongs at the repo root

`agents.md` is discovered by convention at the repo root, same as `README.md`. Putting it under `docs/` breaks agents that walk from the top level. The file in the root is the deployment artifact; *this* doc is the authoring reference that explains what the root file should say and why.

## Cross-references

- `docs/integrations/agents/claude_code_skill.md`
- `docs/integrations/agents/continue_rules.md`
- `docs/integrations/agents/cursor_rules.md`
- `docs/integrations/agents/openhands_tool.md`
- `docs/integrations/agents/devin_tool.md`
- `docs/personas.md` § Persona C
- `docs/roadmap_public.md` § Persona-C GTM
- Lathe project `CLAUDE.md` — author-facing rules overlap with the agent-facing rules listed here; keep the two consistent when either changes.
