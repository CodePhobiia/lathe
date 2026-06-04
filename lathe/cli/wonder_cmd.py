"""``lathe wonder`` subcommands for Wonder-readiness contracts."""

from __future__ import annotations

import json
from pathlib import Path

from ._common import _dump

_VALIDATION_COMMANDS = {
    "validate-brief": "dream_brief",
    "validate-scene": "scene_graph",
    "validate-patch": "scene_patch",
    "validate-scene-history": "scene_history",
    "validate-camera-lock": "camera_lock",
    "validate-render-comparison": "render_comparison",
    "validate-llm-repair-playbook": "llm_repair_playbook",
    "validate-render-inspection": "render_inspection",
    "validate-world-memory": "world_memory",
    "validate-scene-manifest": "scene_manifest",
    "validate-wonder-report": "wonder_report",
    "validate-plan": "scene_plan",
    "validate-scene-materialization-manifest": "scene_materialization_manifest",
    "validate-scene-assembly": "scene_assembly",
    "validate-scene-branch": "scene_branch",
    "validate-scene-diff": "scene_diff",
    "validate-scene-quality-report": "scene_quality_report",
    "validate-scene-repair-report": "scene_repair_report",
    "validate-scene-benchmark-report": "scene_benchmark_report",
    "validate-style-pack": "style_pack",
    "validate-layout-plan": "layout_plan",
    "validate-game-readiness": "game_readiness",
    "validate-asset-provenance-scene": "asset_provenance_scene",
    "validate-roblox-profile": "roblox_profile",
    "validate-roblox-manifest": "roblox_manifest",
    "validate-roblox-export-bundle": "roblox_export_bundle",
    "validate-roblox-fbx-handoff": "roblox_fbx_handoff",
}

_SCHEMA_CONTRACTS = [
    "dream_brief",
    "scene_graph",
    "scene_patch",
    "scene_history",
    "camera_lock",
    "render_comparison",
    "llm_repair_playbook",
    "render_inspection",
    "world_memory",
    "scene_manifest",
    "wonder_report",
    "scene_package_manifest",
    "scene_plan",
    "scene_materialization_manifest",
    "scene_assembly",
    "scene_branch",
    "scene_diff",
    "scene_quality_report",
    "scene_repair_report",
    "scene_benchmark_report",
    "style_pack",
    "layout_plan",
    "game_readiness",
    "asset_provenance_scene",
    "roblox_profile",
    "roblox_manifest",
    "roblox_export_bundle",
    "roblox_fbx_handoff",
]


def register(sub) -> None:
    """Register Wonder contract subcommands."""
    p_wonder = sub.add_parser(
        "wonder",
        help="Validate Wonder-readiness JSON contracts",
        description=(
            "Validate Dream Brief, Scene Graph, Scene Patch, Render Inspection, "
            "World Memory, Scene Package Manifest, and lightweight brief/scene "
            "consistency contracts."
        ),
    )
    wonder_sub = p_wonder.add_subparsers(dest="wonder_cmd", required=True)

    wonder_sub.add_parser("schemas", help="List supported Wonder contract schemas")
    wonder_sub.add_parser("capabilities", help="Emit machine-readable Wonder capability flags")
    wonder_sub.add_parser("status", help="Emit machine-readable Wonder readiness status")

    p_build_world = wonder_sub.add_parser(
        "build",
        help="Build a deterministic Wonder prompt into a .lthworld skeleton",
    )
    p_build_world.add_argument("prompt", help="Natural-language world prompt")
    p_build_world.add_argument("--out", required=True, help="Output .lthworld directory")
    p_build_world.add_argument("--seed", type=int, default=0, help="World seed")
    p_build_world.add_argument(
        "--dry-run",
        action="store_true",
        help="Resolve prompt and world graph without writing the package",
    )
    p_build_world.add_argument(
        "--deterministic",
        action="store_true",
        help="Record deterministic build mode in evidence",
    )
    p_build_world.add_argument(
        "--evidence-only",
        action="store_true",
        help="Write only current evidence sidecars; real asset packages remain planned",
    )

    p_env_probe = wonder_sub.add_parser(
        "env-probe",
        help="Probe deterministic core and optional Wonder runtimes",
    )
    p_env_probe.add_argument("--out", required=True, help="Output environment probe JSON path")
    p_env_probe.add_argument(
        "--mode",
        choices=["core", "strict"],
        default="core",
        help="core keeps optional runtimes nonblocking; strict marks missing optional runtimes as blocking",
    )

    p_evidence_trace = wonder_sub.add_parser(
        "evidence-trace",
        help="Trace checked Wonder readiness tasks to durable evidence",
    )
    p_evidence_trace.add_argument("--tasks", required=True, help="Wonder task checklist Markdown path")
    p_evidence_trace.add_argument("--evidence", required=True, help="Wonder evidence ledger Markdown path")
    p_evidence_trace.add_argument("--out", required=True, help="Output evidence trace JSON path")

    p_alpha_gate = wonder_sub.add_parser(
        "alpha-gate",
        help="Run the deterministic Wonder alpha gate skeleton",
    )
    p_alpha_gate.add_argument("example_dir", help="Wonder example fixture directory")
    p_alpha_gate.add_argument("--out", required=True, help="Output alpha gate directory")
    p_alpha_gate.add_argument("--tasks", default=None, help="Optional Wonder task checklist Markdown path")
    p_alpha_gate.add_argument("--evidence", default=None, help="Optional Wonder evidence ledger Markdown path")
    p_alpha_gate.add_argument(
        "--mode",
        choices=["core", "strict"],
        default="core",
        help="core keeps optional runtimes nonblocking; strict marks missing optional runtimes as blocking",
    )

    p_readiness_report = wonder_sub.add_parser(
        "readiness-report",
        help="Write the final Project Wonder readiness Markdown and JSON reports",
    )
    p_readiness_report.add_argument("--out", required=True, help="Output readiness Markdown path")
    p_readiness_report.add_argument(
        "--alpha-report",
        default=".tmp_tests/wonder_alpha_gate/reports/final_readiness_report.json",
        help="Existing alpha-gate JSON report; generated from the default example when missing",
    )
    p_readiness_report.add_argument(
        "--alpha-out",
        default=".tmp_tests/wonder_alpha_gate",
        help="Alpha-gate output directory to use when --alpha-report is missing",
    )
    p_readiness_report.add_argument(
        "--example-dir",
        default="examples/wonder/alchemist_observatory",
        help="Wonder example used to generate an alpha report when --alpha-report is missing",
    )
    p_readiness_report.add_argument(
        "--mode",
        choices=["core", "strict"],
        default="core",
        help="core keeps optional runtimes nonblocking; strict marks missing optional runtimes as blocking",
    )

    p_schema = wonder_sub.add_parser("schema", help="Emit one Wonder contract schema")
    p_schema.add_argument("contract", choices=_SCHEMA_CONTRACTS)

    p_brief = wonder_sub.add_parser("validate-brief", help="Validate a Dream Brief JSON file")
    p_brief.add_argument("file")

    p_scene = wonder_sub.add_parser("validate-scene", help="Validate a Scene Graph JSON file")
    p_scene.add_argument("file")

    p_check_scene = wonder_sub.add_parser(
        "check-scene-graph",
        help="Run schema and semantic checks for a Scene Graph JSON file",
    )
    p_check_scene.add_argument("file")

    p_decompose_brief = wonder_sub.add_parser(
        "decompose-brief",
        help="Emit deterministic Dream Brief decomposition JSON",
    )
    p_decompose_brief.add_argument("file")

    p_lower_brief = wonder_sub.add_parser(
        "lower-brief",
        help="Lower a Dream Brief JSON file into an initial Scene Graph JSON file",
    )
    p_lower_brief.add_argument("file")
    p_lower_brief.add_argument("--out", required=True, help="Output Scene Graph JSON path")

    p_brief_to_scene = wonder_sub.add_parser(
        "brief-to-scene",
        help="Convert a Dream Brief JSON file into an initial Scene Graph JSON file",
    )
    p_brief_to_scene.add_argument("file")
    p_brief_to_scene.add_argument("--out", required=True, help="Output Scene Graph JSON path")

    p_check_brief_scene = wonder_sub.add_parser(
        "check-brief-scene",
        help="Run schema, scene semantic, and brief/scene consistency checks",
    )
    p_check_brief_scene.add_argument("brief_file")
    p_check_brief_scene.add_argument("scene_graph_file")

    p_patch = wonder_sub.add_parser("validate-patch", help="Validate a Scene Patch JSON file")
    p_patch.add_argument("file")

    p_scene_history = wonder_sub.add_parser("validate-scene-history", help="Validate a Scene History JSON file")
    p_scene_history.add_argument("file")

    p_camera_lock = wonder_sub.add_parser("validate-camera-lock", help="Validate a Camera Lock JSON file")
    p_camera_lock.add_argument("file")

    p_render_comparison = wonder_sub.add_parser(
        "validate-render-comparison",
        help="Validate a Render Comparison JSON file",
    )
    p_render_comparison.add_argument("file")

    p_llm_repair_playbook = wonder_sub.add_parser(
        "validate-llm-repair-playbook",
        help="Validate an LLM Repair Playbook JSON file",
    )
    p_llm_repair_playbook.add_argument("file")

    p_append_memory_event = wonder_sub.add_parser(
        "append-memory-event",
        help="Append a redacted World Memory event idempotently",
    )
    p_append_memory_event.add_argument("world_memory")
    p_append_memory_event.add_argument("--event", required=True, help="Memory event JSON file")
    p_append_memory_event.add_argument("--idempotency-key", required=True, help="Durable idempotency key")
    p_append_memory_event.add_argument("--out", required=True, help="Output World Memory JSON path")

    p_redact_memory = wonder_sub.add_parser(
        "redact-memory",
        help="Redact secrets and PII from a World Memory-related JSON file",
    )
    p_redact_memory.add_argument("memory")
    p_redact_memory.add_argument("--out", required=True, help="Output redacted JSON path")

    p_apply_patch = wonder_sub.add_parser(
        "apply-patch",
        help="Apply a Scene Patch and update hash-guarded Scene History",
    )
    p_apply_patch.add_argument("scene_graph")
    p_apply_patch.add_argument("patch")
    p_apply_patch.add_argument("--out", required=True, help="Output patched Scene Graph JSON path")
    p_apply_patch.add_argument("--history", required=True, help="Scene History JSON path to create or update")

    p_rollback_scene = wonder_sub.add_parser(
        "rollback-scene",
        help="Rollback a Scene Graph using a hash-guarded Scene History event",
    )
    p_rollback_scene.add_argument("scene_graph")
    p_rollback_scene.add_argument("--history", required=True, help="Scene History JSON path")
    p_rollback_scene.add_argument("--to-event", required=True, help="Scene History event_id to roll back")
    p_rollback_scene.add_argument("--out", required=True, help="Output rolled-back Scene Graph JSON path")

    p_branch_history = wonder_sub.add_parser(
        "branch-history",
        help="Emit branch-scoped World Memory events with linked patch history reports",
    )
    p_branch_history.add_argument("--memory", required=True, help="World Memory JSON path")
    p_branch_history.add_argument("--branch", required=True, help="World Memory branch id")
    p_branch_history.add_argument("--history", default=None, help="Optional Scene History JSON path")
    p_branch_history.add_argument("--out", required=True, help="Output Branch History JSON path")

    p_lock_camera = wonder_sub.add_parser(
        "lock-camera",
        help="Extract a deterministic Camera Lock from a Scene Graph",
    )
    p_lock_camera.add_argument("scene_graph")
    p_lock_camera.add_argument("--camera-id", required=True, help="Scene Graph camera_id to lock")
    p_lock_camera.add_argument("--out", required=True, help="Output Camera Lock JSON path")

    p_compare_renders = wonder_sub.add_parser(
        "compare-renders",
        help="Compare deterministic before/after proxy render PNGs",
    )
    p_compare_renders.add_argument("--before", required=True, help="Before render PNG path")
    p_compare_renders.add_argument("--after", required=True, help="After render PNG path")
    p_compare_renders.add_argument("--camera-lock", default=None, help="Optional Camera Lock JSON path")
    p_compare_renders.add_argument("--out", required=True, help="Output Render Comparison JSON path")

    p_demo_before_after = wonder_sub.add_parser(
        "demo-before-after",
        help="Build a deterministic proxy before/after comparison demo",
    )
    p_demo_before_after.add_argument("example_dir", help="Wonder example fixture directory")
    p_demo_before_after.add_argument("--out", required=True, help="Output before/after demo directory")
    p_demo_before_after.add_argument(
        "--renderer",
        choices=["proxy", "blender"],
        default="proxy",
        help="proxy is the core deterministic local renderer; blender is reserved for optional lanes",
    )
    p_demo_before_after.add_argument(
        "--mode",
        choices=["core", "optional", "strict"],
        default="core",
        help="core keeps external renderers nonblocking; strict requires requested external lanes",
    )
    p_demo_before_after.add_argument("--history", default=None, help="Optional Scene History JSON path to update")
    p_demo_before_after.add_argument("--branch", default="main", help="Branch id for generated reports")
    p_demo_before_after.add_argument("--patch", default=None, help="Scene Patch JSON path")
    p_demo_before_after.add_argument("--camera-id", default="camera_reveal", help="Scene Graph camera_id to compare")

    p_validate_example = wonder_sub.add_parser(
        "validate-example",
        help="Validate a Wonder example golden fixture directory",
    )
    p_validate_example.add_argument("example_dir", help="Wonder example fixture directory")
    p_validate_example.add_argument("--out", default=None, help="Optional output report JSON path")
    p_validate_example.add_argument("--strict", action="store_true", help="Require all normally deferred lanes")
    p_validate_example.add_argument(
        "--allow-deferred-scene-source",
        action="store_true",
        help="Allow truthful scene-source deferral even when --strict is set",
    )
    p_validate_example.add_argument(
        "--write-missing-proxy-evidence",
        action="store_true",
        help="Create or refresh deterministic proxy/example golden fixture artifacts before validating",
    )

    p_catalog_examples = wonder_sub.add_parser(
        "catalog-examples",
        help="Validate and catalog all Wonder example golden fixtures",
    )
    p_catalog_examples.add_argument("examples_root", help="Directory containing Wonder example folders")
    p_catalog_examples.add_argument("--out", required=True, help="Output catalog JSON path")
    p_catalog_examples.add_argument(
        "--markdown-out",
        default=None,
        help="Optional output Markdown path; defaults to the JSON sibling if it already exists",
    )
    p_catalog_examples.add_argument("--strict", action="store_true", help="Require all normally deferred lanes")
    p_catalog_examples.add_argument(
        "--allow-deferred-scene-source",
        action="store_true",
        help="Allow truthful scene-source deferral even when --strict is set",
    )
    p_catalog_examples.add_argument(
        "--write-missing-proxy-evidence",
        action="store_true",
        help="Create or refresh deterministic proxy/example golden fixture artifacts before cataloging",
    )

    p_inspection = wonder_sub.add_parser(
        "validate-render-inspection",
        help="Validate a Render Inspection JSON file",
    )
    p_inspection.add_argument("file")

    p_memory = wonder_sub.add_parser("validate-world-memory", help="Validate a World Memory JSON file")
    p_memory.add_argument("file")
    p_memory.add_argument(
        "--scene-graph",
        default=None,
        help="Optional Scene Graph JSON file for affected_id continuity checks",
    )

    p_scene_manifest = wonder_sub.add_parser("validate-scene-manifest", help="Validate a Scene Manifest JSON file")
    p_scene_manifest.add_argument("file")

    p_wonder_report = wonder_sub.add_parser("validate-wonder-report", help="Validate a Wonder Report JSON file")
    p_wonder_report.add_argument("file")

    p_plan = wonder_sub.add_parser("validate-plan", help="Validate a Scene Plan JSON file")
    p_plan.add_argument("file")

    p_scene_materialization_manifest = wonder_sub.add_parser(
        "validate-scene-materialization-manifest",
        help="Validate a Scene Materialization Manifest JSON file",
    )
    p_scene_materialization_manifest.add_argument("file")

    p_generate_scene_plan = wonder_sub.add_parser(
        "generate-scene-plan",
        help="Generate a deterministic offline Scene Plan from a Dream Brief and optional Scene Graph",
    )
    p_generate_scene_plan.add_argument("dream_brief")
    p_generate_scene_plan.add_argument("--scene-graph", default=None, help="Optional Scene Graph JSON for concrete tasks")
    p_generate_scene_plan.add_argument("--out", required=True, help="Output Scene Plan JSON path")
    p_generate_scene_plan.add_argument("--plan-mode", choices=["preview", "final"], default="preview")
    p_generate_scene_plan.add_argument(
        "--mode",
        choices=["deterministic"],
        default="deterministic",
        help="Wave 4 supports deterministic local generation only",
    )

    p_scene_assembly = wonder_sub.add_parser("validate-scene-assembly", help="Validate a Scene Assembly IR JSON file")
    p_scene_assembly.add_argument("file")

    p_scene_branch = wonder_sub.add_parser("validate-scene-branch", help="Validate a Scene Branch JSON file")
    p_scene_branch.add_argument("file")

    p_scene_diff = wonder_sub.add_parser("validate-scene-diff", help="Validate a Scene Diff JSON file")
    p_scene_diff.add_argument("file")

    p_scene_quality = wonder_sub.add_parser(
        "validate-scene-quality-report",
        help="Validate a Scene Quality Report JSON file",
    )
    p_scene_quality.add_argument("file")

    p_scene_repair = wonder_sub.add_parser(
        "validate-scene-repair-report",
        help="Validate a Scene Repair Report JSON file",
    )
    p_scene_repair.add_argument("file")

    p_scene_benchmark = wonder_sub.add_parser(
        "validate-scene-benchmark-report",
        help="Validate a Scene Benchmark Report JSON file",
    )
    p_scene_benchmark.add_argument("file")

    p_style_pack = wonder_sub.add_parser("validate-style-pack", help="Validate a Style Pack JSON file")
    p_style_pack.add_argument("file")

    p_layout_plan = wonder_sub.add_parser("validate-layout-plan", help="Validate a Layout Plan JSON file")
    p_layout_plan.add_argument("file")

    p_game_readiness = wonder_sub.add_parser("validate-game-readiness", help="Validate a Game Readiness JSON file")
    p_game_readiness.add_argument("file")

    p_asset_provenance = wonder_sub.add_parser(
        "validate-asset-provenance-scene",
        help="Validate an Asset Provenance Scene JSON file",
    )
    p_asset_provenance.add_argument("file")

    p_roblox_profile = wonder_sub.add_parser("validate-roblox-profile", help="Validate a Roblox Profile JSON file")
    p_roblox_profile.add_argument("file")

    p_roblox_manifest = wonder_sub.add_parser("validate-roblox-manifest", help="Validate a Roblox Manifest JSON file")
    p_roblox_manifest.add_argument("file")

    p_roblox_export_bundle = wonder_sub.add_parser(
        "validate-roblox-export-bundle",
        help="Validate a Roblox Export Bundle JSON file",
    )
    p_roblox_export_bundle.add_argument("file")

    p_roblox_fbx_handoff = wonder_sub.add_parser(
        "validate-roblox-fbx-handoff",
        help="Validate a Roblox FBX Handoff JSON file",
    )
    p_roblox_fbx_handoff.add_argument("file")

    p_diagnose_for_llm = wonder_sub.add_parser(
        "diagnose-for-llm",
        help="Compact a Wonder payload, report, diagnostics list, or scene source for LLM repair.",
    )
    p_diagnose_for_llm.add_argument("file")
    p_diagnose_for_llm.add_argument("--contract", default=None, help="Optional contract id for JSON payload validation")
    p_diagnose_for_llm.add_argument("--root", default=None, help="Optional root for scene source/graph path checks")
    p_diagnose_for_llm.add_argument("--max-diagnostics", type=int, default=20)
    p_diagnose_for_llm.add_argument("--out", default=None, help="Optional output path for the summary JSON")

    p_repair_playbook = wonder_sub.add_parser(
        "repair-playbook",
        help="Convert diagnostics into deterministic LLM repair steps",
    )
    p_repair_playbook.add_argument("--diagnostics", required=True, help="Diagnostics JSON, Wonder report, or LLM summary")
    p_repair_playbook.add_argument("--out", required=True, help="Output LLM Repair Playbook JSON path")
    p_repair_playbook.add_argument("--max-diagnostics", type=int, default=20)

    p_apply_semantic_patch = wonder_sub.add_parser(
        "apply-semantic-patch",
        help="Convert a semantic edit request JSON file into a schema-valid Scene Patch.",
    )
    p_apply_semantic_patch.add_argument("request_json")
    p_apply_semantic_patch.add_argument("--scene-graph", default=None, help="Optional Scene Graph JSON for defaults")
    p_apply_semantic_patch.add_argument("--out", required=True, help="Output Scene Patch JSON path")

    p_package = wonder_sub.add_parser(
        "validate-package-manifest",
        help="Validate a Scene Package Manifest JSON file and its package paths",
    )
    p_package.add_argument("file")
    p_package.add_argument(
        "--allow-missing-paths",
        action="store_true",
        help="Validate schema and path safety without requiring referenced package paths to exist",
    )

    p_init_package = wonder_sub.add_parser(
        "init-package",
        help="Create a folder-based Scene Package Manifest skeleton",
    )
    p_init_package.add_argument("package_dir")
    p_init_package.add_argument("--scene-id", required=True)
    p_init_package.add_argument("--package-id", default=None)
    p_init_package.add_argument("--force", action="store_true", help="Overwrite an existing scene_package_manifest.json")


def _run_validate(args, contract_id: str) -> None:
    from ..wonder import get_contract_schema, load_and_validate_contract

    _payload, diagnostics = load_and_validate_contract(contract_id, args.file)
    schema = get_contract_schema(contract_id)
    ok = not diagnostics
    _dump(
        {
            "ok": ok,
            "contract": contract_id,
            "schema_id": schema.get("$id", ""),
            "path": args.file,
            "diagnostics": diagnostics,
        }
    )
    if not ok:
        raise SystemExit(1)


def _run_lower_brief(args) -> None:
    from ..scene import check_scene_graph
    from ..wonder import (
        get_contract_schema,
        load_and_validate_contract,
        lower_dream_brief_to_scene_graph,
        validate_contract,
    )

    brief, brief_diagnostics = load_and_validate_contract("dream_brief", args.file)
    if brief_diagnostics:
        _dump(
            {
                "ok": False,
                "contract": "dream_brief",
                "check": "dream_brief_schema",
                "schema_id": get_contract_schema("dream_brief").get("$id", ""),
                "path": args.file,
                "diagnostics": brief_diagnostics,
            }
        )
        raise SystemExit(1)

    out_path = Path(args.out)
    scene_graph = lower_dream_brief_to_scene_graph(brief)
    diagnostics = validate_contract("scene_graph", scene_graph)
    if not diagnostics:
        diagnostics.extend(check_scene_graph(scene_graph, root=out_path.parent))

    ok = not diagnostics
    if ok:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(scene_graph, indent=2, sort_keys=False) + "\n", encoding="utf-8")

    _dump(
        {
            "ok": ok,
            "contract": "scene_graph",
            "source_contract": "dream_brief",
            "check": "dream_brief_lowering",
            "schema_id": get_contract_schema("scene_graph").get("$id", ""),
            "path": args.file,
            "out": str(out_path),
            "diagnostics": diagnostics,
        }
    )
    if not ok:
        raise SystemExit(1)


def _run_decompose_brief(args) -> None:
    from ..wonder import (
        DECOMPOSITION_SCHEMA_VERSION,
        decompose_dream_brief,
        get_contract_schema,
        load_and_validate_contract,
    )

    brief, brief_diagnostics = load_and_validate_contract("dream_brief", args.file)
    if brief_diagnostics:
        _dump(
            {
                "ok": False,
                "contract": "dream_brief",
                "check": "dream_brief_schema",
                "schema_id": get_contract_schema("dream_brief").get("$id", ""),
                "path": args.file,
                "diagnostics": brief_diagnostics,
            }
        )
        raise SystemExit(1)

    decomposition = decompose_dream_brief(brief).as_dict()
    _dump(
        {
            "ok": True,
            "contract": "dream_brief_decomposition",
            "schema_version": DECOMPOSITION_SCHEMA_VERSION,
            "source_contract": "dream_brief",
            "path": args.file,
            "decomposition": decomposition,
            "diagnostics": [],
        }
    )


def _run_check_scene_graph(args) -> None:
    from ..scene import load_and_check_scene_graph, scene_graph_validation_summary
    from ..wonder import get_contract_schema

    payload, diagnostics = load_and_check_scene_graph(args.file)
    schema = get_contract_schema("scene_graph")
    ok = not diagnostics
    _dump(
        {
            "ok": ok,
            "contract": "scene_graph",
            "check": "scene_graph_semantics",
            "schema_id": schema.get("$id", ""),
            "path": args.file,
            "summary": scene_graph_validation_summary(payload, diagnostics),
            "diagnostics": diagnostics,
        }
    )
    if not ok:
        raise SystemExit(1)


def _run_check_brief_scene(args) -> None:
    from ..wonder import get_contract_schema, load_and_check_brief_scene

    _brief, _scene_graph, diagnostics = load_and_check_brief_scene(args.brief_file, args.scene_graph_file)
    ok = not diagnostics
    _dump(
        {
            "ok": ok,
            "contract": "brief_scene",
            "check": "brief_scene_consistency",
            "brief_schema_id": get_contract_schema("dream_brief").get("$id", ""),
            "scene_schema_id": get_contract_schema("scene_graph").get("$id", ""),
            "brief_path": args.brief_file,
            "scene_graph_path": args.scene_graph_file,
            "diagnostics": diagnostics,
        }
    )
    if not ok:
        raise SystemExit(1)


def _run_validate_package_manifest(args) -> None:
    from ..scene import load_and_validate_scene_package_manifest
    from ..wonder import get_contract_schema

    _payload, diagnostics = load_and_validate_scene_package_manifest(
        args.file,
        require_exists=not args.allow_missing_paths,
    )
    schema = get_contract_schema("scene_package_manifest")
    ok = not diagnostics
    _dump(
        {
            "ok": ok,
            "contract": "scene_package_manifest",
            "schema_id": schema.get("$id", ""),
            "path": args.file,
            "require_exists": not args.allow_missing_paths,
            "diagnostics": diagnostics,
        }
    )
    if not ok:
        raise SystemExit(1)


def _run_validate_world_memory(args) -> None:
    from ..scene.memory import load_and_validate_world_memory
    from ..wonder import get_contract_schema

    _payload, diagnostics = load_and_validate_world_memory(args.file, scene_graph=args.scene_graph)
    schema = get_contract_schema("world_memory")
    ok = not diagnostics
    _dump(
        {
            "ok": ok,
            "contract": "world_memory",
            "check": "world_memory_semantics",
            "schema_id": schema.get("$id", ""),
            "path": args.file,
            "scene_graph": args.scene_graph,
            "diagnostics": diagnostics,
        }
    )
    if not ok:
        raise SystemExit(1)


def _run_validate_scene_assembly(args) -> None:
    from ..scene import validate_scene_assembly_payload
    from ..wonder import get_contract_schema, load_and_validate_contract

    payload, diagnostics = load_and_validate_contract("scene_assembly", args.file)
    if not diagnostics:
        diagnostics.extend(validate_scene_assembly_payload(payload, package_root=Path(args.file).parent))
    schema = get_contract_schema("scene_assembly")
    ok = not diagnostics
    _dump(
        {
            "ok": ok,
            "contract": "scene_assembly",
            "check": "scene_assembly_semantics",
            "schema_id": schema.get("$id", ""),
            "path": args.file,
            "diagnostics": diagnostics,
        }
    )
    if not ok:
        raise SystemExit(1)


def _run_validate_scene_branch(args) -> None:
    from ..scene import validate_scene_branch_payload
    from ..wonder import get_contract_schema, load_and_validate_contract

    payload, diagnostics = load_and_validate_contract("scene_branch", args.file)
    if not diagnostics:
        diagnostics.extend(validate_scene_branch_payload(payload))
    schema = get_contract_schema("scene_branch")
    ok = not diagnostics
    _dump(
        {
            "ok": ok,
            "contract": "scene_branch",
            "check": "scene_branch_semantics",
            "schema_id": schema.get("$id", ""),
            "path": args.file,
            "diagnostics": diagnostics,
        }
    )
    if not ok:
        raise SystemExit(1)


def _run_validate_scene_diff(args) -> None:
    from ..scene import validate_scene_diff_payload
    from ..wonder import get_contract_schema, load_and_validate_contract

    payload, diagnostics = load_and_validate_contract("scene_diff", args.file)
    if not diagnostics:
        diagnostics.extend(validate_scene_diff_payload(payload))
    schema = get_contract_schema("scene_diff")
    ok = not diagnostics
    _dump(
        {
            "ok": ok,
            "contract": "scene_diff",
            "check": "scene_diff_semantics",
            "schema_id": schema.get("$id", ""),
            "path": args.file,
            "diagnostics": diagnostics,
        }
    )
    if not ok:
        raise SystemExit(1)


def _run_validate_scene_history(args) -> None:
    from ..scene.history import validate_scene_history_payload
    from ..wonder import get_contract_schema, load_and_validate_contract

    payload, diagnostics = load_and_validate_contract("scene_history", args.file)
    if not diagnostics:
        diagnostics.extend(validate_scene_history_payload(payload))
    schema = get_contract_schema("scene_history")
    ok = not diagnostics
    _dump(
        {
            "ok": ok,
            "contract": "scene_history",
            "check": "scene_history_semantics",
            "schema_id": schema.get("$id", ""),
            "path": args.file,
            "diagnostics": diagnostics,
        }
    )
    if not ok:
        raise SystemExit(1)


def _run_validate_scene_repair_report(args) -> None:
    from ..scene import validate_scene_repair_report_payload
    from ..wonder import get_contract_schema, load_and_validate_contract

    payload, diagnostics = load_and_validate_contract("scene_repair_report", args.file)
    if not diagnostics:
        diagnostics.extend(validate_scene_repair_report_payload(payload))
    schema = get_contract_schema("scene_repair_report")
    ok = not diagnostics
    _dump(
        {
            "ok": ok,
            "contract": "scene_repair_report",
            "check": "scene_repair_report_semantics",
            "schema_id": schema.get("$id", ""),
            "path": args.file,
            "diagnostics": diagnostics,
        }
    )
    if not ok:
        raise SystemExit(1)


def _run_validate_style_pack(args) -> None:
    from ..scene import validate_style_pack_payload
    from ..wonder import get_contract_schema, load_and_validate_contract

    payload, diagnostics = load_and_validate_contract("style_pack", args.file)
    if not diagnostics:
        diagnostics.extend(validate_style_pack_payload(payload))
    schema = get_contract_schema("style_pack")
    ok = not diagnostics
    _dump(
        {
            "ok": ok,
            "contract": "style_pack",
            "check": "style_pack_semantics",
            "schema_id": schema.get("$id", ""),
            "path": args.file,
            "diagnostics": diagnostics,
        }
    )
    if not ok:
        raise SystemExit(1)


def _run_validate_layout_plan(args) -> None:
    from ..scene import validate_layout_plan_payload
    from ..wonder import get_contract_schema, load_and_validate_contract

    payload, diagnostics = load_and_validate_contract("layout_plan", args.file)
    if not diagnostics:
        diagnostics.extend(validate_layout_plan_payload(payload))
    schema = get_contract_schema("layout_plan")
    ok = not diagnostics
    _dump(
        {
            "ok": ok,
            "contract": "layout_plan",
            "check": "layout_plan_semantics",
            "schema_id": schema.get("$id", ""),
            "path": args.file,
            "diagnostics": diagnostics,
        }
    )
    if not ok:
        raise SystemExit(1)


def _run_validate_game_readiness(args) -> None:
    from ..scene import validate_game_readiness_payload
    from ..wonder import get_contract_schema, load_and_validate_contract

    payload, diagnostics = load_and_validate_contract("game_readiness", args.file)
    if not diagnostics:
        diagnostics.extend(validate_game_readiness_payload(payload))
    schema = get_contract_schema("game_readiness")
    ok = not diagnostics
    _dump(
        {
            "ok": ok,
            "contract": "game_readiness",
            "check": "game_readiness_semantics",
            "schema_id": schema.get("$id", ""),
            "path": args.file,
            "diagnostics": diagnostics,
        }
    )
    if not ok:
        raise SystemExit(1)


def _run_validate_asset_provenance_scene(args) -> None:
    from ..scene import validate_asset_provenance_scene_payload
    from ..wonder import get_contract_schema, load_and_validate_contract

    payload, diagnostics = load_and_validate_contract("asset_provenance_scene", args.file)
    if not diagnostics:
        diagnostics.extend(validate_asset_provenance_scene_payload(payload))
    schema = get_contract_schema("asset_provenance_scene")
    ok = not diagnostics
    _dump(
        {
            "ok": ok,
            "contract": "asset_provenance_scene",
            "check": "asset_provenance_scene_semantics",
            "schema_id": schema.get("$id", ""),
            "path": args.file,
            "diagnostics": diagnostics,
        }
    )
    if not ok:
        raise SystemExit(1)


def _read_llm_input(path: str):
    text = Path(path).read_text(encoding="utf-8-sig")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def _write_optional_json(path: str | None, payload: dict) -> None:
    if path is None:
        return
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def _write_json_file(path: str | Path, payload: dict) -> None:
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def _read_json_object(path: str | Path) -> dict:
    payload = _read_llm_input(str(path))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON file root must be an object: {path}")
    return payload


def _error_diagnostic(code: str, message: str, path: str = "/") -> dict:
    return {
        "code": code,
        "severity": "error",
        "path": path,
        "message": message,
    }


def _emit_wonder_failure(payload: dict) -> None:
    _dump(payload)
    raise SystemExit(1)


def _has_error_diagnostic(diagnostics: list[dict]) -> bool:
    return any(diagnostic.get("severity", "error") == "error" for diagnostic in diagnostics)


def _run_diagnose_for_llm(args) -> None:
    from ..wonder import diagnose_for_llm

    payload = diagnose_for_llm(
        _read_llm_input(args.file),
        contract=args.contract,
        root=args.root,
        max_diagnostics=args.max_diagnostics,
    )
    _write_optional_json(args.out, payload)
    _dump(payload)


def _run_generate_scene_plan(args) -> None:
    from ..scene import load_and_check_scene_graph
    from ..wonder import generate_scene_plan, load_and_validate_contract

    dream_brief, diagnostics = load_and_validate_contract("dream_brief", args.dream_brief)
    if diagnostics:
        _emit_wonder_failure(
            {
                "ok": False,
                "command": "wonder.generate-scene-plan",
                "contract": "dream_brief",
                "path": args.dream_brief,
                "scene_graph": args.scene_graph,
                "out": args.out,
                "written": False,
                "diagnostics": diagnostics,
            }
        )

    scene_graph = None
    if args.scene_graph is not None:
        scene_graph, diagnostics = load_and_check_scene_graph(args.scene_graph)
        if diagnostics:
            _emit_wonder_failure(
                {
                    "ok": False,
                    "command": "wonder.generate-scene-plan",
                    "contract": "scene_graph",
                    "path": args.dream_brief,
                    "scene_graph": args.scene_graph,
                    "out": args.out,
                    "written": False,
                    "diagnostics": diagnostics,
                }
            )

    try:
        plan = generate_scene_plan(dream_brief, scene_graph=scene_graph, mode=args.plan_mode)
    except ValueError as exc:
        _emit_wonder_failure(
            {
                "ok": False,
                "command": "wonder.generate-scene-plan",
                "contract": "scene_plan",
                "path": args.dream_brief,
                "scene_graph": args.scene_graph,
                "out": args.out,
                "written": False,
                "diagnostics": [_error_diagnostic("WONDER_GENERATE_SCENE_PLAN_FAILED", str(exc))],
            }
        )

    _write_json_file(args.out, plan)
    _dump(
        {
            "ok": True,
            "command": "wonder.generate-scene-plan",
            "contract": "scene_plan",
            "path": args.dream_brief,
            "scene_graph": args.scene_graph,
            "out": args.out,
            "written": True,
            "scene_plan": plan,
            "diagnostics": [],
        }
    )


def _run_repair_playbook(args) -> None:
    from ..wonder import build_repair_playbook

    diagnostics_input = _read_llm_input(args.diagnostics)
    if not isinstance(diagnostics_input, dict | list):
        _emit_wonder_failure(
            {
                "ok": False,
                "command": "wonder.repair-playbook",
                "contract": "llm_repair_playbook",
                "path": args.diagnostics,
                "out": args.out,
                "written": False,
                "diagnostics": [
                    _error_diagnostic(
                        "WONDER_REPAIR_PLAYBOOK_INPUT_INVALID",
                        "Diagnostics input must be a JSON object, diagnostics list, Wonder report, or LLM summary.",
                    )
                ],
            }
        )
    try:
        playbook = build_repair_playbook(diagnostics_input, max_diagnostics=args.max_diagnostics)
    except ValueError as exc:
        _emit_wonder_failure(
            {
                "ok": False,
                "command": "wonder.repair-playbook",
                "contract": "llm_repair_playbook",
                "path": args.diagnostics,
                "out": args.out,
                "written": False,
                "diagnostics": [_error_diagnostic("WONDER_REPAIR_PLAYBOOK_FAILED", str(exc))],
            }
        )

    _write_json_file(args.out, playbook)
    _dump(
        {
            "ok": True,
            "command": "wonder.repair-playbook",
            "contract": "llm_repair_playbook",
            "path": args.diagnostics,
            "out": args.out,
            "written": True,
            "repair_playbook": playbook,
            "diagnostics": [],
        }
    )


def _run_apply_semantic_patch(args) -> None:
    from ..scene import load_and_check_scene_graph
    from ..wonder import semantic_patch_request_to_scene_patch

    request_payload = _read_llm_input(args.request_json)
    if not isinstance(request_payload, dict):
        _dump(
            {
                "ok": False,
                "contract": "scene_patch",
                "path": args.request_json,
                "diagnostics": [
                    {
                        "code": "LLM_PATCH_REQUEST_NOT_OBJECT",
                        "severity": "error",
                        "contract": "scene_patch",
                        "path": "/",
                        "message": "Semantic patch request root must be a JSON object.",
                    }
                ],
            }
        )
        raise SystemExit(1)

    scene_graph = None
    diagnostics: list[dict] = []
    if args.scene_graph is not None:
        scene_graph, diagnostics = load_and_check_scene_graph(args.scene_graph)
    if diagnostics:
        _dump(
            {
                "ok": False,
                "contract": "scene_graph",
                "path": args.scene_graph,
                "diagnostics": diagnostics,
            }
        )
        raise SystemExit(1)

    try:
        patch = semantic_patch_request_to_scene_patch(request_payload, scene_graph=scene_graph)
    except ValueError as exc:
        _dump(
            {
                "ok": False,
                "contract": "scene_patch",
                "path": args.request_json,
                "diagnostics": [
                    {
                        "code": "LLM_PATCH_REQUEST_INVALID",
                        "severity": "error",
                        "contract": "scene_patch",
                        "path": "/",
                        "message": str(exc),
                    }
                ],
            }
        )
        raise SystemExit(1) from None

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(patch, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    _dump(
        {
            "ok": True,
            "contract": "scene_patch",
            "path": args.request_json,
            "scene_graph": args.scene_graph,
            "out": str(out_path),
            "patch": patch,
            "diagnostics": [],
        }
    )


def _run_append_memory_event(args) -> None:
    from ..scene.memory import append_memory_event_idempotent, validate_world_memory

    try:
        world_memory = _read_json_object(args.world_memory)
        event = _read_json_object(args.event)
        updated = append_memory_event_idempotent(world_memory, event, args.idempotency_key)
        diagnostics = validate_world_memory(updated)
    except (OSError, ValueError) as exc:
        _emit_wonder_failure(
            {
                "ok": False,
                "command": "wonder.append-memory-event",
                "contract": "world_memory",
                "path": args.world_memory,
                "event": args.event,
                "out": args.out,
                "diagnostics": [_error_diagnostic("WONDER_MEMORY_APPEND_FAILED", str(exc))],
            }
        )
    ok = not diagnostics
    if ok:
        _write_json_file(args.out, updated)
    payload = {
        "ok": ok,
        "command": "wonder.append-memory-event",
        "contract": "world_memory",
        "path": args.world_memory,
        "event": args.event,
        "idempotency_key": args.idempotency_key,
        "out": args.out,
        "written": ok,
        "world_memory": updated,
        "diagnostics": diagnostics,
    }
    if ok:
        _dump(payload)
        return
    _emit_wonder_failure(payload)


def _run_redact_memory(args) -> None:
    from ..scene.memory import redact_memory_payload

    try:
        payload = _read_json_object(args.memory)
        redacted = redact_memory_payload(payload)
    except (OSError, ValueError, TypeError) as exc:
        _emit_wonder_failure(
            {
                "ok": False,
                "command": "wonder.redact-memory",
                "path": args.memory,
                "out": args.out,
                "diagnostics": [_error_diagnostic("WONDER_MEMORY_REDACT_FAILED", str(exc))],
            }
        )
    _write_json_file(args.out, redacted)
    _dump(
        {
            "ok": True,
            "command": "wonder.redact-memory",
            "path": args.memory,
            "out": args.out,
            "written": True,
            "diagnostics": [],
        }
    )


def _run_apply_patch(args) -> None:
    from ..scene import check_scene_graph, load_and_check_scene_graph
    from ..scene.history import (
        append_scene_history_record,
        create_scene_history,
        create_scene_history_record,
        validate_scene_history_payload,
    )
    from ..scene.patch import apply_scene_patch
    from ..wonder import load_and_validate_contract, validate_contract

    scene_graph, diagnostics = load_and_check_scene_graph(args.scene_graph)
    if diagnostics:
        _emit_wonder_failure(
            {
                "ok": False,
                "command": "wonder.apply-patch",
                "contract": "scene_graph",
                "path": args.scene_graph,
                "patch": args.patch,
                "out": args.out,
                "history": args.history,
                "written": False,
                "diagnostics": diagnostics,
            }
        )

    patch_payload, diagnostics = load_and_validate_contract("scene_patch", args.patch)
    if diagnostics:
        _emit_wonder_failure(
            {
                "ok": False,
                "command": "wonder.apply-patch",
                "contract": "scene_patch",
                "path": args.scene_graph,
                "patch": args.patch,
                "out": args.out,
                "history": args.history,
                "written": False,
                "diagnostics": diagnostics,
            }
        )

    result = apply_scene_patch(scene_graph, patch_payload)
    out_path = Path(args.out)
    diagnostics = list(result.diagnostics)
    if not _has_error_diagnostic(diagnostics):
        diagnostics.extend(validate_contract("scene_graph", result.scene_graph))
    if not _has_error_diagnostic(diagnostics):
        diagnostics.extend(check_scene_graph(result.scene_graph, root=out_path.parent))
    ok = not _has_error_diagnostic(diagnostics)

    history_path = Path(args.history)
    history_payload: dict | None = None
    history_record: dict | None = None
    if ok:
        if history_path.exists():
            try:
                history_payload = _read_json_object(history_path)
            except (OSError, ValueError) as exc:
                diagnostics.append(_error_diagnostic("WONDER_SCENE_HISTORY_LOAD_FAILED", str(exc)))
                ok = False
        else:
            history_payload = create_scene_history()
    if ok and history_payload is not None:
        history_diagnostics = validate_scene_history_payload(history_payload)
        diagnostics.extend(history_diagnostics)
        ok = not _has_error_diagnostic(diagnostics)
    if ok and history_payload is not None:
        try:
            history_record = create_scene_history_record(
                scene_graph,
                patch_payload,
                result,
                forward_patch_path=args.patch,
            )
            history_payload = append_scene_history_record(history_payload, history_record)
        except ValueError as exc:
            diagnostics.append(_error_diagnostic("WONDER_SCENE_HISTORY_UPDATE_FAILED", str(exc)))
            ok = False

    written = False
    history_written = False
    if ok and history_payload is not None:
        _write_json_file(out_path, result.scene_graph)
        _write_json_file(history_path, history_payload)
        written = True
        history_written = True

    payload = {
        "ok": ok,
        "command": "wonder.apply-patch",
        "contract": "scene_patch",
        "path": args.scene_graph,
        "patch": args.patch,
        "out": args.out,
        "history": args.history,
        "written": written,
        "history_written": history_written,
        "patch_event": result.patch_event,
        "scene_memory_event": result.scene_memory_event,
        "applied_operations": result.applied_operations,
        "rejected_operations": result.rejected_operations,
        "history_record": history_record,
        "diagnostics": diagnostics,
    }
    if ok:
        _dump(payload)
        return
    _emit_wonder_failure(payload)


def _run_rollback_scene(args) -> None:
    from ..scene import check_scene_graph, load_and_check_scene_graph
    from ..scene.history import validate_scene_history_payload
    from ..scene.rollback import RollbackHashMismatch, rollback_scene
    from ..wonder import validate_contract

    scene_graph, diagnostics = load_and_check_scene_graph(args.scene_graph)
    if diagnostics:
        _emit_wonder_failure(
            {
                "ok": False,
                "command": "wonder.rollback-scene",
                "contract": "scene_graph",
                "path": args.scene_graph,
                "history": args.history,
                "to_event": args.to_event,
                "out": args.out,
                "written": False,
                "diagnostics": diagnostics,
            }
        )

    try:
        history_payload = _read_json_object(args.history)
    except (OSError, ValueError) as exc:
        _emit_wonder_failure(
            {
                "ok": False,
                "command": "wonder.rollback-scene",
                "contract": "scene_history",
                "path": args.scene_graph,
                "history": args.history,
                "to_event": args.to_event,
                "out": args.out,
                "written": False,
                "diagnostics": [_error_diagnostic("WONDER_SCENE_HISTORY_LOAD_FAILED", str(exc))],
            }
        )

    diagnostics = validate_scene_history_payload(history_payload)
    if diagnostics:
        _emit_wonder_failure(
            {
                "ok": False,
                "command": "wonder.rollback-scene",
                "contract": "scene_history",
                "path": args.scene_graph,
                "history": args.history,
                "to_event": args.to_event,
                "out": args.out,
                "written": False,
                "diagnostics": diagnostics,
            }
        )

    try:
        rolled_back = rollback_scene(scene_graph, history_payload, args.to_event)
    except RollbackHashMismatch as exc:
        _emit_wonder_failure(
            {
                "ok": False,
                "command": "wonder.rollback-scene",
                "contract": "scene_history",
                "path": args.scene_graph,
                "history": args.history,
                "to_event": args.to_event,
                "out": args.out,
                "written": False,
                "diagnostics": [_error_diagnostic("WONDER_ROLLBACK_HASH_MISMATCH", str(exc))],
            }
        )
    except ValueError as exc:
        _emit_wonder_failure(
            {
                "ok": False,
                "command": "wonder.rollback-scene",
                "contract": "scene_history",
                "path": args.scene_graph,
                "history": args.history,
                "to_event": args.to_event,
                "out": args.out,
                "written": False,
                "diagnostics": [_error_diagnostic("WONDER_ROLLBACK_FAILED", str(exc))],
            }
        )

    out_path = Path(args.out)
    diagnostics = validate_contract("scene_graph", rolled_back)
    if not diagnostics:
        diagnostics.extend(check_scene_graph(rolled_back, root=out_path.parent))
    ok = not diagnostics
    if ok:
        _write_json_file(out_path, rolled_back)
    payload = {
        "ok": ok,
        "command": "wonder.rollback-scene",
        "contract": "scene_history",
        "path": args.scene_graph,
        "history": args.history,
        "to_event": args.to_event,
        "out": args.out,
        "written": ok,
        "diagnostics": diagnostics,
    }
    if ok:
        _dump(payload)
        return
    _emit_wonder_failure(payload)


def _run_branch_history(args) -> None:
    from ..scene.history import branch_history, validate_scene_history_payload
    from ..scene.memory import load_and_validate_world_memory

    world_memory, diagnostics = load_and_validate_world_memory(args.memory)
    if diagnostics:
        _emit_wonder_failure(
            {
                "ok": False,
                "command": "wonder.branch-history",
                "contract": "world_memory",
                "memory": args.memory,
                "branch": args.branch,
                "history": args.history,
                "out": args.out,
                "written": False,
                "diagnostics": diagnostics,
            }
        )

    history_payload = None
    if args.history is not None:
        try:
            history_payload = _read_json_object(args.history)
        except (OSError, ValueError) as exc:
            _emit_wonder_failure(
                {
                    "ok": False,
                    "command": "wonder.branch-history",
                    "contract": "scene_history",
                    "memory": args.memory,
                    "branch": args.branch,
                    "history": args.history,
                    "out": args.out,
                    "written": False,
                    "diagnostics": [_error_diagnostic("WONDER_SCENE_HISTORY_LOAD_FAILED", str(exc))],
                }
            )
        history_diagnostics = validate_scene_history_payload(history_payload)
        if history_diagnostics:
            _emit_wonder_failure(
                {
                    "ok": False,
                    "command": "wonder.branch-history",
                    "contract": "scene_history",
                    "memory": args.memory,
                    "branch": args.branch,
                    "history": args.history,
                    "out": args.out,
                    "written": False,
                    "diagnostics": history_diagnostics,
                }
            )

    payload = branch_history(world_memory, args.branch, scene_history=history_payload)
    _write_json_file(args.out, payload)
    _dump(
        {
            "ok": True,
            "command": "wonder.branch-history",
            "contract": "scene_branch_history",
            "memory": args.memory,
            "branch": args.branch,
            "history": args.history,
            "out": args.out,
            "written": True,
            "branch_history": payload,
            "diagnostics": [],
        }
    )


def _run_lock_camera(args) -> None:
    from ..scene import load_and_check_scene_graph
    from ..scene.camera_lock import lock_camera

    scene_graph, diagnostics = load_and_check_scene_graph(args.scene_graph)
    if diagnostics:
        _emit_wonder_failure(
            {
                "ok": False,
                "command": "wonder.lock-camera",
                "contract": "scene_graph",
                "path": args.scene_graph,
                "camera_id": args.camera_id,
                "out": args.out,
                "written": False,
                "diagnostics": diagnostics,
            }
        )

    camera_lock, diagnostics = lock_camera(scene_graph, args.camera_id)
    ok = camera_lock is not None and not diagnostics
    if ok:
        _write_json_file(args.out, camera_lock)
    payload = {
        "ok": ok,
        "command": "wonder.lock-camera",
        "contract": "camera_lock",
        "path": args.scene_graph,
        "camera_id": args.camera_id,
        "out": args.out,
        "written": ok,
        "camera_lock": camera_lock,
        "diagnostics": diagnostics,
    }
    if ok:
        _dump(payload)
        return
    _emit_wonder_failure(payload)


def _run_compare_renders(args) -> None:
    from ..scene.compare import compare_renders
    from ..wonder import load_and_validate_contract

    camera_lock = None
    if args.camera_lock is not None:
        camera_lock, diagnostics = load_and_validate_contract("camera_lock", args.camera_lock)
        if diagnostics:
            _emit_wonder_failure(
                {
                    "ok": False,
                    "command": "wonder.compare-renders",
                    "contract": "camera_lock",
                    "before": args.before,
                    "after": args.after,
                    "camera_lock": args.camera_lock,
                    "out": args.out,
                    "written": False,
                    "diagnostics": diagnostics,
                }
            )

    comparison, diagnostics = compare_renders(args.before, args.after, camera_lock=camera_lock)
    ok = comparison is not None and not diagnostics
    if ok:
        _write_json_file(args.out, comparison)
    payload = {
        "ok": ok,
        "command": "wonder.compare-renders",
        "contract": "render_comparison",
        "before": args.before,
        "after": args.after,
        "camera_lock": args.camera_lock,
        "out": args.out,
        "written": ok,
        "comparison": comparison,
        "diagnostics": diagnostics,
    }
    if ok:
        _dump(payload)
        return
    _emit_wonder_failure(payload)


def _render_report_artifact_path(package_root: Path, report: dict, *, camera_id: str, render_pass: str) -> Path:
    for artifact in report.get("artifacts", []):
        if not isinstance(artifact, dict):
            continue
        if artifact.get("camera_id") == camera_id and artifact.get("render_pass") == render_pass:
            path = artifact.get("path")
            if isinstance(path, str):
                return package_root / path
    raise ValueError(f"Render report does not contain {render_pass!r} pass for camera {camera_id!r}.")


def _before_after_report_markdown(report: dict) -> str:
    optional_lanes = report.get("optional_lanes", {})
    comparison = report.get("comparison", {})
    pixel_delta = comparison.get("pixel_delta", {}) if isinstance(comparison, dict) else {}
    return "\n".join(
        [
            "# Wonder Before/After Report",
            "",
            f"- Status: {report.get('status', 'unknown')}",
            f"- Renderer: {report.get('renderer', 'unknown')}",
            f"- Mode: {report.get('mode', 'unknown')}",
            f"- Camera: {report.get('camera_id', 'unknown')}",
            f"- Changed pixels: {pixel_delta.get('changed_pixels', 'unknown')}",
            f"- Changed ratio: {pixel_delta.get('changed_ratio', 'unknown')}",
            f"- Blender lane: {optional_lanes.get('blender', {}).get('status', 'unknown')}",
            f"- Roblox lane: {optional_lanes.get('roblox', {}).get('status', 'unknown')}",
            "",
        ]
    )


def _run_demo_before_after(args) -> None:
    from ..scene import SceneArtifactError, check_scene_graph, load_and_check_scene_graph, render_scene_graph
    from ..scene.camera_lock import lock_camera
    from ..scene.compare import compare_renders
    from ..scene.history import (
        append_scene_history_record,
        create_scene_history,
        create_scene_history_record,
        validate_scene_history_payload,
    )
    from ..scene.patch import apply_scene_patch
    from ..wonder import load_and_validate_contract, validate_contract

    if args.renderer != "proxy":
        _emit_wonder_failure(
            {
                "ok": False,
                "command": "wonder.demo-before-after",
                "contract": "render_comparison",
                "example_dir": args.example_dir,
                "out": args.out,
                "written": False,
                "diagnostics": [
                    _error_diagnostic(
                        "WONDER_DEMO_RENDERER_UNAVAILABLE",
                        (
                            "Only the deterministic proxy renderer is available in Wave 3 core mode; "
                            f"requested {args.renderer!r}."
                        ),
                    )
                ],
            }
        )

    example_dir = Path(args.example_dir)
    out_root = Path(args.out)
    before_dir = out_root / "before"
    after_dir = out_root / "after"
    comparisons_dir = out_root / "comparisons"
    history_dir = out_root / "history"
    reports_dir = out_root / "reports"
    scene_path = example_dir / "scene_graph.json"
    if args.patch is not None:
        patch_path = Path(args.patch)
    else:
        patch_path = example_dir / "scene_patch.example.json"
        if not patch_path.exists():
            patch_path = example_dir / "scene_patch_more_sacred.json"
    demo_history_path = history_dir / "scene_history.json"
    history_path = Path(args.history) if args.history is not None else demo_history_path

    scene_graph, diagnostics = load_and_check_scene_graph(scene_path)
    if diagnostics:
        _emit_wonder_failure(
            {
                "ok": False,
                "command": "wonder.demo-before-after",
                "contract": "scene_graph",
                "example_dir": args.example_dir,
                "out": args.out,
                "written": False,
                "diagnostics": diagnostics,
            }
        )

    patch_payload, diagnostics = load_and_validate_contract("scene_patch", patch_path)
    if diagnostics:
        _emit_wonder_failure(
            {
                "ok": False,
                "command": "wonder.demo-before-after",
                "contract": "scene_patch",
                "example_dir": args.example_dir,
                "patch": str(patch_path),
                "out": args.out,
                "written": False,
                "diagnostics": diagnostics,
            }
        )

    camera_lock, diagnostics = lock_camera(scene_graph, args.camera_id)
    if camera_lock is None or diagnostics:
        _emit_wonder_failure(
            {
                "ok": False,
                "command": "wonder.demo-before-after",
                "contract": "camera_lock",
                "example_dir": args.example_dir,
                "patch": str(patch_path),
                "camera_id": args.camera_id,
                "out": args.out,
                "written": False,
                "diagnostics": diagnostics,
            }
        )

    patch_result = apply_scene_patch(scene_graph, patch_payload)
    diagnostics = list(patch_result.diagnostics)
    if not _has_error_diagnostic(diagnostics):
        diagnostics.extend(validate_contract("scene_graph", patch_result.scene_graph))
    if not _has_error_diagnostic(diagnostics):
        diagnostics.extend(check_scene_graph(patch_result.scene_graph, root=after_dir))
    if _has_error_diagnostic(diagnostics):
        _emit_wonder_failure(
            {
                "ok": False,
                "command": "wonder.demo-before-after",
                "contract": "scene_patch",
                "example_dir": args.example_dir,
                "patch": str(patch_path),
                "out": args.out,
                "written": False,
                "diagnostics": diagnostics,
            }
        )

    try:
        beauty_layer = "beauty"
        before_render_report = render_scene_graph(
            scene_graph,
            before_dir,
            mode="preview",
            camera_id=args.camera_id,
            passes=[beauty_layer],
            resolution=[640, 360],
            include_topdown=False,
        )
        after_render_report = render_scene_graph(
            patch_result.scene_graph,
            after_dir,
            mode="preview",
            camera_id=args.camera_id,
            passes=[beauty_layer],
            resolution=[640, 360],
            include_topdown=False,
        )
        before_render_path = _render_report_artifact_path(
            before_dir,
            before_render_report,
            camera_id=args.camera_id,
            render_pass=beauty_layer,
        )
        after_render_path = _render_report_artifact_path(
            after_dir,
            after_render_report,
            camera_id=args.camera_id,
            render_pass=beauty_layer,
        )
    except SceneArtifactError as exc:
        _emit_wonder_failure(
            {
                "ok": False,
                "command": "wonder.demo-before-after",
                "contract": "scene_render",
                "example_dir": args.example_dir,
                "patch": str(patch_path),
                "out": args.out,
                "written": False,
                "diagnostics": exc.diagnostics,
            }
        )
    except (OSError, ValueError) as exc:
        _emit_wonder_failure(
            {
                "ok": False,
                "command": "wonder.demo-before-after",
                "contract": "scene_render",
                "example_dir": args.example_dir,
                "patch": str(patch_path),
                "out": args.out,
                "written": False,
                "diagnostics": [_error_diagnostic("WONDER_DEMO_RENDER_FAILED", str(exc))],
            }
        )

    comparison, diagnostics = compare_renders(before_render_path, after_render_path, camera_lock=camera_lock)
    if comparison is None or diagnostics:
        _emit_wonder_failure(
            {
                "ok": False,
                "command": "wonder.demo-before-after",
                "contract": "render_comparison",
                "example_dir": args.example_dir,
                "patch": str(patch_path),
                "out": args.out,
                "written": False,
                "diagnostics": diagnostics,
            }
        )

    validation_reports = [
        {"stage": "before_scene_graph", "status": "passed", "diagnostics": []},
        {"stage": "after_scene_graph", "status": "passed", "diagnostics": []},
    ]
    history_record = create_scene_history_record(
        scene_graph,
        patch_payload,
        patch_result,
        forward_patch_path=str(patch_path),
        validation_reports=validation_reports,
        render_reports=[before_render_report, after_render_report],
        comparison_reports=[comparison],
    )
    if history_path.exists():
        try:
            history_payload = _read_json_object(history_path)
        except (OSError, ValueError) as exc:
            _emit_wonder_failure(
                {
                    "ok": False,
                    "command": "wonder.demo-before-after",
                    "contract": "scene_history",
                    "history": str(history_path),
                    "out": args.out,
                    "written": False,
                    "diagnostics": [_error_diagnostic("WONDER_SCENE_HISTORY_LOAD_FAILED", str(exc))],
                }
            )
    else:
        history_payload = create_scene_history()
    history_diagnostics = validate_scene_history_payload(history_payload)
    if history_diagnostics:
        _emit_wonder_failure(
            {
                "ok": False,
                "command": "wonder.demo-before-after",
                "contract": "scene_history",
                "history": str(history_path),
                "out": args.out,
                "written": False,
                "diagnostics": history_diagnostics,
            }
        )
    history_payload = append_scene_history_record(history_payload, history_record)

    optional_lanes = {
        "blender": {
            "status": "skipped",
            "blocking": args.mode == "strict",
            "reason": "Blender-backed comparison is outside Wave 3 core mode.",
        },
        "roblox": {
            "status": "skipped",
            "blocking": False,
            "reason": "Roblox Studio is not part of the Wave 3 before/after comparison lane.",
        },
    }
    before_scene_path = before_dir / "scene_graph.json"
    after_scene_path = after_dir / "scene_graph.json"
    camera_lock_path = comparisons_dir / "camera_lock.json"
    comparison_path = comparisons_dir / "render_comparison.json"
    report_path = reports_dir / "before_after_report.json"
    report_md_path = reports_dir / "before_after_report.md"
    report = {
        "schema_version": "lathe.before_after_report.v1",
        "ok": True,
        "status": "passed",
        "renderer": args.renderer,
        "mode": args.mode,
        "branch": args.branch,
        "camera_id": args.camera_id,
        "patch": str(patch_path),
        "paths": {
            "before_scene_graph": str(before_scene_path),
            "after_scene_graph": str(after_scene_path),
            "before_render": str(before_render_path),
            "after_render": str(after_render_path),
            "camera_lock": str(camera_lock_path),
            "comparison": str(comparison_path),
            "history": str(history_path),
            "report": str(report_path),
        },
        "optional_lanes": optional_lanes,
        "camera_lock": camera_lock,
        "comparison": comparison,
        "history_record": history_record,
        "diagnostics": [],
    }

    _write_json_file(before_scene_path, scene_graph)
    _write_json_file(after_scene_path, patch_result.scene_graph)
    _write_json_file(camera_lock_path, camera_lock)
    _write_json_file(comparison_path, comparison)
    _write_json_file(history_path, history_payload)
    if history_path.resolve(strict=False) != demo_history_path.resolve(strict=False):
        _write_json_file(demo_history_path, history_payload)
        report["paths"]["demo_history"] = str(demo_history_path)
    _write_json_file(report_path, report)
    report_md_path.parent.mkdir(parents=True, exist_ok=True)
    report_md_path.write_text(_before_after_report_markdown(report), encoding="utf-8")

    _dump(
        {
            "ok": True,
            "command": "wonder.demo-before-after",
            "contract": "render_comparison",
            "example_dir": args.example_dir,
            "out": args.out,
            "written": True,
            "paths": report["paths"],
            "optional_lanes": optional_lanes,
            "comparison": comparison,
            "diagnostics": [],
        }
    )


def _run_init_package(args) -> None:
    from ..scene import init_scene_package

    manifest_path, manifest = init_scene_package(
        args.package_dir,
        scene_id=args.scene_id,
        package_id=args.package_id,
        overwrite=args.force,
    )
    _dump(
        {
            "ok": True,
            "contract": "scene_package_manifest",
            "package_dir": args.package_dir,
            "manifest_path": str(manifest_path),
            "manifest": manifest,
            "diagnostics": [],
        }
    )


def _run_env_probe(args) -> None:
    from ..wonder import probe_wonder_environment

    payload = probe_wonder_environment(mode=args.mode)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    _dump(payload)
    if not payload.get("ok", False):
        raise SystemExit(1)


def _run_evidence_trace(args) -> None:
    from ..wonder import write_evidence_trace

    payload = write_evidence_trace(args.tasks, args.evidence, args.out)
    _dump(payload)
    if not payload.get("ok", False):
        raise SystemExit(1)


def _run_alpha_gate(args) -> None:
    from ..wonder import build_alpha_gate_report

    payload = build_alpha_gate_report(
        args.example_dir,
        args.out,
        tasks_path=args.tasks,
        evidence_path=args.evidence,
        mode=args.mode,
    )
    _dump(payload)
    if not payload.get("ok", False):
        raise SystemExit(1)


def _run_readiness_report(args) -> None:
    from ..wonder import build_alpha_gate_report, write_readiness_report_files

    alpha_report_path = Path(args.alpha_report)
    if alpha_report_path.exists():
        alpha_report = _read_json_object(alpha_report_path)
    else:
        alpha_report = build_alpha_gate_report(
            args.example_dir,
            args.alpha_out,
            mode=args.mode,
        )
    payload = write_readiness_report_files(args.out, alpha_report)
    _dump(payload)
    if not payload.get("ok", False):
        raise SystemExit(1)


def _allow_deferred_scene_source(args) -> bool:
    return bool(args.allow_deferred_scene_source) or not bool(args.strict)


def _run_validate_example(args) -> None:
    from ..wonder import validate_wonder_example

    payload = validate_wonder_example(
        args.example_dir,
        strict=args.strict,
        allow_deferred_scene_source=_allow_deferred_scene_source(args),
        write_missing_proxy_evidence=args.write_missing_proxy_evidence,
    )
    if args.out is not None:
        _write_json_file(args.out, payload)
    _dump(payload)
    if not payload.get("ok", False):
        raise SystemExit(1)


def _run_catalog_examples(args) -> None:
    from ..wonder import catalog_wonder_examples, render_example_catalog_markdown

    payload = catalog_wonder_examples(
        args.examples_root,
        strict=args.strict,
        allow_deferred_scene_source=_allow_deferred_scene_source(args),
        write_missing_proxy_evidence=args.write_missing_proxy_evidence,
        include_reports=True,
    )
    out_path = Path(args.out)
    catalog_payload = {key: value for key, value in payload.items() if key != "reports"}
    _write_json_file(out_path, catalog_payload)
    markdown_out = Path(args.markdown_out) if args.markdown_out is not None else None
    if markdown_out is None:
        candidate = out_path.with_suffix(".md")
        if candidate.exists():
            markdown_out = candidate
    if markdown_out is not None:
        markdown_out.parent.mkdir(parents=True, exist_ok=True)
        markdown_out.write_text(render_example_catalog_markdown(catalog_payload), encoding="utf-8")
    output = {
        "ok": payload["summary"]["failed"] == 0,
        "command": "wonder.catalog-examples",
        "out": str(out_path),
        "markdown_out": str(markdown_out) if markdown_out is not None else None,
        "summary": payload["summary"],
        "diagnostics": [
            diagnostic
            for report in payload.get("reports", [])
            if isinstance(report, dict)
            for diagnostic in report.get("diagnostics", [])
            if isinstance(diagnostic, dict)
        ],
    }
    _dump(output)
    if not output["ok"]:
        raise SystemExit(1)


def _run_build_world(args) -> None:
    from ..asset_foundry.world_writer import write_lthworld
    from ..forge import compose_world
    from ..wonder.prompt_parser import parse_wonder_prompt

    parsed = parse_wonder_prompt(args.prompt, seed=int(args.seed))
    composition = compose_world(parsed.to_skyborne_intent(), seed=int(args.seed))
    payload = {
        "prompt_request": parsed.to_dict(),
        "world_graph_summary": {
            "world_id": composition.world_id,
            "asset_count": composition.asset_count(),
            "role_counts": composition.role_counts(),
            "style_pack_ids": list(composition.style_pack_ids()),
            "path_node_count": len(composition.path_nodes),
            "path_edge_count": len(composition.path_edges),
            "hazard_zone_count": len(composition.hazard_zones),
            "quest_anchor_count": len(composition.quest_anchors),
            "diagnostics": [dict(d) for d in composition.diagnostics],
        },
    }
    if args.dry_run:
        payload.update(
            {
                "written": False,
                "certified": False,
                "certification_status": "dry_run",
            }
        )
        _dump(payload)
        return

    mode_bits = ["skeleton"]
    if args.deterministic:
        mode_bits.append("deterministic")
    if args.evidence_only:
        mode_bits.append("evidence_only")
    result = write_lthworld(
        composition,
        Path(args.out),
        package_members=not args.evidence_only,
        mode="+".join(mode_bits),
    )
    payload.update(
        {
            "written": True,
            "world_package": result.to_dict(),
            "certified": result.certified,
            "certification_status": result.certification_status,
        }
    )
    _dump(payload)


def run_wonder(args) -> None:
    """Dispatch ``lathe wonder`` subcommands."""
    from ..wonder import get_contract_schema, list_contract_summaries, wonder_capabilities, wonder_status

    if args.wonder_cmd == "build":
        _run_build_world(args)
        return
    if args.wonder_cmd == "schemas":
        _dump({"contracts": list_contract_summaries()})
        return
    if args.wonder_cmd == "capabilities":
        _dump(wonder_capabilities())
        return
    if args.wonder_cmd == "status":
        _dump(wonder_status())
        return
    if args.wonder_cmd == "env-probe":
        _run_env_probe(args)
        return
    if args.wonder_cmd == "evidence-trace":
        _run_evidence_trace(args)
        return
    if args.wonder_cmd == "alpha-gate":
        _run_alpha_gate(args)
        return
    if args.wonder_cmd == "readiness-report":
        _run_readiness_report(args)
        return
    if args.wonder_cmd == "validate-example":
        _run_validate_example(args)
        return
    if args.wonder_cmd == "catalog-examples":
        _run_catalog_examples(args)
        return
    if args.wonder_cmd == "schema":
        _dump(get_contract_schema(args.contract))
        return
    if args.wonder_cmd == "check-scene-graph":
        _run_check_scene_graph(args)
        return
    if args.wonder_cmd == "check-brief-scene":
        _run_check_brief_scene(args)
        return
    if args.wonder_cmd == "decompose-brief":
        _run_decompose_brief(args)
        return
    if args.wonder_cmd == "validate-package-manifest":
        _run_validate_package_manifest(args)
        return
    if args.wonder_cmd == "validate-world-memory":
        _run_validate_world_memory(args)
        return
    if args.wonder_cmd == "validate-scene-assembly":
        _run_validate_scene_assembly(args)
        return
    if args.wonder_cmd == "validate-scene-branch":
        _run_validate_scene_branch(args)
        return
    if args.wonder_cmd == "validate-scene-diff":
        _run_validate_scene_diff(args)
        return
    if args.wonder_cmd == "validate-scene-history":
        _run_validate_scene_history(args)
        return
    if args.wonder_cmd == "validate-scene-repair-report":
        _run_validate_scene_repair_report(args)
        return
    if args.wonder_cmd == "validate-style-pack":
        _run_validate_style_pack(args)
        return
    if args.wonder_cmd == "validate-layout-plan":
        _run_validate_layout_plan(args)
        return
    if args.wonder_cmd == "validate-game-readiness":
        _run_validate_game_readiness(args)
        return
    if args.wonder_cmd == "validate-asset-provenance-scene":
        _run_validate_asset_provenance_scene(args)
        return
    if args.wonder_cmd == "diagnose-for-llm":
        _run_diagnose_for_llm(args)
        return
    if args.wonder_cmd == "generate-scene-plan":
        _run_generate_scene_plan(args)
        return
    if args.wonder_cmd == "repair-playbook":
        _run_repair_playbook(args)
        return
    if args.wonder_cmd == "apply-semantic-patch":
        _run_apply_semantic_patch(args)
        return
    if args.wonder_cmd == "append-memory-event":
        _run_append_memory_event(args)
        return
    if args.wonder_cmd == "redact-memory":
        _run_redact_memory(args)
        return
    if args.wonder_cmd == "apply-patch":
        _run_apply_patch(args)
        return
    if args.wonder_cmd == "rollback-scene":
        _run_rollback_scene(args)
        return
    if args.wonder_cmd == "branch-history":
        _run_branch_history(args)
        return
    if args.wonder_cmd == "lock-camera":
        _run_lock_camera(args)
        return
    if args.wonder_cmd == "compare-renders":
        _run_compare_renders(args)
        return
    if args.wonder_cmd == "demo-before-after":
        _run_demo_before_after(args)
        return
    if args.wonder_cmd == "init-package":
        _run_init_package(args)
        return
    if args.wonder_cmd in {"brief-to-scene", "lower-brief"}:
        _run_lower_brief(args)
        return
    contract_id = _VALIDATION_COMMANDS.get(args.wonder_cmd)
    if contract_id:
        _run_validate(args, contract_id)
        return
    raise SystemExit(2)
