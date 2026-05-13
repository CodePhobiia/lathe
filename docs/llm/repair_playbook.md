# Repair Playbook

`lathe wonder repair-playbook` turns diagnostics into deterministic repair
steps that an LLM or human can apply before rerunning validation.

```powershell
python -m lathe.cli wonder repair-playbook `
  --diagnostics diagnostics.json `
  --out repair_steps.json
```

Accepted diagnostic inputs:

- a JSON list of diagnostics
- a Wonder report with a `diagnostics` array
- a `lathe.llm_diagnostic_summary.v1` payload from `wonder diagnose-for-llm`

Output contract:

- LLM Repair Playbook: [schema/llm_repair_playbook.schema.json](../schema/llm_repair_playbook.schema.json)

Each step includes the diagnostic code/name, JSON pointer, source span when the
upstream diagnostic provided one, allowed values when available, and a concrete
instruction. Unknown diagnostics do not fail the command; they receive a safe
generic instruction to inspect the path, make the smallest schema-valid edit,
and rerun the relevant validator.

The playbook is guidance, not proof of success. Apply the suggested edit, then
validate the edited payload against the canonical schema or scene validator.

