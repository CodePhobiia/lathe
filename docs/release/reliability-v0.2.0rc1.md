# Reliability Plan — Lathe v0.2.0rc1

**Pre-release document. All SLOs are launch-gate commitments, not live SLIs.**
Lathe v0.2.0rc1 is a CLI compiler with no hosted service and telemetry disabled by default.

---

### 1. Critical user journeys

**Install → doctor**
A user performs a fresh `pip install lathe==0.2.0rc1` on a supported OS + Python combination from the support matrix, then runs `lathe doctor`. The journey succeeds when `lathe doctor` exits 0 and reports no missing required dependencies. Failure modes counted against SLO: install error (missing wheel, dependency conflict, unsupported Python version), `lathe doctor` non-zero exit due to import error or broken entry point, or silent failure where `doctor` exits 0 but reports a broken state that blocks the next step.

**Check example**
A user runs `lathe check examples/courier_drone.lth` against a freshly cloned repository. The journey succeeds when the command exits 0 with no parse or semantic errors reported. Failure modes: non-zero exit due to grammar regression, schema drift, or a broken import in the example file; false-positive errors on valid syntax; file-not-found if example path changed without updating CI.

**Build canonical asset**
A user runs `lathe build examples/courier_drone.lth courier_drone --out tmp_x` without a runtime config (conservative/native path). The journey succeeds when the output directory contains `build_report.json` with `"certified": true`. Failure modes: non-zero exit before report is written; `build_report.json` absent or unparseable; `certified` field is `false`; any required downstream stage (topology, UV, validate, package) exits with an unhandled exception.

**Import into Godot**
A user opens the generated `.glb` from a certified build in the Godot stock glTF importer (Godot 4.x, stable channel). The journey succeeds when the scene tree shows the expected hierarchy and socket nodes are present as `BoneAttachment3D` or equivalent empty nodes. Failure modes: importer error on open; missing hierarchy nodes; socket nodes absent or misnamed; UV seams producing visible black lines at import-default settings.

**Troubleshoot failed certification**
A user's `lathe build` run ends without `certified=true`. The journey succeeds when every diagnostic in `build_report.json` includes a `next_step` field pointing to a documented action, and the user can act on it without opening source code. Failure modes: any diagnostic missing `next_step`; `next_step` references a non-existent doc page in `docs/error_codes.md` or runbook `docs/ops/runbooks/canonical-build-failure.md`; `build_report.json` absent when certification fails (swallowed exception).

---

### 2. SLO + error budget per journey

| Journey | SLO commitment | Window | Error budget | Measurement source (RC1) | Measurement source (post-launch) |
|---|---|---|---|---|---|
| Install → doctor | 95% of fresh installs succeed on supported matrix | per-release | 5% across supported matrix cells | `evidence-bundle-v0.2.0rc1/wheel-install-py311.txt` + `requires-human:` matrix CI legs | telemetry `install_ping` success rate (when telemetry on) + GitHub support intake |
| Check example | 100% of canonical examples pass `lathe check` | per-commit | 0% on canonical examples | CI `examples.yml` workflow | CI `examples.yml` (unchanged) |
| Build canonical asset | 100% of hero families certify on native path | per-commit | 0% on hero families | CI `examples.yml` + benchmark workflow + Phase 7 gallery transcripts | telemetry `build_ping` `certified=true` rate by `stack_id` |
| Import into Godot | Every generated `.glb` opens in Godot stock importer with correct hierarchy and sockets | per-release | Manual smoke; `requires-human:` | Manual smoke test on Windows / macOS / Linux | Manual smoke; `requires-human:` automated GUT plan |
| Troubleshoot failed cert | Every failed cert produces diagnostics where 100% have a valid `next_step` | per-commit | 0% diagnostics missing `next_step` | Unit tests on diagnostic schema + Phase 7 unhappy-path walks | telemetry diagnostic-spike alerts |

---

### 3. Burn-rate alerts

v0.2.0rc1 has no hosted measurement, therefore no automated burn-rate alerts. Manual triage runs against:

- the canonical build via the `examples.yml` CI workflow, and
- the support intake (GitHub issues + email to talmerri@gmail.com).

Burn-rate alerts will be implemented when telemetry ingest is provisioned (Phase 11 decision).

**`requires-human:`** Define and configure burn-rate alert thresholds (e.g., >10% install failures in a 24 h window triggers P1) before any hosted dashboard goes live.

---

### 4. Dashboards

All five dashboard questions are `requires-human:` for v0.2.0rc1. Telemetry field names reference `docs/telemetry_event_taxonomy.md`.

| Question | Underlying pull | Status |
|---|---|---|
| Are installs succeeding? | `install_ping`: `success` rate grouped by `lathe_version` × `os` × `python_version` | `requires-human:` — clear when telemetry ingest + dashboard host configured |
| Are builds succeeding? | `build_ping`: `certified=true` rate grouped by `stack_id` × `lathe_version` | `requires-human:` — same trigger |
| Which versions fail? | `build_ping`: failure breakdown by `lathe_version` × `exit_code` | `requires-human:` — same trigger |
| Which diagnostics spike? | Diagnostic-code distribution from `build_ping`; alert when delta > threshold within a release window | `requires-human:` — same trigger |
| Is support volume exceeding capacity? | GitHub issue intake rate vs response-SLA target (target: first response ≤ 3 business days) | `requires-human:` — clear when issue-tracker integration configured |

---

### 5. Synthetic monitoring

All three monitors are `requires-human:` for v0.2.0rc1.

**Docs quickstart synthetic**
Scheduled check that hits the published docs quickstart URL, verifies HTTP 200, and spot-checks that the `lathe check` code block renders. **`requires-human:`** clear once the docs site host is provisioned and the URL is stable.

**Package install synthetic**
Scheduled `pip install lathe==<latest>` in a clean virtualenv followed by `lathe doctor`; asserts exit 0. Proposed cadence: nightly via GitHub Actions cron. **`requires-human:`** clear once the scheduler host (GitHub Actions environment) is configured and the PyPI package is publicly available.

**Telemetry ingest synthetic**
Round-trip a synthetic `install_ping` event through the ingest endpoint; assert receipt + schema validation. **`requires-human:`** clear once telemetry ingest is provisioned (Phase 11).

---

### 6. Backup + restore for release artifacts

**Backup target**
PyPI-hosted wheel (`lathe-0.2.0rc1-py3-none-any.whl`) and sdist (`lathe-0.2.0rc1.tar.gz`) are the canonical store; we do not run a parallel mirror. The local `tmp_release_dist/lathe-0.2.0rc1.*` files are regenerated on demand from a clean `git clone` + `python -m build` per exception `EXC-PHASE3-SIGN-001` in `docs/release/decision-log-v0.2.0rc1.md`.

**Restore process**
If a published artifact is yanked from PyPI, the canonical replacement is rebuilt from the tagged commit. Reference hashes in `evidence-bundle-v0.2.0rc1/SHA256SUMS.txt` are used to verify the rebuilt artifacts match. The replacement is published as a new patch version (not the same version string). Full procedure in `docs/release/rollback-plan-v0.2.0rc1.md` under "Yank procedure".

**Restore drill**
**`requires-human:`** Simulate a yank-and-replace exercise once Trusted Publishing is configured (`EXC-PHASE3-PYPI-TP-002`). Record RTO achieved vs the 4 h target.

---

### 7. RTO + RPO targets

**RTO (recovery-time objective):** 4 h from the yank decision to a user-visible replacement installable via `pip install lathe`. This matches the rollback-plan PyPI-yank target in `docs/release/rollback-plan-v0.2.0rc1.md`.

**RPO (recovery-point objective):** 0. Release artifacts are immutable; the replacement is always a new version built from the tagged commit, not a rollback of source. No user data or build state is held server-side.

**Test:** **`requires-human:`** Dry-run the yank + replace flow once Trusted Publishing is configured (`EXC-PHASE3-PYPI-TP-002`) to validate the 4 h RTO.

---

### 8. Cross-references

- `docs/ops/runbooks/` — incident response runbooks per journey (canonical build failure: `docs/ops/runbooks/canonical-build-failure.md`).
- `docs/release/rollback-plan-v0.2.0rc1.md` — full yank + replace flow.
- `docs/risk_register.md` — RISK-002 (install failure on unsupported Python), RISK-006 (Godot importer regression on .glb schema change), RISK-011 (diagnostic quality regression silencing actionable errors).
- `docs/release/decision-log-v0.2.0rc1.md` — exceptions EXC-PHASE3-SIGN-001, EXC-PHASE3-PYPI-TP-002.
- `docs/error_codes.md` — authoritative list of diagnostic codes and `next_step` values.
- `docs/telemetry_event_taxonomy.md` — field names for post-launch dashboard queries.
