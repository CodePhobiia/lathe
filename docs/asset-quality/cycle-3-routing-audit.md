# Cycle 3 routing audit — synthesizer-vs-recipe dispatch

## Key finding

**There is no `_MIGRATED_TO_SYNTHESIZER` allowlist in the codebase.** The Cycle 1 routing landed as a capability-based predicate, not a family-name allowlist:

- Dispatch entry: `lathe/shape/backend.py:102`
- Predicate: `synthesizer_eligible(asset, runtime_config)` from `lathe/shape/procedural_program_path.py:46`

The synthesizer fires when an asset carries `construction_graph` metadata with at least one node (either at `asset.build.shape.procedural.construction_graph` or `asset.intent.construction_graph`). Otherwise the asset routes to the legacy `compile_scaffold_candidates` path which consults `_RECIPES`.

## Three-way dispatch (current state)

```
shape_backend
  ├─ mesh_program{} authored? → compile_mesh_program_candidate
  ├─ synthesizer_eligible() → compile_procedural_program_candidate
  │                            (uses synthesize_procedural_program)
  └─ otherwise              → compile_scaffold_candidates
                               (uses _RECIPES dispatch)
```

This means **migrating a family does not require touching a Python allowlist.** A family becomes "migrated" when:

1. Its example `.lth` files (and any `library/family` definition) populate `build.shape.procedural.construction_graph` or `intent.construction_graph`, *and*
2. A FamilyAlias JSON exists at `std/procedural/knowledge/family/<family>.json` pointing at the right StyleKnowledge + CompositionPolicy, *and*
3. The synthesizer correctly resolves the construction_graph nodes against the registered NODE_TYPE generators + composition policies.

Once those three conditions hold, the `_RECIPES[family]` entry becomes unreachable (the synthesizer path wins) and can be deleted.

## Implication for Cycle 3 acceptance

Per plan v2 §6.4: *"Authoring a new family requires creating a single FamilyAlias JSON file referencing existing StyleKnowledge + CompositionPolicy packs. Zero Python code change."*

This is already structurally true — the predicate-based dispatch means a new FamilyAlias + a `.lth` file that populates `construction_graph` is enough. The remaining question for Cycle 3 is whether the synthesizer's NODE_TYPE generator coverage is sufficient to produce equivalent-or-better ShapeProgram output for each migrated family (`build-artifact diff` acceptance criterion).

## Implication for the per-family migration protocol

The per-family migration protocol from §6.3 simplifies to:

1. Author StyleKnowledge JSON / pick existing.
2. Author CompositionPolicy / pick existing.
3. Author FamilyAlias JSON.
4. Update the family's example `.lth` files to populate `construction_graph` (so the asset routes through the synthesizer).
5. ShapeProgram diff test passes vs the recipe baseline.
6. Build-artifact diff test passes vs the recipe baseline (face count ±20%, material zones, package outputs).
7. Delete the recipe entry from `_RECIPES`.

No step adds the family to an allowlist; routing is by construction_graph presence.

## Open question for Round 6 decommissioning

After all 71 families migrate, what should the dispatch in `shape/backend.py:102` do?

- Option A: keep three-way dispatch but remove the `_RECIPES` reference from `compile_scaffold_candidates`. The legacy path becomes a true synthesizer fallback that produces a generic scaffold for assets with no authored procedural intent.
- Option B (plan v2 §6.3 Round 6 wording): "Replace the dispatch with direct `synthesize_shape_program(asset, runtime)` call." This collapses the predicate — every asset routes to the synthesizer, including ones without a construction_graph. The synthesizer must then handle the empty/minimal graph case gracefully.

Option B requires the synthesizer to ship a default policy for "unknown asset class with no construction_graph"; option A keeps the existing fallback. Plan §6.3 favors Option B but is achievable only after every family has authored `construction_graph` metadata in its `.lth` fixtures.
