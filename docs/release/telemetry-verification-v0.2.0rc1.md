# Telemetry Verification — Lathe v0.2.0rc1

> Phase 2 P0 verification pass. Read-only review of `lathe/telemetry.py`,
> `lathe/cli/telemetry_cmd.py`, `lathe/cli/build_cmd.py`, and
> `tests/unit/test_telemetry.py` + `tests/unit/test_safe_logging.py`.
> No code mutations were made in this verification pass; any FAIL row carries
> a `requires-fix-before-launch:` annotation and reproduction step.

Reviewer: Tal Merri (@talmerri) — solo maintainer self-assessment.
Date: 2026-04-28.

## Verification matrix

| # | Item | Result | Citation | Notes |
| - | ---- | ------ | -------- | ----- |
| 1 | Telemetry disabled by default in code (no config file ⇒ disabled) | PASS | `lathe/telemetry.py:99-104` (`is_enabled` returns False when `_read_config()` is None or lacks `enabled=True`) and `lathe/telemetry.py:74-81` (`_read_config` returns None when the config file is absent). Test: `tests/unit/test_telemetry.py:43-49` `test_default_state_is_unset_treated_as_disabled`. | Default state confirmed as `unset` ⇒ `enabled=False`. |
| 2 | `lathe telemetry enable` requires explicit consent (writes config with `enabled=True`) | PASS | CLI prompt: `lathe/cli/telemetry_cmd.py:41-62` (`_run_enable` writes only after stdin `y`/`yes`, otherwise reports `cancelled`). `--yes` flag explicitly skips the prompt for scripted use (`lathe/cli/telemetry_cmd.py:29-34`). Underlying writer: `lathe/telemetry.py:107-118` (`enable` sets `enabled=True`, persists 16-byte hex `user_salt`). Test: `tests/unit/test_telemetry.py:53-58`. | Consent flow is interactive by default; salt is 32 hex chars (16 bytes). |
| 3 | `lathe telemetry disable` opts out (`enabled=False`; salt preserved) | PASS | `lathe/telemetry.py:121-128` (`disable` sets `enabled=False`; salt preserved if present, generated otherwise to keep identity stable on re-enable). Test: `tests/unit/test_telemetry.py:60-65` `test_disable_preserves_salt`. | Salt preservation is intentional and tested. |
| 4 | Local-data clear (`lathe telemetry clear`) works | PASS | CLI: `lathe/cli/telemetry_cmd.py:74-82`. Implementation: `lathe/telemetry.py:159-168` (`clear` deletes the config file, returns True if it existed). Tests: `tests/unit/test_telemetry.py:67-75`. | Note: `docs/privacy.md:87` already calls out that the implemented command name is `clear`, not `purge` (the readiness brief uses `purge`). Naming gap recorded as `requires-human` in privacy doc. |
| 5 | No telemetry emitted during `lathe doctor` | PASS | Grep over `lathe/cli/doctor_cmd.py` for `telemetry`/`emit_build_ping` returned 0 matches. Repo-wide grep shows the only `emit_build_ping` call site is `lathe/cli/build_cmd.py:219`. | doctor command never imports or invokes telemetry. |
| 6 | No telemetry emitted during `lathe check` | PASS | Grep over `lathe/cli/check_cmd.py` for `telemetry`/`emit_build_ping` returned 0 matches. Same single-call-site evidence as item 5. | check command never imports or invokes telemetry. |
| 7 | No telemetry emitted during failed builds unless explicitly intended + documented | PASS | `lathe/cli/build_cmd.py:174-226`: `emit_build_ping(report)` is inside the `try` block on the success branch *after* `build_asset` returns. Failure branches (`BuildError` line 227, `ShapeProviderError` line 230, `OSError` line 236) raise `SystemExit(1)` before reaching the telemetry call. | Failed builds never reach the emit_build_ping call. No `emit_build_failure_ping` exists; the only allowlisted event is `build_ping` for successful (or at least completed) builds. |
| 8 | Payload includes only allowlisted fields | PASS | Allowlist defined as the explicit dict literal returned by `_build_payload` (`lathe/telemetry.py:251-259`): `lathe_version`, `build_id_hash`, `build_kind`, `stack_id`, `certified`, `exit_code`, `wall_ms` — exactly seven keys. Test asserts the allowlist: `tests/unit/test_telemetry.py:228-236` (`PayloadHygieneTests._ALLOWED`). Hygiene assertion: `tests/unit/test_telemetry.py:238-264` `test_payload_contains_only_allowed_fields` builds a poisoned report and asserts `set(body.keys()) == self._ALLOWED`. | Hygiene tests pin the schema; any new field would break this test. |
| 9 | Payload does NOT include source paths | PASS | No `path`/`source_path`/`asset_path`/`out_dir` keys appear anywhere in `_build_payload` (`lathe/telemetry.py:239-259`). `_extract_build_id` (`lathe/telemetry.py:187-213`) explicitly only reads `build_id`/`cache_key`/`id` strings or hashes a structured fingerprint of `kind`/`backend_stack`/`certified`/`outputs`-but-only-format/sha256/size. Test: `tests/unit/test_telemetry.py:266-288` asserts that a local output directory does not appear in the serialized body. | |
| 10 | Payload does NOT include asset names | PASS | `_build_payload` never references `build_report["asset"]` (`lathe/telemetry.py:239-259`). `_extract_build_id` (`lathe/telemetry.py:187-213`) explicitly does not consume `asset`. Test: `tests/unit/test_telemetry.py:266-288` `test_payload_extracts_current_build_metadata` builds a poisoned report with `asset="secret_local_asset_name"` and asserts the literal string never appears in the serialized body. Test: `tests/unit/test_telemetry.py:290-317` `test_payload_derives_identity_from_normal_build_report_without_paths` confirms `asset="local_asset_name"` does not leak even when no `build_id` is set. | The hygiene tests do confirm the asset-name claim; no further action required. |
| 11 | Payload does NOT include environment variables | PASS | `_build_payload` does not call `os.environ` and does not consume `build_report["env"]` (`lathe/telemetry.py:239-259`). Test: `tests/unit/test_telemetry.py:238-264` poisons a report with `env={"API_KEY": "hunter2"}` and asserts neither `API_KEY` nor `hunter2` appears in the serialized body. | |
| 12 | Payload does NOT include provider keys | PASS | Same evidence as item 11 — `runtime_config` (which would carry provider URLs/keys) is never read by `_build_payload`. Test: `tests/unit/test_telemetry.py:238-264` poisons with `runtime_config={"shape": {"strict": True}}` and asserts the `runtime_config` key is filtered out. | Lathe ships zero default provider keys, so this is doubly clean: nothing to leak even if the payload were broader. |
| 13 | Payload does NOT include diagnostics or logs | PASS | Same evidence path as item 11 — `_build_payload` does not consume `diagnostics`, `logs`, `stdout`, or `stderr`. Test: `tests/unit/test_telemetry.py:238-264` poisons with `diagnostics=[{"msg": "very secret"}]` and `stdout="build log"`; assertion confirms neither string appears in the serialized body. | |
| 14 | Telemetry tests include a poisoned-build-report case (with secrets) confirming safe stripping | PASS | `tests/unit/test_telemetry.py:201-264` `PayloadHygieneTests.test_payload_contains_only_allowed_fields` is exactly the poisoned-report test: the report contains `asset_path` (`/home/alice/secrets/asset.lth`), `env` (`API_KEY`/`hunter2`), `diagnostics`, `runtime_config`, and `stdout`. The test asserts neither the keys nor the string contents leak into the serialized body, and additionally asserts `set(body.keys()) == _ALLOWED`. The persistent salt itself (`deadbeefcafefeed0123456789abcdef`) is also asserted not to appear in the body. | The test surface is comprehensive. |
| 15 | Safe-logging tests pass (file exists; do not run pytest) | PASS (existence + intent) | File exists: `tests/unit/test_safe_logging.py:1-97`. Three tests assert that `log_event`, plugin-load failure logging, and prompt-injection logging all redact secrets and sensitive paths in both the rendered message and the structured `lathe_details` field. Citations: `tests/unit/test_safe_logging.py:21-51` (token + path redaction), `tests/unit/test_safe_logging.py:54-81` (entry-point name + exception message redaction during plugin load), `tests/unit/test_safe_logging.py:84-97` (prompt-injection diagnostic redacts path). | This is an existence + intent confirmation only; per scope rules pytest was not run. The lead should reconfirm the run status during Phase 6. |

## Summary

- PASS: 15
- FAIL: 0
- `requires-fix-before-launch`: 0

## Open issues

- None new from this verification pass.

## Notes for the lead

- The CLI subcommand for clearing local data is `lathe telemetry clear`, not `purge`. The readiness brief and Phase 1 task list both use `purge`; the implemented name is `clear`. `docs/privacy.md:87-88` already documents this gap with a `requires-human` flag. No code change is required for v0.2.0rc1, but counsel/launch comms should align on the name.
- The build-success path emits exactly one HTTPS POST per build when telemetry is enabled. Failed builds raise before the emit call (`lathe/cli/build_cmd.py:174-226`), so no `emit_build_failure_ping` exists today. If the project later wants failure-rate telemetry, that must be added with explicit consent + documentation; the current absence is the safer default and is documented in `docs/privacy.md` and the event taxonomy.
- The persistent local salt (`user_salt`) is preserved by `disable` so re-enabling does not reset the user's anonymous identity. This is intentional (`lathe/telemetry.py:121-128`); only `clear` deletes the local config file entirely. Counsel should confirm this is acceptable as part of the privacy review (`requires-human:` counsel review of telemetry consent semantics).

## Cross-references

- [docs/privacy.md](../privacy.md)
- [docs/legal/compliance-review-v0.2.0rc1.md](../legal/compliance-review-v0.2.0rc1.md)
- [docs/telemetry_event_taxonomy.md](../telemetry_event_taxonomy.md)
- [SECURITY.md](https://github.com/talmerri/lathe/blob/main/SECURITY.md)
