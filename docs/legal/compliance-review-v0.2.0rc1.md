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

### Other tracked binary / third-party-named fixtures (Phase 2 P0 expansion)

The Phase 2 P0 verification pass also enumerated benchmark fixtures and the
Godot addon LICENSE. Each row is now also tracked in
[docs/release/asset-provenance.md](../release/asset-provenance.md):

- `lathe/benchmarks/catalog.json` — hand-authored Lathe-only catalog; no
  third-party content.
- `lathe/benchmarks/legacy_outputs/legacy_brassbound_chest_v02.json`,
  `lathe/benchmarks/legacy_outputs/legacy_courier_drone_v02.json` —
  snapshots of Lathe's own previous (V0.2-era) legacy-failure outputs,
  generated by the Lathe compiler and retained as regression markers.
- `docs/benchmarks/data/*.json` — reserved competitor-comparison JSON
  files (`result: "not_run"`). They name upstream systems (Hunyuan, Luma,
  Meshy, Quixel, Houdini, Blender) as identifiers but do not redistribute
  any third-party output, model weights, or generated meshes.
  `requires-human: before any benchmark publication that includes real
  competitor metrics, review provider terms for restrictions on benchmark
  publication and side-by-side comparison.`
- `docs/benchmarks/competitors/*.md` — Lathe-authored documentation only.
- `editors/godot/lathe-addon/LICENSE` — Apache-2.0 addon license file added in this pass.

### Per-file provenance attestation

[docs/release/asset-provenance.md](../release/asset-provenance.md) exists and
covers the four `examples/refs/` files,
`tests/fixtures/codex_imagegen_samples/placeholder.png`, the Lathe
benchmark fixtures listed above, and the new addon license file.
`requires-human: counsel review of the attestation procedure (self-authored
synthetic fixtures vs. third-party media, including Lathe's own legacy
outputs and the reserved competitor JSON files) before any public claim
of full IP clearance.`

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

### License round-trip status (Phase 2 P0 pass)

The Phase 2 verification pass attempted to confirm the upstream licenses
listed above with `pip show`. As of 2026-04-28 there is no `.venv` directory
in the worktree, so the per-package license signals could not be confirmed
in this pass. `requires-human: at release-pin time, run `pip show <pkg> |
grep -i license` for each runtime dep (lark, jsonschema, numpy, Pillow,
trimesh) and each optional dep (torch, torchvision, xatlas, scikit-image,
manifold3d, scipy, cryptography, boto3) and update this table to record the
exact License-expression each upstream publishes. The SBOM workflow is the
authoritative cross-check.`

## Editor addon license compatibility (Godot)

Godot itself is MIT-licensed. An addon under MIT or Apache-2.0 is compatible
both with the addon's host (Godot) and with the Lathe repository.

The Godot addon ships at `editors/godot/lathe-addon/`. As of the Phase 2
verification pass on 2026-04-28, an Apache-2.0 `LICENSE` file has been added
at `editors/godot/lathe-addon/LICENSE` that points to the repo-root LICENSE
and reproduces the standard Apache-2.0 boilerplate header. This satisfies
the typical Godot AssetLib expectation that an addon directory carries a
visible license file independent of the parent repository.

`requires-human: confirm that the Godot AssetLib publication path accepts an
Apache-2.0 addon license (vs. a strict MIT preference) before any AssetLib
listing is submitted. Recorded as a follow-up in Phase 16 of the readiness
task list.`

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

### Provider terms pointers and pre-publication wording

For each optional provider, the upstream license / terms page must be
re-read at publication time and the wording in any docs that mention the
integration must be aligned. URLs below are starting points; counsel must
confirm they resolve to the current canonical license at launch time.

- **Hunyuan3D-2.1.**
  - License/terms entry: upstream model card and repo on Hugging Face / GitHub.
    Starting point: `https://github.com/Tencent/Hunyuan3D-2.1` (model card on
    Hugging Face is the authoritative license source). `requires-human: confirm
    current canonical license URL before any public reference; the upstream
    model has shipped under multiple license texts and the canonical URL has
    moved between Hugging Face and GitHub at different points.`
  - Recommended pre-publication wording: "Lathe ships an HTTP client for the
    upstream Hunyuan3D-2.1 server. Lathe does not redistribute model weights,
    model code, or trained outputs. Users who configure a Hunyuan endpoint via
    `--runtime-config` are responsible for complying with the Hunyuan3D
    upstream license; refer to the Hunyuan3D-2.1 model card for the current
    license text."

- **VGGT (Meta).**
  - License/terms entry: `https://github.com/facebookresearch/vggt`
    (LICENSE.txt in the repo). `requires-human: re-read at publication time;
    Meta's research-license family has historically included
    non-commercial-use clauses that materially affect downstream claims.`
  - Recommended pre-publication wording: "Lathe provides an optional
    deterministic-meshing wrapper around the official VGGT package.
    Lathe does not redistribute VGGT code or model weights. VGGT is published
    under Meta's research license; users who choose to install and run VGGT
    locally are responsible for complying with that license, which historically
    has included non-commercial-use restrictions. Verify the upstream LICENSE
    file before any commercial use of Lathe in combination with VGGT."

- **Codex ImageGen (OpenAI).**
  - License/terms entry: OpenAI's API terms of use and usage policies pages
    at `https://openai.com/policies/`. `requires-human: confirm the exact
    current URLs for "Terms of use" / "Sharing & publication policy" /
    "Usage policies" at publication time; OpenAI rotates these URLs.`
  - Recommended pre-publication wording: "Lathe optionally invokes Codex
    ImageGen as a governed surface backend. Lathe does not ship OpenAI API
    keys or proxy traffic; users supply their own credentials via
    `--runtime-config`. Use of OpenAI services is governed by OpenAI's terms
    and usage policies. Lathe always emits a deterministic fallback when the
    governed backend is unavailable, so disabling the integration never
    blocks a build."

## SECURITY.md verification (Phase 2 P0 pass)

- **Contact line.** `SECURITY.md:18-21` lists `talmerri@gmail.com` with the
  `[SECURITY]` subject prefix. Confirmed current as of 2026-04-28.
- **PGP key.** `SECURITY.md:21` states `A PGP key fingerprint will be
  published here once generated.` `requires-human: generate a maintainer PGP
key, publish the fingerprint in SECURITY.md, and rotate the temporary
  text — OR record an approved release exception that PGP is intentionally
  not provided for v0.2.0rc1 because the alternative GHSA channel covers
  coordinated disclosure for the supported personas. Tal Merri (@talmerri)
  is the named owner; backup owner pending per RISK-015.`
- **GitHub Security Advisories (GHSA).** `SECURITY.md:18-19` says the
  preferred channel is GHSA "once the repo is public". `requires-human:
  confirm GHSA is enabled on the public GitHub repository after the
  worktree branch is pushed and the repo's public-visibility flip is
  recorded. The exact verification command (run from a host with a
  `gh`-authenticated session that has admin access to the repo) is:
  `gh api repos/talmerri/lathe --jq '.security_and_analysis.private_vulnerability_reporting.status'`
  — this should return "enabled". An alternative manual confirmation is
  loading https://github.com/talmerri/lathe/security and confirming that
  "Report a vulnerability" is visible to logged-in non-admin users. Do not
  run the gh api command from this verification pass; the lead should run
  it after push.`
- **Safe-harbor language.** `SECURITY.md:38-46` documents safe harbor for
  good-faith research, with bounded scope (no user-data compromise, no
  premature public disclosure, work only against own environment).
  `requires-human: counsel review of the safe-harbor language before any
  public bug-bounty or research-incentive claim. Recorded in the launch
  blocker list.`

## Blender GPL boundary verification

The compliance review's Blender boundary section above relies on Lathe
invoking Blender as a separate operating-system subprocess rather than
linking Blender Python modules in-process. The Phase 2 verification pass
confirmed this concretely:

- **No in-process `bpy` import in `lathe/`.** A repository-wide grep for
  `import bpy` and `from bpy` over the `lathe/` package returned zero
  matches. Blender's Python module is never imported by the Lathe runtime.
- **Subprocess invocation site.** Topology stage code lives in
  `lathe/core/stages/topology.py:19` (`import subprocess`) and the actual
  Blender invocation is delegated to
  `lathe.sandbox.blender.run_blender_sandboxed`. The sandbox helper itself
  uses `subprocess.run`/`subprocess.Popen` (`lathe/subproc.py:204`,
  `lathe/subproc.py:225`, `lathe/subproc.py:247`, with the
  Blender-specific path documented at `lathe/sandbox/blender.py:1-103,
  lathe/sandbox/blender.py:240,272`). Invocation happens through a child
  process with structured input/output (input/output GLB paths plus a
  separate adapter script under `scripts/blender_topology_adapter.py`).
- **Codex Blender bridge.** The Codex bridge planner
  (`lathe/bridge/blender_plan.py`) generates a plan; execution is layered
  through `lathe/blender/execution.py`, which also routes through
  `run_blender_sandboxed` (`lathe/blender/drivers.py:12,47-77`). No
  in-process Blender import.
- **Topology adapter runtime selection.** `lathe/adapters/blender_subdiv.py`
  contains a single comment at line 73 noting that the Blender subprocess
  module is imported lazily; this is a reference to the in-tree subprocess
  helper, not to `bpy`.

Conclusion: the subprocess-boundary reasoning in the GPL section above is
consistent with the actual code. `requires-human: counsel must still concur
with this engineering judgement before any public "no GPL impact" claim,
but the engineering substrate is verified and not at risk of an in-process
`bpy` import slipping in unreviewed.`

## Last reviewed

- Date: 2026-04-28
- Reviewer: Tal Merri (solo maintainer, self-assessment)
- Counsel review: `requires-human: not yet engaged.`
