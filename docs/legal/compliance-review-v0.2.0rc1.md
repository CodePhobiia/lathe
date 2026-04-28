# Compliance Review — Lathe v0.2.0rc1

> **This document is a self-assessment.** No qualified counsel has reviewed
> v0.2.0rc1 as of 2026-04-28. Public launch is BLOCKED until counsel review
> is complete OR a launch exception is recorded with named owner,
> justification, and removal target. — `requires-human: counsel review.`

Scope: the `lathe` Python package and CLI at version 0.2.0rc1, distributed
under Apache-2.0, with telemetry disabled by default and no hosted user-facing
service.

## Regulatory applicability

### GDPR (EU)

**Applicability:** Not applicable to v0.2.0rc1. No personal data is collected
from users by default. The CLI runs locally and does not transmit
identifiable information when telemetry is disabled (the default).

If a user explicitly enables telemetry via `lathe telemetry enable`, the
allowlisted payload (see [docs/privacy.md](../privacy.md)) is engineered to
avoid personal data: build IDs are salted and hashed locally, asset names and
paths are excluded, and the only network identifier is the TLS connection
metadata at the ingest endpoint. Even so, a salted-hash + IP combination from
an EU resident could be argued to be personal data under a strict reading of
GDPR Recital 30.

`requires-human: re-assess GDPR applicability when (a) any telemetry ingest
endpoint is provisioned, (b) any hosted surface ships, or (c) the project
ever knowingly accepts data from EU residents. Counsel must confirm
controller/processor split, lawful basis, and data-subject-rights surface
before public ingest.`

### CCPA / CPRA (California)

**Applicability:** Not applicable to v0.2.0rc1 for the same reason as GDPR:
no personal information is collected by default, and the project does not
sell or share consumer data because no consumer data is collected.

`requires-human: re-assess if telemetry ingest goes live or if any hosted
surface ships, particularly for "Do Not Sell or Share My Personal
Information" surface requirements and the right-to-delete pathway.`

### COPPA / child-safety

**Applicability:** Not applicable to v0.2.0rc1. Lathe is a developer-facing
CLI compiler for 3D asset intent. It is not directed at children under 13,
does not have an account system, and does not collect personal information.

### Export control (EAR / Wassenaar)

**Applicability:** Lathe is open-source software made publicly available on
GitHub and (when published) PyPI. Publicly available open-source software is
generally classified ECCN 5D002 with the TSU (Technology and Software —
Unrestricted) license exception under EAR §740.13(e), which permits
unrestricted publication.

`requires-human: confirm with counsel before making any public ECCN claim,
particularly because Lathe optionally integrates with learned-model providers
(Hunyuan3D, VGGT) whose model weights have separate export-control
considerations distinct from Lathe's source code.`

### Sanctions screening (OFAC / UK / EU)

**Applicability:** GitHub and PyPI handle sanctions enforcement at the
distribution-host layer. Lathe itself does not ship a billing or
account-creation surface, so there is no Lathe-side sanctions-screening
obligation in v0.2.0rc1.

`requires-human: document the project's position on sanctioned-jurisdiction
distribution once counsel weighs in. Re-assess if any hosted surface, paid
plan, or contributor-CLA flow ships.`

### PCI-DSS

**Applicability:** Not applicable to v0.2.0rc1. Lathe does not accept,
process, store, or transmit payment card data.

### HIPAA

**Applicability:** Not applicable to v0.2.0rc1. Lathe is not a covered entity
or business associate, and does not handle protected health information.

### SOC 2

**Applicability:** Not applicable to v0.2.0rc1. SOC 2 attests to the
controls of a service organization; Lathe does not operate a service in this
release. `requires-human: re-assess if any hosted surface ships and Lathe
becomes a service organization, particularly Trust Services Criteria for
Security and Confidentiality.`

## Vendors touching user data

| Vendor | Data handled | DPA status | Scope | Removal target |
| ------ | ------------ | ---------- | ----- | -------------- |
| (none) | —            | —          | —     | —              |

PyPI is used for distribution and GitHub is used for source hosting,
Actions, and security advisories. Neither is a vendor "touching user data" in
the sense relevant here, because Lathe transmits no user data to either
service beyond what the user themselves chooses to publish.

`requires-human: re-assess this table when any data-handling vendor (ingest
provider, error-reporting service, analytics, hosted CI for end users, etc.)
is added.`

## DPA status

N/A in v0.2.0rc1 — no vendor touches user data.

Trigger conditions for needing a Data Processing Agreement:

- Any third-party telemetry / analytics / error-reporting service is added.
- Any hosted ingest endpoint operated by a third party is provisioned.
- Any feature ships that uploads user-authored `.lth` content, refs, or
  build artifacts to a third-party system.

## IP-clearance review

### Checked-in fixtures

Source: `git ls-files examples/refs/ docs/gallery/` returned the following
tracked fixtures. `docs/gallery/` is currently empty (no tracked files), and
`examples/refs/` contains four files. All four are documented in
[docs/release/asset-provenance.md](../release/asset-provenance.md) as
synthetic fixtures created for Lathe and distributed under the repository's
Apache-2.0 license.

| File | Source (per asset-provenance.md) | License | Clearance status |
| ---- | -------------------------------- | ------- | ---------------- |
| `examples/refs/courier_front.png` | Synthetic courier-drone front view created for Lathe reconstruction examples; no embedded metadata. | Apache-2.0 (with the repo). | Self-authored fixture. `requires-human: confirm provenance once counsel reviews the asset-provenance attestation procedure.` |
| `examples/refs/courier_side.png`  | Synthetic courier-drone side view created for Lathe reconstruction examples; no embedded metadata. | Apache-2.0 (with the repo). | Self-authored fixture. `requires-human: confirm provenance.` |
| `examples/refs/materials.jpg`     | Synthetic material swatch used by reconstruction examples; JFIF metadata only. | Apache-2.0 (with the repo). | Self-authored fixture. `requires-human: confirm provenance.` |
| `examples/refs/source_block.obj`  | Minimal box mesh generated by the Trimesh example/export path. | Apache-2.0 fixture; Trimesh remains a runtime dep with its own MIT license. | Self-authored fixture. `requires-human: confirm provenance.` |

`docs/gallery/` is not present in the working tree and is not tracked by git
(zero results from `git ls-files docs/gallery/`). If gallery images are added
later, each must be added to `docs/release/asset-provenance.md` with source,
license, and clearance status in the same change.

### Per-file provenance attestation

[docs/release/asset-provenance.md](../release/asset-provenance.md) exists and
covers the four `examples/refs/` files plus
`tests/fixtures/codex_imagegen_samples/placeholder.png`.
`requires-human: counsel review of the attestation procedure (self-authored
synthetic fixtures vs. third-party media) before any public claim of full IP
clearance.`

## Open-source license compatibility

Read from `pyproject.toml` (not guessed). Apache-2.0 (the repository license)
is compatible with all of the following:

### Required runtime dependencies (`[project.dependencies]`)

| Dependency | License signal | Compatible with Apache-2.0 |
| ---------- | -------------- | -------------------------- |
| `lark>=1.1` | MIT | Yes |
| `jsonschema>=4.0` | MIT | Yes |
| `numpy>=1.26` | BSD-3 (composite SPDX) | Yes |
| `Pillow>=10.0` | HPND / MIT-CMU | Yes |
| `trimesh>=4.0` | MIT | Yes |

### Optional extras (`[project.optional-dependencies]`)

| Extra | Dependency | License signal | Compatible with Apache-2.0 |
| ----- | ---------- | -------------- | -------------------------- |
| `vggt` | `torch>=2.11.0` | BSD-3 | Yes |
| `vggt` | `torchvision>=0.26.0` | BSD-3 | Yes |
| `xatlas` | `xatlas>=0.0.11` | MIT | Yes |
| `geometry` | `scikit-image>=0.25` | BSD-3 | Yes |
| `geometry` | `manifold3d>=2.5` | Apache-2.0 | Yes |
| `export` | `scipy>=1.16` | BSD-3 | Yes |
| `publish` | `cryptography>=43` | Apache-2.0 / BSD-3 dual | Yes |
| `publish` | `boto3>=1.34` | Apache-2.0 | Yes |

`requires-human: SBOM-driven license review at release time. The release
SBOM workflow (referenced in SECURITY.md) is the authoritative input for
transitive license review; this table only covers direct declared
dependencies in pyproject.toml.`

## Editor addon license compatibility (Godot)

Godot itself is MIT-licensed. An addon under MIT or Apache-2.0 is compatible
both with the addon's host (Godot) and with the Lathe repository.

The Godot addon ships at `editors/godot/lathe-addon/`, but **no LICENSE or
LICENSE.txt file is present in that directory** as of 2026-04-28. Per the
repository LICENSE at the repo root, the addon source is covered by the
repo-wide Apache-2.0 grant; however, distributing the addon as a standalone
Godot AssetLib entry typically expects a license file within the addon
directory.

`requires-human: add an Apache-2.0 LICENSE file (or a one-line LICENSE that
inherits from the repo root) inside editors/godot/lathe-addon/ before
publishing the addon to the Godot AssetLib, and confirm that the chosen
license is compatible with how Godot AssetLib expects addon licensing to be
declared.`

## Blender GPL boundary

Blender is GPLv3 software. Lathe invokes Blender as a separate operating-system
subprocess via the topology backend `lathe.topology.blender_hard_surface_v1`
and the Codex bridge planner (`lathe/bridge/blender_plan.py`). Lathe does not
link Blender code into its own address space, does not redistribute Blender
binaries or sources, and does not embed Blender Python modules.

Reasoning: under widely held interpretations of the GPL (including the FSF's
own published guidance on subprocesses with arms-length data exchange), a
separate-process invocation across a process boundary, with structured input
and output, does not produce a derivative work of the invoked program. On
that basis, Lathe's Apache-2.0 license is not affected by Blender's GPL, and
Blender remains a user-installed optional dependency rather than a
redistributed component.

`requires-human: counsel must concur with this subprocess-boundary reasoning
before any "no GPL impact" claim is made publicly. The reasoning above is the
maintainer's good-faith engineering judgement and is not legal advice.`

## Provider terms review

| Provider | Role in Lathe | Status in v0.2.0rc1 | Review item |
| -------- | ------------- | ------------------- | ----------- |
| Hunyuan3D-2.1 | Optional shape provider via `lathe.provider.shape.hunyuan2_1_http_v1` | Mentioned only as a user-configured optional integration. | `requires-human: review current Hunyuan3D-2.1 license and terms before any public reference in marketing docs.` |
| VGGT (Meta) | Optional multiview-reconstruction provider via `lathe.provider.shape.vggt_local_v1` | Mentioned only as a user-configured optional integration. | `requires-human: VGGT ships under a Meta custom research license with non-commercial restrictions; restrict any commercial-use claims accordingly and re-read terms before public launch.` |
| Codex ImageGen | Optional governed surface backend (V1.2 layer). | Documented as a governed backend with explicit fallback. | `requires-human: confirm OpenAI/Codex provider terms before any public claim that Lathe runs ImageGen on the user's behalf.` |

For v0.2.0rc1, public docs may continue to describe these as **optional**
integrations a user configures themselves; Lathe ships no API keys, no proxy
endpoints, and no built-in default provider that calls a third-party service.

## Last reviewed

- Date: 2026-04-28
- Reviewer: Tal Merri (solo maintainer, self-assessment)
- Counsel review: `requires-human: not yet engaged.`
