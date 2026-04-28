# Support Readiness Checklist — v0.2.0rc1

## Status

Support readiness checklist for v0.2.0rc1. Solo maintainer (Tal Merri /
@talmerri); backups for launch-day primary, security primary, PyPI
release authority, GitHub release authority, and community moderation
are all `requires-human` per `docs/ops/on-call.md`. This file describes
the support intake surface (labels, templates, FAQ, macros, SLAs, and
escalation triggers) that must exist before any wider distribution.

## GitHub support intake labels

Labels are defined locally in `.github/labels.yml`. The remote-state
column requires an authenticated `gh` call to verify against
`talmerri/lathe`.

| Label | Purpose | Exists locally? | Exists remotely? |
|---|---|---|---|
| `release-blocker` | Must be fixed or explicitly excepted before a release. | yes (`labels.yml:51`) | `requires-human: gh label list --repo talmerri/lathe --limit 100` |
| `flaky-test` | Test is nondeterministic or environment-sensitive and needs triage. | yes (`labels.yml:54`) | `requires-human: gh label list --repo talmerri/lathe --limit 100` |
| `security` | Security vulnerability or hardening. | yes (`labels.yml:48`) | `requires-human: gh label list --repo talmerri/lathe --limit 100` |
| `bug` | Something is broken. | yes (`labels.yml:3`) | `requires-human: gh label list --repo talmerri/lathe --limit 100` |
| `enhancement` | New feature or capability request. | yes (`labels.yml:6`) | `requires-human: gh label list --repo talmerri/lathe --limit 100` |
| `question` | User question or design discussion. | **no — not in `.github/labels.yml`** | `requires-human: add to labels.yml then gh label sync` |
| `docs` | Documentation or spec changes. | yes (`labels.yml:36`) | `requires-human: gh label list --repo talmerri/lathe --limit 100` |
| `release-exception` | Accepted release exception with recorded owner/date/impact/workaround/removal-target. | **no — not in `.github/labels.yml`** | `requires-human: add to labels.yml then gh label sync` |

To verify the remote set against this table, run with an authenticated
`gh` CLI:

```bash
gh label list --repo talmerri/lathe --limit 100
```

To re-sync the canonical set from `.github/labels.yml` after adding
the two missing labels (`question`, `release-exception`):

```bash
npx github-label-sync --access-token "$GH_TOKEN" --labels .github/labels.yml talmerri/lathe
```

## Issue templates

Templates live under `.github/ISSUE_TEMPLATE/`. Each must render on
GitHub before the repo accepts external traffic.

| Template | Purpose | Required fields present? | Renders on GitHub? |
|---|---|---|---|
| `bug_report.yml` | Report a misbehavior in compiler / runtime / validator / CLI. | yes — `lathe-version`, `os`, `python-version`, `lth-source`, `doctor`, `stage`, `expected`, `actual` are all `required: true`. | `requires-human: GitHub render check` |
| `feature_request.yml` | Propose a new capability, backend, or language surface. | yes — `motivation`, `proposal`, `stage` are `required: true`. Public-surface and backend-ID checkboxes present. | `requires-human: GitHub render check` |
| `lth_authoring_help.yml` | Ask for help writing or certifying a `.lth` source. | yes — `lth-source`, `expected`, `actual`, `validator` are all `required: true`. | `requires-human: GitHub render check` |
| `release_blocker.yml` | Report a defect or missing gate that should block a release. | partial — `target-release`, `blocked-gate`, `evidence`, `proposed-resolution` are required. **Missing required fields: severity (P0/P1/P2/P3), owner, rollback-or-exception decision.** See section below. | `requires-human: GitHub render check` |
| `config.yml` | Issue-template chooser config (disables blank issues, links to Discussions). | n/a (chooser, not a template). | `requires-human: GitHub render check` |

## release-blocker template requirements

`.github/ISSUE_TEMPLATE/release_blocker.yml` currently captures
target-release, blocked-gate, evidence, and proposed-resolution. The
release-readiness checklist requires three additional **required**
fields so every blocker has the data needed to triage in <5 minutes:

1. **Severity** — `dropdown`, options `P0`, `P1`, `P2`, `P3`, mapped
   to the response-time targets below. `required: true`.
2. **Owner** — `input`, the GitHub handle accountable for resolution
   (default Tal Merri / @talmerri). `required: true`.
3. **Rollback or exception decision** — `dropdown`, options
   `fix before release`, `accept release exception`, `roll back`,
   `not yet decided`. `required: true`.

Each accepted release exception must additionally record (in the body or
in `docs/release/decision-log-v0.2.0rc1.md`): owner, date, affected
surface, user impact, workaround, and removal target. The template
should link to that policy explicitly.

## Top-20 FAQ

These are real one-paragraph answers, not placeholders. They derive
from `README.md`, `CLAUDE.md`, `docs/error_codes.md`, `SECURITY.md`,
`docs/telemetry.md`, `docs/godot_integration.md`, and the v0.2.0rc1
release notes.

### 1. What is Lathe? Is it production-ready?

Lathe is a declarative language and a reference compiler/runtime that
turns 3D-asset intent (a `.lth` source file) into certified production
asset packages (`usd`, `glb`, `gltf`, `obj`). The current release,
`0.2.0rc1`, is a **pre-release reference compiler scaffold**, not a
stable production compiler. The compiler has substantial tests and CI,
the hero hard-surface wedge produces real bake outputs, and the
contracts are stable — but features outside that wedge are intentionally
narrower, learned-provider integration is opt-in, and full release
promotion still depends on the remaining items in
`docs/release/release-checklist.md`. Treat it as alpha.

### 2. How do I install on Windows?

The recommended path is the bootstrap script from the repo root in
PowerShell:

```powershell
scripts/bootstrap_local.ps1 -Dev -Export
```

That creates `.venv`, upgrades pip tooling, runs `pip install -e ".[dev,export]"`,
and runs `lathe doctor`. After it finishes, your interpreter is
`.\.venv\Scripts\python.exe`. The minimal-runtime alternative is
`pip install -e .` (no extras), but that omits the test/dev tooling. If
you need `xatlas` on Windows you must also install Visual Studio Build
Tools with the Desktop C++ workload.

### 3. How do I install on macOS or Linux?

From the repo root in bash, zsh, or Git Bash:

```bash
scripts/bootstrap_local.sh --dev --export
```

That mirrors the Windows path but produces `.venv/bin/python`. Optional
extras (`docs`, `vggt`, `xatlas`, `publish`) are installed with
`pip install -e ".[name]"` after bootstrap. VGGT additionally requires
a manual source install of the upstream `vggt` package — see the
README "Manual VGGT source install" block.

### 4. How do I run my first build?

After bootstrap, the smoke loop is one command:

```bash
bash scripts/lathe_smoke.sh    # or scripts/lathe_smoke.ps1 on PowerShell
```

For a single asset end-to-end:

```bash
python -m lathe.cli build examples/courier_drone.lth courier_drone --out dist
```

The output lands in `dist/courier_drone/` with `package_manifest.json`,
`.glb`/`.gltf`/`.obj` artifacts, the certification report, and the trace
JSON. `lathe doctor` first if anything fails on a clean machine.

### 5. How do I tell if my build is certified?

Read `dist/<asset>/stages/validate/certification_bundle.json` (or
`--report json` on the build command). The bundle records per-validator
gate-passes and the aggregate score; `certified: true` plus a
non-failing gate set means it cleared the configured threshold. The
build CLI also exits with code `0` on success and code `1` when the
build ran but failed certification — see `docs/error_codes.md` for the
full exit-code contract.

### 6. What is the shape contract?

The stable shape-stage backend ID is `lathe.shape.intent_mesh_handoff_v1`.
It is the single probabilistic seam in the compiler — every other stage
(topology, UV, surface, validate, package) is deterministic. Under that
contract, Lathe runs a native assembly-first kernel and treats learned
providers (Hunyuan, VGGT) as **optional proposal sources**, not as the
product center. The contract is frozen; ADR 0001 governs any change to
its SHA. Do not rely on internal helpers around it changing in
lock-step with patch releases.

### 7. What does "fallback" mean in the trace?

When a learned provider, Blender, or xatlas is unavailable or fails a
quality gate, Lathe records both the **attempted** provider/adapter
and the **actual** path that produced the artifact. This is why a
build can certify against the stable contract even when an optional
backend is missing. Every fallback shows up in the trace under
`fallbacks: [...]` with `attempted`, `actual`, and `reason` fields. A
green build with a non-empty `fallbacks` list is honest, not silent.

### 8. Do I need Blender, xatlas, Hunyuan, or VGGT to use Lathe?

No. The default no-runtime-config build path is conservative and
self-reliant: shape uses the deterministic
`lathe.provider.shape.reference_conditioned_v1` provider, topology and
UV fall back to deterministic reference adapters, and the package stage
emits `usd`/`glb`/`gltf`/`obj`. Blender/xatlas adapters activate when
the binaries are present; learned providers (Hunyuan HTTP, VGGT local)
activate only when explicitly named in a runtime config. The hero
families (`brassbound_chest`, `industrial_crate`, `mechanical_door`,
`console_terminal`, V1.0 cabinet/pedestal/container/wall) default to
native-only.

### 9. What runtime config should I use?

For the default smoke-test ergonomics, no runtime config — Lathe stays
on the conservative path. For learned-provider work, point
`--runtime-config` at one of the shipped configs:
`examples/runtime_configs/hunyuan_http.json` for image-conditioned
generation against a Hunyuan3D-2.1 HTTP server,
`examples/runtime_configs/vggt_local.json` for multiview reconstruction
via the local VGGT Python package, or
`examples/runtime_configs/auto_learned.json` for the auto-routed
learned mux. Strict mode in those configs makes a missing provider
fail honestly rather than silently fall back.

### 10. Telemetry — is it on?

No. Telemetry is **disabled by default**. Nothing leaves your machine
unless you run `lathe telemetry enable`, which prompts for explicit
confirmation. When enabled, a single small JSON ping after a successful
build sends `lathe_version`, a salted-and-hashed `build_id_hash` (the
salt never leaves the machine), `build_kind`, `stack_id`, `certified`,
`exit_code`, and `wall_ms`. Disable with `lathe telemetry disable`,
purge local state with `lathe telemetry clear`. Full schema and
retention policy live in `docs/telemetry.md`.

### 11. How do I report a security issue?

Use GitHub Security Advisories — the **Report a vulnerability** button
on the repository's Security tab — once the repo is public, or email
`talmerri@gmail.com` with subject prefix `[SECURITY]`. Do not file a
public GitHub issue for a security report. Acknowledgement target is
3 business days, initial triage 10 business days, fix and advisory
within 90 days under coordinated disclosure. The full policy is in
`SECURITY.md`. Good-faith research against your own local environment
is authorized under the Safe Harbor section of that file.

### 12. How do I file a bug?

Open a GitHub issue using the `Bug report` template. Required fields:
Lathe version (`python -m lathe.cli --version`), OS, Python version,
the smallest `.lth` source that reproduces, full `lathe doctor` output,
the stage where the break occurs, expected behavior, actual behavior
with traceback. Bugs without a reproduction get auto-tagged
`needs-repro` and triage stalls until one is provided. For language
authoring questions where the file compiles but certifies wrong, use
the `.lth authoring help` template instead.

### 13. What platforms are supported?

Tier-1 supported during v0.2.0rc1 development: Windows 10/11, macOS
(Apple Silicon and Intel), Ubuntu 22.04+. Path conventions in the
repo are Windows-first (`.\.venv\Scripts\python.exe`) but POSIX paths
work via the bash and bootstrap scripts. Per-platform CI coverage for
the full pytest suite across all three OSes is still being filled in
(see `docs/release/test-report-v0.2.0rc1.md`); cross-platform smoke
runs cleanly today.

### 14. What Python versions are supported?

Python 3.11 and 3.12. Earlier versions are not tested and will likely
fail on type-annotation syntax used inside `lathe/`. The CI matrix
runs both versions on Ubuntu, with Windows and macOS legs filling in
per `readiness-tasks.md`. Use `python --version` before filing an
install or runtime bug — wrong-version reports are the most common
intake noise.

### 15. Is the Godot addon ready?

The Godot addon under `editors/godot/lathe-addon/` is a **manually
installed** component (copy into `<project>/addons/lathe-addon/`,
enable in Project Settings). It supports drag-drop import of
`.lathe_snapshot.json`, auto-thumbnails, the build-trace dock, and the
existing PASS/FAIL bottom panel. **It is not yet submitted to the
Godot AssetLib.** No AssetLib release is planned for v0.2.0rc1; treat
the addon as a development preview that requires manual install.
Manual smoke testing on macOS/Linux requires a human runner.

### 16. Is the API stable?

The public language surface (`profile`, `contract`, `critic`, `asset`,
`variant`) and the named build stages are treated as stable. The
shape contract `lathe.shape.intent_mesh_handoff_v1` and the named
backend IDs (`lathe.stack.hard_surface_game_asset_v1`, the `topology`,
`uv`, `package` IDs) are also stable. Internal Python imports
(`from lathe.executor import …`) are **not** stable across patch
releases. CLI exit codes are stable; CLI flags are mostly stable but
new flags are added each milestone. Any breaking change to the stable
surface ships through an ADR plus a migration note.

### 17. What is `lathe doctor`?

`lathe doctor` is the environment self-check. It reports the active
Python interpreter, Lathe version, presence/absence of optional
dependencies (Blender, xatlas, trimesh, scipy, torch, vggt), the
status of any registered shape providers, and whether the shipped
runtime configs probe successfully. Run it before filing any
install/runtime bug — the output is required by the bug-report
template. `lathe doctor --json` returns a machine-readable form,
useful for CI.

### 18. Why did my build fail certification?

Read the failure reason in `--report json` output or in
`stages/validate/certification_bundle.json`. Each validator
(`semantic_quality`, `visual_quality`, `flow_quality`,
`surface_quality`, `silhouette`) reports `passes: bool` and
contributing evidence. A build can fail because a single gate flipped
to `passes: false` (the certification rule is `min` across gates),
because the weighted score fell below threshold, or because an
upstream stage produced no usable artifact. The certification rules
are intentionally strict — weak / toy-like outputs fail by design. If
the failure is on a stage you intend to skip, look at runtime-config
overrides; if it's on a real failure, fix the upstream input.

### 19. How do I open the GLB output?

Drag the `dist/<asset>/<asset>.glb` file into any glTF viewer:
[gltf-viewer.donmccurdy.com](https://gltf-viewer.donmccurdy.com),
Blender (`File → Import → glTF 2.0`), Godot 4.x (drag into the
`FileSystem` dock — stock glTF importer), or Unreal/Unity via their
standard glTF import paths. For an in-repo preview without leaving the
terminal, `lathe inspect --view <build_dir>` opens a local trimesh
viewer when `trimesh` is installed.

### 20. How do I cite Lathe? Where is the changelog?

The changelog lives at `CHANGELOG.md` in the repo root. Each release
records added features, behavior changes, fixes, and known limitations.
For citation, point at the GitHub repo `talmerri/lathe`, include the
exact tag (`v0.2.0rc1` for the current pre-release), and reference the
shape contract ID and backend stack ID if your work depends on them.
A formal academic-citation block (BibTeX) is `requires-human: add when
a paper or formal release notes are written`.

## Support macros

Short markdown blocks (≤6 lines each) for routine intake responses.
Copy into a GitHub comment, fill in the placeholder, post.

### Macro: install failure

```
Thanks for the report. Two things will unblock triage fastest:
1. Run `python -m lathe.cli doctor` (or `python -m lathe.cli doctor --json`) and paste the full output.
2. Confirm Python version (`python --version`) — Lathe supports 3.11 and 3.12.
If the bootstrap script failed, please also paste the last 30 lines of its output. See README "Install" for the canonical bootstrap path.
```

### Macro: `lathe doctor` failure

```
The doctor failure usually means an optional adapter is missing or misconfigured. Lathe is designed to keep working without optional adapters; the conservative path uses deterministic reference providers. Please paste:
1. Your `lathe doctor --json` output.
2. The exact `lathe build`/`lathe check` command that fails.
3. Your runtime-config file (if any) under `--runtime-config`.
We will tell you whether your environment is missing something or whether this is a real bug.
```

### Macro: provider unavailable

```
Lathe treats learned providers (Hunyuan, VGGT) as optional proposal sources under the stable shape contract. If the provider you selected is unavailable, the trace records both the *attempted* and the *actual* path. Two checks:
1. Run `lathe probe-providers --runtime-config <your config>` to see what each provider reports.
2. If you intended strict mode, confirm `strict: true` is set in your runtime config so a missing provider fails honestly instead of silently falling back.
See `docs/telemetry.md` and `examples/runtime_configs/` for working examples.
```

### Macro: certification failure

```
Lathe certification gates are intentionally strict so weak outputs fail. To triage:
1. Open `<build_dir>/stages/validate/certification_bundle.json` and look for which gate has `passes: false`.
2. Look at the same validator's `evidence` field for the underlying metric.
3. If you used a learned provider, check `<build_dir>/trace.json` for `fallbacks: [...]` — a fallback can produce a weaker result than expected.
Reply with the bundle JSON and we can point at the upstream cause.
```

### Macro: Godot import failure

```
The Godot addon is a manually installed development preview (not on AssetLib). To triage import errors:
1. Confirm the addon is enabled: Project → Project Settings → Plugins → Lathe Integration → Enable.
2. Confirm the build directory is under `res://lathe_out/<asset>/` and contains `.lathe_snapshot.json` plus the `.glb`.
3. Paste the Godot editor console output and your Godot version.
Full setup walkthrough: `docs/godot_integration.md`.
```

### Macro: security / private reporting

```
Please do not file security reports as public issues. Use one of these channels:
1. GitHub Security Advisories — "Report a vulnerability" button on the repository Security tab (preferred once repo is public).
2. Email talmerri@gmail.com with subject prefix `[SECURITY]`.
We will acknowledge within 3 business days and follow the SLAs in SECURITY.md (10 business days triage, 90 days fix + advisory under coordinated disclosure). Good-faith research against your own local environment is authorized under the Safe Harbor section.
```

## Response time targets

These targets apply from the moment an issue or report is received.
They match `docs/ops/on-call.md` for launch-week SLAs and SECURITY.md
for security-specific timing.

| Priority | Acknowledgement | Resolution target | Comms cadence |
|---|---|---|---|
| **P0** — security, privacy/telemetry leak, broken install, certification path entirely broken | 24 h | 24 h fix or workaround | Every 24 h while open |
| **P1** — degraded feature, provider failure, regression in a hero family, blocking docs error | 24 h | 3 business days | On triage and on close |
| **P2** — non-blocking bug, cosmetic issue | Best-effort | Weekly review queue | On close |
| **P3** — tracked enhancement, "nice to have" | Best-effort | Monthly review queue | On close |

Security-specific SLAs from `SECURITY.md`: acknowledgement 3 business
days, triage 10 business days, fix + advisory 90 days from initial
report (coordinated-disclosure window). When a security report enters
P0 (known exploit path, RCE, supply-chain), the on-call.md launch-week
P0 ack target (24 h) supersedes the 3-business-day ack target.

## When a support issue escalates to a release blocker

A reported issue is automatically promoted to release-blocker (and a
`release-blocker` label is applied) when **any** of the following
triggers fires:

1. **Three or more independent reports of the same install failure**
   on the same OS + Python combination. Trigger applies even when each
   individual report is P1; volume itself is the blocker signal.
2. **Any reproducible security issue** with a known exploit path, even
   from a single reporter. SECURITY.md and `docs/release/rollback-plan-v0.2.0rc1.md`
   then govern next steps (yank decision, GHSA, banner).
3. **Any reproducible privacy or telemetry leak** — e.g. telemetry
   sending more fields than `docs/telemetry.md` documents, or
   telemetry running while opt-in is disabled. Single reproducible
   report is sufficient.
4. **Any "certification passes but engine import is broken" report.**
   The certification gate's job is to prevent that exact failure mode;
   one reproducible case is a contract violation, not a normal bug.
5. **Any regression to a hero-family example** (`brassbound_chest`,
   `industrial_crate`, `mechanical_door`, `console_terminal`,
   `sci_fi_wall_panel`, `service_cabinet`, `control_pedestal`,
   `supply_container`) on a stock-config build. The hero wedge is the
   product floor; a regression there is a blocker until fixed or
   formally excepted.

When promotion fires, the issue is moved to the `release-blocker`
template (or re-tagged) and the maintainer evaluates yank under
`docs/release/rollback-plan-v0.2.0rc1.md`. The decision and evidence
are recorded in `docs/release/decision-log-v0.2.0rc1.md`.
