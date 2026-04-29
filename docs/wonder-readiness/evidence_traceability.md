# Wonder Evidence Traceability

`lathe wonder evidence-trace` checks that checked boxes in
`wonder-tasks.md` have durable evidence in
`docs/wonder-readiness/evidence.md`.

The command writes a `lathe.wonder_evidence_trace.v1` JSON report with checked
tasks, parsed evidence items, task-to-evidence coverage, missing evidence, and
diagnostics. Command evidence used to cover a checked task must include a
command, result, status, date, output path, and any referenced output path must
exist.

The current ledger contains a task-box audit decision for the already checked
task state. Future checked tasks should add explicit command, docs, schema,
report, or example-artifact rows so this report remains specific instead of
relying on broad audit evidence.
