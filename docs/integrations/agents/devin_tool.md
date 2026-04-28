# Devin tool directory entry: `lathe`

**Status.** Targeting Month-5 (V0.6) Devin tool-directory submission (see `docs/roadmap_public.md` § Persona-C GTM). Devin's model differs from Claude Code / Continue / Cursor / OpenHands — it is a managed agent whose "tool directory" is more curated and whose workspace is already sandboxed. The entry here is therefore shorter and closer to an advertisement than a rule file.

## Why Devin

Devin is popular with small-team users who do not want to run an agent framework themselves. If Lathe is in Devin's tool directory, a studio can point Devin at "generate 3 crate variants for the industrial kit" and have Devin reach for `lathe build` instead of re-implementing a mesh generator. That is the ideal Persona-C handoff.

## Entry metadata (for the tool directory submission form)

```yaml
tool_name: Lathe
tagline: Declarative, certifiable 3D-asset compiler with a stable intent contract.
category: game-dev / asset-pipeline / 3d
install: pip install lathe
homepage: https://github.com/talmerri/lathe
doc_url: https://talmerri.github.io/lathe/
primary_commands:
  - lathe check <file.lth>
  - lathe plan <file.lth> <asset_id>
  - lathe build <file.lth> <asset_id> --out dist

trigger_phrases:
  - "certify this asset"
  - "build a Lathe asset"
  - "generate a <asset> variant" (when a `.lth` source exists)
  - "validate my .lth"

pass_fail_signal: >-
  Exit code 0 on certified pass, non-zero on fail. Failures are formatted as
  `[stage:rule] value (reason) at: file:line`. A `dist/<asset_id>/stages/package/trace_manifest.json`
  is written on success with stage-by-stage records (attempted vs actual
  provider).

when_to_use:
  - A `.lth` source exists in the repo.
  - The user asks for a game-ready asset with collision / UVs / LODs.
  - The user needs a *reproducible* build (same source → same bytes).

when_not_to_use:
  - Free-form text-to-3D with no `.lth` source. Lathe requires intent.
  - Organic assets (characters, creatures). Out of scope for V0.x.
  - Unity/Unreal-primary pipelines pre-V1.0 (Godot-first wedge).
```

## Directory-listing blurb (≤300 chars)

> Lathe is a declarative compiler for 3D-asset intent. Write `.lth` source, run `lathe build`, get a certified `.glb` with manifest + trace. Deterministic, reproducible, game-ready. Godot-first. Primary interface for agents that need a parseable pass/fail verdict for 3D work.

## Expected Devin behavior

Given a Devin task like *"add a glass-variant to `sci_fi_wall_panel`"*:

1. Devin reads the existing `.lth` source.
2. Adds a `variant glass { ... }` block patterned on the existing variants.
3. Runs `lathe check` (fast) and `lathe build` (slow).
4. On fail, parses `[stage:rule]` and iterates on the source.
5. On pass, attaches `dist/<asset_id>/stages/package/package_manifest.json` to the PR and cites the relevant trace line.

Devin's model will frequently over-confidently write a Blender script instead. The directory entry's `when_to_use` / `when_not_to_use` blocks are specifically there to nudge the planner back to the Lathe-native path.

## What Devin's directory review will likely ask

- **Reproducibility.** Yes — identical source + identical runtime-config → identical `.glb` bytes (within the deterministic stages; shape is the only probabilistic stage and its seeding is explicit).
- **Sandbox-friendliness.** Yes — the conservative fallback path is network-free. Hunyuan / VGGT only via opt-in runtime config.
- **License.** OSS (MIT) is the plan for the V0.5 public launch. Until then, the tool is evaluated under a private staging listing.

## Honest limits

- Devin's directory review has a multi-week lead time. The Month-5 target is *submission*, not listing-live. Treat the listing as aspirational until confirmed.
- Devin's action space is less transparent than OpenHands'. We cannot enforce `check` before `build`; we can only recommend it in the metadata.

## Cross-references

- `docs/integrations/agents/openhands_tool.md` — more detailed schema cousin.
- `docs/integrations/agents/agents_md_listing.md` — generic spec.
- `docs/integrations/agents/claude_code_skill.md`, `continue_rules.md`, `cursor_rules.md`.
- `docs/personas.md` § Persona C.
- `docs/roadmap_public.md` § Persona-C GTM (Month 5).
