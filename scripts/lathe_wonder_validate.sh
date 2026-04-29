#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ -n "${PYTHON_BIN:-}" ]]; then
  PYTHON="$PYTHON_BIN"
elif [[ -x "$ROOT_DIR/.venv/Scripts/python.exe" ]]; then
  PYTHON="$ROOT_DIR/.venv/Scripts/python.exe"
elif [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
  PYTHON="$ROOT_DIR/.venv/bin/python"
else
  PYTHON="python"
fi

EXAMPLE_DIR="${WONDER_EXAMPLE_DIR:-examples/wonder/alchemist_observatory}"
if [[ -n "${WONDER_WORK_DIR:-}" ]]; then
  WORK_DIR="$WONDER_WORK_DIR"
else
  WORK_DIR=".tmp_tests/wonder_validate_$$_$(date +%Y%m%d%H%M%S)"
fi
PYTEST_ARGS=(
  -q
  tests/unit/test_wonder_brief_lowering.py
  tests/unit/test_wonder_contracts.py
  tests/unit/test_wonder_memory.py
  tests/unit/test_wonder_scene_validation.py
  tests/unit/test_wonder_schema_reference_docs.py
  tests/unit/test_scene_cli.py
  tests/unit/test_scene_ids.py
  tests/unit/test_scene_package_manifest.py
  tests/unit/test_scene_patch.py
  tests/unit/test_scene_planner.py
  tests/unit/test_scene_source_roundtrip.py
  tests/unit/test_scene_executor.py
  tests/unit/test_scene_io.py
  tests/unit/test_scene_assembly.py
  tests/unit/test_scene_versioning.py
  tests/unit/test_scene_repair.py
  tests/unit/test_scene_curiosity.py
  tests/unit/test_scene_validators.py
  tests/unit/test_scene_bench.py
  tests/unit/test_scene_roblox.py
  tests/unit/test_scene_style_layout.py
  tests/unit/test_scene_game_readiness_provenance.py
  tests/unit/test_wonder_llm.py
)

run_step() {
  local title="$1"
  shift
  echo
  echo "== $title =="
  echo "$PYTHON $*"
  "$PYTHON" "$@"
}

BRIEF="$EXAMPLE_DIR/dream_brief.json"
SCENE="$EXAMPLE_DIR/scene_graph.json"
PATCH="$EXAMPLE_DIR/scene_patch_more_sacred.json"
RENDER_INSPECTION="$EXAMPLE_DIR/render_inspection.example.json"
WORLD_MEMORY="$EXAMPLE_DIR/world_memory.json"
EXPECTED_SCENE_MANIFEST="$EXAMPLE_DIR/expected/scene_manifest.example.json"
EXPECTED_WONDER_REPORT="$EXAMPLE_DIR/expected/wonder_report.example.json"
ROBLOX_EXAMPLE_DIR="examples/wonder/abandoned_roblox_mall"
ROBLOX_SCENE="$ROBLOX_EXAMPLE_DIR/scene_graph.json"
ROBLOX_PROFILE="$ROBLOX_EXAMPLE_DIR/roblox_profile.json"
ROBLOX_MANIFEST="$WORK_DIR/wonder_roblox_manifest.json"
ROBLOX_ASSET_KIT="$WORK_DIR/roblox_asset_kit/abandoned_roblox_mall"
LOWERED_SCENE="$WORK_DIR/wonder_lower/alchemist_observatory.scene_graph.json"
SCENE_PLAN="$WORK_DIR/wonder_scene_plan.json"
SCENE_ASSEMBLY="$WORK_DIR/wonder_scene_assembly.json"
SCENE_BRANCH="$WORK_DIR/wonder_scene_branch.json"
SCENE_DIFF="$WORK_DIR/wonder_scene_diff.json"
REPAIR_REPORT="$WORK_DIR/wonder_repair_report.json"
REPAIRED_SCENE="$WORK_DIR/wonder_repaired_scene.json"
EXPANDED_SCENE="$WORK_DIR/wonder_expanded_scene.json"
BENCHMARK_TIMINGS="$WORK_DIR/wonder_benchmark_timings.json"
BENCHMARK_SCORES="$WORK_DIR/wonder_benchmark_scores.json"
BENCHMARK_REPORT="$WORK_DIR/wonder_benchmark_report.json"
SEMANTIC_PATCH_REQUEST="$WORK_DIR/wonder_semantic_patch_request.json"
SEMANTIC_PATCH="$WORK_DIR/wonder_semantic_patch.json"
LLM_SUMMARY="$WORK_DIR/wonder_llm_diagnostics.json"
STYLE_PACK="$WORK_DIR/wonder_style_pack.json"
LAYOUT_PLAN="$WORK_DIR/wonder_layout_plan.json"
CAMERA_LIGHTING_PLAN="$WORK_DIR/wonder_camera_lighting_plan.json"
GAME_READINESS="$WORK_DIR/wonder_game_readiness.json"
ASSET_PROVENANCE="$WORK_DIR/wonder_asset_provenance.json"
SCENE_SOURCE="$WORK_DIR/wonder_source/alchemist_observatory.scene.lth"
ROUNDTRIP_SCENE="$WORK_DIR/wonder_source/alchemist_observatory.roundtrip.scene_graph.json"
PATCHED_SCENE="$WORK_DIR/wonder_patch/alchemist_observatory.patched.scene_graph.json"
PACKAGE_DIR="$WORK_DIR/wonder_package"
BUILD_DIR="$WORK_DIR/wonder_scene_build"
RENDER_DIR="$WORK_DIR/wonder_scene_render"
EXPORT_DIR="$WORK_DIR/wonder_scene_export"

echo "Lathe Wonder schema and package validation"
echo "Example: $EXAMPLE_DIR"
echo "Work dir: $WORK_DIR"

mkdir -p "$WORK_DIR"
cat > "$BENCHMARK_TIMINGS" <<'JSON'
{
  "stages": {
    "brief": {"duration_ms": 1000},
    "scene_graph": {"duration_ms": 2000},
    "source_generation": {"duration_ms": 1000},
    "check_plan": {"duration_ms": 500},
    "preview_build": {"duration_ms": 5000},
    "preview_render": {"duration_ms": 1000},
    "patch_preview": {"duration_ms": 1000},
    "final_export": {"duration_ms": 1000}
  },
  "cache": {"hits": 1, "misses": 1, "writes": 1}
}
JSON
cat > "$BENCHMARK_SCORES" <<'JSON'
{
  "metrics": {
    "prompt_to_brief": 0.9,
    "brief_to_scene": 0.9,
    "parse_check": 1.0,
    "build_success": 1.0,
    "scene_validation": 0.9,
    "style_consistency": 0.9,
    "object_count_accuracy": 0.9,
    "render_quality": 0.9,
    "patch_success": 1.0,
    "continuity_preservation": 0.9,
    "export_validity": 1.0
  }
}
JSON
cat > "$SEMANTIC_PATCH_REQUEST" <<'JSON'
{
  "scope": "object",
  "target_id": "obj_astrolabe_table_001",
  "instruction": "Make the table more sacred and less industrial."
}
JSON
cat > "$GAME_READINESS" <<'JSON'
{
  "schema_version": "lathe.game_readiness.v1",
  "scene_id": "alchemist_observatory",
  "target": "generic_game",
  "objects": [
    {
      "object_id": "obj_astrolabe_table_001",
      "mobility": "static",
      "interactable": true,
      "collision": {"type": "box", "required": true},
      "pivot": {"mode": "base_center"}
    }
  ]
}
JSON
cat > "$ASSET_PROVENANCE" <<'JSON'
{
  "schema_version": "lathe.asset_provenance_scene.v1",
  "scene_id": "alchemist_observatory",
  "objects": [
    {
      "object_id": "obj_astrolabe_table_001",
      "provenance": {
        "source": "deterministic_lathe",
        "commercial_use": true,
        "export_permission": "allowed"
      },
      "content_safety": {"status": "passed", "categories": ["environment_prop"]},
      "brand_ip": {"status": "cleared"},
      "user_upload": {"present": false, "safety_status": "passed"}
    }
  ],
  "exports": [
    {
      "target": "scene_package",
      "path": "exports/alchemist_observatory.lathepkg",
      "permission": "allowed",
      "source_object_ids": ["obj_astrolabe_table_001"]
    }
  ]
}
JSON

run_step "Run Wonder contract and scene validation tests" -m pytest "${PYTEST_ARGS[@]}"
run_step "Regenerate Wonder schema reference" scripts/generate_wonder_schema_reference.py
run_step "Emit Wonder capabilities" -m lathe.cli wonder capabilities
run_step "Emit Wonder readiness status" -m lathe.cli wonder status
run_step "Validate Alchemist Observatory Dream Brief" -m lathe.cli wonder validate-brief "$BRIEF"
run_step "Decompose Alchemist Observatory Dream Brief" -m lathe.cli wonder decompose-brief "$BRIEF"
run_step "Lower Alchemist Observatory Dream Brief" -m lathe.cli wonder lower-brief "$BRIEF" --out "$LOWERED_SCENE"
run_step "Check Lowered Alchemist Observatory Scene Graph semantics" -m lathe.cli wonder check-scene-graph "$LOWERED_SCENE"
run_step "Check Brief and Scene consistency" -m lathe.cli wonder check-brief-scene "$BRIEF" "$SCENE"
run_step "Validate Alchemist Observatory Scene Graph schema" -m lathe.cli wonder validate-scene "$SCENE"
run_step "Check Alchemist Observatory Scene Graph semantics" -m lathe.cli wonder check-scene-graph "$SCENE"
run_step "Validate Alchemist Observatory expected Scene Manifest" -m lathe.cli wonder validate-scene-manifest "$EXPECTED_SCENE_MANIFEST"
run_step "Validate Alchemist Observatory expected Wonder Report" -m lathe.cli wonder validate-wonder-report "$EXPECTED_WONDER_REPORT"
run_step "Check Alchemist Observatory scene through scene CLI" -m lathe.cli scene check "$SCENE"
run_step "Plan Alchemist Observatory scene" -m lathe.cli scene plan "$SCENE" --mode preview --out "$SCENE_PLAN"
run_step "Validate Alchemist Observatory Scene Plan" -m lathe.cli wonder validate-plan "$SCENE_PLAN"
run_step "Benchmark Alchemist Observatory Wonder path" -m lathe.cli scene bench "$SCENE" --timings "$BENCHMARK_TIMINGS" --scores "$BENCHMARK_SCORES" --out "$BENCHMARK_REPORT"
run_step "Validate Alchemist Observatory Benchmark Report" -m lathe.cli wonder validate-scene-benchmark-report "$BENCHMARK_REPORT"
run_step "Extract Alchemist Observatory Style Pack" -m lathe.cli scene style-pack "$SCENE" --out "$STYLE_PACK"
run_step "Validate Alchemist Observatory Style Pack" -m lathe.cli wonder validate-style-pack "$STYLE_PACK"
run_step "Plan Alchemist Observatory Layout" -m lathe.cli scene layout "$SCENE" --style-pack "$STYLE_PACK" --out "$LAYOUT_PLAN"
run_step "Validate Alchemist Observatory Layout Plan" -m lathe.cli wonder validate-layout-plan "$LAYOUT_PLAN"
run_step "Plan Alchemist Observatory Camera and Lighting" -m lathe.cli scene camera-lighting "$SCENE" --layout-plan "$LAYOUT_PLAN" --out "$CAMERA_LIGHTING_PLAN"
run_step "Validate Game Readiness metadata" -m lathe.cli wonder validate-game-readiness "$GAME_READINESS"
run_step "Validate Asset Provenance metadata" -m lathe.cli wonder validate-asset-provenance-scene "$ASSET_PROVENANCE"
run_step "Assemble Alchemist Observatory scene IR" -m lathe.cli scene assemble "$SCENE" --out "$SCENE_ASSEMBLY"
run_step "Validate Alchemist Observatory Scene Assembly IR" -m lathe.cli wonder validate-scene-assembly "$SCENE_ASSEMBLY"
run_step "Branch Alchemist Observatory scene" -m lathe.cli scene branch "$SCENE" --name archive_expansion --out "$SCENE_BRANCH"
run_step "Validate Alchemist Observatory Scene Branch" -m lathe.cli wonder validate-scene-branch "$SCENE_BRANCH"
run_step "Diff Alchemist Observatory scene against itself" -m lathe.cli scene diff "$SCENE" "$SCENE" --out "$SCENE_DIFF"
run_step "Validate Alchemist Observatory Scene Diff" -m lathe.cli wonder validate-scene-diff "$SCENE_DIFF"
run_step "Validate Alchemist Observatory scene quality" -m lathe.cli scene validate "$SCENE"
run_step "Validate Alchemist Observatory Scene Patch" -m lathe.cli wonder validate-patch "$PATCH"
run_step "Diagnose Alchemist Observatory Scene Patch for LLM" -m lathe.cli wonder diagnose-for-llm "$PATCH" --contract scene_patch --out "$LLM_SUMMARY"
run_step "Apply Semantic Patch Request for LLM" -m lathe.cli wonder apply-semantic-patch "$SEMANTIC_PATCH_REQUEST" --scene-graph "$SCENE" --out "$SEMANTIC_PATCH"
run_step "Validate LLM-authored Semantic Scene Patch" -m lathe.cli wonder validate-patch "$SEMANTIC_PATCH"
run_step "Preview Alchemist Observatory Scene Patch" -m lathe.cli scene patch "$SCENE" "$PATCH" --out "$PATCHED_SCENE" --preview
run_step "Apply Alchemist Observatory Scene Patch" -m lathe.cli scene patch "$SCENE" "$PATCH" --out "$PATCHED_SCENE"
run_step "Validate Patched Alchemist Observatory Scene Graph" -m lathe.cli wonder check-scene-graph "$PATCHED_SCENE"
run_step "Validate Alchemist Observatory Render Inspection" -m lathe.cli wonder validate-render-inspection "$RENDER_INSPECTION"
run_step "Inspect Alchemist Observatory Render Inspection semantically" -m lathe.cli scene inspect-render "$SCENE" "$RENDER_INSPECTION"
run_step "Propose Alchemist Observatory repairs" -m lathe.cli scene propose-repairs "$SCENE" "$RENDER_INSPECTION" --out "$REPAIR_REPORT"
run_step "Validate Alchemist Observatory Repair Report" -m lathe.cli wonder validate-scene-repair-report "$REPAIR_REPORT"
run_step "Repair Alchemist Observatory offline" -m lathe.cli scene repair "$SCENE" "$RENDER_INSPECTION" --out "$REPAIRED_SCENE" --report-out "$REPAIR_REPORT"
run_step "Validate Repaired Alchemist Observatory Scene Graph" -m lathe.cli wonder check-scene-graph "$REPAIRED_SCENE"
run_step "Validate Alchemist Observatory World Memory" -m lathe.cli wonder validate-world-memory "$WORLD_MEMORY" --scene-graph "$SCENE"
run_step "Summarize Alchemist Observatory curiosity anchors" -m lathe.cli scene curiosity "$SCENE"
run_step "Expand Alchemist Observatory curiosity anchor" -m lathe.cli scene expand-anchor "$SCENE" curiosity_warm_lens --option opened_archive --out "$EXPANDED_SCENE"
run_step "Validate Expanded Alchemist Observatory Scene Graph" -m lathe.cli wonder check-scene-graph "$EXPANDED_SCENE"
run_step "Generate Alchemist Observatory scene source bridge" -m lathe.cli scene scene-graph-to-source "$SCENE" --out "$SCENE_SOURCE"
run_step "Roundtrip Alchemist Observatory scene source bridge" -m lathe.cli scene source-to-scene-graph "$SCENE_SOURCE" --out "$ROUNDTRIP_SCENE"
run_step "Validate Roundtripped Alchemist Observatory Scene Graph" -m lathe.cli wonder check-scene-graph "$ROUNDTRIP_SCENE"
run_step "Initialize Scene Package skeleton" -m lathe.cli scene package init "$PACKAGE_DIR" --scene-id alchemist_observatory --force
run_step "Inspect Scene Package skeleton" -m lathe.cli scene package inspect "$PACKAGE_DIR"
run_step "Validate Scene Package Manifest" -m lathe.cli scene package validate "$PACKAGE_DIR"
run_step "Render Alchemist Observatory proxy PNG passes" -m lathe.cli scene render "$SCENE" --out "$RENDER_DIR" --camera camera_reveal --passes beauty,object_id --width 640 --height 360
run_step "Export Alchemist Observatory proxy GLB" -m lathe.cli scene export "$SCENE" --out "$EXPORT_DIR" --target glb
run_step "Build Alchemist Observatory proxy Scene Package" -m lathe.cli scene build "$SCENE" --out "$BUILD_DIR" --mode preview
run_step "Validate Built Alchemist Observatory Scene Package" -m lathe.cli scene package validate "$BUILD_DIR/alchemist_observatory"
echo
echo "== Validate proxy Scene Package artifact contract =="
"$PYTHON" - "$BUILD_DIR/alchemist_observatory" <<'PY'
import json
import sys
from pathlib import Path

package_dir = Path(sys.argv[1])
manifest = json.loads((package_dir / "scene_package_manifest.json").read_text(encoding="utf-8"))
scene_plan = json.loads((package_dir / "reports" / "scene_plan.json").read_text(encoding="utf-8"))
export_report = json.loads((package_dir / "reports" / "scene_export_artifacts.json").read_text(encoding="utf-8"))
renders = list(manifest.get("renders", []))
glb_entries = [entry for entry in manifest.get("exports", []) if entry.get("target") == "glb"]
planned_render_tasks = list(scene_plan.get("render_tasks", []))
planned_glb_tasks = [
    entry
    for entry in scene_plan.get("export_tasks", [])
    if entry.get("target") == "glb" or entry.get("format") == "glb"
]
glb_artifacts = [entry for entry in export_report.get("artifacts", []) if entry.get("target") == "glb"]
if not renders:
    raise SystemExit("Built scene package has no render entries.")
actual_render_pairs = {
    (entry.get("camera_id"), render_pass)
    for entry in renders
    for render_pass in entry.get("passes", [])
}
for task in planned_render_tasks:
    for render_pass in task.get("passes", []):
        pair = (task.get("camera_id"), render_pass)
        if pair not in actual_render_pairs:
            raise SystemExit(f"Missing planned render artifact: {pair}")
if len(glb_entries) != len(planned_glb_tasks) or len(glb_artifacts) != len(planned_glb_tasks):
    raise SystemExit("Built GLB exports do not match planned GLB export tasks.")
manifest_glb_paths = {entry["path"] for entry in glb_entries}
planned_glb_task_ids = {entry["task_id"] for entry in planned_glb_tasks}
for artifact in glb_artifacts:
    if artifact.get("status") != "built":
        raise SystemExit(f"GLB artifact is not built: {artifact.get('path')}")
    if artifact.get("identity", {}).get("status") != "passed":
        raise SystemExit(f"GLB identity validation failed for: {artifact.get('path')}")
    if artifact.get("path") not in manifest_glb_paths:
        raise SystemExit(f"GLB artifact is missing from package manifest exports: {artifact.get('path')}")
    if artifact.get("task_id") not in planned_glb_task_ids:
        raise SystemExit(f"GLB artifact does not match a planned export task: {artifact.get('task_id')}")
print("Proxy artifact contract passed.")
PY
run_step "Validate Roblox low-poly profile" -m lathe.cli wonder validate-roblox-profile "$ROBLOX_PROFILE"
run_step "Build Roblox manifest" -m lathe.cli scene roblox-manifest "$ROBLOX_SCENE" --profile "$ROBLOX_PROFILE" --out "$ROBLOX_MANIFEST"
run_step "Validate Roblox manifest" -m lathe.cli wonder validate-roblox-manifest "$ROBLOX_MANIFEST"
run_step "Export Roblox asset-kit bundle" -m lathe.cli scene roblox-export "$ROBLOX_SCENE" --profile "$ROBLOX_PROFILE" --out "$ROBLOX_ASSET_KIT"

echo
echo "Lathe Wonder schema and package validation passed."
