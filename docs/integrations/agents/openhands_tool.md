# OpenHands tool registration: `lathe`

**Status.** Targeting Month-5 (V0.6) OpenHands tool-directory submission (see `docs/roadmap_public.md` § Persona-C GTM). OpenHands (formerly OpenDevin) uses a different integration model from Claude Code / Continue / Cursor: tools are explicitly registered with JSON schema, and the agent's planner picks them by signature, not by rule-matching.

## Why OpenHands specifically

OpenHands is the most popular open-source coding-agent framework, and its users skew toward the exact population that cares about reproducibility and CI-friendliness — i.e., Persona B territory crossed with Persona C. A registered tool here is more valuable than a rules file because it shows up in the planner's action space directly.

## Tool registration (target JSON schema)

```json
{
  "name": "lathe_build",
  "description": "Build a certified game-ready 3D asset from a Lathe `.lth` source. Runs check -> plan -> build; emits a `.glb` plus package_manifest.json and trace_manifest.json. Use when the user asks to certify, build, or validate a 3D asset and a `.lth` source exists in the workspace.",
  "parameters": {
    "type": "object",
    "properties": {
      "source": {
        "type": "string",
        "description": "Path to the `.lth` source file, relative to workspace root."
      },
      "asset_id": {
        "type": "string",
        "description": "Asset id inside the source (e.g. `industrial_crate`, `courier_drone_mobile`)."
      },
      "out_dir": {
        "type": "string",
        "description": "Output directory (default: `dist`)."
      },
      "runtime_config": {
        "type": "string",
        "description": "Optional path to a runtime-config JSON. Omit for conservative fallback path."
      }
    },
    "required": ["source", "asset_id"]
  },
  "returns": {
    "type": "object",
    "properties": {
      "status": { "type": "string", "enum": ["pass", "fail"] },
      "artifacts": {
        "type": "array",
        "items": { "type": "string" },
        "description": "Paths to emitted artifacts (`.glb`, manifest, trace)."
      },
      "trace_path": { "type": "string" },
      "failure": {
        "type": "object",
        "description": "Present only when status=fail.",
        "properties": {
          "stage": { "type": "string" },
          "rule": { "type": "string" },
          "value": {},
          "source_location": { "type": "string" }
        }
      }
    }
  }
}
```

The companion `lathe_check` tool registers the same shape with `status` + `failure`, no artifacts — used as a fast pre-flight.

## Why pass/fail is typed

OpenHands' planner is schema-driven. If Lathe emitted free-form stdout, the planner would pattern-match against strings and get it wrong on provider-fallback edge cases. Typing `status: pass|fail` and `failure.stage|rule|value` gives the planner a verdict it can branch on without an LLM hop, which is the entire Persona-C value proposition condensed into a JSON shape.

## Tool implementation sketch

The tool body shells out to the CLI:

```python
# openhands_plugins/lathe/tool.py (sketch)
import json, subprocess, pathlib

def lathe_build(source, asset_id, out_dir="dist", runtime_config=None):
    cmd = ["python", "-m", "lathe.cli", "build", source, asset_id, "--out", out_dir]
    if runtime_config:
        cmd += ["--runtime-config", runtime_config]
    p = subprocess.run(cmd, capture_output=True, text=True)
    trace_path = pathlib.Path(out_dir) / asset_id / "stages" / "package" / "trace_manifest.json"
    if p.returncode == 0 and trace_path.exists():
        trace = json.loads(trace_path.read_text())
        return {"status": "pass", "artifacts": _list_artifacts(out_dir, asset_id),
                "trace_path": str(trace_path)}
    return {"status": "fail", "failure": _parse_failure(p.stderr)}
```

`_parse_failure` parses the `[stage:rule] value (reason) at: file:line` format the CLI already emits. That format is the stable contract; if we change it, this adapter updates in lockstep.

## Expected planner behavior

Given a task like *"apply the V0.8 surface lane to `sci_fi_wall_panel` and certify"*:

1. Planner sees `lathe_check` and `lathe_build` in its action space.
2. Calls `lathe_check(source=…, asset_id=…)` first.
3. On `status=pass`, calls `lathe_build`.
4. Reads `trace_path`, cites provider `attempted`/`actual`.
5. On `status=fail`, reads `failure.stage` + `failure.rule`, proposes a source edit, loops.

The planner never asks the human to eyeball the mesh.

## Submission to the OpenHands tool directory

- Repo pattern: OpenHands accepts tools via `openhands/plugins/<name>/` PRs.
- Maintainer: Lathe core team until co-maintainers onboard.
- Sandboxing: the tool runs `python -m lathe.cli` inside OpenHands' existing sandbox. No special privileges; no network unless a runtime-config references a hosted provider (Hunyuan HTTP, etc.).

## Honest limits

- OpenHands planners vary in quality. If the planner picks `lathe_build` before `lathe_check`, the build still succeeds or fails correctly — it just pays the build-latency cost. The tool description recommends the order, but does not enforce it.
- Runtime configs that hit network providers are out of scope for sandboxed default execution. Users opt in per task.

## Cross-references

- `docs/integrations/agents/devin_tool.md` — sibling directory listing.
- `docs/integrations/agents/agents_md_listing.md` — generic spec.
- `docs/integrations/agents/claude_code_skill.md`, `continue_rules.md`, `cursor_rules.md` — per-framework equivalents.
- `docs/personas.md` § Persona C.
- `docs/roadmap_public.md` § Persona-C GTM (Month 5).
