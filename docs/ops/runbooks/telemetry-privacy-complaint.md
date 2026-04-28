# Runbook: Telemetry Privacy Complaint

A user reports that Lathe sent data without their consent, or more data than documented.

**Owner:** Tal Merri (@talmerri). Backup: `requires-human` + counsel if personal data confirmed

## Symptoms

- User claims they never enabled telemetry but network traffic shows outbound pings from Lathe.
- User claims the telemetry payload contained more fields than `docs/telemetry.md` documents.
- `lathe telemetry status` shows `enabled: true` on a machine where the user never ran `lathe telemetry enable`.

## First response (≤5 min)

1. Treat this as a **P0 candidate** until proven otherwise.
2. Ask the user to share the output of `lathe telemetry status` and the contents of their local telemetry config file.

## Investigation

Confirm telemetry status via the user's local config:

```bash
python -m lathe.cli telemetry status
```

The config file path is documented in `lathe/telemetry.py` (check the `CONFIG_PATH` constant for the platform-specific location). On Windows: `%APPDATA%\lathe\telemetry.json`; on Linux/macOS: `~/.config/lathe/telemetry.json`.

Inspect what the build actually sent by running a build with network capture:

```bash
python -m lathe.cli build examples/courier_drone.lth courier_drone --out dist
# Compare actual outbound requests against the schema in docs/telemetry.md
```

Review `lathe/telemetry.py` to confirm: telemetry must gate every outbound call behind an explicit `opt_in: true` check. Any code path that sends data without that check is a bug.

**If the user's report is confirmed (telemetry sent while opt-in was disabled, or sent undocumented fields):**

This is **P0**. It is a release blocker per trigger #3 in `docs/support/readiness-checklist.md`.

## Mitigation

1. **If confirmed P0:** initiate rollback per `docs/release/rollback-plan-v0.2.0rc1.md`. Yank the release from PyPI. Post an advisory per SECURITY.md.
2. **If the user's local config is the issue** (e.g., a previous install left telemetry enabled): guide them to run `lathe telemetry disable` and `lathe telemetry clear`.
3. **If undocumented fields were sent:** patch `lathe/telemetry.py` to remove the extra fields and update `docs/telemetry.md`. Issue a patch release.

## Communication

Do not dismiss the complaint publicly before investigation. Acknowledge within 24 h. If confirmed P0, follow the GHSA + rollback communication chain in `docs/release/rollback-plan-v0.2.0rc1.md`. Escalate to `requires-human` + counsel immediately if personal data (anything beyond the documented schema) was transmitted.

## Escalation

**Any confirmed telemetry transmission without consent is P0 and a launch blocker.** Do not continue any wider distribution until the root cause is identified and patched.

## Postmortem trigger

Any confirmed privacy incident, including confirmed data collection beyond the documented schema.
