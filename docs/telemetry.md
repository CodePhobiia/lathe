# Telemetry

Lathe ships a minimal, opt-in, anonymous build-ping telemetry pipeline.
It is **disabled by default**; nothing is sent unless you explicitly run
`lathe telemetry enable`.

This page documents exactly what is collected, what is deliberately not
collected, how retention works, and how to turn it off / purge local state.

## TL;DR

- Default: **off** (no config file = telemetry disabled).
- Opt-in: `lathe telemetry enable` (prompts for confirmation).
- Opt-out: `lathe telemetry disable` (preserves your anonymous salt).
- Purge: `lathe telemetry clear` (deletes local telemetry state).
- Ingest URL: `https://telemetry.lathe.dev/ingest`.
- Retention: 90 days, then aggregated/deleted.

## What is collected

When enabled, after a successful `lathe build`, a single small JSON POST is
sent to the ingest URL. The payload has these fields and nothing else:

| Field            | Type   | Description                                                                 |
|------------------|--------|-----------------------------------------------------------------------------|
| `lathe_version`  | string | The `lathe.__version__` of the running CLI (e.g. `"0.2.0rc1"`).             |
| `build_id_hash`  | string | `sha256(local_salt + build_id)[:16]`; the salt itself is never sent.        |
| `build_kind`     | string | Public asset kind, such as `hard_surface_prop` or `mechanical_assembly`.    |
| `stack_id`       | string | Backend stack id used (e.g. `lathe.stack.hard_surface_game_asset_v1`).      |
| `certified`      | bool   | Whether the build certified.                                                |
| `exit_code`      | int    | Build exit status (0 on success).                                           |
| `wall_ms`        | int    | Wall-clock build duration in milliseconds.                                  |

Example payload from the checked-in golden fixture:

```json
{
  "lathe_version": "0.2.0rc1",
  "build_id_hash": "4c00ad8bec8f6988",
  "build_kind": "mechanical_assembly",
  "stack_id": "lathe.stack.hard_surface_game_asset_v1",
  "certified": false,
  "exit_code": 1,
  "wall_ms": 9876
}
```

The fixture intentionally starts from a poisoned build report containing local
paths, a raw build id, an asset name, diagnostics, logs, an environment token,
an output hash, and a provider-key-like string. None of those values may appear
in the emitted payload.

## What is NOT collected

The emitter is implemented against a strict allow-list. The following are
**never included** in the payload:

- Asset content (meshes, textures, materials, images, UV, bakes).
- `.lth` source text, names of your files, or anything derived from them.
- Any filesystem paths (source paths, output dirs, repo roots).
- Environment variables, usernames, hostnames, MAC addresses, IP addresses.
- Provider API keys, tokens, or auth material.
- Build logs, stdout, stderr, or stage diagnostics.
- Runtime config contents (strict mode, codex imagegen mode, etc. are
  intentionally not reported — they are a user preference, not a metric).
- Raw telemetry salts or local identifiers.

Because `build_id_hash` is salted with a locally-held random value, the
ingest side cannot link your pings back to you without physical access to
your machine. If you re-install and run `lathe telemetry enable` again,
a brand-new salt is generated and prior pings become un-correlatable.

## How opt-in works

1. `lathe telemetry enable` prompts:
   `This will enable anonymous opt-in telemetry. Proceed? [y/N]`
   (use `--yes` / `-y` to skip the prompt in scripts).
2. On confirm, a JSON config file is written to an OS-appropriate user
   config directory:
   - Windows: `%APPDATA%\lathe\telemetry.json`
   - macOS: `~/Library/Application Support/lathe/telemetry.json`
   - Linux: `$XDG_CONFIG_HOME/lathe/telemetry.json` or `~/.config/lathe/telemetry.json`
3. That file contains `{enabled: true, user_salt: "<hex>"}`. The salt is
   used locally to derive the one-way `build_id_hash`; it never leaves the
   machine.

## How to turn it off / purge data

- `lathe telemetry disable` — sets `enabled=false`; no more pings. Salt is
  retained so re-enabling keeps your prior aggregate-identity stable.
- `lathe telemetry clear` — deletes the entire local config file. The next
  `enable` will generate a fresh salt.
- Firewall the URL `telemetry.lathe.dev` if you want belt-and-braces.

## Retention & auditability

- Pings are retained for 90 days in raw form, then deleted. Aggregated
  rollups (e.g. "weekly active builds per version") are retained longer.
- The emission path is failure-silent: if the network is down, the host is
  blocked by SSRF policy, or the ingest returns any error, the build is
  **not** affected. You will see a clean build report regardless.
- Network traffic can be audited by any `mitmproxy`-class tool; the emitter
  goes through `lathe.net.safe_urlopen`, which enforces HTTPS, TLS 1.2+,
  DNS-based SSRF guards, and a 2-second timeout.

## Future scope

A public aggregated-metrics dashboard (top stacks, build-duration
distributions by version, failure-code histogram) is **deferred**. This
MVP only wires the ingest pipe; no public dashboard exists yet.
