# Gameplay tag catalog

STAGE-12 of the V0.2 E3 roadmap. Lathe uses a **closed** controlled vocabulary for the `asset.publish.tags` field so downstream engine importers (Godot / Unity / Unreal) can switch on tags without per-asset bespoke handling. The checker/validator rejects any tag that is not in the catalog below (error code `L6410`).

## Vocabulary

| Tag             | Meaning                                                                 |
| --------------- | ----------------------------------------------------------------------- |
| `kinematic`     | Moves every frame by game logic; not driven by the physics solver.      |
| `static`        | Never moves after spawn. Bakes into lightmaps / nav-mesh.               |
| `interactable`  | Accepts player interaction (use, pick-up, activate).                    |
| `weapon`        | Held weapon (melee or ranged). Implies `interactable`.                  |
| `vehicle`       | Player/NPC drivable. Expected to expose `grip` / `mount` sockets.       |
| `door`          | Operable barrier. Expected to expose a `hinge` socket.                  |
| `trigger`       | Invisible volume that emits an event when entered.                      |
| `spawn_point`   | Designated spawn location for entities.                                 |
| `decoration`    | Purely visual; non-interactable, non-collision-critical.                |
| `destructible`  | Can be broken into pieces (runtime fracture or pre-authored chunks).    |
| `consumable`    | One-time-use item (health, ammo, key).                                  |
| `collectible`   | Persists in inventory; tracked by quest/progression systems.            |
| `hazard`        | Deals damage or status to entities that touch it.                       |
| `cover`         | AI cover-node-friendly geometry.                                        |
| `waypoint`      | AI patrol / navigation waypoint.                                        |
| `vfx_anchor`    | Particle / decal emitter attach point.                                  |

## Usage

Declare tags on the asset:

```
asset widget {
  intent {
    role = "small console widget"
  }
  publish {
    tags = ["kinematic", "interactable"]
  }
}
```

Invalid tag example (rejected by the validator with code `L6410`):

```
asset widget {
  publish {
    tags = ["kinematic", "bomb"]      # L6410: unknown gameplay tag 'bomb'
  }
}
```

## Surfaced outputs

* `selector_manifest.json` surfaces the validated tag list under top-level `gameplayTags`.
* `<asset>.lathe_for_godot.json` exposes tags on the root `Node3D.meta.gameplay_tags`.
* `<asset>.lathe_for_unity.yaml` exposes tags under `rootGameObject.tags`.
* `<asset>.lathe_for_unreal.json` exposes tags under `actor.gameplayTags` for `GameplayTagContainer` construction.

## Evolution policy

The catalog is versioned implicitly by Lathe's `schemaVersion`. Adding a new tag is an additive change; renaming or removing an existing tag requires a `schemaVersion` bump in `schema/lathe.selector.schema.json`. Downstream engine adapters map tags one-for-one — renames always cascade.
