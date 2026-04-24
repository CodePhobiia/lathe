# `@lathe[...]` Semantic References

> Public reference for the V0.2 E1 Semantic Reference System.
> Status: **Phase 1 (non-geometric) — landed.** Phase 2 (face/edge/vertex extraction) is scheduled for the follow-on wave.

A `@lathe[...]` token names an addressable entity in a Lathe source or a completed Lathe build. Tokens are stable, round-trippable strings that can be embedded in chat, diagnostics, reports, issue trackers, and agent prompts. The token grammar is defined by `lathe/ref.py`; the forward-looking sidecar shape is defined by `schema/lathe.selector.schema.json`.

## Grammar

```
ref        := "@lathe[" target ( "#" selector )? "]"
target     := <repo-relative path to a build dir or a .lth source file>
selector   := kind "." id
kind       := "asset" | "variant" | "stage" | "diagnostic" | "part"    ; Phase 1
           |  "socket" | "collision" | "pivot" | "material"            ; Phase 2
           |  "lod" <n>                                                ; Phase 2
id         := [A-Za-z_][A-Za-z0-9_.\-]*
```

**Sub-part selectors** (Phase 2 — REF-6):

```
selector   := "part." id ( ".face" <n> | ".edge" <n> | ".vertex" <n> )
```

Tokens are always surrounded by `@lathe[` / `]`. The target portion must be a **repo-relative** path — absolute Windows paths (`C:\...`), UNC paths (`\\?\...`), and `..` traversal components are rejected up front by `parse_ref`.

## Phase 1 vs. Phase 2

| Kind | Phase 1 | Phase 2 (future) |
|---|---|---|
| whole build (`@lathe[dir]`) | ✅ resolves | — |
| `#asset.<name>` | ✅ resolves | — |
| `#variant.<name>` | ✅ resolves | — |
| `#stage.<name>` | ✅ resolves | — |
| `#diagnostic.<id>` | ✅ resolves | — |
| `#part.<id>` | ✅ resolves via shape bundle `part_labels` | richer bbox/faces once REF-6 lands |
| `#part.<id>.face<n>` | ❌ `phase_2_feature_not_yet_available` | ✅ REF-6 |
| `#part.<id>.edge<n>` | ❌ `phase_2_feature_not_yet_available` | ✅ REF-6 |
| `#part.<id>.vertex<n>` | ❌ `phase_2_feature_not_yet_available` | ✅ REF-6 |
| `#socket.<id>` | ❌ `phase_2_feature_not_yet_available` | ✅ REF-5 manifest |
| `#collision.<id>` | ❌ `phase_2_feature_not_yet_available` | ✅ REF-5 manifest |
| `#pivot.<id>` | ❌ `phase_2_feature_not_yet_available` | ✅ REF-5 manifest |
| `#material.<id>` | ❌ `phase_2_feature_not_yet_available` | ✅ REF-5 manifest |
| `#lod<n>.<id>` | ❌ `phase_2_feature_not_yet_available` | ✅ REF-5 manifest |

Phase-2 shapes are **parsed** (to produce a clear error) but **not resolved**. `parse_ref` raises `RefParseError` with `code="phase_2_feature_not_yet_available"` and points back at this doc plus the V0.2 roadmap.

## Resolution

`resolve_ref(parse_ref(token))` returns a JSON-shaped dict:

```json
{
  "ok": true,
  "ref": "@lathe[dist/courier_drone#asset.courier_drone]",
  "target_path": "D:/lathe_v0_1/dist/courier_drone",
  "target_kind": "build",
  "selector_kind": "asset",
  "selector_id": "courier_drone",
  "facts": { "asset": "courier_drone", "kind": "mechanical_assembly", "certified": true, "backend_stack_id": "lathe.stack.hard_surface_game_asset_v1" }
}
```

Resolution rules (Phase 1):

- A **whole-build** ref (no `#selector`) reads `build_report.json` and surfaces asset, kind, cert status, backend stack id, stage ids, diagnostic count, and output artifacts.
- An **`asset.<name>`** selector matches `build_report.json.asset` exactly. Mismatches produce `ok: false` + `reason: "asset_not_in_build"`.
- A **`variant.<name>`** selector also matches against `build_report.json.asset` because materialized variants are built under their own asset name. Mismatches include a helpful hint to run `lathe materialize <file> <variant>`.
- A **`stage.<name>`** selector matches a key in `build_report.json.stage_bundles`. Known stages: `shape`, `topology`, `uv`, `surface`, `rig`, `interfaces`, `physics`, `optimize`, `validate`, `package`.
- A **`diagnostic.<id>`** selector walks the top-level `diagnostics` array plus per-stage `diagnostics`, matching on `id` or `code`.
- A **`part.<id>`** selector reads the selected candidate's `part_labels` from `stages/shape/bundle.json`. Phase 2 (REF-6) will replace this with the selector manifest's authoritative `parts[]` list.

If the target path points at a **.lth source file**, Phase 1 only confirms the file exists and returns `source_ref_not_yet_resolved` — source-level ref resolution (e.g. naming an asset block inside an un-built source file) lands with REF-5 selector manifests in the next wave.

## Stale-ref behaviour

`StaleRefWarning` (a `UserWarning` subclass) fires — **without raising** — in these cases:

- The target directory exists but has no `build_report.json` (build never completed or was cleaned).
- A `#asset.<name>` selector does not match the `asset` field in `build_report.json` (build was renamed or a different asset was built into this directory).

Stale-ref warnings are strictly advisory in Phase 1. Agents and scripts that want hard failures can flip them with `warnings.simplefilter("error", StaleRefWarning)`. Stricter hash-based drift detection (source hash, build hash, selector-manifest hash) lands with REF-7 and the REF-5 manifest writer.

## Examples

Against the `examples/courier_drone.lth` hero and its `dist/courier_drone/` build:

| Token | Meaning |
|---|---|
| `@lathe[dist/courier_drone]` | Whole build — returns cert + outputs summary |
| `@lathe[dist/courier_drone#asset.courier_drone]` | The built asset |
| `@lathe[dist/courier_drone#variant.courier_drone_mobile]` | A variant (may emit a `variant_not_in_build` fact until the mobile variant is materialized) |
| `@lathe[dist/courier_drone#stage.shape]` | The shape stage's bundle |
| `@lathe[dist/courier_drone#stage.package]` | The package stage (includes `.glb` / `.usda`) |
| `@lathe[dist/courier_drone#diagnostic.bake_missing]` | A specific diagnostic id |
| `@lathe[dist/courier_drone#part.body]` | The drone body part |
| `@lathe[dist/courier_drone#part.rotor_fl]` | Front-left rotor part |
| `@lathe[examples/courier_drone.lth]` | Source file (Phase 1: existence only) |
| `@lathe[examples/courier_drone.lth#asset.courier_drone]` | Source-side asset ref (Phase 1: deferred to REF-5) |

Rejected tokens (all raise `RefParseError`):

| Token | Reason |
|---|---|
| `@lathe[../../etc/passwd]` | `path_traversal_rejected` |
| `@lathe[C:\\secrets]` | `path_traversal_rejected` |
| `@lathe[\\\\?\\share]` | `path_traversal_rejected` |
| `@lathe[dist/foo#part.body.face12]` | `phase_2_feature_not_yet_available` |
| `@lathe[dist/foo#socket.grip]` | `phase_2_feature_not_yet_available` |
| `@lathe[dist/foo#nope.bar]` | `unknown_selector_kind` |
| `dist/foo#asset.bar` | `missing_prefix` |
| `@lathe[]` | `empty_ref` |

## Extending with REF-5 selector manifests

REF-5 (next wave) adds a per-build `selector_manifest.json` written alongside `build_report.json` and validated against `schema/lathe.selector.schema.json`. Once that manifest exists, `resolve_ref` will prefer it over the ad-hoc scan of `stages/shape/bundle.json`, and Phase-2 kinds (`socket`, `collision`, `pivot`, `material`, `lod<n>`) will resolve to concrete facts. REF-6 then populates the `faces`, `edges`, and `vertices` arrays from the final mesh.

## CLI

```
lathe ref parse '@lathe[dist/courier_drone#asset.courier_drone]'
```

Exit codes: `0` on success (JSON on stdout), `2` on parse error (JSON on stderr, including a stable `error.code`).

## See also

- `lathe/ref.py` — parser, resolver, exception hierarchy.
- `schema/lathe.selector.schema.json` — forward-looking sidecar schema.
- `docs/next_version_roadmap.md` section **E1** — roadmap & tickets (REF-1..REF-16).
- `AGENTS.md` — agent-facing rules about using refs in edit workflows (refreshed with AGENT-7).
