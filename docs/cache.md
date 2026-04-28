# Build cache

Lathe caches completed builds under a user-level cache directory so that
re-running `lathe build` on an unchanged program + asset + runtime
config skips straight to the packaged outputs.

V0.2 promotes the cache out of the system temp dir (where it was wiped
on reboot) into a stable, per-user location, and adds a
`lathe cache status|clean|warm` CLI for inspecting and managing it.

## Where the cache lives

The builds cache root is `<LATHE_CACHE_DIR>/builds/`. The root resolves
in this order:

| Precedence | Source                                                         |
|-----------:|----------------------------------------------------------------|
| 1          | `LATHE_CACHE_DIR` environment variable (tilde-expanded)        |
| 2          | `platformdirs.user_cache_dir("lathe")` if `platformdirs` is installed |
| 3          | Platform fallback (below)                                      |

Fallback paths when `platformdirs` is not installed:

| Platform       | Default path                                                   |
|----------------|----------------------------------------------------------------|
| Linux / macOS  | `$XDG_CACHE_HOME/lathe` or `~/.cache/lathe`                    |
| Windows        | `%LOCALAPPDATA%\lathe\cache` or `%USERPROFILE%\.lathe\cache`   |

Each cache entry is a directory named by the build's `cache_key` (a
SHA-256 hash) and contains the full packaged build output. Current
entries also include a root `manifest.json` used only as cache metadata;
the package evidence remains under `stages/package/`. The hash is
content-addressed: moving the cache root does not change which keys are
produced, so an existing entry in a new root continues to hit.

Typical entry layout:

```text
<LATHE_CACHE_DIR>/builds/<cache_key>/
  manifest.json                         # cache metadata: key, asset, version
  build_report.json                     # aggregate build report
  selector_manifest.json                # gameplay/import sidecar
  materialized_asset.json
  normalized_program.json
  plan.json
  stages/
    package/
      package_manifest.json             # packaged outputs + hashes
      trace_manifest.json               # stage/provider trace
      <asset>.glb
      <asset>.usda
      previews/
```

The canonical package evidence paths inside each entry are
`stages/package/package_manifest.json` and
`stages/package/trace_manifest.json`.

## `LATHE_CACHE_DIR` override

```
# Linux / macOS
export LATHE_CACHE_DIR=/mnt/fast-nvme/lathe-cache

# Windows (PowerShell)
$env:LATHE_CACHE_DIR = "D:\lathe-cache"
```

Useful to point the cache at a faster disk, share a cache across users
on a build machine, or mount it into a container.

## Cache key

The cache key hashes:

- `cache_version` (bumped when the cache format changes — currently `v10_rc2`)
- the normalized program AST
- the asset name
- the resolved runtime config
- a stable build-environment fingerprint covering selected backends,
  deterministic adapter capability reports, and registered shape providers

Any change to those inputs produces a new key and a new entry. See
`lathe/executor.py` for the exact composition.

## `lathe cache` CLI

```
lathe cache status [--json]
```

Lists every entry under the builds root, with total size and a
per-asset breakdown. Use `--json` for machine-readable output; entries
include the cache key, byte size, asset/variant hints, cache version,
backend stack, source fingerprint, metadata source, and absolute entry
path.

Example JSON shape:

```json
{
  "cache_dir": "/home/me/.cache/lathe",
  "entry_count": 1,
  "total_bytes": 1048576,
  "per_asset": {
    "courier_drone": {"count": 1, "size_bytes": 1048576}
  },
  "entries": [
    {
      "key": "9f0a...",
      "asset": "courier_drone",
      "variant": null,
      "cache_version": "v10_rc2",
      "backend_stack": "lathe.stack.hard_surface_game_asset_v1",
      "source_fingerprint": "d7b1...",
      "metadata_source": "manifest.json",
      "path": "/home/me/.cache/lathe/builds/9f0a..."
    }
  ]
}
```

```
lathe cache clean [--asset NAME] [--older-than 7d] [--dry-run] [--yes]
```

Deletes entries matching the filter. `--older-than` accepts durations
like `30m`, `24h`, `7d`, `2w`. `--dry-run` reports what would be deleted
without touching the filesystem; without `--dry-run`, `--yes` is
required as a safety gate.

Examples:

```bash
lathe cache clean --asset courier_drone --dry-run
lathe cache clean --older-than 2w --yes
```

```
lathe cache migrate [--dry-run]
```

Backfills root `manifest.json` cache metadata for older entries when Lathe can
infer asset, backend stack, cache version, source fingerprint, and created time
from existing `build_report.json`, package manifest, and trace manifest files.
Entries whose identity cannot be inferred are skipped rather than filled with
guesses. Use `--dry-run` first to see what would be written:

```bash
lathe cache migrate --dry-run
lathe cache migrate
```

```
lathe cache warm <file> <asset> [--runtime-config PATH]
```

Runs `lathe build` for the given asset and reports the resulting cache
entry. If the same inputs are already cached the underlying build still
short-circuits; `warm` is intended to be run in CI or a setup script.

Example:

```bash
lathe cache warm examples/courier_drone.lth courier_drone \
  --runtime-config examples/runtime_configs/auto_learned.json
```

## Invalidation

To force a rebuild:

- Delete the specific entry under the cache root (or use
  `lathe cache clean --asset NAME --yes`).
- Or change one of the hash inputs (edit the source, pass a different
  `--runtime-config`, rename the asset).
- Or bump `BUILD_CACHE_VERSION` in `lathe/executor.py` — this
  invalidates every entry and is the preferred lever when the cache
  format itself changes.

## CI hint

Mount the cache dir as an action cache to skip redundant builds across
jobs:

```yaml
# GitHub Actions example
- uses: actions/cache@v4
  with:
    path: ~/.cache/lathe/builds
    key: lathe-builds-${{ runner.os }}-${{ hashFiles('**/*.lth') }}
    restore-keys: |
      lathe-builds-${{ runner.os }}-
```

On Windows runners, substitute `~/AppData/Local/lathe/cache/builds` (or
set `LATHE_CACHE_DIR` to an absolute path you control).
