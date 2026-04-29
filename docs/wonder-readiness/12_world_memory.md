# World Memory

World Memory is the local continuity artifact for Project Wonder scenes. It is
not the long-term Project Wonder product database. Lathe owns the portable
`lathe.world_memory.v1` contract, validation, package location, and CLI helpers
needed to keep scene facts tied to stable IDs.

## What It Stores

A World Memory file records:

- scene facts from prompts, briefs, generated lore, and validation results;
- user or agent decisions;
- hidden state that should not be visible in a first render;
- branch metadata;
- memory events;
- affected scene IDs such as object, region, camera, curiosity, and hidden
  state IDs;
- continuity constraints used by patch, rollback, and branch flows.

Packages store the memory artifact at:

```text
graph/world_memory.json
```

## Validation Rules

Memory validation checks that:

- the schema is `lathe.world_memory.v1`;
- the memory scene ID agrees with the Scene Graph when one is supplied;
- event IDs are unique;
- branch event references point at known events;
- affected IDs use valid Scene Graph reference prefixes;
- affected IDs exist in the supplied Scene Graph when the caller asks for
  graph-aware validation.

The CLI path is:

```bash
python -m lathe.cli wonder validate-world-memory graph/world_memory.json --scene-graph graph/scene_graph.json
python -m lathe.cli scene memory inspect graph/world_memory.json --scene-graph graph/scene_graph.json
```

## Append And Redaction Behavior

`lathe scene memory append <package> <event.json>` appends a memory event to the
package memory file. Appends are idempotent by event ID: rerunning the same
event does not duplicate the record.

Before an event is persisted, memory payload text is redacted for common secret
and personal-data shapes. Redaction preserves the event structure while
removing sensitive values from the stored text.

Rejected scene patches can also be recorded as memory events so a future
Wonder loop can remember that an edit was reviewed and declined instead of
repeating it.

## Runtime Boundary

World Memory helps Lathe keep local scene continuity. It does not own:

- user accounts;
- cross-project app memory;
- chat history;
- billing state;
- social sharing;
- cloud orchestration;
- model provider routing.

Those concerns belong to the Project Wonder application layer.

## Tests

Current coverage lives in:

- `tests/unit/test_wonder_memory.py`;
- `tests/unit/test_scene_cli.py`;
- `tests/unit/test_scene_history.py`;
- `tests/unit/test_scene_rollback.py`.
