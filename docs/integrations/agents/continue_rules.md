# Continue.dev rules: Lathe as a certified-build tool

**Status.** Targeting Month 4–5 submission to the Continue.dev rules hub (see `docs/roadmap_public.md` § Persona-C GTM). This doc specifies the rules file Continue will consume and the agent behavior it enforces.

## Why Continue

Continue.dev is the second-largest agent surface after Claude Code for the population we are targeting (small teams, open-source-friendly). A rules YAML is the lowest-overhead integration: no tool registration, no plugin compile step, just a file the project checks in and Continue picks up.

The same framing as `claude_code_skill.md` applies: Persona C is looking for a **parseable pass/fail**, not prose. The rule's job is to make sure Continue's agent *runs* `lathe` rather than hand-writing a mesh script.

## Target `.continue/rules/lathe.yaml`

```yaml
name: lathe
description: >-
  Rules for using Lathe (a declarative 3D-asset compiler) from Continue.
  Trigger when a `.lth` file is open, when the user mentions "lathe build",
  or when the user asks to certify / validate a 3D asset.

triggers:
  files:
    - "**/*.lth"
  keywords:
    - "lathe build"
    - "lathe check"
    - "lathe plan"
    - "certify asset"
    - "intent-preserving 3D"

rules:
  - id: prefer-lth-source
    when: user_asks_for_3d_asset
    text: |
      If a `.lth` source exists in the repo, edit it and run `lathe build`.
      Do NOT generate a mesh by writing a Python script. Lathe is the source
      of truth for asset intent in this repo.

  - id: check-before-build
    when: editing_lth
    text: |
      After editing a `.lth` file, run `python -m lathe.cli check <file>`
      before `lathe build`. `check` is fast and surfaces semantic errors.

  - id: read-trace
    when: build_succeeded
    text: |
      On success, read `dist/<asset_id>/trace.json`. Cite the `attempted` vs
      `actual` provider when reporting back to the user. Never claim the
      mesh "looks good" — claim the build passed certification.

  - id: parse-failure
    when: build_failed
    text: |
      Lathe failures name `stage.rule` and the offending value. Example:
        [build:uv] uv.texel_density = 128 px/m (below 256 px/m floor)
      Parse the stage + rule, locate the matching block in the `.lth` source,
      edit, re-check, re-build. Do NOT patch downstream (e.g. the `.glb`).
      Fix the intent at the source.

  - id: no-fabricated-sources
    when: no_lth_exists
    text: |
      If the user asks for a 3D asset and no `.lth` source exists, ASK
      whether to scaffold one from `std/` (hard_surface_game_asset_v1 stack)
      before generating. Do not invent a `.lth` from scratch.
```

## How Continue uses this

Continue's agent loads rules alongside system context when a trigger fires. The rules constrain behavior; they do not register a new tool. The CLI invocation itself uses Continue's existing shell/bash tool.

Observed effect when the rules are present (from internal dogfood):

1. Prompt: *"fix the UV density on `examples/industrial_crate.lth`"*.
2. Agent opens the file, runs `lathe check`, reads the stage/rule violation, edits the `surface.uv.texel_density` field, reruns `check`, then `build`, cites `trace.json`.
3. Without rules: agent tends to write a throwaway Blender script and never touches the `.lth` file — exactly the silent-failure class Persona C is most exposed to.

## Submission to the Continue.dev rules hub

- Repo: single-file YAML in `continuedev/rules-hub/lathe/` (hub naming convention as of 2026-01; confirm before submission).
- Maintainer: the Lathe core team until the hub accepts external co-maintainers.
- Version pinning: the rules file declares no Lathe version — the CLI contract (`check` / `plan` / `build` / exit-code semantics) is the stable surface. If that contract changes, update the rules.

## Limits we are honest about

- Continue's trigger system matches on filenames and keywords. Rules do not fire on *semantic* triggers like "this binary asset feels off". That is a limit of the framework, not the rules.
- The rules file cannot install Lathe. The user or their CI must have `pip install lathe` already. The rules assume that; a missing install falls back to a normal "command not found" error, which is the right failure mode.

## Cross-references

- `docs/integrations/agents/claude_code_skill.md` — equivalent surface for Claude Code.
- `docs/integrations/agents/cursor_rules.md` — Cursor's rules equivalent.
- `docs/integrations/agents/agents_md_listing.md` — generic spec entry.
- `docs/personas.md` § Persona C.
- `docs/roadmap_public.md` § Persona-C GTM.
