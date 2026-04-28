# Lathe Privacy Notice

## Status

Lathe v0.2.0rc1 ships with telemetry **disabled by default**. No personal data
is collected from users running the CLI unless they explicitly opt in via
`lathe telemetry enable`. This document describes what would be collected if a
user opts in, and what is never collected even then.

This is a pre-release notice for a reference compiler scaffold. It does not
constitute legal advice and has not been reviewed by counsel.
`requires-human: counsel review before public launch.`

## Data we do not collect (ever)

The opt-in telemetry payload is constructed by `_build_payload` in
`lathe/telemetry.py` and only contains the allowlisted fields enumerated in
the next section. The following are **never** transmitted, regardless of the
opt-in state:

- Source-file paths (`.lth` file names, asset directories, `--out` paths).
- Asset names declared in `.lth` sources.
- Environment variables (no environment is read into the payload).
- Provider API keys, runtime-config contents, or model-server URLs.
- Build diagnostics, stage logs, validator messages, or error message bodies.
- Mesh, image, texture, or `.blend` content.
- Full or partial source content of any `.lth` file.
- The persistent local salt itself (only the first four characters appear in
  `lathe telemetry status` and only locally; the salt never leaves the
  machine).

The build identity transmitted is `sha256(local_salt + build_id)[:16]`. Ingest
cannot recompute or correlate build identities across users without the local
salt, which is never sent.

## Data we may collect when telemetry is opted in

If and only if a user has run `lathe telemetry enable`, each `lathe build`
invocation may emit one anonymous build-ping HTTPS POST to
`https://telemetry.lathe.dev/ingest` with the following allowlisted fields
(exact source: `lathe/telemetry.py:_build_payload`):

| Field            | Type    | Source                                                       |
| ---------------- | ------- | ------------------------------------------------------------ |
| `lathe_version`  | string  | `lathe.__version__`                                          |
| `build_id_hash`  | string  | `sha256(local_salt + build_id)[:16]`, empty when no build_id |
| `build_kind`     | string  | `build_report["kind"]` (e.g., `generate`, `reconstruct`)     |
| `stack_id`       | string  | Backend stack id (e.g., `lathe.stack.hard_surface_game_asset_v1`) |
| `certified`      | bool/null | Validator certification result                             |
| `exit_code`      | int     | CLI exit code                                                |
| `wall_ms`        | int     | Wall-clock build duration in milliseconds                    |

This list is exhaustive for v0.2.0rc1. There are no free-text fields, no IDs
derived from paths or asset names, no OS or hardware fingerprints, and no
network identifiers beyond the TLS connection itself.

`requires-human: implement allowlist enforcement test before any public ingest
endpoint is provisioned, so payload-shape regressions cannot leak fields the
allowlist does not cover.`

The transport (`lathe.net.safe_urlopen`) enforces a hostname allowlist
(`telemetry.lathe.dev`), a 2-second timeout, and a 64 KiB cap. Failures are
silent and never raise into the build path.

## Consent capture and opt-out

Telemetry is opt-in. The `lathe telemetry enable` command shows an
interactive confirmation prompt by default; `--yes` skips it for scripted
environments. On confirmation, the local config file is written to an
OS-appropriate user config directory:

- `%APPDATA%\lathe\telemetry.json` on Windows
- `~/Library/Application Support/lathe/telemetry.json` on macOS
- `$XDG_CONFIG_HOME/lathe/telemetry.json` (or `~/.config/lathe/...`) on Linux

The config contains `enabled: true` and a 16-byte hex `user_salt`. There is
currently no separate consent record file with timestamp and version; the
config file's existence and `enabled` flag are the consent signal.
`requires-human: decide whether to add an explicit consent record (timestamp
+ Lathe version + privacy-doc revision the user agreed to) before any public
ingest is enabled, so consent provenance is auditable.`

Opt-out is `lathe telemetry disable`, which sets `enabled: false` while
preserving the salt so subsequent re-enable does not generate a new identity.
`lathe telemetry clear` deletes the local config file entirely. (The
readiness brief refers to `lathe telemetry purge`; the implemented command
name is `clear` — see `lathe/cli/telemetry_cmd.py`.)

## Retention

Proposed default for any future ingest: **90 days**, after which raw events
must be deleted or aggregated. `requires-human: ingest is not provisioned in
v0.2.0rc1 — retention enforcement is design-only and must be implemented
before the ingest endpoint goes live.`

## Deletion

- Local data: `lathe telemetry clear` deletes the local `telemetry.json`
  entirely. `lathe telemetry disable` retains the salt only.
- Remote data: `requires-human: ingest is not provisioned in v0.2.0rc1; a
  user-initiated remote-deletion path must be designed and implemented before
  any public ingest goes live.`

## Export

`requires-human: a user-facing local export command (e.g., `lathe telemetry
export`) is not implemented in v0.2.0rc1. The local `telemetry.json` is plain
JSON and can be inspected directly. Implement a structured export before any
public claim about user data portability.`

## Vendors touching user data

**None in v0.2.0rc1.** Telemetry is disabled by default, the ingest endpoint
is not provisioned, and no other path in the CLI sends user-identifiable data
to a third party. Optional integrations (Hunyuan3D, VGGT, Codex ImageGen) are
configured by the user via `--runtime-config` and call endpoints the user
chooses; Lathe does not proxy or relay that traffic.

`requires-human: name the ingest provider (and its data-processing agreement
status) before any public dashboard or aggregated-statistics claim is made.`

## Bug bounty / responsible disclosure

See [SECURITY.md](https://github.com/talmerri/lathe/blob/main/SECURITY.md). Safe-harbor language is included there;
`requires-human: counsel review of the safe-harbor language before public
launch.`

## Contact

- Email: <talmerri@gmail.com> (subject prefix `[PRIVACY]` for privacy
  questions, `[SECURITY]` for vulnerabilities).
- GitHub Security Advisories via the repository **Security** tab once the
  repo is public.

## Last reviewed

- Date: 2026-04-28
- Reviewer: Tal Merri (solo maintainer, self-assessment)
- Counsel review: `requires-human: not yet engaged; public launch is gated on
  counsel sign-off per Phase 2 of the v0.2.0rc1 readiness checklist.`
