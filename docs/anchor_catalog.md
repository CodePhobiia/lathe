# Anchor Catalog

Typed sockets and pivots are Lathe's stable addressable attachment points. Each anchor (socket or pivot) has a globally-unique `id` and a `socket_type` / `pivot_type` that tells consumers how the anchor is meant to be used. This catalog is the reference list of valid type values. STAGE-3/4/5 of V0.2 E3.

Every anchor `id` must be unique across **both** sockets and pivots for a given asset. The checker enforces this — duplicate ids produce a helpful error listing both declarations.

In `.lth` source, declare typed entries with constructor calls:

```lathe
interfaces {
  sockets = [socket(id: power_socket, socket_type: port)]
  pivots = [pivot(id: floor_contact, pivot_type: contact)]
}
```

Legacy bare socket names and `anchors = [...]` are still accepted for
source compatibility, but new examples should use typed sockets and pivots.

## Socket types

Sockets are attachment points on the surface of an asset where external geometry (hands, tools, accessories, wall mounts, etc.) can connect. Each socket carries a `transform` (4x4 row-major) and an `aabb` (`{min, max}` in manifest units).

| `socket_type`        | Description                                                                                  | Use case                                                    |
| -------------------- | -------------------------------------------------------------------------------------------- | ----------------------------------------------------------- |
| `attach`             | Generic attachment point. Default when no type is declared.                                  | Fallback for legacy declarations and untyped accessory anchors. |
| `hand`               | Character hand / grip attachment. Indicates where a rigged hand bone should lock on.         | Props picked up and held by a character (tool handles, weapons). |
| `mount`              | Fixed structural mount, typically body-to-body.                                              | Vehicle accessories, gun rails, undercarriage mounts.       |
| `port`               | Data / fluid / power port with a defined connector.                                          | USB ports, hose couplings, electrical plugs.                |
| `attachment_point`   | Generic attachment point with explicit geometry intent (distinct from `attach`, which is fallback). | Accessory slots whose interface matters but kind is unknown. |
| `hinge`              | Rotational joint axis. Used for doors, hatches, articulated sub-meshes.                      | Cargo doors, panel hatches, gun elevation pivots.           |
| `door`               | Full door interface (hinge + latch region). Higher-level than `hinge`.                       | Vehicle doors, cabinets, entry hatches.                     |
| `slot`               | Insertable cavity with a well-defined entry direction.                                       | Battery slots, cartridge ports, drop-in modules.            |
| `grip`               | Grippable surface region for physics / IK (not rig-bone specific like `hand`).               | Handle bars, tool shafts, rope ends.                        |
| `muzzle`             | Forward-pointing emission anchor.                                                            | Gun muzzles, thruster nozzles, torch tips.                  |
| `rail`               | Linear rail surface for sliding attachments.                                                 | Picatinny rails, drawer slides, mounting rails.             |

**Default**: when a socket is declared without `socket_type`, the normalizer applies `attach` and emits a `DeprecationWarning` during V0.2 rollout so legacy `.lth` sources continue to compile.

## Pivot types

Pivots are reference frames used for transforms, collision footprints, sight lines, and grip targets. They do not have an `aabb` — only a `transform`.

| `pivot_type`  | Description                                                                      | Use case                                                         |
| ------------- | -------------------------------------------------------------------------------- | ---------------------------------------------------------------- |
| `world`       | World origin (identity transform). Every asset inherits one by default.          | Engine hand-off, authoring frame reference.                      |
| `center`      | Bounding-box / mass-centroid pivot. Default when no type is declared.            | Rotation and scaling origin during posing or preview rendering.  |
| `bottom`      | Bottom-center contact pivot, aligned with the asset's lower AABB face.           | Placing the asset on a floor without penetration.                |
| `contact`     | Explicit ground-contact pivot driven by the collision proxy, not just the AABB.  | Vehicles with wheels, creatures on feet — the real contact surface. |
| `hand_hold`   | Pivot that a character hand should snap to when holding the asset.               | Props that animation/IK picks up — complements socket `hand`.    |
| `sight_line`  | Pivot aligned with an optical or aim axis.                                       | Weapon sights, camera aim anchors, surveillance pointing.         |

**Default**: when a pivot is declared without `pivot_type`, the normalizer applies `center` and emits a `DeprecationWarning`. Every asset inherits a `world` pivot at identity transform if no pivots are declared at all.

## Transform convention

- `transform` is a 4x4 row-major homogeneous matrix in the asset's coordinate system (see `coordinateSystem` block of the selector manifest).
- For sockets the transform's translation component is the anchor origin; the rotation defines the attachment frame (e.g. the direction a plugged port points, the axis a hinge rotates around).
- For pivots only the translation + rotation are meaningful; there is no associated AABB.
- Identity is `[[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]]`.

## AABB convention (sockets only)

- `aabb.min` / `aabb.max` are length-3 vectors in manifest units.
- The AABB describes the region the socket occupies (e.g. the volume a battery fills when inserted into a `slot`), not the whole host asset.
- Within stage-level precision an AABB on a socket matches the mesh geometry near the socket origin to within 1e-6.
