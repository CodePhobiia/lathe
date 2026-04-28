# Security Review Scope — Lathe v0.2.0rc1

> Phase 9 P0. Self-assessment. Reviewer: Tal Merri (@talmerri).
> Date: 2026-04-28.
>
> This document scopes the third-party security review that **must**
> precede v0.2.0 final or any GA discussion. For v0.2.0rc1 (this
> pre-release), no third-party review is performed; the in-tree
> threat-model + scanner-based gates are the v0.2.0rc1 baseline. See
> the `EXC-PHASE9-PENTEST-001` exception recorded in
> `docs/release/decision-log-v0.2.0rc1.md`.

## Decision

- **Third-party security review for v0.2.0rc1: `requires-human`** —
  not performed for this pre-release.
- **Release exception: `EXC-PHASE9-PENTEST-001`** — recorded in the
  decision log. Scope: "no third-party pen-test for pre-release
  v0.2.0rc1; in-tree threat-model + scanner-based gates are the
  v0.2.0rc1 baseline; pen-test required before v0.2.0 final or any GA
  discussion".
- **Public-launch gate: any CVSS ≥ 7.0 (P0/P1) finding from a future
  security review must be fixed before public launch.** Lower-severity
  findings (CVSS < 7.0) may ship to launch with a recorded mitigation
  + removal target, but every finding MUST be triaged and either fixed
  or recorded as a tracked exception in
  `docs/release/decision-log-v0.2.0rc1.md` (or its successor).

## Items the review must cover

For each in-scope component below, the review should evaluate:

- **Attacker-controlled inputs.** What can the attacker (a hostile
  `.lth` source author, a hostile `runtime_config.json`, a compromised
  provider response, a hostile mesh/image file, …) feed into this
  surface?
- **Trust boundary.** Where does data cross from untrusted to
  semi-trusted to trusted? What invariants must hold across that
  boundary?
- **Existing test coverage.** What tests cite this surface today? Is the
  coverage symbolic (existence + intent) or behavioral (poisoned-input
  assertions)?
- **External-review focus.** What should an external reviewer try first?

### 1. `.lth` parser

**Files / paths**

- `lathe/parser/__init__.py`
- `lathe/parser/fast_parser.py`
- `lathe/parser/fast_parser_expr.py`
- `lathe/parser/grammar.py`
- `lathe/parser/imports.py`
- `lathe/parser/prompt_injection.py`
- `lathe/parser/tokens.py`
- `lathe/parser/transformer.py`
- `lathe/parser/transformer_blocks.py`
- `lathe/parser/transformer_expr.py`
- `grammar/lathe.lark`
- `schema/lathe.schema.json`

**Attacker controls:** the entire `.lth` source byte stream (a developer
may `git clone` a third-party `.lth` source repo). Including: deeply
nested grammar constructs, identifier shadowing of stdlib paths,
oversized literals, suspicious imports, embedded prompt-injection
strings.

**Boundary:** `lathe.parser.parse_file` / `lathe.parser.parse_text`
declare untrusted-input policies via `lathe.security.ingress_boundary`.
Required controls: UTF-8 decode, byte/token/import budgets,
prompt-injection scan, declarative grammar parse, safe import-path
resolution. See `docs/security/threat_model.md` "Enforceable ingress
policy" table.

**Existing test coverage:**

- `tests/fuzz/test_parser_fuzz.py`, `tests/fuzz/test_ingress_fuzz.py`.
- `tests/property/test_resolver_properties.py`,
  `tests/property/test_shape_ir_properties.py`,
  `tests/property/test_geometry_kernel_properties.py`,
  `tests/property/test_feature_grammar_properties.py`,
  `tests/property/test_exact_solids_properties.py`,
  `tests/property/test_normalizer_properties.py`.
- `tests/unit/test_trust_boundaries.py` enforces that the untrusted
  ingress policies remain attached to the parser entry points.

**External review focus:**

- Recursion / depth caps on `_FastParser` (currently tracked as
  `SEC-FUTURE-2`). Fuzz with deeply nested expressions.
- Import shadowing: can a hostile source convince the resolver that a
  user-authored module is `std/...`?
- Prompt injection inside string literals. Validate the static scanner
  (`lathe/parser/prompt_injection.py`) actually catches realistic
  injection patterns, not just toy examples.

### 2. Runtime config loader

**Files / paths**

- `lathe/runtime_config.py`

**Attacker controls:** a `runtime_config.json` checked into a hostile
repo. The attacker can set arbitrary keys (filtered by the JSON-schema),
a `signing_key` path, provider URLs, output paths.

**Boundary:** `lathe.runtime_config.load_runtime_config` (cited at
`lathe/runtime_config.py:165` in the threat model). Required controls:
byte cap, UTF-8 decode, JSON parse, object root, JSON schema
validation. Subprocess env scrub
(`lathe/subproc.py::_FORBIDDEN_ENV_KEYS`) rejects `LD_PRELOAD` /
`PYTHONPATH` even if `extra_env` lists them.

**Existing test coverage:**

- `docs/security/json_ingress_audit.md` documents the JSON-ingress
  hardening.
- Unit tests under `tests/unit/` that exercise the runtime-config
  loader (search for `runtime_config` usages).

**External review focus:**

- Schema-bypass: can a hostile config slip a key past the JSON-schema
  validation?
- Path-traversal in the `signing_key` / `output_dir` fields.
- Provider URL spoofing — is the `url_allowlist` check applied
  consistently across `safe_urlopen` callers?

### 3. Provider HTTP client

**Files / paths**

- `lathe/net.py` (the `safe_urlopen` host-allowlist + safety-cap
  implementation).
- `lathe/providers/transport/http.py` (the Hunyuan-flavored thin
  wrapper with retry/backoff; SEC-NEW-1).
- `lathe/providers/adapters/hunyuan.py`,
  `lathe/providers/adapters/vggt.py`,
  `lathe/providers/adapters/reference_conditioned.py`.
- `lathe/providers/registry.py`,
  `lathe/providers/selection.py`,
  `lathe/providers/errors.py`.

**Attacker controls:** a malicious provider response body (the operator
points the runtime config at an attacker-controlled host on the
allowlist), including oversized bodies, mismatched content-types,
hostile redirects, slow-loris hangs.

**Boundary:** `lathe.net.safe_urlopen`. Controls: scheme allowlist,
host allowlist (private IP rejection, redirect blocking, TLS
verification, timeout cap, body-size cap, content-type check). Wrapper
adds retry/backoff with bounded attempts.

**Existing test coverage:**

- Schema validation on responses (`hunyuan_probe.schema.json`) per
  threat-model row "Tampering" in the provider-HTTP section.
- Unit tests under `tests/unit/` for `safe_urlopen` (search for
  `safe_urlopen` usages).

**External review focus:**

- DNS rebinding: even with host allowlist, can an attacker rebind a
  hostname to an internal IP between resolution and connect?
- Redirect handling: does `safe_urlopen` re-check the host allowlist on
  every redirect, or only on the initial request?
- Content-type sniff vs. declared type — can a malicious server
  smuggle one type past a `expect_content_type=None` check?

### 4. Path / output safety

**Files / paths**

- `lathe/cli/build_cmd.py` — applies the output path safety check.
- `lathe/paths.py::safe_resolve` — the underlying path-traversal
  guard (SEC-1).
- The `LATHE_ALLOW_EXTERNAL_OUT` env var is the operator override
  (default `0` = inside repo only) — see `.env.example:39-43`.

**Attacker controls:** a hostile `--out` path argument or a hostile
field in the `runtime_config.json` that resolves to `..` traversal,
symlink-redirected output, or a UNC/network path.

**Boundary:** `safe_resolve` enforces a canonical-root containment
check; symlink resolution is rejected on POSIX and traversal beyond the
declared root is refused.

**Existing test coverage:**

- Unit tests under `tests/unit/` exercising `safe_resolve`.

**External review focus:**

- Windows-specific path quirks: case-insensitivity, ADS streams, UNC
  paths, the `\\?\` long-path prefix, and reserved device names
  (CON, NUL, AUX, …) — Lathe is Windows-first per `CLAUDE.md`.
- Output-path safety when the user sets `LATHE_ALLOW_EXTERNAL_OUT=1` —
  is there any residual safety net, or does the operator take full
  responsibility?
- The `lathe/cli/output_safety.py` module referenced in older drafts of
  the doc no longer exists; the safety check is inline in
  `lathe/cli/build_cmd.py`. Confirm there is no second copy of the
  check that could drift.

### 5. Mesh / image ingest

**Files / paths**

- `lathe/mesh_ingest.py` — `safe_load_mesh` (SEC-2). Format allowlist,
  byte cap, magic-byte sniff, post-load mesh sanity checks.
- `lathe/providers/mesh_ops.py` — mesh-handling helpers.
- (Note: the historical `lathe/parser/binary.py` location was retired
  during the parser package split; the controls were preserved in
  `lathe/mesh_ingest.py`. The threat-model document was corrected to
  match — see `docs/security/threat_model.md` "Document path-fix log".)

**Attacker controls:** a hostile mesh file referenced from a `.lth`
source. Including: a binary-format mismatch (e.g. STL prefix on a GLB
body), a billion-vertices-on-paper file with a small declared body,
images that decompression-bomb, and crafted asset files exploiting
trimesh / Pillow CVEs.

**Boundary:** `safe_load_mesh` (cited in threat-model
"Enforceable ingress policy" table). Format allowlist, byte cap, magic
sniff, post-load sanity checks.

**Existing test coverage:**

- Unit tests under `tests/unit/` covering mesh ingest.
- pip-audit findings on `Pillow`, `trimesh`, `lxml` are in
  `docs/release/evidence-bundle-v0.2.0rc1/pip-audit-runtime.txt`.

**External review focus:**

- Decompression-bomb resilience — what is the largest pixel/triangle
  count the loader will accept, and is the cap enforced before
  decoding?
- Magic-byte sniff bypass — can an attacker construct a file that
  passes the magic check for one format but is parsed as another?
- Pillow CVE exposure — what versions of Pillow / lxml are pinned, and
  are there known image-format CVEs in those versions?
  (`pip-audit-runtime.txt` covers this for the snapshot moment;
  ongoing surveillance is via Dependabot + pip-audit CI.)

### 6. Blender subprocess sandbox

**Files / paths**

- `lathe/sandbox/__init__.py` — public sandbox surface.
- `lathe/sandbox/blender.py` — Blender-specific sandbox (SEC-7).
- `lathe/subproc.py` — base subprocess wrapper with env scrubbing
  (`_FORBIDDEN_ENV_KEYS`) and stderr scanning.
- `docs/security/blender_sandbox.md` — platform-specific behavior +
  known limits.

**Attacker controls:** a hostile `.blend` file, a hostile Python
snippet declared in the execution plan, or a hostile Blender add-on
path. Less directly, manipulation of `$PATH` or the Blender resolver.

**Boundary:** `run_blender_sandboxed` runs Blender with
`--factory-startup`, env scrubbed to allowlist, CPU + memory caps,
600s timeout, structured `BlenderSandboxResult`.

**Existing test coverage:**

- Phase 6 evidence: `docs/release/evidence-bundle-v0.2.0rc1/bandit.json`
  (bandit subprocess rules).
- Unit tests under `tests/unit/` for `lathe/sandbox/blender.py` and
  `lathe/subproc.py` (search for `run_blender_sandboxed`,
  `run_sandboxed`).

**External review focus:**

- Autoexec — currently default-allow with an opt-out
  (`safety_policy.allow_autoexec=false`). Open follow-up
  `SEC-FUTURE-4` proposes making it default-deny in CLI surface.
  Validate the current default does not surprise operators on
  malicious `.blend`s.
- Resource cap effectiveness on Windows — Linux cgroups are
  straightforward; Windows job-object semantics are different. Confirm
  the documented caps actually apply on the supported matrix.
- Path-allowlist for Blender file ops (tracked as
  `LATHE_BLENDER_ROOTS` / Plan 07 Phase 2 in `.env.example:56`,
  intentionally not yet wired).

### 7. Telemetry

**Files / paths**

- `lathe/telemetry.py` — opt-in build-ping emitter (Phase 2 verified
  15/15 PASS).
- `lathe/cli/telemetry_cmd.py` — `enable` / `disable` / `status` /
  `clear` subcommands.
- `lathe/cli/build_cmd.py` — single emit call site at the success
  branch.
- `docs/privacy.md` — user-facing privacy doc.
- `docs/telemetry_event_taxonomy.md` — payload allowlist documentation.

**Attacker controls:** a hostile build report fed into
`emit_build_ping`. Phase 2 verification covered the poisoned-build-report
case (`tests/unit/test_telemetry.py:201-264`); the seven-key allowlist
is preserved.

**Boundary:** `_build_payload` returns exactly seven keys
(`lathe/telemetry.py:251-259`); HTTPS-only ingest with host pinning
(`lathe/telemetry.py:280-289`).

**Existing test coverage:** see
`docs/release/telemetry-verification-v0.2.0rc1.md` for the 15/15 PASS
matrix and the cited test rows.

**External review focus:**

- Local file write semantics: the `clear` subcommand
  (`lathe/cli/telemetry_cmd.py:74-82`) deletes the config file. Are
  there race conditions with a concurrently-running build that has
  already cached the salt?
- HTTPS pinning: confirm telemetry never falls back to HTTP and never
  follows a redirect off the allowlist.
- Persistent salt: a single host's `user_salt` is stable across
  enable/disable cycles. Confirm this is communicated correctly in
  `docs/privacy.md` and that counsel review can sign off.

### 8. Publish drivers

**Files / paths**

- `lathe/publish/__init__.py`
- `lathe/publish/signed_repro.py` — signed reproducibility receipts
  (SEC-NEW-2).

**Attacker controls:** the `runtime_config.publish` block (target type,
target URL, bucket, signing key). On the receiving side: a malicious
S3 / Supabase / git-lfs server that accepts uploads or returns crafted
responses.

**Boundary:** ed25519 manifest + receipt. Per-artifact sha256 list.
Public key recorded in the build report. Drivers never copy the signing
key into the target dir.

**Existing test coverage:**

- Unit tests under `tests/unit/` for `signed_repro.py` (search for
  `signed_repro` usages).
- `lathe/publish/__init__.py` is a single module and a re-export
  point; the actual driver implementations may live elsewhere — the
  reviewer should `grep -R "publish_driver"` to map current drivers.

**External review focus:**

- Forge-resistance: can an attacker forge a receipt by replacing the
  public key + re-signing with their own private key? The receipt
  format MUST bind the receipt to a publicly-known public key (e.g.
  via a sigstore-style transparency log) for this to be tamper-evident
  at scale. v0.2.0rc1 does NOT have a transparency log integration;
  this is the kind of finding that an external review should flag and
  that maps to `EXC-PHASE3-SIGN-001`.
- Driver allowlist (tracked as `SEC-FUTURE-7` in the threat model) —
  v0.2.0rc1 does not require runtime_config publish targets to be on a
  global allowlist. A hostile config can point at any S3 bucket /
  Supabase project / git-lfs URL.

## What this review is NOT

- It is not a code review of the entire codebase. The scope above is
  the security-relevant surface; everything else is in-scope only if
  it is demonstrably reachable from one of the listed attacker-control
  surfaces.
- It is not a license / compliance review. Those live in
  `docs/legal/compliance-review-v0.2.0rc1.md`.
- It is not a privacy review. That lives in
  `docs/privacy.md` + `docs/release/telemetry-verification-v0.2.0rc1.md`.

## Public-launch gate (re-stated)

- **Any CVSS ≥ 7.0 (P0/P1) finding from a future security review must
  be fixed before public launch.** No exception applies.
- Findings below CVSS 7.0 may ship to launch only if recorded as a
  tracked exception in `docs/release/decision-log-v0.2.0rc1.md` (or its
  successor for the launch version) with named owner, justification,
  workaround, and removal target.

## Cross-references

- [`docs/security/threat_model.md`](threat_model.md)
- [`docs/security/owasp-mapping-v0.2.0rc1.md`](owasp-mapping-v0.2.0rc1.md)
- [`docs/security/secret-hygiene-v0.2.0rc1.md`](secret-hygiene-v0.2.0rc1.md)
- [`docs/security/supply-chain-review-v0.2.0rc1.md`](supply-chain-review-v0.2.0rc1.md)
- [`docs/security/blender_sandbox.md`](blender_sandbox.md)
- [`docs/security/prompt_injection.md`](prompt_injection.md)
- [`docs/security/ci_gates.md`](ci_gates.md)
- [`docs/security/json_ingress_audit.md`](json_ingress_audit.md)
- [`docs/release/decision-log-v0.2.0rc1.md`](../release/decision-log-v0.2.0rc1.md)

## Sign-off
- Reviewed: 2026-04-28
- Reviewer: Tal Merri (self-assessment, solo maintainer)
- Counsel review: requires-human
- Next review: 2026-05-28 or T+30 post-launch (whichever later)
