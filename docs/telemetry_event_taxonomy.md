# Lathe telemetry event taxonomy (v1)

> **Status:** Telemetry remains DISABLED by default in v0.2.0rc1. This taxonomy describes what would be emitted if a user opts in via `lathe telemetry enable`. No data is collected unless the user explicitly enables telemetry.

---

## Current code state

Telemetry lives in `lathe/telemetry.py`. The module contains a complete opt-in implementation with one event type (`build_ping`). Config is persisted at an OS-appropriate path (`%APPDATA%\lathe\telemetry.json` on Windows; `~/.config/lathe/telemetry.json` on POSIX; `~/Library/Application Support/lathe/telemetry.json` on macOS). The `platformdirs` package is used when available; a hand-rolled fallback covers the three platforms.

Ingest endpoint: `https://telemetry.lathe.dev/ingest` (POST, JSON). The ingest service is not yet provisioned — see Dashboards section.

---

## Events

### `build_ping`

The only event currently implemented.

| Field | Type | Description |
|---|---|---|
| `lathe_version` | `str` | Package version (from `lathe.__version__`) |
| `build_id_hash` | `str` | `sha256(user_salt + build_id)[:16]` — anonymous; cannot be reversed without local salt |
| `build_kind` | `str` | Value of `build_report["kind"]` (e.g. `"generate"`, `"reconstruct"`) |
| `stack_id` | `str` | Backend stack ID (e.g. `lathe.stack.hard_surface_game_asset_v1`) |
| `certified` | `bool \| null` | Whether the build report indicates certification passed |
| `exit_code` | `int` | `0` = success, non-zero = failure |
| `wall_ms` | `int` | Build wall-clock time in milliseconds |

**Allowlisted fields** (sent): all seven fields above.

**Rejected / never sent:** asset file paths, asset names, raw build IDs, user name or email, environment variables, raw salt, geometry content, any field not in the payload table above. The `_build_payload` function enforces this by constructing the payload from a fixed key set.

**When emitted:** after each `lathe build` run that reaches the `emit_build_ping` call in the CLI, provided telemetry is `enabled` in the config file and a valid `user_salt` is present.

**When NOT emitted:**
- `lathe doctor`, `lathe check`, `lathe plan`, `lathe materialize`, `lathe test`, `lathe bench`, `lathe bridge`, `lathe inspect`, `lathe export-blend`, `lathe telemetry status/enable/disable/clear` — none of these call `emit_build_ping`.
- Telemetry state is `unset` (no config file) or `disabled`.
- Config file exists but `user_salt` is absent (corrupt config).
- Any exception during dispatch — `emit_build_ping` is failure-silent and never raises.
- `lathe.net.safe_urlopen` is not importable (`net` is a soft dependency).

**Privacy design:** `build_id_hash` is derived as `sha256(local_salt + build_id)[:16]`. The `user_salt` stays on the local machine and is never transmitted. Ingest cannot link build identities across users or reconstruct the original build ID without the local salt.

**Dispatch:** sent via `lathe.net.safe_urlopen` with a 2-second timeout and a 64 KB body cap. The request is POST to `https://telemetry.lathe.dev/ingest` with `Content-Type: application/json`. Only `telemetry.lathe.dev` is on the allowlist.

---

## Additional events

No other events are currently implemented. If future events are needed (e.g., `doctor_ping`, `install_ping`, `check_ping`), they must be added to `lathe/telemetry.py` and documented here before shipping.

requires-human: define and implement any additional events before updating this taxonomy.

---

## North-star metric

**Proposed:** "weekly active certified-build users" — a user counts if they ran at least one `lathe build` whose `build_report.json` shows `certified: true` in the past 7 days. This maps directly to the `certified` field in `build_ping` and the `build_id_hash` for deduplication within a week.

requires-human: pending product owner ratification before adoption as the official north-star.

---

## Funnel definitions

| Stage | Definition | Telemetry signal |
|---|---|---|
| Acquisition | User installs Lathe via `pip install lathe` | requires-human: no install ping implemented; would need a separate `install_ping` event |
| Activation | First `lathe doctor` exits 0 | requires-human: no `doctor_ping` event implemented |
| Engagement | First certified `lathe build` (`certified: true` in `build_ping`) | Covered by `build_ping.certified == true` |
| Retention | Second certified build within 7 days of the first | Computable from `build_ping` stream if ingest is live; requires server-side deduplication by `build_id_hash` |
| Revenue | N/A — no monetization shipping in v0.2.0rc1 | — |

---

## Dashboards (status)

None of the following dashboards are provisioned. Telemetry ingest at `https://telemetry.lathe.dev/ingest` is not yet live. All items below are blocked on a hosting and ingest decision.

| Dashboard | Status |
|---|---|
| Build pings (volume + trend) | requires-human: hosted dashboard not yet provisioned; telemetry remains disabled. If dashboards are required before launch, hosting + ingest decisions must land first. |
| Install success rate | requires-human: same as above; additionally requires an `install_ping` event that does not yet exist. |
| Build success rate | requires-human: hosted dashboard not yet provisioned; computable from `exit_code` in `build_ping` once ingest is live. |
| Certification failure rate | requires-human: hosted dashboard not yet provisioned; computable from `certified == false` in `build_ping` once ingest is live. |
| Support volume | requires-human: no support system integrated; out of scope for v0.2.0rc1. |

---

## Data quality checks (deferred until telemetry is live)

These checks are defined for future implementation. None can be enabled until the ingest service is provisioned and telemetry opt-ins exist.

| Check | What it would verify | Status |
|---|---|---|
| Schema drift | Each incoming `build_ping` payload matches the field set and types documented above; alert if unknown fields appear or required fields go missing | requires-human: enable when telemetry ingest is hosted. |
| Null-rate | `build_id_hash`, `stack_id`, and `certified` should not be null or empty string in more than N% of pings; elevated null rate signals a client-side regression | requires-human: enable when telemetry ingest is hosted. |
| Freshness | Ingest pipeline should produce at least one event per 24-hour window once any users are opted in; stale pipeline indicates ingest failure | requires-human: enable when telemetry ingest is hosted. |
