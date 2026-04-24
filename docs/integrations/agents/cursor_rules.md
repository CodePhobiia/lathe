# Cursor rules: Lathe as a certified-build tool

**Status.** Targeting Month 4–5 Cursor rules hub submission (see `docs/roadmap_public.md` § Persona-C GTM). Cursor's rules system is similar to Continue's in spirit but differs in file placement and trigger semantics; this doc specifies the Cursor-specific entry.

## Why a Cursor rule

Cursor is the agent surface most likely to be open in front of a Persona-A or Persona-B user (human-driven, agent-assisted). A rule file here is read every turn the matching file pattern is active, so Cursor's agent will consistently know about `lathe build` when editing `.lth` sources.

The goal is *not* to make Cursor a primary interface for Persona A — it is to ensure that when a human *is* using Cursor and asks the agent for asset help, the agent does the Lathe-native thing (edit `.lth`, run the compiler, read the trace) instead of the Cursor-default thing (generate a Blender script).

## Target `.cursor/rules/lathe.mdc`

Cursor rules use the `.mdc` (Markdown-with-Cursor-frontmatter) format. Rule frontmatter declares when the rule activates.

```markdown
---
description: >-
  Use Lathe for 3D-asset work in this repo. `.lth` sources are the intent
  of record; `lathe build` is how they become certified `.glb`. Never
  hand-roll a mesh script when a `.lth` exists.
globs:
  - "**/*.lth"
  - "examples/**"
  - "std/**"
alwaysApply: false
---

# Working on Lathe sources

## When this rule fires
- A `.lth` file is open or referenced in the prompt.
- The user mentions `lathe build`, `lathe check`, `lathe plan`, or "certify".

## The loop

    python -m lathe.cli check <file.lth>
    python -m lathe.cli plan <file.lth> <asset_id>
    python -m lathe.cli build <file.lth> <asset_id> --out dist

Read `dist/<asset_id>/trace.json` after a successful build. Cite the
`attempted` vs `actual` provider when reporting back.

## Failure grammar
Lathe errors name `stage.rule` and the offending value. Example:

    [build:uv] uv.texel_density = 128 px/m (below 256 px/m floor)
    at: examples/courier_drone.lth:84

Parse it. Edit the corresponding block in the `.lth` source. Re-run
`check` before another `build` (check is fast; build is not).

## What NOT to do
- Do NOT write a one-off Blender script when a `.lth` source exists in
  the repo. That bypasses intent preservation and breaks reproducibility.
- Do NOT edit `dist/` artifacts directly — they are outputs, not source.
- Do NOT claim "the mesh looks fine" as a verification — cite
  `trace.json` and the certification verdict.
- Do NOT alter the stable shape contract ID `lathe.shape.intent_mesh_handoff_v1`
  unless the user explicitly asks for a migration.

## Runtime configs
If the user wants a learned provider (Hunyuan, VGGT), they will pass
`--runtime-config examples/runtime_configs/<name>.json`. Without a runtime
config, Lathe takes the conservative fallback path. Do not invent a
runtime config the user did not reference.
```

## Expected Cursor agent behavior

With this rule present, a prompt like *"the door family has inconsistent texel density, fix it"* should:

1. Open `examples/mechanical_door.lth` (or equivalent).
2. Run `lathe check`.
3. Locate the variant whose `surface.uv.texel_density` violates the family's `contract`.
4. Edit the source, not the output.
5. Re-run `check`, then `build`. Report the stage/rule that was fixed plus the trace line that confirms it.

Without the rule, Cursor's default is to look for a Blender `.py` script in the repo and suggest edits there — which is exactly the class of silent failure Persona C is meant to eliminate.

## Submission to Cursor's rules hub

Cursor is accumulating a rules directory (as of 2026-01). Submission path and review cadence vary; confirm the current process before the Month-5 deadline. The rule file itself is single-file and self-contained, so submission is primarily a matter of listing.

## Honest limits

- `alwaysApply: false` means the rule only fires when globs match. A user asking generically "make a crate for my game" without opening a `.lth` won't trigger it. That is correct — Lathe is intent-preserving; there must be intent before compilation.
- Cursor rules cannot enforce CI-like gates. They shape agent behavior; they do not block a human from bypassing Lathe entirely.

## Cross-references

- `docs/integrations/agents/claude_code_skill.md`
- `docs/integrations/agents/continue_rules.md`
- `docs/integrations/agents/openhands_tool.md`
- `docs/integrations/agents/agents_md_listing.md`
- `docs/personas.md` § Persona C
- `docs/roadmap_public.md` § Persona-C GTM
