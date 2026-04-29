# Good LLM Outputs

These files are model-facing examples for JSON-first Project Wonder authoring.
They are small enough to paste into prompts and strict enough to run through the
same validators as production Scene Graphs.

- [model_good_archive_scene_graph.json](model_good_archive_scene_graph.json)
  is a valid `lathe.scene_graph.v1` payload with stable IDs, object state,
  affordances, hidden state, curiosity, provenance, material bindings, cameras,
  lights, memory, and export metadata.
- [model_good_archive_generated_scene.lth](model_good_archive_generated_scene.lth)
  is the generated Phase 7 scene source bridge for the same payload. The
  readable scene preview is intentionally partial; the embedded JSON payload is
  the durable contract truth.

Run the examples locally with:

```powershell
python -m lathe.cli scene check docs/llm/good_outputs/model_good_archive_scene_graph.json
python -m lathe.cli scene source-to-scene-graph docs/llm/good_outputs/model_good_archive_generated_scene.lth --out .tmp_tests/model_good_archive.roundtrip.json
```
