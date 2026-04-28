# Lathe Terms of Service

## Status

Lathe is open-source software distributed under the Apache License 2.0. There
is no SaaS, no account system, and no monetized surface in v0.2.0rc1.
Standard third-party Terms of Service do not apply because Lathe does not
host a service or accept user uploads in this release.

This page is a pre-release applicability statement. It is not a contract and
has not been reviewed by counsel.
`requires-human: counsel review before public launch.`

## Applicability decision

ToS is **not applicable** to v0.2.0rc1 because no hosted user-facing service
exists. The governing instruments for v0.2.0rc1 are:

- **[LICENSE](../LICENSE)** — Apache License 2.0 governs use, reproduction,
  modification, and redistribution of the Lathe code and reference compiler.
- **[SECURITY.md](https://github.com/talmerri/lathe/blob/main/SECURITY.md)** — governs vulnerability disclosure,
  coordinated-disclosure window, and safe-harbor scope.
- **[docs/privacy.md](privacy.md)** — governs telemetry behavior, opt-in
  consent capture, and the allowlisted payload shape.

Optional third-party integrations (Hunyuan3D, VGGT, Codex ImageGen, Blender,
xatlas, etc.) remain governed by their respective upstream licenses and
terms. Users who configure those integrations via `--runtime-config` are
responsible for complying with the upstream terms; Lathe does not proxy or
re-license third-party services.

## When ToS will become applicable

A user-facing Terms of Service document must be drafted and adopted **before
any of the following surfaces ship**:

- A hosted asset registry, package index, or shared cache.
- A hosted CI surface, paid build minutes, or any monetized API.
- An account system, login surface, or per-user identity store.
- A user-content upload path (asset uploads, screenshots, gallery
  submissions).
- A hosted telemetry dashboard exposing per-user data back to the user.

`requires-human: counsel-drafted Terms of Service must be in place before any
of the above surfaces becomes part of a Lathe release.`

## Last reviewed

- Date: 2026-04-28
- Reviewer: Tal Merri (solo maintainer, self-assessment)
- Counsel review: `requires-human: not yet engaged.`
