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
SHA-256 hash) and contains the full packaged build output, including
`manifest.json`. The hash is content-addressed: moving the cache root
does not change which keys are produced, so an existing entry in a new
root continues to hit.

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

Any change to those inputs produces a new key and a new entry. See
`lathe/executor.py` for the exact composition.

## `lathe cache` CLI

```
lathe cache status [--json]
```

Lists every entry under the builds root, with total size and a
per-asset breakdown. Use `--json` for machine-readable output.

```
lathe cache clean [--asset NAME] [--older-than 7d] [--dry-run] [--yes]
```

Deletes entries matching the filter. `--older-than` accepts durations
like `30m`, `24h`, `7d`, `2w`. `--dry-run` reports what would be deleted
without touching the filesystem; without `--dry-run`, `--yes` is
required as a safety gate.

```
lathe cache warm <file> <asset> [--runtime-config PATH]
```

Runs `lathe build` for the given asset and reports the resulting cache
entry. If the same inputs are already cached the underlying build still
short-circuits; `warm` is intended to be run in CI or a setup script.

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
