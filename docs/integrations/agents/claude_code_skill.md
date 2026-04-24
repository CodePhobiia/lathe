# Claude Code skill: `lathe-builder`

**Status.** Drafted for Month-4 (V0.5) ship. The skill file itself will live under `.claude/skills/lathe-builder.md` in a future repo (or in a user's `~/.claude/skills/`); this doc is the reference that describes *what* it should contain and *why*. Persona C — the AI coding agent — is the reader. See `docs/personas.md` for the persona definition and `docs/roadmap_public.md` for GTM placement.

## Why a Claude Code skill

Persona C is not Discord-reachable. She is reachable through the agent frameworks she already runs inside. A Claude Code skill is the highest-leverage surface for that persona because:

1. **Discoverability is solved by the framework.** `~/.claude/skills/` is scanned on startup; the agent finds the skill without the user wiring anything.
2. **Trigger rules gate invocation.** A well-written skill fires on `.lth` files or on verbs like "certify this asset", not on every turn — so the agent does not waste context tokens when Lathe is not relevant.
3. **The skill wraps the CLI, not the runtime.** No SDK lock-in. If the Lathe CLI contract is stable, the skill survives compiler refactors.

## Skill frontmatter (target shape)

```markdown
---
name: lathe-builder
description: Build, check, and certify Lathe 3D-asset sources (`.lth` files).
  Use when the user asks to generate a game-ready asset, validate a `.lth` diff,
  or interpret a failed `lathe build` trace. Produces a certified `.glb` +
  manifest that the Godot addon auto-imports. Do NOT use for generic text-to-3D
  prompts without a `.lth` source — Lathe is intent-preserving, not a
  free-form generator.
triggers:
  - file_extension: .lth
  - keywords: ["lathe build", "lathe check", "lathe plan", "certify asset", "intent-preserving 3D"]
tools:
  - Bash
  - Read
  - Edit
---
```

`description` is the discoverability contract. Claude Code shows it to the router; getting it wrong is the #1 reason a skill either never fires or fires when it should not. Two levers: name the *when-to-use* and name the *when-not-to-use* (the latter prevents hijacking every text-to-3D request).

## Skill body (target structure)

```markdown
# Using Lathe from Claude Code

## When to invoke
- A `.lth` file is in scope and the user asks to build, diff, or certify it.
- A `lathe build` run has failed and the user asks you to fix the source.
- The user asks for a "certified" or "game-ready" 3D asset and you have a `.lth` source.

## When NOT to invoke
- The user asks for a text-to-3D mesh with no `.lth` source. Lathe requires a source file; do not fabricate one.
- The user is editing the Lathe compiler itself (`lathe/*.py`). That is normal code work, not a skill task.

## Primary loop (always read stdout — Lathe's failure messages are parseable)

    python -m lathe.cli check <file.lth>
    python -m lathe.cli plan <file.lth> <asset_id>
    python -m lathe.cli build <file.lth> <asset_id> --out dist

## Interpreting failure output
Lathe failures name `stage.rule` and the offending value. Example:

    [build:uv] uv.texel_density = 128 px/m (below 256 px/m floor)
    at: examples/courier_drone.lth:84

Action: edit the `.lth` source to fix the stage/rule. Do not paper over with
downstream edits.

## Round-tripping
After an edit, re-run `check` FIRST. It is fast and catches syntax + semantic
violations before the slow build stage.

## Trace
On success, `dist/<asset_id>/trace.json` contains the stage-by-stage record
(including attempted-vs-actual providers). Read it to confirm the build used
the provider the user expected.
```

## Expected agent behavior

With the skill installed, an agent given *"the panel collision is off in `examples/sci_fi_wall_panel.lth`"* should:

1. Read the `.lth` source.
2. Run `python -m lathe.cli check` to surface semantic violations.
3. Propose an edit to the `collision` block.
4. Run `python -m lathe.cli build ... --out tmp_diagnose` and inspect `trace.json`.
5. Either confirm fix with the trace line cited, or iterate.

The agent never claims "the mesh looks right." It only claims "the build passed certification with `trace.json` showing `validate.collision = pass`." That distinction is the entire reason Persona C exists.

## Installation paths (user-facing)

- Personal: drop into `~/.claude/skills/lathe-builder.md`.
- Project: drop into `<repo>/.claude/skills/lathe-builder.md` (checked into source control so every contributor's agent gets it).
- Marketplace: the Month-5 deliverable is submitting this skill to the Claude Code skills marketplace (see `docs/roadmap_public.md` Persona-C GTM).

## Cross-references

- `docs/integrations/agents/continue_rules.md` — same idea, Continue.dev framing.
- `docs/integrations/agents/cursor_rules.md` — Cursor equivalent.
- `docs/integrations/agents/openhands_tool.md`, `devin_tool.md` — tool-directory listings.
- `docs/integrations/agents/agents_md_listing.md` — generic `agents.md` spec entry.
- `docs/personas.md` § Persona C — why this skill exists at all.
- `docs/roadmap_public.md` § Persona-C GTM — when the skill ships.
