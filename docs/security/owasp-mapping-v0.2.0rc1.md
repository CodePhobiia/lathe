# OWASP Top 10 (2021) Mapping — Lathe v0.2.0rc1

> Phase 9 P0. Self-assessment. Reviewer: Tal Merri (@talmerri).
> Date: 2026-04-28.

This document maps the OWASP Top 10 2021 categories against Lathe's
v0.2.0rc1 attack surface. Lathe in v0.2.0rc1 is a **local CLI compiler**:
no hosted service, no auth surface, no account system, no session, no
hosted registry. Telemetry is opt-in and disabled by default
(`docs/release/telemetry-verification-v0.2.0rc1.md`, 15/15 PASS).

For each category we record:

- **Applicability.** What does this category mean for a local CLI compiler?
- **Status.** Applies / not applicable (with cited reason).
- **Test evidence.** File paths and CI workflows. Cited with `file:line`
  where load-bearing.

A "Future hosted service triggers re-evaluation" footer is recorded at the
end of this document.

---

## A01 — Broken Access Control

**Applicability:** Authorization controls protecting resources (objects,
endpoints, admin pages) from being accessed by users who should not have
access.

**Status:** **Not applicable** to v0.2.0rc1. There is no authorization
surface in the CLI. The CLI runs as the invoking OS user with their own
filesystem and network privileges — no in-app access-control decisions
are made beyond OS-level permissions. The threat model lists this as
"out of scope" because Lathe does not own a user-management surface.

**Re-evaluation triggers:**

- Any hosted registry or hosted CI ships.
- Any account system or signed-token surface ships.
- Any per-user authorization decision is introduced into the CLI (e.g.
  "this stack requires plan X").

---

## A02 — Cryptographic Failures

**Applicability:** Failures around data in transit, data at rest, and
the cryptographic primitives used.

**Status:** Applies (narrow surface).

**Surface in v0.2.0rc1:**

- **Provider HTTP client.** All learned-provider traffic and telemetry
  ingest go through `lathe/net.py::safe_urlopen`. TLS verification is
  always on (`lathe/net.py:1-30` declares the safe-urlopen contract;
  see also `docs/security/threat_model.md` row "Network/provider IO").
  Telemetry is HTTPS-only — `lathe/telemetry.py:40` pins
  `TELEMETRY_INGEST_URL: str = "https://telemetry.lathe.dev/ingest"` with
  a host allowlist.
- **No at-rest crypto for sensitive user data.** Lathe stores no PII at
  rest. The local telemetry config holds an opaque 16-byte hex
  `user_salt` (`lathe/telemetry.py:43`, `lathe/telemetry.py:107-118`)
  which is not a secret in the cryptographic sense — it's a local
  identity separator that prevents ingest from recomputing identities
  without the local file. See `docs/release/telemetry-verification-v0.2.0rc1.md`
  rows 2 and 3 for the consent + persistence model.
- **Signed reproducibility receipts.** `lathe/publish/signed_repro.py`
  uses ed25519 manifests as part of SEC-NEW-2. The signing key is
  user-supplied via `runtime_config.json`; the public key is recorded in
  the build report. Key management is the operator's responsibility —
  see `docs/security/threat_model.md` "Publish driver" section.
- **Release-artifact signatures.** Wheel/sdist/tag signatures are
  **not** performed for v0.2.0rc1 — recorded as
  `EXC-PHASE3-SIGN-001` in `docs/release/decision-log-v0.2.0rc1.md`.

**Test evidence:**

- `tests/unit/test_safe_logging.py:21-51` — token + path redaction in
  logs (covers leaked-secret-in-log failure modes).
- Phase 6 evidence: `docs/release/evidence-bundle-v0.2.0rc1/bandit.json`
  and `bandit.txt` cover Bandit's crypto-related rules.

---

## A03 — Injection

**Applicability:** Untrusted input flowing into an interpreter, parser,
shell, OS command, or LLM prompt.

**Status:** Applies (the `.lth` parser and prompt-injection static scan
are core controls).

**Surface and controls:**

- **`.lth` source parser.** Grammar-driven, declarative; no `eval`/`exec`.
  Bandit gates assert this. The parser lives at `lathe/parser/`.
  Trust-boundary policy is declared and enforced — see
  `docs/security/threat_model.md` "Enforceable ingress policy" table and
  `tests/unit/test_trust_boundaries.py`. Fuzz coverage:
  `tests/fuzz/test_parser_fuzz.py` and `tests/fuzz/test_ingress_fuzz.py`.
  Property-based coverage:
  `tests/property/test_resolver_properties.py`,
  `tests/property/test_shape_ir_properties.py`, etc.
- **Prompt injection.** `lathe/parser/prompt_injection.py` is a static
  scanner that warns on suspected prompt-injection patterns inside
  string literals before they flow to learned providers. SEC-8 (this
  ticket per the threat model). User-facing doc:
  `docs/security/prompt_injection.md`. Safe-logging tests:
  `tests/unit/test_safe_logging.py:84-97` cover the prompt-injection
  diagnostic redacting the offending path.
- **Shell / OS command injection.** Subprocesses (Blender, git, git-lfs)
  go through `lathe/subproc.py` with explicit argv lists; no shell=True;
  env scrubbed with `_FORBIDDEN_ENV_KEYS` rejecting `LD_PRELOAD`,
  `PYTHONPATH`, etc. Argv is validated by
  `lathe/sandbox/blender.py::_validate_argv` (SEC-7).
- **JSON ingestion.** `runtime_config.json` parsed via stdlib `json` with
  byte cap, UTF-8 decode, JSON-schema validation
  (`lathe/runtime_config.py:165` per the threat model citation).

**Test evidence:**

- `tests/fuzz/test_parser_fuzz.py`, `tests/fuzz/test_ingress_fuzz.py`.
- `tests/property/*` (six property suites — see `tests/property/`).
- `tests/unit/test_safe_logging.py` — three tests asserting that
  `log_event`, plugin-load failure logging, and prompt-injection logging
  all redact secrets and sensitive paths in both the rendered message
  and the structured `lathe_details` field.
- `docs/security/prompt_injection.md` — user-facing doc.
- `docs/security/json_ingress_audit.md` — JSON ingress audit.

---

## A04 — Insecure Design

**Applicability:** Architectural / design-time decisions that bake in
security weaknesses (no rate limiting, no defense in depth, no threat
modeling).

**Status:** Applies (threat model is the primary control).

**Surface and controls:**

- **Threat model.** `docs/security/threat_model.md` is the authoritative
  STRIDE-style document. Refreshed and signed off as part of Phase 9
  (this pass).
- **Trust boundaries declared in code.** `lathe.security.ingress_boundary`
  attaches `BoundaryPolicy` values with `InputClass`, `TrustLevel`, and
  named controls to every untrusted ingress chokepoint. See the
  "Enforceable ingress policy" table in
  `docs/security/threat_model.md`. `tests/unit/test_trust_boundaries.py`
  fails if expected untrusted boundaries lose their policies or if an
  untrusted policy omits controls.
- **Defense in depth on Blender subprocess.** Env scrubbing +
  `--factory-startup` + CPU/memory caps + 600s timeout + structured
  result. See `docs/security/blender_sandbox.md`.
- **Default-deny on conservative path.** No-runtime-config build defaults
  to `lathe.provider.shape.reference_conditioned_v1` (offline,
  deterministic). Network providers are explicit opt-in via
  `--runtime-config` (`CLAUDE.md` §"Provider/runtime wiring is opt-in").

**Test evidence:**

- `docs/security/threat_model.md` (refreshed 2026-04-28).
- `docs/security/blender_sandbox.md`.
- `tests/unit/test_trust_boundaries.py`.

---

## A05 — Security Misconfiguration

**Applicability:** Default configurations, hardening gaps, missing CI
gates.

**Status:** Applies.

**Surface and controls:**

- **CI security gates.** `docs/security/ci_gates.md` is the canonical
  list. Workflows enforce: `bandit` (`.github/workflows/security.yml`),
  `gitleaks` (`.github/workflows/gitleaks.yml`), `pip-audit`
  (`.github/workflows/pip-audit.yml`), CodeQL
  (`.github/workflows/codeql.yml`), Semgrep (security workflow),
  SBOM (`.github/workflows/sbom.yml`).
- **Default state hardened.** Telemetry off by default
  (`docs/release/telemetry-verification-v0.2.0rc1.md` row 1, PASS).
  Output paths default to inside the repo root via `LATHE_ALLOW_EXTERNAL_OUT=0`
  (`.env.example:43-44`); operators must set `=1` to opt out.
  Blender autoexec default-deny is tracked as
  `SEC-FUTURE-4` in `docs/security/threat_model.md` §"Open follow-ups".

**Test evidence:**

- `docs/security/ci_gates.md`.
- `.github/workflows/security.yml`, `gitleaks.yml`, `codeql.yml`,
  `pip-audit.yml`, `sbom.yml`.
- `.env.example` (documents safe defaults).

---

## A06 — Vulnerable and Outdated Components

**Applicability:** Known-CVE dependencies; stale pins; lack of update
mechanism.

**Status:** Applies.

**Surface and controls:**

- **pip-audit runs in CI** and was captured for the readiness pass:
  `docs/release/evidence-bundle-v0.2.0rc1/pip-audit-runtime.txt` and
  `pip-audit-dev.txt`. Phase 3 captured the lxml + pip CVE findings;
  see `docs/release/evidence-bundle-v0.2.0rc1/lxml-investigation.txt`
  for the triage.
- **SBOM is published** as part of the evidence bundle:
  `docs/release/evidence-bundle-v0.2.0rc1/sbom.json` (CycloneDX, 211
  components) and `sbom.xml`.
- **Dependabot is enabled** for both `pip` and `github-actions`
  ecosystems on a weekly Monday cadence with `talmerri` as assignee —
  see `.github/dependabot.yml:1-42`.
- **Pinning policy.** `requirements.txt` and `requirements-dev.txt` are
  generated from `pyproject.toml` + `uv.lock`; the dependency-sync
  invariant is verified by
  `docs/release/evidence-bundle-v0.2.0rc1/dep-sync.txt` (`exit_code: 0`).
- **Supply-chain summary** lives at
  `docs/security/supply-chain-review-v0.2.0rc1.md` (Phase 9 output).

**Test evidence:**

- `docs/release/evidence-bundle-v0.2.0rc1/pip-audit-runtime.txt`.
- `docs/release/evidence-bundle-v0.2.0rc1/pip-audit-dev.txt`.
- `docs/release/evidence-bundle-v0.2.0rc1/sbom.json` (211 components).
- `.github/dependabot.yml`.
- `docs/release/evidence-bundle-v0.2.0rc1/dep-sync.txt`.

---

## A07 — Identification and Authentication Failures

**Applicability:** Weaknesses in user identity or authentication.

**Status:** **Not applicable** to v0.2.0rc1. There is no auth surface in
the CLI: no account system, no session, no token issuance, no
credentials managed by Lathe. The user is implicit — whoever runs the
CLI is trusted with their own files and network.

**Re-evaluation triggers** (mirrors the auth attack-tree note):

- Any hosted registry ships.
- Any account system ships.
- Any signed-token surface ships.

---

## A08 — Software and Data Integrity Failures

**Applicability:** Code, dependencies, and pipeline integrity. CI/CD
trust boundaries. Update integrity.

**Status:** Applies (mixed: SBOM yes, signatures no for v0.2.0rc1).

**Surface and controls:**

- **SBOM published** (Phase 3 / evidence bundle).
- **Reproducibility receipts.** SEC-NEW-2 signed receipts via
  `lathe/publish/signed_repro.py` cover the final build + stage
  digests. See `docs/security/threat_model.md` "Mitigation summary"
  row "Signed reproducibility receipts".
- **Release artifact integrity.**
  `docs/release/evidence-bundle-v0.2.0rc1/SHA256SUMS.txt` records
  per-artifact hashes for the wheel, sdist, and SBOM.
- **Signature gap.** Release artifacts are NOT signed for v0.2.0rc1 —
  recorded as `EXC-PHASE3-SIGN-001`. PyPI Trusted Publishing is also not
  configured — recorded as `EXC-PHASE3-PYPI-TP-002`. Both exceptions are
  in `docs/release/decision-log-v0.2.0rc1.md`.

**Test evidence:**

- `docs/release/evidence-bundle-v0.2.0rc1/SHA256SUMS.txt`.
- `docs/release/evidence-bundle-v0.2.0rc1/sbom.json`.
- `docs/release/decision-log-v0.2.0rc1.md` §"Release exceptions accepted
  in this pass".
- `lathe/publish/signed_repro.py`.

---

## A09 — Security Logging and Monitoring Failures

**Applicability:** Inadequate logging, secrets-in-logs, alerting gaps.

**Status:** Applies (logging hygiene is a Phase 2 PASS row).

**Surface and controls:**

- **Safe logging.** `tests/unit/test_safe_logging.py` asserts redaction
  of secrets and sensitive paths in `log_event`, plugin-load failure
  logging, and prompt-injection diagnostics
  (`tests/unit/test_safe_logging.py:21-97`).
- **Telemetry payload allowlist.** `lathe/telemetry.py:251-259` returns
  exactly seven keys: `lathe_version`, `build_id_hash`, `build_kind`,
  `stack_id`, `certified`, `exit_code`, `wall_ms`. Hygiene test:
  `tests/unit/test_telemetry.py:228-264` — poisoned-build-report case
  asserts asset names, env vars (`API_KEY=hunter2`), runtime config,
  diagnostics, and stdout do not leak.
- **PII redaction.** Phase 2 verification confirmed 15/15 PASS; see
  `docs/release/telemetry-verification-v0.2.0rc1.md`.

**Test evidence:**

- `tests/unit/test_safe_logging.py:21-97`.
- `tests/unit/test_telemetry.py:228-317`.
- `docs/release/telemetry-verification-v0.2.0rc1.md` (15/15 PASS).

**Monitoring gap:** there is no live alerting or SOC integration —
v0.2.0rc1 is a local CLI; logs are local. Operations doc covers what to
look for in CI; live alerting is `requires-human` once any hosted
service ships.

---

## A10 — Server-Side Request Forgery (SSRF)

**Applicability:** Server-side code makes outbound requests to URLs
derived from user input. Lathe's analog: the CLI on the user's host
makes outbound requests on behalf of `runtime_config.json`-supplied
provider URLs.

**Status:** Applies (host-allowlist is the primary control).

**Surface and controls:**

- **Host allowlist + scheme enforcement** at `lathe/net.py::safe_urlopen`.
  Per the threat model "Network/provider IO" row, the function enforces:
  scheme allowlist (`https://` for non-localhost; `http://` only for
  explicit localhost provider configs), host allowlist (private IP
  rejection — refuses RFC1918 unless explicitly listed; refuses
  link-local and metadata addresses; refuses redirects), TLS
  verification always on, content-type and body-size checks.
- **Runtime-config provider-URL allowlist.** Each provider config
  declares a `url_allowlist` (`examples/runtime_configs/hunyuan_http.json`
  shows `"url_allowlist": ["localhost"]`). The provider transport
  refuses to connect outside this allowlist.
- **Telemetry ingest is host-pinned.** `lathe/telemetry.py:288` passes
  `allowlist=["telemetry.lathe.dev"]` so even a poisoned config cannot
  redirect telemetry to an attacker-controlled host.
- **Blender subprocess sandbox.** `docs/security/blender_sandbox.md`
  documents the sandbox layer (env scrubbing, `--factory-startup`, CPU
  and memory caps, 600s timeout). The Blender process can in principle
  open sockets — the host allowlist on `lathe/net.py` does not bind it,
  but the sandbox env-scrub policy and the Python-only execution surface
  inside Blender (no autoexec by default — tracked as
  `SEC-FUTURE-4`) reduce this.

**Test evidence:**

- `lathe/net.py` (host allowlist + safety caps).
- `docs/security/blender_sandbox.md`.
- `examples/runtime_configs/*.json` (each declares a `url_allowlist`).
- `lathe/telemetry.py:280-289` (telemetry call site pins `allowlist`).

---

## Future hosted service triggers re-evaluation

Every "Not applicable" row above and several of the cited mitigations
will need to be re-evaluated when any of the following triggers fire.
These triggers map exactly to the auth attack-tree triggers and the
abuse-vector triggers documented elsewhere in this directory:

- Any **hosted registry** (account-aware OR account-less) ships.
- Any **account system** ships (signup, login, password reset, OAuth).
- Any **signed-token surface** ships (API keys, machine-to-machine
  tokens, signed JWTs, project tokens for the CI SaaS).
- **Telemetry ingest is provisioned** (the receiving endpoint goes from
  `requires-human` to live).
- **Hosted CI / certification SaaS** ships (V1.0 PRD M5).
- **Any user-uploaded asset surface** ships (e.g. registry assets,
  marketplace listings, shared snapshots).

Each trigger requires re-running this OWASP mapping with the new surface
folded in BEFORE the surface goes public. The decision-log MUST record
the mapping run as a release-blocking gate.

---

## Cross-references

- [`docs/security/threat_model.md`](threat_model.md)
- [`docs/security/blender_sandbox.md`](blender_sandbox.md)
- [`docs/security/prompt_injection.md`](prompt_injection.md)
- [`docs/security/ci_gates.md`](ci_gates.md)
- [`docs/security/json_ingress_audit.md`](json_ingress_audit.md)
- [`docs/security/secret-hygiene-v0.2.0rc1.md`](secret-hygiene-v0.2.0rc1.md)
- [`docs/security/supply-chain-review-v0.2.0rc1.md`](supply-chain-review-v0.2.0rc1.md)
- [`docs/security/security-review-scope-v0.2.0rc1.md`](security-review-scope-v0.2.0rc1.md)
- [`docs/release/decision-log-v0.2.0rc1.md`](../release/decision-log-v0.2.0rc1.md)
- [`docs/release/telemetry-verification-v0.2.0rc1.md`](../release/telemetry-verification-v0.2.0rc1.md)
- [`docs/release/evidence-bundle-v0.2.0rc1/`](../release/evidence-bundle-v0.2.0rc1/)

## Sign-off
- Reviewed: 2026-04-28
- Reviewer: Tal Merri (self-assessment, solo maintainer)
- Counsel review: requires-human
- Next review: 2026-05-28 or T+30 post-launch (whichever later)
