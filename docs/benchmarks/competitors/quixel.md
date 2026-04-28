# Quixel Megascans — manual run instructions

_Status: not_run. No Quixel runs have been executed in this study yet._

Quixel is the "buy, don't build" baseline. For each asset we search the
Megascans library for the closest matching scanned asset, download it, and
measure the same metrics. Megascans is not a generator — this row is
deliberately here to show that for *real-world* props, scan-and-license can
beat any generator.

## Account setup

1. Sign in at https://quixel.com (Epic account). Megascans is free for use
   inside Unreal Engine; other use requires an Epic Games Account check and
   may require a paid indie plan — verify licensing before publishing results.
2. Install the Megascans Bridge desktop app.

## Search per asset

The 5 assets may or may not map cleanly to a Megascans entry. Be honest: if
Megascans has no matching asset, score the row `result: "not_run"` with the
reason "no library match" and leave it that way.

| Asset | Search term(s) |
|---|---|
| `industrial_crate` | "industrial crate", "shipping crate", "wooden crate" |
| `sci_fi_wall_panel` | "sci fi wall panel", "industrial wall trim" (Megascans leans photoreal so exact sci-fi may not exist) |
| `mechanical_door` | "industrial door", "factory door" |
| `control_pedestal` | "control panel", "pedestal", "kiosk base" |
| `service_cabinet` | "service cabinet", "electrical cabinet", "industrial cabinet" |

Document the exact search term and asset ID used.

## Export

1. Download the asset at **High** quality from Bridge.
2. Export as GLTF/GLB (Bridge supports this via export settings).
3. Do not re-mesh or decimate — we want the raw Megascans output.

## Ingest

Manual, as with other competitors. Record:

- Megascans asset ID.
- Download + export wall time (the "wall_clock_s" for Quixel is basically
  library search + download, which is fundamentally different from generation
  time — note this in `note`).
- Whether the asset was photoscan (PBR-heavy, multi-material) or authored.

## Known caveats

- Megascans produces multi-million-triangle source meshes. The fair
  comparison is the **High** LOD. Record the LOD in the `note` field.
- Quixel assets typically have PBR materials but no collision proxy, no named
  pivot anchor, and often no second UV channel. Record honestly.

## Licensing

Free for UE projects, paid for indie non-UE use. Verify current terms before
publishing.
