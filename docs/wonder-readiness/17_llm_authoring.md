# LLM Authoring

Wave 4 makes the Wonder authoring loop usable without depending on an external
LLM provider. The implemented surface is deterministic and offline:

- `python -m lathe.cli wonder generate-scene-plan ...` writes a schema-valid
  `lathe.scene_plan.v1` payload from a Dream Brief and optional Scene Graph.
- `python -m lathe.cli wonder repair-playbook ...` converts diagnostics into a
  `lathe.llm_repair_playbook.v1` payload for repair loops.
- [LLM schema links](../llm/schema_links.md) list canonical contract files for
  prompts and tool adapters.
- [Bad-output fixtures](../llm/bad_outputs/) pin expected diagnostic categories
  for invalid Scene Plans, Scene Patches, generated scene source, and unredacted
  memory payloads.
- Generated scene source diagnostics now carry source spans when the embedded
  JSON pointer can be mapped truthfully.

Remaining outside Wave 4:

- No external LLM call or model-provider orchestration.
- No full hand-authored scene-language parser beyond the generated JSON-first
  source bridge.
- No semantic visual repair certainty; render comparison remains the proxy
  deterministic lane from Wave 3.

Use [generate_scene_plan.md](../llm/generate_scene_plan.md) and
[repair_playbook.md](../llm/repair_playbook.md) for command contracts.

