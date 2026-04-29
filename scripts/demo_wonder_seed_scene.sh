#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON="${PYTHON_BIN:-}"
EXAMPLE_DIR="${WONDER_EXAMPLE_DIR:-examples/wonder/alchemist_observatory}"
OUT_DIR="${LATHE_WONDER_DEMO_OUT:-tmp_wonder_seed_demo}"
DRY_RUN=0
VERBOSE_OUTPUT=0

if [[ -z "$PYTHON" ]]; then
  if [[ -x "$ROOT_DIR/.venv/Scripts/python.exe" ]]; then
    PYTHON="$ROOT_DIR/.venv/Scripts/python.exe"
  elif [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
    PYTHON="$ROOT_DIR/.venv/bin/python"
  else
    PYTHON="python"
  fi
fi

while [[ $# -gt 0 ]]; do
  case "$1" in
    --python) PYTHON="$2"; shift 2 ;;
    --example-dir) EXAMPLE_DIR="$2"; shift 2 ;;
    --out) OUT_DIR="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    --verbose-output) VERBOSE_OUTPUT=1; shift ;;
    -*) echo "Unknown argument: $1" >&2; exit 2 ;;
    *)
      EXAMPLE_DIR="$1"
      shift
      ;;
  esac
done

EVIDENCE_DIR="$OUT_DIR/_demo_evidence"
SOURCE_DIR="$EVIDENCE_DIR/source_bridge"
BRIEF_DIR="$EVIDENCE_DIR/brief_lowering"
PATCH_DIR="$EVIDENCE_DIR/patch"
REPAIR_DIR="$EVIDENCE_DIR/repair"
CURIOSITY_DIR="$EVIDENCE_DIR/curiosity"
PREVIEW_BUILD_ROOT="$OUT_DIR/preview_build"
PATCHED_BUILD_ROOT="$OUT_DIR/patched_build"
EXPANDED_BUILD_ROOT="$OUT_DIR/expanded_build"
BEFORE_AFTER_DIR="$OUT_DIR/before_after"

if [[ "$DRY_RUN" -eq 0 ]]; then
  mkdir -p "$EVIDENCE_DIR" "$SOURCE_DIR" "$BRIEF_DIR" "$PATCH_DIR" "$REPAIR_DIR" "$CURIOSITY_DIR"
fi

assert_demo_input() {
  local path="$1"
  if [[ ! -e "$path" ]]; then
    echo "Required demo input not found: $path" >&2
    exit 2
  fi
}

run_step() {
  local title="$1"
  local artifact="$2"
  local status=0
  shift
  shift
  echo
  echo "== $title =="
  echo "$PYTHON $*"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    return
  fi
  if [[ -n "$artifact" ]]; then
    local artifact_path="$EVIDENCE_DIR/$artifact"
    mkdir -p "$(dirname "$artifact_path")"
    if [[ "$VERBOSE_OUTPUT" -eq 1 ]]; then
      set +e
      "$PYTHON" "$@" 2>&1 | tee "$artifact_path"
      status="${PIPESTATUS[0]}"
      set -e
    else
      set +e
      "$PYTHON" "$@" >"$artifact_path" 2>&1
      status="$?"
      set -e
    fi
    if [[ "$status" -ne 0 ]]; then
      echo "Command failed. See $artifact_path for details." >&2
      exit "$status"
    fi
    echo "Saved output: $artifact_path"
  else
    "$PYTHON" "$@"
  fi
}

BRIEF="$EXAMPLE_DIR/dream_brief.json"
SCENE="$EXAMPLE_DIR/scene_graph.json"
PATCH="$EXAMPLE_DIR/scene_patch_more_sacred.json"
RENDER_INSPECTION="$EXAMPLE_DIR/render_inspection.example.json"
WORLD_MEMORY="$EXAMPLE_DIR/world_memory.json"
SCENE_SOURCE="$SOURCE_DIR/alchemist_observatory.scene.lth"
ROUNDTRIP_SCENE="$SOURCE_DIR/alchemist_observatory.roundtrip.scene_graph.json"
LOWERED_SCENE="$BRIEF_DIR/alchemist_observatory.lowered.scene_graph.json"
SCENE_PLAN="$EVIDENCE_DIR/scene_plan.json"
SCENE_ASSEMBLY="$EVIDENCE_DIR/scene_assembly.json"
PATCHED_SCENE="$PATCH_DIR/alchemist_observatory.more_sacred.scene_graph.json"
REPAIR_REPORT="$REPAIR_DIR/scene_repair_report.json"
REPAIRED_SCENE="$REPAIR_DIR/alchemist_observatory.repaired.scene_graph.json"
EXPANDED_SCENE="$CURIOSITY_DIR/alchemist_observatory.opened_archive.scene_graph.json"

assert_demo_input "$BRIEF"
assert_demo_input "$SCENE"
assert_demo_input "$PATCH"
assert_demo_input "$RENDER_INSPECTION"
assert_demo_input "$WORLD_MEMORY"

echo "Lathe Wonder seed scene demo"
echo "Example: $EXAMPLE_DIR"
echo "Output:  $OUT_DIR"
echo "Mode:    deterministic proxy package path"

run_step "Emit Wonder capabilities" "00_capabilities.json" -m lathe.cli wonder capabilities
run_step "Validate Dream Brief schema" "01_validate_brief.json" -m lathe.cli wonder validate-brief "$BRIEF"
run_step "Decompose Dream Brief" "02_decompose_brief.json" -m lathe.cli wonder decompose-brief "$BRIEF"
run_step "Lower Dream Brief to fallback Scene Graph" "03_lower_brief.json" -m lathe.cli wonder lower-brief "$BRIEF" --out "$LOWERED_SCENE"
run_step "Check lowered fallback Scene Graph" "04_check_lowered_scene.json" -m lathe.cli wonder check-scene-graph "$LOWERED_SCENE"
run_step "Validate authored Scene Graph schema" "05_validate_scene.json" -m lathe.cli wonder validate-scene "$SCENE"
run_step "Check authored Scene Graph semantics" "06_check_scene_graph.json" -m lathe.cli wonder check-scene-graph "$SCENE"
run_step "Check Dream Brief and Scene Graph consistency" "07_check_brief_scene.json" -m lathe.cli wonder check-brief-scene "$BRIEF" "$SCENE"
run_step "Generate JSON-first scene source bridge" "08_scene_graph_to_source.txt" -m lathe.cli scene scene-graph-to-source "$SCENE" --out "$SCENE_SOURCE"
run_step "Roundtrip scene source bridge to Scene Graph" "09_source_to_scene_graph.txt" -m lathe.cli scene source-to-scene-graph "$SCENE_SOURCE" --out "$ROUNDTRIP_SCENE"
run_step "Check roundtripped Scene Graph" "10_check_roundtrip_scene.json" -m lathe.cli wonder check-scene-graph "$ROUNDTRIP_SCENE"
run_step "Plan preview scene build" "11_scene_plan_cli.txt" -m lathe.cli scene plan "$SCENE" --mode preview --out "$SCENE_PLAN"
run_step "Validate preview Scene Plan" "12_validate_scene_plan.json" -m lathe.cli wonder validate-plan "$SCENE_PLAN"
run_step "Assemble scene IR" "13_scene_assembly_cli.txt" -m lathe.cli scene assemble "$SCENE" --out "$SCENE_ASSEMBLY"
run_step "Validate scene assembly IR" "14_validate_scene_assembly.json" -m lathe.cli wonder validate-scene-assembly "$SCENE_ASSEMBLY"
run_step "Validate authored World Memory" "15_validate_world_memory.json" -m lathe.cli wonder validate-world-memory "$WORLD_MEMORY" --scene-graph "$SCENE"
run_step "Run scene quality validators" "16_scene_quality_report.json" -m lathe.cli scene validate "$SCENE"
run_step "Build proxy preview Scene Package" "17_preview_build.txt" -m lathe.cli scene build "$SCENE" --out "$PREVIEW_BUILD_ROOT" --mode preview
run_step "Validate proxy preview Scene Package" "18_validate_preview_package.json" -m lathe.cli scene package validate "$PREVIEW_BUILD_ROOT/alchemist_observatory"
run_step "Validate Render Inspection contract" "19_validate_render_inspection.json" -m lathe.cli wonder validate-render-inspection "$RENDER_INSPECTION"
run_step "Inspect Render Inspection against scene" "20_inspect_render.json" -m lathe.cli scene inspect-render "$SCENE" "$RENDER_INSPECTION"
run_step "Propose deterministic offline repairs" "21_propose_repairs.txt" -m lathe.cli scene propose-repairs "$SCENE" "$RENDER_INSPECTION" --out "$REPAIR_REPORT"
run_step "Validate repair report" "22_validate_repair_report.json" -m lathe.cli wonder validate-scene-repair-report "$REPAIR_REPORT"
run_step "Run deterministic offline repair" "23_repair_scene.txt" -m lathe.cli scene repair "$SCENE" "$RENDER_INSPECTION" --out "$REPAIRED_SCENE" --report-out "$REPAIR_REPORT"
run_step "Check repaired Scene Graph" "24_check_repaired_scene.json" -m lathe.cli wonder check-scene-graph "$REPAIRED_SCENE"
run_step "Apply more_sacred Scene Patch" "25_apply_more_sacred_patch.json" -m lathe.cli scene patch "$SCENE" "$PATCH" --out "$PATCHED_SCENE"
run_step "Check patched Scene Graph" "26_check_patched_scene.json" -m lathe.cli wonder check-scene-graph "$PATCHED_SCENE"
run_step "Build patched proxy preview Scene Package" "27_patched_build.txt" -m lathe.cli scene build "$PATCHED_SCENE" --out "$PATCHED_BUILD_ROOT" --mode preview
run_step "Validate patched proxy Scene Package" "28_validate_patched_package.json" -m lathe.cli scene package validate "$PATCHED_BUILD_ROOT/alchemist_observatory"
run_step "Render before/after proxy comparison" "28b_before_after_demo.json" -m lathe.cli wonder demo-before-after "$EXAMPLE_DIR" --out "$BEFORE_AFTER_DIR" --patch "$PATCH" --camera-id camera_reveal
run_step "Validate before/after render comparison" "28c_validate_before_after_comparison.json" -m lathe.cli wonder validate-render-comparison "$BEFORE_AFTER_DIR/comparisons/render_comparison.json"
run_step "Summarize curiosity anchors" "29_curiosity_cards.json" -m lathe.cli scene curiosity "$SCENE"
run_step "Expand opened_archive curiosity anchor" "30_expand_opened_archive.txt" -m lathe.cli scene expand-anchor "$SCENE" curiosity_warm_lens --option opened_archive --out "$EXPANDED_SCENE"
run_step "Check expanded Scene Graph" "31_check_expanded_scene.json" -m lathe.cli wonder check-scene-graph "$EXPANDED_SCENE"
run_step "Build expanded proxy preview Scene Package" "32_expanded_build.txt" -m lathe.cli scene build "$EXPANDED_SCENE" --out "$EXPANDED_BUILD_ROOT" --mode preview
run_step "Validate expanded proxy Scene Package" "33_validate_expanded_package.json" -m lathe.cli scene package validate "$EXPANDED_BUILD_ROOT/alchemist_observatory"

ARTIFACT_EVIDENCE="$EVIDENCE_DIR/34_proxy_artifact_evidence.json"
if [[ "$DRY_RUN" -eq 0 ]]; then
  "$PYTHON" - "$PREVIEW_BUILD_ROOT/alchemist_observatory" "$ARTIFACT_EVIDENCE" <<'PY'
import json
import sys
from pathlib import Path

package_dir = Path(sys.argv[1])
evidence_path = Path(sys.argv[2])
manifest_path = package_dir / "scene_package_manifest.json"
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
scene_plan = json.loads((package_dir / "reports" / "scene_plan.json").read_text(encoding="utf-8"))
export_report = json.loads((package_dir / "reports" / "scene_export_artifacts.json").read_text(encoding="utf-8"))
renders = list(manifest.get("renders", []))
glb_exports = [entry for entry in manifest.get("exports", []) if entry.get("target") == "glb"]
planned_render_tasks = list(scene_plan.get("render_tasks", []))
planned_glb_tasks = [
    entry
    for entry in scene_plan.get("export_tasks", [])
    if entry.get("target") == "glb" or entry.get("format") == "glb"
]
glb_artifacts = [entry for entry in export_report.get("artifacts", []) if entry.get("target") == "glb"]
if not renders:
    raise SystemExit(f"Preview package manifest has no render artifacts: {manifest_path}")
if not glb_exports:
    raise SystemExit(f"Preview package manifest has no GLB export artifact: {manifest_path}")
actual_render_pairs = {
    (entry.get("camera_id"), render_pass)
    for entry in renders
    for render_pass in entry.get("passes", [])
}
for task in planned_render_tasks:
    for render_pass in task.get("passes", []):
        pair = (task.get("camera_id"), render_pass)
        if pair not in actual_render_pairs:
            raise SystemExit(f"Preview package is missing planned render artifact: {pair}")
if len(glb_artifacts) != len(planned_glb_tasks):
    raise SystemExit(
        f"Built GLB artifact count {len(glb_artifacts)} does not match planned GLB export task count "
        f"{len(planned_glb_tasks)}"
    )

def assert_magic(relative_path: str, magic: bytes) -> None:
    artifact_path = package_dir / relative_path
    data = artifact_path.read_bytes()
    if not data.startswith(magic):
        raise SystemExit(f"Artifact magic bytes did not match for: {artifact_path}")

for entry in renders:
    assert_magic(entry["path"], b"\x89PNG\r\n\x1a\n")
for entry in glb_exports:
    assert_magic(entry["path"], b"glTF")
manifest_glb_paths = {entry["path"] for entry in glb_exports}
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

evidence = {
    "schema_version": "lathe.wonder_proxy_artifact_evidence.v1",
    "package": f"{sys.argv[1]}",
    "planned_render_task_count": len(planned_render_tasks),
    "planned_glb_export_task_count": len(planned_glb_tasks),
    "render_count": len(renders),
    "glb_export_count": len(glb_exports),
    "render_paths": [entry["path"] for entry in renders],
    "glb_export_paths": [entry["path"] for entry in glb_exports],
    "glb_identity_statuses": [entry["identity"]["status"] for entry in glb_artifacts],
    "glb_task_ids": [entry["task_id"] for entry in glb_artifacts],
    "status": "passed",
}
evidence_path.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
PY
  echo
  echo "Saved output: $ARTIFACT_EVIDENCE"
fi

echo
if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "Dry run complete. Re-run without --dry-run to execute the Wonder seed scene demo."
else
  echo "Wonder seed scene demo complete."
  echo "Evidence:         $EVIDENCE_DIR"
  echo "Preview package:  $PREVIEW_BUILD_ROOT/alchemist_observatory"
  echo "Patched package:  $PATCHED_BUILD_ROOT/alchemist_observatory"
  echo "Expanded package: $EXPANDED_BUILD_ROOT/alchemist_observatory"
  echo "Before/after:     $BEFORE_AFTER_DIR"
  echo "Proxy artifacts:  $ARTIFACT_EVIDENCE"
fi
