# Secret Hygiene Confirmations — Lathe v0.2.0rc1

> Phase 9 P0. Self-assessment. Reviewer: Tal Merri (@talmerri).
> Date: 2026-04-28.
>
> This document records the secret-hygiene confirmations performed
> during the v0.2.0rc1 readiness remediation pass. It pairs with
> `docs/release/evidence-bundle-v0.2.0rc1/gitleaks-history.txt`
> (Phase 9 full-history scan transcript), the existing
> `docs/release/evidence-bundle-v0.2.0rc1/gitleaks.txt`
> (Phase 6 working-tree scan transcript), the safe-logging tests at
> `tests/unit/test_safe_logging.py`, and the telemetry payload-hygiene
> tests at `tests/unit/test_telemetry.py`.

## Confirmation matrix

| # | Item | Result | Evidence |
| - | ---- | ------ | -------- |
| 1 | `.env.example` example values only — no real values | PASS | Read the readiness worktree copy of `.env.example`. All assignments are blank or `0`/`info` defaults; the only literal value is `LATHE_ALLOW_EXTERNAL_OUT=0` which is the safe default. No tokens, no URLs to non-example hosts, no provider keys. Header at `:1-8` documents that listed values are examples, not defaults. |
| 2 | `examples/runtime_configs/*.json` — example values only | PASS | Read all seven configs: `auto_learned.json`, `hunyuan_http.json`, `mock_hunyuan_http.json`, `offline.json`, `real_learned_hunyuan_http.json`, `reference_only.json`, `vggt_local.json`. Hosts are exclusively `localhost`, `127.0.0.1`, or `*.example` (specifically `hunyuan.internal.example`). No bearer tokens, no API keys, no real provider hostnames. The VGGT config references `facebook/VGGT-1B` which is a public Hugging Face model id, not a credential. |
| 3 | Generated artifacts (`tmp_gallery_phase7/<asset>/build_report.json`) | SKIPPED — `requires-human:` rerun after Phase 7 gallery builds | The readiness worktree's `tmp_gallery_phase7/` directory did not exist at scan time (Phase 7 dispatched in parallel; gallery artifacts not yet present). Recorded as `H41` below. |
| 4 | Logs / provider tokens / PII | PASS (cross-reference) | `tests/unit/test_safe_logging.py:21-97` — three tests asserting `log_event`, plugin-load failure logging, and prompt-injection logging redact secrets and sensitive paths. Telemetry ingest token redaction covered by transport tests. |
| 5 | Telemetry poisoned-build-report test | PASS (cross-reference) | `tests/unit/test_telemetry.py:201-264` `PayloadHygieneTests.test_payload_contains_only_allowed_fields` — poisoned report contains `asset_path`, `env={"API_KEY":"hunter2"}`, `diagnostics`, `runtime_config`, `stdout`. Test asserts none of these keys or string contents leak; `set(body.keys())` is exactly the seven-key allowlist. |
| 6 | Safe-logging tests pass | PASS (existence + intent) | `tests/unit/test_safe_logging.py` exists with three redaction assertions (token + path, plugin-load entry-point + exception, prompt-injection diagnostic path). Phase 2 telemetry-verification row 15 (`docs/release/telemetry-verification-v0.2.0rc1.md`) confirms existence + intent; pytest run is the responsibility of Phase 6. |
| 7 | Full-history gitleaks scan | requires-human (H40) | `docs/release/evidence-bundle-v0.2.0rc1/gitleaks-history.txt` records two failed install attempts (native binary not on PATH; npx fallback failed because gitleaks is not an npm package). `.github/workflows/gitleaks.yml` is the canonical authority; CI run will produce the artifact once branch is pushed. |

## Summary

- PASS: 4 (`.env.example`, `runtime_configs`, safe-logging cross-ref,
  telemetry-payload cross-ref).
- PASS (existence + intent): 1 (safe-logging test file).
- SKIPPED: 1 (Phase 7 generated artifacts not yet present).
- requires-human: 2 (full-history gitleaks; Phase 7 rerun).

## Open `requires-human` items raised by this doc

- **H40** — gitleaks must run on a host with the tool installed. Phase 6
  H39 covers the working-tree scan; Phase 9 H40 covers the full-history
  `--log-opts="--all"` scan. Either install scoop/choco/go-installed
  gitleaks locally and rerun BOTH commands, OR rely on the
  `.github/workflows/gitleaks.yml` CI run after the branch is pushed and
  link the GitHub Actions run URL in both transcripts.
- **H41** — secret scan over `tmp_gallery_phase7/<asset>/build_report.json`
  must be rerun after Phase 7 lands. The check is: do the build reports
  emit any local paths, env values, or runtime-config tokens that should
  not appear in a release bundle? The expected answer is "no" because
  `lathe/cli/build_cmd.py` calls `emit_build_ping` only on the success
  branch and the build report itself is sanitized
  (`tests/unit/test_telemetry.py:201-317`). Confirm during Phase 7
  follow-up.

## Secret rotation policy + scope minimization

This is forward-looking: v0.2.0rc1 ships **no first-party hosted
credentials**. The runtime-config schema allows operators to embed their
own provider tokens (e.g. a Hunyuan provider's API key) but Lathe itself
does not provision, distribute, or rotate any secret. The first-party
attack surface for secret rotation is therefore zero today.

### Policy framework (forward-looking, requires-human ratification)

When any first-party hosted credential surface ships, the following
policy applies. **All four sub-policies are `requires-human:` ratified
before any hosted-credential surface ships in any channel — public, dev,
staging, or behind a feature flag.**

1. **Scope minimization.** Every credential is bound to the narrowest
   scope it can do its job in. Telemetry ingest credentials write to
   the ingest endpoint only and have no read scope. Publish-driver
   credentials are bound to a specific S3 prefix or Supabase bucket and
   never to the parent account. Provider credentials are bound to a
   single base URL.
2. **Rotation cadence.** Default rotation cadence is 90 days for
   credentials that are operator-rotated; 24 hours or shorter for
   credentials that are session/CI-issued (OIDC tokens for PyPI Trusted
   Publishing fall in the latter category — see
   `EXC-PHASE3-PYPI-TP-002`). Rotation logs MUST exist; "rotated when we
   remembered" is not acceptable.
3. **Storage.** No long-lived secrets in source control. Any credential
   committed to the repo (intentionally OR accidentally) is treated as
   compromised and rotated immediately. Gitleaks CI gate
   (`.github/workflows/gitleaks.yml`) is the trip wire on commit/PR.
4. **Revocation surface.** A documented runbook MUST exist for revoking
   any first-party credential within 1 hour of compromise notice. The
   runbook is owned by `requires-human:` (see auth attack-tree note —
   no hosted surface today, no runbook required today).

### Until that ratification

- **Operator-supplied secrets in `runtime_config.json`** are the user's
  responsibility. Lathe redacts them from logs
  (`tests/unit/test_safe_logging.py`) and never persists them in the
  build cache or build reports
  (`tests/unit/test_telemetry.py:201-317`). Operators should follow
  their own organization's secret-handling policy.
- **No first-party credentials are required to use Lathe.** The
  conservative offline path (`reference_only.json` runtime config) needs
  zero credentials. Provider configs are explicit opt-in.

## Cross-references

- [`docs/release/evidence-bundle-v0.2.0rc1/gitleaks.txt`](../release/evidence-bundle-v0.2.0rc1/gitleaks.txt) — Phase 6 working-tree scan transcript.
- [`docs/release/evidence-bundle-v0.2.0rc1/gitleaks-history.txt`](../release/evidence-bundle-v0.2.0rc1/gitleaks-history.txt) — Phase 9 full-history scan transcript.
- [`tests/unit/test_safe_logging.py`](https://github.com/talmerri/lathe/blob/main/tests/unit/test_safe_logging.py) — log redaction tests.
- [`tests/unit/test_telemetry.py`](https://github.com/talmerri/lathe/blob/main/tests/unit/test_telemetry.py) — payload-hygiene tests.
- [`docs/release/telemetry-verification-v0.2.0rc1.md`](../release/telemetry-verification-v0.2.0rc1.md) — Phase 2 verification (15/15 PASS).
- [`docs/security/owasp-mapping-v0.2.0rc1.md`](owasp-mapping-v0.2.0rc1.md) — A02, A09 dependencies.
- [`docs/security/threat_model.md`](threat_model.md) — STRIDE per flow.

## Sign-off
- Reviewed: 2026-04-28
- Reviewer: Tal Merri (self-assessment, solo maintainer)
- Counsel review: requires-human
- Next review: 2026-05-28 or T+30 post-launch (whichever later)
