# Curiosity Anchors

Curiosity anchors are the scene-level hooks that turn a static Wonder preview
into a branchable exploration graph. Each anchor keeps a visible clue, a hidden
fact, suggested user actions, and one or more expansion options tied to an
existing object or region.

## Summary Cards

`lathe.scene.curiosity.summarize_curiosity(scene_graph)` returns a deterministic
report:

- `cards` are sorted by `anchor_id`;
- each card includes the visible clue, suggested actions, expansion options,
  linked hidden-state records, and aggregate continuity constraints;
- `diagnostics` reports broken hidden-state links and invalid expansion target
  scopes.

Hidden-state links are resolved conservatively. A hidden fact links to an anchor
when the hidden state is attached to the same scene entity and its fact overlaps
the anchor's hidden fact, or when the attached object's affordance directly
reveals the hidden state. Reveal conditions are copied into the card unchanged.

## Source Syntax

The experimental `.lth` scene source surface accepts scene-local
`curiosity_anchor` and `hidden_state` blocks. These lower into normalized
`scene_curiosity_anchor` and `scene_hidden_state` children with their authored
fields preserved in `values`; Scene Graph lowering remains the durable contract
for full curiosity cards and branch expansion.

```lathe
scene alchemist_observatory {
  region region_central_chamber: interior {}
  object obj_astrolabe_table: hero_prop from ornate_table {
    region = region_central_chamber
  }
  curiosity_anchor curiosity_warm_lens {
    attached_to = obj_astrolabe_table
    visible_clue = "The black glass lens is still warm."
    hidden_fact = "The lens still tracks a living star."
    suggested_user_actions = [inspect_lens, align_astrolabe]
    expansion_options.hidden_star_map.label = "Hidden Star Map"
    expansion_options.hidden_star_map.target_scope = obj_astrolabe_table
  }
  hidden_state hidden_warm_lens_truth {
    attached_to = obj_astrolabe_table
    fact = "The lens is warm because it tracks a living star."
    reveal_condition = "User inspects the lens."
    visible = false
  }
}
```

The checker enforces `curiosity_` and `hidden_` ID prefixes, duplicate
scene-local ID rules, and `attached_to` references against the scene-local ID
set. More detailed expansion-option validation still happens on Scene Graph
JSON through `check_scene_graph`.

## Expansion

`lathe.scene.curiosity.expand_anchor(scene_graph, anchor_id, option_id)` returns
a `CuriosityExpansionResult` containing an updated Scene Graph copy,
diagnostics, appended memory event records, and generated IDs.

For a valid option:

- the Scene Graph `version` increments by one;
- existing object IDs and transforms are preserved;
- object target scopes add deterministic object shells in the target object's
  region;
- region target scopes add a deterministic branch region plus object shells for
  the option's `required_assets`;
- a memory event records the anchor, option, target scope, linked hidden state,
  and generated scene refs.

Generated IDs are stable from the anchor ID, option ID, and required asset name.
If a generated ID already exists with identical content, expansion is idempotent.
If the ID exists with different content, the helper reports a diagnostic and
returns the original graph copy.

## Diagnostics

The helper uses `scene_graph` diagnostics with phase `curiosity_expansion`.
Important codes:

- `C2202`: an anchor hidden fact has no linked hidden-state record;
- `C2204`: an expansion option target scope does not reference the Scene Graph;
- `C2205`: an expansion target exists but is not an object or region;
- `C2206`: requested anchor ID was not found;
- `C2207`: requested option ID was not found;
- `C2211`: expansion would alter an existing object transform or remove an
  existing object.

The helpers do not build geometry, run providers, or call the CLI. They produce
schema-compatible graph branches for later scene commands to wire into the
Wonder workflow.
