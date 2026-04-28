# Runbook: Godot Addon Load Failure

Godot 4.x fails to load the Lathe addon from `editors/godot/lathe-addon/`.

**Owner:** Tal Merri (@talmerri). Backup: `requires-human` (macOS/Linux Godot smoke requires a human runner)

## Symptoms

- Godot editor shows "Failed to load script" or "Parse error" in the Output panel when enabling the Lathe addon.
- The certified-state indicator or build-trace dock does not appear after enabling.
- `plugin.cfg` is missing or returns a parse error.

## First response (≤5 min)

1. Ask the user to paste the full Godot Output panel text (not just the error line) and their Godot version.
2. Confirm the addon was installed by copying `editors/godot/lathe-addon/` into `<project>/addons/lathe-addon/` — not via AssetLib (the addon is not on AssetLib for v0.2.0rc1).

## Investigation

Check `plugin.cfg` syntax:

```bash
cat editors/godot/lathe-addon/plugin.cfg
```

Required fields: `name`, `description`, `author`, `version`, `script`. If any are missing or have incorrect types, Godot will reject the plugin.

Check for GDScript parse errors by opening the addon scripts directly in the Godot editor and looking for red underlines. Common issues:

- `@tool` annotation missing from a script that runs in editor.
- Signal or method signature incompatible with the user's Godot minor version (Godot 4.5 vs 4.6 API differences).
- Missing `lathe_snapshot.json` reference — the addon expects the snapshot file at `res://lathe_out/<asset>/.lathe_snapshot.json`.

For the certified-state indicator: see `editors/godot/lathe-addon/` source and the integration walkthrough at `examples/godot_integration_demo/`.

## Mitigation

- **Roll forward (fix):** patch the offending script, copy the updated addon into the user's project, and ask them to re-enable.
- **Disable while triaging:** guide the user to disable the addon via `Project → Project Settings → Plugins → Lathe Integration → Disable`. Their build pipeline continues to work; only the editor integration is affected.

## Communication

Apply Macro: Godot import failure from `docs/support/readiness-checklist.md`. If the failure is a confirmed Godot version regression, open a labeled issue (`bug`, `product-quality`).

## Escalation

Escalates to release blocker under trigger #4 ("certification passes but engine import is broken") in `docs/support/readiness-checklist.md`. If the certified asset loads fine in Godot but the addon itself fails to enable, this is P1 (degraded feature), not P0.

## Postmortem trigger

Any confirmed addon load failure that was present in the published release and was not caught by the pre-release Godot smoke test.
