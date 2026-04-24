# Engine handoff

STAGE-10 of the V0.2 E3 roadmap (next_version_roadmap.md, PRODUCTION READINESS). Every certified Lathe build emits one sidecar *engine manifest* per target engine alongside the main glb + collision meshes + per-LOD glbs. The manifests are **hints**, not full asset conversions — downstream engine importers (Godot EditorImportPlugin, Unity ScriptedImporter, Unreal Interchange glTF utility) read them to wire the existing artifacts into an engine-native scene hierarchy without manual cleanup.

Lathe does not ship integrations with every engine. The core keeps the manifests small, deterministic, and purely declarative; engine-specific importers (under `editors/` or third-party plugins) consume them.

## Shared output layout

```
dist/<asset>/
  <asset>.glb                       # main authored mesh
  lod_0.glb .. lod_3.glb            # LOD ladder (copied from stages/optimize/)
  collision_hull.glb                # single convex hull
  collision_parts.glb               # per-part hulls fused into one glb
  selector_manifest.json            # canonical sidecar (schema: lathe.selector)
  <asset>.lathe_for_godot.json      # STAGE-10 sidecar — Godot
  <asset>.lathe_for_unity.yaml      # STAGE-10 sidecar — Unity
  <asset>.lathe_for_unreal.json     # STAGE-10 sidecar — Unreal
```

Every sidecar carries `schemaVersion: 1`, `engine` (id), `engineVersion` (min supported), `assetName`, and an engine-native scene-graph description that references artifacts by *relative path*. The selector manifest tracks each sidecar under `engineManifests.{godot,unity,unreal}` with the sha256 hash for reproducibility.

## Godot — `lathe_for_godot.json`

Consumed by an `EditorImportPlugin` (Godot 4.2+). The plugin materialises:

* A `Node3D` root named `<asset>`, with `gameplay_tags` copied to the root's `meta` dict.
* A `LODGroup`-shaped list of `MeshInstance3D` children named `LOD0..LODn`, each carrying `visibility_range_begin` / `visibility_range_end` (metres) from the LOD ladder.
* `Marker3D` sockets + pivots (Position3D pattern), each with `anchor_id` and `socket_type` / `pivot_type` in `meta`.
* A `StaticBody3D` carrying `CollisionShape3D` children for `collision_hull.glb` (single) and `collision_parts.glb` (compound).

## Unity — `lathe_for_unity.yaml`

Consumed by a `ScriptedImporter` (Unity 2022.3+). Hand-formatted YAML (no third-party yaml dependency in Lathe's core). The importer materialises:

* A root `GameObject` with `tags` applied via Unity's tag/label system.
* A `LODGroup` component with per-LOD `screenRelativeTransitionHeight` (from `screen_coverage`) plus `distanceMin/Max` hints.
* Empty `GameObject` children for each socket/pivot (attachment convention).
* `MeshCollider` components for the collision meshes.

## Unreal — `lathe_for_unreal.json`

Consumed by an Interchange/Editor-Utility plugin (Unreal 5.3+). The plugin materialises:

* An `AActor` class scaffold with `GameplayTagContainer` carrying the declared gameplay tags.
* `UStaticMeshComponent` children with `MinDrawDistance` / `LDMaxDrawDistance` from the distance bands.
* `UArrowComponent` sockets/pivots, each with `socketName` + `Tags` entries naming the anchor id and typed kind.
* `UBodySetup` aggregation pointing at the collision glbs.

## LOD configuration

See `docs/gameplay_tags.md` for the tag vocabulary. LOD distance bands default to:

| Level | distance_min | distance_max | screen_coverage |
| ----- | ------------ | ------------ | --------------- |
| LOD0  | 0            | 10           | 1.0             |
| LOD1  | 10           | 30           | 0.4             |
| LOD2  | 30           | 100          | 0.15            |
| LOD3  | 100          | ∞            | 0.05            |

Override per-asset via `build.optimize.lod_config`:

```
build {
  optimize {
    lods = 4
    lod_config = [
      { level = 0, ratio = 1.0,  distance_min = 0,   distance_max = 8,   screen_coverage = 1.0 },
      { level = 1, ratio = 0.5,  distance_min = 8,   distance_max = 25,  screen_coverage = 0.35 },
      { level = 2, ratio = 0.25, distance_min = 25,  distance_max = 80,  screen_coverage = 0.12 },
      { level = 3, ratio = 0.1,  distance_min = 80,  screen_coverage = 0.04 }
    ]
  }
}
```

Omitting `distance_max` on the final entry is the canonical way to signal an unbounded outer band.
