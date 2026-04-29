# Game Readiness And Provenance

Phase 23 and Phase 28 add contract/helper groundwork for game-readiness,
provenance, and safety metadata. This layer is deliberately contract-first: it
validates JSON-shaped metadata and reports deterministic diagnostics, but it
does not export engine files, call providers, or make product policy decisions.

## Contracts

Game-readiness metadata lives in `schema/game_readiness.schema.json` with
schema version `lathe.game_readiness.v1`.

The contract records per-object fields that game targets commonly need:

- mobility: `static`, `dynamic`, `kinematic`, or `decorative`
- interactable and walkable flags
- collision type and whether collision is required
- pivot mode and optional custom pivot position
- snap points and sockets
- LOD, physics, occlusion, and mobile performance hints
- gameplay tags

Asset provenance metadata lives in
`schema/asset_provenance_scene.schema.json` with schema version
`lathe.asset_provenance_scene.v1`.

The provenance contract records:

- deterministic Lathe, provider-generated, user-supplied, licensed-reference,
  or mixed source metadata
- provider and model names when known
- input reference paths
- license, commercial-use, and export-permission status fields
- content-safety, brand/IP, and user-upload review metadata hooks
- export permission metadata for generated export artifacts

These schemas are standalone metadata contracts. The current Scene Graph schema
is closed, so full game-readiness payloads should be carried beside a Scene
Graph until a future compatibility pass explicitly widens the Scene Graph
contract.

## Helpers

`lathe.scene.game_readiness.validate_game_readiness_payload(payload)` validates
the standalone game-readiness contract.

`lathe.scene.game_readiness.validate_scene_game_readiness(scene_graph, *,
game_readiness=None)` checks Scene Graph dictionaries plus an optional
standalone game-readiness payload. It reports:

- `GR1001` missing required collision metadata
- `GR1002` missing pivot metadata on interactable objects
- `GR1003` invalid snap-point or socket names
- `GR1004` game-readiness metadata for an unknown object
- `GR1005` duplicate game-readiness object metadata
- `GR9001` forbidden secret-bearing metadata

`lathe.scene.provenance.validate_asset_provenance_scene_payload(payload)`
validates the standalone provenance contract.

`lathe.scene.provenance.validate_scene_provenance(scene_graph, *,
provenance_payload=None)` checks Scene Graph object provenance and metadata
safety. It reports:

- `PR1001` missing object provenance
- `PR1002` provider-generated object without provider metadata
- `PR1003` licensed-reference object without a license note
- `PR9001` forbidden secret-bearing metadata

The helpers are pure. They read dictionaries and return JSON-ready diagnostic
lists. They do not read assets from disk, resolve external licenses, contact
engines, write manifests, or mutate the input payload.

## Metadata Sources

For compatibility with the current closed Scene Graph v1 shape, validators look
for minimal readiness hints in object `state`, `metadata`, `gameplay`, and
`game_readiness` mappings when those mappings are present. Existing Scene Graph
examples can therefore carry simple values such as `collision`, `collision_mode`,
`pivot`, or `pivot_mode` in `state` while standalone payloads carry the richer
contract.

## Source Syntax

Hand-authored experimental scene source now accepts an object-local gameplay
metadata block:

```lathe
object obj_archive_door: interactive from mechanical_door {
  region = region_sealed_archive

  gameplay {
    interactable = true
    locked = true
    key_item = star_lens
    collision = box
    pivot = base_center
    tags = [door, quest]
    affordances.open_door.action = open
    affordances.open_door.requires = star_lens
  }
}
```

The parser lowers this block into normalized scene-object `values.gameplay`.
Generated scene-source previews also render Scene Graph `objects[].affordances[]`
through `gameplay.affordances.<id>.*` lines so interaction hooks are visible in
the reviewable `.lth` text while the embedded Scene Graph JSON remains the
durable roundtrip payload.

Provenance is already available on Scene Graph objects as `provenance`. The new
provenance scene contract is for richer scene-level reports and future export
manifests.

## Boundaries

This phase does not add:

- gameplay scripting
- engine export generation
- Roblox Studio, Unity, Godot, or Unreal import automation
- content moderation policy enforcement
- legal or IP clearance decisions
- license verification against external services
- user-account, gallery, payment, or Project Wonder product logic

The status fields are audit metadata. A downstream product or human review
process decides what to do with `blocked`, `restricted`, `flagged`, or
`unknown` values.
